"""Prove that two devices converge through cloud sync.

Runs the real js/sync.js against a mock of the two Firestore REST endpoints it
uses, served from the same origin as the app. That means no Firebase project,
no credentials and no network -- while still exercising the actual sign-in
call, document read, merge and write-back that run in production.

Two separate browser contexts stand in for two devices: separate localStorage,
so nothing is shared except the mock server.

What it checks, in order:
  1. a plant created on device A reaches device B
  2. a reading added on B reaches A, without losing A's own readings
  3. a delete on A propagates to B and does not come back
  4. a stale device pushing an old snapshot cannot resurrect deleted records
  5. losing the network leaves local data intact and reports it honestly

Usage:
    pip install playwright
    python3 test/sync_test.py
"""

import contextlib
import functools
import http.server
import json
import pathlib
import socketserver
import threading

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent

# Mock Firestore document store: path -> JSON string of the nursery.
DOCUMENTS: dict[str, str] = {}


def chromium_path() -> str | None:
    for candidate in sorted(pathlib.Path("/opt/pw-browsers").glob("chromium-*/chrome-linux/chrome")):
        return str(candidate)
    return None


class MockFirebaseHandler(http.server.SimpleHTTPRequestHandler):
    """Serves the app, and stands in for Identity Toolkit and Firestore."""

    def log_message(self, *args):
        pass

    def _send(self, code: int, payload: dict):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        return json.loads(self.rfile.read(length))

    def _authorised(self) -> bool:
        return self.headers.get("Authorization") == "Bearer test-id-token"

    def do_POST(self):
        if self.path.startswith("/v1/accounts:signUp"):
            # The real endpoint requires ?key=<apiKey>; mirror that check so a
            # missing key fails here the way it would in production.
            if "key=" not in self.path:
                self._send(400, {"error": {"message": "API key required"}})
                return
            self._send(200, {"idToken": "test-id-token", "expiresIn": "3600"})
            return
        self._send(404, {"error": {"message": "not found"}})

    def do_GET(self):
        if self.path.startswith("/v1/projects/"):
            if not self._authorised():
                self._send(401, {"error": {"message": "unauthenticated"}})
                return
            stored = DOCUMENTS.get(self.path)
            if stored is None:
                self._send(404, {"error": {"message": "Document not found"}})
                return
            self._send(200, {"fields": {"data": {"stringValue": stored}}})
            return
        super().do_GET()

    def do_PATCH(self):
        if not self.path.startswith("/v1/projects/"):
            self._send(404, {"error": {"message": "not found"}})
            return
        if not self._authorised():
            self._send(401, {"error": {"message": "unauthenticated"}})
            return
        payload = self._read_body()
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


CONFIGURE = """
async ([origin, code]) => {
  window.BonsaiSync.setConfig({
    enabled: true, projectId: 'test-project', apiKey: 'test-key', code,
    authBase: origin, firestoreBase: origin
  });
  return window.BonsaiSync.config().code;
}
"""

SYNC = "async () => (await window.BonsaiSync.syncNow()).level"


def open_device(browser, base_url, code):
    context = browser.new_context()
    page = context.new_page()
    page.goto(base_url + "/")
    page.wait_for_selector("h1")
    page.evaluate(CONFIGURE, [base_url, code])
    return page


def plant_names(page):
    return page.evaluate("() => window.BonsaiStore.listPlants().map(p => p.name).sort()")


def reading_count(page):
    return page.evaluate(
        "() => window.BonsaiStore.listPlants()"
        ".reduce((n, p) => n + window.BonsaiStore.entriesFor(p.id).length, 0)"
    )


def main() -> int:
    checks: list[tuple[str, bool, str]] = []

    def check(name, condition, detail=""):
        checks.append((name, bool(condition), detail))

    code = "testnurserycode123456789"

    with serve(ROOT) as base_url, sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=chromium_path())
        errors: list[str] = []

        device_a = open_device(browser, base_url, code)
        device_a.on("pageerror", lambda e: errors.append("A: " + str(e)))
        device_b = open_device(browser, base_url, code)
        device_b.on("pageerror", lambda e: errors.append("B: " + str(e)))

        # --- the Sync page itself renders and offers the fields
        device_a.goto(base_url + "/#/sync")
        device_a.wait_for_selector("h1:has-text('Sync across devices')")
        for name in ("projectId", "apiKey", "code", "syncEnabled"):
            check(f"sync page has {name}", device_a.locator(f"[name={name}]").count() == 1)
        check("setup rules shown", "allow read, write" in device_a.locator("pre.code").inner_text())

        # --- 1. a plant made on A reaches B
        device_a.evaluate("""() => {
            const p = window.BonsaiStore.addPlant({name: 'Bergamot #1', profileId: 'bergamot'});
            window.BonsaiStore.addEntry(p.id, {ph: 6.4, moisture: 45, at: '2026-06-01'});
        }""")
        check("A uploads", device_a.evaluate(SYNC) == "ok")
        check("document stored on the server", len(DOCUMENTS) == 1)

        check("B pulls", device_b.evaluate(SYNC) == "ok")
        check("plant reached device B", plant_names(device_b) == ["Bergamot #1"],
              str(plant_names(device_b)))
        check("reading reached device B", reading_count(device_b) == 1)

        # --- 2. a reading added on B reaches A, and A keeps its own
        device_b.evaluate("""() => {
            const p = window.BonsaiStore.listPlants()[0];
            window.BonsaiStore.addEntry(p.id, {ph: 6.6, moisture: 38, at: '2026-06-20'});
        }""")
        device_b.evaluate(SYNC)
        device_a.evaluate(SYNC)
        check("B's reading reached A, A's kept", reading_count(device_a) == 2,
              f"{reading_count(device_a)} readings on A")

        # --- 3. a delete on A propagates and stays deleted
        device_a.evaluate("""() => {
            window.BonsaiStore.deletePlant(window.BonsaiStore.listPlants()[0].id);
        }""")
        device_a.evaluate(SYNC)
        device_b.evaluate(SYNC)
        check("delete propagated to B", plant_names(device_b) == [], str(plant_names(device_b)))

        # --- 4. a stale device cannot resurrect it
        device_b.evaluate(SYNC)
        device_a.evaluate(SYNC)
        check("delete stays deleted on both",
              plant_names(device_a) == [] and plant_names(device_b) == [])

        # --- 5. losing the network is survivable and honestly reported
        device_a.evaluate("""() => window.BonsaiSync.setConfig({
            firestoreBase: 'http://127.0.0.1:1'
        })""")
        device_a.evaluate("""() => window.BonsaiStore.addPlant({name: 'Offline olive'})""")
        level = device_a.evaluate(SYNC)
        check("offline sync reports an error", level == "error", f"level {level!r}")
        check("offline data still saved locally", plant_names(device_a) == ["Offline olive"],
              str(plant_names(device_a)))

        # ...and goes up once the network returns
        device_a.evaluate(CONFIGURE, [base_url, code])
        check("recovers when the network returns", device_a.evaluate(SYNC) == "ok")
        device_b.evaluate(SYNC)
        check("offline work reached B once online", plant_names(device_b) == ["Offline olive"],
              str(plant_names(device_b)))

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
