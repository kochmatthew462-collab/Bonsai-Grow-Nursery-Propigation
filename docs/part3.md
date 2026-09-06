# Part 3 — Chat-based change control

From 2026-09-06 (ADR-012) repository work follows this loop:

1. **Ask in the maintenance chat**, not in an ad-hoc Claude Code session.
2. The chat produces one of: code to paste into the local repo and push; git commands to export or import from the live target; or a deployment script to run from the terminal.
3. **Every decision is logged** in `MAINTENANCE_LOG.md` as an ADR or an issue row, with the session link, before the PR is opened. The PR description cites the ADR or row it resolves.
4. Claude Code branches are archive-only: consult them for old context; do not build new work on them.

## Entry template

> **Session [link]:**
> Decided *what*, because *why*.
> Updated `MAINTENANCE_LOG.md` ADR-*NNN* to *STATUS*.
> Deployment plan: *steps, target, verification*.

## Deployment facts still to confirm

| Question | Current answer from the repo | Owner to confirm |
|---|---|---|
| Are these repos on GitHub/GitLab? | GitHub, `kochmatthew462-collab/Bonsai-Grow-Nursery-Propigation` | ✓ |
| Self-hosted? | No. Pages for the tracker; local/Codespace for the suite; a Pi on the LAN for the monitor | — |
| CI/CD pipeline? | None | decide whether to add GitHub Actions |
| How are changes deployed today? | Merge to `main` → Pages republishes; suite and Pi are pulled by hand | confirm which branch Pages publishes and its URL |

## Locking the schema

Once the table above is confirmed, ADR-012 moves to LOCKED and `MAINTENANCE_LOG.md`
becomes the sole source of truth for architecture. The exports in
`docs/repo-inventory/` are a snapshot; regenerate them with the commands in
Part 1 and rebuild this PDF with `python3 docs/build_repo_pdf.py` whenever the
inventory changes.
