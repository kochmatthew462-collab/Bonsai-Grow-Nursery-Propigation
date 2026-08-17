"""
The charting tab's HTTP API.

Two conventions run through all of it.

**Preview and save share one code path.** `/preview` builds the candidate entry,
composes the note, runs every interlock and returns the gate — without writing
anything. `/entries` does exactly the same and then enforces the gate before
saving. The front end greys out its Save button from the preview's `blocked` flag,
but that is a courtesy: the check that counts happens on the server, in the same
function, so a disabled button and a refused request can never disagree.

**Documentation time is never accepted from the client.** `_entry_from_payload`
reads `event_at` from the request and then calls `Entry.stamp()`, which sets
`documented_at` from the server clock. There is no field, no header and no query
parameter that moves it. This is the one thing in the module that has no override.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import FileResponse

from . import (
    disclosure, export as export_module, interlocks, language, narrative, phi,
    scales, specialty, store as store_module, systems,
)
from .models import (
    Encounter, Entry, EntryKind, Intervention, Medication, ProviderNotification,
    ScaleResult, Setting, Severity, ShiftContext, SystemFinding, Vitals, Wound,
    iso, now_utc,
)

router = APIRouter(prefix="/api/charting", tags=["charting"])

# Set by `configure()` at application start-up so this module owns no global state
# of its own beyond what the app hands it.
_STORE: store_module.EncounterStore | None = None
_EXPORT_DIR: Path | None = None


def configure(store: store_module.EncounterStore, export_dir: Path) -> None:
    global _STORE, _EXPORT_DIR
    _STORE = store
    _EXPORT_DIR = export_dir


def _store() -> store_module.EncounterStore:
    if _STORE is None:
        raise HTTPException(500, "charting storage is not configured")
    return _STORE


def _load(encounter_id: str) -> Encounter:
    try:
        return _store().load(encounter_id)
    except FileNotFoundError:
        raise HTTPException(404, f"no encounter {encounter_id!r}")
    except ValueError as error:
        raise HTTPException(400, str(error))


def _export_dir(encounter_id: str) -> Path:
    if _EXPORT_DIR is None:
        raise HTTPException(500, "charting exports are not configured")
    safe = "".join(c for c in encounter_id if c.isalnum() or c in "-_")
    if not safe:
        raise HTTPException(400, "unsafe encounter id")
    return _EXPORT_DIR / safe


# ------------------------------------------------------------------- reference


@router.get("/reference")
async def reference() -> dict[str, Any]:
    """Everything static the front end needs, in one request.

    One call rather than a dozen because all of it is constant for the life of the
    process, and a charting screen that has to make eleven round trips before it
    can render is a charting screen nobody opens twice.
    """
    return {
        "disclosure": disclosure.banner(),
        "cannot_do": disclosure.what_it_cannot_do(),
        "settings": [{"value": s.value, "label": s.label} for s in Setting],
        "entry_kinds": [{"value": k.value, "label": k.label} for k in EntryKind],
        "systems": systems.catalogue(),
        "scales": scales.catalogue(),
        "scale_licensing": scales.LICENSING,
        "esi_vital_limits": scales.esi_vital_limits(),
        "macros": narrative.macro_catalogue(),
        "modules": specialty.catalogue(),
        "bundles": specialty.bundle_catalogue(),
        "handoff_routes": narrative.handoff_routes(),
        "language_rules": language.rule_table(),
        "language_categories": language.CATEGORIES,
        "critical_thresholds": interlocks.thresholds_payload(),
        "escalation_ladder": [
            {"rung": name, "why": why} for name, why in interlocks.ESCALATION_LADDER
        ],
        "loop_rules": [
            {"key": key, "minutes": minutes, "what": what}
            for key, _, minutes, what in interlocks.LOOP_RULES
        ],
        "phi": phi.report(),
        "non_overridable": sorted(interlocks.NON_OVERRIDABLE),
    }


@router.get("/handoff/{route_name}")
async def handoff_fields(route_name: str) -> dict[str, Any]:
    try:
        return narrative.handoff_template(route_name)
    except ValueError as error:
        raise HTTPException(404, str(error))


# ------------------------------------------------------------------ encounters


@router.get("/encounters")
async def list_encounters() -> dict[str, Any]:
    return {"encounters": _store().list_encounters()}


@router.post("/encounters")
async def create_encounter(
    local_label: str = Body(...),
    setting: str = Body("med_surg"),
    initials: str = Body(""),
    age_band: str = Body("adult"),
    author_initials: str = Body(""),
) -> dict[str, Any]:
    if not local_label.strip():
        raise HTTPException(400, "a bed or room label is required")
    # Guard the label itself: it is the one identifier-shaped field on the record,
    # so a name typed here would defeat the whole no-PHI design.
    leaks = phi.scan(local_label, field_path="local_label")
    if leaks:
        raise HTTPException(400, {
            "detail": "That label looks like it contains patient information.",
            "flags": [f.as_dict() for f in leaks],
            "advice": ("Use a bed or room — \"Bed 12\", \"Room 415-A\", \"Trauma "
                       "2\". There is no field in this tool for a patient's "
                       "identity, by design."),
        })
    encounter = _store().new_encounter(
        local_label, setting=setting, initials=initials, age_band=age_band,
        author_initials=author_initials)
    return {"encounter": _payload(encounter)}


@router.get("/encounters/{encounter_id}")
async def get_encounter(encounter_id: str) -> dict[str, Any]:
    return {"encounter": _payload(_load(encounter_id))}


@router.delete("/encounters/{encounter_id}")
async def delete_encounter(encounter_id: str) -> dict[str, bool]:
    return {"deleted": _store().delete(encounter_id)}


@router.post("/purge")
async def purge() -> dict[str, Any]:
    removed = _store().purge_all()
    return {
        "removed": removed,
        "message": (f"Deleted {removed} encounter file"
                    f"{'s' if removed != 1 else ''}. The correct end of a shift is "
                    f"an empty data directory — nothing here is the legal record, "
                    f"so nothing here needs to survive you going home."),
    }


@router.post("/encounters/{encounter_id}/details")
async def update_details(encounter_id: str,
                         payload: dict = Body(...)) -> dict[str, Any]:
    """Update the encounter-level facts: code status, allergies, weight, devices."""
    encounter = _load(encounter_id)
    author = str(payload.get("author_initials", ""))

    text_fields = ("code_status", "advance_directive", "allergies", "isolation",
                   "diagnosis_summary", "language", "interpreter_id", "age_band",
                   "baseline_mental_status", "wdl_definition", "initials")
    changed: list[str] = []
    for name in text_fields:
        if name in payload:
            value = str(payload[name] or "").strip()
            if getattr(encounter, name) != value:
                setattr(encounter, name, value)
                changed.append(name)

    if "interpreter_used" in payload:
        encounter.interpreter_used = bool(payload["interpreter_used"])
        changed.append("interpreter_used")

    for name in ("weight_kg", "height_cm"):
        if name in payload:
            raw = payload[name]
            value = None
            if raw not in (None, ""):
                try:
                    value = float(raw)
                except (TypeError, ValueError):
                    raise HTTPException(400, f"{name} must be a number")
                if value <= 0:
                    raise HTTPException(400, f"{name} must be greater than zero")
            if getattr(encounter, name) != value:
                setattr(encounter, name, value)
                changed.append(name)
            if name == "weight_kg" and value is not None:
                encounter.weight_measured_at = (
                    str(payload.get("weight_measured_at", "")).strip()
                    or iso(now_utc()))

    if "setting" in payload:
        try:
            encounter.setting = Setting(str(payload["setting"]))
            changed.append("setting")
        except ValueError:
            raise HTTPException(400, f"unknown setting {payload['setting']!r}")

    if "lines_drains_airways" in payload:
        devices = payload["lines_drains_airways"] or []
        if not isinstance(devices, list):
            raise HTTPException(400, "lines_drains_airways must be a list")
        encounter.lines_drains_airways = [
            {str(k): v for k, v in (d or {}).items()} for d in devices
        ]
        changed.append("lines_drains_airways")

    if "context" in payload:
        context = payload["context"] or {}
        names = {f for f in ShiftContext.__dataclass_fields__}
        for key, value in context.items():
            if key not in names:
                continue
            if key == "patient_count":
                try:
                    encounter.context.patient_count = (
                        int(value) if value not in (None, "") else None)
                except (TypeError, ValueError):
                    raise HTTPException(400, "patient_count must be a whole number")
            else:
                setattr(encounter.context, key, str(value or "").strip())
        changed.append("context")

    if changed:
        encounter.record("details_updated", encounter.encounter_id,
                         ", ".join(sorted(set(changed))), author)
    _store().save(encounter)
    return {"encounter": _payload(encounter), "changed": sorted(set(changed))}


# ----------------------------------------------------------------------- notes


@router.post("/encounters/{encounter_id}/preview")
async def preview(encounter_id: str, payload: dict = Body(...)) -> dict[str, Any]:
    """Compose and check without saving. Drives the Save button's enabled state."""
    encounter = _load(encounter_id)
    entry, composed = _entry_from_payload(payload, encounter)
    gate = interlocks.evaluate(
        encounter, entry,
        override_reason=str(payload.get("override_reason", "")))
    identifiers = phi.scan_many({
        "subjective": entry.subjective, "objective": entry.objective,
        "assessment": entry.assessment, "plan": entry.plan,
        "labs": entry.labs, "pending": entry.pending,
        "narrative": entry.narrative,
    })
    return {
        "narrative": composed,
        "gate": gate.as_dict(),
        "phi": [f.as_dict() for f in identifiers],
        "quote_suggestions": [
            f.as_dict() for f in narrative_quote_hints(entry)
        ],
        "late_entry": entry.late_entry,
        "late_by_minutes": entry.late_by_minutes,
        "documented_at": entry.documented_at,
    }


def narrative_quote_hints(entry: Entry) -> list[Any]:
    hints: list[Any] = []
    for name, text in (("subjective", entry.subjective),
                       ("narrative", entry.narrative)):
        for flag in language.suggest_quotes(text or ""):
            flag.field_path = name
            hints.append(flag)
    return hints


@router.post("/encounters/{encounter_id}/entries")
async def save_entry(encounter_id: str, payload: dict = Body(...)) -> dict[str, Any]:
    """Save a note, enforcing the gate.

    The gate is re-evaluated here rather than trusted from the preview, because a
    client that skipped the preview, or sent a stale one, must not be able to save
    a blocked note. Same function, same rules.
    """
    encounter = _load(encounter_id)
    entry, composed = _entry_from_payload(payload, encounter)
    override = str(payload.get("override_reason", "")).strip()
    gate = interlocks.evaluate(encounter, entry, override_reason=override)

    if gate.blocked:
        raise HTTPException(422, {
            "detail": "This note cannot be saved yet.",
            "gate": gate.as_dict(),
        })

    entry.narrative = composed
    entry.flags = [f.as_dict() for f in gate.flags]
    acknowledged = payload.get("acknowledged_warnings") or []
    entry.acknowledged_warnings = [str(code) for code in acknowledged]

    encounter.entries.append(entry)
    detail = entry.kind.label
    if entry.late_entry:
        detail += f" (late entry, {entry.late_by_minutes} min)"
    if override:
        detail += f" (override: {override})"
    encounter.record("entry_created", entry.entry_id, detail, entry.author_initials)

    added = interlocks.register_loops(encounter, entry)
    for loop in added:
        encounter.record("reassessment_opened", loop.reassessment_id,
                         f"{loop.trigger}, due {loop.due_at}", entry.author_initials)

    _store().save(encounter)
    return {
        "encounter": _payload(encounter),
        "entry_id": entry.entry_id,
        "loops_opened": [
            {"reassessment_id": l.reassessment_id, "trigger": l.trigger,
             "due_at": l.due_at} for l in added
        ],
        "gate": gate.as_dict(),
    }


@router.post("/encounters/{encounter_id}/entries/{entry_id}/revise")
async def revise_entry(encounter_id: str, entry_id: str,
                       new_text: str = Body(...),
                       reason: str = Body(...),
                       author_initials: str = Body("")) -> dict[str, Any]:
    """Append a correction. The original text is kept and struck through on export."""
    encounter = _load(encounter_id)
    entry = encounter.entry(entry_id)
    if not entry:
        raise HTTPException(404, f"no entry {entry_id!r}")
    if not new_text.strip():
        raise HTTPException(400, "the corrected text cannot be empty")

    blocking = language.blocking(language.scan(new_text, field_path="narrative"))
    if blocking:
        raise HTTPException(422, {
            "detail": "The corrected text contains something that must not appear "
                      "in a clinical note.",
            "flags": [f.as_dict() for f in blocking],
        })

    try:
        revision = entry.revise(new_text, reason, author_initials)
    except ValueError as error:
        raise HTTPException(400, str(error))

    encounter.record("entry_revised", entry_id, revision.reason,
                     author_initials or entry.author_initials)
    _store().save(encounter)
    return {"encounter": _payload(encounter), "revision_id": revision.revision_id}


@router.post("/encounters/{encounter_id}/entries/{entry_id}/transcribed")
async def mark_transcribed(encounter_id: str, entry_id: str,
                           note: str = Body(""),
                           author_initials: str = Body(""),
                           undo: bool = Body(False)) -> dict[str, Any]:
    """Record that a note has been entered into the EHR — or undo that."""
    encounter = _load(encounter_id)
    entry = encounter.entry(entry_id)
    if not entry:
        raise HTTPException(404, f"no entry {entry_id!r}")
    if undo:
        entry.transcribed_at = ""
        entry.transcribed_note = ""
        encounter.record("transcription_cleared", entry_id, "", author_initials)
    else:
        entry.transcribed_at = iso(now_utc())
        entry.transcribed_note = note.strip()
        encounter.record("transcribed", entry_id, note.strip()[:120],
                         author_initials)
    _store().save(encounter)
    return {"encounter": _payload(encounter)}


@router.post("/encounters/{encounter_id}/loops/{reassessment_id}")
async def close_loop(encounter_id: str, reassessment_id: str,
                     finding: str = Body(""),
                     not_done_reason: str = Body(""),
                     author_initials: str = Body("")) -> dict[str, Any]:
    encounter = _load(encounter_id)
    if not finding.strip() and not not_done_reason.strip():
        raise HTTPException(400, "record the finding, or why it was not done")
    loop = interlocks.satisfy_loop(
        encounter, reassessment_id, finding=finding,
        not_done_reason=not_done_reason)
    if not loop:
        raise HTTPException(404, f"no reassessment {reassessment_id!r}")
    encounter.record(
        "reassessment_closed" if loop.satisfied else "reassessment_not_done",
        reassessment_id, (loop.finding or loop.not_done_reason)[:120],
        author_initials)
    _store().save(encounter)
    return {"encounter": _payload(encounter)}


# -------------------------------------------------------------------- utilities


@router.post("/score")
async def score(scale_id: str = Body(...),
                responses: dict = Body(default_factory=dict)) -> dict[str, Any]:
    scale = scales.get(scale_id)
    if not scale:
        raise HTTPException(404, f"no scale {scale_id!r}")
    result = scale.evaluate(responses or {})
    return {
        "result": {
            "result_id": result.result_id,
            "scale_id": result.scale_id,
            "scale_name": result.scale_name,
            "score": result.score,
            "subscores": result.subscores,
            "band": result.band,
            "band_detail": result.band_detail,
            "narrative": result.narrative,
            "citation": result.citation,
            "incomplete": result.incomplete,
            "responses": result.responses,
            "scored_at": result.scored_at,
        },
        "note": scale.note,
    }


@router.post("/scale-prefill")
async def scale_prefill(scale_id: str = Body(...),
                        vitals: dict = Body(default_factory=dict)) -> dict[str, Any]:
    """Suggest option keys a recorded vital sign already answers.

    Suggestions only, and only for the aggregate warning scores where the mapping
    from a number to a band is arithmetic. Nothing here scores on the nurse's
    behalf, and no scale requiring you to look at the patient is prefilled.
    """
    return {
        "prefill": scales.prefill_from_vitals(scale_id, _vitals(vitals)),
        "caveat": ("These are suggestions from the vital signs you recorded. Check "
                   "each one — the tool cannot see the patient."),
    }


@router.post("/esi-danger-zone")
async def esi_danger_zone(age_band: str = Body(...),
                          vitals: dict = Body(default_factory=dict)) -> dict[str, Any]:
    """Which published danger-zone thresholds the recorded vitals exceed.

    Informational. It reports the comparison and stops there: the triage nurse
    answers decision point D, because a triage level a tool assigned is not one
    anybody can defend.
    """
    return {
        "exceeded": scales.vitals_outside_esi_zone(_vitals(vitals), age_band),
        "limits": scales.esi_vital_limits(),
        "caveat": disclosure.NOT_CLINICAL_ADVICE,
    }


@router.post("/language-check")
async def language_check(text: str = Body(...),
                         field_path: str = Body("")) -> dict[str, Any]:
    """The objective-language filter, as a checker any field can call.

    This is the spell-check-shaped endpoint: offsets and lengths come back so the
    caller can underline in place, and quoted speech is exempt.
    """
    flags = language.scan(text, field_path=field_path)
    return {
        "flags": [f.as_dict() for f in flags],
        "quote_suggestions": [f.as_dict() for f in language.suggest_quotes(text)],
        "phi": [f.as_dict() for f in phi.scan(text, field_path=field_path)],
        "quoted_spans": language.quoted_spans(text),
        "blocked": bool(language.blocking(flags)),
        "words": len(text.split()),
    }


@router.post("/phi-redact")
# `embed=True` because this is the only body field: without it FastAPI expects a
# bare JSON string rather than {"text": "…"}, which is not what any caller sends.
async def phi_redact(text: str = Body(..., embed=True)) -> dict[str, Any]:
    cleaned, count = phi.redact(text)
    return {"text": cleaned, "redacted": count}


@router.post("/macro")
async def render_macro(macro_id: str = Body(...),
                       values: dict = Body(default_factory=dict)) -> dict[str, Any]:
    try:
        text = narrative.render_macro(macro_id, values or {})
    except ValueError as error:
        raise HTTPException(404, str(error))
    flags = language.scan(text, field_path="macro")
    return {
        "text": text,
        "missing_required": narrative.missing_macro_fields(macro_id, values or {}),
        "flags": [f.as_dict() for f in flags],
        "blocked": bool(language.blocking(flags)),
    }


@router.post("/bundle")
async def bundle(bundle_id: str = Body(...),
                 values: dict = Body(default_factory=dict)) -> dict[str, Any]:
    try:
        status = specialty.bundle_status(bundle_id, values or {})
        text = specialty.render_bundle(bundle_id, values or {})
    except ValueError as error:
        raise HTTPException(404, str(error))
    return {"status": status, "text": text}


@router.post("/encounters/{encounter_id}/handoff")
async def build_handoff(encounter_id: str,
                        route_name: str = Body(...),
                        values: dict = Body(default_factory=dict)) -> dict[str, Any]:
    encounter = _load(encounter_id)
    try:
        text = narrative.render_handoff(route_name, values or {}, encounter)
    except ValueError as error:
        raise HTTPException(404, str(error))
    return {
        "text": text,
        "open_loops": len(encounter.open_loops()),
        "untranscribed": len(encounter.untranscribed()),
    }


@router.get("/encounters/{encounter_id}/audit")
async def audit(encounter_id: str) -> dict[str, Any]:
    encounter = _load(encounter_id)
    verification = store_module.verify_chain(encounter)
    return {
        "verification": verification,
        "events": [
            {"at": e.at, "action": e.action, "target": e.target,
             "detail": e.detail, "author_initials": e.author_initials,
             "digest": e.digest[:16]}
            for e in encounter.audit
        ],
    }


# ----------------------------------------------------------------------- export


@router.post("/encounters/{encounter_id}/export")
async def export_encounter(encounter_id: str,
                           author: str = Body("", embed=True)) -> dict[str, Any]:
    encounter = _load(encounter_id)
    directory = _export_dir(encounter_id)
    produced = export_module.write_documents(encounter, directory, author=author)
    encounter.record("exported", encounter_id,
                     f"{len(produced)} documents", author)
    _store().save(encounter)
    untranscribed = encounter.untranscribed()
    return {
        "files": produced,
        "warning": (
            f"{len(untranscribed)} note{'s' if len(untranscribed) != 1 else ''} in "
            f"this export {'have' if len(untranscribed) != 1 else 'has'} not been "
            f"transcribed into the EHR. "
            f"{'They are' if len(untranscribed) != 1 else 'It is'} printed first "
            f"and marked. The exported file is not the legal record either — "
            f"transcribe {'them' if len(untranscribed) != 1 else 'it'}."
            if untranscribed else ""
        ),
    }


@router.get("/encounters/{encounter_id}/files")
async def list_files(encounter_id: str) -> dict[str, Any]:
    directory = _export_dir(encounter_id)
    if not directory.exists():
        return {"files": []}
    return {"files": sorted(
        [{"name": p.name, "bytes": p.stat().st_size} for p in directory.iterdir()
         if p.is_file()],
        key=lambda row: row["name"],
    )}


@router.get("/encounters/{encounter_id}/files/{name}")
async def download(encounter_id: str, name: str) -> FileResponse:
    directory = _export_dir(encounter_id)
    safe = Path(name).name       # no traversal: only the basename is honoured
    path = directory / safe
    if not path.exists() or not path.is_file():
        raise HTTPException(404, f"no file {safe!r}")
    return FileResponse(str(path), filename=safe)


# ---------------------------------------------------------------- construction


def _vitals(raw: dict[str, Any]) -> Vitals:
    vitals = Vitals()
    numeric = ("systolic", "diastolic", "map_mmhg", "heart_rate",
               "respiratory_rate", "spo2", "fio2", "temperature_c", "pain_score",
               "blood_glucose", "weight_kg", "height_cm", "end_tidal_co2")
    for name in numeric:
        value = (raw or {}).get(name)
        if value in (None, ""):
            continue
        try:
            setattr(vitals, name, float(value))
        except (TypeError, ValueError):
            raise HTTPException(400, f"{name} must be a number")
    for name in ("taken_at", "rhythm", "oxygen_delivery", "temperature_route",
                 "pain_scale"):
        value = (raw or {}).get(name)
        if value:
            setattr(vitals, name, str(value).strip())
    if not vitals.taken_at and not vitals.is_empty():
        # A vital sign with no time is a vital sign nobody can place. Default it to
        # now rather than leaving it blank, and let the nurse correct it — an
        # approximate time that is visible beats an absent one that is not.
        vitals.taken_at = iso(now_utc())
    return vitals


def _entry_from_payload(payload: dict[str, Any],
                        encounter: Encounter) -> tuple[Entry, str]:
    """Build a candidate entry from a request body and compose its narrative.

    `documented_at` is set by `stamp()` from the server clock and is never read
    from the payload. `event_at` is the nurse's; everything else is structure.
    """
    entry = Entry()

    try:
        entry.kind = EntryKind(str(payload.get("kind", "focused_update")))
    except ValueError:
        raise HTTPException(400, f"unknown entry kind {payload.get('kind')!r}")
    entry.setting = encounter.setting

    entry.author_initials = str(payload.get("author_initials", "")).strip()[:8]
    entry.author_credential = str(payload.get("author_credential", "")).strip()[:40]
    entry.event_at = str(payload.get("event_at", "")).strip()

    for name in ("subjective", "objective", "assessment", "plan", "labs",
                 "pending"):
        setattr(entry, name, str(payload.get(name, "") or "").strip())

    entry.vitals = _vitals(payload.get("vitals") or {})

    for raw in payload.get("systems") or []:
        if not isinstance(raw, dict):
            continue
        entry.systems.append(systems.build_finding(
            str(raw.get("system", "")),
            within_defined_limits=bool(raw.get("within_defined_limits")),
            findings={str(k): str(v) for k, v in (raw.get("findings") or {}).items()},
            exceptions=[str(x) for x in (raw.get("exceptions") or [])],
            not_assessed=bool(raw.get("not_assessed")),
            not_assessed_reason=str(raw.get("not_assessed_reason", "")),
        ))

    for raw in payload.get("wounds") or []:
        entry.wounds.append(_fill_into(Wound(), raw))
    for raw in payload.get("scales") or []:
        entry.scales.append(_scale_result(raw))
    for raw in payload.get("medications") or []:
        med = _fill_into(Medication(), raw)
        if med.weight_kg is None and encounter.weight_kg is not None:
            med.weight_kg = encounter.weight_kg
        entry.medications.append(med)
    for raw in payload.get("interventions") or []:
        entry.interventions.append(_fill_into(Intervention(), raw))
    for raw in payload.get("notifications") or []:
        entry.notifications.append(_fill_into(ProviderNotification(), raw))

    module_data = payload.get("module_data") or {}
    if isinstance(module_data, dict):
        entry.module_data = {str(k): v for k, v in module_data.items()}

    entry.stamp()

    supplied = str(payload.get("narrative", "") or "").strip()
    composed = narrative.compose(entry, encounter)
    # A nurse who edited the composed text keeps their edit; the composer is a
    # starting point, not an authority on their words. Which of the two happened
    # decides where the language checker looks — see `interlocks.evaluate`.
    entry.narrative_is_derived = not supplied or supplied == composed.strip()
    entry.narrative = supplied or composed
    return entry, entry.narrative


def _fill_into(target: Any, raw: Any) -> Any:
    """Copy known keys onto a dataclass instance, coercing numbers and booleans."""
    if not isinstance(raw, dict):
        return target
    annotations = {f.name: f.type for f in target.__dataclass_fields__.values()}
    for key, value in raw.items():
        if key not in annotations:
            continue
        declared = str(annotations[key])
        if "float" in declared:
            if value in (None, ""):
                setattr(target, key, None)
                continue
            try:
                setattr(target, key, float(value))
            except (TypeError, ValueError):
                raise HTTPException(400, f"{key} must be a number")
        elif "bool" in declared:
            setattr(target, key, bool(value))
        elif "list" in declared:
            setattr(target, key, [str(v) for v in (value or [])])
        else:
            setattr(target, key, str(value or "").strip())
    return target


def _scale_result(raw: Any) -> ScaleResult:
    """Rebuild a scale result, recomputing the score from the responses.

    The client's score is not trusted: the responses are re-run through the
    registered scale. A score that came from the browser is a score nobody can
    reproduce, and a reproducible score is the entire reason the responses are
    stored alongside it.
    """
    if not isinstance(raw, dict):
        return ScaleResult()
    scale = scales.get(str(raw.get("scale_id", "")))
    if not scale:
        return _fill_into(ScaleResult(), raw)
    result = scale.evaluate(raw.get("responses") or {})
    result.notes = str(raw.get("notes", "") or "").strip()
    return result


# ------------------------------------------------------------------- payloads


def _payload(encounter: Encounter) -> dict[str, Any]:
    """The encounter, plus everything derived that the UI would otherwise recompute."""
    data = store_module._to_jsonable(encounter)
    overdue = encounter.overdue_loops()
    latest = encounter.latest_vitals()
    module = specialty.module_for(encounter.setting)
    data["_derived"] = {
        "entry_count": len(encounter.entries),
        "untranscribed": [
            {"entry_id": e.entry_id, "title": e.title(),
             "documented_at": e.documented_at}
            for e in encounter.untranscribed()
        ],
        "open_loops": [
            {"reassessment_id": l.reassessment_id, "trigger": l.trigger,
             "due_at": l.due_at, "window_minutes": l.window_minutes,
             "overdue": l.is_overdue(), "minutes_late": l.minutes_late()}
            for l in encounter.open_loops()
        ],
        "overdue_count": len(overdue),
        "latest_vitals_narrative": latest.narrative(),
        "critical_values": interlocks.critical_values(latest),
        "requires_weight": encounter.requires_weight(),
        "weight_recorded": encounter.weight_kg is not None,
        "priority_scales": module.priority_scales if module else [],
        "module": module.as_dict() if module else None,
        "revision_count": sum(len(e.revisions) for e in encounter.entries),
        "audit_verification": store_module.verify_chain(encounter),
    }
    return data
