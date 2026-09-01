"""
Grammar and style checking — and the honest answer about Grammarly.

**Grammarly cannot be integrated, by any supported route.** The request asked for
it specifically, so here is exactly where that stands:

* The **Grammarly Text Editor SDK**, which was the only way to embed Grammarly's
  suggestions in your own application, was **discontinued on 10 January 2024**.
  There is no successor.
* The current developer offerings at `developer.grammarly.com` are
  **Enterprise/Education agreements**, and — this is the part that matters even if
  you had one — they return **scores only**. A Writing Score gives you
  correctness, clarity, engagement and delivery as numbers. It does not return
  the individual suggestions, the character offsets, or the corrected text. You
  cannot build a "fix the grammar" feature on a number.
* Driving the consumer product with a script is prohibited by its terms of
  service.

So a tool that claimed Grammarly integration would be lying. What works instead:

**In the pipeline — self-hosted LanguageTool.** LGPL, runs locally, and its
`/v2/check` endpoint returns real errors with offsets and replacement candidates,
which is precisely what Grammarly's API withholds. Nothing leaves the machine.

**In the pipeline — Vale**, for terminology and house style. It reads Markdown
and is designed for exactly this: enforcing "participants" over "subjects", or a
programme's preferred terms.

**As a final pass — Grammarly itself, by hand.** Export the .docx, open it in
Word with the Grammarly add-in, accept the suggestions you agree with. This is
not a workaround for a missing feature; it is the correct place for a
context-sensitive human-reviewed check, and it keeps a paid tool you may already
have in the loop.

The checker is optional. Without it the suite still exports, and it says so
rather than silently skipping the step.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import httpx

DEFAULT_LANGUAGETOOL_URL = "http://localhost:8081/v2/check"
DEFAULT_LANGUAGE = "en-US"

# Rules to switch off for academic prose. LanguageTool's defaults are tuned for
# general writing and fire constantly on correct APA usage.
DISABLED_RULES = [
    "WHITESPACE_RULE",          # double spaces after a period are an APA choice
    "COMMA_PARENTHESIS_WHITESPACE",  # fires on "(Smith, 2020)." constructions
    "EN_QUOTES",                # straight vs curly quotes is a house decision
    "DASH_RULE",
    "PASSIVE_VOICE",            # the passive is legitimate in methods writing
    "TOO_LONG_SENTENCE",        # long sentences are a style target, not an error
    "SENTENCE_WHITESPACE",
    "UPPERCASE_SENTENCE_START",  # fires on run-in Level 4/5 headings
]

# Spans that must not be corrected: citations, DOIs, URLs, statistics. A checker
# that "fixes" (Smith et al., 2020) or p = .03 into prose is worse than no
# checker, and APA's statistical style deliberately breaks ordinary punctuation
# rules (no leading zero on p, italic test statistics).
# Order matters: the most specific patterns run first, because a general one that
# matches part of a longer construct leaves the remainder exposed. "95% CI [0.62,
# 0.98]" masked by the bare-percentage rule first becomes "XXX CI [0.62, 0.98]",
# with the interval still in the text for the checker to complain about.
_PROTECTED = [
    r"\([^()]*\b(?:19|20)\d{2}[a-z]?\b[^()]*\)",       # in-text citations
    r"https?://\S+",
    r"\b10\.\d{4,9}/\S+",                              # DOIs
    # A confidence interval in either notation. The bounds have to be consumed
    # explicitly rather than with a "everything up to punctuation" pattern,
    # because the decimal point in 0.88 *is* punctuation and would end the match
    # halfway through, leaving the upper bound exposed.
    r"\b\d+%\s*CI[s]?\s*\[[^\]]*\]",                   # 95% CI [0.62, 0.98]
    r"\b\d+%\s*CI[s]?\s*[-−\d.]+\s*(?:to|[-–,])\s*[-−\d.]+",  # 95% CI 0.88 to 0.98
    r"\b[a-zA-Z]{1,3}\s*[=<>≤≥]\s*[-−]?[\d,]+(?:\.\d+)?",  # n = 1,204; p = .03
    r"\b[a-zA-Z]{1,3}\s*[=<>≤≥]\s*[-−]?\.\d+",         # p = .03 (no leading zero)
    r"\b\d+(?:\.\d+)?%",                               # a bare percentage, last
]


@dataclass
class ProofIssue:
    message: str
    context: str
    offset: int
    length: int
    replacements: list[str] = field(default_factory=list)
    rule: str = ""
    category: str = ""
    claim_id: str = ""
    section: str = ""


@dataclass
class ProofReport:
    issues: list[ProofIssue] = field(default_factory=list)
    checked_words: int = 0
    available: bool = False
    engine: str = ""
    note: str = ""

    def by_category(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for issue in self.issues:
            counts[issue.category or "other"] = counts.get(issue.category or "other", 0) + 1
        return dict(sorted(counts.items(), key=lambda kv: -kv[1]))


GRAMMARLY_STATUS = {
    "integrable": False,
    "summary": (
        "Grammarly cannot be integrated into this or any third-party tool. The "
        "Text Editor SDK — the only embedding route — was discontinued on 10 "
        "January 2024 with no successor. The current developer API is "
        "Enterprise/Education-only and returns writing scores, not the "
        "suggestions, offsets or corrected text you would need to act on. "
        "Scripting the consumer product breaches its terms of service."
    ),
    "manual_route": (
        "Use Grammarly as a final human pass: export the .docx, open it in Word "
        "with the Grammarly add-in, and accept the suggestions you agree with. "
        "That is the right place for a context-sensitive check anyway, and it "
        "keeps a tool you may already pay for in the loop."
    ),
    "in_pipeline": (
        "Self-hosted LanguageTool handles the automated pass. It returns real "
        "errors with character offsets and replacement candidates — exactly what "
        "Grammarly's API withholds — and runs entirely on your machine, so no "
        "draft leaves it. Start it with:\n\n"
        "    docker run -d -p 8081:8010 erikvl87/languagetool\n\n"
        "then set LANGUAGETOOL_URL=http://localhost:8081/v2/check"
    ),
    "alternatives": [
        {"name": "LanguageTool (self-hosted)", "licence": "LGPL",
         "returns": "errors with offsets and replacements", "local": True},
        {"name": "Harper", "licence": "Apache-2.0",
         "returns": "errors with offsets, millisecond latency, English only",
         "local": True},
        {"name": "Vale", "licence": "MIT",
         "returns": "terminology and house-style violations, markup-aware",
         "local": True},
        {"name": "Sapling.ai", "licence": "commercial API",
         "returns": "suggestions with offsets", "local": False},
        {"name": "LanguageTool Cloud", "licence": "commercial API",
         "returns": "same as self-hosted, without running a server", "local": False},
    ],
}


def protect(text: str) -> tuple[str, list[tuple[int, str]]]:
    """Replace protected spans with neutral filler of the same length.

    Same length matters: LanguageTool reports offsets into the string it was
    given, so a substitution that changed the length would misplace every issue
    after it.
    """
    protected: list[tuple[int, str]] = []
    result = text
    for pattern in _PROTECTED:
        for match in reversed(list(re.finditer(pattern, result))):
            original = match.group(0)
            filler = "X" * len(original)
            protected.append((match.start(), original))
            result = result[:match.start()] + filler + result[match.end():]
    return result, protected


async def check_text(
    text: str,
    *,
    url: str = "",
    language: str = DEFAULT_LANGUAGE,
    claim_id: str = "",
    section: str = "",
    timeout: float = 20.0,
) -> ProofReport:
    """Check one passage against a LanguageTool server."""
    endpoint = url or DEFAULT_LANGUAGETOOL_URL
    report = ProofReport(checked_words=len(text.split()), engine="LanguageTool")
    if not text.strip():
        return report

    guarded, _ = protect(text)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(endpoint, data={
                "text": guarded,
                "language": language,
                "disabledRules": ",".join(DISABLED_RULES),
                "level": "picky",
            })
    except httpx.HTTPError as error:
        report.note = (
            f"No LanguageTool server answered at {endpoint} ({type(error).__name__}). "
            f"Grammar checking was skipped — the export is unaffected. Start one "
            f"with: docker run -d -p 8081:8010 erikvl87/languagetool"
        )
        return report

    if response.status_code != 200:
        report.note = f"LanguageTool returned HTTP {response.status_code}."
        return report

    report.available = True
    try:
        payload = response.json()
    except ValueError:
        report.note = "LanguageTool's response was not JSON."
        return report

    for match in payload.get("matches", []):
        rule = match.get("rule") or {}
        context = match.get("context") or {}
        report.issues.append(ProofIssue(
            message=str(match.get("message", "")),
            context=str(context.get("text", "")),
            offset=int(match.get("offset", 0)),
            length=int(match.get("length", 0)),
            replacements=[str(r.get("value", ""))
                          for r in (match.get("replacements") or [])][:5],
            rule=str(rule.get("id", "")),
            category=str((rule.get("category") or {}).get("name", "")),
            claim_id=claim_id,
            section=section,
        ))
    return report


async def check_project(project, *, url: str = "") -> ProofReport:
    """Check every claim, keeping each issue tied to its claim.

    Checking claim by claim rather than as one blob means an issue arrives with
    the claim id and section attached, so the user can find and fix it — an
    offset into a concatenated document is not actionable.
    """
    combined = ProofReport(engine="LanguageTool")
    for claim in sorted(project.claims, key=lambda c: c.order):
        part = await check_text(claim.text, url=url,
                                claim_id=claim.claim_id, section=claim.section)
        combined.issues.extend(part.issues)
        combined.checked_words += part.checked_words
        combined.available = combined.available or part.available
        if part.note and not combined.note:
            combined.note = part.note
    if combined.available and not combined.issues:
        combined.note = (
            f"LanguageTool found no issues in {combined.checked_words:,} words. "
            f"That is not the same as error-free: a grammar checker cannot see a "
            f"wrong word that is spelled correctly, a misattributed finding, or a "
            f"sentence that says the opposite of what you meant. Read it."
        )
    return combined


def grammarly_report() -> dict:
    """What the UI shows when the user asks about Grammarly."""
    return GRAMMARLY_STATUS
