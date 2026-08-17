"""
The scoring-scale library.

Twenty-one instruments, each computing its published score from clinician-entered
selections and turning the result into a sentence you can put in a note.

## The copyright problem, and how it is handled

Most bedside scoring instruments are copyrighted works, and several are
trademarked and licensed. The Braden Scale belongs to Braden and Bergstrom, the
Morse Fall Scale to Morse, FLACC to the University of Michigan, CPOT to Gélinas,
CAM and CAM-ICU to Inouye and Ely, APACHE II to Knaus and colleagues, and the
Emergency Severity Index to the Emergency Nurses Association. Wong-Baker FACES is
a registered trademark whose artwork is licensed and may not be reproduced.

Reproducing their item wording, anchor descriptions or artwork in this file would
be infringement, and shipping a subtly paraphrased "close enough" version would
be worse — it would look like the instrument while scoring something slightly
different, which is a clinical safety problem rather than a legal one.

So this module implements, for each instrument:

* the **scoring arithmetic** and the **published thresholds**, which are facts
  about the instrument rather than expression;
* item and option labels **written fresh here**, deliberately terse, and marked
  as such;
* a **citation** to the source publication, and a **licence note** naming who
  holds the rights and where the authoritative wording lives.

Use your unit's licensed copy for the definitions. Where an option label here is
ambiguous against the real instrument, the real instrument governs — and that is
worth stating in the note, which is why `ScaleResult` keeps the raw responses.
`LICENSING` is rendered on the charting settings screen so this is visible rather
than buried in a docstring.

## Scores do not direct care

Every scale returns a band and a `band_detail` describing what the published
instrument associates with that band. None of them returns an action. The
Emergency Severity Index implementation is the sharpest case: it computes a level
from the decision points the nurse answers and shows the working, and it does not
assign a triage level, because assigning one from vital signs alone is clinical
decision support that would be wrong at the bedside and indefensible in a
deposition. See `disclosure.NOT_CLINICAL_ADVICE`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable

from .models import ScaleResult, Vitals, iso, now_utc

# ---------------------------------------------------------------------- licences


LICENSING = [
    {
        "scales": ["braden"],
        "holder": "Barbara Braden and Nancy Bergstrom",
        "note": ("Copyrighted. Subscale structure and the published risk "
                 "thresholds are implemented; the anchor wording here is written "
                 "fresh. Licensed copies are distributed through "
                 "prevention plus (bradenscale.com)."),
    },
    {
        "scales": ["morse"],
        "holder": "Janice Morse",
        "note": ("Copyrighted. Item weights and thresholds implemented; wording "
                 "written fresh. Published in Morse et al. (1989)."),
    },
    {
        "scales": ["wong_baker"],
        "holder": "Wong-Baker FACES Foundation",
        "note": ("Registered trademark; the face artwork is licensed and is NOT "
                 "reproduced here. This implementation records the 0-10 numeric "
                 "anchor the child selects from your unit's licensed chart."),
    },
    {
        "scales": ["flacc"],
        "holder": "University of Michigan (Merkel, Voepel-Lewis, Shayevitz, Malviya)",
        "note": ("Copyrighted. Five-category structure and 0-10 total "
                 "implemented; behavioural descriptors written fresh."),
    },
    {
        "scales": ["cpot"],
        "holder": "Céline Gélinas",
        "note": ("Copyrighted. Four-domain structure and the ≥3 threshold "
                 "implemented; descriptors written fresh."),
    },
    {
        "scales": ["cam", "cam_icu"],
        "holder": "Sharon Inouye (CAM) and E. Wesley Ely (CAM-ICU)",
        "note": ("Copyrighted; training materials are distributed through "
                 "icudelirium.org. The diagnostic algorithm — features 1 and 2 "
                 "plus either 3 or 4 — is implemented with fresh wording. The "
                 "attention-testing item lists are not reproduced; use your "
                 "unit's licensed cards."),
    },
    {
        "scales": ["esi"],
        "holder": "Emergency Nurses Association",
        "note": ("The ESI Implementation Handbook is copyrighted and its use is "
                 "licensed. The four decision points and the danger-zone vital "
                 "sign criteria are implemented with fresh wording. This tool "
                 "computes and shows the working; the triage nurse assigns the "
                 "level."),
    },
    {
        "scales": ["apache_ii"],
        "holder": "Knaus, Draper, Wagner and Zimmerman",
        "note": ("Copyrighted (Crit Care Med, 1985). Point tables implemented; "
                 "it is a 24-hour mortality-prediction score for cohorts, not a "
                 "bedside charting scale — see the scale's own note."),
    },
    {
        "scales": ["news2"],
        "holder": "Royal College of Physicians",
        "note": ("NEWS2 is RCP copyright, licensed for clinical use with "
                 "attribution. Implemented per the 2017 report."),
    },
    {
        "scales": ["nihss", "gcs", "rass", "ciwa_ar", "cows", "qsofa", "sofa",
                   "mews", "caprini", "lund_browder", "pews", "pat", "nrs"],
        "holder": "Published in the peer-reviewed literature",
        "note": ("Freely reproducible criteria, cited on each scale. NIHSS is a "
                 "US National Institutes of Health work in the public domain and "
                 "is implemented closest to source."),
    },
]


# --------------------------------------------------------------------- structure


@dataclass
class Option:
    label: str
    points: float
    value: str = ""

    def key(self) -> str:
        return self.value or self.label


@dataclass
class Item:
    """One scored item.

    `label` and the option labels are this module's own wording. `source_hint`
    points at what the licensed instrument calls the item, so a nurse can line the
    two up without the licensed text being reproduced.
    """

    item_id: str
    label: str
    options: list[Option]
    source_hint: str = ""
    optional: bool = False


@dataclass
class Band:
    """A published interpretation range. `low` and `high` are inclusive."""

    low: float
    high: float
    label: str
    detail: str = ""


@dataclass
class Scale:
    scale_id: str
    name: str
    abbreviation: str
    citation: str
    purpose: str
    items: list[Item] = field(default_factory=list)
    bands: list[Band] = field(default_factory=list)
    score_range: tuple[float, float] | None = None
    higher_is_worse: bool = True
    settings: tuple[str, ...] = ()
    reassess_minutes: int = 0
    note: str = ""
    scorer: Callable[["Scale", dict[str, Any]], dict[str, Any]] | None = None
    narrator: Callable[["Scale", dict[str, Any]], str] | None = None

    # ------------------------------------------------------------------ scoring

    def item(self, item_id: str) -> Item | None:
        return next((i for i in self.items if i.item_id == item_id), None)

    def band_for(self, score: float) -> Band | None:
        for band in self.bands:
            if band.low <= score <= band.high:
                return band
        return None

    def score(self, responses: dict[str, Any]) -> dict[str, Any]:
        """Compute the score. Returns total, subscores and missing items."""
        if self.scorer:
            return self.scorer(self, responses)
        return self._additive(responses)

    def _additive(self, responses: dict[str, Any]) -> dict[str, Any]:
        total = 0.0
        subscores: dict[str, float] = {}
        missing: list[str] = []
        for item in self.items:
            raw = responses.get(item.item_id)
            if raw is None or raw == "":
                if not item.optional:
                    missing.append(item.label)
                continue
            points = self._points(item, raw)
            if points is None:
                missing.append(item.label)
                continue
            subscores[item.item_id] = points
            total += points
        return {"score": total, "subscores": subscores, "missing": missing}

    @staticmethod
    def _points(item: Item, raw: Any) -> float | None:
        """Resolve a response to points.

        Accepts the option key, the option label, or a bare number matching an
        option's points — the front end sends keys, tests read better with
        numbers, and an imported response may carry either.
        """
        if isinstance(raw, bool):
            raw = "yes" if raw else "no"
        text = str(raw).strip()
        for option in item.options:
            if text == option.key() or text.lower() == option.label.lower():
                return option.points
        try:
            number = float(text)
        except ValueError:
            return None
        for option in item.options:
            if option.points == number:
                return number
        return None

    def evaluate(self, responses: dict[str, Any], *,
                 at: datetime | None = None) -> ScaleResult:
        """Score, band and narrate in one call — what the route uses."""
        computed = self.score(responses)
        total = computed.get("score")
        band = self.band_for(total) if isinstance(total, (int, float)) else None
        result = ScaleResult(
            scale_id=self.scale_id,
            scale_name=f"{self.name} ({self.abbreviation})" if self.abbreviation else self.name,
            score=total,
            subscores={k: v for k, v in (computed.get("subscores") or {}).items()},
            band=computed.get("band") or (band.label if band else ""),
            band_detail=computed.get("band_detail") or (band.detail if band else ""),
            responses=dict(responses),
            citation=self.citation,
            scored_at=iso(at or now_utc()),
            incomplete=list(computed.get("missing") or []),
        )
        if self.narrator:
            result.narrative = self.narrator(self, {**computed, "responses": responses,
                                                    "band": result.band})
        else:
            result.narrative = _default_narrative(self, result)
        return result

    def as_dict(self) -> dict[str, Any]:
        return {
            "scale_id": self.scale_id,
            "name": self.name,
            "abbreviation": self.abbreviation,
            "citation": self.citation,
            "purpose": self.purpose,
            "note": self.note,
            "settings": list(self.settings),
            "reassess_minutes": self.reassess_minutes,
            "score_range": list(self.score_range) if self.score_range else None,
            "higher_is_worse": self.higher_is_worse,
            "items": [
                {
                    "item_id": item.item_id,
                    "label": item.label,
                    "source_hint": item.source_hint,
                    "optional": item.optional,
                    "options": [
                        {"key": o.key(), "label": o.label, "points": o.points}
                        for o in item.options
                    ],
                }
                for item in self.items
            ],
            "bands": [
                {"low": b.low, "high": b.high, "label": b.label, "detail": b.detail}
                for b in self.bands
            ],
        }


def _default_narrative(scale: Scale, result: ScaleResult) -> str:
    """The sentence a scale produces when it has no custom narrator.

    Shape: instrument, score, range, band, then the published meaning. Naming the
    range matters — "Braden 14" is meaningless to a reader who does not know the
    scale runs 6 to 23 and that lower is worse.
    """
    name = scale.name
    if scale.abbreviation and scale.abbreviation not in name:
        name = f"{name} ({scale.abbreviation})"
    if result.score is None:
        return f"{name}: not scored."
    score = f"{result.score:g}"
    if scale.score_range:
        low, high = scale.score_range
        score += f" (range {low:g}-{high:g})"
    text = f"{name} {score}"
    if result.band:
        text += f": {result.band}"
    text += "."
    if result.band_detail:
        text += f" {result.band_detail}"
    if result.incomplete:
        text += (" Not all items were scored ("
                 + ", ".join(result.incomplete[:4])
                 + ("…" if len(result.incomplete) > 4 else "")
                 + "), so the total is a floor rather than a score.")
    return text


def _yes_no(item_id: str, label: str, points: float,
            hint: str = "", optional: bool = False) -> Item:
    return Item(item_id, label,
                [Option("No", 0.0, "no"), Option("Yes", points, "yes")],
                source_hint=hint, optional=optional)


def _slug(text: str) -> str:
    """A stable option key from a label.

    Keys have to survive being stored in a saved encounter and read back, so they
    are derived from the label rather than from position — a key of "opt3" would
    silently change meaning if an option were ever inserted above it.
    """
    out: list[str] = []
    for char in text.lower():
        if char.isalnum():
            out.append(char)
        elif char in " -_/." and out and out[-1] != "-":
            out.append("-")
    return "".join(out).strip("-")[:32]


def _graded(item_id: str, label: str,
            grades: list[tuple[str, float]] | list[tuple[str, float, str]],
            hint: str = "", optional: bool = False) -> Item:
    """Build an item from (label, points) pairs, or (label, points, key) triples.

    Keys are slugged from the label, which two of the instruments break: CIWA-Ar
    has unlabelled intermediate points (the published scale scores 0-7 with
    anchors only at 0, 1, 4 and 7), and APACHE II's oxygenation item has five
    options all starting "A-a gradient". Both are handled here — an empty label
    becomes a point-value key, and a collision gets a numeric suffix — so no
    option is ever unreachable.
    """
    options: list[Option] = []
    used: set[str] = set()
    for index, grade in enumerate(grades):
        text, points = grade[0], grade[1]
        explicit = grade[2] if len(grade) > 2 else ""
        key = explicit or _slug(text) or f"p{points:g}".replace("-", "neg")
        if key in used:
            key = f"{key}-{index}"
        used.add(key)
        display = text or f"{points:g} — intermediate point, no published anchor"
        options.append(Option(display, points, key))
    return Item(item_id, label, options, source_hint=hint, optional=optional)


REGISTRY: dict[str, Scale] = {}


def register(scale: Scale) -> Scale:
    REGISTRY[scale.scale_id] = scale
    return scale


def get(scale_id: str) -> Scale | None:
    return REGISTRY.get(scale_id)


def for_setting(setting: str) -> list[Scale]:
    """Scales relevant to a specialty module, in a sensible bedside order."""
    return [s for s in REGISTRY.values() if not s.settings or setting in s.settings]


# ============================================================ pressure & falls


register(Scale(
    scale_id="braden",
    name="Braden Scale for Predicting Pressure Sore Risk",
    abbreviation="Braden",
    citation="Bergstrom, N., Braden, B. J., Laguzza, A., & Holman, V. (1987). "
             "The Braden Scale for predicting pressure sore risk. Nursing "
             "Research, 36(4), 205-210.",
    purpose="Pressure injury risk across six subscales; lower totals are worse.",
    note="Copyrighted by Braden and Bergstrom — see LICENSING. Item wording here "
         "is this tool's own; score the patient from your unit's licensed copy.",
    score_range=(6, 23),
    higher_is_worse=False,
    reassess_minutes=1440,
    items=[
        _graded("sensory", "Sensory perception — ability to feel and report discomfort", [
            ("Completely limited — no response to painful stimuli", 1),
            ("Very limited — responds only to painful stimuli", 2),
            ("Slightly limited — responds to speech, cannot always report discomfort", 3),
            ("No impairment — responds and reports discomfort reliably", 4),
        ], hint="Braden subscale 1"),
        _graded("moisture", "Moisture — how often the skin is wet", [
            ("Constantly moist", 1),
            ("Often moist — linen changed at least each shift", 2),
            ("Occasionally moist — an extra linen change about daily", 3),
            ("Rarely moist", 4),
        ], hint="Braden subscale 2"),
        _graded("activity", "Activity — degree of physical activity", [
            ("Bedfast", 1),
            ("Chairfast", 2),
            ("Walks occasionally, short distances", 3),
            ("Walks frequently outside the room", 4),
        ], hint="Braden subscale 3"),
        _graded("mobility", "Mobility — ability to change position", [
            ("Completely immobile", 1),
            ("Very limited — slight changes only", 2),
            ("Slightly limited — frequent small changes independently", 3),
            ("No limitation", 4),
        ], hint="Braden subscale 4"),
        _graded("nutrition", "Nutrition — usual food intake", [
            ("Very poor — never a complete meal", 1),
            ("Probably inadequate — about half of most meals", 2),
            ("Adequate — over half of most meals", 3),
            ("Excellent — eats most of every meal", 4),
        ], hint="Braden subscale 5"),
        _graded("friction", "Friction and shear", [
            ("Problem — requires maximum assistance to move", 1),
            ("Potential problem — moves feebly or needs minimum assistance", 2),
            ("No apparent problem — moves independently in bed and chair", 3),
        ], hint="Braden subscale 6"),
    ],
    bands=[
        Band(6, 9, "very high risk",
             "The published cut points place 9 or below at very high risk."),
        Band(10, 12, "high risk", "Published high-risk range."),
        Band(13, 14, "moderate risk", "Published moderate-risk range."),
        Band(15, 18, "mild risk",
             "Published mild-risk range; risk rises with other factors such as "
             "fever, poor perfusion or advanced age."),
        Band(19, 23, "not at risk by this instrument",
             "A score in this range does not exclude risk from a device, a cast "
             "or a procedure position."),
    ],
))


register(Scale(
    scale_id="morse",
    name="Morse Fall Scale",
    abbreviation="MFS",
    citation="Morse, J. M., Morse, R. M., & Tylko, S. J. (1989). Development of a "
             "scale to identify the fall-prone patient. Canadian Journal on "
             "Aging, 8(4), 366-377.",
    purpose="Fall risk from six weighted items.",
    note="Copyrighted by Morse — see LICENSING. Morse recommended that units "
         "calibrate their own cut points against local fall rates, so the bands "
         "here are the commonly published ones and may not be your policy's.",
    score_range=(0, 125),
    reassess_minutes=720,
    items=[
        _graded("history", "Fell within the last three months", [
            ("No", 0), ("Yes", 25),
        ]),
        _graded("secondary", "More than one medical diagnosis", [
            ("No", 0), ("Yes", 15),
        ]),
        _graded("aid", "Walking aid", [
            ("None, bed rest, or assisted by a nurse", 0),
            ("Crutches, cane or walker", 15),
            ("Steadies against furniture or walls", 30),
        ]),
        _graded("iv", "Intravenous access or saline lock in place", [
            ("No", 0), ("Yes", 20),
        ]),
        _graded("gait", "Gait", [
            ("Normal, bed rest or immobile", 0),
            ("Weak — short steps, may shuffle, steadies self", 10),
            ("Impaired — needs assistance, keeps head down, poor balance", 20),
        ]),
        _graded("mental", "Awareness of own mobility limits", [
            ("Oriented to own ability", 0),
            ("Overestimates ability or forgets limits", 15),
        ]),
    ],
    bands=[
        Band(0, 24, "low risk",
             "Commonly published cut points: 0-24 low, 25-44 moderate, 45 or "
             "above high. Use your unit's calibrated thresholds."),
        Band(25, 44, "moderate risk", "Commonly published moderate-risk range."),
        Band(45, 125, "high risk", "Commonly published high-risk range."),
    ],
))


register(Scale(
    scale_id="caprini",
    name="Caprini Risk Assessment Model for venous thromboembolism",
    abbreviation="Caprini",
    citation="Caprini, J. A. (2005). Thrombosis risk assessment as a guide to "
             "quality patient care. Disease-a-Month, 51(2-3), 70-78.",
    purpose="Cumulative VTE risk score.",
    note="The full model has more than 30 weighted factors. The most commonly "
         "scored ones are here; add the remainder from your unit's form in the "
         "notes field if they apply.",
    score_range=(0, 30),
    reassess_minutes=1440,
    items=[
        _graded("age", "Age band", [
            ("41-60 years", 1), ("61-74 years", 2), ("75 years or older", 3),
            ("40 years or younger", 0),
        ]),
        _yes_no("minor_surgery", "Minor surgery planned or performed", 1),
        _yes_no("major_surgery", "Major surgery longer than 45 minutes", 2),
        _yes_no("arthroplasty", "Elective arthroplasty", 5),
        _yes_no("hip_fracture", "Hip, pelvis or leg fracture", 5),
        _yes_no("stroke", "Stroke within one month", 5),
        _yes_no("spinal_cord", "Acute spinal cord injury within one month", 5),
        _yes_no("vte_history", "Previous venous thromboembolism", 3),
        _yes_no("family_vte", "Family history of thrombosis", 3),
        _yes_no("thrombophilia", "Known thrombophilia", 3),
        _yes_no("malignancy", "Current or previous malignancy", 2),
        _yes_no("bedrest", "Confined to bed longer than 72 hours", 2),
        _yes_no("immobilising_cast", "Immobilising plaster cast", 2),
        _yes_no("central_line", "Central venous access in place", 2),
        _yes_no("bmi", "Body mass index over 25", 1),
        _yes_no("swollen_legs", "Swollen legs", 1),
        _yes_no("varicose", "Varicose veins", 1),
        _yes_no("sepsis", "Sepsis within one month", 1),
        _yes_no("lung_disease", "Serious lung disease or pneumonia within one month", 1),
        _yes_no("oestrogen", "Oral contraceptive or hormone replacement", 1),
        _yes_no("pregnancy", "Pregnant or postpartum within one month", 1),
    ],
    bands=[
        Band(0, 1, "very low risk", "Published banding: 0-1 very low, 2 low, "
                                    "3-4 moderate, 5 or above high."),
        Band(2, 2, "low risk", "Published low-risk score."),
        Band(3, 4, "moderate risk", "Published moderate-risk range."),
        Band(5, 30, "high risk", "Published high-risk range."),
    ],
))


# ================================================================ neurological


def _score_gcs(scale: Scale, responses: dict[str, Any]) -> dict[str, Any]:
    """GCS, with the non-testable convention handled.

    A component that cannot be tested — an intubated patient's verbal response, a
    swollen-shut eye — is charted as not testable, and the total is reported as a
    floor with the untestable component named. Scoring an intubated patient's
    verbal response as 1 makes an alert patient look obtunded, and it is one of
    the most common neuro-charting errors there is.
    """
    total = 0.0
    subscores: dict[str, float] = {}
    missing: list[str] = []
    untestable: list[str] = []
    for item in scale.items:
        raw = responses.get(item.item_id)
        if raw is None or raw == "":
            missing.append(item.label)
            continue
        if str(raw).lower() in ("nt", "not_testable", "not testable"):
            untestable.append(item.label.split("—")[0].strip())
            continue
        points = Scale._points(item, raw)
        if points is None:
            missing.append(item.label)
            continue
        subscores[item.item_id] = points
        total += points

    detail = ""
    band = ""
    if untestable:
        band = "not fully testable"
        detail = ("Components not testable: " + ", ".join(untestable)
                  + ". The total is a floor, not a Glasgow Coma Scale score — "
                    "chart the components rather than the sum.")
    else:
        found = scale.band_for(total)
        if found:
            band, detail = found.label, found.detail
    return {"score": total, "subscores": subscores, "missing": missing,
            "band": band, "band_detail": detail,
            "untestable": untestable}


def _narrate_gcs(scale: Scale, computed: dict[str, Any]) -> str:
    subscores = computed.get("subscores") or {}
    untestable = computed.get("untestable") or []
    eye = subscores.get("eye")
    verbal = subscores.get("verbal")
    motor = subscores.get("motor")
    pieces = []
    for label, value, key in (("E", eye, "eye"), ("V", verbal, "verbal"),
                              ("M", motor, "motor")):
        if value is not None:
            pieces.append(f"{label}{value:g}")
        elif any(key in u.lower() for u in untestable):
            pieces.append(f"{label}NT")
    breakdown = " ".join(pieces)
    total = computed.get("score") or 0
    if untestable:
        return (f"Glasgow Coma Scale components {breakdown} "
                f"(total {total:g} of testable components only; "
                f"{', '.join(untestable)} not testable). "
                f"Charting components rather than a sum, as the total is not a "
                f"valid GCS when a component cannot be tested.")
    text = f"Glasgow Coma Scale {total:g}/15 ({breakdown})."
    band = computed.get("band")
    if band:
        text += f" {band.capitalize()} by published banding."
    return text


register(Scale(
    scale_id="gcs",
    name="Glasgow Coma Scale",
    abbreviation="GCS",
    citation="Teasdale, G., & Jennett, B. (1974). Assessment of coma and impaired "
             "consciousness. The Lancet, 304(7872), 81-84.",
    purpose="Level of consciousness across eye, verbal and motor response.",
    note="Chart the three components, not only the sum. Two patients with a total "
         "of 9 can be in very different condition, and the components are what a "
         "neurosurgeon asks for.",
    score_range=(3, 15),
    higher_is_worse=False,
    reassess_minutes=60,
    scorer=_score_gcs,
    narrator=_narrate_gcs,
    items=[
        Item("eye", "Eye opening", [
            Option("None", 1, "1"),
            Option("To pressure", 2, "2"),
            Option("To sound", 3, "3"),
            Option("Spontaneous", 4, "4"),
            Option("Not testable", 0, "nt"),
        ], source_hint="GCS E"),
        Item("verbal", "Verbal response", [
            Option("None", 1, "1"),
            Option("Sounds only", 2, "2"),
            Option("Words, not conversational", 3, "3"),
            Option("Confused conversation", 4, "4"),
            Option("Oriented", 5, "5"),
            Option("Not testable — intubated or tracheostomy", 0, "nt"),
        ], source_hint="GCS V"),
        Item("motor", "Best motor response", [
            Option("None", 1, "1"),
            Option("Extension to pressure", 2, "2"),
            Option("Abnormal flexion", 3, "3"),
            Option("Withdraws from pressure", 4, "4"),
            Option("Localises pressure", 5, "5"),
            Option("Obeys commands", 6, "6"),
            Option("Not testable", 0, "nt"),
        ], source_hint="GCS M"),
    ],
    bands=[
        Band(3, 8, "severe range", "Published banding places 8 or below in the "
                                   "severe range; airway protection is the usual "
                                   "concern at this level."),
        Band(9, 12, "moderate range", "Published moderate range."),
        Band(13, 15, "mild range", "Published mild range."),
    ],
))


register(Scale(
    scale_id="nihss",
    name="National Institutes of Health Stroke Scale",
    abbreviation="NIHSS",
    citation="Brott, T., Adams, H. P., Olinger, C. P., Marler, J. R., Barsan, "
             "W. G., Biller, J., … Hertzberg, V. (1989). Measurements of acute "
             "cerebral infarction: A clinical examination scale. Stroke, 20(7), "
             "864-870.",
    purpose="Stroke severity across 11 examination items.",
    note="A US National Institutes of Health instrument in the public domain, so "
         "this implementation stays close to source. NIHSS certification is "
         "required to score it for treatment decisions; the total is only "
         "meaningful when the examination was performed in the published order.",
    score_range=(0, 42),
    reassess_minutes=60,
    settings=("emergency", "icu", "med_surg"),
    items=[
        _graded("loc", "1a. Level of consciousness", [
            ("Alert", 0), ("Not alert but rouses to minor stimulation", 1),
            ("Not alert, requires repeated stimulation", 2),
            ("Unresponsive or reflex responses only", 3),
        ]),
        _graded("loc_questions", "1b. Orientation questions — month and age", [
            ("Both correct", 0), ("One correct", 1), ("Neither correct", 2),
        ]),
        _graded("loc_commands", "1c. Commands — open and close eyes, grip and release", [
            ("Both tasks performed", 0), ("One task performed", 1),
            ("Neither performed", 2),
        ]),
        _graded("gaze", "2. Best gaze", [
            ("Normal", 0), ("Partial gaze palsy", 1), ("Forced deviation", 2),
        ]),
        _graded("visual", "3. Visual fields", [
            ("No loss", 0), ("Partial hemianopia", 1), ("Complete hemianopia", 2),
            ("Bilateral hemianopia or blind", 3),
        ]),
        _graded("facial", "4. Facial palsy", [
            ("Normal symmetry", 0), ("Minor asymmetry", 1),
            ("Partial paralysis of the lower face", 2),
            ("Complete paralysis of one or both sides", 3),
        ]),
        _graded("arm_left", "5a. Left arm motor drift", [
            ("No drift for 10 seconds", 0), ("Drift before 10 seconds", 1),
            ("Some effort against gravity", 2), ("No effort against gravity", 3),
            ("No movement", 4), ("Amputation or joint fusion — untestable", 0),
        ]),
        _graded("arm_right", "5b. Right arm motor drift", [
            ("No drift for 10 seconds", 0), ("Drift before 10 seconds", 1),
            ("Some effort against gravity", 2), ("No effort against gravity", 3),
            ("No movement", 4), ("Amputation or joint fusion — untestable", 0),
        ]),
        _graded("leg_left", "6a. Left leg motor drift", [
            ("No drift for 5 seconds", 0), ("Drift before 5 seconds", 1),
            ("Some effort against gravity", 2), ("No effort against gravity", 3),
            ("No movement", 4), ("Amputation or joint fusion — untestable", 0),
        ]),
        _graded("leg_right", "6b. Right leg motor drift", [
            ("No drift for 5 seconds", 0), ("Drift before 5 seconds", 1),
            ("Some effort against gravity", 2), ("No effort against gravity", 3),
            ("No movement", 4), ("Amputation or joint fusion — untestable", 0),
        ]),
        _graded("ataxia", "7. Limb ataxia", [
            ("Absent", 0), ("Present in one limb", 1), ("Present in two limbs", 2),
        ]),
        _graded("sensory", "8. Sensory", [
            ("Normal", 0), ("Mild to moderate loss", 1),
            ("Severe or total loss", 2),
        ]),
        _graded("language", "9. Best language", [
            ("No aphasia", 0), ("Mild to moderate aphasia", 1),
            ("Severe aphasia", 2), ("Mute or global aphasia", 3),
        ]),
        _graded("dysarthria", "10. Dysarthria", [
            ("Normal", 0), ("Mild to moderate — slurred but intelligible", 1),
            ("Severe — unintelligible or mute", 2),
            ("Intubated or other barrier — untestable", 0),
        ]),
        _graded("neglect", "11. Extinction and inattention", [
            ("No abnormality", 0),
            ("Inattention in one sensory modality", 1),
            ("Profound hemi-inattention or inattention in more than one modality", 2),
        ]),
    ],
    bands=[
        Band(0, 0, "no stroke symptoms on this scale", ""),
        Band(1, 4, "minor", "Commonly cited banding: 1-4 minor, 5-15 moderate, "
                            "16-20 moderate to severe, 21-42 severe."),
        Band(5, 15, "moderate", "Commonly cited moderate range."),
        Band(16, 20, "moderate to severe", "Commonly cited range."),
        Band(21, 42, "severe", "Commonly cited severe range."),
    ],
))


register(Scale(
    scale_id="rass",
    name="Richmond Agitation-Sedation Scale",
    abbreviation="RASS",
    citation="Sessler, C. N., Gosnell, M. S., Grap, M. J., Brophy, G. M., "
             "O'Neal, P. V., Keane, K. A., … Elswick, R. K. (2002). The Richmond "
             "Agitation-Sedation Scale. American Journal of Respiratory and "
             "Critical Care Medicine, 166(10), 1338-1344.",
    purpose="Sedation and agitation on a single -5 to +4 scale.",
    note="RASS is a prerequisite for CAM-ICU: a patient at -4 or -5 cannot be "
         "assessed for delirium and is charted as unable to assess.",
    score_range=(-5, 4),
    reassess_minutes=240,
    settings=("icu", "emergency", "med_surg"),
    items=[
        Item("level", "Observed level", [
            Option("+4 Combative — violent, immediate danger to staff", 4, "4"),
            Option("+3 Very agitated — pulls at tubes or catheters, aggressive", 3, "3"),
            Option("+2 Agitated — frequent non-purposeful movement, fights ventilator", 2, "2"),
            Option("+1 Restless — anxious, movements not aggressive", 1, "1"),
            Option("0 Alert and calm", 0, "0"),
            Option("-1 Drowsy — not fully alert, sustains eye contact over 10 seconds", -1, "-1"),
            Option("-2 Light sedation — wakes briefly, eye contact under 10 seconds", -2, "-2"),
            Option("-3 Moderate sedation — movement to voice, no eye contact", -3, "-3"),
            Option("-4 Deep sedation — no response to voice, movement to physical stimulus", -4, "-4"),
            Option("-5 Unarousable — no response to voice or physical stimulus", -5, "-5"),
        ], source_hint="RASS level"),
    ],
    bands=[
        Band(-5, -4, "deep sedation or unarousable",
             "Delirium screening cannot be performed at this level; chart as "
             "unable to assess."),
        Band(-3, -1, "sedated", "Light to moderate sedation."),
        Band(0, 0, "alert and calm", ""),
        Band(1, 4, "agitated", "Consider the cause before the treatment — pain, "
                               "hypoxia, retention, withdrawal and delirium all "
                               "present this way."),
    ],
))


def _score_cam(scale: Scale, responses: dict[str, Any]) -> dict[str, Any]:
    """The CAM algorithm: features 1 and 2, plus 3 or 4.

    Not additive, so it needs its own scorer. The published algorithm requires
    acute onset or fluctuating course (feature 1) AND inattention (feature 2), plus
    either disorganised thinking (3) or altered level of consciousness (4).
    """
    def present(item_id: str) -> bool | None:
        raw = responses.get(item_id)
        if raw is None or raw == "":
            return None
        return str(raw).lower() in ("yes", "y", "true", "1", "present")

    features = {key: present(key) for key in ("acute", "inattention",
                                              "disorganised", "consciousness")}
    missing = [scale.item(k).label for k, v in features.items()
               if v is None and scale.item(k)]
    if any(v is None for v in features.values()):
        return {"score": None, "subscores": {}, "missing": missing,
                "band": "incomplete",
                "band_detail": "All four features are needed before the algorithm "
                               "can be applied."}
    positive = bool(features["acute"] and features["inattention"]
                    and (features["disorganised"] or features["consciousness"]))
    count = sum(1 for v in features.values() if v)
    return {
        "score": float(count),
        "subscores": {k: 1.0 if v else 0.0 for k, v in features.items()},
        "missing": [],
        "band": "positive for delirium" if positive else "negative for delirium",
        "band_detail": (
            "Features 1 and 2 are both present, with feature "
            + ("3" if features["disorganised"] else "4")
            + " also present, satisfying the published algorithm."
            if positive else
            "The published algorithm requires features 1 and 2 together with "
            "either 3 or 4; that combination is not met."
        ),
        "positive": positive,
    }


def _narrate_cam(scale: Scale, computed: dict[str, Any]) -> str:
    responses = computed.get("responses") or {}
    if computed.get("score") is None:
        return f"{scale.name} ({scale.abbreviation}): not completed."
    names = {
        "acute": "acute onset or fluctuating course",
        "inattention": "inattention",
        "disorganised": "disorganised thinking",
        "consciousness": "altered level of consciousness",
    }
    present = [names[k] for k in names
               if str(responses.get(k, "")).lower() in ("yes", "y", "true", "1", "present")]
    absent = [names[k] for k in names if names[k] not in present]
    verdict = "positive" if computed.get("positive") else "negative"
    text = f"{scale.abbreviation} screen {verdict}."
    if present:
        text += " Present: " + ", ".join(present) + "."
    if absent:
        text += " Absent: " + ", ".join(absent) + "."
    text += (" Delirium is a change from baseline, so this screen is interpreted "
             "against the mental status documented on admission.")
    return text


register(Scale(
    scale_id="cam",
    name="Confusion Assessment Method",
    abbreviation="CAM",
    citation="Inouye, S. K., van Dyck, C. H., Alessi, C. A., Balkin, S., Siegal, "
             "A. P., & Horwitz, R. I. (1990). Clarifying confusion: The Confusion "
             "Assessment Method. Annals of Internal Medicine, 113(12), 941-948.",
    purpose="Delirium screening by a four-feature algorithm.",
    note="Copyrighted — see LICENSING. The algorithm is implemented; the "
         "attention-testing items are not reproduced. Score it from your unit's "
         "licensed card.",
    scorer=_score_cam,
    narrator=_narrate_cam,
    reassess_minutes=720,
    items=[
        _yes_no("acute", "Feature 1. Acute change in mental status from baseline, "
                         "or a course that fluctuates through the day", 1,
                hint="CAM feature 1"),
        _yes_no("inattention", "Feature 2. Difficulty focusing, keeping track of "
                              "what is said, or being easily distracted", 1,
                hint="CAM feature 2"),
        _yes_no("disorganised", "Feature 3. Rambling, illogical or unpredictable "
                               "conversation", 1, hint="CAM feature 3"),
        _yes_no("consciousness", "Feature 4. Level of consciousness anything other "
                                "than alert — hyperalert, drowsy, stuporous or "
                                "comatose", 1, hint="CAM feature 4"),
    ],
))


register(Scale(
    scale_id="cam_icu",
    name="Confusion Assessment Method for the ICU",
    abbreviation="CAM-ICU",
    citation="Ely, E. W., Inouye, S. K., Bernard, G. R., Gordon, S., Francis, J., "
             "May, L., … Dittus, R. (2001). Delirium in mechanically ventilated "
             "patients. JAMA, 286(21), 2703-2710.",
    purpose="Delirium screening for patients who cannot speak, using the same "
            "four-feature algorithm with non-verbal testing.",
    note="Copyrighted — see LICENSING. Requires a RASS of -3 or better; at -4 or "
         "-5 the patient is charted as unable to assess rather than negative. "
         "Recording a sedated patient as CAM-ICU negative is a documentation "
         "error that hides delirium.",
    scorer=_score_cam,
    narrator=_narrate_cam,
    reassess_minutes=720,
    settings=("icu", "emergency"),
    items=[
        _yes_no("acute", "Feature 1. Acute change or fluctuation in mental status "
                         "from baseline, including a fluctuating RASS", 1),
        _yes_no("inattention", "Feature 2. Errors on the non-verbal attention "
                              "test used on your unit", 1),
        _yes_no("consciousness", "Feature 3. Current RASS anything other than "
                                "zero", 1),
        _yes_no("disorganised", "Feature 4. Errors on the yes-or-no reasoning "
                               "questions and command test", 1),
    ],
))


# ============================================================== pain assessment


register(Scale(
    scale_id="nrs",
    name="Numeric Rating Scale for pain",
    abbreviation="NRS",
    citation="Downie, W. W., Leatham, P. A., Rhind, V. M., Wright, V., Branco, "
             "J. A., & Anderson, J. A. (1978). Studies with pain rating scales. "
             "Annals of the Rheumatic Diseases, 37(4), 378-381.",
    purpose="Self-reported pain intensity, 0 to 10.",
    note="Self-report is the standard. Chart the number the patient gives, not "
         "the number you would have given.",
    score_range=(0, 10),
    reassess_minutes=60,
    items=[
        Item("score", "Patient's reported pain intensity",
             [Option(str(n), float(n), str(n)) for n in range(11)],
             source_hint="NRS 0-10"),
    ],
    bands=[
        Band(0, 0, "no pain", ""),
        Band(1, 3, "mild", "Commonly used banding: 1-3 mild, 4-6 moderate, "
                           "7-10 severe."),
        Band(4, 6, "moderate", "Commonly used moderate range."),
        Band(7, 10, "severe", "Commonly used severe range."),
    ],
))


register(Scale(
    scale_id="wong_baker",
    name="Wong-Baker FACES Pain Rating Scale",
    abbreviation="FACES",
    citation="Wong, D. L., & Baker, C. M. (1988). Pain in children: Comparison of "
             "assessment scales. Pediatric Nursing, 14(1), 9-17.",
    purpose="Self-reported pain for children and others who do better with faces "
            "than numbers.",
    note="A registered trademark; the artwork is licensed and is NOT reproduced "
         "here. Show the patient your unit's licensed chart and record the anchor "
         "they point to. See LICENSING.",
    score_range=(0, 10),
    reassess_minutes=60,
    settings=("pediatric", "emergency", "med_surg"),
    items=[
        Item("score", "Anchor the patient selected on the licensed FACES chart", [
            Option("0 — no hurt", 0, "0"),
            Option("2 — hurts a little bit", 2, "2"),
            Option("4 — hurts a little more", 4, "4"),
            Option("6 — hurts even more", 6, "6"),
            Option("8 — hurts a whole lot", 8, "8"),
            Option("10 — hurts worst", 10, "10"),
        ], source_hint="FACES anchor"),
    ],
    bands=[
        Band(0, 0, "no pain", ""),
        Band(2, 4, "mild to moderate", ""),
        Band(6, 8, "moderate to severe", ""),
        Band(10, 10, "worst pain", ""),
    ],
))


register(Scale(
    scale_id="flacc",
    name="Face, Legs, Activity, Cry, Consolability scale",
    abbreviation="FLACC",
    citation="Merkel, S. I., Voepel-Lewis, T., Shayevitz, J. R., & Malviya, S. "
             "(1997). The FLACC: A behavioral scale for scoring postoperative "
             "pain in young children. Pediatric Nursing, 23(3), 293-297.",
    purpose="Observed pain for children too young to self-report, or anyone who "
            "cannot.",
    note="Copyrighted by the University of Michigan — see LICENSING. Behavioural "
         "descriptors here are this tool's own wording.",
    score_range=(0, 10),
    reassess_minutes=60,
    settings=("pediatric", "emergency", "icu"),
    items=[
        _graded("face", "Face", [
            ("No particular expression or smile", 0),
            ("Occasional grimace or frown, withdrawn, uninterested", 1),
            ("Frequent to constant frown, clenched jaw, quivering chin", 2),
        ]),
        _graded("legs", "Legs", [
            ("Normal position or relaxed", 0),
            ("Uneasy, restless, tense", 1),
            ("Kicking or legs drawn up", 2),
        ]),
        _graded("activity", "Activity", [
            ("Lying quietly, normal position, moves easily", 0),
            ("Squirming, shifting, tense", 1),
            ("Arched, rigid or jerking", 2),
        ]),
        _graded("cry", "Cry", [
            ("No cry — awake or asleep", 0),
            ("Moans or whimpers, occasional complaint", 1),
            ("Crying steadily, screams or sobs, frequent complaints", 2),
        ]),
        _graded("consolability", "Consolability", [
            ("Content, relaxed", 0),
            ("Reassured by touching, hugging or talking; distractible", 1),
            ("Difficult to console or comfort", 2),
        ]),
    ],
    bands=[
        Band(0, 0, "relaxed and comfortable", ""),
        Band(1, 3, "mild discomfort", "Commonly used banding: 1-3 mild, "
                                      "4-6 moderate, 7-10 severe."),
        Band(4, 6, "moderate pain", "Commonly used moderate range."),
        Band(7, 10, "severe discomfort or pain", "Commonly used severe range."),
    ],
))


register(Scale(
    scale_id="cpot",
    name="Critical-Care Pain Observation Tool",
    abbreviation="CPOT",
    citation="Gélinas, C., Fillion, L., Puntillo, K. A., Viens, C., & Fortier, M. "
             "(2006). Validation of the Critical-Care Pain Observation Tool in "
             "adult patients. American Journal of Critical Care, 15(4), 420-427.",
    purpose="Observed pain in adults who cannot self-report, including ventilated "
            "patients.",
    note="Copyrighted by Gélinas — see LICENSING. Descriptors here are this "
         "tool's own wording.",
    score_range=(0, 8),
    reassess_minutes=60,
    settings=("icu", "emergency"),
    items=[
        _graded("face", "Facial expression", [
            ("Relaxed, neutral", 0),
            ("Tense — frowning, brow lowering, orbit tightening", 1),
            ("Grimacing — all of the above with eyelids tightly closed", 2),
        ]),
        _graded("movements", "Body movements", [
            ("Does not move — not necessarily pain-free", 0),
            ("Protective — slow cautious movements, guarding the site", 1),
            ("Restless — pulling at tubes, attempting to sit, not following "
             "commands", 2),
        ]),
        _graded("tension", "Muscle tension on passive flexion and extension", [
            ("Relaxed, no resistance", 0),
            ("Tense, rigid, some resistance", 1),
            ("Very tense or rigid, strong resistance, unable to complete", 2),
        ]),
        _graded("ventilator", "Ventilator compliance, or vocalisation if extubated", [
            ("Tolerating ventilator, or speaking in a normal tone", 0),
            ("Coughing but tolerating, or sighing and moaning", 1),
            ("Fighting the ventilator, or crying out and sobbing", 2),
        ]),
    ],
    bands=[
        Band(0, 2, "no significant pain by this instrument",
             "A score of 2 or below does not exclude pain; it means the observed "
             "behaviours did not indicate it."),
        Band(3, 8, "significant pain indicated",
             "The published threshold for significant pain is 3 or above."),
    ],
))


# ============================================================= withdrawal


register(Scale(
    scale_id="ciwa_ar",
    name="Clinical Institute Withdrawal Assessment for Alcohol, revised",
    abbreviation="CIWA-Ar",
    citation="Sullivan, J. T., Sykora, K., Schneiderman, J., Naranjo, C. A., & "
             "Sellers, E. M. (1989). Assessment of alcohol withdrawal: The "
             "revised Clinical Institute Withdrawal Assessment for Alcohol scale. "
             "British Journal of Addiction, 84(11), 1353-1357.",
    purpose="Alcohol withdrawal severity across ten items.",
    note="Requires the patient to be able to communicate. CIWA-Ar is not valid in "
         "a patient who cannot report symptoms, and using it on an intubated or "
         "obtunded patient produces a falsely reassuring score.",
    score_range=(0, 67),
    reassess_minutes=60,
    settings=("med_surg", "emergency", "icu"),
    items=[
        _graded("nausea", "Nausea and vomiting", [
            ("None", 0), ("Mild nausea, no vomiting", 1), ("", 2), ("", 3),
            ("Intermittent nausea with dry heaves", 4), ("", 5), ("", 6),
            ("Constant nausea, frequent dry heaves and vomiting", 7),
        ]),
        _graded("tremor", "Tremor with arms extended and fingers apart", [
            ("None", 0), ("Not visible but felt at the fingertips", 1),
            ("", 2), ("", 3), ("Moderate with arms extended", 4), ("", 5),
            ("", 6), ("Severe, even with arms not extended", 7),
        ]),
        _graded("sweats", "Paroxysmal sweats", [
            ("None visible", 0), ("Barely perceptible, palms moist", 1),
            ("", 2), ("", 3), ("Beads of sweat obvious on the forehead", 4),
            ("", 5), ("", 6), ("Drenching sweats", 7),
        ]),
        _graded("anxiety", "Anxiety", [
            ("None, at ease", 0), ("Mildly anxious", 1), ("", 2), ("", 3),
            ("Moderately anxious or guarded", 4), ("", 5), ("", 6),
            ("Equivalent to an acute panic state", 7),
        ]),
        _graded("agitation", "Agitation", [
            ("Normal activity", 0), ("Somewhat more than normal", 1), ("", 2),
            ("", 3), ("Moderately fidgety and restless", 4), ("", 5), ("", 6),
            ("Pacing or thrashing constantly", 7),
        ]),
        _graded("tactile", "Tactile disturbance", [
            ("None", 0), ("Very mild itching, pins and needles or numbness", 1),
            ("Mild", 2), ("Moderate", 3),
            ("Moderately severe hallucinations", 4),
            ("Severe hallucinations", 5), ("Extremely severe hallucinations", 6),
            ("Continuous hallucinations", 7),
        ]),
        _graded("auditory", "Auditory disturbance", [
            ("Not present", 0), ("Very mild harshness or ability to frighten", 1),
            ("Mild", 2), ("Moderate", 3),
            ("Moderately severe hallucinations", 4),
            ("Severe hallucinations", 5), ("Extremely severe hallucinations", 6),
            ("Continuous hallucinations", 7),
        ]),
        _graded("visual", "Visual disturbance", [
            ("Not present", 0), ("Very mild sensitivity", 1), ("Mild", 2),
            ("Moderate", 3), ("Moderately severe hallucinations", 4),
            ("Severe hallucinations", 5), ("Extremely severe hallucinations", 6),
            ("Continuous hallucinations", 7),
        ]),
        _graded("headache", "Headache or fullness in the head", [
            ("Not present", 0), ("Very mild", 1), ("Mild", 2), ("Moderate", 3),
            ("Moderately severe", 4), ("Severe", 5), ("Very severe", 6),
            ("Extremely severe", 7),
        ]),
        _graded("orientation", "Orientation and clouding of sensorium", [
            ("Oriented, can do serial additions", 0),
            ("Cannot do serial additions or is uncertain about the date", 1),
            ("Disoriented to date by no more than two calendar days", 2),
            ("Disoriented to date by more than two calendar days", 3),
            ("Disoriented to place or person", 4),
        ]),
    ],
    bands=[
        Band(0, 8, "minimal withdrawal",
             "Commonly used banding: 8 or below minimal, 9-15 moderate, "
             "16 or above severe with a raised risk of seizure and delirium "
             "tremens."),
        Band(9, 15, "moderate withdrawal", "Commonly used moderate range."),
        Band(16, 67, "severe withdrawal",
             "Commonly used severe range; the published association is with "
             "seizure and delirium tremens risk."),
    ],
))


register(Scale(
    scale_id="cows",
    name="Clinical Opiate Withdrawal Scale",
    abbreviation="COWS",
    citation="Wesson, D. R., & Ling, W. (2003). The Clinical Opiate Withdrawal "
             "Scale (COWS). Journal of Psychoactive Drugs, 35(2), 253-259.",
    purpose="Opioid withdrawal severity across eleven items.",
    score_range=(0, 48),
    reassess_minutes=60,
    settings=("med_surg", "emergency", "icu"),
    items=[
        _graded("pulse", "Resting pulse rate after sitting or lying for one minute", [
            ("80 or below", 0), ("81-100", 1), ("101-120", 2), ("Above 120", 4),
        ]),
        _graded("sweating", "Sweating over the past half hour, not from activity or "
                            "room temperature", [
            ("No report of chills or flushing", 0),
            ("Subjective report of chills or flushing", 1),
            ("Flushed or observable moistness on the face", 2),
            ("Beads of sweat on the brow or face", 3),
            ("Sweat streaming off the face", 4),
        ]),
        _graded("restlessness", "Restlessness during the assessment", [
            ("Able to sit still", 0),
            ("Reports difficulty sitting still but is able to", 1),
            ("Frequent shifting or extraneous movements of legs or arms", 3),
            ("Unable to sit still for more than a few seconds", 5),
        ]),
        _graded("pupil", "Pupil size in room light", [
            ("Pinned or normal size", 0), ("Possibly larger than normal", 1),
            ("Moderately dilated", 2),
            ("So dilated that only the rim of the iris is visible", 5),
        ]),
        _graded("bone_joint", "Bone or joint aches, excluding pre-existing pain", [
            ("Not present", 0), ("Mild diffuse discomfort", 1),
            ("Reports severe diffuse aching in joints or muscles", 2),
            ("Rubbing joints or muscles, unable to sit still because of "
             "discomfort", 4),
        ]),
        _graded("runny_nose", "Runny nose or tearing, not from a cold or allergy", [
            ("Not present", 0), ("Nasal stuffiness or unusually moist eyes", 1),
            ("Nose running or tearing", 2),
            ("Nose constantly running or tears streaming down the cheeks", 4),
        ]),
        _graded("gi", "Gastrointestinal upset over the last half hour", [
            ("No symptoms", 0), ("Stomach cramps", 1),
            ("Nausea or loose stool", 2), ("Vomiting or diarrhoea", 3),
            ("Multiple episodes of diarrhoea or vomiting", 5),
        ]),
        _graded("tremor", "Tremor of the outstretched hands", [
            ("No tremor", 0), ("Tremor can be felt but not observed", 1),
            ("Slight tremor observable", 2), ("Gross tremor or muscle twitching", 4),
        ]),
        _graded("yawning", "Yawning during the assessment", [
            ("None", 0), ("Once or twice", 1), ("Three or more times", 2),
            ("Several times a minute", 4),
        ]),
        _graded("anxiety", "Anxiety or irritability", [
            ("None", 0), ("Reports increasing irritability or anxiousness", 1),
            ("Obviously irritable or anxious", 2),
            ("So irritable or anxious that participation is difficult", 4),
        ]),
        _graded("gooseflesh", "Gooseflesh skin", [
            ("Smooth skin", 0),
            ("Piloerection can be felt or hairs standing up on the arms", 3),
            ("Prominent piloerection", 5),
        ]),
    ],
    bands=[
        Band(0, 4, "no active withdrawal by this instrument", ""),
        Band(5, 12, "mild withdrawal", "Published banding: 5-12 mild, 13-24 "
                                       "moderate, 25-36 moderately severe, "
                                       "37 or above severe."),
        Band(13, 24, "moderate withdrawal", "Published moderate range."),
        Band(25, 36, "moderately severe withdrawal", "Published range."),
        Band(37, 48, "severe withdrawal", "Published severe range."),
    ],
))


# ========================================================== deterioration scores


def _score_qsofa(scale: Scale, responses: dict[str, Any]) -> dict[str, Any]:
    computed = scale._additive(responses)
    total = computed["score"]
    computed["band"] = ("two or more criteria met" if total >= 2
                        else "fewer than two criteria met")
    computed["band_detail"] = (
        "Two or more criteria is the published threshold associated with worse "
        "outcomes in suspected infection. qSOFA is a prognostic prompt, not a "
        "diagnosis of sepsis and not a substitute for your unit's screening tool."
    )
    return computed


register(Scale(
    scale_id="qsofa",
    name="Quick Sequential Organ Failure Assessment",
    abbreviation="qSOFA",
    citation="Seymour, C. W., Liu, V. X., Iwashyna, T. J., Brunkhorst, F. M., "
             "Rea, T. D., Scherag, A., … Angus, D. C. (2016). Assessment of "
             "clinical criteria for sepsis. JAMA, 315(8), 762-774.",
    purpose="Three-criterion bedside prompt for poor outcomes in suspected "
            "infection.",
    score_range=(0, 3),
    scorer=_score_qsofa,
    reassess_minutes=60,
    settings=("emergency", "med_surg", "icu"),
    items=[
        _yes_no("resp", "Respiratory rate 22 breaths per minute or higher", 1),
        _yes_no("mental", "Altered mentation — any Glasgow Coma Scale below 15", 1),
        _yes_no("sbp", "Systolic blood pressure 100 mmHg or lower", 1),
    ],
))


register(Scale(
    scale_id="mews",
    name="Modified Early Warning Score",
    abbreviation="MEWS",
    citation="Subbe, C. P., Kruger, M., Rutherford, P., & Gemmel, L. (2001). "
             "Validation of a modified Early Warning Score in medical admissions. "
             "QJM, 94(10), 521-526.",
    purpose="Aggregate physiological deterioration score.",
    note="Many hospitals run a locally modified MEWS. The point bands here are "
         "the originally published ones; if your unit's differ, its version "
         "governs.",
    score_range=(0, 14),
    reassess_minutes=240,
    settings=("med_surg", "emergency"),
    items=[
        _graded("sbp", "Systolic blood pressure", [
            ("70 or below", 3), ("71-80", 2), ("81-100", 1), ("101-199", 0),
            ("200 or above", 2),
        ]),
        _graded("hr", "Heart rate", [
            ("Below 40", 2), ("40-50", 1), ("51-100", 0), ("101-110", 1),
            ("111-129", 2), ("130 or above", 3),
        ]),
        _graded("rr", "Respiratory rate", [
            ("Below 9", 2), ("9-14", 0), ("15-20", 1), ("21-29", 2),
            ("30 or above", 3),
        ]),
        _graded("temp", "Temperature in degrees Celsius", [
            ("Below 35", 2), ("35-38.4", 0), ("38.5 or above", 2),
        ]),
        _graded("avpu", "Level of consciousness", [
            ("Alert", 0), ("Responds to voice", 1), ("Responds to pain", 2),
            ("Unresponsive", 3),
        ]),
    ],
    bands=[
        Band(0, 2, "low aggregate score", ""),
        Band(3, 4, "raised aggregate score",
             "Commonly used trigger point for increased observation frequency; "
             "follow your unit's escalation policy."),
        Band(5, 14, "high aggregate score",
             "Commonly used trigger for urgent review. A single item scoring 3 is "
             "also a trigger in most policies regardless of the total."),
    ],
))


register(Scale(
    scale_id="news2",
    name="National Early Warning Score 2",
    abbreviation="NEWS2",
    citation="Royal College of Physicians. (2017). National Early Warning Score "
             "(NEWS) 2: Standardising the assessment of acute-illness severity in "
             "the NHS. RCP.",
    purpose="Aggregate deterioration score with a separate scale for patients on "
            "target saturations of 88-92%.",
    note="Royal College of Physicians copyright, licensed with attribution. Use "
         "SpO2 scale 2 only when target saturations of 88-92% are prescribed — "
         "applying it otherwise understates hypoxaemia.",
    score_range=(0, 20),
    reassess_minutes=240,
    settings=("med_surg", "emergency", "icu"),
    items=[
        _graded("rr", "Respiratory rate", [
            ("8 or below", 3), ("9-11", 1), ("12-20", 0), ("21-24", 2),
            ("25 or above", 3),
        ]),
        _graded("spo2", "Oxygen saturation — scale 1, the default", [
            ("91 or below", 3), ("92-93", 2), ("94-95", 1), ("96 or above", 0),
        ], optional=True),
        _graded("spo2_scale2", "Oxygen saturation — scale 2, only if target is "
                              "88-92%", [
            ("83 or below", 3), ("84-85", 2), ("86-87", 1),
            ("88-92, or 93 or above on air", 0),
            ("93-94 on oxygen", 1), ("95-96 on oxygen", 2),
            ("97 or above on oxygen", 3),
        ], optional=True),
        _graded("air_or_oxygen", "Receiving supplemental oxygen", [
            ("Air", 0), ("Oxygen", 2),
        ]),
        _graded("sbp", "Systolic blood pressure", [
            ("90 or below", 3), ("91-100", 2), ("101-110", 1), ("111-219", 0),
            ("220 or above", 3),
        ]),
        _graded("hr", "Pulse", [
            ("40 or below", 3), ("41-50", 1), ("51-90", 0), ("91-110", 1),
            ("111-130", 2), ("131 or above", 3),
        ]),
        _graded("consciousness", "Consciousness", [
            ("Alert", 0), ("Confusion, voice, pain or unresponsive", 3),
        ]),
        _graded("temp", "Temperature in degrees Celsius", [
            ("35.0 or below", 3), ("35.1-36.0", 1), ("36.1-38.0", 0),
            ("38.1-39.0", 1), ("39.1 or above", 2),
        ]),
    ],
    bands=[
        Band(0, 0, "no aggregate score", ""),
        Band(1, 4, "low aggregate score",
             "RCP guidance: ward-based response."),
        Band(5, 6, "medium aggregate score",
             "RCP guidance: key threshold for an urgent review. A single "
             "parameter scoring 3 also triggers review at any total."),
        Band(7, 20, "high aggregate score",
             "RCP guidance: emergency response threshold."),
    ],
))


register(Scale(
    scale_id="sofa",
    name="Sequential Organ Failure Assessment",
    abbreviation="SOFA",
    citation="Vincent, J. L., Moreno, R., Takala, J., Willatts, S., De Mendonça, "
             "A., Bruining, H., … Thijs, L. G. (1996). The SOFA score to describe "
             "organ dysfunction/failure. Intensive Care Medicine, 22(7), 707-710.",
    purpose="Organ dysfunction across six systems, scored serially.",
    note="A trend score. One SOFA value describes a moment; the change over 24 to "
         "48 hours is what the literature associates with outcome.",
    score_range=(0, 24),
    reassess_minutes=1440,
    settings=("icu",),
    items=[
        _graded("respiration", "Respiration — PaO2/FiO2 ratio in mmHg", [
            ("400 or above", 0), ("Below 400", 1), ("Below 300", 2),
            ("Below 200 with respiratory support", 3),
            ("Below 100 with respiratory support", 4),
        ]),
        _graded("coagulation", "Coagulation — platelets ×10³/µL", [
            ("150 or above", 0), ("Below 150", 1), ("Below 100", 2),
            ("Below 50", 3), ("Below 20", 4),
        ]),
        _graded("liver", "Liver — bilirubin mg/dL", [
            ("Below 1.2", 0), ("1.2-1.9", 1), ("2.0-5.9", 2), ("6.0-11.9", 3),
            ("12.0 or above", 4),
        ]),
        _graded("cardiovascular", "Cardiovascular", [
            ("MAP 70 mmHg or above", 0), ("MAP below 70 mmHg", 1),
            ("Dopamine 5 or below, or any dobutamine", 2),
            ("Dopamine above 5, epinephrine 0.1 or below, or norepinephrine "
             "0.1 or below, all mcg/kg/min", 3),
            ("Dopamine above 15, epinephrine above 0.1, or norepinephrine above "
             "0.1, all mcg/kg/min", 4),
        ]),
        _graded("cns", "Central nervous system — Glasgow Coma Scale", [
            ("15", 0), ("13-14", 1), ("10-12", 2), ("6-9", 3), ("Below 6", 4),
        ]),
        _graded("renal", "Renal — creatinine mg/dL or urine output", [
            ("Below 1.2", 0), ("1.2-1.9", 1), ("2.0-3.4", 2),
            ("3.5-4.9, or urine output below 500 mL/day", 3),
            ("5.0 or above, or urine output below 200 mL/day", 4),
        ]),
    ],
    bands=[
        Band(0, 6, "low organ dysfunction score", ""),
        Band(7, 12, "moderate organ dysfunction score", ""),
        Band(13, 24, "high organ dysfunction score",
             "The published association is between rising serial scores and "
             "mortality, not between any single total and an individual outcome."),
    ],
))


register(Scale(
    scale_id="apache_ii",
    name="Acute Physiology and Chronic Health Evaluation II",
    abbreviation="APACHE II",
    citation="Knaus, W. A., Draper, E. A., Wagner, D. P., & Zimmerman, J. E. "
             "(1985). APACHE II: A severity of disease classification system. "
             "Critical Care Medicine, 13(10), 818-829.",
    purpose="ICU severity of illness from the worst values in the first 24 hours.",
    note="Copyrighted — see LICENSING. Two cautions that matter more than the "
         "arithmetic: it uses the WORST value of each variable in the first 24 "
         "hours after admission, so it is not a bedside or shift score; and it "
         "predicts mortality for cohorts, not for the patient in front of you. "
         "Charting an APACHE II as though it were a current assessment "
         "misrepresents it.",
    score_range=(0, 71),
    settings=("icu",),
    items=[
        _graded("temp", "Worst temperature in degrees Celsius", [
            ("41 or above", 4), ("39-40.9", 3), ("38.5-38.9", 1),
            ("36-38.4", 0), ("34-35.9", 1), ("32-33.9", 2), ("30-31.9", 3),
            ("Below 30", 4),
        ]),
        _graded("map", "Worst mean arterial pressure in mmHg", [
            ("160 or above", 4), ("130-159", 3), ("110-129", 2), ("70-109", 0),
            ("50-69", 2), ("Below 50", 4),
        ]),
        _graded("hr", "Worst heart rate", [
            ("180 or above", 4), ("140-179", 3), ("110-139", 2), ("70-109", 0),
            ("55-69", 2), ("40-54", 3), ("Below 40", 4),
        ]),
        _graded("rr", "Worst respiratory rate", [
            ("50 or above", 4), ("35-49", 3), ("25-34", 1), ("12-24", 0),
            ("10-11", 1), ("6-9", 2), ("Below 6", 4),
        ]),
        _graded("oxygenation", "Oxygenation — A-a gradient if FiO2 is 0.5 or above, "
                               "otherwise PaO2", [
            ("A-a gradient 500 or above", 4), ("A-a gradient 350-499", 3),
            ("A-a gradient 200-349", 2), ("A-a gradient below 200", 0),
            ("PaO2 above 70", 0), ("PaO2 61-70", 1), ("PaO2 55-60", 3),
            ("PaO2 below 55", 4),
        ]),
        _graded("ph", "Worst arterial pH", [
            ("7.7 or above", 4), ("7.6-7.69", 3), ("7.5-7.59", 1),
            ("7.33-7.49", 0), ("7.25-7.32", 2), ("7.15-7.24", 3),
            ("Below 7.15", 4),
        ]),
        _graded("sodium", "Worst serum sodium mmol/L", [
            ("180 or above", 4), ("160-179", 3), ("155-159", 2), ("150-154", 1),
            ("130-149", 0), ("120-129", 2), ("111-119", 3), ("Below 111", 4),
        ]),
        _graded("potassium", "Worst serum potassium mmol/L", [
            ("7 or above", 4), ("6-6.9", 3), ("5.5-5.9", 1), ("3.5-5.4", 0),
            ("3-3.4", 1), ("2.5-2.9", 2), ("Below 2.5", 4),
        ]),
        _graded("creatinine", "Worst serum creatinine mg/dL — double the points in "
                              "acute renal failure", [
            ("3.5 or above", 4), ("2-3.4", 3), ("1.5-1.9", 2), ("0.6-1.4", 0),
            ("Below 0.6", 2),
        ]),
        _graded("haematocrit", "Worst haematocrit percentage", [
            ("60 or above", 4), ("50-59.9", 2), ("46-49.9", 1), ("30-45.9", 0),
            ("20-29.9", 2), ("Below 20", 4),
        ]),
        _graded("wbc", "Worst white cell count ×10³/mm³", [
            ("40 or above", 4), ("20-39.9", 2), ("15-19.9", 1), ("3-14.9", 0),
            ("1-2.9", 2), ("Below 1", 4),
        ]),
        _graded("gcs_points", "15 minus the Glasgow Coma Scale", [
            ("0", 0), ("1", 1), ("2", 2), ("3", 3), ("4", 4), ("5", 5), ("6", 6),
            ("7", 7), ("8", 8), ("9", 9), ("10", 10), ("11", 11), ("12", 12),
        ]),
        _graded("age", "Age points", [
            ("44 or younger", 0), ("45-54", 2), ("55-64", 3), ("65-74", 5),
            ("75 or older", 6),
        ]),
        _graded("chronic_health", "Chronic health points", [
            ("No severe organ insufficiency or immunocompromise", 0),
            ("Severe organ insufficiency or immunocompromise, elective "
             "postoperative", 2),
            ("Severe organ insufficiency or immunocompromise, non-operative or "
             "emergency postoperative", 5),
        ]),
    ],
    bands=[
        Band(0, 9, "lower severity range", ""),
        Band(10, 19, "moderate severity range", ""),
        Band(20, 29, "high severity range", ""),
        Band(30, 71, "very high severity range",
             "The published mortality figures are cohort predictions and are not "
             "individual prognoses."),
    ],
))


# ============================================================= paediatric scores


register(Scale(
    scale_id="pews",
    name="Pediatric Early Warning Score",
    abbreviation="PEWS",
    citation="Monaghan, A. (2005). Detecting and managing deterioration in "
             "children. Paediatric Nursing, 17(1), 32-35.",
    purpose="Aggregate deterioration score for children across behaviour, "
            "cardiovascular and respiratory domains.",
    note="PEWS is locally adapted almost everywhere, and the age-banded vital "
         "sign thresholds differ between versions. This implements the commonly "
         "used three-domain structure with nurse-concern and therapy modifiers; "
         "your hospital's version governs.",
    score_range=(0, 13),
    reassess_minutes=240,
    settings=("pediatric", "emergency"),
    items=[
        _graded("behaviour", "Behaviour", [
            ("Playing or appropriate for age", 0),
            ("Sleeping", 1),
            ("Irritable", 2),
            ("Lethargic, confused, or reduced response to pain", 3),
        ]),
        _graded("cardiovascular", "Cardiovascular", [
            ("Pink, or capillary refill 1-2 seconds", 0),
            ("Pale, or capillary refill 3 seconds", 1),
            ("Grey, capillary refill 4 seconds, or heart rate 20 above normal "
             "for age", 2),
            ("Grey and mottled, capillary refill 5 seconds or more, or heart "
             "rate 30 above normal for age, or bradycardia", 3),
        ]),
        _graded("respiratory", "Respiratory", [
            ("Within normal parameters for age, no retractions", 0),
            ("Rate 10 above normal for age, accessory muscle use, or 30% or more "
             "FiO2 or 3 L/min or more", 1),
            ("Rate 20 above normal for age, retractions, or 40% or more FiO2 or "
             "6 L/min or more", 2),
            ("Rate 5 or more below normal for age with retractions and grunting, "
             "or 50% or more FiO2 or 8 L/min or more", 3),
        ]),
        _yes_no("nebulisers", "Persistent vomiting after surgery, or quarter-hourly "
                             "nebulised treatment", 2),
        _yes_no("nurse_concern", "Nurse or family concern out of proportion to the "
                                "score", 2,
                hint="Present in most local versions; a documented concern is a "
                     "valid trigger on its own"),
    ],
    bands=[
        Band(0, 2, "low aggregate score", ""),
        Band(3, 4, "raised aggregate score",
             "A common local trigger for increased observation and a senior "
             "review."),
        Band(5, 13, "high aggregate score",
             "A common local trigger for urgent review or a rapid response call."),
    ],
))


def _score_pat(scale: Scale, responses: dict[str, Any]) -> dict[str, Any]:
    """The Pediatric Assessment Triangle is not a numeric score.

    It is a structured first impression across appearance, work of breathing and
    circulation to the skin. Forcing it into a total would misrepresent it, so this
    scorer reports which limbs are abnormal and what physiological state that
    pattern is classically associated with.
    """
    def abnormal(item_id: str) -> bool | None:
        raw = responses.get(item_id)
        if raw is None or raw == "":
            return None
        return str(raw).lower() not in ("normal", "no", "0")

    limbs = {k: abnormal(k) for k in ("appearance", "breathing", "circulation")}
    missing = [scale.item(k).label for k, v in limbs.items()
               if v is None and scale.item(k)]
    if any(v is None for v in limbs.values()):
        return {"score": None, "subscores": {}, "missing": missing,
                "band": "incomplete",
                "band_detail": "All three limbs are needed for a first impression."}

    abnormal_limbs = [k for k, v in limbs.items() if v]
    patterns = {
        (): "stable first impression",
        ("appearance",): "possible central nervous system or metabolic problem",
        ("breathing",): "respiratory distress",
        ("circulation",): "possible compensated shock",
        ("appearance", "breathing"): "respiratory failure",
        ("appearance", "circulation"): "shock",
        ("breathing", "circulation"): "respiratory distress with poor perfusion",
        ("appearance", "breathing", "circulation"): "cardiopulmonary failure",
    }
    key = tuple(k for k in ("appearance", "breathing", "circulation") if k in abnormal_limbs)
    return {
        "score": float(len(abnormal_limbs)),
        "subscores": {k: 1.0 if v else 0.0 for k, v in limbs.items()},
        "missing": [],
        "band": patterns.get(key, "abnormal first impression"),
        "band_detail": ("The Pediatric Assessment Triangle is a structured first "
                        "impression, not a score. The number here is only a count "
                        "of abnormal limbs."),
        "abnormal": abnormal_limbs,
    }


def _narrate_pat(scale: Scale, computed: dict[str, Any]) -> str:
    if computed.get("score") is None:
        return "Pediatric Assessment Triangle: not completed."
    abnormal = computed.get("abnormal") or []
    responses = computed.get("responses") or {}
    described = []
    for limb, label in (("appearance", "appearance"),
                        ("breathing", "work of breathing"),
                        ("circulation", "circulation to the skin")):
        value = str(responses.get(limb, "")).strip()
        described.append(f"{label} {value or 'not recorded'}")
    text = ("Pediatric Assessment Triangle: " + ", ".join(described) + ". ")
    if abnormal:
        text += (f"Abnormal in {len(abnormal)} of 3 limbs, a pattern classically "
                 f"associated with {computed.get('band')}.")
    else:
        text += "All three limbs within normal appearance for age."
    return text


register(Scale(
    scale_id="pat",
    name="Pediatric Assessment Triangle",
    abbreviation="PAT",
    citation="Dieckmann, R. A., Brownstein, D., & Gausche-Hill, M. (2010). The "
             "Pediatric Assessment Triangle. Pediatric Emergency Care, 26(4), "
             "312-315.",
    purpose="A structured first impression of a child from across the room, before "
            "hands are laid on.",
    note="Not a numeric score — see the scale's own detail. Charted as a pattern.",
    scorer=_score_pat,
    narrator=_narrate_pat,
    settings=("pediatric", "emergency"),
    items=[
        Item("appearance", "Appearance — tone, interactiveness, consolability, "
                           "look or gaze, speech or cry", [
            Option("Normal for age", 0, "normal"),
            Option("Abnormal — one or more elements off", 1, "abnormal"),
        ]),
        Item("breathing", "Work of breathing — abnormal sounds, position, "
                          "retractions, nasal flaring, head bobbing", [
            Option("Normal for age", 0, "normal"),
            Option("Abnormal — increased or decreased effort", 1, "abnormal"),
        ]),
        Item("circulation", "Circulation to the skin — pallor, mottling, cyanosis", [
            Option("Normal for age", 0, "normal"),
            Option("Abnormal", 1, "abnormal"),
        ]),
    ],
))


# ================================================================= burns & area


# Lund-Browder percentages by age band. Each entry is
# (region, {age_band: percent_of_total_body_surface_area}). The age dependence is
# the whole point of the chart: a newborn's head is roughly 19% of body surface
# and an adult's is 7%, so the rule of nines materially overestimates burn size in
# small children — which then overestimates fluid resuscitation.
_LUND_BROWDER = {
    "head": {"0": 19, "1": 17, "5": 13, "10": 11, "15": 9, "adult": 7},
    "neck": {"0": 2, "1": 2, "5": 2, "10": 2, "15": 2, "adult": 2},
    "anterior_trunk": {"0": 13, "1": 13, "5": 13, "10": 13, "15": 13, "adult": 13},
    "posterior_trunk": {"0": 13, "1": 13, "5": 13, "10": 13, "15": 13, "adult": 13},
    "right_buttock": {"0": 2.5, "1": 2.5, "5": 2.5, "10": 2.5, "15": 2.5, "adult": 2.5},
    "left_buttock": {"0": 2.5, "1": 2.5, "5": 2.5, "10": 2.5, "15": 2.5, "adult": 2.5},
    "genitalia": {"0": 1, "1": 1, "5": 1, "10": 1, "15": 1, "adult": 1},
    "right_upper_arm": {"0": 4, "1": 4, "5": 4, "10": 4, "15": 4, "adult": 4},
    "left_upper_arm": {"0": 4, "1": 4, "5": 4, "10": 4, "15": 4, "adult": 4},
    "right_lower_arm": {"0": 3, "1": 3, "5": 3, "10": 3, "15": 3, "adult": 3},
    "left_lower_arm": {"0": 3, "1": 3, "5": 3, "10": 3, "15": 3, "adult": 3},
    "right_hand": {"0": 2.5, "1": 2.5, "5": 2.5, "10": 2.5, "15": 2.5, "adult": 2.5},
    "left_hand": {"0": 2.5, "1": 2.5, "5": 2.5, "10": 2.5, "15": 2.5, "adult": 2.5},
    "right_thigh": {"0": 5.5, "1": 6.5, "5": 8, "10": 8.5, "15": 9, "adult": 9.5},
    "left_thigh": {"0": 5.5, "1": 6.5, "5": 8, "10": 8.5, "15": 9, "adult": 9.5},
    "right_leg": {"0": 5, "1": 5, "5": 5.5, "10": 6, "15": 6.5, "adult": 7},
    "left_leg": {"0": 5, "1": 5, "5": 5.5, "10": 6, "15": 6.5, "adult": 7},
    "right_foot": {"0": 3.5, "1": 3.5, "5": 3.5, "10": 3.5, "15": 3.5, "adult": 3.5},
    "left_foot": {"0": 3.5, "1": 3.5, "5": 3.5, "10": 3.5, "15": 3.5, "adult": 3.5},
}

_LB_AGE_BANDS = [
    ("0", "Under 1 year"),
    ("1", "1 to 4 years"),
    ("5", "5 to 9 years"),
    ("10", "10 to 14 years"),
    ("15", "15 years"),
    ("adult", "Adult"),
]

_LB_REGION_LABELS = {
    "head": "Head", "neck": "Neck",
    "anterior_trunk": "Anterior trunk", "posterior_trunk": "Posterior trunk",
    "right_buttock": "Right buttock", "left_buttock": "Left buttock",
    "genitalia": "Genitalia",
    "right_upper_arm": "Right upper arm", "left_upper_arm": "Left upper arm",
    "right_lower_arm": "Right lower arm", "left_lower_arm": "Left lower arm",
    "right_hand": "Right hand", "left_hand": "Left hand",
    "right_thigh": "Right thigh", "left_thigh": "Left thigh",
    "right_leg": "Right lower leg", "left_leg": "Left lower leg",
    "right_foot": "Right foot", "left_foot": "Left foot",
}


def _score_lund_browder(scale: Scale, responses: dict[str, Any]) -> dict[str, Any]:
    """Total burn surface area from partial and full-thickness involvement.

    `responses` carries an age band plus, per region, the fraction of that region
    involved (0, 0.25, 0.5, 0.75, 1). Superficial (first-degree) burns are
    excluded from the total, which is the convention the resuscitation formulae
    assume — including them inflates the calculated fluid requirement.
    """
    band = str(responses.get("age_band", "adult"))
    if band not in ("0", "1", "5", "10", "15", "adult"):
        band = "adult"
    # The item table declares flat `region_<name>` fields, which is what the front
    # end sends; a nested `regions` map is also accepted so a caller can post the
    # whole chart in one object.
    nested = responses.get("regions") or {}
    total = 0.0
    subscores: dict[str, float] = {}
    for region, percentages in _LUND_BROWDER.items():
        raw = responses.get(f"region_{region}", nested.get(region))
        if raw in (None, "", 0, "0"):
            continue
        try:
            fraction = float(raw)
        except (TypeError, ValueError):
            continue
        fraction = min(max(fraction, 0.0), 1.0)
        contribution = round(percentages[band] * fraction, 2)
        if contribution:
            subscores[region] = contribution
            total += contribution
    total = round(total, 1)
    detail = (f"Age band used: "
              f"{dict(_LB_AGE_BANDS).get(band, band)}. Superficial burns are "
              f"excluded from this total, as the resuscitation formulae assume "
              f"partial and full thickness only.")
    return {"score": total, "subscores": subscores, "missing": [],
            "band": f"{total:g}% total body surface area",
            "band_detail": detail, "age_band": band}


def _narrate_lund_browder(scale: Scale, computed: dict[str, Any]) -> str:
    total = computed.get("score") or 0.0
    subscores = computed.get("subscores") or {}
    if not subscores:
        return "Lund-Browder chart completed: no partial or full-thickness burn area recorded."
    listed = ", ".join(
        f"{_LB_REGION_LABELS.get(region, region)} {value:g}%"
        for region, value in sorted(subscores.items(), key=lambda kv: -kv[1])
    )
    band = dict(_LB_AGE_BANDS).get(str(computed.get("age_band")), "adult")
    return (f"Burn area estimated by Lund-Browder chart at {total:g}% total body "
            f"surface area using the {band.lower()} column: {listed}. "
            f"Superficial burn excluded from the total.")


register(Scale(
    scale_id="lund_browder",
    name="Lund-Browder chart for burn surface area",
    abbreviation="Lund-Browder",
    citation="Lund, C. C., & Browder, N. C. (1944). The estimation of areas of "
             "burns. Surgery, Gynecology and Obstetrics, 79, 352-358.",
    purpose="Age-adjusted total body surface area burned.",
    note="Use this rather than the rule of nines in children. A newborn's head is "
         "about 19% of body surface against an adult's 7%, so the rule of nines "
         "overestimates burn size in small children and therefore overestimates "
         "the fluid they are given.",
    scorer=_score_lund_browder,
    narrator=_narrate_lund_browder,
    settings=("emergency", "icu", "pediatric"),
    items=[
        Item("age_band", "Age band for the chart column",
             [Option(label, 0, key) for key, label in _LB_AGE_BANDS]),
    ] + [
        Item(f"region_{region}", _LB_REGION_LABELS[region], [
            Option("None", 0, "0"),
            Option("One quarter", 0.25, "0.25"),
            Option("Half", 0.5, "0.5"),
            Option("Three quarters", 0.75, "0.75"),
            Option("All", 1.0, "1"),
        ], optional=True)
        for region in _LUND_BROWDER
    ],
))


# ====================================================================== triage


# The danger-zone vital sign criteria at ESI decision point D, by age band.
_ESI_VITAL_LIMITS = [
    ("under_3m", "Under 3 months", {"hr": 180, "rr": 50}),
    ("3m_3y", "3 months to 3 years", {"hr": 160, "rr": 40}),
    ("3y_8y", "3 to 8 years", {"hr": 140, "rr": 30}),
    ("over_8y", "Over 8 years and adult", {"hr": 100, "rr": 20}),
]


def _score_esi(scale: Scale, responses: dict[str, Any]) -> dict[str, Any]:
    """Walk the four ESI decision points and show the working.

    Deliberately does not "auto-suggest" a level from vital signs. The
    specification asked for auto-suggestion from vitals and chief complaint; that
    is clinical decision support, it is wrong often enough to be dangerous, and a
    triage level a tool assigned is indefensible in a deposition. What this does
    instead is answer each decision point the nurse answered, report the level the
    published algorithm yields from those answers, and label it as computed.
    """
    def yes(key: str) -> bool:
        return str(responses.get(key, "")).lower() in ("yes", "y", "true", "1")

    steps: list[str] = []

    if yes("life_saving"):
        steps.append("Decision point A: a life-saving intervention is required.")
        return {"score": 1.0, "subscores": {}, "missing": [],
                "band": "level 1 by the algorithm",
                "band_detail": " ".join(steps), "steps": steps}
    steps.append("Decision point A: no life-saving intervention required.")

    high_risk = yes("high_risk")
    confused = yes("confused")
    severe_pain = yes("severe_pain")
    if high_risk or confused or severe_pain:
        which = [name for name, flag in (
            ("a high-risk situation", high_risk),
            ("new confusion, lethargy or disorientation", confused),
            ("severe pain or distress", severe_pain)) if flag]
        steps.append("Decision point B: " + ", ".join(which) + " present.")
        return {"score": 2.0, "subscores": {}, "missing": [],
                "band": "level 2 by the algorithm",
                "band_detail": " ".join(steps), "steps": steps}
    steps.append("Decision point B: no high-risk situation, no new confusion, "
                 "no severe pain or distress.")

    raw_resources = responses.get("resources")
    if raw_resources in (None, ""):
        return {"score": None, "subscores": {}, "missing": ["Expected resources"],
                "band": "incomplete",
                "band_detail": " ".join(steps
                                        + ["Decision point C needs the number of "
                                           "expected resources."]),
                "steps": steps}
    try:
        resources = int(float(raw_resources))
    except (TypeError, ValueError):
        resources = 0

    if resources == 0:
        steps.append("Decision point C: no resources expected.")
        return {"score": 5.0, "subscores": {}, "missing": [],
                "band": "level 5 by the algorithm",
                "band_detail": " ".join(steps), "steps": steps}
    if resources == 1:
        steps.append("Decision point C: one resource expected.")
        return {"score": 4.0, "subscores": {}, "missing": [],
                "band": "level 4 by the algorithm",
                "band_detail": " ".join(steps), "steps": steps}

    steps.append(f"Decision point C: {resources} or more resources expected.")
    danger = yes("danger_vitals")
    if danger:
        steps.append("Decision point D: vital signs in the danger zone for age, "
                     "which the algorithm treats as grounds to consider "
                     "up-triage to level 2.")
        return {"score": 2.0, "subscores": {}, "missing": [],
                "band": "level 3 with danger-zone vitals — consider level 2",
                "band_detail": " ".join(steps), "steps": steps}
    steps.append("Decision point D: vital signs not in the danger zone for age.")
    return {"score": 3.0, "subscores": {}, "missing": [],
            "band": "level 3 by the algorithm",
            "band_detail": " ".join(steps), "steps": steps}


def _narrate_esi(scale: Scale, computed: dict[str, Any]) -> str:
    if computed.get("score") is None:
        return "Emergency Severity Index: decision points incomplete."
    steps = computed.get("steps") or []
    return (f"Emergency Severity Index computed as {computed.get('band')} from the "
            f"decision points recorded. " + " ".join(steps)
            + " Level computed by this tool from the nurse's answers; the triage "
              "level of record is the one the triage nurse assigns.")


register(Scale(
    scale_id="esi",
    name="Emergency Severity Index",
    abbreviation="ESI",
    citation="Gilboy, N., Tanabe, P., Travers, D., & Rosenau, A. M. (2020). "
             "Emergency Severity Index (ESI): A triage tool for emergency "
             "department care, version 4. Emergency Nurses Association.",
    purpose="Five-level triage acuity from four decision points.",
    note="Licensed to the Emergency Nurses Association — see LICENSING. This "
         "computes the level the algorithm yields from the decision points you "
         "answer, and shows the working. It does not read your vital signs and "
         "propose a level: assigning triage acuity from vitals alone is unsafe, "
         "and a level a tool assigned is not one you can defend.",
    scorer=_score_esi,
    narrator=_narrate_esi,
    score_range=(1, 5),
    higher_is_worse=False,
    settings=("emergency",),
    items=[
        _yes_no("life_saving", "A. Does this patient require an immediate "
                              "life-saving intervention — airway, breathing, "
                              "circulation or an immediate medication?", 1),
        _yes_no("high_risk", "B. Is this a high-risk situation in your judgement?", 1),
        _yes_no("confused", "B. New confusion, lethargy or disorientation?", 1),
        _yes_no("severe_pain", "B. Severe pain or distress?", 1),
        Item("resources", "C. How many resources do you expect this patient to "
                          "need?", [
            Option("None", 0, "0"),
            Option("One", 1, "1"),
            Option("Two or more", 2, "2"),
        ], source_hint="ESI resource count"),
        _yes_no("danger_vitals", "D. Are the vital signs in the danger zone for "
                                "this patient's age?", 1,
                hint="Age thresholds are listed in scales.esi_vital_limits()"),
    ],
))


def esi_vital_limits() -> list[dict[str, Any]]:
    """The danger-zone thresholds, shown next to decision point D.

    Displayed rather than applied. The nurse decides whether the vitals are in the
    danger zone; the tool shows what the published thresholds are so that decision
    is informed rather than remembered.
    """
    return [
        {"key": key, "label": label,
         "heart_rate_above": limits["hr"],
         "respiratory_rate_above": limits["rr"]}
        for key, label, limits in _ESI_VITAL_LIMITS
    ]


def vitals_outside_esi_zone(vitals: Vitals, age_band_key: str) -> list[str]:
    """Which danger-zone thresholds the recorded vitals exceed.

    Returns descriptions, not a level. This is the informational half of decision
    point D: the nurse sees "HR 168 exceeds the 160 threshold for 3 months to 3
    years" and answers the question themselves.
    """
    limits = next((l for k, _, l in _ESI_VITAL_LIMITS if k == age_band_key), None)
    if not limits:
        return []
    found: list[str] = []
    if vitals.heart_rate is not None and vitals.heart_rate > limits["hr"]:
        found.append(f"heart rate {vitals.heart_rate:g} exceeds the "
                     f"{limits['hr']} threshold for this age band")
    if vitals.respiratory_rate is not None and vitals.respiratory_rate > limits["rr"]:
        found.append(f"respiratory rate {vitals.respiratory_rate:g} exceeds the "
                     f"{limits['rr']} threshold for this age band")
    if vitals.spo2 is not None and vitals.spo2 < 92:
        found.append(f"oxygen saturation {vitals.spo2:g}% is below the 92% "
                     f"threshold the handbook flags at triage")
    return found


# ------------------------------------------------------------------ conveniences


def prefill_from_vitals(scale_id: str, vitals: Vitals) -> dict[str, Any]:
    """Suggest option keys for items a recorded vital sign already answers.

    Only offered for the aggregate warning scores, where the mapping from a number
    to a band is arithmetic rather than judgement. It returns *suggestions* the
    front end shows pre-selected and the nurse can change — it never scores on the
    nurse's behalf, and nothing here touches a scale where the item requires
    looking at the patient.
    """
    scale = get(scale_id)
    if not scale:
        return {}

    def pick(item_id: str, value: float | None,
             ranges: list[tuple[float, float, str]]) -> str:
        """Resolve a measurement to an option key by matching the option's label.

        The label is matched rather than a hard-coded key so this cannot drift out
        of step with the item tables above: if an option's wording changes, its
        slug changes, and looking it up by label keeps working.
        """
        if value is None:
            return ""
        item = scale.item(item_id)
        if not item:
            return ""
        for low, high, label in ranges:
            if low <= value <= high:
                wanted = _slug(label)
                return next((o.key() for o in item.options if o.key() == wanted), "")
        return ""

    if scale_id == "qsofa":
        out: dict[str, Any] = {}
        if vitals.respiratory_rate is not None:
            out["resp"] = "yes" if vitals.respiratory_rate >= 22 else "no"
        if vitals.systolic is not None:
            out["sbp"] = "yes" if vitals.systolic <= 100 else "no"
        return out

    if scale_id == "mews":
        return {k: v for k, v in {
            "sbp": pick("sbp", vitals.systolic,
                        [(0, 70, "70 or below"), (71, 80, "71-80"),
                         (81, 100, "81-100"), (101, 199, "101-199"),
                         (200, 400, "200 or above")]),
            "hr": pick("hr", vitals.heart_rate,
                       [(0, 39, "Below 40"), (40, 50, "40-50"),
                        (51, 100, "51-100"), (101, 110, "101-110"),
                        (111, 129, "111-129"), (130, 400, "130 or above")]),
            "rr": pick("rr", vitals.respiratory_rate,
                       [(0, 8, "Below 9"), (9, 14, "9-14"), (15, 20, "15-20"),
                        (21, 29, "21-29"), (30, 99, "30 or above")]),
            "temp": pick("temp", vitals.temperature_c,
                         [(0, 34.99, "Below 35"), (35, 38.49, "35-38.4"),
                          (38.5, 45, "38.5 or above")]),
        }.items() if v}

    if scale_id == "news2":
        prefilled = {k: v for k, v in {
            "rr": pick("rr", vitals.respiratory_rate,
                       [(0, 8, "8 or below"), (9, 11, "9-11"), (12, 20, "12-20"),
                        (21, 24, "21-24"), (25, 99, "25 or above")]),
            "spo2": pick("spo2", vitals.spo2,
                         [(0, 91, "91 or below"), (92, 93, "92-93"),
                          (94, 95, "94-95"), (96, 100, "96 or above")]),
            "sbp": pick("sbp", vitals.systolic,
                        [(0, 90, "90 or below"), (91, 100, "91-100"),
                         (101, 110, "101-110"), (111, 219, "111-219"),
                         (220, 400, "220 or above")]),
            "hr": pick("hr", vitals.heart_rate,
                       [(0, 40, "40 or below"), (41, 50, "41-50"),
                        (51, 90, "51-90"), (91, 110, "91-110"),
                        (111, 130, "111-130"), (131, 400, "131 or above")]),
            "temp": pick("temp", vitals.temperature_c,
                         [(0, 35, "35.0 or below"), (35.01, 36, "35.1-36.0"),
                          (36.01, 38, "36.1-38.0"), (38.01, 39, "38.1-39.0"),
                          (39.01, 45, "39.1 or above")]),
        }.items() if v}
        # Scale 2 is deliberately never prefilled: it applies only when target
        # saturations of 88-92% have been prescribed, which is a fact about the
        # order set and not something a saturation reading can imply.
        if vitals.oxygen_delivery:
            on_oxygen = "room air" not in vitals.oxygen_delivery.lower()
            prefilled["air_or_oxygen"] = "oxygen" if on_oxygen else "air"
        return prefilled

    if scale_id in ("nrs", "wong_baker") and vitals.pain_score is not None:
        return {"score": str(int(vitals.pain_score))}

    return {}


def catalogue(setting: str = "") -> list[dict[str, Any]]:
    """Every scale, or the ones relevant to a setting, as JSON for the front end."""
    scales = for_setting(setting) if setting else list(REGISTRY.values())
    return [scale.as_dict() for scale in scales]
