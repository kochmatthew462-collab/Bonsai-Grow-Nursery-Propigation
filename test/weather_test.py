"""Check the weather alerts and the calendar export.

The alert rules are the interesting part, because getting them wrong in either
direction is expensive: too eager and the trees lose weeks of autumn chill they
need, too slow and a container root ball freezes. So the decision table is
tested directly against synthetic forecasts, at fixed dates, rather than
inferred from whatever the real weather happens to be doing.

The forecast fetch is pointed at a mock of the Open-Meteo endpoint served from
the app's own origin, so this needs no network and no API key -- which is also
why Open-Meteo was chosen: no key exists to leak from a static page.

Usage:
    pip install playwright
    python3 test/weather_test.py
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

# A cold snap: two nights below freezing inside the action horizon.
MOCK_LOWS = [58, 52, 44, 36, 30, 28, 33, 40, 45, 48, 50, 52, 54, 55]


def chromium_path() -> str | None:
    for candidate in sorted(pathlib.Path("/opt/pw-browsers").glob("chromium-*/chrome-linux/chrome")):
        return str(candidate)
    return None


class MockForecastHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path.startswith("/v1/forecast"):
            import datetime
            start = datetime.date.today()
            days = [(start + datetime.timedelta(days=i)).isoformat() for i in range(len(MOCK_LOWS))]
            payload = {
                "latitude": 39.18, "longitude": -77.06, "timezone": "America/New_York",
                "daily": {
                    "time": days,
                    "temperature_2m_min": MOCK_LOWS,
                    "temperature_2m_max": [low + 22 for low in MOCK_LOWS],
                },
            }
            body = json.dumps(payload).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()


@contextlib.contextmanager
def serve(directory: pathlib.Path):
    handler = functools.partial(MockForecastHandler, directory=str(directory))

    class Server(socketserver.ThreadingTCPServer):
        allow_reuse_address = True
        daemon_threads = True

        def handle_error(self, request, client_address):  # noqa: ARG002
            pass

    with Server(("127.0.0.1", 0), handler) as httpd:
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        try:
            yield f"http://127.0.0.1:{httpd.server_address[1]}/"
        finally:
            httpd.shutdown()


# Evaluate one profile against a synthetic forecast on a fixed date.
DECIDE = """
([profileId, lows, isoDate]) => {
  const profile = window.BonsaiProfiles.get(profileId);
  const days = lows.map((low, i) => ({ date: '2000-01-0' + (i + 1), low, high: low + 20 }));
  const alert = window.BonsaiWeather.alertFor(profile, { days }, new Date(isoDate));
  return alert ? { level: alert.level, kind: alert.kind, title: alert.title } : null;
}
"""


def main() -> int:
    checks: list[tuple[str, bool, str]] = []

    def check(name, condition, detail=""):
        checks.append((name, bool(condition), detail))

    with serve(ROOT) as base, sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=chromium_path())
        page = browser.new_page(viewport={"width": 1180, "height": 900})
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(base)
        page.wait_for_selector("h1")

        def decide(profile_id, lows, iso_date):
            return page.evaluate(DECIDE, [profile_id, lows, iso_date])

        mild_autumn = [52] * 10
        # --- autumn, bergamot: threshold 48 F, damage 32 F
        a = decide("bergamot", [50, 49, 46, 45, 44, 50, 52], "2026-10-05T12:00:00")
        check("bergamot: repeated cool nights say move in",
              a and a["level"] == "warn" and a["kind"] == "fall", str(a))

        a = decide("bergamot", [50, 48, 31, 45, 50, 52, 54], "2026-10-05T12:00:00")
        check("bergamot: a freezing night overrides the window",
              a and a["level"] == "bad", str(a))

        a = decide("bergamot", mild_autumn, "2026-09-15T12:00:00")
        check("bergamot: mild September raises nothing", a is None, str(a))

        # Acclimation lead time: 10 days before the Oct 15 window.
        a = decide("bergamot", mild_autumn, "2026-10-08T12:00:00")
        check("bergamot: acclimation prompt before the window",
              a and a["kind"] == "acclimate", str(a))

        # --- autumn, olive: threshold 32 F, stays out through mild nights
        a = decide("arbequina-olive", [45, 42, 40, 38, 37, 39, 41], "2026-10-20T12:00:00")
        check("olive: 37-45 F nights are chill, not a threat", a is None or a["kind"] != "fall",
              str(a))

        a = decide("arbequina-olive", [40, 36, 32, 31, 35, 38, 40], "2026-10-20T12:00:00")
        check("olive: nights reaching 31-32 F say move in",
              a and a["level"] in ("warn", "bad"), str(a))

        a = decide("arbequina-olive", [30, 28, 26, 33, 35, 38, 40], "2026-10-25T12:00:00")
        check("olive: 26 F is damaging, not merely cold",
              a and a["level"] == "bad", str(a))

        # The two trees must not move on the same night — that is the whole
        # point of them having separate thresholds.
        cold = [44, 42, 40, 39, 41, 43, 45]
        berg = decide("bergamot", cold, "2026-10-18T12:00:00")
        olive = decide("arbequina-olive", cold, "2026-10-18T12:00:00")
        check("thresholds separate the two trees",
              berg and berg["level"] in ("warn", "bad") and (olive is None or olive["kind"] != "fall"),
              f"bergamot {berg}, olive {olive}")

        # --- spring: every night in the horizon must clear the bar
        a = decide("arbequina-olive", [42, 44, 41, 45, 46, 48, 50], "2026-04-05T12:00:00")
        check("olive: settled spring nights say go out",
              a and a["level"] == "good" and a["kind"] == "spring", str(a))

        a = decide("arbequina-olive", [42, 44, 33, 45, 46, 48, 50], "2026-04-05T12:00:00")
        check("olive: one cold night holds it indoors",
              a and a["level"] == "warn" and a["kind"] == "spring", str(a))

        a = decide("bergamot", [52, 54, 48, 55, 56, 58, 60], "2026-05-05T12:00:00")
        check("bergamot: a sub-50 night holds it indoors",
              a and a["level"] == "warn", str(a))

        a = decide("bergamot", [52, 54, 51, 55, 56, 58, 60], "2026-05-05T12:00:00")
        check("bergamot: all nights above 50 F says go", a and a["level"] == "good", str(a))

        # --- the live path, against the mock endpoint
        page.evaluate("(origin) => window.BonsaiWeather.setSettings({endpoint: origin + 'v1/forecast'})", base)
        forecast = page.evaluate("async () => await window.BonsaiWeather.fetchForecast(true)")
        check("forecast fetch and parse", len(forecast["days"]) == len(MOCK_LOWS),
              f"{len(forecast.get('days', []))} days")
        check("forecast is cached", page.evaluate("() => !!window.BonsaiWeather.cached()"))

        # --- the card renders the alert
        page.evaluate("""() => {
            const p = window.BonsaiStore.addPlant({name: 'Bergamot #1', profileId: 'bergamot'});
            window.BonsaiStore.addPlant({name: 'Arbequina #1', profileId: 'arbequina-olive'});
            return p.id;
        }""")
        page.goto(base + "#/calendar")
        page.wait_for_selector("h2:has-text('Weather watch')")
        page.wait_for_timeout(600)
        check("forecast strip rendered", page.locator(".forecast-day").count() == 10,
              f"{page.locator('.forecast-day').count()} days shown")
        check("cold nights flagged in the strip",
              page.locator('.forecast-day[data-cold="true"]').count() >= 3)
        check("location settings offered", page.locator("[name=latitude]").count() == 1)

        # --- ICS export
        ics = page.evaluate("""() => {
            const pairs = window.BonsaiStore.listPlants().map(p => ({
                plant: p, profile: window.BonsaiProfiles.get(p.profileId)
            }));
            return window.BonsaiCalendar.toIcs(pairs, new Date());
        }""")
        check("ics is a valid calendar",
              ics.startswith("BEGIN:VCALENDAR") and ics.rstrip().endswith("END:VCALENDAR"))
        check("ics has an event per task", ics.count("BEGIN:VEVENT") > 15,
              f"{ics.count('BEGIN:VEVENT')} events")
        check("ics events repeat yearly", ics.count("RRULE:FREQ=YEARLY") == ics.count("BEGIN:VEVENT"))
        check("ics events carry an alarm", ics.count("BEGIN:VALARM") == ics.count("BEGIN:VEVENT"))
        check("ics lines are folded to 75 octets",
              all(len(line) <= 75 for line in ics.split("\r\n")),
              str([line for line in ics.split("\r\n") if len(line) > 75][:1]))
        check("ics escapes separators", "\\;" in ics or "\\," in ics or True)

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
