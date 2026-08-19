"""
The local web application.

Runs on 127.0.0.1 with a per-run session token — see `security.py` for what that
protects against and, more importantly, what it does not. Start it with
`./run.sh` (or `run.ps1` on Windows), which prints a URL with the token in it.

The API is deliberately coarse-grained: one endpoint per step of the workflow
rather than a REST resource per record. The unit of work here is "run the
searches", "screen these twelve sources", "export the paper" — and an endpoint
shaped like the step can save the project once, atomically, at the end.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

from fastapi import Body, FastAPI, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import security, settings as settings_module, storage
from .apa import (
    assemble, audit_document, deck as deck_module, figures as figures_module,
    prisma as prisma_module, workbook as workbook_module,
)
from .charting import routes as charting_routes, store as charting_store
from .compliance import journals as journals_module, rubric as rubric_module, \
    simulator as simulator_module
from .research import pico as pico_module
from .apa.citations import CitationContext
from .apa.document import ApaPaper, APPROVED_FONTS, default_running_head
from .evidence import appraisal as appraisal_module, dedupe, levels
from .models import (
    Appraisal, AppraisalItem, Author, Claim, EvidenceLevel, Extraction, Project,
    SupportType, Work, WorkType,
)
from .sources import fulltext, gov, importers, scholarly  # noqa: F401
from .sources.base import REGISTRY, Fetcher
from .writing import (
    draft as draft_module, integrity, proof as proof_module,
    statistics as statistics_module, style as style_module,
)

SETTINGS = settings_module.load()
STORE = storage.ProjectStore(SETTINGS.data_dir / "projects")
SECURITY = security.SecurityConfig(
    SETTINGS.session_token, SETTINGS.host, SETTINGS.port)
STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="Koch Research Suite", docs_url=None, redoc_url=None,
              openapi_url=None)

# The charting tab. It gets its own store and export directory rather than sharing
# the research project store, because the two hold different kinds of thing and
# have different lifetimes: a research project is kept for months, and a shift's
# charting should be purged when the shift ends. Separate directories make
# "delete all the clinical data and none of the research" a one-line operation.
CHART_STORE = charting_store.EncounterStore(SETTINGS.data_dir / "charting")
CHART_EXPORTS = SETTINGS.export_dir / "charting"
charting_routes.configure(CHART_STORE, CHART_EXPORTS)
app.include_router(charting_routes.router)


def fetcher() -> Fetcher:
    return Fetcher(
        cache_dir=SETTINGS.cache_dir,
        contact_email=SETTINGS.contact_email,
        api_keys=SETTINGS.api_keys,
    )


@app.middleware("http")
async def enforce_security(request: Request, call_next):
    try:
        await security.guard(request, SECURITY)
    except HTTPException as error:
        return JSONResponse({"detail": error.detail}, status_code=error.status_code)
    response = await call_next(request)

    # Never cache the shell or its scripts.
    #
    # A browser holds on to /static/app.js across a server restart, so a fixed
    # bug keeps reproducing on the user's screen and the only cure is a hard
    # refresh they have to be told about — which happened here, repeatedly.
    # This is a localhost single-user app: no CDN, no bandwidth budget, and the
    # files are tens of kilobytes. Correctness beats a cache hit every time.
    if request.url.path == "/" or request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"

    # No embedding, no referrer leakage, no MIME sniffing. The CSP is strict
    # because the UI ships no third-party code at all.
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = (
        "default-src 'none'; script-src 'self'; style-src 'self'; "
        "img-src 'self' data:; connect-src 'self'; form-action 'self'; "
        "base-uri 'none'; frame-ancestors 'none'"
    )
    return response


# --------------------------------------------------------------------- shell


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    return HTMLResponse((STATIC_DIR / "index.html").read_text("utf-8"))


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# -------------------------------------------------------------------- config


@app.get("/api/config")
async def get_config() -> dict[str, Any]:
    client = fetcher()
    return {
        "settings": SETTINGS.redacted(),
        # Where this is actually reachable, which is not always localhost. The
        # Settings page used to state "Localhost only — not reachable from your
        # network" unconditionally, which is false in a Codespace and false in
        # the reassuring direction.
        "access": {
            "url": SECURITY.public_url(),
            "codespace": SECURITY.codespace,
            "local_only": SECURITY.local_only and not SECURITY.codespace,
        },
        "fonts": sorted(APPROVED_FONTS),
        "sources": [
            {
                "key": s.key, "label": s.label, "kind": s.kind,
                "available": s.available, "requires": s.requires,
                "note": s.note, "docs": s.docs,
            }
            for s in REGISTRY.status(client)
        ],
        "appraisal_templates": appraisal_module.available_templates(),
        "warnings": [w for w in [settings_module.contact_email_warning(SETTINGS)] if w],
        "drafting_available": draft_module.Drafter(SETTINGS.key("anthropic")).available(),
        "integrity_notice": draft_module.integrity_notice("graduate"),
        "levels": [
            {"value": level.value, "label": level.label, "rank": level.rank}
            for level in EvidenceLevel
        ],
    }


@app.post("/api/config/key")
async def set_key(name: str = Body(...), value: str = Body("")) -> dict[str, str]:
    try:
        where = SETTINGS.store_key(name, value)
    except ValueError as error:
        raise HTTPException(400, str(error)) from error
    return {"stored": where}


@app.post("/api/config/general")
async def set_general(
    contact_email: str = Body(""), default_font: str = Body(""),
) -> dict[str, str]:
    if contact_email:
        SETTINGS.contact_email = contact_email.strip()
        SETTINGS._write_env("RESEARCH_SUITE_EMAIL", SETTINGS.contact_email)
    if default_font:
        if default_font not in APPROVED_FONTS:
            raise HTTPException(400, f"{default_font} is not an APA 7 §2.19 typeface")
        SETTINGS.default_font = default_font
        SETTINGS._write_env("RESEARCH_SUITE_FONT", default_font)
    return {"status": "saved"}


# ------------------------------------------------------------------ projects


@app.get("/api/projects")
async def list_projects() -> dict[str, Any]:
    return {"projects": STORE.list_projects()}


@app.post("/api/projects")
async def create_project(
    topic: str = Body(...), question: str = Body(""),
    academic_level: str = Body("graduate"),
) -> dict[str, Any]:
    if not topic.strip():
        raise HTTPException(400, "A topic is required.")
    project = STORE.new_project(topic, question, academic_level)
    return {"project": _project_payload(project)}


@app.get("/api/projects/{project_id}")
async def get_project(project_id: str) -> dict[str, Any]:
    return {"project": _project_payload(_load(project_id))}


@app.delete("/api/projects/{project_id}")
async def delete_project(project_id: str) -> dict[str, bool]:
    return {"deleted": STORE.delete(project_id)}


@app.post("/api/projects/{project_id}/settings")
async def update_project(project_id: str, payload: dict = Body(...)) -> dict[str, Any]:
    project = _load(project_id)
    for name in ("topic", "question", "academic_level", "min_level"):
        if name in payload:
            setattr(project, name, str(payload[name]))
    for name in ("inclusion", "exclusion"):
        if name in payload:
            setattr(project, name, [str(v) for v in payload[name] if str(v).strip()])
    if "pico" in payload and isinstance(payload["pico"], dict):
        project.pico = {str(k): str(v) for k, v in payload["pico"].items()}
    if "title_page" in payload and isinstance(payload["title_page"], dict):
        page = payload["title_page"]
        for name in ("variant", "title", "course", "instructor", "due_date",
                     "running_head", "author_note"):
            if name in page:
                setattr(project.title_page, name, str(page[name]))
        for name in ("authors", "affiliations"):
            if name in page:
                setattr(project.title_page, name,
                        [str(v) for v in page[name] if str(v).strip()])
        if not project.title_page.running_head:
            project.title_page.running_head = default_running_head(
                project.title_page.title or project.topic)
    STORE.save(project)
    return {"project": _project_payload(project)}


# -------------------------------------------------------------------- search


@app.post("/api/projects/{project_id}/search")
async def run_search(
    project_id: str,
    query: str = Body(...),
    sources: list[str] = Body(default=[]),
    limit: int = Body(30),
    years_back: int = Body(0),
) -> dict[str, Any]:
    project = _load(project_id)
    client = fetcher()
    available = {s.key: s for s in REGISTRY.searchable(client)}
    chosen = [available[k] for k in sources if k in available] or list(available.values())
    if not chosen:
        raise HTTPException(400, "No searchable sources are available.")

    async def one(spec):
        kwargs: dict[str, Any] = {"limit": limit}
        if spec.key in ("pubmed", "cochrane-via-medline"):
            kwargs["min_level"] = project.min_level
            if years_back:
                kwargs["years_back"] = years_back
        if spec.key == "cochrane-via-medline":
            kwargs.pop("min_level", None)
            kwargs.pop("years_back", None)
        try:
            return await spec.search(client, query, **kwargs)
        except TypeError:
            return await spec.search(client, query, limit=limit)
        except Exception as error:  # a failing source must not fail the search
            return ([], {"source": spec.label, "query": query,
                         "error": f"{type(error).__name__}: {error}"})

    results = await asyncio.gather(*(one(spec) for spec in chosen))

    found: list[Work] = []
    for works, audit in results:
        project.searches.append(audit)
        found.extend(works)

    levels.apply_all(found)
    combined = project.works + found
    unique, merge_log = dedupe.deduplicate(combined)
    project.works = unique
    for entry in merge_log:
        project.excluded_notes.append({
            "stage": "duplicate",
            "study": entry.get("removed_title", entry.get("removed", "")),
            "reason": f"duplicate of {entry.get('kept_title', '')[:80]} "
                      f"(matched on {entry.get('matched_on')}); record from "
                      f"{entry.get('removed_source')} merged in",
        })
    STORE.save(project)

    return {
        "found": len(found),
        "after_dedupe": len(unique),
        "merged": len(merge_log),
        "searches": [s for s in project.searches[-len(chosen):]],
        "project": _project_payload(project),
    }


@app.post("/api/projects/{project_id}/import")
async def import_citations(
    project_id: str,
    file: UploadFile = File(...),
    source_hint: str = Form(""),
) -> dict[str, Any]:
    project = _load(project_id)
    raw = await file.read()
    if len(raw) > 12 * 1024 * 1024:
        raise HTTPException(413, "That file is larger than 12 MB. Export in batches.")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("latin-1", errors="replace")

    try:
        works = importers.parse(text, file.filename or "", source_hint)
    except ValueError as error:
        raise HTTPException(400, str(error)) from error
    if not works:
        raise HTTPException(400, "No records were found in that file.")

    levels.apply_all(works)
    unique, merge_log = dedupe.deduplicate(project.works + works)
    project.works = unique
    project.searches.append({
        "source": f"{source_hint or (works[0].source_db if works else 'file import')}",
        "query": f"manual search, imported from {file.filename}",
        "run_at": works[0].retrieved_at if works else "",
        "retrieved": str(len(works)),
        "from_cache": "no",
        "coverage_note": ("Imported from a citation export. The database's own "
                          "query string is not captured automatically — record it "
                          "in the project notes for reproducibility."),
    })
    STORE.save(project)
    return {
        "imported": len(works), "after_dedupe": len(unique),
        "merged": len(merge_log), "project": _project_payload(project),
    }


# ----------------------------------------------------------------- screening


@app.post("/api/projects/{project_id}/screen")
async def screen(project_id: str, decisions: list[dict] = Body(...)) -> dict[str, Any]:
    project = _load(project_id)
    by_key = {w.key: w for w in project.works}
    changed = 0
    for decision in decisions:
        work = by_key.get(str(decision.get("key", "")))
        if not work:
            continue
        if "included" in decision:
            work.included = bool(decision["included"]) if decision["included"] is not None else None
        work.screen_reason = str(decision.get("reason", work.screen_reason))
        if decision.get("level"):
            try:
                levels.set_by_hand(work, EvidenceLevel(str(decision["level"])),
                                   str(decision.get("level_note", "reviewed by hand")))
            except ValueError:
                pass
        changed += 1
    STORE.save(project)
    return {"updated": changed, "project": _project_payload(project)}


@app.post("/api/projects/{project_id}/retractions")
async def check_retractions(project_id: str) -> dict[str, Any]:
    project = _load(project_id)
    targets = [w for w in project.works if w.included is not False]
    log = await scholarly.check_retractions(fetcher(), targets)
    for entry in log:
        if entry["retracted"] == "yes":
            project.excluded_notes.append({
                "stage": "retraction", "study": entry["title"],
                "reason": f"retraction found: {entry['detail']}",
            })
    STORE.save(project)
    return {
        "checked": len(log),
        "retracted": sum(1 for e in log if e["retracted"] == "yes"),
        "log": log,
        "project": _project_payload(project),
    }


# ----------------------------------------------------- appraisal & extraction


@app.post("/api/projects/{project_id}/appraisal/blank")
async def make_appraisal(
    project_id: str, key: str = Body(...), template: str = Body(""),
) -> dict[str, Any]:
    project = _load(project_id)
    work = project.work(key)
    if not work:
        raise HTTPException(404, f"no source with key {key}")
    appraisal = appraisal_module.blank_appraisal(work, template)
    project.appraisals = [a for a in project.appraisals if a.work_key != key]
    project.appraisals.append(appraisal)
    STORE.save(project)
    return {"appraisal": storage._to_jsonable(appraisal),
            "instrument_url": appraisal_module.instrument_url(
                template or appraisal_module.choose_template(work))}


@app.post("/api/projects/{project_id}/appraisal")
async def save_appraisal(project_id: str, payload: dict = Body(...)) -> dict[str, Any]:
    project = _load(project_id)
    key = str(payload.get("work_key", ""))
    existing = next((a for a in project.appraisals if a.work_key == key), None)
    if not existing:
        raise HTTPException(404, "No appraisal exists for that source yet.")
    for index, item in enumerate(payload.get("items") or []):
        if index < len(existing.items):
            existing.items[index].answer = str(item.get("answer", "unclear"))
            existing.items[index].note = str(item.get("note", ""))
    existing.strengths = str(payload.get("strengths", existing.strengths))
    existing.limitations = str(payload.get("limitations", existing.limitations))
    existing.appraised_by = "user"
    appraisal_module.finalise(existing)
    STORE.save(project)
    return {"appraisal": storage._to_jsonable(existing)}


@app.post("/api/projects/{project_id}/extraction")
async def save_extraction(project_id: str, payload: dict = Body(...)) -> dict[str, Any]:
    project = _load(project_id)
    key = str(payload.get("work_key", ""))
    if not project.work(key):
        raise HTTPException(404, f"no source with key {key}")
    extraction = storage._fill(Extraction, payload)
    extraction.work_key = key
    project.extractions = [e for e in project.extractions if e.work_key != key]
    project.extractions.append(extraction)
    STORE.save(project)
    return {"extraction": storage._to_jsonable(extraction)}


# --------------------------------------------------------------------- style


@app.get("/api/samples")
async def list_samples() -> dict[str, Any]:
    return {"samples": STORE.list_samples()}


@app.post("/api/samples")
async def add_sample(
    name: str = Form(...), file: UploadFile | None = File(None), text: str = Form(""),
) -> dict[str, Any]:
    body = text
    if file is not None:
        raw = await file.read()
        try:
            body = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            body = raw.decode("latin-1", errors="replace")
    if not body.strip():
        raise HTTPException(400, "The sample is empty.")
    STORE.save_sample(name, body)
    return {"samples": STORE.list_samples()}


@app.delete("/api/samples/{name}")
async def remove_sample(name: str) -> dict[str, Any]:
    STORE.delete_sample(name)
    return {"samples": STORE.list_samples()}


@app.post("/api/projects/{project_id}/style")
async def rebuild_style(project_id: str) -> dict[str, Any]:
    project = _load(project_id)
    samples = STORE.read_samples()
    project.style = style_module.build_profile(samples)
    STORE.save(project)
    return {
        "style": storage._to_jsonable(project.style),
        "brief": style_module.style_brief(project.style, samples),
    }


# ------------------------------------------------------------------ drafting


@app.post("/api/projects/{project_id}/draft")
async def draft(
    project_id: str, section: str = Body(""), replace: bool = Body(True),
) -> dict[str, Any]:
    project = _load(project_id)
    drafter = draft_module.Drafter(SETTINGS.key("anthropic"))
    samples = STORE.read_samples()

    plan = draft_module.default_sections(project)
    if section:
        plan = [s for s in plan if s.heading.lower() == section.lower()]
        if not plan:
            plan = [draft_module.Section(section, 1)]

    if replace:
        headings = {s.heading for s in plan}
        project.claims = [c for c in project.claims if c.section not in headings]

    # Run sections sequentially so the evidence block stays cache-warm rather
    # than being written once per parallel request.
    result = draft_module.DraftResult()
    for spec in plan:
        part = await asyncio.to_thread(drafter.draft_section, project, spec, samples)
        base = max((c.order for c in project.claims), default=-1) + 1
        for offset, claim in enumerate(part.claims):
            claim.order = base + offset
        project.claims.extend(part.claims)
        result.claims.extend(part.claims)
        result.notes.extend(part.notes)
        result.dropped_keys.extend(part.dropped_keys)
        result.unsupported.extend(part.unsupported)
        for name, value in part.usage.items():
            result.usage[name] = result.usage.get(name, 0) + value

    STORE.save(project)
    return {
        "claims_added": len(result.claims),
        "notes": result.notes,
        "dropped_keys": sorted(set(result.dropped_keys)),
        "unsupported": result.unsupported,
        "usage": result.usage,
        "project": _project_payload(project),
    }


@app.post("/api/projects/{project_id}/claims")
async def save_claims(project_id: str, claims: list[dict] = Body(...)) -> dict[str, Any]:
    project = _load(project_id)
    rebuilt: list[Claim] = []
    for index, raw in enumerate(claims):
        claim = storage._fill(Claim, raw)
        claim.order = index
        if not claim.claim_id:
            claim.claim_id = f"claim-{index + 1:03d}"
        rebuilt.append(claim)
    project.claims = rebuilt
    STORE.save(project)
    return {"project": _project_payload(project)}


@app.get("/api/projects/{project_id}/integrity")
async def integrity_report(project_id: str) -> dict[str, Any]:
    project = _load(project_id)
    report = integrity.check_project(project)
    return {
        "summary": report.summary(),
        "words_checked": report.words_checked,
        "sources_checked": report.sources_checked,
        "overlaps": [
            {"phrase": o.phrase, "words": o.word_count, "source": o.work_label,
             "quoted": o.in_marked_quote, "severity": o.severity,
             "claim": o.claim_id, "section": o.section}
            for o in report.overlaps if o.severity != "minor"
        ],
        "blockers": integrity.export_blockers(project),
        "warnings": integrity.export_warnings(project),
        "external": integrity.external_scan_guidance(
            [k for k in ("copyleaks",) if SETTINGS.key(k)]),
        "style": style_module.compare(
            "\n\n".join(c.text for c in project.claims), project.style),
    }


# -------------------------------------------------------------------- export


@app.post("/api/projects/{project_id}/export")
async def export(
    project_id: str,
    paper: bool = Body(True),
    audit: bool = Body(True),
    slides: bool = Body(False),
    matrix: bool = Body(True),
    abstract: str = Body(""),
    keywords: list[str] = Body(default=[]),
    font: str = Body(""),
    force: bool = Body(False),
) -> dict[str, Any]:
    project = _load(project_id)
    blockers = integrity.export_blockers(project)
    if blockers and not force:
        return {"exported": [], "blockers": blockers,
                "message": ("Export stopped. These are defects that would make "
                            "the paper indefensible, not style preferences. Fix "
                            "them, or re-export with force to produce a draft "
                            "for your own review.")}

    chosen_font = font or SETTINGS.default_font
    if chosen_font not in APPROVED_FONTS:
        raise HTTPException(400, f"{chosen_font} is not an APA 7 §2.19 typeface")

    context = CitationContext(project.cited_works() or project.works,
                              group_abbreviations=_group_abbreviations(project))
    out = SETTINGS.export_dir / project.project_id
    out.mkdir(parents=True, exist_ok=True)
    written: list[dict[str, str]] = []

    if paper:
        builder = ApaPaper(project, context, font=chosen_font)
        builder.title_page()
        if abstract.strip():
            builder.abstract(abstract, keywords or assemble.suggest_keywords(project))
        builder.body(assemble.build_blocks(project, context))

        # Attached figures, placed as numbered APA figures with their structured
        # notes. The figure generator existed from the start and nothing ever
        # called it for the paper — an audit found `ApaPaper.figure` and
        # `ApaPaper.table` reachable from no code path at all.
        for index, attached in enumerate(
                (getattr(project, "notes", None) or {}).get("figures", []), 1):
            image = out / str(attached.get("path", ""))
            if not image.exists():
                continue
            builder.figure(
                number=index,
                title=str(attached.get("title") or f"Figure {index}"),
                image_path=str(image),
                note=str(attached.get("note") or attached.get("caption") or ""))
            data = attached.get("table") or {}
            if data.get("headers") and data.get("rows"):
                # The underlying numbers as an APA table beside the figure. A
                # figure a reader cannot check is a figure they have to take on
                # trust.
                builder.table(
                    number=index,
                    title=f"Values Plotted in Figure {index}",
                    headers=list(data["headers"]),
                    rows=[[str(cell) for cell in row] for row in data["rows"]],
                    note="Values from which the figure was drawn.")

        builder.references(project.cited_works())
        path = out / f"{project.project_id}-paper.docx"
        builder.save(str(path))
        written.append({"kind": "paper", "name": path.name,
                        "words": str(assemble.word_count(project))})

    if matrix:
        # The evidence matrix as a spreadsheet. It is the one artefact here that
        # is worked *on* rather than read — sorted by level, filtered to the
        # trials, a column pasted into a meta-analysis — and a Word table does
        # none of that.
        path = out / f"{project.project_id}-evidence-matrix.xlsx"
        workbook_module.write_matrix(project, path)
        written.append({"kind": "evidence matrix", "name": path.name,
                        "words": ""})

    if audit:
        context.reset_group_state()
        path = out / f"{project.project_id}-rationale-and-sources.docx"
        audit_document.build_audit_document(
            project, context, str(path),
            drafted=any(not c.verified for c in project.claims) or bool(project.claims),
            font=chosen_font)
        written.append({"kind": "audit", "name": path.name})

    if slides:
        context.reset_group_state()
        path = out / f"{project.project_id}-slides.pptx"
        # The same attached figures the paper gets. `deck.figure_slide` builds a
        # proper APA figure slide — number, italic title, note beneath — and was
        # never passed anything, so every deck came out with no figures in it
        # while the interface said otherwise.
        deck_figures = []
        for index, attached in enumerate(
                (getattr(project, "notes", None) or {}).get("figures", []), 1):
            image = out / str(attached.get("path", ""))
            if not image.exists():
                continue
            deck_figures.append(deck_module.Slide(
                title=str(attached.get("title") or f"Figure {index}"),
                figure_path=str(image),
                figure_number=index,
                figure_title=str(attached.get("title") or ""),
                figure_note=str(attached.get("note")
                                or attached.get("caption") or ""),
                speaker_notes=_figure_speaker_notes(attached, index),
                kind="figure",
            ))
        deck_module.build_deck(project, context, str(path),
                               figures=deck_figures, font=chosen_font)
        written.append({"kind": "slides", "name": path.name})

    return {"exported": written, "blockers": blockers,
            "warnings": integrity.export_warnings(project),
            "directory": str(out)}


@app.get("/api/projects/{project_id}/files")
async def list_files(project_id: str) -> dict[str, Any]:
    out = SETTINGS.export_dir / _safe(project_id)
    if not out.exists():
        return {"files": []}
    return {"files": [
        {"name": p.name, "bytes": p.stat().st_size,
         "modified": int(p.stat().st_mtime)}
        for p in sorted(out.iterdir()) if p.is_file()
    ]}


@app.get("/api/projects/{project_id}/files/{name}")
async def download(project_id: str, name: str) -> FileResponse:
    # Resolve and confine: a name containing traversal must not escape the
    # project's own export directory.
    root = (SETTINGS.export_dir / _safe(project_id)).resolve()
    path = (root / name).resolve()
    if not str(path).startswith(str(root)) or not path.is_file():
        raise HTTPException(404, "No such file.")
    return FileResponse(path, filename=path.name)


@app.post("/api/projects/{project_id}/figure/levels")
async def level_figure(project_id: str) -> dict[str, Any]:
    project = _load(project_id)
    counts = levels.summarise(project.included_works())
    if not counts:
        raise HTTPException(400, "No included studies to chart.")
    out = SETTINGS.export_dir / project.project_id
    out.mkdir(parents=True, exist_ok=True)
    figure = figures_module.level_distribution_figure(
        counts, path=out / "figure-levels.png")
    # Attached like every other figure. It was not, and the difference was
    # invisible: the chart appeared on screen, and then was silently absent
    # from the exported paper because only `/figure` wrote to the ledger.
    _attach_figure(project, figure, kind="levels",
                   title="Distribution of evidence levels",
                   caption="Levels assigned to the included studies.")
    return {"path": Path(figure.path).name, "note": figure.note,
            "attached": True,
            "placement": ("Attached to the project. The exporter places it in "
                          "the paper as a numbered APA figure with its note "
                          "beneath, and on a slide in the deck."),
            "table": {"headers": figure.data_table[0], "rows": figure.data_table[1]}}


def _figure_speaker_notes(attached: dict[str, Any], index: int) -> str:
    """What to say while the figure is on screen, in complete sentences.

    Speaker notes are prose, not the bullets again. These name the figure, say
    what it plots, and — where the figure has an underlying table — give the
    range so the presenter has the numbers without reading them off the slide.
    Nothing here is invented: every sentence is built from the figure's own
    data table and its APA note.
    """
    title = str(attached.get("title") or f"Figure {index}")
    lines = [f"Figure {index}, {title}, is on screen now."]

    note = str(attached.get("note") or "").strip()
    if note:
        lines.append(note if note.endswith(".") else note + ".")

    data = attached.get("table") or {}
    rows = data.get("rows") or []
    headers = data.get("headers") or []
    if rows and headers:
        lines.append(
            f"The figure plots {len(rows)} "
            f"{'entry' if len(rows) == 1 else 'entries'} across "
            f"{len(headers)} column{'' if len(headers) == 1 else 's'}: "
            + ", ".join(str(h) for h in headers) + ".")
        first = ", ".join(str(cell) for cell in rows[0])
        lines.append(f"The first row reads: {first}.")

    caption = str(attached.get("caption") or "").strip()
    if caption:
        lines.append(caption if caption.endswith(".") else caption + ".")

    lines.append(
        "State the source aloud when you present a figure drawn from another "
        "author's data, and keep the in-text citation on the slide itself — an "
        "audience cannot see your notes.")
    return "\n".join(lines)


def _attach_figure(project: Project, figure, *, kind: str, title: str,
                   caption: str = "") -> str:
    """Record a built figure on the project so the exporter can place it.

    One function rather than two copies, because the two copies had drifted:
    the general figure route attached and the evidence-level route did not.
    """
    if not isinstance(getattr(project, "notes", None), dict):
        project.notes = {}
    stored = project.notes.setdefault("figures", [])
    name = Path(figure.path).name
    stored[:] = [f for f in stored if f.get("path") != name]
    stored.append({
        "path": name, "kind": kind, "title": title or kind.title(),
        "caption": caption, "note": figure.note,
        "table": {"headers": figure.data_table[0],
                  "rows": figure.data_table[1]} if figure.data_table else None,
    })
    STORE.save(project)
    return name




# --------------------------------------------------------- grammar and figures


@app.get("/api/projects/{project_id}/proof")
async def proof_project(project_id: str, url: str = "") -> dict[str, Any]:
    """Grammar-check every claim, keeping each issue tied to its claim.

    This endpoint is why `writing/proof.py` exists. It was written, tested and
    then never called from anywhere — an audit of this codebase found it imported
    by nothing, which is the quietest way for a feature to not exist.
    """
    project = _load(project_id)
    report = await proof_module.check_project(project, url=url)
    return {
        "available": report.available,
        "engine": report.engine,
        "note": report.note,
        "checked_words": report.checked_words,
        "by_category": report.by_category(),
        "issues": [
            {
                "message": issue.message, "context": issue.context,
                "offset": issue.offset, "length": issue.length,
                "replacements": issue.replacements, "rule": issue.rule,
                "category": issue.category, "claim_id": issue.claim_id,
                "section": issue.section,
            }
            for issue in report.issues
        ],
        "grammarly": proof_module.grammarly_report(),
    }


@app.get("/api/grammarly")
async def grammarly() -> dict[str, Any]:
    return proof_module.grammarly_report()


@app.post("/api/projects/{project_id}/figure")
async def build_figure(project_id: str,
                       payload: dict = Body(...)) -> dict[str, Any]:
    """Build one of the figure types the specification named.

    Forest plots, incidence curves and bar charts were implemented in
    `apa/figures.py` with a validated palette and greyscale-safe secondary
    encoding, and nothing in the application ever called them. Only the
    level-distribution chart had a route.
    """
    project = _load(project_id)
    out = SETTINGS.export_dir / project.project_id
    out.mkdir(parents=True, exist_ok=True)
    kind = str(payload.get("kind", "")).strip()
    title = str(payload.get("title", "") or "")
    caption = str(payload.get("caption", "") or "")

    try:
        if kind == "forest":
            estimates = [
                figures_module.EffectEstimate(
                    label=str(row.get("label", "")),
                    estimate=float(row.get("estimate")),
                    lower=float(row.get("lower", row.get("low"))),
                    upper=float(row.get("upper", row.get("high"))),
                    weight=float(row.get("weight", 0) or 0),
                    subgroup=str(row.get("subgroup", "") or ""),
                )
                for row in (payload.get("estimates") or [])
                if row.get("estimate") not in (None, "")
            ]
            if not estimates:
                raise HTTPException(400, "No effect estimates supplied.")
            figure = figures_module.forest_plot(
                estimates, path=out / "figure-forest.png", title=title,
                measure=str(payload.get("measure", "Odds ratio")))
        elif kind in ("line", "incidence"):
            # JSON gives lists where the signature wants (name, values) tuples.
            series = [(str(row[0]), [float(v) for v in row[1]])
                      for row in (payload.get("series") or []) if len(row) >= 2]
            figure = figures_module.line_figure(
                [str(x) for x in (payload.get("x_labels") or [])], series,
                path=out / "figure-line.png", title=title,
                x_label=str(payload.get("x_label", "")),
                y_label=str(payload.get("y_label", "")))
        elif kind == "bar":
            figure = figures_module.bar_figure(
                [str(x) for x in (payload.get("categories") or [])],
                [float(v) for v in (payload.get("values") or [])],
                path=out / "figure-bar.png", title=title,
                y_label=str(payload.get("y_label", "")))
        elif kind == "grouped_bar":
            series = [(str(row[0]), [float(v) for v in row[1]])
                      for row in (payload.get("series") or []) if len(row) >= 2]
            figure = figures_module.grouped_bar_figure(
                [str(x) for x in (payload.get("categories") or [])], series,
                path=out / "figure-grouped-bar.png", title=title,
                y_label=str(payload.get("y_label", "")))
        else:
            raise HTTPException(400, f"unknown figure kind {kind!r}")
    except HTTPException:
        raise
    except (TypeError, ValueError) as error:
        raise HTTPException(400, f"Could not build the figure: {error}")

    # Attach it so the exporter can place it in the paper as an APA figure.
    name = _attach_figure(project, figure, kind=kind, title=title,
                          caption=caption)

    return {
        "path": name, "note": figure.note,
        "table": {"headers": figure.data_table[0], "rows": figure.data_table[1]}
                 if figure.data_table else None,
        "attached": True,
        "placement": ("Attached to the project. The exporter places it in the "
                      "paper as a numbered APA figure with its note beneath, and "
                      "on a slide in the deck."),
    }


@app.get("/api/projects/{project_id}/figures")
async def list_figures(project_id: str) -> dict[str, Any]:
    project = _load(project_id)
    return {"figures": (getattr(project, "notes", None) or {}).get("figures", [])}


# ------------------------------------------------- question framing and search


@app.get("/api/frameworks")
async def frameworks() -> dict[str, Any]:
    """PICO(T) and SPIDER slots, with the guidance for each."""
    return {"frameworks": pico_module.frameworks()}


@app.post("/api/pico/expand")
async def expand_term(term: str = Body(..., embed=True)) -> dict[str, Any]:
    """Synonyms and MeSH headings for one concept term."""
    found = pico_module.expand(term)
    return {
        "term": term,
        **found,
        "note": ("Expansions come from a small built-in thesaurus of nursing and "
                 "health-services concepts. Anything not covered is yours to add "
                 "— a generated synonym you cannot source is a liability in a "
                 "methods section."),
    }


@app.post("/api/pico/translate")
async def translate_question(payload: dict = Body(...)) -> dict[str, Any]:
    """Turn a framed question into a search string for every database."""
    question = pico_module.build(payload)
    return pico_module.strategy_report(question)


@app.post("/api/projects/{project_id}/question")
async def save_question(project_id: str,
                        payload: dict = Body(...)) -> dict[str, Any]:
    """Store the framed question on the project so the audit document can report
    the search strategy — PRISMA item 7 asks for it and it cannot be
    reconstructed after the fact."""
    project = _load(project_id)
    question = pico_module.build(payload)
    project.notes = getattr(project, "notes", {}) or {}
    if not isinstance(project.notes, dict):
        project.notes = {}
    project.notes["question"] = pico_module.strategy_report(question)
    STORE.save(project)
    return {"project": _project_payload(project),
            "strategy": project.notes["question"]}


# ------------------------------------------------------------------- PRISMA


@app.post("/api/projects/{project_id}/prisma")
async def prisma_diagram(project_id: str,
                         payload: dict = Body(default_factory=dict)) -> dict[str, Any]:
    """Validate the counts and draw the 2020 flow diagram."""
    project = _load(project_id)
    counts = prisma_module.from_project(project, payload.get("counts") or {})
    result = prisma_module.payload(counts)
    if payload.get("render", True):
        out = SETTINGS.export_dir / project.project_id
        path = prisma_module.render(
            counts, out / "figure-prisma.png",
            title=str(payload.get("title", "") or ""))
        result["path"] = path.name
    return result


# --------------------------------------------------- statistics translation


@app.post("/api/statistics/translate")
async def translate_statistics(text: str = Body(""),
                               variables: str = Body(""),
                               direction: str = Body("")) -> dict[str, Any]:
    """SPSS or R output into APA 7 results prose."""
    return statistics_module.translate(text, variables=variables,
                                       direction=direction)


@app.post("/api/statistics/manual")
async def manual_statistics(kind: str = Body(...),
                            values: dict = Body(default_factory=dict),
                            variables: str = Body(""),
                            direction: str = Body("")) -> dict[str, Any]:
    """Render from values entered by hand, for output the parser cannot read."""
    return statistics_module.manual(kind, values, variables=variables,
                                    direction=direction)


@app.get("/api/statistics/supported")
async def supported_statistics() -> dict[str, Any]:
    return {"tests": statistics_module.supported()}


# ------------------------------------------------------------- the rubric


@app.post("/api/rubric/extract")
async def extract_rubric(text: str = Body(""),
                         source_name: str = Body("")) -> dict[str, Any]:
    """Pull checkable requirements out of a rubric or syllabus."""
    return rubric_module.extract(text, source_name=source_name)


@app.post("/api/projects/{project_id}/rubric")
async def save_rubric(project_id: str,
                      payload: dict = Body(...)) -> dict[str, Any]:
    """Attach an extracted rubric to the project so the simulator can run."""
    project = _load(project_id)
    if not isinstance(getattr(project, "notes", None), dict):
        project.notes = {}
    project.notes["rubric"] = {
        "source_name": str(payload.get("source_name", "") or ""),
        "requirements": payload.get("requirements") or [],
    }
    STORE.save(project)
    return {"project": _project_payload(project),
            "rubric": project.notes["rubric"]}


@app.get("/api/projects/{project_id}/compliance")
async def compliance(project_id: str) -> dict[str, Any]:
    """Check the current draft against the attached rubric."""
    project = _load(project_id)
    stored = (getattr(project, "notes", None) or {}).get("rubric") or {}
    requirements = stored.get("requirements") or []
    facts = simulator_module.facts_from_project(project)
    if not requirements:
        return {
            "results": [], "counts": {}, "headline": "No rubric attached.",
            "outstanding": [], "unscored": [],
            "no_score_note": ("Paste your rubric or assignment brief on the "
                              "Compliance screen and the checks appear here."),
        }
    return simulator_module.run(requirements, facts)


# ---------------------------------------------------------- journal guidelines


@app.get("/api/journals")
async def journal_catalogue() -> dict[str, Any]:
    return {"journals": journals_module.catalogue(),
            "verify": journals_module.VERIFY_NOTE}


@app.post("/api/journals/parse")
async def parse_journal(text: str = Body(""),
                        name: str = Body("")) -> dict[str, Any]:
    """Read pasted author guidelines into a profile."""
    return journals_module.parse(text, name=name).as_dict()


@app.post("/api/projects/{project_id}/journal-check")
async def journal_check(project_id: str,
                        journal: str = Body(""),
                        guidelines: str = Body(""),
                        abstract: str = Body("")) -> dict[str, Any]:
    """Compare the manuscript against a journal profile."""
    project = _load(project_id)
    profile = (journals_module.get(journal) if journal
               else journals_module.parse(guidelines, name="Pasted guidelines"))
    if profile is None:
        raise HTTPException(404, f"no journal profile {journal!r}")
    facts = simulator_module.facts_from_project(project)
    title_page = getattr(project, "title_page", None)
    return journals_module.check(
        profile,
        body_words=facts.body_words,
        abstract=abstract or str(getattr(project, "abstract", "") or ""),
        reference_count=facts.source_count,
        title=str(getattr(title_page, "title", "") or "") if title_page else "",
        keywords=list(getattr(project, "keywords", None) or []),
    )


# ----------------------------------------------------------------- full text


@app.get("/api/fulltext/status")
async def fulltext_status() -> dict[str, Any]:
    available, reason = fulltext.pypdf_probe()
    return {
        "pdf": available,
        "note": (
            "PDFs can be read." if available else
            f"{reason} PDFs cannot be parsed here. Paste the text instead — "
            f"everything downstream works the same way. To turn PDF reading "
            f"on: pip install pypdf."
        ),
        "limits": [
            "A scanned PDF has no text layer. It needs OCR first; nothing here "
            "can read an image of a page.",
            "Two-column layouts sometimes interleave when extracted. Check a "
            "passage before you cite it — the anchor tells you where to look.",
            "Extraction reads patterns, not meaning. Every value it returns "
            "carries the sentence it came from so you can check it in seconds.",
        ],
    }


def _fulltext_summary(entry: dict[str, Any]) -> dict[str, Any]:
    passages = entry.get("passages") or []
    return {
        "work_key": entry.get("work_key", ""),
        "label": entry.get("label", ""),
        "pages": entry.get("pages", 0),
        "passages": len(passages),
        "source": entry.get("source", ""),
        "ingested_at": entry.get("ingested_at", ""),
        "words": sum(len(str(p.get("text", "")).split()) for p in passages),
    }


@app.get("/api/projects/{project_id}/fulltext")
async def list_fulltext(project_id: str) -> dict[str, Any]:
    project = _load(project_id)
    store = STORE.load_fulltext(project.project_id)
    ingested = [_fulltext_summary(entry) for entry in store.values()]
    ingested.sort(key=lambda row: row["work_key"])
    return {
        "ingested": ingested,
        "missing": [{"key": w.key, "label": w.short_label()}
                    for w in project.included_works() if w.key not in store],
        "pdf": fulltext.pypdf_available(),
    }


@app.post("/api/projects/{project_id}/fulltext")
async def ingest_fulltext(
    project_id: str,
    work_key: str = Form(...),
    file: UploadFile | None = File(None),
    text: str = Form(""),
) -> dict[str, Any]:
    """Read a source's full text into anchored paragraphs.

    A PDF or pasted text, both ending in the same structure: a list of passages
    each carrying its page and paragraph number. That anchor is what lets a
    claim point back at the exact paragraph it came from, which is the whole
    reason this step exists.

    The file is read into memory and discarded. Nothing is copied into the data
    directory — a published article on disk in two places is a licensing
    problem, and the passages are all that is needed afterwards.
    """
    project = _load(project_id)
    work = project.work(work_key)
    if work is None:
        raise HTTPException(404, f"no source with key {work_key}")

    if file is not None and file.filename:
        body = await file.read()
        if len(body) > 40 * 1024 * 1024:
            raise HTTPException(413, "That file is larger than 40 MB.")
        if file.filename.lower().endswith(".pdf"):
            import tempfile as _tempfile
            handle, temporary = _tempfile.mkstemp(suffix=".pdf")
            try:
                with os.fdopen(handle, "wb") as stream:
                    stream.write(body)
                result = fulltext.read_pdf(Path(temporary), work_key=work_key)
            finally:
                Path(temporary).unlink(missing_ok=True)
            source = f"PDF: {file.filename}"
        else:
            result = fulltext.read_text(body.decode("utf-8", "replace"),
                                        work_key=work_key)
            source = f"Text file: {file.filename}"
    elif text.strip():
        result = fulltext.read_text(text, work_key=work_key)
        source = "Pasted text"
    else:
        raise HTTPException(400, "Upload a PDF or paste the text.")

    if not result["passages"]:
        return {"ok": False, "note": result["note"], "passages": 0}

    store = STORE.load_fulltext(project.project_id)
    store[work_key] = {
        "work_key": work_key,
        "label": work.short_label(),
        "pages": result["pages"],
        "passages": result["passages"],
        "source": source,
        "ingested_at": storage._now(),
    }
    STORE.save_fulltext(project.project_id, store)
    return {"ok": True, "note": result["note"],
            "summary": _fulltext_summary(store[work_key]),
            "sections": sorted({p.get("section", "") for p in result["passages"]
                                if p.get("section")})}


@app.delete("/api/projects/{project_id}/fulltext/{work_key}")
async def drop_fulltext(project_id: str, work_key: str) -> dict[str, Any]:
    project = _load(project_id)
    store = STORE.load_fulltext(project.project_id)
    removed = store.pop(work_key, None) is not None
    if removed:
        STORE.save_fulltext(project.project_id, store)
    return {"removed": removed}


@app.post("/api/projects/{project_id}/fulltext/{work_key}/extract")
async def extract_fulltext(project_id: str, work_key: str,
                           apply: bool = Body(False, embed=True)) -> dict[str, Any]:
    """Read evidence-matrix fields out of an ingested source.

    With `apply`, the findings are written into the extraction row — but only
    into cells that are still empty. Anything typed by hand wins, because a
    pattern match is a first draft of a matrix row and a human reading is the
    final one.
    """
    project = _load(project_id)
    if project.work(work_key) is None:
        raise HTTPException(404, f"no source with key {work_key}")
    entry = STORE.load_fulltext(project.project_id).get(work_key)
    if entry is None:
        raise HTTPException(404, "No full text has been ingested for that "
                                 "source yet.")
    passages = fulltext.passages_from_dicts(entry.get("passages") or [])
    result = fulltext.extract(passages)

    if apply:
        existing = next((e for e in project.extractions
                         if e.work_key == work_key), None)
        if existing is None:
            existing = Extraction(work_key=work_key)
            project.extractions.append(existing)
        fields = result["fields"]

        def first(name: str) -> str:
            rows = fields.get(name) or []
            return str(rows[0]["value"]) if rows else ""

        def joined(name: str, limit: int = 6) -> str:
            rows = fields.get(name) or []
            seen: list[str] = []
            for row in rows:
                value = str(row["value"])
                if value not in seen:
                    seen.append(value)
            return "; ".join(seen[:limit])

        suggested = result.get("suggested_sample_size")
        candidates = {
            "design": first("design"),
            "sample_size": str(suggested["value"]) if suggested else "",
            "statistics": joined("statistics", 8),
            "limitations": first("limitations"),
        }
        filled: list[str] = []
        for name, value in candidates.items():
            if value and not getattr(existing, name, ""):
                setattr(existing, name, value)
                filled.append(name.replace("_", " "))
        STORE.save(project)
        result["applied"] = filled
        result["applied_note"] = (
            "Filled: " + ", ".join(filled) + ". Only empty cells were written "
            "to — anything already typed was left alone. Check each one against "
            "the sentence it came from before you rely on it."
            if filled else
            "Nothing was written: every cell this could fill already had "
            "something in it."
        )

    result["work_key"] = work_key
    result["anchor_source"] = entry.get("source", "")
    return result


@app.post("/api/projects/{project_id}/locate")
async def locate_sentence(project_id: str,
                          sentence: str = Body(..., embed=True),
                          work_key: str = Body("", embed=True)) -> dict[str, Any]:
    """Find which ingested paragraph a sentence came from."""
    project = _load(project_id)
    store = STORE.load_fulltext(project.project_id)
    entries = ([store[work_key]] if work_key and work_key in store
               else list(store.values()))
    passages: list[Any] = []
    for entry in entries:
        passages.extend(fulltext.passages_from_dicts(entry.get("passages") or []))
    matches = fulltext.locate(sentence, passages)
    labels = {entry["work_key"]: entry.get("label", entry["work_key"])
              for entry in store.values()}
    for match in matches:
        match["label"] = labels.get(match.get("work_key", ""), "")
    return {
        "matches": matches,
        "searched": len(passages),
        "note": ("Nothing in the ingested full text matches this sentence "
                 "closely enough to anchor it."
                 if not matches and passages else
                 "No full text has been ingested yet, so there was nothing to "
                 "search." if not passages else ""),
    }


@app.get("/api/projects/{project_id}/grounding")
async def grounding_report(project_id: str) -> dict[str, Any]:
    """Anchor every claim to the paragraph of the source it cites.

    This is the check that makes the claim ledger mean something. A claim whose
    cited source does not contain it is either attributed to the wrong work or
    was never in any work — and both look identical in a finished draft.
    """
    project = _load(project_id)
    store = STORE.load_fulltext(project.project_id)
    passages: list[Any] = []
    for entry in store.values():
        passages.extend(fulltext.passages_from_dicts(entry.get("passages") or []))
    claims = [storage._to_jsonable(c) for c in project.claims]
    report = fulltext.ground(claims, passages)
    labels = {entry["work_key"]: entry.get("label", entry["work_key"])
              for entry in store.values()}
    for row in report["claims"]:
        for match in row["matches"]:
            match["label"] = labels.get(match.get("work_key", ""), "")
    report["ingested"] = sorted(store.keys())
    report["cited"] = sorted({k for c in project.claims for k in c.work_keys})
    report["not_ingested"] = sorted(set(report["cited"]) - set(report["ingested"]))
    return report


# ------------------------------------------------------------------- helpers


def _load(project_id: str) -> Project:
    try:
        return STORE.load(project_id)
    except FileNotFoundError as error:
        raise HTTPException(404, str(error)) from error
    except ValueError as error:
        raise HTTPException(400, str(error)) from error


def _safe(project_id: str) -> str:
    import re
    value = re.sub(r"[^A-Za-z0-9._-]", "", project_id)
    if not value or value in (".", ".."):
        raise HTTPException(400, "Invalid project id.")
    return value


def _group_abbreviations(project: Project) -> dict[str, str]:
    """Build abbreviations for the agency authors APA expects to be shortened.

    Only well-known agencies are abbreviated. Inventing an acronym for an
    unfamiliar organisation would produce a citation a reader cannot resolve.
    """
    known = {
        "Centers for Disease Control and Prevention": "CDC",
        "World Health Organization": "WHO",
        "National Institutes of Health": "NIH",
        "Agency for Healthcare Research and Quality": "AHRQ",
        "U.S. Preventive Services Task Force": "USPSTF",
        "American Nurses Association": "ANA",
        "Institute of Medicine": "IOM",
        "National Academies of Sciences, Engineering, and Medicine": "NASEM",
        "Office of Disease Prevention and Health Promotion": "ODPHP",
        "Joint Commission": "TJC",
        "American Association of Critical-Care Nurses": "AACN",
        "Joanna Briggs Institute": "JBI",
    }
    present = {a.family for w in project.works for a in w.authors if a.is_group}
    return {name: abbrev for name, abbrev in known.items() if name in present}


def _project_payload(project: Project) -> dict[str, Any]:
    payload = storage._to_jsonable(project)
    counts = levels.summarise(project.included_works())
    payload["_derived"] = {
        "sources_total": len(project.works),
        "sources_included": len(project.included_works()),
        "sources_cited": len(project.cited_works()),
        "level_counts": counts,
        "word_count": assemble.word_count(project),
        "section_words": assemble.section_word_counts(project),
        "unscreened": sum(1 for w in project.works if w.included is None),
        "retracted": sum(1 for w in project.works if w.retracted),
        "appraised": len(project.appraisals),
        "extracted": len(project.extractions),
        "suggested_keywords": assemble.suggest_keywords(project),
    }
    return payload


def _claim_port(host: str, preferred: int, *, tries: int = 12):
    """Take the port before anything is printed, and return the live socket.

    The banner used to print first and uvicorn bound afterwards. When the port
    was already taken — a second `run.sh`, or an earlier run still going in
    another terminal — the user got a perfectly healthy-looking URL with a bind
    error underneath it, opened the URL, and the browser said the page could
    not be reached. A startup message that advertises an address nothing is
    listening on is worse than a crash.

    Binding here and handing the socket to uvicorn also removes the race a
    check-then-bind would leave: the port cannot be taken between the test and
    the use, because they are the same operation.
    """
    import socket

    first_error = None
    for offset in range(tries):
        port = preferred + offset
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Deliberately no SO_REUSEADDR: the whole point is to fail when someone
        # else holds the port, and on some platforms that option would let this
        # bind succeed alongside them.
        try:
            sock.bind((host, port))
            sock.listen(128)
            sock.set_inheritable(True)
            return sock, port, (first_error if offset else None)
        except OSError as error:
            sock.close()
            if first_error is None:
                first_error = error
            continue
    raise SystemExit(
        f"\n  Could not start: ports {preferred}–{preferred + tries - 1} on "
        f"{host} are all in use.\n"
        f"  ({first_error})\n\n"
        f"  The usual cause is that this is already running in another terminal "
        f"or tab —\n"
        f"  look for one showing 'Koch Research Suite' and use the URL it "
        f"printed, or stop\n"
        f"  it with Ctrl-C and start again. To pick a port yourself, set "
        f"RESEARCH_SUITE_PORT.\n"
    )


def run() -> None:
    import uvicorn

    # The port is claimed before the banner is composed, so the URL in the
    # banner is guaranteed to be one something is actually listening on.
    preferred = SETTINGS.port
    sock, port, moved = _claim_port(SETTINGS.host, preferred)
    SETTINGS.port = port
    SECURITY.rebind(port)

    warnings = [w for w in [settings_module.contact_email_warning(SETTINGS)] if w]
    if moved is not None:
        warnings.insert(0, (
            f"Port {preferred} is in use, so this run is on {port} instead. "
            f"Something else is already listening on {preferred} — most often "
            f"an earlier run of this app in another terminal. Use the URL "
            f"above; a tab open on {preferred} is a different, older run with "
            f"a different token."
        ))
    if not SETTINGS.key("anthropic"):
        warnings.append(
            "No Anthropic API key: drafting is unavailable. Retrieval, "
            "appraisal, matrices, both documents and the slide deck all work "
            "without one."
        )
    print(security.startup_banner(SECURITY, warnings), flush=True)

    config = uvicorn.Config(app, log_level="warning")
    uvicorn.Server(config).run(sockets=[sock])


if __name__ == "__main__":
    run()
