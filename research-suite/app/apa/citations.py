"""
APA 7th edition in-text citations and reference entries.

Written by hand rather than driven by a CSL style file, for three reasons:
the tricky parts of APA 7 (the et al. rules, disambiguation, group-author
abbreviation, the 21-author ellipsis) are exactly the parts a generic CSL
processor gets subtly wrong; every rule here is covered by a test that quotes
the manual section it comes from; and it keeps the tool working with no style
repository to fetch.

**Output is styled runs, not strings.** APA italicises the journal name and
volume but not the issue number or the article title, so a reference rendered
as one flat string is already wrong before it reaches the page. Every function
here returns `list[Run]`, and `plain()` is provided only for tests and logs.

Rule sources are cited inline as (APA, 2020, §x.y) against the *Publication
Manual of the American Psychological Association* (7th ed.).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..models import Author, Work, WorkType, normalise_doi

EN_DASH = "–"
ELLIPSIS = "…"

# APA 7 §9.8: list up to 20 authors; for 21 or more, give the first 19, an
# ellipsis, then the final author. No ampersand before the ellipsis.
MAX_LISTED_AUTHORS = 20
AUTHORS_BEFORE_ELLIPSIS = 19


@dataclass
class Run:
    """A span of text with one formatting flag. `italic` is the only one APA
    reference entries need."""

    text: str
    italic: bool = False


def plain(runs: list[Run]) -> str:
    return "".join(r.text for r in runs)


def _join(*groups: list[Run]) -> list[Run]:
    """Concatenate run lists and merge adjacent runs of the same style, so the
    docx writer emits one XML run per span instead of one per fragment."""
    out: list[Run] = []
    for group in groups:
        for run in group:
            if not run.text:
                continue
            if out and out[-1].italic == run.italic:
                out[-1] = Run(out[-1].text + run.text, run.italic)
            else:
                out.append(Run(run.text, run.italic))
    return out


def t(text: str) -> list[Run]:
    return [Run(text, False)]


def i(text: str) -> list[Run]:
    return [Run(text, True)]


# ============================================================ disambiguation


class CitationContext:
    """Holds the whole reference list so citations can be disambiguated.

    Three APA rules cannot be applied to one work in isolation, which is why
    they live here rather than on `Work`:

    * **Year letters** (APA 7 §8.19). Two works by the same author in the same
      year become 2020a and 2020b, lettered by the *title* order they take in
      the reference list — so you cannot assign the letter until you have
      sorted every reference.
    * **Expanded et al.** (APA 7 §8.18). When two works with three-or-more
      authors would both shorten to "Smith et al., 2020", you must give as many
      surnames as it takes to tell them apart. That needs the other work.
    * **Group abbreviations** (APA 7 §8.21). "Centers for Disease Control and
      Prevention (CDC)" is spelled out the first time and abbreviated after,
      which is state that must persist across the document.
    """

    def __init__(self, works: list[Work], group_abbreviations: dict[str, str] | None = None):
        self.works = sorted((w for w in works), key=lambda w: w.sort_key())
        for work in self.works:
            work.ensure_key()
        self._year_letter: dict[str, str] = {}
        self._etal_names: dict[str, int] = {}
        self._abbrev = dict(group_abbreviations or {})
        self._abbrev_seen: set[str] = set()
        self._assign_year_letters()
        self._assign_etal_depth()

    # -- year letters ------------------------------------------------------

    def _assign_year_letters(self) -> None:
        buckets: dict[tuple, list[Work]] = {}
        for work in self.works:
            names = tuple(a.sort_key() for a in (work.authors or work.editors))
            buckets.setdefault((names, work.year[:4]), []).append(work)
        for (_, year), group in buckets.items():
            if len(group) < 2 or not year:
                continue
            # Already sorted by title inside sort_key(), so index order is
            # reference-list order.
            for index, work in enumerate(group):
                if index < 26:
                    self._year_letter[work.key] = chr(ord("a") + index)
                else:  # 27+ same-author-same-year works: aa, ab, ...
                    first, second = divmod(index - 26, 26)
                    self._year_letter[work.key] = chr(ord("a") + first) + chr(ord("a") + second)

    def year_of(self, work: Work) -> str:
        """The year as it must be printed, including any disambiguating letter."""
        year = work.year.strip() or "n.d."
        if year.lower().startswith("n.d"):
            base = "n.d."
        else:
            base = year[:4]
        letter = self._year_letter.get(work.key, "")
        return f"{base}{letter}"

    # -- expanded et al. ---------------------------------------------------

    def _assign_etal_depth(self) -> None:
        """How many surnames each 3+-author work must show before "et al."."""
        shortened: dict[tuple[str, str], list[Work]] = {}
        for work in self.works:
            authors = work.authors or work.editors
            if len(authors) < 3:
                continue
            key = (authors[0].intext_name(), self.year_of(work))
            shortened.setdefault(key, []).append(work)

        for group in shortened.values():
            if len(group) < 2:
                continue
            # Walk out from the second surname until every work in the clash
            # group is distinguishable, per APA 7 §8.18.
            depth = 1
            max_len = max(len(w.authors or w.editors) for w in group)
            while depth < max_len:
                depth += 1
                seen = {
                    tuple(
                        a.intext_name()
                        for a in (w.authors or w.editors)[:depth]
                    )
                    for w in group
                }
                if len(seen) == len(group):
                    break
            for work in group:
                self._etal_names[work.key] = depth

    def etal_depth(self, work: Work) -> int:
        return self._etal_names.get(work.key, 1)

    # -- group abbreviation ------------------------------------------------

    def abbreviation_for(self, name: str) -> str:
        return self._abbrev.get(name, "")

    def take_group_form(self, name: str) -> str:
        """Spelled-out-with-abbreviation on first use, abbreviation after.

        Mutating state on read is deliberate: APA's rule *is* order-dependent,
        so the first call for a given group is the first appearance in the
        document, and there is nowhere else that fact lives.
        """
        abbrev = self._abbrev.get(name)
        if not abbrev:
            return name
        if name in self._abbrev_seen:
            return abbrev
        self._abbrev_seen.add(name)
        return f"{name} [{abbrev}]"

    def reset_group_state(self) -> None:
        """Call before re-rendering a document so first-use logic repeats."""
        self._abbrev_seen.clear()


# ============================================================= in-text names


def _intext_author_string(
    work: Work,
    context: CitationContext,
    narrative: bool,
) -> str:
    """The author portion of an in-text citation (APA 7 §8.17).

    One author: Smith. Two: Smith & Jones (parenthetical) / Smith and Jones
    (narrative). Three or more: Smith et al. — from the very first citation,
    which is the change from APA 6 that most reference software still gets
    wrong.
    """
    authors = work.authors or work.editors
    if not authors:
        return ""

    if authors[0].is_group and len(authors) == 1:
        return context.take_group_form(authors[0].intext_name())

    names = [a.intext_name() for a in authors]
    conjunction = "and" if narrative else "&"

    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} {conjunction} {names[1]}"

    depth = context.etal_depth(work)
    if depth >= len(names):
        # Every surname is needed; APA still uses "et al." only when a name is
        # being omitted, so with none omitted we join the full list.
        return ", ".join(names[:-1]) + f", {conjunction} {names[-1]}"
    shown = ", ".join(names[:depth])
    return f"{shown}, et al." if depth > 1 else f"{shown} et al."


def _no_author_stand_in(work: Work) -> tuple[str, bool]:
    """APA 7 §8.14: with no author, the title moves into the author slot —
    italicised for standalone works, in quotation marks for parts of works."""
    title = _sentence_case(work.title).rstrip(".")
    words = title.split()
    short = " ".join(words[:4]) + (ELLIPSIS if len(words) > 4 else "")
    standalone = work.work_type in (
        WorkType.BOOK, WorkType.REPORT, WorkType.WEBPAGE,
        WorkType.DATASET, WorkType.THESIS, WorkType.GUIDELINE,
    )
    return (short, standalone)


def intext(
    works: Work | list[Work],
    context: CitationContext,
    *,
    narrative: bool = False,
    locator: str = "",
) -> list[Run]:
    """Render one in-text citation covering one or more works.

    `narrative` produces ``Smith and Jones (2021)`` for use inside a sentence;
    the default parenthetical form produces ``(Smith & Jones, 2021)``.
    `locator` is appended for direct quotations and specific passages —
    ``p. 14``, ``pp. 14-15``, ``para. 3``, ``Table 2`` (APA 7 §8.13).
    """
    items = [works] if isinstance(works, Work) else list(works)
    if not items:
        return []

    # APA 7 §8.12: multiple works in one parenthesis go in the same order as
    # the reference list, separated by semicolons.
    items = sorted(items, key=lambda w: w.sort_key())

    # Same author across several years collapses to one name (APA 7 §8.12).
    #
    # The author string is resolved exactly once per work, because
    # `_intext_author_string` consumes the group-author first-use state — call
    # it twice for the same citation and the first appearance of "Centers for
    # Disease Control and Prevention [CDC]" silently becomes "(CDC, 2023)".
    grouped: list[tuple[Work, str, list[str]]] = []
    for work in items:
        author_str = _intext_author_string(work, context, narrative)
        year = context.year_of(work)
        if grouped and grouped[-1][1] == author_str and author_str:
            grouped[-1][2].append(year)
        else:
            grouped.append((work, author_str, [year]))

    if narrative:
        if len(grouped) != 1:
            # Narrative form only makes sense for a single work; fall back to
            # parenthetical rather than emit something APA has no rule for.
            return intext(items, context, narrative=False, locator=locator)
        work, name, years = grouped[0]
        if not name:
            stand_in, italic = _no_author_stand_in(work)
            head = i(stand_in) if italic else t(f"“{stand_in}”")
            return _join(head, t(f" ({', '.join(years)}{_loc(locator)})"))
        return _join(t(f"{name} ({', '.join(years)}{_loc(locator)})"))

    chunks: list[list[Run]] = []
    for work, name, years in grouped:
        if name:
            chunks.append(t(f"{name}, {', '.join(years)}"))
        else:
            stand_in, italic = _no_author_stand_in(work)
            head = i(stand_in) if italic else t(f"“{stand_in}”")
            chunks.append(_join(head, t(f", {', '.join(years)}")))

    body: list[Run] = []
    for index, chunk in enumerate(chunks):
        if index:
            body = _join(body, t("; "))
        body = _join(body, chunk)
    return _join(t("("), body, t(_loc(locator)), t(")"))


def preview_author(work: Work, context: CitationContext, narrative: bool = False) -> str:
    """The author string a citation *would* use, without consuming first-use
    state. For UI previews and logs only — never for rendering a document."""
    authors = work.authors or work.editors
    if not authors:
        return ""
    if authors[0].is_group and len(authors) == 1:
        name = authors[0].intext_name()
        abbrev = context.abbreviation_for(name)
        return f"{name} [{abbrev}]" if abbrev else name
    return _intext_author_string(work, context, narrative)


def _loc(locator: str) -> str:
    if not locator:
        return ""
    locator = locator.strip().rstrip(",")
    return f", {locator}"


def format_locator(kind: str, value: str) -> str:
    """Build an APA-correct locator. ``page`` with a range becomes ``pp.`` and
    an en dash (APA 7 §8.13, §6.6)."""
    value = value.strip()
    if not value:
        return ""
    if kind == "page":
        ranged = re.search(r"[-–]", value)
        prefix = "pp." if ranged or "," in value else "p."
        return f"{prefix} {value.replace('-', EN_DASH)}"
    if kind == "paragraph":
        return f"para. {value}"
    if kind == "section":
        return f"Section {value}"
    return value


# ========================================================== reference entries


def reference(work: Work, context: CitationContext) -> list[Run]:
    """One reference-list entry, as styled runs."""
    author_part = _reference_authors(work, context)
    year_part = t(f"({context.year_of(work)}). ")

    builder = {
        WorkType.JOURNAL_ARTICLE: _ref_journal,
        WorkType.PREPRINT: _ref_journal,
        WorkType.CONFERENCE_PAPER: _ref_journal,
        WorkType.BOOK: _ref_book,
        WorkType.BOOK_CHAPTER: _ref_chapter,
        WorkType.REPORT: _ref_report,
        WorkType.GUIDELINE: _ref_report,
        WorkType.DATASET: _ref_dataset,
        WorkType.THESIS: _ref_thesis,
        WorkType.WEBPAGE: _ref_webpage,
    }.get(work.work_type, _ref_journal)

    entry = _join(author_part, year_part, builder(work))
    if work.retracted:
        # APA 7 §10.1 example 10: a retraction is part of the citation, not a
        # footnote. Printing the article without it would misrepresent it.
        note = work.retraction_note or "Retraction notice"
        entry = _join(entry, t(f" [Retracted; {note}]"))
    return _tidy(entry)


def _reference_authors(work: Work, context: CitationContext) -> list[Run]:
    authors = work.authors
    if not authors and work.editors:
        names = _author_list(work.editors)
        label = "Ed." if len(work.editors) == 1 else "Eds."
        return t(f"{names} ({label}). ")
    if not authors:
        # No author at all: the title takes the author slot (APA 7 §9.12) and
        # the body builder must not repeat it.
        return []
    return t(f"{_author_list(authors)} ")


def _author_list(authors: list[Author]) -> str:
    """APA 7 §9.8. Ampersand before the last name; 21+ authors get an ellipsis
    after the 19th and then the final author, with no ampersand."""
    names = [a.reference_name() for a in authors]
    if len(names) == 1:
        return _period(names[0])
    if len(names) <= MAX_LISTED_AUTHORS:
        return _period(", ".join(names[:-1]) + f", & {names[-1]}")
    head = ", ".join(names[:AUTHORS_BEFORE_ELLIPSIS])
    return _period(f"{head}, {ELLIPSIS} {names[-1]}")


def _period(text: str) -> str:
    """Close the author group with exactly one period — initials already end in
    one, and "Smith, J. A.." is the classic double-period bug."""
    return text if text.endswith(".") else text + "."


def _ref_journal(work: Work) -> list[Run]:
    out = _title_slot(work, italic=False)
    if work.container:
        out = _join(out, i(_title_case(work.container)))
        if work.volume:
            out = _join(out, t(", "), i(work.volume))
            if work.issue:
                out = _join(out, t(f"({work.issue})"))
        if work.pages:
            out = _join(out, t(f", {_pages(work.pages)}"))
        out = _join(out, t("."))
    out = _join(out, _doi_or_url(work))
    return out


def _ref_book(work: Work) -> list[Run]:
    out = _title_slot(work, italic=True, suppress_period=True)
    bracket = []
    if work.edition:
        bracket.append(_edition(work.edition))
    out = _join(out, t(f" ({'; '.join(bracket)})") if bracket else t(""), t(". "))
    if work.publisher:
        out = _join(out, t(f"{work.publisher}."))
    return _join(out, _doi_or_url(work))


def _ref_chapter(work: Work) -> list[Run]:
    out = _title_slot(work, italic=False)
    # APA 7 §9.9: editors in the "In" position are given initials-first, with
    # an ampersand before the last — not the surname-first form used in the
    # author slot.
    names = [
        e.family if e.is_group else f"{e.initials()} {e.family}".strip()
        for e in work.editors
    ]
    if len(names) == 1:
        editors = names[0]
    elif len(names) == 2:
        editors = f"{names[0]} & {names[1]}"
    elif names:
        editors = ", ".join(names[:-1]) + f", & {names[-1]}"
    else:
        editors = ""
    label = "Ed." if len(work.editors) == 1 else "Eds."
    if editors:
        out = _join(out, t(f"In {editors} ({label}), "))
    else:
        out = _join(out, t("In "))
    out = _join(out, i(_sentence_case(work.container)))
    detail = []
    if work.edition:
        detail.append(_edition(work.edition))
    if work.pages:
        detail.append(f"pp. {_pages(work.pages)}")
    if detail:
        out = _join(out, t(f" ({', '.join(detail)})"))
    out = _join(out, t(". "))
    if work.publisher:
        out = _join(out, t(f"{work.publisher}."))
    return _join(out, _doi_or_url(work))


def _ref_report(work: Work) -> list[Run]:
    out = _title_slot(work, italic=True, suppress_period=True)
    if work.report_number:
        out = _join(out, t(f" ({_report_label(work.report_number)})"))
    out = _join(out, t(". "))
    # APA 7 §9.11: omit the publisher when it is the same as the author, which
    # is the normal case for CDC and WHO reports.
    author_names = {a.family for a in work.authors if a.is_group}
    if work.publisher and work.publisher not in author_names:
        out = _join(out, t(f"{work.publisher}."))
    return _join(out, _doi_or_url(work))


def _ref_dataset(work: Work) -> list[Run]:
    out = _title_slot(work, italic=True, suppress_period=True)
    out = _join(out, t(" [Data set]. "))
    if work.publisher:
        out = _join(out, t(f"{work.publisher}."))
    return _join(out, _doi_or_url(work))


def _ref_thesis(work: Work) -> list[Run]:
    out = _title_slot(work, italic=True, suppress_period=True)
    kind = "Doctoral dissertation" if "dissert" in (work.raw.get("degree", "") or "").lower() \
        else work.raw.get("thesis_kind", "Doctoral dissertation")
    institution = work.publisher or work.raw.get("institution", "")
    out = _join(out, t(f" [{kind}, {institution}]. " if institution else f" [{kind}]. "))
    if work.container:
        out = _join(out, t(f"{work.container}."))
    return _join(out, _doi_or_url(work))


def _ref_webpage(work: Work) -> list[Run]:
    out = _title_slot(work, italic=True)
    # The site name is omitted when it duplicates the author (APA 7 §10.16).
    author_names = {a.family for a in work.authors}
    if work.container and work.container not in author_names:
        out = _join(out, t(f"{work.container}. "))
    return _join(out, _doi_or_url(work))


def _title_slot(work: Work, *, italic: bool, suppress_period: bool = False) -> list[Run]:
    """The title, in sentence case, italic or not depending on work type."""
    title = _sentence_case(work.title).rstrip(". ")
    if not title:
        return []
    runs = i(title) if italic else t(title)
    if suppress_period:
        return runs
    return _join(runs, t(". "))


def _doi_or_url(work: Work) -> list[Run]:
    """APA 7 §9.34-9.36: a DOI is printed as an https://doi.org/ link, with no
    "doi:" prefix and no "Retrieved from". A URL is used only when there is no
    DOI."""
    if work.doi:
        return t(f" https://doi.org/{normalise_doi(work.doi)}")
    target = work.open_access_url or work.url
    if target:
        return t(f" {target.strip()}")
    return []


def _pages(pages: str) -> str:
    """Normalise to an en dash and expand elided ranges (412-8 -> 412-418)."""
    pages = pages.strip().replace("--", EN_DASH).replace("-", EN_DASH)
    match = re.fullmatch(rf"(\d+)\s*{EN_DASH}\s*(\d+)", pages)
    if match:
        start, end = match.group(1), match.group(2)
        if len(end) < len(start):
            end = start[: len(start) - len(end)] + end
        return f"{start}{EN_DASH}{end}"
    return pages


def _edition(edition: str) -> str:
    edition = edition.strip()
    if re.fullmatch(r"\d+", edition):
        return f"{_ordinal(int(edition))} ed."
    if "ed" not in edition.lower():
        return f"{edition} ed."
    return edition


def _ordinal(n: int) -> str:
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _report_label(number: str) -> str:
    number = number.strip()
    if re.match(r"(?i)(report|publication|no\.|pub\.)", number):
        return number
    return f"Report No. {number}"


# --------------------------------------------------------------------- casing

# Words kept lowercase inside a title-cased journal name, unless they are the
# first or last word (APA 7 §6.17).
_MINOR_WORDS = {
    "a", "an", "and", "as", "at", "but", "by", "for", "if", "in", "nor", "of",
    "off", "on", "or", "per", "so", "the", "to", "up", "via", "vs", "with",
}

# Proper nouns that must keep their capitalisation when a title is folded to
# sentence case. Mechanical lowercasing otherwise produces visibly wrong output
# ("united states", "medicare", "type 2 diabetes").
#
# **Acronyms are deliberately absent.** Any run of two or more capitals in the
# source title is preserved by `_ACRONYM_RE` below, which is both more general
# and — critically — case-sensitive. An earlier version listed acronyms here
# and matched them case-insensitively, which turned "patients who received
# care" into "patients WHO received care" and "a device that aids recovery"
# into "a device that AIDS recovery". Short acronyms collide with ordinary
# English words often enough that case-insensitive matching is simply unsafe.
_PROPER_NOUNS = {
    "United States", "United Kingdom", "Europe", "European", "Africa", "Asia",
    "Australia", "Canada", "Mexico", "China", "India", "Japan",
    "Medicare", "Medicaid", "Healthy People", "Black", "White", "Hispanic",
    "Latino", "Latina", "Latinx", "Indigenous", "Native American",
    "Alaska Native", "Pacific Islander", "Appalachian",
    "English", "Spanish", "Somali", "Hmong",
    "Type 1", "Type 2", "Alzheimer", "Parkinson", "Crohn", "Down",
    "Medicaid Expansion", "Affordable Care Act", "Joanna Briggs",
    "Cochrane", "Magnet", "Healthy Start",
}

# Mixed-case terms the acronym pattern cannot express (a lowercase letter in
# the middle breaks the all-capitals run).
_MIXED_CASE_TERMS = {"SARS-CoV-2", "MERS-CoV", "HbA1c", "pH", "mRNA", "rRNA", "tRNA"}

# Any capitalised acronym run, with optional hyphenated numeric or capital
# tails: COVID-19, SARS, HIV, ICD-10, HEDIS, PM2.5-style tokens.
_ACRONYM_RE = re.compile(r"\b(?:[A-Z]{2,}(?:[-–][A-Z0-9]+)*|[A-Z]\w*[A-Z]\w*)\b")

_STASH = "\x00"


def _sentence_case(title: str) -> str:
    """Sentence case per APA 7 §6.16 — capitalise the first word, the first
    word after a colon or dash, and proper nouns; lowercase the rest.

    Titles that arrive already in sentence case are returned essentially
    untouched; the transformation only bites on the Title Case that many
    databases store.
    """
    title = " ".join(title.split())
    if not title:
        return ""

    if not _is_title_case(title):
        return title

    protected: list[tuple[str, str]] = []

    def stash(match: re.Match) -> str:
        token = f"{_STASH}{len(protected)}{_STASH}"
        protected.append((token, match.group(0)))
        return token

    # Longest first, so "United States" is taken before "United".
    # Case-sensitive: in a Title Cased source every content word is already
    # capitalised, so matching case-insensitively would buy nothing and would
    # reintroduce the "who"/"aids" collisions described above.
    for term in sorted(_MIXED_CASE_TERMS | _PROPER_NOUNS, key=len, reverse=True):
        title = re.sub(rf"\b{re.escape(term)}\b", stash, title)

    title = _ACRONYM_RE.sub(stash, title)

    out = _capitalise_sentence_starts(title.lower())

    for token, original in protected:
        # The token survived .lower() only in its digits, so match the lowered
        # form first and the original form as a fallback.
        out = out.replace(token.lower(), original).replace(token, original)
    return out


def _is_title_case(title: str) -> bool:
    """True when the string looks mechanically Title Cased.

    The test is whether several *minor* words are capitalised — a genuine
    sentence-case title has "the" and "of" in lowercase, while a Title Cased
    one usually capitalises at least some of them. Counting only content words
    would misfire on titles that are mostly proper nouns.
    """
    words = [w for w in re.findall(r"[A-Za-z][A-Za-z'-]*", title)]
    if len(words) < 4:
        return False
    minor = [w for w in words[1:-1] if w.lower() in _MINOR_WORDS]
    if not minor:
        # No minor words to judge by: fall back to how many content words are
        # capitalised.
        content = [w for w in words[1:] if len(w) > 3]
        if not content:
            return False
        capped = sum(1 for w in content if w[0].isupper() and not w.isupper())
        return capped / len(content) > 0.6
    return sum(1 for w in minor if w[0].isupper()) / len(minor) > 0.5


def _capitalise_sentence_starts(text: str) -> str:
    """Capitalise the first word, and the first word after a colon, em dash, or
    terminal punctuation (APA 7 §6.16).

    A stashed proper noun or acronym satisfies the sentence start on its own —
    otherwise a title beginning "COVID-19 vaccination uptake" would come back
    as "COVID-19 Vaccination uptake", because the capitalisation would skip
    past the placeholder and land on the following word.
    """
    out = list(text)
    capitalise_next = True
    for index, char in enumerate(out):
        if char == _STASH:
            capitalise_next = False
        elif capitalise_next and char.isalpha():
            out[index] = char.upper()
            capitalise_next = False
        elif char in ":?!" or (char == "." and index + 1 < len(out) and out[index + 1] == " "):
            capitalise_next = True
        elif char in (EN_DASH, "—"):
            capitalise_next = True
    return "".join(out)


def _title_case(name: str) -> str:
    """Title case for journal names (APA 7 §6.17) — every major word
    capitalised, minor words lowercase unless first or last."""
    name = " ".join(name.split())
    if not name:
        return ""
    if name.isupper() and len(name) > 6:
        name = name.title()  # "JOURNAL OF NURSING" arrives shouting from some indexes
    words = name.split(" ")
    out: list[str] = []
    for index, word in enumerate(words):
        bare = word.strip("()[]:,.")
        if index not in (0, len(words) - 1) and bare.lower() in _MINOR_WORDS:
            out.append(word.lower())
        elif bare.isupper() and len(bare) <= 5:
            out.append(word)  # BMJ, JAMA, PLOS
        elif word[:1].isalpha():
            out.append(word[0].upper() + word[1:])
        else:
            out.append(word)
    return " ".join(out)


def _tidy(runs: list[Run]) -> list[Run]:
    """Collapse the double spaces and doubled periods that segment assembly
    leaves behind, without touching italic boundaries."""
    merged = _join(runs)
    for run in merged:
        run.text = re.sub(r"\s{2,}", " ", run.text)
        run.text = re.sub(r"\.\.(?!\.)", ".", run.text)
        run.text = run.text.replace(" ,", ",").replace(" .", ".")
    while merged and not merged[-1].text.strip():
        merged.pop()
    if merged:
        merged[-1].text = merged[-1].text.rstrip()
    return [r for r in merged if r.text]


# ------------------------------------------------------------- reference list


def reference_list(works: list[Work], context: CitationContext) -> list[list[Run]]:
    """Every entry, in APA order (APA 7 §9.44-9.49): alphabetical by the first
    author's surname, then by year, then by title."""
    return [reference(w, context) for w in sorted(works, key=lambda w: w.sort_key())]
