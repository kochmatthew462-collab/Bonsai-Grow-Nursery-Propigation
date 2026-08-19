"""
Tests for the scoring-scale library.

Two kinds of check, and the second is the one that matters.

**Arithmetic**: does a scale add up its items and land in the published band. Easy
to get right and easy to test.

**The awkward cases**: an untestable GCS component, a non-additive algorithm (CAM),
an age-dependent chart (Lund-Browder), a decision tree (ESI), and an instrument
that is not a score at all (the Pediatric Assessment Triangle). Every one of these
is somewhere a naive implementation quietly produces a plausible wrong number, and
a plausible wrong number in a clinical note is worse than no number.

Run: python3 tests/test_charting_scales.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.charting import scales  # noqa: E402
from app.charting.models import Vitals  # noqa: E402

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
        FAILURES.append(f"{label}\n    {needle!r} not found in {haystack!r}")


def absent(label: str, haystack: str, needle: str) -> None:
    global CHECKS
    CHECKS += 1
    if needle.lower() in (haystack or "").lower():
        FAILURES.append(f"{label}\n    {needle!r} unexpectedly present in "
                        f"{haystack!r}")


# ============================================================= structural sanity


def test_registry_integrity() -> None:
    """Every option must be reachable and every item resolvable.

    Two real bugs were caught here rather than at the bedside: CIWA-Ar has
    unlabelled intermediate points, which produced empty option keys, and APACHE
    II's oxygenation item has five options that all begin "A-a gradient", which
    slugged to the same key and made four of them unselectable.
    """
    check("scales registered", len(scales.REGISTRY) >= 21, True)
    for scale in scales.REGISTRY.values():
        for item in scale.items:
            keys = [option.key() for option in item.options]
            check(f"{scale.scale_id}.{item.item_id} keys unique",
                  len(keys), len(set(keys)))
            check(f"{scale.scale_id}.{item.item_id} keys non-empty",
                  all(bool(k) for k in keys), True)
            check(f"{scale.scale_id}.{item.item_id} labels non-empty",
                  all(bool(o.label.strip()) for o in item.options), True)
        check(f"{scale.scale_id} cites a source", bool(scale.citation.strip()), True)
        # Every option must round-trip through the resolver, or a nurse can select
        # something the scorer silently ignores.
        for item in scale.items:
            for option in item.options:
                resolved = scales.Scale._points(item, option.key())
                check(f"{scale.scale_id}.{item.item_id}.{option.key()} resolves",
                      resolved, option.points)


def test_band_coverage() -> None:
    """Bands must not overlap, or a score would report two interpretations."""
    for scale in scales.REGISTRY.values():
        seen: list[tuple[float, float]] = []
        for band in scale.bands:
            for low, high in seen:
                overlap = not (band.high < low or band.low > high)
                check(f"{scale.scale_id} band {band.label} does not overlap",
                      overlap, False)
            seen.append((band.low, band.high))
        check(f"{scale.scale_id} bands ordered low to high",
              seen, sorted(seen))


# ======================================================================= Braden


def test_braden() -> None:
    worst = {k: "1" for k in ("sensory", "moisture", "activity", "mobility",
                              "nutrition")}
    worst["friction"] = "1"
    result = scales.get("braden").evaluate(worst)
    check("braden minimum is 6", result.score, 6.0)
    check("braden 6 band", result.band, "very high risk")

    best = {"sensory": "4", "moisture": "4", "activity": "4", "mobility": "4",
            "nutrition": "4", "friction": "3"}
    result = scales.get("braden").evaluate(best)
    check("braden maximum is 23", result.score, 23.0)
    contains("braden 23 detail", result.band_detail, "does not exclude risk")

    mid = {"sensory": "3", "moisture": "3", "activity": "2", "mobility": "2",
           "nutrition": "2", "friction": "2"}
    result = scales.get("braden").evaluate(mid)
    check("braden 14", result.score, 14.0)
    check("braden 14 band", result.band, "moderate risk")
    contains("braden narrative names the range", result.narrative, "range 6-23")

    partial = scales.get("braden").evaluate({"sensory": "3"})
    check("braden partial score is a floor", partial.score, 3.0)
    check("braden partial names what is missing", len(partial.incomplete), 5)
    contains("braden partial narrative admits it", partial.narrative,
             "total is a floor")


def key_for(scale_id: str, item_id: str, label_starts: str) -> str:
    """Find an option's key by the start of its label.

    Keys are slugged from labels and truncated, so hand-writing one in a test is
    both tedious and wrong the first time a label is reworded — which is exactly
    what happened while writing this file. Resolving by label keeps the tests
    honest about what they are asserting: the points, not the slug.
    """
    item = scales.get(scale_id).item(item_id)
    for option in item.options:
        if option.label.lower().startswith(label_starts.lower()):
            return option.key()
    raise AssertionError(f"no option starting {label_starts!r} on "
                         f"{scale_id}.{item_id}")


def test_morse() -> None:
    result = scales.get("morse").evaluate({
        "history": "yes",
        "secondary": "yes",
        "aid": key_for("morse", "aid", "Crutches"),
        "iv": "yes",
        "gait": key_for("morse", "gait", "Weak"),
        "mental": key_for("morse", "mental", "Overestimates"),
    })
    check("morse 25+15+15+20+10+15", result.score, 100.0)
    check("morse high risk", result.band, "high risk")
    contains("morse note warns about local calibration",
             scales.get("morse").note, "calibrate their own cut points")


# ====================================================================== GCS


def test_gcs_full() -> None:
    result = scales.get("gcs").evaluate({"eye": "4", "verbal": "5", "motor": "6"})
    check("gcs 15", result.score, 15.0)
    contains("gcs narrative shows components", result.narrative, "E4 V5 M6")
    check("gcs 15 band", result.band, "mild range")

    result = scales.get("gcs").evaluate({"eye": "1", "verbal": "1", "motor": "1"})
    check("gcs 3", result.score, 3.0)
    check("gcs 3 band", result.band, "severe range")


def test_gcs_untestable_component() -> None:
    """An intubated patient's verbal response is not 1.

    Scoring it as 1 makes an alert patient look obtunded. This is among the most
    common neuro-charting errors, and a tool that reproduces it is worse than no
    tool.
    """
    result = scales.get("gcs").evaluate({"eye": "4", "verbal": "nt", "motor": "6"})
    check("untestable total is the sum of what was tested", result.score, 10.0)
    check("untestable band", result.band, "not fully testable")
    contains("narrative marks the component", result.narrative, "VNT")
    contains("narrative refuses to call it a GCS", result.narrative,
             "not a valid GCS")
    absent("narrative does not claim a band", result.narrative, "mild range")


# ====================================================================== CAM


def test_cam_algorithm() -> None:
    """Features 1 and 2, plus 3 or 4 — not a sum."""
    cam = scales.get("cam")

    both_plus_three = cam.evaluate({"acute": "yes", "inattention": "yes",
                                    "disorganised": "yes", "consciousness": "no"})
    check("1+2+3 positive", both_plus_three.band, "positive for delirium")

    both_plus_four = cam.evaluate({"acute": "yes", "inattention": "yes",
                                   "disorganised": "no", "consciousness": "yes"})
    check("1+2+4 positive", both_plus_four.band, "positive for delirium")

    # Three features present but not the required pair: this is the case a naive
    # "count the features" implementation gets wrong.
    without_inattention = cam.evaluate({"acute": "yes", "inattention": "no",
                                        "disorganised": "yes",
                                        "consciousness": "yes"})
    check("3 features but no inattention is negative",
          without_inattention.band, "negative for delirium")
    check("count is still reported", without_inattention.score, 3.0)

    only_pair = cam.evaluate({"acute": "yes", "inattention": "yes",
                              "disorganised": "no", "consciousness": "no"})
    check("1+2 alone is negative", only_pair.band, "negative for delirium")

    incomplete = cam.evaluate({"acute": "yes"})
    check("incomplete has no score", incomplete.score, None)
    check("incomplete band", incomplete.band, "incomplete")

    contains("cam-icu note warns about RASS", scales.get("cam_icu").note,
             "unable to assess")


# ====================================================================== RASS


def test_rass_negative_values() -> None:
    """A scale whose scores go below zero — bands and lookup must both handle it."""
    result = scales.get("rass").evaluate({"level": "-4"})
    check("rass -4", result.score, -4.0)
    check("rass -4 band", result.band, "deep sedation or unarousable")
    contains("rass -4 blocks delirium screening", result.band_detail,
             "cannot be performed")

    check("rass 0", scales.get("rass").evaluate({"level": "0"}).band,
          "alert and calm")
    check("rass +3", scales.get("rass").evaluate({"level": "3"}).band, "agitated")


# ================================================================ CIWA and COWS


def test_ciwa_ar_range() -> None:
    ciwa = scales.get("ciwa_ar")
    zeros = {item.item_id: "0" for item in ciwa.items}
    check("ciwa all-zero", ciwa.evaluate(zeros).score, 0.0)
    check("ciwa all-zero band", ciwa.evaluate(zeros).band, "minimal withdrawal")

    # Nine items score 0-7 and orientation scores 0-4: 63 + 4 = 67.
    worst = {item.item_id: str(max(o.points for o in item.options))
             for item in ciwa.items}
    check("ciwa maximum", ciwa.evaluate(worst).score, 67.0)
    check("ciwa maximum band", ciwa.evaluate(worst).band, "severe withdrawal")
    contains("ciwa note warns about non-communicative patients", ciwa.note,
             "cannot report symptoms")


def test_cows_range() -> None:
    cows = scales.get("cows")
    worst = {item.item_id: str(max(o.points for o in item.options))
             for item in cows.items}
    check("cows maximum", cows.evaluate(worst).score, 48.0)
    check("cows maximum band", cows.evaluate(worst).band, "severe withdrawal")


# ============================================================ warning scores


def test_qsofa() -> None:
    result = scales.get("qsofa").evaluate({"resp": "yes", "mental": "no",
                                          "sbp": "yes"})
    check("qsofa 2", result.score, 2.0)
    check("qsofa 2 band", result.band, "two or more criteria met")
    contains("qsofa is not a diagnosis", result.band_detail, "not a diagnosis")

    one = scales.get("qsofa").evaluate({"resp": "yes", "mental": "no", "sbp": "no"})
    check("qsofa 1 band", one.band, "fewer than two criteria met")


def test_mews_and_news2_from_vitals() -> None:
    """Prefill must land on real option keys, not near-misses.

    The keys are slugged from the option labels, so a prefill table written by hand
    drifts silently the moment a label changes. `prefill_from_vitals` looks the
    option up by label for exactly that reason, and this test is what proves the
    lookup resolves.
    """
    vitals = Vitals(systolic=88, diastolic=50, heart_rate=132,
                    respiratory_rate=26, spo2=89, temperature_c=38.6,
                    oxygen_delivery="2 L/min nasal cannula")

    mews_prefill = scales.prefill_from_vitals("mews", vitals)
    check("mews prefills four items", len(mews_prefill), 4)
    mews = scales.get("mews").evaluate({**mews_prefill, "avpu": "alert"})
    # sbp 81-100 = 1, hr 130+ = 3, rr 21-29 = 2, temp 38.5+ = 2, alert = 0
    check("mews total from vitals", mews.score, 8.0)
    check("mews band", mews.band, "high aggregate score")
    check("mews nothing missing", mews.incomplete, [])

    news_prefill = scales.prefill_from_vitals("news2", vitals)
    news = scales.get("news2").evaluate({**news_prefill, "consciousness": "alert"})
    # rr 25+ = 3, spo2 <=91 = 3, sbp <=90 = 3, hr 131+ = 3, temp 38.1-39 = 1,
    # oxygen = 2, alert = 0
    check("news2 total from vitals", news.score, 15.0)
    check("news2 band", news.band, "high aggregate score")
    check("news2 nothing missing", news.incomplete, [])


def test_news2_scale_two_never_prefilled() -> None:
    """Scale 2 depends on a prescribed target, not on a reading.

    Applying it because a saturation looks low would understate hypoxaemia in
    every patient who is not on an 88-92% target.
    """
    prefill = scales.prefill_from_vitals("news2", Vitals(spo2=85))
    check("scale 2 not prefilled", "spo2_scale2" in prefill, False)
    check("scale 1 is prefilled", prefill.get("spo2"), "91-or-below")


# ==================================================================== ESI


def test_esi_decision_points() -> None:
    """Each decision point must short-circuit at the right level."""
    esi = scales.get("esi")
    cases = [
        ({"life_saving": "yes"}, 1.0),
        ({"life_saving": "no", "high_risk": "yes"}, 2.0),
        ({"life_saving": "no", "high_risk": "no", "confused": "yes"}, 2.0),
        ({"life_saving": "no", "high_risk": "no", "confused": "no",
          "severe_pain": "yes"}, 2.0),
        ({"life_saving": "no", "high_risk": "no", "confused": "no",
          "severe_pain": "no", "resources": "0"}, 5.0),
        ({"life_saving": "no", "high_risk": "no", "confused": "no",
          "severe_pain": "no", "resources": "1"}, 4.0),
        ({"life_saving": "no", "high_risk": "no", "confused": "no",
          "severe_pain": "no", "resources": "2", "danger_vitals": "no"}, 3.0),
    ]
    for responses, expected in cases:
        result = esi.evaluate(responses)
        check(f"esi {responses} -> {expected}", result.score, expected)

    danger = esi.evaluate({"life_saving": "no", "high_risk": "no",
                           "confused": "no", "severe_pain": "no",
                           "resources": "2", "danger_vitals": "yes"})
    contains("danger-zone vitals suggest up-triage", danger.band,
             "consider level 2")

    incomplete = esi.evaluate({"life_saving": "no", "high_risk": "no",
                               "confused": "no", "severe_pain": "no"})
    check("esi without a resource count is incomplete", incomplete.score, None)


def test_esi_does_not_assign_from_vitals() -> None:
    """The tool reports the comparison; the nurse answers decision point D.

    Auto-suggesting a triage level from vital signs is clinical decision support,
    it is wrong often enough to be dangerous, and a level a tool assigned is not
    one anybody can defend in a deposition.
    """
    exceeded = scales.vitals_outside_esi_zone(
        Vitals(heart_rate=132, respiratory_rate=26, spo2=88), "over_8y")
    check("three thresholds exceeded", len(exceeded), 3)
    for line in exceeded:
        absent("no level is proposed", line, "level")

    infant = scales.vitals_outside_esi_zone(Vitals(heart_rate=170), "under_3m")
    check("170 is within the infant threshold", infant, [])
    child = scales.vitals_outside_esi_zone(Vitals(heart_rate=170), "over_8y")
    check("170 exceeds the adult threshold", len(child), 1)

    narrative = scales.get("esi").evaluate({"life_saving": "yes"}).narrative
    contains("narrative attributes the level to the tool", narrative,
             "computed by this tool")
    contains("narrative defers to the triage nurse", narrative,
             "the triage nurse assigns")


# =============================================================== Lund-Browder


def test_lund_browder_is_age_dependent() -> None:
    """The whole point of the chart: a newborn's head is 19%, an adult's is 7%.

    The rule of nines overestimates burn size in small children, which then
    overestimates the fluid they are given.
    """
    scale = scales.get("lund_browder")
    infant = scale.evaluate({"age_band": "0", "region_head": "1"})
    adult = scale.evaluate({"age_band": "adult", "region_head": "1"})
    check("infant head 19%", infant.score, 19.0)
    check("adult head 7%", adult.score, 7.0)

    partial = scale.evaluate({"age_band": "adult", "region_anterior_trunk": "0.5"})
    check("half the anterior trunk", partial.score, 6.5)

    combined = scale.evaluate({"age_band": "0", "region_head": "1",
                               "region_anterior_trunk": "0.5"})
    check("infant head plus half trunk", combined.score, 25.5)
    contains("narrative names the column used", combined.narrative,
             "under 1 year")
    contains("narrative excludes superficial burn", combined.narrative,
             "Superficial burn excluded")

    nested = scale.evaluate({"age_band": "adult", "regions": {"head": "1"}})
    check("nested regions accepted too", nested.score, 7.0)

    check("no burn recorded", scale.evaluate({"age_band": "adult"}).score, 0.0)


def test_lund_browder_totals_100() -> None:
    """Every column must sum to 100% of body surface area."""
    for band, label in scales._LB_AGE_BANDS:
        total = sum(percentages[band] for percentages in scales._LUND_BROWDER.values())
        check(f"lund-browder {label} column sums to 100", round(total, 1), 100.0)


# ======================================================================= PAT


def test_pat_is_not_a_score() -> None:
    """The Pediatric Assessment Triangle is a pattern, not a total."""
    pat = scales.get("pat")
    result = pat.evaluate({"appearance": "abnormal", "breathing": "abnormal",
                           "circulation": "normal"})
    check("two limbs abnormal", result.score, 2.0)
    check("pattern named", result.band, "respiratory failure")
    contains("detail says it is not a score", result.band_detail, "not a score")

    check("appearance only",
          pat.evaluate({"appearance": "abnormal", "breathing": "normal",
                        "circulation": "normal"}).band,
          "possible central nervous system or metabolic problem")
    check("all three",
          pat.evaluate({"appearance": "abnormal", "breathing": "abnormal",
                        "circulation": "abnormal"}).band,
          "cardiopulmonary failure")
    check("none",
          pat.evaluate({"appearance": "normal", "breathing": "normal",
                        "circulation": "normal"}).band,
          "stable first impression")


# =================================================================== licensing


def test_licensing_is_declared() -> None:
    """Every copyrighted instrument must name its holder somewhere visible.

    A tool that implemented Braden, Morse, FLACC, CPOT, CAM and ESI without saying
    whose work they are would be quietly infringing, and the wording in this module
    is written fresh precisely so it does not.
    """
    declared: set[str] = set()
    for entry in scales.LICENSING:
        for scale_id in entry["scales"]:
            declared.add(scale_id)
        check(f"licensing entry {entry['holder']} has a note",
              bool(entry["note"].strip()), True)
    for scale_id in scales.REGISTRY:
        check(f"{scale_id} licensing declared", scale_id in declared, True)

    for scale_id in ("braden", "morse", "flacc", "cpot", "cam", "cam_icu", "esi",
                     "apache_ii", "wong_baker", "news2"):
        entry = next(e for e in scales.LICENSING if scale_id in e["scales"])
        check(f"{scale_id} names a rights holder",
              bool(entry["holder"].strip()), True)

    faces = next(e for e in scales.LICENSING if "wong_baker" in e["scales"])
    contains("FACES artwork is not reproduced", faces["note"], "NOT reproduced")

    apache = scales.get("apache_ii")
    contains("apache note warns it is not a bedside score", apache.note,
             "not a bedside")
    contains("apache note warns about cohorts", apache.note, "cohorts")


def test_for_setting_filters() -> None:
    emergency = {s.scale_id for s in scales.for_setting("emergency")}
    icu = {s.scale_id for s in scales.for_setting("icu")}
    check("esi is an emergency scale", "esi" in emergency, True)
    check("esi is not an ICU scale", "esi" in icu, False)
    check("sofa is an ICU scale", "sofa" in icu, True)
    check("braden is universal", "braden" in emergency and "braden" in icu, True)


def main() -> int:
    for name, function in sorted(globals().items()):
        if name.startswith("test_") and callable(function):
            function()
    print(f"tests/test_charting_scales.py: {CHECKS} checks, "
          f"{len(FAILURES)} failures")
    for failure in FAILURES:
        print(f"  ✗ {failure}")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    raise SystemExit(main())
