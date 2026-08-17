"""
The record types for the charting tab.

Four design decisions drive everything else here.

**Documentation time is the system clock. Event time is yours.** `Entry` carries
both, and only `event_at` is editable. There is no way to make this tool say a
note was written at a time it was not written, because the single most damaging
thing a nurse can do to their own credibility is back-date. When the gap between
the two exceeds the late-entry window, the entry is tagged `[LATE ENTRY]`
automatically — which is the correct, defensible way to document something you
remembered an hour later, and it reads far better than a timestamp that quietly
does not match the medication scanner's log.

**Nothing is ever overwritten.** `Entry.revisions` is append-only. Correcting a
note keeps the original text, records who-changed-what-and-why, and the export
renders the superseded text struck through with the addendum beneath it. An
altered record is the one fact pattern that turns a defensible case into an
indefensible one, so the tool has no mutation path at all: `Entry.revise()`
appends.

**The audit trail is hash-chained.** Each `AuditEvent` includes the digest of the
one before it (`prev_digest`), so the sequence can be verified with
`store.verify_chain`. This does not make the file tamper-*proof* — anything on
your own disk can be rewritten wholesale — but it does mean a single edited or
deleted event is detectable rather than invisible, which is the honest version of
"immutable" for a local file.

**No patient identifiers exist as fields.** See `disclosure.py`. An `Encounter`
is a bed label and, optionally, initials.
"""

from __future__ import annotations

import hashlib
import json
import re
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

# How stale an event can be before the entry is tagged as a late entry. The
# user's specification said 60 minutes, which matches common hospital policy.
LATE_ENTRY_MINUTES = 60


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso(moment: datetime | None) -> str:
    return moment.isoformat(timespec="seconds") if moment else ""


def parse_iso(text: str) -> datetime | None:
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}-{secrets.token_hex(4)}"


# ------------------------------------------------------------------ enumerations


class EntryKind(str, Enum):
    """What a note is for.

    The kind drives which interlocks run. A shift assessment and a code blue
    record have different completeness requirements, and a tool that applied one
    checklist to both would either block routine notes or wave through the ones
    that matter.
    """

    SHIFT_ASSESSMENT = "shift_assessment"
    FOCUSED_UPDATE = "focused_update"
    EVENT_NOTE = "event_note"
    PROVIDER_NOTIFICATION = "provider_notification"
    MEDICATION = "medication"
    PROCEDURE = "procedure"
    EDUCATION = "education"
    REFUSAL = "refusal"
    RESTRAINT = "restraint"
    BLOOD_PRODUCT = "blood_product"
    FALL_EVENT = "fall_event"
    RAPID_RESPONSE = "rapid_response"
    HANDOFF = "handoff"
    DISCHARGE = "discharge"
    ASSIGNMENT = "assignment"

    @property
    def label(self) -> str:
        return {
            "shift_assessment": "Shift assessment",
            "focused_update": "Focused update",
            "event_note": "Event note",
            "provider_notification": "Provider notification",
            "medication": "Medication administration",
            "procedure": "Procedure",
            "education": "Patient education",
            "refusal": "Refusal of care / AMA",
            "restraint": "Restraint episode",
            "blood_product": "Blood product administration",
            "fall_event": "Fall event",
            "rapid_response": "Rapid response / code",
            "handoff": "Handoff",
            "discharge": "Discharge",
            "assignment": "Assignment and staffing",
        }[self.value]


class Setting(str, Enum):
    """The specialty module in play."""

    MED_SURG = "med_surg"
    EMERGENCY = "emergency"
    ICU = "icu"
    PEDIATRIC = "pediatric"
    OTHER = "other"

    @property
    def label(self) -> str:
        return {
            "med_surg": "Medical-surgical / telemetry",
            "emergency": "Emergency department",
            "icu": "Intensive care",
            "pediatric": "Pediatrics",
            "other": "Other / general",
        }[self.value]


class Severity(str, Enum):
    BLOCK = "block"       # save is refused
    WARN = "warn"         # save proceeds, the note records the warning
    INFO = "info"


# ------------------------------------------------------------------- vital signs


@dataclass
class Vitals:
    """One set of vital signs.

    Stored as optional floats rather than a formatted string so the escalation
    matrix and the scoring scales can read them. `taken_at` is separate from the
    entry's own timestamps because a note written at 14:20 routinely quotes vitals
    taken at 14:05, and conflating the two is how documentation drifts out of
    agreement with the flowsheet.
    """

    taken_at: str = ""
    systolic: float | None = None
    diastolic: float | None = None
    map_mmhg: float | None = None
    heart_rate: float | None = None
    rhythm: str = ""
    respiratory_rate: float | None = None
    spo2: float | None = None
    oxygen_delivery: str = ""          # "room air", "2 L/min nasal cannula", …
    fio2: float | None = None
    temperature_c: float | None = None
    temperature_route: str = ""
    pain_score: float | None = None
    pain_scale: str = ""               # which scale produced that number
    blood_glucose: float | None = None
    weight_kg: float | None = None
    height_cm: float | None = None
    end_tidal_co2: float | None = None

    def temperature_f(self) -> float | None:
        return None if self.temperature_c is None else self.temperature_c * 9 / 5 + 32

    def computed_map(self) -> float | None:
        """MAP, measured if present and estimated from the cuff if not.

        The estimate is the standard (SBP + 2·DBP)/3. It is labelled as estimated
        wherever it is rendered, because an arterial line MAP and a calculated one
        are not interchangeable when a pressor is being titrated to it.
        """
        if self.map_mmhg is not None:
            return self.map_mmhg
        if self.systolic is None or self.diastolic is None:
            return None
        return round((self.systolic + 2 * self.diastolic) / 3, 1)

    def map_is_estimated(self) -> bool:
        return self.map_mmhg is None and self.computed_map() is not None

    def is_empty(self) -> bool:
        return not any(
            value is not None
            for value in (
                self.systolic, self.diastolic, self.map_mmhg, self.heart_rate,
                self.respiratory_rate, self.spo2, self.temperature_c,
                self.pain_score, self.blood_glucose, self.end_tidal_co2,
            )
        )

    def narrative(self) -> str:
        """The vitals as a clinical sentence.

        Written in the order a nurse says them aloud, which is also the order they
        appear on every flowsheet: pressure, rate, respirations, saturation,
        temperature, pain.
        """
        parts: list[str] = []
        if self.systolic is not None and self.diastolic is not None:
            pressure = f"BP {self.systolic:g}/{self.diastolic:g} mmHg"
            mean = self.computed_map()
            if mean is not None:
                pressure += (f" (MAP {mean:g}, calculated)" if self.map_is_estimated()
                             else f" (MAP {mean:g})")
            parts.append(pressure)
        elif self.map_mmhg is not None:
            parts.append(f"MAP {self.map_mmhg:g} mmHg")
        if self.heart_rate is not None:
            rate = f"HR {self.heart_rate:g}"
            if self.rhythm:
                rate += f", {self.rhythm}"
            parts.append(rate)
        if self.respiratory_rate is not None:
            parts.append(f"RR {self.respiratory_rate:g}")
        if self.spo2 is not None:
            saturation = f"SpO2 {self.spo2:g}%"
            if self.oxygen_delivery:
                saturation += f" on {self.oxygen_delivery}"
            parts.append(saturation)
        if self.end_tidal_co2 is not None:
            parts.append(f"EtCO2 {self.end_tidal_co2:g} mmHg")
        if self.temperature_c is not None:
            fahrenheit = self.temperature_f()
            temperature = f"T {self.temperature_c:.1f} °C ({fahrenheit:.1f} °F)"
            if self.temperature_route:
                temperature += f", {self.temperature_route}"
            parts.append(temperature)
        if self.pain_score is not None:
            scale = self.pain_scale or "0-10"
            parts.append(f"pain {self.pain_score:g}/10 ({scale})")
        if self.blood_glucose is not None:
            parts.append(f"glucose {self.blood_glucose:g} mg/dL")
        if not parts:
            return ""
        stamp = parse_iso(self.taken_at)
        prefix = f"Vital signs at {stamp:%H:%M}: " if stamp else "Vital signs: "
        return prefix + "; ".join(parts) + "."


# ------------------------------------------------------------- system assessment


@dataclass
class SystemFinding:
    """One body system's assessment.

    `within_defined_limits` is the charting-by-exception toggle. It is not a way
    to skip the assessment: `store` records which systems were marked WDL and the
    export prints the unit's WDL definition alongside them, because "WDL" means
    nothing to a jury unless the document says what limits were defined. A system
    marked WDL with exceptions listed is the normal case and is rendered as
    "within defined limits except …".
    """

    system: str = ""
    within_defined_limits: bool = False
    findings: dict[str, str] = field(default_factory=dict)
    exceptions: list[str] = field(default_factory=list)
    narrative_override: str = ""
    assessed_at: str = ""
    not_assessed: bool = False
    not_assessed_reason: str = ""


@dataclass
class Wound:
    """One wound or pressure injury.

    `present_on_admission` is here because it carries more consequence than any
    other field in this file. A pressure injury documented on admission is a
    patient's pre-existing condition; the same injury documented first on day
    three is a hospital-acquired condition, reportable, non-reimbursable and the
    starting point of a claim. If it was there when you met the patient, say so in
    the note that first describes it.
    """

    wound_id: str = field(default_factory=lambda: new_id("wnd"))
    location: str = ""
    kind: str = ""                     # pressure injury, surgical, venous, …
    stage: str = ""
    length_cm: float | None = None
    width_cm: float | None = None
    depth_cm: float | None = None
    tunneling_cm: float | None = None
    tunneling_position: str = ""       # clock position
    undermining_cm: float | None = None
    undermining_position: str = ""
    wound_bed: str = ""
    drainage_amount: str = ""
    drainage_type: str = ""
    odour: str = ""
    periwound: str = ""
    dressing: str = ""
    dressing_changed: bool = False
    present_on_admission: bool = False
    photographed: bool = False
    measured_at: str = ""

    def narrative(self) -> str:
        parts: list[str] = []
        head = self.kind or "Wound"
        if self.location:
            head += f" to {self.location}"
        if self.stage:
            head += f", {self.stage}"
        parts.append(head)
        if self.length_cm is not None or self.width_cm is not None:
            dimensions = [
                f"{self.length_cm:g} cm" if self.length_cm is not None else "unmeasured",
                f"{self.width_cm:g} cm" if self.width_cm is not None else "unmeasured",
            ]
            if self.depth_cm is not None:
                dimensions.append(f"{self.depth_cm:g} cm")
            parts.append("measuring " + " × ".join(dimensions)
                         + (" (L × W × D)" if self.depth_cm is not None else " (L × W)"))
        if self.tunneling_cm is not None:
            tunnel = f"tunneling {self.tunneling_cm:g} cm"
            if self.tunneling_position:
                tunnel += f" at {self.tunneling_position}"
            parts.append(tunnel)
        if self.undermining_cm is not None:
            under = f"undermining {self.undermining_cm:g} cm"
            if self.undermining_position:
                under += f" at {self.undermining_position}"
            parts.append(under)
        if self.wound_bed:
            parts.append(f"wound bed {self.wound_bed}")
        if self.drainage_amount or self.drainage_type:
            parts.append(f"drainage {' '.join(x for x in (self.drainage_amount, self.drainage_type) if x)}")
        if self.odour:
            parts.append(f"odour {self.odour}")
        if self.periwound:
            parts.append(f"periwound {self.periwound}")
        text = "; ".join(parts) + "."
        if self.dressing:
            text += (f" {self.dressing} applied." if self.dressing_changed
                     else f" {self.dressing} in place, clean, dry and intact.")
        if self.present_on_admission:
            text += " Present on admission."
        return text


# --------------------------------------------------------------- scoring scales


@dataclass
class ScaleResult:
    """A completed scoring scale.

    `responses` keeps the raw selections so the score can be recomputed and
    audited; `narrative` is the clinical sentence that goes in the note. Both are
    stored because a score without its inputs cannot be defended, and inputs
    without a sentence do not chart.
    """

    result_id: str = field(default_factory=lambda: new_id("scl"))
    scale_id: str = ""
    scale_name: str = ""
    score: float | None = None
    subscores: dict[str, float] = field(default_factory=dict)
    band: str = ""
    band_detail: str = ""
    responses: dict[str, Any] = field(default_factory=dict)
    narrative: str = ""
    citation: str = ""
    scored_at: str = ""
    incomplete: list[str] = field(default_factory=list)
    notes: str = ""


# ---------------------------------------------------------------- interventions


@dataclass
class Medication:
    """One medication administration.

    Deliberately verbose. Route, site, and the two-identifier check are separate
    fields rather than free text because these are exactly the elements a
    deposition asks about one at a time, and a nurse reading their own note two
    years later needs to find them without interpreting a sentence.

    `weight_kg` is on the record, not just the encounter, because a paediatric
    dose is defended against the weight used *at that administration*.
    """

    med_id: str = field(default_factory=lambda: new_id("med"))
    name: str = ""
    dose: str = ""
    dose_mg_per_kg: str = ""
    route: str = ""
    site: str = ""
    given_at: str = ""
    scheduled_at: str = ""
    indication: str = ""
    prn: bool = False
    pre_assessment: str = ""
    two_identifiers_verified: bool = False
    high_alert: bool = False
    second_nurse_verified: bool = False
    second_nurse_initials: str = ""
    weight_kg: float | None = None
    pump_programmed_check: bool = False
    held: bool = False
    hold_reason: str = ""
    provider_notified_of_hold: bool = False
    refused: bool = False
    wasted_amount: str = ""
    waste_witness_initials: str = ""
    effect_checked_at: str = ""
    effect: str = ""
    reaction: str = ""

    def requires_reassessment(self) -> bool:
        """Whether a closed loop is owed.

        Anything given for pain, fever, agitation, hypoglycaemia or blood
        pressure has an effect that must be documented. This is the trigger for
        the reassessment timer in `interlocks.py`.
        """
        if self.held or self.refused:
            return False
        return bool(self.prn or self.indication)


@dataclass
class ProviderNotification:
    """Who you told, when, how, and what came back.

    This is the single most load-bearing record in the module. In a claim where a
    patient deteriorated, the question is almost never whether the nurse noticed;
    it is whether the nurse escalated and what happened next. A note that says
    "MD aware" answers none of it.

    `no_response` plus `escalated_to` is the chain-of-command path: a provider who
    does not answer is not the end of the nurse's duty, and the record has to show
    the next rung being climbed.
    """

    notification_id: str = field(default_factory=lambda: new_id("ntf"))
    notified_at: str = ""
    provider_name: str = ""
    provider_role: str = ""
    method: str = ""                   # paged, phone, secure text, in person
    reason: str = ""
    information_given: str = ""
    read_back: bool = False
    response_at: str = ""
    response: str = ""
    orders_received: str = ""
    no_new_orders: bool = False
    no_response: bool = False
    escalated_to: str = ""
    escalated_at: str = ""
    escalation_response: str = ""

    def is_complete(self) -> bool:
        return bool(self.notified_at and self.provider_name and self.method
                    and self.reason)

    # The method is stored as the nurse selected it — "paged", "phone" — and has to
    # be rendered as a phrase. "Notified Dr. Alvarez by paged" is the kind of
    # sentence that makes a whole note look auto-generated, which is the last
    # impression a defensible chart wants to give.
    _METHOD_PHRASES = {
        "paged": "by page",
        "page": "by page",
        "phone": "by telephone",
        "telephone": "by telephone",
        "call": "by telephone",
        "secure text": "by secure message",
        "secure message": "by secure message",
        "text": "by secure message",
        "in person": "in person",
        "bedside": "at the bedside",
        "at the bedside": "at the bedside",
        "email": "by email",
        "overhead": "by overhead page",
    }

    def method_phrase(self) -> str:
        key = self.method.strip().lower()
        if not key:
            return ""
        return self._METHOD_PHRASES.get(key, f"by {self.method.strip()}")

    def narrative(self) -> str:
        stamp = parse_iso(self.notified_at)
        when = f"{stamp:%H:%M}" if stamp else "time not recorded"
        who = self.provider_name or "provider"
        if self.provider_role:
            who += f" ({self.provider_role})"
        method = self.method_phrase()
        text = f"At {when}, notified {who}"
        if method:
            text += f" {method}"
        if self.reason:
            text += f" regarding {self.reason}"
        text += "."
        if self.information_given:
            text += f" Reported {self.information_given}."
        if self.read_back:
            text += " Orders read back and verified."
        if self.response:
            reply = parse_iso(self.response_at)
            prefix = f"At {reply:%H:%M}, " if reply else ""
            text += f" {prefix}{who} responded: {self.response}."
        if self.orders_received:
            text += f" Orders received: {self.orders_received}."
        elif self.no_new_orders:
            text += " No new orders received."
        if self.no_response:
            text += " No response received."
        if self.escalated_to:
            climb = parse_iso(self.escalated_at)
            when_climbed = f"At {climb:%H:%M}, " if climb else ""
            text += f" {when_climbed}escalated to {self.escalated_to}."
            if self.escalation_response:
                text += f" {self.escalation_response}."
        text += " Continued to monitor."
        return text


@dataclass
class Intervention:
    """Something you did, and what happened after.

    `evaluated_at` and `response` are the closing half of the loop. An
    intervention with no documented response reads, to a reviewer, as an
    intervention that was never evaluated.
    """

    intervention_id: str = field(default_factory=lambda: new_id("int"))
    action: str = ""
    performed_at: str = ""
    route: str = ""
    site: str = ""
    dose: str = ""
    equipment: str = ""
    patient_tolerance: str = ""
    evaluated_at: str = ""
    response: str = ""
    performed_by: str = ""


@dataclass
class Reassessment:
    """A follow-up owed or performed.

    Created by the interlocks when something opens a loop — an analgesic, a
    pressor titration, a restraint check, a blood product — and satisfied when the
    nurse records the follow-up. Overdue loops are the charting tab's main nag.
    """

    reassessment_id: str = field(default_factory=lambda: new_id("ras"))
    trigger: str = ""
    trigger_entry_id: str = ""
    due_at: str = ""
    window_minutes: int = 60
    performed_at: str = ""
    finding: str = ""
    satisfied: bool = False
    not_done_reason: str = ""

    def is_overdue(self, at: datetime | None = None) -> bool:
        if self.satisfied or self.not_done_reason:
            return False
        due = parse_iso(self.due_at)
        return bool(due and (at or now_utc()) > due)

    def minutes_late(self, at: datetime | None = None) -> int:
        due = parse_iso(self.due_at)
        if not due:
            return 0
        delta = (at or now_utc()) - due
        return max(0, int(delta.total_seconds() // 60))


# ------------------------------------------------------------------- provenance


@dataclass
class Revision:
    """One correction to an entry. Append-only; the original text is kept.

    `reason` is required by `Entry.revise`. "Wrong chart" and "typographical
    error" are the two the specification named; the field is free text because a
    correction whose reason does not fit a dropdown still has to be explainable.
    """

    revision_id: str = field(default_factory=lambda: new_id("rev"))
    revised_at: str = ""
    reason: str = ""
    author_initials: str = ""
    previous_text: str = ""
    new_text: str = ""


@dataclass
class AuditEvent:
    """One link in the hash chain.

    `digest` covers the event's own content *and* `prev_digest`, so altering any
    earlier event breaks every digest after it. `store.verify_chain` walks the
    file and reports the first break.
    """

    event_id: str = field(default_factory=lambda: new_id("aud"))
    at: str = ""
    action: str = ""
    target: str = ""
    detail: str = ""
    author_initials: str = ""
    prev_digest: str = ""
    digest: str = ""

    def compute_digest(self) -> str:
        payload = json.dumps(
            {
                "event_id": self.event_id,
                "at": self.at,
                "action": self.action,
                "target": self.target,
                "detail": self.detail,
                "author_initials": self.author_initials,
                "prev_digest": self.prev_digest,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def seal(self, prev_digest: str) -> "AuditEvent":
        self.prev_digest = prev_digest
        self.digest = self.compute_digest()
        return self


@dataclass
class Flag:
    """Something the tool has to say about an entry before it is saved.

    A flag with `severity == BLOCK` prevents the save. Blocks are deliberately
    rare and all of them come from the user's specification: an incident-report
    reference, a critical vital with no notification, a paediatric medication with
    no weight, an unchanged copy-forward, a correction with no reason.
    """

    code: str = ""
    severity: Severity = Severity.WARN
    message: str = ""
    field_path: str = ""
    excerpt: str = ""
    suggestion: str = ""
    offset: int = -1
    length: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity.value,
            "message": self.message,
            "field_path": self.field_path,
            "excerpt": self.excerpt,
            "suggestion": self.suggestion,
            "offset": self.offset,
            "length": self.length,
        }


# ------------------------------------------------------------------------ entry


@dataclass
class Entry:
    """One note.

    The composed text lives in `narrative`; the structured pieces that produced
    it stay alongside it, because a note is far easier to defend when the
    underlying observation is still addressable. `sbar` holds the four-part
    hybrid the specification asked for.
    """

    entry_id: str = field(default_factory=lambda: new_id("ent"))
    kind: EntryKind = EntryKind.FOCUSED_UPDATE
    setting: Setting = Setting.MED_SURG
    author_initials: str = ""
    author_credential: str = ""

    documented_at: str = ""            # system clock, never user-set
    event_at: str = ""                 # when it happened, user-set
    late_entry: bool = False
    late_by_minutes: int = 0

    # Why this note exists. The specification put it in the S section beside the
    # patient's own words, and there was nowhere to put it — the entry-kind
    # dropdown was standing in for it, which answers "what kind of note" rather
    # than "what prompted it".
    reason: str = ""
    subjective: str = ""
    objective: str = ""
    assessment: str = ""
    plan: str = ""
    narrative: str = ""
    # Whether `narrative` was composed from the sections above or typed by the
    # nurse. Two reasons this is worth storing: the language checker must scan the
    # sections *or* the narrative but not both, otherwise every flagged word is
    # reported twice from the same text; and it is real provenance — a note the
    # nurse wrote in their own words and a note the tool assembled are different
    # artefacts, and the audit appendix should not blur them.
    narrative_is_derived: bool = True

    vitals: Vitals = field(default_factory=Vitals)
    systems: list[SystemFinding] = field(default_factory=list)
    wounds: list[Wound] = field(default_factory=list)
    scales: list[ScaleResult] = field(default_factory=list)
    medications: list[Medication] = field(default_factory=list)
    interventions: list[Intervention] = field(default_factory=list)
    notifications: list[ProviderNotification] = field(default_factory=list)
    labs: str = ""
    pending: str = ""
    module_data: dict[str, Any] = field(default_factory=dict)

    revisions: list[Revision] = field(default_factory=list)
    flags: list[dict[str, Any]] = field(default_factory=list)
    acknowledged_warnings: list[str] = field(default_factory=list)

    transcribed_at: str = ""
    transcribed_note: str = ""
    signed: bool = False
    signed_at: str = ""

    def stamp(self, at: datetime | None = None,
              late_window: int = LATE_ENTRY_MINUTES) -> "Entry":
        """Set the documentation time from the clock and derive late-entry state.

        Called on create and never again — `documented_at` is the one timestamp in
        this module that no caller can supply.
        """
        moment = at or now_utc()
        self.documented_at = iso(moment)
        event = parse_iso(self.event_at) or moment
        if not self.event_at:
            self.event_at = iso(moment)
        gap = int((moment - event).total_seconds() // 60)
        self.late_by_minutes = max(0, gap)
        self.late_entry = self.late_by_minutes > late_window
        return self

    def event_in_future(self, at: datetime | None = None) -> bool:
        """Whether the event time is ahead of the clock.

        Charting something before it happens is a different failure from charting
        it late, and a worse one — it is the shape of a pre-signed assessment.
        The interlocks refuse it.
        """
        event = parse_iso(self.event_at)
        return bool(event and event > (at or now_utc()) + timedelta(minutes=2))

    def revise(self, new_text: str, reason: str, author_initials: str = "",
               at: datetime | None = None) -> Revision:
        """Append a correction. Raises if no reason is given.

        There is no setter for `narrative` anywhere else in the package. This is
        the only path, and it cannot lose the previous text.
        """
        reason = reason.strip()
        if not reason:
            raise ValueError(
                "A correction needs a reason — 'wrong chart', 'typographical "
                "error', or whatever actually happened. An unexplained change to "
                "a clinical note is the fact pattern that turns a defensible "
                "record into an indefensible one."
            )
        revision = Revision(
            revised_at=iso(at or now_utc()),
            reason=reason,
            author_initials=author_initials or self.author_initials,
            previous_text=self.narrative,
            new_text=new_text,
        )
        self.revisions.append(revision)
        self.narrative = new_text
        return revision

    def blocking_flags(self) -> list[dict[str, Any]]:
        return [f for f in self.flags if f.get("severity") == Severity.BLOCK.value]

    def title(self) -> str:
        stamp = parse_iso(self.event_at)
        when = f"{stamp:%H:%M}" if stamp else "unstamped"
        prefix = "[LATE ENTRY] " if self.late_entry else ""
        return f"{prefix}{when} — {self.kind.label}"


# -------------------------------------------------------------------- encounter


@dataclass
class ShiftContext:
    """The unit conditions the shift ran under.

    This exists because of the ratios in the specification, and it is more
    protective than it looks. A nurse who carried nine patients on a unit
    budgeted for five, escalated it, and documented that contemporaneously is in a
    materially different position from one who did the same work silently. It
    belongs in a shift record, not in a patient's chart — which is exactly why it
    lives on the encounter's context and not in a note.
    """

    unit: str = ""
    shift: str = ""                    # days, nights, 0700-1930
    patient_count: int | None = None
    expected_ratio: str = ""
    acuity_note: str = ""
    support_staff: str = ""
    charge_nurse: str = ""
    concerns_raised_to: str = ""
    concerns_raised_at: str = ""
    concerns_summary: str = ""
    response_received: str = ""


@dataclass
class Encounter:
    """One patient, one shift, no identifiers.

    `local_label` is a bed or room. `initials` is optional and is the furthest
    this module goes toward identification — see `disclosure.py` for why there is
    no name field and never will be.
    """

    encounter_id: str = ""
    local_label: str = ""
    initials: str = ""
    setting: Setting = Setting.MED_SURG
    age_band: str = ""                 # "adult", "8 y", "preterm" — not a DOB
    weight_kg: float | None = None
    weight_measured_at: str = ""
    height_cm: float | None = None
    code_status: str = ""
    advance_directive: str = ""
    allergies: str = ""
    isolation: str = ""
    diagnosis_summary: str = ""
    language: str = ""
    interpreter_used: bool = False
    interpreter_id: str = ""
    baseline_mental_status: str = ""
    lines_drains_airways: list[dict[str, Any]] = field(default_factory=list)
    context: ShiftContext = field(default_factory=ShiftContext)

    entries: list[Entry] = field(default_factory=list)
    reassessments: list[Reassessment] = field(default_factory=list)
    audit: list[AuditEvent] = field(default_factory=list)
    wdl_definition: str = ""
    created_at: str = ""
    updated_at: str = ""
    schema_version: int = 1

    # ------------------------------------------------------------- derivations

    def sorted_entries(self) -> list[Entry]:
        return sorted(self.entries, key=lambda e: (e.event_at or e.documented_at))

    def entry(self, entry_id: str) -> Entry | None:
        return next((e for e in self.entries if e.entry_id == entry_id), None)

    def last_entry_of(self, kind: EntryKind) -> Entry | None:
        matching = [e for e in self.sorted_entries() if e.kind == kind]
        return matching[-1] if matching else None

    def open_loops(self, at: datetime | None = None) -> list[Reassessment]:
        return [r for r in self.reassessments
                if not r.satisfied and not r.not_done_reason]

    def overdue_loops(self, at: datetime | None = None) -> list[Reassessment]:
        return [r for r in self.open_loops() if r.is_overdue(at)]

    def untranscribed(self) -> list[Entry]:
        return [e for e in self.sorted_entries() if not e.transcribed_at]

    def requires_weight(self) -> bool:
        """Whether the paediatric weight hard stop applies.

        Weight-based dosing is the default in paediatrics and the error mode is
        catastrophic, so the specification asked for a hard stop. It applies to
        the paediatric setting and to any encounter with a paediatric age band.
        """
        if self.setting is Setting.PEDIATRIC:
            return True
        band = self.age_band.lower()
        if any(token in band for token in
               ("neonat", "infant", "preterm", "child", "paed", "ped",
                "month", "week", "day", "mo", "wk", "newborn", "toddler",
                "adolescen", "teen")):
            return True
        # "8 y", "4 yr", "16 years" — how a nurse actually writes an age band, and
        # the form the original token list missed entirely. A paediatric patient
        # boarded on an adult unit still needs the weight before a dose.
        match = re.search(r"(\d+)\s*(?:y|yr|yrs|year|years)\b", band)
        return bool(match and int(match.group(1)) < 18)

    def latest_vitals(self) -> Vitals:
        for entry in reversed(self.sorted_entries()):
            if not entry.vitals.is_empty():
                return entry.vitals
        return Vitals()

    def last_audit_digest(self) -> str:
        return self.audit[-1].digest if self.audit else ""

    def record(self, action: str, target: str = "", detail: str = "",
               author_initials: str = "", at: datetime | None = None) -> AuditEvent:
        event = AuditEvent(
            at=iso(at or now_utc()),
            action=action,
            target=target,
            detail=detail,
            author_initials=author_initials,
        ).seal(self.last_audit_digest())
        self.audit.append(event)
        return event
