"""
Originality and citation-integrity checks.

**Read this first, because it contradicts one of the requested features.**

The request asks for a scanner that verifies **0% similarity** before export.
That number is not achievable, and more importantly it is not desirable — no
legitimate paper scores 0%. Similarity scores count matched strings, and a
correct APA paper necessarily contains:

* every reference-list entry, which matches the original article exactly by
  design;
* direct quotations, which are supposed to match verbatim;
* the standard phrasing of the field — "a statistically significant
  difference", "the purpose of this study was to examine", "participants were
  recruited from" — which appears in thousands of papers because it is the
  correct way to say those things;
* instrument names, MeSH terms, and legally fixed wording.

Turnitin reports a similarity *index*, not a verdict, and its own guidance is
that the number needs human interpretation. A tool promising 0% would either be
lying or would be pushing the user to mangle correct citations to chase a
meaningless target. No vendor guarantees 0%, and AI-detection scores are less
reliable still — they carry documented false-positive rates against
non-native-English writing, so gating an export on one would fail honest work.

**What this module does instead**, all three of which are more useful than a
single percentage:

1. **Verbatim overlap against the sources this paper actually cites.** This is
   the check that catches real accidental plagiarism: a phrase lifted from an
   abstract during note-taking and never reworded. A general web scan cannot do
   this better, because it does not know which twenty papers you were reading.
2. **A citation-coverage audit.** Every borrowed claim must name a source;
   every direct quotation must carry a locator; every quotation of 40+ words
   must be a block quote; in-text citations and the reference list must match
   exactly, both directions. These are hard failures that block export.
3. **A hook for a commercial similarity API** if the user buys one, with the
   result reported as an index to interpret rather than a pass/fail gate.

`export_blockers` is what the export endpoint calls. It returns hard defects
only — things that are unambiguously wrong in an APA paper, not stylistic
opinions.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from ..models import Claim, Project, SupportType, Work

# A match of this many consecutive significant words is long enough to be worth
# a human look. Eight is the shortest window that does not fire constantly on
# ordinary academic phrasing while still catching a lifted clause.
DEFAULT_SHINGLE = 8

# Fixed academic phrasing that legitimately recurs. Matches consisting only of
# these words are not reported, because telling a user to reword "there was no
# statistically significant difference between groups" is bad advice.
_CONVENTIONAL_PHRASES = [
    "the purpose of this study was to",
    "the aim of this study was to",
    "there was no statistically significant difference",
    "a statistically significant difference between groups",
    "participants were recruited from",
    "data were analysed using",
    "data were analyzed using",
    "informed consent was obtained from all participants",
    "the institutional review board approved",
    "further research is needed to",
    "these findings suggest that",
    "results are presented as mean and standard deviation",
    "odds ratio and ninety five percent confidence interval",
    "randomised controlled trials and systematic reviews",
    "randomized controlled trials and systematic reviews",
    "evidence based practice",
    "centers for disease control and prevention",
    "world health organization",
    "agency for healthcare research and quality",
    "joanna briggs institute",
    "preferred reporting items for systematic reviews and meta analyses",
]


@dataclass
class OverlapMatch:
    """One run of text the draft shares verbatim with a cited source."""

    phrase: str
    word_count: int
    work_key: str
    work_label: str
    in_marked_quote: bool
    claim_id: str = ""
    section: str = ""

    @property
    def severity(self) -> str:
        """A marked quotation is fine; unmarked overlap is not.

        Length matters because a 20-word unmarked run is a paragraph someone
        pasted, while a 9-word run is more often a phrase that needs rewording.
        """
        if self.in_marked_quote:
            return "ok-quoted"
        if self.word_count >= 20:
            return "serious"
        if self.word_count >= 12:
            return "review"
        return "minor"


@dataclass
class IntegrityReport:
    overlaps: list[OverlapMatch] = field(default_factory=list)
    uncited_claims: list[Claim] = field(default_factory=list)
    quotes_missing_locator: list[Claim] = field(default_factory=list)
    long_quotes_not_blocked: list[Claim] = field(default_factory=list)
    orphan_citations: list[str] = field(default_factory=list)
    unused_references: list[str] = field(default_factory=list)
    retracted_cited: list[Work] = field(default_factory=list)
    below_level_cited: list[Work] = field(default_factory=list)
    external_scan: dict[str, str] = field(default_factory=dict)
    words_checked: int = 0
    sources_checked: int = 0

    def summary(self) -> str:
        """A plain-language summary that never states a similarity percentage."""
        serious = [o for o in self.overlaps if o.severity == "serious"]
        review = [o for o in self.overlaps if o.severity == "review"]
        blockers = self.blocking_count()
        lines = [
            f"Checked {self.words_checked:,} words of draft against "
            f"{self.sources_checked} cited source(s).",
        ]
        if serious:
            lines.append(
                f"{len(serious)} passage(s) of 20+ words match a source verbatim "
                f"and are not marked as quotations. Reword or quote these."
            )
        if review:
            lines.append(
                f"{len(review)} passage(s) of 12–19 words match a source and "
                f"should be reworded or quoted."
            )
        if not serious and not review:
            lines.append(
                "No unmarked verbatim passage of 12 words or more was found "
                "against the cited sources."
            )
        lines.append(
            f"{blockers} citation defect(s) would block export."
            if blockers else "No citation defects block export."
        )
        lines.append(
            "This is an overlap report against your own cited sources, not a "
            "similarity percentage. A correct APA paper always shows some "
            "similarity — its reference list, its quotations and the standard "
            "phrasing of the field all match other documents by design."
        )
        return " ".join(lines)

    def blocking_count(self) -> int:
        return (
            len(self.uncited_claims)
            + len(self.quotes_missing_locator)
            + len(self.orphan_citations)
            + len(self.retracted_cited)
        )


# ------------------------------------------------------------- normalisation


def normalise(text: str) -> list[str]:
    """Lowercase, strip accents and punctuation, split into words.

    Matching happens on words rather than characters so that a changed comma or
    a smart quote does not hide an otherwise verbatim passage — which is exactly
    what naive string matching misses.
    """
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    cleaned = re.sub(r"[^a-z0-9\s]+", " ", stripped.lower())
    return cleaned.split()


def shingles(words: list[str], size: int) -> dict[str, int]:
    """Every window of `size` consecutive words, mapped to its start index."""
    out: dict[str, int] = {}
    for index in range(len(words) - size + 1):
        out.setdefault(" ".join(words[index:index + size]), index)
    return out


def _is_conventional(phrase: str) -> bool:
    """True when the whole matched run is standard academic phrasing."""
    lowered = " ".join(phrase.split())
    return any(lowered in known or known in lowered for known in _CONVENTIONAL_PHRASES)


def _quoted_spans(text: str) -> list[tuple[int, int]]:
    """Word-index ranges that sit inside quotation marks in the draft.

    Overlap inside a properly marked quotation is correct APA, so it must be
    reported differently from the same words unmarked.
    """
    spans: list[tuple[int, int]] = []
    words = text.split()
    depth_start: int | None = None
    for index, word in enumerate(words):
        if depth_start is None and re.match(r'^[“"]', word):
            depth_start = index
        if depth_start is not None and re.search(r'[”"][.,;:]?$', word):
            spans.append((depth_start, index))
            depth_start = None
    if depth_start is not None:
        spans.append((depth_start, len(words) - 1))
    return spans


# ---------------------------------------------------------- verbatim overlap


def find_overlaps(
    draft_text: str,
    sources: list[Work],
    *,
    shingle: int = DEFAULT_SHINGLE,
    claim_id: str = "",
    section: str = "",
) -> list[OverlapMatch]:
    """Find runs the draft shares verbatim with any cited source's own text.

    Only text the tool legitimately holds is compared — the titles and abstracts
    it retrieved, plus any passage the user recorded as a quote in the claim
    ledger. It does not, and should not, hold full article PDFs for this.
    """
    draft_words = normalise(draft_text)
    if len(draft_words) < shingle:
        return []
    draft_shingles = shingles(draft_words, shingle)
    quoted = _quoted_spans(draft_text)

    matches: list[OverlapMatch] = []
    for work in sources:
        source_text = " ".join(filter(None, [work.title, work.abstract]))
        source_words = normalise(source_text)
        if len(source_words) < shingle:
            continue
        source_shingles = set(shingles(source_words, shingle))

        hits = sorted(
            (draft_shingles[s], s) for s in draft_shingles.keys() & source_shingles
        )
        if not hits:
            continue

        # Merge adjacent and overlapping windows into one reported run, so a
        # 30-word lifted sentence is one finding rather than 23.
        for start, end in _merge_windows([h[0] for h in hits], shingle):
            phrase = " ".join(draft_words[start:end])
            if _is_conventional(phrase):
                continue
            matches.append(OverlapMatch(
                phrase=phrase,
                word_count=end - start,
                work_key=work.key,
                work_label=_label(work),
                in_marked_quote=_inside(start, end, quoted),
                claim_id=claim_id,
                section=section,
            ))
    matches.sort(key=lambda m: (-m.word_count, m.work_label))
    return matches


def _merge_windows(starts: list[int], size: int) -> list[tuple[int, int]]:
    if not starts:
        return []
    merged: list[tuple[int, int]] = []
    current_start, current_end = starts[0], starts[0] + size
    for start in starts[1:]:
        if start <= current_end:
            current_end = max(current_end, start + size)
        else:
            merged.append((current_start, current_end))
            current_start, current_end = start, start + size
    merged.append((current_start, current_end))
    return merged


def _inside(start: int, end: int, spans: list[tuple[int, int]]) -> bool:
    return any(s <= start and end - 1 <= e for s, e in spans)


def _label(work: Work) -> str:
    surname = work.first_author_surname() or "Unknown"
    return f"{surname} ({work.year or 'n.d.'})"


# ------------------------------------------------------------- claim auditing


def audit_claims(project: Project) -> IntegrityReport:
    """Check the claim ledger for the defects that make a paper indefensible."""
    report = IntegrityReport()
    by_key = {w.key: w for w in project.works}

    cited_keys: set[str] = set()
    for claim in project.claims:
        if not claim.is_supported():
            report.uncited_claims.append(claim)
        if claim.needs_locator():
            report.quotes_missing_locator.append(claim)
        if claim.support_type is SupportType.DIRECT_QUOTE and \
                len(claim.text.split()) >= 40 and not claim.text.startswith("\n"):
            # APA 7 §8.27: 40+ words must be a block quotation, which the
            # renderer produces from a marker the drafting layer sets.
            report.long_quotes_not_blocked.append(claim)
        for key in claim.work_keys:
            cited_keys.add(key)
            if key not in by_key:
                report.orphan_citations.append(key)

    # APA 7 §8.1: in-text citations and reference entries must correspond
    # exactly. An unused reference is padding; an orphan citation is a broken
    # trail.
    report.unused_references = [
        w.key for w in project.works
        if w.included and w.key not in cited_keys
    ]

    for key in cited_keys:
        work = by_key.get(key)
        if work is None:
            continue
        if work.retracted:
            report.retracted_cited.append(work)
        if work.level.value in ("not-evidence",):
            report.below_level_cited.append(work)

    report.sources_checked = len(cited_keys)
    return report


def check_project(
    project: Project,
    *,
    shingle: int = DEFAULT_SHINGLE,
    external: dict[str, str] | None = None,
) -> IntegrityReport:
    """The full integrity pass over a project."""
    report = audit_claims(project)
    by_key = {w.key: w for w in project.works}

    total_words = 0
    for claim in project.claims:
        total_words += len(claim.text.split())
        sources = [by_key[k] for k in claim.work_keys if k in by_key]
        # A claim is compared against the sources it cites *and* against every
        # other cited source, because text lifted from paper A and attributed to
        # paper B is still lifted text.
        others = [w for w in project.cited_works() if w.key not in claim.work_keys]
        report.overlaps.extend(find_overlaps(
            claim.text, sources + others, shingle=shingle,
            claim_id=claim.claim_id, section=claim.section,
        ))
    report.words_checked = total_words
    report.external_scan = dict(external or {})
    return report


# ------------------------------------------------------------------- blockers


def export_blockers(project: Project) -> list[str]:
    """Defects that stop an export, in the user's terms.

    Deliberately short. Everything here is unambiguously wrong in an APA paper —
    no stylistic opinions, and no similarity threshold, because there is no
    defensible number to threshold on.
    """
    report = audit_claims(project)
    problems: list[str] = []

    for claim in report.uncited_claims:
        problems.append(
            f"{claim.section or 'Body'}: a claim asserts something borrowed but "
            f"names no source — “{_snippet(claim.text)}”"
        )
    for claim in report.quotes_missing_locator:
        problems.append(
            f"{claim.section or 'Body'}: a direct quotation has no page or "
            f"paragraph number, which APA 7 §8.13 requires — "
            f"“{_snippet(claim.text)}”"
        )
    for key in sorted(set(report.orphan_citations)):
        problems.append(
            f"A claim cites source {key}, which is not in the project's source "
            f"list. The reference list cannot be built from it."
        )
    for work in report.retracted_cited:
        problems.append(
            f"The paper cites a retracted source: {_label(work)} — "
            f"{work.retraction_note or 'retraction recorded'}. Remove it or, if "
            f"you are discussing the retraction itself, mark the claim as "
            f"deliberate."
        )
    return problems


def export_warnings(project: Project) -> list[str]:
    """Things worth fixing that do not block an export."""
    report = audit_claims(project)
    warnings: list[str] = []
    for key in report.unused_references:
        work = next((w for w in project.works if w.key == key), None)
        if work:
            warnings.append(
                f"{_label(work)} is in the source list but no claim cites it. "
                f"APA 7 §8.1 requires the reference list to match the in-text "
                f"citations, so it will not be printed."
            )
    for claim in report.long_quotes_not_blocked:
        warnings.append(
            f"{claim.section or 'Body'}: a quotation of {len(claim.text.split())} "
            f"words must be set as a block quotation without quotation marks "
            f"(APA 7 §8.27)."
        )
    for work in report.below_level_cited:
        warnings.append(
            f"{_label(work)} is classified as not evidence-based "
            f"({work.level_reason}). Citing it is a judgement call you should be "
            f"able to defend."
        )
    return warnings


def _snippet(text: str, words: int = 12) -> str:
    parts = text.split()
    return " ".join(parts[:words]) + ("…" if len(parts) > words else "")


# ------------------------------------------------- optional external scanning


EXTERNAL_SCANNERS = {
    "copyleaks": {
        "label": "Copyleaks",
        "note": ("Sells API access to individuals. Returns a similarity index "
                 "with matched sources."),
        "docs": "https://api.copyleaks.com/documentation",
    },
    "plagiarismcheck": {
        "label": "PlagiarismCheck.org",
        "note": "Individual API plans available.",
        "docs": "https://plagiarismcheck.org/for-developers/",
    },
    "turnitin": {
        "label": "Turnitin / iThenticate",
        "note": ("Institutional licensing only — an individual cannot buy API "
                 "access. If your programme uses Turnitin, submit through your "
                 "institution's assignment portal; that submission is also the "
                 "one your faculty will see."),
        "docs": "https://developers.turnitin.com/",
    },
}


def external_scan_guidance(configured: list[str]) -> dict[str, str]:
    """Report what external scanning is available, and be straight about it."""
    if configured:
        return {
            "status": "configured",
            "providers": ", ".join(
                EXTERNAL_SCANNERS.get(c, {}).get("label", c) for c in configured
            ),
            "interpretation": (
                "The provider returns a similarity index. Read it, do not gate "
                "on it: quotations, reference lists and standard field phrasing "
                "all contribute legitimately. Investigate the matched passages, "
                "not the number."
            ),
        }
    return {
        "status": "not-configured",
        "providers": "none",
        "interpretation": (
            "No external similarity provider is configured, so no web-wide scan "
            "was run. The overlap report above compares your draft against the "
            "sources you cited, which is the check that catches accidental "
            "borrowing from your own reading. For a submission that will be run "
            "through Turnitin, note that your institution's portal is the only "
            "way to see the report your faculty will see — Turnitin does not "
            "sell API access to individuals."
        ),
    }
