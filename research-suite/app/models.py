"""
The record types the whole suite passes around.

Two design decisions worth stating up front, because everything else follows
from them:

**A Work carries its provenance, not just its metadata.** `source_db` and
`raw` are kept for every record, so the audit document can say *where* a
citation came from — PubMed's own record, a CINAHL export the user made by
hand, or a DOI resolved through Crossref. A reference the tool cannot trace
back to a retrieval is a reference it should not print.

**A Claim binds one sentence to one locus in one Work.** This is the object
that makes the companion audit document possible, and it is why drafting is
built as "assemble claims, then render prose" rather than "write prose, then
find citations for it". The second order is how unsupported sentences get
into papers.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any


# --------------------------------------------------------------------- authors


@dataclass
class Author:
    """One author.

    `family` + `given` for people; `is_group` for corporate authors (CDC, WHO,
    American Nurses Association), which APA 7 renders whole and never
    initialises. Getting this wrong is the single most common APA error in
    reference lists that were assembled by software.
    """

    family: str = ""
    given: str = ""
    suffix: str = ""
    is_group: bool = False

    @classmethod
    def group(cls, name: str) -> "Author":
        return cls(family=name.strip(), is_group=True)

    @classmethod
    def parse(cls, text: str) -> "Author":
        """Parse the shapes real databases emit.

        Handles ``Smith, John A.``, ``Smith JA`` (PubMed), ``John A. Smith``,
        and single-token corporate names. Ambiguity is resolved toward
        person-names only when there is a comma or a plausible initial run;
        otherwise the name is kept whole as a group, because mangling
        "World Health Organization" into "Organization, W. H." is a much worse
        failure than leaving a person's name unsplit.
        """
        text = " ".join(text.split())
        if not text:
            return cls()

        suffix = ""
        for candidate in ("Jr.", "Jr", "Sr.", "Sr", "II", "III", "IV"):
            pattern = r"(,\s*|\s+)" + re.escape(candidate) + r"\.?$"
            match = re.search(pattern, text)
            if match:
                suffix = candidate.rstrip(".")
                text = text[: match.start()].strip().rstrip(",")
                break

        if "," in text:
            family, _, given = text.partition(",")
            return cls(family=family.strip(), given=given.strip(), suffix=suffix)

        parts = text.split()
        if len(parts) == 1:
            return cls.group(text)
        if any(p.strip(".,").lower() in _ORG_WORDS for p in parts):
            return cls.group(text)

        # PubMed style: "Smith JA" / "van der Berg JAH" — trailing token is a
        # run of capitals with no periods and no lowercase.
        tail = parts[-1]
        if len(tail) <= 4 and tail.isupper() and tail.isalpha():
            return cls(family=" ".join(parts[:-1]), given=tail, suffix=suffix)

        # Otherwise assume "Given Middle Family", but only when the leading
        # tokens look like given names or initials.
        if _looks_like_given_run(parts[:-1]):
            return cls(family=parts[-1], given=" ".join(parts[:-1]), suffix=suffix)

        return cls.group(text)

    # -- rendering ---------------------------------------------------------

    def initials(self) -> str:
        """``John Archibald`` -> ``J. A.``; ``JA`` -> ``J. A.``"""
        if self.is_group or not self.given:
            return ""
        out: list[str] = []
        for token in re.split(r"[\s.]+", self.given):
            if not token:
                continue
            if token.isupper() and len(token) > 1 and "-" not in token:
                out.extend(f"{ch}." for ch in token)  # "JA" -> J. A.
            elif "-" in token:
                out.append("-".join(f"{p[0]}." for p in token.split("-") if p))
            else:
                out.append(f"{token[0]}.")
        return " ".join(out)

    def reference_name(self) -> str:
        """APA 7 reference-list form: ``Smith, J. A.`` or the whole group name."""
        if self.is_group:
            return self.family
        if not self.family:
            return self.given
        name = f"{self.family}, {self.initials()}".rstrip(", ").rstrip()
        if self.suffix:
            name = f"{name}, {self.suffix}"
        return name

    def intext_name(self) -> str:
        """APA 7 in-text form: surname only, or the whole group name."""
        return self.family or self.given

    def sort_key(self) -> str:
        return _fold(f"{self.family} {self.initials()}").strip()


# Words that mark a name as an organisation rather than a person. Without
# this, "World Health Organization" parses as a person named Organization and
# renders as "Organization, W. H." — which is both wrong and the kind of wrong
# a reader notices immediately.
_ORG_WORDS = {
    "academy", "administration", "agency", "alliance", "association",
    "authority", "board", "bureau", "center", "centers", "centre", "centres",
    "coalition", "college", "commission", "committee", "consortium", "corps",
    "council", "department", "division", "federation", "force", "foundation",
    "group", "hospital", "initiative", "institute", "institutes", "laboratory",
    "ministry", "network", "office", "organisation", "organization",
    "partnership", "program", "programme", "project", "school", "service",
    "services", "society", "taskforce", "trust", "university", "workgroup",
}


def _looks_like_given_run(tokens: list[str]) -> bool:
    """True when every leading token reads as a given name or an initial.

    This is the person-vs-organisation decision, and it is deliberately biased
    toward organisation: leaving a person's name unsplit is a cosmetic error,
    while initialising an agency's name produces a citation a reviewer will
    reject.
    """
    for token in tokens:
        bare = token.replace(".", "").replace("-", "")
        if not bare:
            return False
        if bare.lower() in _ORG_WORDS:
            return False
        if any(ch.isdigit() for ch in bare):
            return False  # "Healthy People 2030"
        if len(bare) == 1:
            continue  # an initial
        if bare[0].islower():
            return False  # "van", "de" — a name particle, not a given name
        if bare.isupper() and len(bare) > 3:
            return False  # "NIOSH" — an acronym
    # Three or more spelled-out capitalised words before the last token is far
    # more often an organisation than a person with three given names.
    spelled_out = [t for t in tokens if len(t.replace(".", "")) > 1]
    return len(spelled_out) < 3


def _fold(text: str) -> str:
    """Accent-insensitive, case-insensitive key for sorting and matching."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower()


# ------------------------------------------------------------------ work types


class WorkType(str, Enum):
    JOURNAL_ARTICLE = "journal-article"
    BOOK = "book"
    BOOK_CHAPTER = "book-chapter"
    REPORT = "report"
    WEBPAGE = "webpage"
    DATASET = "dataset"
    THESIS = "thesis"
    PREPRINT = "preprint"
    CONFERENCE_PAPER = "conference-paper"
    GUIDELINE = "guideline"


class EvidenceLevel(str, Enum):
    """JBI / AACN levels, kept as roman numerals because that is how they are
    written in every matrix a reviewer will read.

    ``UNGRADED`` is deliberately distinct from ``LEVEL_V``: a source we could
    not classify is not the same as expert opinion, and collapsing the two
    would let unclassifiable records masquerade as the bottom of the
    hierarchy.
    """

    LEVEL_I = "I"
    LEVEL_II = "II"
    LEVEL_III = "III"
    LEVEL_IV = "IV"
    LEVEL_V = "V"
    UNGRADED = "ungraded"
    EXCLUDED = "not-evidence"  # editorial, letter, news, retracted

    @property
    def label(self) -> str:
        return {
            "I": "Level I — systematic review, meta-analysis, or RCT",
            "II": "Level II — controlled trial without randomisation",
            "III": "Level III — cohort or case-control study",
            "IV": "Level IV — descriptive or qualitative study",
            "V": "Level V — expert consensus or clinical guideline",
            "ungraded": "Not graded — design could not be determined",
            "not-evidence": "Not evidence-based — opinion, editorial, or retracted",
        }[self.value]

    @property
    def rank(self) -> int:
        """Sortable: lower is stronger. Non-levels sort last."""
        return {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5,
                "ungraded": 8, "not-evidence": 9}[self.value]


@dataclass
class Work:
    """One retrieved or imported source."""

    # identity
    key: str = ""                      # stable local id, assigned by fingerprint()
    doi: str = ""
    pmid: str = ""
    pmcid: str = ""
    isbn: str = ""
    url: str = ""

    # bibliographic
    work_type: WorkType = WorkType.JOURNAL_ARTICLE
    authors: list[Author] = field(default_factory=list)
    editors: list[Author] = field(default_factory=list)
    year: str = ""                     # str, not int: "2024", "2024a", "n.d.", "in press"
    title: str = ""
    container: str = ""                # journal, book, or site name
    volume: str = ""
    issue: str = ""
    pages: str = ""
    edition: str = ""
    publisher: str = ""
    report_number: str = ""
    language: str = ""
    abstract: str = ""

    # evidence metadata
    publication_types: list[str] = field(default_factory=list)
    mesh_terms: list[str] = field(default_factory=list)
    level: EvidenceLevel = EvidenceLevel.UNGRADED
    level_reason: str = ""
    peer_reviewed: bool | None = None
    retracted: bool = False
    retraction_note: str = ""
    open_access_url: str = ""

    # provenance — never dropped
    source_db: str = ""                # "pubmed", "europepmc", "ris-import", ...
    retrieved_at: str = ""
    query: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    # screening
    included: bool | None = None
    screen_reason: str = ""

    # ---------------------------------------------------------------- helpers

    def fingerprint(self) -> str:
        """A stable id that survives being retrieved twice from two databases.

        DOI wins, then PMID, then a normalised title+year hash. The title
        fallback is what catches the same trial indexed in PubMed and CINAHL
        with different accession numbers and no shared DOI.
        """
        if self.doi:
            return "doi:" + normalise_doi(self.doi)
        if self.pmid:
            return "pmid:" + self.pmid.strip()
        if self.pmcid:
            return "pmcid:" + self.pmcid.strip().upper()
        stem = f"{_title_key(self.title)}|{self.year.strip()[:4]}"
        return "sig:" + hashlib.sha1(stem.encode("utf-8")).hexdigest()[:16]

    def ensure_key(self) -> str:
        if not self.key:
            self.key = self.fingerprint()
        return self.key

    def short_label(self) -> str:
        """"Smith (2023)" — how a source is named on screen and in a report.

        Not a citation: it has no formatting rules to honour and never stands in
        for one. It exists so a list of sources reads like something a person
        would say out loud, rather than like a list of keys.
        """
        name = self.first_author_surname() or (self.title[:40] or "Untitled")
        year = self.year or "n.d."
        return f"{name} ({year})"

    def first_author_surname(self) -> str:
        if self.authors:
            return self.authors[0].intext_name()
        if self.editors:
            return self.editors[0].intext_name()
        return ""

    def sort_key(self) -> tuple:
        """APA 7 reference-list order: author, then year, then title."""
        names = [a.sort_key() for a in (self.authors or self.editors)]
        year = self.year or "zzzz"          # n.d. sorts before a year in APA,
        if year.lower().startswith("n.d"):  # so give it a low sentinel instead
            year = "0000"
        return (names or [_fold(self.title)], year, _title_key(self.title))

    def to_dict(self) -> dict[str, Any]:
        out = asdict(self)
        out["work_type"] = self.work_type.value
        out["level"] = self.level.value
        return out


def normalise_doi(doi: str) -> str:
    """Strip the many prefixes databases put in front of a DOI, and lowercase.

    DOIs are case-insensitive by specification, which matters here because the
    same article arrives as ``10.1001/JAMA.2023.1`` from one index and
    ``https://doi.org/10.1001/jama.2023.1`` from another; without this they
    would dedupe as two studies.
    """
    doi = doi.strip()
    for prefix in ("https://doi.org/", "http://doi.org/", "https://dx.doi.org/",
                   "http://dx.doi.org/", "doi:", "DOI:", "doi.org/"):
        if doi.lower().startswith(prefix.lower()):
            doi = doi[len(prefix):]
            break
    return doi.strip().rstrip(".").lower()


def _title_key(title: str) -> str:
    """Normalised title for matching: folded, punctuation-free, single-spaced."""
    folded = _fold(title)
    return " ".join(re.sub(r"[^a-z0-9 ]+", " ", folded).split())


# ----------------------------------------------------------------- appraisal


@dataclass
class AppraisalItem:
    question: str
    answer: str = "unclear"       # yes | no | unclear | n/a
    note: str = ""


@dataclass
class Appraisal:
    """A critical appraisal of one Work.

    `instrument` names the published instrument this appraisal *follows*
    (CASP, JBI, AMSTAR 2, AGREE II, RoB 2). The question text in `items` is
    written for this tool rather than copied from those instruments — see
    `app/evidence/appraisal.py` for why that distinction is load-bearing.
    """

    work_key: str = ""
    instrument: str = ""
    instrument_citation: str = ""
    items: list[AppraisalItem] = field(default_factory=list)
    strengths: str = ""
    limitations: str = ""
    overall: str = ""             # high | moderate | low | very-low
    overall_reason: str = ""      # how the rating was derived, printed on screen
    appraised_by: str = "assisted"  # assisted | user
    appraised_at: str = ""

    def score(self) -> tuple[int, int]:
        """(items answered 'yes', items that could be answered)."""
        gradable = [i for i in self.items if i.answer != "n/a"]
        return sum(1 for i in gradable if i.answer == "yes"), len(gradable)


@dataclass
class Extraction:
    """One row of the evidence matrix."""

    work_key: str = ""
    design: str = ""
    setting: str = ""
    sample_description: str = ""
    sample_size: str = ""
    intervention: str = ""
    comparator: str = ""
    outcomes: str = ""
    key_findings: str = ""
    statistics: str = ""
    strengths: str = ""
    limitations: str = ""
    relevance: str = ""


# --------------------------------------------------------------------- claims


class SupportType(str, Enum):
    PARAPHRASE = "paraphrase"       # synthesised in the author's own words
    DIRECT_QUOTE = "direct-quote"   # verbatim, requires page/para locator
    DATA_POINT = "data-point"       # a number or statistic lifted from a source
    NO_CITATION = "no-citation"     # the author's own analysis or transition


@dataclass
class Claim:
    """One sentence of the paper, bound to what supports it.

    A claim with `support_type` other than NO_CITATION and no `work_keys` is a
    defect the tool refuses to export — that combination is exactly what an
    uncited borrowed assertion looks like.
    """

    claim_id: str = ""
    section: str = ""
    order: int = 0
    text: str = ""
    support_type: SupportType = SupportType.PARAPHRASE
    work_keys: list[str] = field(default_factory=list)
    locus: str = ""                 # "p. 412", "para. 3", "Table 2", "Section 3.2"
    source_quote: str = ""          # the passage relied on, for the audit doc
    rationale: str = ""             # why this source, in the author's terms
    verified: bool = False

    def is_supported(self) -> bool:
        return self.support_type is SupportType.NO_CITATION or bool(self.work_keys)

    def needs_locator(self) -> bool:
        """APA 7 requires a locator for direct quotations, and recommends one
        for a specific paraphrased passage."""
        return self.support_type is SupportType.DIRECT_QUOTE and not self.locus


# -------------------------------------------------------------------- project


@dataclass
class TitlePage:
    """APA 7 distinguishes student and professional title pages, and the
    difference is not cosmetic — a student paper carries course, instructor and
    due date; a professional paper carries an author note and running head."""

    variant: str = "student"        # student | professional
    title: str = ""
    authors: list[str] = field(default_factory=list)
    affiliations: list[str] = field(default_factory=list)
    course: str = ""
    instructor: str = ""
    due_date: str = ""
    running_head: str = ""         # <= 50 chars incl. spaces, uppercase
    author_note: str = ""


@dataclass
class StyleProfile:
    """Measured features of the user's own writing, from samples they supply."""

    sample_count: int = 0
    word_count: int = 0
    mean_sentence_words: float = 0.0
    sentence_words_sd: float = 0.0
    mean_paragraph_sentences: float = 0.0
    type_token_ratio: float = 0.0
    passive_rate: float = 0.0
    hedge_rate: float = 0.0
    first_person_rate: float = 0.0
    semicolon_per_1k: float = 0.0
    flesch_kincaid_grade: float = 0.0
    frequent_terms: list[str] = field(default_factory=list)
    frequent_connectives: list[str] = field(default_factory=list)
    notes: str = ""


@dataclass
class Project:
    """One paper, with everything needed to rebuild both documents."""

    project_id: str = ""
    topic: str = ""
    question: str = ""
    pico: dict[str, str] = field(default_factory=dict)
    academic_level: str = "graduate"    # undergraduate | graduate | doctoral
    inclusion: list[str] = field(default_factory=list)
    exclusion: list[str] = field(default_factory=list)
    min_level: str = "IV"

    title_page: TitlePage = field(default_factory=TitlePage)
    works: list[Work] = field(default_factory=list)
    appraisals: list[Appraisal] = field(default_factory=list)
    extractions: list[Extraction] = field(default_factory=list)
    claims: list[Claim] = field(default_factory=list)
    style: StyleProfile = field(default_factory=StyleProfile)

    searches: list[dict[str, Any]] = field(default_factory=list)
    excluded_notes: list[dict[str, str]] = field(default_factory=list)

    # Free-form structured attachments that are not part of the paper itself:
    # the framed question and its search strategy, the extracted rubric, the
    # journal profile. Kept as one dict rather than as three typed fields because
    # each is produced by a module that owns its own shape, and pinning those
    # shapes here would mean editing the core model every time one of them gains
    # a field.
    notes: dict[str, Any] = field(default_factory=dict)
    abstract: str = ""
    keywords: list[str] = field(default_factory=list)
    font: str = ""

    created_at: str = ""
    updated_at: str = ""

    def work(self, key: str) -> Work | None:
        return next((w for w in self.works if w.key == key), None)

    def included_works(self) -> list[Work]:
        return [w for w in self.works if w.included is not False and not w.retracted]

    def cited_works(self) -> list[Work]:
        """Only works an actual claim relies on.

        APA 7 requires the reference list and the in-text citations to match
        exactly, so the reference page is generated from the claim ledger and
        never from the search results.
        """
        used: list[str] = []
        for claim in self.claims:
            for key in claim.work_keys:
                if key not in used:
                    used.append(key)
        return sorted(
            (w for w in self.works if w.key in used),
            key=lambda w: w.sort_key(),
        )
