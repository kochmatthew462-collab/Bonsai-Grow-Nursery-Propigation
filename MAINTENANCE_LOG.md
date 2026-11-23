# Koch's Tree Nursery Tracker — Maintenance & Architecture Log

## Overview

- **Repo:** https://github.com/kochmatthew462-collab/Bonsai-Grow-Nursery-Propigation
- **Default branch:** `main`
- **Live:**
  - Nursery tracker — GitHub Pages, published from the repo root of the chosen branch (Settings → Pages → deploy from a branch → `/ (root)`). Static; `.nojekyll` keeps Pages from running Jekyll.
  - Pi cabinet monitor (`pi/`) — installed on a Raspberry Pi 3B+ under systemd as `plantmon`; writes to the same Firestore document the app syncs.
- **Last updated:** 2026-11-23
- **Last commit on `main`:** `7e52e50` (2026-09-01) — Merge pull request #12
- **Current issues/debt:** see [Known Issues & Debt](#known-issues--debt)

This log is the source of truth for architectural decisions. Every decision or
problem gets an entry here **with a link to the session or pull request that
made it**. Claude Code sessions are archive-only context; the log is what is
maintained.

---

## Two products, one repository

| Product | Path | Stack | Runs where | Tests |
|---|---|---|---|---|
| Koch's Tree Nursery Tracker | `index.html`, `css/`, `js/` | Static HTML/CSS/JS, no build, no CDN | GitHub Pages, any browser, `file://` | `test/*.py` (Playwright), `test/verify_qr.py` |
| Cabinet monitor | `pi/` | Python 3 on Raspberry Pi OS, smbus2, SQLite, Firestore REST | Raspberry Pi 3B+, systemd | `pi/test_pi.py` |

The clinical/APA research suite that used to live in `research-suite/` (with its
`.devcontainer/`, its ADRs and its notes) moved to the owner's private Study-Buddy
repository on 2026-11-23. Its history up to that date remains in this repository's git log.

---

## Architecture Decision Record (ADR)

### ADR-001: Static site, no server, no accounts (tracker)
- **Date:** 2026-08-16
- **Decision:** The tracker is plain static files served by GitHub Pages. Data lives in the browser (localStorage) with optional sync. No build step, no bundler, no CDN dependency.
- **Rationale:** Labels must print and scan from a phone in a greenhouse with no signal and from a `file://` copy. [PR #1](https://github.com/kochmatthew462-collab/Bonsai-Grow-Nursery-Propigation/pull/1)
- **Status:** LOCKED
- **Impact:** Every feature must work offline; nothing secret may live in this repo (it is public, and Pages serves its root).

### ADR-002: QR codes, not 1D barcodes; encoder written from scratch
- **Date:** 2026-08-16
- **Decision:** Every label is a QR code carrying the plant's full URL. `js/qrcode.js` is a self-contained encoder (versions 1–10, EC levels L and M, URLs up to 213 bytes).
- **Rationale:** A phone camera opens a URL with nothing installed; a 1D barcode needs a scanner app plus a lookup. A CDN encoder fails offline. [PR #1](https://github.com/kochmatthew462-collab/Bonsai-Grow-Nursery-Propigation/pull/1)
- **Status:** LOCKED
- **Impact:** `test/verify_qr.py` decodes 138 matrices through zxing-cpp and compares function patterns to segno. Any change to the encoder must pass it.

### ADR-003: Optional Firestore sync over REST, merge-by-record, tombstones
- **Date:** 2026-08-16
- **Decision:** Cross-device sync uses the Cloud Firestore REST API via `fetch` with anonymous auth. No Firebase SDK. Each plant and each check merges independently, newest edit wins; deletes are tombstones. The nursery code (24 chars, ~120 bits) is the only credential.
- **Rationale:** Free Spark plan, does not pause when idle, keeps the app a set of plain files. [PR #2](https://github.com/kochmatthew462-collab/Bonsai-Grow-Nursery-Propigation/pull/2)
- **Status:** LOCKED
- **Impact:** Shared document has a 1 MiB ceiling; app warns at 800 KB. Sync is not backup — JSON export remains the recovery path. The Pi (ADR-005) must obey the same merge rules.

### ADR-004: Care profiles aligned to the three handbooks
- **Date:** 2026-08-16
- **Decision:** Tracked factors, target bands, seasonal windows and the master calendar are derived from the indoor bench, bergamot and olive handbooks, and the app was renamed Koch's Tree Nursery Tracker.
- **Rationale:** [PR #3](https://github.com/kochmatthew462-collab/Bonsai-Grow-Nursery-Propigation/pull/3), [PR #4](https://github.com/kochmatthew462-collab/Bonsai-Grow-Nursery-Propigation/pull/4), [PR #5](https://github.com/kochmatthew462-collab/Bonsai-Grow-Nursery-Propigation/pull/5)
- **Status:** LOCKED
- **Impact:** `js/profiles.js` is the single place bands live. README records where the app's dates deliberately differ from the handbooks.

### ADR-005: The Raspberry Pi is "one more device on the nursery"
- **Date:** 2026-08-29
- **Decision:** The Pi daemon uses the same three Sync credentials and the same merge rules as the app (ported to Python, proven byte-identical against `js/store.js` in `pi/test_pi.py`). Raw one-minute readings stay in SQLite on the Pi; a live document every 5 minutes feeds the Live sensors card; one minimal summary entry per plant per day merges under a deterministic id. Relays are low-voltage only and disabled by default.
- **Rationale:** No port forwarding, no new server, nothing new to secure. [PR #8](https://github.com/kochmatthew462-collab/Bonsai-Grow-Nursery-Propigation/pull/8), [PR #9](https://github.com/kochmatthew462-collab/Bonsai-Grow-Nursery-Propigation/pull/9)
- **Status:** LOCKED
- **Impact:** A year of summaries for six plants is ~250 KB of the 1 MiB document. Stale after 15 quiet minutes is a loud state, by design.

_ADR-006 to ADR-011 concerned the clinical suite and moved with it._

### ADR-012: Repository management moves to the chat-based maintenance log
- **Date:** 2026-09-06
- **Decision:** New work is decided and logged here first, with a session link, then applied to the repo. Claude Code session branches become archive-only context. This file is the "Domain 11: Code Repos" record.
- **Rationale:** Decisions spread across a dozen session branches were not searchable.
- **Status:** OPEN — awaiting the owner's confirmation of the deployment method (see Immediate Action Items)
- **Impact:** Each future PR description should cite the ADR or issue row it resolves.

---

## Known Issues & Debt

| Issue | Impact | Session / PR | Status |
|---|---|---|---|
| Firestore shared document has a 1 MiB hard ceiling; sensor summaries accrue ~250 KB/yr for six plants | sync stops working when exceeded | ADR-003, ADR-005 | monitor the 800 KB warning; prune yearly |
| Tracker tests need `segno zxing-cpp numpy playwright pillow` installed manually | friction | README "Tests" | open: add a `requirements-test.txt` |
| Pi wiring cannot be proven by tests; `i2cdetect` and `--once --no-cloud` are the bench checks | a probe pulled loose reads dry forever | `pi/README.md` | operational, documented |

---

## How to Deploy

```bash
# Nursery tracker (GitHub Pages) — nothing to build
git checkout main
git pull origin main
# edit index.html / css / js
python3 -m http.server 8000        # local check at http://localhost:8000
git commit -am "..." && git push origin main
# Pages re-publishes main automatically (Settings → Pages: deploy from a branch, main, / (root))

# Pi cabinet monitor
# on the Pi, inside pi/ (clone the repo or copy pi/ over)
bash install.sh
nano ~/plantmon/config.json        # Sync credentials, plant ids, probe calibration
python3 ~/plantmon/sensord.py --config ~/plantmon/config.json --once --no-cloud
sudo systemctl start plantmon
journalctl -u plantmon -f
```

## How to Test (run before every push)

```bash
# Tracker
pip install segno zxing-cpp numpy playwright pillow
python3 test/verify_qr.py
python3 test/smoke_app.py
python3 test/sync_test.py
python3 test/calendar_test.py
python3 test/weather_test.py
python3 test/pro_test.py
python3 test/sensors_test.py
python3 pi/test_pi.py
```

---

## Debugging & Common Problems

### "Live sensors card says stale"
**Solution:** ADR-005 — the Pi has not written the live document for 15 minutes. On the Pi: `journalctl -u plantmon -f`, then `i2cdetect -y 1` (expect 29, 5c, 68, 70, 48 and 49/4a/4b). A missing address is wiring.

### "Scanned a label and got an empty plant"
**Solution:** README "Sync" — this device has never seen the plant. Join the nursery with the same code on the Sync page or import the JSON backup.

### "Sync stopped; document too large"
**Solution:** ADR-003 — export a JSON backup and prune old sensor entries; the shared document ceiling is 1 MiB.

### "Pi install fails: externally-managed-environment"
**Solution:** [PR #9](https://github.com/kochmatthew462-collab/Bonsai-Grow-Nursery-Propigation/pull/9) — Bookworm refuses system-wide pip. `install.sh` now installs `python3-smbus2` and `python3-requests` from apt.

---

## Session Index (which sessions touched which files)

| Session branch | PRs | Dates | Files touched |
|---|---|---|---|
| `claude/bonsai-metrics-tracking-h8r68l` | #1–#6 (squash-merged), #8, #9 | 2026-08-16 → 2026-08-30 | `index.html`, `css/styles.css`, `js/*.js`, `test/*`, `pi/*`, `README.md`, `.gitignore` |
| `claude/repos-pdf-maintenance-log-jlwmtl` | this log (#14) | 2026-09-06 | `MAINTENANCE_LOG.md` (the generated `docs/` inventory it added was removed on 2026-11-23) |

---

## Immediate Action Items

1. **Confirm deployment method** for the tracker: which branch does GitHub Pages currently publish, and what is the published URL? Record it in Overview.
2. **Add the tracker's Playwright tests to CI** (`node --check` and `pi/test_pi.py` already run there).
3. **Lock this log**: from here on, every change starts as an ADR or issue row with a session link, then a PR that cites it.

---

## Change log for this file

| Date | Change | Session |
|---|---|---|
| 2026-09-06 | Created from the full repo inventory; ADR-001 to ADR-012 recorded | PR #14 |
| 2026-11-23 | Clinical suite moved out: its ADRs (006–011), issues, deploy/debug notes and session rows removed; CI now runs `node --check` and the Pi tests | this change |
