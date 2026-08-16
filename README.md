# Bonsai Grow / Nursery / Propagation Tracker

Track **pH, moisture, growth, watering and fertiliser** per plant, with a
**QR label** on each pot that opens that plant's metrics when scanned.

This repo contains a working tracker — a static web app with no accounts, no
server and no subscription. It also answers the question that started it: *can
we build this, or can Office or another free tool already do it?*

---

## Short answer

**Yes to both, and the right choice depends on one thing: does more than one
person need to see the same data on more than one device?**

| Approach | Scanning a label opens the plant? | Cost | Multi-device | Verdict |
|---|---|---|---|---|
| **Excel alone** | No — a workbook has no per-row web address to point a QR at | Owned | File-share only | Fine as a ledger, not as a scan target |
| **Microsoft Lists** (M365) | Yes — every list item has a stable URL | M365 licence | Yes, real sync | Best Microsoft-stack answer |
| **Google Forms + Sheets** | Yes — a QR opens a pre-filled form | Free | Yes, real sync | Best free no-code answer |
| **Microsoft Access** | No — desktop only | Owned | No | Not suited to phones |
| **This repo** | Yes | Free | **No — see the limitation below** | Best if you want it tailored and offline |

A short but important detail: **use QR codes, not barcodes.** A 1D barcode
(the supermarket kind) encodes a number and needs a dedicated scanner app plus
software that knows what that number means. A QR code can hold a full web
address, so any phone's built-in camera opens the plant's page directly, with
nothing installed. That is why every label here is a QR code.

### If you want zero code, do this instead

1. Make a Google Sheet with one row per reading.
2. Make a Google Form with a hidden **Plant ID** field plus pH, moisture,
   growth, watering and fertiliser.
3. Use the form's **"Get pre-filled link"** to bake each plant's ID into its own
   URL.
4. Turn each of those URLs into a QR code and stick it on the pot.

Scanning then opens a form already knowing which plant it is, and every
submission lands in the Sheet, where charts and pivot tables work normally.
It syncs across devices and costs nothing. It is a genuinely good answer, and
if a shared, always-synced record matters more than tailored charts, take it.

### What this repo gives you instead

Tailored per-plant dashboards, a printable label sheet, no accounts, and full
offline operation — everything works from a phone in a greenhouse with no
signal. The trade is stated plainly in **[Limitation](#limitation-data-is-per-device)**.

---

## Quick start

Everything is static — no build step, no dependencies.

```bash
git clone https://github.com/kochmatthew462-collab/bonsai-grow-nursery-propigation.git
cd bonsai-grow-nursery-propigation
python3 -m http.server 8000
```

Open <http://localhost:8000>, add a plant, log a check, and print the label
sheet.

### Publishing so labels actually scan

A QR label has to point at an address your phone can reach, so the app needs to
live somewhere real. GitHub Pages is free and enough:

1. Repo **Settings → Pages**.
2. **Source:** deploy from a branch, pick your branch and `/ (root)`.
3. Wait for the green tick, then open the published URL.
4. Go to **Labels**, confirm the **Base URL** matches the published address,
   press **Apply**, then **Print**.

Print onto weatherproof or laminated stock — labels live outdoors, and a QR
code that has bleached or delaminated will not scan.

---

## Using it

**Nursery** lists every plant with its latest readings. **Add a plant** gives it
a short ID like `k3m9x2` (no vowels and no look-alike characters, so nothing is
misread off a wet label from across the bench).

**A plant's page** has:

- five headline tiles — latest pH, moisture, growth, days since watering, days
  since feeding;
- **Log a check** — fill in only what you actually measured; a blank field
  records nothing rather than a zero;
- trend charts for pH, moisture and growth, each with a hover and keyboard
  readout and a table view;
- a care timeline showing every watering and feeding;
- the full history, and the plant's own QR code.

**Labels** prints the whole nursery as a QR label sheet. **Backup** exports and
imports.

### About the metrics

You asked for four and listed five: pH, moisture, growth, watering and
fertiliser. All five are tracked. They split naturally into two kinds, which is
why they are charted differently:

- **pH, moisture and growth** are measurements — they trend over time, so they
  get line charts.
- **Watering and fertiliser** are events — they happen or they don't, so they
  get a timeline of dots rather than a line.

Record growth the same way every time (new leader height, or trunk caliper —
pick one and stay with it), or the trend measures your technique instead of
the tree.

---

## Limitation: data is per-device

**Readings are stored in the browser's local storage on the device that entered
them.** They are not synced. A plant logged on the greenhouse phone will not
appear on the office laptop, and clearing site data erases it.

This is the direct cost of having no server and no accounts. It is fine for one
person working from one phone, and wrong for a team sharing a bench.

What to do about it:

- **Export a JSON backup regularly** (Backup → Download JSON backup). Importing
  merges by ID, so importing the same file twice changes nothing and importing
  the phone's export onto the laptop combines both sets.
- **Export CSV for Excel or Sheets** — one row per check, ready for a
  PivotTable. This is the bridge to the Office side of the question.
- **If you need real sync**, the honest fix is a shared backend. `js/store.js`
  is the only file that touches storage, so swapping localStorage for
  Supabase, Airtable or a SharePoint list is a contained change — the views and
  charts do not care where the data comes from.

Scanning a label for a plant this device has never seen shows a clear message
pointing at the import page, rather than a confusing empty dashboard.

---

## How it is put together

```
index.html          shell and routes
css/styles.css      theme tokens, light and dark
js/qrcode.js        self-contained QR encoder (no CDN)
js/store.js         plants, readings, import/export — the only storage code
js/charts.js        SVG charts, hover and keyboard readout, table views
js/app.js           routing and views
test/               verification, described below
```

Two decisions worth knowing about:

**The QR encoder is written from scratch** rather than pulled from a CDN. Labels
must print correctly from a phone in a greenhouse with no signal, and from a
plain `file://` copy of the folder. It covers versions 1–10 at error-correction
levels L and M — URLs up to 213 bytes.

**The chart palette is validated, not eyeballed.** The five series hues clear
the lightness band, chroma floor, colourblind separation and normal-vision
floor in both light and dark mode. Aqua sits below 3:1 contrast on the light
surface, which is why every chart also carries a direct end label and a table
view, so no value is reachable by colour or hover alone.

---

## Tests

```bash
pip install segno zxing-cpp numpy playwright pillow
python3 test/verify_qr.py     # the QR encoder
python3 test/smoke_app.py     # the app, in a real browser
```

`verify_qr.py` checks 138 matrices three ways: every one decodes back to its
payload through **zxing-cpp** (the decoder family phone cameras use), every
function-pattern module matches **segno** exactly, and version selection always
picks the smallest version that fits.

> One quirk worth recording: segno cannot be used as a byte-exact reference in
> byte mode. Its `write_padding_bits` appends a spurious zero byte whenever the
> bit stream is already byte-aligned after the terminator — which in byte mode
> it always is. The extra byte lands after the terminator so both encoders
> still decode identically; it just means the data region is compared by
> decoding rather than by matrix equality.

`smoke_app.py` drives a real Chromium: adds plants, logs checks, renders the
label sheet, then takes the QR the sheet actually drew, decodes it, and follows
the decoded URL to confirm it lands on the plant it names — proving the label
loop end to end rather than just that a QR was drawn. It also round-trips the
JSON export and checks that re-importing does not duplicate.

Add `--screenshots DIR` to `smoke_app.py` to capture the pages.
