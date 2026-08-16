"""End-to-end check of the tracker in a real browser.

Drives the app the way the nursery would: add plants, log checks, open the
label sheet, then take the QR code the sheet actually rendered, decode it with
zxing-cpp, and follow the decoded URL to confirm it lands on the right plant.
That last step is the one that matters -- it proves a printed label routes to
the plant it names, rather than merely that a QR code was drawn.

Usage:
    pip install playwright zxing-cpp numpy pillow
    python3 test/smoke_app.py [--screenshots DIR]
"""

import argparse
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


def add_plant(page, name, species, stage):
    page.goto_hash("#/")
    page.fill("form.card input[type=text] >> nth=0", name)
    page.fill("form.card input[type=text] >> nth=1", species)
    page.select_option("form.card select", stage)
    page.click("button:has-text('Add plant')")
    page.wait_for_selector("h2:has-text('Log a check')")
    return page.url.split("#/p/")[1]


def log_check(page, plant_id, *, date, ph=None, moisture=None, growth=None,
              watered=False, water_ml=None, fertilised=False, fertiliser=""):
    page.goto_hash(f"#/p/{plant_id}")
    page.wait_for_selector("h2:has-text('Log a check')")
    form = page.locator("form.card:has(h2:text('Log a check'))")
    form.locator("input[type=date]").fill(date)
    if ph is not None:
        form.locator("input[type=number]").nth(0).fill(str(ph))
    if moisture is not None:
        form.locator("input[type=number]").nth(1).fill(str(moisture))
    if growth is not None:
        form.locator("input[type=number]").nth(2).fill(str(growth))
    if watered:
        form.locator("input[type=checkbox]").nth(0).check()
        if water_ml is not None:
            form.locator("input[type=number]").nth(3).fill(str(water_ml))
    if fertilised:
        form.locator("input[type=checkbox]").nth(1).check()
        form.locator("input[type=text]").nth(0).fill(fertiliser)
    form.locator("button[type=submit]").click()
    page.wait_for_timeout(120)


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
    import base64
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
            page.wait_for_timeout(120)

        page.goto_hash = goto_hash

        goto_hash("#/")
        check("app boots", page.locator("h1:has-text('Nursery')").count() == 1)

        juniper = add_plant(page, "Shohin juniper #4", "Juniperus procumbens 'Nana'", "cutting")
        maple = add_plant(page, "Trident maple A2", "Acer buergerianum", "air layer")
        check("two plants added", juniper != maple and len(juniper) == 6)

        readings = [
            ("2026-05-02", 6.8, 7.0, 24, True, 250, True, "Biogold"),
            ("2026-05-16", 6.6, 5.5, 29, True, 240, False, ""),
            ("2026-06-01", 6.4, 4.0, 35, True, 260, True, "Biogold"),
            ("2026-06-18", 6.3, 6.5, 41, True, 250, False, ""),
            ("2026-07-04", 6.1, 3.5, 48, True, 300, True, "fish emulsion"),
            ("2026-07-22", 6.2, 5.0, 55, True, 280, False, ""),
        ]
        for date, ph, moisture, growth, watered, ml, fert, name in readings:
            log_check(page, juniper, date=date, ph=ph, moisture=moisture, growth=growth,
                      watered=watered, water_ml=ml, fertilised=fert, fertiliser=name)
        log_check(page, maple, date="2026-06-10", ph=6.9, moisture=6.0, growth=12, watered=True, water_ml=180)
        log_check(page, maple, date="2026-07-10", ph=6.7, moisture=4.5, growth=19, watered=True, water_ml=200)

        goto_hash(f"#/p/{juniper}")
        page.wait_for_selector(".chart-svg")
        check("trend charts render", page.locator(".chart-svg").count() >= 4,
              f"found {page.locator('.chart-svg').count()}")
        check("stat tiles render", page.locator(".stat-tile").count() == 5)
        check("history rows", page.locator("table tbody tr").count() > 0)

        # Hover the pH chart and confirm the tooltip appears with a value.
        chart = page.locator(".chart-holder").first
        box = chart.bounding_box()
        page.mouse.move(box["x"] + box["width"] * 0.5, box["y"] + box["height"] * 0.5)
        page.wait_for_timeout(150)
        check("hover tooltip", page.locator(".chart-tooltip:not([hidden])").count() >= 1)

        if args.screenshots:
            page.screenshot(path=str(args.screenshots / "plant-detail.png"), full_page=True)

        # --- the label loop
        goto_hash("#/labels")
        page.wait_for_selector(".label-cell svg")
        check("a label per plant", page.locator(".label-cell").count() == 2)

        decoded = decode_svg(page, ".label-cell:first-child svg")
        expected_ids = {juniper, maple}
        decoded_id = decoded.rsplit("#/p/", 1)[-1] if "#/p/" in decoded else ""
        check("label QR decodes", decoded.startswith("http") and decoded_id in expected_ids,
              f"decoded {decoded!r}")

        if args.screenshots:
            page.screenshot(path=str(args.screenshots / "label-sheet.png"), full_page=True)

        # Follow the decoded URL exactly as a phone camera would.
        page.goto(decoded)
        page.wait_for_timeout(200)
        heading = page.locator("h1").first.inner_text()
        expected_name = "Shohin juniper #4" if decoded_id == juniper else "Trident maple A2"
        check("scanned label opens its plant", heading == expected_name,
              f"landed on {heading!r}, expected {expected_name!r}")

        # --- export round-trip
        goto_hash("#/backup")
        csv = page.evaluate("window.BonsaiStore.exportCsv()")
        check("CSV has a row per check", len(csv.strip().splitlines()) == len(readings) + 2 + 1,
              f"{len(csv.strip().splitlines())} lines")
        backup = page.evaluate("window.BonsaiStore.exportJson()")
        page.evaluate("window.BonsaiStore.replaceAll({version:1,plants:[],entries:[]})")
        added = page.evaluate("(text) => window.BonsaiStore.importJson(text)", backup)
        check("import restores everything", added["plants"] == 2 and added["entries"] == len(readings) + 2,
              str(added))
        again = page.evaluate("(text) => window.BonsaiStore.importJson(text)", backup)
        check("re-import does not duplicate", again["plants"] == 0 and again["entries"] == 0, str(again))

        goto_hash("#/")
        if args.screenshots:
            page.screenshot(path=str(args.screenshots / "nursery-list.png"), full_page=True)
            page.emulate_media(color_scheme="dark")
            goto_hash(f"#/p/{juniper}")
            page.wait_for_selector(".chart-svg")
            page.screenshot(path=str(args.screenshots / "plant-detail-dark.png"), full_page=True)
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
