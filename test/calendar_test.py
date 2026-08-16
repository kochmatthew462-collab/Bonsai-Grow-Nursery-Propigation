"""Check the master calendar and the derived drip log.

The drip log is the part worth testing hard, because it writes data nobody
typed. It must be arithmetically right, idempotent (it re-runs on every render
and syncs between devices, so a duplicate would multiply your water record),
bounded (never inventing months of history on first use), and honest about
whether the flow rate is calibrated or nominal.

Usage:
    pip install playwright
    python3 test/calendar_test.py
"""

import contextlib
import datetime
import functools
import http.server
import pathlib
import socketserver
import threading

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent


def chromium_path() -> str | None:
    for candidate in sorted(pathlib.Path("/opt/pw-browsers").glob("chromium-*/chrome-linux/chrome")):
        return str(candidate)
    return None


@contextlib.contextmanager
def serve(directory: pathlib.Path):
    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

    handler = functools.partial(QuietHandler, directory=str(directory))

    class Server(socketserver.TCPServer):
        allow_reuse_address = True

        def handle_error(self, request, client_address):  # noqa: ARG002
            pass

    with Server(("127.0.0.1", 0), handler) as httpd:
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        try:
            yield f"http://127.0.0.1:{httpd.server_address[1]}/"
        finally:
            httpd.shutdown()


def add_plant(page, base, name, profile_id, started_on):
    page.goto(base + "#/")
    page.wait_for_timeout(120)
    form = page.locator("form.card:has(h2:text('Add a plant'))")
    form.locator("[name=name]").fill(name)
    form.locator("[name=profileId]").select_option(profile_id)
    form.locator("[name=startedOn]").fill(started_on)
    form.locator("button[type=submit]").click()
    page.wait_for_selector("h2:has-text('Log a check')")
    return page.url.split("#/p/")[1]


def drip_entries(page, plant_id):
    return page.evaluate(
        "(id) => window.BonsaiStore.entriesFor(id).filter(e => e.auto === 'drip')"
        ".map(e => ({at: e.at.slice(0,10), ml: e.waterMl, note: e.note}))",
        plant_id,
    )


def main() -> int:
    checks: list[tuple[str, bool, str]] = []

    def check(name, condition, detail=""):
        checks.append((name, bool(condition), detail))

    today = datetime.date.today()
    started = (today - datetime.timedelta(days=40)).isoformat()

    with serve(ROOT) as base, sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=chromium_path())
        page = browser.new_page(viewport={"width": 1180, "height": 900})
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))

        # --- drip: a bench tree on the Parrot's beak allocation (2 emitters)
        pb = add_plant(page, base, "Parrot's beak #1", "parrots-beak", started)
        entries = drip_entries(page, pb)
        check("drip log auto-created", len(entries) > 10, f"{len(entries)} entries")

        # Bounded: never more than the 30-day backfill window.
        oldest = min(e["at"] for e in entries)
        floor = (today - datetime.timedelta(days=31)).isoformat()
        check("backfill is bounded to 30 days", oldest >= floor, f"oldest {oldest}")

        # Never on a Sunday — that is the hand-watering day by design.
        sundays = [e for e in entries
                   if datetime.date.fromisoformat(e["at"]).weekday() == 6]
        check("never schedules a Sunday", not sundays, f"{len(sundays)} Sunday entries")

        # Arithmetic: 2 emitters x 11.7 ml/min nominal x the season's runtime.
        summary = page.evaluate(
            """(id) => {
                const p = window.BonsaiStore.getPlant(id);
                const prof = window.BonsaiProfiles.get(p.profileId);
                return window.BonsaiCalendar.dripSummary(prof, p, new Date());
            }""", pb)
        expected = round(summary["emitters"] * summary["mlPerMin"] * summary["minutes"])
        recent = [e for e in entries if e["at"] > (today - datetime.timedelta(days=7)).isoformat()]
        check("volume matches emitters x flow x runtime",
              recent and all(e["ml"] == expected for e in recent),
              f"expected {expected}, got {sorted({e['ml'] for e in recent})}")
        check("flow is flagged as nominal until calibrated",
              summary["calibrated"] is False and "nominal flow" in entries[-1]["note"],
              entries[-1]["note"])

        # --- idempotent across reloads: this runs on every render and syncs
        before = len(entries)
        for _ in range(3):
            page.goto(base + f"#/p/{pb}")
            page.wait_for_timeout(150)
        check("re-running creates no duplicates", len(drip_entries(page, pb)) == before,
              f"{before} then {len(drip_entries(page, pb))}")

        # --- calibration changes the derived volume
        page.goto(base + f"#/p/{pb}")
        page.wait_for_selector("h2:has-text('Drip system')")
        page.locator("[name=mlPerMin]").fill("9.4")
        page.locator("button:has-text('Save calibration')").click()
        page.wait_for_timeout(200)
        after = page.evaluate(
            """(id) => {
                const p = window.BonsaiStore.getPlant(id);
                const prof = window.BonsaiProfiles.get(p.profileId);
                return window.BonsaiCalendar.dripSummary(prof, p, new Date());
            }""", pb)
        check("calibration is used once saved",
              after["calibrated"] is True and after["mlPerMin"] == 9.4,
              str(after))
        check("calibrated flow shown as such",
              page.locator(".card:has(h2:text('Drip system')) .chip-good").count() == 1)

        # --- the pomegranate's winter clamp must not log water
        clamped = page.evaluate(
            """() => {
                const prof = window.BonsaiProfiles.get('dwarf-pomegranate');
                const jan = new Date(2027, 0, 12);           // a Tuesday in winter
                return window.BonsaiCalendar.dripOn(prof, {}, jan);
            }""")
        check("winter clamp logs nothing for the pomegranate", clamped is None, str(clamped))

        # --- master calendar
        add_plant(page, base, "Arbequina #1", "arbequina-olive", started)
        page.goto(base + "#/calendar")
        page.wait_for_selector("h1:has-text('Master calendar')")
        rows = page.locator(".task-row")
        check("calendar lists tasks across plants", rows.count() > 3, f"{rows.count()} rows")
        check("tasks name their plant",
              page.locator(".task-meta a:has-text(\"Parrot's beak #1\")").count() >= 1)
        check("tasks carry a category", page.locator(".cat-chip").count() > 3)

        first_title = rows.first.locator(".task-title").inner_text()
        rows.first.locator("button:has-text('Mark done')").click()
        page.wait_for_timeout(200)
        done_section = page.locator(".card:has(h2:text('Done this year')) .task-row")
        check("marking done moves it to the done group",
              done_section.count() == 1
              and done_section.first.locator(".task-title").inner_text() == first_title,
              f"{done_section.count()} done rows")

        # Completion must survive a reload, and sync like any other record.
        page.goto(base + "#/calendar")
        page.wait_for_timeout(200)
        check("completion persists",
              page.locator(".card:has(h2:text('Done this year')) .task-row").count() == 1)
        snapshot = page.evaluate("() => window.BonsaiStore.snapshot()")
        check("completions travel in the sync snapshot",
              len(snapshot.get("completions", [])) == 1, str(snapshot.get("completions")))

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
