"""
Full-text ingestion: PDFs into anchored paragraphs, and data out of them.

Two jobs, and the first is what makes the second trustworthy.

## 1. Anchoring

A PDF is read into a list of `Passage` objects, each carrying its page number, its
index on that page, and a stable digest of its own text. That triple is the anchor
a claim points at. The specification asked for every generated claim to be linked
to "the exact paragraph in the source PDF it was drawn from", and an anchor is how
that link survives: a page number alone is not enough to find a paragraph again,
and a character offset breaks the moment the file is re-saved.

`locate()` goes the other way — given a sentence, find the passage it came from —
using the same 8-word shingle overlap the integrity checker uses, so a claim whose
support cannot be found in its own source is detectable rather than assumed.

## 2. Extraction

`extract()` pulls the fields the evidence matrix wants — design, setting, sample,
sample size, statistical results, funding, ethical approval, limitations — from
the passages.

**It is a reader, not a model.** Everything it returns carries the page and the
sentence it came from, and it returns nothing it cannot point at. That is a
deliberate limit, and the reason for it is the failure mode of the alternative: a
model asked to fill an extraction table will fill it, and a plausible sample size
in a matrix is worse than an empty cell, because an empty cell gets checked. Where
an Anthropic key is configured, `app/writing/draft.py` can do model-assisted
extraction — and it too is required to quote the passage it drew from.

## Why pypdf is optional

It is listed in `requirements.txt` but imported lazily behind a guard. Without it
the module still ingests plain text and pasted text, and it says so rather than
failing at the point of use. That matters because a user who cannot install a
dependency should lose PDF parsing, not the whole ingestion path.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------- structures


@dataclass
class Passage:
    """One paragraph of a source, with everything needed to find it again."""

    work_key: str = ""
    page: int = 0
    index: int = 0                  # position on that page
    text: str = ""
    digest: str = ""
    section: str = ""               # detected heading it falls under

    def anchor(self) -> str:
        """The citable locus: `p. 4 ¶2`, in the form APA wants for a locator."""
        return f"p. {self.page}, para. {self.index + 1}"

    def as_dict(self) -> dict[str, Any]:
        return {
            "work_key": self.work_key, "page": self.page, "index": self.index,
            "text": self.text, "digest": self.digest, "section": self.section,
            "anchor": self.anchor(),
        }


def _digest(text: str) -> str:
    normalised = " ".join(text.lower().split())
    return hashlib.sha1(normalised.encode("utf-8")).hexdigest()[:12]


# Headings a research paper actually uses, in the order they usually appear. Used
# to tag each passage with the section it sits under, because "the sample size was
# 1,204" means something different in Methods and in Discussion.
_HEADINGS = [
    ("abstract", r"^\s*abstract\b"),
    ("introduction", r"^\s*(?:1\.?\s*)?(?:introduction|background)\b"),
    ("methods", r"^\s*(?:2\.?\s*)?(?:methods?|methodology|materials and methods|"
                r"design|study design)\b"),
    ("results", r"^\s*(?:3\.?\s*)?(?:results?|findings)\b"),
    ("discussion", r"^\s*(?:4\.?\s*)?discussion\b"),
    ("limitations", r"^\s*limitations?\b"),
    ("conclusion", r"^\s*(?:5\.?\s*)?conclusions?\b"),
    ("references", r"^\s*(?:references|bibliography|works cited)\b"),
    ("funding", r"^\s*(?:funding|financial support|acknowledg)"),
    ("ethics", r"^\s*(?:ethic|institutional review|irb)"),
    ("conflicts", r"^\s*(?:conflicts? of interest|competing interests|"
                  r"declaration of interest)"),
]


# A heading is matched against the WHOLE line, not searched for within it. The
# first version of this searched, and "Abstract reasoning was assessed by the
# Raven matrices" re-sectioned the rest of the paper as an abstract. Requiring
# the line to *be* the heading — allowing a leading number and trailing
# punctuation, which is how journals typeset them — is the difference between a
# section tag that can be trusted and one that quietly mislabels every anchor.
_HEADING_LINES = [
    (name, re.compile(pattern + r"[\s:.–—-]*$", re.IGNORECASE))
    for name, pattern in _HEADINGS
]


def heading_name(line: str) -> str:
    """Return the section a line announces, or "" if it announces nothing."""
    stripped = " ".join((line or "").split())
    # A heading is short and is not a sentence. Both tests are needed: the
    # length alone lets "Methods were poor. We say so." through, and the
    # sentence test alone lets a long subtitle through.
    #
    # The sentence test looks past any leading section number, because "2.
    # Methods" contains ". " and would otherwise be read as prose — which is
    # how half the numbered headings in a typeset paper get missed.
    body = re.sub(r"^\d+(?:\.\d+)*\.?\s*", "", stripped)
    if not stripped or len(stripped) > 60 or ". " in body:
        return ""
    for name, pattern in _HEADING_LINES:
        if pattern.match(stripped):
            return name
    return ""


def paragraphs(text: str, *, page: int = 1, work_key: str = "",
               start_section: str = "") -> list[Passage]:
    """Split one page of text into anchored paragraphs. See `page_passages`."""
    found, _ = page_passages(text, page=page, work_key=work_key,
                             start_section=start_section)
    return found


def page_passages(text: str, *, page: int = 1, work_key: str = "",
                  start_section: str = "") -> tuple[list[Passage], str]:
    """Split one page of text into anchored paragraphs.

    Returns the passages and the section in force at the end of the page, so a
    heading on the last line of page 3 still governs page 4. Returning it
    separately matters because a page can end on a heading with no body text
    under it, and reading the section off the last passage would lose it.

    Blank-line separated where the text has blank lines, and split again at any
    line that is itself a section heading — PDF extraction routinely drops the
    blank line before "Results", and without that second split every paragraph
    after it inherits the wrong section.

    A heading line is consumed rather than kept: it becomes the block's
    `section`, so a limitations paragraph reads "Limitations include a single
    site" and not "Limitations Limitations include a single site".

    Very short fragments are folded into the previous paragraph — a PDF
    line-breaks mid-sentence, and treating each line as a paragraph would make
    every anchor useless — but never across a section boundary.
    """
    section = start_section
    blocks: list[tuple[str, str]] = []       # (text, section)
    current: list[str] = []

    def flush() -> None:
        nonlocal current
        if current:
            blocks.append((" ".join(current), section))
            current = []

    for line in (text or "").splitlines():
        if not line.strip():
            flush()
            continue
        announced = heading_name(line)
        if announced:
            flush()
            section = announced
            continue                          # the heading is the tag, not text
        current.append(line.strip())
    flush()

    out: list[Passage] = []
    for raw, block_section in blocks:
        cleaned = " ".join(raw.split())
        if not cleaned:
            continue
        # Fold a fragment into its predecessor rather than anchoring it alone,
        # but only when both sit under the same heading.
        if (out and len(cleaned.split()) < 12
                and out[-1].section == block_section):
            out[-1].text = (out[-1].text + " " + cleaned).strip()
            out[-1].digest = _digest(out[-1].text)
            continue
        out.append(Passage(work_key=work_key, page=page, index=len(out),
                           text=cleaned, digest=_digest(cleaned),
                           section=block_section))
    return out, section


# ------------------------------------------------------------------ ingestion


_PYPDF: tuple[bool, str] | None = None


def pypdf_probe() -> tuple[bool, str]:
    """Is PDF reading usable, and if not, why not.

    Catches far more than ImportError, and the reason is worth writing down: on
    one machine `import pypdf` did not raise ImportError at all — it pulled in a
    `cryptography` build whose Rust extension aborted, which surfaces as a
    PanicException inheriting from BaseException. A guard that catches only
    ImportError turns a broken optional dependency into a 500 on an endpoint
    that was only asking whether the feature exists.

    The result is cached: an import that dies this way tends to die slowly, and
    the answer cannot change while the process is running.
    """
    global _PYPDF
    if _PYPDF is not None:
        return _PYPDF
    try:
        import pypdf  # noqa: F401
        _PYPDF = (True, "")
    except ImportError:
        _PYPDF = (False, "pypdf is not installed.")
    except (KeyboardInterrupt, SystemExit):
        raise
    except BaseException as error:                  # noqa: BLE001 — deliberate
        _PYPDF = (False, f"pypdf is installed but failed to load "
                         f"({type(error).__name__}). Its optional cryptography "
                         f"backend is the usual cause.")
    return _PYPDF


def pypdf_available() -> bool:
    return pypdf_probe()[0]


def read_pdf(path: Path, *, work_key: str = "") -> dict[str, Any]:
    """Read a PDF into anchored passages.

    Degrades rather than fails: without pypdf, or on a scanned PDF with no text
    layer, it says which of those happened. A scanned PDF is the common case for
    an older paper and the message names OCR rather than leaving the user to
    guess why a 30-page article produced nothing.
    """
    usable, reason = pypdf_probe()
    if not usable:
        return {
            "passages": [], "pages": 0, "available": False,
            "note": (f"{reason} PDFs cannot be read. Everything else works: "
                     f"paste the text instead, or install it with "
                     f"`pip install pypdf`. It is in requirements.txt."),
        }

    import pypdf
    try:
        reader = pypdf.PdfReader(str(path))
    except Exception as error:
        return {"passages": [], "pages": 0, "available": True,
                "note": f"Could not open the PDF: {type(error).__name__}."}

    out: list[Passage] = []
    section = ""
    for number, page in enumerate(reader.pages, 1):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        found, section = page_passages(text, page=number, work_key=work_key,
                                       start_section=section)
        out.extend(found)

    if not out:
        return {
            "passages": [], "pages": len(reader.pages), "available": True,
            "note": ("The PDF opened but contained no extractable text. That "
                     "almost always means it is a scan rather than a digital "
                     "document — the pages are images. It needs OCR before "
                     "anything here can read it."),
        }
    return {
        "passages": [p.as_dict() for p in out],
        "pages": len(reader.pages),
        "available": True,
        "note": (f"{len(out)} paragraphs across {len(reader.pages)} pages. Every "
                 f"one carries its page and paragraph number, so a claim drawn "
                 f"from it can point at where it came from."),
    }


def read_text(text: str, *, work_key: str = "") -> dict[str, Any]:
    """Ingest pasted text, splitting on form feeds as page breaks."""
    pages = (text or "").split("\f")
    out: list[Passage] = []
    section = ""
    for number, page in enumerate(pages, 1):
        found, section = page_passages(page, page=number, work_key=work_key,
                                       start_section=section)
        out.extend(found)
    return {
        "passages": [p.as_dict() for p in out],
        "pages": len(pages),
        "available": True,
        "note": (f"{len(out)} paragraphs. Page numbers are approximate for pasted "
                 f"text — they come from form-feed characters, which a copy and "
                 f"paste usually loses. Check any locator before you cite it."
                 if len(pages) == 1 else
                 f"{len(out)} paragraphs across {len(pages)} pages."),
    }


# ------------------------------------------------------------------- locating


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", (text or "").lower())


def _shingles(text: str, size: int = 8) -> set[str]:
    words = _words(text)
    if len(words) < size:
        return {" ".join(words)} if words else set()
    return {" ".join(words[i:i + size]) for i in range(len(words) - size + 1)}


# Removed before scoring, because "the", "of" and "was" are in every paragraph
# of every paper and a match built on them is a match on nothing.
_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "but", "by", "for",
    "from", "had", "has", "have", "he", "her", "his", "in", "into", "is", "it",
    "its", "of", "on", "or", "our", "she", "than", "that", "the", "their",
    "then", "there", "these", "they", "this", "to", "was", "were", "which",
    "who", "will", "with", "would", "we", "us", "you", "not", "no", "also",
    "such", "when", "while", "both", "each", "more", "most", "other", "some",
    "any", "all", "may", "can", "could", "should", "between", "during", "after",
    "before", "over", "under", "about", "further", "however", "therefore",
}


def _content(text: str) -> list[str]:
    return [w for w in _words(text) if w not in _STOPWORDS and len(w) > 2]


def _ngrams(words: list[str], size: int) -> set[str]:
    if len(words) < size:
        return {" ".join(words)} if words else set()
    return {" ".join(words[i:i + size]) for i in range(len(words) - size + 1)}


def locate(sentence: str, passages: list[Passage], *, floor: float = 0.20,
           limit: int = 5) -> list[dict[str, Any]]:
    """Find the passages a sentence could have come from.

    Scores on *containment*, not similarity: what share of the claim's content
    appears in the passage. A long paragraph is not penalised for saying more
    than the claim does, which is the normal case — a claim is a compression of
    a paragraph, not a restatement of it.

    Two signals, and the difference between them is the whole point:

    * **Content-word and trigram containment** catch a *paraphrase*, which is
      what source-grounding needs. The first version of this scored 8-word
      shingles alone and returned nothing for a properly paraphrased claim —
      it could only find the sentences that were already a plagiarism problem.
    * **8-word verbatim runs** are reported separately, using the same shingle
      size as `writing/integrity.py`. A run here means the claim has lifted a
      phrase and must be quoted and given a locator, or rewritten.

    Returns every candidate above the floor, best first — a claim synthesised
    from two paragraphs should show both rather than being forced to pick one.
    An empty list is the meaningful answer it exists to give: this claim's
    support cannot be found in the source it cites.
    """
    target_words = _content(sentence)
    if not target_words:
        return []
    target_set = set(target_words)
    target_tri = _ngrams(target_words, 3)
    target_verbatim = _shingles(sentence, 8)

    scored: list[tuple[float, Passage, dict[str, Any]]] = []
    for passage in passages:
        passage_words = _content(passage.text)
        if not passage_words:
            continue
        shared_words = target_set & set(passage_words)
        unigram = len(shared_words) / len(target_set)
        shared_tri = target_tri & _ngrams(passage_words, 3)
        trigram = len(shared_tri) / len(target_tri) if target_tri else 0.0
        verbatim = sorted(target_verbatim & _shingles(passage.text, 8))
        # Weighted toward the trigram signal: shared vocabulary alone is weak
        # evidence in a paper where every paragraph is about the same topic.
        score = 0.55 * unigram + 0.45 * trigram
        if score < floor and not verbatim:
            continue
        if verbatim:
            basis = "verbatim"
        elif trigram >= 0.20 or unigram >= 0.50:
            # A genuine paraphrase reorders, so it can share almost no phrases
            # while sharing most of its content words. Either signal alone is
            # enough to call it a match; requiring both would label every
            # properly reworded claim "possible" and train the user to ignore
            # the column.
            basis = "close paraphrase"
        else:
            basis = "possible"
        scored.append((score, passage, {
            "score": round(score, 3),
            "word_overlap": round(unigram, 3),
            "phrase_overlap": round(trigram, 3),
            "verbatim_runs": verbatim[:3],
            "basis": basis,
        }))

    scored.sort(key=lambda row: (-len(row[2]["verbatim_runs"]), -row[0]))
    return [
        {
            "work_key": passage.work_key,
            "anchor": passage.anchor(),
            "page": passage.page,
            "index": passage.index,
            "digest": passage.digest,
            "section": passage.section,
            "excerpt": passage.text[:400],
            **detail,
        }
        for _, passage, detail in scored[:limit]
    ]


def ground(claims: list[dict[str, Any]],
           passages: list[Passage]) -> dict[str, Any]:
    """Anchor a claim ledger to the passages it says it came from.

    For each claim, find the passages of *the works it cites* that support it,
    and report the ones where nothing was found. That report is the deliverable:
    a claim whose cited source does not contain it is either mis-attributed or
    invented, and both are silent failures otherwise.

    A claim carrying a verbatim run is flagged separately from an unsupported
    one. They are opposite defects — too little of the source and too much of
    it — and collapsing them into one "problem" list would hide whichever is
    rarer in a given paper.
    """
    by_work: dict[str, list[Passage]] = {}
    for passage in passages:
        by_work.setdefault(passage.work_key, []).append(passage)

    rows: list[dict[str, Any]] = []
    unsupported: list[str] = []
    verbatim: list[str] = []
    unchecked: list[str] = []

    for claim in claims or []:
        claim_id = str(claim.get("claim_id") or "")
        text = str(claim.get("text") or "")
        keys = [k for k in (claim.get("work_keys") or []) if k]
        support = str(claim.get("support_type") or "paraphrase")
        if support == "no-citation":
            continue

        pool: list[Passage] = []
        missing_text: list[str] = []
        for key in keys:
            if key in by_work:
                pool.extend(by_work[key])
            else:
                missing_text.append(key)

        if not pool:
            unchecked.append(claim_id)
            rows.append({
                "claim_id": claim_id, "text": text[:200], "work_keys": keys,
                "matches": [], "status": "no full text",
                "detail": ("No full text has been ingested for "
                           + ", ".join(missing_text or ["this claim's sources"])
                           + ", so this claim could not be checked against its "
                             "source. That is not the same as it being wrong."),
            })
            continue

        matches = locate(text, pool)
        has_verbatim = any(m["verbatim_runs"] for m in matches)
        if has_verbatim:
            status = "verbatim overlap"
            verbatim.append(claim_id)
        elif matches:
            status = "anchored"
        else:
            status = "not found in source"
            unsupported.append(claim_id)
        rows.append({
            "claim_id": claim_id, "text": text[:200], "work_keys": keys,
            "matches": matches, "status": status,
            "detail": {
                "anchored": "Found in the cited source; the locator is below.",
                "verbatim overlap": (
                    "This claim repeats a run of eight or more words from the "
                    "source. Quote it and give the locator, or rewrite it."),
                "not found in source": (
                    "Nothing in the ingested full text of the cited work "
                    "supports this sentence. Either the citation is wrong or "
                    "the sentence is."),
            }[status],
        })

    return {
        "claims": rows,
        "unsupported": unsupported,
        "verbatim": verbatim,
        "unchecked": unchecked,
        "checked": len(rows) - len(unchecked),
        "note": (
            "Matching is by word and phrase overlap, so it finds where a claim "
            "came from — it does not judge whether the source actually says "
            "what the claim says it says. A green anchor means the sentence is "
            "traceable, not that it is true. Read the excerpt."
        ),
    }


# ----------------------------------------------------------------- extraction


# Thousands separators are allowed inside the number but never at its end —
# `\d[\d,]*` swallowed the comma after "p < .001," and put it in the matrix.
_NUM = r"\d(?:[\d,]*\d)?(?:\.\d+)?"

# Each pattern returns the value plus the sentence it came from, because an
# extracted number a user cannot trace is one they have to re-check anyway —
# at which point the extraction saved nothing.
_FIELD_PATTERNS: list[tuple[str, str, str]] = [
    ("sample_size", rf"\bn\s*=\s*({_NUM})", "an explicit n ="),
    ("sample_size", rf"\b({_NUM})\s+participants?\b", "participants"),
    ("sample_size", rf"\b({_NUM})\s+patients?\b", "patients"),
    ("sample_size", rf"\b({_NUM})\s+(?:nurses|respondents|subjects|women|men|"
                    rf"children|adults)\b", "a named population"),
    ("sample_size", rf"\bsample\s+(?:of|size\s+(?:was|of))\s+({_NUM})",
     "sample of"),
    ("response_rate", rf"response\s+rate\s+(?:of\s+)?({_NUM})\s*%", "response rate"),
    ("follow_up", rf"(?:followed|follow[- ]up)\s+(?:for\s+|of\s+)?({_NUM})\s*"
                  rf"(?:months?|years?|weeks?|days?)", "follow-up period"),
    ("attrition", rf"({_NUM})\s*%\s+(?:attrition|dropped out|lost to follow)",
     "attrition"),
]

# Ordered most-specific first: `extract()` skips a term whose match falls
# inside one already claimed for the same sentence, so "cluster randomised
# trial" has to be tested before the "randomised trial" inside it.
_DESIGN_TERMS = [
    ("cluster randomised trial", r"cluster[- ]randomi[sz]ed(?:[- ]controlled)?"
                                 r"(?:[- ]trial)?"),
    ("stepped-wedge trial", r"stepped[- ]wedge"),
    ("randomised controlled trial",
     r"randomi[sz]ed[- ](?:controlled[- ])?trial|\bRCTs?\b"),
    ("quasi-experimental", r"quasi[- ]experimental"),
    ("systematic review", r"systematic review"),
    ("meta-analysis", r"meta[- ]analys[ie]s"),
    ("scoping review", r"scoping review"),
    ("integrative review", r"integrative review"),
    ("cohort study", r"\bcohort\b"),
    ("case-control study", r"case[- ]control"),
    ("cross-sectional study", r"cross[- ]sectional"),
    ("qualitative descriptive", r"qualitative descriptive"),
    ("phenomenology", r"phenomenolog"),
    ("grounded theory", r"grounded theory"),
    ("mixed methods", r"mixed[- ]methods?"),
    ("quality improvement", r"quality improvement|\bPDSA\b|plan[- ]do[- ]study"),
    ("pilot study", r"\bpilot\b"),
    ("secondary analysis", r"secondary analysis"),
]

_SIGNED = r"[-−–]?" + _NUM

# The confidence-interval pattern reads to the closing bracket rather than to
# the first period. Stopping at a period cut "95% CI [0.45, 0.85]" down to
# "95% CI [0" — a truncated interval in an evidence matrix is worse than none,
# because it looks like a value.
# A bracket is only closed if it was opened. The single optional `[\])]?` this
# replaced produced "95% CI 1.02 to 3.31)" — an unbalanced interval, which in a
# matrix cell reads as a transcription error the user then has to go and check.
_CI_BODY = rf"{_SIGNED}\s*(?:,|to|–|—|-)\s*{_SIGNED}"
_STAT_PATTERNS = [
    rf"\bp\s*[<=>≤≥]\s*\.?{_NUM}",
    rf"\b(?:aOR|aRR|OR|RR|HR|IRR)\s*[=:]\s*{_SIGNED}",
    rf"\b\d{{2}}\s*%\s*CI[:\s]*(?:\[\s*{_CI_BODY}\s*\]|\(\s*{_CI_BODY}\s*\)|"
    rf"{_CI_BODY})",
    rf"\bt\s*\(\s*\d+(?:\.\d+)?\s*\)\s*=\s*{_SIGNED}",
    rf"\bF\s*\(\s*\d+\s*,\s*\d+\s*\)\s*=\s*{_NUM}",
    rf"\b(?:χ2|χ²|x2)\s*\(\s*\d+(?:\s*,\s*N\s*=\s*{_NUM})?\s*\)\s*=\s*{_NUM}",
    rf"\b(?:Cohen's\s*)?d\s*=\s*{_SIGNED}",
    rf"\br\s*=\s*[-−–]?\.?{_NUM}",
    rf"\bM\s*=\s*{_SIGNED}\s*(?:,|\()\s*SD\s*=\s*{_SIGNED}",
]

# The name of a test is not a result, so it gets its own field. It belongs in
# the methodology column of an evidence matrix, and mixing it into the results
# column was making "chi-square" sit beside "p = .006" as though it were one.
_TEST_NAMES = [
    ("chi-square test", r"chi[- ]squared?\b|\bχ2\b"),
    ("independent-samples t test", r"\bt[- ]tests?\b"),
    ("ANCOVA", r"\bANCOVA\b|analysis of covariance"),
    ("ANOVA", r"\bANOVA\b|analysis of variance"),
    ("logistic regression", r"logistic regression"),
    ("linear regression", r"(?:multiple |multivariable )?linear regression"),
    ("Cox proportional hazards", r"cox (?:proportional[- ]hazards?|regression)"),
    ("Mann-Whitney U", r"mann[-– ]whitney"),
    ("Wilcoxon signed-rank", r"wilcoxon"),
    ("Kruskal-Wallis", r"kruskal[-– ]wallis"),
    ("Fisher's exact test", r"fisher'?s? exact"),
    ("Kaplan-Meier", r"kaplan[-– ]meier"),
    ("intention-to-treat analysis", r"intention[- ]to[- ]treat|\bITT\b"),
    ("per-protocol analysis", r"per[- ]protocol analysis"),
    ("thematic analysis", r"thematic analysis"),
    ("content analysis", r"content analysis"),
    ("constant comparative method", r"constant comparative"),
    ("random-effects model", r"random[- ]effects? model"),
    ("fixed-effect model", r"fixed[- ]effects? model"),
    ("heterogeneity (I²)", r"\bI2\b|\bI²\b|heterogeneit"),
]

_ETHICS = r"(?:institutional review board|\bIRB\b|research ethics committee|" \
          r"ethical approval|ethics approval|approved by the)"
_FUNDING = r"(?:funded by|funding was provided|grant (?:number|no)|" \
           r"supported by (?:a |an |the )?(?:grant|award))"
_CONFLICT = r"(?:conflicts? of interest|competing interests?|" \
            r"declare[sd]? no (?:conflicts?|competing))"


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text or "") if s.strip()]


def extract(passages: list[Passage]) -> dict[str, Any]:
    """Pull evidence-matrix fields out of anchored passages.

    Everything returned carries the page it came from and the sentence it was
    read out of. Nothing is returned that cannot be pointed at — an extraction
    table filled with plausible unsourced numbers is worse than an empty one,
    because an empty cell gets checked and a filled one does not.
    """
    found: dict[str, list[dict[str, Any]]] = {}

    def record(field_name: str, value: str, passage: Passage, sentence: str,
               why: str = "") -> None:
        rows = found.setdefault(field_name, [])
        # Compare on a normalised key so "1,204" and "1204" from the same page
        # are one finding, not two. The displayed value keeps its original
        # punctuation, because that is what the reader will find in the PDF.
        key = re.sub(r"[\s,]+", "", value.lower())
        if any(row["_key"] == key and row["page"] == passage.page
               for row in rows):
            return
        rows.append({
            "value": value,
            "page": passage.page,
            "anchor": passage.anchor(),
            "section": passage.section,
            "sentence": sentence.strip()[:320],
            "why": why,
            "_key": key,
        })

    for passage in passages:
        for sentence in _sentences(passage.text):
            for field_name, pattern, why in _FIELD_PATTERNS:
                for match in re.finditer(pattern, sentence, re.IGNORECASE):
                    record(field_name, match.group(1), passage, sentence, why)

            # Design terms are ordered most-specific first, and a term whose
            # match sits inside an already-matched span is skipped: "cluster
            # randomised trial" should not also report the plain "randomised
            # controlled trial" it contains.
            claimed: list[tuple[int, int]] = []
            for label, pattern in _DESIGN_TERMS:
                for match in re.finditer(pattern, sentence, re.IGNORECASE):
                    start, end = match.span()
                    if any(s <= start and end <= e for s, e in claimed):
                        continue
                    claimed.append((start, end))
                    record("design", label, passage, sentence,
                           "named in the text")
                    break

            for pattern in _STAT_PATTERNS:
                for match in re.finditer(pattern, sentence, re.IGNORECASE):
                    record("statistics", match.group(0).strip(), passage,
                           sentence, "statistical result")

            for label, pattern in _TEST_NAMES:
                if re.search(pattern, sentence, re.IGNORECASE):
                    record("analysis", label, passage, sentence,
                           "named analysis")

            if re.search(_ETHICS, sentence, re.IGNORECASE):
                record("ethical_approval", "stated", passage, sentence,
                       "ethics statement")
            if re.search(_FUNDING, sentence, re.IGNORECASE):
                record("funding", "stated", passage, sentence, "funding statement")
            if re.search(_CONFLICT, sentence, re.IGNORECASE):
                record("conflicts", "stated", passage, sentence,
                       "conflict of interest statement")
            if passage.section == "limitations" or re.search(
                    r"\b(?:a )?limitations? (?:of|include|is|are|was|were)\b",
                    sentence, re.IGNORECASE):
                record("limitations", sentence.strip()[:240], passage, sentence,
                       "limitation")

    # Sample size gets a best guess: the largest figure found in the methods,
    # which is where a total N is stated. Reported as a candidate with its
    # sentence rather than as an answer.
    best_n = None
    candidates = found.get("sample_size", [])
    methods_first = [c for c in candidates if c["section"] == "methods"] or candidates
    if methods_first:
        def as_number(row: dict[str, Any]) -> float:
            try:
                return float(str(row["value"]).replace(",", ""))
            except ValueError:
                return 0.0
        best_n = max(methods_first, key=as_number)

    missing = [name for name in
               ("design", "sample_size", "analysis", "statistics",
                "ethical_approval", "funding", "conflicts", "limitations")
               if not found.get(name)]

    for rows in found.values():                 # drop the dedupe key
        for row in rows:
            row.pop("_key", None)

    return {
        "fields": found,
        "suggested_sample_size": best_n,
        "missing": missing,
        "note": (
            "Every value above carries the page and the sentence it was read "
            "from. Check each one before it goes in the matrix — this is a "
            "reader, not a model, and it reports what it matched rather than "
            "what a study means. Anything it could not find is listed as "
            "missing rather than guessed, because a plausible unsourced number "
            "in an extraction table is worse than an empty cell: the empty cell "
            "gets checked."
        ),
        "missing_note": (
            "Not found in the text: " + ", ".join(m.replace("_", " ")
                                                  for m in missing) + ". "
            "An absent funding or ethics statement is itself a finding — both "
            "are reporting requirements, and their absence belongs in your "
            "appraisal."
            if missing else ""
        ),
    }


def passages_from_dicts(rows: list[dict[str, Any]]) -> list[Passage]:
    out: list[Passage] = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        passage = Passage()
        for name in passage.__dataclass_fields__:
            if name in row:
                setattr(passage, name, row[name])
        out.append(passage)
    return out
