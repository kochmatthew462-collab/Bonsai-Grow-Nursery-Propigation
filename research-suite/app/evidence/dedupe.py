"""
Deduplication across databases.

Searching PubMed, Europe PMC and a CINAHL export for the same question returns
the same trials three times. A matrix that lists one study three times
overstates the evidence base, so this runs before anything is counted.

Matching happens in three passes, strongest identifier first:

1. **DOI**, normalised and lowercased (DOIs are case-insensitive by spec, and
   the same article arrives as `10.1001/JAMA...` and `https://doi.org/10.1001/jama...`).
2. **PMID / PMCID**, exact.
3. **Normalised title plus year**, with a first-author surname check. This is
   the pass that catches the same trial indexed under different accession
   numbers with no shared DOI — the common case for CINAHL and Embase records.

Merging keeps the *richest* field from each duplicate rather than the first one
seen, and records every contributing database in `raw["merged_from"]`, so the
audit document can state that a record was confirmed in more than one index —
which is a strength, not something to hide.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import fields as dataclass_fields

from ..models import Work, normalise_doi

# Below this Jaccard similarity on title word sets, two records with the same
# year are treated as different studies. Set from the shape of real collisions:
# high enough that "Effect of X on Y in adults" and "Effect of X on Y in
# children" stay separate, low enough that a subtitle or a trailing
# "a randomised controlled trial" does not split a pair.
TITLE_SIMILARITY_FLOOR = 0.82

# Words carried by so many biomedical titles that they say nothing about
# whether two records are the same study.
_STOPWORDS = {
    "a", "an", "and", "the", "of", "in", "on", "for", "with", "to", "from",
    "study", "trial", "randomized", "randomised", "controlled", "effects",
    "effect", "among", "using", "versus", "vs", "between", "association",
    "systematic", "review", "analysis", "patients", "adults", "care",
}


def normalise_title(title: str) -> str:
    decomposed = unicodedata.normalize("NFKD", title)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^a-z0-9 ]+", " ", stripped.lower()).split())


def title_tokens(title: str) -> set[str]:
    return {w for w in normalise_title(title).split() if w not in _STOPWORDS and len(w) > 2}


def similarity(left: str, right: str) -> float:
    """Jaccard similarity of significant title words."""
    a, b = title_tokens(left), title_tokens(right)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def same_work(left: Work, right: Work) -> tuple[bool, str]:
    """Decide whether two records describe the same study, and say why."""
    left_doi, right_doi = normalise_doi(left.doi), normalise_doi(right.doi)
    if left_doi and right_doi:
        # Two records that both carry a DOI and disagree are different studies,
        # full stop — no title fallback, or an erratum merges into its article.
        return (left_doi == right_doi, "DOI" if left_doi == right_doi else "")

    if left.pmid and right.pmid:
        return (left.pmid.strip() == right.pmid.strip(), "PMID")
    if left.pmcid and right.pmcid:
        return (left.pmcid.strip().upper() == right.pmcid.strip().upper(), "PMCID")

    left_year, right_year = left.year[:4], right.year[:4]
    if left_year and right_year and left_year != right_year:
        # Allow one year of drift for the ahead-of-print/issue gap, which
        # routinely differs between indexes for the same article.
        try:
            if abs(int(left_year) - int(right_year)) > 1:
                return (False, "")
        except ValueError:
            return (False, "")

    score = similarity(left.title, right.title)
    if score < TITLE_SIMILARITY_FLOOR:
        return (False, "")

    left_surname = left.first_author_surname().lower()
    right_surname = right.first_author_surname().lower()
    if left_surname and right_surname and left_surname != right_surname:
        # Same title and year but different first authors is far more often two
        # papers in a series than one paper indexed twice.
        return (False, "")

    return (True, f"title similarity {score:.2f} with matching year")


def merge(primary: Work, other: Work) -> Work:
    """Fold `other` into `primary`, preferring whichever value is richer.

    "Richer" means present over absent, and longer over shorter for free text —
    abstracts in particular are frequently truncated in one index and complete
    in another.
    """
    scalar_fields = [
        f.name for f in dataclass_fields(Work)
        if f.name not in {"key", "raw", "authors", "editors", "publication_types",
                          "mesh_terms", "level", "level_reason", "work_type",
                          "included", "screen_reason", "source_db", "retracted",
                          "retraction_note", "peer_reviewed"}
    ]
    for name in scalar_fields:
        mine, theirs = getattr(primary, name), getattr(other, name)
        if not isinstance(mine, str) or not isinstance(theirs, str):
            continue
        if not mine.strip() and theirs.strip():
            setattr(primary, name, theirs)
        elif name in ("abstract", "title") and len(theirs) > len(mine) * 1.15:
            setattr(primary, name, theirs)

    if len(other.authors) > len(primary.authors):
        primary.authors = other.authors
    if len(other.editors) > len(primary.editors):
        primary.editors = other.editors

    for name in ("publication_types", "mesh_terms"):
        combined = list(getattr(primary, name))
        seen = {v.lower() for v in combined}
        for value in getattr(other, name):
            if value.lower() not in seen:
                combined.append(value)
                seen.add(value.lower())
        setattr(primary, name, combined)

    # A retraction found in any index applies to the article everywhere.
    if other.retracted and not primary.retracted:
        primary.retracted = True
        primary.retraction_note = other.retraction_note or primary.retraction_note
    if other.peer_reviewed and primary.peer_reviewed is None:
        primary.peer_reviewed = other.peer_reviewed

    sources = primary.raw.get("merged_from") or [primary.source_db]
    if other.source_db and other.source_db not in sources:
        sources.append(other.source_db)
    primary.raw["merged_from"] = [s for s in sources if s]
    for key, value in other.raw.items():
        if key not in primary.raw:
            primary.raw[key] = value

    primary.ensure_key()
    return primary


def deduplicate(works: list[Work]) -> tuple[list[Work], list[dict[str, str]]]:
    """Collapse duplicates.

    Returns the unique records and a log of every merge, which the audit
    document prints so the PRISMA "duplicates removed" figure is auditable
    rather than asserted.
    """
    unique: list[Work] = []
    log: list[dict[str, str]] = []

    for candidate in works:
        candidate.ensure_key()
        for existing in unique:
            matched, reason = same_work(existing, candidate)
            if matched:
                log.append({
                    "kept": existing.key,
                    "kept_title": existing.title[:120],
                    "removed": candidate.key,
                    "removed_source": candidate.source_db,
                    "matched_on": reason,
                })
                merge(existing, candidate)
                break
        else:
            unique.append(candidate)

    return unique, log


def prisma_counts(
    retrieved: int,
    after_dedupe: int,
    screened_out: int,
    excluded_by_level: int,
    included: int,
) -> dict[str, int]:
    """The five figures a PRISMA 2020 flow diagram needs.

    PRISMA is referenced by name and cited in the audit document; the checklist
    and diagram themselves are the property of the PRISMA group and are not
    reproduced. These are the counts a user needs to fill in the official
    diagram themselves.
    """
    return {
        "records_identified": retrieved,
        "duplicates_removed": max(0, retrieved - after_dedupe),
        "records_screened": after_dedupe,
        "records_excluded_at_screening": screened_out,
        "records_excluded_below_level_threshold": excluded_by_level,
        "studies_included": included,
    }
