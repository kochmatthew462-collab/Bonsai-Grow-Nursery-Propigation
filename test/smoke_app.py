"""End-to-end check of the tracker in a real browser.

Drives the app the way the nursery would: add plants on three different care
profiles (indoor bonsai bench, container bergamot, container olive), log checks
carrying the full set of factors, then take the QR code the label sheet actually
rendered, decode it with zxing-cpp, and follow the decoded URL to confirm it
lands on the right plant. That last step is the one that matters -- it proves a
printed label routes to the plant it names, rather than merely that a QR code
was drawn.

Usage:
    pip install playwright zxing-cpp numpy pillow
    python3 test/smoke_app.py [--screenshots DIR]
"""

import argparse
import base64
import contextlib
import functools
import http.server
import io
import pathlib
import socketserver
import threading

import numpy as np
import zxingcpp
from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent


def chromium_path() -> str | None:
    """Use the preinstalled Chromium when there is one; otherwise let Playwright decide."""
    for candidate in sorted(pathlib.Path("/opt/pw-browsers").glob("chromium-*/chrome-linux/chrome")):
        return str(candidate)
    return None


@contextlib.contextmanager
def serve(directory: pathlib.Path):
    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args):  # keep the test output to the checks alone
            pass

    handler = functools.partial(QuietHandler, directory=str(directory))

    class Server(socketserver.TCPServer):
        allow_reuse_address = True

        def handle_error(self, request, client_address):  # noqa: ARG002
            pass

    with Server(("127.0.0.1", 0), handler) as httpd:
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            yield f"http://127.0.0.1:{httpd.server_address[1]}/"
        finally:
            httpd.shutdown()


def add_plant(page, name, species, profile_id, stage="stem graft"):
    page.goto_hash("#/")
    form = page.locator("form.card:has(h2:text('Add a plant'))")
    form.locator("[name=name]").fill(name)
    form.locator("[name=species]").fill(species)
    form.locator("[name=profileId]").select_option(profile_id)
    form.locator("[name=stage]").select_option(stage)
    form.locator("button[type=submit]").click()
    page.wait_for_selector("h2:has-text('Log a check')")
    return page.url.split("#/p/")[1]


def log_check(page, plant_id, **values):
    """Fill whichever named fields exist on this plant's profile-driven form."""
    page.goto_hash(f"#/p/{plant_id}")
    page.wait_for_selector("h2:has-text('Log a check')")
    form = page.locator("form.card:has(h2:text('Log a check'))")
    for key, value in values.items():
        control = form.locator(f"[name={key}]")
        if control.count() == 0:
            raise AssertionError(f"field {key!r} not on the form for {plant_id}")
        if isinstance(value, bool):
            if value:
                control.check()
        elif control.evaluate("el => el.tagName") == "SELECT":
            control.select_option(value)
        else:
            control.fill(str(value))
    form.locator("button[type=submit]").click()
    page.wait_for_timeout(110)


def decode_svg(page, selector: str) -> str:
    """Rasterise a rendered QR <svg> through the browser and decode it."""
    png_b64 = page.evaluate(
        """(sel) => new Promise((resolve) => {
            const svg = document.querySelector(sel);
            const markup = new XMLSerializer().serializeToString(svg);
            const img = new Image();
            img.onload = () => {
                const scale = 8;
                const canvas = document.createElement('canvas');
                const box = svg.viewBox.baseVal;
                canvas.width = box.width * scale;
                canvas.height = box.height * scale;
                const ctx = canvas.getContext('2d');
                ctx.imageSmoothingEnabled = false;
                ctx.fillStyle = '#fff';
                ctx.fillRect(0, 0, canvas.width, canvas.height);
                ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
                resolve(canvas.toDataURL('image/png').split(',')[1]);
            };
            img.src = 'data:image/svg+xml;base64,' + btoa(unescape(encodeURIComponent(markup)));
        })""",
        selector,
    )
    image = Image.open(io.BytesIO(base64.b64decode(png_b64))).convert("L")
    result = zxingcpp.read_barcode(np.array(image))
    return result.text if result else ""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--screenshots", type=pathlib.Path)
    args = parser.parse_args()
    if args.screenshots:
        args.screenshots.mkdir(parents=True, exist_ok=True)

    checks: list[tuple[str, bool, str]] = []

    def check(name, condition, detail=""):
        checks.append((name, bool(condition), detail))

    with serve(ROOT) as base_url, sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=chromium_path())
        page = browser.new_page(viewport={"width": 1180, "height": 900})

        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)

        def goto_hash(h):
            page.goto(base_url + h)
            page.wait_for_timeout(110)

        page.goto_hash = goto_hash

        goto_hash("#/")
        check("app boots", page.locator("h1:has-text('Nursery')").count() == 1)

        juniper = add_plant(page, "Shohin juniper #4", "Juniperus procumbens 'Nana'",
                            "bench-median", "cutting")
        bergamot = add_plant(page, "Bergamot #1", "Citrus bergamia", "bergamot")
        olive = add_plant(page, "Arbequina #1", "Olea europaea 'Arbequina'", "arbequina-olive")
        check("three plants on three profiles", len({juniper, bergamot, olive}) == 3)

        # --- bench tree: the packet's factors, ending in band
        bench_readings = [
            ("2026-05-03", 6.3, 52, 1.0, 24, 64, 75, 55, 9200, 4),
            ("2026-05-17", 6.4, 48, 1.1, 29, 65, 76, 57, 9400, 4),
            ("2026-06-07", 6.2, 55, 1.2, 35, 66, 77, 54, 9100, 5),
            ("2026-06-28", 6.3, 45, 1.1, 41, 65, 76, 56, 9300, 5),
        ]
        for date, ph, moisture, ec, growth, low, high, rh, lux, vigor in bench_readings:
            log_check(page, juniper, at=date, ph=ph, moisture=moisture, ec=ec, growth=growth,
                      tempLow=low, tempHigh=high, humidity=rh, light=lux, vigor=vigor,
                      watered=True, waterMl=250, fertilised=True, fertiliser="Biogold")

        goto_hash(f"#/p/{juniper}")
        page.wait_for_selector(".chart-svg")
        check("bench profile charts every tracked factor",
              page.locator(".chart-grid-cards > .card").count() == 8,
              f"{page.locator('.chart-grid-cards > .card').count()} chart cards")
        check("this-month calendar shown",
              page.locator("h2:has-text('This month')").count() == 1)
        check("current month row highlighted", page.locator("tr.row-now").count() >= 1)
        check("winter floor stated", page.locator(".floor-note").count() == 1,
              page.locator(".floor-note").inner_text() if page.locator(".floor-note").count() else "absent")
        check("temperature drawn as one range chart",
              page.locator(".card:has(h2:text('Air temperature')) .legend-item").count() == 2)
        check("target bands shaded", page.locator("rect.chart-band").count() >= 4,
              f"{page.locator('rect.chart-band').count()} bands")
        check("in-band status shown", page.locator(".stat-tile .chip-good").count() >= 3,
              f"{page.locator('.stat-tile .chip-good').count()} good chips")
        check("full year table available",
              page.locator("summary:has-text('The year on one page')").count() == 1)

        if args.screenshots:
            page.screenshot(path=str(args.screenshots / "bench-plant.png"), full_page=True)

        # --- bergamot: an out-of-band pH must be called out, not just plotted
        log_check(page, bergamot, at="2026-06-05", ph=7.8, moisture=25, ec=1.4, growth=140,
                  tempLow=58, tempHigh=88, humidity=55, watered=True,
                  graftChecked=True, suckersRemoved=True, note="Two suckers below the graft.")
        log_check(page, bergamot, at="2026-06-20", ph=7.6, moisture=22, ec=1.5, growth=147,
                  tempLow=61, tempHigh=91, humidity=52, watered=True,
                  pestSeen=True, pestType="citrus leaf miner")
        goto_hash(f"#/p/{bergamot}")
        page.wait_for_selector(".chart-svg")
        check("out-of-band pH flagged", page.locator(".stat-tile .chip-bad, .stat-tile .chip-warn").count() >= 1,
              "no warn/bad chip on a pH of 7.6 against a 6.0-7.0 band")
        check("graft and sucker work logged",
              page.locator("td:has-text('Rootstock suckers removed')").count() == 1)
        check("pest sighting logged", page.locator("td:has-text('Pest seen')").count() == 1)
        check("bergamot watch list present",
              page.locator(".watch-item").count() >= 6,
              f"{page.locator('.watch-item').count()} watch items")
        check("bergamot has a move field",
              page.locator("form.card:has(h2:text('Log a check')) [name=moved]").count() == 1)
        if args.screenshots:
            page.screenshot(path=str(args.screenshots / "bergamot.png"), full_page=True)

        # --- olive: chill hours tracked, humidity and light are not
        log_check(page, olive, at="2026-01-15", ph=7.2, moisture=20, growth=95,
                  tempLow=52, tempHigh=56, chill=240)
        goto_hash(f"#/p/{olive}")
        page.wait_for_selector(".chart-svg")
        olive_form = page.locator("form.card:has(h2:text('Log a check'))")
        check("olive tracks chill hours", olive_form.locator("[name=chill]").count() == 1)
        # The handbook wants winter humidity under 50% with air movement, and
        # 8+ hours of direct light, so the olive tracks both.
        check("olive tracks humidity and light per its handbook",
              olive_form.locator("[name=humidity]").count() == 1
              and olive_form.locator("[name=light]").count() == 1)
        check("olive is seasonal, so it has a move field",
              olive_form.locator("[name=moved]").count() == 1)
        check("olive vigor tracked", olive_form.locator("[name=vigor]").count() == 1)
        check("olive winter warning surfaced",
              page.locator('.watch-item[data-severity="high"]').count() >= 3,
              f"{page.locator('.watch-item[data-severity=high]').count()} high-severity items")
        if args.screenshots:
            page.screenshot(path=str(args.screenshots / "olive.png"), full_page=True)

        # --- hover readout still works (hover() scrolls the chart into view;
        # a raw mouse.move would miss it, since these cards sit far down the page)
        goto_hash(f"#/p/{juniper}")
        page.wait_for_selector(".chart-svg")
        page.locator(".chart-holder svg").first.hover()
        page.wait_for_timeout(200)
        tooltip = page.locator(".chart-tooltip:not([hidden])")
        check("hover tooltip", tooltip.count() >= 1)
        check("tooltip carries a value and a date",
              tooltip.count() >= 1 and any(c.isdigit() for c in tooltip.first.inner_text()),
              tooltip.first.inner_text() if tooltip.count() else "no tooltip")

        # --- the label loop
        goto_hash("#/labels")
        page.wait_for_selector(".label-cell svg")
        check("a label per plant", page.locator(".label-cell").count() == 3)

        decoded = decode_svg(page, ".label-cell:first-child svg")
        decoded_id = decoded.rsplit("#/p/", 1)[-1] if "#/p/" in decoded else ""
        names = {juniper: "Shohin juniper #4", bergamot: "Bergamot #1", olive: "Arbequina #1"}
        check("label QR decodes", decoded.startswith("http") and decoded_id in names,
              f"decoded {decoded!r}")

        page.goto(decoded)
        page.wait_for_timeout(200)
        heading = page.locator("h1").first.inner_text()
        check("scanned label opens its plant", heading == names.get(decoded_id),
              f"landed on {heading!r}, expected {names.get(decoded_id)!r}")

        # --- export round-trip
        goto_hash("#/backup")
        csv = page.evaluate("window.BonsaiStore.exportCsv()")
        header = csv.splitlines()[0].split(",")
        total_checks = len(bench_readings) + 2 + 1
        check("CSV has a row per check", len(csv.strip().splitlines()) == total_checks + 1,
              f"{len(csv.strip().splitlines())} lines")
        for column in ("ec_ms_cm", "temp_low_f", "humidity_pct", "chill_hours", "vigor", "suckers_removed", "profile"):
            check(f"CSV carries {column}", column in header)

        backup = page.evaluate("window.BonsaiStore.exportJson()")
        page.evaluate("window.BonsaiStore.replaceAll({version:1,plants:[],entries:[]})")
        added = page.evaluate("(text) => window.BonsaiStore.importJson(text)", backup)
        check("import restores everything",
              added["plants"] == 3 and added["entries"] == total_checks, str(added))
        again = page.evaluate("(text) => window.BonsaiStore.importJson(text)", backup)
        check("re-import does not duplicate", again["plants"] == 0 and again["entries"] == 0, str(again))

        goto_hash("#/")
        check("nursery list shows status", page.locator("tbody .chip").count() >= 2)
        if args.screenshots:
            page.screenshot(path=str(args.screenshots / "nursery-list.png"), full_page=True)
            page.emulate_media(color_scheme="dark")
            goto_hash(f"#/p/{juniper}")
            page.wait_for_selector(".chart-svg")
            page.screenshot(path=str(args.screenshots / "bench-plant-dark.png"), full_page=True)
            page.emulate_media(color_scheme="light")

        check("no console or page errors", not errors, "; ".join(errors[:3]))
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
