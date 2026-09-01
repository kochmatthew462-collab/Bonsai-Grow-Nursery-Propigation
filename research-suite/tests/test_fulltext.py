"""
Tests for full-text ingestion, anchoring, grounding and extraction.

The defects this suite exists to catch are the quiet ones — the ones that leave
a plausible value in a matrix cell or a green tick beside an unsupported claim:

* **Section mislabelling.** The first version searched for headings inside every
  line, so "Abstract reasoning was assessed" re-tagged the rest of the paper as
  an abstract and every anchor after it named the wrong section. Headings are
  now matched against the whole line, and both halves of that are tested.
* **A locator that only finds plagiarism.** The first `locate()` scored 8-word
  shingles alone and returned nothing for a properly paraphrased claim — which
  is to say, it could anchor exactly the sentences that were already a problem
  and none of the ones that were fine. Paraphrase matching is tested directly.
* **Truncated numbers.** `95% CI [0.45, 0.85]` came out as `95% CI [0`, and
  `p < .001,` kept its comma. A half-copied interval in an evidence matrix reads
  as a transcription error the user has to chase down.
* **Invention.** Nothing may be returned that cannot be pointed at. Every field
  carries a page and the sentence it was read from, and a source that states
  none of these things must produce an empty matrix and a `missing` list, not a
  filled one.

Everything runs offline. The PDF path is exercised against a PDF generated
here by matplotlib, and skipped with a printed line — never silently — when
pypdf is unavailable.

Run: python3 tests/test_fulltext.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.sources import fulltext  # noqa: E402

FAILURES: list[str] = []
CHECKS = 0
SKIPPED: list[str] = []


def check(label: str, got, want) -> None:
    global CHECKS
    CHECKS += 1
    if got != want:
        FAILURES.append(f"{label}\n     got: {got!r}\n    want: {want!r}")


def contains(label: str, haystack, needle: str) -> None:
    global CHECKS
    CHECKS += 1
    if needle.lower() not in str(haystack or "").lower():
        FAILURES.append(f"{label}\n    {needle!r} not in {haystack!r}")


def absent(label: str, haystack, needle: str) -> None:
    global CHECKS
    CHECKS += 1
    if needle.lower() in str(haystack or "").lower():
        FAILURES.append(f"{label}\n    {needle!r} unexpectedly in {haystack!r}")


def truthy(label: str, value) -> None:
    check(label, bool(value), True)


PAPER = """Effect of a Nurse-Led Handoff Bundle on Adverse Events

Abstract
This study evaluated a structured handoff bundle across six units.

Introduction
Handoff failures are implicated in a large share of sentinel events.

Methods
We conducted a cluster randomised trial across six medical-surgical units.
A total of 1,204 patients were enrolled between January and June 2023.
We used multivariable logistic regression and an intention-to-treat analysis.
Ethical approval was granted by the institutional review board of the study site.

Results
Adverse events fell in the intervention arm (OR = 0.62, 95% CI [0.45, 0.85], p = .003).
Mean pain improved (M = 3.10, SD = 1.20), t(210) = 4.55, p < .001, d = 0.42.
The response rate was 78% among nurses (n = 212).

Limitations
Limitations include a single health system and a six-month follow-up period.

Funding
This work was supported by a grant from the National Institute of Nursing Research.

Conflicts of Interest
The authors declare no competing interests.
"""


def _passages(text: str = PAPER, key: str = "smith2023"):
    return fulltext.passages_from_dicts(
        fulltext.read_text(text, work_key=key)["passages"])


# ------------------------------------------------------------------ headings


def test_heading_is_matched_against_the_whole_line() -> None:
    check("bare heading", fulltext.heading_name("Methods"), "methods")
    check("numbered heading", fulltext.heading_name("2. Methods"), "methods")
    check("colon", fulltext.heading_name("Results:"), "results")
    check("uppercase", fulltext.heading_name("DISCUSSION"), "discussion")
    check("materials and methods",
          fulltext.heading_name("Materials and Methods"), "methods")
    check("conflicts", fulltext.heading_name("Conflicts of Interest"),
          "conflicts")


def test_a_sentence_that_starts_with_a_heading_word_is_not_a_heading() -> None:
    """The bug this replaced: one such sentence re-sectioned the whole paper."""
    check("abstract sentence",
          fulltext.heading_name("Abstract reasoning was assessed by matrices."), "")
    check("methods sentence",
          fulltext.heading_name("Methods were poor. We say so below."), "")
    check("long subtitle", fulltext.heading_name(
        "Discussion of the implications for medical-surgical nursing practice "
        "and for future research"), "")
    check("empty", fulltext.heading_name("   "), "")


def test_sections_are_assigned_per_paragraph() -> None:
    got = {p.section for p in _passages()}
    for name in ("abstract", "introduction", "methods", "results",
                 "limitations", "funding", "conflicts"):
        check(f"section present: {name}", name in got, True)
    by_section = {p.section: p.text for p in _passages()}
    contains("methods content", by_section["methods"], "cluster randomised")
    contains("results content", by_section["results"], "OR = 0.62")
    check("title has no section", _passages()[0].section, "")


def test_the_heading_line_is_not_left_in_the_paragraph_text() -> None:
    """"Limitations Limitations include..." was the symptom of keeping it."""
    text = {p.section: p.text for p in _passages()}["limitations"]
    check("no doubled heading", text.lower().startswith("limitations include"),
          True)
    absent("heading not repeated", text[:30], "limitations limitations")


def test_a_section_carries_across_a_page_break() -> None:
    two_pages = "Methods\nWe enrolled patients in six units.\f" \
                "A second paragraph of methods continues here at length."
    passages = _passages(two_pages)
    check("page 2 keeps the section", passages[-1].section, "methods")
    check("page 2 is page 2", passages[-1].page, 2)


def test_a_page_ending_on_a_heading_still_sets_the_next_page() -> None:
    """Reading the section off the last passage would lose it entirely."""
    text = "Some introductory prose that runs on for a while.\nResults\f" \
           "Adverse events fell in the intervention arm of the trial."
    passages = _passages(text)
    check("heading carried over the break", passages[-1].section, "results")


# ------------------------------------------------------------------- anchors


def test_every_passage_can_be_pointed_at() -> None:
    for passage in _passages():
        truthy(f"digest for {passage.anchor()}", passage.digest)
        truthy(f"work key for {passage.anchor()}", passage.work_key)
    check("anchor format", _passages()[0].anchor(), "p. 1, para. 1")
    check("second anchor", _passages()[1].anchor(), "p. 1, para. 2")


def test_a_digest_survives_reserialisation() -> None:
    original = _passages()
    round_tripped = fulltext.passages_from_dicts([p.as_dict() for p in original])
    check("count preserved", len(round_tripped), len(original))
    check("digests preserved", [p.digest for p in round_tripped],
          [p.digest for p in original])
    check("sections preserved", [p.section for p in round_tripped],
          [p.section for p in original])


def test_short_fragments_fold_into_their_predecessor() -> None:
    """A PDF line-breaks mid-sentence; one anchor per line is one per nothing."""
    text = ("This is a full paragraph of at least twelve words so that it "
            "stands alone.\n\nToo short.\n\n")
    passages = _passages(text)
    check("folded", len(passages), 1)
    contains("fragment kept", passages[0].text, "Too short")


def test_a_fragment_does_not_fold_across_a_section_boundary() -> None:
    text = ("A methods paragraph long enough to stand on its own two feet "
            "here.\n\nResults\n\nEvents fell.\n")
    sections = {p.section for p in _passages(text)}
    check("results kept separate", "results" in sections, True)


# ------------------------------------------------------------------ locating


def test_a_verbatim_sentence_is_found_and_flagged() -> None:
    matches = fulltext.locate(
        "A total of 1,204 patients were enrolled between January and June 2023.",
        _passages())
    truthy("found", matches)
    check("basis", matches[0]["basis"], "verbatim")
    check("section", matches[0]["section"], "methods")
    truthy("runs reported", matches[0]["verbatim_runs"])


def test_a_paraphrase_is_found_too() -> None:
    """The whole point. Shingles alone returned nothing here."""
    matches = fulltext.locate(
        "Adverse events were less frequent in the intervention arm, with an "
        "odds ratio of 0.62.", _passages())
    truthy("paraphrase anchored", matches)
    check("no verbatim run", matches[0]["verbatim_runs"], [])
    check("section", matches[0]["section"], "results")
    check("labelled a paraphrase", matches[0]["basis"], "close paraphrase")


def test_an_unrelated_sentence_finds_nothing() -> None:
    """An empty result is the answer this exists to give."""
    check("no false anchor", fulltext.locate(
        "Bonsai propagation requires careful humidity control in a mist "
        "chamber.", _passages()), [])


def test_stopwords_alone_do_not_make_a_match() -> None:
    check("function words are not evidence", fulltext.locate(
        "It was of the and to be in a for that this.", _passages()), [])


def test_matches_are_ordered_with_verbatim_first() -> None:
    """A lifted phrase is the finding that must not be buried under a better
    scoring paraphrase, so it leads even when it scores lower."""
    sentence = ("Nurses reported that the handover checklist was completed at "
                "every shift change without exception.")
    passages = fulltext.passages_from_dicts([
        # Heavy topical overlap, but nothing lifted.
        {"work_key": "w", "page": 1, "index": 0, "text":
            "Handover checklist completion was reported by nurses at shift "
            "change, and exception reporting was rare across every unit "
            "studied in this programme of work."},
        # One lifted run, and little else in common.
        {"work_key": "w", "page": 9, "index": 0, "text":
            "Across the programme, staff said the handover checklist was "
            "completed at every shift change without exception, which the "
            "audit could not corroborate."},
    ])
    matches = fulltext.locate(sentence, passages)
    check("both matched", len(matches), 2)
    check("verbatim leads", matches[0]["page"], 9)
    truthy("runs reported", matches[0]["verbatim_runs"])
    check("the higher-scoring paraphrase is still reported",
          matches[1]["page"], 1)


def test_locate_reports_a_page_that_can_be_cited() -> None:
    match = fulltext.locate("Ethical approval was granted by the institutional "
                            "review board of the study site.", _passages())[0]
    check("page", match["page"], 1)
    contains("anchor", match["anchor"], "para.")
    contains("excerpt", match["excerpt"], "Ethical approval")


# ----------------------------------------------------------------- grounding


CLAIMS = [
    {"claim_id": "c1", "support_type": "paraphrase", "work_keys": ["smith2023"],
     "text": "A structured handoff bundle reduced adverse events in a cluster "
             "randomised trial."},
    {"claim_id": "c2", "support_type": "paraphrase", "work_keys": ["smith2023"],
     "text": "A total of 1,204 patients were enrolled between January and June "
             "2023."},
    {"claim_id": "c3", "support_type": "paraphrase", "work_keys": ["smith2023"],
     "text": "Handoff bundles reduce paediatric mortality in intensive care."},
    {"claim_id": "c4", "support_type": "paraphrase", "work_keys": ["jones2024"],
     "text": "Nursing shortages are worsening across the sector."},
    {"claim_id": "c5", "support_type": "no-citation", "work_keys": [],
     "text": "This paper argues the following."},
]


def test_grounding_separates_the_three_outcomes() -> None:
    report = fulltext.ground(CLAIMS, _passages())
    status = {row["claim_id"]: row["status"] for row in report["claims"]}
    check("supported", status["c1"], "anchored")
    check("verbatim", status["c2"], "verbatim overlap")
    check("unsupported", status["c3"], "not found in source")
    check("uncheckable", status["c4"], "no full text")
    check("own analysis is skipped", "c5" in status, False)
    check("unsupported list", report["unsupported"], ["c3"])
    check("verbatim list", report["verbatim"], ["c2"])
    check("unchecked list", report["unchecked"], ["c4"])
    check("checked count", report["checked"], 3)


def test_an_unchecked_claim_is_not_called_wrong() -> None:
    """"No full text" and "not in the source" are different findings."""
    row = next(r for r in fulltext.ground(CLAIMS, _passages())["claims"]
               if r["claim_id"] == "c4")
    contains("says why", row["detail"], "could not be checked")
    contains("not an accusation", row["detail"], "not the same as it being wrong")
    check("not counted as unsupported",
          "c4" in fulltext.ground(CLAIMS, _passages())["unsupported"], False)


def test_a_verbatim_claim_is_told_what_to_do() -> None:
    row = next(r for r in fulltext.ground(CLAIMS, _passages())["claims"]
               if r["claim_id"] == "c2")
    contains("quote or rewrite", row["detail"], "quote it")
    contains("locator mentioned", row["detail"], "locator")


def test_grounding_does_not_claim_to_verify_truth() -> None:
    contains("honest about what matching means",
             fulltext.ground(CLAIMS, _passages())["note"], "not that it is true")


def test_grounding_only_searches_the_works_a_claim_cites() -> None:
    """A claim must not be anchored to a source it does not cite."""
    other = _passages(PAPER, key="other2020")
    report = fulltext.ground(
        [{"claim_id": "x", "support_type": "paraphrase",
          "work_keys": ["smith2023"],
          "text": "Adverse events fell in the intervention arm."}], other)
    check("wrong source is not used", report["claims"][0]["status"],
          "no full text")


def test_grounding_with_nothing_ingested_is_empty_not_wrong() -> None:
    report = fulltext.ground(CLAIMS, [])
    check("nothing marked unsupported", report["unsupported"], [])
    check("everything unchecked", len(report["unchecked"]), 4)


# ---------------------------------------------------------------- extraction


def test_extraction_finds_the_matrix_fields() -> None:
    fields = fulltext.extract(_passages())["fields"]
    check("design", fields["design"][0]["value"], "cluster randomised trial")
    check("ethics", fields["ethical_approval"][0]["value"], "stated")
    check("funding", fields["funding"][0]["value"], "stated")
    check("conflicts", fields["conflicts"][0]["value"], "stated")
    contains("limitations", fields["limitations"][0]["value"],
             "single health system")
    analyses = {row["value"] for row in fields["analysis"]}
    check("logistic regression", "logistic regression" in analyses, True)
    check("ITT", "intention-to-treat analysis" in analyses, True)


def test_a_confidence_interval_is_not_truncated() -> None:
    """"95% CI [0" in a matrix cell reads as a transcription error."""
    values = {row["value"] for row in
              fulltext.extract(_passages())["fields"]["statistics"]}
    check("interval intact", "95% CI [0.45, 0.85]" in values, True)
    for value in values:
        if "CI" in value and "[" in value:
            check(f"brackets balanced in {value!r}", value.count("["),
                  value.count("]"))


def test_a_p_value_does_not_keep_its_trailing_comma() -> None:
    values = {row["value"] for row in
              fulltext.extract(_passages())["fields"]["statistics"]}
    check("p = .003", "p = .003" in values, True)
    check("p < .001 without its comma", "p < .001" in values, True)
    for value in values:
        check(f"no trailing comma in {value!r}", value.endswith(","), False)


def test_statistics_and_analyses_are_separate_fields() -> None:
    """The name of a test is methodology; a number is a result."""
    extracted = fulltext.extract(_passages())["fields"]
    stats = {row["value"] for row in extracted["statistics"]}
    analyses = {row["value"] for row in extracted["analysis"]}
    check("test name not in results", "chi-square test" in stats, False)
    check("effect size is a result", "d = 0.42" in stats, True)
    check("M and SD together", "M = 3.10, SD = 1.20" in stats, True)
    check("t statistic", "t(210) = 4.55" in stats, True)
    truthy("analyses found", analyses)


def test_the_specific_design_wins_over_the_general_one() -> None:
    designs = [row["value"] for row in
               fulltext.extract(_passages())["fields"]["design"]]
    check("cluster reported", "cluster randomised trial" in designs, True)
    check("plain RCT not double-reported",
          "randomised controlled trial" in designs, False)


def test_a_plain_rct_is_still_recognised() -> None:
    passages = _passages("Methods\nWe conducted a randomised controlled trial "
                         "in two hospitals over one year.")
    designs = [row["value"] for row in
               fulltext.extract(passages)["fields"]["design"]]
    check("RCT found", designs, ["randomised controlled trial"])


def test_the_same_number_written_two_ways_is_one_finding() -> None:
    passages = _passages("Methods\nWe enrolled 1,204 patients in the study. "
                         "The sample of 1204 was adequate for the analysis.")
    values = [row["value"] for row in
              fulltext.extract(passages)["fields"]["sample_size"]]
    check("deduplicated", len(values), 1)


def test_every_extracted_value_carries_its_evidence() -> None:
    """Nothing may be returned that the user cannot check in seconds."""
    for name, rows in fulltext.extract(_passages())["fields"].items():
        for row in rows:
            truthy(f"{name} has a page", row["page"])
            truthy(f"{name} has an anchor", row["anchor"])
            truthy(f"{name} has its sentence", row["sentence"])
            check(f"{name} value appears in its sentence or is a marker",
                  row["value"][:12].lower() in row["sentence"].lower()
                  or row["value"] in ("stated",)
                  or name in ("design", "analysis"), True)
            check(f"{name} exposes no internal key", "_key" in row, False)


def test_the_suggested_sample_size_prefers_the_methods_section() -> None:
    suggested = fulltext.extract(_passages())["suggested_sample_size"]
    check("value", suggested["value"], "1,204")
    check("from methods", suggested["section"], "methods")
    contains("with its sentence", suggested["sentence"], "1,204 patients")


def test_a_source_that_states_nothing_produces_nothing() -> None:
    """An empty cell gets checked; a plausible invented one does not."""
    passages = _passages("Introduction\nThis is a short opinion piece about "
                         "the state of the profession and its future.")
    result = fulltext.extract(passages)
    check("no design invented", result["fields"].get("design"), None)
    check("no sample invented", result["suggested_sample_size"], None)
    for name in ("design", "sample_size", "statistics", "funding", "conflicts",
                 "ethical_approval", "limitations", "analysis"):
        check(f"{name} listed as missing", name in result["missing"], True)
    contains("absence is itself a finding", result["missing_note"],
             "absence belongs in your appraisal")


def test_extraction_says_what_it_is() -> None:
    note = fulltext.extract(_passages())["note"]
    contains("a reader not a model", note, "reader, not a model")
    contains("says to check", note, "check each one")


# ----------------------------------------------------------------- ingestion


def test_pasted_text_warns_that_pages_are_approximate() -> None:
    contains("single-page caveat", fulltext.read_text(PAPER)["note"],
             "approximate")


def test_form_feeds_become_pages() -> None:
    result = fulltext.read_text("Page one of this document, at some length "
                                "here.\fPage two of this document, likewise.")
    check("two pages", result["pages"], 2)
    check("page numbers", [p["page"] for p in result["passages"]], [1, 2])


def test_empty_input_is_handled() -> None:
    check("no passages", fulltext.read_text("")["passages"], [])
    check("no crash on none", fulltext.paragraphs(""), [])


def test_a_missing_or_broken_pypdf_degrades_rather_than_fails() -> None:
    """Losing PDF parsing must not lose the whole ingestion path."""
    saved = fulltext._PYPDF
    try:
        fulltext._PYPDF = (False, "pypdf is not installed.")
        result = fulltext.read_pdf(Path("nonexistent.pdf"))
        check("no passages", result["passages"], [])
        check("marked unavailable", result["available"], False)
        contains("names the cause", result["note"], "not installed")
        contains("offers the way round", result["note"], "paste the text")
        contains("says how to fix it", result["note"], "pip install pypdf")
    finally:
        fulltext._PYPDF = saved


def test_an_unreadable_pdf_is_reported_not_raised() -> None:
    if not fulltext.pypdf_available():
        SKIPPED.append("unreadable-PDF check (pypdf unavailable)")
        return
    import logging
    logging.getLogger("pypdf").setLevel(logging.CRITICAL)  # it is meant to fail
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "broken.pdf"
        path.write_bytes(b"this is not a PDF at all")
        result = fulltext.read_pdf(path)
        check("no passages", result["passages"], [])
        contains("says it could not open it", result["note"], "could not open")


def _write_sample_pdf(path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages

    pages = [
        ["Effect of a Nurse-Led Handoff Bundle", "", "Abstract",
         "This study evaluated a structured handoff bundle across six units."],
        ["Methods",
         "We conducted a cluster randomised trial across six medical-surgical",
         "units. A total of 1,204 patients were enrolled between January and",
         "June 2023. Ethical approval was granted by the institutional review",
         "board.", "", "Results",
         "Adverse events fell in the intervention arm (OR = 0.62, 95% CI [0.45,",
         "0.85], p = .003)."],
        ["Limitations",
         "Limitations include a single health system and a short follow-up."],
    ]
    with PdfPages(path) as pdf:
        for lines in pages:
            figure = plt.figure(figsize=(8.5, 11))
            y = 0.94
            for line in lines:
                figure.text(0.1, y, line, fontsize=10, family="serif")
                y -= 0.03
            pdf.savefig(figure)
            plt.close(figure)


def test_a_real_pdf_reads_into_anchored_passages() -> None:
    if not fulltext.pypdf_available():
        SKIPPED.append("PDF round-trip (pypdf unavailable)")
        return
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "paper.pdf"
        _write_sample_pdf(path)
        result = fulltext.read_pdf(path, work_key="smith2023")
        check("three pages", result["pages"], 3)
        truthy("passages found", result["passages"])
        passages = fulltext.passages_from_dicts(result["passages"])
        sections = {p.section: p for p in passages}
        check("methods on page 2", sections["methods"].page, 2)
        check("results on page 2", sections["results"].page, 2)
        check("limitations on page 3", sections["limitations"].page, 3)

        extracted = fulltext.extract(passages)
        check("design read from the PDF",
              extracted["fields"]["design"][0]["value"],
              "cluster randomised trial")
        check("sample size read from the PDF",
              extracted["suggested_sample_size"]["value"], "1,204")
        # The interval is split across a line break in the rendered page. If
        # the reassembly is wrong this is where it shows.
        values = {row["value"] for row in extracted["fields"]["statistics"]}
        check("interval survived the line break",
              "95% CI [0.45, 0.85]" in values, True)


def main() -> int:
    for name, function in sorted(globals().items()):
        if name.startswith("test_") and callable(function):
            function()
    print(f"tests/test_fulltext.py: {CHECKS} checks, {len(FAILURES)} failures")
    for note in SKIPPED:
        print(f"  · skipped: {note}")
    for failure in FAILURES:
        print(f"  ✗ {failure}")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    raise SystemExit(main())
