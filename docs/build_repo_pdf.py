#!/usr/bin/env python3
"""Build docs/Repo-Inventory-and-Maintenance-Log.pdf from MAINTENANCE_LOG.md
and the raw exports in docs/repo-inventory/. Run from the repo root:
    python3 docs/build_repo_pdf.py
Needs: pip install weasyprint markdown   (and fonts-texgyre for the house faces;
falls back to Liberation/DejaVu when absent)."""
import datetime, html, pathlib, subprocess
import markdown
from weasyprint import HTML

ROOT = pathlib.Path(__file__).resolve().parent.parent
INV = ROOT / "docs" / "repo-inventory"
OUT = ROOT / "docs" / "Repo-Inventory-and-Maintenance-Log.pdf"
SESSION = "https://claude.ai/code/session_01Ju7ziEbYXfmFG4jX54a6Q1"

def sh(*cmd):
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True).stdout.strip()

def pre(path):
    return "<pre>" + html.escape((INV / path).read_text()) + "</pre>"

def md(text):
    return markdown.markdown(text, extensions=["tables", "fenced_code", "toc"])

today = datetime.date.today().isoformat()
head = sh("git", "log", "-1", "--format=%h %ad %s", "--date=short", "main")
n_commits = sh("git", "rev-list", "--count", "--all")
n_files = sh("git", "ls-files").count("\n") + 1

cover = f"""
<section class="cover">
  <p class="kicker">Domain 11 · Code Repos</p>
  <h1>Repository Inventory<br>&amp; Maintenance Log</h1>
  <p class="sub">Koch's Tree Nursery Tracker · Koch Clinical Suite · Pi Cabinet Monitor</p>
  <table class="meta">
    <tr><th>Repository</th><td>kochmatthew462-collab/Bonsai-Grow-Nursery-Propigation</td></tr>
    <tr><th>Head of main</th><td>{html.escape(head)}</td></tr>
    <tr><th>Commits (all branches)</th><td>{n_commits}</td></tr>
    <tr><th>Tracked files</th><td>{n_files}</td></tr>
    <tr><th>Compiled</th><td>{today}</td></tr>
    <tr><th>Session</th><td>{SESSION}</td></tr>
  </table>
  <p class="note">Prepared by Matthew Koch. Parts 1–3 of the repository-management plan:
  export and index, permanent maintenance log, chat-based change control.</p>
</section>
"""

part1 = f"""
<section>
<h1>Part 1 — Export &amp; Index</h1>
<p>Raw output of the export commands, run at the repository root on {today}.
Only this repository was available in the session; the three
<em>myomedprep.org</em> projects are not attached and their exports must be
pasted separately.</p>

<h2>[Project: Bonsai-Grow-Nursery-Propigation]</h2>
<h3>Git History</h3>{pre("git_log_dated.txt")}
<h3>Remotes</h3>{pre("git_remotes.txt")}
<h3>Branch Structure</h3>{pre("git_branches.txt")}
<h3>File Inventory</h3>{pre("file_tree.txt")}
</section>
"""

domain11 = md((ROOT / "docs" / "domain11.md").read_text())
log = md((ROOT / "MAINTENANCE_LOG.md").read_text())
part3 = md((ROOT / "docs" / "part3.md").read_text())
appendix = f"""
<section>
<h1>Appendix — Files touched per session merge</h1>
{pre("files_by_session.txt")}
</section>
"""

css = """
@page { size: Letter; margin: 22mm 20mm 24mm 20mm;
  @bottom-left { content: "Repository Inventory & Maintenance Log · " string(doctitle); font: 8.5pt "TeX Gyre Heros", "Liberation Sans", sans-serif; color: #17273F; }
  @bottom-right { content: counter(page) " / " counter(pages); font: 8.5pt "TeX Gyre Heros", "Liberation Sans", sans-serif; color: #17273F; } }
@page :first { @bottom-left { content: none } @bottom-right { content: none } }
body { font: 10.5pt/1.42 "TeX Gyre Schola", "Century Schoolbook", "Liberation Serif", serif; color: #1a1a1a; }
h1, h2, h3, h4 { font-family: "TeX Gyre Heros", "Liberation Sans", sans-serif; color: #17273F; }
h1 { font-size: 20pt; border-bottom: 2pt solid #7A1E2B; padding-bottom: 4pt; margin: 0 0 12pt; string-set: doctitle content(); page-break-before: always; }
h2 { font-size: 14.5pt; margin: 18pt 0 6pt; border-left: 4pt solid #B4913E; padding-left: 8pt; }
h3 { font-size: 11.5pt; margin: 14pt 0 4pt; color: #7A1E2B; }
section { display: block; }
p { margin: 0 0 7pt; }
a { color: #7A1E2B; text-decoration: none; }
code { font: 9pt "Liberation Mono", "DejaVu Sans Mono", monospace; background: #F8F4EA; padding: 0 2pt; }
pre { font: 7.8pt/1.3 "Liberation Mono", "DejaVu Sans Mono", monospace; background: #F8F4EA; border: 0.5pt solid #C9A94A; padding: 7pt 8pt; white-space: pre-wrap; word-break: break-all; margin: 6pt 0 10pt; }
table { border-collapse: collapse; width: 100%; margin: 6pt 0 12pt; font-size: 9.2pt; page-break-inside: auto; }
th, td { border: 0.5pt solid #C9A94A; padding: 3.5pt 5pt; vertical-align: top; text-align: left; }
th { background: #17273F; color: #F8F4EA; font-family: "TeX Gyre Heros", "Liberation Sans", sans-serif; font-weight: 600; }
tr { page-break-inside: avoid; }
tbody tr:nth-child(even) td { background: #FBF9F2; }
ul, ol { margin: 0 0 8pt 0; padding-left: 18pt; }
li { margin-bottom: 2pt; }
strong { color: #17273F; }
hr { border: 0; border-top: 0.5pt solid #C9A94A; margin: 12pt 0; }
.cover { page-break-after: always; padding-top: 60mm; }
.cover h1 { border: 0; font-size: 30pt; line-height: 1.15; page-break-before: auto; margin-bottom: 6pt; }
.cover .kicker { font-family: "TeX Gyre Heros", sans-serif; letter-spacing: 2pt; text-transform: uppercase; color: #7A1E2B; font-size: 10pt; }
.cover .sub { font-size: 13pt; color: #7A1E2B; margin-bottom: 24pt; }
.cover .meta th { width: 38mm; background: #F8F4EA; color: #17273F; }
.cover .note { margin-top: 24pt; font-size: 9.5pt; color: #444; }
.toc { page-break-after: always; }
"""

toc = """
<section class="toc">
<h1>Contents</h1>
<ol>
<li>Part 1 — Export &amp; Index (raw git and file exports)</li>
<li>Domain 11 — Code Repos (structured schema entry)</li>
<li>Part 2 — MAINTENANCE_LOG.md (ADRs, known issues, deploy, debugging, session index)</li>
<li>Part 3 — Chat-based change control going forward</li>
<li>Appendix — Files touched per session merge</li>
</ol>
</section>
"""

doc = f"<!doctype html><meta charset='utf-8'><style>{css}</style>{cover}{toc}{part1}<section>{domain11}</section><section>{log}</section><section>{part3}</section>{appendix}"
(ROOT / "docs" / ".build.html").write_text(doc)
HTML(string=doc, base_url=str(ROOT)).write_pdf(OUT)
(ROOT / "docs" / ".build.html").unlink()
print("wrote", OUT)
