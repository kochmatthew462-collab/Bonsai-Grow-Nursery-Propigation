"""
The grading simulator: check a draft against extracted requirements, live.

Runs on every preview, so a missing requirement surfaces while there is still time
to write it. The output is a checklist with three states and no score.

## Why there is no percentage

The obvious design is a "predicted grade". It would be wrong, and wrong in the
direction that hurts: a paper meeting every countable requirement can still fail
on the qualitative ones, which are the ones carrying most of the marks. A number
that said 94% on such a paper would be worse than no number, because the writer
would stop working.

So the simulator reports:

* **met** — the requirement is satisfied, with the observed value beside it, so
  you can see *why* it passed and catch a check that passed for the wrong reason;
* **not met** — with the observed value and the gap;
* **cannot check** — the qualitative criteria, listed as prompts, never scored.

The third category is shown as prominently as the first two, and its count is in
the headline. That is the honest summary: "14 of 16 checkable requirements met,
and 5 criteria no tool can judge."

## What it measures against

The draft, as the claim ledger holds it — not a rendered document. Word counts
exclude the title page and reference list, because that is what a rubric means by
a word count and counting them in is how a compliant paper gets reported as
over-length.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .rubric import Requirement, from_dicts

MET = "met"
NOT_MET = "not_met"
UNKNOWN = "cannot_check"
PARTIAL = "partial"


@dataclass
class CheckResult:
    requirement_id: str = ""
    label: str = ""
    kind: str = ""
    status: str = UNKNOWN
    observed: str = ""
    expected: str = ""
    gap: str = ""
    advice: str = ""
    source_text: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "requirement_id": self.requirement_id,
            "label": self.label,
            "kind": self.kind,
            "status": self.status,
            "observed": self.observed,
            "expected": self.expected,
            "gap": self.gap,
            "advice": self.advice,
            "source_text": self.source_text,
        }


# ------------------------------------------------------------------ the draft


@dataclass
class DraftFacts:
    """Everything measurable about the current draft.

    Assembled once and passed to every check, so the checks stay cheap enough to
    run on each keystroke-triggered preview.
    """

    body_words: int = 0
    total_words: int = 0
    abstract_words: int = 0
    section_titles: list[str] = field(default_factory=list)
    heading_levels: set[int] = field(default_factory=set)
    source_count: int = 0
    peer_reviewed_count: int = 0
    source_years: list[int] = field(default_factory=list)
    has_title_page: bool = False
    has_abstract: bool = False
    has_keywords: bool = False
    has_references: bool = False
    has_appendix: bool = False
    citation_style: str = ""
    font: str = ""
    text: str = ""
    levels_assigned: int = 0
    non_research_count: int = 0


def facts_from_project(project) -> DraftFacts:
    """Read the measurable facts off a Project.

    Written defensively with getattr throughout: this runs against a live project
    that may be half-built, and a simulator that raised on an empty draft would be
    useless exactly when it is most wanted.
    """
    facts = DraftFacts()

    claims = list(getattr(project, "claims", None) or [])
    body_text = " ".join(str(getattr(c, "text", "") or "") for c in claims)
    facts.text = body_text
    facts.body_words = len(body_text.split())

    abstract = str(getattr(project, "abstract", "") or "")
    facts.abstract_words = len(abstract.split())
    facts.has_abstract = bool(abstract.strip())
    facts.total_words = facts.body_words + facts.abstract_words

    facts.section_titles = sorted({
        str(getattr(c, "section", "") or "") for c in claims
        if str(getattr(c, "section", "") or "").strip()
    })

    works = list(getattr(project, "works", None) or [])
    cited = getattr(project, "cited_works", None)
    if callable(cited):
        try:
            works = list(cited()) or works
        except Exception:
            pass
    facts.source_count = len(works)

    for work in works:
        year = getattr(work, "year", None)
        if isinstance(year, int) and year > 1800:
            facts.source_years.append(year)
        work_type = str(getattr(work, "work_type", "") or "")
        peer = getattr(work, "peer_reviewed", None)
        if peer is True or "journal" in work_type.lower():
            facts.peer_reviewed_count += 1
        level = getattr(work, "evidence_level", None)
        if level is not None and str(getattr(level, "value", level)) not in (
                "not_evidence", "ungraded", ""):
            facts.levels_assigned += 1
        if work_type.lower() in ("website", "report", "book", "news"):
            facts.non_research_count += 1

    title_page = getattr(project, "title_page", None)
    facts.has_title_page = bool(title_page and str(
        getattr(title_page, "title", "") or "").strip())
    facts.has_keywords = bool(getattr(project, "keywords", None))
    facts.has_references = facts.source_count > 0
    facts.citation_style = "APA 7"
    facts.font = str(getattr(project, "font", "") or "")
    return facts


# ------------------------------------------------------------------- checking


def _year_now() -> int:
    return datetime.now(timezone.utc).year


_SECTION_ALIASES = {
    "methods": ("method", "methodology", "methods", "design"),
    "limitations": ("limitation", "limitations"),
    "implications for practice": ("implication", "implications", "practice"),
    "discussion": ("discussion",),
    "conclusion": ("conclusion", "conclusions"),
    "literature review": ("literature", "review", "background"),
    "recommendations": ("recommendation", "recommendations"),
    "irb / ethical approval": ("irb", "ethic", "approval", "consent"),
    "theoretical framework": ("framework", "theoretical", "conceptual", "theory"),
    "level of evidence": ("evidence", "level"),
    "prisma diagram": ("prisma", "flow"),
    "pico(t) question": ("pico", "question"),
    "abstract": ("abstract",),
    "appendix": ("appendix", "appendices"),
}


def _mentions(facts: DraftFacts, label: str) -> bool:
    """Whether a named section is present, by heading or by body text.

    Headings are checked first because that is what a rubric means. Body text is a
    fallback so a writer who covered IRB approval inside their methods paragraph
    is not told they omitted it — reported as a partial match rather than a pass,
    since a rubric asking for a section usually means a heading.
    """
    aliases = _SECTION_ALIASES.get(label.lower(), (label.lower(),))
    joined = " ".join(facts.section_titles).lower()
    return any(alias in joined for alias in aliases)


def _in_body(facts: DraftFacts, label: str) -> bool:
    aliases = _SECTION_ALIASES.get(label.lower(), (label.lower(),))
    text = facts.text.lower()
    return any(alias in text for alias in aliases)


def _compare(value: float, operator: str, threshold: float,
             threshold_max: float | None = None) -> bool:
    if operator == ">=":
        return value >= threshold
    if operator == "<=":
        return value <= threshold
    if operator == "==":
        # A rubric saying "approximately 2,000 words" is not asking for exactly
        # 2,000, so equality is treated as ±10%.
        return abs(value - threshold) <= max(1.0, threshold * 0.10)
    if operator == "between" and threshold_max is not None:
        return threshold <= value <= threshold_max
    return False


def check_one(requirement: Requirement, facts: DraftFacts) -> CheckResult:
    result = CheckResult(
        requirement_id=requirement.requirement_id,
        label=requirement.label,
        kind=requirement.kind,
        source_text=requirement.source_text,
        expected=requirement.describe(),
    )

    if not requirement.checkable:
        result.status = UNKNOWN
        result.advice = (
            "No tool can judge this. It is here so you check it yourself — and "
            "these criteria usually carry more marks than the countable ones."
        )
        return result

    kind = requirement.kind

    # ---- counts of sources
    if kind == "source_count":
        observed = (facts.peer_reviewed_count
                    if requirement.target == "peer_reviewed"
                    else facts.source_count)
        if requirement.target == "any" and requirement.operator == "<=":
            observed = facts.non_research_count
            result.label = "Non-research sources"
        result.observed = f"{observed} in the draft"
        passed = _compare(observed, requirement.operator, requirement.value or 0,
                          requirement.value_max)
        result.status = MET if passed else NOT_MET
        if not passed and requirement.operator == ">=":
            short = int((requirement.value or 0) - observed)
            result.gap = f"{short} more needed"
            result.advice = ("Add sources on the Sources screen and cite them — "
                             "the count is of works actually cited in the claim "
                             "ledger, not of works retrieved, because that is "
                             "what appears in your reference list.")
        elif not passed:
            result.gap = f"{int(observed - (requirement.value or 0))} too many"
        return result

    # ---- recency
    if kind == "source_recency":
        if not facts.source_years:
            result.status = UNKNOWN
            result.observed = "no publication years recorded"
            result.advice = ("Publication years are missing from the cited works, "
                             "so recency cannot be checked.")
            return result
        now = _year_now()
        if requirement.operator == ">=":                # "published since 2019"
            cutoff = int(requirement.value or 0)
        else:                                           # "within the last 5 years"
            cutoff = now - int(requirement.value or 0)
        too_old = sorted(y for y in facts.source_years if y < cutoff)
        result.observed = (f"oldest cited work is {min(facts.source_years)}; "
                           f"cutoff is {cutoff}")
        result.status = MET if not too_old else NOT_MET
        if too_old:
            result.gap = (f"{len(too_old)} cited work"
                          f"{'s' if len(too_old) != 1 else ''} predate{'s' if len(too_old) == 1 else ''} "
                          f"{cutoff} ({', '.join(str(y) for y in too_old[:6])})")
            result.advice = ("Replace them, or justify each one explicitly — a "
                             "seminal or landmark source outside the window is "
                             "usually acceptable if the paper says why it is "
                             "there.")
        return result

    # ---- word and page counts
    if kind in ("word_count", "page_count"):
        if kind == "word_count":
            observed = facts.body_words
            unit = "words"
            note = ("Counted from the claim ledger — the body text only, "
                    "excluding the title page, abstract and reference list, "
                    "which is what a rubric means by a word count.")
        else:
            # 250 words per double-spaced page in 12-point Times New Roman is the
            # figure most style guides use for an estimate.
            observed = round(facts.body_words / 250, 1)
            unit = "pages"
            note = ("Estimated at 250 words per double-spaced page. Check the "
                    "exported document if the count is close to a boundary.")
        result.observed = f"{observed:g} {unit}"
        passed = _compare(observed, requirement.operator, requirement.value or 0,
                          requirement.value_max)
        result.status = MET if passed else NOT_MET
        result.advice = note
        if not passed:
            if requirement.operator == "between":
                if observed < (requirement.value or 0):
                    result.gap = f"{(requirement.value or 0) - observed:g} short"
                else:
                    result.gap = f"{observed - (requirement.value_max or 0):g} over"
            elif requirement.operator == ">=":
                result.gap = f"{(requirement.value or 0) - observed:g} short"
            else:
                result.gap = f"{observed - (requirement.value or 0):g} over"
        return result

    # ---- citation style
    if kind == "citation_style":
        wanted = requirement.label.lower()
        if "apa 7" in wanted or "apa (edition" in wanted:
            result.status = MET
            result.observed = "APA 7 throughout"
            return result
        if "apa 6" in wanted:
            result.status = NOT_MET
            result.observed = "APA 7"
            result.advice = ("This tool produces APA 7 only. If your rubric "
                             "requires APA 6, the differences are substantive — "
                             "running heads, title page, and the DOI format all "
                             "changed — and you will need to adjust the exported "
                             "document by hand.")
            return result
        result.status = NOT_MET
        result.observed = "APA 7"
        result.advice = (f"This tool produces APA 7. Your rubric asks for "
                         f"{requirement.label}, which the exporter does not "
                         f"produce.")
        return result

    # ---- structural and formatting artefacts
    if kind in ("structural", "formatting", "section_required"):
        label = requirement.label.lower()
        present = {
            "title page": facts.has_title_page,
            "abstract": facts.has_abstract,
            "keywords": facts.has_keywords,
            "reference list": facts.has_references,
            "running head": True,
            "double spacing": True,
            "one-inch margins": True,
            "hanging indent": True,
            "times new roman": (facts.font or "Times New Roman").lower()
                               .startswith("times"),
            "in-text citations": facts.source_count > 0,
            "level 1 headings": bool(facts.section_titles),
            "headings": bool(facts.section_titles),
        }.get(label)

        if present is not None:
            result.status = MET if present else NOT_MET
            result.observed = "present" if present else "not present"
            if label in ("running head", "double spacing", "one-inch margins",
                         "hanging indent"):
                result.advice = ("Applied automatically by the exporter — this is "
                                 "a property of the document it produces rather "
                                 "than something you have to do.")
            elif not present:
                result.advice = {
                    "title page": "Set the title and paper type on the Export "
                                  "screen.",
                    "abstract": "Draft one on the Write screen.",
                    "keywords": "Add keywords on the Export screen.",
                    "times new roman": f"The font is set to "
                                       f"{facts.font or 'Times New Roman'}. "
                                       f"Change it on the Export screen.",
                }.get(label, "")
            return result

        # Named sections: heading first, body text as a partial.
        if _mentions(facts, requirement.label):
            result.status = MET
            result.observed = "a section with this heading exists"
            return result
        if _in_body(facts, requirement.label):
            result.status = PARTIAL
            result.observed = "mentioned in the body but not as a heading"
            result.advice = ("A rubric asking for a section usually means a "
                             "heading a marker can find. Promote it to its own "
                             "section rather than leaving it inside a paragraph.")
            return result
        result.status = NOT_MET
        result.observed = "not found"
        result.advice = (f"Add a section for {requirement.label.lower()}, or "
                         f"dismiss this if the rubric meant something else — "
                         f"extraction is pattern-based and can misread.")
        return result

    result.status = UNKNOWN
    result.advice = "This requirement type has no automatic check."
    return result


def run(requirements: list[Requirement] | list[dict[str, Any]],
        facts: DraftFacts) -> dict[str, Any]:
    """Check every requirement and summarise, without producing a score."""
    if requirements and isinstance(requirements[0], dict):
        requirements = from_dicts(requirements)   # type: ignore[arg-type]

    results = [check_one(r, facts) for r in requirements]   # type: ignore[arg-type]
    met = [r for r in results if r.status == MET]
    not_met = [r for r in results if r.status == NOT_MET]
    partial = [r for r in results if r.status == PARTIAL]
    unknown = [r for r in results if r.status == UNKNOWN]
    checkable = len(met) + len(not_met) + len(partial)

    return {
        "results": [r.as_dict() for r in results],
        "counts": {
            "met": len(met), "not_met": len(not_met), "partial": len(partial),
            "cannot_check": len(unknown), "checkable": checkable,
        },
        "headline": (
            f"{len(met)} of {checkable} checkable requirement"
            f"{'s' if checkable != 1 else ''} met"
            + (f", {len(partial)} partly" if partial else "")
            + (f", and {len(unknown)} criteri"
               f"{'a' if len(unknown) != 1 else 'on'} no tool can judge."
               if unknown else ".")
        ),
        "no_score_note": (
            "There is no predicted grade here, deliberately. A paper can meet "
            "every countable requirement and still fail on the qualitative ones, "
            "which usually carry most of the marks — and a number saying 94% on "
            "such a paper would stop you working on the part that mattered."
        ),
        "outstanding": [r.as_dict() for r in not_met + partial],
        "unscored": [r.as_dict() for r in unknown],
    }
