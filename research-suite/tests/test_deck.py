"""
Tests for the slide deck and for the figures that are supposed to reach it.

Every defect this suite covers was of one kind: a feature that existed, worked,
and was reachable from nothing. The code was written and tested; no caller ever
passed it anything. That is the hardest sort of gap to see, because the module
is present, the function is correct, and the only symptom is an artefact that
quietly lacks something.

* `ApaDeck.figure_slide` builds a proper APA figure slide. `build_deck` was
  called without a `figures` argument, so every deck exported with no figures
  in it while the interface said each one had been placed "on a slide in the
  deck".
* The evidence-level chart was drawn and shown on screen but never recorded on
  the project, so it was silently absent from the exported paper — while the
  four other figure types, which went through a different route, were not.
* Speaker notes read `claim-003: <rationale>`. The specification asked for
  formal, complete sentences carrying APA in-text citations, which is what a
  presenter actually needs: the citation has to be sayable aloud.

The assertions are made against the saved .pptx and .docx — the packaged XML,
not the builder's return values — because that is where this class of defect
becomes visible.

Run: python3 tests/test_deck.py
"""

from __future__ import annotations

import os
import re
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("KRS_DATA_DIR", tempfile.mkdtemp(prefix="krs-deck-test-"))

from app.apa import deck as deck_module  # noqa: E402
from app.apa.citations import CitationContext  # noqa: E402
from app.models import (  # noqa: E402
    Author, Claim, EvidenceLevel, Project, SupportType, TitlePage, Work,
)

FAILURES: list[str] = []
CHECKS = 0


def check(label: str, got, want) -> None:
    global CHECKS
    CHECKS += 1
    if got != want:
        FAILURES.append(f"{label}\n     got: {got!r}\n    want: {want!r}")


def contains(label: str, haystack, needle: str) -> None:
    global CHECKS
    CHECKS += 1
    if needle.lower() not in str(haystack or "").lower():
        FAILURES.append(f"{label}\n    {needle!r} not in {str(haystack)[:400]!r}")


def absent(label: str, haystack, needle: str) -> None:
    global CHECKS
    CHECKS += 1
    if needle.lower() in str(haystack or "").lower():
        FAILURES.append(f"{label}\n    {needle!r} unexpectedly present")


def _project() -> Project:
    project = Project(project_id="deck-test", topic="Nurse staffing and falls")
    project.title_page = TitlePage(variant="student", title="Nurse Staffing and Falls",
                                   authors=["M. Koch"])
    project.works = [
        Work(key="smith2023", title="Staffing and inpatient falls", year="2023",
             authors=[Author(family="Smith", given="J"), Author(family="Ng", given="A")],
             level=EvidenceLevel.LEVEL_II, container="Journal of Nursing Care"),
        Work(key="who2022", title="Global patient safety report", year="2022",
             authors=[Author.group("World Health Organization")],
             level=EvidenceLevel.LEVEL_V),
    ]
    project.claims = [
        Claim(claim_id="c1", section="Introduction", order=0,
              text="Falls remain the most frequently reported inpatient safety incident.",
              work_keys=["who2022"], support_type=SupportType.PARAPHRASE,
              rationale="it is the most recent global surveillance figure available"),
        Claim(claim_id="c2", section="Introduction", order=1,
              text="Higher registered-nurse staffing was associated with fewer falls.",
              work_keys=["smith2023"], support_type=SupportType.PARAPHRASE),
        Claim(claim_id="c3", section="Introduction", order=2,
              text="Staffing is “the single most modifiable determinant of fall "
                   "rates”.",
              work_keys=["smith2023"], support_type=SupportType.DIRECT_QUOTE,
              locus="p. 412"),
        Claim(claim_id="c4", section="Discussion", order=3,
              text="This review argues for a prospective replication.",
              support_type=SupportType.NO_CITATION),
    ]
    return project


def _context(project: Project) -> CitationContext:
    """The same context the exporter builds: every work in the project, so year
    letters and expanded et al. resolve the way they will in the paper."""
    return CitationContext(project.works,
                           {"World Health Organization": "WHO"})


def _notes_text(path: Path) -> list[str]:
    """Every notes page's text, in slide order."""
    archive = zipfile.ZipFile(path)
    names = sorted(
        (n for n in archive.namelist()
         if re.match(r"ppt/notesSlides/notesSlide\d+\.xml$", n)),
        key=lambda n: int(re.search(r"(\d+)", n.rsplit("/", 1)[1]).group(1)))
    return ["\n".join(re.findall(r"<a:t>([^<]*)</a:t>",
                                 archive.read(name).decode("utf-8")))
            for name in names]


def _media(path: Path) -> list[str]:
    archive = zipfile.ZipFile(path)
    return sorted(n for n in archive.namelist() if n.startswith("ppt/media/"))


# ------------------------------------------------------------- speaker notes


def test_speaker_notes_are_sentences_not_claim_ids() -> None:
    project = _project()
    plans = deck_module.ApaDeck(project, _context(project)).plan_from_claims()
    notes = "\n".join(plan.speaker_notes for plan in plans)
    absent("no raw claim ids", notes, "c1:")
    absent("no raw claim ids", notes, "claim-")
    contains("names the section", notes, "This slide covers Introduction")
    for line in notes.splitlines():
        check(f"complete sentence: {line[:50]!r}",
              line.rstrip().endswith((".", "!", "?", "”")), True)


def test_speaker_notes_carry_apa_in_text_citations() -> None:
    """A presenter has to be able to attribute a point out loud."""
    project = _project()
    plans = deck_module.ApaDeck(project, _context(project)).plan_from_claims()
    notes = "\n".join(plan.speaker_notes for plan in plans)
    contains("group author abbreviated", notes, "(WHO, 2022)")
    contains("two authors joined with an ampersand", notes, "(Smith & Ng, 2023")
    contains("quotation carries its locator", notes, "p. 412)")


def test_a_direct_quotation_is_flagged_in_the_notes() -> None:
    project = _project()
    plans = deck_module.ApaDeck(project, _context(project)).plan_from_claims()
    notes = "\n".join(plan.speaker_notes for plan in plans)
    contains("says it is a quotation", notes, "direct quotation")


def test_an_uncited_claim_gets_no_invented_citation() -> None:
    project = _project()
    plans = deck_module.ApaDeck(project, _context(project)).plan_from_claims()
    discussion = next(p for p in plans if p.title.startswith("Discussion"))
    contains("the sentence is there", discussion.speaker_notes,
             "prospective replication")
    absent("no citation attached", discussion.speaker_notes, "(")
    absent("no references pointer on an uncited slide",
           discussion.speaker_notes, "Full references")


def test_the_rationale_becomes_a_sentence() -> None:
    project = _project()
    plans = deck_module.ApaDeck(project, _context(project)).plan_from_claims()
    notes = "\n".join(plan.speaker_notes for plan in plans)
    contains("rationale reads as prose", notes,
             "This source was chosen because it is the most recent")


# -------------------------------------------------------------- figure slides


def _figure_png(directory: Path) -> Path:
    """A real PNG, drawn by the same module the application uses."""
    from app.apa import figures as figures_module
    return Path(figures_module.forest_plot(
        [figures_module.EffectEstimate(label="Smith (2023)", estimate=0.62,
                                       lower=0.45, upper=0.85, weight=100.0)],
        path=directory / "figure-forest.png", title="Odds of Falling",
        measure="Odds ratio").path)


def test_figures_reach_the_deck() -> None:
    """`figure_slide` was implemented, correct, and passed nothing."""
    with tempfile.TemporaryDirectory() as directory:
        out = Path(directory)
        image = _figure_png(out)
        path = out / "deck.pptx"
        project = _project()
        deck_module.build_deck(
            project, _context(project), str(path),
            figures=[deck_module.Slide(
                title="Odds of Falling", figure_path=str(image),
                figure_number=1, figure_title="Odds of Falling",
                figure_note="Squares show each study's odds ratio.",
                speaker_notes="Figure 1, Odds of Falling, is on screen now.",
                kind="figure")])
        check("the image is packaged", _media(path), ["ppt/media/image1.png"])
        notes = "\n".join(_notes_text(path))
        contains("the figure's notes are packaged too", notes,
                 "Figure 1, Odds of Falling")


def test_a_deck_with_no_figures_still_builds() -> None:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "deck.pptx"
        project = _project()
        deck_module.build_deck(project, _context(project), str(path))
        check("no media", _media(path), [])
        check("still a valid package", path.exists(), True)


def test_a_missing_image_does_not_break_the_deck() -> None:
    """A figure file deleted between building and exporting must not lose the
    deck along with it."""
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "deck.pptx"
        project = _project()
        deck_module.build_deck(
            project, _context(project), str(path),
            figures=[deck_module.Slide(title="Gone",
                                       figure_path=str(Path(directory) / "nope.png"),
                                       figure_number=1, kind="figure")])
        check("built anyway", path.exists(), True)
        check("no phantom media", _media(path), [])


# ------------------------------------------------ the export wiring in main.py


def test_every_figure_route_attaches_to_the_project() -> None:
    """The level chart drew, displayed, and never reached the paper.

    It went through its own route, which did not write to the figure ledger the
    exporter reads. Both routes now share one function; this asserts the
    ledger entry rather than the drawing, because the drawing was never the
    part that was broken.
    """
    import app.main as main_module
    from app.apa import figures as figures_module

    with tempfile.TemporaryDirectory() as directory:
        project = _project()
        figure = figures_module.level_distribution_figure(
            {"II": 1, "V": 1}, path=Path(directory) / "figure-levels.png")
        name = main_module._attach_figure(
            project, figure, kind="levels",
            title="Distribution of evidence levels", caption="")
        check("name returned", name, "figure-levels.png")
        stored = project.notes["figures"]
        check("one entry", len(stored), 1)
        check("kind recorded", stored[0]["kind"], "levels")
        check("note carried", bool(stored[0]["note"]), True)
        check("table carried", bool(stored[0]["table"]["rows"]), True)

        # Attaching the same figure twice replaces rather than duplicates: a
        # redrawn chart must not appear in the paper two times.
        main_module._attach_figure(project, figure, kind="levels",
                                   title="Distribution of evidence levels")
        check("still one entry", len(project.notes["figures"]), 1)


def test_figure_speaker_notes_are_built_from_the_figures_own_data() -> None:
    import app.main as main_module

    notes = main_module._figure_speaker_notes({
        "title": "Odds of Falling",
        "note": "Squares show each study's odds ratio",
        "caption": "Adapted from the included trials",
        "table": {"headers": ["Study", "Odds ratio"],
                  "rows": [["Smith (2023)", "0.62"]]},
    }, 2)
    contains("names the figure", notes, "Figure 2, Odds of Falling")
    contains("the APA note is there", notes, "odds ratio")
    contains("counts what is plotted", notes, "1 entry across 2 columns")
    contains("gives the first row", notes, "Smith (2023), 0.62")
    contains("reminds about attribution", notes, "citation on the slide")
    for line in notes.splitlines():
        check(f"complete sentence: {line[:40]!r}", line.rstrip().endswith("."), True)


def test_figure_speaker_notes_survive_a_figure_with_no_table() -> None:
    import app.main as main_module
    notes = main_module._figure_speaker_notes(
        {"title": "Incidence", "note": "", "caption": "", "table": None}, 1)
    contains("still names the figure", notes, "Figure 1, Incidence")
    check("no invented row count", "entry across" in notes, False)


def main() -> int:
    for name, function in sorted(globals().items()):
        if name.startswith("test_") and callable(function):
            function()
    print(f"tests/test_deck.py: {CHECKS} checks, {len(FAILURES)} failures")
    for failure in FAILURES:
        print(f"  ✗ {failure}")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    raise SystemExit(main())
