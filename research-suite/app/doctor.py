"""
Self-check: is this running, where, and can anything reach it.

This exists because a real diagnosis took four rounds of guessing. The symptom
was a 404 from a Codespaces forwarded URL, and the possible causes — the app not
running, the app on a different port, a loopback-only bind, a port that was
never forwarded, a stale token — all look identical from the browser. Each one
needed a different fix and none of them announced itself.

So: one command that reports every layer in order, from the inside out, and
names the next step for whichever layer is broken. It answers questions rather
than asserting health, and where it cannot determine something it says so
instead of guessing.

    python -m app.doctor
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import security, settings as settings_module  # noqa: E402

OK, BAD, UNKNOWN = "  ok  ", " FAIL ", "  ??  "


def line(status: str, label: str, detail: str = "") -> None:
    print(f"[{status}] {label}" + (f"\n         {detail}" if detail else ""))


def _probe(host: str, port: int, timeout: float = 2.0) -> bool:
    sock = socket.socket()
    sock.settimeout(timeout)
    try:
        sock.connect((host, port))
        return True
    except OSError:
        return False
    finally:
        sock.close()


def _get(url: str, timeout: float = 4.0) -> tuple[int, str]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return response.status, response.read(400).decode("utf-8", "replace")
    except urllib.error.HTTPError as error:
        return error.code, error.read(400).decode("utf-8", "replace")
    except Exception as error:                       # noqa: BLE001
        return 0, f"{type(error).__name__}: {error}"


def main() -> int:
    settings = settings_module.load()
    config = security.SecurityConfig(
        settings.session_token, settings.host, settings.port)

    print()
    print("  Koch Clinical Suite — self check")
    print("  " + "─" * 62)
    print()

    # 1. Where does this think it is running.
    in_cs = security.in_codespace()
    line(OK, f"Environment: {'GitHub Codespace' if in_cs else 'local machine'}")
    if in_cs:
        line(OK, f"Codespace name: {os.environ.get('CODESPACE_NAME', '?')}")
    line(OK, f"Configured bind: {settings.host}:{settings.port}")

    if in_cs and settings.host == "127.0.0.1":
        line(BAD, "Bound to loopback inside a Codespace.",
             "The port forwarder cannot see it. Unset RESEARCH_SUITE_HOST, or "
             "set it to 0.0.0.0, and restart.")

    # 2. Is anything actually listening, here or on a neighbouring port.
    listening = [p for p in range(settings.port, settings.port + 6)
                 if _probe("127.0.0.1", p, 0.4)]
    if not listening:
        line(BAD, f"Nothing is listening on {settings.port}"
                  f"–{settings.port + 5}.",
             "The application is not running. Start it in another terminal "
             "with `bash run.sh` and leave it running, then run this again.")
        print()
        return 1

    port = settings.port if settings.port in listening else listening[0]
    if port != settings.port:
        line(BAD, f"Nothing on {settings.port}, but something is on {port}.",
             f"A previous run probably still holds {settings.port}, so this one "
             f"moved. Open the URL for {port}, or stop the old run.")
    else:
        line(OK, f"Something is listening on {port}")

    # Everything below must describe the port actually in use. Checking the
    # configured port instead reported the host for 8765 while the app was on
    # 8766 — a reassurance about an address the browser will never send.
    config.rebind(port)

    # 3. Is it this application, and does it answer.
    status, body = _get(f"http://127.0.0.1:{port}/healthz")
    if status == 200 and "ok" in body:
        line(OK, "It responds to /healthz and it is this application")
    elif status == 0:
        line(BAD, f"Could not reach it on 127.0.0.1:{port}.", body)
        print()
        return 1
    else:
        line(BAD, f"Something is on {port} but it is not this app "
                  f"(HTTP {status}).",
             "Another program holds the port. Stop it, or run this on another "
             "port with RESEARCH_SUITE_PORT=9000 bash run.sh")
        print()
        return 1

    # 4. Does the host check accept what a browser would send.
    for header in filter(None, [f"localhost:{port}", config.codespace]):
        allowed = config.host_allowed(header)
        line(OK if allowed else BAD, f"Host header accepted: {header}",
             "" if allowed else "This is the DNS-rebinding allowlist refusing "
                                "the address you are opening.")

    # 5. Codespaces: is the port actually forwarded. This is the layer that
    #    produces a 404 while everything above it is perfectly healthy.
    if in_cs:
        forwarded = None
        if shutil.which("gh"):
            try:
                result = subprocess.run(
                    ["gh", "codespace", "ports", "--json",
                     "sourcePort,visibility"],
                    capture_output=True, text=True, timeout=25)
                if result.returncode == 0 and result.stdout.strip():
                    rows = json.loads(result.stdout)
                    forwarded = {int(r["sourcePort"]): r.get("visibility", "?")
                                 for r in rows}
            except Exception:                        # noqa: BLE001
                forwarded = None

        if forwarded is None:
            line(UNKNOWN, "Could not determine whether the port is forwarded.",
                 "`gh codespace ports` did not answer — it often needs a "
                 "codespace name when run from inside one. Check the PORTS "
                 "panel in VS Code instead: port " + str(port) +
                 " must be listed.")
        elif port in forwarded:
            line(OK, f"Port {port} is forwarded "
                     f"(visibility: {forwarded[port]})")
            if forwarded[port] == "public":
                line(BAD, "Visibility is public.",
                     "Anyone with the URL can reach this and the session token "
                     "is the only protection. Set it back to private.")
        else:
            line(BAD, f"Port {port} is NOT forwarded — this is your 404.",
                 "Nothing is wrong with the application. GitHub's proxy has no "
                 "route to it.\n         Fix: open the PORTS panel in VS Code, "
                 "click 'Forward a Port', enter " + str(port) + ".\n"
                 "         Or in another terminal: gh codespace ports forward "
                 f"{port}:{port}")

    # 6. The URL to actually open.
    print()
    print("  Open this, including everything after the '#':")
    print(f"    {config.public_url()}#token={settings.session_token}")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
