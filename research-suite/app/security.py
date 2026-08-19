"""
The access boundary, and an honest account of where it sits.

**What this protects against.** The app binds to `127.0.0.1`, so nothing on the
network can reach it — not another machine on the same Wi-Fi, not a device on the
same LAN. Every request must also carry a session token generated fresh at
startup, which blocks the two attacks a localhost service is actually exposed to:

* **A web page you visit doing requests to your own machine.** Any site's
  JavaScript can issue requests to `http://127.0.0.1:8765`. Without a token it
  could drive this app. With one it cannot, because the token is never in a page
  another origin can read, and the response carries no CORS headers so a
  cross-origin reader gets nothing back.
* **DNS rebinding**, where a hostname the attacker controls resolves to
  `127.0.0.1` so their page appears same-origin. The `Host` header is checked
  against an allowlist, which is what defeats it — a token alone does not.

**What this does not protect against, stated plainly.** Anything already running
as your user account on your machine can read the `.env` file, the token and the
project data. This is a single-user desktop application; its security boundary is
your operating system account, exactly like Word's. If you need protection from
other people using the same computer under the same login, this design does not
give it to you, and no amount of application-level authentication would.

**If you expose it beyond localhost** — by setting `RESEARCH_SUITE_HOST` to
`0.0.0.0`, or by putting it behind a tunnel — the app prints a warning and keeps
running, because refusing would be wrong for someone who genuinely wants it on a
Tailscale network behind Tailscale's own authentication. But the token then
becomes the only thing standing between the internet and your API keys, and a
token in a URL ends up in browser history and server logs. Put a real
authenticating proxy in front of it, or leave it on localhost.
"""

from __future__ import annotations

import hmac
import os
import ipaddress
from urllib.parse import urlparse

# FastAPI is imported inside `guard()`, not here.
#
# Everything else in this module is plain standard library, and `app/doctor.py`
# needs it to answer "is this thing running and can anything reach it" — which
# is a question you ask precisely when the environment is broken. Importing
# fastapi at module scope meant the self check died with ModuleNotFoundError
# when run outside the virtual environment, which is the most likely way anyone
# will run it.

# Host header values a browser will legitimately send for a local service.
LOCAL_HOSTS = {"127.0.0.1", "localhost", "[::1]", "::1", "0.0.0.0"}


def codespace_host() -> str:
    """The forwarded hostname when running inside a GitHub Codespace, else "".

    A Codespace does not reach this app on localhost. GitHub forwards the port
    and the browser arrives with `Host: <name>-<port>.app.github.dev`, which the
    loopback allowlist rejects with a 421 — so the app is unusable there unless
    that host is recognised. Detected from the environment rather than accepted
    from the request, because a Host header is attacker-controlled and the whole
    point of the allowlist is that it is not.
    """
    name = os.environ.get("CODESPACE_NAME", "").strip()
    domain = os.environ.get(
        "GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN", "app.github.dev").strip()
    if not name or not domain:
        return ""
    return f"{name}-{{port}}.{domain}"


def in_codespace() -> bool:
    return bool(os.environ.get("CODESPACES", "").strip()) and bool(codespace_host())

# Paths reachable without a token: the shell page (which then supplies the token
# from its URL fragment) and the health probe.
PUBLIC_PATHS = {"/", "/index.html", "/healthz", "/favicon.ico"}
PUBLIC_PREFIXES = ("/static/",)

TOKEN_HEADER = "X-Research-Token"
TOKEN_COOKIE = "research_token"


class SecurityConfig:
    def __init__(self, token: str, host: str, port: int,
                 extra_hosts: set[str] | None = None):
        self.token = token
        self.host = host
        self.port = port
        self.allowed_hosts = set(LOCAL_HOSTS) | set(extra_hosts or set())
        self.local_only = _is_loopback(host)
        # A Codespace forwards the port over HTTPS under a hostname derived from
        # the codespace name. Allowed only when the environment says we are in
        # one, and only for the port actually served.
        self.codespace = (codespace_host().format(port=port)
                          if in_codespace() else "")
        if self.codespace:
            self.allowed_hosts.add(self.codespace)

    def rebind(self, port: int) -> None:
        """Move to a different port after startup claimed one.

        `run()` may land on 8766 when 8765 is busy, and the forwarded Codespaces
        hostname embeds the port. Without recomputing it here the allowlist
        would name a host the browser never sends, and every request would be
        rejected with a 421 that blamed the user's URL.
        """
        if port == self.port:
            return
        if self.codespace:
            self.allowed_hosts.discard(self.codespace)
        self.port = port
        self.codespace = (codespace_host().format(port=port)
                          if in_codespace() else "")
        if self.codespace:
            self.allowed_hosts.add(self.codespace)

    def public_url(self) -> str:
        """Where to actually open this, which is not always localhost."""
        if self.codespace:
            return f"https://{self.codespace}/"
        return f"http://{'localhost' if self.local_only else self.host}:{self.port}/"

    def launch_url(self) -> str:
        """The address to actually open, token included.

        Separate from `public_url` because the token is what makes the URL
        work, and leaving the two callers to append it themselves is a defect
        waiting to happen — the second one did exactly that and printed an
        address that answers "Missing or invalid session token".
        """
        return f"{self.public_url()}#token={self.token}"

    def host_allowed(self, header: str) -> bool:
        """Check the Host header, which is the DNS-rebinding defence.

        A page on `evil.test` whose DNS points at 127.0.0.1 reaches this app with
        `Host: evil.test`. Rejecting unknown hosts is what stops it; the token
        alone would not, because the browser would treat the request as
        same-origin and could read the reply.
        """
        if not header:
            return False
        name = header.split(",")[0].strip()
        # An IPv6 literal arrives bracketed, and with a port it is
        # "[::1]:8765". Stripping brackets *before* the port left "::1]:8765",
        # which matched nothing — so a browser that resolved localhost to ::1
        # was locked out with a 421 blaming its own URL. Take the bracketed
        # part first, then the port, then compare.
        if name.startswith("["):
            end = name.find("]")
            name = name[1:end] if end != -1 else name.lstrip("[")
        elif name.count(":") > 1:
            # More than one colon and no brackets: a bare IPv6 literal, which
            # has no port to strip. Splitting on the last colon would turn
            # "::1" into ":".
            pass
        elif ":" in name:
            name = name.rsplit(":", 1)[0]
        name = name.lower()
        if name in {h.strip("[]").lower() for h in self.allowed_hosts}:
            return True
        if not self.local_only:
            # Deliberately exposed: accept the interface's own address and any
            # host the operator allowlisted, nothing else.
            return name == self.host.lower()
        return False

    def token_valid(self, supplied: str) -> bool:
        # Constant-time compare, so a wrong token cannot be narrowed down by
        # timing. Cheap, and the alternative is indefensible.
        return bool(supplied) and hmac.compare_digest(supplied, self.token)


def _is_loopback(host: str) -> bool:
    if host in ("localhost", ""):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


async def guard(request: "Request", config: SecurityConfig) -> None:
    """Reject anything that fails the host or token check."""
    from fastapi import HTTPException

    path = request.url.path
    if not config.host_allowed(request.headers.get("host", "")):
        raise HTTPException(
            status_code=421,
            detail=(
                "Request rejected: the Host header does not name this machine. "
                "Open the application at the address printed when it started. "
                "This check is what prevents a web page from driving your local "
                "app through DNS rebinding."
            ),
        )

    # A cross-origin page must not be able to issue state-changing requests even
    # with a stolen token, so the Origin header is checked on writes.
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        origin = request.headers.get("origin", "")
        if origin:
            host = urlparse(origin).hostname or ""
            if host.lower() not in {h.strip("[]").lower() for h in config.allowed_hosts} \
                    and host.lower() != config.host.lower():
                raise HTTPException(
                    status_code=403,
                    detail=f"Cross-origin request from {origin} refused.",
                )

    if path in PUBLIC_PATHS or path.startswith(PUBLIC_PREFIXES):
        return

    supplied = (
        request.headers.get(TOKEN_HEADER, "")
        or request.cookies.get(TOKEN_COOKIE, "")
        or request.query_params.get("token", "")
    )
    if not config.token_valid(supplied):
        raise HTTPException(
            status_code=401,
            detail=(
                "Missing or invalid session token. The token is printed in the "
                "terminal each time the application starts and is included in "
                "the launch URL. Reload from that URL."
            ),
        )


def startup_banner(config: SecurityConfig, warnings: list[str]) -> str:
    """What the user sees in the terminal. The URL includes the token so
    clicking it is all that is needed."""
    lines = [
        "",
        "  Koch Research Suite",
        "  " + "─" * 62,
        f"  Open:  {config.launch_url()}",
        "",
    ]
    if config.codespace:
        # Different boundary, and worth stating rather than implying. A
        # forwarded port is private to the codespace owner by default — GitHub
        # authenticates it — but "Public" visibility is one menu click away, and
        # at that point the session token is the only thing left.
        lines += [
            "  Running in a GitHub Codespace, so this is reached over HTTPS at",
            "  the forwarded address above, not at localhost.",
            "",
            "  Port visibility governs who can reach it. The default is Private:",
            "  only your GitHub account, which is the setting you want. If you",
            "  set the port to Public, anyone with the URL can reach this and the",
            "  session token becomes the only protection — and a token in a URL",
            "  leaks into history and logs. Check the Ports panel.",
            "",
            "  Your API keys and project data live in the codespace, which is",
            "  deleted when the codespace is. Export anything you want to keep.",
            "",
            "  If that URL 404s, the port is not forwarded and the request never",
            "  reaches this app. In another terminal, run:",
            "      python3 -m app.doctor",
        ]
    elif config.local_only:
        lines += [
            "  Bound to localhost only — not reachable from your network.",
            "  Security boundary: your operating system user account. Anything",
            "  running as you can read the project data and the API keys.",
        ]
    else:
        lines += [
            f"  ⚠  Bound to {config.host}, NOT localhost.",
            "",
            "  This is reachable from your network. The session token is now the",
            "  only thing protecting your API keys, and a token in a URL leaks",
            "  into browser history and proxy logs. Put an authenticating proxy",
            "  in front of this (Cloudflare Access, Tailscale, or Caddy with",
            "  basic auth over TLS), or set RESEARCH_SUITE_HOST=127.0.0.1.",
        ]
    for warning in warnings:
        lines += ["", f"  Note: {warning}"]
    lines += ["", "  Stop with Ctrl-C.", ""]
    return "\n".join(lines)
