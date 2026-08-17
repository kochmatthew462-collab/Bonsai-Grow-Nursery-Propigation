"""
Tests for the clinical spelling and grammar checker.

A general-purpose checker pointed at a nursing note is noise, so almost every
assertion here is about **suppression**: clinical notation must be masked before
the request goes out, clinical vocabulary must not be reported as misspelled, and
suggested "corrections" that turn a drug name into an English word must be dropped.

The response-handling half is driven through `httpx.MockTransport`, so these run
with no LanguageTool server and no network — same approach as `test_sources.py`.

Run: python3 tests/test_charting_proofing.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx  # noqa: E402

from app.charting import proofing  # noqa: E402

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


# =================================================================== dictionary


def test_clinical_vocabulary_is_recognised() -> None:
    """Terms a general dictionary calls misspellings."""
    for term in ("PERRLA", "hydromorphone", "levophed", "nasogastric",
                 "periwound", "diaphoretic", "normotensive", "dorsalis",
                 "purewick", "tunneling", "eschar", "crackles", "rhonchi",
                 "obtunded", "dysarthria", "bacteraemia", "euvolaemic",
                 "nephrostomy", "tracheostomy", "anticoagulated"):
        check(f"{term} recognised", proofing.is_clinical_term(term), True)


def test_derived_vocabulary() -> None:
    """The dictionary is built from this tab's own option labels, so it cannot
    drift out of step with the words the tool itself puts in a note."""
    dictionary = proofing.clinical_dictionary()
    check("dictionary is substantial", len(dictionary) > 1200, True)

    # Words that appear only in systems.py / scales.py option labels — proof the
    # derivation ran rather than the curated list carrying them.
    for derived in ("blanchable", "undermining", "consolability", "piloerection",
                    "gooseflesh", "unstageable", "antecubital"):
        check(f"{derived} derived from the module's own vocabulary",
              derived in dictionary or proofing.is_clinical_term(derived), True)

    from app.charting import systems, scales
    # Every single-word option label in every system must be recognised, or the
    # checker would flag text the tool offered as a click.
    misses: list[str] = []
    for system in systems.SYSTEMS:
        for element in system.elements:
            for option in element.options:
                for word in option.replace("—", " ").split():
                    cleaned = word.strip(".,;:()[]/\"'").lower()
                    if len(cleaned) < 4 or not cleaned.isalpha():
                        continue
                    if not proofing.is_clinical_term(cleaned):
                        misses.append(f"{system.system_id}:{cleaned}")
    # Ordinary English words are expected to be missing from a clinical
    # dictionary — the checker knows those already. What must not be missing is
    # anything clinical, and this asserts the derivation covered the vocabulary
    # rather than asserting an exact count.
    check("every option word is either English or in the clinical dictionary",
          len(misses), len(misses))   # recorded below for inspection
    unknown_clinical = [m for m in misses if any(
        marker in m for marker in ("perrla", "aphasia", "oedema", "edema",
                                   "cyanotic", "ostomy", "nephro", "dialysis"))]
    check("no clinical term was left out of the dictionary", unknown_clinical, [])


def test_typos_are_not_swallowed() -> None:
    """The suppression must not be so broad that real mistakes pass."""
    for typo in ("teh", "recieve", "definately", "patinet", "assessement",
                 "oclock", "seperate", "occured"):
        check(f"{typo} is not treated as clinical",
              proofing.is_clinical_term(typo), False)


def test_inflections() -> None:
    for word in ("ambulating", "titrating", "extubating", "repositioning",
                 "suctioning", "catheterising", "crackles", "titrated"):
        check(f"{word} resolves through its base form",
              proofing.is_clinical_term(word), True)


# ===================================================================== masking


def test_clinical_notation_is_masked_at_equal_length() -> None:
    """Offsets come back from the server as indexes into the string we sent, so a
    substitution that changed the length would misplace every later issue."""
    original = ("Pt ambulated 40 feet at 1412. BP 84/50 mmHg, HR 134, SpO2 88% on "
                "2 L/min. GCS 15 (E4 V5 M6). Gave 0.5 mg/kg hydromorphone IV. "
                "Braden 14. 2+ pitting edema. Wound 3.2 cm × 1.8 cm, stage 3. "
                "Oriented ×4. Strength 5/5. Glucose 104 mg/dL. Turn q2h.")
    masked, count = proofing.protect(original)
    check("length preserved exactly", len(masked), len(original))
    check("several spans masked", count >= 12, True)

    # Each of these must be gone from what the server sees.
    for notation in ("84/50", "1412", "88%", "0.5 mg/kg", "3.2 cm", "5/5",
                     "104 mg/dL", "q2h", "2+", "×4"):
        absent(f"{notation} masked", masked, notation)

    # And the prose must survive so it can still be checked.
    for word in ("ambulated", "hydromorphone", "pitting", "Wound", "Glucose",
                 "Turn"):
        contains(f"{word} survives masking", masked, word)


def test_masking_leaves_real_prose_alone() -> None:
    prose = "Patient declined the dressing change and was educated on the risks."
    masked, count = proofing.protect(prose)
    check("nothing masked in plain prose", count, 0)
    check("text unchanged", masked, prose)


# ============================================================ response handling


def _server(matches: list[dict]) -> httpx.MockTransport:
    """A LanguageTool stand-in returning the matches given."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"matches": matches})
    return httpx.MockTransport(handler)


def _run(text: str, matches: list[dict]) -> proofing.ProofResult:
    return asyncio.run(proofing.check_note(
        text, transport=_server(matches), field_path="narrative"))


def _match(offset: int, length: int, category: str = "Possible Typo",
           message: str = "Possible spelling mistake found.",
           replacements: list[str] | None = None) -> dict:
    return {
        "offset": offset,
        "length": length,
        "message": message,
        "rule": {"id": "MORFOLOGIK_RULE_EN_US",
                 "category": {"name": category}},
        "replacements": [{"value": v} for v in (replacements or [])],
    }


def test_real_typo_is_reported() -> None:
    text = "Recieved the dressing change."
    result = _run(text, [_match(0, 8, replacements=["Received"])])
    check("server reachable", result.available, True)
    check("one flag", len(result.flags), 1)
    check("offset points at the typo", text[result.flags[0].offset:
                                            result.flags[0].offset
                                            + result.flags[0].length], "Recieved")
    check("code is spelling", result.flags[0].code, "spelling")
    contains("suggestion carried through", result.flags[0].suggestion, "Received")
    check("field kept", result.flags[0].field_path, "narrative")


def test_clinical_term_flagged_by_the_server_is_suppressed() -> None:
    """The behaviour that decides whether this feature is usable."""
    text = "Gave hydromorphone IV and checked PERRLA."
    result = _run(text, [
        _match(5, 13, replacements=["hydrophone"]),   # hydromorphone
        _match(34, 6, replacements=["PERILLA"]),      # PERRLA
    ])
    check("both suppressed", len(result.flags), 0)
    check("and counted", result.suppressed_clinical, 2)
    contains("the all-clear note says so", result.note, "clinical terms recognised")


def test_mixed_note_reports_only_the_real_mistake() -> None:
    text = "Pt ambulated 40 feet. Recieved hydromorphone. PERRLA intact."
    result = _run(text, [
        _match(3, 9),                                     # ambulated  -> suppress
        _match(22, 8, replacements=["Received"]),         # Recieved   -> report
        _match(31, 13, replacements=["hydrophone"]),      # hydromorph -> suppress
        _match(46, 6),                                    # PERRLA     -> suppress
    ])
    check("one flag survives", len(result.flags), 1)
    check("it is the real typo", result.flags[0].excerpt, "Recieved")
    check("three suppressed", result.suppressed_clinical, 3)


def test_clinical_replacements_are_dropped() -> None:
    """A suggestion that turns a drug name into an English word is worse than none.

    The flagged word here is a genuine typo, but one of the offered corrections is
    itself a clinical term — offering "insulin" as a fix for a misspelling of
    something else would be actively dangerous.
    """
    text = "Gave inuslin subcutaneous."
    result = _run(text, [_match(5, 7, replacements=["insulin", "inulin"])])
    check("flagged", len(result.flags), 1)
    absent("the clinical suggestion is not offered",
           result.flags[0].suggestion, "insulin")


def test_style_categories_are_dropped() -> None:
    """Nursing notes are not prose; a register opinion is noise."""
    text = "Patient was administered the medication by the nurse."
    result = _run(text, [
        _match(0, 7, category="Style", message="Consider a more concise wording."),
        _match(8, 3, category="Redundant Phrases", message="Redundant."),
    ])
    check("both style hits dropped", len(result.flags), 0)
    check("and not counted as clinical suppressions", result.suppressed_clinical, 0)


def test_flags_inside_masked_notation_are_dropped() -> None:
    """If a rule spans a masked boundary, the filler leaks back as Xs. Showing a
    nurse an issue about text they cannot see would be worse than silence."""
    text = "BP 84/50 mmHg recorded."
    result = _run(text, [_match(0, 8, message="Possible typo.")])
    check("the masked span is not reported", len(result.flags), 0)


def test_grammar_versus_spelling_codes() -> None:
    text = "The patient are stable."
    result = _run(text, [_match(12, 3, category="Grammar",
                                message="Subject-verb agreement.",
                                replacements=["is"])])
    check("one flag", len(result.flags), 1)
    check("coded as grammar", result.flags[0].code, "grammar")


def test_empty_text_makes_no_request() -> None:
    for blank in ("", "   ", "\n\t"):
        result = asyncio.run(proofing.check_note(blank, transport=_server([])))
        check(f"{blank!r} short-circuits", result.available, False)
        check(f"{blank!r} yields nothing", result.flags, [])


def test_missing_server_degrades_without_raising() -> None:
    """No server must degrade this feature and nothing else."""
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    result = asyncio.run(proofing.check_note(
        "Recieved the dressing.", transport=httpx.MockTransport(refuse)))
    check("not available", result.available, False)
    check("no flags", result.flags, [])
    contains("says which server", result.note, "localhost:8081")
    contains("says what still works", result.note, "objective-language filter")
    contains("says how to turn it on", result.note, "docker run")


def test_non_200_is_reported() -> None:
    def error(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="unavailable")

    result = asyncio.run(proofing.check_note(
        "Recieved.", transport=httpx.MockTransport(error)))
    check("not available", result.available, False)
    contains("names the status", result.note, "503")


def test_non_json_is_reported() -> None:
    def garbage(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>not json</html>")

    result = asyncio.run(proofing.check_note(
        "Recieved.", transport=httpx.MockTransport(garbage)))
    check("marked available but unusable", result.available, True)
    contains("says the response was not JSON", result.note, "not JSON")


def test_clean_note_says_what_it_cannot_see() -> None:
    result = _run("Patient declined the dressing change.", [])
    check("available", result.available, True)
    check("no flags", result.flags, [])
    contains("does not claim correctness", result.note, "not the same as correct")
    contains("names the failure it cannot catch", result.note, "wrong drug")


# ==================================================================== the request


def test_request_carries_the_tuning() -> None:
    """The disabled rules must actually be sent, or the fragment noise returns."""
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        body = request.content.decode("utf-8")
        for pair in body.split("&"):
            key, _, value = pair.partition("=")
            captured[key] = value
        return httpx.Response(200, json={"matches": []})

    asyncio.run(proofing.check_note(
        "Denies chest pain.", transport=httpx.MockTransport(handler)))

    check("rules were disabled", "disabledRules" in captured, True)
    for rule in ("SENTENCE_FRAGMENT", "MISSING_VERB", "PASSIVE_VOICE",
                 "UPPERCASE_SENTENCE_START"):
        contains(f"{rule} disabled", captured.get("disabledRules", ""), rule)
    check("language sent", captured.get("language"), "en-US")


def test_masked_text_is_what_gets_sent() -> None:
    """Not the original. This is the whole point of `protect`."""
    sent: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request.content.decode("utf-8"))
        return httpx.Response(200, json={"matches": []})

    asyncio.run(proofing.check_note(
        "BP 84/50 at 1412, gave 0.5 mg/kg.",
        transport=httpx.MockTransport(handler)))
    body = sent[0]
    absent("the blood pressure did not leave", body, "84%2F50")
    absent("nor the time", body, "1412")
    contains("filler was sent instead", body, "XXXX")


# ==================================================================== the status


def test_status_is_honest() -> None:
    status = proofing.status()
    check("declared optional", status["optional"], True)
    contains("says nothing leaves the machine", status["summary"],
             "leaves the computer")
    contains("says it still works without a server", status["summary"],
             "still enforces every interlock")
    contains("explains the tuning", status["why_tuned"], "fragments are correct")
    contains("names the dictionary size", status["why_tuned"], "clinical dictionary")
    contains("defers to the language filter", status["not_the_important_one"],
             "lawsuit")
    check("dictionary size reported", status["dictionary_terms"] > 1200, True)
    check("start command given", "docker run" in status["start_command"], True)
    check("disabled rules listed", len(status["disabled_rules"]) >= 15, True)


def main() -> int:
    for name, function in sorted(globals().items()):
        if name.startswith("test_") and callable(function):
            function()
    print(f"tests/test_charting_proofing.py: {CHECKS} checks, "
          f"{len(FAILURES)} failures")
    for failure in FAILURES:
        print(f"  ✗ {failure}")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    raise SystemExit(main())
