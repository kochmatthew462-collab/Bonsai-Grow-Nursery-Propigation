"""
The PRISMA 2020 flow diagram, drawn rather than reproduced.

## Why this is drawn from scratch

The PRISMA flow diagram is a published figure from the PRISMA 2020 statement and
its template files are the PRISMA group's work. Reproducing their artwork or
copying their template would be redistributing someone else's figure inside a
tool. What is *not* anyone's property is the reporting structure the statement
describes — identification, screening, eligibility, inclusion, and which counts
belong in which box — because that is the method, not its expression.

So this draws the diagram with matplotlib from your own counts, in the layout the
2020 statement describes, and cites the statement. The output is a 300-dpi PNG that
drops into the paper as an APA figure and into the deck as a slide.

## The version that matters

PRISMA 2020 changed the diagram in a way people still get wrong: it separates
records identified **from databases and registers** from those identified **by
other methods** — citation searching, hand searching, contact with authors — into
two parallel columns that converge at the included box. A 2009-style single-column
diagram submitted today is a reviewer comment. Both columns are drawn here, and the
second is omitted only when its counts are all zero, which is itself reportable.

## Arithmetic is checked, not assumed

`validate()` walks the same subtraction a reader will: records identified, minus
duplicates and other pre-screening removals, equals records screened; screened
minus excluded equals sought; and so on down. A diagram whose boxes do not
subtract is the single most common PRISMA error, it is caught instantly by anyone
who checks, and it invalidates the flow. The numbers are reported as they are and
the mismatch is stated — silently correcting them would hide the error rather than
fix it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")                                    # headless, before pyplot
import matplotlib.pyplot as plt                          # noqa: E402
from matplotlib.patches import FancyArrowPatch, Rectangle  # noqa: E402

CITATION = (
    "Page, M. J., McKenzie, J. E., Bossuyt, P. M., Boutron, I., Hoffmann, T. C., "
    "Mulrow, C. D., … Moher, D. (2021). The PRISMA 2020 statement: An updated "
    "guideline for reporting systematic reviews. BMJ, 372, n71. "
    "https://doi.org/10.1136/bmj.n71"
)

LICENSING_NOTE = (
    "Drawn from your counts in the layout the PRISMA 2020 statement describes, "
    "rather than reproduced from the PRISMA group's template files. The reporting "
    "structure is the method and is freely usable; the group's own artwork is "
    "theirs. Cite the statement wherever the diagram appears."
)

# Ink on paper, not a palette. A flow diagram is read, not compared, so colour
# carries no information here and adding it would only cost contrast in greyscale
# printing — the same reasoning that governs `figures.py`, arriving at the
# opposite answer because the job is different.
_EDGE = "#333333"
_FILL = "#ffffff"
_SHADE = "#f2f1ee"
_TEXT = "#111111"


@dataclass
class PrismaCounts:
    """Every box in the 2020 diagram.

    Field names follow the statement's own wording so a user filling this in from
    the checklist does not have to translate.
    """

    # Identification — databases and registers
    records_databases: int = 0
    records_registers: int = 0
    duplicates_removed: int = 0
    removed_ineligible_automation: int = 0
    removed_other_reasons: int = 0

    # Screening — the main column
    records_screened: int = 0
    records_excluded: int = 0
    reports_sought: int = 0
    reports_not_retrieved: int = 0
    reports_assessed: int = 0
    reports_excluded_reasons: dict[str, int] = field(default_factory=dict)

    # Identification — other methods
    records_websites: int = 0
    records_organisations: int = 0
    records_citation_searching: int = 0
    other_reports_sought: int = 0
    other_reports_not_retrieved: int = 0
    other_reports_assessed: int = 0
    other_reports_excluded_reasons: dict[str, int] = field(default_factory=dict)

    # Included
    studies_included: int = 0
    reports_of_included: int = 0

    # ------------------------------------------------------------- derivations

    def total_identified(self) -> int:
        return self.records_databases + self.records_registers

    def total_removed_before_screening(self) -> int:
        return (self.duplicates_removed + self.removed_ineligible_automation
                + self.removed_other_reasons)

    def total_other_identified(self) -> int:
        return (self.records_websites + self.records_organisations
                + self.records_citation_searching)

    def total_excluded_with_reasons(self) -> int:
        return sum(self.reports_excluded_reasons.values())

    def total_other_excluded_with_reasons(self) -> int:
        return sum(self.other_reports_excluded_reasons.values())

    def has_other_methods(self) -> bool:
        return bool(self.total_other_identified() or self.other_reports_assessed)


def validate(counts: PrismaCounts) -> list[dict[str, Any]]:
    """Walk the subtractions a reader will walk.

    Returns a problem list rather than raising: the diagram still draws, with the
    numbers exactly as entered, and the mismatches are reported next to it. A tool
    that adjusted the counts to make them add up would be fabricating a flow
    diagram, which is a research-integrity problem rather than a formatting one.
    """
    problems: list[dict[str, Any]] = []

    def expect(label: str, computed: int, entered: int, explanation: str) -> None:
        if computed != entered:
            problems.append({
                "check": label,
                "expected": computed,
                "entered": entered,
                "difference": entered - computed,
                "explanation": explanation,
            })

    expect(
        "Records screened",
        counts.total_identified() - counts.total_removed_before_screening(),
        counts.records_screened,
        "Records identified from databases and registers, minus everything "
        "removed before screening (duplicates, automation exclusions, other "
        "reasons), should equal the number screened.",
    )
    expect(
        "Reports sought for retrieval",
        counts.records_screened - counts.records_excluded,
        counts.reports_sought,
        "Records screened minus records excluded at title and abstract should "
        "equal the reports you went looking for.",
    )
    expect(
        "Reports assessed for eligibility",
        counts.reports_sought - counts.reports_not_retrieved,
        counts.reports_assessed,
        "Reports sought minus those you could not retrieve should equal the "
        "reports assessed at full text.",
    )

    if counts.reports_excluded_reasons:
        expect(
            "Studies included (main column)",
            counts.reports_assessed - counts.total_excluded_with_reasons(),
            counts.studies_included - (
                counts.other_reports_assessed
                - counts.total_other_excluded_with_reasons()
                if counts.has_other_methods() else 0),
            "Reports assessed at full text, minus the full-text exclusions with "
            "reasons, should equal the studies included from this column. PRISMA "
            "2020 requires a reason and a count for every full-text exclusion — "
            "an unexplained drop between these two boxes is the first thing a "
            "reviewer asks about.",
        )

    if counts.has_other_methods():
        expect(
            "Other-method reports assessed",
            counts.other_reports_sought - counts.other_reports_not_retrieved,
            counts.other_reports_assessed,
            "Same subtraction, for the citation-searching column.",
        )

    if counts.reports_assessed and not counts.reports_excluded_reasons:
        problems.append({
            "check": "Full-text exclusion reasons",
            "expected": "at least one reason with a count",
            "entered": "none",
            "difference": 0,
            "explanation": (
                "PRISMA 2020 requires the reasons for full-text exclusions to be "
                "reported with their counts. A diagram that shows reports "
                "assessed and studies included with nothing between them cannot "
                "be appraised."
            ),
        })

    if counts.studies_included and counts.reports_of_included < counts.studies_included:
        problems.append({
            "check": "Reports of included studies",
            "expected": f"at least {counts.studies_included}",
            "entered": counts.reports_of_included,
            "difference": counts.reports_of_included - counts.studies_included,
            "explanation": (
                "One study can be reported in several papers, so reports of "
                "included studies is normally equal to or greater than the number "
                "of studies. Fewer reports than studies means the two boxes have "
                "been swapped, which is a common slip."
            ),
        })

    return problems


# ------------------------------------------------------------------- drawing


import textwrap


def _wrap(text: str, box_width: float, figure_width: float,
          size: float) -> str:
    """Hard-wrap each line to what actually fits inside the box.

    matplotlib's `wrap=True` measures against the axes rather than the patch, so
    it lets text run out of a box and off the figure — which is exactly what the
    first version of this diagram did to "Removed by automation tools (n = 18)".
    Wrapping by character count against the box's own width in inches is crude but
    it is measured against the right thing.
    """
    inches = box_width * figure_width
    # ~1.9 characters per point of font size per inch for this font at these sizes.
    columns = max(12, int(inches * 96 / (size * 0.62)))
    out: list[str] = []
    for line in text.split("\n"):
        out.extend(textwrap.wrap(line, columns) or [""])
    return "\n".join(out)


def _box(ax, x: float, y: float, width: float, height: float, text: str, *,
         shaded: bool = False, size: float = 7.4,
         figure_width: float = 8.0) -> None:
    ax.add_patch(Rectangle(
        (x, y), width, height,
        facecolor=_SHADE if shaded else _FILL,
        edgecolor=_EDGE, linewidth=0.9, zorder=2))
    ax.text(x + width / 2, y + height / 2,
            _wrap(text, width, figure_width, size),
            ha="center", va="center", fontsize=size, color=_TEXT,
            zorder=3, linespacing=1.3)


def _arrow(ax, start: tuple[float, float], end: tuple[float, float]) -> None:
    ax.add_patch(FancyArrowPatch(
        start, end, arrowstyle="-|>", mutation_scale=9,
        linewidth=0.9, color=_EDGE, shrinkA=0, shrinkB=0, zorder=1))


def _stage_label(ax, top: float, bottom: float, text: str) -> None:
    """The rotated stage banner down the left edge, spanning its actual rows."""
    height = top - bottom
    ax.add_patch(Rectangle((0.005, bottom), 0.045, height, facecolor=_SHADE,
                           edgecolor=_EDGE, linewidth=0.9, zorder=2))
    ax.text(0.0275, bottom + height / 2, text, ha="center", va="center",
            fontsize=7.6, color=_TEXT, rotation=90, zorder=3)


def _exclusion_text(header: str, reasons: dict[str, int]) -> str:
    if not reasons:
        return f"{header}:\nnone recorded"
    lines = [f"{reason} (n = {number:,})"
             for reason, number in list(reasons.items())[:6]]
    if len(reasons) > 6:
        lines.append(f"and {len(reasons) - 6} further reasons")
    return f"{header}:\n" + "\n".join(lines)


def render(counts: PrismaCounts, path: Path, *,
           title: str = "", dpi: int = 300) -> Path:
    """Draw the diagram to a PNG and return the path.

    Geometry is computed per layout rather than shared, because the one-column and
    two-column diagrams are different figures: reusing one row table for both left
    a third of the single-column version empty, which read as a missing stage.
    """
    other = counts.has_other_methods()
    figure_width, figure_height = (13.0, 6.0) if other else (9.0, 7.0)
    figure, ax = plt.subplots(figsize=(figure_width, figure_height))
    ax.set_xlim(0, 1)
    ax.axis("off")

    box_h = 0.115
    gap = 0.055

    if other:
        main_x, main_w = 0.075, 0.30
        main_ex_x, main_ex_w = 0.395, 0.17
        side_x, side_w = 0.605, 0.24
        side_ex_x, side_ex_w = 0.865, 0.13
    else:
        main_x, main_w = 0.085, 0.44
        main_ex_x, main_ex_w = 0.565, 0.42
        side_x = side_w = side_ex_x = side_ex_w = 0.0

    # Four stacked rows in the main flow, then the included box beneath. The top
    # edge is placed so the first row's box fits inside the axes — at 0.90 the box
    # ran to 1.015 and was clipped by the frame.
    top = 0.98 - box_h
    rows = [top - index * (box_h + gap) for index in range(4)]
    included_y = rows[3] - box_h - gap - 0.03

    # The y limits follow the content rather than spanning 0-1. Leaving them at
    # 0-1 left a third of the canvas empty below the included box, which reads as
    # a missing stage rather than as whitespace.
    ax.set_ylim(included_y - 0.04, 1.0)

    def centre(y: float) -> float:
        return y + box_h / 2

    # ---- stage banners, spanning exactly the rows they cover
    _stage_label(ax, rows[0] + box_h, rows[1] + box_h + 0.015, "Identification")
    _stage_label(ax, rows[1] + box_h, rows[3] - 0.015, "Screening")
    _stage_label(ax, included_y + box_h + 0.02, included_y - 0.005, "Included")

    # ---- identification
    _box(ax, main_x, rows[0], main_w, box_h,
         f"Records identified from:\n"
         f"Databases (n = {counts.records_databases:,})\n"
         f"Registers (n = {counts.records_registers:,})",
         figure_width=figure_width)

    removed_lines = [f"Duplicates removed (n = {counts.duplicates_removed:,})"]
    if counts.removed_ineligible_automation:
        removed_lines.append(
            f"Removed by automation (n = {counts.removed_ineligible_automation:,})")
    if counts.removed_other_reasons:
        removed_lines.append(
            f"Removed, other reasons (n = {counts.removed_other_reasons:,})")
    _box(ax, main_ex_x, rows[0], main_ex_w, box_h,
         "Records removed before screening:\n" + "\n".join(removed_lines),
         size=6.8, figure_width=figure_width)
    _arrow(ax, (main_x + main_w, centre(rows[0])), (main_ex_x, centre(rows[0])))

    # ---- screening column
    _box(ax, main_x, rows[1], main_w, box_h,
         f"Records screened\n(n = {counts.records_screened:,})",
         figure_width=figure_width)
    _arrow(ax, (main_x + main_w / 2, rows[0]), (main_x + main_w / 2, rows[1] + box_h))
    _box(ax, main_ex_x, rows[1], main_ex_w, box_h,
         f"Records excluded\n(n = {counts.records_excluded:,})",
         figure_width=figure_width)
    _arrow(ax, (main_x + main_w, centre(rows[1])), (main_ex_x, centre(rows[1])))

    _box(ax, main_x, rows[2], main_w, box_h,
         f"Reports sought for retrieval\n(n = {counts.reports_sought:,})",
         figure_width=figure_width)
    _arrow(ax, (main_x + main_w / 2, rows[1]), (main_x + main_w / 2, rows[2] + box_h))
    _box(ax, main_ex_x, rows[2], main_ex_w, box_h,
         f"Reports not retrieved\n(n = {counts.reports_not_retrieved:,})",
         figure_width=figure_width)
    _arrow(ax, (main_x + main_w, centre(rows[2])), (main_ex_x, centre(rows[2])))

    _box(ax, main_x, rows[3], main_w, box_h,
         f"Reports assessed for eligibility\n(n = {counts.reports_assessed:,})",
         figure_width=figure_width)
    _arrow(ax, (main_x + main_w / 2, rows[2]), (main_x + main_w / 2, rows[3] + box_h))
    _box(ax, main_ex_x, rows[3] - 0.03, main_ex_w, box_h + 0.06,
         _exclusion_text("Reports excluded", counts.reports_excluded_reasons),
         size=6.8, figure_width=figure_width)
    _arrow(ax, (main_x + main_w, centre(rows[3])), (main_ex_x, centre(rows[3])))

    # ---- other-methods column
    if other:
        other_lines = ["Records identified from:"]
        if counts.records_websites:
            other_lines.append(f"Websites (n = {counts.records_websites:,})")
        if counts.records_organisations:
            other_lines.append(
                f"Organisations (n = {counts.records_organisations:,})")
        if counts.records_citation_searching:
            other_lines.append(
                f"Citation searching (n = {counts.records_citation_searching:,})")
        _box(ax, side_x, rows[0], side_w, box_h, "\n".join(other_lines),
             size=6.8, figure_width=figure_width)

        _box(ax, side_x, rows[2], side_w, box_h,
             f"Reports sought for retrieval\n"
             f"(n = {counts.other_reports_sought:,})",
             size=7.0, figure_width=figure_width)
        _arrow(ax, (side_x + side_w / 2, rows[0]),
               (side_x + side_w / 2, rows[2] + box_h))
        _box(ax, side_ex_x, rows[2], side_ex_w, box_h,
             f"Not retrieved\n(n = {counts.other_reports_not_retrieved:,})",
             size=6.8, figure_width=figure_width)
        _arrow(ax, (side_x + side_w, centre(rows[2])), (side_ex_x, centre(rows[2])))

        _box(ax, side_x, rows[3], side_w, box_h,
             f"Reports assessed for eligibility\n"
             f"(n = {counts.other_reports_assessed:,})",
             size=7.0, figure_width=figure_width)
        _arrow(ax, (side_x + side_w / 2, rows[2]),
               (side_x + side_w / 2, rows[3] + box_h))
        _box(ax, side_ex_x, rows[3] - 0.03, side_ex_w, box_h + 0.06,
             _exclusion_text("Excluded", counts.other_reports_excluded_reasons),
             size=6.6, figure_width=figure_width)
        _arrow(ax, (side_x + side_w, centre(rows[3])), (side_ex_x, centre(rows[3])))

    # ---- included
    included_x = main_x
    included_w = (side_x + side_w - main_x) if other else main_w
    _box(ax, included_x, included_y, included_w, box_h,
         f"Studies included in review (n = {counts.studies_included:,})\n"
         f"Reports of included studies (n = {counts.reports_of_included:,})",
         figure_width=figure_width)
    _arrow(ax, (main_x + main_w / 2, rows[3]),
           (main_x + main_w / 2, included_y + box_h))
    if other:
        _arrow(ax, (side_x + side_w / 2, rows[3]),
               (side_x + side_w / 2, included_y + box_h))

    if title:
        ax.set_title(title, fontsize=10, color=_TEXT, pad=6)

    figure.tight_layout(pad=0.3)
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(str(path), dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(figure)
    return path


# --------------------------------------------------------------- project bridge


def from_project(project, extra: dict[str, Any] | None = None) -> PrismaCounts:
    """Pre-fill the counts the tool can observe, leaving the rest to the user.

    Records identified, duplicates removed and records screened are facts about
    what the tool did, so they are filled from the project. Everything downstream —
    what was sought, what could not be retrieved, why each full text was excluded —
    happened outside the tool and is the user's to supply. Guessing them would
    fabricate the parts of a flow diagram that matter most.
    """
    # Derived from the project directly rather than through
    # `dedupe.prisma_counts`, whose five-integer signature answers a different
    # question (it summarises a completed screening pass; this needs the live
    # state of a project that may be half-screened).
    works = list(getattr(project, "works", None) or [])
    searches = list(getattr(project, "searches", None) or [])

    retrieved = 0
    for search in searches:
        try:
            retrieved += int(search.get("returned", 0) or 0)
        except (AttributeError, TypeError, ValueError):
            continue
    retrieved = retrieved or len(works)

    after_dedupe = len(works)
    screened_out = sum(1 for w in works if getattr(w, "included", None) is False)
    included_now = [w for w in works
                    if getattr(w, "included", None) is not False
                    and not getattr(w, "retracted", False)]

    cited = getattr(project, "cited_works", None)
    if callable(cited):
        try:
            included_now = list(cited()) or included_now
        except Exception:
            pass

    counts = PrismaCounts()
    counts.records_databases = retrieved
    counts.duplicates_removed = max(0, retrieved - after_dedupe)
    counts.records_screened = after_dedupe
    counts.records_excluded = screened_out
    counts.reports_sought = max(0, after_dedupe - screened_out)
    counts.reports_assessed = counts.reports_sought
    counts.studies_included = len(included_now)
    counts.reports_of_included = len(included_now)

    for key, value in (extra or {}).items():
        if not hasattr(counts, key):
            continue
        current = getattr(counts, key)
        if isinstance(current, dict):
            setattr(counts, key, {str(k): int(v) for k, v in (value or {}).items()})
        else:
            try:
                setattr(counts, key, int(value))
            except (TypeError, ValueError):
                continue
    return counts


def apa_figure_note(counts: PrismaCounts) -> str:
    """The structured note that goes beneath the figure in an APA paper."""
    parts = [
        f"From {counts.total_identified():,} records identified through database "
        f"and register searching",
    ]
    if counts.has_other_methods():
        parts.append(f" and {counts.total_other_identified():,} identified through "
                     f"other methods")
    parts.append(
        f", {counts.studies_included:,} studies met the inclusion criteria. "
        f"Diagram drawn following the reporting structure of the PRISMA 2020 "
        f"statement."
    )
    return "".join(parts)


def payload(counts: PrismaCounts) -> dict[str, Any]:
    """Counts, derived totals and validation, as JSON for the UI."""
    return {
        "counts": {
            key: getattr(counts, key)
            for key in counts.__dataclass_fields__
        },
        "derived": {
            "total_identified": counts.total_identified(),
            "total_removed_before_screening":
                counts.total_removed_before_screening(),
            "total_other_identified": counts.total_other_identified(),
            "total_excluded_with_reasons": counts.total_excluded_with_reasons(),
            "has_other_methods": counts.has_other_methods(),
        },
        "problems": validate(counts),
        "citation": CITATION,
        "licensing": LICENSING_NOTE,
        "figure_note": apa_figure_note(counts),
    }
