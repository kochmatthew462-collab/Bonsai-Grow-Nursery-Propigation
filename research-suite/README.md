# Koch Clinical Suite

Two tools that share a shell, a session token and a stylesheet, and nothing else.

**Research & writing.** Searches evidence-based health-science literature, screens
and appraises it, and writes the results into a **Word document that actually
conforms to APA 7** — plus a **companion document that maps every sentence of the
paper back to the source and page it came from**.

**Clinical charting.** A defensible-documentation composer for bedside and
advanced-practice nurses: an SBAR-SOAP note builder, a head-to-toe assessment with
charting by exception, 23 scoring instruments, an objective-language checker that
works like a spell-checker, and the workflow interlocks that refuse to save a note
missing the thing that matters. **It is not an EHR and not the legal medical
record** — see [The charting tab](#the-charting-tab) before using it, because that
distinction changes how it behaves.

Both run on your own machine at `127.0.0.1`. Nothing is hosted, nothing is
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
| A charting tab that leaves a nurse "100% covered" in litigation | **No document guarantees an outcome.** A nurse who did the right thing can still be named; one who documented perfectly can still be found to have breached a standard of care. → The tool structures the five things that actually go missing under pressure — observation, impression, action, **notification**, re-evaluation — and refuses to save a note that drops the one that matters. See [The charting tab](#the-charting-tab). |
| Auto-suggest an ESI triage level from vitals and chief complaint | **This is clinical decision support and it would be unsafe.** A triage acuity assigned by a tool is also indefensible in a deposition. → The tool walks the four published decision points *you* answer, computes what the algorithm yields, shows the working, and displays the danger-zone thresholds so your judgement is informed rather than replaced. |
| Reproduce Braden, Morse, Wong-Baker FACES, CAM-ICU, FLACC, CPOT, ESI, APACHE II | **Copyrighted, and FACES is a trademark whose artwork is licensed.** A subtly paraphrased near-copy would be worse than either extreme: it looks like the instrument while scoring something slightly different. → Scoring arithmetic and published thresholds implemented, item wording written fresh, no artwork reproduced, every rights holder named on the Reference screen. |
| A charting tool that holds the patient's details | **Deliberately impossible.** There is no field for a name, MRN or date of birth. Most hospitals prohibit PHI on a personal device and the HIPAA finding lands on the nurse. → Encounters are identified by bed or room; free text is scanned for identifiers with one-click redaction; purge is on every screen. |

Everything else — retrieval, deduplication, level-of-evidence classification,
retraction checking, appraisal, evidence matrices, APA 7 formatting, both
documents, the slide deck, the figures — works, and is tested.

---

## The charting tab

A second tab, for composing nursing documentation. Everything below it was asked
for; three things were added because they change whether the tool is safe to use
at all, and they come first.

### Read this before the feature list

**It is not an EHR and it is not the legal medical record.** Your hospital's chart
is. This tab produces text you compose here and then **transcribe into that
record**. That is not a disclaimer to scroll past — it changes how the tool
behaves:

- A second record that disagrees with the chart is a weapon for the other side.
  Plaintiff's counsel subpoenas the nurse's own notes, finds a timestamp that
  differs from the EHR by ten minutes, and spends an afternoon on it. So each note
  tracks whether it has been transcribed, the tool nags until it has, the export
  prints untranscribed notes **first and marked**, and the handoff builder calls
  them out.
- Where timing *is* the standard of care — sepsis bundles, stroke windows,
  restraint checks, blood administration — the EHR timestamps govern.
- It is not a downtime form. If the chart is down, your unit has a downtime
  procedure and paper forms, and those are the legal record during a downtime.

Where it genuinely helps: it gives you somewhere to compose a hard note carefully
— an escalation, a refusal, a fall, a restraint episode — with the language check
and the completeness interlocks in front of you, *before* you commit words to a
record you cannot take back.

**It is built to hold no protected health information.** There is **no field for a
patient name, medical record number or date of birth** — not an optional one, not
a discouraged one. An encounter is a bed or room label plus optional initials, and
the label itself is scanned before it is accepted. Free text is scanned for the
identifiers that leak anyway (record numbers, dates of birth, phone numbers,
addresses, "Mr./Mrs. Surname") with one-click redaction. Purge is on every screen.
Most hospitals prohibit PHI on a personal device and the HIPAA finding lands on
the nurse, not the unit.

**Scores are computed and shown; they never direct care.** Every scale returns the
published band and what the instrument associates with it. None returns an action.

### What "100% covered if a patient sues" can actually mean

Nothing guarantees an outcome. A nurse who did everything right can still be
named; a nurse who documented perfectly can still be found to have breached a
standard of care. What good documentation does is narrower and more valuable: it
makes the record of your reasoning survive four years and a hostile reading.

The defensible note shows five things — what you observed in objective terms, what
you concluded, what you did, **who you told, when, by what means and what they
said**, and what happened when you looked again. Every interlock in the module
exists because one of those five is the one that goes missing under pressure.

### The note composer

SBAR crossed with SOAP, because SBAR is built for a phone call and SOAP is built
for a chart, and a shift note has to do both:

| Section | Holds |
|---|---|
| **S** | the patient's own words, verbatim — the one part of a note that cannot be characterised as your opinion |
| **B/O** | vitals, head-to-toe findings, pertinent labs, scored scales |
| **A** | your clinical impression and the risk you identified — the only section where interpretation belongs |
| **R/P** | interventions with route, dose and site; the provider notification; the re-evaluation; what is still pending |

The order matters more than the labels: observation before impression is what
makes a note read as an assessment rather than a conclusion looking for support.

### Head to toe, with charting by exception

Eight systems, 57 elements. Marking a system "within defined limits" **prints the
full defined-limits statement into the note, verbatim**, because "Neuro WDL" on
its own is worth nothing in a deposition — the question is always *what did you
actually check*. A system can be WDL with exceptions, which renders as "within
defined limits except …". A system that was not assessed is recorded as **not
assessed, with a reason**; there is no third state, because a blank system and a
skipped system look identical in a chart and only one is defensible.

### 23 scoring instruments

Braden, Morse, Caprini, GCS, NIHSS, RASS, CAM, CAM-ICU, NRS, Wong-Baker FACES,
FLACC, CPOT, CIWA-Ar, COWS, qSOFA, MEWS, NEWS2, SOFA, APACHE II, PEWS, PAT,
Lund-Browder, ESI.

Five of them are implemented carefully because the obvious implementation is
quietly wrong:

- **GCS** — an intubated patient's verbal response is *not* 1. Scoring it that way
  makes an alert patient look obtunded. Untestable components are charted as
  untestable and the total is reported as a floor, not a GCS.
- **CAM / CAM-ICU** — the algorithm is features 1 **and** 2 plus 3 **or** 4, not a
  sum. Three features present without inattention is negative, and a "count the
  features" implementation gets that backwards.
- **Lund-Browder** — age-banded, because a newborn's head is ~19% of body surface
  and an adult's is 7%. The rule of nines overestimates burn size in small
  children, which then overestimates the fluid they are given.
- **ESI** — the specification asked for a level auto-suggested from vitals and
  chief complaint. That is clinical decision support, it is wrong often enough to
  be dangerous, and a triage level a tool assigned is indefensible in a
  deposition. Instead it walks the four published decision points you answer,
  computes the level the algorithm yields, **shows the working**, and displays the
  danger-zone thresholds so your answer to decision point D is informed rather
  than remembered.
- **APACHE II** — implemented, and labelled as what it is: a 24-hour
  worst-value cohort mortality score, not a bedside or shift assessment.

**On copyright.** Braden, Morse, FLACC, CPOT, CAM, CAM-ICU, ESI, APACHE II and
NEWS2 are copyrighted, and Wong-Baker FACES is a registered trademark whose
artwork is licensed. Reproducing their item wording would be infringement, and
shipping a subtly paraphrased version would be worse — it would look like the
instrument while scoring something slightly different. So the tool implements the
**scoring arithmetic and the published thresholds** (facts about an instrument,
not expression), with item wording **written fresh**, no artwork reproduced, the
instrument cited, and a licensing register on the Reference screen naming every
rights holder. Use your unit's licensed copy for the definitions.

### The objective language filter

A spell-checker for legally dangerous wording: 24 rules across nine categories,
returning character offsets and suggested replacements so the flagged text can be
underlined in place.

**The one subtlety that makes it usable: quoted speech is exempt.** `Patient
stated, "I'm so angry I could scream"` is *excellent* documentation — the
subjective word belongs to the patient, is attributed, and is exactly what a chart
should preserve. A checker that flagged "angry" there would train the nurse to
stop quoting patients, which is the opposite of what you want. So quotation marks
are found first and every rule skips what is inside them, and the filter actively
*suggests* quoting where speech is reported indirectly.

| Category | Example flagged | What it asks for instead |
|---|---|---|
| Judgmental | "non-compliant", "refused" | "Patient declined the 0900 metoprolol. Educated on the risk of rebound hypertension. Verbalised understanding and continued to decline. Dr. Osei notified at 0915." |
| Emotional | "aggressive", "drunk", "agitated" | "Shouting, pacing the room, struck the bedside table with an open hand. Strong odour of alcohol on the breath. Speech slurred." |
| Assumptive | "appears", "seems", **"sleeping"** | "Lying in bed, eyes closed, respirations regular and unlaboured at 16, roused to light touch." A patient charted as sleeping who was in fact unresponsive is a case that settles. |
| Vague | "ate well", "tolerated well", "per protocol", "frequently" | "Consumed 80% of the lunch tray." "Repositioned at 2000, 2200, 0000, 0200." "Per the adult sepsis order set" — a protocol you did not name is one nobody can confirm you followed. |
| Vague | **"MD aware"** | The weakest sentence in nursing documentation and the first thing counsel looks for. Use the notification block: time, name, method, response. |
| Stigmatising | "drug-seeker", "frequent flyer", "malingering" | The category with the best evidence of downstream harm, and indefensible if the patient reads their record — which they are entitled to do. |
| Wrong document | "short staffed", "no help" | Moved to the shift assignment record, where it protects you, rather than a patient's chart, where it reads as an excuse and hands the plaintiff a theory. |
| Dosing notation | "1.0 mg", ".5 mg", "10 U", "q.d.", "MS", "cc", "@" | The Joint Commission and ISMP do-not-use lists — the notations with documented death and injury cases behind them. |
| Liability / privacy | fault, blame, another patient, incident reports | Hard blocks. See below. |

### The interlocks

Six blocks, and no more. An interlock that fires on a routine note teaches the
nurse to click past interlocks, and then the one that mattered gets clicked past
too.

1. **Critical vitals with no provider notification.** Crossing a threshold (HR
   >130, SBP <90, MAP <65, SpO₂ <90 and nine others) disables Save until the
   notification block has a time, a name, a method and a response — or an
   escalation instead.
2. **A paediatric medication with no weight in kilograms.** A
   pounds-for-kilograms substitution is a 2.2-fold overdose. Triggered by the
   paediatric setting *or* by an age band like "8 y" on an adult unit.
3. **An incident-report reference**, plus the other three never-in-a-chart items:
   another patient, blame directed at a named colleague, and an admission of
   fault. The error message is the one specified: *do not reference incident
   reports in the clinical chart; document only the clinical facts of the event.*
4. **A copy-forward that was not updated** — identical text to the previous note
   of the same kind with unchanged vitals. A shift of byte-identical notes
   establishes that none of them describes an actual assessment.
5. **An event time in the future.** Late is fine and gets labelled; early is the
   shape of a pre-signed assessment.
6. **A correction with no reason.**

**Blocks 1, 2, 4 and 6 are overridable with a typed reason**, and the override is
written into the note and the audit trail. This is deliberate: a tool that cannot
be overridden gets worked around, and a nurse in a genuine emergency has to be
able to save now and finish in four minutes. A recorded override showing a person
deciding under pressure is a **stronger** artefact than a block that got bypassed.
Blocks 3 and 5 have no override, because there is no clinical circumstance in
which those words belong in a chart and because the clock does not negotiate.

**The chain of command.** When a notification records no response, or no new
orders while the patient is still unstable, the tool names the next rung — charge
nurse, rapid response, attending, nursing supervisor — with the reason it is the
next rung. Nothing is auto-escalated: the tool prompts, the nurse decides, and the
record shows which.

**Closed loops.** Twelve triggers open a reassessment with its own window: an
analgesic 30 minutes, a pressor titration 15, a blood product 15, naloxone 15
(reversal agents are shorter-acting than what they reverse), insulin 60. An
overdue loop is the tab's main nag, and closing it late is a labelled late entry
rather than a quiet edit.

### Timestamps, corrections and the audit chain

- **Documentation time is the server clock and no caller can set it.** Event time
  is yours. There is no field, header or parameter that moves the first one.
- **Over 60 minutes' gap auto-tags `[LATE ENTRY]`** with both times printed. That
  is the correct way to document something recalled later, and it reads far better
  than a timestamp that does not match the medication scanner.
- **Nothing is overwritten.** Corrections append: the original text is kept, a
  reason is required, and the export prints the superseded text **struck through
  and still legible** — exactly what a single line through an error on a paper
  chart does. A record that shows what it used to say is trustworthy; one that
  silently shows only current text invites the question of what it said before.
- **The audit trail is hash-chained.** Each event carries its predecessor's
  digest, so an altered event and a deleted event are separately detectable and
  the verification says which. This is not tamper-*proof* — nothing on your own
  disk is — and the tool says so rather than implying otherwise.

### Specialty modules

Not four note formats; the composer and the assessment are the same everywhere. Each
module adds the structured block that setting documents badly:

- **Emergency** — ABCDE primary survey, secondary survey, and **time to
  intervention** as fields rather than something a reviewer reconstructs from
  scattered timestamps. Includes *the exact time the provider was at the bedside*,
  which is a different fact from when they were paged and is the one that gets
  asked about. Reassessment after every intervention.
- **Intensive care** — haemodynamics with the MAP source named (a cuff MAP and an
  arterial MAP are not interchangeable when you are titrating to one), the
  line-drain-airway register with insertion dates and a *current* indication, and
  the **titration block**: drug, previous rate, new rate, the parameter, **the
  reading that prompted the change**, and the response. "Norepinephrine increased
  to 8 mcg/min" documents an action; "increased by 2 mcg/min to maintain a MAP
  above 65, MAP was 58" documents nursing judgement, and only the second defends
  the nurse who titrated.
- **Pediatrics** — weight in kilograms with how it was obtained, the hard stop,
  age-normed observations with the chart used, and **who was at the bedside** by
  relationship (consent, education and any supervision allegation turn on it).
- **Medical-surgical** — the assignment and staffing record, rounding times,
  prevention measures already in place, and discharge teaching recorded as
  **teach-back** rather than "verbalised understanding".

### Time-critical bundles

Sepsis (SEP-1), stroke and STEMI, because they cut across settings. Each element
carries its published target and computes the interval actually achieved,
including across midnight.

Two details worth calling out. If **time zero** is not recorded, *no* interval in
the sepsis bundle can be computed or evidenced, and the tool says exactly that
rather than showing plausible numbers. And the stroke bundle anchors on **arrival,
not last known well** — last known well sets the treatment window, but every
door-to-imaging target runs from arrival, and measuring door-to-CT from last known
well would report a compliant department as non-compliant.

### Macros, handoff and export

Six macro templates — chain of command, refusal/AMA, education with teach-back,
restraint, fall, blood product — filled from structured fields rather than pasted
as snippets, so a template cannot carry the previous patient's numbers into this
note, which is the failure mode of every snippet library in every EHR. The refusal
template enforces the four pillars (capacity, risks explained, attending notified,
the patient's own words), because three of four is not enough — whichever is
missing is the one counsel will ask about.

Four handoff routes (ER→ICU, ICU→med-surg, shift-to-shift, to a procedure).
Required items you did not fill print as **NOT HANDED OVER** rather than being
omitted: a handoff that silently drops the airway line is worse than one that says
the airway was not handed over, because the receiving nurse cannot know what they
were not told.

Export produces two Word documents — the shift record (untranscribed notes first
and marked) and an audit appendix (timestamp ledger, corrections with superseded
text struck through, every interlock that fired, instruments cited, chain
verification, and the honest ledger of what the record does not establish).

### What was added that was not asked for

Restraint documentation, blood product administration, fall-event documentation
distinct from fall *risk*, present-on-admission marking for pressure injuries,
controlled-substance waste witnessing, high-alert double checks, interpreter
recording, teach-back, the sepsis/stroke/STEMI bundles, the staffing record, the
device register, and the three framing items at the top of this section. The
reasoning for each is in the module that implements it.

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
  charting/
    disclosure.py    not-the-record, no-PHI — read this one first
    models.py        Encounter, Entry, hash-chained audit, append-only revisions
    scales.py        23 scoring instruments, licensing register
    systems.py       8 body systems, 57 elements, WDL definitions
    language.py      the objective-language filter, quote exemption
    phi.py           identifier detection and redaction
    interlocks.py    the six blocks, chain of command, closed loops
    narrative.py     SBAR-SOAP composer, six macros, four handoff routes
    specialty.py     ER / ICU / peds / med-surg modules, timed bundles
    store.py         one JSON file per encounter, purge, chain verification
    export.py        shift record and audit appendix, struck-through revisions
    routes.py        the charting API — preview and save share one code path
  static/            the UI — vanilla JS, no build step, no CDN
                     app.js research · chart.js charting · shell.js the tab switch
tests/               2,663 checks, all offline
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
| `test_charting_scales.py` | 1,447 | Every option key on every instrument resolves and is unique; non-overlapping bands; the awkward cases — an untestable GCS component reported as a floor, the CAM algorithm rejecting three-features-without-inattention, each Lund-Browder age column summing to 100%, all seven ESI decision paths, the PAT reported as a pattern rather than a total; and that no copyrighted instrument is used without its rights holder named |
| `test_charting_language.py` | 607 | **The negative assertions**: nothing fires inside a patient's quotation, `don't` does not open a quoted span, "pain management" is not a staffing complaint, "Pump serial checked" is not a device identifier, clinical numbers are not record numbers, and every objective replacement the tool suggests itself passes the filter |
| `test_charting_flow.py` | 250 | Each interlock as a **pair** — the note refused, then accepted once the missing element is supplied; future events refused and non-overridable; an override recording itself; corrections keeping the original; hash-chain detecting alteration and deletion separately; storage round-tripping every nested type; the stroke bundle anchoring on arrival; and both exported documents, including that the superseded text really carries strike-through |

---

## What is deliberately not built

- **Automated access to subscription databases.** Not a missing feature — a
  licence violation with real consequences for a hospital library.
- **An AI-detection gate.** See the table at the top.
- **A similarity percentage.** Same.
- **Verbatim copies of copyrighted appraisal instruments.**
- **Cloud sync.** A single-user local tool with JSON files does not need it, and
  it would mean uploading unpublished work to somebody's server.
- **An EHR.** The charting tab composes notes for transcription into your
  hospital's chart. It does not try to be the chart, and a tool that implied
  otherwise would put a nurse in more jeopardy rather than less.
- **Any field for a patient identifier.** Not a missing feature — the absence is
  the privacy control.
- **A triage level, a disposition or an order derived from a score.** The tool
  computes published scores from what you enter and shows you the band. Converting
  one into a decision is yours and the provider's.
