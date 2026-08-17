"""Check the professional-record layer: specimen fields, lineage, IPM detail,
photos, and the derived readouts (DLI, wire age, REI, quarantine).

The photo store is the piece with a real failure mode -- it must stay OUT of
the sync snapshot, because the whole nursery ships as one Firestore document
with a 1 MiB ceiling and a single raw phone photo would blow it. So this suite
asserts the exclusion, not just the upload.

Usage:
    pip install playwright pillow
    python3 test/pro_test.py
"""

import contextlib
import datetime
import functools
import http.server
import pathlib
import socketserver
import threading

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRATCH = pathlib.Path("/tmp/claude-0/-home-user-Bonsai-Grow-Nursery-Propigation/"
                       "87922c87-9dd4-5426-bd69-463339801715/scratchpad")


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


def main() -> int:
    checks: list[tuple[str, bool, str]] = []

    def check(name, condition, detail=""):
        checks.append((name, bool(condition), detail))

    # A photo bigger than the 640px cap, so the downscale has work to do.
    SCRATCH.mkdir(parents=True, exist_ok=True)
    photo_path = SCRATCH / "pro-test-photo.png"
    Image.new("RGB", (1200, 900), (34, 120, 60)).save(photo_path)

    with serve(ROOT) as base, sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=chromium_path())
        page = browser.new_page(viewport={"width": 1180, "height": 900})
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))

        def goto(h):
            page.goto(base + h)
            page.wait_for_timeout(140)

        goto("#/")

        # --- mother plant on the bench profile (has light + drip photoperiod)
        form = page.locator("form.card:has(h2:text('Add a plant'))")
        form.locator("[name=name]").fill("Mother ficus")
        form.locator("[name=profileId]").select_option("bench-median")
        form.locator("summary:has-text('Provenance')").click()
        form.locator("[name=location]").fill("Bench 2, top shelf")
        form.locator("[name=quarantine]").check()
        form.locator("button[type=submit]").click()
        page.wait_for_selector("h2:has-text('Specimen record')")
        mother = page.url.split("#/p/")[1]

        check("quarantine chip from the new-stock checkbox",
              page.locator(".chip:has-text('quarantine until')").count() >= 1)

        # --- specimen record: valuation fields persist
        page.locator("summary:has-text('Edit identity')").click()
        card = page.locator(".card:has(h2:text('Specimen record'))")
        card.locator("[name=cost]").fill("40")
        card.locator("[name=estValue]").fill("250")
        card.locator("[name=ageYears]").fill("6")
        card.locator("[name=grade]").select_option("early refinement")
        card.locator("button:has-text('Save record')").click()
        page.wait_for_timeout(150)
        saved = page.evaluate("(id) => window.BonsaiStore.getPlant(id)", mother)
        check("valuation fields persist",
              saved["cost"] == 40 and saved["estValue"] == 250
              and saved["ageYears"] == 6 and saved["grade"] == "early refinement",
              str({k: saved.get(k) for k in ("cost", "estValue", "ageYears", "grade")}))
        check("location from the add form persists", saved["location"] == "Bench 2, top shelf",
              saved.get("location", ""))

        # --- child plant linked to the mother
        goto("#/")
        form = page.locator("form.card:has(h2:text('Add a plant'))")
        form.locator("[name=name]").fill("Ficus cutting 1")
        form.locator("[name=profileId]").select_option("ginseng-ficus")
        form.locator("summary:has-text('Provenance')").click()
        form.locator("[name=parentId]").select_option(mother)
        form.locator("[name=propMethod]").select_option("cutting — softwood")
        form.locator("button[type=submit]").click()
        page.wait_for_selector("h2:has-text('Specimen record')")
        child = page.url.split("#/p/")[1]

        check("child shows its parent",
              page.locator(".lineage:has-text('Propagated from Mother ficus')").count() == 1)
        goto(f"#/p/{mother}")
        check("mother lists her propagation",
              page.locator(".lineage:has-text('1 propagation · 1 alive')").count() == 1)

        # --- a detailed check: new metrics + styling + treatment + labor + move
        form = page.locator("form.card:has(h2:text('Log a check'))")
        form.locator("[name=height]").fill("14.5")
        form.locator("[name=canopy]").fill("12")
        form.locator("[name=percolation]").fill("20")
        form.locator("[name=light]").fill("9300")
        form.locator("summary:has-text('Detail —')").click()
        form.locator("[name=wired]").check()
        form.locator("[name=wireGauge]").fill("2 mm aluminium")
        form.locator("[name=treated]").check()
        form.locator("[name=treatmentAgent]").fill("horticultural oil")
        form.locator("[name=reiHours]").fill("12")
        form.locator("[name=npk]").fill("10-10-10")
        form.locator("[name=fertMethod]").select_option("drench")
        form.locator("[name=minutes]").fill("25")
        form.locator("[name=movedTo]").fill("South wall")
        form.locator("button[type=submit]").click()
        page.wait_for_timeout(200)

        check("failed percolation raises correct-now",
              page.locator(".stat-tile:has(.stat-label:has-text('Percolation')) .chip-bad").count() == 1)
        check("height and canopy tiles present",
              page.locator(".stat-tile:has(.stat-label:has-text('Height'))").count() == 1
              and page.locator(".stat-tile:has(.stat-label:has-text('Canopy'))").count() == 1)
        # 9300 lux under summer's 16 h photoperiod: 9300/70 = 133 PPFD, DLI 7.7
        light_sub = page.locator(".stat-tile:has(.stat-label:has-text('Light')) .stat-sub").inner_text()
        check("light tile derives PPFD and DLI", "133" in light_sub and "DLI" in light_sub, light_sub)
        check("wire chip appears", page.locator(".chip:has-text('wire on')").count() == 1)
        check("REI chip appears", page.locator(".chip:has-text('REI until')").count() == 1)
        check("movedTo updated the plant location",
              page.evaluate("(id) => window.BonsaiStore.getPlant(id).location", mother) == "South wall")
        check("labor total shown",
              page.locator(".card:has(h2:text('Specimen record')) .hint:has-text('0.4 h logged work')").count() == 1)
        check("milestones log wiring and treatment",
              page.locator("td:has-text('Wired')").count() >= 1
              and page.locator("td:has-text('Treated')").count() >= 1)

        # --- wire removal clears the chip
        form = page.locator("form.card:has(h2:text('Log a check'))")
        form.locator("summary:has-text('Detail —')").click()
        form.locator("[name=wireRemoved]").check()
        form.locator("button[type=submit]").click()
        page.wait_for_timeout(200)
        check("wire chip clears after removal", page.locator(".chip:has-text('wire on')").count() == 0)

        # --- photos: upload, downscale, and stay out of the sync snapshot
        page.locator("[name=photoNote]").fill("front, after wiring")
        page.locator("[name=photoFile]").set_input_files(str(photo_path))
        page.wait_for_selector(".photo-cell img")
        width = page.evaluate("""() => new Promise((resolve) => {
            const img = document.querySelector('.photo-cell img');
            const probe = new Image();
            probe.onload = () => resolve(probe.width);
            probe.src = img.src;
        })""")
        check("photo stored and downscaled to 640 px", width == 640, f"width {width}")
        check("photo is re-encoded jpeg",
              page.evaluate("() => document.querySelector('.photo-cell img').src.slice(0, 23)")
              == "data:image/jpeg;base64,")
        snapshot_text = page.evaluate("() => JSON.stringify(window.BonsaiStore.snapshot())")
        check("photos excluded from the sync snapshot", "data:image" not in snapshot_text,
              f"snapshot is {len(snapshot_text)} bytes")
        check("caption shown", page.locator(".photo-meta:has-text('front, after wiring')").count() == 1)

        # --- compliance CSV carries the treatment record
        csv = page.evaluate("() => window.BonsaiStore.exportCsv()")
        header = csv.splitlines()[0]
        for column in ("height_in", "canopy_in", "percolation_s", "wire_gauge",
                       "treatment_agent", "rei_hours", "npk", "fert_method",
                       "moved_to", "minutes", "location", "root_prune_pct"):
            check(f"CSV carries {column}", column in header.split(","))
        check("CSV carries the agent value", "horticultural oil" in csv)

        # --- lost flow: child dies, mortality shows on the mother
        goto(f"#/p/{child}")
        page.on("dialog", lambda d: d.accept())
        page.locator("button:has-text('Mark as lost')").click()
        page.wait_for_timeout(250)
        check("lost plant leaves the active list",
              page.evaluate("() => window.BonsaiStore.listPlants().length") == 1)
        goto("#/")
        check("lost list offered",
              page.locator("summary:has-text('Lost plants (1)')").count() == 1)
        goto(f"#/p/{mother}")
        check("mortality visible in the lineage",
              page.locator(".lineage:has-text('1 propagation · 0 alive')").count() == 1)

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
