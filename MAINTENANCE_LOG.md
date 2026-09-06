# Koch's Tree Nursery Tracker & Koch Clinical Suite — Maintenance & Architecture Log

## Overview

- **Repo:** https://github.com/kochmatthew462-collab/Bonsai-Grow-Nursery-Propigation
- **Default branch:** `main`
- **Live:**
  - Nursery tracker — GitHub Pages, published from the repo root of the chosen branch (Settings → Pages → deploy from a branch → `/ (root)`). Static; `.nojekyll` keeps Pages from running Jekyll.
  - Clinical suite (`research-suite/`) — **not hosted**. Runs locally at `127.0.0.1:8765`, or in a GitHub Codespace on forwarded port 8765 (private visibility).
  - Pi cabinet monitor (`pi/`) — installed on a Raspberry Pi 3B+ under systemd as `plantmon`; writes to the same Firestore document the app syncs.
- **Last updated:** 2026-09-06
- **Last commit on `main`:** `7e52e50` (2026-09-01) — Merge pull request #12
- **Raw inventory:** `docs/repo-inventory/` (git log, remotes, branches, file tree, files touched per session)
- **Current issues/debt:** see [Known Issues & Debt](#known-issues--debt)

This log is the source of truth for architectural decisions. Every decision or
problem gets an entry here **with a link to the session or pull request that
made it**. Claude Code sessions are archive-only context; the log is what is
maintained.

---

## Three products, one repository

| Product | Path | Stack | Runs where | Tests |
|---|---|---|---|---|
| Koch's Tree Nursery Tracker | `index.html`, `css/`, `js/` | Static HTML/CSS/JS, no build, no CDN | GitHub Pages, any browser, `file://` | `test/*.py` (Playwright), `test/verify_qr.py` |
| Koch Clinical Suite (research & APA 7 authoring + clinical charting) | `research-suite/` | Python 3.11+, FastAPI, uvicorn, python-docx, python-pptx, matplotlib | Local machine or Codespace, loopback only | `research-suite/tests/run_all.sh` (13 suites, offline) |
| Cabinet monitor | `pi/` | Python 3 on Raspberry Pi OS, smbus2, SQLite, Firestore REST | Raspberry Pi 3B+, systemd | `pi/test_pi.py` |

---

## Architecture Decision Record (ADR)

### ADR-001: Static site, no server, no accounts (tracker)
- **Date:** 2026-08-16
- **Decision:** The tracker is plain static files served by GitHub Pages. Data lives in the browser (localStorage) with optional sync. No build step, no bundler, no CDN dependency.
- **Rationale:** Labels must print and scan from a phone in a greenhouse with no signal and from a `file://` copy. [PR #1](https://github.com/kochmatthew462-collab/Bonsai-Grow-Nursery-Propigation/pull/1)
- **Status:** LOCKED
- **Impact:** Every feature must work offline; nothing secret may live in this half of the repo (see ADR-006).

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

### ADR-006: The clinical suite is a local app, never a static site
- **Date:** 2026-08-17
- **Decision:** `research-suite/` binds to `127.0.0.1`, requires a session token, checks the `Host` header against an allowlist taken from the environment (never from the request), and checks `Origin` on writes. API keys live in the OS keychain or a git-ignored `.env`.
- **Rationale:** It holds API keys and calls APIs with no CORS headers; a key in front-end JavaScript is a published key. Because this repo publishes GitHub Pages from its own branch, a committed key would be served at a guessable URL. [PR #7](https://github.com/kochmatthew462-collab/Bonsai-Grow-Nursery-Propigation/pull/7)
- **Status:** LOCKED
- **Impact:** `.env`, `data/`, `.session-token` are git-ignored. A key that has ever been committed must be rotated. Binding wide (`RESEARCH_SUITE_HOST=0.0.0.0`) does not widen admission; hosts must be named in `RESEARCH_SUITE_ALLOWED_HOSTS` ([PR #11](https://github.com/kochmatthew462-collab/Bonsai-Grow-Nursery-Propigation/pull/11)).

### ADR-007: Session token is stable and carried in an HttpOnly cookie
- **Date:** 2026-08-19
- **Decision:** The token is generated once into `data/.session-token` (0600), not per run. On first visit it is written to an `HttpOnly`, `SameSite=Lax` cookie (Secure over HTTPS, 30 days). A rejected cookie is deleted by the rejection. Rotate by deleting the file; pin with `RESEARCH_SUITE_TOKEN`.
- **Rationale:** Regenerating per run invalidated every open tab on restart; `sessionStorage` lost it on tab close. Commits `3dd82c6`, `026ef9f`, `ce20031`, `f2044d5` in [PR #7](https://github.com/kochmatthew462-collab/Bonsai-Grow-Nursery-Propigation/pull/7).
- **Status:** LOCKED
- **Impact:** Bookmark the plain address without `#token=`. The real boundary is the OS account plus the Host allowlist, not the token.

### ADR-008: Fixed port 8765; Codespace starts the app on container start
- **Date:** 2026-08-18 / 2026-08-19
- **Decision:** One port, `8765`, declared in `.devcontainer/devcontainer.json` with private visibility and `onAutoForward: openBrowser`. `postStartCommand` launches `run.sh` detached, logging to `/tmp/koch-suite.log`. `python -m app.doctor` diagnoses the layers when the forwarded URL 404s.
- **Rationale:** A moving port and an un-forwarded port both look like a broken app. Commits `5b03b56`, `2191825`, `4bcc8e0` in [PR #7](https://github.com/kochmatthew462-collab/Bonsai-Grow-Nursery-Propigation/pull/7).
- **Status:** LOCKED
- **Impact:** Devcontainer changes take effect on **rebuild**, not restart.

### ADR-009: Drafting produces a claim ledger, not prose; no AI-detection gate; no "humanizer"
- **Date:** 2026-08-17
- **Decision:** The research half anchors every claim to a source, page and paragraph. No plagiarism percentage is printed; unattributed verbatim overlap against cited sources is reported with offsets. No AI-detector gate and no detector-evasion feature. Stylometric calibration against the author's own samples is provided instead.
- **Rationale:** Detectors measure perplexity, not authorship; evasion tools are unstable and presume the work is not the author's. Documented in `research-suite/README.md`, [PR #7](https://github.com/kochmatthew462-collab/Bonsai-Grow-Nursery-Propigation/pull/7).
- **Status:** LOCKED
- **Impact:** Any request to add a similarity percentage, an AI-detection gate, or paraphrase-to-evade is refused by design.

### ADR-010: Charting holds no PHI; instruments re-implemented, never reproduced
- **Date:** 2026-08-17
- **Decision:** No field for name, MRN or DOB; encounters keyed by bed/room; free text scanned for identifiers with one-click redaction; purge on every screen. Scoring arithmetic and thresholds for 23 instruments are implemented with fresh item wording; no copyrighted text or artwork (e.g. Wong-Baker FACES) is reproduced; rights holders are named on the Reference screen. ESI is walked as decision points the user answers, never auto-suggested.
- **Rationale:** HIPAA exposure on a personal device lands on the nurse; a paraphrased near-copy of an instrument is worse than either extreme; auto-triage is clinical decision support and indefensible in deposition. [PR #7](https://github.com/kochmatthew462-collab/Bonsai-Grow-Nursery-Propigation/pull/7)
- **Status:** LOCKED
- **Impact:** `test_charting_scales.py` asserts every instrument names its rights holder; `test_charting_language.py` holds the negative assertions.

### ADR-011: Every test suite runs offline
- **Date:** 2026-08-17
- **Decision:** No test needs network, keys or credentials. Retrieval adapters are tested against `httpx.MockTransport`; sync against a mocked Firestore; the front end with `node --check` plus orphan-route detection.
- **Rationale:** A syntax error once shipped that took out the whole UI and no Python test noticed (`9b4000a`). [PR #7](https://github.com/kochmatthew462-collab/Bonsai-Grow-Nursery-Propigation/pull/7)
- **Status:** LOCKED
- **Impact:** `bash research-suite/tests/run_all.sh` is the pre-push gate for the suite.

### ADR-012: Repository management moves to the chat-based maintenance log
- **Date:** 2026-09-06
- **Decision:** New work is decided and logged here first, with a session link, then applied to the repo. Claude Code session branches become archive-only context. This file plus `docs/repo-inventory/` is the "Domain 11: Code Repos" record.
- **Rationale:** Decisions spread across a dozen session branches were not searchable. [Session](https://claude.ai/code/session_01Ju7ziEbYXfmFG4jX54a6Q1)
- **Status:** OPEN — awaiting the owner's confirmation of the deployment method (see Immediate Action Items)
- **Impact:** Each future PR description should cite the ADR or issue row it resolves.

---

## Known Issues & Debt

| Issue | Impact | Session / PR | Status |
|---|---|---|---|
| PR #13 "Add a place to actually write in APA 7" is open and unmerged (head `479490f` on `claude/research-paper-generator-w6h7et`) | research suite feature gap | [PR #13](https://github.com/kochmatthew462-collab/Bonsai-Grow-Nursery-Propigation/pull/13) | needs review and merge decision |
| PR #10 Radiology Interpretation Academy was closed without merging; branch `claude/radiologic-imaging-interpreter-tlr236` is not on the remote | work possibly lost; scope question (does it belong in this repo?) | [PR #10](https://github.com/kochmatthew462-collab/Bonsai-Grow-Nursery-Propigation/pull/10) | needs owner decision |
| Three products share one repo and one Pages deployment; `research-suite/` source is published as static files by Pages | any committed secret is served publicly | ADR-006 | mitigated by `.gitignore`; consider splitting repos |
| Firestore shared document has a 1 MiB hard ceiling; sensor summaries accrue ~250 KB/yr for six plants | sync stops working when exceeded | ADR-003, ADR-005 | monitor the 800 KB warning; prune yearly |
| No CI/CD: no `.github/workflows`; tests run only by hand | regressions reach `main` unnoticed | — | open: add a GitHub Actions job running `research-suite/tests/run_all.sh` and `node --check js/*.js` |
| Tracker tests need `segno zxing-cpp numpy playwright pillow` installed manually | friction | README "Tests" | open: add a `requirements-test.txt` |
| Gated databases (CINAHL, PsycINFO, Embase, Cochrane, JBI, Scopus, IEEE, JSTOR) cannot be queried by API | manual citation-file import is the only path | `research-suite/README.md` | by design, will not change |
| Grammarly cannot be integrated; LanguageTool must be self-hosted via Docker | grammar checking degrades silently to off when server absent | `research-suite/README.md` | by design |
| Pi wiring cannot be proven by tests; `i2cdetect` and `--once --no-cloud` are the bench checks | a probe pulled loose reads dry forever | `pi/README.md` | operational, documented |
| Codespace data (keys, projects) lives only in the container | lost on container deletion | ADR-008 | export regularly |

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

# Clinical suite — local machine
cd research-suite
./run.sh                           # or .\run.ps1 on Windows; makes .venv on first run
python3 -m app.doctor --url        # prints the launch URL with the token
# In a Codespace: port 8765 forwards itself and opens the browser; rebuild the
# container after changing .devcontainer/devcontainer.json.

# Clinical suite — always-on box on the LAN
RESEARCH_SUITE_HOST=0.0.0.0 \
RESEARCH_SUITE_ALLOWED_HOSTS=pi-3bplus.local,192.168.1.50 \
./run.sh

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
# Clinical suite — all 13 suites, offline
bash research-suite/tests/run_all.sh

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

### "Forwarded Codespace URL returns 404"
**Solution:** ADR-008 — nothing is listening. Run `python3 -m app.doctor`; it says whether the app is not running, on another port, bound to loopback only, or the port was never forwarded. If the devcontainer was edited, rebuild the container.

### "Missing or invalid session token" on every reload
**Solution:** ADR-007 — the cookie was rejected and deleted. Get the launch URL back with `python3 -m app.doctor --url`, open it once, then bookmark the address without `#token=`.

### "421 Misdirected Request" from another machine
**Solution:** [PR #11](https://github.com/kochmatthew462-collab/Bonsai-Grow-Nursery-Propigation/pull/11) — binding wide is not admission. Add the address you are browsing from to `RESEARCH_SUITE_ALLOWED_HOSTS`.

### "bash: ./run.sh: /usr/bin/env bash^M: bad interpreter"
**Solution:** CRLF checkout on Windows. `.gitattributes` now pins `*.sh` to LF; re-clone or run `git checkout -- run.sh` after `git config core.autocrlf false`. `bash run.sh` also works.

### "Suite starts but Word export is missing"
**Solution:** `requirements.txt` has no optional split on purpose. `./run.sh` refreshes the venv when requirements change; delete `research-suite/.venv` and rerun if a wheel failed.

### "Blank screen in the suite"
**Solution:** commits `bc86193` and `9b4000a` — a CSS rule defeated the `hidden` attribute, and a syntax error in `app.js`. `python3 research-suite/tests/test_frontend.py` runs `node --check` on every script and catches both.

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
| `claude/research-paper-generator-w6h7et` | #7, #11, #12 merged; #13 open | 2026-08-17 → 2026-09-01 | `research-suite/**`, `.devcontainer/devcontainer.json`, `.gitattributes`, `.gitignore` |
| `claude/radiologic-imaging-interpreter-tlr236` | #10 closed, not merged | 2026-08-31 | none on `main`; branch absent from remote |
| `claude/repos-pdf-maintenance-log-jlwmtl` | this log | 2026-09-06 | `MAINTENANCE_LOG.md`, `docs/repo-inventory/*`, `docs/*.pdf` |

Full per-merge file lists: `docs/repo-inventory/files_by_session.txt`.

---

## Immediate Action Items

1. **Confirm deployment method** for the tracker: which branch does GitHub Pages currently publish, and what is the published URL? Record it in Overview.
2. **Decide PR #13** (merge, revise, or close) and **PR #10** (recover the radiology app into its own repo, or abandon).
3. **Add CI**: one GitHub Actions workflow running the suite tests and `node --check`.
4. **Lock this log**: from here on, every change starts as an ADR or issue row with a session link, then a PR that cites it.

---

## Change log for this file

| Date | Change | Session |
|---|---|---|
| 2026-09-06 | Created from the full repo inventory; ADR-001 to ADR-012 recorded | [session_01Ju7ziEbYXfmFG4jX54a6Q1](https://claude.ai/code/session_01Ju7ziEbYXfmFG4jX54a6Q1) |
