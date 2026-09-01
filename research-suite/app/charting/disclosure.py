"""
What this module is, what it is not, and the two things it must say every time.

The request was for a charting tab that leaves a nurse "100% covered in case a
patient takes any sort of legal action". Everything else in this package is built
toward that. This file exists because two parts of that goal cannot be delivered
by writing more features, and a tool that quietly implied otherwise would put a
nurse in *more* jeopardy, not less.

## 1. This is not the legal medical record

The legal medical record is the hospital's EHR — Epic, Cerner, Meditech,
whatever the unit runs. That is the document produced in discovery, read to a
jury, and audited by a surveyor. This module produces **text you compose and
then transcribe into that record**.

That distinction is not a disclaimer to scroll past; it changes how the tool has
to behave, in ways you can see in the code:

* **A second record that disagrees with the chart is a weapon for the other
  side.** Plaintiff's counsel subpoenas the nurse's own notes, finds a timestamp
  or a vital sign that differs from the EHR by ten minutes, and spends an
  afternoon on it. So this module tracks whether each note has been transcribed
  (`Entry.transcribed_at`), warns while any note is untranscribed, and prints
  the untranscribed ones first in the export. An unfiled note is treated as an
  open problem, not a saved one.
* **It cannot be the contemporaneous record for timing purposes.** Where timing
  is itself the standard of care — sepsis bundles, stroke windows, restraint
  checks, blood administration — the EHR timestamps govern. This module records
  event time separately from documentation time (see `models.Entry`) so a late
  entry is labelled rather than disguised, but the label describes *this*
  document's history, not the chart's.
* **Do not use it as a workaround for a chart you cannot get into.** If the EHR
  is down, the unit has a downtime procedure and downtime paper forms; those are
  the legal record during a downtime, and this is not one of them.

Where it does help, and this is not a small thing: it gives you somewhere to
compose a hard note carefully — an escalation, a refusal of care, a fall, a
restraint episode — with the objective-language check and the completeness
interlocks in front of you, before you commit the words to a record you cannot
take back.

## 2. It is built to hold no protected health information

Almost every hospital's acceptable-use policy prohibits PHI on a personal
device. The nurse, not the hospital, absorbs a HIPAA finding for a personal
phone or laptop holding patient identifiers. And a Notice of Privacy Practices
violation is a far more likely adverse event for a working nurse than a
malpractice suit.

So the data model has **no field for a patient name, medical record number or
date of birth** — not an optional one, not a discouraged one. An encounter is
identified by a bed or room label you choose (`Encounter.local_label`) and an
optional set of initials. `phi.py` scans free text for the patterns that leak
anyway — MRN-shaped digit runs, dates of birth, phone numbers, Social Security
numbers, addresses, "Mr./Mrs. Surname" constructions — and flags them before a
save. Purging is one call (`store.purge_all`) and it is offered on every screen.

This is also good documentation practice independent of privacy: a note that
reads "the patient reports…" transcribes into any chart, while a note carrying
the wrong patient's name is a sentinel event.

## What "100% covered" can actually mean

No document guarantees an outcome; a nurse who did the right thing can still be
named in a suit, and a nurse who documented perfectly can still be found to have
breached a standard of care. What good documentation does is much narrower and
much more valuable: it makes the record of your reasoning survive four years and
a hostile reading.

Concretely, the defensible note shows: what you observed, in objective terms;
what you concluded; what you did; **who you told, when, by what means, and what
they said**; and what happened when you looked again. That is the structure the
composer enforces, and every interlock in `interlocks.py` exists because one of
those five is the one that goes missing under pressure.
"""

from __future__ import annotations

NOT_THE_RECORD = (
    "This is not an electronic health record and not the legal medical record. "
    "Your hospital's EHR is. Compose notes here, then transcribe them into the "
    "chart and mark them transcribed — an unfiled note that disagrees with the "
    "chart helps the other side, not you."
)

NO_PHI = (
    "Do not enter patient names, medical record numbers or dates of birth. "
    "There are no fields for them. Most hospitals prohibit protected health "
    "information on a personal device, and a HIPAA finding lands on you rather "
    "than the unit. Identify the encounter by bed or room."
)

NOT_CLINICAL_ADVICE = (
    "Scores are computed from what you enter and shown to you. They do not "
    "direct care, and none of them replaces your assessment or the provider's. "
    "A score that disagrees with what you are looking at is a reason to escalate."
)

LOCAL_ONLY = (
    "Everything here is stored in a plain JSON file on this machine, inside the "
    "application's data directory. Nothing is uploaded, and no part of the "
    "charting tab calls out to the network. Purge it from the Charting tab when "
    "your shift is over."
)


def banner() -> dict[str, str]:
    """The four statements the UI shows above every charting screen."""
    return {
        "not_the_record": NOT_THE_RECORD,
        "no_phi": NO_PHI,
        "not_clinical_advice": NOT_CLINICAL_ADVICE,
        "local_only": LOCAL_ONLY,
    }


# Printed into every exported document, ahead of the notes themselves. Export is
# the moment the text leaves this tool, so it is the moment the statement matters
# most — a file on a shared drive outlives the screen it was composed on.
EXPORT_HEADER = (
    "Nursing documentation draft — not the legal medical record. Composed in a "
    "local note composer for transcription into the electronic health record. "
    "Where this document and the EHR differ, the EHR governs. Times shown as "
    "“documented” are when the text was written in this tool, not when "
    "it was entered in the chart."
)


def what_it_cannot_do() -> list[dict[str, str]]:
    """The honest ledger for this tab, shown on its landing screen.

    The research half of this suite carries the same kind of list. A tool that
    only advertises its features teaches you to trust it in the places it should
    not be trusted.
    """
    return [
        {
            "claim": "Guarantee you are covered if a patient sues",
            "reality": (
                "Nothing can. Documentation does not decide whether a standard "
                "of care was met; it decides whether your reasoning is legible "
                "years later. This tool structures the five things that go "
                "missing under pressure — observation, impression, action, "
                "notification, re-evaluation — and refuses to save a note that "
                "drops the one that matters most."
            ),
        },
        {
            "claim": "Be your chart",
            "reality": (
                "It is a composer. The EHR is the record. Notes here track "
                "whether they have been transcribed, and the tool nags until "
                "they have been."
            ),
        },
        {
            "claim": "Hold your patients' information",
            "reality": (
                "By design it has nowhere to put it. No name, MRN or date of "
                "birth fields exist, and free text is scanned for identifiers "
                "before every save."
            ),
        },
        {
            "claim": "Reproduce the published scoring instruments",
            "reality": (
                "Most of them are copyrighted — Braden, the Morse Fall Scale, "
                "Wong-Baker FACES, CAM-ICU, ESI, APACHE II. The scoring logic "
                "and the published thresholds are implemented and the "
                "instrument is cited, but the item wording is written fresh and "
                "no instrument artwork is reproduced. Use your unit's licensed "
                "copy for the definitions. See scales.LICENSING."
            ),
        },
        {
            "claim": "Tell you what to do clinically",
            "reality": (
                "It computes scores and shows thresholds from the published "
                "instruments. It never converts a score into an order, a "
                "disposition or a triage decision. Those are yours and the "
                "provider's."
            ),
        },
        {
            "claim": "Replace your unit's policy",
            "reality": (
                "Reassessment intervals, critical-value thresholds and "
                "escalation chains are all configurable here because they vary "
                "by unit, and the defaults shipped are common practice rather "
                "than your policy. Set them to match your policy on the "
                "Charting settings screen."
            ),
        },
    ]
