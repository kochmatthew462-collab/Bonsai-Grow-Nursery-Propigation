"""
Tests for the objective-language filter, the identifier scanner, and the note
composer's punctuation.

The interesting assertions here are the **negative** ones. A checker that flags
everything is a checker that gets ignored within a shift, so as much of this file
tests what must *not* fire as what must:

* quoted patient speech is exempt from every rule, because a verbatim quote is the
  strongest sentence in a nursing note and a tool that punished quoting would make
  documentation worse;
* "pain management" and "airway management" are not staffing complaints;
* "Pump serial checked" is not a device identifier;
* clinical numbers are not medical record numbers.

Run: python3 tests/test_charting_language.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.charting import language, narrative, phi, systems  # noqa: E402
from app.charting.models import (  # noqa: E402
    Encounter, Entry, EntryKind, Medication, ProviderNotification, Severity,
    Vitals, iso, now_utc,
)

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


def codes(text: str) -> set[str]:
    return {flag.code for flag in language.scan(text)}


# ============================================================== the hard blocks


def test_incident_report_firewall() -> None:
    """The one rule with no override, in every phrasing it occurs in."""
    for phrase in ("Completed an incident report.",
                   "Event report filed.",
                   "Occurrence report submitted to the unit.",
                   "Notified risk management of the event.",
                   "Safety report entered."):
        flags = language.scan(phrase)
        blocking = language.blocking(flags)
        check(f"{phrase!r} blocks", len(blocking) >= 1, True)
        check(f"{phrase!r} blocks on the right rule",
              any(f.code == "incident_report" for f in blocking), True)
        # The specification named the wording for this one exactly: the message
        # tells the nurse to document only the clinical facts of the event, and
        # the suggestion explains where the incident report itself goes.
        contains(f"{phrase!r} states the rule", blocking[0].message,
                 "clinical facts of the event")
        contains(f"{phrase!r} says what to do instead",
                 blocking[0].suggestion, "File the incident report separately")

    # And the clinical facts of the same event must pass cleanly.
    clean = ("At 0910, 0.5 mg was given rather than the ordered 0.25 mg. "
             "Recognised at 0915. Dr. Chen notified at 0918.")
    check("the same event stated as facts is clean",
          language.blocking(language.scan(clean)), [])


def test_other_patient_blocked() -> None:
    for phrase in ("The other patient in room 12 was coding.",
                   "Delayed because another patient needed help.",
                   "My other patient was unstable."):
        blocking = language.blocking(language.scan(phrase))
        check(f"{phrase!r} blocks", any(f.code == "other_patient" for f in blocking),
              True)
    check("a de-identified delay is fine",
          language.blocking(language.scan(
              "Response delayed by a concurrent emergency on the unit; charge "
              "nurse notified at 1420.")), [])


def test_blame_and_fault_blocked() -> None:
    blame = language.blocking(language.scan(
        "Dr. Alvarez failed to respond to three pages."))
    check("naming a colleague at fault blocks",
          any(f.code == "blame_colleague" for f in blame), True)
    contains("the suggestion offers the factual version", blame[0].suggestion,
             "Paged Dr. Alvarez at 1412")

    # The same failure stated as verifiable facts must pass.
    factual = ("Paged Dr. Alvarez at 1412 and again at 1435. No response "
               "received. Escalated to the charge nurse at 1440.")
    check("the factual version is clean",
          language.blocking(language.scan(factual)), [])

    for phrase in ("Given by mistake.", "This was my fault.",
                   "I forgot to check the pump.",
                   "Wrong medication was given.",
                   "I should have noticed the change sooner."):
        blocking = language.blocking(language.scan(phrase))
        check(f"{phrase!r} blocks as an admission of fault",
              any(f.code == "admission_of_fault" for f in blocking), True)


# ============================================================= the quote exemption


def test_quoted_speech_is_exempt() -> None:
    """The single most important behaviour in this module.

    A checker that flagged "angry" inside a patient's own quotation would train
    the nurse to stop quoting patients, which is the opposite of what defensible
    documentation needs.
    """
    quoted = 'Patient stated, "I am so angry I could scream, and I refuse to stay."'
    check("nothing fires inside a quotation", codes(quoted), set())

    curly = 'Patient stated, “I feel drunk and confused.”'
    check("curly quotes are exempt too", codes(curly), set())

    single = "Patient stated, 'I am not taking that pill.'"
    check("single quotes are exempt", codes(single), set())

    # Outside the quotation, the same words still fire.
    mixed = ('Patient stated, "I am so angry." Patient was aggressive and '
             'non-compliant.')
    found = codes(mixed)
    check("emotional label outside the quote fires",
          "emotional_label" in found, True)
    check("judgmental label outside the quote fires",
          "noncompliant" in found, True)


def test_apostrophes_do_not_open_a_quote() -> None:
    """`don't` must not be read as opening a single-quoted span.

    If it were, every word after it in the sentence would be silently exempt — a
    checker that stops checking is worse than no checker, because it looks like it
    is working.
    """
    text = "Patient doesn't want the dressing changed; appears uncomfortable."
    check("appears still fires after an apostrophe",
          "appears_seems" in codes(text), True)
    check("no quoted span was detected", language.quoted_spans(text), [])


def test_quote_suggestions() -> None:
    hints = {f.excerpt.lower() for f in language.suggest_quotes(
        "Patient reported chest pain. Family stated they were worried.")}
    check("both reported-speech constructions suggested", len(hints), 2)

    already = language.suggest_quotes('Patient stated, "It hurts here."')
    check("no suggestion when already quoted", already, [])


# ======================================================== the five categories


def test_judgmental_and_stigmatising() -> None:
    check("non-compliant", "noncompliant" in codes("Patient is non-compliant."), True)
    check("refused", "refused" in codes("Patient refused the dressing change."), True)
    check("drug seeking", "drug_seeking" in codes("Known drug-seeker."), True)
    check("frequent flyer", "drug_seeking" in codes("This frequent flyer again."),
          True)

    stigma = next(f for f in language.scan("Known drug-seeker.")
                  if f.code == "drug_seeking")
    contains("stigma rule cites downstream harm", stigma.message,
             "change how later clinicians")
    contains("stigma rule notes the patient can read it", stigma.message,
             "reads their record")


def test_assumptive() -> None:
    check("appears", "appears_seems" in codes("Patient appears comfortable."), True)
    check("seems", "appears_seems" in codes("Patient seems better."), True)
    check("sleeping", "sleeping" in codes("Patient sleeping."), True)

    sleeping = next(f for f in language.scan("Patient sleeping.")
                    if f.code == "sleeping")
    contains("the sleeping rule explains the stakes", sleeping.message,
             "unresponsive")
    contains("the sleeping rule gives the objective version",
             sleeping.suggestion, "respirations regular and unlaboured")

    # The objective replacement must itself pass.
    replacement = ("Lying in bed with eyes closed, respirations regular and "
                   "unlaboured at 16, roused to light touch and oriented to "
                   "person and place.")
    check("the suggested objective wording is clean", codes(replacement), set())


def test_vague() -> None:
    check("ate well", "ate_well" in codes("Patient ate well."), True)
    check("slept well", "good_night" in codes("Slept well all night."), True)
    check("tolerated well", "tolerated_well" in codes("Tolerated the walk well."),
          True)
    check("per protocol", "adequate" in codes("Treated per protocol."), True)
    check("frequently", "adequate" in codes("Repositioned frequently."), True)

    quantified = ("Consumed 80% of the lunch tray. Repositioned at 2000, 2200, "
                  "0000 and 0200. Treated per the adult sepsis order set.")
    check("the quantified versions are clean", codes(quantified), set())


def test_md_aware() -> None:
    """A notification with no time is the sentence counsel looks for first."""
    check("MD aware fires", "md_aware" in codes("MD aware of the change."), True)
    check("physician notified fires",
          "md_aware" in codes("Physician notified."), True)

    # A notification that carries a time is not flagged: the rule's lookahead
    # exists so the correct form passes.
    good = ("At 1412, paged Dr. Alvarez regarding a systolic of 84. Orders "
            "received at 1418.")
    check("a timed notification is clean", "md_aware" in codes(good), False)


def test_staffing_moves_to_the_right_document() -> None:
    check("short staffed fires",
          "staffing_complaint" in codes("We were short staffed."), True)
    complaint = next(f for f in language.scan("We were short staffed.")
                     if f.code == "staffing_complaint")
    contains("it names the right document", complaint.suggestion,
             "Assignment and Staffing record")
    contains("it explains why", complaint.message, "theory of the case")

    # The false positives that would have made this rule noise.
    for phrase in ("Pain management plan reviewed.",
                   "Airway management per anaesthesia.",
                   "Wound management consult placed.",
                   "Discussed with case management."):
        check(f"{phrase!r} is not a staffing complaint",
              "staffing_complaint" in codes(phrase), False)


def test_dosing_notation() -> None:
    check("trailing zero", "trailing_zero" in codes("Gave 1.0 mg."), True)
    check("naked decimal", "naked_decimal" in codes("Gave .5 mg."), True)
    check("unit abbreviation", "unit_abbrev" in codes("Gave 10 U insulin."), True)
    check("latin frequency", "latin_frequency" in codes("Ordered q.d."), True)
    check("ambiguous drug", "dangerous_drug_abbrev" in codes("MS drip running."),
          True)
    check("cc", "dangerous_drug_abbrev" in codes("Gave 30 cc."), True)
    check("at symbol", "at_symbol" in codes("Running 5 @ 10 mL/hr."), True)

    # Correct notation must pass, including interval notations, which are fine —
    # it is the Latin that causes errors, not "q4h".
    clean = ("Gave 1 mg morphine IV and 0.5 mg lorazepam. Insulin 10 units "
             "subcutaneous. Scheduled q4h. 30 mL flush.")
    found = codes(clean)
    for code in ("trailing_zero", "naked_decimal", "unit_abbrev",
                 "dangerous_drug_abbrev", "at_symbol"):
        check(f"{code} does not fire on correct notation", code in found, False)


def test_rule_table_is_complete() -> None:
    table = language.rule_table()
    listed = {rule["code"] for group in table for rule in group["rules"]}
    check("every rule is in the table", listed, {r.code for r in language.RULES})
    for group in table:
        check(f"category {group['category']} has a label",
              bool(group["label"].strip()), True)
        for rule in group["rules"]:
            check(f"{rule['code']} has a message", bool(rule["message"].strip()),
                  True)
            check(f"{rule['code']} has a suggestion",
                  bool(rule["suggestion"].strip()), True)


# ================================================================== identifiers


def test_phi_detection() -> None:
    text = ("Mrs. Delacroix, MRN 8842301, DOB 04/12/1958, on (555) 867-5309, "
            "j.d@example.com, 42 Maple Street, SSN 123-45-6789.")
    found = {flag.code for flag in phi.scan(text)}
    for code in ("phi_honorific_name", "phi_mrn", "phi_dob", "phi_phone",
                 "phi_email", "phi_address", "phi_ssn"):
        check(f"{code} detected", code in found, True)

    cleaned, count = phi.redact(text)
    check("seven identifiers redacted", count, 7)
    for leak in ("Delacroix", "8842301", "867-5309", "example.com", "Maple",
                 "123-45-6789"):
        absent("redacted text has no identifier", cleaned, leak)
    contains("sentence punctuation survives redaction", cleaned, "removed].")


def test_phi_does_not_fire_on_clinical_text() -> None:
    """The false positives that would make the scanner get switched off."""
    for phrase in ("Lactate 2.4, WBC 14.2, gave 500 mL LR at 1420. HR 118.",
                   "Pump serial checked and settings verified.",
                   "Ambulated 40 feet at 1430 with a front-wheel walker.",
                   "Foley inserted 3 days ago; indication strict output "
                   "monitoring.",
                   "Braden 14, Morse 45, GCS 15."):
        found = [f.code for f in phi.scan(phrase)]
        check(f"{phrase[:40]!r} is clean", found, [])

    # But a real serial number is caught.
    check("a real serial is caught",
          any(f.code == "phi_device_serial"
              for f in phi.scan("Pacemaker serial AB12345X documented.")), True)


def test_phi_summary_is_honest() -> None:
    """The scanner must state its own limits.

    A privacy feature that implied completeness would be the most dangerous kind of
    false assurance in this module.
    """
    contains("summary admits it does not detect names", phi.SUMMARY,
             "does not try to detect names")
    contains("summary explains why", phi.SUMMARY, "dismissed within a shift")
    contains("summary points at the structural protection", phi.SUMMARY,
             "no field in this tool")


# ================================================================ the composer


def test_composed_note_order() -> None:
    """Observation before impression — the order is what makes a note read as an
    assessment rather than a conclusion looking for support."""
    encounter = Encounter(encounter_id="e", local_label="Bed 1")
    entry = Entry(kind=EntryKind.SHIFT_ASSESSMENT)
    entry.subjective = 'Patient stated, "My chest is tight."'
    entry.vitals = Vitals(systolic=118, diastolic=72, heart_rate=84,
                          taken_at=iso(now_utc()))
    entry.assessment = "Stable, no new findings this shift."
    entry.plan = "Continue current plan."
    entry.stamp()

    text = narrative.compose(entry, encounter)
    for marker in ("S — Subjective", "B/O — Background and objective",
                   "A — Assessment", "R/P — Response and plan"):
        contains(f"{marker} present", text, marker)
    check("subjective precedes objective",
          text.index("S — Subjective") < text.index("B/O —"), True)
    check("objective precedes assessment",
          text.index("B/O —") < text.index("A — Assessment"), True)
    check("assessment precedes plan",
          text.index("A — Assessment") < text.index("R/P —"), True)


def test_empty_sections_are_omitted() -> None:
    encounter = Encounter(encounter_id="e", local_label="Bed 1")
    entry = Entry(kind=EntryKind.FOCUSED_UPDATE)
    entry.assessment = "No change."
    entry.stamp()
    text = narrative.compose(entry, encounter)
    contains("assessment kept", text, "A — Assessment")
    absent("empty subjective omitted", text, "S — Subjective")
    absent("empty plan omitted", text, "R/P —")


def test_late_entry_prefix() -> None:
    from datetime import timedelta
    encounter = Encounter(encounter_id="e", local_label="Bed 1")
    now = now_utc()
    entry = Entry(kind=EntryKind.EVENT_NOTE,
                  event_at=iso(now - timedelta(minutes=95)))
    entry.assessment = "Recalled later."
    entry.stamp(now)
    check("flagged late", entry.late_entry, True)
    check("gap recorded", entry.late_by_minutes, 95)
    text = narrative.compose(entry, encounter)
    contains("prefix present", text, "[LATE ENTRY]")
    contains("prefix states both times", text, "95 minutes later")
    contains("title carries the tag", entry.title(), "[LATE ENTRY]")


def test_medication_sentence_shapes() -> None:
    given = narrative.medication_sentence(Medication(
        name="Morphine", dose="2 mg", route="IV", site="right forearm",
        given_at=iso(now_utc()), indication="pain rated 7 of 10",
        two_identifiers_verified=True, high_alert=True,
        second_nurse_verified=True, second_nurse_initials="JP",
        wasted_amount="2 mg", waste_witness_initials="JP"))
    for fragment in ("administered Morphine 2 mg IV", "to the right forearm",
                     "for pain rated 7 of 10", "Two patient identifiers verified",
                     "Independent double check completed with JP",
                     "wasted, witnessed by JP"):
        contains(f"given sentence has {fragment!r}", given, fragment)

    held = narrative.medication_sentence(Medication(
        name="Metoprolol", scheduled_at=iso(now_utc()), held=True,
        hold_reason="heart rate 48", provider_notified_of_hold=True))
    contains("held sentence", held, "Metoprolol held")
    contains("held reason", held, "heart rate 48")
    contains("held notification", held, "Prescriber notified")
    absent("held is not phrased as administered", held, "administered")

    declined = narrative.medication_sentence(Medication(
        name="Warfarin", given_at=iso(now_utc()), refused=True))
    contains("declined not refused", declined, "Patient declined")
    absent("declined avoids the word refused", declined, "refused")


def test_notification_method_phrases() -> None:
    """"Notified Dr. Alvarez by paged" is the kind of sentence that makes a whole
    note look machine-generated."""
    for method, expected in (("paged", "by page"), ("phone", "by telephone"),
                             ("secure text", "by secure message"),
                             ("in person", "in person"),
                             ("bedside", "at the bedside")):
        text = ProviderNotification(
            notified_at=iso(now_utc()), provider_name="Dr. Alvarez",
            method=method, reason="a systolic of 84").narrative()
        contains(f"{method} renders as {expected}", text, expected)
        absent(f"{method} is not rendered raw", text, f"by {method} regarding")

    unknown = ProviderNotification(
        notified_at=iso(now_utc()), provider_name="Dr. Alvarez",
        method="carrier pigeon", reason="x").narrative()
    contains("an unknown method still renders", unknown, "by carrier pigeon")

    escalated = ProviderNotification(
        notified_at=iso(now_utc()), provider_name="Dr. Chen", method="paged",
        reason="new confusion", no_response=True, escalated_to="charge nurse",
        escalated_at=iso(now_utc())).narrative()
    contains("no response recorded", escalated, "No response received")
    contains("escalation recorded", escalated, "escalated to charge nurse")
    contains("closes with monitoring", escalated, "Continued to monitor")


# ==================================================================== macros


def test_macro_punctuation() -> None:
    """A quoted sentence carries one terminal period, inside the closing mark."""
    text = narrative.render_macro("refusal", {
        "time": "0900", "what": "the scheduled metoprolol",
        "capacity": "oriented to person, place, time and situation",
        "risks_explained": "rebound hypertension and tachycardia",
        "patient_quote": "I am not taking that until my cardiologist calls back",
        "provider_notified": "Dr. Osei at 0915",
    })
    contains("quote punctuated inside", text, 'calls back."')
    absent("no double period after the quote", text, '.".')
    absent("no stray quote-period-period", text, '".')
    contains("attending phrasing reads naturally", text,
             "Attending notified: Dr. Osei at 0915")
    contains("the offer is left open", text, "remains open")


def test_macro_required_fields() -> None:
    missing = narrative.missing_macro_fields("refusal", {})
    check("all six refusal pillars reported missing", len(missing), 6)
    for label in ("Capacity assessment", "Risks explained",
                  "Patient's own words",
                  "Attending notified — name and time"):
        check(f"{label} listed", label in missing, True)

    filled = narrative.missing_macro_fields("refusal", {
        "time": "0900", "what": "x", "capacity": "x", "risks_explained": "x",
        "patient_quote": "x", "provider_notified": "x",
    })
    check("nothing missing when filled", filled, [])


def test_fall_macro_shape() -> None:
    text = narrative.render_macro("fall", {
        "time": "0342", "witnessed": "unwitnessed — patient found",
        "found_how": "Found sitting on the floor at the right side of the bed",
        "patient_account": "My legs gave out",
        "precautions_in_place": "bed low, call light within reach, alarm on",
        "head_strike": "cannot be excluded — unwitnessed",
        "anticoagulated": "yes — apixaban",
        "neuro_checks": "0345 GCS 15; 0400 GCS 15",
        "provider_notified": "Dr. Fenner at 0348",
    })
    contains("opens with the fall and its time", text, "Fall at 0342")
    contains("witnessed status is explicit", text, "Witnessed status:")
    contains("quote punctuated", text, 'gave out."')
    contains("precautions before the fall are recorded", text,
             "Fall precautions in place at the time")
    contains("anticoagulation recorded", text, "Anticoagulation")
    contains("neuro checks recorded", text, "Neurological checks")
    contains("provider phrasing", text, "Provider notified:")


def test_all_macros_render_from_empty() -> None:
    """No macro may raise on an empty form — a half-filled template still has to
    produce something the nurse can read and finish."""
    for macro in narrative.MACROS:
        text = narrative.render_macro(macro.macro_id, {})
        check(f"{macro.macro_id} renders from empty", bool(text.strip()), True)
        check(f"{macro.macro_id} has no None leaking", "None" in text, False)


# ================================================================== systems


def test_wdl_prints_its_definition() -> None:
    """"Neuro WDL" alone is worth nothing in a deposition."""
    finding = systems.build_finding("neuro", within_defined_limits=True)
    text = systems.narrate(finding)
    contains("WDL stated", text, "within defined limits")
    contains("the definition is printed verbatim", text,
             "Alert and oriented to person, place, time and situation")

    with_exception = systems.build_finding(
        "respiratory", within_defined_limits=True,
        findings={"breath_sounds": "Crackles at the bases"})
    text = systems.narrate(with_exception)
    contains("renders as an exception", text, "within defined limits except")
    contains("names the finding", text, "crackles at the bases")
    contains("still prints the definition", text, "Defined limits for this system")


def test_not_assessed_is_a_state() -> None:
    """A blank system and a skipped system must not look identical."""
    finding = systems.build_finding(
        "gastrointestinal", not_assessed=True,
        not_assessed_reason="patient off the unit for imaging")
    text = systems.narrate(finding)
    contains("states not assessed", text, "not assessed this shift")
    contains("carries the reason", text, "off the unit for imaging")
    contains("explains itself", text, "rather than left blank")

    unassessed = systems.unassessed([finding])
    check("the other seven are reported unassessed", len(unassessed), 7)
    check("the declared one is not in the list",
          "Gastrointestinal" in unassessed, False)


def test_prompt_tails_are_stripped() -> None:
    """Option labels carry instructions to the nurse, not text for the note."""
    finding = systems.build_finding(
        "respiratory", findings={"oxygen": "Nasal cannula — specify L/min"})
    text = systems.narrate(finding)
    contains("the clinical content survives", text, "nasal cannula")
    absent("the instruction does not reach the note", text, "specify")
    check("and it is reported as detail still owed",
          systems.needs_detail(finding), ["Oxygen delivery: specify L/min"])

    # A free-text note on the same system satisfies the request.
    satisfied = systems.build_finding(
        "respiratory", findings={"oxygen": "Nasal cannula — specify L/min",
                                 "resp_notes": "Nasal cannula at 3 L/min."})
    check("detail supplied clears it", systems.needs_detail(satisfied), [])

    # Every option in every system must survive the cleaner with content left.
    for system in systems.SYSTEMS:
        for element in system.elements:
            for option in element.options:
                cleaned = systems._clean_option(option)
                check(f"{system.system_id}.{element.element_id} option survives "
                      f"cleaning", bool(cleaned.strip()), True)


def test_rubber_stamp_detection() -> None:
    findings = [systems.build_finding(s.system_id, within_defined_limits=True)
                for s in systems.SYSTEMS]
    check("all eight flagged as bare WDL",
          len(systems.wdl_without_detail(findings)), 8)

    detailed = systems.build_finding(
        "neuro", within_defined_limits=True,
        findings={"neuro_notes": "Baseline expressive aphasia unchanged."})
    check("a system with detail is not counted",
          systems.wdl_without_detail([detailed]), [])


def main() -> int:
    for name, function in sorted(globals().items()):
        if name.startswith("test_") and callable(function):
            function()
    print(f"tests/test_charting_language.py: {CHECKS} checks, "
          f"{len(FAILURES)} failures")
    for failure in FAILURES:
        print(f"  ✗ {failure}")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    raise SystemExit(main())
