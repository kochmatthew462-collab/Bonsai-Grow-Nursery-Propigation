"""
Government and agency sources: ERIC, ClinicalTrials.gov, CDC, WHO, ODPHP, USPSTF.

These serve two different purposes and the distinction matters for how the tool
treats them:

* **Literature and guidance** — ERIC records, USPSTF recommendations, Healthy
  People objectives — become `Work` objects and flow through the normal
  screening, appraisal and citation path.
* **Numeric data** — CDC surveillance datasets, WHO Global Health Observatory
  indicators — become `DataSeries`, which feed the APA figure and table
  builders. This is where a paper's charts should come from: the agency's own
  published figures, cited to the agency, rather than numbers retyped from a
  secondary source.

**Reuse licensing differs sharply between them, and the tool records which
applies.** US federal government works are generally in the public domain, so a
CDC chart can be redrawn and republished freely with attribution. WHO material
is not: it is released under a Creative Commons licence with a
non-commercial/share-alike condition. Every `DataSeries` therefore carries a
`licence` and an `attribution` string, and the figure builder prints the
attribution in the figure note — because a figure whose source note is missing
is a figure that cannot be used.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

from ..models import Author, Work, WorkType
from .base import REGISTRY, Fetcher, SourceSpec

ERIC = "https://api.ies.ed.gov/eric/"
CLINICALTRIALS = "https://clinicaltrials.gov/api/v2/studies"
CDC_SOCRATA = "https://data.cdc.gov"
WHO_GHO = "https://ghoapi.azureedge.net/api"
ODPHP = "https://odphp.health.gov/myhealthfinder/api/v4"
USPSTF = "https://data.uspreventiveservicestaskforce.org/api/recommendations"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class DataSeries:
    """Numeric data ready to become an APA figure or table."""

    title: str
    labels: list[str] = field(default_factory=list)
    values: list[float] = field(default_factory=list)
    unit: str = ""
    series_name: str = ""
    source_label: str = ""
    source_url: str = ""
    licence: str = ""
    attribution: str = ""
    retrieved_at: str = ""
    notes: str = ""

    def apa_note(self) -> str:
        """The figure or table note APA 7 §7.14 and §7.28 require.

        A figure adapted from someone else's data needs its source named in the
        note, and needs a copyright line when the source is not public domain.
        Producing that automatically is the difference between a figure that can
        be submitted and one that cannot.
        """
        parts = []
        if self.attribution:
            parts.append(self.attribution)
        elif self.source_label:
            parts.append(f"Data from {self.source_label}.")
        if self.licence:
            parts.append(self.licence)
        if self.notes:
            parts.append(self.notes)
        return " ".join(parts)


# ======================================================================= ERIC


async def search_eric(
    fetcher: Fetcher, query: str, *, limit: int = 25, peer_reviewed_only: bool = True
) -> tuple[list[Work], dict[str, str]]:
    """ERIC — education research, including health education and nursing
    education. Free API, no key."""
    term = query.strip()
    if peer_reviewed_only:
        term = f'({term}) AND peerreviewed:"T"'
    params = {
        "search": term, "format": "json", "rows": str(min(limit, 200)),
        "fields": ("id,title,author,source,publicationdateyear,description,"
                   "subject,peerreviewed,publicationtype,issn,url,e_issn"),
    }
    response = await fetcher.get(ERIC, params, ttl_seconds=21_600)
    audit = {
        "source": "ERIC (Institute of Education Sciences)", "query": term,
        "url": response.url, "run_at": response.fetched_at or _now(),
        "from_cache": "yes" if response.from_cache else "no",
    }
    if not response.ok or not isinstance(response.json, dict):
        audit["error"] = response.error or f"HTTP {response.status}"
        return ([], audit)

    body = (response.json.get("response") or {})
    docs = body.get("docs") or []
    audit["total_available"] = str(body.get("numFound", len(docs)))
    audit["retrieved"] = str(len(docs))

    works: list[Work] = []
    for doc in docs:
        work = Work(source_db="ERIC", retrieved_at=_now(), query=term)
        work.title = " ".join(str(doc.get("title") or "").split())
        work.container = str(doc.get("source") or "")
        work.year = str(doc.get("publicationdateyear") or "")
        work.abstract = str(doc.get("description") or "")
        work.url = str(doc.get("url") or "")
        work.raw = {"eric_id": doc.get("id")}
        for name in doc.get("author") or []:
            work.authors.append(Author.parse(str(name)))
        work.mesh_terms = [str(s) for s in doc.get("subject") or []]
        types = [str(t) for t in doc.get("publicationtype") or []]
        work.publication_types = types
        work.peer_reviewed = str(doc.get("peerreviewed") or "") == "T"
        work.work_type = (
            WorkType.REPORT if any("report" in t.lower() for t in types)
            else WorkType.JOURNAL_ARTICLE
        )
        if not work.url and doc.get("id"):
            work.url = f"https://eric.ed.gov/?id={doc['id']}"
        work.ensure_key()
        works.append(work)
    return (works, audit)


# ========================================================== ClinicalTrials.gov


async def search_clinical_trials(
    fetcher: Fetcher, query: str, *, limit: int = 20, completed_only: bool = False
) -> tuple[list[Work], dict[str, str]]:
    """ClinicalTrials.gov API v2.

    Registry entries are not peer-reviewed literature, and are marked as such.
    They matter for two things a literature search cannot do: identifying
    completed trials whose results were never published (which is publication
    bias, visible), and checking whether a published trial's reported outcomes
    match the ones it pre-registered.
    """
    params = {
        "query.term": query, "pageSize": str(min(limit, 100)), "format": "json",
        "fields": ("NCTId,BriefTitle,OfficialTitle,OverallStatus,StudyType,"
                   "Phase,EnrollmentCount,StartDate,CompletionDate,"
                   "PrimaryOutcomeMeasure,LeadSponsorName,BriefSummary,"
                   "DesignAllocation,DesignInterventionModel,HasResults,"
                   "ResultsFirstSubmitDate,CompletionDateType"),
    }
    if completed_only:
        params["filter.overallStatus"] = "COMPLETED"

    response = await fetcher.get(CLINICALTRIALS, params, ttl_seconds=86_400)
    audit = {
        "source": "ClinicalTrials.gov (API v2)", "query": query,
        "url": response.url, "run_at": response.fetched_at or _now(),
        "from_cache": "yes" if response.from_cache else "no",
        "coverage_note": (
            "Registry records, not peer-reviewed publications. Useful for "
            "detecting unpublished completed trials and for checking outcome "
            "reporting against pre-registration."
        ),
    }
    if not response.ok or not isinstance(response.json, dict):
        audit["error"] = response.error or f"HTTP {response.status}"
        return ([], audit)

    studies = response.json.get("studies") or []
    audit["total_available"] = str(response.json.get("totalCount", len(studies)))
    audit["retrieved"] = str(len(studies))

    works: list[Work] = []
    for study in studies:
        protocol = study.get("protocolSection") or {}
        identification = protocol.get("identificationModule") or {}
        status = protocol.get("statusModule") or {}
        design = protocol.get("designModule") or {}
        sponsor = protocol.get("sponsorCollaboratorsModule") or {}
        description = protocol.get("descriptionModule") or {}

        nct = str(identification.get("nctId") or "")
        work = Work(
            work_type=WorkType.DATASET, source_db="ClinicalTrials.gov",
            retrieved_at=_now(), query=query, peer_reviewed=False,
        )
        work.title = str(
            identification.get("officialTitle") or identification.get("briefTitle") or ""
        )
        work.container = "ClinicalTrials.gov"
        work.url = f"https://clinicaltrials.gov/study/{nct}" if nct else ""
        work.report_number = nct
        work.abstract = str(description.get("briefSummary") or "")
        work.year = _year(str((status.get("startDateStruct") or {}).get("date") or ""))
        lead = (sponsor.get("leadSponsor") or {}).get("name")
        if lead:
            work.authors = [Author.group(str(lead))]

        allocation = str((design.get("designInfo") or {}).get("allocation") or "")
        enrolment = str((design.get("enrollmentInfo") or {}).get("count") or "")
        overall_status = str(status.get("overallStatus") or "")
        has_results = bool(study.get("hasResults") or status.get("resultsFirstSubmitDate"))

        work.publication_types = ["Clinical trial registry record"]
        if "RANDOMIZED" in allocation.upper():
            work.publication_types.append("Randomized allocation (registered)")
        work.raw = {
            "nct_id": nct, "status": overall_status, "allocation": allocation,
            "enrollment": enrolment, "has_results": "yes" if has_results else "no",
            "study_type": str(design.get("studyType") or ""),
            "phases": ", ".join(str(p) for p in design.get("phases") or []),
        }
        # A completed trial with no posted results is exactly what publication
        # bias looks like, and it is worth surfacing rather than filtering out.
        if overall_status == "COMPLETED" and not has_results:
            work.raw["flag"] = (
                "Completed with no results posted — a possible source of "
                "publication bias worth noting in the review."
            )
        work.ensure_key()
        works.append(work)
    return (works, audit)


# ================================================================ CDC Socrata


async def search_cdc_datasets(
    fetcher: Fetcher, query: str, *, limit: int = 20
) -> tuple[list[Work], dict[str, str]]:
    """Find CDC open datasets by keyword.

    Dataset discovery only — pulling the rows is `fetch_cdc_series`, because the
    column names differ per dataset and cannot be guessed.
    """
    params = {"q": query, "limit": str(min(limit, 100)), "only": "dataset",
              "domains": "data.cdc.gov", "search_context": "data.cdc.gov"}
    response = await fetcher.get("https://api.us.socrata.com/api/catalog/v1",
                                 params, ttl_seconds=86_400)
    audit = {
        "source": "CDC open data (data.cdc.gov)", "query": query,
        "url": response.url, "run_at": response.fetched_at or _now(),
        "from_cache": "yes" if response.from_cache else "no",
    }
    if not response.ok or not isinstance(response.json, dict):
        audit["error"] = response.error or f"HTTP {response.status}"
        return ([], audit)

    results = response.json.get("results") or []
    audit["total_available"] = str(
        (response.json.get("resultSetSize") or len(results)))
    audit["retrieved"] = str(len(results))

    works: list[Work] = []
    for entry in results:
        resource = entry.get("resource") or {}
        work = Work(
            work_type=WorkType.DATASET,
            authors=[Author.group("Centers for Disease Control and Prevention")],
            source_db="CDC open data", retrieved_at=_now(), query=query,
            peer_reviewed=None,
        )
        work.title = str(resource.get("name") or "")
        work.abstract = str(resource.get("description") or "")
        work.year = _year(str(resource.get("updatedAt") or ""))
        work.url = str((entry.get("permalink") or entry.get("link") or ""))
        work.publisher = "Centers for Disease Control and Prevention"
        work.report_number = str(resource.get("id") or "")
        work.raw = {
            "dataset_id": resource.get("id"),
            "columns": [str(c) for c in resource.get("columns_field_name") or []][:40],
            "licence": "US federal government work — generally public domain",
        }
        work.ensure_key()
        works.append(work)
    return (works, audit)


async def fetch_cdc_series(
    fetcher: Fetcher,
    dataset_id: str,
    label_column: str,
    value_column: str,
    *,
    where: str = "",
    order: str = "",
    limit: int = 200,
    title: str = "",
    unit: str = "",
) -> DataSeries | None:
    """Pull one series out of a CDC dataset, ready to chart.

    Column names must be supplied because they differ per dataset — the UI shows
    the column list from `search_cdc_datasets` so the user can pick, rather than
    the tool guessing and silently charting the wrong field.
    """
    params = {
        "$select": f"{label_column},{value_column}",
        "$limit": str(min(limit, 5000)),
    }
    if where:
        params["$where"] = where
    params["$order"] = order or label_column

    response = await fetcher.get(
        f"{CDC_SOCRATA}/resource/{dataset_id}.json", params, ttl_seconds=86_400)
    if not response.ok or not isinstance(response.json, list):
        return None

    labels: list[str] = []
    values: list[float] = []
    for row in response.json:
        label = str(row.get(label_column, "")).strip()
        raw_value = row.get(value_column)
        if not label or raw_value in (None, ""):
            continue
        try:
            values.append(float(str(raw_value).replace(",", "")))
            labels.append(label)
        except ValueError:
            continue

    if not values:
        return None
    return DataSeries(
        title=title or f"{value_column.replace('_', ' ').title()} by "
                       f"{label_column.replace('_', ' ')}",
        labels=labels, values=values, unit=unit,
        series_name=value_column.replace("_", " "),
        source_label="Centers for Disease Control and Prevention",
        source_url=f"https://data.cdc.gov/d/{dataset_id}",
        licence="Public domain (US federal government work).",
        attribution=(
            f"Data from the Centers for Disease Control and Prevention "
            f"(dataset {dataset_id}), retrieved {date_only(_now())}."
        ),
        retrieved_at=_now(),
    )


# ==================================================================== WHO GHO


async def search_who_indicators(
    fetcher: Fetcher, query: str, *, limit: int = 25
) -> list[dict[str, str]]:
    """Find WHO Global Health Observatory indicators by name."""
    response = await fetcher.get(f"{WHO_GHO}/Indicator", {}, ttl_seconds=604_800)
    if not response.ok or not isinstance(response.json, dict):
        return []
    needle = query.lower()
    matches = [
        {"code": str(item.get("IndicatorCode") or ""),
         "name": str(item.get("IndicatorName") or "")}
        for item in response.json.get("value") or []
        if needle in str(item.get("IndicatorName") or "").lower()
    ]
    return matches[:limit]


async def fetch_who_series(
    fetcher: Fetcher,
    indicator_code: str,
    *,
    country: str = "",
    title: str = "",
    limit: int = 200,
) -> DataSeries | None:
    """Pull a WHO GHO indicator as a time series.

    The licence line is not optional here: WHO content is released under a
    Creative Commons Attribution-NonCommercial-ShareAlike licence, not into the
    public domain, so a figure built from it must carry the attribution. The
    figure builder prints `apa_note()` for exactly this reason.
    """
    params: dict[str, str] = {"$top": str(min(limit, 1000))}
    if country:
        params["$filter"] = f"SpatialDim eq '{country.upper()}'"
    response = await fetcher.get(f"{WHO_GHO}/{indicator_code}", params,
                                 ttl_seconds=604_800)
    if not response.ok or not isinstance(response.json, dict):
        return None

    rows = response.json.get("value") or []
    points: list[tuple[str, float]] = []
    for row in rows:
        year = str(row.get("TimeDim") or "")
        value = row.get("NumericValue")
        if not year or value in (None, ""):
            continue
        try:
            points.append((year, float(value)))
        except (TypeError, ValueError):
            continue
    if not points:
        return None
    points.sort(key=lambda kv: kv[0])

    return DataSeries(
        title=title or f"WHO indicator {indicator_code}"
                       + (f" — {country.upper()}" if country else ""),
        labels=[p[0] for p in points], values=[p[1] for p in points],
        series_name=indicator_code,
        source_label="World Health Organization Global Health Observatory",
        source_url=f"https://www.who.int/data/gho/data/indicators",
        licence=("Reproduced from WHO Global Health Observatory data, which is "
                 "licensed CC BY-NC-SA 3.0 IGO. Check that your intended use "
                 "meets the non-commercial and share-alike conditions."),
        attribution=(
            f"Data from the World Health Organization Global Health Observatory "
            f"(indicator {indicator_code}), retrieved {date_only(_now())}."
        ),
        retrieved_at=_now(),
    )


# ====================================================================== USPSTF


async def search_uspstf(
    fetcher: Fetcher, query: str, *, limit: int = 25
) -> tuple[list[Work], dict[str, str]]:
    """USPSTF recommendations — Level V clinical guidance, public domain."""
    response = await fetcher.get(USPSTF, {"format": "json"}, ttl_seconds=604_800)
    audit = {
        "source": "US Preventive Services Task Force (AHRQ)", "query": query,
        "url": response.url, "run_at": response.fetched_at or _now(),
        "from_cache": "yes" if response.from_cache else "no",
    }
    if not response.ok:
        audit["error"] = response.error or f"HTTP {response.status}"
        return ([], audit)

    payload = response.json
    entries = payload if isinstance(payload, list) else (
        (payload or {}).get("specificRecommendations")
        or (payload or {}).get("recommendations") or []
    )
    needle = query.lower()
    works: list[Work] = []
    for entry in entries:
        title = str(entry.get("title") or entry.get("topic") or "")
        text = " ".join(str(v) for v in entry.values() if isinstance(v, str))
        if needle and needle not in text.lower():
            continue
        work = Work(
            work_type=WorkType.GUIDELINE,
            authors=[Author.group("U.S. Preventive Services Task Force")],
            title=title, year=_year(str(entry.get("date") or entry.get("year") or "")),
            container="U.S. Preventive Services Task Force",
            publisher="Agency for Healthcare Research and Quality",
            url=str(entry.get("url") or ""),
            abstract=str(entry.get("text") or entry.get("clinical") or ""),
            source_db="USPSTF (AHRQ)", retrieved_at=_now(), query=query,
            publication_types=["Practice Guideline"], peer_reviewed=None,
        )
        work.raw = {"grade": str(entry.get("grade") or ""),
                    "licence": "Public domain (US federal government work)"}
        work.ensure_key()
        works.append(work)
        if len(works) >= limit:
            break
    audit["retrieved"] = str(len(works))
    return (works, audit)


# ====================================================== Healthy People 2030


async def search_healthy_people(
    fetcher: Fetcher, query: str, *, limit: int = 25
) -> tuple[list[Work], dict[str, str]]:
    """Healthy People 2030 objectives — national public-health targets.

    Cited as agency guidance (Level V). The endpoint shape has changed more than
    once, so a failure here is reported rather than raised: this is a
    supplementary source, and a paper should not fail to build because a
    government site was reorganised.
    """
    response = await fetcher.get(
        f"{ODPHP}/topicsearch.json", {"keyword": query}, ttl_seconds=604_800)
    audit = {
        "source": "Healthy People 2030 / ODPHP", "query": query,
        "url": response.url, "run_at": response.fetched_at or _now(),
        "from_cache": "yes" if response.from_cache else "no",
    }
    if not response.ok or not isinstance(response.json, dict):
        audit["error"] = (
            f"{response.error or f'HTTP {response.status}'} — the ODPHP endpoint "
            f"has been reorganised more than once; check "
            f"https://health.gov/our-work/national-health-initiatives/"
            f"healthy-people for the current API."
        )
        return ([], audit)

    resources = (((response.json.get("Result") or {}).get("Resources") or {})
                 .get("Resource") or [])
    works: list[Work] = []
    for entry in resources[:limit]:
        work = Work(
            work_type=WorkType.WEBPAGE,
            authors=[Author.group(
                "Office of Disease Prevention and Health Promotion")],
            title=str(entry.get("Title") or ""),
            year=_year(str(entry.get("LastUpdate") or "")),
            container="Healthy People 2030",
            publisher="U.S. Department of Health and Human Services",
            url=str(entry.get("AccessibleVersion") or ""),
            abstract=" ".join(re.sub(r"<[^>]+>", " ",
                                     str(entry.get("Categories") or "")).split()),
            source_db="Healthy People 2030", retrieved_at=_now(), query=query,
            publication_types=["Government publication"], peer_reviewed=None,
        )
        work.raw = {"licence": "Public domain (US federal government work)"}
        work.ensure_key()
        works.append(work)
    audit["retrieved"] = str(len(works))
    return (works, audit)


# ------------------------------------------------------------------ utilities


def _year(value: str) -> str:
    match = re.search(r"(1[5-9]\d{2}|20\d{2})", value or "")
    return match.group(1) if match else ""


def date_only(timestamp: str) -> str:
    return (timestamp or "")[:10]


# ------------------------------------------------------------------- registry

REGISTRY.register(SourceSpec(
    key="eric", label="ERIC (education research)", kind="api",
    discipline="Health education and nursing education",
    docs="https://eric.ed.gov/?api",
    note="Free, no key. Peer-review filter available.",
    search=search_eric,
))
REGISTRY.register(SourceSpec(
    key="clinicaltrials", label="ClinicalTrials.gov", kind="api",
    discipline="Clinical trials registry",
    docs="https://clinicaltrials.gov/data-api/api",
    note=("Free, no key. Registry records, not peer-reviewed articles — used to "
          "spot unpublished completed trials and outcome-reporting changes."),
    search=search_clinical_trials,
))
REGISTRY.register(SourceSpec(
    key="cdc-data", label="CDC open data", kind="api",
    discipline="US public health surveillance",
    docs="https://dev.socrata.com/",
    note="Free. Public domain, so figures may be redrawn with attribution.",
    search=search_cdc_datasets,
))
REGISTRY.register(SourceSpec(
    key="uspstf", label="USPSTF recommendations (AHRQ)", kind="api",
    discipline="Preventive services guidance",
    docs="https://www.uspreventiveservicestaskforce.org/apps/",
    note=("Free but approval-gated: request access from uspstfpda@ahrq.gov "
          "before the endpoint will answer. The recommendations' own copyright "
          "permits verbatim reproduction with citation but forbids reproducing "
          "them with changes — so quote a recommendation, do not paraphrase it. "
          "Clinical guidance, Level V on the hierarchy."),
    search=search_uspstf,
))
REGISTRY.register(SourceSpec(
    key="healthy-people", label="Healthy People 2030 (ODPHP)", kind="api",
    discipline="US public health policy objectives",
    docs="https://health.gov/our-work/national-health-initiatives/healthy-people",
    note="Free. Endpoint has moved before; failures are reported, not fatal.",
    search=search_healthy_people,
))
REGISTRY.register(SourceSpec(
    key="who-gho", label="WHO Global Health Observatory", kind="api",
    discipline="Global health indicators (numeric data)",
    docs="https://www.who.int/data/gho/info/gho-odata-api",
    note=("Free, no key. Numeric indicators for figures. Licensed CC BY-NC-SA "
          "3.0 IGO — not public domain, so attribution is required and "
          "commercial reuse is restricted."),
))

# --------------------------------------------- databases with no API to offer

# Registered so the UI can list them honestly rather than leaving the user to
# discover the gap. Each says what the actual route is.
for key, label, discipline, note in [
    ("cinahl", "CINAHL (EBSCOhost)", "Nursing and allied health",
     "No API for individuals. Search in CINAHL, export to RIS, then import."),
    ("psycinfo", "PsycINFO (APA)", "Behavioural and mental health",
     "No individual developer API. Search via EBSCO or Ovid, export RIS, import."),
    ("embase", "Embase (Elsevier)", "Biomedicine and pharmacology",
     "Subscription API only. Search in Embase, export RIS, import."),
    ("scopus", "Scopus (Elsevier)", "All disciplines",
     "A free key exists but full records need institutional entitlement. "
     "CSV or RIS export and import is the reliable route."),
    ("cochrane-full", "Cochrane Library full text and CENTRAL", "Clinical medicine",
     "No API. Review records reach this tool via MEDLINE; for full text and "
     "CENTRAL, export RIS from the Cochrane Library and import."),
    ("jbi", "JBI EBP Database", "Nursing and allied health",
     "Subscription via Ovid/Lippincott, no API. Export and import."),
    ("global-health", "Global Health (CABI)", "International public health",
     "Subscription, no API. Export and import."),
    ("trip", "TRIP Database", "Evidence-based practice",
     "API available to Pro subscribers only. Export and import."),
]:
    REGISTRY.register(SourceSpec(
        key=key, label=label, kind="import-only", discipline=discipline, note=note,
    ))
