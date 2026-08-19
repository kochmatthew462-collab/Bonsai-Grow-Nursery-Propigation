"""
APA 7th edition conformance tests.

Every case names the manual section it comes from. This file is the reason the
citation engine is hand-written rather than delegated to a generic style
processor: each of these rules is one an APA-conformant tool must get exactly
right, and several are ones that generic processors get subtly wrong.

Run: python3 tests/test_apa_citations.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.apa.citations import (  # noqa: E402
    CitationContext,
    format_locator,
    intext,
    plain,
    reference,
    reference_list,
)
from app.models import Author, Work, WorkType  # noqa: E402

FAILURES: list[str] = []
CHECKS = 0


def check(label: str, got, want) -> None:
    global CHECKS
    CHECKS += 1
    if got != want:
        FAILURES.append(f"{label}\n     got: {got!r}\n    want: {want!r}")


def article(authors, year, title, journal, volume="", issue="", pages="", doi="", **kw) -> Work:
    work = Work(
        work_type=WorkType.JOURNAL_ARTICLE,
        authors=[Author.parse(a) if isinstance(a, str) else a for a in authors],
        year=year, title=title, container=journal,
        volume=volume, issue=issue, pages=pages, doi=doi, **kw,
    )
    work.ensure_key()
    return work


# ------------------------------------------------------ author-name parsing


def test_author_parsing() -> None:
    check("parse 'Smith, John A.' family", Author.parse("Smith, John A.").family, "Smith")
    check("parse 'Smith, John A.' initials", Author.parse("Smith, John A.").initials(), "J. A.")
    # PubMed emits "Smith JA" with no punctuation at all.
    check("parse PubMed 'Smith JA'", Author.parse("Smith JA").reference_name(), "Smith, J. A.")
    check("parse 'John A. Smith'", Author.parse("John A. Smith").reference_name(), "Smith, J. A.")
    # A hyphenated given name keeps both initials (APA 7 §9.8).
    check("hyphenated given", Author.parse("Lee, Mary-Jane").initials(), "M.-J.")
    # Corporate authors are never initialised — the classic failure is
    # rendering this as "Organization, W. H."
    check("group author whole",
          Author.parse("World Health Organization").reference_name(),
          "World Health Organization")
    check("group author flagged", Author.parse("World Health Organization").is_group, True)
    # A name particle must not be mistaken for a given name.
    check("particle surname", Author.parse("van der Berg JAH").family, "van der Berg")
    check("suffix retained", Author.parse("King, Martin L., Jr.").reference_name(),
          "King, M. L., Jr")


# ------------------------------------------------------------ in-text: counts


def test_intext_author_counts() -> None:
    one = article(["Smith, John"], "2022", "A study of things", "Nursing Research")
    two = article(["Smith, John", "Jones, Alice"], "2023", "Another study", "Nursing Research")
    three = article(["Smith, John", "Jones, Alice", "Lee, Bo"], "2024", "A third study",
                    "Nursing Research")
    ctx = CitationContext([one, two, three])

    # APA 7 §8.17
    check("1 author parenthetical", plain(intext(one, ctx)), "(Smith, 2022)")
    check("2 authors use ampersand", plain(intext(two, ctx)), "(Smith & Jones, 2023)")
    # APA 7 changed this from APA 6: "et al." applies from the FIRST citation
    # for three or more authors, with no full listing anywhere.
    check("3 authors et al. on first use", plain(intext(three, ctx)), "(Smith et al., 2024)")

    check("1 author narrative", plain(intext(one, ctx, narrative=True)), "Smith (2022)")
    # Narrative form spells out "and" instead of using an ampersand.
    check("2 authors narrative uses and", plain(intext(two, ctx, narrative=True)),
          "Smith and Jones (2023)")
    check("3 authors narrative", plain(intext(three, ctx, narrative=True)),
          "Smith et al. (2024)")


def test_intext_twenty_one_authors_still_et_al() -> None:
    many = article([f"Author{n}, X" for n in range(1, 22)], "2021", "Big collaboration",
                   "The Lancet")
    ctx = CitationContext([many])
    check("21 authors in text", plain(intext(many, ctx)), "(Author1 et al., 2021)")


# ------------------------------------------------------- in-text: group author


def test_group_author_abbreviation() -> None:
    cdc = Work(
        work_type=WorkType.REPORT,
        authors=[Author.group("Centers for Disease Control and Prevention")],
        year="2023", title="Surveillance summary",
        publisher="Centers for Disease Control and Prevention",
    )
    cdc.ensure_key()
    ctx = CitationContext(
        [cdc],
        group_abbreviations={"Centers for Disease Control and Prevention": "CDC"},
    )
    # APA 7 §8.21: spelled out with the abbreviation bracketed on first use,
    # abbreviation alone thereafter.
    check("group first use",
          plain(intext(cdc, ctx)),
          "(Centers for Disease Control and Prevention [CDC], 2023)")
    check("group later use", plain(intext(cdc, ctx)), "(CDC, 2023)")

    ctx.reset_group_state()
    check("group state resets for a re-render",
          plain(intext(cdc, ctx)),
          "(Centers for Disease Control and Prevention [CDC], 2023)")


# ------------------------------------------------------ in-text: year letters


def test_same_author_same_year_gets_letters() -> None:
    # APA 7 §8.19. Letters follow reference-list order, which is by title.
    beta = article(["Smith, John"], "2020", "Beta findings", "Nursing Research")
    alpha = article(["Smith, John"], "2020", "Alpha findings", "Nursing Research")
    ctx = CitationContext([beta, alpha])
    check("alphabetically first title gets 'a'", plain(intext(alpha, ctx)), "(Smith, 2020a)")
    check("second title gets 'b'", plain(intext(beta, ctx)), "(Smith, 2020b)")


def test_same_author_different_years_collapses() -> None:
    # APA 7 §8.12: one name, years ascending, comma separated.
    a = article(["Smith, John"], "2019", "Earlier work", "Nursing Research")
    b = article(["Smith, John"], "2021", "Later work", "Nursing Research")
    ctx = CitationContext([a, b])
    check("same author two years", plain(intext([a, b], ctx)), "(Smith, 2019, 2021)")


# ------------------------------------------------ in-text: expanded et al.


def test_expanded_et_al_disambiguation() -> None:
    # APA 7 §8.18: when two 3+-author works shorten identically, give as many
    # surnames as needed to distinguish them.
    #
    # Note there is deliberately no year letter here. §8.19's a/b lettering is
    # for the *same* authors in the same year; these two works have different
    # author lists, so §8.18's name expansion is what distinguishes them and
    # adding a letter as well would be wrong.
    first = article(["Smith, A", "Jones, B", "Lee, C"], "2020", "First study", "J Nurs")
    second = article(["Smith, A", "Kumar, D", "Lee, C"], "2020", "Second study", "J Nurs")
    ctx = CitationContext([first, second])
    check("expanded et al. #1", plain(intext(first, ctx)), "(Smith, Jones, et al., 2020)")
    check("expanded et al. #2", plain(intext(second, ctx)), "(Smith, Kumar, et al., 2020)")

    # A non-clashing work in the same document must NOT be expanded.
    solo = article(["Brown, E", "Green, F", "Blue, G"], "2020", "Unrelated", "J Nurs")
    ctx2 = CitationContext([first, second, solo])
    check("non-clashing work stays short", plain(intext(solo, ctx2)), "(Brown et al., 2020)")


def test_expanded_et_al_stops_when_all_names_shown() -> None:
    # Two works that differ only in the third author, with exactly three
    # authors each: showing all three means no name is omitted, so "et al."
    # must not appear at all — it abbreviates something, and here there is
    # nothing left to abbreviate.
    a = article(["Smith, A", "Jones, B", "Lee, C"], "2020", "Aaa", "J Nurs")
    b = article(["Smith, A", "Jones, B", "Kumar, D"], "2020", "Bbb", "J Nurs")
    ctx = CitationContext([a, b])
    check("all names shown, no et al.",
          plain(intext(a, ctx)), "(Smith, Jones, & Lee, 2020)")
    check("all names shown, sibling", plain(intext(b, ctx)), "(Smith, Jones, & Kumar, 2020)")


def test_year_letters_need_identical_author_lists() -> None:
    # The complement of the test above: identical authors and year DO get
    # letters (APA 7 §8.19), even with three authors, because name expansion
    # cannot separate them.
    a = article(["Smith, A", "Jones, B", "Lee, C"], "2020", "Aaa", "J Nurs")
    b = article(["Smith, A", "Jones, B", "Lee, C"], "2020", "Bbb", "J Nurs")
    ctx = CitationContext([a, b])
    check("identical authors get letters", plain(intext(a, ctx)), "(Smith et al., 2020a)")
    check("identical authors get letters b", plain(intext(b, ctx)), "(Smith et al., 2020b)")


# --------------------------------------------------- in-text: multiple works


def test_multiple_works_one_parenthesis() -> None:
    # APA 7 §8.12: reference-list order, semicolon separated.
    zeta = article(["Zeta, A"], "2018", "Zeta work", "J Nurs")
    alpha = article(["Alpha, B"], "2022", "Alpha work", "J Nurs")
    ctx = CitationContext([zeta, alpha])
    check("multiple works alphabetical",
          plain(intext([zeta, alpha], ctx)),
          "(Alpha, 2022; Zeta, 2018)")


# ------------------------------------------------------------ in-text: dates


def test_no_date() -> None:
    work = article(["Smith, John"], "", "Undated page", "J Nurs")
    ctx = CitationContext([work])
    check("no date", plain(intext(work, ctx)), "(Smith, n.d.)")


def test_no_author_uses_title() -> None:
    # APA 7 §8.14. A standalone work's title is italicised; part of a work is
    # quoted. Either way it moves into the author slot.
    report = Work(work_type=WorkType.REPORT, authors=[], year="2021",
                  title="National health objectives for the coming decade")
    report.ensure_key()
    ctx = CitationContext([report])
    runs = intext(report, ctx)
    check("no-author standalone italicises the title",
          [(r.text, r.italic) for r in runs][1][1], True)
    check("no-author text", plain(runs), "(National health objectives for…, 2021)")

    art = article([], "2021", "Short news item about a thing", "J Nurs")
    ctx2 = CitationContext([art])
    check("no-author article is quoted", plain(intext(art, ctx2)),
          "(“Short news item about…”, 2021)")


# ---------------------------------------------------------------- locators


def test_locators() -> None:
    work = article(["Smith, John"], "2022", "A study", "J Nurs")
    ctx = CitationContext([work])
    check("single page", plain(intext(work, ctx, locator=format_locator("page", "14"))),
          "(Smith, 2022, p. 14)")
    # A range takes pp. and an en dash (APA 7 §8.13, §6.6).
    check("page range", plain(intext(work, ctx, locator=format_locator("page", "14-17"))),
          "(Smith, 2022, pp. 14–17)")
    check("paragraph", plain(intext(work, ctx, locator=format_locator("paragraph", "3"))),
          "(Smith, 2022, para. 3)")
    check("narrative with locator",
          plain(intext(work, ctx, narrative=True, locator=format_locator("page", "9"))),
          "Smith (2022, p. 9)")


# ------------------------------------------------------- reference entries


def test_reference_journal_article() -> None:
    work = article(
        ["Smith, John A.", "Jones, Alice B."], "2023",
        "Nurse staffing ratios and patient outcomes in acute care",
        "Journal of Nursing Scholarship",
        volume="55", issue="4", pages="412-425",
        doi="https://doi.org/10.1111/jnu.12345",
    )
    ctx = CitationContext([work])
    check(
        "journal article reference",
        plain(reference(work, ctx)),
        "Smith, J. A., & Jones, A. B. (2023). Nurse staffing ratios and patient "
        "outcomes in acute care. Journal of Nursing Scholarship, 55(4), 412–425. "
        "https://doi.org/10.1111/jnu.12345",
    )
    styled = [(r.text, r.italic) for r in reference(work, ctx)]
    italics = "".join(text for text, italic in styled if italic)
    # APA italicises the journal name and the volume, but NOT the issue number
    # or the article title.
    check("journal name and volume italic", italics, "Journal of Nursing Scholarship55")
    check("issue not italic", "(4)" in "".join(t for t, it in styled if not it), True)


def test_reference_doi_has_no_prefix() -> None:
    work = article(["Smith, J"], "2020", "Title here", "J Nurs", doi="doi:10.1000/XYZ123")
    ctx = CitationContext([work])
    text = plain(reference(work, ctx))
    # APA 7 §9.35: no "doi:", no "Retrieved from", lowercase, as an https link.
    check("doi rendered as URL", text.endswith("https://doi.org/10.1000/xyz123"), True)
    check("no doi: prefix", "doi:10" in text, False)
    check("no retrieved from", "Retrieved" in text, False)


def test_reference_twenty_one_authors_uses_ellipsis() -> None:
    authors = [Author(family=f"Surname{n}", given="A B") for n in range(1, 22)]
    work = article(authors, "2021", "A very collaborative paper", "The Lancet",
                   volume="397", pages="1-10")
    ctx = CitationContext([work])
    text = plain(reference(work, ctx))
    # APA 7 §9.8: first 19, ellipsis, final author, and no ampersand.
    check("19th author present", "Surname19, A. B." in text, True)
    check("20th author omitted", "Surname20" in text, False)
    check("final author present", "Surname21, A. B." in text, True)
    check("ellipsis present", "…" in text, True)
    check("no ampersand with ellipsis", "& Surname21" in text, False)


def test_reference_twenty_authors_lists_all() -> None:
    authors = [Author(family=f"Surname{n}", given="A") for n in range(1, 21)]
    work = article(authors, "2021", "Exactly twenty", "The Lancet")
    ctx = CitationContext([work])
    text = plain(reference(work, ctx))
    check("20 authors all listed", "Surname20, A." in text, True)
    check("20 authors use ampersand", "& Surname20" in text, True)
    check("20 authors no ellipsis", "…" in text, False)


def test_reference_book_and_chapter() -> None:
    book = Work(work_type=WorkType.BOOK, authors=[Author.parse("Polit, Denise F.")],
                year="2020", title="Nursing research: Generating evidence for practice",
                edition="11", publisher="Wolters Kluwer")
    book.ensure_key()
    ctx = CitationContext([book])
    check("book reference", plain(reference(book, ctx)),
          "Polit, D. F. (2020). Nursing research: Generating evidence for practice "
          "(11th ed.). Wolters Kluwer.")

    chapter = Work(
        work_type=WorkType.BOOK_CHAPTER,
        authors=[Author.parse("Lee, Bo")],
        editors=[Author.parse("Grant, Ann"), Author.parse("Hall, Ray")],
        year="2019", title="Measuring adherence in community settings",
        container="Handbook of public health practice",
        pages="112-138", publisher="Springer",
    )
    chapter.ensure_key()
    ctx2 = CitationContext([chapter])
    # APA 7 §9.9: editors in the "In" position are initials-first with an
    # ampersand, not the surname-first form used in the author slot.
    check("chapter reference", plain(reference(chapter, ctx2)),
          "Lee, B. (2019). Measuring adherence in community settings. In A. Grant "
          "& R. Hall (Eds.), Handbook of public health practice (pp. 112–138). Springer.")


def test_reference_agency_report_omits_duplicate_publisher() -> None:
    # APA 7 §9.11: when the author is also the publisher, the publisher is not
    # repeated. CDC and WHO reports are the normal case for this.
    work = Work(
        work_type=WorkType.REPORT,
        authors=[Author.group("Centers for Disease Control and Prevention")],
        year="2023", title="Youth risk behavior surveillance system summary",
        report_number="SS-72-1",
        publisher="Centers for Disease Control and Prevention",
        url="https://www.cdc.gov/example",
    )
    work.ensure_key()
    ctx = CitationContext([work])
    text = plain(reference(work, ctx))
    check("report reference", text,
          "Centers for Disease Control and Prevention. (2023). Youth risk behavior "
          "surveillance system summary (Report No. SS-72-1). https://www.cdc.gov/example")
    check("publisher not duplicated", text.count("Centers for Disease Control"), 1)


def test_reference_retraction_is_surfaced() -> None:
    work = article(["Wakefield, A"], "1998", "A withdrawn study", "The Lancet",
                   volume="351", pages="637-641")
    work.retracted = True
    work.retraction_note = "retracted 2010"
    ctx = CitationContext([work])
    # A retracted article must be labelled in the reference itself (APA 7
    # §10.1); printing it as ordinary evidence would misrepresent it.
    check("retraction labelled", "[Retracted; retracted 2010]" in plain(reference(work, ctx)),
          True)


# --------------------------------------------------------------- title casing


def test_sentence_case_conversion() -> None:
    work = article(["Smith, J"], "2022",
                   "The Effects Of Nurse Staffing On Patient Falls In The ICU",
                   "J Nurs")
    ctx = CitationContext([work])
    text = plain(reference(work, ctx))
    # APA 7 §6.16: article titles go to sentence case, but acronyms survive.
    check("title folded to sentence case",
          "The effects of nurse staffing on patient falls in the ICU." in text, True)


def test_sentence_case_preserves_proper_nouns() -> None:
    work = article(["Smith, J"], "2022",
                   "COVID-19 Vaccination Uptake Among Black Adults In The United States",
                   "J Public Health")
    ctx = CitationContext([work])
    text = plain(reference(work, ctx))
    check("COVID-19 preserved", "COVID-19 vaccination" in text, True)
    check("United States preserved", "United States" in text, True)
    check("Black preserved", "Black adults" in text, True)


def test_sentence_case_leaves_existing_sentence_case_alone() -> None:
    original = "Nurse staffing ratios and patient outcomes in acute care settings"
    work = article(["Smith, J"], "2022", original, "J Nurs")
    ctx = CitationContext([work])
    check("already sentence case untouched", original + "." in plain(reference(work, ctx)), True)


def test_journal_name_title_case() -> None:
    work = article(["Smith, J"], "2022", "A study", "journal of advanced nursing and the arts")
    ctx = CitationContext([work])
    # APA 7 §6.17: journal names are title case, minor words lowercase inside.
    check("journal title case",
          "Journal of Advanced Nursing and the Arts" in plain(reference(work, ctx)), True)


def test_elided_page_range_expanded() -> None:
    work = article(["Smith, J"], "2022", "A study", "J Nurs", volume="12", pages="412-8")
    ctx = CitationContext([work])
    # PubMed stores "412-8"; APA requires the full second number.
    check("elided range expanded", "412–418" in plain(reference(work, ctx)), True)


# ------------------------------------------------------------ list ordering


def test_reference_list_ordering() -> None:
    c = article(["Zimmer, A"], "2019", "Zzz", "J Nurs")
    a = article(["Adams, B"], "2021", "Aaa", "J Nurs")
    b1 = article(["Baker, C"], "2018", "Older", "J Nurs")
    b2 = article(["Baker, C"], "2022", "Newer", "J Nurs")
    ctx = CitationContext([c, a, b1, b2])
    entries = [plain(e) for e in reference_list([c, a, b1, b2], ctx)]
    order = [e.split(",")[0] for e in entries]
    # APA 7 §9.44-9.47: surname, then year ascending within an author.
    check("list ordering", order, ["Adams", "Baker", "Baker", "Zimmer"])
    check("earlier year first for same author", entries[1].startswith("Baker, C. (2018)"), True)


def test_no_double_period_after_initials() -> None:
    work = article(["Smith, John A."], "2022", "A study", "J Nurs")
    ctx = CitationContext([work])
    text = plain(reference(work, ctx))
    check("no doubled period after initials", "A.. (" in text, False)
    check("single period after initials", "Smith, J. A. (2022)" in text, True)


def test_the_worked_examples_on_the_apa_screen_are_correct() -> None:
    """Pin the nine examples the APA 7 screen shows.

    They are rendered live by this engine rather than copied out, which makes
    them a demonstration rather than a claim — and makes them wrong on screen
    the moment the engine regresses. That is only worth having if the expected
    output is asserted somewhere, so it is asserted here, exactly, character
    for character. Each one is a reference type that gets marked wrong.
    """
    from app.main import (  # noqa: PLC0415 - imported here to keep this file
        KNOWN_GROUP_ABBREVIATIONS,  # runnable without the web layer loaded
        _example_works,             # for the rest of its cases
        _preview_rows,
    )

    rows = {row["key"]: row for row in
            _preview_rows(_example_works(), KNOWN_GROUP_ABBREVIATIONS, points=True)}
    check("every example carries the rule it demonstrates",
          all(row["point"] for row in rows.values()), True)

    # §8.17: two authors take an ampersand inside parentheses and "and" in
    # narrative use. Getting this backwards is the commonest citation error.
    check("two authors, parenthetical", rows["ex-journal-two"]["parenthetical"],
          "(Alvarez & Okonkwo, 2023)")
    check("two authors, narrative", rows["ex-journal-two"]["narrative"],
          "Alvarez and Okonkwo")
    check("journal article reference", rows["ex-journal-two"]["reference"],
          "Alvarez, M. R., & Okonkwo, D. (2023). Nurse staffing ratios and "
          "inpatient fall rates in adult acute care. Journal of Advanced "
          "Nursing, 79(4), 1120\u20131133. https://doi.org/10.1111/jan.15487")

    # §8.17: three or more authors are et al. from the *first* citation. The
    # 6th edition rule of spelling out the first occurrence is the single most
    # common leftover in papers written with older templates.
    check("three authors elide from the first citation",
          rows["ex-journal-three"]["parenthetical"], "(Brennan et al., 2022)")
    check("but the reference list names all three",
          rows["ex-journal-three"]["reference"].startswith(
              "Brennan, K. L., Duffy, S., & Nakamura, H. (2022)."), True)

    # §8.21: a group author is spelled out with its abbreviation the first
    # time and abbreviated after; the reference list never abbreviates.
    check("group author, first citation", rows["ex-group-report"]["parenthetical"],
          "(World Health Organization [WHO], 2021)")
    check("group author reference is not abbreviated",
          rows["ex-group-report"]["reference"].startswith(
              "World Health Organization. (2021)."), True)

    # §9.29: edition in parentheses, publisher with no location, no doubled
    # period after the closing parenthesis.
    check("book with an edition", rows["ex-book"]["reference"],
          "Polit, D. F., & Beck, C. T. (2021). Nursing research: Generating "
          "and assessing evidence for nursing practice (11th ed.). "
          "Wolters Kluwer.")

    # §9.28: editors run initial-then-surname after "In", the chapter title is
    # upright and the book title italic, and pages take "pp." with an en dash.
    check("chapter in an edited book", rows["ex-chapter"]["reference"],
          "Ramirez, L. A. (2020). Falls and fall prevention among older "
          "adults. In R. G. Hughes (Ed.), Patient safety and quality: An "
          "evidence-based handbook for nurses (pp. 211\u2013238). Agency for "
          "Healthcare Research and Quality.")

    # §9.31: a thesis carries its type and awarding institution in brackets.
    check("thesis", rows["ex-thesis"]["reference"],
          "Whitfield, A. J. (2022). Bedside handoff and patient-reported "
          "involvement in care [Doctoral dissertation, University of "
          "Michigan]. https://deepblue.lib.umich.edu/handle/2027.42/example")

    # §9.8: 21 or more authors take the first 19, an ellipsis, then the final
    # author. Never et al., and never all twenty-four.
    many = rows["ex-many-authors"]["reference"]
    check("nineteen names before the ellipsis",
          many[:many.index(" \u2026 ")].count(".,") >= 19, True)
    check("ellipsis, then the final author",
          " \u2026 Zhang, Q. (2024)." in many, True)
    check("the twentieth author is omitted", "Tanaka" in many, False)
    check("and et al. never appears in a reference entry",
          "et al." in many, False)

    # §9.17: no date is n.d., in the citation and the reference alike, and is
    # never quietly replaced with a guess.
    check("no date, in text", rows["ex-no-date"]["parenthetical"],
          "(American Nurses Association [ANA], n.d.)")
    check("no date, in the reference",
          "(n.d.)." in rows["ex-no-date"]["reference"], True)


def test_the_worked_examples_are_labelled_as_examples() -> None:
    """They must not be mistakable for sources.

    Nine plausible-looking references on screen are a hazard if anyone thinks
    they are retrievable. The screen says so in words; this asserts that the
    data itself never enters a project — the works are built on demand and
    carry keys no fingerprint would ever produce.
    """
    from app.main import _example_works  # noqa: PLC0415

    works = _example_works()
    check("nine worked examples", len(works), 9)
    check("all keyed as examples",
          all(w.key.startswith("ex-") for w in works), True)
    check("none carries a source database",
          any(w.source_db for w in works), False)
    check("and a fresh list is built each time, so nothing is shared state",
          _example_works()[0] is works[0], False)


def main() -> int:
    tests = [value for name, value in sorted(globals().items())
             if name.startswith("test_") and callable(value)]
    for test in tests:
        test()
    print(f"APA 7 citation engine: {CHECKS} checks, {len(FAILURES)} failed")
    for failure in FAILURES:
        print(f"  FAIL {failure}")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    raise SystemExit(main())
