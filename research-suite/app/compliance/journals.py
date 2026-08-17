"""
Journal submission guidelines: built-in profiles, and a parser for the rest.

A paper written to APA 7 and submitted to a journal is still likely to be desk
rejected, because journals impose their own constraints on top of a style: a word
ceiling, a structured abstract with named headings, a reference cap, a required
reporting checklist. Those are the things a desk editor checks first and they are
in a different document from the style guide.

## Two ways in

**Built-in profiles** for journals a nursing or health-services author actually
submits to, each recording the constraints that get papers returned. They are
starting points with a "verify against the current guidelines" note and the date
they were compiled, because these change without announcement — a profile presented
as current when it is two years stale is worse than no profile.

**A parser** for anything else: paste the author guidelines and it pulls out word
limits, abstract structure, reference caps and required statements using the same
approach as `rubric.py`.

## The structured abstract is the part that bites

Several nursing journals require an abstract broken into named sections, and the
names differ: *Background / Methods / Results / Conclusions* at one journal,
*Objectives / Design / Setting / Participants / Methods / Results / Conclusions* at
another. An unstructured abstract sent to a journal that requires structure is
returned without review. `check()` compares the abstract's headings against the
profile and names the ones that are missing.

## Reporting guidelines

Most health journals now require the relevant EQUATOR checklist — CONSORT for
trials, PRISMA for systematic reviews, STROBE for observational studies, SRQR or
COREQ for qualitative work — submitted alongside the manuscript. The profile
records which, because the checklist is usually the thing an author discovers is
missing on submission day.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

COMPILED = "2026-08"

VERIFY_NOTE = (
    f"Compiled {COMPILED} from the journals' public author guidelines. Journals "
    f"change these without announcement, so check the current 'Instructions for "
    f"Authors' page before you submit and correct anything that has moved — a "
    f"profile trusted after it has gone stale is worse than no profile."
)


@dataclass
class JournalProfile:
    key: str
    name: str
    publisher: str = ""
    style: str = "APA 7"
    word_limit: int | None = None
    word_limit_note: str = ""
    abstract_limit: int | None = None
    abstract_structured: bool = False
    abstract_headings: list[str] = field(default_factory=list)
    reference_limit: int | None = None
    title_limit_characters: int | None = None
    keywords_range: tuple[int, int] | None = None
    reporting_guideline: str = ""
    required_statements: list[str] = field(default_factory=list)
    tables_figures_limit: int | None = None
    blinded: bool = False
    notes: str = ""
    url: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "name": self.name,
            "publisher": self.publisher,
            "style": self.style,
            "word_limit": self.word_limit,
            "word_limit_note": self.word_limit_note,
            "abstract_limit": self.abstract_limit,
            "abstract_structured": self.abstract_structured,
            "abstract_headings": self.abstract_headings,
            "reference_limit": self.reference_limit,
            "title_limit_characters": self.title_limit_characters,
            "keywords_range": list(self.keywords_range) if self.keywords_range
                              else None,
            "reporting_guideline": self.reporting_guideline,
            "required_statements": self.required_statements,
            "tables_figures_limit": self.tables_figures_limit,
            "blinded": self.blinded,
            "notes": self.notes,
            "url": self.url,
            "verify": VERIFY_NOTE,
        }


PROFILES: dict[str, JournalProfile] = {
    "jan": JournalProfile(
        key="jan",
        name="Journal of Advanced Nursing",
        publisher="Wiley",
        style="APA 7",
        word_limit=5000,
        word_limit_note="Excludes the abstract, references, tables and figures.",
        abstract_limit=300,
        abstract_structured=True,
        abstract_headings=["Aim", "Design", "Methods", "Results", "Conclusion",
                           "Impact", "Reporting Method",
                           "Patient or Public Contribution"],
        reporting_guideline="EQUATOR checklist matching the design",
        required_statements=[
            "Conflict of interest", "Funding", "Ethical approval",
            "Data availability", "Patient or public contribution",
        ],
        notes=("The 'Impact' and 'Patient or Public Contribution' abstract "
               "headings are the two most often omitted, and an abstract missing "
               "them is returned before review. The Patient or Public "
               "Contribution statement is required even when the answer is that "
               "there was none — 'No patient or public contribution' is an "
               "acceptable entry and a blank is not."),
        url="https://onlinelibrary.wiley.com/journal/13652648",
    ),
    "ijns": JournalProfile(
        key="ijns",
        name="International Journal of Nursing Studies",
        publisher="Elsevier",
        style="Vancouver-style numbered references",
        word_limit=5000,
        word_limit_note="Main text, excluding abstract, references and tables.",
        abstract_limit=350,
        abstract_structured=True,
        abstract_headings=["Background", "Objective", "Design", "Setting",
                           "Participants", "Methods", "Results", "Conclusions",
                           "Registration number", "Tweetable abstract"],
        reporting_guideline="EQUATOR checklist matching the design",
        required_statements=["Funding", "Ethical approval",
                             "Conflict of interest", "CRediT author statement"],
        notes=("References are numbered rather than author-date, so this tool's "
               "APA output needs converting. That conversion is not cosmetic — "
               "in-text citations change shape entirely — so budget time for it."),
        url="https://www.sciencedirect.com/journal/international-journal-of-nursing-studies",
    ),
    "jcn": JournalProfile(
        key="jcn",
        name="Journal of Clinical Nursing",
        publisher="Wiley",
        style="APA 7",
        word_limit=6000,
        abstract_limit=250,
        abstract_structured=True,
        abstract_headings=["Aims and Objectives", "Background", "Design",
                           "Methods", "Results", "Conclusions",
                           "Relevance to Clinical Practice",
                           "Patient or Public Contribution"],
        reporting_guideline="EQUATOR checklist matching the design",
        required_statements=["Conflict of interest", "Funding",
                             "Ethical approval"],
        notes="'Relevance to Clinical Practice' is a required abstract heading "
              "and is the one most often missing.",
        url="https://onlinelibrary.wiley.com/journal/13652702",
    ),
    "nursing_research": JournalProfile(
        key="nursing_research",
        name="Nursing Research",
        publisher="Wolters Kluwer",
        style="APA 7",
        word_limit=5000,
        abstract_limit=250,
        abstract_structured=True,
        abstract_headings=["Background", "Objectives", "Methods", "Results",
                           "Discussion"],
        reporting_guideline="EQUATOR checklist matching the design",
        required_statements=["Conflict of interest", "Funding"],
        url="https://journals.lww.com/nursingresearchonline/",
    ),
    "worldviews": JournalProfile(
        key="worldviews",
        name="Worldviews on Evidence-Based Nursing",
        publisher="Wiley / Sigma",
        style="APA 7",
        word_limit=5000,
        abstract_limit=250,
        abstract_structured=True,
        abstract_headings=["Background", "Aims", "Methods", "Results",
                           "Linking Evidence to Action"],
        reporting_guideline="PRISMA for reviews; EQUATOR otherwise",
        required_statements=["Conflict of interest", "Funding"],
        notes="'Linking Evidence to Action' is specific to this journal and is "
              "required in the abstract.",
        url="https://sigmapubs.onlinelibrary.wiley.com/journal/17416787",
    ),
    "bmj_open": JournalProfile(
        key="bmj_open",
        name="BMJ Open",
        publisher="BMJ",
        style="Vancouver",
        word_limit=4000,
        abstract_limit=300,
        abstract_structured=True,
        abstract_headings=["Objectives", "Design", "Setting", "Participants",
                           "Interventions", "Primary and secondary outcome "
                           "measures", "Results", "Conclusions",
                           "Trial registration number"],
        reporting_guideline="Mandatory EQUATOR checklist, uploaded at submission",
        required_statements=["Competing interests", "Funding",
                             "Ethics approval", "Data availability",
                             "Patient and public involvement",
                             "Author contributions"],
        notes=("The reporting checklist is a hard submission requirement, not a "
               "recommendation — the system will not accept the manuscript "
               "without it."),
        url="https://bmjopen.bmj.com/pages/authors/",
    ),
    "lancet": JournalProfile(
        key="lancet",
        name="The Lancet",
        publisher="Elsevier",
        style="Vancouver",
        word_limit=4500,
        word_limit_note="Articles; other formats have much lower limits.",
        abstract_limit=300,
        abstract_structured=True,
        abstract_headings=["Background", "Methods", "Findings",
                           "Interpretation", "Funding"],
        reference_limit=30,
        reporting_guideline="Mandatory reporting checklist",
        required_statements=["Declaration of interests", "Data sharing",
                             "Role of the funding source", "Contributors"],
        notes=("'Findings' rather than 'Results' and 'Interpretation' rather than "
               "'Conclusions' — the wording is specific and is checked. A "
               "'Research in context' panel is also required for research "
               "articles."),
        url="https://www.thelancet.com/lancet/information-for-authors",
    ),
    "ajn": JournalProfile(
        key="ajn",
        name="American Journal of Nursing",
        publisher="Wolters Kluwer",
        style="APA 7",
        word_limit=3000,
        abstract_limit=150,
        abstract_structured=False,
        reporting_guideline="EQUATOR where applicable",
        required_statements=["Conflict of interest", "Funding"],
        notes="Written for a broad clinical readership rather than a research "
              "audience; the guidelines ask for accessible prose.",
        url="https://journals.lww.com/ajnonline/",
    ),
}


def catalogue() -> list[dict[str, Any]]:
    return [profile.as_dict() for profile in PROFILES.values()]


def get(key: str) -> JournalProfile | None:
    return PROFILES.get(key)


# ------------------------------------------------------------------- parsing


_NUM = r"(\d[\d,]*)"


def parse(text: str, *, name: str = "") -> JournalProfile:
    """Read author guidelines into a profile.

    Same conservative approach as `rubric.py`: recognise the shapes guidelines
    actually use, and leave unrecognised fields empty rather than guessing. An
    invented word limit is worse than a blank one, because a blank prompts the
    author to look it up.
    """
    blob = text or ""
    profile = JournalProfile(key="parsed", name=name or "Parsed guidelines",
                             notes="Parsed from pasted guidelines.")

    def find(pattern: str) -> int | None:
        match = re.search(pattern, blob, re.IGNORECASE)
        if not match:
            return None
        try:
            return int(match.group(1).replace(",", ""))
        except (TypeError, ValueError):
            return None

    profile.word_limit = (
        find(rf"(?:manuscript|article|main\s+text|paper)s?\s+(?:should|must)?\s*"
             rf"(?:not\s+exceed|be\s+no\s+more\s+than|be\s+limited\s+to|"
             rf"be\s+under)\s*{_NUM}\s*words")
        or find(rf"(?:maximum|limit)\s+of\s+{_NUM}\s*words")
        or find(rf"{_NUM}\s*words\s+(?:maximum|max|or\s+fewer|limit)")
        or find(rf"word\s+(?:count|limit)[^.\n]{{0,30}}?{_NUM}")
    )

    abstract_zone = blob
    match = re.search(r"abstract", blob, re.IGNORECASE)
    if match:
        abstract_zone = blob[match.start(): match.start() + 900]
    profile.abstract_limit = (
        re.search(rf"{_NUM}\s*words", abstract_zone, re.IGNORECASE)
        and int(re.search(rf"{_NUM}\s*words", abstract_zone,
                          re.IGNORECASE).group(1).replace(",", ""))
    ) or None

    profile.reference_limit = (
        find(rf"(?:no\s+more\s+than|maximum\s+of|limit(?:ed)?\s+to)\s*{_NUM}\s*"
             rf"references")
        or find(rf"{_NUM}\s*references\s*(?:maximum|max|or\s+fewer)")
    )

    profile.title_limit_characters = find(
        rf"title[^.\n]{{0,40}}?{_NUM}\s*characters")

    keywords = re.search(rf"{_NUM}\s*(?:to|-|–)\s*{_NUM}\s*key\s*words",
                         blob, re.IGNORECASE)
    if keywords:
        profile.keywords_range = (int(keywords.group(1)),
                                  int(keywords.group(2)))

    # Structured abstract: look for a run of capitalised headings near "abstract".
    structured = re.search(
        r"structured\s+abstract|abstract\s+(?:should|must)\s+be\s+structured",
        blob, re.IGNORECASE)
    profile.abstract_structured = bool(structured)
    headings = re.findall(
        r"\b(Background|Objectives?|Aims?(?:\s+and\s+Objectives)?|Design|Setting|"
        r"Participants?|Interventions?|Methods?|Results?|Findings|Conclusions?|"
        r"Discussion|Impact|Implications?|Relevance\s+to\s+Clinical\s+Practice|"
        r"Interpretation|Funding|Registration|Trial\s+registration[^,.\n]*|"
        r"Patient\s+or\s+Public\s+Contribution|Linking\s+Evidence\s+to\s+Action)"
        r"\s*[:—-]", abstract_zone)
    if headings:
        seen: list[str] = []
        for heading in headings:
            cleaned = " ".join(heading.split())
            if cleaned not in seen:
                seen.append(cleaned)
        profile.abstract_headings = seen
        profile.abstract_structured = profile.abstract_structured or len(seen) >= 3

    for pattern, label in [
        (r"\bCONSORT\b", "CONSORT"), (r"\bPRISMA\b", "PRISMA"),
        (r"\bSTROBE\b", "STROBE"), (r"\bCOREQ\b", "COREQ"),
        (r"\bSRQR\b", "SRQR"), (r"\bSQUIRE\b", "SQUIRE"),
        (r"\bSTARD\b", "STARD"), (r"\bEQUATOR\b", "EQUATOR checklist"),
    ]:
        if re.search(pattern, blob, re.IGNORECASE):
            profile.reporting_guideline = (
                (profile.reporting_guideline + "; " if profile.reporting_guideline
                 else "") + label)

    for pattern, label in [
        (r"conflicts?\s+of\s+interest|competing\s+interests?",
         "Conflict of interest"),
        (r"\bfunding\b", "Funding"),
        (r"ethic(?:s|al)\s+(?:approval|statement)", "Ethical approval"),
        (r"data\s+(?:availability|sharing)", "Data availability"),
        (r"author\s+contributions?|CRediT", "Author contributions"),
        (r"patient\s+(?:and|or)\s+public\s+(?:involvement|contribution)",
         "Patient or public involvement"),
        (r"informed\s+consent", "Informed consent"),
        (r"trial\s+registration", "Trial registration"),
    ]:
        if re.search(pattern, blob, re.IGNORECASE):
            profile.required_statements.append(label)

    for pattern, style in [
        (r"\bAPA\s*7", "APA 7"), (r"\bVancouver\b", "Vancouver"),
        (r"\bnumbered\s+references?\b", "Vancouver-style numbered references"),
        (r"\bAMA\b", "AMA"), (r"\bHarvard\b", "Harvard"),
    ]:
        if re.search(pattern, blob, re.IGNORECASE):
            profile.style = style
            break

    profile.blinded = bool(re.search(
        r"blind(?:ed)?\s+review|anonymou?s(?:ed)?\s+manuscript|"
        r"remove\s+all\s+identifying", blob, re.IGNORECASE))
    return profile


# ------------------------------------------------------------------- checking


_ABSTRACT_HEADING = re.compile(
    r"^\s*([A-Z][A-Za-z /]{2,48}?)\s*[:—-]\s+", re.MULTILINE)


def check(profile: JournalProfile, *, body_words: int = 0,
          abstract: str = "", reference_count: int = 0,
          title: str = "", keywords: list[str] | None = None,
          tables_figures: int = 0) -> dict[str, Any]:
    """Compare a manuscript against a profile, one constraint at a time."""
    findings: list[dict[str, Any]] = []

    def add(label: str, status: str, observed: str, expected: str,
            advice: str = "") -> None:
        findings.append({"label": label, "status": status, "observed": observed,
                         "expected": expected, "advice": advice})

    if profile.word_limit:
        over = body_words > profile.word_limit
        add("Word limit", "not_met" if over else "met",
            f"{body_words:,} words",
            f"{profile.word_limit:,} maximum"
            + (f" — {profile.word_limit_note}" if profile.word_limit_note else ""),
            f"Cut {body_words - profile.word_limit:,} words." if over else "")

    if profile.abstract_limit:
        abstract_words = len(abstract.split())
        over = abstract_words > profile.abstract_limit
        add("Abstract length", "not_met" if over else "met",
            f"{abstract_words} words", f"{profile.abstract_limit} maximum",
            f"Cut {abstract_words - profile.abstract_limit} words from the "
            f"abstract." if over else "")

    if profile.abstract_structured and profile.abstract_headings:
        present = {" ".join(m.group(1).split()).lower()
                   for m in _ABSTRACT_HEADING.finditer(abstract or "")}
        missing = [h for h in profile.abstract_headings
                   if h.lower() not in present]
        add("Structured abstract",
            "met" if not missing else "not_met",
            f"{len(profile.abstract_headings) - len(missing)} of "
            f"{len(profile.abstract_headings)} headings present",
            "; ".join(profile.abstract_headings),
            ("Missing: " + ", ".join(missing)
             + ". An unstructured abstract, or one missing a required heading, is "
               "returned without review at journals that specify this."
             if missing else ""))

    if profile.reference_limit:
        over = reference_count > profile.reference_limit
        add("Reference limit", "not_met" if over else "met",
            f"{reference_count} references",
            f"{profile.reference_limit} maximum",
            f"Remove {reference_count - profile.reference_limit} references."
            if over else "")

    if profile.title_limit_characters and title:
        over = len(title) > profile.title_limit_characters
        add("Title length", "not_met" if over else "met",
            f"{len(title)} characters",
            f"{profile.title_limit_characters} maximum")

    if profile.keywords_range:
        low, high = profile.keywords_range
        count = len(keywords or [])
        ok = low <= count <= high
        add("Keywords", "met" if ok else "not_met",
            f"{count} keywords", f"{low}–{high}")

    if profile.tables_figures_limit:
        over = tables_figures > profile.tables_figures_limit
        add("Tables and figures", "not_met" if over else "met",
            f"{tables_figures}", f"{profile.tables_figures_limit} maximum")

    if profile.style and not profile.style.startswith("APA"):
        add("Reference style", "not_met", "APA 7", profile.style,
            f"This tool produces APA 7. {profile.name} requires "
            f"{profile.style}, and the conversion changes in-text citations as "
            f"well as the reference list — budget real time for it rather than "
            f"treating it as formatting.")

    for statement in profile.required_statements:
        add(f"Statement: {statement}", "cannot_check", "—", "required",
            "Add it to the manuscript before submission. This tool cannot see "
            "your submission form.")

    if profile.reporting_guideline:
        add("Reporting checklist", "cannot_check", "—",
            profile.reporting_guideline,
            "Download the checklist from equator-network.org, complete it, and "
            "upload it with the manuscript. This is the item authors most often "
            "discover is missing on submission day.")

    met = sum(1 for f in findings if f["status"] == "met")
    not_met = sum(1 for f in findings if f["status"] == "not_met")
    unknown = sum(1 for f in findings if f["status"] == "cannot_check")
    return {
        "journal": profile.name,
        "findings": findings,
        "counts": {"met": met, "not_met": not_met, "cannot_check": unknown},
        "headline": (f"{met} met, {not_met} outstanding, {unknown} to confirm "
                     f"yourself."),
        "verify": VERIFY_NOTE if profile.key in PROFILES else
                  "Parsed from the text you pasted. Check it against the source.",
        "notes": profile.notes,
    }
