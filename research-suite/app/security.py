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
import ipaddress
from urllib.parse import urlparse

from fastapi import HTTPException, Request

# Host header values a browser will legitimately send for a local service.
LOCAL_HOSTS = {"127.0.0.1", "localhost", "[::1]", "::1", "0.0.0.0"}

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
        if ":" in name and not name.startswith("["):
            name = name.rsplit(":", 1)[0]
        name = name.strip("[]").lower()
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


async def guard(request: Request, config: SecurityConfig) -> None:
    """Reject anything that fails the host or token check."""
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
    url = f"http://{'localhost' if config.local_only else config.host}:{config.port}/"
    lines = [
        "",
        "  Koch Research Suite",
        "  " + "─" * 62,
        f"  Open:  {url}#token={config.token}",
        "",
    ]
    if config.local_only:
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
