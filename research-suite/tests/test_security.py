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
        contains("points at the self check for a 404", banner, "app.doctor")
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


def test_security_imports_without_fastapi() -> None:
    """The self check must run outside the virtual environment.

    `python3 -m app.doctor` died with ModuleNotFoundError: No module named
    'fastapi', because this module imported it at top level. That is the most
    likely way anyone runs the self check — reaching for it precisely when the
    environment is in doubt — and a diagnostic that needs a working environment
    to tell you the environment is broken is no diagnostic at all.

    Everything here except `guard()` is plain standard library, so fastapi is
    imported inside `guard()` now. This asserts the import stays there.
    """
    source = (Path(__file__).resolve().parents[1] / "app" / "security.py").read_text("utf-8")
    body = source[:source.index("async def guard(")]
    check("no top-level fastapi import", "from fastapi import" in body, False)
    check("no top-level fastapi import", "import fastapi" in body, False)

    guard_body = source[source.index("async def guard("):]
    check("guard imports it itself", "from fastapi import" in guard_body, True)

    doctor = (Path(__file__).resolve().parents[1] / "app" / "doctor.py").read_text("utf-8")
    for heavy in ("fastapi", "uvicorn", "matplotlib", "docx", "pptx", "httpx"):
        check(f"doctor does not import {heavy}",
              f"import {heavy}" in doctor, False)


def test_the_doctor_only_suggests_tools_that_exist() -> None:
    """Advice that ends in "command not found" costs a round trip.

    The remedy for an unforwarded port recommended `gh codespace ports
    forward`. Codespaces images do not all ship the GitHub CLI, and the user's
    did not — so the one actionable line in the diagnosis was a dead end.
    """
    doctor = (Path(__file__).resolve().parents[1] / "app" / "doctor.py").read_text("utf-8")
    block = doctor[doctor.index("Port {port} is NOT forwarded") - 900:
                   doctor.index("# 6. The URL to actually open.")]
    check("the gh suggestion is guarded on it being installed",
          'shutil.which("gh")' in block, True)
    check("the PORTS panel is named", "PORTS panel" in block, True)
    check("a rebuild is offered when there is no panel",
          "Rebuild Container" in block, True)
    check("visibility guidance travels with it",
          "Private" in block, True)


def test_the_session_token_survives_a_restart() -> None:
    """A rotating token invalidated the browser URL on every restart.

    Restarting is what you do after every code change, every Ctrl-C and every
    crash, so the practical effect was a stream of "missing or invalid session
    token" that read as a bug in the application.

    Stability is not a weakening here. The token stops other local processes
    and other pages from driving the API, and that is equally true of a stable
    one — anything running as this user can read it either way, including out
    of the terminal it is printed in. The boundary was always the OS account
    plus the host allowlist.
    """
    import tempfile
    from app import settings as settings_module

    with tempfile.TemporaryDirectory() as directory:
        saved = os.environ.get("RESEARCH_SUITE_DATA")
        os.environ["RESEARCH_SUITE_DATA"] = directory
        os.environ.pop("RESEARCH_SUITE_TOKEN", None)
        try:
            first = settings_module.load().session_token
            second = settings_module.load().session_token
            check("stable across loads", first, second)
            check("long enough to be a token", len(first) >= 24, True)

            token_file = Path(directory) / ".session-token"
            check("stored on disk", token_file.exists(), True)
            check("owner-only permissions",
                  oct(token_file.stat().st_mode & 0o777), "0o600")

            # A truncated or hand-edited file must not silently weaken it.
            token_file.write_text("short", "utf-8")
            replaced = settings_module.load().session_token
            check("a short file is replaced", len(replaced) >= 24, True)
            check("and is a different token", replaced != "short", True)

            # Deleting it mints a new one — the documented way to rotate.
            token_file.unlink()
            check("a new token after deletion",
                  settings_module.load().session_token != first, True)

            os.environ["RESEARCH_SUITE_TOKEN"] = "pinned-token-value-abcdefgh"
            check("an explicit token still wins",
                  settings_module.load().session_token,
                  "pinned-token-value-abcdefgh")
        finally:
            os.environ.pop("RESEARCH_SUITE_TOKEN", None)
            if saved is None:
                os.environ.pop("RESEARCH_SUITE_DATA", None)
            else:
                os.environ["RESEARCH_SUITE_DATA"] = saved


def test_the_launch_url_always_carries_the_token() -> None:
    """A URL without the fragment is refused, so nothing may print a bare one.

    The "already running" message did exactly that: it called `public_url()`,
    which stops at the port, and printed an address that answers "Missing or
    invalid session token". The banner had been appending the fragment itself,
    so the two callers could not help but drift. One method now owns it.
    """
    with not_a_codespace():
        config = security.SecurityConfig("tok-abc", "127.0.0.1", 8765)
        check("launch url carries the token", config.launch_url(),
              "http://localhost:8765/#token=tok-abc")
        check("and is the public url plus the fragment",
              config.launch_url().startswith(config.public_url()), True)

    with codespace():
        config = security.SecurityConfig("tok-abc", "0.0.0.0", 8765)
        check("forwarded launch url too", config.launch_url(),
              f"https://{FORWARDED}/#token=tok-abc")

    # And the banner must use it rather than reassembling the URL, which is
    # how the two drifted in the first place.
    source = (Path(__file__).resolve().parents[1] / "app" / "security.py"
              ).read_text("utf-8")
    banner = source[source.index("def startup_banner("):]
    check("the banner prints launch_url()", "config.launch_url()" in banner, True)
    check("and does not rebuild the fragment itself",
          "#token=" in banner.split("def ")[0], False)


def test_a_second_run_is_sent_to_the_first_rather_than_hopping() -> None:
    """The 404 this exists to prevent.

    `_claim_port` walks forward when a port is busy, so a second `bash run.sh`
    quietly became a second application on a second port. In a Codespace the
    forwarded URL carries the port number, so every address the user already
    had — the bookmark, the open tab, the URL in the earlier banner — pointed
    at nothing and GitHub answered 404. It is checked here against the source
    rather than by starting two servers, because the ordering is the point:
    the existing-run probe must come *before* the port walk.
    """
    source = (Path(__file__).resolve().parents[1] / "app" / "main.py"
              ).read_text("utf-8")

    check("there is an existing-run probe", "def _existing_run(" in source, True)
    check("keyed on a marker rather than the word 'ok'",
          'HEALTH_MARKER = "koch-clinical-suite"' in source, True)
    check("which /healthz actually returns",
          '"app": HEALTH_MARKER' in source, True)

    run = source[source.index("def run() -> None:"):]
    probe = run.index("_existing_run(preferred)")
    walk = run.index("_claim_port(SETTINGS.host, preferred)")
    check("the probe runs before the port walk", probe < walk, True)
    check("and a match returns instead of starting a second copy",
          "return" in run[probe:walk], True)
    check("and hands off to the message builder",
          "_existing_run_message(running, preferred)" in run[probe:walk], True)
    # It must NOT print this process's own URL there: this invocation's
    # settings describe the run that is about to exit, not the one serving.
    check("not this invocation's own address",
          "SECURITY.launch_url()" in run[probe:walk], False)


def test_a_restart_reclaims_its_own_port() -> None:
    """Without SO_REUSEADDR a restart could not rebind, and the port moved.

    A comment here used to refuse the option, reasoning that this must fail
    when someone else holds the port. It still does — SO_REUSEADDR does not
    permit binding a port another process is actively listening on; that is
    SO_REUSEPORT, which is not set. What it does permit is binding over the
    TIME_WAIT remnants of connections this app itself closed, and without it
    stopping the server and starting it again within a couple of minutes of
    serving a page moved the app to the next port — which, in a Codespace,
    404s every URL the user already had.
    """
    import socket

    source = (Path(__file__).resolve().parents[1] / "app" / "main.py"
              ).read_text("utf-8")
    claim = source[source.index("def _claim_port("):source.index("def run() -> None:")]
    check("the listener sets SO_REUSEADDR",
          "setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)" in claim, True)
    # Matched as a call, not as a word: the comment above the setsockopt
    # explains why SO_REUSEPORT is *not* used, and a bare substring test
    # therefore matches the explanation and fails on correct code.
    check("and not SO_REUSEPORT, which would allow two live listeners",
          "socket.SO_REUSEPORT," in claim, False)

    # The behaviour itself, not just the source: with the same option set, a
    # second bind against a live listener must still fail.
    held = socket.socket()
    held.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    held.bind(("127.0.0.1", 0))
    held.listen(4)
    port = held.getsockname()[1]
    second = socket.socket()
    second.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        second.bind(("127.0.0.1", port))
        refused = False
    except OSError:
        refused = True
    finally:
        second.close()
        held.close()
    check("a live listener still refuses a second bind", refused, True)


class _FakeRequest:
    """Enough of a Request for token_source: three places a token can be."""

    def __init__(self, *, header="", query="", cookie=""):
        self.headers = {security.TOKEN_HEADER: header} if header else {}
        self.query_params = {"token": query} if query else {}
        self.cookies = {security.TOKEN_COOKIE: cookie} if cookie else {}


class _FakeResponse:
    def __init__(self):
        self.set = {}
        self.deleted = []

    def set_cookie(self, name, value, **kwargs):
        self.set[name] = (value, kwargs)

    def delete_cookie(self, name, **kwargs):
        self.deleted.append(name)


def test_the_token_survives_closing_the_tab() -> None:
    """sessionStorage is cleared on tab close, which made every new tab dead.

    The front end held the token in `sessionStorage`. Closing the tab threw it
    away, so the only way back in was the launch URL out of the terminal — and
    in a Codespace that means finding the terminal, and, if the container had
    suspended in the meantime, starting the app first. The user's description
    was exact: having to do this every time you exit out of the tab.

    So a token that arrives in the URL or a header is written to a cookie, and
    the cookie is what the next tab presents.
    """
    config = security.SecurityConfig("real-token", "127.0.0.1", 8765)

    check("a token in the launch URL is recognised",
          security.token_source(_FakeRequest(query="real-token"), config), "query")
    check("a token in the header is recognised",
          security.token_source(_FakeRequest(header="real-token"), config), "header")
    check("a token already in the cookie is recognised as such",
          security.token_source(_FakeRequest(cookie="real-token"), config), "cookie")
    check("a wrong token is no source at all",
          security.token_source(_FakeRequest(query="wrong"), config), "")
    check("and neither is nothing",
          security.token_source(_FakeRequest(), config), "")

    response = _FakeResponse()
    security.remember_token(response, config, secure=False)
    value, options = response.set[security.TOKEN_COOKIE]
    check("the cookie carries the token", value, "real-token")
    check("no script can read it", options["httponly"], True)
    check("it is not sent on cross-site writes", options["samesite"], "lax")
    check("it outlives the tab by a long way",
          options["max_age"] >= 60 * 60 * 24 * 7, True)
    check("and covers the whole app", options["path"], "/")


def test_the_cookie_is_https_only_when_the_connection_is() -> None:
    """Unconditional Secure would mean never stored on a plain-http run.

    Which is most of them: localhost is http, and a cookie marked Secure is
    silently dropped there. Marking it by scheme keeps the Codespaces case —
    which is HTTPS — protected without breaking the local case.
    """
    config = security.SecurityConfig("real-token", "127.0.0.1", 8765)

    local = _FakeResponse()
    security.remember_token(local, config, secure=False)
    check("plain http: not marked Secure",
          local.set[security.TOKEN_COOKIE][1]["secure"], False)

    forwarded = _FakeResponse()
    security.remember_token(forwarded, config, secure=True)
    check("https: marked Secure",
          forwarded.set[security.TOKEN_COOKIE][1]["secure"], True)

    # And the middleware must decide that from the request scheme rather than
    # hard-coding either answer.
    main = (Path(__file__).resolve().parents[1] / "app" / "main.py"
            ).read_text("utf-8")
    check("the middleware keys Secure off the scheme",
          'secure=request.url.scheme == "https"' in main, True)


def test_a_rejected_cookie_is_discarded() -> None:
    """Otherwise a wrong cookie is a trap with no way out from the browser.

    The page can neither read an HttpOnly cookie nor delete it, so every reload
    and every retry would resend the same rejected credential — the same shape
    of trap that storing a bad token used to produce, and it self-heals for the
    same reason: whatever rejects the credential is what discards it.
    """
    response = _FakeResponse()
    security.forget_token(response)
    check("the cookie is cleared", response.deleted, [security.TOKEN_COOKIE])

    main = (Path(__file__).resolve().parents[1] / "app" / "main.py"
            ).read_text("utf-8")
    guard = main[main.index("async def enforce_security("):
                 main.index("# --------------------------------------------------------------------- shell")]
    check("a 401 clears it", "if error.status_code == 401:" in guard, True)
    check("by calling forget_token", "security.forget_token(" in guard, True)
    # Only a token that arrived from outside is worth writing back; re-setting
    # one that came from the cookie is a wasted header on every request.
    check("and only an external token is remembered",
          'arrived_by in ("header", "query")' in guard, True)


def test_the_cookie_does_not_stand_alone_against_csrf() -> None:
    """A cookie travels automatically where a custom header did not.

    That is precisely the property CSRF exploits, so the checks that do not
    depend on the cookie have to still be there: the Host allowlist for the
    DNS-rebinding case, and the Origin check on writes.
    """
    with not_a_codespace():
        config = security.SecurityConfig("tok", "127.0.0.1", 8765)
        check("an unknown Host is still refused",
              config.host_allowed("evil.test"), False)

    source = (Path(__file__).resolve().parents[1] / "app" / "security.py"
              ).read_text("utf-8")
    guard = source[source.index("async def guard("):source.index("def startup_banner(")]
    check("writes still check the Origin",
          'request.method not in ("GET", "HEAD", "OPTIONS")' in guard, True)
    check("and refuse a foreign one", "Cross-origin request from" in guard, True)


def test_a_named_host_is_admitted_and_nothing_else() -> None:
    """LAN access is opt-in by name, and the name is the whole of the grant.

    On a Raspberry Pi the app is not on the machine doing the browsing, so the
    bind has to be wide — and at that point the Host allowlist stops being
    belt-and-braces over a loopback bind and becomes the thing actually holding
    the door. It has to admit exactly what was configured and nothing that
    merely resembles it.
    """
    with not_a_codespace():
        config = security.SecurityConfig(
            "tok", "0.0.0.0", 8765, extra_hosts={"pi-3bplus.local"})
        for header in ("pi-3bplus.local", "pi-3bplus.local:8765",
                       "PI-3BPlus.local:8765", "localhost:8765", "127.0.0.1"):
            check(f"{header} admitted", config.host_allowed(header), True)
        for header in ("evil.test",
                       "pi-3bplus.local.evil.test",     # suffix, not the name
                       "evil.test/pi-3bplus.local",
                       "192.168.1.50",                  # not the one configured
                       "pi-3bplus",                     # not the name either
                       ""):
            check(f"{header!r} refused", config.host_allowed(header), False)
        check("and a wrong token is still a wrong token",
              config.token_valid("nope"), False)


def test_an_empty_allowlist_admits_nothing_extra() -> None:
    """The default must not be a wildcard. An allowlist that fills itself in is
    not an allowlist, and the failure mode is silent."""
    with not_a_codespace():
        config = security.SecurityConfig("tok", "0.0.0.0", 8765)
        check("no extra hosts by default", config.extra_hosts, [])
        for header in ("pi-3bplus.local", "192.168.1.50", "evil.test"):
            check(f"{header} refused", config.host_allowed(header), False)
        check("localhost still works", config.host_allowed("localhost"), True)

        # And an explicit empty configuration is the same thing, not a bypass.
        empty = security.SecurityConfig("tok", "0.0.0.0", 8765, extra_hosts=set())
        check("empty set is not a wildcard",
              empty.host_allowed("anything.test"), False)


def test_the_printed_address_is_one_you_can_open() -> None:
    """`http://0.0.0.0:8765/` reaches nothing.

    That is what the banner printed for anyone who bound the app wide outside a
    Codespace: a link that cannot work, offered as the way in. 0.0.0.0 is a
    bind address — "accept on every interface" — not a destination.
    """
    with not_a_codespace():
        bare = security.SecurityConfig("tok", "0.0.0.0", 8765)
        check("no 0.0.0.0 in the URL", "0.0.0.0" in bare.public_url(), False)
        check("falls back to localhost", bare.public_url(),
              "http://localhost:8765/")

        named = security.SecurityConfig(
            "tok", "0.0.0.0", 8765,
            extra_hosts={"pi-3bplus.local", "192.168.1.50"})
        check("prints an allowlisted name", named.public_url(),
              "http://192.168.1.50:8765/")
        check("and the token comes with it", named.launch_url(),
              "http://192.168.1.50:8765/#token=tok")
        check("the choice is stable across runs",
              security.SecurityConfig(
                  "tok", "0.0.0.0", 8765,
                  extra_hosts={"192.168.1.50", "pi-3bplus.local"}).public_url(),
              named.public_url())

        # Bound to loopback, an allowlisted LAN name is not reachable however
        # many are configured, so printing one would be a lie.
        local = security.SecurityConfig(
            "tok", "127.0.0.1", 8765, extra_hosts={"pi-3bplus.local"})
        check("loopback still says localhost", local.public_url(),
              "http://localhost:8765/")

        # An explicit non-loopback address is printed as given, and an IPv6
        # literal has to be bracketed or it is not a URL.
        check("an explicit address is kept",
              security.SecurityConfig("tok", "192.168.1.50", 8765).public_url(),
              "http://192.168.1.50:8765/")
        check("IPv6 is bracketed",
              security.SecurityConfig("tok", "fd00::5", 8765).public_url(),
              "http://[fd00::5]:8765/")
        check("and :: falls back too",
              security.SecurityConfig("tok", "::", 8765).public_url(),
              "http://localhost:8765/")


def test_the_allowlist_is_parsed_the_way_it_gets_typed() -> None:
    """People paste what they typed into the browser, so a scheme, a port and a
    trailing path all have to survive being pasted."""
    from app.settings import _host_list

    check("empty is empty", _host_list(""), set())
    check("whitespace is empty", _host_list("  ,  ; "), set())
    check("a plain name", _host_list("pi-3bplus.local"), {"pi-3bplus.local"})
    check("a list", _host_list("pi.local, 192.168.1.50"),
          {"pi.local", "192.168.1.50"})
    check("semicolons too", _host_list("pi.local;192.168.1.50"),
          {"pi.local", "192.168.1.50"})
    check("a pasted URL", _host_list("http://pi-3bplus.local:8765/#token=x"),
          {"pi-3bplus.local"})
    check("case folded", _host_list("PI-3BPlus.Local"), {"pi-3bplus.local"})
    check("a bracketed IPv6 keeps its brackets",
          _host_list("[fd00::5]:8765"), {"[fd00::5]"})
    check("a bare IPv6 keeps every group",
          _host_list("fd00::5"), {"fd00::5"})

    # And what it parses is what the allowlist then honours.
    with not_a_codespace():
        config = security.SecurityConfig(
            "tok", "0.0.0.0", 8765,
            extra_hosts=_host_list("http://pi-3bplus.local:8765/"))
        check("parsed then admitted",
              config.host_allowed("pi-3bplus.local:8765"), True)


def test_the_allowlist_is_read_from_configuration_only() -> None:
    """Never from the request, never from the machine's own hostname.

    Inferring it from the Host header would delete the DNS-rebinding defence
    outright; inferring it from `socket.gethostname()` would quietly admit a
    name the operator never chose. Naming the hosts is the point of them.
    """
    import tempfile
    from app import settings as settings_module

    # Checked against the parsed module rather than the text, because the
    # comment explaining why we do not call gethostname() matched a substring
    # search and made the assertion pass for the wrong reason.
    import ast
    tree = ast.parse((Path(__file__).resolve().parents[1] / "app" /
                      "settings.py").read_text("utf-8"))
    names = {node.attr for node in ast.walk(tree)
             if isinstance(node, ast.Attribute)}
    names |= {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    check("hostname is never consulted",
          {"gethostname", "getfqdn"} & names, set())

    with tempfile.TemporaryDirectory() as directory:
        saved_data = os.environ.get("RESEARCH_SUITE_DATA")
        saved_hosts = os.environ.get("RESEARCH_SUITE_ALLOWED_HOSTS")
        os.environ["RESEARCH_SUITE_DATA"] = directory
        os.environ.pop("RESEARCH_SUITE_ALLOWED_HOSTS", None)
        try:
            check("nothing allowlisted by default",
                  settings_module.load().allowed_hosts, set())

            os.environ["RESEARCH_SUITE_ALLOWED_HOSTS"] = \
                "pi-3bplus.local, 192.168.1.50"
            loaded = settings_module.load()
            check("the environment is honoured", loaded.allowed_hosts,
                  {"pi-3bplus.local", "192.168.1.50"})
            check("and shown in the settings screen",
                  loaded.redacted()["allowed_hosts"],
                  ["192.168.1.50", "pi-3bplus.local"])
        finally:
            if saved_hosts is None:
                os.environ.pop("RESEARCH_SUITE_ALLOWED_HOSTS", None)
            else:
                os.environ["RESEARCH_SUITE_ALLOWED_HOSTS"] = saved_hosts
            if saved_data is None:
                os.environ.pop("RESEARCH_SUITE_DATA", None)
            else:
                os.environ["RESEARCH_SUITE_DATA"] = saved_data


def test_the_running_app_is_given_the_allowlist() -> None:
    """Parsed and unused is the same as absent.

    `SecurityConfig` grew `extra_hosts` before anything passed it, so the
    setting existed and did nothing — the exact defect this checks for.
    """
    root = Path(__file__).resolve().parents[1]
    for name in ("main.py", "doctor.py"):
        source = (root / "app" / name).read_text("utf-8")
        check(f"{name} passes the allowlist through",
              "extra_hosts=" in source and "allowed_hosts" in source, True)


def test_the_settings_screen_says_what_is_admitted() -> None:
    """The screen that reports "not localhost" is where you look when the other
    machine gets a 421, so it has to answer the question rather than restate
    the bind address."""
    root = Path(__file__).resolve().parents[1]
    payload = (root / "app" / "main.py").read_text("utf-8")
    check("the allowlist is sent to the UI",
          '"allowed_hosts": sorted(SECURITY.extra_hosts)' in payload, True)

    script = (root / "app" / "static" / "app.js").read_text("utf-8")
    notice = script[script.index("function accessNotice("):
                    script.index("function grammarlyCard(")]
    check("the notice reads it", "access.allowed_hosts" in notice, True)
    check("names the setting when empty",
          "RESEARCH_SUITE_ALLOWED_HOSTS" in notice, True)
    check("and explains the 421", "421" in notice, True)


def test_a_wide_bind_without_an_allowlist_says_so() -> None:
    """The next thing that happens is a 421 from the other machine, so the
    banner has to name the setting that prevents it rather than leaving the
    user to read a status code."""
    with not_a_codespace():
        bare = security.startup_banner(
            security.SecurityConfig("tok", "0.0.0.0", 8765), [])
        check("names the setting", "RESEARCH_SUITE_ALLOWED_HOSTS" in bare, True)
        check("and explains the 421", "421" in bare, True)

        named = security.startup_banner(
            security.SecurityConfig("tok", "0.0.0.0", 8765,
                                    extra_hosts={"pi-3bplus.local"}), [])
        check("lists what is admitted", "pi-3bplus.local" in named, True)
        check("and stops nagging", "421" in named, False)

        quiet = security.startup_banner(
            security.SecurityConfig("tok", "127.0.0.1", 8765), [])
        check("loopback is not warned about", "421" in quiet, False)


def test_only_this_machine_is_told_how_this_run_is_configured() -> None:
    """`/healthz` needs no token, so it must not carry one — and bound wide,
    anything on the network can reach it."""
    check("loopback recognised", security.is_loopback_client("127.0.0.1"), True)
    check("IPv6 loopback too", security.is_loopback_client("::1"), True)
    check("bracketed IPv6 loopback",
          security.is_loopback_client("[::1]"), True)
    for address in ("192.168.1.168", "10.0.0.4", "8.8.8.8", "", "not-an-ip"):
        check(f"{address!r} is not this machine",
              security.is_loopback_client(address), False)

    root = Path(__file__).resolve().parents[1]
    source = (root / "app" / "main.py").read_text("utf-8")
    route = source[source.index("async def healthz("):
                   source.index("if STATIC_DIR.exists():")]
    check("the detail is gated on the peer address",
          "security.is_loopback_client(client)" in route, True)
    check("the payload has no token field", '"token":' in route, False)
    check("only a fingerprint of it",
          "security.token_fingerprint(SECURITY.token)" in route, True)

    # The fingerprint identifies a token without carrying it.
    first = security.token_fingerprint("a-real-token-value")
    check("stable", first, security.token_fingerprint("a-real-token-value"))
    check("short", len(first), 12)
    check("not the token", "a-real-token-value" in first, False)
    check("different tokens differ",
          first != security.token_fingerprint("another-token-value"), True)
    check("empty stays empty", security.token_fingerprint(""), "")


def test_a_second_run_describes_the_first_not_itself() -> None:
    """The "already running" message used to be built from the settings of the
    invocation that was about to exit.

    On the Pi that meant: start it bound to loopback, then run it again with
    RESEARCH_SUITE_HOST=0.0.0.0 and a LAN name, and it printed a LAN URL for a
    server listening only on 127.0.0.1. The browser answered
    ERR_CONNECTION_REFUSED, which reads as "the feature is broken" rather than
    "the settings only apply to a run they start".
    """
    root = Path(__file__).resolve().parents[1]
    source = (root / "app" / "main.py").read_text("utf-8")

    message = source[source.index("def _existing_run_message("):
                     source.index("def _claim_port(")]
    check("the URL comes from the running process",
          "live.launch_url()" in message, True)
    check("built from what that run reported",
          'bind.get("host", SETTINGS.host)' in message, True)
    check("and its allowlist, not this one's",
          'bind.get("allowed_hosts")' in message, True)
    check("a disagreement is named", "not the" in message, True)
    check("with the command that fixes it",
          "pkill -f 'app.main'" in message, True)

    # And the probe has to hand the payload back, not a bare yes.
    probe = source[source.index("def _existing_run("):
                   source.index("def _existing_run_message(")]
    check("the probe returns the payload", "return payload if" in probe, True)
    check("and None when it is not us", "return None" in probe, True)


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
