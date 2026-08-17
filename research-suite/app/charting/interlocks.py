"""
The workflow interlocks: what the tool refuses to let you save, and why.

Every rule here was asked for, and each one exists because the thing it checks is
the thing that goes missing under pressure. The list is short on purpose. An
interlock that fires on a routine note teaches the nurse to click past interlocks,
and then the one that mattered gets clicked past too.

## Blocks

Six, and no more:

1. **Critical vital signs with no provider notification.** When a recorded vital
   crosses a threshold, the note cannot be saved until the notification block has
   a time, a name, a method and a response — or until the nurse records that they
   escalated instead, or explicitly overrides with a reason. See
   `CRITICAL_THRESHOLDS`.
2. **A paediatric medication with no weight in kilograms.** Weight-based dosing is
   the norm in paediatrics and a tenfold error is survivable in neither direction.
3. **An incident-report reference,** and the three other never-in-a-chart items —
   enforced by `language.RULES`, surfaced here.
4. **A copy-forward that was not updated.** If the narrative matches the previous
   note of the same kind and neither the vitals nor the timestamps moved, the save
   is refused.
5. **An event time in the future.** Charting ahead is the shape of a pre-signed
   assessment. Late is fine and gets labelled; early is refused.
6. **A correction with no reason.** Enforced in `models.Entry.revise`, reported
   here.

Every block except 3 and 5 is **overridable with a typed reason**, and the
override is written into the note and the audit trail. A tool that cannot be
overridden gets worked around, and a nurse in a genuine emergency needs to be able
to save a note now and complete it in four minutes. The record of the override is
what keeps that honest — it is a stronger artefact than a block, because it shows
a decision being made by a person.

Block 3 has no override because there is no clinical circumstance in which the
words "incident report" belong in a chart note, and block 5 has none because the
clock is not negotiable.

## The chain of command

`CRITICAL_THRESHOLDS` fires the notification requirement. If the notification
records no response, or no new orders while the patient remains unstable,
`escalation_prompt` returns the next rung — charge nurse, then rapid response,
then the attending, then the nursing supervisor. Nothing is auto-escalated: the
tool prompts, the nurse decides and the record shows which.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from . import language
from .models import (
    Encounter, Entry, EntryKind, Flag, Medication, Reassessment, Setting, Severity,
    Vitals, iso, new_id, now_utc, parse_iso,
)


# ------------------------------------------------------- critical value thresholds


@dataclass
class Threshold:
    """One critical-value rule.

    `label` is written into the flag and into the notification's default reason, so
    the resulting note says *why* the provider was called in the words of the
    threshold that fired.
    """

    key: str
    label: str
    field: str
    low: float | None = None
    high: float | None = None
    settings: tuple[str, ...] = ()
    paediatric_only: bool = False


# Adult defaults. These are common practice rather than anyone's policy, and the
# Charting settings screen edits them — a unit whose critical systolic is 85 rather
# than 90 must be able to say so, because a tool that fires on the wrong number
# either nags or, much worse, stays quiet.
CRITICAL_THRESHOLDS: list[Threshold] = [
    Threshold("hr_high", "heart rate above 130", "heart_rate", high=130),
    Threshold("hr_low", "heart rate below 45", "heart_rate", low=45),
    Threshold("sbp_low", "systolic below 90", "systolic", low=90),
    Threshold("sbp_high", "systolic above 200", "systolic", high=200),
    Threshold("map_low", "mean arterial pressure below 65", "map", low=65),
    Threshold("rr_high", "respiratory rate above 28", "respiratory_rate", high=28),
    Threshold("rr_low", "respiratory rate below 9", "respiratory_rate", low=9),
    Threshold("spo2_low", "oxygen saturation below 90%", "spo2", low=90),
    Threshold("temp_high", "temperature above 39.5 °C", "temperature_c", high=39.5),
    Threshold("temp_low", "temperature below 35 °C", "temperature_c", low=35),
    Threshold("glucose_low", "blood glucose below 70 mg/dL", "blood_glucose", low=70),
    Threshold("glucose_high", "blood glucose above 400 mg/dL", "blood_glucose",
              high=400),
    Threshold("pain_high", "pain reported at 8 or above", "pain_score", high=7),
]


def _reading(vitals: Vitals, field: str) -> float | None:
    if field == "map":
        return vitals.computed_map()
    return getattr(vitals, field, None)


def critical_values(vitals: Vitals, *,
                    thresholds: list[Threshold] | None = None) -> list[str]:
    """Which thresholds the recorded vitals cross, described in words."""
    crossed: list[str] = []
    for threshold in (thresholds or CRITICAL_THRESHOLDS):
        value = _reading(vitals, threshold.field)
        if value is None:
            continue
        if threshold.high is not None and value > threshold.high:
            crossed.append(f"{threshold.label} (recorded {value:g})")
        elif threshold.low is not None and value < threshold.low:
            crossed.append(f"{threshold.label} (recorded {value:g})")
    return crossed


def thresholds_payload() -> list[dict[str, Any]]:
    return [
        {"key": t.key, "label": t.label, "field": t.field,
         "low": t.low, "high": t.high}
        for t in CRITICAL_THRESHOLDS
    ]


# ---------------------------------------------------------------- chain of command


ESCALATION_LADDER = [
    ("primary provider", "The provider responsible for this patient — hospitalist, "
                         "intensivist, surgeon or the resident covering."),
    ("charge nurse", "The next rung when a provider does not respond, and the one "
                     "most often skipped. A charge nurse who was told can act; one "
                     "who was not cannot."),
    ("rapid response team", "For a patient who is deteriorating now. Calling it is "
                            "never the wrong decision to have made, and a chart "
                            "showing a nurse called it early is a chart that "
                            "defends itself."),
    ("attending physician", "Over the head of a resident or covering provider when "
                            "the response received does not match what you are "
                            "seeing."),
    ("nursing supervisor or administrator on call", "The end of the nursing chain. "
                                                    "Use it when the medical chain "
                                                    "has not responded."),
]


def escalation_prompt(entry: Entry) -> Flag | None:
    """Whether the notifications on this entry show a stalled chain of command.

    Fires on two patterns: a notification with no response recorded, and a
    notification that produced no new orders in a note that also carries a
    critical value. Both are moments where the nurse's duty has not ended, and both
    are moments the chart routinely goes quiet.
    """
    if not entry.notifications:
        return None
    latest = entry.notifications[-1]
    if latest.escalated_to:
        return None

    stalled = latest.no_response or (not latest.response and not latest.orders_received)
    unstable = bool(critical_values(entry.vitals))
    if not stalled and not (latest.no_new_orders and unstable):
        return None

    already = {n.provider_role.lower() for n in entry.notifications}
    already |= {n.escalated_to.lower() for n in entry.notifications if n.escalated_to}
    nxt = next((name for name, _ in ESCALATION_LADDER[1:]
                if name not in already), "nursing supervisor or administrator on call")

    reason = ("No response has been recorded from the provider you notified."
              if stalled else
              "No new orders were received and this note records a critical value.")
    return Flag(
        code="escalation_available",
        severity=Severity.WARN,
        message=f"{reason} The chain of command does not end here.",
        field_path="notifications",
        suggestion=(
            f"If the patient is still unstable, escalate to the {nxt} and record "
            f"the time, the name and the response in the escalation fields. If you "
            f"escalated and it is not yet charted, add it now — an escalation that "
            f"happened and was not written down is, to a reviewer, an escalation "
            f"that did not happen."
        ),
    )


# ------------------------------------------------------------------ closed loops


# What opens a loop, and how long the window is. The 30-minute analgesic window is
# the one the specification named; the others follow the same principle — an
# intervention whose effect is not documented reads as an intervention that was
# never evaluated.
LOOP_RULES = [
    ("analgesic", ("pain", "analgesi", "morphine", "hydromorphone", "fentanyl",
                   "oxycodone", "acetaminophen", "paracetamol", "ibuprofen",
                   "ketorolac", "tramadol", "toradol", "dilaudid"), 30,
     "pain reassessment"),
    ("antipyretic", ("fever", "antipyretic", "tylenol", "temperature"), 60,
     "temperature recheck"),
    ("antihypertensive", ("blood pressure", "hypertension", "labetalol",
                          "hydralazine", "metoprolol", "nicardipine"), 30,
     "blood pressure recheck"),
    ("vasopressor", ("norepinephrine", "levophed", "vasopressin", "phenylephrine",
                     "epinephrine", "dopamine", "map"), 15,
     "haemodynamic recheck after titration"),
    ("hypoglycaemia", ("glucose", "dextrose", "d50", "glucagon", "juice",
                       "hypoglyc"), 15,
     "blood glucose recheck"),
    ("insulin", ("insulin", "novolog", "humalog", "lantus"), 60,
     "blood glucose recheck"),
    ("sedative", ("sedat", "lorazepam", "midazolam", "propofol", "precedex",
                  "dexmedetomidine", "haloperidol", "agitation"), 30,
     "sedation and airway reassessment"),
    ("opioid_reversal", ("naloxone", "narcan", "flumazenil"), 15,
     "respiratory reassessment — reversal agents are shorter-acting than what "
     "they reverse"),
    ("bronchodilator", ("albuterol", "salbutamol", "nebulis", "nebuliz",
                        "ipratropium", "wheez"), 30,
     "respiratory reassessment"),
    ("antiemetic", ("nausea", "vomit", "ondansetron", "zofran", "antiemetic"), 60,
     "nausea reassessment"),
    ("blood_product", ("transfus", "packed red", "platelets", "plasma", "cryo"), 15,
     "transfusion reaction check — vitals at 15 minutes"),
    ("restraint", ("restraint",), 15, "restraint safety check"),
]


def loops_for_entry(entry: Entry, *, at: datetime | None = None) -> list[Reassessment]:
    """Every follow-up this entry owes.

    Derived from the medications given and the interventions performed, matched on
    drug name, class and indication. Deliberately generous — a spurious reminder
    costs a click, and a missing one costs the thing this whole module exists to
    protect.
    """
    moment = at or now_utc()
    base = parse_iso(entry.event_at) or moment
    owed: list[Reassessment] = []
    seen: set[str] = set()

    def add(key: str, minutes: int, what: str, source: str) -> None:
        if key in seen:
            return
        seen.add(key)
        owed.append(Reassessment(
            trigger=f"{what} after {source}",
            trigger_entry_id=entry.entry_id,
            due_at=iso(base + timedelta(minutes=minutes)),
            window_minutes=minutes,
        ))

    haystacks: list[tuple[str, str]] = []
    for med in entry.medications:
        if med.held or med.refused:
            continue
        haystacks.append((
            f"{med.name} {med.indication} {med.route}".lower(),
            f"{med.name or 'the medication'}"
            + (f" for {med.indication}" if med.indication else ""),
        ))
    for intervention in entry.interventions:
        haystacks.append((
            f"{intervention.action} {intervention.equipment}".lower(),
            intervention.action or "the intervention",
        ))

    for haystack, source in haystacks:
        for key, needles, minutes, what in LOOP_RULES:
            if any(needle in haystack for needle in needles):
                add(f"{key}:{source}", minutes, what, source)

    # A recorded critical value owes a recheck regardless of what was given for it.
    crossed = critical_values(entry.vitals)
    if crossed:
        add("critical_recheck", 30, "repeat vital signs",
            "a critical value (" + "; ".join(crossed[:2]) + ")")

    return owed


def overdue_summary(encounter: Encounter, *,
                    at: datetime | None = None) -> list[Flag]:
    """Open loops that have passed their window."""
    flags: list[Flag] = []
    for loop in encounter.overdue_loops(at):
        late = loop.minutes_late(at)
        flags.append(Flag(
            code="loop_overdue",
            severity=Severity.WARN,
            message=f"{loop.trigger} is {late} minutes past its "
                    f"{loop.window_minutes}-minute window.",
            field_path=f"reassessment:{loop.reassessment_id}",
            suggestion=("Record the follow-up now with the time you actually "
                        "performed it, or record why it was not done. A window "
                        "that closed without either is the gap a reviewer finds. "
                        "If you did it and did not chart it, this is a late entry "
                        "— which is fine, and the tool will label it."),
        ))
    return flags


# ------------------------------------------------------------- copy-forward guard


def _normalise(text: str) -> str:
    return " ".join((text or "").lower().split())


def copy_forward_flag(encounter: Encounter, entry: Entry) -> Flag | None:
    """Refuse a note that duplicates the previous one of its kind unchanged.

    The specification asked for smart copy-paste protection forcing a manual update
    of timestamps, vitals and variance notes. This is that: the check is not "did
    you paste" — it cannot know — but "is this note distinguishable from the last
    one". A shift where four notes are byte-identical is the pattern that makes an
    entire chart worthless, because it establishes that none of the notes describe
    an actual assessment.
    """
    previous = None
    for candidate in reversed(encounter.sorted_entries()):
        if candidate.entry_id == entry.entry_id:
            continue
        if candidate.kind == entry.kind:
            previous = candidate
            break
    if previous is None:
        return None

    same_narrative = (_normalise(previous.narrative) == _normalise(entry.narrative)
                      and bool(_normalise(entry.narrative)))
    if not same_narrative:
        return None

    vitals_moved = (
        previous.vitals.narrative() != entry.vitals.narrative()
        and not entry.vitals.is_empty()
    )
    if vitals_moved:
        return None

    return Flag(
        code="copy_forward_unchanged",
        severity=Severity.BLOCK,
        message=(f"This note is identical to the {previous.kind.label.lower()} at "
                 f"{(parse_iso(previous.event_at) or now_utc()):%H:%M} and the "
                 f"vital signs have not changed."),
        field_path="narrative",
        suggestion=("Update what actually changed: the vital signs, the times, and "
                    "a sentence on how the patient differs from the last "
                    "assessment — including \"no change from the 1400 "
                    "assessment\", which is a real finding and is not the same as "
                    "a duplicated note. If nothing changed and nothing needed to, "
                    "say so in those words."),
    )


# ------------------------------------------------------------ paediatric weight


def weight_flags(encounter: Encounter, entry: Entry) -> list[Flag]:
    """The paediatric weight hard stop, plus the staleness warning.

    Two separate concerns. The block is a missing weight on a paediatric encounter
    with a medication on the note. The warning is a weight that is present but old
    — a three-day-old weight on a dehydrated infant is a dosing error waiting for
    someone to trust it.
    """
    flags: list[Flag] = []
    if not entry.medications:
        return flags

    weight = encounter.weight_kg
    on_entry = next((m.weight_kg for m in entry.medications
                     if m.weight_kg is not None), None)
    effective = on_entry if on_entry is not None else weight

    if encounter.requires_weight() and not effective:
        flags.append(Flag(
            code="paediatric_weight_required",
            severity=Severity.BLOCK,
            message="A weight in kilograms is required before a medication can be "
                    "documented on a paediatric encounter.",
            field_path="encounter.weight_kg",
            suggestion=("Record the weight in kilograms, not pounds, and record "
                        "when it was measured. Nearly every paediatric dose is "
                        "weight-based, a pounds-for-kilograms substitution is a "
                        "2.2-fold overdose, and a dose defended against a weight "
                        "that is not in the record is not defended at all."),
        ))
        return flags

    if effective and encounter.weight_measured_at:
        measured = parse_iso(encounter.weight_measured_at)
        documented = parse_iso(entry.documented_at) or now_utc()
        if measured and (documented - measured) > timedelta(hours=24):
            hours = int((documented - measured).total_seconds() // 3600)
            flags.append(Flag(
                code="weight_stale",
                severity=Severity.WARN,
                message=f"The recorded weight is {hours} hours old.",
                field_path="encounter.weight_kg",
                suggestion=("Reweigh if the plan of care allows it. Weight-based "
                            "doses drift with fluid status, and this matters most "
                            "in exactly the patients who are being actively "
                            "resuscitated."),
            ))

    # A high-alert medication with no second-nurse verification, at any age.
    for med in entry.medications:
        if med.high_alert and not med.second_nurse_verified and not med.held:
            flags.append(Flag(
                code="high_alert_no_double_check",
                severity=Severity.WARN,
                message=f"{med.name or 'A high-alert medication'} is marked "
                        f"high-alert with no independent double check recorded.",
                field_path=f"medication:{med.med_id}",
                suggestion=("Record the second nurse's initials. Insulin, heparin, "
                            "concentrated electrolytes, opioids, paralytics and "
                            "chemotherapy are the classes where a double check "
                            "measurably prevents harm, and the check is only worth "
                            "anything if it is documented."),
            ))
        if med.two_identifiers_verified is False and not med.held:
            flags.append(Flag(
                code="identifiers_not_verified",
                severity=Severity.INFO,
                message=f"Two-identifier verification is not recorded for "
                        f"{med.name or 'this medication'}.",
                field_path=f"medication:{med.med_id}",
                suggestion="Tick the verification box once you have checked two "
                           "patient identifiers against the order.",
            ))
    return flags


# -------------------------------------------------------------------- the gate


@dataclass
class Gate:
    """The answer to "can this be saved".

    `blocked` drives the disabled Save button. `overridable` tells the UI whether
    to offer the override box, which the specification's grey-out requirement needs
    in order not to trap a nurse mid-emergency.
    """

    flags: list[Flag]
    blocked: bool
    overridable: bool
    requires_notification: bool
    critical_values: list[str]
    loops: list[Reassessment]

    def as_dict(self) -> dict[str, Any]:
        return {
            "flags": [f.as_dict() for f in self.flags],
            "blocked": self.blocked,
            "overridable": self.overridable,
            "requires_notification": self.requires_notification,
            "critical_values": self.critical_values,
            "loops": [
                {"trigger": l.trigger, "due_at": l.due_at,
                 "window_minutes": l.window_minutes}
                for l in self.loops
            ],
        }


# The four block codes that cannot be overridden, and why:
#   - the never-in-a-chart language rules are policy, not judgement;
#   - a future event time is a clock problem, and the clock does not negotiate.
NON_OVERRIDABLE = {
    "incident_report", "other_patient", "blame_colleague", "admission_of_fault",
    "event_in_future",
}


def evaluate(encounter: Encounter, entry: Entry, *,
             at: datetime | None = None,
             override_reason: str = "") -> Gate:
    """Run every interlock against a candidate entry.

    Called on every keystroke-triggered preview and again on save, with the same
    code path, so what the nurse saw is what the server enforced. A front end that
    greys out its own button is a courtesy; the check that counts happens here.
    """
    moment = at or now_utc()
    flags: list[Flag] = []

    # 1. Language, across every free-text field on the entry.
    #
    # The narrative is scanned only when the nurse typed it. When it was composed
    # from the sections, its text *is* the section text, and scanning both reports
    # every flagged word twice from a single mistake — which trains the reader to
    # ignore the count.
    scanned = {
        "subjective": entry.subjective,
        "objective": entry.objective,
        "assessment": entry.assessment,
        "plan": entry.plan,
        "labs": entry.labs,
        "pending": entry.pending,
    }
    if not entry.narrative_is_derived:
        scanned["narrative"] = entry.narrative
    flags.extend(language.scan_many(scanned))
    for finding in entry.systems:
        for element_id, value in finding.findings.items():
            if isinstance(value, str) and len(value) > 30:
                flags.extend(language.scan(
                    value, field_path=f"systems.{finding.system}.{element_id}"))

    # 2. The clock.
    if entry.event_in_future(moment):
        flags.append(Flag(
            code="event_in_future",
            severity=Severity.BLOCK,
            message="The event time is in the future.",
            field_path="event_at",
            suggestion=("Set the event time to when it happened. Documenting "
                        "ahead of the clock is the shape of a pre-signed "
                        "assessment, and it is the one pattern that damages a "
                        "chart more than a missing note."),
        ))
    if entry.late_entry:
        flags.append(Flag(
            code="late_entry",
            severity=Severity.INFO,
            message=f"This will be tagged [LATE ENTRY] — the event was "
                    f"{entry.late_by_minutes} minutes before you documented it.",
            field_path="event_at",
            suggestion=("Nothing to fix. A labelled late entry is correct and "
                        "defensible; an unlabelled one that disagrees with the "
                        "medication scanner is not."),
        ))

    # 3. Critical values and the notification requirement.
    crossed = critical_values(entry.vitals)
    complete_notification = any(n.is_complete() for n in entry.notifications)
    escalated = any(n.escalated_to for n in entry.notifications)
    requires_notification = bool(crossed) and entry.kind not in (
        EntryKind.HANDOFF, EntryKind.ASSIGNMENT, EntryKind.DISCHARGE,
    )
    if requires_notification and not (complete_notification or escalated):
        flags.append(Flag(
            code="critical_value_unnotified",
            severity=Severity.BLOCK,
            message=("This note records " + "; ".join(crossed)
                     + ". Provider notification is required before it can be "
                       "saved."),
            field_path="notifications",
            suggestion=("Complete the Provider Notification block: the exact time "
                        "you called or paged, the provider's name, the method "
                        "(paged, phone, secure message or at the bedside), and "
                        "what came back. If nobody has been told yet, tell them "
                        "now — that is what this block is for. If you escalated "
                        "instead of notifying a provider, record the escalation."),
        ))

    ladder = escalation_prompt(entry)
    if ladder:
        flags.append(ladder)

    # 4. Weight, double checks, identifiers.
    flags.extend(weight_flags(encounter, entry))

    # 5. Copy-forward.
    duplicate = copy_forward_flag(encounter, entry)
    if duplicate:
        flags.append(duplicate)

    # 6. Completeness of the note itself.
    flags.extend(_completeness(entry))

    # 7. Overdue loops elsewhere on the encounter — a warning, never a block. The
    # note in front of the nurse is not the place to refuse work owed by another.
    flags.extend(overdue_summary(encounter, at=moment))

    # Two interlocks can independently notice the same thing — a critical value
    # that is also an overdue loop, say. Identical flags are collapsed so a count
    # of warnings means a count of problems.
    seen: set[tuple] = set()
    deduped: list[Flag] = []
    for flag in flags:
        key = (flag.code, flag.field_path, flag.excerpt, flag.offset)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(flag)
    flags = deduped

    blockers = [f for f in flags if f.severity is Severity.BLOCK]
    hard = [f for f in blockers if f.code in NON_OVERRIDABLE]
    overridable = bool(blockers) and not hard

    blocked = bool(hard) or (bool(blockers) and not override_reason.strip())
    if blockers and override_reason.strip() and not hard:
        flags.append(Flag(
            code="override_recorded",
            severity=Severity.INFO,
            message="Saved with an override.",
            field_path="override",
            excerpt=override_reason.strip(),
            suggestion=("The override and its reason are written into the note and "
                        "the audit trail. Complete the missing element as soon as "
                        "you can and add it as an addendum — an override followed "
                        "by completion reads as a nurse managing an emergency, "
                        "which is what happened."),
        ))

    return Gate(
        flags=flags,
        blocked=blocked,
        overridable=overridable,
        requires_notification=requires_notification,
        critical_values=crossed,
        loops=loops_for_entry(entry, at=moment),
    )


def _completeness(entry: Entry) -> list[Flag]:
    """Kind-specific gaps. Warnings, because what is missing depends on the case."""
    flags: list[Flag] = []

    def warn(code: str, message: str, suggestion: str, field_path: str = "") -> None:
        flags.append(Flag(code=code, severity=Severity.WARN, message=message,
                          suggestion=suggestion, field_path=field_path))

    if entry.kind is EntryKind.SHIFT_ASSESSMENT:
        from . import systems as systems_module
        missing = systems_module.unassessed(entry.systems)
        if missing:
            warn("systems_unassessed",
                 f"{len(missing)} body systems have no record: "
                 + ", ".join(missing) + ".",
                 "Assess them, or mark them not assessed with a reason. A blank "
                 "system and a skipped system look identical in a chart, and only "
                 "one of them is defensible.",
                 "systems")
        rubber = systems_module.wdl_without_detail(entry.systems)
        if len(rubber) >= 6:
            warn("wdl_across_the_board",
                 f"{len(rubber)} systems are marked within defined limits with no "
                 f"detail at all.",
                 "This may be entirely accurate — most patients are normal in most "
                 "systems. It is flagged because a full column of bare WDL entries "
                 "is the pattern a reviewer reads as rubber-stamping, and one "
                 "specific normal finding per system defeats that reading "
                 "completely.",
                 "systems")

    if entry.kind is EntryKind.PROVIDER_NOTIFICATION and not entry.notifications:
        warn("notification_note_without_notification",
             "This is a provider notification note with no notification recorded.",
             "Add the time, name, method and response.", "notifications")

    for notification in entry.notifications:
        if notification.is_complete() and not (
                notification.response or notification.orders_received
                or notification.no_new_orders or notification.no_response):
            warn("notification_no_outcome",
                 f"The notification to {notification.provider_name} records no "
                 f"outcome.",
                 "Record what came back: the orders, or that there were none, or "
                 "that there was no response. The outcome is the half of the "
                 "notification that a reviewer actually reads.",
                 f"notification:{notification.notification_id}")
        if notification.orders_received and not notification.read_back:
            warn("orders_not_read_back",
                 "Orders were received without a read-back recorded.",
                 "Tick read-back. A verbal order read back and verified is the "
                 "standard, and the read-back is what protects you if the order "
                 "was misheard.",
                 f"notification:{notification.notification_id}")

    for intervention in entry.interventions:
        if intervention.action and not intervention.response:
            warn("intervention_not_evaluated",
                 f"\"{intervention.action}\" has no documented response.",
                 "Record what happened after. An intervention with no evaluation "
                 "reads as an intervention nobody followed up.",
                 f"intervention:{intervention.intervention_id}")

    for med in entry.medications:
        if med.held and not med.hold_reason:
            warn("hold_without_reason",
                 f"{med.name or 'A medication'} is marked held with no reason.",
                 "Say why, and whether the provider was told. A held dose with no "
                 "reason is indistinguishable from a missed dose.",
                 f"medication:{med.med_id}")
        if med.held and med.hold_reason and not med.provider_notified_of_hold:
            warn("hold_not_notified",
                 f"{med.name or 'A medication'} was held without the provider "
                 f"being notified.",
                 "Most held doses need the prescriber to know. If your unit's "
                 "policy does not require it for this drug, tick it and move on.",
                 f"medication:{med.med_id}")
        if med.wasted_amount and not med.waste_witness_initials:
            warn("waste_without_witness",
                 f"Waste of {med.name or 'a controlled substance'} has no witness "
                 f"recorded.",
                 "A controlled-substance waste needs a witness at the time of "
                 "wasting. An unwitnessed waste is a diversion investigation "
                 "waiting to happen, and the nurse it happens to is you.",
                 f"medication:{med.med_id}")

    if entry.kind is EntryKind.REFUSAL:
        pillars = entry.module_data.get("refusal") or {}
        for key, label in (("capacity", "an assessment of decision-making capacity"),
                           ("risks_explained", "the risks explained to the patient"),
                           ("provider_notified", "notification of the attending"),
                           ("patient_quote", "the patient's own words")):
            if not str(pillars.get(key, "")).strip():
                warn(f"refusal_missing_{key}",
                     f"The refusal record is missing {label}.",
                     "All four elements are what makes a refusal defensible: the "
                     "patient had capacity, was told the risks, the attending was "
                     "informed, and the patient's decision is in their own words. "
                     "Three of four is not enough — the missing one is the one "
                     "counsel will ask about.",
                     "module_data.refusal")

    if entry.kind is EntryKind.RESTRAINT:
        restraint = entry.module_data.get("restraint") or {}
        if not str(restraint.get("order_time", "")).strip():
            warn("restraint_no_order",
                 "No order time is recorded for the restraint.",
                 "Restraints need a time-limited provider order and a documented "
                 "face-to-face evaluation within the window your policy sets. This "
                 "is among the most heavily regulated things a nurse documents.",
                 "module_data.restraint")
        for key, label in (("checks", "the safety checks performed"),
                           ("circulation", "circulation and skin checks"),
                           ("release_rom", "release and range of motion"),
                           ("needs_offered", "food, fluid and toileting offered"),
                           ("discontinuation_criteria",
                            "the behavioural criteria for discontinuation")):
            if not str(restraint.get(key, "")).strip():
                warn(f"restraint_missing_{key}",
                     f"The restraint record is missing {label}.",
                     "Each of these is separately required by the Conditions of "
                     "Participation, and each is separately asked about in a "
                     "survey or a deposition.",
                     "module_data.restraint")

    if entry.kind is EntryKind.BLOOD_PRODUCT:
        blood = entry.module_data.get("blood_product") or {}
        for key, label in (("consent", "documented consent"),
                           ("two_person_verification",
                            "two-person verification at the bedside"),
                           ("baseline_vitals", "baseline vital signs"),
                           ("unit_number", "the unit identification number")):
            if not str(blood.get(key, "")).strip():
                warn(f"blood_missing_{key}",
                     f"The transfusion record is missing {label}.",
                     "Transfusion documentation is checked line by line after any "
                     "reaction. The bedside verification by two people is the step "
                     "that prevents the error that kills.",
                     "module_data.blood_product")

    if entry.kind is EntryKind.FALL_EVENT:
        fall = entry.module_data.get("fall") or {}
        if not str(fall.get("witnessed", "")).strip():
            warn("fall_witnessed_unknown",
                 "The fall record does not say whether the fall was witnessed.",
                 "Witnessed and unwitnessed falls are documented differently: an "
                 "unwitnessed fall means the mechanism is unknown, which means a "
                 "head strike cannot be excluded, which changes the assessment "
                 "that is expected of you.",
                 "module_data.fall")
        if not str(fall.get("neuro_checks", "")).strip():
            warn("fall_no_neuro_checks",
                 "No neurological checks are recorded after the fall.",
                 "Record the checks and their times, especially if the patient is "
                 "anticoagulated. Post-fall neuro checks on an anticoagulated "
                 "patient are the single most examined element of a fall case.",
                 "module_data.fall")

    if entry.kind is EntryKind.EDUCATION:
        education = entry.module_data.get("education") or {}
        if not str(education.get("teach_back", "")).strip():
            warn("education_no_teach_back",
                 "No teach-back is recorded.",
                 "\"Verbalised understanding\" is weak. Record what the patient "
                 "said or did back: \"Patient drew up 8 units of insulin "
                 "correctly on the second attempt and stated the signs of "
                 "hypoglycaemia without prompting.\" That is evidence the "
                 "teaching worked.",
                 "module_data.education")

    return flags


# ------------------------------------------------------------------- apply loops


def register_loops(encounter: Encounter, entry: Entry, *,
                   at: datetime | None = None) -> list[Reassessment]:
    """Attach this entry's owed follow-ups to the encounter, skipping duplicates."""
    existing = {(r.trigger, r.trigger_entry_id) for r in encounter.reassessments}
    added: list[Reassessment] = []
    for loop in loops_for_entry(entry, at=at):
        if (loop.trigger, loop.trigger_entry_id) in existing:
            continue
        encounter.reassessments.append(loop)
        added.append(loop)
    return added


def satisfy_loop(encounter: Encounter, reassessment_id: str, *,
                 finding: str, at: datetime | None = None,
                 not_done_reason: str = "") -> Reassessment | None:
    """Close a loop, recording the time it was actually performed."""
    loop = next((r for r in encounter.reassessments
                 if r.reassessment_id == reassessment_id), None)
    if not loop:
        return None
    if not_done_reason.strip():
        loop.not_done_reason = not_done_reason.strip()
        return loop
    loop.performed_at = iso(at or now_utc())
    loop.finding = finding.strip()
    loop.satisfied = bool(finding.strip())
    return loop
