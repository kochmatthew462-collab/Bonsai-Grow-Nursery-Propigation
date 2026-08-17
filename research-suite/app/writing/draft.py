"""
Drafting, as a claim ledger rather than as prose.

**The central design decision.** The model is never asked to "write a section
with citations". It is asked to produce a list of *claims*, each one a single
sentence bound to the sources that support it, the locus within them, the
passage relied on, and why that source was chosen. Prose is then assembled from
the ledger by `assemble.py`, which inserts the APA citations mechanically.

That ordering is what makes the rest of the tool possible:

* **The audit document is a byproduct, not a reconstruction.** Every sentence
  already knows its source and locus, so the companion document is a
  transcription of the ledger rather than a second guess at what supported what.
* **Unsupported sentences cannot hide.** A claim with no `work_keys` is a
  visible, blockable defect. In the other ordering — prose first, citations
  found afterwards — an unsupported assertion is indistinguishable from a
  supported one until a human reads both closely.
* **Citations cannot be fabricated.** The model may only reference keys from the
  evidence block it was given, and any key it invents is dropped and reported.
  This is the failure mode that matters most: a plausible-looking citation to a
  paper that does not exist.

The model sees only the evidence the user retrieved and screened. It is not
asked to recall literature, which is the other way fabricated references get in.

Requires an Anthropic API key. Everything else in the suite — retrieval,
appraisal, matrices, APA formatting, both documents — works without one; only
the drafting step needs it.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from ..models import Claim, Project, StyleProfile, SupportType, Work
from . import style as style_module

MODEL = "claude-opus-5"
MAX_TOKENS = 32_000

CLAIM_SCHEMA = {
    "type": "object",
    "properties": {
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": (
                            "One sentence of the paper, in the author's voice. No "
                            "citation markers — those are inserted afterwards."
                        ),
                    },
                    "support_type": {
                        "type": "string",
                        "enum": ["paraphrase", "direct-quote", "data-point",
                                 "no-citation"],
                    },
                    "work_keys": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Keys of supporting sources, copied exactly from the "
                            "evidence block. Empty only for no-citation."
                        ),
                    },
                    "locus": {
                        "type": "string",
                        "description": (
                            "Where in the source: 'p. 412', 'para. 3', 'Table 2', "
                            "'Abstract, Results'. Required for direct-quote and "
                            "data-point."
                        ),
                    },
                    "source_quote": {
                        "type": "string",
                        "description": (
                            "The passage from the source this claim rests on, "
                            "copied verbatim, for the audit document."
                        ),
                    },
                    "rationale": {
                        "type": "string",
                        "description": (
                            "Why this source supports this claim, in one clause."
                        ),
                    },
                },
                "required": ["text", "support_type", "work_keys", "locus",
                             "source_quote", "rationale"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["claims"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = """\
You draft sections of evidence-based health-sciences papers as a claim ledger.

You produce a list of claims. Each claim is ONE sentence of the finished paper,
bound to the evidence that supports it. You never write a formatted citation
into the sentence text — those are inserted mechanically afterwards from the keys
you supply, so that they are always correctly formatted and always match the
reference list.

You control WHERE each citation lands, using two placeholders:

- `[[NARRATIVE]]` at the very start of `text` produces a narrative citation:
  "Aiken et al. (2014) reported that each additional patient per nurse…". Write
  the rest of the sentence to follow that opening, starting with the verb —
  `[[NARRATIVE]] reported that each additional patient per nurse raised…`.
- `[[CITE]]` anywhere in `text` puts the parenthetical citation at that point,
  which is what you want when the citation belongs mid-sentence.
- With neither placeholder, the parenthetical citation goes before the final
  full stop, which is the default position.

Vary between narrative and parenthetical the way a person writing well does.
Use narrative form when the study or its authors are the subject of the
sentence, or when you are contrasting two studies; use parenthetical when the
finding is the subject. A section in which every citation is parenthetical and
sits at the end of the sentence reads mechanically — do not produce that.

Rules that are not negotiable:

1. Use ONLY the sources in the evidence block. Do not draw on anything you
   recall from training. If the evidence does not support a point, do not make
   the point.
2. Every `work_keys` entry must be copied exactly from a KEY line in the
   evidence block. Never construct, guess or adapt a key. A key that is not in
   the block is a fabricated citation.
3. Every substantive claim about the literature, about findings, about numbers,
   or about what other authors concluded needs at least one source. Use
   `no-citation` only for the author's own transitions, framing sentences and
   analytical statements that assert nothing borrowed.
4. Do not copy source wording into `text`. Synthesise in the author's own words.
   If a phrase genuinely must be verbatim, set `support_type` to `direct-quote`,
   put the exact words in `text` wrapped in double quotation marks, and give the
   page or paragraph in `locus`.
5. `source_quote` is for the audit trail: the passage from the source that you
   relied on, copied exactly. It is never printed in the paper.
6. Report what the evidence says, including where it is weak, mixed or limited.
   Do not smooth over inconsistency between studies — the inconsistency is a
   finding. When studies disagree, say so and say how.
7. Respect each source's level of evidence and appraisal rating. Do not lean a
   strong claim on a Level IV descriptive study, and do not present a single
   study's result as established.
8. Never assert causation from a cross-sectional or correlational design.

Write in the author's measured style, given below. Match the shape of their
sentences, not a generic academic register."""


@dataclass
class DraftResult:
    claims: list[Claim] = field(default_factory=list)
    dropped_keys: list[str] = field(default_factory=list)
    unsupported: list[str] = field(default_factory=list)
    usage: dict[str, int] = field(default_factory=dict)
    model: str = MODEL
    notes: list[str] = field(default_factory=list)


@dataclass
class Section:
    """One section to draft."""

    heading: str
    level: int = 1
    instruction: str = ""
    target_words: int = 400
    work_keys: list[str] = field(default_factory=list)


def default_sections(project: Project) -> list[Section]:
    """A conventional structure for an evidence review.

    Deliberately editable — a DNP practice-change project, a scoping review and
    a course paper want different shapes, and the tool should not pretend
    otherwise.
    """
    question = project.question or project.topic
    return [
        Section("Introduction", 1, target_words=450, instruction=(
            f"Establish why {question} matters, state the scope of the problem "
            f"with figures from the evidence, and end with the question this "
            f"paper addresses. Do not preview conclusions.")),
        Section("Review of the Literature", 1, target_words=1200, instruction=(
            "Synthesise the included studies by theme, not one study per "
            "paragraph. Group findings that agree, and treat disagreement "
            "between studies as a finding to explain rather than a problem to "
            "hide. Weight claims by level of evidence and appraisal rating.")),
        Section("Methodological Quality of the Evidence", 2, target_words=450,
                instruction=(
                    "Describe the strength and limitations of the evidence base "
                    "as a whole: which designs dominate, what the appraisals "
                    "found, where the gaps are. Reference specific studies for "
                    "each characterisation.")),
        Section("Discussion", 1, target_words=700, instruction=(
            "Interpret what the evidence supports and what it does not. Be "
            "explicit about the limits of inference the designs allow. "
            "Analytical sentences that are the author's own reasoning should be "
            "marked no-citation; anything resting on a study must cite it.")),
        Section("Implications for Practice", 2, target_words=450, instruction=(
            "State what follows for practice, tied to the strength of the "
            "supporting evidence. Do not recommend more firmly than the "
            "evidence allows.")),
        Section("Limitations", 2, target_words=250, instruction=(
            "The limitations of this review — search scope, databases reachable, "
            "level thresholds applied, languages, date range.")),
        Section("Conclusion", 1, target_words=250, instruction=(
            "What the evidence establishes, in the author's own words. No new "
            "citations, and no restatement of the introduction.")),
    ]


class Drafter:
    """Drafts claim ledgers with Claude."""

    def __init__(self, api_key: str = "", model: str = MODEL):
        self.model = model
        self._api_key = api_key
        self._client = None

    def available(self) -> bool:
        try:
            import anthropic  # noqa: F401
        except ImportError:
            return False
        return bool(self._api_key)

    def _get_client(self):
        if self._client is None:
            import anthropic
            self._client = anthropic.Anthropic(api_key=self._api_key or None)
        return self._client

    # ------------------------------------------------------------- prompting

    def evidence_block(self, works: list[Work], project: Project) -> str:
        """The stable prefix: every source the drafter may cite.

        Built identically on every call for a given project so it can sit behind
        a prompt-cache breakpoint — the section instruction is what varies, and
        it goes after.
        """
        by_key = {a.work_key: a for a in project.appraisals}
        extractions = {e.work_key: e for e in project.extractions}

        lines = ["# Evidence available", ""]
        for work in works:
            appraisal = by_key.get(work.key)
            extraction = extractions.get(work.key)
            authors = ", ".join(a.reference_name() for a in work.authors[:4])
            if len(work.authors) > 4:
                authors += ", et al."
            lines += [
                f"KEY: {work.key}",
                f"  Citation: {authors} ({work.year or 'n.d.'}). {work.title}. "
                f"{work.container}.",
                f"  Level of evidence: {work.level.value} — {work.level.label}",
                f"  Level rationale: {work.level_reason}",
                f"  Source database: {work.source_db}",
            ]
            if work.doi:
                lines.append(f"  DOI: {work.doi}")
            if appraisal:
                yes, total = appraisal.score()
                lines.append(
                    f"  Appraisal: {appraisal.overall or 'not rated'} "
                    f"({yes}/{total} criteria met, following {appraisal.instrument})"
                )
                if appraisal.limitations:
                    lines.append(f"  Appraisal limitations: {appraisal.limitations}")
            if extraction:
                for label, value in (
                    ("Design", extraction.design), ("Setting", extraction.setting),
                    ("Sample", f"{extraction.sample_description} "
                               f"(n = {extraction.sample_size})".strip()),
                    ("Key findings", extraction.key_findings),
                    ("Statistics", extraction.statistics),
                    ("Limitations", extraction.limitations),
                ):
                    if value and value.strip():
                        lines.append(f"  {label}: {value.strip()}")
            if work.abstract:
                lines.append(f"  Abstract: {work.abstract[:1800]}")
            lines.append("")
        return "\n".join(lines)

    def _project_brief(self, project: Project) -> str:
        pico = "; ".join(f"{k}: {v}" for k, v in project.pico.items() if v)
        lines = [
            "# Paper",
            f"Topic: {project.topic}",
            f"Question: {project.question or project.topic}",
            f"Academic level: {project.academic_level}",
        ]
        if pico:
            lines.append(f"PICO: {pico}")
        if project.inclusion:
            lines.append(f"Inclusion criteria: {'; '.join(project.inclusion)}")
        if project.exclusion:
            lines.append(f"Exclusion criteria: {'; '.join(project.exclusion)}")
        lines.append(f"Minimum level of evidence accepted: {project.min_level}")
        return "\n".join(lines)

    # --------------------------------------------------------------- drafting

    def draft_section(
        self,
        project: Project,
        section: Section,
        samples: list[str] | None = None,
    ) -> DraftResult:
        """Draft one section as a claim ledger."""
        result = DraftResult(model=self.model)
        if not self.available():
            result.notes.append(
                "No Anthropic API key is configured, so no draft was generated. "
                "Everything else — retrieval, appraisal, the evidence matrix, "
                "APA formatting and both documents — works without one. Add a "
                "key on the Settings page to enable drafting, or write the "
                "claims yourself in the Claims editor."
            )
            return result

        allowed = self._sources_for(project, section)
        if not allowed:
            result.notes.append(
                "No included sources are available for this section, so there is "
                "nothing to draft from. Run a search and screen some sources "
                "first."
            )
            return result

        valid_keys = {w.key for w in allowed}
        evidence = self.evidence_block(allowed, project)
        brief = self._project_brief(project)
        style_text = style_module.style_brief(project.style, samples)

        instruction = (
            f"# Section to draft\n"
            f"Heading: {section.heading}\n"
            f"Approximate length: {section.target_words} words "
            f"({max(6, section.target_words // 22)}–"
            f"{max(10, section.target_words // 14)} claims)\n\n"
            f"{section.instruction}\n\n"
            f"Produce the claim ledger for this section now. Copy each work key "
            f"exactly from a KEY line above."
        )

        client = self._get_client()
        # The evidence block and style brief are stable across sections for a
        # given project, so the cache breakpoint goes after them and the
        # per-section instruction after that.
        response = client.messages.create(
            model=self.model,
            max_tokens=MAX_TOKENS,
            system=[
                {"type": "text", "text": SYSTEM_PROMPT},
                {"type": "text", "text": f"{brief}\n\n# Author's style\n{style_text}"},
                {"type": "text", "text": evidence,
                 "cache_control": {"type": "ephemeral"}},
            ],
            thinking={"type": "adaptive"},
            output_config={
                "effort": "high",
                "format": {"type": "json_schema", "schema": CLAIM_SCHEMA},
            },
            messages=[{"role": "user", "content": instruction}],
        )

        result.usage = {
            "input_tokens": getattr(response.usage, "input_tokens", 0),
            "output_tokens": getattr(response.usage, "output_tokens", 0),
            "cache_read_input_tokens": getattr(
                response.usage, "cache_read_input_tokens", 0),
            "cache_creation_input_tokens": getattr(
                response.usage, "cache_creation_input_tokens", 0),
        }

        # A refusal returns HTTP 200 with an empty or partial content list, so
        # stop_reason must be checked before content is read.
        if getattr(response, "stop_reason", "") == "refusal":
            details = getattr(response, "stop_details", None)
            result.notes.append(
                "The model declined this request"
                + (f" ({details.category})" if details and getattr(details, "category", None)
                   else "")
                + ". Nothing was drafted. Rephrase the section instruction, or "
                  "write the claims by hand."
            )
            return result

        payload = self._extract_json(response)
        if payload is None:
            result.notes.append(
                "The model's response could not be read as a claim ledger. "
                "Nothing was written to the project."
            )
            return result

        result.claims, result.dropped_keys, result.unsupported = self._to_claims(
            payload.get("claims", []), section, valid_keys, len(project.claims)
        )
        if result.dropped_keys:
            result.notes.append(
                f"{len(result.dropped_keys)} citation(s) referenced a source key "
                f"that is not in this project and were removed: "
                f"{', '.join(sorted(set(result.dropped_keys))[:5])}. The claims "
                f"that relied on them are marked as needing a source."
            )
        if result.unsupported:
            result.notes.append(
                f"{len(result.unsupported)} claim(s) assert something borrowed but "
                f"name no source. They are flagged and will block export until "
                f"you attach a source or mark them as your own analysis."
            )
        return result

    def _sources_for(self, project: Project, section: Section) -> list[Work]:
        from ..evidence import levels as levels_module

        works = [
            w for w in project.included_works()
            if levels_module.meets_minimum(w, project.min_level)
        ]
        if section.work_keys:
            works = [w for w in works if w.key in section.work_keys]
        # Strongest evidence first, so it leads the context window.
        return sorted(works, key=lambda w: (w.level.rank, w.year), reverse=False)

    @staticmethod
    def _extract_json(response) -> dict | None:
        for block in getattr(response, "content", []) or []:
            if getattr(block, "type", "") != "text":
                continue
            text = getattr(block, "text", "") or ""
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                match = re.search(r"\{.*\}", text, re.DOTALL)
                if match:
                    try:
                        return json.loads(match.group(0))
                    except json.JSONDecodeError:
                        continue
        return None

    @staticmethod
    def _to_claims(
        raw: list[dict], section: Section, valid_keys: set[str], offset: int
    ) -> tuple[list[Claim], list[str], list[str]]:
        claims: list[Claim] = []
        dropped: list[str] = []
        unsupported: list[str] = []

        for index, item in enumerate(raw):
            text = str(item.get("text") or "").strip()
            if not text:
                continue
            try:
                support = SupportType(str(item.get("support_type") or "paraphrase"))
            except ValueError:
                support = SupportType.PARAPHRASE

            keys: list[str] = []
            for key in item.get("work_keys") or []:
                key = str(key).strip()
                if key in valid_keys:
                    if key not in keys:
                        keys.append(key)
                elif key:
                    dropped.append(key)

            claim = Claim(
                claim_id=f"{_slug(section.heading)}-{offset + index + 1:03d}",
                section=section.heading,
                order=offset + index,
                text=text,
                support_type=support,
                work_keys=keys,
                locus=str(item.get("locus") or "").strip(),
                source_quote=str(item.get("source_quote") or "").strip(),
                rationale=str(item.get("rationale") or "").strip(),
                verified=False,
            )
            if not claim.is_supported():
                unsupported.append(claim.claim_id)
            claims.append(claim)
        return (claims, dropped, unsupported)

    # ------------------------------------------------------------ whole paper

    def draft_paper(
        self,
        project: Project,
        sections: list[Section] | None = None,
        samples: list[str] | None = None,
    ) -> DraftResult:
        combined = DraftResult(model=self.model)
        for section in sections or default_sections(project):
            part = self.draft_section(project, section, samples)
            combined.claims.extend(part.claims)
            combined.dropped_keys.extend(part.dropped_keys)
            combined.unsupported.extend(part.unsupported)
            combined.notes.extend(part.notes)
            for name, value in part.usage.items():
                combined.usage[name] = combined.usage.get(name, 0) + value
        return combined

    def draft_abstract(self, project: Project, body_claims: list[Claim]) -> str:
        """An abstract from the drafted body (APA 7 §2.9: 150–250 words).

        Written from the claims rather than from the sources, so it summarises
        the paper that exists rather than the literature in general.
        """
        if not self.available() or not body_claims:
            return ""
        body = "\n".join(f"- {c.text}" for c in body_claims[:120])
        client = self._get_client()
        response = client.messages.create(
            model=self.model,
            max_tokens=2_000,
            system=(
                "Write an APA 7 abstract: a single paragraph of 150 to 250 words, "
                "no citations, no first sentence that merely restates the title. "
                "Cover purpose, the evidence reviewed, principal findings and "
                "implications. Match the author's register. Return the abstract "
                "text only."
            ),
            thinking={"type": "adaptive"},
            output_config={"effort": "medium"},
            messages=[{
                "role": "user",
                "content": (
                    f"Topic: {project.topic}\n"
                    f"Question: {project.question}\n\n"
                    f"The paper makes these claims:\n{body}"
                ),
            }],
        )
        if getattr(response, "stop_reason", "") == "refusal":
            return ""
        return " ".join(
            "".join(
                getattr(b, "text", "") for b in response.content
                if getattr(b, "type", "") == "text"
            ).split()
        )


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:24] or "section"


# ----------------------------------------------------------------- disclosure


def ai_use_disclosure(project: Project, drafted: bool, model: str = MODEL) -> str:
    """A disclosure statement describing how the tool was used.

    Included because most institutions and journals now require it, and because
    the honest version is short and specific. ICMJE holds that an AI tool cannot
    be an author and that its use must be disclosed; COPE takes the same
    position; and university coursework policies vary from "permitted with
    disclosure" to "prohibited". The tool cannot know which applies to any given
    submission, so it produces an accurate statement and leaves the decision
    with the user.

    If drafting was not used, the statement says so — which is a materially
    different and much less restricted claim.
    """
    tools = [
        "Literature searching through the PubMed, Europe PMC, Crossref and "
        "OpenAlex APIs, and by importing citation exports from subscription "
        "databases",
        "Deduplication, level-of-evidence classification and retraction checking",
        "Critical appraisal prompts, evidence-matrix assembly, and APA 7 "
        "formatting of the manuscript and reference list",
    ]
    if drafted:
        tools.append(
            f"Generation of an initial claim-by-claim draft using {model} "
            f"(Anthropic), from the sources the author selected and appraised, "
            f"which the author then reviewed, verified against each source, and "
            f"revised"
        )

    statement = [
        "Disclosure of artificial intelligence use",
        "",
        "The author used Koch Research Suite, a locally run research and "
        "manuscript-preparation tool, in producing this work. Specifically:",
        "",
    ]
    statement += [f"{index}. {item}." for index, item in enumerate(tools, 1)]
    statement += [
        "",
        "The author formulated the research question, set the inclusion and "
        "exclusion criteria, selected and appraised every source, verified each "
        "claim against its cited source, and is responsible for the content and "
        "conclusions. No artificial intelligence tool is listed as an author, in "
        "accordance with ICMJE and COPE positions that authorship requires "
        "accountability an AI system cannot hold.",
    ]
    if drafted:
        statement += [
            "",
            "A companion document, submitted alongside this paper, records every "
            "claim, the source and locus supporting it, and the rationale for "
            "each source's inclusion.",
        ]
    return "\n".join(statement)


def integrity_notice(academic_level: str) -> str:
    """A short, non-preachy note about where drafting assistance may not be
    permitted. Shown once in the UI, not attached to output."""
    base = (
        "Institutional policies on AI-assisted drafting differ widely and change "
        "often. Journals in this field generally permit AI assistance with "
        "disclosure but not AI authorship; university coursework policies range "
        "from permitted-with-disclosure to prohibited. Check the policy that "
        "applies to this specific submission before using the drafting step — "
        "the retrieval, appraisal, matrix and formatting steps raise no such "
        "question."
    )
    if academic_level in ("undergraduate", "graduate"):
        return base + (
            " For coursework in particular, a programme that permits AI for "
            "formatting and citation management may still prohibit AI-generated "
            "prose."
        )
    return base
