"""
Tests for the host allowlist, the Origin check and the token.

These are the checks that decide who can drive this application, so each one is
tested in both directions: the request that must be allowed, and the request
that must not. A security check that only ever gets tested with valid input is
a security check nobody has actually tested.

The Codespaces support is here because of a real failure. Run inside a GitHub
Codespace, the app binds to 127.0.0.1 as always, GitHub forwards the port over
HTTPS, and the browser arrives with `Host: <name>-<port>.app.github.dev`. The
loopback-only allowlist rejected every one of those with a 421 — the app was
simply unusable there, and the message blamed the user's URL.

Recognising that host must not weaken the thing the allowlist exists for. The
forwarded name is taken from the environment, never from the request, because a
Host header is attacker-controlled and the entire point of the allowlist is
that it is not.

Run: python3 tests/test_security.py
"""

from __future__ import annotations

import os
import sys
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import security  # noqa: E402

FAILURES: list[str] = []
CHECKS = 0

CODESPACE = "legendary-barnacle-qvvv4xqq6q66hj4w"
FORWARDED = f"{CODESPACE}-8765.app.github.dev"


def check(label: str, got, want) -> None:
    global CHECKS
    CHECKS += 1
    if got != want:
        FAILURES.append(f"{label}\n     got: {got!r}\n    want: {want!r}")


def contains(label: str, haystack, needle: str) -> None:
    global CHECKS
    CHECKS += 1
    if needle.lower() not in str(haystack or "").lower():
        FAILURES.append(f"{label}\n    {needle!r} not in {str(haystack)[:300]!r}")


@contextmanager
def codespace(name: str = CODESPACE, domain: str = "app.github.dev"):
    """Run a block as though inside a Codespace, then put the environment back."""
    saved = {k: os.environ.get(k) for k in
             ("CODESPACES", "CODESPACE_NAME",
              "GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN")}
    os.environ["CODESPACES"] = "true"
    os.environ["CODESPACE_NAME"] = name
    os.environ["GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN"] = domain
    try:
        yield
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


@contextmanager
def not_a_codespace():
    saved = {k: os.environ.get(k) for k in
             ("CODESPACES", "CODESPACE_NAME",
              "GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN")}
    for key in saved:
        os.environ.pop(key, None)
    try:
        yield
    finally:
        for key, value in saved.items():
            if value is not None:
                os.environ[key] = value


# ------------------------------------------------------------ the local case


def test_loopback_hosts_are_allowed() -> None:
    with not_a_codespace():
        config = security.SecurityConfig("tok", "127.0.0.1", 8765)
        # [::1]:8765 is the form a browser sends when localhost resolves to
        # IPv6, and stripping the brackets before the port used to leave
        # "::1]:8765" — locking those machines out with a 421.
        for header in ("127.0.0.1:8765", "localhost:8765", "localhost",
                       "[::1]:8765", "[::1]", "::1", "0.0.0.0:8765",
                       "LOCALHOST:8765"):
            check(f"{header} allowed", config.host_allowed(header), True)


def test_an_unknown_host_is_refused() -> None:
    """The DNS-rebinding defence. A page on evil.test whose DNS points at
    127.0.0.1 reaches this app with Host: evil.test."""
    with not_a_codespace():
        config = security.SecurityConfig("tok", "127.0.0.1", 8765)
        for header in ("evil.test", "evil.test:8765", "", "127.0.0.1.evil.test",
                       "localhost.evil.test", "[dead:beef::1]:8765",
                       "dead:beef::1", "[]", "evil.test, localhost"):
            check(f"{header!r} refused", config.host_allowed(header), False)


def test_the_token_compare_is_constant_time_and_rejects_empties() -> None:
    config = security.SecurityConfig("s3cret", "127.0.0.1", 8765)
    check("correct token", config.token_valid("s3cret"), True)
    check("wrong token", config.token_valid("s3crea"), False)
    check("empty token", config.token_valid(""), False)
    check("prefix of the token", config.token_valid("s3cre"), False)


def test_a_local_run_advertises_localhost() -> None:
    with not_a_codespace():
        config = security.SecurityConfig("tok", "127.0.0.1", 8765)
        check("no codespace host", config.codespace, "")
        check("url", config.public_url(), "http://localhost:8765/")


# -------------------------------------------------------- the Codespaces case


def test_the_forwarded_host_is_allowed_inside_a_codespace() -> None:
    with codespace():
        config = security.SecurityConfig("tok", "127.0.0.1", 8765)
        check("forwarded host allowed", config.host_allowed(FORWARDED), True)
        check("and with a port suffix",
              config.host_allowed(f"{FORWARDED}:443"), True)
        check("localhost still allowed",
              config.host_allowed("localhost:8765"), True)
        check("url is the https one", config.public_url(),
              f"https://{FORWARDED}/")


def test_the_forwarded_host_is_not_allowed_outside_one() -> None:
    """Nothing may be inferred from the request itself."""
    with not_a_codespace():
        config = security.SecurityConfig("tok", "127.0.0.1", 8765)
        check("refused", config.host_allowed(FORWARDED), False)


def test_only_this_codespace_and_this_port_are_allowed() -> None:
    with codespace():
        config = security.SecurityConfig("tok", "127.0.0.1", 8765)
        for header, why in [
            (f"{CODESPACE}-9999.app.github.dev", "a different port"),
            ("someone-elses-codespace-8765.app.github.dev", "another codespace"),
            (f"{CODESPACE}-8765.app.github.dev.evil.test", "a suffix attack"),
            (f"evil.test/{FORWARDED}", "a path-shaped spoof"),
            ("app.github.dev", "the bare domain"),
        ]:
            check(f"{why} refused", config.host_allowed(header), False)


def test_moving_port_moves_the_allowed_host() -> None:
    """`run()` lands on 8766 when 8765 is busy, and the forwarded name embeds
    the port. A stale entry would reject every request and blame the URL."""
    with codespace():
        config = security.SecurityConfig("tok", "127.0.0.1", 8765)
        config.rebind(8766)
        moved = f"{CODESPACE}-8766.app.github.dev"
        check("new port allowed", config.host_allowed(moved), True)
        check("old port no longer allowed", config.host_allowed(FORWARDED), False)
        check("url follows", config.public_url(), f"https://{moved}/")
        check("localhost unaffected", config.host_allowed("localhost"), True)


def test_rebinding_to_the_same_port_is_a_no_op() -> None:
    with codespace():
        config = security.SecurityConfig("tok", "127.0.0.1", 8765)
        config.rebind(8765)
        check("still allowed", config.host_allowed(FORWARDED), True)


def test_a_half_configured_codespace_is_not_treated_as_one() -> None:
    """CODESPACES set without a name must not produce a wildcard host."""
    with codespace(name=""):
        config = security.SecurityConfig("tok", "127.0.0.1", 8765)
        check("no codespace host", config.codespace, "")
        check("nothing extra allowed", config.host_allowed(FORWARDED), False)
        check("falls back to localhost", config.public_url(),
              "http://localhost:8765/")


def test_the_banner_states_the_codespaces_boundary() -> None:
    """The security model genuinely differs there, so the banner must say so
    rather than repeating the localhost reassurance, which would be false."""
    with codespace():
        config = security.SecurityConfig("tok", "127.0.0.1", 8765)
        banner = security.startup_banner(config, [])
        contains("names the https URL", banner, f"https://{FORWARDED}/")
        contains("says it is a codespace", banner, "GitHub Codespace")
        contains("explains port visibility", banner, "Private")
        contains("warns about Public", banner, "anyone with the URL")
        contains("warns tokens leak in URLs", banner, "leaks into history")
        contains("warns the data is ephemeral", banner, "deleted when the")
        for phrase in ("not reachable from your network", "Localhost only"):
            check(f"does not claim {phrase!r}", phrase in banner, False)


def test_the_local_banner_still_says_localhost() -> None:
    with not_a_codespace():
        config = security.SecurityConfig("tok", "127.0.0.1", 8765)
        banner = security.startup_banner(config, [])
        contains("localhost stated", banner, "localhost only")
        check("no codespaces text", "Codespace" in banner, False)


def test_a_codespace_binds_wide_enough_to_be_forwarded() -> None:
    """GitHub's own guidance is that a forwarded app listens on 0.0.0.0.

    A service bound only to loopback is unreliably detected by the port
    forwarder, and the symptom is a 404 on the *.app.github.dev URL while the
    application sits there serving happily — nothing in either place points at
    the other.

    Outside a codespace the bind must stay on loopback, and an explicit
    RESEARCH_SUITE_HOST must win in both cases.
    """
    from app import settings as settings_module

    with not_a_codespace():
        os.environ.pop("RESEARCH_SUITE_HOST", None)
        check("loopback by default", settings_module.load().host, "127.0.0.1")

    with codespace():
        os.environ.pop("RESEARCH_SUITE_HOST", None)
        check("wide inside a codespace", settings_module.load().host, "0.0.0.0")

    with codespace():
        os.environ["RESEARCH_SUITE_HOST"] = "127.0.0.1"
        try:
            check("an explicit host still wins",
                  settings_module.load().host, "127.0.0.1")
        finally:
            os.environ.pop("RESEARCH_SUITE_HOST", None)


def test_binding_wide_does_not_widen_who_is_admitted() -> None:
    """0.0.0.0 changes which interface accepts a connection, not the allowlist."""
    with codespace():
        config = security.SecurityConfig("tok", "0.0.0.0", 8765)
        check("forwarded host allowed", config.host_allowed(FORWARDED), True)
        check("localhost allowed", config.host_allowed("localhost"), True)
        for header in ("evil.test", "someone-else-8765.app.github.dev",
                       f"{CODESPACE}-9999.app.github.dev"):
            check(f"{header} still refused", config.host_allowed(header), False)
        check("a wrong token is still a wrong token",
              config.token_valid("nope"), False)


def main() -> int:
    for name, function in sorted(globals().items()):
        if name.startswith("test_") and callable(function):
            function()
    print(f"tests/test_security.py: {CHECKS} checks, {len(FAILURES)} failures")
    for failure in FAILURES:
        print(f"  ✗ {failure}")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    raise SystemExit(main())
