"""
The head-to-toe assessment, with charting by exception.

Eight body systems, each a list of elements with a defined-normal value and the
abnormal findings that are worth a click rather than free text.

## What "within defined limits" has to mean

Charting by exception is defensible only when the document says what the limits
were. "Neuro WDL" in isolation is worth nothing in a deposition — the question
is always *"what did you actually check?"*, and a nurse who cannot answer it has
charted nothing at all. So:

* every system carries a `wdl_statement` spelling out precisely what WDL asserts
  for that system, and it is printed in the note rather than referenced;
* marking a system WDL records the statement's text into the entry, so a later
  change to the wording cannot retroactively alter what an old note claimed;
* a system can be WDL **with exceptions**, which is the ordinary case and renders
  as "within defined limits except …";
* a system that was not assessed is recorded as not assessed, with a reason.
  There is no third state. An assessment silently left blank looks, later, exactly
  like an assessment that was skipped and hidden.

That last point is the one that matters most. The failure mode this module is
built against is not the nurse who charts too little; it is the nurse who charts
"WDL" across eight systems in nine seconds on a patient they have not seen, and
then has to explain the timestamps.

## Element vocabularies

Findings are picked from lists rather than typed, for three reasons: it is faster
at 0300, it produces consistent language a reviewer can follow across a shift, and
it keeps the objective-language filter from having to fight the nurse over wording
that a dropdown could have got right the first time. Anything the lists do not
cover goes in the system's free-text field, which *is* run through the filter.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .models import SystemFinding, iso, now_utc


@dataclass
class Element:
    """One thing you check within a system."""

    element_id: str
    label: str
    normal: str = ""
    options: list[str] = field(default_factory=list)
    free_text: bool = False
    hint: str = ""
    # Elements that are a task rather than an observation — "turned every two
    # hours", "bed alarm on" — render as a performed statement rather than a
    # finding, and their absence is a gap rather than an abnormality.
    is_task: bool = False


@dataclass
class System:
    system_id: str
    label: str
    wdl_statement: str
    elements: list[Element] = field(default_factory=list)
    settings: tuple[str, ...] = ()

    def element(self, element_id: str) -> Element | None:
        return next((e for e in self.elements if e.element_id == element_id), None)

    def as_dict(self) -> dict[str, Any]:
        return {
            "system_id": self.system_id,
            "label": self.label,
            "wdl_statement": self.wdl_statement,
            "settings": list(self.settings),
            "elements": [
                {
                    "element_id": e.element_id,
                    "label": e.label,
                    "normal": e.normal,
                    "options": e.options,
                    "free_text": e.free_text,
                    "hint": e.hint,
                    "is_task": e.is_task,
                }
                for e in self.elements
            ],
        }


SYSTEMS: list[System] = [

    System(
        system_id="neuro",
        label="Neurological",
        wdl_statement=(
            "Alert and oriented to person, place, time and situation. Speech clear "
            "and appropriate. Pupils equal, round and reactive to light. Moves all "
            "four extremities on command with symmetrical strength against "
            "resistance. Sensation intact to light touch in all four extremities. "
            "No new deficit from the documented baseline."
        ),
        elements=[
            Element("loc", "Level of consciousness", normal="Alert",
                    options=["Alert", "Drowsy but rouses to voice",
                             "Rouses to touch", "Rouses to painful stimulus only",
                             "Unresponsive", "Sedated — see RASS"]),
            Element("orientation", "Orientation",
                    normal="Oriented ×4 — person, place, time, situation",
                    options=["Oriented ×4 — person, place, time, situation",
                             "Oriented ×3 — disoriented to time",
                             "Oriented ×2 — person and place",
                             "Oriented ×1 — person only",
                             "Disoriented",
                             "Non-verbal — unable to assess orientation"],
                    hint="State which spheres, not just the number — \"oriented ×3\" "
                         "does not say which one was lost, and that is the "
                         "clinically important part."),
            Element("pupils", "Pupils",
                    normal="PERRLA — equal, round, reactive to light bilaterally",
                    options=["PERRLA — equal, round, reactive to light bilaterally",
                             "Sluggish bilaterally", "Unequal — right larger",
                             "Unequal — left larger", "Non-reactive bilaterally",
                             "Pinpoint", "Dilated and fixed",
                             "Unable to assess — swelling or dressing"]),
            Element("speech", "Speech",
                    normal="Clear and appropriate",
                    options=["Clear and appropriate", "Slurred", "Expressive aphasia",
                             "Receptive aphasia", "Garbled", "Non-verbal",
                             "Baseline dysarthria"]),
            Element("strength", "Motor strength",
                    normal="5/5 and symmetrical in all four extremities",
                    options=["5/5 and symmetrical in all four extremities",
                             "Generalised weakness, symmetrical",
                             "Right-sided weakness", "Left-sided weakness",
                             "Upper extremity weakness", "Lower extremity weakness",
                             "Flaccid", "Unable to follow commands to test"],
                    hint="Graded 0-5: 0 none, 1 flicker, 2 movement with gravity "
                         "eliminated, 3 against gravity only, 4 against some "
                         "resistance, 5 full."),
            Element("sensation", "Sensation",
                    normal="Intact to light touch in all four extremities",
                    options=["Intact to light touch in all four extremities",
                             "Numbness — specify distribution",
                             "Tingling — specify distribution",
                             "Absent below a level — specify",
                             "Unable to assess"]),
            Element("headache_dizziness", "Headache or dizziness",
                    normal="Denies headache and dizziness",
                    options=["Denies headache and dizziness", "Reports headache",
                             "Reports dizziness", "Reports both"]),
            Element("neuro_notes", "Additional neurological findings",
                    free_text=True),
        ],
    ),

    System(
        system_id="cardiovascular",
        label="Cardiovascular",
        wdl_statement=(
            "S1 and S2 audible with no murmur, rub or gallop. Rhythm regular. "
            "Peripheral pulses 2+ and equal bilaterally. Capillary refill under "
            "three seconds. No oedema. Skin warm and dry with colour appropriate "
            "to the patient's baseline. No chest pain reported."
        ),
        elements=[
            Element("heart_sounds", "Heart sounds",
                    normal="S1 and S2 audible, no murmur, rub or gallop",
                    options=["S1 and S2 audible, no murmur, rub or gallop",
                             "Systolic murmur", "Diastolic murmur",
                             "Friction rub", "S3 gallop", "S4 gallop",
                             "Distant or muffled", "Unable to auscultate"]),
            Element("rhythm", "Rhythm",
                    normal="Regular",
                    options=["Regular", "Irregularly irregular",
                             "Regularly irregular",
                             "Atrial fibrillation", "Atrial flutter",
                             "Sinus tachycardia", "Sinus bradycardia",
                             "Paced", "Frequent premature ventricular complexes",
                             "Frequent premature atrial complexes",
                             "Not on telemetry"]),
            Element("pulses", "Peripheral pulses",
                    normal="2+ and equal bilaterally",
                    options=["2+ and equal bilaterally", "1+ — diminished",
                             "3+ — bounding", "0 — absent, specify site",
                             "Doppler required", "Unequal — specify site"],
                    hint="Graded 0-3+: 0 absent, 1+ diminished, 2+ normal, "
                         "3+ bounding."),
            Element("cap_refill", "Capillary refill",
                    normal="Under three seconds",
                    options=["Under three seconds", "Three to four seconds",
                             "Over four seconds", "Unable to assess — nail polish "
                             "or trauma"]),
            Element("oedema", "Oedema",
                    normal="None",
                    options=["None", "1+ trace, pitting", "2+ mild, pitting",
                             "3+ moderate, pitting", "4+ severe, pitting",
                             "Non-pitting", "Generalised or anasarca"],
                    hint="Record the site and whether it is new. Bilateral "
                         "dependent oedema and a new unilateral calf are entirely "
                         "different findings."),
            Element("skin_temp_colour", "Skin temperature and colour",
                    normal="Warm and dry, colour appropriate to baseline",
                    options=["Warm and dry, colour appropriate to baseline",
                             "Cool", "Cold", "Diaphoretic", "Pale", "Flushed",
                             "Mottled", "Cyanotic — central",
                             "Cyanotic — peripheral", "Jaundiced", "Ashen or grey"]),
            Element("chest_pain", "Chest pain",
                    normal="Reports no chest pain",
                    options=["Reports no chest pain",
                             "Reports chest pain — see focused assessment",
                             "Unable to report"]),
            Element("telemetry", "Telemetry", normal="",
                    options=["Continuous telemetry, leads in place and tracing "
                             "clear", "Telemetry alarms set and audible",
                             "Lead artefact — leads replaced",
                             "Not on telemetry"],
                    is_task=True,
                    hint="Alarm settings and the fact you could hear them are "
                         "worth charting. An alarm-related death is nearly always "
                         "a case about whether the alarm was on and audible."),
            Element("cardiac_notes", "Additional cardiovascular findings",
                    free_text=True),
        ],
    ),

    System(
        system_id="respiratory",
        label="Respiratory",
        wdl_statement=(
            "Breath sounds clear and equal in all auscultated fields. Respirations "
            "regular, unlaboured, no accessory muscle use and no retractions. No "
            "cough. Oxygen saturation within the range ordered for this patient on "
            "the delivery method documented."
        ),
        elements=[
            Element("breath_sounds", "Breath sounds",
                    normal="Clear and equal in all fields",
                    options=["Clear and equal in all fields",
                             "Diminished at the bases",
                             "Diminished unilaterally — specify side",
                             "Crackles at the bases", "Crackles throughout",
                             "Expiratory wheeze", "Inspiratory wheeze",
                             "Rhonchi, clearing with cough", "Stridor",
                             "Pleural friction rub", "Absent — specify field"]),
            Element("effort", "Respiratory effort",
                    normal="Regular and unlaboured, no accessory muscle use",
                    options=["Regular and unlaboured, no accessory muscle use",
                             "Mildly increased work of breathing",
                             "Accessory muscle use", "Intercostal retractions",
                             "Subcostal retractions", "Nasal flaring",
                             "Tripod positioning", "Paradoxical breathing",
                             "Apnoeic episodes", "Ventilated — see ventilator "
                             "settings"]),
            Element("cough", "Cough",
                    normal="No cough",
                    options=["No cough", "Dry, non-productive",
                             "Productive — clear sputum",
                             "Productive — white sputum",
                             "Productive — yellow sputum",
                             "Productive — green sputum",
                             "Productive — blood-tinged sputum",
                             "Productive — frank blood",
                             "Weak, unable to clear secretions"]),
            Element("oxygen", "Oxygen delivery",
                    normal="Room air",
                    options=["Room air", "Nasal cannula — specify L/min",
                             "Simple face mask", "Venturi mask",
                             "Non-rebreather", "High-flow nasal cannula",
                             "Continuous positive airway pressure",
                             "Bilevel positive airway pressure",
                             "Tracheostomy collar", "Mechanical ventilation"]),
            Element("resp_interventions", "Respiratory interventions", normal="",
                    options=["Incentive spirometry encouraged",
                             "Head of bed elevated", "Suctioned — oral",
                             "Suctioned — nasotracheal",
                             "Suctioned — endotracheal", "Chest physiotherapy",
                             "Nebulised treatment given",
                             "Repositioned for ventilation"],
                    is_task=True),
            Element("resp_notes", "Additional respiratory findings", free_text=True),
        ],
    ),

    System(
        system_id="gastrointestinal",
        label="Gastrointestinal",
        wdl_statement=(
            "Abdomen soft, non-tender and non-distended. Bowel sounds active in "
            "all four quadrants. Tolerating the prescribed diet without nausea or "
            "vomiting. Bowel pattern at the patient's baseline."
        ),
        elements=[
            Element("bowel_sounds", "Bowel sounds",
                    normal="Active in all four quadrants",
                    options=["Active in all four quadrants", "Hypoactive",
                             "Hyperactive", "Absent — specify quadrant",
                             "Absent in all four quadrants"]),
            Element("abdomen", "Abdomen",
                    normal="Soft, non-tender, non-distended",
                    options=["Soft, non-tender, non-distended", "Soft but tender",
                             "Firm", "Distended", "Rigid", "Guarding",
                             "Rebound tenderness", "Visible peristalsis",
                             "Surgical dressing in place", "Ostomy — see output"]),
            Element("diet_tolerance", "Diet and tolerance",
                    normal="Tolerating the prescribed diet",
                    options=["Tolerating the prescribed diet",
                             "Nil by mouth", "Clear liquids tolerated",
                             "Full liquids tolerated", "Poor oral intake",
                             "Enteral feeding — see rate",
                             "Parenteral nutrition",
                             "Aspiration precautions in place",
                             "Dysphagia — thickened liquids"]),
            Element("nausea_vomiting", "Nausea and vomiting",
                    normal="Denies nausea, no vomiting",
                    options=["Denies nausea, no vomiting", "Reports nausea",
                             "Vomited once — describe",
                             "Vomited more than once — describe",
                             "Retching without emesis",
                             "Bilious emesis", "Coffee-ground emesis",
                             "Frank blood in emesis"]),
            Element("last_bm", "Last bowel movement",
                    normal="",
                    options=["This shift", "Within 24 hours", "24 to 48 hours ago",
                             "48 to 72 hours ago", "More than 72 hours ago",
                             "Unknown — patient unable to report"],
                    hint="Record the date and character, not just \"yes\". Three "
                         "days without a bowel movement on opioids is a finding, "
                         "and it is one that is regularly missed."),
            Element("stool_character", "Stool character", normal="",
                    options=["Formed, brown", "Soft", "Loose", "Watery",
                             "Hard or pellet-like", "Melaena — black and tarry",
                             "Frank blood", "Clay-coloured", "Mucus present"],
                    free_text=False),
            Element("gi_notes", "Additional gastrointestinal findings",
                    free_text=True),
        ],
    ),

    System(
        system_id="genitourinary",
        label="Genitourinary",
        wdl_statement=(
            "Voiding without difficulty. Urine clear, yellow and without odour. "
            "Output adequate for body weight. Continent at the patient's baseline. "
            "No suprapubic tenderness."
        ),
        elements=[
            Element("voiding", "Voiding pattern",
                    normal="Voiding without difficulty",
                    options=["Voiding without difficulty", "Frequency",
                             "Urgency", "Hesitancy", "Dysuria",
                             "Incontinent — stress", "Incontinent — urge",
                             "Incontinent — functional", "Retention",
                             "Anuric", "Oliguric", "Dialysis-dependent"]),
            Element("urine_colour", "Urine colour and clarity",
                    normal="Clear, yellow",
                    options=["Clear, yellow", "Clear, straw-coloured",
                             "Dark amber, concentrated", "Cloudy",
                             "Sediment present", "Blood-tinged",
                             "Frank blood", "Tea-coloured",
                             "Clots present"]),
            Element("urine_odour", "Urine odour",
                    normal="No unusual odour",
                    options=["No unusual odour", "Strong or foul",
                             "Ammoniacal", "Sweet or fruity"]),
            Element("output", "Output", normal="",
                    options=["Adequate for body weight",
                             "Under 0.5 mL/kg/hr — recorded and escalated",
                             "Under 30 mL/hr for two consecutive hours",
                             "Measured — see intake and output record"],
                    hint="For an adult, under 0.5 mL/kg/hr over consecutive hours "
                         "is oliguria and is worth a notification, not just a "
                         "flowsheet entry."),
            Element("device", "Urinary device",
                    normal="No urinary device",
                    options=["No urinary device",
                             "Indwelling urinary catheter — record insertion date "
                             "and ongoing indication",
                             "External urinary catheter",
                             "Intermittent catheterisation",
                             "Suprapubic catheter", "Nephrostomy tube",
                             "Urostomy", "Condom catheter"],
                    hint="An indwelling catheter needs its insertion date and a "
                         "daily documented indication. \"Still in\" is not an "
                         "indication, and a catheter-associated infection is a "
                         "reportable, non-reimbursable event."),
            Element("dialysis_access", "Dialysis access", normal="",
                    options=["Not applicable",
                             "Arteriovenous fistula — bruit and thrill present",
                             "Arteriovenous graft — bruit and thrill present",
                             "Tunnelled catheter — dressing clean, dry, intact",
                             "Peritoneal catheter — site clean",
                             "Access limb signed — no blood pressure or "
                             "venipuncture"],
                    hint="If there is a fistula, charting the bruit and thrill and "
                         "the no-cuff sign on that limb protects both the patient "
                         "and you."),
            Element("gu_notes", "Additional genitourinary findings", free_text=True),
        ],
    ),

    System(
        system_id="musculoskeletal",
        label="Musculoskeletal and mobility",
        wdl_statement=(
            "Full range of motion in all extremities without pain. Gait steady at "
            "the patient's baseline. Weight-bearing status as ordered. Assistive "
            "device used as prescribed. Repositioned per the plan of care."
        ),
        elements=[
            Element("rom", "Range of motion",
                    normal="Full in all extremities, without pain",
                    options=["Full in all extremities, without pain",
                             "Limited — specify joint",
                             "Painful — specify joint",
                             "Contracture present", "Passive range only",
                             "Immobilised — cast, splint or brace"]),
            Element("gait", "Gait",
                    normal="Steady at baseline",
                    options=["Steady at baseline", "Unsteady",
                             "Shuffling", "Wide-based", "Antalgic",
                             "Requires one-person assist",
                             "Requires two-person assist",
                             "Non-ambulatory", "Bed rest ordered"]),
            Element("assistive_device", "Assistive device",
                    normal="None required",
                    options=["None required", "Cane", "Single-point walker",
                             "Front-wheel walker", "Rollator", "Crutches",
                             "Wheelchair", "Mechanical lift",
                             "Gait belt used", "Prosthesis in place"]),
            Element("weight_bearing", "Weight-bearing status",
                    normal="Weight-bearing as tolerated",
                    options=["Weight-bearing as tolerated", "Full weight-bearing",
                             "Partial weight-bearing — specify percentage",
                             "Toe-touch weight-bearing", "Non-weight-bearing",
                             "Not applicable"],
                    hint="Copy this from the order, not from what the patient did. "
                         "A patient who walked on a non-weight-bearing leg is an "
                         "event to document, not a status to update."),
            Element("repositioning", "Repositioning", normal="",
                    options=["Repositioned every two hours per plan of care",
                             "Self-repositioning independently",
                             "Turn schedule in place — see times",
                             "Declined repositioning — education given",
                             "Specialty surface in use"],
                    is_task=True,
                    hint="Chart the times, not the interval. \"Repositioned at "
                         "2000, 2200, 0000, 0200\" is evidence; \"turned q2h\" is "
                         "an assertion."),
            Element("mobility_activity", "Activity this shift", normal="",
                    options=["Ambulated in the hall — record distance",
                             "Ambulated to the bathroom",
                             "Up to the chair", "Dangled at the bedside",
                             "Passive range of motion performed",
                             "Remained on bed rest"],
                    is_task=True),
            Element("msk_notes", "Additional musculoskeletal findings",
                    free_text=True),
        ],
    ),

    System(
        system_id="integumentary",
        label="Integumentary and wounds",
        wdl_statement=(
            "Skin intact, warm and dry with elastic turgor and no unusual "
            "moisture. No redness over bony prominences. No rash, bruising or "
            "breakdown observed on a full-body inspection including the sacrum, "
            "heels and areas under devices."
        ),
        elements=[
            Element("integrity", "Skin integrity",
                    normal="Intact, no breakdown observed",
                    options=["Intact, no breakdown observed",
                             "Blanchable erythema", "Non-blanchable erythema",
                             "Open area — document as a wound below",
                             "Rash — describe and locate", "Bruising",
                             "Skin tear", "Surgical incision",
                             "Device-related pressure — specify device",
                             "Moisture-associated damage"]),
            Element("turgor", "Turgor",
                    normal="Elastic, recoils immediately",
                    options=["Elastic, recoils immediately",
                             "Slightly decreased", "Tenting",
                             "Not assessable — oedema"]),
            Element("moisture", "Moisture",
                    normal="Dry, no unusual moisture",
                    options=["Dry, no unusual moisture", "Diaphoretic",
                             "Incontinence-associated moisture",
                             "Wound drainage on the skin",
                             "Macerated"]),
            Element("bony_prominences", "Bony prominences inspected", normal="",
                    options=["Sacrum, heels, elbows and occiput inspected — no "
                             "redness",
                             "Sacrum inspected — finding documented",
                             "Heels inspected — finding documented",
                             "Under-device skin inspected",
                             "Unable to fully inspect — reason documented"],
                    is_task=True,
                    hint="Naming the areas you looked at is what makes a later "
                         "\"present on admission\" claim credible."),
            Element("prevention", "Pressure injury prevention", normal="",
                    options=["Heels floated", "Pressure-redistributing mattress",
                             "Pressure-redistributing cushion",
                             "Barrier cream applied", "Silicone dressing applied "
                             "prophylactically", "Turn schedule in place",
                             "Nutrition consult placed"],
                    is_task=True),
            Element("skin_notes", "Additional integumentary findings",
                    free_text=True),
        ],
    ),

    System(
        system_id="psychosocial",
        label="Psychosocial and safety",
        wdl_statement=(
            "Affect appropriate to the situation. Behaviour cooperative and at the "
            "patient's baseline. Denies suicidal and homicidal ideation. Call "
            "light within reach, bed in the low position, brakes locked, "
            "environment clear. Vascular access site without redness, swelling or "
            "tenderness. Fall precautions in place as assessed."
        ),
        elements=[
            Element("affect", "Affect",
                    normal="Appropriate to the situation",
                    options=["Appropriate to the situation", "Flat", "Tearful",
                             "Labile", "Withdrawn", "Irritable — describe "
                             "behaviour", "Euphoric", "Guarded"]),
            Element("behaviour", "Behaviour",
                    normal="Cooperative, at baseline",
                    options=["Cooperative, at baseline",
                             "Restless — describe what was observed",
                             "Calling out", "Attempting to get out of bed",
                             "Pulling at lines or devices", "Wandering",
                             "Verbally escalated — quote what was said",
                             "Physically escalated — describe actions"],
                    hint="Describe actions, never adjectives. \"Aggressive\" is a "
                         "conclusion; \"shouting, pacing, struck the bedside "
                         "table\" is an observation."),
            Element("ideation", "Suicidal or homicidal ideation",
                    normal="Denies suicidal and homicidal ideation",
                    options=["Denies suicidal and homicidal ideation",
                             "Reports passive suicidal ideation — quote and "
                             "escalate",
                             "Reports active suicidal ideation with a plan — "
                             "quote and escalate immediately",
                             "Reports homicidal ideation — escalate immediately",
                             "Unable to assess",
                             "One-to-one observation in place",
                             "Ligature risk assessment completed"],
                    hint="Quote the patient exactly, document the exact time you "
                         "escalated, to whom, and what safety measures were put in "
                         "place. This is the highest-liability element on this "
                         "screen."),
            Element("vascular_access", "Vascular access site",
                    normal="Without redness, swelling or tenderness",
                    options=["Without redness, swelling or tenderness",
                             "Redness at the site", "Swelling at the site",
                             "Tenderness on palpation", "Infiltration — stopped "
                             "and removed", "Phlebitis — graded",
                             "Extravasation — escalated",
                             "Occluded", "Dressing changed",
                             "No vascular access in place"],
                    hint="Record the site, gauge, insertion date and dressing "
                         "condition. A peripheral line past its dwell time is a "
                         "finding."),
            Element("fall_precautions", "Fall precautions", normal="",
                    options=["Call light within reach, bed low, brakes locked",
                             "Non-slip footwear in place",
                             "Bed alarm on and audible",
                             "Chair alarm on and audible",
                             "Hourly rounding performed",
                             "Bedside commode within reach",
                             "Family or sitter at the bedside",
                             "Room close to the nursing station",
                             "Declined precautions — education documented"],
                    is_task=True,
                    hint="List every measure actually in place. After a fall, the "
                         "question is which interventions were in place before it, "
                         "and the answer has to already be in the chart."),
            Element("support", "Support and coping", normal="",
                    options=["Family at the bedside", "Family updated by phone",
                             "Chaplaincy involved", "Social work consulted",
                             "Interpreter used — record language and identifier",
                             "Declined support services",
                             "Patient alone by preference"]),
            Element("psychosocial_notes", "Additional psychosocial findings",
                    free_text=True),
        ],
    ),
]


BY_ID = {system.system_id: system for system in SYSTEMS}


def get(system_id: str) -> System | None:
    return BY_ID.get(system_id)


def catalogue(setting: str = "") -> list[dict[str, Any]]:
    return [s.as_dict() for s in SYSTEMS
            if not s.settings or not setting or setting in s.settings]


# ---------------------------------------------------------------------- narrative


# Several options end in an instruction to the nurse rather than clinical content
# — "Nasal cannula — specify L/min", "Absent, specify site". That tail is a prompt
# for the UI, not text for the note, so it is stripped on the way out and tracked
# separately by `needs_detail` so the interlocks can ask for what it wanted.
# The separator may be a dash or a comma — "Nasal cannula — specify L/min" and
# "0 — absent, specify site" both occur in the tables above. `record\b` matches the
# instruction "record insertion date" without touching the clinical phrase
# "recorded and escalated", which is why the word boundary is load-bearing.
_PROMPT_TAIL = re.compile(
    r"\s*[,—–-]\s*(?:specify|record|describe|document|quote|see|graded)\b.*$",
    re.IGNORECASE,
)


def _clean_option(text: str) -> str:
    return _PROMPT_TAIL.sub("", text).rstrip(" ,;").strip()


def _lower_first(text: str) -> str:
    """Lowercase a finding's first letter when it follows an element label.

    Skipped for acronyms and for anything whose second character is already
    uppercase (PERRLA, S1, ROM), because lowercasing those makes them wrong rather
    than merely mid-sentence.
    """
    if not text:
        return text
    first = text.split()[0].strip(".,")
    if first.isupper() or (len(first) > 1 and first[1].isupper()):
        return text
    return text[0].lower() + text[1:]


def needs_detail(finding: SystemFinding) -> list[str]:
    """Elements whose selected option asked for a specific that was not supplied.

    "Absent — specify site" without a site is a half-finding: it records that
    something was wrong and loses the only part a reader needs.
    """
    system = get(finding.system)
    if not system:
        return []
    supplied = " ".join(
        [str(v) for k, v in finding.findings.items()
         if (system.element(k) or Element("", "")).free_text]
        + list(finding.exceptions)
    ).lower()
    wanted: list[str] = []
    for element_id, value in finding.findings.items():
        text = str(value)
        if not _PROMPT_TAIL.search(text):
            continue
        element = system.element(element_id)
        label = element.label if element else element_id
        asked = _PROMPT_TAIL.search(text).group(0).strip(" ,—–-")
        # A free-text note on the same system counts as the detail: the nurse was
        # asked for a site and typed one, which is the intended flow.
        if len(supplied) > 12:
            continue
        wanted.append(f"{label}: {asked}")
    return wanted


def build_finding(system_id: str, *, within_defined_limits: bool = False,
                  findings: dict[str, str] | None = None,
                  exceptions: list[str] | None = None,
                  not_assessed: bool = False,
                  not_assessed_reason: str = "",
                  at: str = "") -> SystemFinding:
    """Assemble a SystemFinding, dropping selections that equal the normal value.

    Dropping normals is what makes charting by exception concise, and it is safe
    only because the WDL statement is recorded verbatim in the note: the reader
    sees exactly which normals were asserted, without a screen of "clear and
    equal" lines to read past.
    """
    system = get(system_id)
    findings = dict(findings or {})
    if system and within_defined_limits:
        for element in system.elements:
            value = findings.get(element.element_id)
            if value and element.normal and value == element.normal:
                findings.pop(element.element_id, None)
    return SystemFinding(
        system=system_id,
        within_defined_limits=within_defined_limits,
        findings=findings,
        exceptions=list(exceptions or []),
        not_assessed=not_assessed,
        not_assessed_reason=not_assessed_reason,
        assessed_at=at or iso(now_utc()),
    )


def narrate(finding: SystemFinding, *, include_wdl_statement: bool = True) -> str:
    """One system as a paragraph.

    `include_wdl_statement` prints the defined-limits text in full. It defaults to
    true and the export never turns it off, because a note that says "WDL" without
    saying what WDL meant has documented nothing.
    """
    system = get(finding.system)
    label = system.label if system else finding.system.replace("_", " ").title()

    if finding.not_assessed:
        reason = finding.not_assessed_reason or "no reason recorded"
        return (f"{label}: not assessed this shift ({reason}). "
                f"Recorded as not assessed rather than left blank.")

    if finding.narrative_override.strip():
        return f"{label}: {finding.narrative_override.strip()}"

    abnormal: list[str] = []
    tasks: list[str] = []
    free: list[str] = []
    for element_id, value in finding.findings.items():
        if not str(value).strip():
            continue
        element = system.element(element_id) if system else None
        text = str(value).strip()
        if element and element.free_text:
            free.append(text)
        elif element and element.is_task:
            tasks.append(_clean_option(text))
        elif element and element.normal and text == element.normal:
            continue    # a normal explicitly selected outside WDL mode
        else:
            cleaned = _clean_option(text)
            if not cleaned:
                continue
            if element:
                abnormal.append(f"{element.label.lower()} {_lower_first(cleaned)}")
            else:
                abnormal.append(cleaned)
    abnormal.extend(e.strip() for e in finding.exceptions if e.strip())

    parts: list[str] = []
    if finding.within_defined_limits:
        if abnormal:
            statement = (system.wdl_statement if system and include_wdl_statement
                         else "within defined limits")
            parts.append(f"{label}: within defined limits except "
                         + "; ".join(abnormal) + ".")
            if system and include_wdl_statement:
                parts.append(f"Defined limits for this system: {statement}")
        else:
            if system and include_wdl_statement:
                parts.append(f"{label}: within defined limits. "
                             f"{system.wdl_statement}")
            else:
                parts.append(f"{label}: within defined limits.")
    else:
        if abnormal:
            parts.append(f"{label}: " + "; ".join(abnormal) + ".")
        elif not tasks and not free:
            parts.append(f"{label}: assessed, no abnormal findings recorded. "
                         f"Not marked within defined limits.")
    if tasks:
        parts.append(" ".join(t if t.endswith(".") else f"{t}." for t in tasks))
    if free:
        parts.append(" ".join(f if f.endswith(".") else f"{f}." for f in free))
    return " ".join(parts)


def narrate_all(findings: list[SystemFinding], *,
                include_wdl_statement: bool = True) -> str:
    """Every assessed system, in head-to-toe order."""
    order = {system.system_id: index for index, system in enumerate(SYSTEMS)}
    ordered = sorted(findings, key=lambda f: order.get(f.system, 99))
    return "\n\n".join(
        narrate(f, include_wdl_statement=include_wdl_statement)
        for f in ordered
        if narrate(f, include_wdl_statement=include_wdl_statement)
    )


def unassessed(findings: list[SystemFinding]) -> list[str]:
    """Systems with no record at all — neither assessed nor declared unassessed."""
    recorded = {f.system for f in findings}
    return [s.label for s in SYSTEMS if s.system_id not in recorded]


def wdl_without_detail(findings: list[SystemFinding]) -> list[str]:
    """Systems marked WDL with no exceptions and no element detail whatsoever.

    Not an error — a genuinely normal system is the common case. It is surfaced so
    a nurse can see, before saving, that they are about to assert eight normals in
    a row, which is the pattern a reviewer reads as rubber-stamping.
    """
    out: list[str] = []
    for finding in findings:
        if not finding.within_defined_limits:
            continue
        if finding.exceptions:
            continue
        if any(str(v).strip() for v in finding.findings.values()):
            continue
        system = get(finding.system)
        out.append(system.label if system else finding.system)
    return out
