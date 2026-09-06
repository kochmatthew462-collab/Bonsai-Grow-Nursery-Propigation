# Domain 11 — Code Repos

## 11.1 Repository record

| Field | Value |
|---|---|
| Name | Bonsai-Grow-Nursery-Propigation |
| Owner | kochmatthew462-collab |
| URL | https://github.com/kochmatthew462-collab/Bonsai-Grow-Nursery-Propigation |
| Clone (HTTPS) | `https://github.com/kochmatthew462-collab/Bonsai-Grow-Nursery-Propigation.git` |
| Hosting | GitHub (cloud). No self-hosted mirror. |
| CI/CD | None. No `.github/workflows`. Tests are run by hand before pushing. |
| Deploy: tracker | GitHub Pages, deploy-from-branch, root folder, `.nojekyll` present |
| Deploy: clinical suite | Not deployed. `research-suite/run.sh` locally, or Codespace port 8765 (private) |
| Deploy: Pi monitor | `pi/install.sh` on the Pi → systemd unit `plantmon` |
| Default branch | `main` — head `7e52e50`, 2026-09-01 |
| Contributors | kochmatthew462-collab (13 commits), Claude via Claude Code sessions (30 commits) |
| Size | 111 tracked files, ~2.5 MB working tree, ~43,600 lines of source and tests |
| Secrets policy | `.env`, `research-suite/data/`, `.session-token`, `pi/config.json`, `*.db` git-ignored; committed key = rotate |

## 11.2 Branches and their purposes

| Branch | On remote | Purpose | Last commit | State |
|---|---|---|---|---|
| `main` | yes | Default; what GitHub Pages publishes | `7e52e50` 2026-09-01 Merge PR #12 | current |
| `claude/research-paper-generator-w6h7et` | yes (via PR #13 head `479490f`) | Claude Code session: clinical suite, APA 7, charting, Codespace/token fixes | `479490f` | PR #13 open |
| `claude/bonsai-metrics-tracking-h8r68l` | no (deleted after merge) | Claude Code session: tracker, profiles, calendar, weather, Pi monitor | `65f59fb` 2026-08-30 | fully merged via PR #9 |
| `claude/radiologic-imaging-interpreter-tlr236` | no | Claude Code session: Radiology Interpretation Academy | `6c533ac` | PR #10 closed, not merged |
| `claude/repos-pdf-maintenance-log-jlwmtl` | yes | This inventory, `MAINTENANCE_LOG.md`, this PDF | see PR | open |

## 11.3 Pull request ledger

| PR | Title | Session branch | Merged |
|---|---|---|---|
| #1 | Add bonsai nursery tracker with scannable QR plant labels | bonsai-metrics-tracking | 2026-08-16 (squash `750d52c`) |
| #2 | Add environment factors, care profiles, target bands and optional cloud sync | bonsai-metrics-tracking | 2026-08-16 (squash `9f8f639`) |
| #3 | Align care profiles with the three handbooks; rename to Koch's Tree Nursery Tracker | bonsai-metrics-tracking | 2026-08-16 (`ab26e88`) |
| #4 | Add master calendar, derived drip log, and handbook task windows | bonsai-metrics-tracking | 2026-08-17 (`3d97ca5`) |
| #5 | Add weather watch, move alerts, and calendar export | bonsai-metrics-tracking | 2026-08-17 (`39ffeb7`) |
| #6 | Add professional record layer: specimen, lineage, IPM, photos, derived readouts | bonsai-metrics-tracking | 2026-08-17 (`32ded12`) |
| #7 | Clinical suite: APA 7 research authoring with source-anchored claims, plus a nursing charting tab | research-paper-generator | 2026-09-01 (merge `365de62`, 24 commits) |
| #8 | Add Raspberry Pi cabinet monitor: continuous sensors, live card, chill logger | bonsai-metrics-tracking | 2026-08-29 (`00c8563`) |
| #9 | Fix Pi install for Bookworm (PEP 668) and non-'pi' user accounts | bonsai-metrics-tracking | 2026-08-30 (`a257bec`) |
| #10 | Add Radiology Interpretation Academy — self-study radiologic imaging interpretation app | radiologic-imaging-interpreter | **closed, not merged** |
| #11 | Let the suite be reached from another machine, deliberately | research-paper-generator | 2026-09-01 (`7cc36fe`) |
| #12 | Make the "already running" message describe the run that is running | research-paper-generator | 2026-09-01 (`7e52e50`) |
| #13 | Add a place to actually write in APA 7 | research-paper-generator | **open** |

## 11.4 File structure

```
.
├── index.html                tracker shell and routes
├── css/styles.css            theme tokens, light and dark
├── js/                       app.js · store.js · profiles.js · calendar.js
│                             weather.js · charts.js · photos.js · sync.js · qrcode.js
├── test/                     tracker tests (7 scripts + emit_matrices.js)
├── pi/                       sensord.py · sensors.py · store.py · cloud.py
│                             install.sh · plantmon.service · config.example.json
│                             test_pi.py · README.md
├── research-suite/
│   ├── run.sh / run.ps1      launcher; creates and refreshes .venv
│   ├── requirements.txt      fastapi, uvicorn, python-docx, python-pptx,
│   │                         matplotlib, anthropic, keyring, pypdf…
│   ├── .env.example          every key optional; HOST/PORT/ALLOWED_HOSTS
│   ├── app/
│   │   ├── main.py · security.py · settings.py · storage.py
│   │   ├── models.py · doctor.py
│   │   ├── apa/              citations, document, ooxml, assemble,
│   │   │                     audit_document, figures, prisma, workbook, deck
│   │   ├── charting/         routes, models, store, interlocks, scales,
│   │   │                     language, proofing, phi, narrative, export…
│   │   ├── compliance/       rubric, simulator, journals
│   │   ├── evidence/         levels, appraisal, dedupe
│   │   ├── research/         pico.py
│   │   ├── sources/          base, scholarly, gov, fulltext, importers
│   │   ├── writing/          draft, style, proof, integrity, statistics
│   │   └── static/           index.html · shell.js · app.js · chart.js · styles.css
│   └── tests/                run_all.sh + 13 offline suites
├── docs/
│   ├── repo-inventory/       raw git and file exports (Part 1)
│   ├── build_repo_pdf.py     rebuilds this PDF
│   └── Repo-Inventory-and-Maintenance-Log.pdf
├── MAINTENANCE_LOG.md        source of truth for decisions
├── .devcontainer/            Codespace: port 8765 private, auto-start
├── .gitattributes            LF for *.sh; binaries marked
├── .gitignore                secrets, data, venv, caches
├── .nojekyll                 Pages publishes as-is
└── README.md                 tracker documentation (33 KB)
```

## 11.5 Which Claude Code sessions touched which files

| Session | Files |
|---|---|
| `bonsai-metrics-tracking-h8r68l` (PRs #1–#6) | `index.html`, `css/styles.css`, `js/app.js`, `js/store.js`, `js/profiles.js`, `js/calendar.js`, `js/weather.js`, `js/charts.js`, `js/photos.js`, `js/sync.js`, `js/qrcode.js`, `test/*`, `README.md`, `.nojekyll` |
| `bonsai-metrics-tracking-h8r68l` (PR #8) | `pi/*` (all), `js/app.js`, `js/sync.js`, `test/sensors_test.py`, `README.md`, `.gitignore` |
| `bonsai-metrics-tracking-h8r68l` (PR #9) | `pi/README.md`, `pi/install.sh`, `pi/plantmon.service` |
| `research-paper-generator-w6h7et` (PR #7) | `research-suite/**` (all 80 files), `.devcontainer/devcontainer.json`, `.gitattributes`, `.gitignore` |
| `research-paper-generator-w6h7et` (PR #11) | `research-suite/app/{main,security,settings,doctor}.py`, `app/static/app.js`, `tests/test_security.py`, `README.md` |
| `research-paper-generator-w6h7et` (PR #12) | `research-suite/app/{main,security}.py`, `tests/test_security.py`, `README.md` |
| `repos-pdf-maintenance-log-jlwmtl` (this) | `MAINTENANCE_LOG.md`, `docs/**` |
