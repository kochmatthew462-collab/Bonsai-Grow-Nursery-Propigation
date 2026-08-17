"""
Tests for the import bridge, level classification and deduplication.

The import tests use real export shapes — the tag order, continuation-line
style and quirks that CINAHL, Ovid, PubMed, Scopus and Zotero actually emit.
Fixtures written to the spec rather than to the exports would pass while the
tool failed on every real file a user dropped in.

Run: python3 tests/test_evidence.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.evidence import dedupe, levels  # noqa: E402
from app.models import Author, EvidenceLevel, Work, WorkType  # noqa: E402
from app.sources import importers  # noqa: E402

FAILURES: list[str] = []
CHECKS = 0


def check(label: str, got, want) -> None:
    global CHECKS
    CHECKS += 1
    if got != want:
        FAILURES.append(f"{label}\n     got: {got!r}\n    want: {want!r}")


# ======================================================================= RIS

# A CINAHL/EBSCOhost export: T2 for the journal, DB naming the database, M3 for
# the publication type, AN for the accession number, and a wrapped abstract.
CINAHL_RIS = """\
TY  - JOUR
AU  - Aiken, Linda H.
AU  - Sloane, Douglas M.
AU  - Bruyneel, Luk
TI  - Nurse staffing and education and hospital mortality in nine European
      countries: a retrospective observational study
T2  - The Lancet
PY  - 2014
VL  - 383
IS  - 9931
SP  - 1824
EP  - 1830
DO  - 10.1016/S0140-6736(13)62631-8
AB  - Austerity measures and health-system redesign to minimise hospital
      expenditures risk adversely affecting patient outcomes.
KW  - Nurse Staffing
KW  - Hospital Mortality
M3  - Retrospective Observational Study
DB  - CINAHL Complete
AN  - 104028772
LA  - English
UR  - https://search.ebscohost.com/login.aspx?direct=true&db=ccm&AN=104028772
ER  -

TY  - BOOK
AU  - Polit, Denise F.
AU  - Beck, Cheryl Tatano
TI  - Nursing research: generating and assessing evidence for nursing practice
PY  - 2021
ET  - 11
PB  - Wolters Kluwer
SN  - 9781975110642
DB  - CINAHL Complete
ER  -
"""

COCHRANE_RIS = """\
TY  - JOUR
AU  - Smith, Jane
TI  - Exercise interventions for preventing falls in older people living in the community
JO  - Cochrane Database of Systematic Reviews
PY  - 2019
IS  - 1
DO  - 10.1002/14651858.CD012424.pub2
N1  - This is a systematic review with meta-analysis of randomized controlled trials.
DB  - Cochrane Database of Systematic Reviews
ER  -
"""


def test_ris_parses_cinahl_export() -> None:
    works = importers.parse(CINAHL_RIS, "export.ris")
    check("two records parsed", len(works), 2)

    article = works[0]
    check("authors parsed", len(article.authors), 3)
    check("first author", article.authors[0].reference_name(), "Aiken, L. H.")
    # A wrapped TI must rejoin into one title, not lose its tail.
    check("wrapped title rejoined",
          article.title,
          "Nurse staffing and education and hospital mortality in nine European "
          "countries: a retrospective observational study")
    check("T2 became the journal", article.container, "The Lancet")
    check("year", article.year, "2014")
    check("volume", article.volume, "383")
    check("issue", article.issue, "9931")
    check("page range assembled from SP and EP", article.pages, "1824-1830")
    check("doi normalised", article.doi, "10.1016/s0140-6736(13)62631-8")
    check("wrapped abstract rejoined", article.abstract.endswith("patient outcomes."), True)
    check("keywords", article.mesh_terms, ["Nurse Staffing", "Hospital Mortality"])
    # Provenance must say this came from an export, not from a live retrieval.
    check("database recorded and normalised", article.source_db, "CINAHL (export)")
    check("accession kept", article.raw.get("accession"), "104028772")

    book = works[1]
    check("book type", book.work_type, WorkType.BOOK)
    check("book edition", book.edition, "11")
    check("book publisher", book.publisher, "Wolters Kluwer")
    check("isbn on a book", book.isbn, "9781975110642")


def test_ris_note_field_supplies_design_signal() -> None:
    works = importers.parse(COCHRANE_RIS, "cochrane.ris")
    work = works[0]
    check("cochrane db normalised", work.source_db, "Cochrane Library (export)")
    # N1 is where Cochrane and Ovid put the design description; without mining
    # it, a Cochrane review imported by file would grade as ungraded.
    check("systematic review found in note",
          any("systematic review" in p.lower() for p in work.publication_types), True)
    level, _ = levels.classify(work)
    check("cochrane review grades Level I", level, EvidenceLevel.LEVEL_I)


def test_ris_recovers_doi_from_url() -> None:
    text = ("TY  - JOUR\nTI  - A study\nPY  - 2020\n"
            "UR  - https://doi.org/10.1234/abcd.5678\nER  -\n")
    work = importers.parse(text, "x.ris")[0]
    check("doi recovered from UR", work.doi, "10.1234/abcd.5678")


def test_ris_handles_missing_final_terminator() -> None:
    text = "TY  - JOUR\nTI  - Truncated export\nPY  - 2020\n"
    works = importers.parse(text, "x.ris")
    check("record without ER still parsed", len(works), 1)
    check("title present", works[0].title, "Truncated export")


# ====================================================================== NBIB

PUBMED_NBIB = """\
PMID- 31234567
OWN - NLM
STAT- MEDLINE
DP  - 2019 Mar 15
TI  - Effect of a nurse-led intervention on hospital readmission: a randomized
      clinical trial.
PG  - 412-425
AB  - Importance: Readmissions remain common. Objective: To determine whether a
      nurse-led transitional care intervention reduces 30-day readmission.
FAU - Chen, Wei Ling
AU  - Chen WL
FAU - O'Brien, Mary Kate
AU  - O'Brien MK
CN  - American Nurses Association
TA  - JAMA Intern Med
JT  - JAMA internal medicine
VI  - 179
IP  - 3
LA  - eng
PT  - Journal Article
PT  - Randomized Controlled Trial
PT  - Multicenter Study
MH  - *Patient Readmission
MH  - Humans
AID - 10.1001/jamainternmed.2018.7624 [doi]
PMC - PMC6439682

PMID- 22222222
TI  - Retracted: a study that did not hold up.
TA  - J Example
DP  - 2015
PT  - Journal Article
PT  - Retracted Publication
RIN - Retraction in: J Example. 2016;12(3):200
AID - 10.1000/retracted.1 [doi]
"""


def test_nbib_parses_pubmed_export() -> None:
    works = importers.parse(PUBMED_NBIB, "pubmed.nbib")
    check("two records parsed", len(works), 2)

    work = works[0]
    check("pmid", work.pmid, "31234567")
    # FAU carries the full name; AU only has "Chen WL". Preferring FAU means
    # initials are read, not guessed.
    check("full author names preferred", work.authors[0].reference_name(), "Chen, W. L.")
    check("apostrophe surname", work.authors[1].reference_name(), "O'Brien, M. K.")
    check("corporate author appended", work.authors[-1].is_group, True)
    check("corporate author name", work.authors[-1].family, "American Nurses Association")
    check("full journal title preferred over abbreviation",
          work.container, "JAMA internal medicine")
    check("wrapped title rejoined and period stripped",
          work.title,
          "Effect of a nurse-led intervention on hospital readmission: a "
          "randomized clinical trial")
    check("year from DP", work.year, "2019")
    check("volume", work.volume, "179")
    check("pages", work.pages, "412-425")
    check("doi from AID", work.doi, "10.1001/jamainternmed.2018.7624")
    check("pmcid", work.pmcid, "PMC6439682")
    check("mesh asterisk stripped", "Patient Readmission" in work.mesh_terms, True)
    check("publication types", "Randomized Controlled Trial" in work.publication_types, True)
    check("medline marked peer reviewed", work.peer_reviewed, True)


def test_nbib_detects_retraction() -> None:
    works = importers.parse(PUBMED_NBIB, "pubmed.nbib")
    retracted = works[1]
    check("retraction detected", retracted.retracted, True)
    check("retraction note kept", "Retraction in" in retracted.retraction_note, True)
    level, reason = levels.classify(retracted)
    # A retracted article must not be gradeable as evidence at any level.
    check("retracted is excluded, not Level V", level, EvidenceLevel.EXCLUDED)
    check("reason mentions retraction", "retracted" in reason.lower(), True)


# ==================================================================== BibTeX

ZOTERO_BIBTEX = """\
@article{aiken2014nurse,
  title = {Nurse staffing and education and hospital mortality in nine {European} countries},
  author = {Aiken, Linda H. and Sloane, Douglas M. and Bruyneel, Luk},
  journal = {The Lancet},
  volume = {383},
  number = {9931},
  pages = {1824--1830},
  year = {2014},
  doi = {10.1016/S0140-6736(13)62631-8},
  keywords = {nurse staffing, mortality},
}

@book{polit2021nursing,
  title = {Nursing Research},
  author = {Polit, Denise F.},
  year = {2021},
  edition = {11},
  publisher = {Wolters Kluwer},
}

@techreport{cdc2023youth,
  title = {Youth Risk Behavior Surveillance System},
  author = {{Centers for Disease Control and Prevention}},
  year = {2023},
  institution = {Centers for Disease Control and Prevention},
  number = {SS-72-1},
}
"""


def test_bibtex_parses_and_strips_protective_braces() -> None:
    works = importers.parse(ZOTERO_BIBTEX, "library.bib")
    check("three entries", len(works), 3)

    article = works[0]
    # Zotero brace-protects capitals; those braces must not reach the paper.
    check("protective braces removed",
          article.title,
          "Nurse staffing and education and hospital mortality in nine European countries")
    check("bibtex authors split on 'and'", len(article.authors), 3)
    check("en dash range normalised", article.pages, "1824-1830")
    check("number became issue", article.issue, "9931")

    check("book type", works[1].work_type, WorkType.BOOK)
    report = works[2]
    check("techreport type", report.work_type, WorkType.REPORT)
    # A double-braced author is a corporate name that must not be initialised.
    check("corporate author kept whole", report.authors[0].is_group, True)
    check("corporate author text", report.authors[0].family,
          "Centers for Disease Control and Prevention")
    check("report number", report.report_number, "SS-72-1")


def test_bibtex_nested_braces_do_not_split_entry() -> None:
    text = "@article{k, title = {A {nested {deep}} title}, year = {2020}}"
    works = importers.parse(text, "x.bib")
    check("one entry despite nesting", len(works), 1)
    check("nested braces flattened", works[0].title, "A nested deep title")


# =============================================================== EndNote XML

ENDNOTE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<xml><records>
<record>
<ref-type name="Journal Article">17</ref-type>
<contributors><authors>
  <author><style>Kim, Soo Jin</style></author>
  <author><style>Patel, Ravi</style></author>
</authors></contributors>
<titles>
  <title><style>Telehealth uptake among rural adults</style></title>
  <secondary-title><style>Journal of Rural Health</style></secondary-title>
</titles>
<periodical><full-title>Journal of Rural Health</full-title></periodical>
<dates><year><style>2022</style></year></dates>
<volume>38</volume><number>2</number><pages>210-219</pages>
<electronic-resource-num>10.1111/jrh.12600</electronic-resource-num>
<abstract><style>Rural adults face access barriers.</style></abstract>
<keywords><keyword>telehealth</keyword><keyword>rural health</keyword></keywords>
<remote-database-name>MEDLINE</remote-database-name>
<accession-num>35123456</accession-num>
</record>
</records></xml>
"""


def test_endnote_xml_parses() -> None:
    works = importers.parse(ENDNOTE_XML, "export.xml")
    check("one record", len(works), 1)
    work = works[0]
    # EndNote nests text inside <style> elements; flattening is required.
    check("style-wrapped author flattened", work.authors[0].reference_name(), "Kim, S. J.")
    check("style-wrapped title flattened", work.title, "Telehealth uptake among rural adults")
    check("journal from secondary-title", work.container, "Journal of Rural Health")
    check("year", work.year, "2022")
    check("doi", work.doi, "10.1111/jrh.12600")
    check("database normalised", work.source_db, "MEDLINE (export)")
    check("pmid from accession", work.pmid, "35123456")
    check("ref-type mapped", work.work_type, WorkType.JOURNAL_ARTICLE)


# ======================================================================= CSV

SCOPUS_CSV = """\
Authors,Title,Year,Source title,Volume,Issue,Page start,Page end,DOI,Document Type
"Lee, B.; Gomez, A.","Community health worker programs and blood pressure control",2021,"Preventive Medicine",145,,106,113,10.1016/j.ypmed.2021.106,Article
"""


def test_csv_maps_vendor_columns() -> None:
    works = importers.parse(SCOPUS_CSV, "scopus.csv")
    check("one row", len(works), 1)
    work = works[0]
    check("semicolon-separated authors split", len(work.authors), 2)
    check("first author", work.authors[0].reference_name(), "Lee, B.")
    check("source title mapped to container", work.container, "Preventive Medicine")
    check("year", work.year, "2021")
    check("doi", work.doi, "10.1016/j.ypmed.2021.106")
    check("document type kept", work.publication_types, ["Article"])


def test_csv_without_title_column_is_rejected() -> None:
    try:
        importers.parse("foo,bar\n1,2\n", "x.csv")
    except ValueError as error:
        check("clear error for unusable CSV", "title column" in str(error), True)
    else:
        check("clear error for unusable CSV", False, True)


# ========================================================== format detection


def test_format_detection_ignores_wrong_extension() -> None:
    # EBSCO's "Export to RIS" routinely arrives as .txt; PubMed's NBIB too.
    check("RIS content in a .txt file", importers.detect_format(CINAHL_RIS, "export.txt"), "ris")
    check("NBIB content in a .txt file", importers.detect_format(PUBMED_NBIB, "pm.txt"), "nbib")
    check("BibTeX content in a .txt file",
          importers.detect_format(ZOTERO_BIBTEX, "lib.txt"), "bibtex")
    check("EndNote XML detected", importers.detect_format(ENDNOTE_XML, "e.xml"), "endnote-xml")


def test_unrecognisable_file_gives_actionable_error() -> None:
    try:
        importers.parse("just some prose with no structure at all", "notes.md")
    except ValueError as error:
        check("error names the accepted formats", "RIS" in str(error), True)
    else:
        check("error names the accepted formats", False, True)


# ================================================================== levels


def make(title="", abstract="", types=(), **kw) -> Work:
    work = Work(title=title, abstract=abstract, publication_types=list(types), **kw)
    work.ensure_key()
    return work


def test_level_from_publication_types() -> None:
    check("meta-analysis is Level I",
          levels.classify(make(types=["Journal Article", "Meta-Analysis"]))[0],
          EvidenceLevel.LEVEL_I)
    check("RCT is Level I",
          levels.classify(make(types=["Randomized Controlled Trial"]))[0],
          EvidenceLevel.LEVEL_I)
    check("controlled clinical trial is Level II",
          levels.classify(make(types=["Controlled Clinical Trial"]))[0],
          EvidenceLevel.LEVEL_II)
    check("observational study is Level III",
          levels.classify(make(types=["Observational Study"]))[0],
          EvidenceLevel.LEVEL_III)
    check("practice guideline is Level V",
          levels.classify(make(types=["Practice Guideline"]))[0],
          EvidenceLevel.LEVEL_V)


def test_bare_review_is_level_five_not_level_one() -> None:
    # The most common misclassification in automated EBP tooling: PubMed's
    # "Review" type covers narrative reviews, which are not Level I evidence.
    level, reason = levels.classify(
        make(title="Managing chronic pain in primary care", types=["Journal Article", "Review"])
    )
    check("bare Review is Level V", level, EvidenceLevel.LEVEL_V)
    check("reason explains the distinction", "narrative" in reason.lower(), True)


def test_review_type_with_systematic_wording_is_level_one() -> None:
    level, _ = levels.classify(make(
        title="Exercise for falls prevention: a systematic review and meta-analysis",
        types=["Journal Article", "Review"],
    ))
    check("systematic review tagged Review is Level I", level, EvidenceLevel.LEVEL_I)


def test_level_from_text_when_no_publication_types() -> None:
    # The normal case for a record imported from an export rather than PubMed.
    check("cohort wording is Level III",
          levels.classify(make(abstract="We conducted a prospective cohort study of 4,000 "
                                        "adults."))[0],
          EvidenceLevel.LEVEL_III)
    check("qualitative wording is Level IV",
          levels.classify(make(abstract="We used grounded theory with semi-structured "
                                        "interviews."))[0],
          EvidenceLevel.LEVEL_IV)
    check("quasi-experimental wording is Level II",
          levels.classify(make(abstract="A quasi-experimental pre-post design was used."))[0],
          EvidenceLevel.LEVEL_II)
    check("consensus wording is Level V",
          levels.classify(make(title="Consensus statement on sepsis screening"))[0],
          EvidenceLevel.LEVEL_V)


def test_editorial_is_excluded_not_graded() -> None:
    level, _ = levels.classify(make(types=["Editorial"]))
    # Excluded rather than Level V, so it cannot slip through a minimum-level
    # filter set to V.
    check("editorial excluded", level, EvidenceLevel.EXCLUDED)
    work = make(types=["Editorial"])
    levels.apply(work)
    check("excluded fails a Level V floor", levels.meets_minimum(work, "V"), False)


def test_unclassifiable_record_is_ungraded_and_fails_filters() -> None:
    work = make(title="Some article", abstract="No design words at all here.")
    levels.apply(work)
    check("no signal means ungraded", work.level, EvidenceLevel.UNGRADED)
    check("reason tells the user to grade it by hand", "by hand" in work.level_reason, True)
    # An ungraded record must not quietly pass as evidence.
    check("ungraded fails a Level V floor", levels.meets_minimum(work, "V"), False)


def test_agency_report_defaults_to_level_five() -> None:
    work = make(title="Surveillance summary", work_type=WorkType.REPORT,
                authors=[Author.group("Centers for Disease Control and Prevention")])
    level, _ = levels.classify(work)
    check("agency report is Level V", level, EvidenceLevel.LEVEL_V)


def test_manual_override_survives_reclassification() -> None:
    work = make(types=["Journal Article", "Review"])
    levels.apply(work)
    check("auto grade first", work.level, EvidenceLevel.LEVEL_V)
    levels.set_by_hand(work, EvidenceLevel.LEVEL_I,
                       "read the methods; it is a full systematic review")
    levels.apply(work)  # must not undo the override
    check("override survives", work.level, EvidenceLevel.LEVEL_I)
    check("override is labelled", work.level_reason.startswith("Set by hand"), True)


def test_minimum_level_filter() -> None:
    strong = make(types=["Meta-Analysis"])
    weak = make(abstract="A cross-sectional survey was administered.")
    levels.apply_all([strong, weak])
    check("Level I passes a III floor", levels.meets_minimum(strong, "III"), True)
    check("Level IV fails a III floor", levels.meets_minimum(weak, "III"), False)
    check("Level IV passes a IV floor", levels.meets_minimum(weak, "IV"), True)


# ================================================================== dedupe


def test_dedupe_on_doi_across_databases() -> None:
    pubmed = make(title="Nurse staffing and mortality", doi="10.1016/S0140-6736(13)62631-8",
                  source_db="pubmed", abstract="Short version.")
    cinahl = make(title="Nurse staffing and mortality in nine European countries",
                  doi="https://doi.org/10.1016/s0140-6736(13)62631-8",
                  source_db="CINAHL (export)",
                  abstract="A considerably longer abstract with much more detail in it.")
    unique, log = dedupe.deduplicate([pubmed, cinahl])
    check("merged to one record", len(unique), 1)
    check("merge logged", len(log), 1)
    check("matched on DOI", log[0]["matched_on"], "DOI")
    # Both databases are named, because confirmation in two indexes is a
    # strength the methodology section should be able to state.
    check("both sources recorded",
          sorted(unique[0].raw["merged_from"]), ["CINAHL (export)", "pubmed"])
    check("longer abstract kept", unique[0].abstract.startswith("A considerably longer"), True)
    check("longer title kept", unique[0].title.endswith("European countries"), True)


def test_dedupe_on_pmid_when_no_doi() -> None:
    a = make(title="A trial", pmid="31234567", source_db="pubmed")
    b = make(title="A trial of something", pmid="31234567", source_db="embase")
    unique, log = dedupe.deduplicate([a, b])
    check("merged on PMID", len(unique), 1)
    check("matched on PMID", log[0]["matched_on"], "PMID")


def test_dedupe_on_title_and_year_without_identifiers() -> None:
    # The case that matters for CINAHL and Embase records with no shared DOI.
    a = make(title="Exercise interventions for preventing falls in older people",
             year="2019", authors=[Author.parse("Smith, J")], source_db="cinahl")
    b = make(title="Exercise interventions for preventing falls in older people.",
             year="2019", authors=[Author.parse("Smith, Jane")], source_db="embase")
    unique, log = dedupe.deduplicate([a, b])
    check("merged on title", len(unique), 1)
    check("reason names title similarity", "title similarity" in log[0]["matched_on"], True)


def test_conflicting_dois_are_not_merged() -> None:
    # An erratum shares its article's title; merging them would delete the
    # article and keep the correction.
    a = make(title="Effect of X on Y", doi="10.1/aaa", year="2020")
    b = make(title="Effect of X on Y", doi="10.1/bbb", year="2020")
    unique, _ = dedupe.deduplicate([a, b])
    check("different DOIs stay separate", len(unique), 2)


def test_similar_titles_by_different_authors_stay_separate() -> None:
    a = make(title="Effect of exercise on blood pressure in adults", year="2020",
             authors=[Author.parse("Smith, J")])
    b = make(title="Effect of exercise on blood pressure in adults", year="2020",
             authors=[Author.parse("Kumar, R")])
    unique, _ = dedupe.deduplicate([a, b])
    check("same title different first author stays separate", len(unique), 2)


def test_different_populations_stay_separate() -> None:
    a = make(title="Effect of metformin on weight in adults with type 2 diabetes",
             year="2020", authors=[Author.parse("Smith, J")])
    b = make(title="Effect of metformin on weight in children with type 1 diabetes",
             year="2020", authors=[Author.parse("Smith, J")])
    unique, _ = dedupe.deduplicate([a, b])
    check("different populations stay separate", len(unique), 2)


def test_ahead_of_print_year_drift_still_merges() -> None:
    a = make(title="Telehealth uptake among rural adults during the pandemic",
             year="2021", authors=[Author.parse("Kim, S")])
    b = make(title="Telehealth uptake among rural adults during the pandemic",
             year="2022", authors=[Author.parse("Kim, S")])
    unique, _ = dedupe.deduplicate([a, b])
    # One year of drift is the ahead-of-print/issue gap, which differs between
    # indexes for the same article.
    check("one year of drift merges", len(unique), 1)


def test_retraction_propagates_through_merge() -> None:
    clean = make(title="A study", doi="10.1/x", source_db="cinahl")
    flagged = make(title="A study", doi="10.1/x", source_db="pubmed")
    flagged.retracted = True
    flagged.retraction_note = "Retraction in: J Example 2016"
    unique, _ = dedupe.deduplicate([clean, flagged])
    # A retraction found in any index applies to the article everywhere.
    check("retraction survives the merge", unique[0].retracted, True)
    check("retraction note survives", "J Example" in unique[0].retraction_note, True)


def test_prisma_counts() -> None:
    counts = dedupe.prisma_counts(retrieved=120, after_dedupe=95,
                                  screened_out=60, excluded_by_level=12, included=23)
    check("duplicates removed derived", counts["duplicates_removed"], 25)
    check("screened", counts["records_screened"], 95)
    check("included", counts["studies_included"], 23)


def main() -> int:
    tests = [value for name, value in sorted(globals().items())
             if name.startswith("test_") and callable(value)]
    for test in tests:
        test()
    print(f"Evidence pipeline: {CHECKS} checks, {len(FAILURES)} failed")
    for failure in FAILURES:
        print(f"  FAIL {failure}")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    raise SystemExit(main())
