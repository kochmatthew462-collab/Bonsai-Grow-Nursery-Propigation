"""
Grammar and spelling for clinical notes.

The request asked for the charting tab to "grammar/spell check properly". A
general-purpose checker pointed at a nursing note does not do that — it produces
so much noise that it gets switched off within one shift, and a checker that is
switched off catches nothing. Three reasons, each handled here:

**1. Nursing notes are deliberately fragmentary.** "Alert and oriented ×4."
"Denies chest pain." "Bed low, brakes locked, call light within reach." Every one
of those is a sentence fragment and every one is correct clinical documentation.
A checker set to flag fragments would flag most of a good note, so the
fragment, agreement-with-fragment and sentence-start rules are off (see
`DISABLED_RULES`).

**2. Clinical vocabulary is not in a general dictionary.** "PERRLA", "hydromorphone",
"nasogastric", "q4h", "PRN", "levophed" — a spell-checker calls all of these
misspellings. So spelling hits are filtered against `clinical_dictionary()`, which
is **derived from this package** wherever possible: every option label in
`systems.py`, every scale name and item label in `scales.py`, every drug and class
in `interlocks.LOOP_RULES`, plus a curated list of medications, abbreviations and
anatomy. Deriving it means the dictionary cannot drift out of step with the
vocabulary the tab itself offers.

**3. Clinical notation looks like broken text.** `BP 84/50`, `SpO2 88%`,
`0.5 mg/kg`, `1412`, `GCS 15 (E4 V5 M6)`, `2+ pitting`, `L × W × D`. Left alone,
the checker "fixes" these into prose. They are masked at **equal length** before
the request goes out, exactly as `writing/proof.py` does for APA statistics, so
the offsets that come back still point at the right characters.

## What this is and is not

It runs against the same self-hosted LanguageTool server as the research half, so
nothing leaves the machine. It is **optional**: with no server running, the tab
still composes, checks language, and exports, and it says so rather than silently
skipping.

It is also not the important checker in this tab. A misspelling is embarrassing;
"patient appears sleeping" is a lawsuit. `language.py` is the one that matters,
runs with no server, and never gets switched off. This one is the polish pass.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import httpx

from . import scales as scales_module, systems as systems_module
from .models import Flag, Severity

DEFAULT_LANGUAGETOOL_URL = "http://localhost:8081/v2/check"
DEFAULT_LANGUAGE = "en-US"

# Rules that fire constantly on correct nursing documentation. Each one is off for
# a stated reason, because a disabled rule with no reason is how a checker quietly
# stops checking things it should.
DISABLED_RULES = [
    "SENTENCE_FRAGMENT",             # "Denies chest pain." is correct charting
    "FRAGMENT_TWO_ARTICLES",
    "MISSING_VERB",                  # "Bed low, brakes locked, alarm on."
    "UPPERCASE_SENTENCE_START",      # notes routinely open on a time or a value
    "PUNCTUATION_PARAGRAPH_END",
    "WHITESPACE_RULE",
    "COMMA_PARENTHESIS_WHITESPACE",
    "EN_QUOTES",                     # straight quotes around patient speech
    "DASH_RULE",
    "PASSIVE_VOICE",                 # "was administered" is standard
    "TOO_LONG_SENTENCE",
    "SENTENCE_WHITESPACE",
    "ARTICLE_MISSING",               # "Patient ambulated to bathroom."
    "THE_SUPERLATIVE",
    "PLURAL_VERB_AFTER_THIS",
    "ENGLISH_WORD_REPEAT_BEGINNING_RULE",
    "ADVERB_WORD_ORDER",
]

# Spans that must reach the server as filler rather than as text. Ordered
# most-specific-first for the same reason `writing/proof.py` is: a general pattern
# that swallows half of a longer construct leaves the remainder exposed.
_PROTECTED = [
    # Vital-sign notation
    r"\bBP\s*\d{2,3}\s*/\s*\d{2,3}(?:\s*mmHg)?",
    r"\bMAP\s*\d{2,3}(?:\s*mmHg)?",
    r"\b(?:HR|RR|SpO2|SpO₂|EtCO2|EtCO₂|CVP)\s*\d{1,3}(?:\s*%)?",
    r"\bT\s*\d{2}(?:\.\d)?\s*°?\s*[CF]\b",
    r"\b\d{1,3}(?:\.\d)?\s*°\s*[CF]\b",
    # Scored scales, including the GCS component breakdown
    r"\bGCS\s*\d{1,2}(?:\s*/\s*15)?(?:\s*\([^)]*\))?",
    r"\b(?:E|V|M)(?:\d|NT)\b",
    r"\b(?:RASS|NIHSS|Braden|Morse|FLACC|CPOT|PEWS|MEWS|NEWS2?|CIWA-Ar|COWS|"
    r"qSOFA|SOFA|APACHE\s*II|ESI|Caprini)\s*[-+]?\d{1,3}",
    # Dose and rate notation
    r"\b\d+(?:\.\d+)?\s*(?:mcg|mg|g|kg|mL|L|units?|mEq|mmol|ng)"
    r"(?:\s*/\s*(?:kg|hr|h|min|day|dL|L|m2))*",
    r"\b\d+(?:\.\d+)?\s*mL\s*/\s*(?:hr|h|min)",
    # Times: military and clock, plus intervals
    r"(?<![\d:/])\b(?:[01]\d|2[0-3])[0-5]\d\b(?![\d:/])",
    r"\b(?:[01]?\d|2[0-3]):[0-5]\d\b",
    r"\bq\s*\d{1,2}\s*(?:h|hr|hrs|min)\b",
    # Grades, strengths, stages and measurements
    r"\b[0-4]\+",
    r"\b[0-5]\s*/\s*5\b",
    r"\b\d+(?:\.\d+)?\s*(?:cm|mm)(?:\s*[×x]\s*\d+(?:\.\d+)?\s*(?:cm|mm)?){0,2}",
    r"\bstage\s*(?:1|2|3|4|I{1,3}V?|unstageable)\b",
    r"\b(?:oriented\s*)?[×x]\s*[1-4]\b",
    # Percentages, ratios and lab values
    r"\b\d+(?:\.\d+)?\s*%",
    r"\b\d{1,2}\s*:\s*\d{1,2}\b",
    r"\b(?:1|2|3)?\d{1,3}(?:\.\d+)?\s*(?:mg/dL|mmol/L|mEq/L|g/dL|ng/mL|"
    r"µg/L|IU/L|U/L|mmHg)",
    # Bare identifiers that would otherwise be "corrected"
    r"\bFiO2\s*\d+(?:\.\d+)?%?",
    r"\b\d+\s*L\s*/\s*min\b",
]


@dataclass
class ProofResult:
    flags: list[Flag] = field(default_factory=list)
    available: bool = False
    engine: str = "LanguageTool"
    note: str = ""
    checked_words: int = 0
    suppressed_clinical: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "flags": [f.as_dict() for f in self.flags],
            "available": self.available,
            "engine": self.engine,
            "note": self.note,
            "checked_words": self.checked_words,
            "suppressed_clinical": self.suppressed_clinical,
        }


# ------------------------------------------------------------------ dictionary


# Medications, abbreviations, anatomy and clinical terms that a general dictionary
# does not carry. Kept short and high-frequency on purpose: the derived half of the
# dictionary does most of the work, and a hand-list that tried to be a formulary
# would rot.
_CURATED_TERMS = """
acetaminophen albuterol alteplase amiodarone amlodipine amoxicillin apixaban
atorvastatin azithromycin bupivacaine carvedilol cefazolin ceftriaxone
chlorhexidine clopidogrel dabigatran dexamethasone dexmedetomidine diltiazem
diphenhydramine dobutamine docusate enoxaparin epoetin ertapenem esmolol
esomeprazole famotidine fentanyl furosemide gabapentin glargine haloperidol
heparin hydralazine hydrochlorothiazide hydromorphone ibuprofen insulin
ipratropium ketamine ketorolac labetalol lactulose levetiracetam levofloxacin
levothyroxine lidocaine lisinopril lorazepam losartan meropenem metformin
methylprednisolone metoclopramide metoprolol metronidazole midazolam milrinone
mirtazapine morphine moxifloxacin naloxone nicardipine nitroglycerin
norepinephrine olanzapine ondansetron oxycodone pantoprazole phenylephrine
piperacillin polyethylene potassium pravastatin prednisone propofol quetiapine
ranitidine rivaroxaban rocuronium salbutamol senna sertraline sevoflurane
simvastatin spironolactone succinylcholine sugammadex tamsulosin tazobactam
tenecteplase ticagrelor tramadol vancomycin vasopressin venlafaxine warfarin
zoledronic

levophed neosynephrine precedex dilaudid toradol zofran protonix lovenox
coumadin lasix ativan versed haldol narcan tylenol motrin colace senokot
novolog humalog lantus levemir tresiba humulin

PERRLA WDL PRN NPO NKDA BiPAP CPAP HFNC ETT LMA NGT OGT PEG PICC CVC IJ EJ
AVF AVG SCD TED DVT VTE CAUTI CLABSI HAPI MDRO MRSA VRE CDI ESBL
ADLs ROM AAOx AOx PIV IVPB IVP SQ subq subcut IM ID PO PR SL NG
telemetry sinus tachycardic bradycardic normotensive hypotensive hypertensive
hypoxic hypoxaemic hypoxemic tachypnoeic tachypneic dyspnoeic dyspneic
diaphoretic afebrile febrile euvolaemic euvolemic hypovolaemic hypovolemic
oliguric anuric polyuric nocturia dysuria haematuria hematuria
auscultated palpated percussed inspected
crackles rhonchi wheezes stridor rales egophony
antecubital dorsalis pedis radialis brachialis femoral popliteal
sacrum sacral coccyx trochanter olecranon calcaneus occiput ischial
periwound eschar slough granulation epithelialisation epithelialization
maceration excoriation erythema blanchable nonblanchable induration
unstageable
tunnelling tunneling undermining serosanguinous serosanguineous purulent
ecchymosis petechiae urticaria
nasogastric orogastric gastrostomy jejunostomy nephrostomy urostomy ileostomy
colostomy tracheostomy thoracostomy jugular subclavian
ambulate ambulated ambulating ambulatory reposition repositioned
premedicate premedicated titrate titrated titration bolus bolused
extubate extubated intubate intubated suction suctioned lavage
foley purewick condom catheterise catheterize catheterisation catheterization
delirium delirious obtunded lethargic somnolent stuporous comatose
aphasia aphasic dysarthria dysarthric dysphagia dysphagic hemiparesis
hemiplegia paraplegia quadriplegia paraesthesia paresthesia
sepsis septic bacteraemia bacteremia urosepsis pneumonia aspiration
withdrawal detoxification benzodiazepine opioid opiate naloxone
anticoagulated anticoagulation thrombolytic thrombolysis
hypoglycaemia hypoglycemia hyperglycaemia hyperglycemia ketoacidosis
normoglycaemic normoglycemic euglycaemic euglycemic
"""


def _tokens(text: str) -> set[str]:
    """Every word-like token in a string, lowercased.

    Hyphenated and slashed compounds are split as well as kept whole, so both
    "front-wheel" and "wheel" resolve — a spell-checker flags the part, not the
    compound.
    """
    found: set[str] = set()
    for raw in re.split(r"[^A-Za-z\u00C0-\u024F'’-]+", text or ""):
        word = raw.strip("-'’").lower()
        if len(word) < 2:
            continue
        found.add(word)
        for piece in word.split("-"):
            if len(piece) >= 3:
                found.add(piece)
    return found


_DICTIONARY: set[str] | None = None


def clinical_dictionary() -> set[str]:
    """Terms a general spell-checker would wrongly flag.

    Built once and cached. The derived half — everything this tab itself offers as
    a clickable option — is what keeps it honest: if a new system element or scale
    item is added above, its vocabulary is in the dictionary automatically, so the
    checker cannot start flagging words the tool put in the note.
    """
    global _DICTIONARY
    if _DICTIONARY is not None:
        return _DICTIONARY

    # Curated terms keep their length: several real clinical abbreviations are two
    # or three characters ("IJ", "NPO", "PRN", "WDL") and dropping them would mean
    # the checker flags them.
    words: set[str] = set(_tokens(_CURATED_TERMS))

    derived: set[str] = set()

    # Derived: every body-system label, element label, option and WDL statement.
    for system in systems_module.SYSTEMS:
        derived |= _tokens(system.label)
        derived |= _tokens(system.wdl_statement)
        for element in system.elements:
            derived |= _tokens(element.label)
            derived |= _tokens(element.hint)
            for option in element.options:
                derived |= _tokens(option)

    # Derived: every scale name, abbreviation, item and option label.
    for scale in scales_module.REGISTRY.values():
        derived |= _tokens(scale.name)
        derived |= _tokens(scale.abbreviation)
        for item in scale.items:
            derived |= _tokens(item.label)
            for option in item.options:
                derived |= _tokens(option.label)
        for band in scale.bands:
            derived |= _tokens(band.label)

    # Derived: every drug and class name the closed-loop rules match on. Several
    # are prefixes rather than words ("analgesi", "hypoglyc") — harmless in a
    # dictionary, and dropping them would mean the checker flags the full form.
    from . import interlocks as interlocks_module
    for _key, needles, _minutes, _what in interlocks_module.LOOP_RULES:
        for needle in needles:
            derived |= _tokens(needle)

    # Derived tokens are floored at four characters. The option labels are written
    # in English prose, so deriving from them sweeps up "the", "and", "are", "was"
    # — short function words that a spell-checker already knows and that have no
    # business in a clinical dictionary. Leaving them in was actively harmful: a
    # grammar rule flagging "are" would have been suppressed as "clinical
    # vocabulary".
    words |= {w for w in derived if len(w) >= 4}

    _DICTIONARY = {w for w in words if len(w) >= 2}
    return _DICTIONARY


def is_clinical_term(text: str) -> bool:
    """Whether a flagged span is vocabulary rather than a mistake."""
    candidate = (text or "").strip().strip(".,;:()[]\"'").lower()
    if not candidate:
        return False
    dictionary = clinical_dictionary()
    if candidate in dictionary:
        return True
    # Inflections a dictionary of base forms will not carry. Three shapes, and the
    # e-dropping one matters most in this vocabulary: "titrate" → "titrating",
    # "ambulate" → "ambulating", "extubate" → "extubating" are all words a nurse
    # writes and a base-form dictionary misses.
    for suffix in ("s", "es", "ed", "ing", "'s", "’s"):
        if not candidate.endswith(suffix):
            continue
        stem = candidate[: -len(suffix)]
        if stem in dictionary:
            return True
        if stem + "e" in dictionary:            # titrating → titrate
            return True
        if len(stem) > 2 and stem[-1] == stem[-2] and stem[:-1] in dictionary:
            return True                         # bolussed → bolus
    return False


# --------------------------------------------------------------------- masking


def protect(text: str) -> tuple[str, int]:
    """Replace clinical notation with equal-length filler.

    Equal length matters: LanguageTool reports offsets into the string it was
    given, so a substitution that changed the length would misplace every issue
    after it. Same constraint, same solution as `writing/proof.py`.
    """
    result = text
    masked = 0
    for pattern in _PROTECTED:
        for match in reversed(list(re.finditer(pattern, result, re.IGNORECASE))):
            span = match.group(0)
            result = result[: match.start()] + ("X" * len(span)) + result[match.end():]
            masked += 1
    return result, masked


# ---------------------------------------------------------------------- checking


# Spelling and typography are worth surfacing; style opinions are not. Nursing
# notes are not prose and a checker offering to improve their register is noise.
_KEEP_CATEGORIES = {
    "Possible Typo", "Typos", "Spelling", "Grammar", "Punctuation",
    "Confused words", "Capitalization", "Miscellaneous", "Compounding",
}


async def check_note(text: str, *, url: str = "",
                     language: str = DEFAULT_LANGUAGE,
                     field_path: str = "",
                     timeout: float = 15.0,
                     transport: Any = None) -> ProofResult:
    """Check one note against a LanguageTool server.

    Returns flags with offsets into the ORIGINAL text, so the caller can underline
    in place alongside the objective-language flags from `language.py`.

    `transport` exists so the tests can drive this code path with an
    `httpx.MockTransport` and no server, the same way `sources/base.Fetcher` is
    tested. Without it the response-handling half — which is where the clinical
    suppression and the offset mapping live — could only be tested by mocking out
    the function that contains it.
    """
    endpoint = url or DEFAULT_LANGUAGETOOL_URL
    result = ProofResult(checked_words=len(text.split()))
    if not text.strip():
        return result

    guarded, _ = protect(text)
    try:
        async with httpx.AsyncClient(timeout=timeout, transport=transport) as client:
            response = await client.post(endpoint, data={
                "text": guarded,
                "language": language,
                "disabledRules": ",".join(DISABLED_RULES),
                "level": "default",
            })
    except httpx.HTTPError as error:
        result.note = (
            f"No LanguageTool server answered at {endpoint} "
            f"({type(error).__name__}), so spelling and grammar were not checked. "
            f"Everything else — the objective-language filter, the interlocks, the "
            f"export — is unaffected and does not need a server. To turn this on: "
            f"docker run -d -p 8081:8010 erikvl87/languagetool"
        )
        return result

    if response.status_code != 200:
        result.note = f"LanguageTool returned HTTP {response.status_code}."
        return result

    result.available = True
    try:
        payload = response.json()
    except ValueError:
        result.note = "LanguageTool's response was not JSON."
        return result

    for match in payload.get("matches", []):
        rule = match.get("rule") or {}
        category = str((rule.get("category") or {}).get("name", ""))
        if category and category not in _KEEP_CATEGORIES:
            continue

        offset = int(match.get("offset", 0))
        length = int(match.get("length", 0))
        excerpt = text[offset: offset + length]

        # A masked span should never be flagged, but a rule can span a boundary and
        # come back pointing at filler. The test has to be against what the SERVER
        # saw, not against the original text — checking `excerpt` here looks right
        # and never fires, because the original still holds the real notation.
        seen_by_server = guarded[offset: offset + length]
        if seen_by_server and "X" in seen_by_server and (
                set(seen_by_server.strip()) <= set("X ")):
            continue

        # Dictionary suppression applies to SPELLING hits only. A grammar rule
        # that flags "are" is not claiming "are" is misspelled — it is claiming the
        # agreement is wrong — so checking it against a clinical dictionary would
        # discard a real finding for an irrelevant reason.
        spelling = ("typo" in category.lower() or "spell" in category.lower())
        if spelling and is_clinical_term(excerpt):
            result.suppressed_clinical += 1
            continue

        replacements = [str(r.get("value", ""))
                        for r in (match.get("replacements") or [])][:4]
        # A "correction" that turns a clinical term into an English word is worse
        # than no suggestion — "hydromorphone" → "hydrophone" is the classic.
        replacements = [r for r in replacements if not is_clinical_term(r)]

        result.flags.append(Flag(
            code="spelling" if spelling else "grammar",
            severity=Severity.INFO,
            message=str(match.get("message", "")),
            field_path=field_path,
            excerpt=excerpt,
            suggestion=("Suggested: " + ", ".join(replacements)) if replacements
                       else "No suggestion offered — check it by eye.",
            offset=offset,
            length=length,
        ))

    if result.available and not result.flags:
        result.note = (
            f"No spelling or grammar issues in {result.checked_words:,} words"
            + (f" ({result.suppressed_clinical} clinical terms recognised and "
               f"passed over)" if result.suppressed_clinical else "")
            + ". That is not the same as correct: a checker cannot see a wrong "
              "drug, a wrong side, or a sentence that says the opposite of what "
              "you meant. Read it before you transcribe it."
        )
    return result


def status(url: str = "") -> dict[str, Any]:
    """What the charting settings screen shows about this checker."""
    return {
        "engine": "LanguageTool (self-hosted)",
        "endpoint": url or DEFAULT_LANGUAGETOOL_URL,
        "optional": True,
        "summary": (
            "Spelling and grammar for the note text, checked against a "
            "LanguageTool server running on this machine. Nothing leaves the "
            "computer. It is optional: with no server running the tab still "
            "composes, still runs the objective-language filter, still enforces "
            "every interlock and still exports."
        ),
        "why_tuned": (
            "A general checker pointed at a nursing note is noise. Sentence "
            "fragments are correct charting, clinical vocabulary is not in a "
            "general dictionary, and clinical notation looks like broken text. So "
            "17 rules are off, notation is masked at equal length before the "
            "request goes out, and spelling hits are filtered against a "
            f"{len(clinical_dictionary()):,}-term clinical dictionary derived from "
            "this tab's own vocabulary plus a curated medication and abbreviation "
            "list."
        ),
        "not_the_important_one": (
            "A misspelling is embarrassing; \"patient appears sleeping\" is a "
            "lawsuit. The objective-language filter is the checker that matters "
            "here, it needs no server, and it runs on every keystroke."
        ),
        "dictionary_terms": len(clinical_dictionary()),
        "disabled_rules": DISABLED_RULES,
        "start_command": "docker run -d -p 8081:8010 erikvl87/languagetool",
    }
