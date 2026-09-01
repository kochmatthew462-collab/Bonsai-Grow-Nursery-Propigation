"""
Specialty modules: what each setting documents that the others do not.

Four modules, plus the time-critical bundles that cut across them.

The modules are not four different note formats. The SBAR-SOAP composer and the
head-to-toe assessment are the same everywhere — a patient is a patient. What
changes is the extra structured block a setting needs, the scales it reaches for
first, and the reassessment interval its patients are held to.

## Where the real difference is

Each module exists because one thing about that setting is documented badly
almost everywhere:

* **Emergency** — *time to intervention*. Everything in an emergency chart is
  read against a clock, and the interval that matters is arrival-to-action. The
  module makes each of those intervals a field rather than something a reviewer
  has to reconstruct from timestamps scattered across a record.
* **Intensive care** — *why a drip was titrated*. Flowsheets capture the new rate
  automatically; nothing captures the reason. "Norepinephrine increased to 8
  mcg/min" documents an action. "Norepinephrine increased by 2 mcg/min to
  maintain a MAP above 65; MAP was 58 on the previous reading" documents nursing
  judgement, and only the second one defends the nurse who titrated.
* **Pediatrics** — *the weight, and who was at the bedside*. Weight-based dosing
  is enforced as a hard stop in `interlocks.weight_flags`. Who was present is
  here because consent, education and any allegation about supervision all turn
  on it.
* **Medical-surgical** — *the assignment, and what education actually landed*.
  With five or six patients the honest constraint is time, and the two things
  that suffer are documented teaching and documented rounding.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .models import Setting


@dataclass
class Field:
    key: str
    label: str
    kind: str = "text"          # text, textarea, time, select, number, checkbox
    options: list[str] = field(default_factory=list)
    hint: str = ""
    required: bool = False


@dataclass
class Block:
    """A named group of fields inside a specialty module."""

    block_id: str
    label: str
    why: str = ""
    fields: list[Field] = field(default_factory=list)
    repeatable: bool = False


@dataclass
class Module:
    setting: Setting
    label: str
    summary: str
    default_reassess_minutes: int
    priority_scales: list[str] = field(default_factory=list)
    blocks: list[Block] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "setting": self.setting.value,
            "label": self.label,
            "summary": self.summary,
            "default_reassess_minutes": self.default_reassess_minutes,
            "priority_scales": self.priority_scales,
            "blocks": [
                {
                    "block_id": b.block_id,
                    "label": b.label,
                    "why": b.why,
                    "repeatable": b.repeatable,
                    "fields": [
                        {"key": f.key, "label": f.label, "kind": f.kind,
                         "options": f.options, "hint": f.hint,
                         "required": f.required}
                        for f in b.fields
                    ],
                }
                for b in self.blocks
            ],
        }


# ------------------------------------------------------------------- emergency


EMERGENCY = Module(
    setting=Setting.EMERGENCY,
    label="Emergency department",
    summary=("Undifferentiated patients, a clock on everything, and a "
             "reassessment owed after every intervention. The primary survey is "
             "first because an emergency note that starts with a chief complaint "
             "has already skipped the part that keeps the patient alive."),
    default_reassess_minutes=30,
    priority_scales=["esi", "gcs", "nihss", "nrs", "lund_browder", "qsofa", "pat"],
    blocks=[
        Block(
            block_id="primary_survey",
            label="Primary survey — ABCDE",
            why=("Charted in order and charted every time, including when it is "
                 "normal. A documented patent airway at triage is what makes a "
                 "later airway event a change rather than a discovery."),
            fields=[
                Field("time", "Time of primary survey", "time", required=True),
                Field("airway", "A — Airway", "select", required=True, options=[
                    "Patent, speaking in full sentences",
                    "Patent, maintaining own airway",
                    "At risk — pooling secretions",
                    "At risk — reduced level of consciousness",
                    "Partially obstructed — stridor",
                    "Obstructed", "Secured — endotracheal tube",
                    "Secured — supraglottic airway",
                    "Secured — tracheostomy"]),
                Field("breathing", "B — Breathing", "select", required=True, options=[
                    "Bilateral equal air entry, unlaboured",
                    "Increased work of breathing",
                    "Reduced air entry — specify side",
                    "Absent air entry — specify side",
                    "Bag-mask ventilation in progress",
                    "Mechanically ventilated"]),
                Field("circulation", "C — Circulation", "select", required=True,
                      options=[
                          "Warm and well perfused, radial pulses present",
                          "Tachycardic, peripherally warm",
                          "Cool peripheries, delayed capillary refill",
                          "Weak or absent radial pulses",
                          "Active haemorrhage — site controlled",
                          "Active haemorrhage — not controlled",
                          "Cardiac arrest"]),
                Field("disability", "D — Disability", "select", required=True,
                      options=["Alert, moving all four limbs",
                               "Responds to voice", "Responds to pain",
                               "Unresponsive", "New focal deficit",
                               "Seizure activity", "Post-ictal"]),
                Field("exposure", "E — Exposure and environment", "textarea",
                      hint="Temperature, what was exposed and found, warming or "
                           "cooling measures, and whether dignity was maintained."),
                Field("glucose", "Point-of-care glucose", "number",
                      hint="On every altered patient. A hypoglycaemic patient "
                           "charted as intoxicated is a recurring, entirely "
                           "avoidable catastrophe."),
                Field("interventions_during",
                      "Interventions performed during the primary survey",
                      "textarea"),
            ],
        ),
        Block(
            block_id="secondary_survey",
            label="Secondary survey",
            why=("Head-to-toe plus history. The mechanism and the last oral intake "
                 "are the two items that later decisions depend on and that "
                 "nobody can reconstruct afterwards."),
            fields=[
                Field("chief_complaint", "Chief complaint in the patient's words",
                      "textarea", required=True,
                      hint="Verbatim, in quotation marks. This is the patient's "
                           "own account and it is exempt from the "
                           "objective-language filter."),
                Field("onset", "Onset and time of onset", "text", required=True),
                Field("mechanism", "Mechanism of injury or illness", "textarea"),
                Field("history", "Relevant history, medications and allergies",
                      "textarea"),
                Field("last_intake", "Last oral intake — time", "text"),
                Field("last_menstrual", "Last menstrual period, if applicable",
                      "text"),
                Field("tetanus", "Tetanus status, if applicable", "text"),
                Field("focused_exam", "Focused examination findings", "textarea"),
            ],
        ),
        Block(
            block_id="timing",
            label="Time to intervention",
            why=("Every interval here is a quality measure somewhere and a "
                 "discovery request everywhere. Recording them as they happen is "
                 "the only way they are accurate."),
            fields=[
                Field("arrival", "Arrival time", "time", required=True),
                Field("triage", "Triage time", "time"),
                Field("first_provider_contact",
                      "Exact time the provider was at the bedside", "time",
                      hint="Not the time they were paged, and not the time they "
                           "acknowledged. The time they were physically present. "
                           "This is a different fact and it is the one that gets "
                           "asked about."),
                Field("first_ecg", "First ECG obtained", "time"),
                Field("first_analgesia", "First analgesia given", "time"),
                Field("first_antibiotic", "First antibiotic given", "time"),
                Field("first_imaging", "First imaging performed", "time"),
                Field("disposition_decision", "Disposition decision time", "time"),
                Field("departure", "Time the patient left the department", "time"),
                Field("delays", "Delays and their causes", "textarea",
                      hint="Record the delay and the reason factually. Do not name "
                           "another patient, and do not characterise staffing — "
                           "that belongs in the assignment record."),
            ],
        ),
        Block(
            block_id="reassessment",
            label="Reassessment after intervention",
            why=("The department's core documentation failure is a patient who was "
                 "treated and not looked at again. Every intervention gets one of "
                 "these."),
            repeatable=True,
            fields=[
                Field("intervention", "Intervention", "text", required=True),
                Field("performed_at", "Performed at", "time", required=True),
                Field("reassessed_at", "Reassessed at", "time", required=True),
                Field("finding", "Finding on reassessment", "textarea",
                      required=True),
                Field("escalated", "Escalated as a result", "textarea"),
            ],
        ),
    ],
)


# ------------------------------------------------------------------ intensive care


ICU = Module(
    setting=Setting.ICU,
    label="Intensive care",
    summary=("Hourly and quarter-hourly data, invasive devices, and titrated "
             "infusions. The module's centre of gravity is the titration record, "
             "because that is the piece of ICU nursing judgement that flowsheets "
             "capture worst."),
    default_reassess_minutes=60,
    priority_scales=["rass", "cam_icu", "cpot", "gcs", "sofa", "apache_ii",
                     "braden"],
    blocks=[
        Block(
            block_id="haemodynamics",
            label="Haemodynamics and support",
            why=("Which numbers are measured and which are derived matters when a "
                 "pressor is being titrated to a MAP. A cuff MAP and an arterial "
                 "line MAP are not interchangeable and the note should say which "
                 "one the titration was made against."),
            fields=[
                Field("time", "Time", "time", required=True),
                Field("arterial_line", "Arterial line in place", "select",
                      options=["No — cuff pressures", "Yes — radial",
                               "Yes — femoral", "Yes — brachial",
                               "Yes — other site"]),
                Field("map_source", "MAP source", "select",
                      options=["Arterial line", "Calculated from cuff"],
                      required=True),
                Field("cvp", "Central venous pressure", "number"),
                Field("cardiac_output", "Cardiac output or index", "text"),
                Field("urine_output_hourly", "Urine output this hour, mL", "number"),
                Field("fluid_balance", "Running fluid balance", "text"),
                Field("lactate", "Most recent lactate", "text"),
                Field("ventilator", "Ventilator settings", "textarea",
                      hint="Mode, set rate, tidal volume, PEEP, FiO2, and the "
                           "measured values you are seeing."),
                Field("sedation_target", "Sedation target", "text",
                      hint="The ordered RASS target. A sedation assessment is "
                           "meaningless without the target it is measured "
                           "against."),
            ],
        ),
        Block(
            block_id="titration",
            label="Infusion titration — with the reason",
            why=("The single most important block in this module. A rate change "
                 "with no reason recorded is an action; a rate change with the "
                 "parameter, the reading and the target is nursing judgement. "
                 "Only the second one is defensible, and only the second one "
                 "shows the nurse was titrating rather than guessing."),
            repeatable=True,
            fields=[
                Field("time", "Time of change", "time", required=True),
                Field("drug", "Infusion", "text", required=True),
                Field("previous_rate", "Rate before", "text", required=True),
                Field("new_rate", "Rate after", "text", required=True),
                Field("direction", "Direction", "select", required=True,
                      options=["increased", "decreased", "held", "restarted",
                               "discontinued"]),
                Field("parameter", "Parameter titrated to", "text", required=True,
                      hint="\"MAP above 65\", \"RASS -1 to 0\", \"heart rate below "
                           "110\". Copy it from the order."),
                Field("reading", "Reading that prompted the change", "text",
                      required=True,
                      hint="The actual value you saw. \"MAP 58\" — this is the "
                           "clause that makes the titration reasonable on its "
                           "face."),
                Field("response", "Response after the change", "textarea",
                      required=True),
                Field("response_time", "Time of the response reading", "time"),
                Field("within_order", "Within the ordered range", "select",
                      options=["Yes", "No — provider notified"]),
            ],
        ),
        Block(
            block_id="lda",
            label="Lines, drains and airways",
            why=("Each device carries an insertion date and a current indication, "
                 "and both are checked daily. A device left in without a "
                 "documented reason is how a catheter-associated infection "
                 "becomes an indefensible one."),
            repeatable=True,
            fields=[
                Field("kind", "Device", "select", required=True, options=[
                    "Peripheral intravenous catheter",
                    "Midline catheter",
                    "Peripherally inserted central catheter",
                    "Central venous catheter",
                    "Arterial line", "Dialysis catheter",
                    "Endotracheal tube", "Tracheostomy",
                    "Nasogastric tube", "Orogastric tube",
                    "Gastrostomy tube", "Indwelling urinary catheter",
                    "Chest tube", "Surgical drain",
                    "External ventricular drain", "Epidural catheter",
                    "Intraosseous access", "Pacing wires"]),
                Field("site", "Site and side", "text", required=True),
                Field("size", "Size or gauge", "text"),
                Field("inserted_at", "Insertion date and time", "text",
                      required=True),
                Field("inserted_by", "Inserted by", "text"),
                Field("indication", "Current indication", "textarea", required=True,
                      hint="Today's reason, not the admission reason. \"Still in\" "
                           "is not an indication."),
                Field("dressing", "Dressing and site condition", "select", options=[
                    "Clean, dry and intact",
                    "Changed this shift — clean, dry and intact",
                    "Soiled — changed", "Loose — reinforced",
                    "Redness at the site", "Drainage at the site",
                    "Tenderness on palpation"]),
                Field("output", "Output — volume and character", "text"),
                Field("securement", "Securement verified", "checkbox"),
                Field("necessity_reviewed", "Ongoing necessity reviewed today",
                      "checkbox"),
                Field("removal_plan", "Plan for removal", "text"),
            ],
        ),
        Block(
            block_id="high_frequency",
            label="Quarter-hourly observations",
            why=("For a patient on a titrating infusion or in the first hour after "
                 "a major change. Recorded as a series so the trend is visible in "
                 "one place rather than spread across a shift."),
            repeatable=True,
            fields=[
                Field("time", "Time", "time", required=True),
                Field("observation", "Observation", "textarea", required=True),
                Field("action", "Action taken", "textarea"),
            ],
        ),
    ],
)


# ------------------------------------------------------------------- paediatrics


PEDIATRIC = Module(
    setting=Setting.PEDIATRIC,
    label="Pediatrics",
    summary=("Weight in kilograms before any medication — enforced as a hard stop, "
             "not a reminder — age-normed vital signs, and a record of who was at "
             "the bedside."),
    default_reassess_minutes=60,
    priority_scales=["pat", "pews", "flacc", "wong_baker", "gcs", "lund_browder"],
    blocks=[
        Block(
            block_id="weight_and_dosing",
            label="Weight and dosing basis",
            why=("Nearly every paediatric dose is weight-based, a "
                 "pounds-for-kilograms substitution is a 2.2-fold overdose, and a "
                 "dose defended against a weight that is not in the record is not "
                 "defended at all. `interlocks.weight_flags` refuses to save a "
                 "medication on a paediatric encounter without this."),
            fields=[
                Field("weight_kg", "Weight in kilograms", "number", required=True,
                      hint="Kilograms only. If the scale reads pounds, convert and "
                           "record the conversion."),
                Field("weight_method", "How the weight was obtained", "select",
                      required=True,
                      options=["Measured on a bed or chair scale",
                               "Measured on a standing scale",
                               "Measured on an infant scale",
                               "Stated by the caregiver — not yet verified",
                               "Estimated from a length-based tape",
                               "Estimated from age — verify as soon as possible"]),
                Field("weight_measured_at", "Time weighed", "time", required=True),
                Field("length_cm", "Length or height in centimetres", "number"),
                Field("dosing_weight", "Dosing weight used, if different", "text",
                      hint="For an obese or oedematous child the dosing weight may "
                           "not be the measured weight. If it differs, say so and "
                           "say why."),
                Field("allergies", "Allergies and reactions", "textarea"),
            ],
        ),
        Block(
            block_id="bedside_presence",
            label="Who was at the bedside",
            why=("Consent, education and any allegation about supervision all turn "
                 "on who was present. Record the relationship, never a name."),
            fields=[
                Field("time", "Time", "time"),
                Field("present", "Present at the bedside", "select", options=[
                    "Mother", "Father", "Both parents", "Legal guardian",
                    "Grandparent", "Other relative", "Foster carer",
                    "Nobody present", "Sitter or staff member",
                    "Child protective services representative"], required=True),
                Field("consent_capable",
                      "Person present able to consent for treatment", "select",
                      options=["Yes", "No — guardian being contacted",
                               "Not applicable"]),
                Field("interpreter", "Interpreter used — language and identifier",
                      "text"),
                Field("safeguarding", "Safeguarding concerns", "textarea",
                      hint="If there are concerns, document the objective "
                           "observations only and escalate per policy. Do not "
                           "record conclusions about anyone's conduct."),
            ],
        ),
        Block(
            block_id="age_norms",
            label="Age-normed observations",
            why=("A heart rate of 150 is a crisis in an adult and normal in an "
                 "infant. Recording the age band the observations were judged "
                 "against makes the assessment interpretable."),
            fields=[
                Field("age_band", "Age band", "select", required=True, options=[
                    "Under 3 months", "3 to 12 months", "1 to 3 years",
                    "3 to 5 years", "5 to 8 years", "8 to 12 years",
                    "12 to 18 years"]),
                Field("normal_range_used", "Normal range applied", "text",
                      hint="From your unit's chart. Recording which chart you used "
                           "matters when they disagree."),
                Field("feeding", "Feeding and hydration", "textarea",
                      hint="Wet nappies, oral intake, last feed. In a small child "
                           "this is the fluid-status assessment."),
                Field("play", "Activity, play and interaction", "textarea",
                      hint="A child who has stopped playing is a child who is "
                           "unwell, and it is often the first sign."),
            ],
        ),
    ],
)


# --------------------------------------------------------------- medical-surgical


MED_SURG = Module(
    setting=Setting.MED_SURG,
    label="Medical-surgical and telemetry",
    summary=("Five or six patients, so the honest constraint is time. This module "
             "documents the assignment, the rounding, the fall-prevention measures "
             "actually in place, and what education the patient could give back."),
    default_reassess_minutes=240,
    priority_scales=["braden", "morse", "caprini", "ciwa_ar", "nrs", "mews",
                     "news2", "cam"],
    blocks=[
        Block(
            block_id="assignment",
            label="Assignment and staffing",
            why=("Kept on the encounter's shift context, not in a patient's note. "
                 "A contemporaneous record that you carried nine patients and "
                 "raised it is strong evidence about the conditions of care; the "
                 "same sentence inside a patient's chart reads as an excuse and "
                 "hands the plaintiff a theory. The objective-language filter "
                 "moves it here for you."),
            fields=[
                Field("patient_count", "Patients assigned", "number",
                      required=True),
                Field("expected_ratio", "Unit's expected ratio", "text",
                      hint="Typically one nurse to five or six on a "
                           "medical-surgical unit."),
                Field("acuity", "Acuity factors", "textarea",
                      hint="Fresh post-operative patients, one-to-one "
                           "observations, active withdrawal, total care — the "
                           "things that make a count of five not a count of "
                           "five."),
                Field("support_staff", "Support available", "text"),
                Field("raised_with", "Concern raised with", "text"),
                Field("raised_at", "Time raised", "time"),
                Field("concern", "Concern as you stated it", "textarea"),
                Field("response", "Response received", "textarea"),
            ],
        ),
        Block(
            block_id="rounding",
            label="Rounding and safety checks",
            why=("Hourly rounding is a fall-prevention intervention and is only "
                 "worth anything if the times are recorded. \"Hourly rounding "
                 "performed\" with no times is an assertion; a list of times is "
                 "evidence."),
            repeatable=True,
            fields=[
                Field("time", "Time", "time", required=True),
                Field("checks", "Checked", "select", options=[
                    "Pain, toileting, position, possessions within reach",
                    "Call light within reach and answered",
                    "Bed low, brakes locked, alarm on",
                    "Patient asleep — observed respirations, did not wake",
                    "Patient out of the room", "Family present"]),
                Field("finding", "Anything found", "textarea"),
            ],
        ),
        Block(
            block_id="discharge_planning",
            label="Discharge planning and education",
            why=("Whether the patient understood is the question, and \"verbalised "
                 "understanding\" does not answer it. Teach-back does."),
            fields=[
                Field("barriers", "Discharge barriers identified", "textarea"),
                Field("teaching_topics", "Topics taught this shift", "textarea"),
                Field("teach_back", "What the patient demonstrated back",
                      "textarea",
                      hint="Concretely. \"Drew up 8 units correctly on the second "
                           "attempt and named three signs of hypoglycaemia without "
                           "prompting.\""),
                Field("materials", "Written material provided", "text"),
                Field("interpreter", "Interpreter used — language and identifier",
                      "text",
                      hint="Education given in a language the patient does not "
                           "speak is not education. This is a common and expensive "
                           "gap."),
                Field("caregiver_taught", "Caregiver taught — relationship only",
                      "text"),
                Field("referrals", "Referrals made", "textarea"),
                Field("transport", "Discharge transport and condition on leaving",
                      "textarea"),
                Field("follow_up", "Follow-up arranged", "textarea"),
            ],
        ),
        Block(
            block_id="prevention_bundle",
            label="Prevention measures in place",
            why=("After an adverse event the question is which measures were "
                 "already in place. That answer has to be in the chart before the "
                 "event, which means it goes in every shift assessment."),
            fields=[
                Field("fall_measures", "Fall prevention in place", "textarea",
                      required=True),
                Field("pressure_measures", "Pressure injury prevention in place",
                      "textarea"),
                Field("vte_measures", "Venous thromboembolism prophylaxis",
                      "textarea"),
                Field("infection_measures",
                      "Catheter and line infection prevention", "textarea"),
                Field("aspiration_measures", "Aspiration precautions", "textarea"),
                Field("declined", "Measures the patient declined, with education "
                                  "given", "textarea",
                      hint="A declined intervention with documented education is "
                           "defensible. An intervention that was simply not in "
                           "place is not."),
            ],
        ),
    ],
)


MODULES = {
    Setting.EMERGENCY: EMERGENCY,
    Setting.ICU: ICU,
    Setting.PEDIATRIC: PEDIATRIC,
    Setting.MED_SURG: MED_SURG,
}


def module_for(setting: Setting | str) -> Module | None:
    if isinstance(setting, str):
        try:
            setting = Setting(setting)
        except ValueError:
            return None
    return MODULES.get(setting)


def catalogue() -> list[dict[str, Any]]:
    return [module.as_dict() for module in MODULES.values()]


def missing_required(setting: Setting | str, block_id: str,
                     values: dict[str, Any]) -> list[str]:
    module = module_for(setting)
    if not module:
        return []
    block = next((b for b in module.blocks if b.block_id == block_id), None)
    if not block:
        return []
    return [f.label for f in block.fields
            if f.required and not str(values.get(f.key, "") or "").strip()]


# ------------------------------------------------------------- time-critical bundles


@dataclass
class Bundle:
    """A time-critical protocol whose elements are defined by their clock.

    These cut across settings — sepsis presents to the emergency department, is
    recognised on a ward, and is managed in intensive care — so they live here
    rather than inside one module. Each element records a target interval and the
    time it was actually done, and `bundle_status` computes what is outstanding.

    The targets are the published ones. They are shown so the nurse can see the
    clock; the tool does not decide whether the bundle applies, because that is a
    clinical judgement and getting it wrong in either direction is harmful.
    """

    bundle_id: str
    label: str
    citation: str
    why: str
    elements: list[dict[str, Any]] = field(default_factory=list)
    # Which element every interval is measured from. Defaults to the first
    # element, which is right for sepsis (time zero) but wrong for stroke: the
    # door-to-imaging and door-to-needle targets run from ARRIVAL, while last
    # known well is what determines treatment eligibility. Measuring door-to-CT
    # from last known well would report a 45-minute interval as a 105-minute one
    # and make a compliant department look non-compliant.
    anchor_key: str = ""

    def anchor(self) -> str:
        return self.anchor_key or (self.elements[0]["key"] if self.elements else "")


BUNDLES = [
    Bundle(
        bundle_id="sepsis",
        label="Sepsis bundle",
        citation="Centers for Medicare and Medicaid Services. Severe sepsis and "
                 "septic shock early management bundle (SEP-1). National Hospital "
                 "Inpatient Quality Measures.",
        why=("Every element is timed from a single point — time zero, the moment "
             "of presentation with the documented signs. If time zero is not "
             "recorded, none of the intervals can be shown to have been met, and "
             "the bundle is scored as failed regardless of what was actually "
             "done."),
        elements=[
            {"key": "time_zero", "label": "Time zero — presentation with signs",
             "target_minutes": 0, "required": True,
             "hint": "The clock every other element is measured from. Record it "
                     "first."},
            {"key": "lactate", "label": "Initial lactate drawn",
             "target_minutes": 180},
            {"key": "blood_cultures",
             "label": "Blood cultures drawn — before antibiotics",
             "target_minutes": 180,
             "hint": "Before antibiotics. If antibiotics went first, say so and "
                     "say why; cultures drawn after are still worth drawing but "
                     "the sequence has to be honest."},
            {"key": "antibiotics", "label": "Broad-spectrum antibiotics given",
             "target_minutes": 180},
            {"key": "fluids", "label": "30 mL/kg crystalloid started",
             "target_minutes": 180,
             "hint": "Weight-based. Record the weight used and the volume ordered, "
                     "and if the volume was reduced for heart failure or renal "
                     "disease, record who ordered the reduction."},
            {"key": "repeat_lactate", "label": "Repeat lactate, if initial elevated",
             "target_minutes": 360},
            {"key": "vasopressors",
             "label": "Vasopressors for hypotension after fluids",
             "target_minutes": 360},
            {"key": "reassessment", "label": "Documented volume-status reassessment",
             "target_minutes": 360},
        ],
    ),
    Bundle(
        bundle_id="stroke",
        label="Acute stroke timing",
        citation="Powers, W. J., Rabinstein, A. A., Ackerson, T., Adeoye, O. M., "
                 "Bambakidis, N. C., Becker, K., … Tirschwell, D. L. (2019). "
                 "Guidelines for the early management of patients with acute "
                 "ischemic stroke. Stroke, 50(12), e344-e418.",
        why=("Two clocks, and confusing them is the classic error. Last known well "
             "sets the treatment window and is the field the entire decision hangs "
             "on — get it from whoever saw the patient last, quote them, and "
             "record who they were by relationship. The door-to-imaging and "
             "door-to-needle targets, by contrast, are all measured from arrival, "
             "which is why arrival is this bundle's anchor."),
        anchor_key="arrival",
        elements=[
            {"key": "last_known_well", "label": "Last known well — time and source",
             "target_minutes": 0, "required": True,
             "hint": "Quote the source. \"Spouse states the patient was normal at "
                     "0630 when they left for work.\" This sets the treatment "
                     "window; it is not what the door-to-imaging targets are "
                     "measured from."},
            {"key": "arrival", "label": "Arrival time", "target_minutes": 0,
             "required": True,
             "hint": "Every target below is measured from this time."},
            {"key": "stroke_alert", "label": "Stroke alert activated",
             "target_minutes": 15},
            {"key": "provider_assessment", "label": "Provider at the bedside",
             "target_minutes": 10},
            {"key": "nihss", "label": "NIHSS performed", "target_minutes": 15},
            {"key": "ct_started", "label": "Imaging started", "target_minutes": 25},
            {"key": "ct_read", "label": "Imaging interpreted", "target_minutes": 45},
            {"key": "glucose", "label": "Point-of-care glucose",
             "target_minutes": 15},
            {"key": "thrombolytic_decision", "label": "Thrombolytic decision made",
             "target_minutes": 45},
            {"key": "thrombolytic_given", "label": "Thrombolytic given, if indicated",
             "target_minutes": 60},
            {"key": "swallow_screen", "label": "Swallow screen before anything oral",
             "target_minutes": 240,
             "hint": "Before any oral intake including medication. A stroke patient "
                     "given oral medication before a swallow screen is a "
                     "documented, preventable aspiration risk."},
        ],
    ),
    Bundle(
        bundle_id="stemi",
        label="ST-elevation myocardial infarction timing",
        citation="O'Gara, P. T., Kushner, F. G., Ascheim, D. D., Casey, D. E., "
                 "Chung, M. K., de Lemos, J. A., … Zhao, D. X. (2013). ACCF/AHA "
                 "guideline for the management of ST-elevation myocardial "
                 "infarction. Circulation, 127(4), e362-e425.",
        why="Door to balloon, and the ECG that starts the clock.",
        elements=[
            {"key": "arrival", "label": "Arrival time", "target_minutes": 0,
             "required": True},
            {"key": "first_ecg", "label": "First ECG", "target_minutes": 10},
            {"key": "ecg_interpreted", "label": "ECG interpreted by a provider",
             "target_minutes": 15},
            {"key": "cath_lab_activated", "label": "Catheterisation laboratory "
                                                  "activated", "target_minutes": 20},
            {"key": "aspirin", "label": "Aspirin given", "target_minutes": 30},
            {"key": "device_time", "label": "Device time", "target_minutes": 90},
        ],
    ),
]


BUNDLE_BY_ID = {bundle.bundle_id: bundle for bundle in BUNDLES}


def bundle_catalogue() -> list[dict[str, Any]]:
    return [
        {"bundle_id": b.bundle_id, "label": b.label, "citation": b.citation,
         "why": b.why, "elements": b.elements}
        for b in BUNDLES
    ]


def bundle_status(bundle_id: str, values: dict[str, Any]) -> dict[str, Any]:
    """What is recorded, what is outstanding, and which intervals were exceeded.

    Times come in as HH:MM strings, because that is what a nurse reads off a wall
    clock and what the elements are documented in. Intervals are computed only when
    both the anchor and the element are present; a missing anchor makes every
    interval unknown, which is exactly the point the sepsis bundle's `why` makes.
    """
    bundle = BUNDLE_BY_ID.get(bundle_id)
    if not bundle:
        raise ValueError(f"unknown bundle {bundle_id!r}")

    anchor_key = bundle.anchor()
    anchor = _minutes(values.get(anchor_key, ""))
    anchor_element = next((e for e in bundle.elements if e["key"] == anchor_key),
                         bundle.elements[0])

    rows: list[dict[str, Any]] = []
    outstanding: list[str] = []
    exceeded: list[str] = []
    for element in bundle.elements:
        raw = str(values.get(element["key"], "") or "").strip()
        recorded = _minutes(raw)
        interval = None
        over = False
        if recorded is not None and anchor is not None and element["key"] != anchor_key:
            interval = recorded - anchor
            if interval < 0:
                # Crossed midnight, or the element genuinely preceded time zero.
                interval += 24 * 60
            target = element.get("target_minutes") or 0
            over = bool(target and interval > target)
        if not raw:
            outstanding.append(element["label"])
        if over:
            exceeded.append(f"{element['label']} at {interval} minutes against a "
                            f"{element['target_minutes']}-minute target")
        rows.append({
            "key": element["key"],
            "label": element["label"],
            "recorded": raw,
            "target_minutes": element.get("target_minutes"),
            "interval_minutes": interval,
            "exceeded": over,
            "hint": element.get("hint", ""),
        })

    return {
        "bundle_id": bundle_id,
        "label": bundle.label,
        "anchor_recorded": anchor is not None,
        "anchor_label": anchor_element["label"],
        "rows": rows,
        "outstanding": outstanding,
        "exceeded": exceeded,
        "note": (
            "" if anchor is not None else
            f"{anchor_element['label']} is not recorded, so no interval in "
            f"this bundle can be computed or evidenced. Record it first."
        ),
    }


def _minutes(text: str) -> int | None:
    """Parse HH:MM or HHMM into minutes past midnight."""
    raw = str(text or "").strip()
    if not raw:
        return None
    digits = raw.replace(":", "").replace(".", "")
    if not digits.isdigit() or len(digits) not in (3, 4):
        return None
    digits = digits.zfill(4)
    hours, mins = int(digits[:2]), int(digits[2:])
    if hours > 23 or mins > 59:
        return None
    return hours * 60 + mins


def render_bundle(bundle_id: str, values: dict[str, Any]) -> str:
    """The bundle as note text, naming what was not done."""
    status = bundle_status(bundle_id, values)
    lines = [f"{status['label']} — timing record"]
    for row in status["rows"]:
        if row["recorded"]:
            piece = f"  {row['label']}: {row['recorded']}"
            if row["interval_minutes"] is not None:
                piece += f" ({row['interval_minutes']} minutes from "
                piece += f"{status['anchor_label'].lower()}"
                if row["target_minutes"]:
                    piece += f", target {row['target_minutes']}"
                piece += ")"
                if row["exceeded"]:
                    piece += " — target exceeded"
            lines.append(piece)
        else:
            lines.append(f"  {row['label']}: not recorded")
    if status["note"]:
        lines.append("")
        lines.append(status["note"])
    return "\n".join(lines)
