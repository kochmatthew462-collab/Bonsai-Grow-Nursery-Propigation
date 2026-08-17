"""
Tests for the discovery, compliance and statistics modules.

Four things get most of the attention here, because each is a place where a
plausible-looking wrong answer would be worse than no answer:

* **Database syntax.** A PubMed string pasted into CINAHL returns almost nothing,
  silently. Each translator is checked for the field tags that database actually
  uses, and for the ones it must *not* emit.
* **PRISMA arithmetic.** The subtraction is walked, and a diagram whose boxes do
  not subtract must be reported rather than corrected — silently fixing the counts
  would be fabricating a flow diagram.
* **APA statistical style.** The leading-zero rule cuts both ways: `p = .03` but
  `M = 0.45`. Getting the set of no-leading-zero symbols wrong is how `M = .45`
  reaches a marker.
* **The refusal to score.** The simulator must never produce a grade, and a
  missing *p* must never render as "not statistically significant" — both are
  confident claims manufactured from an absence.

Run: python3 tests/test_research_tools.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.apa import prisma  # noqa: E402
from app.compliance import journals, rubric, simulator  # noqa: E402
from app.models import Project  # noqa: E402
from app.research import pico  # noqa: E402
from app.writing import statistics  # noqa: E402

FAILURES: list[str] = []
CHECKS = 0


def check(label: str, got, want) -> None:
    global CHECKS
    CHECKS += 1
    if got != want:
        FAILURES.append(f"{label}\n     got: {got!r}\n    want: {want!r}")


def contains(label: str, haystack: str, needle: str) -> None:
    global CHECKS
    CHECKS += 1
    if needle.lower() not in (haystack or "").lower():
        FAILURES.append(f"{label}\n    {needle!r} not in {haystack!r}")


def absent(label: str, haystack: str, needle: str) -> None:
    global CHECKS
    CHECKS += 1
    if needle.lower() in (haystack or "").lower():
        FAILURES.append(f"{label}\n    {needle!r} unexpectedly in {haystack!r}")


def sample_question() -> pico.Question:
    return pico.build({
        "framework": "pico",
        "question_text": "Does hourly rounding reduce falls?",
        "years": 5,
        "languages": ["english"],
        "concepts": {
            "population": {"terms": ["adult inpatients"]},
            "intervention": {"terms": ["hourly rounding", "nurse"],
                             "expand": True},
            "comparison": {"terms": ["usual care"]},
            "outcome": {"terms": ["fall"], "expand": True},
        },
    })


# =========================================================== PICO and SPIDER


def test_frameworks_are_offered() -> None:
    keys = {f["key"] for f in pico.frameworks()}
    check("both frameworks", keys, {"pico", "spider"})
    for framework in pico.frameworks():
        check(f"{framework['key']} has slots", len(framework["slots"]) >= 5, True)
        for slot in framework["slots"]:
            check(f"{framework['key']}.{slot['key']} has guidance",
                  bool(slot["guidance"].strip()), True)
    spider = next(f for f in pico.frameworks() if f["key"] == "spider")
    contains("SPIDER explains when to use it", spider["use_when"], "qualitative")


def test_required_slots_are_reported() -> None:
    empty = pico.build({"framework": "pico", "concepts": {}})
    missing = empty.missing_required()
    check("three required PICO slots reported", len(missing), 3)
    contains("population named", " ".join(missing), "Population")
    contains("intervention named", " ".join(missing), "Intervention")
    contains("outcome named", " ".join(missing), "Outcome")
    # The comparison is optional: leaving it empty widens the search, it does not
    # break the question.
    absent("comparison is not required", " ".join(missing), "Comparison")


def test_expansion_is_bounded() -> None:
    """Expansion must not fire on a substring — "fall" inside "fallopian"."""
    found = pico.expand("fall")
    check("synonyms found", "falls" in found["synonyms"], True)
    check("MeSH found", found["mesh"], ["Accidental Falls"])
    check("plural resolves to the same entry",
          pico.expand("falls")["mesh"], ["Accidental Falls"])
    check("an unknown term expands to nothing",
          pico.expand("fallopian"), {"synonyms": [], "mesh": []})
    check("an empty term is safe", pico.expand(""), {"synonyms": [], "mesh": []})


def test_expansion_is_opt_in() -> None:
    without = pico.build({"concepts": {"outcome": {"terms": ["fall"]}}})
    with_expand = pico.build({"concepts": {"outcome": {"terms": ["fall"],
                                                       "expand": True}}})
    check("no expansion by default",
          without.concepts["outcome"].all_terms(), ["fall"])
    check("expansion adds synonyms",
          len(with_expand.concepts["outcome"].all_terms()) > 1, True)
    check("and MeSH", with_expand.concepts["outcome"].mesh, ["Accidental Falls"])


def test_pubmed_syntax() -> None:
    query = pico.to_pubmed(sample_question())
    contains("uses tiab", query, "[tiab]")
    contains("uses Mesh", query, "[Mesh]")
    contains("phrases are quoted", query, '"adult inpatients"[tiab]')
    # A single-term block is emitted bare rather than wrapped in redundant
    # parentheses, so the join is asserted rather than a parenthesis pattern.
    contains("blocks are ANDed", query, " AND ")
    contains("humans limit", query, '"humans"[MeSH Terms]')
    contains("date limit", query, "last 5 years")
    contains("language limit", query, "english[lang]")
    # CINAHL syntax must not leak into a PubMed string.
    absent("no CINAHL field tags", query, "(MH ")
    absent("no Cochrane field tags", query, ":ti,ab,kw")


def test_cinahl_syntax() -> None:
    """CINAHL has no combined title-abstract field. A PubMed string pasted here
    returns almost nothing, and the failure is silent."""
    query = pico.to_cinahl(sample_question())
    contains("searches TI and AB separately", query, "TI ")
    contains("and AB", query, "AB ")
    contains("uses MH headings", query, "(MH ")
    absent("never emits tiab", query, "[tiab]")
    absent("never emits Mesh", query, "[Mesh]")
    contains("limiters are stated", query, "Limiters")
    contains("peer reviewed limiter", query, "Peer Reviewed")


def test_cochrane_syntax() -> None:
    query = pico.to_cochrane(sample_question())
    contains("uses ti,ab,kw", query, ":ti,ab,kw")
    contains("uses mh", query, "[mh ")
    absent("no tiab", query, "[tiab]")


def test_scopus_and_wos_have_no_thesaurus() -> None:
    """Both lack controlled vocabulary, so headings fold in as phrases rather
    than being dropped — dropping them would narrow the search silently."""
    question = sample_question()
    scopus = pico.to_scopus(question)
    contains("uses TITLE-ABS-KEY", scopus, "TITLE-ABS-KEY(")
    absent("no MeSH tags", scopus, "[Mesh]")
    contains("headings folded in as phrases", scopus, "Accidental Falls")
    contains("year limit", scopus, "PUBYEAR")

    wos = pico.to_web_of_science(question)
    contains("uses TS=", wos, "TS=(")


def test_folded_headings_are_deduplicated() -> None:
    """"Nurses" the heading and "nurses" the synonym search identically."""
    question = pico.build({"concepts": {
        "population": {"terms": ["adults"]},
        "intervention": {"terms": ["nurse"], "expand": True},
        "outcome": {"terms": ["fall"], "expand": True},
    }})
    plain = pico.to_plain(question)
    check("no case-only duplicate", plain.lower().count(" or nurses"), 1)


def test_translate_all_carries_caveats() -> None:
    rows = pico.translate_all(sample_question())
    check("six databases", len(rows), 6)
    by_key = {row["database"]: row for row in rows}
    contains("CINAHL warns about its own headings",
             " ".join(by_key["cinahl"]["caveats"]), "CINAHL Headings")
    contains("Scopus explains the fold-in",
             " ".join(by_key["scopus"]["caveats"]), "folded in as phrases")
    for row in rows:
        check(f"{row['database']} says how to run it",
              bool(row["how_to_run"].strip()), True)


def test_strategy_report_is_reportable() -> None:
    report = pico.strategy_report(sample_question())
    check("framework named", report["framework"], "PICO")
    check("concepts listed", len(report["concepts"]), 4)
    contains("PRISMA item 7 is referenced", report["reporting_note"], "item 7")
    contains("run date is demanded", report["reporting_note"], "date you ran it")
    check("limits carried", report["limits"]["years"], 5)


def test_spider_is_a_different_shape() -> None:
    question = pico.build({
        "framework": "spider",
        "concepts": {
            "sample": {"terms": ["intensive care"], "expand": True},
            "phenomenon": {"terms": ["moral distress"]},
            "evaluation": {"terms": ["experience"], "expand": True},
        },
    })
    check("nothing required is missing", question.missing_required(), [])
    query = pico.to_pubmed(question)
    contains("phenomenon block present", query, "moral distress")
    contains("evaluation expanded", query, "perception")


# ====================================================================== PRISMA


def consistent_counts() -> prisma.PrismaCounts:
    return prisma.PrismaCounts(
        records_databases=1284, records_registers=31,
        duplicates_removed=214, removed_ineligible_automation=18,
        removed_other_reasons=5,
        records_screened=1078, records_excluded=903,
        reports_sought=175, reports_not_retrieved=9, reports_assessed=166,
        reports_excluded_reasons={"Wrong population": 61, "Wrong outcome": 44,
                                  "Not primary research": 29, "No comparator": 18},
        studies_included=14, reports_of_included=17)


def test_consistent_counts_validate_clean() -> None:
    check("no problems", prisma.validate(consistent_counts()), [])


def test_broken_arithmetic_is_reported_not_fixed() -> None:
    """Silently correcting the counts would be fabricating a flow diagram."""
    counts = consistent_counts()
    counts.records_screened = 999            # was 1,078
    problems = prisma.validate(counts)
    check("reported", len(problems) >= 1, True)
    first = next(p for p in problems if p["check"] == "Records screened")
    check("expected value given", first["expected"], 1078)
    check("entered value given", first["entered"], 999)
    check("difference given", first["difference"], -79)
    # And the count is untouched.
    check("the entered number is not modified", counts.records_screened, 999)


def test_each_subtraction_is_walked() -> None:
    for field_name, expected_check in [
        ("records_screened", "Records screened"),
        ("reports_sought", "Reports sought for retrieval"),
        ("reports_assessed", "Reports assessed for eligibility"),
    ]:
        counts = consistent_counts()
        setattr(counts, field_name, getattr(counts, field_name) + 7)
        problems = {p["check"] for p in prisma.validate(counts)}
        check(f"{field_name} mismatch is caught", expected_check in problems, True)


def test_missing_exclusion_reasons_are_required() -> None:
    counts = consistent_counts()
    counts.reports_excluded_reasons = {}
    problems = {p["check"] for p in prisma.validate(counts)}
    check("PRISMA requires reasons with counts",
          "Full-text exclusion reasons" in problems, True)


def test_reports_fewer_than_studies_is_caught() -> None:
    """One study can be reported in several papers, never fewer."""
    counts = consistent_counts()
    counts.reports_of_included = 3           # fewer than 14 studies
    problems = {p["check"] for p in prisma.validate(counts)}
    check("caught", "Reports of included studies" in problems, True)


def test_other_methods_column_detection() -> None:
    counts = consistent_counts()
    check("single column by default", counts.has_other_methods(), False)
    counts.records_citation_searching = 40
    check("second column once citation searching is entered",
          counts.has_other_methods(), True)


def test_diagram_renders_both_layouts() -> None:
    directory = Path(tempfile.mkdtemp())
    single = prisma.render(consistent_counts(), directory / "single.png")
    check("single-column file written", single.exists(), True)
    check("and is a real PNG", single.stat().st_size > 20_000, True)

    counts = consistent_counts()
    counts.records_citation_searching = 40
    counts.other_reports_sought = 40
    counts.other_reports_assessed = 38
    counts.other_reports_excluded_reasons = {"Duplicate of included": 30}
    two = prisma.render(counts, directory / "two.png")
    check("two-column file written", two.exists(), True)
    check("and is wider than the single column",
          two.stat().st_size != single.stat().st_size, True)


def test_diagram_cites_and_declares_licensing() -> None:
    contains("cites the 2020 statement", prisma.CITATION, "PRISMA 2020 statement")
    contains("names the BMJ", prisma.CITATION, "BMJ")
    contains("says it is drawn not reproduced", prisma.LICENSING_NOTE,
             "rather than reproduced")
    note = prisma.apa_figure_note(consistent_counts())
    contains("figure note carries the totals", note, "1,315 records")
    contains("and names the structure followed", note, "PRISMA 2020")


def test_from_project_fills_only_what_is_observable() -> None:
    """Everything downstream of screening happened outside the tool. Guessing it
    would fabricate the parts of a flow diagram that matter most."""
    project = Project(project_id="p", topic="t")
    counts = prisma.from_project(project)
    check("nothing invented", counts.reports_not_retrieved, 0)
    check("no exclusion reasons invented", counts.reports_excluded_reasons, {})
    # User-supplied extras override.
    counts = prisma.from_project(project, {"reports_not_retrieved": 9,
                                           "reports_excluded_reasons": {"x": 3}})
    check("extras applied", counts.reports_not_retrieved, 9)
    check("dict extras applied", counts.reports_excluded_reasons, {"x": 3})


# ================================================================== statistics


def test_leading_zero_rule_cuts_both_ways() -> None:
    check("p drops the zero", statistics.fmt_stat("p", 0.03), "p = .03")
    check("r drops the zero", statistics.fmt_stat("r", 0.42), "r = .42")
    check("M keeps it", statistics.fmt_stat("M", 0.45), "M = 0.45")
    check("SD keeps it", statistics.fmt_stat("SD", 0.9), "SD = 0.90")
    check("t keeps it", statistics.fmt_stat("t", 0.5), "t = 0.50")
    check("negative r drops the zero", statistics.fmt_stat("r", -0.42), "r = -.42")


def test_p_value_formatting() -> None:
    check("small p", statistics.fmt_p(0.0000004), "p < .001")
    check("exactly at the boundary", statistics.fmt_p(0.001), "p = .001")
    check("ordinary p", statistics.fmt_p(0.04196), "p = .042")
    check("large p", statistics.fmt_p(0.9999), "p > .999")
    check("p = 1", statistics.fmt_p(1.0), "p > .999")
    # SPSS prints .000 because it rounds; a p value is never zero.
    check("never reports zero", statistics.fmt_p(0.0), "p < .001")


def test_confidence_intervals() -> None:
    check("bracket form", statistics.fmt_ci(0.14, 6.98),
          "95% CI [0.14, 6.98]")
    check("level is configurable", statistics.fmt_ci(1.0, 2.0, level=99),
          "99% CI [1.00, 2.00]")


def test_italic_runs_follow_apa() -> None:
    runs = dict(statistics.italic_runs(
        "t(34) = 2.11, p = .042, 95% CI [0.14, 6.98], d = 0.51"))
    check("t is italic", runs.get("t"), True)
    check("p is italic", runs.get("p"), True)
    check("d is italic", runs.get("d"), True)
    # Greek is never italicised (§6.44) — the rule people get backwards.
    greek = dict(statistics.italic_runs("F(2, 87) = 6.44, p = .002, ηp² = .13"))
    check("F is italic", greek.get("F"), True)
    check("eta is not offered as an italic run", "ηp²" in greek, False)


def test_parses_r_output() -> None:
    out = statistics.translate(
        "\tWelch Two Sample t-test\n\n"
        "data:  scores by group\n"
        "t = 2.1134, df = 33.847, p-value = 0.04196\n",
        variables="fall rates")
    check("one result", out["recognised"], 1)
    result = out["results"][0]
    check("kind", result["kind"], "t_test")
    contains("fractional df preserved", result["statistics"], "t(33.85)")
    contains("p formatted", result["statistics"], "p = .042")
    contains("Welch note", result["note"], "Welch")


def test_parses_spss_anova_by_row() -> None:
    """SPSS output is column-oriented. Keyword matching cannot read it — there is
    no "F = " anywhere — so the row is located by its label."""
    out = statistics.translate(
        "ANOVA\n"
        "                 Sum of Squares   df   Mean Square      F      Sig.\n"
        "Between Groups          28.442     2        14.221   6.442    .002\n"
        "Within Groups          192.030    87         2.207\n"
        "Total                  220.472    89\n",
        variables="staffing level")
    result = next(r for r in out["results"] if r["kind"] == "anova")
    contains("F and both df read positionally", result["statistics"], "F(2, 87)")
    contains("F value", result["statistics"], "6.44")
    contains("p from the Sig. column", result["statistics"], "p = .002")


def test_sig_parenthetical_is_not_read_as_p() -> None:
    """"Asymp. Sig. (2-sided) .007" — a lazy match takes the 2 from the
    parenthetical and reports p = 2.00, which then renders as p > .999."""
    out = statistics.translate(
        "Pearson Chi-Square 9.874  df = 2  Asymp. Sig. (2-sided) .0072  "
        "N of Valid Cases 180")
    result = next(r for r in out["results"] if r["kind"] == "chi_square")
    contains("p is the real value", result["statistics"], "p = .007")
    absent("not the parenthetical", result["statistics"], "p > .999")
    contains("N is inside the parentheses", result["statistics"], "N = 180")


def test_missing_p_never_asserts_non_significance() -> None:
    """The most dangerous failure this module could have: a confident claim
    manufactured from an absence."""
    result = statistics.ParsedResult(
        kind="anova", values={"F": 6.44, "df1": 2, "df2": 87}, label="one-way")
    text = statistics.sentence(result, variables="staffing level")
    absent("does not say not significant", text, "not statistically significant")
    absent("does not say significant either", text, "was statistically significant")
    contains("says the p value is missing", text, "p value could not be read")
    contains("and says significance is unknown", text, "not known")
    contains("but still reports what it has", text, "F(2, 87) = 6.44")


def test_significance_is_stated_when_p_is_present() -> None:
    significant = statistics.ParsedResult(
        kind="t_test", values={"t": 2.11, "df": 34, "p": 0.042})
    contains("significant", statistics.sentence(significant, variables="the units"),
             "differed significantly")
    not_significant = statistics.ParsedResult(
        kind="t_test", values={"t": 1.20, "df": 30, "p": 0.24})
    contains("not significant",
             statistics.sentence(not_significant, variables="the units"),
             "did not differ significantly")


def test_prose_checker() -> None:
    codes = {i.code for i in statistics.check_prose(
        "Results were significant (p = 0.000). The correlation r = 0.42 "
        "approached significance and proves the effect at p < .05.")}
    for code in ("p_leading_zero", "p_is_zero", "r_leading_zero",
                 "approached_significance", "proves", "threshold_p"):
        check(f"{code} flagged", code in codes, True)

    clean = statistics.check_prose(
        "The groups differed, t(34) = 2.11, p = .042, d = 0.51.")
    codes = {i.code for i in clean}
    for code in ("p_leading_zero", "p_is_zero", "approached_significance"):
        check(f"{code} does not fire on correct prose", code in codes, False)


def test_manual_entry_covers_every_supported_test() -> None:
    for spec in statistics.supported():
        values = {field: 1.5 for field in spec["fields"]}
        values["p"] = 0.02
        out = statistics.manual(spec["kind"], values, variables="the outcome")
        check(f"{spec['kind']} renders", bool(out["sentence"].strip()), True)
        check(f"{spec['kind']} produces runs", len(out["runs"]) > 0, True)
        check(f"{spec['kind']} has an example", bool(spec["apa"].strip()), True)


# ================================================================ the rubric


SAMPLE_RUBRIC = """
- The paper must be 1,500 to 2,000 words, excluding the title page and references.
- You must cite at least five peer-reviewed journal articles published within the
  last 5 years.
- No more than two sources may be non-research citations.
- APA 7th edition formatting is required, including a title page, running head and
  a hanging-indent reference list.
- The paper must be double-spaced with 1-inch margins in Times New Roman.
- Your methodology section must address the IRB approval process.
- Include a Limitations section and Implications for Practice.
- The student demonstrates critical analysis rather than description.
"""


def test_rubric_extraction() -> None:
    out = rubric.extract(SAMPLE_RUBRIC, source_name="NUR 6050")
    described = {r["label"] for r in out["requirements"]}
    for label in ("Word count", "Peer-reviewed sources", "Source recency",
                  "APA 7th edition", "Title page", "Running head",
                  "Hanging indent", "Double spacing", "One-inch margins",
                  "Times New Roman", "IRB / ethical approval", "Limitations",
                  "Implications for practice"):
        check(f"{label} extracted", label in described, True)

    by_label = {r["label"]: r for r in out["requirements"]}
    words = by_label["Word count"]
    check("word range parsed", (words["value"], words["value_max"]),
          (1500.0, 2000.0))
    check("operator is between", words["operator"], "between")
    sources = by_label["Peer-reviewed sources"]
    check("count parsed from a spelled-out number", sources["value"], 5.0)
    check("operator", sources["operator"], ">=")


def test_countable_and_qualitative_are_separated() -> None:
    out = rubric.extract(SAMPLE_RUBRIC)
    qualitative = [r for r in out["requirements"] if not r["checkable"]]
    check("the judgement criterion is not checkable", len(qualitative) >= 1, True)
    contains("and says why", qualitative[0]["note"], "No program can score this")
    contains("summary states both counts", out["summary"], "it cannot")
    contains("caveat admits pattern matching", out["caveat"], "pattern-based")


def test_every_requirement_keeps_its_source_sentence() -> None:
    """An extracted requirement the user cannot trace back is one they cannot
    trust."""
    for requirement in rubric.extract(SAMPLE_RUBRIC)["requirements"]:
        check(f"{requirement['label']} carries its source",
              bool(requirement["source_text"].strip()), True)


def test_general_artefact_does_not_duplicate_the_specific_one() -> None:
    out = rubric.extract("- Include a Level 1 heading for each major section.")
    labels = [r["label"] for r in out["requirements"]]
    check("Level 1 headings extracted", "Level 1 headings" in labels, True)
    check("bare Headings not also extracted", "Headings" in labels, False)


def test_hyphenated_artefacts() -> None:
    out = rubric.extract("- Use a hanging-indent reference list and a title-page.")
    labels = {r["label"] for r in out["requirements"]}
    check("hyphenated hanging indent found", "Hanging indent" in labels, True)
    check("hyphenated title page found", "Title page" in labels, True)


def test_descriptive_prose_is_not_extracted() -> None:
    """A rubric is mostly commentary. Extracting all of it buries the
    requirements."""
    out = rubric.extract(
        "This assignment builds on the concepts introduced in week three. "
        "The literature in this area has grown considerably.")
    check("nothing extracted from description", out["requirements"], [])


def test_manual_requirements() -> None:
    manual = rubric.manual("At least 3 primary studies", kind="source_count",
                           operator=">=", value=3, unit="sources", target="any")
    check("checkable", manual.checkable, True)
    check("described", manual.describe(),
          "At least 3 primary studies: at least 3 sources")


# ================================================================= simulator


def draft_facts(**overrides) -> simulator.DraftFacts:
    base = dict(body_words=1750, source_count=6, peer_reviewed_count=6,
                source_years=[2022, 2023, 2021, 2024, 2022, 2023],
                section_titles=["Introduction", "Methods", "Limitations",
                                "Implications for Practice", "Discussion"],
                has_title_page=True, has_abstract=True, has_references=True,
                text="IRB approval was obtained for all included studies.")
    base.update(overrides)
    return simulator.DraftFacts(**base)


def test_simulator_never_scores() -> None:
    out = simulator.run(rubric.extract(SAMPLE_RUBRIC)["requirements"],
                        draft_facts())
    check("no score key", "score" in out, False)
    check("no grade key", "grade" in out, False)
    check("no percentage key", "percentage" in out, False)
    contains("and says why", out["no_score_note"], "no predicted grade")
    contains("naming the risk", out["no_score_note"], "stop you working")


def test_simulator_passes_a_compliant_draft() -> None:
    out = simulator.run(rubric.extract(SAMPLE_RUBRIC)["requirements"],
                        draft_facts())
    by_label = {r["label"]: r for r in out["results"]}
    check("word count met", by_label["Word count"]["status"], simulator.MET)
    check("sources met", by_label["Peer-reviewed sources"]["status"],
          simulator.MET)
    check("recency met", by_label["Source recency"]["status"], simulator.MET)
    check("limitations met", by_label["Limitations"]["status"], simulator.MET)


def test_simulator_reports_the_gap() -> None:
    out = simulator.run(rubric.extract(SAMPLE_RUBRIC)["requirements"],
                        draft_facts(body_words=1180, source_count=4,
                                    peer_reviewed_count=4,
                                    source_years=[2014, 2019, 2022, 2023]))
    by_label = {r["label"]: r for r in out["results"]}
    words = by_label["Word count"]
    check("short", words["status"], simulator.NOT_MET)
    contains("gap quantified", words["gap"], "320")
    sources = by_label["Peer-reviewed sources"]
    contains("shortfall quantified", sources["gap"], "1 more needed")
    recency = by_label["Source recency"]
    check("old sources caught", recency["status"], simulator.NOT_MET)
    contains("the offending years are named", recency["gap"], "2014")


def test_body_mention_is_partial_not_met() -> None:
    """A rubric asking for a section usually means a heading a marker can find."""
    out = simulator.run(rubric.extract(SAMPLE_RUBRIC)["requirements"],
                        draft_facts(section_titles=["Introduction", "Methods"]))
    by_label = {r["label"]: r for r in out["results"]}
    irb = by_label["IRB / ethical approval"]
    check("partial", irb["status"], simulator.PARTIAL)
    contains("explains the difference", irb["advice"], "heading a marker can find")


def test_recency_without_years_is_unknown_not_failed() -> None:
    out = simulator.run(rubric.extract(SAMPLE_RUBRIC)["requirements"],
                        draft_facts(source_years=[]))
    by_label = {r["label"]: r for r in out["results"]}
    check("cannot check rather than fail",
          by_label["Source recency"]["status"], simulator.UNKNOWN)


def test_facts_from_an_empty_project() -> None:
    """The simulator runs on every preview, including on a project with nothing
    in it. It must not raise."""
    facts = simulator.facts_from_project(Project(project_id="p", topic="t"))
    check("no words", facts.body_words, 0)
    check("no sources", facts.source_count, 0)
    out = simulator.run(rubric.extract(SAMPLE_RUBRIC)["requirements"], facts)
    check("still produces results", len(out["results"]) > 0, True)


# ================================================================== journals


def test_journal_profiles() -> None:
    profiles = journals.catalogue()
    check("eight profiles", len(profiles), 8)
    for profile in profiles:
        check(f"{profile['key']} has a name", bool(profile["name"].strip()), True)
        contains(f"{profile['key']} carries the verify note",
                 profile["verify"], "check the current")


def test_structured_abstract_check() -> None:
    """An abstract missing a required heading is returned without review."""
    profile = journals.get("jan")
    out = journals.check(profile, body_words=4000,
                         abstract="Aim: x.\nDesign: y.\nMethods: z.\n")
    structured = next(f for f in out["findings"]
                      if f["label"] == "Structured abstract")
    check("not met", structured["status"], "not_met")
    contains("names what is missing", structured["advice"], "Impact")
    contains("and the consequence", structured["advice"], "without review")


def test_word_and_reference_limits() -> None:
    profile = journals.get("lancet")
    out = journals.check(profile, body_words=5200, reference_count=44,
                         abstract="Background: x.")
    by_label = {f["label"]: f for f in out["findings"]}
    check("over the word limit", by_label["Word limit"]["status"], "not_met")
    contains("says how much to cut", by_label["Word limit"]["advice"], "700")
    check("over the reference cap", by_label["Reference limit"]["status"],
          "not_met")


def test_non_apa_journal_is_flagged() -> None:
    out = journals.check(journals.get("ijns"), body_words=1000, abstract="")
    style = next(f for f in out["findings"] if f["label"] == "Reference style")
    check("flagged", style["status"], "not_met")
    contains("warns the conversion is substantive", style["advice"],
             "in-text citations")


def test_statements_are_cannot_check() -> None:
    """The tool cannot see a submission form."""
    out = journals.check(journals.get("bmj_open"), body_words=1000, abstract="")
    statements = [f for f in out["findings"]
                  if f["label"].startswith("Statement:")]
    check("several statements listed", len(statements) >= 4, True)
    for statement in statements:
        check(f"{statement['label']} is not scored",
              statement["status"], "cannot_check")


def test_guideline_parser() -> None:
    profile = journals.parse(
        "Manuscripts should not exceed 4000 words, excluding references.\n"
        "The abstract must be structured with the following headings: "
        "Background: Objectives: Methods: Results: Conclusions:\n"
        "Abstracts are limited to 250 words.\n"
        "No more than 40 references.\n"
        "Authors must complete the relevant EQUATOR checklist (CONSORT, PRISMA "
        "or STROBE).\n"
        "A competing interests statement and funding statement are required. "
        "Data availability must be declared.\n"
        "References should follow Vancouver style.\n"
        "Manuscripts undergo double-blind review; remove all identifying "
        "information.\n",
        name="Test Journal")
    check("word limit", profile.word_limit, 4000)
    check("abstract limit", profile.abstract_limit, 250)
    check("structured", profile.abstract_structured, True)
    check("headings", profile.abstract_headings,
          ["Background", "Objectives", "Methods", "Results", "Conclusions"])
    check("reference limit", profile.reference_limit, 40)
    check("style", profile.style, "Vancouver")
    check("blinded", profile.blinded, True)
    contains("checklists found", profile.reporting_guideline, "PRISMA")
    check("statements found",
          {"Conflict of interest", "Funding", "Data availability"}
          <= set(profile.required_statements), True)


def test_parser_invents_nothing() -> None:
    """A blank prompts the author to look it up; an invented number does not."""
    profile = journals.parse("Submit your manuscript through the portal.")
    check("no word limit invented", profile.word_limit, None)
    check("no reference limit invented", profile.reference_limit, None)
    check("not claimed structured", profile.abstract_structured, False)
    check("no statements invented", profile.required_statements, [])


def main() -> int:
    for name, function in sorted(globals().items()):
        if name.startswith("test_") and callable(function):
            function()
    print(f"tests/test_research_tools.py: {CHECKS} checks, {len(FAILURES)} failures")
    for failure in FAILURES:
        print(f"  ✗ {failure}")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    raise SystemExit(main())
