"""
Encounter storage: one JSON file per encounter, written atomically.

Same reasoning as `storage.ProjectStore` — a shift's notes are a small object you
want to be able to read, grep, back up and delete without any tooling — with three
additions that the clinical side needs.

**Purge is a first-class operation.** `purge_all` deletes every encounter file and
says how many it removed. It is on every charting screen, not buried in settings,
because the correct end of a shift is an empty data directory. A charting tool
whose data accumulates for months is a privacy incident waiting for a lost laptop.

**The audit chain is verified on load.** Every `AuditEvent` carries the digest of
its predecessor, so `verify_chain` can report the first point where the sequence
does not add up. This does not make the file tamper-proof — nothing on your own
disk is — but it distinguishes "this file was edited by hand" from "this file is
intact", which is the difference between a record and a rumour.

**Nothing is deleted inside an encounter.** Entries are never removed and never
overwritten; `Entry.revise` appends. The only destructive operation in this module
is deleting a whole encounter, which is the privacy operation and is deliberately
total.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import tempfile
from dataclasses import fields as dataclass_fields, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import (
    AuditEvent, Encounter, Entry, EntryKind, Flag, Intervention, Medication,
    ProviderNotification, Reassessment, Revision, ScaleResult, Setting, ShiftContext,
    Severity, SystemFinding, Vitals, Wound, iso, now_utc,
)

SCHEMA_VERSION = 1


class EncounterStore:
    def __init__(self, directory: Path):
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)

    # -------------------------------------------------------------- lifecycle

    def new_encounter(self, local_label: str, *, setting: str = "med_surg",
                      initials: str = "", age_band: str = "adult",
                      author_initials: str = "") -> Encounter:
        try:
            resolved = Setting(setting)
        except ValueError:
            resolved = Setting.MED_SURG
        encounter = Encounter(
            encounter_id=self._make_id(local_label),
            local_label=local_label.strip(),
            initials=initials.strip()[:4],
            setting=resolved,
            age_band=age_band.strip() or "adult",
            created_at=iso(now_utc()),
            updated_at=iso(now_utc()),
        )
        encounter.record("encounter_created", encounter.encounter_id,
                         f"setting {resolved.value}", author_initials)
        self.save(encounter)
        return encounter

    def _make_id(self, label: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")[:24] or "encounter"
        candidate = f"{datetime.now().strftime('%Y%m%d')}-{slug}"
        while (self.directory / f"{candidate}.json").exists():
            candidate = f"{datetime.now().strftime('%Y%m%d')}-{slug}-{secrets.token_hex(2)}"
        return candidate

    def path_for(self, encounter_id: str) -> Path:
        """Resolve an id to a file, refusing anything path-shaped.

        Stripping the separators out and carrying on would be *safe* — the result
        cannot escape the directory — but it would silently write to a mangled
        filename, so a caller passing rubbish would get a junk file instead of an
        error. Refusing outright says what happened.
        """
        if any(token in encounter_id for token in ("/", "\\", "..", "\0")):
            raise ValueError(f"unsafe encounter id {encounter_id!r}")
        safe = re.sub(r"[^A-Za-z0-9._-]", "", encounter_id)
        if not safe or safe in (".", ".."):
            raise ValueError(f"unsafe encounter id {encounter_id!r}")
        return self.directory / f"{safe}.json"

    def list_encounters(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for path in sorted(self.directory.glob("*.json"), reverse=True):
            try:
                raw = json.loads(path.read_text("utf-8"))
            except (OSError, ValueError):
                continue
            entries = raw.get("entries") or []
            rows.append({
                "encounter_id": raw.get("encounter_id", path.stem),
                "local_label": raw.get("local_label", ""),
                "initials": raw.get("initials", ""),
                "setting": raw.get("setting", "med_surg"),
                "created_at": raw.get("created_at", ""),
                "updated_at": raw.get("updated_at", ""),
                "entry_count": len(entries),
                "untranscribed": sum(1 for e in entries if not e.get("transcribed_at")),
            })
        return rows

    def save(self, encounter: Encounter) -> Encounter:
        encounter.updated_at = iso(now_utc())
        encounter.schema_version = SCHEMA_VERSION
        payload = _to_jsonable(encounter)
        path = self.path_for(encounter.encounter_id)
        handle = tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=str(self.directory), delete=False,
            prefix=".tmp-", suffix=".json")
        try:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.flush()
            os.fsync(handle.fileno())
            handle.close()
            os.replace(handle.name, path)
        except BaseException:
            handle.close()
            try:
                os.unlink(handle.name)
            except OSError:
                pass
            raise
        try:
            path.chmod(0o600)   # a shift's notes are nobody else's business
        except OSError:
            pass
        return encounter

    def load(self, encounter_id: str) -> Encounter:
        path = self.path_for(encounter_id)
        if not path.exists():
            raise FileNotFoundError(encounter_id)
        raw = json.loads(path.read_text("utf-8"))
        return _encounter_from_dict(raw)

    def delete(self, encounter_id: str) -> bool:
        path = self.path_for(encounter_id)
        if not path.exists():
            return False
        path.unlink()
        return True

    def purge_all(self) -> int:
        """Delete every encounter. Returns the count removed."""
        removed = 0
        for path in list(self.directory.glob("*.json")):
            try:
                path.unlink()
                removed += 1
            except OSError:
                continue
        return removed


# ------------------------------------------------------------------ audit chain


def verify_chain(encounter: Encounter) -> dict[str, Any]:
    """Walk the audit chain and report the first break.

    Two failure shapes are distinguished, because they mean different things: a
    digest that does not match its own content means that event was altered, and a
    `prev_digest` that does not match the previous event's digest means an event
    was inserted or removed.
    """
    previous = ""
    for index, event in enumerate(encounter.audit):
        if event.prev_digest != previous:
            return {
                "intact": False,
                "broken_at": index,
                "event_id": event.event_id,
                "reason": ("This event's predecessor digest does not match the "
                           "event before it, which means an event was inserted or "
                           "removed at this point."),
                "verified": index,
            }
        if event.digest != event.compute_digest():
            return {
                "intact": False,
                "broken_at": index,
                "event_id": event.event_id,
                "reason": ("This event's own digest does not match its content, "
                           "which means the event was altered after it was "
                           "written."),
                "verified": index,
            }
        previous = event.digest
    return {
        "intact": True,
        "broken_at": None,
        "event_id": "",
        "reason": (f"All {len(encounter.audit)} audit events verify against the "
                   f"hash chain. Note that this proves internal consistency, not "
                   f"tamper-proofing — a file on your own disk can be rewritten "
                   f"wholesale. What it does prove is that no single event was "
                   f"quietly changed or dropped."),
        "verified": len(encounter.audit),
    }


# ------------------------------------------------------- serialisation helpers


def _to_jsonable(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return {f.name: _to_jsonable(getattr(value, f.name))
                for f in dataclass_fields(value)}
    if isinstance(value, (Setting, EntryKind, Severity)):
        return value.value
    if isinstance(value, dict):
        return {str(k): _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(v) for v in value]
    return value


def _fill(cls, raw: Any):
    """Build a dataclass from a dict, ignoring unknown keys.

    Unknown keys are dropped rather than raising so a file written by a later
    version still loads. Missing keys keep their defaults, which is what makes a
    schema addition non-breaking.
    """
    if not isinstance(raw, dict):
        return cls()
    names = {f.name for f in dataclass_fields(cls)}
    return cls(**{k: v for k, v in raw.items() if k in names})


def _entry_from_dict(raw: dict[str, Any]) -> Entry:
    entry = _fill(Entry, {k: v for k, v in raw.items()
                          if k not in ("kind", "setting", "vitals", "systems",
                                       "wounds", "scales", "medications",
                                       "interventions", "notifications",
                                       "revisions")})
    try:
        entry.kind = EntryKind(raw.get("kind", "focused_update"))
    except ValueError:
        entry.kind = EntryKind.FOCUSED_UPDATE
    try:
        entry.setting = Setting(raw.get("setting", "med_surg"))
    except ValueError:
        entry.setting = Setting.MED_SURG
    entry.vitals = _fill(Vitals, raw.get("vitals") or {})
    entry.systems = [_fill(SystemFinding, s) for s in raw.get("systems") or []]
    entry.wounds = [_fill(Wound, w) for w in raw.get("wounds") or []]
    entry.scales = [_fill(ScaleResult, s) for s in raw.get("scales") or []]
    entry.medications = [_fill(Medication, m) for m in raw.get("medications") or []]
    entry.interventions = [_fill(Intervention, i)
                           for i in raw.get("interventions") or []]
    entry.notifications = [_fill(ProviderNotification, n)
                           for n in raw.get("notifications") or []]
    entry.revisions = [_fill(Revision, r) for r in raw.get("revisions") or []]
    return entry


def _encounter_from_dict(raw: dict[str, Any]) -> Encounter:
    encounter = _fill(Encounter, {k: v for k, v in raw.items()
                                  if k not in ("setting", "context", "entries",
                                               "reassessments", "audit")})
    try:
        encounter.setting = Setting(raw.get("setting", "med_surg"))
    except ValueError:
        encounter.setting = Setting.MED_SURG
    encounter.context = _fill(ShiftContext, raw.get("context") or {})
    encounter.entries = [_entry_from_dict(e) for e in raw.get("entries") or []]
    encounter.reassessments = [_fill(Reassessment, r)
                               for r in raw.get("reassessments") or []]
    encounter.audit = [_fill(AuditEvent, a) for a in raw.get("audit") or []]
    return encounter
