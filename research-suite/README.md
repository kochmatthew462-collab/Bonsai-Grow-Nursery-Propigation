# Koch Research Suite

A local application that searches evidence-based health-science literature,
screens and appraises it, and writes the results into a **Word document that
actually conforms to APA 7** — plus a **companion document that maps every
sentence of the paper back to the source and page it came from**.

It runs on your own machine at `127.0.0.1`. Nothing is hosted, nothing is
uploaded, and no API key ever leaves the computer.

```bash
cd research-suite
./run.sh          # or run.ps1 on Windows
```

First run makes a virtual environment, installs dependencies, and prints a URL
with a session token in it. Open that URL.

---

## Start here: what this does and does not do

Some of what was asked for is not buildable as stated. Rather than shipping
something that quietly does less than it claims, here is the honest ledger.

| Asked for | Reality |
|---|---|
| Direct API access to CINAHL, PsycINFO, Embase, Cochrane, JBI, Global Health, Scopus | **None of these sells API access to an unaffiliated individual, at any price.** PsycINFO has no API for *anyone*. Automating them through a library proxy violates every one of those licences and can get a hospital library's whole IP range blocked. → The tool makes **citation-file import a first-class path**, so those records flow through the same pipeline. See [Reaching the gated databases](#reaching-the-gated-databases). |
| Grammarly integration | **Not possible by any supported route.** The Text Editor SDK — the only embedding route — was discontinued on 10 January 2024, with no successor. The current developer API is Enterprise/Education-only and returns *scores*, not suggestions, offsets or corrected text. → Self-hosted **LanguageTool** in the pipeline; Grammarly as a manual final pass in Word. See [Grammar and spelling](#grammar-and-spelling). |
| Verify 0% similarity before export | **Not achievable and not desirable.** No legitimate paper scores 0% — reference lists match the original articles byte-for-byte by design, quotations are supposed to match verbatim, and the standard phrasing of the field recurs in thousands of papers. Real journals see 16–19% on average. **0% is the fraud signature**, not the goal. → The tool reports **unattributed verbatim overlap against the sources you actually cited**, with offsets, and blocks export on citation defects. It never prints a percentage. See [What "no plagiarism" can honestly mean](#what-no-plagiarism-can-honestly-mean). |
| Reproduce CASP / JBI / AGREE II checklists | **Depends on the instrument, and the differences are large.** JBI's 2023–25 tools say "unauthorized reproduction prohibited"; COREQ is all-rights-reserved. → The tool implements the same methodological **domains** in its own words, names and cites the instrument it follows, and never reproduces item text. See [Appraisal and licensing](#appraisal-and-licensing). |
| AI-detection gate before export | **Deliberately not built.** Detectors measure perplexity, not authorship, and misclassify non-native-English writing at a high rate (Liang et al., *Patterns*, 2023). Gating on one would fail honest work. → A claim-by-claim provenance ledger instead, which is something a detector cannot give you. |

Everything else — retrieval, deduplication, level-of-evidence classification,
retraction checking, appraisal, evidence matrices, APA 7 formatting, both
documents, the slide deck, the figures — works, and is tested.

---

## The two documents

**The paper** (`*-paper.docx`) is a real APA 7 manuscript: 1-inch margins,
double-spaced throughout, 0.5-inch first-line indents, page number in a header
field on every page, student *or* professional title page, the five heading
levels, hanging-indent reference list on its own page, and tables with
horizontal rules only. 85 automated checks assert this against the generated
OOXML rather than against the builder's return values, because everything that
goes wrong in Word export goes wrong between the API call and the file.

**The companion document** (`*-rationale-and-sources.docx`) is what makes the
paper defensible. Nine sections:

1. Every database searched, with the **exact query string** and the date it ran
2. Screening decisions, with the record counts a PRISMA diagram needs
3. The evidence matrix — one row per study, on a landscape page
4. The appraisal of each study, with the instrument named and the rating derived
5. **The claim-to-source map**: every sentence, its source, the locus in that
   source, the passage relied on, and why that source was chosen
6. Why each study was included, and what was considered and not used
7. Retraction checks — including the negatives, because "we checked 23 sources
   and found none" is a methodological statement and silence is not
8. An AI-use disclosure describing exactly which steps were assisted
9. The reference list again, so the document reads on its own

A slide deck (`*-slides.pptx`) is optional: in-text citations on the slides
themselves, a References slide with hanging indents, and figures with their APA
notes.

---

## Why drafting produces a claim ledger, not prose

The model is never asked to "write a section with citations". It produces a list
of **claims** — one sentence each, bound to the sources supporting it, the locus
within them, the passage relied on, and a rationale. Prose is assembled from the
ledger afterwards, and the citations are inserted mechanically by the tested
citation engine.

That ordering is the whole design:

- **The companion document is a byproduct, not a reconstruction.** Every
  sentence already knows its source.
- **Unsupported sentences cannot hide.** A claim with no source is a visible,
  blockable defect. Written the other way round — prose first, citations found
  afterwards — an unsupported assertion looks exactly like a supported one.
- **Citations cannot be fabricated.** The model may only reference source keys
  from the evidence block it was given, and any key it invents is dropped and
  reported. It is never asked to recall literature, which is the other way
  invented references get in.

The claim ledger is editable by hand, and the drafting step is entirely
optional — the tool is fully useful under a policy that forbids AI-generated
prose.

## Writing in your own voice

Add two or three of your own finished papers on the Settings page. The tool
measures sentence-length mean *and spread*, paragraph length, passive-voice
rate, hedging density, first-person use, punctuation habits, lexical variety and
reading grade, then passes those as targets alongside a representative excerpt
of your own prose. After drafting it shows you where the output drifted from
your profile, rather than asserting a match.

Under about 1,500 words of sample the numbers are noise, and the tool says so
instead of reporting a confident-looking figure from three paragraphs.

What this can and cannot do, plainly: it can match how your sentences are
shaped. It cannot supply your clinical judgement. What makes the output yours is
that you set the question, chose and appraised the sources, and reviewed every
claim.

---

## Sources

**Searched automatically** (11): PubMed/MEDLINE, Europe PMC, Cochrane reviews
via MEDLINE indexing, Crossref, OpenAlex, ERIC, ClinicalTrials.gov, CDC open
data, WHO Global Health Observatory, USPSTF, Healthy People 2030.

Every search records its exact query and is reproduced in the companion
document. A source that fails is **reported, not swallowed** — a search that
silently returns nothing looks identical to a topic with no literature, which is
the worst failure mode here.

### Reaching the gated databases

CINAHL, PsycINFO, Embase, Scopus, the Cochrane Library's full text and CENTRAL,
the JBI EBP Database and Global Health all export RIS. So the workflow is: run
the search in the database's own interface, export, and drop the file on the
Sources tab. RIS, NBIB, BibTeX, EndNote XML and CSV are all parsed, with format
detected from content rather than extension — EBSCO's "Export to RIS" routinely
arrives as `.txt`.

Imported records go through the same deduplication, level classification,
appraisal, matrix and APA formatting as anything retrieved automatically. Their
provenance is recorded as e.g. "CINAHL (export)", so the companion document
never implies the tool queried CINAHL directly.

How much you lose by not having direct access, as engineering estimates:

| Database | Reachable free | Not recoverable |
|---|---|---|
| Cochrane CDSR | ~100% — MEDLINE-indexed and deposited to PMC | nothing material |
| Scopus | ~90–95% of the use case via OpenAlex + Crossref | Scopus-specific citation counts, SciVal |
| CINAHL | ~80–90% of indexed articles are also in MEDLINE | CINAHL subject headings, CINAHL-only journals, care sheets |
| Embase | ~75–85% | **conference abstracts — effectively 0%**, Emtree indexing |
| Cochrane CENTRAL | ~75–90% rebuildable from PubMed + ClinicalTrials.gov | hand-searched and non-indexed trials |
| PsycINFO | ~60–70% | APA Thesaurus terms, books, tests and measures |
| Global Health / CABI | ~50–70% via PubMed + WHO Global Index Medicus | CAB Thesaurus, CABI grey literature |
| JBI EBP Database | ~100% of JBI *reviews* (published in *JBI Evidence Synthesis*) | **Evidence Summaries and Best Practice Sheets — 0%** |

If your review needs conference abstracts or CENTRAL, say so in your methods.
That is a limitation to declare, not one to paper over.

---

## Level of evidence

Classification on the JBI/AACN hierarchy, from publication types where they
exist (PubMed assigns these from the article itself) and from design wording in
the title and abstract otherwise. Every grade carries a **plain-language reason**
that prints in the matrix, so a reader can check it rather than accept it, and
you can override any grade by hand.

Two classifications carry more weight than they look:

- **"Review" is not "systematic review".** PubMed's `Review` publication type
  covers narrative reviews. Software that treats it as Level I inflates the
  apparent strength of an entire matrix, and it is the most common
  misclassification in automated EBP tooling. Here a bare `Review` lands at
  Level V and says why; a review whose abstract identifies it as systematic goes
  to Level I.
- **Editorials, letters and retracted articles are not graded at all.** They get
  "not evidence-based", not Level V, so they cannot pass a minimum-level filter.
  An *ungraded* record also fails the filter, deliberately: it means "read the
  methods and decide", not "include quietly".

Retractions are checked against three independent signals — Crossref retraction
notices, MEDLINE retraction records, and the OpenAlex flag — because no single
one is complete. Citing a retracted trial is one of the few citation errors that
can change a clinical conclusion.

## Appraisal and licensing

Each appraisal follows the methodological domains of a published instrument and
names which one: AMSTAR 2 and JBI for systematic reviews, CASP and Cochrane
RoB 2 for trials, CASP and JBI for cohort, case-control and qualitative designs,
AGREE II for guidelines, JBI for cross-sectional and quasi-experimental designs.

**The question wording is this tool's own.** Those instruments are copyrighted,
and their terms differ sharply — JBI's 2023–25 tools state that unauthorized
reproduction is prohibited; COREQ is all-rights-reserved; CASP is CC BY-NC-SA;
PRISMA 2020, CONSORT and SPIRIT are CC BY 4.0 and *could* be embedded verbatim
if you wanted to carry their licence terms. Rather than ship a mixture of
licences, the tool covers the same domains in original wording and cites the
instrument.

The practical consequence, stated plainly: what you get is *an appraisal
following the CASP cohort-study domains*, not "a completed CASP checklist". If a
course or journal requires the official instrument, complete the official form —
this is a working appraisal and an audit record, not a substitute for a form
someone else specified.

Two domains appear in every template regardless of design, because the stated
research criteria require them: **institutional ethical approval** and **funding
and conflict-of-interest disclosure**. A "no" on either caps the confidence
rating at low regardless of the rest.

---

## What "no plagiarism" can honestly mean

The tool makes a claim it can actually verify: **no unattributed verbatim
overlap with any source this tool retrieved.**

It compares your draft against the titles and abstracts of the sources you
cited, plus any passage you recorded as a quote, using 8-word shingles. Matches
are reported with their length and their source, and classified: a match inside
quotation marks is correct APA; a 20-word unmarked run is a paragraph someone
pasted. Standard academic phrasing is allowlisted, because telling a user to
reword "there was no statistically significant difference between groups" is bad
advice.

This is a better check than a web-wide scan for the failure that actually
happens — a phrase lifted from an abstract during note-taking and never
reworded. A general scanner does not know which twenty papers you were reading.

**Export is blocked** on citation defects, which are unambiguous: a borrowed
claim with no source, a direct quotation with no page or paragraph number, a
citation pointing at a source not in the project, or a citation to a retracted
article. Export is **not** blocked on any similarity threshold, because there is
no defensible number to threshold on.

If you buy a commercial similarity API, the tool will report its index and tell
you to read the matched passages rather than the number. Turnitin does not sell
API access to individuals; if your programme uses it, your institution's portal
is the only way to see the report your faculty will see.

## Grammar and spelling

Point a self-hosted LanguageTool at the app and it checks every claim, returning
errors with offsets and replacement candidates. Citations, DOIs, URLs,
p-values, confidence intervals and sample sizes are masked before checking —
with same-length filler, so the reported offsets stay correct — because a
checker that "fixes" `(Smith et al., 2020)` or `p = .03` is worse than no
checker.

```bash
docker run -d -p 8081:8010 erikvl87/languagetool
```

Then use Grammarly the way it can actually be used: export the `.docx`, open it
in Word with the Grammarly add-in, and accept the suggestions you agree with.
That is the right place for a context-sensitive human-reviewed check anyway.

---

## Figures

Bar, grouped bar, line (incidence and prevalence curves), forest plots of
effect estimates with confidence intervals, and evidence-level distributions —
rendered at 300 dpi and embedded with their APA number, italic title and note.

Three things they get right that generated charts usually do not:

- **Colour is never the only encoding.** Every multi-series figure varies marker
  shape and line style too, and lines carry direct end labels. APA figures get
  printed and photocopied in greyscale.
- **The palette is validated, not chosen by eye** — four hues checked on all
  pairs for colour-vision-deficiency separation and normal-vision separation.
  Past four series the builder refuses and tells you to use small multiples,
  rather than generating an unchecked fifth hue.
- **Ratio measures go on a log axis.** An odds ratio of 0.5 and one of 2.0 are
  the same size of effect in opposite directions; on a linear axis the
  protective half is compressed into a fifth of the width. Forest-plot marker
  *area* is proportional to study weight, not marker width.

Data pulled from CDC datasets and WHO indicators arrives with its licence
attached, and the note is generated from it. This matters: US federal data is
public domain, but **WHO material is CC BY-NC-SA 3.0 IGO**, so a WHO figure
without its attribution line is a figure that must not be published.

---

## Security, honestly

The app binds to `127.0.0.1` and requires a session token generated fresh each
run. Together those stop the two attacks a local service is actually exposed to:
a web page you visit issuing requests to your own machine, and DNS rebinding
(which the `Host` header check defeats — a token alone would not).

**What this does not protect against:** anything already running as your user
account can read the `.env` file, the token and the project data. This is a
single-user desktop application, and its security boundary is your operating
system account, exactly like Word's.

Keys are stored in the OS keychain where one is available, in a `.env` file with
owner-only permissions otherwise. `.env` is git-ignored — and that matters more
than usual here, because this repository publishes a GitHub Pages site from its
own branch, so a committed key would be served as a static file at a guessable
URL. A key that has ever been committed must be rotated; rewriting history does
not unpublish it.

Every logged URL is redacted before it can reach a log or the companion
document, because that document reproduces query URLs so searches can be re-run.

If you set `RESEARCH_SUITE_HOST` to anything other than a loopback address, the
app prints a warning and keeps running — someone genuinely wanting this on a
Tailscale network behind Tailscale's own authentication should be able to. But
the token then becomes the only thing between the internet and your API keys,
and a token in a URL ends up in browser history. Put a real authenticating proxy
in front of it.

---

## Why this is a local app, not a static site

The nursery tracker in this repository is a static site on GitHub Pages, and for
that app it is exactly right: it has nothing to keep secret. This one holds API
keys and needs to call a dozen APIs that send no CORS headers. A key in
front-end JavaScript is a published key, and a browser cannot call those APIs at
all. Both constraints point at the same answer.

---

## How it is put together

```
app/
  main.py            FastAPI app, one endpoint per workflow step
  security.py        localhost binding, session token, Host and Origin checks
  settings.py        keychain / .env secret resolution
  storage.py         one JSON file per project, atomic writes
  models.py          Work, Claim, Appraisal, Extraction, Project
  sources/
    base.py          the single outbound HTTP path: cache, rate limits, redaction
    scholarly.py     PubMed, Europe PMC, Crossref, OpenAlex, Unpaywall, retractions
    gov.py           ERIC, ClinicalTrials.gov, CDC, WHO, USPSTF, Healthy People
    importers.py     RIS, NBIB, BibTeX, EndNote XML, CSV
  evidence/
    levels.py        JBI/AACN classification with printed rationales
    appraisal.py     appraisal domains in original wording, instruments cited
    dedupe.py        DOI → PMID → title+year matching, merge logging
  apa/
    citations.py     APA 7 in-text citations and reference entries, as styled runs
    ooxml.py         page-number fields, running heads, APA table borders
    document.py      the APA 7 manuscript
    assemble.py      claim ledger → prose with citations placed
    audit_document.py  the companion rationale and mapping document
    deck.py          APA-conventional slides
    figures.py       validated-palette figures, forest plots
  writing/
    draft.py         claim-ledger drafting, AI-use disclosure
    style.py         stylometric profiling from your own samples
    integrity.py     verbatim overlap, citation audit, export blockers
    proof.py         LanguageTool integration, the Grammarly answer
  static/            the UI — vanilla JS, no build step, no CDN
tests/               359 checks, all offline
```

## Tests

```bash
bash tests/run_all.sh
```

**Every test runs with no network, no API keys and no credentials.** The
retrieval tests drive the real adapter code against `httpx.MockTransport` serving
recorded response shapes — the same approach the nursery tracker's sync tests
take against Firestore.

| Suite | Checks | What it holds down |
|---|---|---|
| `test_apa_citations.py` | 68 | Every APA 7 rule a tool gets wrong: et al. from the first citation, expanded et al. for clashing author groups, year letters, group-author first use, the 21-author ellipsis, sentence-case conversion that preserves COVID-19 and proper nouns, en-dash page ranges, elided range expansion |
| `test_docx_layout.py` | 85 | Assertions against the saved OOXML: margins, all four font attributes, double spacing, the `PAGE` **field** rather than a literal digit, running head presence by paper type, five distinct heading levels, hanging indents, horizontal-only table borders |
| `test_evidence.py` | 121 | Real CINAHL/Ovid/PubMed/Zotero/Scopus export shapes; `Review` ≠ systematic review; retraction excluded rather than graded; DOI/PMID/title dedupe; conflicting DOIs kept separate; retraction propagating through a merge |
| `test_sources.py` | 85 | Structured-abstract labels preserved, collective authors, `CommentsCorrections` retractions, JATS markup stripped, NCBI identification params sent, **API keys redacted from logs**, failures surfaced rather than swallowed |

---

## What is deliberately not built

- **Automated access to subscription databases.** Not a missing feature — a
  licence violation with real consequences for a hospital library.
- **An AI-detection gate.** See the table at the top.
- **A similarity percentage.** Same.
- **Verbatim copies of copyrighted appraisal instruments.**
- **Cloud sync.** A single-user local tool with JSON files does not need it, and
  it would mean uploading unpublished work to somebody's server.
