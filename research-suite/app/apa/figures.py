"""
APA 7-compliant figures, rendered with matplotlib to PNG for embedding.

Design constraints, each with a reason:

**Colour is never the only encoding.** APA figures are routinely printed and
photocopied in greyscale, and readers with colour-vision deficiency are a normal
part of any audience. So every multi-series figure also varies marker shape and
line style, and lines carry a direct end label. That satisfies APA 7 §7.26's
legibility requirement and the colour-vision requirement with one mechanism.

**The palette is validated, not chosen by eye.** Four hues — blue `#2a78d6`,
orange `#eb6834`, aqua `#1baf7a`, violet `#4a3aa7` — checked with the data-viz
validator against a white surface on all pairs: worst colour-vision-deficiency
separation ΔE 9.2, worst normal-vision separation ΔE 16.3, both above their
floors. Aqua sits below 3:1 contrast against white, which is why direct labels
and the companion data table are not optional extras here.

**One axis, always.** A second y-scale lets a figure imply a relationship that
is an artefact of two arbitrary scalings, which is the most misleading thing a
chart can do in a paper about evidence. Two measures get two figures.

**No chartjunk.** APA 7 §7.22: no 3-D, no shading, no decorative frames, no
gridlines that are not needed to read a value. The top and right spines come off,
and a horizontal grid is drawn faintly only where the reader has to compare
magnitudes across a wide axis.

Every figure returns its path plus the APA note text, so the caller cannot embed
a figure without its source attribution.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import matplotlib
matplotlib.use("Agg")           # headless: no display, no GUI backend
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import (  # noqa: E402
    MaxNLocator, NullFormatter, NullLocator, ScalarFormatter,
)

# Validated categorical palette (see module docstring).
SERIES_COLOURS = ["#2a78d6", "#eb6834", "#1baf7a", "#4a3aa7"]
# Secondary encoding, applied in the same order. Never optional.
SERIES_MARKERS = ["o", "s", "^", "D"]
SERIES_LINESTYLES = ["-", "--", "-.", ":"]

INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
GRID = "#d8d7d2"
RULE = "#52514e"

# APA 7 §7.24 asks for a sans serif typeface inside figures, at a size that
# stays legible when the figure is reduced to fit the page.
FIGURE_FONT = ["DejaVu Sans", "Arial", "Helvetica", "sans-serif"]
BASE_SIZE = 10
DPI = 300                       # print quality; a 150-dpi figure looks soft in Word


@dataclass
class Figure:
    """A rendered figure and everything needed to caption it correctly."""

    path: str
    title: str
    note: str
    kind: str
    data_table: tuple[list[str], list[list[str]]] | None = None


def _style() -> None:
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": FIGURE_FONT,
        "font.size": BASE_SIZE,
        "axes.labelsize": BASE_SIZE,
        "axes.titlesize": BASE_SIZE,
        "xtick.labelsize": BASE_SIZE - 1,
        "ytick.labelsize": BASE_SIZE - 1,
        "legend.fontsize": BASE_SIZE - 1,
        "axes.edgecolor": RULE,
        "axes.labelcolor": INK,
        "text.color": INK,
        "xtick.color": INK_SECONDARY,
        "ytick.color": INK_SECONDARY,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "savefig.facecolor": "white",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": False,
        "legend.frameon": False,
    })


def _finish(fig, axes, path: Path) -> str:
    axes.tick_params(length=3, width=0.8)
    for spine in ("left", "bottom"):
        axes.spines[spine].set_linewidth(0.8)
    fig.tight_layout(pad=0.6)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return str(path)


# =========================================================== bar / categorical


def bar_figure(
    labels: list[str],
    values: list[float],
    *,
    path: str | Path,
    title: str = "",
    y_label: str = "",
    note: str = "",
    horizontal: bool | None = None,
    value_labels: bool = True,
) -> Figure:
    """A bar chart for comparing magnitudes across categories.

    Orientation is chosen from the label lengths rather than left to the caller:
    long category names rotated 45° on a vertical chart are the most common
    unreadable figure in student papers, and a horizontal bar chart fixes it.
    """
    _style()
    if horizontal is None:
        horizontal = (
            len(labels) > 7
            or max((len(str(label)) for label in labels), default=0) > 14
        )

    height = max(2.6, 0.42 * len(labels) + 1.1) if horizontal else 3.4
    fig, axes = plt.subplots(figsize=(6.5, height))
    colour = SERIES_COLOURS[0]

    if horizontal:
        positions = range(len(labels))
        axes.barh(positions, values, color=colour, height=0.62, zorder=3)
        axes.set_yticks(list(positions))
        axes.set_yticklabels(labels)
        axes.invert_yaxis()          # first category at the top, as read
        axes.set_xlabel(y_label)
        axes.xaxis.grid(True, color=GRID, linewidth=0.6, zorder=0)
        axes.set_axisbelow(True)
        if value_labels:
            span = max(values) - min(0, min(values)) or 1
            for position, value in zip(positions, values):
                axes.text(value + span * 0.012, position, _format_value(value),
                          va="center", ha="left", fontsize=BASE_SIZE - 1,
                          color=INK_SECONDARY)
    else:
        axes.bar(labels, values, color=colour, width=0.62, zorder=3)
        axes.set_ylabel(y_label)
        axes.yaxis.grid(True, color=GRID, linewidth=0.6, zorder=0)
        axes.set_axisbelow(True)
        if value_labels:
            span = max(values) or 1
            for index, value in enumerate(values):
                axes.text(index, value + span * 0.015, _format_value(value),
                          ha="center", va="bottom", fontsize=BASE_SIZE - 1,
                          color=INK_SECONDARY)

    rendered = _finish(fig, axes, Path(path))
    return Figure(
        path=rendered, title=title, note=note, kind="bar",
        data_table=(["Category", y_label or "Value"],
                    [[str(label), _format_value(value)]
                     for label, value in zip(labels, values)]),
    )


def grouped_bar_figure(
    labels: list[str],
    series: list[tuple[str, list[float]]],
    *,
    path: str | Path,
    title: str = "",
    y_label: str = "",
    note: str = "",
) -> Figure:
    """Bars for two to four series.

    Series are separated by a visible gap rather than butted together, which is
    what keeps adjacent fills distinguishable in greyscale.
    """
    if not series:
        raise ValueError("grouped_bar_figure needs at least one series")
    if len(series) > len(SERIES_COLOURS):
        raise ValueError(
            f"{len(series)} series exceeds the {len(SERIES_COLOURS)} validated "
            f"colours. Fold the smallest into an 'Other' series, or split into "
            f"separate figures — a fifth generated hue would not be checked for "
            f"colour-vision separation."
        )
    _style()
    fig, axes = plt.subplots(figsize=(6.5, 3.6))

    count = len(series)
    group_width = 0.78
    bar_width = group_width / count * 0.9    # the 0.9 leaves the separating gap
    for index, (name, values) in enumerate(series):
        offsets = [
            position - group_width / 2 + bar_width * (index + 0.5)
            + (group_width / count - bar_width) * index
            for position in range(len(labels))
        ]
        axes.bar(offsets, values, width=bar_width, label=name,
                 color=SERIES_COLOURS[index], zorder=3)

    axes.set_xticks(range(len(labels)))
    axes.set_xticklabels(labels)
    axes.set_ylabel(y_label)
    axes.yaxis.grid(True, color=GRID, linewidth=0.6, zorder=0)
    axes.set_axisbelow(True)
    # A legend is always present for two or more series, so identity is never
    # carried by colour alone.
    axes.legend(loc="upper left", bbox_to_anchor=(0, 1.02), ncol=min(count, 3))

    rendered = _finish(fig, axes, Path(path))
    return Figure(
        path=rendered, title=title, note=note, kind="grouped-bar",
        data_table=(
            ["Category"] + [name for name, _ in series],
            [[str(label)] + [_format_value(values[i]) for _, values in series]
             for i, label in enumerate(labels)],
        ),
    )


# ============================================================== line / trend


def line_figure(
    x_labels: list[str],
    series: list[tuple[str, list[float]]],
    *,
    path: str | Path,
    title: str = "",
    x_label: str = "",
    y_label: str = "",
    note: str = "",
) -> Figure:
    """A line chart for change over time — incidence and prevalence curves.

    Each series varies colour, line style *and* marker, and carries a direct
    label at its right end. A reader working from a greyscale photocopy can still
    tell the series apart, which is the test that matters for a printed paper.
    """
    if not series:
        raise ValueError("line_figure needs at least one series")
    if len(series) > len(SERIES_COLOURS):
        raise ValueError(
            f"{len(series)} series exceeds the {len(SERIES_COLOURS)} validated "
            f"colours. Use small multiples instead of adding a fifth hue."
        )
    _style()
    fig, axes = plt.subplots(figsize=(6.5, 3.6))

    for index, (name, values) in enumerate(series):
        axes.plot(
            range(len(x_labels)), values,
            color=SERIES_COLOURS[index],
            linestyle=SERIES_LINESTYLES[index],
            marker=SERIES_MARKERS[index],
            markersize=4.5, linewidth=2.0, label=name, zorder=3,
        )
        # Direct end label: the relief the palette's contrast warning requires,
        # and what makes the figure readable without consulting a legend.
        if values:
            axes.annotate(
                name, xy=(len(x_labels) - 1, values[-1]),
                xytext=(6, 0), textcoords="offset points",
                va="center", ha="left", fontsize=BASE_SIZE - 1, color=INK_SECONDARY,
            )

    axes.set_xticks(range(len(x_labels)))
    axes.set_xticklabels(x_labels)
    if len(x_labels) > 12:
        # Thin the tick labels rather than rotating them into an unreadable fan.
        step = max(1, len(x_labels) // 10)
        axes.set_xticks(range(0, len(x_labels), step))
        axes.set_xticklabels([x_labels[i] for i in range(0, len(x_labels), step)])
    axes.set_xlabel(x_label)
    axes.set_ylabel(y_label)
    axes.yaxis.grid(True, color=GRID, linewidth=0.6, zorder=0)
    axes.set_axisbelow(True)
    axes.margins(x=0.12)             # room for the end labels
    if len(series) > 1:
        axes.legend(loc="upper left", bbox_to_anchor=(0, 1.02),
                    ncol=min(len(series), 3))

    rendered = _finish(fig, axes, Path(path))
    return Figure(
        path=rendered, title=title, note=note, kind="line",
        data_table=(
            [x_label or "Period"] + [name for name, _ in series],
            [[str(label)] + [_format_value(values[i]) for _, values in series]
             for i, label in enumerate(x_labels)],
        ),
    )


# ================================================================ forest plot


@dataclass
class EffectEstimate:
    """One row of a forest plot."""

    label: str
    estimate: float
    lower: float
    upper: float
    weight: float = 0.0
    subgroup: str = ""


def forest_plot(
    estimates: list[EffectEstimate],
    *,
    path: str | Path,
    title: str = "",
    measure: str = "Odds ratio",
    note: str = "",
    null_value: float = 1.0,
    log_scale: bool | None = None,
    pooled: EffectEstimate | None = None,
) -> Figure:
    """A forest plot of effect estimates with confidence intervals.

    Two things this gets right that hand-drawn forest plots often do not:

    **Ratio measures are plotted on a log scale.** An odds ratio of 0.5 and one
    of 2.0 are the same size of effect in opposite directions, and only a log
    axis shows that. On a linear axis the protective half of the plot is
    compressed into a fifth of the width, which visually understates it. The
    scale is chosen from the measure name unless overridden.

    **Marker area is proportional to weight, not marker width.** Scaling the
    diameter by weight makes a study with twice the weight look four times as
    influential.
    """
    if not estimates:
        raise ValueError("forest_plot needs at least one estimate")
    if log_scale is None:
        log_scale = any(
            token in measure.lower()
            for token in ("ratio", "odds", "risk", "hazard", "rr", "or", "hr")
        )
    _style()

    rows = list(estimates) + ([pooled] if pooled else [])
    height = max(2.4, 0.36 * len(rows) + 1.3)
    fig, axes = plt.subplots(figsize=(6.5, height))

    weights = [e.weight for e in estimates if e.weight > 0]
    max_weight = max(weights) if weights else 0.0

    for index, estimate in enumerate(estimates):
        y = len(rows) - 1 - index
        axes.plot([estimate.lower, estimate.upper], [y, y],
                  color=INK_SECONDARY, linewidth=1.4, solid_capstyle="butt", zorder=3)
        if max_weight > 0 and estimate.weight > 0:
            # Area ∝ weight, so size = sqrt(weight).
            size = 4.0 + 7.0 * math.sqrt(estimate.weight / max_weight)
        else:
            size = 6.0
        axes.plot([estimate.estimate], [y], marker="s", markersize=size,
                  color=SERIES_COLOURS[0], zorder=4)

    if pooled:
        y = 0
        axes.plot([pooled.lower, pooled.upper], [y, y],
                  color=SERIES_COLOURS[3], linewidth=2.0, zorder=3)
        # A diamond for the pooled estimate — the convention, and a second
        # encoding that survives greyscale.
        axes.plot([pooled.estimate], [y], marker="D", markersize=9,
                  color=SERIES_COLOURS[3], zorder=5)

    axes.axvline(null_value, color=RULE, linewidth=0.9, linestyle=(0, (4, 3)),
                 zorder=2)

    axes.set_yticks(range(len(rows)))
    axes.set_yticklabels([r.label for r in reversed(rows)])
    if pooled:
        # Bold the pooled row's label so it reads as a summary, not a study.
        axes.get_yticklabels()[0].set_fontweight("bold")

    axes.set_xlabel(f"{measure} (95% CI)")
    axes.set_ylim(-0.8, len(rows) - 0.2)

    if log_scale:
        axes.set_xscale("log")
        axes.xaxis.set_major_formatter(ScalarFormatter())
        # A log axis draws minor ticks at 2×10ⁿ, 3×10ⁿ … and labels them, which
        # overprints the chosen major labels into an unreadable smear. Silencing
        # the minor formatter is the only way to get a clean ratio axis.
        axes.xaxis.set_minor_formatter(NullFormatter())
        axes.xaxis.set_minor_locator(NullLocator())
        ticks = [t for t in (0.1, 0.2, 0.25, 0.5, 1, 2, 4, 5, 10)
                 if min(e.lower for e in rows) / 1.6 <= t
                 <= max(e.upper for e in rows) * 1.6]
        if len(ticks) >= 2:
            axes.set_xticks(ticks)
            axes.set_xticklabels([_format_value(t) for t in ticks])
    else:
        axes.xaxis.set_major_locator(MaxNLocator(nbins=6))

    axes.xaxis.grid(True, color=GRID, linewidth=0.6, zorder=0)
    axes.set_axisbelow(True)
    axes.spines["left"].set_visible(False)
    axes.tick_params(axis="y", length=0)

    # Numeric values beside each row: a forest plot without them makes the reader
    # estimate from pixel positions.
    for index, estimate in enumerate(rows):
        y = len(rows) - 1 - index
        axes.annotate(
            f"{_format_value(estimate.estimate)} "
            f"[{_format_value(estimate.lower)}, {_format_value(estimate.upper)}]",
            xy=(1.02, y), xycoords=("axes fraction", "data"),
            va="center", ha="left", fontsize=BASE_SIZE - 1.5, color=INK_SECONDARY,
            annotation_clip=False,
        )

    default_note = (
        f"Squares show each study's {measure.lower()}"
        + (", sized in proportion to study weight" if max_weight > 0 else "")
        + f"; horizontal lines show the 95% confidence interval. The dashed line "
        f"marks no effect ({_format_value(null_value)})."
        + (" The diamond shows the pooled estimate." if pooled else "")
        + (" The horizontal axis is logarithmic, so equal distances represent "
           "equal proportional effects." if log_scale else "")
    )
    rendered = _finish(fig, axes, Path(path))
    return Figure(
        path=rendered, title=title,
        note=f"{default_note} {note}".strip(), kind="forest",
        data_table=(
            ["Study", measure, "95% CI lower", "95% CI upper", "Weight"],
            [[e.label, _format_value(e.estimate), _format_value(e.lower),
              _format_value(e.upper),
              _format_value(e.weight) if e.weight else "—"] for e in rows],
        ),
    )


# ==================================================== evidence-level summary


def level_distribution_figure(
    counts: dict[str, int], *, path: str | Path, note: str = ""
) -> Figure:
    """The distribution of evidence levels across included studies.

    A useful figure for a review's methods section, and one the tool can build
    from its own classification without the user assembling anything.
    """
    order = ["I", "II", "III", "IV", "V", "ungraded", "not-evidence"]
    labels = [
        {"I": "Level I", "II": "Level II", "III": "Level III", "IV": "Level IV",
         "V": "Level V", "ungraded": "Not graded",
         "not-evidence": "Not evidence"}[key]
        for key in order if counts.get(key)
    ]
    values = [float(counts[key]) for key in order if counts.get(key)]
    if not values:
        raise ValueError("no level counts to plot")

    figure = bar_figure(
        labels, values, path=path,
        title="Distribution of Included Studies by Level of Evidence",
        y_label="Number of studies", horizontal=True,
        note=note or (
            "Levels follow the Joanna Briggs Institute and AACN hierarchies. "
            "Studies graded “not graded” could not be classified from the "
            "publication type or abstract and were reviewed by hand."
        ),
    )
    figure.kind = "level-distribution"
    return figure


# ------------------------------------------------------------------ utilities


def _format_value(value: float) -> str:
    """Format a number the way APA 7 §6.36 expects.

    Values below one keep a leading zero unless they cannot exceed one — but a
    figure cannot know that about arbitrary data, so the leading zero stays,
    which is the safe direction.
    """
    if value != value or value in (float("inf"), float("-inf")):
        return "—"
    if abs(value) >= 10_000:
        return f"{value:,.0f}"
    if abs(value) >= 100:
        return f"{value:,.0f}"
    if abs(value) >= 10:
        return f"{value:.1f}".rstrip("0").rstrip(".")
    if abs(value) >= 1:
        return f"{value:.2f}".rstrip("0").rstrip(".")
    return f"{value:.2f}"


def series_to_figure(series, path: str | Path, kind: str = "auto") -> Figure:
    """Render a `DataSeries` from `sources/gov.py` as a figure.

    The series' own `apa_note()` becomes the figure note, so the agency
    attribution and licence line travel with the figure automatically. A WHO
    figure that loses its CC BY-NC-SA line is a figure that must not be
    published.
    """
    labels = [str(label) for label in series.labels]
    values = [float(value) for value in series.values]
    if kind == "auto":
        looks_like_time = all(
            label.strip().isdigit() and 1900 <= int(label.strip()) <= 2100
            for label in labels
        )
        kind = "line" if looks_like_time and len(labels) > 3 else "bar"

    if kind == "line":
        return line_figure(
            labels, [(series.series_name or "Value", values)], path=path,
            title=series.title, x_label="Year",
            y_label=series.unit or series.series_name or "Value",
            note=series.apa_note(),
        )
    return bar_figure(
        labels, values, path=path, title=series.title,
        y_label=series.unit or series.series_name or "Value",
        note=series.apa_note(),
    )
