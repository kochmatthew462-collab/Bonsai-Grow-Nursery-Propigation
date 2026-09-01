"""
Statistical narrative translation: SPSS and R output into APA 7 results prose.

Paste the output table, get the sentence. The value is not in saving typing — it
is that APA's statistical style has a dozen rules that are individually trivial
and collectively impossible to get right by hand at 2 a.m., and every one of them
is the sort of thing a marker circles.

## The rules this enforces (APA 7, chapter 6)

| Rule | Section | What goes wrong without it |
|---|---|---|
| Statistical symbols are **italicised**: *M*, *SD*, *t*, *F*, *p*, *r*, *d*, *n* | §6.44 | Roman symbols throughout, marked down every time |
| **Greek letters are not italicised**: α, β, χ², η² | §6.44 | Over-italicising after learning the first rule |
| **No leading zero** where the value cannot exceed 1: *p*, *r*, β, partial η² | §6.36 | `p = 0.03` instead of `p = .03` |
| **Leading zero kept** where it can: *M*, *SD*, *t*, *F*, *d*, CI bounds | §6.36 | `M = .45` when the mean really can exceed 1 |
| *p* reported to **two or three decimals**, and as `p < .001` below that | §6.36 | `p = .000`, which is false — it is small, not zero |
| Degrees of freedom in **parentheses**, italic statistic | §6.44 | `t 34 = 2.11` |
| **Exact *p*** rather than a threshold, unless below .001 | §6.36 | `p < .05`, which discards information |
| Confidence intervals as **[lower, upper]** with no repeated units | §6.42 | Ad-hoc bracket styles |
| Numbers **1–9 spelled out** in prose, 10+ as numerals, except with units | §6.32 | Inconsistent within a sentence |

`p = .000` deserves its own note. SPSS prints it because it rounds, and it is the
single most common statistical-reporting error in student work. A *p* value is
never zero; the correct report is `p < .001`, and this module converts it silently
and says it did.

## What it does not do

It does not compute anything and it does not interpret. It reads numbers you have
already produced and formats them. Two specific refusals:

* **It will not turn a non-significant result into a hedge.** `p = .08` renders as
  `p = .08` with the effect size beside it, not as "approached significance",
  which is a phrase that means nothing and is increasingly called out in review.
* **It will not infer a test you did not name.** If the parser cannot tell whether
  a table is a one-way or repeated-measures ANOVA, it says so rather than
  guessing, because those are reported differently and the difference is not
  cosmetic.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# Values that cannot exceed 1 in absolute terms, so APA drops the leading zero
# (§6.36). Correlations and proportions belong here; means and test statistics do
# not, and getting the set wrong is how `M = .45` reaches a marker.
_NO_LEADING_ZERO = {
    "p", "r", "rs", "rho", "tau", "beta", "β", "R2", "R²", "r2", "r²",
    "eta2", "η²", "partial_eta2", "ηp²", "omega2", "ω²", "alpha", "α",
    "phi", "φ", "cramers_v", "V", "ICC", "kappa", "κ", "AUC", "prop",
}

# Symbols italicised in APA. Greek letters are NOT (§6.44) — this is the rule
# people get backwards immediately after learning that symbols are italicised.
_ITALIC_SYMBOLS = {
    "M", "SD", "SE", "Mdn", "n", "N", "t", "F", "z", "U", "H", "W", "r", "R",
    "d", "g", "p", "df", "b", "B", "MSE", "IQR", "Q1", "Q3",
}
_NEVER_ITALIC = {"α", "β", "χ²", "η²", "ηp²", "ω²", "φ", "κ", "Δ", "ε", "λ"}


def fmt_number(value: float, *, decimals: int = 2,
               leading_zero: bool = True) -> str:
    """Format a number APA-style, dropping the leading zero where required."""
    text = f"{value:.{decimals}f}"
    if not leading_zero:
        if text.startswith("0."):
            text = text[1:]
        elif text.startswith("-0."):
            text = "-" + text[2:]
    return text


def fmt_p(value: float, *, decimals: int = 3) -> str:
    """Format a *p* value.

    Three rules in one place: no leading zero, `< .001` rather than a rounded
    zero, and `> .999` at the other end for the same reason.
    """
    if value < 0:
        return "p = [invalid, negative]"
    if value < 0.001:
        return "p < .001"
    if value > 0.999:
        return "p > .999"
    return "p = " + fmt_number(value, decimals=decimals, leading_zero=False)


def fmt_stat(symbol: str, value: float, *, decimals: int = 2) -> str:
    """One `symbol = value` pair, with the leading-zero rule applied."""
    leading = symbol not in _NO_LEADING_ZERO
    return f"{symbol} = {fmt_number(value, decimals=decimals, leading_zero=leading)}"


def fmt_ci(lower: float, upper: float, *, level: int = 95,
           decimals: int = 2, leading_zero: bool = True) -> str:
    """A confidence interval in APA's bracket form (§6.42)."""
    return (f"{level}% CI ["
            f"{fmt_number(lower, decimals=decimals, leading_zero=leading_zero)}, "
            f"{fmt_number(upper, decimals=decimals, leading_zero=leading_zero)}]")


def italic_runs(text: str) -> list[tuple[str, bool]]:
    """Split a rendered sentence into (text, italic) runs.

    Returned rather than applied so the Word writer can produce real italic runs
    instead of markdown asterisks — `apa/citations.py` uses the same shape, and it
    is the reason the exported statistics are correctly styled rather than
    correctly spelled.
    """
    runs: list[tuple[str, bool]] = []
    # A symbol is italicised only when it stands as a statistic: preceded by a
    # boundary and followed by an equals, a comparison, or an opening paren.
    pattern = re.compile(
        r"(?<![A-Za-z])(" + "|".join(sorted(
            (re.escape(s) for s in _ITALIC_SYMBOLS), key=len, reverse=True))
        + r")(?=\s*[=<>(]|\s*$)")
    position = 0
    for match in pattern.finditer(text):
        if match.start() > position:
            runs.append((text[position:match.start()], False))
        runs.append((match.group(1), True))
        position = match.end()
    if position < len(text):
        runs.append((text[position:], False))
    return [r for r in runs if r[0]]


# --------------------------------------------------------------------- parsing


@dataclass
class ParsedResult:
    """One statistical result, in a form the renderers can use."""

    kind: str = ""                       # t_test, anova, correlation, …
    label: str = ""
    values: dict[str, float] = field(default_factory=dict)
    groups: list[dict[str, Any]] = field(default_factory=list)
    note: str = ""
    confidence: str = "parsed"           # parsed | ambiguous
    raw: str = ""


_NUM = r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?"

# SPSS labels its significance column "Sig." and then adds a parenthetical —
# "Sig. (2-tailed)", "Asymp. Sig. (2-sided)". A lazy `[^\n]*?` after the label
# matches the 2 inside that parenthesis, which silently reports p = 2.00 and then
# renders as "p > .999". The parenthetical has to be consumed explicitly.
_SIG = rf"Sig\.?\s*(?:\([^)]*\))?\s*[=:]?\s*({_NUM})"
_ASYMP = rf"Asymp\.?\s*Sig\.?\s*(?:\([^)]*\))?\s*[=:]?\s*({_NUM})"


def _spss_row(blob: str, label: str) -> list[float]:
    """Numbers on an SPSS table row, found by its row label.

    SPSS output is column-oriented: the header names the columns once and every
    data row is bare numbers. Keyword matching cannot read that — there is no
    "F = " anywhere — so the row is located by its label and read positionally,
    which is how a human reads it too.
    """
    match = re.search(rf"^[^\S\n]*{re.escape(label)}[^\n]*$", blob,
                      re.IGNORECASE | re.MULTILINE)
    if not match:
        return []
    tail = match.group(0)[len(label):] if match.group(0).lower().startswith(
        label.lower()) else match.group(0)
    return [float(n) for n in re.findall(_NUM, tail)]


def _find(pattern: str, text: str, group: int = 1) -> float | None:
    match = re.search(pattern, text, re.IGNORECASE)
    if not match:
        return None
    try:
        return float(match.group(group))
    except (TypeError, ValueError):
        return None


def parse(text: str) -> list[ParsedResult]:
    """Read SPSS or R output and pull out what can be recognised.

    Deliberately conservative. Every recogniser requires a distinctive marker —
    an R `t.test` header, an SPSS `ANOVA` table label — rather than pattern-matching
    loose numbers, because a parser that guesses produces a results section that is
    confidently wrong, which is worse than one that produces nothing.
    """
    results: list[ParsedResult] = []
    blob = text or ""

    # ---- R: t.test()
    if re.search(r"\b(Welch|Two Sample|One Sample|Paired)\s+t-test\b", blob, re.I):
        t_value = _find(rf"\bt\s*=\s*({_NUM})", blob)
        df = _find(rf"\bdf\s*=\s*({_NUM})", blob)
        p_value = _find(rf"p-value\s*[<=]\s*({_NUM})", blob)
        ci = re.search(rf"({_NUM})\s+({_NUM})", blob[blob.lower().find(
            "confidence interval"):] if "confidence interval" in blob.lower() else "")
        paired = bool(re.search(r"\bPaired\b", blob, re.I))
        one_sample = bool(re.search(r"\bOne Sample\b", blob, re.I))
        values = {k: v for k, v in {
            "t": t_value, "df": df, "p": p_value,
            "ci_low": float(ci.group(1)) if ci else None,
            "ci_high": float(ci.group(2)) if ci else None,
        }.items() if v is not None}
        if "t" in values:
            results.append(ParsedResult(
                kind="t_test", raw=blob, values=values,
                label=("paired-samples" if paired
                       else "one-sample" if one_sample
                       else "independent-samples"),
                note=("R reports Welch's t by default, which does not assume "
                      "equal variances and usually has fractional degrees of "
                      "freedom. Report the df as given rather than rounding — a "
                      "fractional df is the evidence that Welch's was used."
                      if re.search(r"\bWelch\b", blob, re.I) else ""),
            ))

    # ---- R: cor.test()
    if re.search(r"correlation", blob, re.I) and re.search(
            r"\bcor\s*\n?\s*" + _NUM, blob, re.I | re.M):
        r_value = _find(rf"\bcor\s*\n\s*({_NUM})", blob) or _find(
            rf"\bcor\s*=\s*({_NUM})", blob)
        t_value = _find(rf"\bt\s*=\s*({_NUM})", blob)
        df = _find(rf"\bdf\s*=\s*({_NUM})", blob)
        p_value = _find(rf"p-value\s*[<=]\s*({_NUM})", blob)
        spearman = bool(re.search(r"Spearman", blob, re.I))
        if r_value is not None:
            results.append(ParsedResult(
                kind="correlation", raw=blob,
                label="Spearman" if spearman else "Pearson",
                values={k: v for k, v in {
                    "r": r_value, "t": t_value, "df": df, "p": p_value,
                }.items() if v is not None},
            ))

    # ---- SPSS: Independent Samples Test
    if re.search(r"Independent Samples Test", blob, re.I):
        t_value = _find(rf"\bt\b[^\n]*?({_NUM})", blob)
        df = _find(rf"\bdf\b[^\n]*?({_NUM})", blob)
        p_value = _find(_SIG, blob)
        levene = _find(rf"Levene[^\n]*?({_NUM})", blob)
        results.append(ParsedResult(
            kind="t_test", raw=blob, label="independent-samples",
            values={k: v for k, v in {
                "t": t_value, "df": df, "p": p_value, "levene_p": levene,
            }.items() if v is not None},
            note=("SPSS prints two rows: equal variances assumed and not "
                  "assumed. Read Levene's test first and report the row it "
                  "points to — reporting the wrong row is a substantive error, "
                  "not a formatting one."),
            confidence="ambiguous",
        ))

    # ---- SPSS / R: ANOVA
    if re.search(r"\bANOVA\b|\bAnalysis of Variance\b|\bDf\s+Sum Sq\b", blob, re.I):
        f_value = _find(rf"\bF\s*(?:value|-statistic)?\s*[=:]\s*({_NUM})", blob)
        df1 = _find(rf"\bdf1\s*[=:]\s*({_NUM})", blob)
        df2 = _find(rf"\bdf2\s*[=:]\s*({_NUM})", blob)

        # SPSS one-way ANOVA: "Between Groups" carries SS, df, MS, F and Sig. in
        # that column order, and "Within Groups" carries SS, df and MS.
        between = _spss_row(blob, "Between Groups")
        within = _spss_row(blob, "Within Groups")
        if len(between) >= 4:
            df1 = df1 if df1 is not None else between[1]
            f_value = f_value if f_value is not None else between[3]
        if len(within) >= 2 and df2 is None:
            df2 = within[1]
        p_value = (_find(_SIG, blob)
                   or _find(rf"Pr\(>F\)\s*[=:]?\s*({_NUM})", blob)
                   or _find(rf"\bp\s*[<=]\s*({_NUM})", blob))
        if p_value is None and len(between) >= 5:
            p_value = between[4]
        eta = _find(rf"(?:Partial\s+)?Eta\s*Squared\s*[=:]?\s*({_NUM})", blob)
        repeated = bool(re.search(r"repeated|within-subjects|Mauchly", blob, re.I))
        results.append(ParsedResult(
            kind="anova", raw=blob,
            label="repeated-measures" if repeated else "one-way",
            values={k: v for k, v in {
                "F": f_value, "df1": df1, "df2": df2, "p": p_value,
                "partial_eta2": eta,
            }.items() if v is not None},
            note=("Mauchly's test appears in this output, so sphericity was "
                  "assessed. If it was violated, report the corrected degrees of "
                  "freedom (Greenhouse-Geisser or Huynh-Feldt) and say which "
                  "correction you used."
                  if re.search(r"Mauchly", blob, re.I) else ""),
            confidence="ambiguous" if (df1 is None or df2 is None) else "parsed",
        ))

    # ---- Regression
    if re.search(r"\bCoefficients\b|\blm\(|\bRegression\b", blob, re.I):
        r2 = _find(rf"R Square[^\n]*?({_NUM})", blob) or _find(
            rf"Multiple R-squared:\s*({_NUM})", blob)
        adj = _find(rf"Adjusted R Square[^\n]*?({_NUM})", blob) or _find(
            rf"Adjusted R-squared:\s*({_NUM})", blob)
        f_value = _find(rf"F-statistic:\s*({_NUM})", blob) or _find(
            rf"\bF\b[^\n]*?({_NUM})", blob)
        p_value = _find(rf"p-value:\s*[<]?\s*({_NUM})", blob)
        results.append(ParsedResult(
            kind="regression", raw=blob, label="linear regression",
            values={k: v for k, v in {
                "R2": r2, "adj_R2": adj, "F": f_value, "p": p_value,
            }.items() if v is not None},
            confidence="ambiguous" if r2 is None else "parsed",
        ))

    # ---- Chi-square
    if re.search(r"chi-square|Pearson Chi|X-squared", blob, re.I):
        chi = (_find(rf"X-squared\s*=\s*({_NUM})", blob)
               or _find(rf"Pearson Chi-Square[^\n]*?({_NUM})", blob))
        df = _find(rf"\bdf\s*=\s*({_NUM})", blob)
        p_value = (_find(rf"p-value\s*[<=]\s*({_NUM})", blob)
                   or _find(_ASYMP, blob))
        n = _find(rf"N of Valid Cases[^\n]*?({_NUM})", blob)
        results.append(ParsedResult(
            kind="chi_square", raw=blob, label="chi-square test of independence",
            values={k: v for k, v in {
                "chi2": chi, "df": df, "p": p_value, "N": n,
            }.items() if v is not None},
            note=("APA requires the sample size inside the parentheses with the "
                  "degrees of freedom: χ²(2, N = 180). Without N the statistic "
                  "cannot be interpreted."
                  if n is None else ""),
            confidence="ambiguous" if chi is None else "parsed",
        ))

    return results


# ------------------------------------------------------------------- rendering


def render(result: ParsedResult) -> str:
    """One parsed result as an APA sentence fragment."""
    v = result.values
    kind = result.kind

    def stat(symbol: str, key: str, decimals: int = 2) -> str | None:
        if key not in v:
            return None
        return fmt_stat(symbol, v[key], decimals=decimals)

    if kind == "t_test":
        pieces: list[str] = []
        if "t" in v and "df" in v:
            df = v["df"]
            df_text = f"{df:.2f}" if abs(df - round(df)) > 1e-6 else f"{int(round(df))}"
            pieces.append(f"t({df_text}) = "
                          f"{fmt_number(v['t'], decimals=2)}")
        elif "t" in v:
            pieces.append(fmt_stat("t", v["t"]))
        if "p" in v:
            pieces.append(fmt_p(v["p"]))
        if "ci_low" in v and "ci_high" in v:
            pieces.append(fmt_ci(v["ci_low"], v["ci_high"]))
        if "d" in v:
            pieces.append(fmt_stat("d", v["d"]))
        return ", ".join(pieces)

    if kind == "anova":
        pieces = []
        if "F" in v and "df1" in v and "df2" in v:
            pieces.append(f"F({int(v['df1'])}, {int(v['df2'])}) = "
                          f"{fmt_number(v['F'], decimals=2)}")
        elif "F" in v:
            pieces.append(fmt_stat("F", v["F"]))
        if "p" in v:
            pieces.append(fmt_p(v["p"]))
        if "partial_eta2" in v:
            pieces.append("ηp² = " + fmt_number(v["partial_eta2"], decimals=2,
                                                leading_zero=False))
        return ", ".join(pieces)

    if kind == "correlation":
        pieces = []
        symbol = "rs" if result.label == "Spearman" else "r"
        if "df" in v and "r" in v:
            pieces.append(f"{symbol}({int(v['df'])}) = "
                          + fmt_number(v["r"], decimals=2, leading_zero=False))
        elif "r" in v:
            pieces.append(f"{symbol} = "
                          + fmt_number(v["r"], decimals=2, leading_zero=False))
        if "p" in v:
            pieces.append(fmt_p(v["p"]))
        return ", ".join(pieces)

    if kind == "regression":
        pieces = []
        if "R2" in v:
            pieces.append("R² = " + fmt_number(v["R2"], decimals=2,
                                               leading_zero=False))
        if "adj_R2" in v:
            pieces.append("adjusted R² = "
                          + fmt_number(v["adj_R2"], decimals=2,
                                       leading_zero=False))
        if "F" in v:
            pieces.append(fmt_stat("F", v["F"]))
        if "p" in v:
            pieces.append(fmt_p(v["p"]))
        return ", ".join(pieces)

    if kind == "chi_square":
        pieces = []
        if "chi2" in v and "df" in v:
            inner = f"{int(v['df'])}"
            if "N" in v:
                inner += f", N = {int(v['N'])}"
            pieces.append(f"χ²({inner}) = {fmt_number(v['chi2'], decimals=2)}")
        elif "chi2" in v:
            pieces.append("χ² = " + fmt_number(v["chi2"], decimals=2))
        if "p" in v:
            pieces.append(fmt_p(v["p"]))
        return ", ".join(pieces)

    return ", ".join(f"{k} = {val:g}" for k, val in v.items())


def sentence(result: ParsedResult, *, variables: str = "",
             direction: str = "") -> str:
    """A full sentence, with the statistics where APA puts them.

    **A missing p value never renders as a non-significant result.** The first
    version of this function used `p is not None and p < alpha`, so an ANOVA whose
    p the parser failed to read came back as "was not statistically significant" —
    a confident, wrong claim generated from an absence. When p is missing the
    sentence states the statistics and says the p value is missing, which is the
    only honest thing it can say.
    """
    body = render(result)
    subject = variables.strip() or "the comparison"

    if result.values.get("p") is None:
        stem = {
            "t_test": f"A {result.label or ''} t test compared {subject}".strip(),
            "anova": f"An analysis of variance examined the effect of {subject}",
            "correlation": f"{subject} were correlated",
            "regression": f"A regression model predicted {subject}",
            "chi_square": f"A chi-square test examined the association between "
                          f"{subject}",
        }.get(result.kind, subject)
        tail = f", {body}" if body else ""
        return (f"{stem}{tail}. [The p value could not be read from the output "
                f"you pasted — add it before using this sentence. Significance "
                f"is not stated here because it is not known.]")

    lead = {
        "t_test": f"{subject} differed significantly"
                  if _is_significant(result) else
                  f"{subject} did not differ significantly",
        "anova": f"The effect of {subject} was statistically significant"
                 if _is_significant(result) else
                 f"The effect of {subject} was not statistically significant",
        "correlation": f"{subject} were significantly correlated"
                       if _is_significant(result) else
                       f"{subject} were not significantly correlated",
        "regression": f"The model significantly predicted {subject}"
                      if _is_significant(result) else
                      f"The model did not significantly predict {subject}",
        "chi_square": f"The association between {subject} was statistically "
                      f"significant" if _is_significant(result) else
                      f"The association between {subject} was not statistically "
                      f"significant",
    }.get(result.kind, subject)
    if direction.strip():
        lead += f", {direction.strip()}"
    return f"{lead}, {body}."


def _is_significant(result: ParsedResult, alpha: float = 0.05) -> bool:
    p_value = result.values.get("p")
    return p_value is not None and p_value < alpha


# ------------------------------------------------------------------ the checker


@dataclass
class StyleIssue:
    code: str
    message: str
    excerpt: str
    suggestion: str


# Applied to prose the user wrote themselves, so a results section drafted by hand
# gets the same rules as one generated here.
_STYLE_RULES = [
    (r"\bp\s*[=<>]\s*0\.\d+", "p_leading_zero",
     "APA drops the leading zero on values that cannot exceed 1 (§6.36).",
     "Write p = .03 rather than p = 0.03."),
    # `0?\.?0{2,}` so both "p = .000" and SPSS's own "p = 0.000" match — the
    # earlier `\.?0{2,}` anchored straight after the equals and could not get
    # past the leading zero, so the commonest form of this error went unflagged.
    (r"\bp\s*=\s*0?\.?0{2,}\b", "p_is_zero",
     "A p value is never zero. SPSS prints .000 because it rounds.",
     "Write p < .001. This is the most common statistical-reporting error in "
     "student work and it is caught every time."),
    (r"\b(?:r|R)\s*[=]\s*0\.\d+", "r_leading_zero",
     "A correlation cannot exceed 1, so APA drops the leading zero (§6.36).",
     "Write r = .42 rather than r = 0.42."),
    (r"\bp\s*<\s*\.05\b", "threshold_p",
     "APA asks for exact p values rather than thresholds (§6.36).",
     "Report the exact value — p = .032 — unless it is below .001."),
    (r"\b(approached|trending toward|marginally)\s+significan",
     "approached_significance",
     "\"Approached significance\" has no statistical meaning: a result is either "
     "below your alpha or it is not.",
     "Report the exact p value and the effect size, and discuss the effect size. "
     "That is the honest version of what this phrase is reaching for."),
    (r"\bproves?\b", "proves",
     "Statistical tests do not prove.",
     "\"Suggests\", \"indicates\", or \"is consistent with\"."),
    (r"\bsignificant\b(?![^.]{0,40}\b(?:p|statistical))", "significant_bare",
     "\"Significant\" without a qualifier is ambiguous between statistical and "
     "clinical significance, and the difference matters most in exactly the "
     "papers where it is blurred.",
     "Say \"statistically significant\" or \"clinically significant\", and if "
     "both apply say both."),
    (r"\b(?:t|F|r|M|SD|p)\s*=\s*", "italics_reminder"),
]


def check_prose(text: str) -> list[StyleIssue]:
    """Flag APA statistical-style problems in a results section.

    The italics rule cannot be checked from plain text — a `.docx` carries the
    formatting and a textarea does not — so it is reported once as a reminder
    rather than per occurrence, and the export applies real italic runs.
    """
    issues: list[StyleIssue] = []
    if not text.strip():
        return issues
    for entry in _STYLE_RULES:
        pattern, code = entry[0], entry[1]
        if code == "italics_reminder":
            if re.search(pattern, text):
                issues.append(StyleIssue(
                    code=code,
                    message="Statistical symbols must be italicised in the "
                            "exported document (§6.44): M, SD, t, F, p, r, d, n.",
                    excerpt="",
                    suggestion="The exporter applies this automatically to "
                               "statistics it rendered. If you typed these by "
                               "hand, italicise the symbols — and remember the "
                               "matching rule that Greek letters (α, β, χ², η²) "
                               "are NOT italicised.",
                ))
            continue
        message, suggestion = entry[2], entry[3]
        for match in re.finditer(pattern, text, re.IGNORECASE):
            issues.append(StyleIssue(code=code, message=message,
                                     excerpt=match.group(0),
                                     suggestion=suggestion))
    return issues


def translate(text: str, *, variables: str = "",
              direction: str = "") -> dict[str, Any]:
    """The whole pipeline: parse, render, and report what could not be read."""
    parsed = parse(text)
    rendered = []
    for result in parsed:
        body = render(result)
        rendered.append({
            "kind": result.kind,
            "label": result.label,
            "statistics": body,
            "sentence": sentence(result, variables=variables,
                                 direction=direction),
            "runs": [{"text": t, "italic": i}
                     for t, i in italic_runs(sentence(result,
                                                      variables=variables,
                                                      direction=direction))],
            "values": result.values,
            "note": result.note,
            "confidence": result.confidence,
        })
    return {
        "results": rendered,
        "recognised": len(rendered),
        "issues": [
            {"code": i.code, "message": i.message, "excerpt": i.excerpt,
             "suggestion": i.suggestion}
            for i in check_prose(text)
        ],
        "note": (
            "Nothing was recognised. This reads output rather than computing it, "
            "and it only recognises output it can identify with confidence — an "
            "R t.test block, an SPSS ANOVA table, a regression summary. Paste the "
            "block including its header line, or enter the values by hand below."
            if not rendered else
            "Check every number against your output before you use these "
            "sentences. This formats what it read; it cannot tell you whether it "
            "read the right row, and on an SPSS independent-samples table there "
            "are two rows and only one of them is yours."
        ),
    }


def manual(kind: str, values: dict[str, Any], *, variables: str = "",
           direction: str = "") -> dict[str, Any]:
    """Render from values entered by hand, for output the parser cannot read."""
    cleaned: dict[str, float] = {}
    for key, value in (values or {}).items():
        if value in (None, ""):
            continue
        try:
            cleaned[key] = float(value)
        except (TypeError, ValueError):
            continue
    result = ParsedResult(kind=kind, values=cleaned, label=kind)
    text = sentence(result, variables=variables, direction=direction)
    return {
        "statistics": render(result),
        "sentence": text,
        "runs": [{"text": t, "italic": i} for t, i in italic_runs(text)],
    }


def supported() -> list[dict[str, Any]]:
    """What can be entered by hand, and which fields each test needs."""
    return [
        {"kind": "t_test", "label": "t test",
         "fields": ["t", "df", "p", "ci_low", "ci_high", "d"],
         "apa": "t(34) = 2.11, p = .042, 95% CI [0.14, 6.98], d = 0.51"},
        {"kind": "anova", "label": "ANOVA",
         "fields": ["F", "df1", "df2", "p", "partial_eta2"],
         "apa": "F(2, 87) = 6.44, p = .002, ηp² = .13"},
        {"kind": "correlation", "label": "Correlation",
         "fields": ["r", "df", "p"],
         "apa": "r(58) = .42, p < .001"},
        {"kind": "regression", "label": "Regression",
         "fields": ["R2", "adj_R2", "F", "df1", "df2", "p"],
         "apa": "R² = .34, adjusted R² = .32, F(3, 96) = 16.21, p < .001"},
        {"kind": "chi_square", "label": "Chi-square",
         "fields": ["chi2", "df", "N", "p"],
         "apa": "χ²(2, N = 180) = 9.87, p = .007"},
    ]
