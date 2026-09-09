"""
Writing a paper in APA 7, with no research pipeline in the way.

Everything else in this application starts from a research question: frame it,
search the databases, screen, appraise, extract, build a claim ledger, export.
That is the right shape for a systematic review, and it is the wrong shape for
the far commoner job of *having a paper to write and needing it in APA 7*.

Asked for a place to write in APA 7, this suite offered a reference screen —
the rules, the heading levels, nine worked examples — and an export button at
the end of a pipeline you had to walk first. Reading the rules is not writing,
and a formatter you can only reach by first inventing a systematic review is a
formatter you do not have.

So this module is the straight lane. You are prompted for the title page, the
abstract, the body and the references; what comes out is a .docx that is APA 7
in the file rather than in a checklist. It shares the citation engine, the
OOXML layer and the typeface rules with the research lane — the formatting is
the same formatting, and a defect fixed in one is fixed in both — and shares
nothing else. No question, no evidence levels, no appraisal, no claim ledger.

What this deliberately does not do is write the prose. The words are yours.
What it does is stop the mechanical marks being wrong: the heading that skipped
a level, the reference nobody cited, the citation with no reference, the
quotation long enough to need a block, the running head over 50 characters.
Those are what gets marked down, and they are exactly what a person cannot
reliably check by re-reading their own draft at one in the morning.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import tempfile
from dataclasses import dataclass, field, fields as dataclass_fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..models import Author, Project, TitlePage, Work, WorkType
from . import citations as citations_module
from .citations import CitationContext, Run, plain
from .document import (
    APPROVED_FONTS, BODY_INDENT, ApaPaper, Block,
    default_running_head,
)
from docx.enum.text import WD_ALIGN_PARAGRAPH

# ---------------------------------------------------------------- the markup
#
# One convention, printed on the screen beside the box you type into. The hash
# marks map onto the five APA heading levels in order, which is the one thing
# about APA headings people do remember, and everything else is just prose.
#
# Chosen over a rich-text editor on purpose. A contenteditable box produces
# HTML that then has to be mapped to Word styles, and every such mapping in
# this codebase's experience loses something silently — a bold run that was
# really a Level 4 heading, a paste from a browser carrying spans. Plain text
# with five markers cannot lose anything, because there is nothing in it to
# lose.

HEADING_PATTERN = re.compile(r"^(#{1,5})\s+(.*)$")
LIST_PATTERN = re.compile(r"^[-*+]\s+(.+)$")
QUOTE_PATTERN = re.compile(r"^>\s?(.*)$")

# APA 7 §8.27: a quotation of 40 words or more is set as a block.
BLOCK_QUOTE_WORDS = 40

# APA 7 §2.9 gives no hard limit but says most abstracts run 150-250 words, and
# journals and course rubrics almost always enforce that band.
ABSTRACT_MIN_WORDS = 150
ABSTRACT_MAX_WORDS = 250

# APA 7 §2.4: the running head is at most 50 characters including spaces and
# punctuation. This one *is* a hard limit.
RUNNING_HEAD_MAX = 50

MARKUP_HELP = [
    ("# Heading", "Level 1 — centred, bold. The main sections."),
    ("## Heading", "Level 2 — flush left, bold."),
    ("### Heading", "Level 3 — flush left, bold italic."),
    ("#### Heading", "Level 4 — indented, bold, run into the paragraph."),
    ("##### Heading", "Level 5 — indented, bold italic, run into the paragraph."),
    ("> Quoted text", "A block quotation. Quotations of 40 words or more are "
                      "made blocks automatically, so this is only needed for "
                      "shorter ones you want set off."),
    ("- Item", "A list item."),
    ("Blank line", "Separates paragraphs. Every paragraph is indented half an "
                   "inch and double spaced, as APA requires — you do not type "
                   "the indents."),
]


# ------------------------------------------------------------------ the model


@dataclass
class Paper:
    """One paper being written.

    Separate from `Project` rather than a flavour of it. A Project carries a
    question, inclusion criteria, an evidence floor, appraisals and a claim
    ledger, and every one of those would sit on this screen as a field that
    must be left blank — or worse, as an export blocker demanding sources for
    a reflective essay that legitimately cites four.
    """

    paper_id: str = ""
    variant: str = "student"            # student | professional
    title: str = ""
    authors: list[str] = field(default_factory=list)
    affiliations: list[str] = field(default_factory=list)
    course: str = ""
    instructor: str = ""
    due_date: str = ""
    running_head: str = ""
    author_note: str = ""
    abstract: str = ""
    keywords: list[str] = field(default_factory=list)
    body: str = ""
    references: list[Work] = field(default_factory=list)
    font: str = ""
    created_at: str = ""
    updated_at: str = ""

    def title_page(self) -> TitlePage:
        return TitlePage(
            variant=self.variant,
            title=self.title,
            authors=list(self.authors),
            affiliations=list(self.affiliations),
            course=self.course,
            instructor=self.instructor,
            due_date=self.due_date,
            running_head=self.running_head or default_running_head(self.title),
            author_note=self.author_note,
        )

    def as_project(self) -> Project:
        """A Project shell, purely to satisfy the document builder.

        `ApaPaper` reads exactly two things off a project — the title page and
        the topic — and building one here is cheaper and clearer than
        loosening its constructor. Nothing is stored; this object never
        reaches the project store.
        """
        return Project(
            project_id=self.paper_id,
            topic=self.title,
            title_page=self.title_page(),
            works=list(self.references),
            font=self.font,
        )


# ----------------------------------------------------------------- the parser


def parse_body(text: str) -> list[Block]:
    """Turn the written text into the blocks the document builder renders.

    Paragraph breaks are blank lines, so a single newline inside a paragraph is
    a soft wrap and not a new paragraph — which is what happens when someone
    pastes from a PDF and every line arrives separately.
    """
    blocks: list[Block] = []
    pending: list[str] = []

    def flush() -> None:
        if not pending:
            return
        paragraph = " ".join(" ".join(pending).split())
        pending.clear()
        if not paragraph:
            return
        kind = "quote" if _is_long_quotation(paragraph) else "paragraph"
        runs = _runs_for(_unquote(paragraph) if kind == "quote" else paragraph)
        blocks.append(Block(kind=kind, runs=runs))

    for raw in (text or "").splitlines():
        line = raw.rstrip()
        stripped = line.strip()

        if not stripped:
            flush()
            continue

        heading = HEADING_PATTERN.match(stripped)
        if heading:
            flush()
            level = len(heading.group(1))
            blocks.append(Block(kind="heading", level=level,
                                text=heading.group(2).strip()))
            continue

        quote = QUOTE_PATTERN.match(stripped)
        if quote:
            flush()
            blocks.append(Block(kind="quote", runs=_runs_for(quote.group(1).strip())))
            continue

        item = LIST_PATTERN.match(stripped)
        if item:
            flush()
            blocks.append(Block(kind="list-item", runs=_runs_for(item.group(1).strip())))
            continue

        pending.append(stripped)

    flush()
    return blocks


def _runs_for(text: str) -> list[Run]:
    """Split *asterisked* spans into italic runs, leaving the rest plain.

    Italics are the one piece of inline formatting APA actually requires in
    body text — a genus name, a statistical symbol, a term being defined
    (§6.22) — so there has to be a way to type one. Everything else that a
    word processor offers is either decoration or a heading in disguise.
    """
    runs: list[Run] = []
    for index, chunk in enumerate(re.split(r"\*(.+?)\*", text)):
        if not chunk:
            continue
        runs.append(Run(chunk, italic=bool(index % 2)))
    return runs or [Run(text)]


def _is_long_quotation(paragraph: str) -> bool:
    """A paragraph that is wholly a quotation of 40+ words (APA 7 §8.27)."""
    stripped = paragraph.strip()
    if not (stripped.startswith(("“", '"')) and "”" in stripped[1:]
            or stripped.startswith('"') and stripped.count('"') >= 2):
        return False
    return len(_unquote(stripped).split()) >= BLOCK_QUOTE_WORDS


def _unquote(paragraph: str) -> str:
    """Strip the outer quotation marks. A block quotation carries none: the
    indent is what marks it as quoted (§8.27), and keeping the marks as well
    is the single commonest block-quote error."""
    text = paragraph.strip()
    for opening, closing in (("“", "”"), ('"', '"')):
        if text.startswith(opening):
            end = text.rfind(closing)
            if end > 0:
                return (text[1:end] + text[end + 1:]).strip()
    return text


def outline(blocks: list[Block]) -> list[dict[str, Any]]:
    """The heading structure, with the words under each one.

    Shown beside the editor because a paper's shape is the thing you cannot see
    while writing it, and because the level-skip check below is far easier to
    act on when you can see what it is talking about.
    """
    rows: list[dict[str, Any]] = []
    for block in blocks:
        if block.kind == "heading":
            rows.append({"level": block.level, "text": block.text, "words": 0})
        elif rows:
            rows[-1]["words"] += len(plain(block.runs).split())
    return rows


def word_count(blocks: list[Block]) -> int:
    return sum(len(plain(block.runs).split()) for block in blocks
               if block.kind != "heading")


# ------------------------------------------------------------------ the checks
#
# Reported as findings with a severity, never as a percentage. A score invites
# treating 92% as good enough, and the missing 8% is the title page.

CITATION_PATTERN = re.compile(
    # "(Smith, 2020)", "(Smith & Jones, 2020, p. 4)", "(CDC, 2023a)" — and the
    # multi-work form separated by semicolons, which is split afterwards.
    r"\(([^()]{2,200}?,\s*(?:n\.d\.|in press|(?:1[6-9]|20)\d{2}[a-z]?)[^()]{0,60})\)"
)
NARRATIVE_PATTERN = re.compile(
    r"\b([A-Z][\w'’-]+(?:(?:,| and| &)\s+(?:et al\.|[A-Z][\w'’-]+))*)"
    r"\s+\((?:n\.d\.|in press|(?:1[6-9]|20)\d{2}[a-z]?)"
)
YEAR_PATTERN = re.compile(r"(?:n\.d\.|in press|(?:1[6-9]|20)\d{2}[a-z]?)")


def check(paper: Paper, blocks: list[Block] | None = None) -> list[dict[str, str]]:
    """Everything mechanically checkable about an APA 7 paper.

    Ordered worst first. `severity` is "error" for something APA states as a
    rule, "warn" for guidance with a defensible exception, and "check" for
    something this code cannot be certain about and is raising for a human to
    look at rather than asserting.
    """
    blocks = parse_body(paper.body) if blocks is None else blocks
    found: list[dict[str, str]] = []

    def add(severity: str, rule: str, message: str) -> None:
        found.append({"severity": severity, "rule": rule, "message": message})

    # --- the title page ------------------------------------------------------
    if not paper.title.strip():
        add("error", "§2.4", "The paper has no title. It goes on the title "
                             "page and is repeated, centred and bold, at the "
                             "top of the first page of text.")
    elif len(paper.title.split()) > 15:
        add("warn", "§2.4", f"The title runs to {len(paper.title.split())} "
                            "words. APA 7 dropped the old 12-word limit but "
                            "asks for a title that is focused and concise; a "
                            "rubric may still hold you to twelve.")
    if not [a for a in paper.authors if a.strip()]:
        add("error", "§2.5", "No author is named on the title page.")

    if paper.variant == "student":
        for label, value, rule in (("course", paper.course, "§2.7"),
                                   ("instructor", paper.instructor, "§2.7"),
                                   ("due date", paper.due_date, "§2.8")):
            if not value.strip():
                add("error", rule, f"A student title page carries the {label}, "
                                   "and this one does not.")
        if paper.running_head.strip():
            add("warn", "§2.4", "Student papers do not carry a running head — "
                                "only the page number. Clear it, or switch the "
                                "paper to professional.")
    else:
        head = paper.running_head.strip() or default_running_head(paper.title)
        if not head:
            add("error", "§2.4", "A professional paper needs a running head.")
        elif len(head) > RUNNING_HEAD_MAX:
            add("error", "§2.4", f"The running head is {len(head)} characters. "
                                 f"The limit is {RUNNING_HEAD_MAX}, including "
                                 "spaces and punctuation.")
        elif head != head.upper():
            add("error", "§2.4", "The running head is set in capitals in the "
                                 "header. Type it as you want it read.")
        if not [a for a in paper.affiliations if a.strip()]:
            add("warn", "§2.6", "A professional paper names the author's "
                                "affiliation under the author.")

    # --- the abstract --------------------------------------------------------
    if paper.abstract.strip():
        words = len(paper.abstract.split())
        if words < ABSTRACT_MIN_WORDS or words > ABSTRACT_MAX_WORDS:
            add("warn", "§2.9", f"The abstract is {words} words. APA 7 sets no "
                                f"hard limit but most run "
                                f"{ABSTRACT_MIN_WORDS}–{ABSTRACT_MAX_WORDS}, "
                                "and rubrics enforce it.")
        if paper.keywords and not (3 <= len(paper.keywords) <= 5):
            add("warn", "§2.10", f"{len(paper.keywords)} keywords. Three to "
                                 "five is the usual range.")

    # --- the body ------------------------------------------------------------
    if not blocks:
        add("error", "§2.11", "There is no body text yet.")

    found.extend(_heading_findings(blocks))
    found.extend(_quotation_findings(blocks))
    found.extend(_reference_findings(paper, blocks))

    order = {"error": 0, "warn": 1, "check": 2}
    found.sort(key=lambda f: order.get(f["severity"], 3))
    return found


def _heading_findings(blocks: list[Block]) -> list[dict[str, str]]:
    """A heading level may not be skipped (APA 7 §2.27).

    Levels are used in order — a Level 3 under a Level 1 with no Level 2
    between them is wrong, however sensible the nesting looks. This is the
    structural error a person almost never catches by re-reading, because the
    formatting looks fine on the page.
    """
    findings: list[dict[str, str]] = []
    seen = 0
    for block in blocks:
        if block.kind != "heading":
            continue
        if not (block.text or "").strip():
            findings.append({"severity": "error", "rule": "§2.27",
                             "message": "There is an empty heading."})
            continue
        if block.level > seen + 1:
            findings.append({
                "severity": "error", "rule": "§2.27",
                "message": (f"“{block.text}” is a Level {block.level} heading, "
                            f"but the deepest level used before it is "
                            f"{seen or 'none'}. Levels are used in order and "
                            "none may be skipped."),
            })
        seen = max(seen, block.level)
    return findings


def _quotation_findings(blocks: list[Block]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for block in blocks:
        text = plain(block.runs)
        if block.kind == "quote":
            if not _has_locator(text):
                findings.append({
                    "severity": "error", "rule": "§8.13",
                    "message": (f"A block quotation has no page or paragraph "
                                f"number: “{_snippet(text)}”. Every direct "
                                "quotation carries one."),
                })
            continue
        for quoted in re.findall(r"[“\"]([^”\"]{2,2000})[”\"]", text):
            words = len(quoted.split())
            if words >= BLOCK_QUOTE_WORDS:
                findings.append({
                    "severity": "error", "rule": "§8.27",
                    "message": (f"A quotation of {words} words sits inside a "
                                f"paragraph: “{_snippet(quoted)}”. Forty words "
                                "or more is set as an indented block with no "
                                "quotation marks — put it in its own paragraph "
                                "and it will be made one."),
                })
            elif words >= 3 and not _has_locator(text):
                findings.append({
                    "severity": "check", "rule": "§8.13",
                    "message": (f"A quotation with no page or paragraph number "
                                f"nearby: “{_snippet(quoted)}”."),
                })
    return findings


def _has_locator(text: str) -> bool:
    return bool(re.search(r"\b(?:pp?\.|paras?\.|Chapter|Table|Figure)\s*\d", text))


def _snippet(text: str, width: int = 60) -> str:
    words = text.split()
    short = " ".join(words[:12])
    return short if len(short) <= width else short[:width].rstrip() + "…"


def _reference_findings(paper: Paper, blocks: list[Block]) -> list[dict[str, str]]:
    """The correspondence rule, which is the one that costs marks.

    APA 7 §8.1 and §9.51: every work in the reference list is cited in the
    text, and every work cited in the text is in the reference list. Exactly —
    a reference list is not a bibliography of what you read.

    Both directions are checked, and they are checked differently on purpose.
    Going from a reference to the text is reliable: we know the surname and the
    year, so finding them is a fact. Going the other way means recognising
    citation-shaped text, which cannot be exact — so those come back as
    "check", never as an assertion that something is wrong.
    """
    findings: list[dict[str, str]] = []
    text = " ".join(plain(block.runs) if block.kind != "heading" else block.text
                    for block in blocks)
    if not paper.references and not text:
        return findings

    context = CitationContext(paper.references)

    # 1. Listed but never cited.
    for work in paper.references:
        name = _surname(work)
        year = (work.year or "").strip()
        if not name:
            continue
        if not _cited(text, name, year):
            entry = plain(citations_module.reference(work, CitationContext(
                paper.references)))
            findings.append({
                "severity": "error", "rule": "§9.51",
                "message": (f"“{_snippet(entry, 80)}” is in the reference list "
                            "but is never cited in the text. Cite it or remove "
                            "it — a reference list is what you cited, not what "
                            "you read."),
            })

    # 2. Cited but not listed.
    listed = {_surname(work).lower() for work in paper.references if _surname(work)}
    for candidate in _cited_names(text):
        head = candidate.split()[0].strip(",").lower() if candidate.split() else ""
        if head and not any(head == name or head in name.split()
                            for name in listed):
            findings.append({
                "severity": "check", "rule": "§8.1",
                "message": (f"“{candidate}” looks like a citation, but nothing "
                            "in the reference list matches it. Add the "
                            "reference, or ignore this if it is not a "
                            "citation."),
            })

    # 3. Author-date shapes the engine would render differently.
    #
    # Matched on the author-year core rather than the whole rendered citation,
    # because a citation carrying a locator — "(Aiken et al., 2021, p. 14)" —
    # does not contain "(Aiken et al., 2021)" as a substring, and comparing
    # whole strings reported every correctly-cited quotation as wrong.
    for work in paper.references:
        surname = _surname(work)
        if not surname or not _cited(text, surname, work.year):
            continue
        parenthetical = plain(citations_module.intext(
            work, CitationContext(paper.references))).rstrip(")")
        narrative = plain(citations_module.intext(
            work, CitationContext(paper.references), narrative=True)).rstrip(")")
        if parenthetical in text or narrative in text:
            continue
        findings.append({
            "severity": "check", "rule": "§8.17",
            "message": (f"{surname} is cited, but not in the form this "
                        f"reference produces: {parenthetical}) or "
                        f"{narrative}). Three or more authors take et al. from "
                        "the first citation in APA 7 — copy the form shown "
                        "beside the reference."),
        })

    # 4. The same source listed twice.
    #
    # Easy to do and hard to see: add a reference from a DOI, then add it again
    # by hand, and the two differ in a field the fingerprint hashes while being
    # the same paper. The reader sees one source with two entries, and the year
    # letters the engine adds to tell them apart (2021a, 2021b) make it look
    # deliberate.
    seen: dict[tuple[str, str, str], Work] = {}
    for work in paper.references:
        signature = (_surname(work).lower(), (work.year or "")[:4],
                     re.sub(r"[^a-z0-9]+", "", (work.title or "").lower())[:60])
        if not signature[0] and not signature[2]:
            continue
        if signature in seen:
            findings.append({
                "severity": "error", "rule": "§9.51",
                "message": (f"“{_snippet(work.title or _surname(work), 70)}” is "
                            "in the reference list twice. One source gets one "
                            "entry; the a/b year letters beside it are the "
                            "engine telling them apart, not a citation style."),
            })
        else:
            seen[signature] = work

    del context
    return findings


def _surname(work: Work) -> str:
    people = work.authors or work.editors
    if not people:
        return ""
    return (people[0].family or "").strip()


def _cited(text: str, surname: str, year: str) -> bool:
    """Whether the text cites this author-year pair anywhere.

    The year has to be near the name rather than merely present, or a paper
    that mentions 2020 once would mark every 2020 reference as cited.
    """
    if not surname:
        return False
    year = (year or "").strip() or "n.d."
    for match in re.finditer(re.escape(surname), text):
        window = text[match.end():match.end() + 80]
        if year[:4] and year[:4] in window:
            return True
        if year in ("n.d.", "") and "n.d." in window:
            return True
    return False


def _cited_names(text: str) -> list[str]:
    """Author strings that look like citations, de-duplicated in order."""
    names: list[str] = []
    for match in CITATION_PATTERN.finditer(text):
        for part in match.group(1).split(";"):
            head = YEAR_PATTERN.split(part.strip(), 1)[0].strip().rstrip(",").strip()
            if head and head not in names and not head[0].islower():
                names.append(head)
    for match in NARRATIVE_PATTERN.finditer(text):
        head = match.group(1).strip().rstrip(",")
        if head and head not in names:
            names.append(head)
    return names


# ----------------------------------------------------------------- references


REFERENCE_FIELDS = [
    {"name": "work_type", "label": "Type", "kind": "select",
     "options": [t.value for t in WorkType],
     "help": "Journal article, book, chapter, report, webpage — each has its "
             "own reference shape, and picking the wrong one is why a "
             "reference looks nearly right."},
    {"name": "authors", "label": "Authors", "kind": "text",
     "help": "One per line, as “Family, Given” — Smith, Jane A. For an "
             "organisation (CDC, World Health Organization) put the whole name "
             "on its own line; it is kept whole and never initialised."},
    {"name": "year", "label": "Year", "kind": "text",
     "help": "2024, or n.d. when there is no date."},
    {"name": "title", "label": "Title", "kind": "text",
     "help": "Type it however it appears. It is converted to sentence case, "
             "with proper nouns and terms like COVID-19 preserved."},
    {"name": "container", "label": "Journal, book or site", "kind": "text"},
    {"name": "volume", "label": "Volume", "kind": "text"},
    {"name": "issue", "label": "Issue", "kind": "text"},
    {"name": "pages", "label": "Pages", "kind": "text",
     "help": "45-52. The hyphen becomes an en dash."},
    {"name": "edition", "label": "Edition", "kind": "text"},
    {"name": "publisher", "label": "Publisher", "kind": "text"},
    {"name": "doi", "label": "DOI", "kind": "text",
     "help": "Rendered as https://doi.org/… — APA 7 dropped “doi:”."},
    {"name": "url", "label": "URL", "kind": "text",
     "help": "Only when there is no DOI."},
]


def work_from_fields(values: dict[str, Any]) -> Work:
    """Build a Work from what the reference form collected."""
    work = Work()
    raw_type = str(values.get("work_type") or "").strip()
    try:
        work.work_type = WorkType(raw_type) if raw_type else WorkType.JOURNAL_ARTICLE
    except ValueError:
        work.work_type = WorkType.JOURNAL_ARTICLE

    authors = values.get("authors")
    lines = (authors if isinstance(authors, list)
             else str(authors or "").splitlines())
    work.authors = [Author.parse(line) for line in lines if str(line).strip()]

    for name in ("year", "title", "container", "volume", "issue", "pages",
                 "edition", "publisher", "doi", "url"):
        setattr(work, name, str(values.get(name) or "").strip())

    work.key = work.fingerprint() if hasattr(work, "fingerprint") else ""
    if not work.key:
        work.key = secrets.token_hex(6)
    return work


def reference_preview(works: list[Work]) -> list[dict[str, str]]:
    """Each reference with the two in-text forms it produces.

    Rendered by the engine that writes the document, so what is shown is what
    lands in the .docx — and a fresh context per row so every row reads as a
    first citation, which is where the et al. and group-abbreviation rules
    actually differ.
    """
    rows: list[dict[str, str]] = []
    for work in works:
        rows.append({
            "key": work.key,
            "reference": plain(citations_module.reference(
                work, CitationContext(works))),
            "parenthetical": plain(citations_module.intext(
                work, CitationContext(works))),
            "narrative": plain(citations_module.intext(
                work, CitationContext(works), narrative=True)),
        })
    return rows


def write_body(builder: ApaPaper, blocks: list[Block], title: str) -> None:
    """Render the body, running Level 4 and 5 headings into their paragraph.

    `ApaPaper.body` emits every heading as its own paragraph, which is right
    for levels 1-3 and wrong for 4 and 5: APA 7 §2.27 makes those run-in, with
    the text continuing on the same line after the full stop. Doing it here
    needs one look-ahead, which is why the generic builder does not.
    """
    builder._paragraph(
        [Run(title)], align=WD_ALIGN_PARAGRAPH.CENTER,
        bold=True, keep_next=True, new_page=True)

    index = 0
    while index < len(blocks):
        block = blocks[index]
        following = blocks[index + 1] if index + 1 < len(blocks) else None
        if (block.kind == "heading" and block.level >= 4
                and following is not None and following.kind == "paragraph"):
            builder.run_in_heading(block.text or "", block.level, following.runs)
            index += 2
            continue
        if block.kind == "heading":
            builder.heading(block.text or "", block.level)
        elif block.kind == "quote":
            builder.block_quote(block.runs)
        elif block.kind == "list-item":
            builder._paragraph(block.runs, left_indent=BODY_INDENT)
        else:
            builder._paragraph(block.runs,
                               first_line_indent=BODY_INDENT)
        index += 1


# --------------------------------------------------------------------- storage


SCHEMA_VERSION = 1


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class PaperStore:
    """One JSON file per paper, written atomically — as the project store does,
    and for the same reason: losing a draft to a crash mid-save is the failure
    a writing tool must not have."""

    def __init__(self, directory: Path):
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)

    def _make_id(self, title: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:40] or "paper"
        candidate = slug
        while (self.directory / f"{candidate}.json").exists():
            candidate = f"{slug}-{secrets.token_hex(2)}"
        return candidate

    def path_for(self, paper_id: str) -> Path:
        safe = re.sub(r"[^A-Za-z0-9._-]", "", paper_id)
        if not safe or safe in (".", ".."):
            raise ValueError(f"unsafe paper id {paper_id!r}")
        return self.directory / f"{safe}.json"

    def new_paper(self, title: str, variant: str = "student") -> Paper:
        paper = Paper(
            paper_id=self._make_id(title),
            title=title.strip(),
            variant=variant if variant in ("student", "professional") else "student",
            created_at=_now(),
            updated_at=_now(),
        )
        if paper.variant == "professional":
            paper.running_head = default_running_head(paper.title)
        self.save(paper)
        return paper

    def list_papers(self) -> list[dict[str, Any]]:
        summaries: list[dict[str, Any]] = []
        for path in sorted(self.directory.glob("*.json")):
            try:
                payload = json.loads(path.read_text("utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            paper = payload.get("paper", {})
            summaries.append({
                "paper_id": paper.get("paper_id", path.stem),
                "title": paper.get("title", ""),
                "variant": paper.get("variant", "student"),
                "words": len((paper.get("body") or "").split()),
                "references": len(paper.get("references", [])),
                "updated_at": paper.get("updated_at", ""),
            })
        summaries.sort(key=lambda s: s["updated_at"], reverse=True)
        return summaries

    def load(self, paper_id: str) -> Paper:
        path = self.path_for(paper_id)
        if not path.exists():
            raise FileNotFoundError(f"no paper named {paper_id!r}")
        payload = json.loads(path.read_text("utf-8"))
        return _paper_from_dict(payload.get("paper", {}))

    def save(self, paper: Paper) -> Path:
        paper.updated_at = _now()
        path = self.path_for(paper.paper_id)
        payload = {"schema_version": SCHEMA_VERSION, "saved_at": paper.updated_at,
                   "paper": to_jsonable(paper)}
        handle, temporary = tempfile.mkstemp(dir=str(self.directory), suffix=".tmp")
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                json.dump(payload, stream, indent=2, ensure_ascii=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        except BaseException:
            Path(temporary).unlink(missing_ok=True)
            raise
        return path

    def delete(self, paper_id: str) -> bool:
        path = self.path_for(paper_id)
        if not path.exists():
            return False
        path.unlink()
        return True


def to_jsonable(value: Any) -> Any:
    from enum import Enum
    if isinstance(value, Enum):
        return value.value
    if hasattr(value, "__dataclass_fields__"):
        return {f.name: to_jsonable(getattr(value, f.name))
                for f in dataclass_fields(value)}
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: to_jsonable(item) for key, item in value.items()}
    return value


def _paper_from_dict(data: dict[str, Any]) -> Paper:
    paper = Paper()
    for spec in dataclass_fields(Paper):
        if spec.name == "references":
            continue
        if spec.name in data and data[spec.name] is not None:
            setattr(paper, spec.name, data[spec.name])
    paper.references = [_work_from_dict(row) for row in data.get("references", [])]
    return paper


def _work_from_dict(data: dict[str, Any]) -> Work:
    work = Work()
    for spec in dataclass_fields(Work):
        if spec.name not in data or data[spec.name] is None:
            continue
        value = data[spec.name]
        if spec.name in ("authors", "editors"):
            setattr(work, spec.name,
                    [Author(**{k: v for k, v in row.items()
                               if k in {f.name for f in dataclass_fields(Author)}})
                     for row in value if isinstance(row, dict)])
        elif spec.name == "work_type":
            try:
                work.work_type = WorkType(value)
            except ValueError:
                work.work_type = WorkType.JOURNAL_ARTICLE
        else:
            try:
                setattr(work, spec.name, value)
            except Exception:                        # noqa: BLE001
                pass
    return work
