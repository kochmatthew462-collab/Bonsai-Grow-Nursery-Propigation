"""
PICO(T) and SPIDER question builders, and the Boolean strings they produce.

## Why a framework at all

A question written as prose retrieves prose. "Does hourly rounding reduce falls?"
run against PubMed returns whatever shares those words. The same question framed as
PICO — population, intervention, comparison, outcome, timeframe — decomposes into
concept blocks, and a search built from concept blocks is the one a systematic
review can defend: each block is OR-ed internally to catch synonyms, and the blocks
are AND-ed together to enforce the question.

This module does that decomposition and then **translates it per database**,
because the syntax genuinely differs and a string that works in PubMed fails
silently in CINAHL:

| | PubMed | CINAHL (EBSCOhost) | Cochrane CENTRAL | Scopus |
|---|---|---|---|---|
| Controlled vocabulary | `"term"[MeSH]` | `(MH "Term")` | `[mh term]` | none |
| Title/abstract | `[tiab]` | `TI x OR AB x` | `:ti,ab,kw` | `TITLE-ABS-KEY()` |
| Truncation | `*` | `*` | `*` | `*` |
| Adjacency | none | `N3` | `NEAR/3` | `W/3` |

The differences matter more than they look. CINAHL has no `[tiab]` at all, so a
PubMed-shaped string returns almost nothing there; and PubMed's automatic term
mapping silently expands unquoted phrases, which is why every phrase here is
quoted.

## What this does not do

It does not invent your synonyms. It expands a term you enter against a small
built-in thesaurus of nursing and health-services concepts, and everything else is
yours to add. A tool that generated plausible-looking synonym lists would produce a
search strategy nobody could defend at a viva, because you would not be able to say
where the terms came from.

`SPIDER` is offered alongside PICO because PICO is built for effectiveness
questions with a comparison, and qualitative questions do not have one. Forcing a
qualitative question into PICO produces an empty C block and a search that misses
the phenomenological literature entirely.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# ------------------------------------------------------------------- thesaurus


# Deliberately small. These are the concepts where a missing synonym silently
# halves a nursing search, and each entry is a term pair a reviewer would expect
# to see OR-ed together. Anything not here is the user's to supply, and the UI says
# so — a generated synonym you cannot source is a liability in a methods section.
_THESAURUS: dict[str, list[str]] = {
    "nurse": ["nurses", "nursing", "nursing staff", "registered nurse"],
    "nursing": ["nurse", "nurses", "nursing staff"],
    "staffing": ["nurse staffing", "staffing level", "nurse-to-patient ratio",
                 "workload", "skill mix"],
    "fall": ["falls", "accidental fall", "falling"],
    "pressure injury": ["pressure ulcer", "bedsore", "decubitus ulcer",
                        "pressure sore"],
    "pressure ulcer": ["pressure injury", "bedsore", "decubitus ulcer"],
    "delirium": ["acute confusion", "acute confusional state"],
    "sepsis": ["septicaemia", "septicemia", "septic shock", "bloodstream infection"],
    "hand hygiene": ["handwashing", "hand washing", "hand disinfection"],
    "catheter-associated urinary tract infection": ["CAUTI", "catheter associated"],
    "central line": ["central venous catheter", "CLABSI", "central line associated"],
    "burnout": ["occupational burnout", "compassion fatigue", "emotional exhaustion"],
    "retention": ["turnover", "intent to leave", "attrition"],
    "medication error": ["drug error", "administration error", "prescribing error"],
    "handoff": ["handover", "shift report", "SBAR", "clinical handover"],
    "readmission": ["rehospitalisation", "rehospitalization", "readmitted"],
    "adherence": ["compliance", "concordance", "persistence"],
    "education": ["teaching", "patient education", "health education",
                  "psychoeducation"],
    "telehealth": ["telemedicine", "remote monitoring", "virtual care",
                   "e-health"],
    "quality of life": ["QOL", "health-related quality of life", "wellbeing"],
    "mortality": ["death", "survival", "fatality", "case fatality"],
    "length of stay": ["hospital stay", "LOS", "duration of hospitalisation"],
    "pain": ["analgesia", "pain management", "pain score"],
    "anxiety": ["anxiousness", "anxiety disorder"],
    "depression": ["depressive symptoms", "depressive disorder"],
    "older adult": ["elderly", "aged", "geriatric", "older people"],
    "intensive care": ["critical care", "ICU", "intensive care unit"],
    "emergency department": ["emergency room", "accident and emergency", "ED",
                             "A&E"],
    "usual care": ["standard care", "routine care", "control group",
                   "treatment as usual"],
    "simulation": ["simulation training", "high-fidelity simulation",
                   "simulated learning"],
    "experience": ["perception", "perspective", "view", "attitude", "lived experience"],
}


# MeSH headings for the same concepts, where a widely used heading exists. Only
# terms verifiable in the MeSH tree are listed: a fabricated MeSH heading produces
# a search that silently returns nothing, which is worse than no MeSH at all
# because the zero looks like a finding.
_MESH: dict[str, list[str]] = {
    "nurse": ["Nurses", "Nursing Staff, Hospital"],
    "nursing": ["Nursing", "Nursing Care"],
    "staffing": ["Personnel Staffing and Scheduling", "Nursing Staff, Hospital"],
    "fall": ["Accidental Falls"],
    "pressure injury": ["Pressure Ulcer"],
    "pressure ulcer": ["Pressure Ulcer"],
    "delirium": ["Delirium"],
    "sepsis": ["Sepsis", "Shock, Septic"],
    "hand hygiene": ["Hand Hygiene", "Hand Disinfection"],
    "burnout": ["Burnout, Professional"],
    "medication error": ["Medication Errors"],
    "readmission": ["Patient Readmission"],
    "adherence": ["Patient Compliance", "Medication Adherence"],
    "education": ["Patient Education as Topic", "Health Education"],
    "telehealth": ["Telemedicine"],
    "quality of life": ["Quality of Life"],
    "mortality": ["Mortality", "Hospital Mortality"],
    "length of stay": ["Length of Stay"],
    "pain": ["Pain", "Pain Management"],
    "anxiety": ["Anxiety"],
    "depression": ["Depression"],
    "older adult": ["Aged", "Aged, 80 and over"],
    "intensive care": ["Intensive Care Units", "Critical Care"],
    "emergency department": ["Emergency Service, Hospital"],
    "simulation": ["Simulation Training", "Patient Simulation"],
}


def expand(term: str) -> dict[str, list[str]]:
    """Synonyms and MeSH headings for one concept term.

    Matching is on the whole normalised term and on its singular form only. A
    substring match would expand "fall" inside "fallopian", and a search strategy
    that quietly included the wrong concept is the kind of error that survives peer
    review and then gets found by a reader.
    """
    key = " ".join((term or "").lower().split())
    singular = key[:-1] if key.endswith("s") and not key.endswith("ss") else key
    synonyms = _THESAURUS.get(key) or _THESAURUS.get(singular) or []
    mesh = _MESH.get(key) or _MESH.get(singular) or []
    return {"synonyms": list(synonyms), "mesh": list(mesh)}


# ------------------------------------------------------------------- structures


@dataclass
class Concept:
    """One block of a framed question: a label plus the terms that stand for it.

    `terms` are OR-ed together inside the block. `mesh` is OR-ed in as controlled
    vocabulary where the database supports it. `explode` maps to PubMed's default
    (a MeSH term explodes unless suffixed `:noexp`), and is offered because a
    reviewer will ask.
    """

    label: str = ""
    terms: list[str] = field(default_factory=list)
    mesh: list[str] = field(default_factory=list)
    explode: bool = True
    optional: bool = False

    def all_terms(self) -> list[str]:
        return [t.strip() for t in self.terms if t and t.strip()]

    def is_empty(self) -> bool:
        return not self.all_terms() and not self.mesh


# The two frameworks, as (key, label, guidance, required) tuples. Guidance is shown
# in the UI beside each box, because the commonest way a PICO goes wrong is a
# population written as a diagnosis or an outcome written as an intervention.
PICO_SLOTS = [
    ("population", "P — Population or problem",
     "Who, and in what setting. \"Adult inpatients on medical-surgical units\", "
     "not \"falls\". If you find yourself writing the intervention here, the "
     "question is not yet framed.", True),
    ("intervention", "I — Intervention or exposure",
     "The thing being done or experienced. \"Hourly nurse rounding\". For an "
     "aetiology question this is the exposure rather than a treatment.", True),
    ("comparison", "C — Comparison",
     "What it is being compared against — usual care, another intervention, or "
     "nothing. Leaving this empty is legitimate and common; it widens the search "
     "rather than breaking it.", False),
    ("outcome", "O — Outcome",
     "What you will measure, in the terms the literature measures it. \"Fall "
     "rate per 1,000 patient-days\" retrieves differently from \"safety\".", True),
    ("timeframe", "T — Timeframe",
     "The follow-up period, if the question depends on one. Usually left empty; "
     "it is a screening criterion more often than a search term.", False),
]

SPIDER_SLOTS = [
    ("sample", "S — Sample",
     "Qualitative research studies a sample, not a population — the word choice "
     "is deliberate, because the findings are not claimed to generalise.", True),
    ("phenomenon", "PI — Phenomenon of interest",
     "The experience, behaviour or decision being studied, rather than an "
     "intervention applied to it.", True),
    ("design", "D — Design",
     "Interview, focus group, grounded theory, phenomenology, case study. This "
     "block is what pulls qualitative work out of a database that indexes it "
     "poorly.", False),
    ("evaluation", "E — Evaluation",
     "The outcome as qualitative research frames it: views, experiences, "
     "attitudes, perceptions.", True),
    ("research_type", "R — Research type",
     "Qualitative, mixed methods, or both.", False),
]


@dataclass
class Question:
    """A framed question, its concepts, and the limits applied to the search."""

    framework: str = "pico"                 # "pico" or "spider"
    question_text: str = ""
    concepts: dict[str, Concept] = field(default_factory=dict)
    years: int | None = None                # publication window, in years
    languages: list[str] = field(default_factory=list)
    humans_only: bool = True
    peer_reviewed_only: bool = True
    minimum_level: str = ""                 # a JBI/AACN level id, or blank

    def slots(self) -> list[tuple[str, str, str, bool]]:
        return SPIDER_SLOTS if self.framework == "spider" else PICO_SLOTS

    def filled(self) -> list[tuple[str, Concept]]:
        """Non-empty concept blocks, in framework order."""
        order = [key for key, _, _, _ in self.slots()]
        return [(key, self.concepts[key]) for key in order
                if key in self.concepts and not self.concepts[key].is_empty()]

    def missing_required(self) -> list[str]:
        out: list[str] = []
        for key, label, _guidance, required in self.slots():
            if not required:
                continue
            concept = self.concepts.get(key)
            if concept is None or concept.is_empty():
                out.append(label)
        return out

    def narrative(self) -> str:
        """The question as a sentence, for the methods section.

        A framed question has to appear in the paper in prose as well as in a
        table, and writing it twice by hand is how the two drift apart.
        """
        parts = self.filled()
        if not parts:
            return self.question_text.strip()
        pieces: list[str] = []
        labels = {key: label for key, label, _g, _r in self.slots()}
        for key, concept in parts:
            label = labels.get(key, key).split("—")[-1].strip()
            pieces.append(f"{label}: {', '.join(concept.all_terms()) or '—'}")
        head = self.question_text.strip()
        return (f"{head} " if head else "") + "(" + "; ".join(pieces) + ")"


# ------------------------------------------------------------------ translation


def _quote(term: str) -> str:
    """Quote a phrase so a database treats it as one concept.

    PubMed's automatic term mapping silently expands unquoted phrases into
    something else entirely — "nurse staffing" becomes a MeSH explosion plus every
    word individually — so a phrase that is not quoted is not the phrase you
    searched.
    """
    cleaned = " ".join((term or "").split())
    if not cleaned:
        return ""
    if cleaned.startswith('"') and cleaned.endswith('"'):
        return cleaned
    # A single word with no wildcard needs no quoting and quoting it would block
    # PubMed's stemming, which is usually wanted.
    if " " not in cleaned and "*" not in cleaned:
        return cleaned
    return f'"{cleaned}"'


def _dedupe(terms: list[str]) -> list[str]:
    """Drop case-insensitive duplicates, keeping first appearance.

    The databases without a thesaurus get MeSH headings folded in as phrases, and
    a heading often differs from a synonym only in case — "Nurses" beside
    "nurses". Both would be searched identically and the duplicate only makes the
    string harder to read in a methods section.
    """
    seen: set[str] = set()
    out: list[str] = []
    for term in terms:
        key = " ".join(term.lower().split())
        if key and key not in seen:
            seen.add(key)
            out.append(term)
    return out


def _or_join(parts: list[str]) -> str:
    parts = [p for p in parts if p]
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    return "(" + " OR ".join(parts) + ")"


def _and_join(blocks: list[str]) -> str:
    blocks = [b for b in blocks if b]
    if not blocks:
        return ""
    return " AND ".join(blocks)


def to_pubmed(question: Question) -> str:
    """PubMed / MEDLINE syntax: `[Mesh]` and `[tiab]`."""
    blocks: list[str] = []
    for _key, concept in question.filled():
        parts: list[str] = []
        for heading in concept.mesh:
            suffix = "" if concept.explode else ":noexp"
            parts.append(f'"{heading}"[Mesh{suffix}]')
        for term in concept.all_terms():
            parts.append(f"{_quote(term)}[tiab]")
        blocks.append(_or_join(parts))
    query = _and_join(blocks)

    limits: list[str] = []
    if question.humans_only:
        limits.append('"humans"[MeSH Terms]')
    if question.languages:
        limits.append(_or_join([f"{lang}[lang]" for lang in question.languages]))
    if question.years:
        limits.append(f'"last {question.years} years"[dp]')
    if limits:
        query = _and_join([query] + limits) if query else _and_join(limits)
    return query


def to_cinahl(question: Question) -> str:
    """CINAHL / EBSCOhost syntax.

    Two differences from PubMed that break a copied string: controlled vocabulary
    is `(MH "Heading")` rather than `[Mesh]`, and there is **no combined
    title-abstract field** — `TI` and `AB` are searched separately and OR-ed. A
    PubMed string pasted into CINAHL returns almost nothing, silently.
    """
    blocks: list[str] = []
    for _key, concept in question.filled():
        parts: list[str] = []
        for heading in concept.mesh:
            # CINAHL headings differ from MeSH, so these are offered as a starting
            # point and flagged as needing checking against CINAHL Headings.
            plus = "+" if concept.explode else ""
            parts.append(f'(MH "{heading}{plus}")')
        for term in concept.all_terms():
            quoted = _quote(term)
            parts.append(f"TI {quoted} OR AB {quoted}")
        blocks.append(_or_join(parts))
    query = _and_join(blocks)
    if question.years:
        query += f"\nLimiters: Published Date last {question.years} years"
    if question.peer_reviewed_only:
        query += "; Peer Reviewed"
    if question.languages:
        query += "; Language: " + ", ".join(question.languages)
    return query


def to_cochrane(question: Question) -> str:
    """Cochrane Library / CENTRAL syntax: `[mh]` and `:ti,ab,kw`."""
    blocks: list[str] = []
    for _key, concept in question.filled():
        parts: list[str] = []
        for heading in concept.mesh:
            prefix = "mh" if concept.explode else "mh ^"
            parts.append(f'[{prefix} "{heading}"]')
        for term in concept.all_terms():
            parts.append(f"{_quote(term)}:ti,ab,kw")
        blocks.append(_or_join(parts))
    return _and_join(blocks)


def to_scopus(question: Question) -> str:
    """Scopus syntax: no controlled vocabulary, `TITLE-ABS-KEY()`."""
    blocks: list[str] = []
    for _key, concept in question.filled():
        # Scopus has no thesaurus, so MeSH headings are folded in as phrases
        # rather than dropped — losing them would narrow the search silently.
        terms = _dedupe(concept.all_terms() + list(concept.mesh))
        parts = [_quote(term) for term in terms]
        inner = _or_join(parts)
        blocks.append(f"TITLE-ABS-KEY({inner})" if inner else "")
    query = _and_join(blocks)
    if question.years:
        query += f" AND PUBYEAR > {2026 - question.years - 1}"
    if question.languages:
        query += " AND (" + " OR ".join(
            f'LANGUAGE("{lang}")' for lang in question.languages) + ")"
    return query


def to_web_of_science(question: Question) -> str:
    """Web of Science syntax: `TS=` topic search."""
    blocks: list[str] = []
    for _key, concept in question.filled():
        terms = _dedupe(concept.all_terms() + list(concept.mesh))
        inner = _or_join([_quote(term) for term in terms])
        blocks.append(f"TS=({inner})" if inner else "")
    return _and_join(blocks)


def to_plain(question: Question) -> str:
    """A syntax-free string for Europe PMC, Google Scholar and general use."""
    blocks: list[str] = []
    for _key, concept in question.filled():
        terms = _dedupe(concept.all_terms() + list(concept.mesh))
        blocks.append(_or_join([_quote(term) for term in terms]))
    return _and_join(blocks)


TRANSLATORS = {
    "pubmed": ("PubMed / MEDLINE", to_pubmed,
               "Runs directly from the Sources screen."),
    "cinahl": ("CINAHL (EBSCOhost)", to_cinahl,
               "Copy into CINAHL, run it there, export the results and import "
               "the file — CINAHL has no API a personal licence reaches."),
    "cochrane": ("Cochrane Library / CENTRAL", to_cochrane,
                 "Copy into the Cochrane Library's advanced search."),
    "scopus": ("Scopus", to_scopus,
               "Copy into Scopus, export as CSV or RIS and import the file."),
    "web_of_science": ("Web of Science", to_web_of_science,
                       "Copy into Web of Science and export."),
    "plain": ("Europe PMC and general", to_plain,
              "Runs directly from the Sources screen."),
}


def translate_all(question: Question) -> list[dict[str, Any]]:
    """Every database's string, with the caveats that apply to it."""
    out: list[dict[str, Any]] = []
    for key, (label, translator, note) in TRANSLATORS.items():
        try:
            query = translator(question)
        except Exception as error:                       # pragma: no cover
            query, note = "", f"could not be built: {error}"
        caveats: list[str] = []
        if key == "cinahl" and any(c.mesh for _k, c in question.filled()):
            caveats.append(
                "The controlled-vocabulary terms here are MeSH headings. CINAHL "
                "uses its own CINAHL Headings, which overlap but are not "
                "identical — check each one in CINAHL's thesaurus before you run "
                "this, or drop them and rely on the TI/AB terms.")
        if key == "scopus" and any(c.mesh for _k, c in question.filled()):
            caveats.append(
                "Scopus has no thesaurus, so the controlled-vocabulary terms have "
                "been folded in as phrases. That is deliberate — dropping them "
                "would narrow the search without saying so.")
        if key == "pubmed" and question.years:
            caveats.append(
                "The date limit uses [dp], the publication date. If you need the "
                "Entrez date instead, change [dp] to [edat].")
        out.append({
            "database": key,
            "label": label,
            "query": query,
            "how_to_run": note,
            "caveats": caveats,
        })
    return out


# ------------------------------------------------------------------- building


def build(payload: dict[str, Any]) -> Question:
    """Construct a Question from a request body, expanding each concept."""
    framework = str(payload.get("framework", "pico")).lower()
    if framework not in ("pico", "spider"):
        framework = "pico"
    question = Question(
        framework=framework,
        question_text=str(payload.get("question_text", "") or "").strip(),
        humans_only=bool(payload.get("humans_only", True)),
        peer_reviewed_only=bool(payload.get("peer_reviewed_only", True)),
        minimum_level=str(payload.get("minimum_level", "") or ""),
        languages=[str(x) for x in (payload.get("languages") or []) if x],
    )
    years = payload.get("years")
    if years not in (None, ""):
        try:
            question.years = max(1, int(years))
        except (TypeError, ValueError):
            question.years = None

    raw_concepts = payload.get("concepts") or {}
    for key, label, _guidance, _required in question.slots():
        entry = raw_concepts.get(key) or {}
        if isinstance(entry, str):
            entry = {"terms": [entry]}
        terms = entry.get("terms")
        if isinstance(terms, str):
            terms = [t.strip() for t in re.split(r"[,;\n]", terms)]
        terms = [str(t).strip() for t in (terms or []) if str(t).strip()]

        mesh = entry.get("mesh")
        if isinstance(mesh, str):
            mesh = [m.strip() for m in re.split(r"[,;\n]", mesh)]
        mesh = [str(m).strip() for m in (mesh or []) if str(m).strip()]

        # Expansion is opt-in per block, so a user who wants exactly their own
        # terms gets exactly their own terms.
        if entry.get("expand"):
            for term in list(terms):
                found = expand(term)
                for synonym in found["synonyms"]:
                    if synonym.lower() not in {t.lower() for t in terms}:
                        terms.append(synonym)
                for heading in found["mesh"]:
                    if heading.lower() not in {m.lower() for m in mesh}:
                        mesh.append(heading)

        question.concepts[key] = Concept(
            label=label,
            terms=terms,
            mesh=mesh,
            explode=bool(entry.get("explode", True)),
            optional=not _required,
        )
    return question


def frameworks() -> list[dict[str, Any]]:
    """Both frameworks and their slots, for the UI."""
    return [
        {
            "key": "pico",
            "label": "PICO(T)",
            "use_when": "Effectiveness, aetiology, diagnosis or prognosis — any "
                        "question with a comparison.",
            "slots": [{"key": k, "label": l, "guidance": g, "required": r}
                      for k, l, g, r in PICO_SLOTS],
        },
        {
            "key": "spider",
            "label": "SPIDER",
            "use_when": "Qualitative and mixed-methods questions. PICO forces an "
                        "empty comparison block on these and the search then "
                        "misses the phenomenological literature.",
            "slots": [{"key": k, "label": l, "guidance": g, "required": r}
                      for k, l, g, r in SPIDER_SLOTS],
        },
    ]


def strategy_report(question: Question) -> dict[str, Any]:
    """Everything a methods section needs about the search, in one object.

    A systematic review is appraised on its search strategy, and PRISMA item 7
    asks for the full string for at least one database with all limits. This is
    what the audit document prints.
    """
    return {
        "framework": question.framework.upper(),
        "question": question.narrative(),
        "concepts": [
            {
                "key": key,
                "label": concept.label,
                "terms": concept.all_terms(),
                "mesh": concept.mesh,
                "explode": concept.explode,
            }
            for key, concept in question.filled()
        ],
        "limits": {
            "years": question.years,
            "languages": question.languages,
            "humans_only": question.humans_only,
            "peer_reviewed_only": question.peer_reviewed_only,
            "minimum_level": question.minimum_level,
        },
        "queries": translate_all(question),
        "missing_required": question.missing_required(),
        "reporting_note": (
            "PRISMA 2020 item 7 asks for the full search strategy for at least "
            "one database, including every filter and limit, so that it can be "
            "reproduced. Paste the string for whichever database you actually "
            "searched into your methods section, with the date you ran it — a "
            "strategy without a run date cannot be reproduced, because databases "
            "grow."
        ),
    }
