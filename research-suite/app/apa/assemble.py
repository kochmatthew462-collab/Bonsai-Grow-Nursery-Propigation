"""
Turning a claim ledger into APA-formatted prose.

The drafting layer produces claims; this puts the citations in. Doing it
mechanically rather than asking the model to write citation markers has one
decisive advantage: a citation can only ever be built from a source that exists
in the project, formatted by the tested citation engine, and guaranteed to match
the reference list. A model writing "(Aiken et al., 2014)" into its own prose can
get the punctuation wrong, the et al. threshold wrong, or the source wrong.

**Citation placement.** A paper where every citation is parenthetical and sits at
the end of every sentence reads mechanically, and APA does not require that. So
the claim text may carry two markers:

* ``[[CITE]]`` — put the parenthetical citation here, mid-sentence.
* ``[[NARRATIVE]]`` — start the sentence with the narrative form,
  ``Aiken et al. (2014) reported that…``.

With no marker, the parenthetical citation goes before the sentence's final
punctuation, which is the default APA position.

**Every claim that names a source gets a citation.** APA 7 §8.1 requires the
source in each sentence where its material is paraphrased. Some writers omit it
in later sentences of an obviously single-source paragraph; that is a judgement
call a reviewer may disagree with, so the tool takes the always-defensible
route and the user can delete any they consider redundant.
"""

from __future__ import annotations

import re

from ..models import Claim, Project, StyleProfile, SupportType, Work
from .citations import CitationContext, Run, format_locator, intext
from .document import BLOCK_QUOTE_MIN_WORDS, Block

CITE_MARKER = "[[CITE]]"
NARRATIVE_MARKER = "[[NARRATIVE]]"

# Heading levels for the section names the default plan produces. A section the
# plan does not know about defaults to Level 1.
DEFAULT_LEVELS = {
    "introduction": 1,
    "review of the literature": 1,
    "literature review": 1,
    "background": 1,
    "methods": 1,
    "search strategy": 2,
    "methodological quality of the evidence": 2,
    "findings": 1,
    "results": 1,
    "discussion": 1,
    "implications for practice": 2,
    "implications": 2,
    "limitations": 2,
    "recommendations": 2,
    "conclusion": 1,
}


def section_level(heading: str) -> int:
    return DEFAULT_LEVELS.get(heading.strip().lower(), 1)


def build_blocks(
    project: Project,
    context: CitationContext,
    *,
    include_headings: bool = True,
) -> list[Block]:
    """Assemble every claim into ordered paper blocks."""
    context.reset_group_state()
    by_key = {w.key: w for w in project.works}
    blocks: list[Block] = []

    for heading, claims in _group_by_section(project.claims):
        if include_headings and heading:
            blocks.append(Block("heading", level=section_level(heading), text=heading))
        blocks.extend(_section_blocks(claims, by_key, context, project.style))
    return blocks


def _group_by_section(claims: list[Claim]) -> list[tuple[str, list[Claim]]]:
    """Preserve the order sections were drafted in, not alphabetical order."""
    grouped: list[tuple[str, list[Claim]]] = []
    for claim in sorted(claims, key=lambda c: c.order):
        if grouped and grouped[-1][0] == claim.section:
            grouped[-1][1].append(claim)
        else:
            grouped.append((claim.section, [claim]))
    return grouped


def _section_blocks(
    claims: list[Claim],
    by_key: dict[str, Work],
    context: CitationContext,
    profile: StyleProfile,
) -> list[Block]:
    blocks: list[Block] = []
    paragraph: list[Run] = []
    # Paragraph length follows the author's own measured habit where one is
    # available, rather than a fixed number.
    target = int(round(profile.mean_paragraph_sentences)) or 4
    target = max(2, min(8, target))
    sentences_in_paragraph = 0

    def flush() -> None:
        nonlocal paragraph, sentences_in_paragraph
        if paragraph:
            blocks.append(Block("paragraph", runs=_tidy_paragraph(paragraph)))
        paragraph = []
        sentences_in_paragraph = 0

    for claim in claims:
        works = [by_key[k] for k in claim.work_keys if k in by_key]

        # A block quotation is its own paragraph either side (APA 7 §8.27).
        if claim.support_type is SupportType.DIRECT_QUOTE and \
                len(claim.text.split()) >= BLOCK_QUOTE_MIN_WORDS:
            flush()
            blocks.append(Block("quote", runs=_block_quote_runs(claim, works, context)))
            continue

        runs = render_claim(claim, works, context)
        if not runs:
            continue
        if paragraph:
            paragraph.append(Run(" "))
        paragraph.extend(runs)
        sentences_in_paragraph += 1
        if sentences_in_paragraph >= target:
            flush()

    flush()
    return blocks


# ------------------------------------------------------------ claim rendering


def render_claim(
    claim: Claim, works: list[Work], context: CitationContext
) -> list[Run]:
    """One claim as styled runs, with its citation in the right place."""
    text = claim.text.strip()
    if not text:
        return []

    if not works:
        # A claim with no source is either the author's own analysis (fine) or a
        # defect (blocked at export). Either way it renders as plain prose.
        return [Run(_strip_markers(text))]

    locator = _locator_for(claim)

    if NARRATIVE_MARKER in text:
        citation = intext(works, context, narrative=True, locator=locator)
        body = _strip_markers(text.replace(NARRATIVE_MARKER, "", 1)).lstrip()
        body = body[0].lower() + body[1:] if body and body[0].isupper() and \
            _starts_with_verb_phrase(body) else body
        return citation + [Run(" " + body if body else "")]

    citation = intext(works, context, narrative=False, locator=locator)

    if CITE_MARKER in text:
        before, _, after = text.partition(CITE_MARKER)
        return (
            [Run(_strip_markers(before))]
            + citation
            + [Run(_strip_markers(after))]
        )

    # An in-line direct quotation punctuates differently from a paraphrase
    # (APA 7 §8.28): the closing quotation mark comes first, then the citation,
    # then the sentence's period — "…predictor" (Griffiths, 2019, p. 412).
    # Leaving the period inside the quotation and adding another after the
    # citation is the usual mistake.
    if claim.support_type is SupportType.DIRECT_QUOTE:
        quoted = _strip_markers(text).strip()
        closing = re.search(r"([”\"'])\s*\.?\s*$", quoted)
        if closing:
            inner = quoted[: closing.start()].rstrip().rstrip(".,")
            return [Run(f"{inner}{closing.group(1)} ")] + citation + [Run(".")]
        return [Run(quoted.rstrip(". ") + " ")] + citation + [Run(".")]

    # Default APA position for a paraphrase: inside the sentence's final
    # punctuation. Both straight and curly closing quotes are matched, because
    # drafts contain a mixture.
    match = re.search(r"([.!?][”\"']?\s*)$", text)
    if match:
        return (
            [Run(_strip_markers(text[: match.start()]) + " ")]
            + citation
            + [Run(match.group(1).rstrip())]
        )
    return [Run(_strip_markers(text) + " ")] + citation + [Run(".")]


def _block_quote_runs(
    claim: Claim, works: list[Work], context: CitationContext
) -> list[Run]:
    """A block quotation: no quotation marks, citation *after* the final
    punctuation (APA 7 §8.27 — the opposite of an in-line quotation)."""
    text = _strip_markers(claim.text).strip().strip("“”\"")
    if not text.endswith((".", "!", "?")):
        text += "."
    runs = [Run(text + " ")]
    if works:
        runs += intext(works, context, locator=_locator_for(claim))
    return runs


def _locator_for(claim: Claim) -> str:
    """Normalise whatever the drafter recorded into an APA locator.

    A direct quotation without one is a defect the integrity pass blocks, so
    this never invents a page number — it formats what is there.
    """
    raw = (claim.locus or "").strip()
    if not raw:
        return ""
    lowered = raw.lower()
    if lowered.startswith(("p.", "pp.", "para.", "section", "table", "figure",
                           "chapter", "slide")):
        return raw
    if re.fullmatch(r"\d+(\s*[-–]\s*\d+)?", raw):
        return format_locator("page", raw)
    if lowered.startswith("page"):
        return format_locator("page", raw.split(None, 1)[-1])
    if lowered.startswith(("paragraph", "par ")):
        return format_locator("paragraph", raw.split(None, 1)[-1])
    # Anything else — "Abstract, Results", "Methods" — is a section reference.
    return raw


def _strip_markers(text: str) -> str:
    return text.replace(CITE_MARKER, "").replace(NARRATIVE_MARKER, "")


def _starts_with_verb_phrase(text: str) -> bool:
    """Whether a narrative citation reads correctly with the sentence lowercased.

    ``[[NARRATIVE]] Reported that staffing…`` should become
    ``Aiken et al. (2014) reported that staffing…``, but
    ``[[NARRATIVE]] Staffing ratios predict falls`` must keep its capital.
    """
    first = re.match(r"([A-Za-z]+)", text)
    if not first:
        return False
    word = first.group(1).lower()
    return word in {
        "reported", "found", "showed", "demonstrated", "concluded", "observed",
        "noted", "argued", "examined", "identified", "described", "measured",
        "compared", "estimated", "suggested", "proposed", "documented",
        "analysed", "analyzed", "reviewed", "surveyed", "tested",
    }


def _tidy_paragraph(runs: list[Run]) -> list[Run]:
    """Merge adjacent same-style runs and normalise spacing."""
    merged: list[Run] = []
    for run in runs:
        if not run.text:
            continue
        if merged and merged[-1].italic == run.italic:
            merged[-1] = Run(merged[-1].text + run.text, run.italic)
        else:
            merged.append(Run(run.text, run.italic))
    for run in merged:
        run.text = re.sub(r"\s{2,}", " ", run.text)
        run.text = re.sub(r"\s+([.,;:)])", r"\1", run.text)
        run.text = run.text.replace("( ", "(")
    if merged:
        merged[0].text = merged[0].text.lstrip()
        merged[-1].text = merged[-1].text.rstrip()
    return [r for r in merged if r.text]


# ----------------------------------------------------------------- keyword aid


def suggest_keywords(project: Project, limit: int = 5) -> list[str]:
    """Keywords for the abstract, drawn from the MeSH terms of the cited sources.

    Using the indexers' own controlled vocabulary rather than words pulled from
    the title is what makes a paper findable, which is the point of the field.
    """
    counts: dict[str, int] = {}
    for work in project.cited_works():
        for term in work.mesh_terms:
            cleaned = term.strip().strip("*")
            if not cleaned or cleaned.lower() in ("humans", "female", "male",
                                                  "adult", "aged", "adolescent",
                                                  "middle aged", "young adult",
                                                  "child", "infant"):
                continue
            counts[cleaned] = counts.get(cleaned, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [term.lower() for term, _ in ranked[:limit]]


def word_count(project: Project) -> int:
    return sum(len(c.text.split()) for c in project.claims)


def section_word_counts(project: Project) -> dict[str, int]:
    counts: dict[str, int] = {}
    for claim in project.claims:
        counts[claim.section] = counts.get(claim.section, 0) + len(claim.text.split())
    return counts
