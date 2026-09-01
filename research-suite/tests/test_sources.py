"""
Retrieval-layer tests, run against a mock transport.

No network, no API keys. `httpx.MockTransport` serves recorded response shapes,
which is the same approach the nursery tracker's sync tests take against
Firestore — it exercises the real adapter code, real parsing and the real cache,
while staying runnable on a laptop with no credentials and in CI.

The fixtures are trimmed real response shapes: NCBI's `PubmedArticleSet` XML
with a structured abstract, a `CollectiveName` author and a retraction link;
Europe PMC's `resultList`; Crossref's JATS-fragment abstract and `update-to`
relation; OpenAlex's inverted index and `is_retracted` flag.

Run: python3 tests/test_sources.py
"""

from __future__ import annotations

import asyncio
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx  # noqa: E402

from app.evidence import levels  # noqa: E402
from app.models import EvidenceLevel  # noqa: E402
from app.sources import scholarly  # noqa: E402
from app.sources.base import Fetcher  # noqa: E402

FAILURES: list[str] = []
CHECKS = 0


def check(label: str, got, want) -> None:
    global CHECKS
    CHECKS += 1
    if got != want:
        FAILURES.append(f"{label}\n     got: {got!r}\n    want: {want!r}")


# ------------------------------------------------------------------- fixtures

ESEARCH_JSON = {
    "esearchresult": {"count": "1284", "retmax": "2", "idlist": ["31234567", "22222222"]}
}

EFETCH_XML = """<?xml version="1.0"?>
<PubmedArticleSet>
<PubmedArticle>
  <MedlineCitation Status="MEDLINE">
    <PMID Version="1">31234567</PMID>
    <Article PubModel="Print">
      <Journal>
        <ISOAbbreviation>JAMA Intern Med</ISOAbbreviation>
        <Title>JAMA internal medicine</Title>
        <JournalIssue CitedMedium="Internet">
          <Volume>179</Volume><Issue>3</Issue>
          <PubDate><Year>2019</Year><Month>Mar</Month></PubDate>
        </JournalIssue>
      </Journal>
      <ArticleTitle>Effect of a nurse-led transitional care intervention on
        <i>30-day</i> readmission: a randomized clinical trial.</ArticleTitle>
      <Pagination><MedlinePgn>412-425</MedlinePgn></Pagination>
      <Abstract>
        <AbstractText Label="IMPORTANCE">Readmissions remain common.</AbstractText>
        <AbstractText Label="METHODS">A randomized clinical trial enrolled 1204
          adults across 9 hospitals.</AbstractText>
        <AbstractText Label="RESULTS">Readmission fell from 21.4% to 15.2%
          (OR, 0.66; 95% CI, 0.52-0.84).</AbstractText>
      </Abstract>
      <AuthorList CompleteYN="Y">
        <Author ValidYN="Y"><LastName>Chen</LastName><ForeName>Wei Ling</ForeName>
          <Initials>WL</Initials></Author>
        <Author ValidYN="Y"><LastName>O'Brien</LastName><ForeName>Mary Kate</ForeName>
          <Initials>MK</Initials></Author>
        <Author ValidYN="Y"><CollectiveName>Transitional Care Study Group</CollectiveName>
        </Author>
      </AuthorList>
      <Language>eng</Language>
      <PublicationTypeList>
        <PublicationType UI="D016428">Journal Article</PublicationType>
        <PublicationType UI="D016449">Randomized Controlled Trial</PublicationType>
      </PublicationTypeList>
      <ELocationID EIdType="doi" ValidYN="Y">10.1001/jamainternmed.2018.7624</ELocationID>
    </Article>
    <MeshHeadingList>
      <MeshHeading><DescriptorName MajorTopicYN="Y">Patient Readmission</DescriptorName>
      </MeshHeading>
      <MeshHeading><DescriptorName MajorTopicYN="N">Humans</DescriptorName></MeshHeading>
    </MeshHeadingList>
  </MedlineCitation>
  <PubmedData>
    <ArticleIdList>
      <ArticleId IdType="pubmed">31234567</ArticleId>
      <ArticleId IdType="doi">10.1001/jamainternmed.2018.7624</ArticleId>
      <ArticleId IdType="pmc">PMC6439682</ArticleId>
    </ArticleIdList>
  </PubmedData>
</PubmedArticle>
<PubmedArticle>
  <MedlineCitation Status="MEDLINE">
    <PMID Version="1">22222222</PMID>
    <Article>
      <Journal><Title>Journal of Example</Title>
        <JournalIssue><Volume>12</Volume>
          <PubDate><MedlineDate>2015 Nov-Dec</MedlineDate></PubDate>
        </JournalIssue></Journal>
      <ArticleTitle>A trial that did not hold up.</ArticleTitle>
      <PublicationTypeList>
        <PublicationType>Journal Article</PublicationType>
        <PublicationType>Randomized Controlled Trial</PublicationType>
      </PublicationTypeList>
    </Article>
    <CommentsCorrectionsList>
      <CommentsCorrections RefType="RetractionIn">
        <RefSource>J Example. 2016 Mar;13(3):200</RefSource>
      </CommentsCorrections>
    </CommentsCorrectionsList>
  </MedlineCitation>
</PubmedArticle>
</PubmedArticleSet>
"""

EPMC_JSON = {
    "hitCount": 4211,
    "resultList": {"result": [
        {
            "id": "31234567", "source": "MED", "pmid": "31234567",
            "pmcid": "PMC6439682", "doi": "10.1001/jamainternmed.2018.7624",
            "title": "Effect of a nurse-led transitional care intervention.",
            "authorString": "Chen WL, O'Brien MK.",
            "authorList": {"author": [
                {"lastName": "Chen", "firstName": "Wei Ling", "initials": "WL"},
                {"collectiveName": "Transitional Care Study Group"},
            ]},
            "journalInfo": {"volume": "179", "issue": "3",
                            "journal": {"title": "JAMA internal medicine"}},
            "pubYear": "2019", "pageInfo": "412-425",
            "abstractText": "Readmissions remain common.",
            "pubTypeList": {"pubType": ["Journal Article", "Randomized Controlled Trial"]},
            "keywordList": {"keyword": ["readmission", "transitional care"]},
            "isOpenAccess": "Y", "language": "eng",
        },
        {
            "id": "PPR123456", "source": "PPR", "doi": "10.1101/2024.01.01.123456",
            "title": "An unreviewed preprint about staffing.",
            "authorString": "Doe J.",
            "journalInfo": {"journal": {"title": "medRxiv"}},
            "pubYear": "2024", "pubTypeList": {"pubType": ["Preprint"]},
        },
    ]},
}

CROSSREF_JSON = {
    "message": {
        "total-results": 88,
        "items": [{
            "DOI": "10.1016/S0140-6736(13)62631-8",
            "title": ["Nurse staffing and education and hospital mortality"],
            "author": [
                {"given": "Linda H.", "family": "Aiken"},
                {"name": "RN4CAST Consortium"},
            ],
            "container-title": ["The Lancet"],
            "volume": "383", "issue": "9931", "page": "1824-1830",
            "published": {"date-parts": [[2014, 2, 26]]},
            "type": "journal-article", "publisher": "Elsevier BV",
            "abstract": "<jats:p>Austerity measures risk <jats:italic>adversely</jats:italic> "
                        "affecting outcomes.</jats:p>",
            "subject": ["General Medicine"], "language": "en",
        }],
    }
}

CROSSREF_RETRACTED_JSON = {
    "message": {
        "DOI": "10.1000/retracted.1",
        "title": ["A study that was withdrawn"],
        "author": [{"given": "A", "family": "Author"}],
        "container-title": ["Journal of Example"],
        "published": {"date-parts": [[2015]]},
        "type": "journal-article",
        "update-to": [{"type": "retraction", "DOI": "10.1000/notice.1",
                       "label": "Retraction"}],
    }
}

OPENALEX_JSON = {
    "meta": {"count": 512},
    "results": [{
        "id": "https://openalex.org/W123", "doi": "https://doi.org/10.1000/retracted.1",
        "title": "A study that was withdrawn", "publication_year": 2015,
        "authorships": [{"author": {"display_name": "A Author"}}],
        "primary_location": {"source": {"display_name": "Journal of Example",
                                        "host_organization_name": "Example Press"}},
        "biblio": {"volume": "12", "issue": "3", "first_page": "100", "last_page": "110"},
        "type": "article", "is_retracted": True,
        "open_access": {"oa_url": "https://example.org/paper.pdf"},
        "language": "en", "cited_by_count": 4,
    }],
}


def handler(request: httpx.Request) -> httpx.Response:
    url = str(request.url)
    if "esearch.fcgi" in url:
        return httpx.Response(200, json=ESEARCH_JSON)
    if "efetch.fcgi" in url:
        return httpx.Response(200, text=EFETCH_XML,
                              headers={"content-type": "application/xml"})
    if "europepmc" in url:
        return httpx.Response(200, json=EPMC_JSON)
    if "api.crossref.org/works/10.1000/retracted.1" in url:
        return httpx.Response(200, json=CROSSREF_RETRACTED_JSON)
    if "api.crossref.org/works?" in url or url.endswith("/works"):
        return httpx.Response(200, json=CROSSREF_JSON)
    if "api.openalex.org/works/doi:" in url:
        # Only the one known-retracted DOI comes back flagged; a stub that
        # flagged everything would make the negative-path test vacuous.
        flagged = "retracted.1" in url
        return httpx.Response(200, json={"is_retracted": flagged})
    if "api.openalex.org" in url:
        return httpx.Response(200, json=OPENALEX_JSON)
    if "api.unpaywall.org" in url:
        return httpx.Response(200, json={
            "best_oa_location": {"url_for_pdf": "https://example.org/oa.pdf"}})
    return httpx.Response(404, json={"error": f"unmocked: {url}"})


def make_fetcher(**kwargs) -> Fetcher:
    return Fetcher(
        cache_dir=Path(tempfile.mkdtemp()) / "cache",
        contact_email="researcher@example.org",
        transport=httpx.MockTransport(handler),
        **kwargs,
    )


def run(coro):
    return asyncio.run(coro)


# ------------------------------------------------------------------- PubMed


def test_pubmed_search_and_parse() -> None:
    works, audit = run(scholarly.search_pubmed(make_fetcher(), "nurse staffing falls"))
    check("two records returned", len(works), 2)

    trial = works[0]
    check("pmid", trial.pmid, "31234567")
    # Mixed content (<i>30-day</i>) must flatten rather than truncate the title.
    check("title flattened across inline markup",
          trial.title,
          "Effect of a nurse-led transitional care intervention on 30-day "
          "readmission: a randomized clinical trial")
    check("full journal title preferred", trial.container, "JAMA internal medicine")
    check("year", trial.year, "2019")
    check("volume", trial.volume, "179")
    check("issue", trial.issue, "3")
    check("pages", trial.pages, "412-425")
    check("doi", trial.doi, "10.1001/jamainternmed.2018.7624")
    check("pmcid", trial.pmcid, "PMC6439682")
    check("three authors including the collective",
          [a.reference_name() for a in trial.authors],
          ["Chen, W. L.", "O'Brien, M. K.", "Transitional Care Study Group"])
    check("collective author flagged as a group", trial.authors[2].is_group, True)
    check("publication types", trial.publication_types,
          ["Journal Article", "Randomized Controlled Trial"])
    check("mesh terms", trial.mesh_terms, ["Patient Readmission", "Humans"])
    check("medline marked peer reviewed", trial.peer_reviewed, True)
    check("source recorded", trial.source_db, "PubMed/MEDLINE")

    # Structured abstracts must keep their section labels, because the
    # Methods/Results boundary is what design classification reads.
    check("structured abstract keeps labels", "Methods:" in trial.abstract, True)
    check("results section present", "Results:" in trial.abstract, True)

    check("audit records the query", "nurse staffing falls" in audit["query"], True)
    check("audit records total available", audit["total_available"], "1284")
    check("audit records the URL", audit["url"].startswith("https://eutils"), True)
    # The query must be reproducible, so the quality filter is visible in it.
    check("quality filter present in the recorded query",
          "editorial[pt]" in audit["query"], True)


def test_pubmed_detects_retraction_from_comments_corrections() -> None:
    works, _ = run(scholarly.search_pubmed(make_fetcher(), "anything"))
    retracted = works[1]
    check("retraction detected from CommentsCorrections", retracted.retracted, True)
    check("retraction source recorded", "J Example" in retracted.retraction_note, True)
    # An RCT that has been retracted must not grade as Level I.
    level, _ = levels.classify(retracted)
    check("retracted RCT is excluded, not Level I", level, EvidenceLevel.EXCLUDED)


def test_pubmed_handles_medline_date_form() -> None:
    works, _ = run(scholarly.search_pubmed(make_fetcher(), "anything"))
    # "2015 Nov-Dec" has no <Year>; the year must still be recovered.
    check("year from MedlineDate", works[1].year, "2015")


def test_pubmed_level_filter_narrows_the_query() -> None:
    _, audit = run(scholarly.search_pubmed(make_fetcher(), "falls", min_level="II"))
    query = audit["query"]
    # A Level II floor admits I and II and nothing weaker.
    check("Level I filter included", "meta analysis" in query, True)
    check("Level II filter included", "controlled clinical trial" in query, True)
    check("Level IV filter excluded", "cross-sectional studies" in query, False)


def test_pubmed_years_back_filter() -> None:
    _, audit = run(scholarly.search_pubmed(make_fetcher(), "falls", years_back=5))
    check("date filter present", '"last 5 years"[dp]' in audit["query"], True)


def test_ncbi_identification_params_are_sent() -> None:
    fetcher = make_fetcher()
    run(scholarly.search_pubmed(fetcher, "falls"))
    urls = " ".join(entry["url"] for entry in fetcher.log)
    # NCBI's usage policy asks every client to identify itself.
    check("tool param sent", "tool=KochResearchSuite" in urls, True)
    check("email param sent", "email=researcher%40example.org" in urls or
          "email=researcher@example.org" in urls, True)


def test_api_key_is_redacted_from_the_log() -> None:
    fetcher = make_fetcher(api_keys={"ncbi": "secret-key-value"})
    run(scholarly.search_pubmed(fetcher, "falls"))
    urls = " ".join(entry["url"] for entry in fetcher.log)
    # The log feeds the audit document; a key must never reach it.
    check("key not present in the log", "secret-key-value" in urls, False)
    check("key redacted", "api_key=REDACTED" in urls, True)


def test_api_key_raises_the_rate_limit() -> None:
    plain = make_fetcher()
    keyed = make_fetcher(api_keys={"ncbi": "k"})
    # NCBI documents 3/s unauthenticated, 10/s with a key.
    check("unauthenticated interval", round(
        plain.limiter.interval_for("eutils.ncbi.nlm.nih.gov"), 2), 0.34)
    check("keyed interval is faster", round(
        keyed.limiter.interval_for("eutils.ncbi.nlm.nih.gov"), 2), 0.11)


def test_cochrane_search_states_its_limits() -> None:
    works, audit = run(scholarly.search_cochrane_reviews(make_fetcher(), "falls"))
    check("journal restriction applied", "Cochrane Database Syst Rev" in audit["query"], True)
    # The tool must be explicit that this is not the Cochrane Library API.
    check("coverage limit stated", "not full review text" in audit["coverage_note"], True)
    check("CENTRAL limit stated", "CENTRAL" in audit["coverage_note"], True)
    check("source label is honest",
          "via MEDLINE indexing" in audit["source"], True)
    del works


# ---------------------------------------------------------------- Europe PMC


def test_europepmc_search_and_parse() -> None:
    works, audit = run(scholarly.search_europepmc(make_fetcher(), "nurse staffing"))
    check("two records", len(works), 2)
    article = works[0]
    check("doi", article.doi, "10.1001/jamainternmed.2018.7624")
    check("journal from nested journalInfo", article.container, "JAMA internal medicine")
    check("collective author preserved", article.authors[1].is_group, True)
    check("open access url built from pmcid",
          article.open_access_url, "https://europepmc.org/article/PMC/PMC6439682")
    check("audit hit count", audit["total_available"], "4211")


def test_europepmc_flags_preprints_as_not_peer_reviewed() -> None:
    works, _ = run(scholarly.search_europepmc(make_fetcher(), "staffing"))
    preprint = works[1]
    # The project's criteria require peer review, so a preprint must be
    # identifiable rather than blending in with journal articles.
    check("preprint not peer reviewed", preprint.peer_reviewed, False)
    check("preprint work type", preprint.work_type.value, "preprint")
    check("preprint type recorded", "Preprint" in preprint.publication_types, True)


# ------------------------------------------------------------------ Crossref


def test_crossref_search_and_parse() -> None:
    works, audit = run(scholarly.search_crossref(make_fetcher(), "nurse staffing mortality"))
    check("one record", len(works), 1)
    work = works[0]
    check("doi lowercased", work.doi, "10.1016/s0140-6736(13)62631-8")
    check("year from date-parts", work.year, "2014")
    check("named author parsed", work.authors[0].reference_name(), "Aiken, L. H.")
    # A Crossref `name` field (rather than given/family) is a corporate author.
    check("corporate author kept whole", work.authors[1].is_group, True)
    check("corporate author name", work.authors[1].family, "RN4CAST Consortium")
    # Crossref abstracts are JATS fragments; the markup must be stripped.
    check("JATS markup stripped from the abstract",
          work.abstract, "Austerity measures risk adversely affecting outcomes.")
    check("audit total", audit["total_available"], "88")


def test_crossref_doi_lookup() -> None:
    work = run(scholarly.lookup_doi(make_fetcher(), "https://doi.org/10.1000/retracted.1"))
    check("doi lookup returned a work", work is not None, True)
    check("update-to retraction detected", work.retracted, True)
    check("retraction note names the notice DOI",
          "10.1000/notice.1" in work.retraction_note, True)


# ------------------------------------------------------------------ OpenAlex


def test_openalex_search_and_parse() -> None:
    works, audit = run(scholarly.search_openalex(make_fetcher(), "withdrawn study"))
    check("one record", len(works), 1)
    work = works[0]
    check("doi stripped of the resolver prefix", work.doi, "10.1000/retracted.1")
    check("pages assembled from biblio", work.pages, "100-110")
    check("container from primary_location", work.container, "Journal of Example")
    check("open access url", work.open_access_url, "https://example.org/paper.pdf")
    # OpenAlex's explicit retraction flag is the reason it is worth querying.
    check("is_retracted honoured", work.retracted, True)
    check("audit count", audit["total_available"], "512")


# --------------------------------------------------------------- retractions


def test_retraction_check_combines_signals() -> None:
    from app.models import Work
    work = Work(title="A study that was withdrawn", doi="10.1000/retracted.1", year="2015")
    work.ensure_key()
    retracted, detail = run(scholarly.check_retraction(make_fetcher(), work))
    check("retraction found", retracted, True)
    check("Crossref signal named", "Crossref" in detail, True)


def test_retraction_check_logs_negatives_too() -> None:
    from app.models import Work
    clean = Work(title="A sound study", doi="10.1016/S0140-6736(13)62631-8", year="2014")
    clean.ensure_key()
    log = run(scholarly.check_retractions(make_fetcher(), [clean]))
    check("one log entry", len(log), 1)
    # "We checked and found nothing" is a methodological statement; silence is not.
    check("negative result recorded", log[0]["retracted"], "no")
    check("negative detail names the sources checked",
          "Crossref" in log[0]["detail"] and "MEDLINE" in log[0]["detail"], True)
    check("check is timestamped", bool(log[0]["checked_at"]), True)


# --------------------------------------------------------------- open access


def test_unpaywall_lookup_needs_an_email() -> None:
    from app.models import Work
    work = Work(doi="10.1000/xyz")
    with_email = run(scholarly.find_open_access(make_fetcher(), work))
    check("oa url found with an email", with_email, "https://example.org/oa.pdf")

    anonymous = Fetcher(cache_dir=Path(tempfile.mkdtemp()),
                        transport=httpx.MockTransport(handler))
    work2 = Work(doi="10.1000/xyz")
    # Unpaywall's terms require a contact address; skipping the call is the
    # correct behaviour, not sending a request without one.
    check("no call without an email", run(scholarly.find_open_access(anonymous, work2)), "")


# ------------------------------------------------------------- cache & limits


def test_second_identical_request_is_served_from_cache() -> None:
    fetcher = make_fetcher()
    run(scholarly.search_europepmc(fetcher, "identical query"))
    before = len(fetcher.log)
    run(scholarly.search_europepmc(fetcher, "identical query"))
    check("second call logged", len(fetcher.log), before + 1)
    check("second call came from cache", fetcher.log[-1]["cached"], "yes")


def test_cache_respects_ttl_zero() -> None:
    fetcher = make_fetcher()
    run(fetcher.get("https://www.ebi.ac.uk/europepmc/webservices/rest/search",
                    {"query": "x"}, ttl_seconds=0))
    result = run(fetcher.get("https://www.ebi.ac.uk/europepmc/webservices/rest/search",
                             {"query": "x"}, ttl_seconds=0))
    check("ttl of zero bypasses the cache", result.from_cache, False)


def test_failed_response_is_not_cached() -> None:
    fetcher = make_fetcher()
    # A host the mock does not recognise, so it genuinely 404s.
    first = run(fetcher.get("https://unmocked.example.org/nope", {}))
    second = run(fetcher.get("https://unmocked.example.org/nope", {}))
    check("404 returned", first.status, 404)
    # Caching an error would freeze a transient failure into the project.
    check("error not served from cache", second.from_cache, False)


def test_search_failure_is_reported_not_swallowed() -> None:
    def failing(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="service unavailable")

    fetcher = Fetcher(cache_dir=Path(tempfile.mkdtemp()),
                      contact_email="a@b.org",
                      transport=httpx.MockTransport(failing))
    works, audit = run(scholarly.search_europepmc(fetcher, "anything"))
    check("no works on failure", works, [])
    # A search that silently returns nothing looks identical to a topic with no
    # literature, which is the worst possible failure mode here.
    check("failure surfaced in the audit record", "error" in audit, True)
    check("failure names the status", "503" in audit["error"], True)


def test_user_agent_identifies_the_tool_and_contact() -> None:
    fetcher = make_fetcher()
    agent = fetcher.user_agent()
    check("tool named", "KochResearchSuite" in agent, True)
    check("contact included", "researcher@example.org" in agent, True)


def main() -> int:
    tests = [value for name, value in sorted(globals().items())
             if name.startswith("test_") and callable(value)]
    for test in tests:
        test()
    print(f"Retrieval layer: {CHECKS} checks, {len(FAILURES)} failed")
    for failure in FAILURES:
        print(f"  FAIL {failure}")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    raise SystemExit(main())
