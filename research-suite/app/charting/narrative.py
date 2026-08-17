"""
The note composer: SBAR-SOAP hybrid, plus the macro library and handoff builders.

## Why a hybrid, and what each letter holds

The specification asked for SBAR crossed with SOAP, which is the right instinct:
SBAR is a communication format built for a phone call and SOAP is a documentation
format built for a chart, and a shift note has to do both. The mapping used here:

| Section | Holds | Why it is separate |
|---|---|---|
| **S** — Subjective | the patient's own words, verbatim, and the reason this note exists | A quotation is the patient's testimony. It is the one part of a note that cannot be characterised as the nurse's opinion. |
| **B/O** — Background and Objective | vitals, head-to-toe findings, pertinent labs, scored scales | Everything measurable, so a reader can form their own impression before yours. |
| **A** — Assessment | your clinical impression and the risk you identified | The only section where interpretation belongs. Keeping it separate is what lets the objective section stay clean. |
| **R/P** — Recommendation and Plan | interventions with route, dose and site; the provider notification; the re-evaluation; what is still pending | The four things that get dropped, in the order they get dropped. |

The order matters more than the labels. Observation before impression is what makes
a note read as an assessment rather than a conclusion looking for support.

## The macros

Six templates, each covering a situation where the words are hard to find under
pressure and the cost of getting them wrong is high. They are filled from
structured fields rather than being free-text snippets, so a macro cannot be
pasted with last patient's numbers still in it — which is the failure mode of every
snippet library in every EHR.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from . import systems as systems_module
from .models import (
    Encounter, Entry, EntryKind, Medication, ProviderNotification, Setting,
    iso, now_utc, parse_iso,
)


def _clock(value: str) -> str:
    stamp = parse_iso(value)
    return f"{stamp:%H:%M}" if stamp else "time not recorded"


# ------------------------------------------------------------------- composition


def compose(entry: Entry, encounter: Encounter, *,
            include_wdl_statement: bool = True) -> str:
    """Assemble the four sections into the note that gets transcribed.

    Sections with nothing in them are omitted rather than printed empty: a heading
    with no content under it invites the reader to wonder what was left out.
    """
    blocks: list[str] = []

    subjective = _subjective(entry)
    if subjective:
        blocks.append(f"S — Subjective\n{subjective}")

    objective = _objective(entry, include_wdl_statement=include_wdl_statement)
    if objective:
        blocks.append(f"B/O — Background and objective\n{objective}")

    assessment = _assessment(entry, encounter)
    if assessment:
        blocks.append(f"A — Assessment\n{assessment}")

    plan = _plan(entry, encounter)
    if plan:
        blocks.append(f"R/P — Response and plan\n{plan}")

    body = "\n\n".join(blocks)
    if entry.late_entry:
        body = (f"[LATE ENTRY] Event occurred at {_clock(entry.event_at)}; "
                f"documented at {_clock(entry.documented_at)}, "
                f"{entry.late_by_minutes} minutes later.\n\n" + body)
    return body


def _subjective(entry: Entry) -> str:
    parts: list[str] = []
    if entry.subjective.strip():
        parts.append(entry.subjective.strip())
    return "\n".join(parts)


def _objective(entry: Entry, *, include_wdl_statement: bool = True) -> str:
    parts: list[str] = []
    vitals = entry.vitals.narrative()
    if vitals:
        parts.append(vitals)
    if entry.objective.strip():
        parts.append(entry.objective.strip())
    systems_text = systems_module.narrate_all(
        entry.systems, include_wdl_statement=include_wdl_statement)
    if systems_text:
        parts.append(systems_text)
    for wound in entry.wounds:
        parts.append(wound.narrative())
    for scale in entry.scales:
        if scale.narrative:
            parts.append(scale.narrative)
    if entry.labs.strip():
        parts.append(f"Pertinent laboratory results: {entry.labs.strip()}")
    return "\n\n".join(p for p in parts if p)


def _assessment(entry: Entry, encounter: Encounter) -> str:
    parts: list[str] = []
    if entry.assessment.strip():
        parts.append(entry.assessment.strip())
    return "\n\n".join(parts)


def _plan(entry: Entry, encounter: Encounter) -> str:
    parts: list[str] = []

    for med in entry.medications:
        parts.append(medication_sentence(med, encounter))

    for intervention in entry.interventions:
        if not intervention.action.strip():
            continue
        sentence = f"At {_clock(intervention.performed_at)}, {intervention.action}"
        detail = [d for d in (intervention.dose, intervention.route,
                              intervention.site, intervention.equipment) if d]
        if detail:
            sentence += " (" + ", ".join(detail) + ")"
        sentence += "."
        if intervention.patient_tolerance:
            sentence += f" Patient tolerance: {intervention.patient_tolerance}."
        if intervention.response:
            sentence += (f" Re-evaluated at {_clock(intervention.evaluated_at)}: "
                         f"{intervention.response}."
                         if intervention.evaluated_at
                         else f" Response: {intervention.response}.")
        parts.append(sentence)

    for notification in entry.notifications:
        parts.append(notification.narrative())

    if entry.plan.strip():
        parts.append(entry.plan.strip())

    if entry.pending.strip():
        parts.append(f"Outstanding at the time of this note: {entry.pending.strip()}")

    return "\n\n".join(p for p in parts if p)


def medication_sentence(med: Medication, encounter: Encounter | None = None) -> str:
    """One medication administration as a defensible sentence.

    Held and refused doses get their own shapes, because a held dose documented as
    though it were given is a chart that does not match the medication record, and
    that discrepancy is found every time.
    """
    name = med.name or "medication"
    if med.held:
        text = f"{name} held"
        if med.scheduled_at:
            text += f" at the {_clock(med.scheduled_at)} scheduled time"
        text += f". Reason: {med.hold_reason or 'not recorded'}."
        if med.provider_notified_of_hold:
            text += " Prescriber notified of the held dose."
        return text
    if med.refused:
        text = (f"{name} offered at {_clock(med.given_at or med.scheduled_at)}. "
                f"Patient declined.")
        if med.pre_assessment:
            text += f" {med.pre_assessment}"
        return text

    text = f"At {_clock(med.given_at)}, administered {name}"
    if med.dose:
        text += f" {med.dose}"
    if med.dose_mg_per_kg:
        text += f" ({med.dose_mg_per_kg})"
    if med.route:
        text += f" {med.route}"
    if med.site:
        text += f" to the {med.site}"
    if med.indication:
        text += f" for {med.indication}"
    text += "."

    if med.weight_kg is not None:
        text += f" Dose calculated on a weight of {med.weight_kg:g} kg."
    if med.pre_assessment:
        text += f" Pre-administration assessment: {med.pre_assessment}."
    if med.two_identifiers_verified:
        text += " Two patient identifiers verified against the order."
    if med.high_alert and med.second_nurse_verified:
        witness = med.second_nurse_initials or "a second nurse"
        text += f" Independent double check completed with {witness}."
    if med.pump_programmed_check:
        text += " Pump settings verified against the order at the bedside."
    if med.wasted_amount:
        witness = med.waste_witness_initials or "no witness recorded"
        text += f" {med.wasted_amount} wasted, witnessed by {witness}."
    if med.effect:
        when = _clock(med.effect_checked_at) if med.effect_checked_at else ""
        text += (f" Re-evaluated at {when}: {med.effect}." if when
                 else f" Effect: {med.effect}.")
    if med.reaction:
        text += f" Reaction observed: {med.reaction}."
    return text


# ------------------------------------------------------------------------ macros


@dataclass
class Macro:
    macro_id: str
    label: str
    purpose: str
    fields: list[dict[str, Any]] = field(default_factory=list)
    guidance: str = ""


MACROS: list[Macro] = [
    Macro(
        macro_id="chain_of_command",
        label="Chain of command notification",
        purpose="A provider was told about a change in status. This is the sentence "
                "that decides most nursing malpractice cases.",
        guidance=("Fill every field. The four that matter are the exact time, the "
                  "provider's name, how you reached them, and what came back — a "
                  "notification missing any one of those is a notification a "
                  "reviewer will treat as not having happened."),
        fields=[
            {"key": "time", "label": "Exact time of notification", "type": "time",
             "required": True},
            {"key": "provider", "label": "Provider name", "type": "text",
             "required": True},
            {"key": "role", "label": "Role", "type": "text"},
            {"key": "method", "label": "Method", "type": "select",
             "options": ["paged", "phone", "secure text", "in person", "overhead"],
             "required": True},
            {"key": "status_change", "label": "Change in status reported",
             "type": "text", "required": True},
            {"key": "data", "label": "Data reported", "type": "textarea"},
            {"key": "orders", "label": "Orders received", "type": "textarea"},
            {"key": "response_time", "label": "Time of response", "type": "time"},
        ],
    ),
    Macro(
        macro_id="refusal",
        label="Refusal of care or against medical advice",
        purpose="A patient declined something. Four pillars make it defensible.",
        guidance=("Capacity, risks explained, attending notified, and the patient's "
                  "own words. Three of the four is not enough — whichever one is "
                  "missing is the one counsel will build the case on. Quote the "
                  "patient exactly, including profanity; a sanitised quote is a "
                  "weaker quote."),
        fields=[
            {"key": "time", "label": "Time of refusal", "type": "time",
             "required": True},
            {"key": "what", "label": "What was declined", "type": "text",
             "required": True},
            {"key": "capacity", "label": "Capacity assessment", "type": "textarea",
             "required": True,
             "hint": "Oriented, able to state the decision and its consequences in "
                     "their own words, no evidence of intoxication or delirium."},
            {"key": "risks_explained", "label": "Risks explained", "type": "textarea",
             "required": True},
            {"key": "patient_quote", "label": "Patient's own words", "type": "textarea",
             "required": True},
            {"key": "provider_notified", "label": "Attending notified — name and time",
             "type": "text", "required": True},
            {"key": "alternatives", "label": "Alternatives offered", "type": "textarea"},
            {"key": "form_signed", "label": "AMA form signed", "type": "select",
             "options": ["signed", "declined to sign", "not applicable"]},
            {"key": "safety", "label": "Safety measures and follow-up offered",
             "type": "textarea"},
        ],
    ),
    Macro(
        macro_id="education",
        label="Patient education with teach-back",
        purpose="Teaching was done and understanding was demonstrated.",
        guidance=("\"Verbalised understanding\" is the weakest phrase in nursing "
                  "documentation. Record what the patient said or did back to you. "
                  "If an interpreter was used, name the language and the "
                  "interpreter's identifier — education delivered in a language "
                  "the patient does not speak is not education, and this is a "
                  "common and expensive gap."),
        fields=[
            {"key": "time", "label": "Time", "type": "time", "required": True},
            {"key": "topic", "label": "Topic taught", "type": "text", "required": True},
            {"key": "method", "label": "Method", "type": "select",
             "options": ["verbal", "written material provided", "demonstration",
                         "video", "verbal with written material"]},
            {"key": "learner", "label": "Who was taught", "type": "text",
             "hint": "The patient, or a named relationship — \"spouse at the "
                     "bedside\". Not a name."},
            {"key": "interpreter", "label": "Interpreter used", "type": "text",
             "hint": "Language and interpreter identifier, or \"not required\"."},
            {"key": "teach_back", "label": "Teach-back demonstrated",
             "type": "textarea", "required": True},
            {"key": "barriers", "label": "Barriers identified", "type": "textarea"},
            {"key": "follow_up", "label": "Reinforcement planned", "type": "textarea"},
        ],
    ),
    Macro(
        macro_id="restraint",
        label="Restraint episode",
        purpose="Restraints were applied or continued. Among the most heavily "
                "regulated things a nurse documents.",
        guidance=("Every field here maps to a separately auditable requirement: a "
                  "time-limited order, less-restrictive alternatives tried first, "
                  "safety checks at your policy's interval, circulation and skin, "
                  "release and range of motion, food, fluid and toileting offered, "
                  "and the behavioural criteria that will end the restraint. A "
                  "surveyor checks them one at a time."),
        fields=[
            {"key": "time", "label": "Time applied or continued", "type": "time",
             "required": True},
            {"key": "type", "label": "Type", "type": "select",
             "options": ["soft wrist bilateral", "soft wrist unilateral",
                         "soft ankle", "mitts", "vest", "four-point",
                         "enclosure bed", "chemical restraint"], "required": True},
            {"key": "behaviour", "label": "Behaviour necessitating restraint",
             "type": "textarea", "required": True,
             "hint": "Describe actions. \"Pulled out a peripheral line and "
                     "attempted to climb over the bed rail twice\" — not "
                     "\"combative\"."},
            {"key": "alternatives", "label": "Less restrictive alternatives tried",
             "type": "textarea", "required": True},
            {"key": "order_time", "label": "Provider order — name and time",
             "type": "text", "required": True},
            {"key": "face_to_face", "label": "Face-to-face evaluation time",
             "type": "text"},
            {"key": "checks", "label": "Safety checks performed with times",
             "type": "textarea", "required": True},
            {"key": "circulation", "label": "Circulation and skin under the device",
             "type": "textarea", "required": True},
            {"key": "release_rom", "label": "Release and range of motion with times",
             "type": "textarea", "required": True},
            {"key": "needs_offered", "label": "Food, fluid and toileting offered",
             "type": "textarea", "required": True},
            {"key": "discontinuation_criteria",
             "label": "Behavioural criteria for discontinuation", "type": "textarea",
             "required": True},
            {"key": "family_notified", "label": "Family notified", "type": "text"},
        ],
    ),
    Macro(
        macro_id="fall",
        label="Fall event",
        purpose="A patient fell. What was in place before it matters as much as what "
                "happened after.",
        guidance=("Witnessed and unwitnessed falls are documented differently: if "
                  "nobody saw it, the mechanism is unknown and a head strike "
                  "cannot be excluded, which changes what is expected of your "
                  "assessment. Record the precautions that were already in place — "
                  "that is the question a claim turns on — and the neurological "
                  "checks with their times, especially on an anticoagulated "
                  "patient."),
        fields=[
            {"key": "time", "label": "Time found or witnessed", "type": "time",
             "required": True},
            {"key": "witnessed", "label": "Witnessed", "type": "select",
             "options": ["witnessed by staff", "witnessed by family",
                         "unwitnessed — patient found", "unwitnessed — patient "
                         "reported afterwards"], "required": True},
            {"key": "found_how", "label": "How the patient was found",
             "type": "textarea", "required": True},
            {"key": "patient_account", "label": "Patient's account, in their words",
             "type": "textarea"},
            {"key": "precautions_in_place",
             "label": "Fall precautions in place before the fall", "type": "textarea",
             "required": True},
            {"key": "head_strike", "label": "Head strike", "type": "select",
             "options": ["no head strike observed or reported",
                         "head strike observed", "head strike reported by patient",
                         "cannot be excluded — unwitnessed"], "required": True},
            {"key": "anticoagulated", "label": "On anticoagulation", "type": "select",
             "options": ["no", "yes — name the agent", "unknown"]},
            {"key": "injury_assessment", "label": "Head-to-toe injury assessment",
             "type": "textarea", "required": True},
            {"key": "neuro_checks", "label": "Neurological checks with times",
             "type": "textarea", "required": True},
            {"key": "vitals_after", "label": "Vital signs after the fall",
             "type": "textarea"},
            {"key": "provider_notified", "label": "Provider notified — name and time",
             "type": "text", "required": True},
            {"key": "family_notified", "label": "Family notified — time", "type": "text"},
            {"key": "interventions_after",
             "label": "Interventions and precautions added afterwards",
             "type": "textarea"},
        ],
    ),
    Macro(
        macro_id="blood_product",
        label="Blood product administration",
        purpose="A blood product was transfused. Checked line by line after any "
                "reaction.",
        guidance=("The bedside verification by two people is the step that prevents "
                  "the error that kills. Baseline vitals, vitals at 15 minutes, and "
                  "vitals at completion are the three that a reaction "
                  "investigation looks for."),
        fields=[
            {"key": "product", "label": "Product", "type": "select",
             "options": ["packed red blood cells", "platelets", "fresh frozen plasma",
                         "cryoprecipitate", "albumin", "whole blood"],
             "required": True},
            {"key": "unit_number", "label": "Unit identification number",
             "type": "text", "required": True},
            {"key": "consent", "label": "Consent documented", "type": "text",
             "required": True},
            {"key": "two_person_verification",
             "label": "Two-person bedside verification — both initials",
             "type": "text", "required": True},
            {"key": "baseline_vitals", "label": "Baseline vital signs",
             "type": "textarea", "required": True},
            {"key": "start_time", "label": "Start time", "type": "time",
             "required": True},
            {"key": "vitals_15", "label": "Vital signs at 15 minutes",
             "type": "textarea"},
            {"key": "vitals_completion", "label": "Vital signs at completion",
             "type": "textarea"},
            {"key": "stop_time", "label": "Completion time", "type": "time"},
            {"key": "volume", "label": "Volume infused", "type": "text"},
            {"key": "reaction", "label": "Reaction", "type": "textarea",
             "hint": "If any: what you observed, when you stopped the infusion, "
                     "what you did with the bag and tubing, who you notified."},
        ],
    ),
]


MACRO_BY_ID = {macro.macro_id: macro for macro in MACROS}


def macro_catalogue() -> list[dict[str, Any]]:
    return [
        {"macro_id": m.macro_id, "label": m.label, "purpose": m.purpose,
         "guidance": m.guidance, "fields": m.fields}
        for m in MACROS
    ]


def render_macro(macro_id: str, values: dict[str, Any]) -> str:
    """Turn filled macro fields into note text.

    Each renderer is written out rather than templated generically, because the
    sentence order carries meaning: precautions before the fall, then the fall, then
    the assessment, then the notification. A generic field-by-field dump would
    produce grammatical text in an order no reviewer reads in.
    """
    def value(key: str, default: str = "") -> str:
        return str(values.get(key, "") or default).strip()

    def quote(text: str) -> str:
        """A patient's words, punctuated once.

        The quotation carries its own terminal period inside the closing mark —
        US convention for a quoted complete sentence — so the sentence must not
        add a second one after it. Getting this wrong produces `"…".` which reads
        as sloppy in exactly the notes that are read most carefully.
        """
        cleaned = text.strip().strip('"“”').rstrip()
        if cleaned and cleaned[-1] not in ".!?":
            cleaned += "."
        return f'Patient stated, "{cleaned}"'

    if macro_id == "chain_of_command":
        time = value("time", "time not recorded")
        provider = value("provider", "the provider")
        role = value("role")
        who = f"{provider} ({role})" if role else provider
        method = value("method")
        method_phrase = ProviderNotification(method=method).method_phrase()
        text = f"At {time}, notified {who}"
        if method_phrase:
            text += f" {method_phrase}"
        text += f" regarding {value('status_change', 'a change in status')}."
        if value("data"):
            text += f" Reported {value('data')}."
        orders = value("orders")
        response_time = value("response_time")
        if orders:
            prefix = f"At {response_time}, o" if response_time else "O"
            text += f" {prefix}rders received for {orders}."
        else:
            text += " No new orders received."
        text += " Continued to monitor."
        return text

    if macro_id == "refusal":
        text = (f"At {value('time', 'time not recorded')}, "
                f"{value('what', 'the treatment')} was offered and the patient "
                f"declined.")
        if value("capacity"):
            text += (f" Decision-making capacity assessed: {value('capacity')}.")
        if value("risks_explained"):
            text += (f" Risks and likely consequences of declining were explained: "
                     f"{value('risks_explained')}.")
        if value("alternatives"):
            text += f" Alternatives offered: {value('alternatives')}."
        if value("patient_quote"):
            text += f" {quote(value('patient_quote'))}"
        if value("provider_notified"):
            text += f" Attending notified: {value('provider_notified')}."
        form = value("form_signed")
        if form and form != "not applicable":
            text += f" Against-medical-advice documentation {form}."
        if value("safety"):
            text += f" {value('safety')}"
            if not value("safety").endswith("."):
                text += "."
        text += (" Patient advised that the offer remains open and that they may "
                 "change their decision at any time.")
        return text

    if macro_id == "education":
        text = (f"At {value('time', 'time not recorded')}, provided education on "
                f"{value('topic', 'the plan of care')}")
        learner = value("learner")
        if learner:
            text += f" to {learner}"
        method = value("method")
        if method:
            text += f" ({method})"
        text += "."
        interpreter = value("interpreter")
        if interpreter and interpreter.lower() not in ("not required", "none", "n/a"):
            text += f" Interpreter used: {interpreter}."
        if value("teach_back"):
            text += f" Understanding demonstrated: {value('teach_back')}."
        if value("barriers"):
            text += f" Barriers identified: {value('barriers')}."
        if value("follow_up"):
            text += f" Reinforcement planned: {value('follow_up')}."
        return text

    if macro_id == "restraint":
        text = (f"At {value('time', 'time not recorded')}, "
                f"{value('type', 'restraint')} applied or continued.")
        if value("behaviour"):
            text += f" Behaviour necessitating restraint: {value('behaviour')}."
        if value("alternatives"):
            text += (f" Less restrictive alternatives attempted first: "
                     f"{value('alternatives')}.")
        if value("order_time"):
            text += f" Provider order: {value('order_time')}."
        if value("face_to_face"):
            text += f" Face-to-face evaluation: {value('face_to_face')}."
        if value("checks"):
            text += f" Safety checks: {value('checks')}."
        if value("circulation"):
            text += (f" Circulation and skin under the device: "
                     f"{value('circulation')}.")
        if value("release_rom"):
            text += f" Release and range of motion: {value('release_rom')}."
        if value("needs_offered"):
            text += f" Offered: {value('needs_offered')}."
        if value("discontinuation_criteria"):
            text += (f" Criteria for discontinuation: "
                     f"{value('discontinuation_criteria')}. Restraint will be "
                     f"removed as soon as those criteria are met.")
        if value("family_notified"):
            text += f" Family notified: {value('family_notified')}."
        return text

    if macro_id == "fall":
        text = (f"Fall at {value('time', 'time not recorded')}. Witnessed status: "
                f"{value('witnessed', 'not recorded')}.")
        if value("found_how"):
            text += f" {value('found_how')}"
            if not value("found_how").endswith("."):
                text += "."
        if value("patient_account"):
            text += f" {quote(value('patient_account'))}"
        if value("precautions_in_place"):
            text += (f" Fall precautions in place at the time: "
                     f"{value('precautions_in_place')}.")
        if value("head_strike"):
            text += f" Head strike: {value('head_strike')}."
        anticoag = value("anticoagulated")
        if anticoag and anticoag != "no":
            text += f" Anticoagulation: {anticoag}."
        if value("injury_assessment"):
            text += f" Injury assessment: {value('injury_assessment')}."
        if value("vitals_after"):
            text += f" Vital signs after the event: {value('vitals_after')}."
        if value("neuro_checks"):
            text += f" Neurological checks: {value('neuro_checks')}."
        if value("provider_notified"):
            text += f" Provider notified: {value('provider_notified')}."
        if value("family_notified"):
            text += f" Family notified at {value('family_notified')}."
        if value("interventions_after"):
            text += (f" Precautions added following the event: "
                     f"{value('interventions_after')}.")
        return text

    if macro_id == "blood_product":
        text = (f"{value('product', 'Blood product')}, unit "
                f"{value('unit_number', 'number not recorded')}, transfused.")
        if value("consent"):
            text += f" Consent: {value('consent')}."
        if value("two_person_verification"):
            text += (f" Two-person bedside verification of patient identifiers, "
                     f"product, unit number and expiry completed by "
                     f"{value('two_person_verification')}.")
        if value("baseline_vitals"):
            text += f" Baseline vital signs: {value('baseline_vitals')}."
        if value("start_time"):
            text += f" Infusion started at {value('start_time')}."
        if value("vitals_15"):
            text += f" Vital signs at 15 minutes: {value('vitals_15')}."
        if value("vitals_completion"):
            text += f" Vital signs at completion: {value('vitals_completion')}."
        if value("stop_time"):
            text += f" Infusion completed at {value('stop_time')}."
        if value("volume"):
            text += f" Volume infused: {value('volume')}."
        reaction = value("reaction")
        text += (f" Reaction: {reaction}." if reaction
                 else " No signs or symptoms of a transfusion reaction observed "
                      "during the infusion or at completion.")
        return text

    raise ValueError(f"unknown macro {macro_id!r}")


def missing_macro_fields(macro_id: str, values: dict[str, Any]) -> list[str]:
    macro = MACRO_BY_ID.get(macro_id)
    if not macro:
        return []
    return [
        f["label"] for f in macro.fields
        if f.get("required") and not str(values.get(f["key"], "") or "").strip()
    ]


# ----------------------------------------------------------------------- handoff


# What the receiving unit needs that the sending unit tends not to think about.
# Built from the specification's two named transitions, plus the two others that
# occur just as often on a real shift.
HANDOFF_ROUTES = {
    "er_to_icu": {
        "label": "Emergency department to intensive care",
        "focus": [
            ("code_status", "Code status and whether it was confirmed with the "
                            "patient or a surrogate", True),
            ("airway", "Airway stability — patent, at risk, or secured, and by "
                       "what", True),
            ("lines", "Every line placed in the department, with site, gauge and "
                      "whether placement was sterile", True),
            ("last_bolus", "Time and volume of the last fluid bolus", True),
            ("last_antibiotic", "Time of the last antibiotic and which one", True),
            ("time_zero", "Time zero for any bundle in progress — sepsis, stroke, "
                          "trauma", False),
            ("pending_results", "Results still pending and who is chasing them",
             False),
            ("imaging", "Imaging done and not yet read", False),
            ("family", "Who is present, who has been updated and what they were "
                       "told", False),
        ],
        "why": ("The department's clock is not the unit's clock. Antibiotic and "
                "bolus times are what the receiving team dose off, and a line "
                "placed under emergency conditions has to be flagged so it can be "
                "changed within the window."),
    },
    "icu_to_med_surg": {
        "label": "Intensive care to medical-surgical",
        "focus": [
            ("weaning", "Where the patient is in any weaning process — oxygen, "
                        "sedation, pressors, insulin", True),
            ("mobility", "Mobility status and how many people it takes", True),
            ("remaining_devices", "Every drain, tube and line still in, with "
                                  "insertion dates and the current indication",
             True),
            ("baseline_mental_status", "Mental status baseline, and whether "
                                       "delirium is resolving or active", True),
            ("triggers", "What would send this patient back — the specific "
                         "parameters", True),
            ("nutrition", "Diet, swallow status and feeding route", False),
            ("skin", "Pressure injuries present, and the prevention plan", False),
            ("goals", "Goals of care conversations that have happened", False),
        ],
        "why": ("A patient leaving intensive care is at their most vulnerable to "
                "under-monitoring. The parameters that would trigger a return have "
                "to be handed over explicitly, because the receiving nurse's "
                "threshold for calling is calibrated to a different population."),
    },
    "shift_to_shift": {
        "label": "Shift to shift",
        "focus": [
            ("overnight_events", "What changed this shift", True),
            ("open_loops", "Reassessments owed and when they are due", True),
            ("pending_tasks", "Tasks handed over, with times", True),
            ("provider_contacts", "Who has been called and what they said", True),
            ("family", "Family present and what they have been told", False),
            ("watch_items", "What to watch for and what to do about it", True),
        ],
        "why": ("The handover is where an owed reassessment goes missing. Naming the "
                "open loops and their due times transfers them rather than "
                "dropping them."),
    },
    "to_procedure": {
        "label": "To a procedure or another department",
        "focus": [
            ("consent", "Consent signed and in the chart", True),
            ("npo_status", "Time the patient was last fed", True),
            ("allergies", "Allergies and reactions", True),
            ("anticoagulation", "Last dose of any anticoagulant", True),
            ("access", "Working vascular access and its size", True),
            ("mobility_transport", "How the patient is being transported and with "
                                   "what monitoring", True),
            ("baseline_vitals", "Vital signs immediately before transport", True),
        ],
        "why": ("A patient off the unit is a patient whose monitoring has gaps. The "
                "pre-transport vitals are the baseline anything that happens is "
                "compared against."),
    },
}


def handoff_template(route: str) -> dict[str, Any]:
    spec = HANDOFF_ROUTES.get(route)
    if not spec:
        raise ValueError(f"unknown handoff route {route!r}")
    return {
        "route": route,
        "label": spec["label"],
        "why": spec["why"],
        "fields": [
            {"key": key, "label": label, "required": required}
            for key, label, required in spec["focus"]
        ],
    }


def handoff_routes() -> list[dict[str, Any]]:
    return [
        {"route": key, "label": spec["label"], "why": spec["why"]}
        for key, spec in HANDOFF_ROUTES.items()
    ]


def render_handoff(route: str, values: dict[str, Any],
                   encounter: Encounter) -> str:
    """The handoff as a document, with the unfilled required items named.

    Unfilled items are printed rather than omitted. A handoff that silently drops
    the airway line is worse than one that says the airway was not handed over,
    because the receiving nurse cannot know what they were not told.
    """
    spec = HANDOFF_ROUTES.get(route)
    if not spec:
        raise ValueError(f"unknown handoff route {route!r}")

    lines = [f"Handoff — {spec['label']}",
             f"Encounter: {encounter.local_label or 'unlabelled'}"
             + (f" ({encounter.initials})" if encounter.initials else "")]
    if encounter.code_status:
        lines.append(f"Code status: {encounter.code_status}")
    if encounter.allergies:
        lines.append(f"Allergies: {encounter.allergies}")
    if encounter.isolation:
        lines.append(f"Isolation: {encounter.isolation}")
    if encounter.weight_kg is not None:
        lines.append(f"Weight: {encounter.weight_kg:g} kg")
    lines.append("")

    omitted: list[str] = []
    for key, label, required in spec["focus"]:
        text = str(values.get(key, "") or "").strip()
        if text:
            lines.append(f"{label}: {text}")
        elif required:
            lines.append(f"{label}: NOT HANDED OVER")
            omitted.append(label)

    devices = encounter.lines_drains_airways or []
    if devices:
        lines.append("")
        lines.append("Lines, drains and airways:")
        for device in devices:
            parts = [str(device.get("kind", "device"))]
            for field_name in ("site", "size", "inserted_at", "indication",
                              "dressing"):
                if device.get(field_name):
                    parts.append(f"{field_name.replace('_', ' ')} "
                                 f"{device[field_name]}")
            lines.append("  - " + ", ".join(parts))

    open_loops = encounter.open_loops()
    if open_loops:
        lines.append("")
        lines.append("Reassessments owed:")
        for loop in open_loops:
            lines.append(f"  - {loop.trigger}, due {_clock(loop.due_at)}"
                         + (" — OVERDUE" if loop.is_overdue() else ""))

    untranscribed = encounter.untranscribed()
    if untranscribed:
        lines.append("")
        lines.append(f"Notes composed here but not yet transcribed into the EHR: "
                     f"{len(untranscribed)}. Transcribe them before you leave — "
                     f"the receiving nurse cannot see this tool.")

    if omitted:
        lines.append("")
        lines.append("Required items not handed over: " + ", ".join(omitted) + ".")

    return "\n".join(lines)
