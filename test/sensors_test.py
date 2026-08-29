"""Check the app's side of the Pi integration.

Two things have to hold for the cabinet monitor to be trustworthy from a
phone: the live card must say plainly when the Pi has gone quiet (a stale
reading shown as current is worse than none), and the Pi's MINIMAL sensor
entries - which carry only the keys they measured - must flow through the
same merge, charts, tiles and CSV as hand-typed checks.

The Firestore endpoints are mocked from the app's own origin, as in
sync_test.py: no Firebase project, no credentials, no network.

Usage:
    pip install playwright
    python3 test/sensors_test.py
"""

import contextlib
import datetime
import functools
import http.server
import json
import pathlib
import socketserver
import threading

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent

DOCUMENTS: dict[str, str] = {}


def chromium_path() -> str | None:
    for candidate in sorted(pathlib.Path("/opt/pw-browsers").glob("chromium-*/chrome-linux/chrome")):
        return str(candidate)
    return None


class MockFirebaseHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, code, payload):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path.startswith("/v1/accounts:signUp"):
            self._send(200, {"idToken": "test-token", "expiresIn": "3600"})
            return
        self._send(404, {"error": {"message": "not found"}})

    def do_GET(self):
        if self.path.startswith("/v1/projects/"):
            stored = DOCUMENTS.get(self.path)
            if stored is None:
                self._send(404, {"error": {"message": "not found"}})
                return
            self._send(200, {"fields": {"data": {"stringValue": stored}}})
            return
        super().do_GET()

    def do_PATCH(self):
        length = int(self.headers.get("Content-Length") or 0)
        payload = json.loads(self.rfile.read(length))
        DOCUMENTS[self.path] = payload["fields"]["data"]["stringValue"]
        self._send(200, {"name": self.path})


@contextlib.contextmanager
def serve(directory: pathlib.Path):
    handler = functools.partial(MockFirebaseHandler, directory=str(directory))

    class Server(socketserver.ThreadingTCPServer):
        allow_reuse_address = True
        daemon_threads = True

        def handle_error(self, request, client_address):  # noqa: ARG002
            pass

    with Server(("127.0.0.1", 0), handler) as httpd:
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        try:
            yield f"http://127.0.0.1:{httpd.server_address[1]}"
        finally:
            httpd.shutdown()


CODE = "sensortestcode1234567890"
LIVE_PATH = "/v1/projects/test-project/databases/(default)/documents/nurseries/%s-live" % CODE


def iso(minutes_ago: int) -> str:
    stamp = datetime.datetime.utcnow() - datetime.timedelta(minutes=minutes_ago)
    return stamp.strftime("%Y-%m-%dT%H:%M:%S") + ".000Z"


def main() -> int:
    checks: list[tuple[str, bool, str]] = []

    def check(name, condition, detail=""):
        checks.append((name, bool(condition), detail))

    with serve(ROOT) as base, sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=chromium_path())
        page = browser.new_page(viewport={"width": 1180, "height": 900})
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))

        def goto(h):
            # A same-URL hash navigation would not re-render, so always reload:
            # the card under test is built during render.
            page.goto(base + "/" + h)
            page.reload()
            page.wait_for_timeout(250)

        goto("#/")
        page.evaluate(
            """([origin, code]) => window.BonsaiSync.setConfig({
                enabled: true, projectId: 'test-project', apiKey: 'k', code,
                authBase: origin, firestoreBase: origin })""",
            [base, CODE])

        # --- with no live document, the card hides itself
        olive = page.evaluate("""() => {
            const p = window.BonsaiStore.addPlant({name: 'Arbequina #1', profileId: 'arbequina-olive'});
            return p.id;
        }""")
        goto("#/")
        page.wait_for_timeout(400)
        check("card hides when no Pi has ever reported",
              page.evaluate("() => { const c = document.querySelector('.card h2'); "
                            "return !Array.from(document.querySelectorAll('.card:not([hidden]) h2'))"
                            ".some(h => h.textContent === 'Live sensors'); }"))

        # --- a fresh live document renders
        DOCUMENTS[LIVE_PATH] = json.dumps({
            "at": iso(2),
            "air": {"tempF": 74.6, "rh": 54.0, "pressureHpa": 1006.2, "lux": 9150},
            "moisture": {olive: 41.5},
            "chill": {olive: 132},
            "relays": {"humidifier": True, "fan": False},
        })
        goto("#/")
        page.wait_for_selector(".card:not([hidden]) h2:has-text('Live sensors')")
        card = page.locator(".card:has(h2:text('Live sensors'))")
        check("fresh reading shows a live chip",
              card.locator(".chip-good:has-text('live')").count() == 1)
        check("air readings render",
              card.locator(".month-fact:has-text('74.6 °F')").count() == 1
              and card.locator(".month-fact:has-text('9150 lux')").count() == 1)
        check("moisture is named by plant, not id",
              card.locator(".month-fact:has-text('Arbequina #1 moisture')").count() == 1)
        check("chill hours shown for the olive",
              card.locator(".month-fact:has-text('132 h')").count() == 1)
        check("relay states shown",
              card.locator(".month-fact:has-text('humidifier')").count() == 1)

        # --- plant page narrows to that plant
        goto(f"#/p/{olive}")
        page.wait_for_selector(".card:not([hidden]) h2:has-text('Live sensors')")
        plant_card = page.locator(".card:has(h2:text('Live sensors'))")
        check("plant page shows its own moisture",
              plant_card.locator(".month-fact:has-text('moisture')").count() == 1)

        # --- a quiet Pi is called stale, loudly
        DOCUMENTS[LIVE_PATH] = json.dumps({"at": iso(45), "air": {"tempF": 70.0}})
        goto("#/")
        page.wait_for_selector(".card:not([hidden]) h2:has-text('Live sensors')")
        card = page.locator(".card:has(h2:text('Live sensors'))")
        check("stale chip after 15 quiet minutes",
              card.locator(".chip-bad:has-text('stale')").count() == 1)
        check("stale card says what to check",
              card.locator(".hint:has-text('journalctl')").count() == 1)

        # --- a minimal sensor entry (only the keys it measured) flows through
        page.evaluate(
            """(olive) => window.BonsaiStore.mergeSnapshot({
                version: 1, plants: [], completions: [],
                entries: [{
                    id: 'sensor-' + olive + '-2026-08-16', plantId: olive,
                    at: '2026-08-16T12:00:00.000Z', auto: 'sensor',
                    tempLow: 52.1, tempHigh: 56.4, humidity: 47,
                    moisture: 21, chill: 132,
                    updatedAt: new Date().toISOString()
                }]
            })""", olive)
        goto(f"#/p/{olive}")
        page.wait_for_selector(".stat-tile")
        # Temperature tiles render at 0 decimals, so 52.1 displays as 52.
        check("sensor tempLow reaches the tiles",
              page.locator(".stat-tile:has(.stat-label:has-text('Low temp')) .stat-value:has-text('52')").count() == 1)
        check("sensor moisture reaches the tiles",
              page.locator(".stat-tile:has(.stat-label:has-text('Moisture')) .stat-value:has-text('21')").count() == 1)
        check("sensor entry appears in history, labelled",
              page.locator("td:has-text('sensor summary')").count() >= 1)
        csv = page.evaluate("() => window.BonsaiStore.exportCsv()")
        check("sensor entry reaches the CSV with auto=sensor",
              any("sensor" in line and "52.1" in line for line in csv.splitlines()))

        # --- and hand checks still coexist: log one on the same plant
        form = page.locator("form.card:has(h2:text('Log a check'))")
        form.locator("[name=ph]").fill("7.1")
        form.locator("button[type=submit]").click()
        page.wait_for_timeout(200)
        count = page.evaluate("(id) => window.BonsaiStore.entriesFor(id).length", olive)
        check("hand check coexists with the sensor entry", count == 2, f"{count} entries")

        check("no page errors", not errors, "; ".join(errors[:3]))
        browser.close()

    width = max(len(name) for name, _, _ in checks)
    failed = 0
    for name, ok, detail in checks:
        print(f"  {'PASS' if ok else 'FAIL'}  {name.ljust(width)}  {detail if not ok else ''}".rstrip())
        failed += 0 if ok else 1
    print(f"\n{len(checks) - failed}/{len(checks)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
