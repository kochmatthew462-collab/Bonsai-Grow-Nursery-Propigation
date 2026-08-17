"""
Critical appraisal checklists.

**A licensing note that shapes this whole module.** CASP, JBI, AGREE II, AMSTAR
2, RoB 2 and PRISMA are copyrighted instruments. CASP's checklists are released
under a CC BY-NC-SA licence; JBI's tools, AGREE II and AMSTAR 2 each carry their
own terms, and AGREE II additionally expects users to register. Reproducing
their item text inside a private tool is a licensing question, not a coding one
— so this module does not reproduce it.

What it does instead:

* Each template **names the published instrument it follows** and cites it, so
  the methodology section can state which appraisal framework was used.
* Every question is **written for this tool**, in its own words, covering the
  same methodological domains — bias, sampling, measurement, analysis,
  confounding, ethics, conflicts of interest.
* Where a user wants the exact published wording, the tool points them at the
  instrument rather than shipping a copy. `instrument_url` exists for that.

The practical consequence for the user is worth stating plainly: an appraisal
produced here is *an appraisal following the CASP cohort-study domains*, not
"a completed CASP checklist". If a course or a journal requires the official
instrument, fill in the official form — this output is a working appraisal and
a defensible audit record, not a substitute for a form someone else specified.

Two domains appear in every template regardless of design, because the
project's stated research criteria require them: **institutional ethical
approval** and **funding and conflict-of-interest disclosure**.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from ..models import Appraisal, AppraisalItem, EvidenceLevel, Work

# --------------------------------------------------------------------- shared

_UNIVERSAL_ITEMS = [
    ("ethics",
     "Does the report state that an institutional review board, research ethics "
     "committee or equivalent body approved the study, or explain why approval "
     "was not required?"),
    ("consent",
     "Where human participants were involved, does the report describe how "
     "informed consent or assent was obtained?"),
    ("funding",
     "Are the study's funding sources named, including any commercial sponsor?"),
    ("conflicts",
     "Do the authors disclose competing interests, or state that they have none?"),
    ("reporting",
     "Is the report complete enough that another team could repeat the study — "
     "eligibility rules, setting, dates, measures and analysis all stated?"),
]

_INSTRUMENTS = {
    "systematic-review": {
        "follows": "AMSTAR 2 and the JBI checklist for systematic reviews",
        "citation": (
            "Domains follow AMSTAR 2 (Shea et al., 2017) and the Joanna Briggs "
            "Institute checklist for systematic reviews. Question wording is this "
            "tool's own; consult the published instruments for their exact items."
        ),
        "url": "https://amstar.ca/Amstar-2.php",
        "items": [
            ("question", "Is the review question stated in terms of population, "
                         "intervention or exposure, comparator and outcomes?"),
            ("protocol", "Was a protocol registered or published before the review "
                         "was carried out, and are any departures from it explained?"),
            ("search", "Was the search broad enough — at least two databases, plus "
                       "reference lists or grey literature — and is the full strategy "
                       "reported so it could be re-run?"),
            ("selection", "Were study selection and data extraction each done by "
                          "more than one reviewer, with disagreements resolved in a "
                          "stated way?"),
            ("appraisal", "Was the risk of bias in each included study assessed with "
                          "a named tool, and are the per-study judgements reported?"),
            ("synthesis", "If results were pooled, was the method appropriate to the "
                          "data, and was heterogeneity examined rather than assumed "
                          "away?"),
            ("publication-bias", "Was the possibility of publication or small-study "
                                 "bias investigated and discussed?"),
            ("conclusions", "Do the conclusions follow from the included evidence and "
                            "acknowledge its limitations, rather than overreaching?"),
        ],
    },
    "rct": {
        "follows": "the CASP randomised controlled trial checklist and Cochrane RoB 2",
        "citation": (
            "Domains follow the Critical Appraisal Skills Programme checklist for "
            "randomised controlled trials and the Cochrane risk-of-bias tool "
            "(RoB 2). Question wording is this tool's own; consult the published "
            "instruments for their exact items."
        ),
        "url": "https://casp-uk.net/casp-tools-checklists/",
        "items": [
            ("question", "Does the trial address a clearly focused question, with the "
                         "population, intervention, comparator and outcomes all "
                         "specified?"),
            ("randomisation", "Is the method of generating the allocation sequence "
                              "described, and was it genuinely random rather than "
                              "quasi-random?"),
            ("concealment", "Was the allocation concealed from those enrolling "
                            "participants until assignment happened?"),
            ("blinding", "Were participants, those delivering the intervention and "
                         "those assessing outcomes blinded as far as the design "
                         "allowed, and is any unblinding accounted for?"),
            ("baseline", "Were the groups comparable at baseline on the "
                         "characteristics likely to affect the outcome?"),
            ("fidelity", "Apart from the intervention, were the groups treated alike, "
                         "and is intervention fidelity reported?"),
            ("attrition", "Is participant flow accounted for — how many were "
                          "randomised, followed up and analysed, and is loss to "
                          "follow-up low enough or handled appropriately?"),
            ("analysis", "Were participants analysed in the groups to which they were "
                         "randomised (intention to treat), and is any per-protocol "
                         "analysis presented as secondary?"),
            ("precision", "Are effect estimates reported with confidence intervals "
                          "rather than p values alone, and is the sample size "
                          "justified?"),
            ("outcomes-prespecified", "Do the reported outcomes match those "
                                      "pre-specified in the protocol or registry "
                                      "entry?"),
            ("applicability", "Are the participants, setting and comparator close "
                              "enough to your own context for the result to "
                              "transfer?"),
        ],
    },
    "cohort": {
        "follows": "the CASP cohort study checklist and the JBI checklist for cohort studies",
        "citation": (
            "Domains follow the Critical Appraisal Skills Programme cohort study "
            "checklist and the Joanna Briggs Institute checklist for cohort "
            "studies. Question wording is this tool's own; consult the published "
            "instruments for their exact items."
        ),
        "url": "https://casp-uk.net/casp-tools-checklists/",
        "items": [
            ("question", "Is the research question focused, with the exposure and "
                         "outcome both clearly defined?"),
            ("cohort-recruitment", "Was the cohort recruited in a way that makes it "
                                   "representative of the population of interest?"),
            ("exposure-measurement", "Was exposure measured objectively, using a "
                                     "method unlikely to introduce differential "
                                     "misclassification?"),
            ("outcome-measurement", "Was the outcome measured with a valid and "
                                    "reliable method, applied the same way to "
                                    "exposed and unexposed participants?"),
            ("confounders-identified", "Have the important confounders been "
                                       "identified, and does the list look complete "
                                       "for this question?"),
            ("confounders-handled", "Were confounders accounted for in the design or "
                                    "the analysis, and is the adjustment strategy "
                                    "stated?"),
            ("follow-up-length", "Was follow-up long enough for the outcome to "
                                 "occur?"),
            ("follow-up-completeness", "Was follow-up complete enough, and are those "
                                       "lost to follow-up described and compared with "
                                       "those retained?"),
            ("precision", "Are effect estimates reported with confidence intervals, "
                          "and is precision adequate for the conclusion drawn?"),
            ("applicability", "Do the setting and population resemble yours closely "
                              "enough for the result to apply?"),
        ],
    },
    "case-control": {
        "follows": "the CASP case-control study checklist",
        "citation": (
            "Domains follow the Critical Appraisal Skills Programme case-control "
            "study checklist. Question wording is this tool's own; consult the "
            "published instrument for its exact items."
        ),
        "url": "https://casp-uk.net/casp-tools-checklists/",
        "items": [
            ("question", "Is the question focused, with the outcome and the exposure "
                         "of interest clearly defined?"),
            ("case-definition", "Were cases defined by explicit criteria, applied "
                                "before exposure status was known?"),
            ("case-recruitment", "Were cases recruited in an acceptable way, and is "
                                 "the source population described?"),
            ("control-selection", "Were controls drawn from the same population as "
                                  "the cases, and selected without reference to "
                                  "exposure?"),
            ("exposure-measurement", "Was exposure measured the same way for cases "
                                     "and controls, and is recall bias addressed?"),
            ("confounders", "Were confounders identified and accounted for by "
                            "matching or in the analysis?"),
            ("precision", "Are odds ratios reported with confidence intervals?"),
            ("applicability", "Does the study population resemble yours closely "
                              "enough for the result to inform your question?"),
        ],
    },
    "qualitative": {
        "follows": "the CASP qualitative studies checklist and the JBI qualitative checklist",
        "citation": (
            "Domains follow the Critical Appraisal Skills Programme qualitative "
            "studies checklist and the Joanna Briggs Institute checklist for "
            "qualitative research. Question wording is this tool's own; consult the "
            "published instruments for their exact items."
        ),
        "url": "https://casp-uk.net/casp-tools-checklists/",
        "items": [
            ("aims", "Are the aims of the research stated clearly, and is a "
                     "qualitative approach the right one for them?"),
            ("methodology", "Is the methodology named — phenomenology, grounded "
                            "theory, ethnography, thematic analysis — and does it fit "
                            "the aims?"),
            ("design", "Is the research design justified, including why this way of "
                       "collecting data suits the question?"),
            ("recruitment", "Is the recruitment strategy explained, including why "
                            "these participants were the right ones to approach?"),
            ("data-collection", "Is data collection described in enough detail — "
                                "setting, method, saturation, any changes made during "
                                "the study?"),
            ("reflexivity", "Have the researchers examined their own role, potential "
                            "bias and influence during formulation, data collection "
                            "and analysis?"),
            ("ethics-detail", "Are ethical issues considered in the report itself, "
                              "beyond the fact of committee approval?"),
            ("analysis-rigour", "Is the analysis sufficiently rigorous — an explicit "
                                "process, more than one analyst or a stated audit "
                                "trail, and contradictory data addressed?"),
            ("findings", "Are the findings stated explicitly, with enough participant "
                         "data presented to support each interpretation?"),
            ("value", "Is the contribution of the research discussed in relation to "
                      "existing knowledge and practice, including transferability?"),
        ],
    },
    "cross-sectional": {
        "follows": "the JBI checklist for analytical cross-sectional studies",
        "citation": (
            "Domains follow the Joanna Briggs Institute checklist for analytical "
            "cross-sectional studies. Question wording is this tool's own; consult "
            "the published instrument for its exact items."
        ),
        "url": "https://jbi.global/critical-appraisal-tools",
        "items": [
            ("inclusion", "Are the criteria for inclusion in the sample defined "
                          "clearly?"),
            ("sample-frame", "Is the sampling frame described, and does the sample "
                             "plausibly represent the target population?"),
            ("sample-size", "Is the sample size justified, and is it adequate for the "
                            "analyses reported?"),
            ("response-rate", "Is the response rate reported, and are non-responders "
                              "compared with responders?"),
            ("exposure-measurement", "Were the exposures or predictors measured "
                                     "validly and reliably?"),
            ("outcome-measurement", "Were the outcomes measured validly and "
                                    "reliably, using standard criteria?"),
            ("confounders", "Were confounders identified and dealt with in the "
                            "analysis?"),
            ("analysis", "Was the statistical analysis appropriate to the design and "
                         "the measurement scales used?"),
            ("causal-language", "Does the report avoid causal claims that a "
                                "cross-sectional design cannot support?"),
        ],
    },
    "guideline": {
        "follows": "the AGREE II domains for clinical practice guidelines",
        "citation": (
            "Domains follow AGREE II (Brouwers et al., 2010). Question wording is "
            "this tool's own; AGREE II's own items and its scoring procedure "
            "require use of the official instrument, which asks users to register."
        ),
        "url": "https://www.agreetrust.org/",
        "items": [
            ("scope", "Are the guideline's objectives, clinical questions and target "
                      "population described specifically?"),
            ("stakeholders", "Does the development group include all relevant "
                             "professional groups, and were the views of the target "
                             "population sought?"),
            ("rigour-search", "Are systematic methods used to search for evidence, "
                              "with the search and selection criteria reported?"),
            ("rigour-evidence", "Are the strengths and limitations of the evidence "
                                "described, and is each recommendation linked "
                                "explicitly to supporting evidence?"),
            ("rigour-review", "Was the guideline externally reviewed by experts before "
                              "publication, and is there a stated updating "
                              "procedure?"),
            ("clarity", "Are the recommendations specific, unambiguous, and are "
                        "different management options clearly presented?"),
            ("applicability", "Does the guideline address facilitators and barriers, "
                              "resource implications and monitoring criteria?"),
            ("independence", "Is the funding body's influence on the content "
                             "addressed, and are competing interests of the "
                             "development group recorded?"),
            ("currency", "Is the guideline current enough for your use, given its "
                         "publication date and any stated review date?"),
        ],
    },
    "quasi-experimental": {
        "follows": "the JBI checklist for quasi-experimental studies",
        "citation": (
            "Domains follow the Joanna Briggs Institute checklist for "
            "quasi-experimental (non-randomised experimental) studies. Question "
            "wording is this tool's own; consult the published instrument for its "
            "exact items."
        ),
        "url": "https://jbi.global/critical-appraisal-tools",
        "items": [
            ("causal-clarity", "Is it clear in the study what is the cause and what "
                               "is the effect — that is, does the exposure precede "
                               "the outcome?"),
            ("group-similarity", "Were the comparison groups similar in the "
                                 "characteristics that matter, apart from the "
                                 "intervention?"),
            ("comparable-treatment", "Did the groups receive similar treatment other "
                                     "than the intervention of interest?"),
            ("control-group", "Was there a control group at all, and if not, is a "
                              "pre-post comparison adequate for the claim made?"),
            ("multiple-measurements", "Were outcomes measured both before and after "
                                      "the intervention, in every group?"),
            ("follow-up", "Was follow-up complete, and are differences between groups "
                          "in loss to follow-up described and handled?"),
            ("outcome-measurement", "Were outcomes measured the same way across "
                                    "groups, using reliable methods?"),
            ("analysis", "Was the statistical analysis appropriate, and does it "
                         "account for the non-random assignment?"),
        ],
    },
}

# The design each level and set of publication types most likely calls for.
_DESIGN_SIGNALS: list[tuple[str, tuple[str, ...]]] = [
    ("systematic-review", (r"\bsystematic review\b", r"\bmeta-?analys[ie]s\b",
                           r"\bumbrella review\b", r"\bscoping review\b")),
    ("guideline", (r"\bpractice guideline\b", r"\bclinical guideline\b",
                   r"\bconsensus statement\b", r"\bposition statement\b",
                   r"\brecommendations\b")),
    ("rct", (r"\brandomi[sz]ed controlled trial\b", r"\brandomi[sz]ed clinical trial\b",
             r"\bRCT\b", r"\bplacebo-?controlled\b")),
    ("quasi-experimental", (r"\bquasi-?experimental\b", r"\bnon-?randomi[sz]ed\b",
                            r"\bpre-?post\b", r"\binterrupted time series\b",
                            r"\bcontrolled before-?and-?after\b")),
    ("qualitative", (r"\bqualitative\b", r"\bphenomenolog", r"\bgrounded theory\b",
                     r"\bethnograph", r"\bthematic analysis\b", r"\bfocus group",
                     r"\bsemi-?structured interview", r"\bcontent analysis\b")),
    ("case-control", (r"\bcase-?control\b",)),
    ("cohort", (r"\bcohort\b", r"\blongitudinal\b", r"\bprospective stud",
                r"\bretrospective stud")),
    ("cross-sectional", (r"\bcross-?sectional\b", r"\bsurvey\b", r"\bprevalence stud",
                         r"\bdescriptive stud")),
]


def choose_template(work: Work) -> str:
    """Pick the appraisal template that matches the study's design."""
    haystack = " ".join([
        work.title, work.abstract, " ".join(work.publication_types),
    ]).lower()
    for name, patterns in _DESIGN_SIGNALS:
        for pattern in patterns:
            if re.search(pattern, haystack, re.IGNORECASE):
                return name
    # Fall back on the level, which was itself derived from design signals.
    return {
        EvidenceLevel.LEVEL_I: "systematic-review",
        EvidenceLevel.LEVEL_II: "quasi-experimental",
        EvidenceLevel.LEVEL_III: "cohort",
        EvidenceLevel.LEVEL_IV: "cross-sectional",
        EvidenceLevel.LEVEL_V: "guideline",
    }.get(work.level, "cross-sectional")


def blank_appraisal(work: Work, template: str = "") -> Appraisal:
    """Build an unanswered appraisal for a work.

    Every answer starts at "unclear" rather than "yes". An appraisal that
    defaults to yes and is never reviewed reads, to a faculty reader, exactly
    like one that was done carelessly — because it is indistinguishable from
    one.
    """
    name = template or choose_template(work)
    spec = _INSTRUMENTS.get(name) or _INSTRUMENTS["cross-sectional"]
    items = [
        AppraisalItem(question=question, answer="unclear")
        for _, question in list(spec["items"]) + _UNIVERSAL_ITEMS
    ]
    return Appraisal(
        work_key=work.key,
        instrument=f"{name} domains, following {spec['follows']}",
        instrument_citation=spec["citation"],
        items=items,
        appraised_by="assisted",
        appraised_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )


def item_keys(template: str) -> list[str]:
    spec = _INSTRUMENTS.get(template) or _INSTRUMENTS["cross-sectional"]
    return [key for key, _ in spec["items"]] + [key for key, _ in _UNIVERSAL_ITEMS]


def instrument_url(template: str) -> str:
    spec = _INSTRUMENTS.get(template) or {}
    return spec.get("url", "")


def available_templates() -> list[dict[str, str]]:
    return [
        {"name": name, "follows": spec["follows"], "url": spec["url"],
         "item_count": str(len(spec["items"]) + len(_UNIVERSAL_ITEMS))}
        for name, spec in sorted(_INSTRUMENTS.items())
    ]


def overall_confidence(appraisal: Appraisal) -> tuple[str, str]:
    """Summarise an appraisal into a confidence rating, and explain it.

    The thresholds are this tool's own and are stated on screen, because a
    rating whose derivation is invisible is worse than no rating: a reader
    cannot tell whether "moderate" means anything.

    Any "no" on ethics, consent or conflicts caps the rating at low regardless
    of the rest — those are the items the project's criteria treat as
    threshold requirements, not as points to be traded off.
    """
    yes, gradable = appraisal.score()
    if not gradable:
        return ("very-low", "no items have been answered yet")

    unclear = sum(1 for i in appraisal.items if i.answer == "unclear")
    no_count = sum(1 for i in appraisal.items if i.answer == "no")

    threshold_failures = [
        item for item in appraisal.items
        if item.answer == "no" and _is_threshold_item(item.question)
    ]
    if threshold_failures:
        return (
            "low",
            f"{len(threshold_failures)} threshold item(s) answered no — ethical "
            f"approval, consent or conflict-of-interest disclosure is missing, "
            f"which the project's criteria treat as a requirement rather than a "
            f"score",
        )

    ratio = yes / gradable
    if ratio >= 0.85 and no_count == 0:
        rating = "high"
    elif ratio >= 0.65:
        rating = "moderate"
    elif ratio >= 0.4:
        rating = "low"
    else:
        rating = "very-low"

    return (
        rating,
        f"{yes} of {gradable} items answered yes, {no_count} no, {unclear} "
        f"unclear (thresholds: high ≥85% yes with no 'no'; moderate ≥65%; "
        f"low ≥40%)",
    )


def _is_threshold_item(question: str) -> bool:
    lowered = question.lower()
    return any(
        needle in lowered
        for needle in ("review board", "research ethics", "informed consent",
                       "competing interests", "funding sources")
    )


def finalise(appraisal: Appraisal) -> Appraisal:
    rating, reason = overall_confidence(appraisal)
    appraisal.overall = rating
    if not appraisal.limitations:
        unclear = [i.question for i in appraisal.items if i.answer == "unclear"]
        if unclear:
            appraisal.limitations = (
                f"{len(unclear)} appraisal item(s) remain unclear from the report "
                f"as published: " + "; ".join(q.rstrip("?") for q in unclear[:3])
                + ("; …" if len(unclear) > 3 else "")
            )
    appraisal.overall_reason = reason
    return appraisal
