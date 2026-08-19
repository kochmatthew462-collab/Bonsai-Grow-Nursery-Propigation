"""
Citation-file importers: RIS, NBIB/MEDLINE, BibTeX, EndNote XML, CSV.

**This module is what makes the subscription databases usable.** CINAHL,
PsycINFO, Embase, Scopus, the Cochrane Library, the JBI EBP Database and
Global Health have no API an unaffiliated individual can buy — but every one of
them exports RIS, and PubMed exports NBIB. So the tool's answer to "I need
CINAHL" is not a broken API call: it is *run the search in CINAHL, export the
results, drop the file here*, after which those records flow through
deduplication, level-of-evidence classification, appraisal, the evidence matrix
and the APA reference list exactly like anything retrieved automatically.

Records carry `source_db` set from the file's own database field where one
exists, so the audit document can say a citation came from a CINAHL export
rather than implying the tool retrieved it directly. That distinction is the
difference between a traceable methodology and a misleading one.
"""

from __future__ import annotations

import csv
import io
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

from ..models import Author, Work, WorkType, normalise_doi

# ------------------------------------------------------------- type mapping

# RIS TY codes (Reference Manager / EBSCO / Ovid / Clarivate all use these).
RIS_TYPES = {
    "JOUR": WorkType.JOURNAL_ARTICLE,
    "EJOUR": WorkType.JOURNAL_ARTICLE,
    "BOOK": WorkType.BOOK,
    "EBOOK": WorkType.BOOK,
    "EDBOOK": WorkType.BOOK,
    "CHAP": WorkType.BOOK_CHAPTER,
    "ECHAP": WorkType.BOOK_CHAPTER,
    "RPRT": WorkType.REPORT,
    "GOVDOC": WorkType.REPORT,
    "ELEC": WorkType.WEBPAGE,
    "ICOMM": WorkType.WEBPAGE,
    "WEB": WorkType.WEBPAGE,
    "THES": WorkType.THESIS,
    "CONF": WorkType.CONFERENCE_PAPER,
    "CPAPER": WorkType.CONFERENCE_PAPER,
    "DATA": WorkType.DATASET,
    "STAND": WorkType.GUIDELINE,
    "GEN": WorkType.JOURNAL_ARTICLE,
}

BIBTEX_TYPES = {
    "article": WorkType.JOURNAL_ARTICLE,
    "book": WorkType.BOOK,
    "inbook": WorkType.BOOK_CHAPTER,
    "incollection": WorkType.BOOK_CHAPTER,
    "techreport": WorkType.REPORT,
    "misc": WorkType.WEBPAGE,
    "online": WorkType.WEBPAGE,
    "electronic": WorkType.WEBPAGE,
    "phdthesis": WorkType.THESIS,
    "mastersthesis": WorkType.THESIS,
    "inproceedings": WorkType.CONFERENCE_PAPER,
    "conference": WorkType.CONFERENCE_PAPER,
    "dataset": WorkType.DATASET,
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def detect_format(text: str, filename: str = "") -> str:
    """Identify the citation format from content, falling back to extension.

    Content sniffing comes first because exports are routinely saved with the
    wrong extension — EBSCO's "Export to RIS" often lands as `.txt`, and
    PubMed's NBIB as `.nbib` or `.txt` interchangeably.
    """
    head = text[:4000]
    if re.search(r"^\s*TY\s{2}-", head, re.MULTILINE):
        return "ris"
    if re.search(r"^\s*(PMID|OWN|STAT)\s*-\s", head, re.MULTILINE):
        return "nbib"
    if re.search(r"@\w+\s*\{", head):
        return "bibtex"
    if "<xml>" in head or "<records>" in head or "<record>" in head:
        return "endnote-xml"
    lower = filename.lower()
    for extension, name in (
        (".ris", "ris"), (".nbib", "nbib"), (".bib", "bibtex"),
        (".bibtex", "bibtex"), (".xml", "endnote-xml"), (".enw", "ris"),
        (".csv", "csv"), (".tsv", "csv"), (".txt", "ris"),
    ):
        if lower.endswith(extension):
            return name
    if "," in head.split("\n", 1)[0]:
        return "csv"
    raise ValueError(
        "Could not identify this file as RIS, NBIB, BibTeX, EndNote XML or CSV. "
        "Re-export from the database using one of those formats."
    )


def parse(text: str, filename: str = "", source_hint: str = "") -> list[Work]:
    """Parse any supported citation file into Works."""
    text = text.lstrip("\ufeff")
    kind = detect_format(text, filename)
    parser = {
        "ris": parse_ris,
        "nbib": parse_nbib,
        "bibtex": parse_bibtex,
        "endnote-xml": parse_endnote_xml,
        "csv": parse_csv,
    }[kind]
    works = parser(text)
    for work in works:
        if source_hint and not work.source_db:
            work.source_db = source_hint
        if not work.source_db:
            work.source_db = f"{kind}-import"
        work.retrieved_at = work.retrieved_at or _now()
        work.ensure_key()
    return works


# ---------------------------------------------------------------------- RIS


def parse_ris(text: str) -> list[Work]:
    """RIS, as exported by CINAHL/EBSCO, Ovid, Scopus, Embase and Cochrane.

    Tags repeat (several AU lines, several KW lines) and values can wrap onto
    continuation lines with no tag, so parsing accumulates per tag rather than
    assigning once.
    """
    works: list[Work] = []
    fields: dict[str, list[str]] = {}
    last_tag = ""

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue
        match = re.match(r"^([A-Z][A-Z0-9])\s{2}-\s?(.*)$", line)
        if match:
            tag, value = match.group(1), match.group(2).strip()
            if tag == "ER":
                if fields:
                    works.append(_ris_to_work(fields))
                fields, last_tag = {}, ""
                continue
            fields.setdefault(tag, []).append(value)
            last_tag = tag
        elif last_tag:
            # A continuation line: append to the value already collected.
            fields[last_tag][-1] = (fields[last_tag][-1] + " " + line.strip()).strip()

    if fields:  # a final record with no ER terminator
        works.append(_ris_to_work(fields))
    return works


def _ris_to_work(fields: dict[str, list[str]]) -> Work:
    def one(*tags: str) -> str:
        for tag in tags:
            if fields.get(tag):
                return fields[tag][0].strip()
        return ""

    def many(*tags: str) -> list[str]:
        out: list[str] = []
        for tag in tags:
            out.extend(v.strip() for v in fields.get(tag, []) if v.strip())
        return out

    ty = one("TY").upper()
    work = Work(work_type=RIS_TYPES.get(ty, WorkType.JOURNAL_ARTICLE))

    work.authors = [Author.parse(a) for a in many("AU", "A1")]
    work.editors = [Author.parse(a) for a in many("ED", "A2", "A3")]
    if not work.authors and work.work_type is WorkType.BOOK_CHAPTER:
        work.editors = work.editors or [Author.parse(a) for a in many("A2")]

    work.title = _strip_wrappers(one("TI", "T1"))
    # T2 is the secondary title: the journal for an article, the book for a
    # chapter. JO/JF/J2 are journal-specific and take precedence for articles.
    if work.work_type is WorkType.BOOK_CHAPTER:
        work.container = _strip_wrappers(one("T2", "BT"))
    else:
        work.container = _strip_wrappers(one("JO", "JF", "T2", "J2", "JA"))

    work.year = _year_from(one("PY", "Y1", "DA"))
    work.volume = one("VL")
    work.issue = one("IS", "CP")
    start, end = one("SP"), one("EP")
    work.pages = f"{start}-{end}" if start and end else (start or one("PG"))
    work.publisher = one("PB")
    work.edition = one("ET")
    work.language = one("LA")
    work.abstract = one("AB", "N2")
    work.url = _first_url(many("UR", "L1", "L2"))
    work.isbn = one("SN") if work.work_type in (WorkType.BOOK, WorkType.BOOK_CHAPTER) else ""
    work.report_number = one("M1") if work.work_type is WorkType.REPORT else ""

    doi = one("DO", "DI")
    if not doi:
        # Some exports bury the DOI in a note or URL field.
        for candidate in many("UR", "N1", "L1", "ID"):
            found = re.search(r"10\.\d{4,9}/\S+", candidate)
            if found:
                doi = found.group(0)
                break
    work.doi = normalise_doi(doi) if doi else ""

    work.mesh_terms = many("KW")
    # M3 carries the publication type in EBSCO and Ovid exports; it is the
    # main signal available for level-of-evidence classification on an import.
    work.publication_types = [p for p in many("M3", "TY") if p and p.upper() != ty]
    for note in many("N1", "N2"):
        for phrase in ("randomized controlled trial", "randomised controlled trial",
                       "systematic review", "meta-analysis", "meta analysis",
                       "cohort study", "case-control", "qualitative study",
                       "clinical trial", "practice guideline"):
            if phrase in note.lower():
                work.publication_types.append(phrase)

    accession = one("AN", "ID")
    database = one("DB", "DP")
    if database:
        work.source_db = _normalise_db_name(database)
    if re.fullmatch(r"\d{7,8}", accession) and "pubmed" in database.lower():
        work.pmid = accession

    work.raw = {k: v for k, v in fields.items()}
    if accession:
        work.raw["accession"] = accession
    return work


def _normalise_db_name(name: str) -> str:
    """Map the many spellings of a database name onto one label.

    The audit document names the database each record came from, and
    "CINAHL Complete", "CINAHL Plus with Full Text" and "cinahl" should not
    appear as three different sources in a methodology section.
    """
    lower = name.lower()
    for needle, label in (
        ("cinahl", "CINAHL (export)"),
        ("medline", "MEDLINE (export)"),
        ("pubmed", "PubMed (export)"),
        ("psycinfo", "PsycINFO (export)"),
        ("psycarticles", "PsycARTICLES (export)"),
        ("embase", "Embase (export)"),
        ("cochrane", "Cochrane Library (export)"),
        ("central", "Cochrane CENTRAL (export)"),
        ("scopus", "Scopus (export)"),
        ("web of science", "Web of Science (export)"),
        ("eric", "ERIC (export)"),
        ("global health", "Global Health / CABI (export)"),
        ("jbi", "JBI EBP Database (export)"),
        ("joanna briggs", "JBI EBP Database (export)"),
        ("sciencedirect", "ScienceDirect (export)"),
        ("ovid", "Ovid (export)"),
        ("ebsco", "EBSCOhost (export)"),
        ("proquest", "ProQuest (export)"),
    ):
        if needle in lower:
            return label
    return f"{name.strip()} (export)"


# --------------------------------------------------------------------- NBIB


def parse_nbib(text: str) -> list[Work]:
    """PubMed's MEDLINE/NBIB format.

    Continuation lines are indented by six spaces, and PT (publication type)
    repeats — which is the richest level-of-evidence signal any format carries,
    because PubMed indexers assign it from the article itself.
    """
    works: list[Work] = []
    for chunk in re.split(r"\n\s*\n+", text.strip()):
        if not chunk.strip():
            continue
        fields: dict[str, list[str]] = {}
        last_tag = ""
        for line in chunk.splitlines():
            match = re.match(r"^([A-Z]{2,4})\s*-\s?(.*)$", line)
            if match:
                last_tag = match.group(1)
                fields.setdefault(last_tag, []).append(match.group(2).strip())
            elif last_tag and line.startswith(" "):
                fields[last_tag][-1] = (fields[last_tag][-1] + " " + line.strip()).strip()
        if fields:
            works.append(_nbib_to_work(fields))
    return works


def _nbib_to_work(fields: dict[str, list[str]]) -> Work:
    def one(*tags: str) -> str:
        for tag in tags:
            if fields.get(tag):
                return fields[tag][0].strip()
        return ""

    def many(*tags: str) -> list[str]:
        out: list[str] = []
        for tag in tags:
            out.extend(v.strip() for v in fields.get(tag, []) if v.strip())
        return out

    work = Work(work_type=WorkType.JOURNAL_ARTICLE, source_db="PubMed (export)")
    # FAU is the full author name; AU is the abbreviated "Smith JA" form. Prefer
    # FAU so initials are not guessed.
    work.authors = [Author.parse(a) for a in (many("FAU") or many("AU"))]
    if any("CN" in fields for _ in [0]):
        work.authors.extend(Author.group(n) for n in many("CN"))

    work.title = _strip_wrappers(one("TI")).rstrip(".")
    work.container = _strip_wrappers(one("JT") or one("TA"))
    work.year = _year_from(one("DP", "DEP", "EDAT"))
    work.volume = one("VI")
    work.issue = one("IP")
    work.pages = one("PG")
    work.abstract = one("AB")
    work.language = one("LA")
    work.pmid = one("PMID")
    work.mesh_terms = [m.lstrip("*") for m in many("MH", "OT")]
    work.publication_types = many("PT")

    for candidate in many("AID", "LID"):
        if "[doi]" in candidate.lower():
            work.doi = normalise_doi(candidate.split(" ")[0])
            break
    for candidate in many("PMC"):
        work.pmcid = candidate.strip()

    # RF/RIN/ROF carry retraction relationships in MEDLINE.
    retraction_fields = many("RIN", "ROF", "RPI", "RPF")
    if any("retract" in v.lower() for v in retraction_fields) or \
            any("retracted publication" in p.lower() for p in work.publication_types):
        work.retracted = True
        work.retraction_note = next(
            (v for v in retraction_fields if "retract" in v.lower()),
            "MEDLINE retraction record",
        )

    work.peer_reviewed = True  # MEDLINE indexes peer-reviewed journals
    work.raw = dict(fields)
    return work


# ------------------------------------------------------------------- BibTeX


def parse_bibtex(text: str) -> list[Work]:
    works: list[Work] = []
    for entry_type, body in _bibtex_entries(text):
        fields = _bibtex_fields(body)
        work = Work(work_type=BIBTEX_TYPES.get(entry_type.lower(), WorkType.JOURNAL_ARTICLE))
        work.authors = [Author.parse(a) for a in _split_bibtex_names(fields.get("author", ""))]
        work.editors = [Author.parse(a) for a in _split_bibtex_names(fields.get("editor", ""))]
        work.title = _clean_bibtex(fields.get("title", ""))
        work.container = _clean_bibtex(
            fields.get("journal") or fields.get("booktitle") or fields.get("journaltitle", "")
        )
        work.year = _year_from(fields.get("year") or fields.get("date", ""))
        work.volume = _clean_bibtex(fields.get("volume", ""))
        work.issue = _clean_bibtex(fields.get("number") or fields.get("issue", ""))
        work.pages = _clean_bibtex(fields.get("pages", "")).replace("--", "-")
        work.publisher = _clean_bibtex(fields.get("publisher") or fields.get("institution", ""))
        work.edition = _clean_bibtex(fields.get("edition", ""))
        work.doi = normalise_doi(fields.get("doi", ""))
        work.url = fields.get("url", "").strip()
        work.abstract = _clean_bibtex(fields.get("abstract", ""))
        work.isbn = fields.get("isbn", "").strip()
        work.report_number = _clean_bibtex(fields.get("number", "")) \
            if work.work_type is WorkType.REPORT else ""
        keywords = fields.get("keywords", "")
        work.mesh_terms = [k.strip() for k in re.split(r"[;,]", keywords) if k.strip()]
        work.raw = dict(fields)
        works.append(work)
    return works


def _bibtex_entries(text: str) -> list[tuple[str, str]]:
    """Split @type{...} entries, tracking brace depth so nested braces in
    titles do not terminate an entry early."""
    entries: list[tuple[str, str]] = []
    index = 0
    while True:
        at = text.find("@", index)
        if at == -1:
            break
        match = re.match(r"@(\w+)\s*[{(]", text[at:])
        if not match:
            index = at + 1
            continue
        entry_type = match.group(1)
        if entry_type.lower() in ("comment", "preamble", "string"):
            index = at + len(match.group(0))
            continue
        start = at + len(match.group(0))
        depth = 1
        position = start
        while position < len(text) and depth:
            if text[position] == "{":
                depth += 1
            elif text[position] == "}":
                depth -= 1
            position += 1
        entries.append((entry_type, text[start:position - 1]))
        index = position
    return entries


def _bibtex_fields(body: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    # Drop the citation key, which precedes the first comma.
    _, _, remainder = body.partition(",")
    position = 0
    while position < len(remainder):
        match = re.match(r"\s*([A-Za-z_-]+)\s*=\s*", remainder[position:])
        if not match:
            position += 1
            continue
        name = match.group(1).lower()
        value_start = position + len(match.group(0))
        value, position = _read_bibtex_value(remainder, value_start)
        fields[name] = value
    return fields


def _read_bibtex_value(text: str, start: int) -> tuple[str, int]:
    if start >= len(text):
        return "", start
    if text[start] == "{":
        depth, position = 1, start + 1
        while position < len(text) and depth:
            if text[position] == "{":
                depth += 1
            elif text[position] == "}":
                depth -= 1
            position += 1
        return text[start + 1:position - 1], position
    if text[start] == '"':
        position = start + 1
        while position < len(text) and text[position] != '"':
            position += 2 if text[position] == "\\" else 1
        return text[start + 1:position], position + 1
    end = start
    while end < len(text) and text[end] not in ",\n":
        end += 1
    return text[start:end].strip(), end + 1


def _split_bibtex_names(value: str) -> list[str]:
    """Split a BibTeX name list on " and ", respecting brace depth.

    Double braces are how BibTeX marks a corporate name as one unit —
    ``{{Centers for Disease Control and Prevention}}``. Splitting naively on
    " and " tears that into two authors named "Centers for Disease Control" and
    "Prevention", which then both get initialised. Depth tracking is the whole
    reason the braces are there.
    """
    names: list[str] = []
    current: list[str] = []
    depth = 0
    index = 0
    while index < len(value):
        char = value[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth = max(0, depth - 1)
        if depth == 0 and value.startswith(" and ", index):
            names.append("".join(current))
            current = []
            index += 5
            continue
        current.append(char)
        index += 1
    names.append("".join(current))
    return [_clean_bibtex(n) for n in names if _clean_bibtex(n)]


def _clean_bibtex(value: str) -> str:
    """Remove protective braces and resolve the common LaTeX escapes.

    BibTeX from Zotero and Scopus wraps capitals in braces ({COVID-19}) to stop
    BibTeX lowercasing them. Those braces must not reach the reference list.
    """
    value = value.replace("\\&", "&").replace("\\%", "%").replace("\\_", "_")
    value = re.sub(r"\\textendash\s*", "–", value)
    value = re.sub(r"\\text(?:it|bf|rm)\s*\{([^}]*)\}", r"\1", value)
    accents = {
        r"\\'": "", r'\\"': "", r"\\`": "", r"\\\^": "", r"\\~": "", r"\\=": "",
    }
    for pattern in accents:
        value = re.sub(pattern + r"\{?(\w)\}?", r"\1", value)
    value = value.replace("{", "").replace("}", "")
    return " ".join(value.split())


# -------------------------------------------------------------- EndNote XML


def parse_endnote_xml(text: str) -> list[Work]:
    """EndNote XML, which EBSCOhost and ProQuest both offer."""
    works: list[Work] = []
    try:
        root = ET.fromstring(text)
    except ET.ParseError as error:
        raise ValueError(f"EndNote XML would not parse: {error}") from error

    for record in root.iter("record"):
        work = Work()
        work.title = _en_text(record, "titles/title")
        work.container = _en_text(record, "titles/secondary-title") or \
            _en_text(record, "periodical/full-title")
        work.year = _year_from(_en_text(record, "dates/year"))
        work.volume = _en_text(record, "volume")
        work.issue = _en_text(record, "number")
        work.pages = _en_text(record, "pages")
        work.publisher = _en_text(record, "publisher")
        work.abstract = _en_text(record, "abstract")
        work.language = _en_text(record, "language")
        work.doi = normalise_doi(_en_text(record, "electronic-resource-num"))
        work.url = _en_text(record, "urls/related-urls/url")
        work.isbn = _en_text(record, "isbn")

        for node in record.findall("contributors/authors/author"):
            name = _flatten(node)
            if name:
                work.authors.append(Author.parse(name))
        for node in record.findall("contributors/secondary-authors/author"):
            name = _flatten(node)
            if name:
                work.editors.append(Author.parse(name))
        work.mesh_terms = [_flatten(n) for n in record.findall("keywords/keyword")]
        work.mesh_terms = [k for k in work.mesh_terms if k]

        ref_type = record.find("ref-type")
        label = (ref_type.get("name") if ref_type is not None else "") or ""
        work.work_type = {
            "Journal Article": WorkType.JOURNAL_ARTICLE,
            "Book": WorkType.BOOK,
            "Book Section": WorkType.BOOK_CHAPTER,
            "Report": WorkType.REPORT,
            "Web Page": WorkType.WEBPAGE,
            "Thesis": WorkType.THESIS,
            "Conference Paper": WorkType.CONFERENCE_PAPER,
            "Dataset": WorkType.DATASET,
        }.get(label, WorkType.JOURNAL_ARTICLE)
        if label:
            work.publication_types.append(label)

        database = _en_text(record, "remote-database-name")
        if database:
            work.source_db = _normalise_db_name(database)
        accession = _en_text(record, "accession-num")
        if re.fullmatch(r"\d{7,8}", accession) and "medline" in database.lower():
            work.pmid = accession
        works.append(work)
    return works


def _en_text(record: ET.Element, path: str) -> str:
    node = record.find(path)
    return _flatten(node) if node is not None else ""


def _flatten(node: ET.Element | None) -> str:
    """EndNote wraps most text in <style> children."""
    if node is None:
        return ""
    return " ".join("".join(node.itertext()).split())


# ---------------------------------------------------------------------- CSV


CSV_ALIASES = {
    "authors": ("authors", "author", "author(s)", "author full names", "au"),
    "year": ("year", "publication year", "date", "py", "pub year"),
    "title": ("title", "document title", "article title", "ti"),
    "container": ("journal", "source title", "journal name", "publication title",
                  "source", "so"),
    "volume": ("volume", "vol", "vl"),
    "issue": ("issue", "number", "no", "is"),
    "pages": ("pages", "page numbers", "page range", "pp"),
    "doi": ("doi", "digital object identifier"),
    "abstract": ("abstract", "ab"),
    "url": ("url", "link", "fulltext url"),
    "publisher": ("publisher", "pb"),
    "pmid": ("pmid", "pubmed id", "pubmed_id"),
    "publication_types": ("publication type", "document type", "type", "pt"),
    "mesh_terms": ("keywords", "mesh terms", "author keywords", "kw"),
    "source_db": ("database", "db", "source database"),
}


def parse_csv(text: str) -> list[Work]:
    """A CSV or TSV export, as Scopus, Web of Science and CDC WONDER produce.

    Column names are matched case-insensitively against known aliases, because
    every vendor names them differently and asking the user to rename headers
    would make the import path useless in practice.
    """
    sample = text[:8192]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t;|")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    if not reader.fieldnames:
        return []

    lookup: dict[str, str] = {}
    for column in reader.fieldnames:
        normalised = (column or "").strip().lower().lstrip("\ufeff")
        for field_name, aliases in CSV_ALIASES.items():
            if normalised in aliases and field_name not in lookup:
                lookup[field_name] = column
                break

    if "title" not in lookup:
        raise ValueError(
            "This CSV has no recognisable title column. Expected one of: "
            + ", ".join(CSV_ALIASES["title"])
        )

    works: list[Work] = []
    for row in reader:
        def get(name: str) -> str:
            column = lookup.get(name)
            return (row.get(column) or "").strip() if column else ""

        if not get("title"):
            continue
        work = Work(work_type=WorkType.JOURNAL_ARTICLE)
        work.authors = [Author.parse(a) for a in re.split(r";|\band\b", get("authors")) if a.strip()]
        work.title = get("title")
        work.container = get("container")
        work.year = _year_from(get("year"))
        work.volume = get("volume")
        work.issue = get("issue")
        work.pages = get("pages").replace("--", "-")
        work.doi = normalise_doi(get("doi"))
        work.abstract = get("abstract")
        work.url = get("url")
        work.publisher = get("publisher")
        work.pmid = get("pmid")
        work.publication_types = [p.strip() for p in re.split(r"[;,]", get("publication_types"))
                                  if p.strip()]
        work.mesh_terms = [k.strip() for k in re.split(r"[;,]", get("mesh_terms")) if k.strip()]
        if get("source_db"):
            work.source_db = _normalise_db_name(get("source_db"))
        work.raw = {k: v for k, v in row.items() if v}
        works.append(work)
    return works


# ----------------------------------------------------------------- utilities


def _year_from(value: str) -> str:
    """Pull a four-digit year out of any of the dozen date shapes exports use."""
    if not value:
        return ""
    match = re.search(r"(1[5-9]\d{2}|20\d{2}|21\d{2})", value)
    return match.group(1) if match else ""


def _strip_wrappers(title: str) -> str:
    """Remove the brackets MEDLINE puts around translated titles, and the
    trailing period exports add."""
    title = title.strip()
    if title.startswith("[") and title.rstrip(".").endswith("]"):
        title = title.rstrip(".")[1:-1]
    return " ".join(title.split())


def _first_url(candidates: list[str]) -> str:
    for candidate in candidates:
        for part in re.split(r"[;\s]+", candidate):
            if part.startswith("http"):
                return part
    return ""
