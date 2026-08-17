# Koch's Tree Nursery Tracker

Track **pH, moisture, EC, growth, temperature, humidity, light, watering and
fertiliser** per plant, with a **QR label** on each pot that opens that plant's
metrics when scanned. One site carries both the indoor bonsai bench and the
container trees that move in and out with the seasons, and optionally syncs
itself across devices for free.

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
| **This repo** | Yes | Free | Yes, optional free sync | Best if you want it tailored and offline |

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
signal. Cross-device sync is available and free but **optional**, and what it
does and does not protect you from is spelled out in
**[Sync](#sync-or-the-lack-of-it)**.

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
4. Go to **Labels** and press **Print**. The Base URL fills itself in from the
   address you are on, so it only needs changing if you print from one device
   and scan against another.

Print onto weatherproof or laminated stock — labels live outdoors, and a QR
code that has bleached or delaminated will not scan.

---

## Using it

**Nursery** lists every plant with its latest readings. **Add a plant** gives it
a short ID like `k3m9x2` (no vowels and no look-alike characters, so nothing is
misread off a wet label from across the bench).

**A plant's page** has:

- **headline tiles** for every factor its profile tracks, each carrying an
  in-band / act-soon / correct-now status against that profile's target;
- **this month's row** from that tree's handbook calendar — where it should be,
  watering interval, feed state and the key action;
- **Log a check** — only the fields its profile actually uses, so a bench tree is
  never asked for chill hours; a blank field records nothing rather than a zero;
- **trend charts** with the target band shaded behind the line, plus a hover and
  keyboard readout and a table view on each;
- a **care timeline** of watering and feeding, and a **work and health log** of
  repots, pruning, pest sightings and graft checks;
- **what to watch** for that species, the full history, and the plant's own QR
  code.

**Calendar** is every dated task across the nursery. **Labels** prints the whole
nursery as a QR label sheet. **Sync** keeps devices in step automatically.
**Backup** exports and imports by hand.

## What it tracks

Factors split into three kinds, which is why they are presented differently.

**Measurements** trend over time, so they get line charts with the target band
shaded behind them:

| Factor | Unit | Notes |
|---|---|---|
| pH | — | pour-through leachate, not the pot surface |
| Moisture | % | capacitive probe, same depth and spot each time |
| EC | mS/cm | nutrient load, from the same pour-through sample |
| Growth | mm | trunk caliper or leader height — pick one and stay with it |
| Low / high temperature | °F | one range chart, both bands named |
| Humidity | % | bench probe, or winter rest RH for the container trees |
| Light | lux | lux meter at the canopy, midday |
| Chill hours | h | the olive — running hours below 45 °F |
| Vigor | /5 | the book's quarterly 1–5 audit; no styling below 4 |

**Recurring care** happens or it doesn't, so watering and feeding get a timeline
of dots rather than a line.

**Occasional work and health** — repots, pruning and wiring, pest sightings,
graft-line checks, rootstock suckers removed, and moving a plant in or out —
lands in a dated log rather than a chart. These happen a few times a year, and a
labelled list reads better than five more colour-coded lanes.

### Care profiles

A plant's **care profile** decides which factors it records and the bands each
reading is judged against. Every reading is scored on the same three tiers the
bench packet uses: **in band**, **act soon**, **correct now** — always as a
glyph plus a word plus a colour, never colour alone.

Profiles included:

- **Bonsai bench — median program**, plus per-species profiles for Parrot's
  beak, Hawaiian umbrella, Ginseng ficus and Dwarf pomegranate. Numbers are
  transcribed from the *Bonsai Bench Environment Packet* (Aug 2026): the median
  card, the per-species temperature envelopes, and the per-species soil
  envelopes, plus the bench's own season programme as a month calendar.
- **Italian bergamot — container** and **Arbequina olive — container**, both for
  young grafted trees that summer outdoors and take a cool bright winter rest
  indoors, with the full month-by-month calendar from each handbook.
- **No profile**, which records readings without judging them.

Each profile carries a *What to watch* list on the plant's page — the failure
modes that actually matter for that plant, rather than generic advice.

### Where the numbers come from

Every band, calendar row and watch item is transcribed from one of three
handbooks, and each profile names its source on screen:

| Tag | Handbook | Supplies |
|---|---|---|
| BENCH | *Bonsai Bench Environment Packet* (Aug 2026) | median card, per-species temperature and soil envelopes, the season program |
| BOOK | *The Complete Bonsai Grower* | class defaults: substrate pH, leachate EC by development phase, VWC trigger, light by class, winter floors, the vigor rubric |
| TREE | *The Arbequina Olive in Central Maryland* and *Bergamot in Central Maryland* | everything for the two container trees — both written for ZIP 20833, zone 7b |

Where a species handbook and a class default disagree, **the species handbook
wins** and the disagreement is written into the profile's note rather than
quietly resolved. Three worth knowing:

- **Olive winter temperature.** The book puts olive at 35–45 °F; the Arbequina
  handbook specifies 50–55 °F sustained and says induction *fails* at 39 °F. The
  app follows the handbook.
- **Olive media pH.** 6.5–8.5, and explicitly *do not acidify* — the opposite of
  the bench's 6.3 target. Chasing the bench number here would be actively wrong.
- **Moisture scale.** The bench packet reads 35–65% running / water at 33% on its
  own probe; the book quotes a 20–28% VWC trigger. These are different scales for
  the same thing. The bench profiles keep the packet's numbers, the container
  trees use the book's, and both say so in the note. **Do not mix the two.**

### Seasonal targets

Several bands change with the season, because the trees do. A bergamot's winter
rest wants 45–58 °F and its summer wants nothing of the kind. Profiles declare
their rest months, and the app judges readings against whichever band is in force
today — the plant page says which one, and flags when a rest-season target
applies.

### The two container trees

Both are young stem grafts in pots, and both move with the seasons:

- **Bergamot** — out around May 10–20, in around Oct 1–15, then a **bright cool
  rest at 45–58 °F**. The rest is not storage: it is what induces the following
  spring's bloom. A bergamot kept at living-room temperature stays healthy and
  never flowers.
- **Arbequina olive** — out mid-to-late April, in late Oct to mid Nov, then
  **50–55 °F for 10–12 weeks** banking 200–400 chill hours below 45 °F. Chill
  fails from being too warm as readily as too cold: induction fails at 39 °F and
  at 64 °F alike. Never below 40 °F at pot level — a container root zone sits at
  air temperature, 20–30 °F colder than the same tree in the ground.

The app tracks chill hours for the olive precisely because that number, more than
any other, decides whether there is a crop.

---

## The master calendar

**Calendar** collects every dated window across the whole nursery — 46 of them,
transcribed from the three handbooks — and sorts them into **Missed**, **Due
now**, **Coming up** and **Done this year**. Each carries the plant it belongs
to, its window, its category (move / prune / repot / feed / scout / measure /
system) and the handbook's own wording for what to do.

Marking one done is remembered **for that year only**, so it returns next
season. A missed window nags for 45 days and then stops, rather than staying red
forever. Completions sync between devices like any other record.

Each plant's page also shows just its own **due now and next 30 days**.

## The drip log

Bench trees never need a watering entry typed. The app writes one for every
scheduled run — date, volume, which recipe — and the plant's Drip card shows the
programme in force.

**These volumes are derived, not measured.** The GrowHub outlet is a smart
switch: it reports on/off, and there is no public API to ask it anything anyway.
So the volume is `emitters × flow × runtime` on the days the season's recipe
runs, using the packet's own emitter allocation and seasonal runtimes.

Two consequences worth being clear about:

- **Calibrate, or the number is only nominal.** Until you enter a measured flow
  rate the app uses the kit's nominal 0.7 L/hr per emitter, and says so on
  screen and in every entry it writes. The catch-cup pass — lift the staked
  lines into cups, manual-run exactly 2 minutes, mL ÷ 2 — gives you the real
  figure per plant. Re-run it after any repot, substrate or line change.
- **A clogged emitter still reads as watered.** Nothing here can see a blocked
  dripper or a pump that did not start. The packet's 30-second daily glance is
  what catches that, and it is not replaceable by software.

The pomegranate's winter bypass is respected: while its lines are clamped
nothing is logged, and the card tells you to hand-water every 7–10 days instead.

Because the site is static there is nothing running overnight, so the log is
caught up whenever you open the app. Entry ids are deterministic, which makes
that idempotent — it re-runs on every render and syncs between two devices
without ever double-counting.

## The handbook forms

The two tree handbooks carry eleven paper forms each, and the book adds its
eight-block tree record. Most of them are already what this app stores, so
rather than making you write every number twice:

| Handbook form | Where it lives here |
|---|---|
| Care Log | every logged check |
| Annual Growth Measurement | the growth series (trunk caliper) |
| Winter Chill Log | the chill-hours series, with the 200–400 h band |
| Media and Water Chemistry | the pH and EC series, with pour-through notes |
| Pruning Record · Repot / Root-Prune Record | the work and health log |
| Pest Scouting Log | pest sightings, with the species' own pest list |
| Seasonal Transition Log | the move-in / move-out entries |
| Tree Provenance Record | the plant's identity fields |
| Targets block (book) | the care profile — bands, winter floor, light, EC |
| Quarterly vigor audit (book) | the vigor 1–5 series |

Still on paper, and worth keeping there for now: the phenology log (bud break,
bloom, colour break), the harvest log, and the annual season review — which
should be *generated* from a full year of data rather than typed, and will be
once there is a full year to generate it from.

---

## Weather watch and move alerts

Both container trees move in and out on a schedule, and the whole point of the
schedule is that it bends to the actual weather. The app fetches the 14-day
forecast for the nursery's coordinates and judges each tree against **its own**
thresholds:

| Tree | In | Threshold | Out | Threshold |
|---|---|---|---|---|
| Italian bergamot | Oct 15–20 | nights settling to 45–50 °F; 32 °F damages foliage | May 1–10 | nights reliably above 50 °F |
| Arbequina olive | Nov 1–10 | nights approaching 30–32 °F | Apr 1–10 | nights consistently above 35–40 °F |

The two directions are judged differently on purpose. **In autumn the worst
night rules** — one freeze does the damage, so a single forecast night at or
below the damage threshold overrides the calendar entirely. **In spring every
night has to clear the bar** — the risk is moving too early, so one cold night
in the next five holds the tree indoors.

A 10-day acclimation prompt appears before each window: shaded porch before
coming in, sheltered shade with morning sun introduced gradually before going
out.

Location defaults to Brookeville, MD (39.18, −77.06), the ZIP 20833 both tree
handbooks are written for, and is editable on the Calendar page. The forecast
comes from **Open-Meteo** — free, no API key, CORS-enabled, which is what makes
it usable from a static page with nothing to keep secret. Responses are cached
for an hour.

### Where these dates differ from the handbooks

The transition schedule above is followed, and it is not identical to the
handbooks. The differences are noted in each task on screen:

- **Bergamot in** — schedule Oct 15–20, handbook Oct 1–15. The schedule is
  *later*; the weather rule pulls it forward if nights actually drop.
- **Bergamot out** — schedule May 1–10, handbook May 10–20.
- **Olive out** — schedule Apr 1–10, handbook mid-to-late April, so about two
  weeks earlier.

In every case the forecast rule overrides the date, which is what keeps the
earlier windows safe: the app will not say "go" while cold nights are coming.

## What "notify" can honestly mean here

There is no server in this app, which is what makes it free — and it is also
why it cannot wake a sleeping phone by itself. So the notification problem is
split in two:

**Date-driven reminders → your own calendar.** The Calendar page exports every
dated window as an `.ics` file: yearly-repeating all-day events with an alarm
the day before. Import or subscribe once and your phone's calendar fires those
in the background, forever, with nothing running anywhere. This covers moves,
pruning, repotting, feeding cutoffs and the bench changeovers.

**Weather-driven alerts → while the app is open.** These cannot be scheduled in
advance, because the forecast that triggers them does not exist yet. The app
raises them whenever it is open or opened, and will fire a real system
notification at that moment if you allow it — once per alert per day, so it does
not train you to ignore it.

The practical habit: subscribe to the calendar for the dates, and open the app
during a cold snap. Anything more than that needs a server sending push, which
would end the "free, no accounts" property this whole thing is built on.

---

## Sync, or the lack of it

By default **readings are stored in this browser on this device** and are not
synced anywhere. That is the cost of having no server and no accounts: fine for
one person on one phone, wrong for a bench shared between a phone and a laptop.

There are two ways out, and they are not exclusive.

### Manual: JSON backup

Backup → **Download JSON backup**, then **Import** it on the other device.
Imports merge by record id and by edit time, so importing the same file twice
changes nothing, and two devices' readings combine rather than overwrite.
**Download CSV for Excel** gives one row per check with every factor as a
column.

### Automatic: Cloud Firestore sync

The **Sync** page connects the app to a free Firebase project so devices keep
themselves in step. It is free on the Spark plan, needs no card, and — unlike
some free tiers — does not pause when idle, so a nursery you do not open for a
fortnight in winter still works.

There is no Firebase SDK: sync speaks to the Firestore REST API with `fetch`,
so the app stays a set of plain files with no build step and no CDN. Losing the
network is not an error state — readings are saved locally and go up when you
reconnect.

Setup is about ten minutes and the steps are printed on the Sync page itself:
create a project, create a Firestore database, enable **Anonymous**
authentication, publish the rules shown on that page, then paste the Project ID
and Web API Key in and generate a **nursery code**. Entering that same code on
another device joins it to the same nursery.

Three things worth knowing before you turn it on:

- **The code is the key.** There are no usernames. Anyone holding the nursery
  code can read and write the nursery, exactly like an unguessable share link.
  A generated code is 24 characters from a 32-character alphabet — about 120
  bits, so it will not be guessed — but treat it as a password, not a username.
- **Edits merge, they do not overwrite.** Each plant and each check syncs
  independently, newest edit winning. Deletes are kept as tombstones so they
  propagate properly instead of reappearing from whichever device still had the
  record.
- **Sync is not backup.** It copies your data; it does not version it. Keep
  exporting a JSON file occasionally — that is what saves you from a mistaken
  bulk delete, which sync would faithfully replicate everywhere.

Scanning a label for a plant this device has never seen shows a clear message
pointing at the sync and import pages, rather than a confusing empty dashboard.

---

## How it is put together

```
index.html          shell and routes
css/styles.css      theme tokens, light and dark
js/qrcode.js        self-contained QR encoder (no CDN)
js/profiles.js      care profiles: tracked factors, target bands, watch lists
js/store.js         plants, readings, merge and tombstones — the only storage code
js/sync.js          optional Firestore sync over REST (no SDK, no CDN)
js/charts.js        SVG charts, hover and keyboard readout, table views
js/calendar.js      dated task windows, the derived drip log, .ics export
js/weather.js       forecast fetch and the move alerts it drives
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
python3 test/sync_test.py     # two devices converging through sync
python3 test/calendar_test.py # the calendar and the derived drip log
python3 test/weather_test.py  # move alerts and the calendar export
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

`smoke_app.py` drives a real Chromium across all three profile kinds — indoor
bench, container bergamot, container olive. It adds plants, logs checks carrying
every factor, and confirms the profile actually drives the page: the bench tree
gets seven chart cards and a season program, the olive gets a chill-hours field
but no humidity or light, and a pH of 7.6 against a 6.0–7.0 band raises a status
chip rather than being quietly plotted. Then it renders the label sheet, takes
the QR the sheet actually drew, decodes it, and follows the decoded URL to
confirm it lands on the plant it names — proving the label loop end to end
rather than just that a QR was drawn. It also round-trips the JSON export and
checks that re-importing does not duplicate.

`sync_test.py` runs the real `js/sync.js` against a mock of the two Firestore
REST endpoints, served from the same origin as the app — so it needs no Firebase
project, no credentials and no network, while still exercising the actual
sign-in, read, merge and write-back. Two browser contexts stand in for two
devices. It checks that a plant made on A reaches B, that a reading added on B
reaches A without losing A's own, that a delete propagates and **stays** deleted
when a stale device pushes an old snapshot back, and that losing the network
leaves local data intact and recovers when it returns.

`calendar_test.py` leans on the drip log, because it writes data nobody typed:
the volume must match `emitters × flow × runtime`, it must never schedule a
Sunday (the hand-watering day), it must stay bounded to 30 days of backfill so
first use does not invent months of history, it must be idempotent across
repeated renders, it must honour the pomegranate's winter clamp by logging
nothing, and it must say plainly whether the flow rate is calibrated or nominal.

`weather_test.py` tests the alert decision table directly, against synthetic
forecasts at fixed dates rather than whatever the weather happens to be doing —
getting it wrong either way is expensive, since too eager costs the olive weeks
of the chill it needs and too slow freezes a container root ball. It checks that
a freezing night overrides the window, that 37–45 °F nights read as chill for the
olive but a threat for the citrus, that the two trees do **not** move on the same
night, and that one cold night in spring holds a tree indoors. The forecast fetch
runs against a mock of the Open-Meteo endpoint served from the app's own origin,
so it needs no network and no key.

Add `--screenshots DIR` to `smoke_app.py` to capture the pages.
