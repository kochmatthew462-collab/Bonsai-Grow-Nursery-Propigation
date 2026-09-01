"""
The evidence matrix as an Excel workbook, written without a spreadsheet library.

## Why the matrix belongs in a spreadsheet

The extraction matrix is the one artefact in this suite that is genuinely tabular
and genuinely worked *on* rather than read: you sort it by level of evidence, you
filter to the randomised trials, you paste a column into a meta-analysis, you send
it to a supervisor who wants to add a column. A Word table does none of that. It
was the obvious answer to "use multiple Microsoft products" and it was the piece
that was missing — the matrix existed only as a table inside the audit document.

## Why there is no dependency

`.xlsx` is a ZIP of XML parts, and the subset needed for a formatted data sheet is
small enough to write directly — the same judgement `apa/ooxml.py` makes about
Word. Adding `openpyxl` to get a header row and a frozen pane would be a
150-file dependency for about eighty lines of XML.

Three things this writes that make the sheet usable rather than merely valid:

* **A frozen header row and an auto-filter**, so the matrix behaves like a
  filterable table the moment it opens.
* **Real numbers as numbers.** A sample size written as a string sorts
  lexicographically — 9 after 1,204 — which is exactly the sort you reach for
  first. `_cell` types each value.
* **Column widths from the content**, because the default width truncates every
  author-and-year cell and the first thing a reader does otherwise is drag
  eighteen column borders.

Inline strings are used rather than a shared-string table: the table saves space
on repetitive data, and an evidence matrix is not repetitive.
"""

from __future__ import annotations

import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

# The parts a minimal but well-formed workbook needs. Anything omitted here is
# something Excel supplies a default for.
_CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
{sheet_overrides}
<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>"""

_ROOT_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>"""

# Style 0 is the default, 1 is the bold header, 2 wraps text at the top of the
# cell — which is what makes a key-findings column readable instead of a single
# clipped line.
_STYLES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<fonts count="2">
<font><sz val="11"/><name val="Calibri"/></font>
<font><b/><sz val="11"/><name val="Calibri"/></font>
</fonts>
<fills count="3">
<fill><patternFill patternType="none"/></fill>
<fill><patternFill patternType="gray125"/></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FFF2F1EE"/><bgColor indexed="64"/></patternFill></fill>
</fills>
<borders count="2">
<border><left/><right/><top/><bottom/><diagonal/></border>
<border><left/><right/><top/><bottom style="thin"><color rgb="FF333333"/></bottom><diagonal/></border>
</borders>
<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
<cellXfs count="3">
<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
<xf numFmtId="0" fontId="1" fillId="2" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf>
<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf>
</cellXfs>
</styleSheet>"""


def _column_name(index: int) -> str:
    """1 → A, 26 → Z, 27 → AA."""
    name = ""
    while index > 0:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


def _is_number(value: Any) -> bool:
    """Whether a value should be written as a number.

    Booleans are excluded deliberately: `True` is an int in Python and writing it
    as 1 in a spreadsheet loses the only thing it was saying.
    """
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return True
    if isinstance(value, str):
        candidate = value.strip().replace(",", "")
        if not candidate:
            return False
        try:
            float(candidate)
            return True
        except ValueError:
            return False
    return False


def _cell(reference: str, value: Any, style: int) -> str:
    if value is None or value == "":
        return f'<c r="{reference}" s="{style}"/>'
    if _is_number(value):
        number = str(value).replace(",", "") if isinstance(value, str) else value
        return f'<c r="{reference}" s="{style}"><v>{number}</v></c>'
    text = escape(str(value)).replace("\n", "&#10;")
    return (f'<c r="{reference}" s="{style}" t="inlineStr">'
            f"<is><t xml:space=\"preserve\">{text}</t></is></c>")


def _sheet_xml(headers: list[str], rows: list[list[Any]],
               widths: list[float]) -> str:
    columns = "".join(
        f'<col min="{index}" max="{index}" width="{width:.1f}" customWidth="1"/>'
        for index, width in enumerate(widths, 1))

    body = [
        "<row r=\"1\">" + "".join(
            _cell(f"{_column_name(index)}1", header, 1)
            for index, header in enumerate(headers, 1)) + "</row>"
    ]
    for row_index, row in enumerate(rows, 2):
        cells = "".join(
            _cell(f"{_column_name(index)}{row_index}", value, 2)
            for index, value in enumerate(row, 1))
        body.append(f'<row r="{row_index}">{cells}</row>')

    last = f"{_column_name(max(1, len(headers)))}{len(rows) + 1}"
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<sheetViews><sheetView workbookViewId="0" tabSelected="1">
<pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>
</sheetView></sheetViews>
<sheetFormatPr defaultRowHeight="15"/>
<cols>{columns}</cols>
<sheetData>{"".join(body)}</sheetData>
<autoFilter ref="A1:{last}"/>
</worksheet>"""


def _widths(headers: list[str], rows: list[list[Any]]) -> list[float]:
    """Column widths from the widest cell, clamped.

    Clamped at both ends: a narrow column truncates its header, and an unclamped
    wide one turns a key-findings paragraph into a single column three screens
    across. The wrap style handles the overflow instead.
    """
    widths: list[float] = []
    for index in range(len(headers)):
        longest = len(str(headers[index]))
        for row in rows:
            if index < len(row):
                cell = str(row[index] or "")
                longest = max(longest, min(len(cell), 60))
        widths.append(max(10.0, min(48.0, longest + 2)))
    return widths


def write(path: Path, sheets: list[dict[str, Any]], *,
          title: str = "Evidence matrix") -> Path:
    """Write a workbook. Each sheet is {name, headers, rows}."""
    if not sheets:
        raise ValueError("a workbook needs at least one sheet")

    path.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    sheet_overrides = "\n".join(
        f'<Override PartName="/xl/worksheets/sheet{index}.xml" '
        f'ContentType="application/vnd.openxmlformats-officedocument.'
        f'spreadsheetml.worksheet+xml"/>'
        for index in range(1, len(sheets) + 1))

    sheet_entries = "".join(
        f'<sheet name="{escape(_safe_name(sheet.get("name") or f"Sheet{index}"))}" '
        f'sheetId="{index}" r:id="rId{index}"/>'
        for index, sheet in enumerate(sheets, 1))
    workbook = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<sheets>{sheet_entries}</sheets></workbook>"""

    relationships = "".join(
        f'<Relationship Id="rId{index}" Type="http://schemas.openxmlformats.org/'
        f'officeDocument/2006/relationships/worksheet" '
        f'Target="worksheets/sheet{index}.xml"/>'
        for index in range(1, len(sheets) + 1))
    style_id = len(sheets) + 1
    workbook_rels = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
{relationships}
<Relationship Id="rId{style_id}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>"""

    core = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
 xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/"
 xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<dc:title>{escape(title)}</dc:title>
<dcterms:created xsi:type="dcterms:W3CDTF">{stamp}</dcterms:created>
<dcterms:modified xsi:type="dcterms:W3CDTF">{stamp}</dcterms:modified>
</cp:coreProperties>"""

    app_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties">
<Application>Koch Research Suite</Application></Properties>"""

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml",
                         _CONTENT_TYPES.format(sheet_overrides=sheet_overrides))
        archive.writestr("_rels/.rels", _ROOT_RELS)
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        archive.writestr("xl/styles.xml", _STYLES)
        archive.writestr("docProps/core.xml", core)
        archive.writestr("docProps/app.xml", app_xml)
        for index, sheet in enumerate(sheets, 1):
            headers = [str(h) for h in (sheet.get("headers") or [])]
            rows = [list(r) for r in (sheet.get("rows") or [])]
            archive.writestr(f"xl/worksheets/sheet{index}.xml",
                             _sheet_xml(headers, rows, _widths(headers, rows)))
    return path


def _safe_name(name: str) -> str:
    """A sheet name Excel will accept: 31 characters, none of []:*?/\\."""
    cleaned = "".join(c for c in str(name) if c not in "[]:*?/\\")
    return (cleaned.strip() or "Sheet")[:31]


# ------------------------------------------------------------- the matrix sheet


MATRIX_HEADERS = [
    "Author and year", "Title", "Journal", "Design / methodology",
    "Setting", "Sample", "Sample size", "Key findings", "Strengths",
    "Limitations", "Level of evidence", "Appraisal", "DOI", "Source database",
]


def evidence_matrix(project) -> list[dict[str, Any]]:
    """Build the workbook's sheets from a project.

    Two sheets rather than one: the matrix people work on, and a provenance sheet
    recording where every record came from and what was done to it. The second is
    the same information the audit document carries in prose, in the form a
    supervisor asking "where did this come from" can sort.
    """
    from ..evidence import levels as levels_module

    works = list(project.cited_works() or project.included_works())
    extractions = {e.work_key: e for e in (getattr(project, "extractions", None)
                                           or [])}
    appraisals = {a.work_key: a for a in (getattr(project, "appraisals", None)
                                          or [])}

    rows: list[list[Any]] = []
    for work in works:
        extraction = extractions.get(work.key)
        appraisal = appraisals.get(work.key)
        level = getattr(work, "evidence_level", None)
        sample_size = getattr(extraction, "sample_size", "") if extraction else ""
        rows.append([
            _author_year(work),
            getattr(work, "title", ""),
            getattr(work, "container", "") or getattr(work, "journal", ""),
            getattr(extraction, "design", "") if extraction else "",
            getattr(extraction, "setting", "") if extraction else "",
            getattr(extraction, "sample", "") if extraction else "",
            sample_size,
            getattr(extraction, "findings", "") if extraction else "",
            getattr(extraction, "strengths", "") if extraction else "",
            getattr(extraction, "limitations", "") if extraction else "",
            getattr(level, "label", "") if level else "",
            _appraisal_summary(appraisal),
            getattr(work, "doi", ""),
            getattr(work, "source_db", ""),
        ])

    provenance = [
        [
            _author_year(work),
            getattr(work, "source_db", ""),
            getattr(work, "retrieved_at", ""),
            "yes" if getattr(work, "retracted", False) else "no",
            "excluded" if getattr(work, "included", None) is False else "included",
            getattr(work, "screening_note", "") or "",
            getattr(work, "url", "") or (
                f"https://doi.org/{work.doi}" if getattr(work, "doi", "") else ""),
        ]
        for work in (getattr(project, "works", None) or [])
    ]

    return [
        {"name": "Evidence matrix", "headers": MATRIX_HEADERS, "rows": rows},
        {"name": "Provenance",
         "headers": ["Author and year", "Source", "Retrieved", "Retracted",
                     "Screening decision", "Screening note", "Link"],
         "rows": provenance},
    ]


def _author_year(work) -> str:
    authors = getattr(work, "authors", None) or []
    year = getattr(work, "year", "") or "n.d."
    if not authors:
        return f"[no author] ({year})"
    first = authors[0]
    name = getattr(first, "family", "") or getattr(first, "given", "")
    if len(authors) == 1:
        return f"{name} ({year})"
    if len(authors) == 2:
        second = getattr(authors[1], "family", "")
        return f"{name} & {second} ({year})"
    return f"{name} et al. ({year})"


def _appraisal_summary(appraisal) -> str:
    if not appraisal:
        return "not appraised"
    instrument = getattr(appraisal, "instrument", "") or "instrument not recorded"
    confidence = getattr(appraisal, "overall", "") or "not rated"
    return f"{instrument}: {confidence}"


def write_matrix(project, path: Path) -> Path:
    return write(path, evidence_matrix(project),
                 title=f"Evidence matrix — {getattr(project, 'topic', '')}")
