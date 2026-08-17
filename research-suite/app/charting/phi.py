"""
Protected health information detection.

The data model has no fields for identifiers (see `disclosure.NO_PHI`), but free
text does not care about the data model. A nurse composing a note at speed will
type "Mrs. Delacroix in 412 with MRN 8842301" without thinking about it, because
that is how people talk about their patients.

So every free-text field is scanned before every save, and the scan is a **warning
with a one-click redaction**, not a block. Blocking here would be wrong: a nurse
whose note is refused at 0300 will not carefully de-identify it, they will
disable the feature or stop using the tool. A warning that offers to fix the text
for them gets the identifier out of the file, which is the actual goal.

## What it looks for, and what it deliberately does not

It looks for the patterns that are unambiguous or nearly so: medical record
numbers, Social Security numbers, phone numbers, email addresses, dates written as
dates, addresses, and honorific-plus-surname constructions.

It does **not** attempt to detect names in general. A name detector without a model
is either a list of common given names — which flags "Grace" in "gait steady with
grace" and misses every surname that is not on the list — or it is a capitalisation
heuristic, which flags every drug name, every unit, and the start of every
sentence. Both make the feature noise, and a noisy privacy warning is a privacy
warning that gets dismissed. What is caught instead is the *construction* names
appear in: an honorific, a "patient's name is", a signature line.

The honest summary, which `SUMMARY` states in the UI: this catches the common
accidents. It is not a guarantee, and the guarantee comes from the design — there
is nowhere in the schema for an identifier to live, and the purge button is on
every screen.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .models import Flag, Severity

SUMMARY = (
    "Free text is scanned for the identifier patterns that leak by accident — "
    "record numbers, Social Security numbers, phone numbers, email addresses, "
    "written dates, street addresses, and titles followed by a surname. It does "
    "not try to detect names in general, because a detector that flagged every "
    "capitalised word would be dismissed within a shift and would then catch "
    "nothing at all. The real protection is structural: there is no field in this "
    "tool for a name, a record number or a date of birth, and Purge removes "
    "everything in one action."
)


@dataclass
class Detector:
    code: str
    pattern: str
    label: str
    advice: str
    redaction: str
    flags: int = re.IGNORECASE


DETECTORS: list[Detector] = [
    Detector(
        code="phi_mrn",
        pattern=r"\b(?:mrn|mr#|medical\s+record\s*(?:number|#)?|"
                r"account\s*(?:number|#)|chart\s*#)\s*[:#]?\s*([A-Z]?\d[\d-]{4,})",
        label="a medical record or account number",
        advice="Remove it. This tool identifies the encounter by bed or room, and "
               "a record number is the single most direct identifier there is.",
        redaction="[identifier removed]",
    ),
    Detector(
        code="phi_bare_long_number",
        pattern=r"(?<![\d.\-/:])\d{7,12}(?![\d.\-/])",
        label="a long bare number that may be an identifier",
        advice="If it is a record number, remove it. If it is a lab value, a pump "
               "serial or a phone extension, leave it — this detector cannot tell, "
               "which is why it warns rather than blocks.",
        redaction="[number removed]",
    ),
    Detector(
        code="phi_ssn",
        pattern=r"\b\d{3}-\d{2}-\d{4}\b",
        label="a Social Security number",
        advice="Remove it. A Social Security number has no clinical use and its "
               "presence turns an ordinary privacy lapse into an identity-theft "
               "exposure.",
        redaction="[SSN removed]",
    ),
    Detector(
        code="phi_phone",
        pattern=r"(?<![\d-])(?:\+?1[\s.-]?)?(?:\(\d{3}\)|\d{3})[\s.-]\d{3}[\s.-]\d{4}(?![\d-])",
        label="a telephone number",
        advice="Remove it. If you need to record that a family member was called, "
               "write \"spouse contacted by telephone at 1420\" — the fact of the "
               "call is clinical, the number is not.",
        redaction="[phone removed]",
    ),
    Detector(
        code="phi_email",
        pattern=r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
        label="an email address",
        advice="Remove it.",
        redaction="[email removed]",
    ),
    Detector(
        code="phi_date",
        pattern=r"\b(?:0?[1-9]|1[0-2])[/-](?:0?[1-9]|[12]\d|3[01])[/-](?:19|20)?\d{2}\b",
        label="a written date, which may be a date of birth",
        advice="Dates of birth are identifiers. If you need to express timing, use "
               "an interval — \"three days after admission\", \"on hospital day "
               "four\" — which is also more useful clinically than a calendar "
               "date.",
        redaction="[date removed]",
    ),
    Detector(
        code="phi_dob",
        # `[\w/.-]*` rather than `\S*` so the match stops at the sentence's comma
        # instead of swallowing it into the redaction.
        pattern=r"\b(?:dob|date\s+of\s+birth|born\s+on|birth\s*date)\b\s*[:]?\s*[\w/.-]*",
        label="a date of birth",
        advice="Remove it. Use an age band instead — the encounter has a field for "
               "one.",
        redaction="[date of birth removed]",
    ),
    Detector(
        code="phi_address",
        # Case-sensitive on the street name — it has to be capitalised to be a
        # name — but case-insensitive on the suffix, which people write both ways.
        pattern=r"\b\d{1,5}\s+(?:[A-Z][a-z]+\s){1,3}"
                r"(?i:street|st|avenue|ave|road|rd|drive|dr|lane|ln|boulevard|blvd|"
                r"court|ct|place|pl|way|circle|cir|terrace|ter)\b",
        label="a street address",
        advice="Remove it. Where a living situation is clinically relevant, "
               "describe it — \"lives alone on a second floor with no lift\" — "
               "rather than locating it.",
        redaction="[address removed]",
        flags=0,
    ),
    Detector(
        code="phi_honorific_name",
        pattern=r"\b(?:Mr|Mrs|Ms|Miss|Mx)\.?\s+[A-Z][a-zA-Z\-']{2,}",
        label="a title followed by a surname",
        advice="Write \"the patient\". This is the most common way a name reaches "
               "a note, and it is also the way a name reaches the *wrong* note — "
               "which is a far worse problem than the privacy one.",
        redaction="the patient",
        flags=0,
    ),
    Detector(
        code="phi_named_patient",
        pattern=r"\b(?:patient(?:'s)?|resident(?:'s)?)\s+name\s*(?:is|:)\s*\S+"
                r"(?:\s+\S+)?",
        label="a patient's name",
        advice="Remove it.",
        redaction="[name removed]",
    ),
    Detector(
        code="phi_insurance",
        pattern=r"\b(?:policy|member|subscriber|insurance|medicare|medicaid)\s*"
                r"(?:number|#|id)\s*[:#]?\s*[A-Z0-9-]{5,}",
        label="an insurance or beneficiary identifier",
        advice="Remove it. It has no clinical use in a nursing note.",
        redaction="[identifier removed]",
    ),
    Detector(
        code="phi_device_serial",
        # Case-sensitive on the identifier itself: a serial number is upper-case
        # and digits. Under IGNORECASE, `[A-Z0-9-]{6,}` also matches lower-case
        # words, so "Pump serial checked" was being reported as a device identifier.
        pattern=r"(?i:serial|device\s*id|implant)\s*(?i:number|#|no\.?)?\s*[:#]?\s*"
                r"(?=[A-Z0-9-]*\d)[A-Z0-9-]{6,}",
        label="a device serial or implant identifier",
        advice="A device identifier is an identifier under the privacy rule. Record "
               "the device type and the date it was placed instead.",
        redaction="[device identifier removed]",
        flags=0,
    ),
]


def scan(text: str, *, field_path: str = "") -> list[Flag]:
    """Flag identifier patterns, with an offer to redact each one."""
    if not text or not text.strip():
        return []
    found: list[Flag] = []
    for detector in DETECTORS:
        for match in re.finditer(detector.pattern, text, detector.flags):
            found.append(Flag(
                code=detector.code,
                severity=Severity.WARN,
                message=f"This looks like {detector.label}.",
                field_path=field_path,
                excerpt=match.group(0),
                suggestion=detector.advice,
                offset=match.start(),
                length=match.end() - match.start(),
            ))
    # Overlapping detectors are common — a phone number is also a long bare number
    # — so keep the longest match at each starting position and drop the rest.
    found.sort(key=lambda f: (f.offset, -f.length))
    kept: list[Flag] = []
    for flag in found:
        if any(k.offset <= flag.offset
               and flag.offset + flag.length <= k.offset + k.length
               for k in kept):
            continue
        kept.append(flag)
    return kept


def scan_many(fields: dict[str, str]) -> list[Flag]:
    flags: list[Flag] = []
    for name, value in fields.items():
        flags.extend(scan(value or "", field_path=name))
    return flags


def redact(text: str) -> tuple[str, int]:
    """Replace every detected identifier with its placeholder.

    Returns the cleaned text and a count. Applied right-to-left so earlier offsets
    stay valid as the string shrinks — the same reason `writing/proof.py` pads its
    protected spans to equal length, arrived at from the opposite direction.
    """
    if not text:
        return text, 0
    replacements: list[tuple[int, int, str]] = []
    for detector in DETECTORS:
        for match in re.finditer(detector.pattern, text, detector.flags):
            replacements.append((match.start(), match.end(), detector.redaction))
    replacements.sort(key=lambda r: (r[0], -(r[1] - r[0])))
    filtered: list[tuple[int, int, str]] = []
    for start, end, placeholder in replacements:
        if any(s <= start and end <= e for s, e, _ in filtered):
            continue
        filtered.append((start, end, placeholder))
    result = text
    for start, end, placeholder in sorted(filtered, key=lambda r: -r[0]):
        result = result[:start] + placeholder + result[end:]
    return result, len(filtered)


def report() -> dict[str, Any]:
    """What the settings screen shows about this scanner."""
    return {
        "summary": SUMMARY,
        "detectors": [
            {"code": d.code, "label": d.label, "advice": d.advice}
            for d in DETECTORS
        ],
    }
