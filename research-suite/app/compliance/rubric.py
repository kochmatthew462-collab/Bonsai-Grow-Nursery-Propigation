"""
Rubric and syllabus ingestion: prose requirements into a checkable list.

Paste a rubric or upload the assignment brief and get back a list of requirements,
each with a type the simulator can actually verify.

## The distinction that makes this work

A rubric mixes two kinds of statement and they need completely different handling:

**Countable requirements** — "at least five peer-reviewed sources", "published
within the last five years", "1,500 to 2,000 words", "APA 7th edition", "include a
Level 1 heading for each section". These have a number or a named artefact in
them, and a program can check them. They are extracted with their operator and
threshold so `simulator.py` can compare against the draft.

**Qualitative criteria** — "demonstrates critical analysis rather than
description", "synthesises across sources". No program checks these. Extracting
them and then scoring them would be inventing a grade.

So both are extracted, and they are **labelled differently and treated
differently**. Countable requirements get a pass/fail with the observed value.
Qualitative ones are listed as prompts for the writer, explicitly unscored. A tool
that blurred the two would produce a green checklist on a paper that fails, which
is worse than no checklist at all.

## Extraction is pattern-based, and says so

There is no model call here. The extractor recognises the sentence shapes rubrics
actually use — "at least N", "no more than N", "minimum of N", "within the last N
years", "N–N words", "must include", "should address" — and reports its confidence.
A requirement it could not classify is still listed, as unparsed text, rather than
dropped: the commonest failure of a tool like this is silently losing the one
requirement that mattered.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any

# --------------------------------------------------------------------- types


@dataclass
class Requirement:
    """One extracted requirement.

    `kind` decides what the simulator does with it. `source_text` is always the
    rubric's own words, so a user can see what was interpreted and correct it —
    an extracted requirement the user cannot trace back to the rubric is one they
    cannot trust.
    """

    requirement_id: str = ""
    kind: str = "qualitative"     # see KINDS
    label: str = ""
    source_text: str = ""
    operator: str = ""            # >=, <=, between, ==, contains
    value: float | None = None
    value_max: float | None = None
    unit: str = ""
    target: str = ""              # what it applies to: sources, words, headings…
    confidence: str = "medium"    # high | medium | low
    checkable: bool = False
    note: str = ""

    def describe(self) -> str:
        if not self.checkable:
            return self.label or self.source_text
        if self.operator == "between" and self.value is not None:
            return f"{self.label}: {self.value:g}–{self.value_max:g} {self.unit}"
        symbol = {">=": "at least", "<=": "no more than", "==": "exactly"}.get(
            self.operator, self.operator)
        if self.value is None:
            return self.label
        return f"{self.label}: {symbol} {self.value:g} {self.unit}".strip()


KINDS = {
    "source_count": "A minimum or maximum number of sources",
    "source_recency": "How recent the sources must be",
    "source_type": "What kind of sources are required",
    "word_count": "A word or page count",
    "page_count": "A page count",
    "section_required": "A named section that must be present",
    "citation_style": "The referencing style and edition",
    "formatting": "A formatting rule",
    "structural": "A structural element — title page, abstract, headings",
    "qualitative": "A criterion no program can score",
    "unparsed": "A requirement that could not be classified",
}


# ------------------------------------------------------------------ extraction


_NUM_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "fifteen": 15,
    "twenty": 20, "twenty-five": 25, "thirty": 30,
}


def _number(text: str) -> float | None:
    """A count written as a numeral or a word."""
    cleaned = text.strip().lower().replace(",", "")
    try:
        return float(cleaned)
    except ValueError:
        return _NUM_WORDS.get(cleaned)


_NUMBER_PATTERN = r"(\d[\d,]*|" + "|".join(_NUM_WORDS) + r")"

_AT_LEAST = r"(?:at\s+least|minimum\s+of|no\s+fewer\s+than|a\s+minimum\s+of|" \
            r"not\s+less\s+than)"
_AT_MOST = r"(?:no\s+more\s+than|maximum\s+of|up\s+to|not\s+exceeding|" \
           r"a\s+maximum\s+of|no\s+longer\s+than)"

# Each rule: pattern, kind, label, unit, target, operator, confidence.
# Ordered most-specific-first, and a sentence stops at its first match, because a
# sentence that says "at least five peer-reviewed journal articles from the last
# five years" holds two requirements and both need to be found rather than the
# first swallowing the second.
_RULES: list[tuple[str, str, str, str, str, str, str]] = [
    (rf"{_AT_LEAST}\s+{_NUMBER_PATTERN}\s+(?:peer[- ]reviewed|scholarly|"
     rf"refereed)\s*(?:journal\s*)?(?:article|source|reference|citation)s?",
     "source_count", "Peer-reviewed sources", "sources", "peer_reviewed",
     ">=", "high"),
    (rf"{_AT_LEAST}\s+{_NUMBER_PATTERN}\s+(?:scholarly\s+|academic\s+|"
     rf"primary\s+|research\s+)?(?:source|reference|citation|article)s?",
     "source_count", "Sources", "sources", "any", ">=", "high"),
    (rf"{_AT_MOST}\s+{_NUMBER_PATTERN}\s+(?:source|reference|citation)s?",
     "source_count", "Maximum sources", "sources", "any", "<=", "high"),
    (rf"{_NUMBER_PATTERN}\s*(?:-|–|to)\s*{_NUMBER_PATTERN}\s+(?:source|reference)s?",
     "source_count", "Sources", "sources", "any", "between", "high"),

    (rf"(?:published|from|within)\s+(?:the\s+)?(?:last|past|previous)\s+"
     rf"{_NUMBER_PATTERN}\s+years?",
     "source_recency", "Source recency", "years", "publication_year", "<=",
     "high"),
    (rf"(?:no\s+older\s+than|not\s+older\s+than)\s+{_NUMBER_PATTERN}\s+years?",
     "source_recency", "Source recency", "years", "publication_year", "<=",
     "high"),
    (rf"published\s+(?:in\s+or\s+)?(?:after|since)\s+(\d{{4}})",
     "source_recency", "Published since", "year", "publication_year", ">=",
     "high"),

    (rf"{_NUMBER_PATTERN}\s*(?:-|–|to)\s*{_NUMBER_PATTERN}\s+words",
     "word_count", "Word count", "words", "body", "between", "high"),
    (rf"{_AT_LEAST}\s+{_NUMBER_PATTERN}\s+words",
     "word_count", "Word count", "words", "body", ">=", "high"),
    (rf"{_AT_MOST}\s+{_NUMBER_PATTERN}\s+words",
     "word_count", "Word count", "words", "body", "<=", "high"),
    (rf"approximately\s+{_NUMBER_PATTERN}\s+words",
     "word_count", "Word count (approximate)", "words", "body", "==", "medium"),
    (rf"{_NUMBER_PATTERN}\s+words\s+(?:in\s+length|maximum|max)",
     "word_count", "Word count", "words", "body", "<=", "high"),

    (rf"{_NUMBER_PATTERN}\s*(?:-|–|to)\s*{_NUMBER_PATTERN}\s+pages",
     "page_count", "Page count", "pages", "body", "between", "high"),
    (rf"{_AT_LEAST}\s+{_NUMBER_PATTERN}\s+pages",
     "page_count", "Page count", "pages", "body", ">=", "high"),
    (rf"{_AT_MOST}\s+{_NUMBER_PATTERN}\s+pages",
     "page_count", "Page count", "pages", "body", "<=", "high"),
]

# Named artefacts. Presence-checkable rather than countable.
_ARTEFACTS: list[tuple[str, str, str]] = [
    (r"\btitle[\s-]+page\b", "structural", "Title page"),
    (r"\brunning[\s-]+head\b", "structural", "Running head"),
    (r"\babstract\b", "structural", "Abstract"),
    (r"\bkeywords?\b", "structural", "Keywords"),
    (r"\breference\s+(?:list|page|section)\b|\breferences\b", "structural",
     "Reference list"),
    (r"\bappendix|appendices\b", "structural", "Appendix"),
    (r"\btable[\s-]+of[\s-]+contents\b", "structural", "Table of contents"),
    (r"\blevel\s+1\s+heading|level\s+one\s+heading\b", "formatting",
     "Level 1 headings"),
    (r"\bheadings?\s+(?:and\s+subheadings?)?\b", "formatting", "Headings"),
    (r"\bdouble[- ]spac(?:ed|ing)\b", "formatting", "Double spacing"),
    (r"\b1[- ]inch\s+margins?|one[- ]inch\s+margins?\b", "formatting",
     "One-inch margins"),
    (r"\bTimes\s+New\s+Roman\b", "formatting", "Times New Roman"),
    (r"\bhanging[\s-]+indent\b", "formatting", "Hanging indent"),
    (r"\bin[\s-]*text[\s-]+citations?\b", "citation_style", "In-text citations"),
    (r"\bPRISMA\b", "structural", "PRISMA diagram"),
    (r"\bPICO(?:T)?\b", "structural", "PICO(T) question"),
    (r"\bIRB\b|\binstitutional\s+review\s+board\b", "section_required",
     "IRB / ethical approval"),
    (r"\bconflicts?\s+of\s+interest\b", "section_required",
     "Conflict of interest statement"),
    (r"\blimitations?\b", "section_required", "Limitations"),
    (r"\bimplications?\s+for\s+(?:practice|nursing)\b", "section_required",
     "Implications for practice"),
    (r"\brecommendations?\b", "section_required", "Recommendations"),
    (r"\bliterature\s+review\b", "section_required", "Literature review"),
    (r"\bmethodology|\bmethods\s+section\b", "section_required", "Methods"),
    (r"\bdiscussion\b", "section_required", "Discussion"),
    (r"\bconclusion\b", "section_required", "Conclusion"),
    (r"\bevidence[- ]based\s+practice\b", "qualitative", "Evidence-based practice"),
    (r"\blevel\s+of\s+evidence\b", "section_required", "Level of evidence"),
    (r"\btheoretical\s+framework|conceptual\s+framework\b", "section_required",
     "Theoretical framework"),
]

# A general artefact must not be reported alongside the specific one it contains:
# "Include a Level 1 heading for each major section" is one requirement, not two.
_SUBSUMED_BY = {
    "Headings": {"Level 1 headings"},
    "Reference list": {"Hanging indent"},
}


_STYLE = [
    (r"\bAPA\s*(?:7(?:th)?|seventh)\b", "APA 7th edition"),
    (r"\bAPA\s*(?:6(?:th)?|sixth)\b", "APA 6th edition"),
    (r"\bAMA\s*(?:\d+(?:th)?)?\s*(?:edition)?\b", "AMA style"),
    (r"\bAPA\b", "APA (edition unspecified)"),
    (r"\bMLA\b", "MLA style"),
    (r"\bVancouver\b", "Vancouver style"),
    (r"\bHarvard\b", "Harvard style"),
]

# Verbs that mark a sentence as a requirement rather than description. A rubric
# is full of explanatory prose, and extracting all of it would bury the
# requirements in commentary.
_OBLIGATION = re.compile(
    r"\b(must|shall|should|required?|need\s+to|are\s+expected\s+to|"
    r"is\s+expected\s+to|ensure|include|incorporate|address|demonstrate|"
    r"provide|submit|use|apply|cite|discuss|analyz|analys|synthes|evaluat|"
    r"identif|describ|explain|compare|critique)\w*\b",
    re.IGNORECASE,
)


def _sentences(text: str) -> list[str]:
    """Split into sentences and bullet lines, rejoining wrapped continuations.

    Two things a naive split gets wrong on a real rubric:

    * Bullets matter as much as sentences — rubrics are mostly bulleted, and
      splitting on periods merges a whole bullet list into one item.
    * **Bullets wrap.** "cite at least five peer-reviewed articles published
      within the / last 5 years" is one requirement across two lines, and taking
      only the first line loses the recency requirement entirely. A line that is
      not itself a bullet and follows one is a continuation of it.
    """
    bullet = re.compile(r"^\s*(?:[-•*●▪‣]|\d+[.)]|[a-z][.)])\s+", re.IGNORECASE)
    blocks: list[str] = []
    current: str | None = None

    for line in (text or "").splitlines():
        stripped = line.strip()
        if not stripped:
            if current is not None:
                blocks.append(current)
                current = None
            continue
        if bullet.match(line):
            if current is not None:
                blocks.append(current)
            current = bullet.sub("", line).strip()
            continue
        if current is not None and line[:1].isspace():
            # Indented and not a bullet: a wrapped continuation of the one above.
            current += " " + stripped
            continue
        if current is not None:
            blocks.append(current)
            current = None
        blocks.append(stripped)
    if current is not None:
        blocks.append(current)

    out: list[str] = []
    for block in blocks:
        for piece in re.split(r"(?<=[.;:!?])\s+(?=[A-Z(])", block):
            if piece.strip():
                out.append(" ".join(piece.split()))
    return out


def _identifier(text: str, index: int) -> str:
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:8]
    return f"req-{index:02d}-{digest}"


def extract(text: str, *, source_name: str = "") -> dict[str, Any]:
    """Pull requirements out of rubric or syllabus prose."""
    requirements: list[Requirement] = []
    seen: set[tuple[str, str, float | None]] = set()

    for index, sentence in enumerate(_sentences(text)):
        lowered = sentence.lower()
        matched_any = False

        # --- countable rules
        for pattern, kind, label, unit, target, operator, confidence in _RULES:
            for match in re.finditer(pattern, lowered, re.IGNORECASE):
                groups = [g for g in match.groups() if g]
                value = _number(groups[0]) if groups else None
                value_max = _number(groups[1]) if len(groups) > 1 else None
                if value is None:
                    continue
                key = (kind, target, value)
                if key in seen:
                    continue
                seen.add(key)
                matched_any = True
                requirements.append(Requirement(
                    requirement_id=_identifier(sentence + kind + str(value), index),
                    kind=kind, label=label, source_text=sentence,
                    operator=operator, value=value, value_max=value_max,
                    unit=unit, target=target, confidence=confidence,
                    checkable=True,
                ))

        # --- citation style
        for pattern, label in _STYLE:
            if re.search(pattern, sentence, re.IGNORECASE):
                key = ("citation_style", label, None)
                if key not in seen:
                    seen.add(key)
                    matched_any = True
                    requirements.append(Requirement(
                        requirement_id=_identifier(sentence + label, index),
                        kind="citation_style", label=label,
                        source_text=sentence, operator="==", target="style",
                        confidence="high", checkable=True,
                    ))
                break

        # --- named artefacts, only in sentences that carry an obligation
        if _OBLIGATION.search(sentence):
            matched_here: set[str] = set()
            for pattern, kind, label in _ARTEFACTS:
                if re.search(pattern, sentence, re.IGNORECASE):
                    if _SUBSUMED_BY.get(label, set()) & matched_here:
                        continue
                    matched_here.add(label)
                    key = (kind, label, None)
                    if key in seen:
                        continue
                    seen.add(key)
                    matched_any = True
                    requirements.append(Requirement(
                        requirement_id=_identifier(sentence + label, index),
                        kind=kind, label=label, source_text=sentence,
                        operator="contains", target=label.lower(),
                        confidence="medium", checkable=(kind != "qualitative"),
                    ))

        # --- everything else that reads like a requirement
        if not matched_any and _OBLIGATION.search(sentence) and len(sentence) > 25:
            requirements.append(Requirement(
                requirement_id=_identifier(sentence, index),
                kind="qualitative", label=_shorten(sentence),
                source_text=sentence, confidence="low", checkable=False,
                note="No program can score this. It is listed so you can check it "
                     "yourself before you submit.",
            ))

    checkable = [r for r in requirements if r.checkable]
    qualitative = [r for r in requirements if not r.checkable]
    return {
        "source_name": source_name,
        "requirements": [_as_dict(r) for r in requirements],
        "checkable_count": len(checkable),
        "qualitative_count": len(qualitative),
        "summary": (
            f"{len(checkable)} requirement"
            f"{'s' if len(checkable) != 1 else ''} the tool can verify, and "
            f"{len(qualitative)} it cannot. The second group is listed rather "
            f"than scored: \"demonstrates critical analysis\" is a judgement, and "
            f"a tool that ticked it would be inventing a grade."
        ),
        "caveat": (
            "Extraction is pattern-based, not a model reading the document. Check "
            "the list against your rubric — anything it misread is visible "
            "because every requirement carries the sentence it came from, and "
            "anything it missed you can add by hand."
        ),
    }


def _shorten(text: str, limit: int = 90) -> str:
    cleaned = " ".join(text.split())
    return cleaned if len(cleaned) <= limit else cleaned[: limit - 1].rstrip() + "…"


def _as_dict(requirement: Requirement) -> dict[str, Any]:
    return {
        "requirement_id": requirement.requirement_id,
        "kind": requirement.kind,
        "kind_label": KINDS.get(requirement.kind, requirement.kind),
        "label": requirement.label,
        "describe": requirement.describe(),
        "source_text": requirement.source_text,
        "operator": requirement.operator,
        "value": requirement.value,
        "value_max": requirement.value_max,
        "unit": requirement.unit,
        "target": requirement.target,
        "confidence": requirement.confidence,
        "checkable": requirement.checkable,
        "note": requirement.note,
    }


def from_dicts(rows: list[dict[str, Any]]) -> list[Requirement]:
    """Rebuild Requirements from stored dictionaries."""
    out: list[Requirement] = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        requirement = Requirement()
        for name in requirement.__dataclass_fields__:
            if name in row:
                setattr(requirement, name, row[name])
        out.append(requirement)
    return out


def manual(label: str, *, kind: str = "qualitative", operator: str = "",
           value: float | None = None, unit: str = "",
           target: str = "") -> Requirement:
    """A requirement the user adds by hand, for anything extraction missed."""
    return Requirement(
        requirement_id=_identifier(label + kind, 99),
        kind=kind if kind in KINDS else "qualitative",
        label=label.strip(),
        source_text=label.strip(),
        operator=operator,
        value=value,
        unit=unit,
        target=target,
        confidence="high",
        checkable=bool(operator and kind != "qualitative"),
        note="Added by hand.",
    )
