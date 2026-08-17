"""
Adapters for the scholarly indexes that expose a public API.

Covered here: PubMed/MEDLINE (NCBI E-utilities), Europe PMC, Crossref,
OpenAlex, Semantic Scholar, Unpaywall, and a retraction check that combines
three independent signals.

**Cochrane is reached through PubMed and Europe PMC, not through Wiley.** The
Cochrane Library has no API an individual can buy, but Cochrane reviews are
indexed in MEDLINE and Europe PMC, so `search_cochrane_reviews` runs a filtered
query against those. That gets the review records and their abstracts; it does
not get the full review text, and the tool says so rather than implying
otherwise. For CENTRAL and for the databases with no index route at all —
CINAHL, PsycINFO, Embase, JBI, Global Health — the path is a manual search and
an RIS export through `importers.py`.

Every adapter returns `Work` objects with `source_db` set, so a reference can
always be traced to the index that produced it.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

from ..models import Author, Work, WorkType, normalise_doi
from .base import REGISTRY, Fetcher, SourceSpec

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
EUROPE_PMC = "https://www.ebi.ac.uk/europepmc/webservices/rest"
CROSSREF = "https://api.crossref.org"
OPENALEX = "https://api.openalex.org"
SEMANTIC_SCHOLAR = "https://api.semanticscholar.org/graph/v1"
UNPAYWALL = "https://api.unpaywall.org/v2"

# PubMed's own filters for study design. These are the documented
# publication-type and subset filters, which is why level classification on
# PubMed records is far more reliable than on imported ones.
PUBMED_LEVEL_FILTERS = {
    "I": ('(systematic[sb] OR "meta analysis"[pt] OR "systematic review"[pt] '
          'OR "randomized controlled trial"[pt])'),
    "II": '("controlled clinical trial"[pt] OR "clinical trial"[pt])',
    "III": ('("cohort studies"[mh] OR "case-control studies"[mh] '
            'OR "observational study"[pt])'),
    "IV": ('("cross-sectional studies"[mh] OR "qualitative research"[mh] '
           'OR "survey"[tiab])'),
    "V": '("practice guideline"[pt] OR "consensus development conference"[pt])',
}

# Applied to every PubMed search: peer-reviewed journal content in English,
# with opinion and correspondence types removed. The project's criteria exclude
# editorials and narrative opinion, so filtering at the query is cheaper and
# more honest than retrieving them and discarding them later.
PUBMED_QUALITY_FILTER = (
    'NOT (editorial[pt] OR letter[pt] OR comment[pt] OR news[pt] '
    'OR "newspaper article"[pt] OR biography[pt])'
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ============================================================= PubMed/MEDLINE


async def search_pubmed(
    fetcher: Fetcher,
    query: str,
    *,
    limit: int = 40,
    min_level: str = "",
    years_back: int = 0,
    peer_reviewed_only: bool = True,
) -> tuple[list[Work], dict[str, str]]:
    """Search PubMed, then fetch full records for the hits.

    Returns the works plus a record of the exact query that was run — which the
    audit document reproduces, because a search that cannot be re-run is not a
    reproducible method.
    """
    term = query.strip()
    if peer_reviewed_only:
        term = f"({term}) {PUBMED_QUALITY_FILTER}"
    if min_level and min_level in PUBMED_LEVEL_FILTERS:
        allowed = [
            PUBMED_LEVEL_FILTERS[level]
            for level in ("I", "II", "III", "IV", "V")
            if _rank(level) <= _rank(min_level)
        ]
        term = f"({term}) AND ({' OR '.join(allowed)})"
    if years_back:
        term = f'({term}) AND ("last {years_back} years"[dp])'

    params = {
        "db": "pubmed", "term": term, "retmax": str(limit),
        "retmode": "json", "sort": "relevance", **fetcher.ncbi_params(),
    }
    search = await fetcher.get(f"{EUTILS}/esearch.fcgi", params, ttl_seconds=21_600)
    audit = {
        "source": "PubMed/MEDLINE (NCBI E-utilities)",
        "query": term,
        "url": search.url,
        "run_at": search.fetched_at or _now(),
        "from_cache": "yes" if search.from_cache else "no",
    }
    if not search.ok or not isinstance(search.json, dict):
        audit["error"] = search.error or f"HTTP {search.status}"
        return ([], audit)

    result = search.json.get("esearchresult", {})
    ids = [i for i in result.get("idlist", []) if i]
    audit["total_available"] = str(result.get("count", len(ids)))
    audit["retrieved"] = str(len(ids))
    if not ids:
        return ([], audit)

    works = await fetch_pubmed_records(fetcher, ids)
    for work in works:
        work.query = term
    return (works, audit)


async def fetch_pubmed_records(fetcher: Fetcher, pmids: list[str]) -> list[Work]:
    """Fetch full MEDLINE records by PMID.

    efetch XML is used rather than esummary JSON because only the XML carries
    publication types, MeSH headings and the CommentsCorrections links that
    reveal retractions — the three fields the evidence pipeline needs most.
    """
    works: list[Work] = []
    for batch in _chunks(pmids, 100):     # NCBI's documented POST-free batch size
        params = {
            "db": "pubmed", "id": ",".join(batch), "retmode": "xml",
            **fetcher.ncbi_params(),
        }
        response = await fetcher.get(f"{EUTILS}/efetch.fcgi", params,
                                     expect="xml", ttl_seconds=604_800)
        if not response.ok or not response.text:
            continue
        works.extend(parse_pubmed_xml(response.text))
    return works


def parse_pubmed_xml(xml_text: str) -> list[Work]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    works: list[Work] = []
    for article in root.iter("PubmedArticle"):
        work = Work(work_type=WorkType.JOURNAL_ARTICLE, source_db="PubMed/MEDLINE",
                    retrieved_at=_now(), peer_reviewed=True)
        citation = article.find("MedlineCitation")
        if citation is None:
            continue

        work.pmid = _text(citation.find("PMID"))
        art = citation.find("Article")
        if art is None:
            continue

        work.title = _clean_title(_all_text(art.find("ArticleTitle")))
        work.abstract = _abstract_text(art.find("Abstract"))

        journal = art.find("Journal")
        if journal is not None:
            work.container = _text(journal.find("Title")) or \
                _text(journal.find("ISOAbbreviation"))
            issue = journal.find("JournalIssue")
            if issue is not None:
                work.volume = _text(issue.find("Volume"))
                work.issue = _text(issue.find("Issue"))
                work.year = _pubmed_year(issue.find("PubDate"))

        pagination = art.find("Pagination")
        if pagination is not None:
            work.pages = _text(pagination.find("MedlinePgn")) or \
                _text(pagination.find("StartPage"))

        work.language = _text(art.find("Language"))
        work.authors = _pubmed_authors(art.find("AuthorList"))
        work.publication_types = [
            _text(pt) for pt in art.findall("PublicationTypeList/PublicationType")
            if _text(pt)
        ]
        work.mesh_terms = [
            _text(d) for d in citation.findall("MeshHeadingList/MeshHeading/DescriptorName")
            if _text(d)
        ]

        for eloc in art.findall("ELocationID"):
            if eloc.get("EIdType") == "doi":
                work.doi = normalise_doi(_text(eloc))
        for article_id in article.findall("PubmedData/ArticleIdList/ArticleId"):
            kind = article_id.get("IdType")
            value = _text(article_id)
            if kind == "doi" and not work.doi:
                work.doi = normalise_doi(value)
            elif kind == "pmc":
                work.pmcid = value

        # CommentsCorrectionsList is how MEDLINE records that an article has
        # been retracted. Without checking it, a retracted trial reads as
        # ordinary Level I evidence.
        for correction in citation.findall("CommentsCorrectionsList/CommentsCorrections"):
            ref_type = (correction.get("RefType") or "").lower()
            if "retraction" in ref_type:
                work.retracted = True
                work.retraction_note = (
                    f"{correction.get('RefType')}: "
                    f"{_text(correction.find('RefSource'))}".strip(": ")
                )
        if any("retracted publication" in p.lower() for p in work.publication_types):
            work.retracted = True
            work.retraction_note = work.retraction_note or "indexed as Retracted Publication"

        work.raw = {"pmid": work.pmid, "publication_types": work.publication_types}
        work.ensure_key()
        works.append(work)
    return works


def _pubmed_authors(author_list: ET.Element | None) -> list[Author]:
    if author_list is None:
        return []
    authors: list[Author] = []
    for node in author_list.findall("Author"):
        collective = _text(node.find("CollectiveName"))
        if collective:
            authors.append(Author.group(collective))
            continue
        family = _text(node.find("LastName"))
        given = _text(node.find("ForeName")) or _text(node.find("Initials"))
        suffix = _text(node.find("Suffix"))
        if family or given:
            authors.append(Author(family=family, given=given, suffix=suffix))
    return authors


def _pubmed_year(pub_date: ET.Element | None) -> str:
    if pub_date is None:
        return ""
    year = _text(pub_date.find("Year"))
    if year:
        return year
    # MedlineDate carries irregular forms: "2019 Nov-Dec", "2018-2019".
    match = re.search(r"(1[5-9]\d{2}|20\d{2})", _text(pub_date.find("MedlineDate")))
    return match.group(1) if match else ""


def _abstract_text(abstract: ET.Element | None) -> str:
    """Join a structured abstract, keeping its section labels.

    MEDLINE splits structured abstracts into labelled AbstractText elements.
    Concatenating them without the labels loses the Methods/Results boundary
    that both design classification and data extraction depend on.
    """
    if abstract is None:
        return ""
    parts: list[str] = []
    for node in abstract.findall("AbstractText"):
        label = (node.get("Label") or "").strip()
        body = _all_text(node)
        if not body:
            continue
        parts.append(f"{label.title()}: {body}" if label else body)
    return " ".join(parts)


def _clean_title(title: str) -> str:
    title = title.strip()
    if title.startswith("[") and title.rstrip(".").endswith("]"):
        title = title.rstrip(".")[1:-1]
    return " ".join(title.split()).rstrip(".")


async def search_cochrane_reviews(
    fetcher: Fetcher, query: str, *, limit: int = 25
) -> tuple[list[Work], dict[str, str]]:
    """Cochrane systematic reviews, via their MEDLINE indexing.

    The Cochrane Library itself has no API an unaffiliated individual can buy.
    Cochrane Database of Systematic Reviews records *are* indexed in MEDLINE, so
    this restricts a PubMed search to that journal. Two limits worth being
    explicit about: this returns review records and abstracts, not full review
    text, and it does not reach CENTRAL — the trials register — at all. For
    CENTRAL, search the Cochrane Library by hand and import the RIS export.
    """
    term = f'({query}) AND "Cochrane Database Syst Rev"[jour]'
    works, audit = await search_pubmed(
        fetcher, term, limit=limit, peer_reviewed_only=False
    )
    audit["source"] = "Cochrane Database of Systematic Reviews (via MEDLINE indexing)"
    audit["coverage_note"] = (
        "Review records and abstracts only — not full review text, and not "
        "CENTRAL. Import a Cochrane Library RIS export for those."
    )
    return (works, audit)


# =================================================================== EuropePMC


async def search_europepmc(
    fetcher: Fetcher, query: str, *, limit: int = 40, open_access_only: bool = False
) -> tuple[list[Work], dict[str, str]]:
    """Europe PMC: MEDLINE plus preprints, patents and agency reports.

    Worth searching alongside PubMed rather than instead of it — the coverage
    overlaps heavily but not completely, and Europe PMC additionally exposes
    full-text search over its open-access subset.
    """
    term = query.strip()
    if open_access_only:
        term = f"({term}) AND OPEN_ACCESS:y"
    params = {
        "query": term, "format": "json", "resultType": "core",
        "pageSize": str(min(limit, 100)), "sort": "CITED desc",
    }
    response = await fetcher.get(f"{EUROPE_PMC}/search", params, ttl_seconds=21_600)
    audit = {
        "source": "Europe PMC", "query": term, "url": response.url,
        "run_at": response.fetched_at or _now(),
        "from_cache": "yes" if response.from_cache else "no",
    }
    if not response.ok or not isinstance(response.json, dict):
        audit["error"] = response.error or f"HTTP {response.status}"
        return ([], audit)

    payload = response.json
    audit["total_available"] = str(payload.get("hitCount", 0))
    results = (payload.get("resultList") or {}).get("result") or []
    audit["retrieved"] = str(len(results))

    works: list[Work] = []
    for item in results:
        work = Work(work_type=_epmc_type(item), source_db="Europe PMC",
                    retrieved_at=_now(), query=term)
        work.pmid = str(item.get("pmid") or "")
        work.pmcid = str(item.get("pmcid") or "")
        work.doi = normalise_doi(str(item.get("doi") or ""))
        work.title = _clean_title(str(item.get("title") or ""))
        work.abstract = str(item.get("abstractText") or "")
        work.year = str(item.get("pubYear") or "")
        work.pages = str(item.get("pageInfo") or "")
        work.language = str(item.get("language") or "")

        journal_info = item.get("journalInfo") or {}
        work.volume = str(journal_info.get("volume") or "")
        work.issue = str(journal_info.get("issue") or "")
        work.container = str((journal_info.get("journal") or {}).get("title") or "")

        author_list = (item.get("authorList") or {}).get("author") or []
        for entry in author_list:
            if entry.get("collectiveName"):
                work.authors.append(Author.group(entry["collectiveName"]))
            else:
                work.authors.append(Author(
                    family=str(entry.get("lastName") or ""),
                    given=str(entry.get("firstName") or entry.get("initials") or ""),
                ))
        if not work.authors and item.get("authorString"):
            work.authors = [Author.parse(a) for a in
                            str(item["authorString"]).rstrip(".").split(", ") if a]

        work.publication_types = [
            str(t) for t in (item.get("pubTypeList") or {}).get("pubType", []) if t
        ]
        work.mesh_terms = [
            str(k) for k in (item.get("keywordList") or {}).get("keyword", []) if k
        ]
        if str(item.get("isOpenAccess") or "").upper() == "Y" and work.pmcid:
            work.open_access_url = f"https://europepmc.org/article/PMC/{work.pmcid}"
        # Europe PMC marks preprints explicitly; they are not peer reviewed and
        # the project's criteria require peer review.
        is_preprint = str(item.get("source") or "") == "PPR"
        work.peer_reviewed = not is_preprint
        if is_preprint:
            work.work_type = WorkType.PREPRINT
            work.publication_types.append("Preprint")
        work.raw = {"source": item.get("source"), "id": item.get("id")}
        work.ensure_key()
        works.append(work)
    return (works, audit)


def _epmc_type(item: dict) -> WorkType:
    types = " ".join(str(t).lower() for t in (item.get("pubTypeList") or {}).get("pubType", []))
    if "preprint" in types or str(item.get("source") or "") == "PPR":
        return WorkType.PREPRINT
    if "book" in types:
        return WorkType.BOOK
    if "report" in types:
        return WorkType.REPORT
    return WorkType.JOURNAL_ARTICLE


# ==================================================================== Crossref


async def lookup_doi(fetcher: Fetcher, doi: str) -> Work | None:
    """Resolve one DOI through Crossref.

    This is how a citation the user pastes in, or a reference found in another
    paper, becomes a fully-formed reference entry with no manual typing.
    """
    doi = normalise_doi(doi)
    if not doi:
        return None
    params = {"mailto": fetcher.contact_email} if fetcher.contact_email else {}
    response = await fetcher.get(f"{CROSSREF}/works/{doi}", params, ttl_seconds=2_592_000)
    if not response.ok or not isinstance(response.json, dict):
        return None
    return _crossref_work(response.json.get("message") or {})


async def search_crossref(
    fetcher: Fetcher, query: str, *, limit: int = 25, journal_articles_only: bool = True
) -> tuple[list[Work], dict[str, str]]:
    params = {
        "query.bibliographic": query, "rows": str(min(limit, 100)),
        "select": ("DOI,title,author,container-title,volume,issue,page,published,"
                   "type,publisher,abstract,update-to,is-referenced-by-count,"
                   "subject,ISSN,language"),
    }
    if journal_articles_only:
        params["filter"] = "type:journal-article"
    if fetcher.contact_email:
        params["mailto"] = fetcher.contact_email

    response = await fetcher.get(f"{CROSSREF}/works", params, ttl_seconds=21_600)
    audit = {
        "source": "Crossref", "query": query, "url": response.url,
        "run_at": response.fetched_at or _now(),
        "from_cache": "yes" if response.from_cache else "no",
    }
    if not response.ok or not isinstance(response.json, dict):
        audit["error"] = response.error or f"HTTP {response.status}"
        return ([], audit)

    message = response.json.get("message") or {}
    audit["total_available"] = str(message.get("total-results", 0))
    items = message.get("items") or []
    audit["retrieved"] = str(len(items))
    works = [_crossref_work(item) for item in items]
    for work in works:
        work.query = query
    return ([w for w in works if w.title], audit)


def _crossref_work(item: dict) -> Work:
    kind = str(item.get("type") or "journal-article")
    work = Work(
        work_type={
            "journal-article": WorkType.JOURNAL_ARTICLE,
            "book": WorkType.BOOK,
            "book-chapter": WorkType.BOOK_CHAPTER,
            "monograph": WorkType.BOOK,
            "report": WorkType.REPORT,
            "dataset": WorkType.DATASET,
            "posted-content": WorkType.PREPRINT,
            "proceedings-article": WorkType.CONFERENCE_PAPER,
            "dissertation": WorkType.THESIS,
        }.get(kind, WorkType.JOURNAL_ARTICLE),
        source_db="Crossref", retrieved_at=_now(),
    )
    work.doi = normalise_doi(str(item.get("DOI") or ""))
    titles = item.get("title") or []
    work.title = _clean_title(str(titles[0]) if titles else "")
    containers = item.get("container-title") or []
    work.container = str(containers[0]) if containers else ""
    work.volume = str(item.get("volume") or "")
    work.issue = str(item.get("issue") or "")
    work.pages = str(item.get("page") or "")
    work.publisher = str(item.get("publisher") or "")
    work.language = str(item.get("language") or "")

    parts = ((item.get("published") or {}).get("date-parts") or [[]])[0]
    work.year = str(parts[0]) if parts else ""

    for entry in item.get("author") or []:
        if entry.get("name"):
            work.authors.append(Author.group(str(entry["name"])))
        else:
            work.authors.append(Author(
                family=str(entry.get("family") or ""),
                given=str(entry.get("given") or ""),
                suffix=str(entry.get("suffix") or ""),
            ))

    abstract = str(item.get("abstract") or "")
    if abstract:
        # Crossref abstracts arrive as JATS XML fragments.
        work.abstract = " ".join(re.sub(r"<[^>]+>", " ", abstract).split())

    work.mesh_terms = [str(s) for s in item.get("subject") or []]
    if kind == "posted-content":
        work.peer_reviewed = False
        work.publication_types.append("Preprint")

    # Crossref records a retraction as an `update-to` relation on the notice, and
    # the retracted article carries the reciprocal link.
    for update in item.get("update-to") or []:
        if "retract" in str(update.get("type") or "").lower():
            work.retracted = True
            work.retraction_note = (
                f"Crossref update-to: {update.get('type')} "
                f"({update.get('DOI', '')})".strip()
            )
    work.raw = {"crossref_type": kind,
                "cited_by": item.get("is-referenced-by-count")}
    work.ensure_key()
    return work


# ==================================================================== OpenAlex


async def search_openalex(
    fetcher: Fetcher, query: str, *, limit: int = 25
) -> tuple[list[Work], dict[str, str]]:
    """OpenAlex — useful mainly for two things PubMed lacks: an explicit
    `is_retracted` flag, and open-access locations."""
    params = {
        "search": query, "per_page": str(min(limit, 50)),
        "select": ("id,doi,title,publication_year,authorships,primary_location,"
                   "biblio,type,is_retracted,open_access,language,cited_by_count"),
    }
    if fetcher.contact_email:
        params["mailto"] = fetcher.contact_email
    # OpenAlex moved to mandatory API keys in February 2026. Anonymous callers
    # get roughly 100 credits a day, which a single literature search exhausts,
    # so the key is effectively required rather than merely recommended. Some of
    # OpenAlex's own documentation pages still say no key is needed; the
    # behaviour of the API is what counts.
    if fetcher.api_keys.get("openalex"):
        params["api_key"] = fetcher.api_keys["openalex"]

    response = await fetcher.get(f"{OPENALEX}/works", params, ttl_seconds=21_600)
    audit = {
        "source": "OpenAlex", "query": query, "url": response.url,
        "run_at": response.fetched_at or _now(),
        "from_cache": "yes" if response.from_cache else "no",
    }
    if not response.ok or not isinstance(response.json, dict):
        audit["error"] = response.error or f"HTTP {response.status}"
        return ([], audit)

    audit["total_available"] = str((response.json.get("meta") or {}).get("count", 0))
    results = response.json.get("results") or []
    audit["retrieved"] = str(len(results))

    works: list[Work] = []
    for item in results:
        work = Work(source_db="OpenAlex", retrieved_at=_now(), query=query)
        work.doi = normalise_doi(str(item.get("doi") or ""))
        work.title = _clean_title(str(item.get("title") or ""))
        work.year = str(item.get("publication_year") or "")
        work.language = str(item.get("language") or "")
        work.retracted = bool(item.get("is_retracted"))
        if work.retracted:
            work.retraction_note = "OpenAlex is_retracted flag"

        location = item.get("primary_location") or {}
        source = location.get("source") or {}
        work.container = str(source.get("display_name") or "")
        work.publisher = str(source.get("host_organization_name") or "")

        biblio = item.get("biblio") or {}
        work.volume = str(biblio.get("volume") or "")
        work.issue = str(biblio.get("issue") or "")
        first, last = biblio.get("first_page"), biblio.get("last_page")
        work.pages = f"{first}-{last}" if first and last else str(first or "")

        for authorship in item.get("authorships") or []:
            name = str((authorship.get("author") or {}).get("display_name") or "")
            if name:
                work.authors.append(Author.parse(name))

        open_access = item.get("open_access") or {}
        work.open_access_url = str(open_access.get("oa_url") or "")

        kind = str(item.get("type") or "")
        work.work_type = {
            "article": WorkType.JOURNAL_ARTICLE, "book": WorkType.BOOK,
            "book-chapter": WorkType.BOOK_CHAPTER, "report": WorkType.REPORT,
            "dataset": WorkType.DATASET, "preprint": WorkType.PREPRINT,
            "dissertation": WorkType.THESIS,
        }.get(kind, WorkType.JOURNAL_ARTICLE)
        if kind == "preprint":
            work.peer_reviewed = False
        work.raw = {"openalex_id": item.get("id"), "cited_by": item.get("cited_by_count")}
        work.ensure_key()
        works.append(work)
    return (works, audit)


# ================================================================== Unpaywall


async def find_open_access(fetcher: Fetcher, work: Work) -> str:
    """Find a legal open-access copy, so the user can actually read the source
    they are about to cite. Requires a contact email, which Unpaywall's terms
    ask for."""
    if not work.doi or not fetcher.contact_email:
        return ""
    response = await fetcher.get(
        f"{UNPAYWALL}/{work.doi}", {"email": fetcher.contact_email},
        ttl_seconds=604_800,
    )
    if not response.ok or not isinstance(response.json, dict):
        return ""
    best = response.json.get("best_oa_location") or {}
    url = str(best.get("url_for_pdf") or best.get("url") or "")
    if url:
        work.open_access_url = url
    return url


# ================================================================ retractions


async def check_retraction(fetcher: Fetcher, work: Work) -> tuple[bool, str]:
    """Check one work for a retraction against three independent signals.

    Retraction checking is not optional for evidence-based work: citing a
    retracted trial as support is one of the few citation errors that can change
    a clinical conclusion. Three signals are used because no single one is
    complete — MEDLINE indexes retractions for journals it covers, Crossref
    carries publisher-deposited retraction notices (and now hosts the Retraction
    Watch database), and OpenAlex maintains its own flag.
    """
    if work.retracted:
        return (True, work.retraction_note or "already flagged")

    signals: list[str] = []

    if work.doi:
        response = await fetcher.get(
            f"{CROSSREF}/works/{work.doi}",
            {"mailto": fetcher.contact_email} if fetcher.contact_email else {},
            ttl_seconds=604_800,
        )
        if response.ok and isinstance(response.json, dict):
            message = response.json.get("message") or {}
            for update in message.get("update-to") or []:
                if "retract" in str(update.get("type") or "").lower():
                    signals.append(f"Crossref retraction notice ({update.get('DOI', '')})")
            for update in message.get("updated-by") or []:
                if "retract" in str(update.get("type") or "").lower():
                    signals.append(f"Crossref updated-by retraction ({update.get('DOI', '')})")

    if work.pmid:
        response = await fetcher.get(
            f"{EUTILS}/efetch.fcgi",
            {"db": "pubmed", "id": work.pmid, "retmode": "xml", **fetcher.ncbi_params()},
            expect="xml", ttl_seconds=604_800,
        )
        if response.ok and response.text:
            parsed = parse_pubmed_xml(response.text)
            if parsed and parsed[0].retracted:
                signals.append(f"MEDLINE: {parsed[0].retraction_note}")

    if work.doi and not signals:
        response = await fetcher.get(
            f"{OPENALEX}/works/doi:{work.doi}",
            {"select": "is_retracted", "mailto": fetcher.contact_email},
            ttl_seconds=604_800,
        )
        if response.ok and isinstance(response.json, dict) and response.json.get("is_retracted"):
            signals.append("OpenAlex is_retracted flag")

    if signals:
        work.retracted = True
        work.retraction_note = "; ".join(signals)
        return (True, work.retraction_note)
    return (False, "no retraction found in Crossref, MEDLINE or OpenAlex")


async def check_retractions(fetcher: Fetcher, works: list[Work]) -> list[dict[str, str]]:
    """Check every work, returning a log for the audit document.

    The log records the negatives too. "We checked 23 sources for retractions
    and found none" is a methodological statement; silence is not.
    """
    log: list[dict[str, str]] = []
    for work in works:
        retracted, detail = await check_retraction(fetcher, work)
        log.append({
            "work": work.key,
            "title": work.title[:120],
            "retracted": "yes" if retracted else "no",
            "detail": detail,
            "checked_at": _now(),
        })
    return log


# ------------------------------------------------------------------ utilities


def _rank(level: str) -> int:
    return {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5}.get(level, 9)


def _text(node: ET.Element | None) -> str:
    return (node.text or "").strip() if node is not None else ""


def _all_text(node: ET.Element | None) -> str:
    """Flatten mixed content — titles and abstracts contain <i>, <sup>, <b>."""
    if node is None:
        return ""
    return " ".join("".join(node.itertext()).split())


def _chunks(items: list, size: int):
    for start in range(0, len(items), size):
        yield items[start:start + size]


# ------------------------------------------------------------------- registry

REGISTRY.register(SourceSpec(
    key="pubmed", label="PubMed / MEDLINE", kind="api",
    discipline="Nursing, medicine and public health",
    docs="https://www.ncbi.nlm.nih.gov/books/NBK25501/",
    needs_email=True,
    note=("Free. An NCBI API key raises the rate limit from 3 to 10 requests per "
          "second. Publication types and MeSH make this the most reliable source "
          "for level-of-evidence classification."),
    search=search_pubmed,
))
REGISTRY.register(SourceSpec(
    key="europepmc", label="Europe PMC", kind="api",
    discipline="Life sciences and public health",
    docs="https://europepmc.org/RestfulWebService",
    note="Free, no key. Overlaps MEDLINE and adds preprints and agency reports.",
    search=search_europepmc,
))
REGISTRY.register(SourceSpec(
    key="cochrane-via-medline", label="Cochrane Reviews (via MEDLINE)", kind="api",
    discipline="Clinical medicine and nursing",
    docs="https://www.cochranelibrary.com/",
    needs_email=True,
    note=("Review records and abstracts only — the Cochrane Library has no "
          "individual API. Full review text and CENTRAL need a manual search "
          "and an RIS import."),
    search=search_cochrane_reviews,
))
REGISTRY.register(SourceSpec(
    key="crossref", label="Crossref", kind="api",
    discipline="All disciplines (metadata and DOI resolution)",
    docs="https://api.crossref.org/swagger-ui/index.html",
    note="Free. Best route for resolving a DOI and for retraction notices.",
    search=search_crossref,
))
REGISTRY.register(SourceSpec(
    key="openalex", label="OpenAlex", kind="api",
    discipline="All disciplines",
    docs="https://docs.openalex.org/",
    needs_key="openalex",
    note=("Free, but a key has been required since February 2026 — anonymous "
          "callers get about 100 credits a day, which one literature search "
          "spends. Carries an explicit retraction flag and open-access "
          "locations, which is what makes it worth registering for."),
    search=search_openalex,
))
