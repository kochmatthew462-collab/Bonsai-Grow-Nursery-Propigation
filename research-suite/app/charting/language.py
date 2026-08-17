"""
The Objective Language Filter: a spell-checker for legally dangerous wording.

It works the way a spell-checker works — scan the text, return matches with
character offsets and suggested replacements, let the writer decide — except that
what it flags is not misspelling. It flags the five kinds of language that turn a
defensible note into a liability, plus the abbreviations that cause medication
errors, plus the handful of things that must never appear in a clinical note at
all.

## The one subtlety that makes this usable

**Direct quotations are exempt.** "Patient stated, 'I'm so angry I could scream'"
is *excellent* documentation — the subjective word belongs to the patient, is
attributed, and is exactly what a chart should preserve. A checker that flagged
"angry" there would train the nurse to stop quoting patients, which is the
opposite of what you want. So `quoted_spans()` finds quotation marks first and
every rule skips what is inside them.

The same exemption covers the reverse case: the filter *encourages* quotes. Where
a rule's fix is "write what the patient said", the suggestion says so.

## Severity

* **block** — the save is refused. Four rules only: a reference to an incident
  report, a reference to another patient, blame directed at a named colleague,
  and an admission of error phrased as fault. Everything about these is settled
  law-and-policy rather than style, and none has a legitimate use in a clinical
  note.
* **warn** — flagged, editable, saved if the nurse chooses. The note records that
  the warning was shown and acknowledged, which is itself protective: it
  demonstrates the language was a considered choice.
* **info** — a nudge, mostly about precision.

## Why "block" is a short list

A checker that blocks on style makes nurses fight the tool, and a nurse fighting a
tool at 0300 writes a worse note than one with no tool at all. Everything that is
a matter of judgement warns. Only the four things that are never right block.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .models import Flag, Severity

# ------------------------------------------------------------------- quote spans


_QUOTE_PATTERNS = [
    re.compile(r"\"[^\"\n]{1,400}\""),          # "…"
    re.compile(r"[“][^”\n]{1,400}[”]"),         # curly doubles
    re.compile(r"(?<![A-Za-z])'[^'\n]{2,400}'(?![A-Za-z])"),   # '…', not an apostrophe
    re.compile(r"[‘][^’\n]{2,400}[’]"),
]


def quoted_spans(text: str) -> list[tuple[int, int]]:
    """Character ranges holding attributed speech.

    The single-quote patterns guard against apostrophes: `don't` must not open a
    quote, so a `'` only counts when it is not flanked by letters.
    """
    spans: list[tuple[int, int]] = []
    for pattern in _QUOTE_PATTERNS:
        for match in pattern.finditer(text):
            spans.append((match.start(), match.end()))
    return _merge(spans)


def _merge(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    if not spans:
        return []
    ordered = sorted(spans)
    merged = [ordered[0]]
    for start, end in ordered[1:]:
        if start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def _inside(spans: list[tuple[int, int]], start: int, end: int) -> bool:
    return any(s <= start and end <= e for s, e in spans)


# ------------------------------------------------------------------------- rules


@dataclass
class Rule:
    code: str
    pattern: str
    category: str
    message: str
    suggestion: str
    severity: Severity = Severity.WARN
    replacements: list[str] = field(default_factory=list)
    quote_exempt: bool = True
    flags: int = re.IGNORECASE

    def compiled(self) -> re.Pattern[str]:
        if not hasattr(self, "_compiled"):
            self._compiled = re.compile(self.pattern, self.flags)
        return self._compiled


# The categories are the ones from the specification, kept in its order so the UI
# can group by them: judgmental, emotional, assumptive, vague, liability. Three
# more were added — stigmatising, staffing, and dosing — for reasons given at each.
CATEGORIES = {
    "judgmental": "Judgmental — characterises the patient rather than describing them",
    "emotional": "Emotional — an interpretation presented as an observation",
    "assumptive": "Assumptive — states as fact something that was inferred",
    "vague": "Vague — cannot be verified or reproduced by a reader",
    "liability": "Liability — assigns fault, or admits it, in a clinical record",
    "stigmatising": "Stigmatising — language shown to change how later clinicians treat the patient",
    "staffing": "Wrong document — a unit problem recorded in a patient's chart",
    "dosing": "Dosing notation — abbreviations that cause medication errors",
    "privacy": "Privacy — content that must not appear in this patient's record",
}


RULES: list[Rule] = [

    # ------------------------------------------------------- hard blocks

    Rule(
        code="incident_report",
        pattern=r"\b(incident\s+report|event\s+report|occurrence\s+report|"
                r"risk\s+management|safety\s+report|near\s+miss\s+report)\b",
        category="liability",
        severity=Severity.BLOCK,
        # The specification gave this message verbatim. It is reproduced exactly
        # rather than paraphrased, because the wording is what the nurse reads at
        # the moment they are about to make the mistake.
        message="Error: Do not reference incident reports in the clinical chart. "
                "Document only the clinical facts of the event.",
        suggestion="Delete the reference. Chart what happened to the patient, "
                   "what you assessed, who you notified and what was done. File "
                   "the incident report separately — it is a distinct document "
                   "with its own protections, and naming it in the chart is what "
                   "puts those protections at risk.",
        replacements=[],
    ),
    Rule(
        code="other_patient",
        pattern=r"\b(?:the\s+)?(?:other|another|room\s*\d+(?:'s)?|bed\s*\d+(?:'s)?)\s+"
                r"patient(?:'s)?\b|\bmy\s+other\s+patient\b",
        category="privacy",
        severity=Severity.BLOCK,
        message="Another patient must not appear in this patient's record.",
        suggestion="Remove the reference. If the other patient is why something "
                   "was delayed, record the delay and the reason without "
                   "identifying anyone: \"Response delayed by a concurrent "
                   "emergency on the unit; charge nurse notified at 1420.\"",
    ),
    Rule(
        code="blame_colleague",
        pattern=r"\b(?:Dr\.?|Doctor|NP|PA|RN|nurse|resident|attending|therapist)\s+"
                r"[A-Z][a-zA-Z\-']{1,20}\s+(?:failed\s+to|neglected\s+to|"
                r"refused\s+to|did\s+not\s+bother|never\s+(?:came|responded|"
                r"answered)|was\s+(?:wrong|negligent|careless))",
        category="liability",
        severity=Severity.BLOCK,
        message="Do not assign fault to a named colleague in the chart.",
        suggestion="State the facts and let them speak: \"Paged Dr. Alvarez at "
                   "1412 and again at 1435. No response received. Escalated to "
                   "the charge nurse at 1440 and to the hospitalist on call at "
                   "1445.\" That documents the same failure and is unimpeachable, "
                   "because every clause is a verifiable fact rather than a "
                   "conclusion about someone's conduct.",
        flags=0,   # case-sensitive: the capitalised surname is the whole point
    ),
    Rule(
        code="admission_of_fault",
        pattern=r"\b(by\s+mistake|by\s+accident|accidentally|inadvertently|"
                r"my\s+fault|I\s+forgot|I\s+failed\s+to|error\s+on\s+my\s+part|"
                r"should\s+have\s+(?:been|given|checked|noticed)|"
                r"wrong\s+(?:med|medication|dose|patient|site|route|time|"
                r"limb|side|blood|product|chart))\b",
        category="liability",
        severity=Severity.BLOCK,
        message="This phrases an event as fault. Chart what happened, not whose "
                "fault it was.",
        suggestion="State exactly what happened, when it was recognised, what you "
                   "assessed, who you notified and what was done. \"At 0910, "
                   "0.5 mg was given rather than the ordered 0.25 mg. Recognised "
                   "at 0915. Vital signs taken: BP 118/72, HR 76. Dr. Chen "
                   "notified at 0918; orders received to monitor hourly for four "
                   "hours.\" Nothing there is an admission, and everything there "
                   "is a fact — which is what both a reviewer and a defence "
                   "attorney need.",
    ),

    # ------------------------------------------------------- judgmental

    Rule(
        code="noncompliant",
        pattern=r"\b(non[\s-]?compliant|noncompliance|non[\s-]?adherent|"
                r"uncooperative|difficult\s+patient|unmotivated|lazy)\b",
        category="judgmental",
        message="Characterises the patient instead of recording what happened.",
        suggestion="Describe the behaviour and your response: \"Patient declined "
                   "the 0900 metoprolol. Educated on the risk of rebound "
                   "hypertension and tachycardia. Patient verbalised "
                   "understanding and continued to decline. Dr. Osei notified at "
                   "0915.\"",
        replacements=["declined", "did not take", "chose not to"],
    ),
    Rule(
        code="refused",
        pattern=r"\b(refus(?:ed|es|ing|al))\b",
        category="judgmental",
        severity=Severity.WARN,
        message="\"Refused\" reads as defiance and, on its own, does not show "
                "that the patient was informed.",
        suggestion="\"Declined\" plus the education you gave: \"Patient declined "
                   "the dressing change. Explained the infection risk. Patient "
                   "stated, 'I want to wait until my daughter is here.' Will "
                   "reoffer at 1600.\" A declination with documented education "
                   "and a reoffer is defensible; a bare refusal is not.",
        replacements=["declined"],
    ),
    Rule(
        code="drug_seeking",
        pattern=r"\b(drug[\s-]?seek(?:ing|er)|frequent\s+flyer|malinger(?:ing|er)|"
                r"faking|attention[\s-]?seeking|manipulative|"
                r"pill[\s-]?seek(?:ing|er)|narcotic\s+seek\w*)\b",
        category="stigmatising",
        message="Stigmatising language. This is the category with the best "
                "evidence of downstream harm — notes carrying it change how "
                "later clinicians assess the same patient's pain — and it is "
                "indefensible if the patient reads their record, which they are "
                "entitled to do.",
        suggestion="Record the request, the assessment and the decision: "
                   "\"Patient requested additional hydromorphone at 1340, 90 "
                   "minutes after the previous dose. Reports pain 8/10. RR 12, "
                   "sedation scale 1. Next dose due 1500 per order. Dr. Park "
                   "notified at 1345; no new orders.\"",
        replacements=["requested", "asked for"],
    ),

    # ------------------------------------------------------- emotional

    Rule(
        code="emotional_label",
        pattern=r"\b(aggressive|angry|hostile|combative|belligerent|abusive|"
                r"agitated|anxious|depressed|drunk|intoxicated|high|"
                r"psychotic|crazy|confused)\b",
        category="emotional",
        message="An interpretation stated as an observation. A reader cannot tell "
                "what you actually saw.",
        suggestion="Write what you saw and heard. Instead of \"patient was "
                   "aggressive and drunk\": \"Patient shouting, pacing the room, "
                   "struck the bedside table with an open hand. Strong odour of "
                   "alcohol on the breath. Speech slurred. Gait unsteady, "
                   "requiring two-person assist.\" Every clause of that survives "
                   "cross-examination; \"aggressive and drunk\" does not.",
        replacements=[],
    ),
    Rule(
        code="tolerated_well",
        # Up to three words between "tolerated" and "well", so "tolerated the walk
        # well" and "tolerated the procedure well" are caught alongside the bare
        # form — the padded version is the one nurses actually write.
        pattern=r"\b(tolerated\s+(?:\w+\s+){0,3}well|did\s+well|doing\s+well|"
                r"no\s+complaints|uneventful|unremarkable)\b",
        category="vague",
        message="Not verifiable. A reader learns nothing about the patient's "
                "actual state.",
        suggestion="Say what you measured. \"Ambulated 40 feet with a front-wheel "
                   "walker and one-person assist. SpO2 94% on room air before, "
                   "92% after, returning to 95% within two minutes of rest. "
                   "Denied dyspnoea and chest pain. Gait steady.\"",
    ),

    # ------------------------------------------------------- assumptive

    Rule(
        code="appears_seems",
        pattern=r"\b(appears?\s+to\s+be|appears?|seems?\s+to\s+be|seems?|"
                r"apparently|evidently|presumably|looks\s+like|"
                r"probably|must\s+have\s+been)\b",
        category="assumptive",
        message="Hedged inference. If you observed it, state it; if you inferred "
                "it, say what you observed and what you concluded.",
        suggestion="Split the observation from the conclusion: not \"appears "
                   "comfortable\" but \"lying still with eyes closed, respirations "
                   "regular and unlaboured at 14, no grimacing or guarding, "
                   "denied pain when roused.\" Then, if you want the conclusion, "
                   "own it in the assessment section rather than the objective "
                   "one.",
    ),
    Rule(
        code="sleeping",
        pattern=r"\b(sleeping|asleep|resting\s+comfortably|napping)\b",
        category="assumptive",
        message="You cannot observe sleep, only its appearance — and this is the "
                "single most litigated word in nursing documentation, because a "
                "patient charted as sleeping who was in fact unresponsive is a "
                "case that settles.",
        suggestion="\"Lying in bed with eyes closed, respirations regular and "
                   "unlaboured at 16, no response to name spoken at normal "
                   "volume, roused to light touch and oriented to person and "
                   "place.\" If you did not rouse the patient, do not imply that "
                   "you could have.",
    ),
    Rule(
        code="denies",
        pattern=r"\b(denies|denied)\b",
        category="judgmental",
        severity=Severity.INFO,
        message="\"Denies\" carries a faint suggestion of disbelief. It is "
                "conventional and widely accepted, so this is a nudge rather "
                "than a correction.",
        suggestion="\"Reports no chest pain\" or \"states he has no chest pain\" "
                   "reads as neutral. Keep \"denies\" if it is your unit's "
                   "convention.",
        replacements=["reports no", "states no"],
    ),

    # ------------------------------------------------------- vague

    Rule(
        code="ate_well",
        pattern=r"\b(ate\s+(?:well|good|fine|most|some)|"
                r"good\s+(?:appetite|intake)|"
                r"poor\s+(?:appetite|intake)|drank\s+(?:well|some|a\s+little))\b",
        category="vague",
        message="Not quantified.",
        suggestion="Give the number: \"Consumed 80% of the lunch tray\" or "
                   "\"Oral intake 240 mL over the shift.\"",
    ),
    Rule(
        code="good_night",
        # "Good night" belongs here rather than with the meal rule. It used to be
        # matched by `ate_well`, which then offered "consumed 80% of the meal" as
        # the objective alternative to a statement about sleep.
        pattern=r"\b(slept\s+(?:well|all\s+night|through\s+the\s+night)|"
                r"restful\s+night|good\s+night|quiet\s+(?:night|shift))\b",
        category="vague",
        message="Not quantified, and \"slept all night\" implies continuous "
                "observation you probably did not have.",
        suggestion="\"Eyes closed with regular respirations at each hourly "
                   "check between 2300 and 0500. Awake and requesting the toilet "
                   "at 0130.\"",
    ),
    Rule(
        code="adequate",
        pattern=r"\b(adequate|sufficient|appropriate|as\s+needed|prn\s+basis|"
                r"as\s+tolerated|frequently|occasionally|periodically|"
                r"several\s+times|a\s+few\s+times|multiple\s+times|"
                r"regularly|routinely|"
                r"per\s+(?:protocol|policy|routine))\b",
        category="vague",
        message="Unquantified or unspecified.",
        suggestion="Give a number, a time or a name. \"Repositioned at 2000, "
                   "2200, 0000 and 0200\" rather than \"repositioned "
                   "frequently\". \"Per the adult sepsis order set\" rather than "
                   "\"per protocol\" — a protocol you did not name is a protocol "
                   "nobody can confirm you followed.",
    ),
    Rule(
        code="md_aware",
        pattern=r"\b(?:MD|M\.D\.|doctor|physician|provider|NP|PA|team)\s+"
                r"(?:is\s+|was\s+)?(?:aware|notified|informed|updated|called)\b"
                r"(?![^.]{0,80}\bat\s+\d)",
        category="vague",
        severity=Severity.WARN,
        message="A notification with no time, no name and no response is the "
                "weakest sentence in nursing documentation, and it is the one "
                "plaintiff's counsel looks for first.",
        suggestion="Use the Provider Notification block, which requires all four: "
                   "\"At 1412, paged Dr. Alvarez (hospitalist) regarding a "
                   "systolic of 84. Reported BP 84/50, HR 118, patient alert. "
                   "Dr. Alvarez responded at 1418 with orders for a 500 mL "
                   "lactated Ringer's bolus and a repeat pressure in 30 minutes. "
                   "Continued to monitor.\"",
    ),

    # ------------------------------------------------------- staffing

    Rule(
        code="staffing_complaint",
        # "management" is deliberately not matched on its own: pain management,
        # airway management and wound management are all ordinary clinical
        # language, and flagging them would make the rule noise.
        pattern=r"\b(short[\s-]?staffed|understaffed|no\s+help|too\s+many\s+patients|"
                r"unsafe\s+(?:assignment|staffing|ratio)|"
                r"(?:management|administration|supervisor)\s+"
                r"(?:refused|denied|declined|would\s+not|ignored|said\s+no)|"
                r"no\s+one\s+(?:available|answered|would\s+help))\b",
        category="staffing",
        message="A staffing problem does not belong in a patient's chart. It "
                "belongs in the shift and assignment record, where it protects "
                "you without handing the plaintiff a theory of the case.",
        suggestion="Move it to the Assignment and Staffing record on this "
                   "encounter, which timestamps it and records who you raised it "
                   "with. In the chart, document the patient's care and its "
                   "timing factually. A contemporaneous assignment record showing "
                   "you carried nine patients and escalated it is powerful "
                   "evidence; the same sentence in a chart note reads as an "
                   "excuse.",
    ),

    # ------------------------------------------------------- dosing notation

    # From the ISMP list of error-prone abbreviations and the Joint Commission's
    # minimum "do not use" list. These are the notations with documented death and
    # injury cases behind them, which is why they are here rather than in a style
    # guide.
    Rule(
        code="trailing_zero",
        pattern=r"\b(\d+\.0)\s*(mg|mcg|g|mL|units?|mEq)\b",
        category="dosing",
        message="A trailing zero has been read as a tenfold overdose when the "
                "decimal point was missed. On the Joint Commission's do-not-use "
                "list.",
        suggestion="Write the whole number: 1 mg, not 1.0 mg.",
    ),
    Rule(
        code="naked_decimal",
        pattern=r"(?<![\d.])\.\d+\s*(mg|mcg|g|mL|units?|mEq)\b",
        category="dosing",
        message="A decimal with no leading zero has been read as a tenfold "
                "overdose. On the Joint Commission's do-not-use list.",
        suggestion="Write a leading zero: 0.5 mg, not .5 mg.",
    ),
    Rule(
        code="unit_abbrev",
        pattern=r"(?<![A-Za-z])(?:U|IU)(?![A-Za-z])(?=\s|$|\.|,)",
        category="dosing",
        message="\"U\" has been misread as 0, 4 and cc; \"IU\" as IV and 10. Both "
                "are on the Joint Commission's do-not-use list, and both have "
                "insulin deaths behind them.",
        suggestion="Write \"units\" or \"international units\" in full.",
        replacements=["units", "international units"],
        flags=0,
    ),
    Rule(
        code="latin_frequency",
        pattern=r"(?<![A-Za-z])(q\.?d\.?|q\.?o\.?d\.?|q\.?i\.?d\.?|b\.?i\.?d\.?|"
                r"t\.?i\.?d\.?|h\.?s\.?|o\.?d\.?|o\.?s\.?|o\.?u\.?|"
                r"a\.?s\.?|a\.?d\.?|a\.?u\.?|s\.?c\.?|s\.?q\.?)(?![A-Za-z])",
        category="dosing",
        severity=Severity.INFO,
        message="Error-prone Latin abbreviation. \"qd\" and \"qod\" are confused "
                "with each other and with \"qid\"; the eye and ear pairs (od/os/"
                "ou, ad/as/au) are confused with each other.",
        suggestion="Write the frequency out: \"daily\", \"every other day\", "
                   "\"four times a day\", \"at bedtime\", \"right eye\", "
                   "\"subcutaneous\". Note that \"q4h\" and similar interval "
                   "notations are fine — it is the Latin that causes errors.",
        flags=0,
    ),
    Rule(
        code="dangerous_drug_abbrev",
        pattern=r"(?<![A-Za-z])(MS|MSO4|MgSO4|HCT|HCTZ|AZT|CPZ|DPT|"
                r"6\s*MP|TAC|ZnSO4|APAP|"
                r"cc)(?![A-Za-z])",
        category="dosing",
        message="Ambiguous drug abbreviation. \"MS\" means morphine sulphate to "
                "some readers and magnesium sulphate to others; \"cc\" is "
                "misread as \"u\" and as zeros.",
        suggestion="Write the drug name in full, and use mL rather than cc.",
        flags=0,
    ),
    Rule(
        code="at_symbol",
        pattern=r"(?<=\d)\s*@\s*(?=\d)",
        category="dosing",
        severity=Severity.INFO,
        message="\"@\" is misread as \"2\" and as \"0\".",
        suggestion="Write \"at\".",
        replacements=[" at "],
    ),
]


# ------------------------------------------------------------------------ engine


def scan(text: str, *, field_path: str = "") -> list[Flag]:
    """Flag every rule hit outside quoted speech, in document order.

    Overlapping hits from different rules are all reported: "patient appears
    non-compliant and refused" genuinely has three separate problems, and merging
    them would hide two.
    """
    if not text or not text.strip():
        return []
    exempt = quoted_spans(text)
    found: list[Flag] = []
    for rule in RULES:
        for match in rule.compiled().finditer(text):
            start, end = match.span()
            if rule.quote_exempt and _inside(exempt, start, end):
                continue
            found.append(Flag(
                code=rule.code,
                severity=rule.severity,
                message=rule.message,
                field_path=field_path,
                excerpt=match.group(0),
                suggestion=rule.suggestion,
                offset=start,
                length=end - start,
            ))
    found.sort(key=lambda f: (f.offset, f.code))
    return found


def scan_many(fields: dict[str, str]) -> list[Flag]:
    """Scan several named fields, keeping each flag tied to its field."""
    flags: list[Flag] = []
    for name, value in fields.items():
        flags.extend(scan(value or "", field_path=name))
    return flags


def blocking(flags: list[Flag]) -> list[Flag]:
    return [f for f in flags if f.severity is Severity.BLOCK]


def rule_table() -> list[dict[str, Any]]:
    """The whole rule set, for the settings screen and the export appendix.

    Shown in full deliberately: a nurse who understands *why* "sleeping" is
    flagged writes better notes everywhere, including in the EHR where this tool
    cannot follow them. A checker that only says "don't" teaches nothing.
    """
    by_category: dict[str, list[dict[str, Any]]] = {}
    for rule in RULES:
        by_category.setdefault(rule.category, []).append({
            "code": rule.code,
            "severity": rule.severity.value,
            "message": rule.message,
            "suggestion": rule.suggestion,
            "replacements": rule.replacements,
        })
    return [
        {"category": key, "label": CATEGORIES.get(key, key), "rules": rules}
        for key, rules in sorted(
            by_category.items(),
            key=lambda kv: list(CATEGORIES).index(kv[0])
            if kv[0] in CATEGORIES else 99,
        )
    ]


# --------------------------------------------------------------- quote assistance


_UNATTRIBUTED = re.compile(
    r"\b(?:patient|pt|resident|client|family|mother|father|spouse|daughter|son)\s+"
    r"(?:stated|said|reported|told\s+me|verbalized|verbalised|expressed|"
    r"complained\s+of|c/o)\b",
    re.IGNORECASE,
)


def suggest_quotes(text: str) -> list[Flag]:
    """Nudge toward a direct quote where speech is reported indirectly.

    Separate from `scan` because it is an opportunity rather than a defect, and
    because it inverts the usual advice: for the *patient's own words*, verbatim
    is better than paraphrase. A jury hears "Patient stated, 'It feels like an
    elephant is sitting on my chest'" very differently from "patient reported
    chest discomfort", and only one of them is the patient's testimony.
    """
    if not text:
        return []
    exempt = quoted_spans(text)
    flags: list[Flag] = []
    for match in _UNATTRIBUTED.finditer(text):
        tail = text[match.end(): match.end() + 200]
        if any(mark in tail[:80] for mark in ('"', "“", "”")):
            continue
        if _inside(exempt, *match.span()):
            continue
        flags.append(Flag(
            code="prefer_direct_quote",
            severity=Severity.INFO,
            message="Reported speech. The patient's own words are stronger "
                    "evidence than your summary of them, and they are exempt "
                    "from every objective-language rule here.",
            suggestion="Quote it: Patient stated, \"…\". Use quotation marks — "
                       "this checker skips everything inside them, because what "
                       "the patient said is data, not your characterisation.",
            excerpt=match.group(0),
            offset=match.start(),
            length=match.end() - match.start(),
        ))
    return flags
