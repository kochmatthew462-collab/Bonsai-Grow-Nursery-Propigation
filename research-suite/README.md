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
| Direct API access to CINAHL, PsycINFO, Embase, Cochrane, JBI, Global Health, Scopus, IEEE Xplore, JSTOR | **None of these sells API access to an unaffiliated individual, at any price.** PsycINFO has no API for *anyone*. IEEE Xplore's API is institution-only and its terms forbid redistribution of the metadata. JSTOR has no search API at all — its Constellate text-analysis service closed in July 2025, and what remains is a dataset request for named research projects, not a query endpoint. Automating any of them through a library proxy violates every one of those licences and can get a hospital library's whole IP range blocked. → The tool makes **citation-file import a first-class path**, so those records flow through the same pipeline with their provenance recorded. See [Reaching the gated databases](#reaching-the-gated-databases). |
| Grammarly integration | **Not possible by any supported route.** The Text Editor SDK — the only embedding route — was discontinued on 10 January 2024, with no successor. The current developer API is Enterprise/Education-only and returns *scores*, not suggestions, offsets or corrected text. → Self-hosted **LanguageTool** in the pipeline; Grammarly as a manual final pass in Word. See [Grammar and spelling](#grammar-and-spelling). |
| Verify a 0% similarity score on Turnitin before export | **Not achievable and not desirable.** No legitimate paper scores 0% — reference lists match the original articles byte-for-byte by design, quotations are supposed to match verbatim, and the standard phrasing of the field recurs in thousands of papers. Real journals see 16–19% on average. **0% is the fraud signature**, not the goal. → The tool reports **unattributed verbatim overlap against the sources you actually cited**, with offsets, and blocks export on citation defects. It never prints a percentage. See [What "no plagiarism" can honestly mean](#what-no-plagiarism-can-honestly-mean). |
| Reproduce CASP / JBI / AGREE II checklists | **Depends on the instrument, and the differences are large.** JBI's 2023–25 tools say "unauthorized reproduction prohibited"; COREQ is all-rights-reserved. → The tool implements the same methodological **domains** in its own words, names and cites the instrument it follows, and never reproduces item text. See [Appraisal and licensing](#appraisal-and-licensing). |
| AI-detection gate before export | **Deliberately not built.** Detectors measure perplexity, not authorship, and misclassify non-native-English writing at a high rate (Liang et al., *Patterns*, 2023). Gating on one would fail honest work. → A claim-by-claim provenance ledger instead, which is something a detector cannot give you. |
| AI-detection shielding — vary sentence length and vocabulary to bypass detectors | **Not built, and I want to be straight with you about why rather than quietly leaving it out.** Two separate reasons. First, it does not work: every published evaluation of "humanizer" tools finds the effect is unstable and detector-specific, so a paper that passes one checker this week fails another next week, and you would have traded real confidence for a number you cannot rely on. Second, a tool whose stated purpose is defeating an academic-integrity check is a tool that assumes the work is not yours — and if the draft came out of the claim ledger, in your own sentences, from sources you read, then it *is* yours and the honest answer to a flag is the ledger. → What is built instead is **stylometric calibration against your own writing samples**: sentence-length variance, subordination, hedging, nominalisation and reading level measured on your uploaded work and compared with the draft, with the drifted features named. That is the same underlying statistics, aimed at making the draft sound like you rather than at making it sound like nobody. See [Writing in your own voice](#writing-in-your-own-voice). |
| Royalty-free visual assets with APA provenance | **Not built, and this row exists because an audit found it missing from this table.** The tool generates figures from your own data and cites them properly; it does not source stock imagery. A general image search that respected licensing would need a licensed image API and a rights database, and an unlicensed one would hand you an image you cannot legally publish while telling you that you can — which is worse than nothing. → Generate figures from data, or supply your own image and record its licence and attribution yourself. |
| Pull graphs, pictures and charts *out of* retrieved papers | **Not built.** A figure lifted from a published paper is the copyright holder's, and reproducing one in your own work needs permission that a tool cannot grant. Extracting the underlying *data* from a published chart is also not reliable enough to trust silently. → The suite plots figures from data you enter or from the CDC and WHO data APIs, with the provenance and licence recorded. Full-text **numbers** are a different matter and are extracted — see [Full text: anchoring and extraction](#full-text-anchoring-and-extraction). |
| "The AI reads the PDFs and extracts sample sizes, methodologies, *p*-values and outcomes" | **Built, and built as a reader rather than a model** — which is a smaller promise, deliberately. It returns nothing it cannot point at: every value carries the page, the paragraph and the sentence it was read out of, and anything it could not find is listed as missing rather than guessed. A model asked to fill an extraction table will fill it, and a plausible sample size in a matrix is worse than an empty cell, because the empty cell gets checked. See [Full text: anchoring and extraction](#full-text-anchoring-and-extraction). |
| A charting tab that leaves a nurse "100% covered" in litigation | **No document guarantees an outcome.** A nurse who did the right thing can still be named; one who documented perfectly can still be found to have breached a standard of care. → The tool structures the five things that actually go missing under pressure — observation, impression, action, **notification**, re-evaluation — and refuses to save a note that drops the one that matters. See [The charting tab](#the-charting-tab). |
| Auto-suggest an ESI triage level from vitals and chief complaint | **This is clinical decision support and it would be unsafe.** A triage acuity assigned by a tool is also indefensible in a deposition. → The tool walks the four published decision points *you* answer, computes what the algorithm yields, shows the working, and displays the danger-zone thresholds so your judgement is informed rather than replaced. |
| Reproduce Braden, Morse, Wong-Baker FACES, CAM-ICU, FLACC, CPOT, ESI, APACHE II | **Copyrighted, and FACES is a trademark whose artwork is licensed.** A subtly paraphrased near-copy would be worse than either extreme: it looks like the instrument while scoring something slightly different. → Scoring arithmetic and published thresholds implemented, item wording written fresh, no artwork reproduced, every rights holder named on the Reference screen. |
| A charting tool that holds the patient's details | **Deliberately impossible.** There is no field for a name, MRN or date of birth. Most hospitals prohibit PHI on a personal device and the HIPAA finding lands on the nurse. → Encounters are identified by bed or room; free text is scanned for identifiers with one-click redaction; purge is on every screen. |

Everything else — retrieval, deduplication, level-of-evidence classification,
retraction checking, appraisal, evidence matrices, APA 7 formatting, both
documents, the slide deck, the figures — works, and is tested.

---

## APA 7, on screen

APA 7 is the standard the whole research half works toward, and for a long time
the only place any of it surfaced was a `.docx` at the end of an eight-step
workflow whose first screen was PICO(T). That was the wrong shape: the framework
question is step one by *workflow order*, not by importance. **APA 7 now leads the
navigation**, ahead of the numbered steps, and it reads without a project open —
the manual does not depend on your having started a paper.

The screen has five parts:

**The defaults every paper starts from**, or, with a project open, *that* paper's
setup: paper type, typeface and size, margins, spacing and the page-number field,
each labelled with the section of the Publication Manual it comes from.

**Still to supply** (with a project open). What APA requires that this paper has
not got yet — a missing title, an unnamed author, a course or instructor absent
from a student title page, a running head over 50 characters, no cited source.
Stated as what is missing rather than as a percentage, because a score invites
treating 90% as good enough when the missing tenth is the title.

**Worked examples of the nine hardest reference types.** Two authors and the
ampersand-versus-"and" rule (§8.17); three authors and *et al.* from the first
citation, not the second (§8.17); a group author spelled out with its abbreviation
and abbreviated after (§8.21); a book with an edition (§9.29); a chapter in an
edited book (§9.28); an organisation's web page (§9.34); a thesis (§9.31); a
twenty-four-author trial showing the first nineteen, an ellipsis and the final
author (§9.8); and a source with no date (§9.17).

They are **rendered by the same citation engine that writes your references**, not
copied out of the manual — so they are a demonstration of what this code does
rather than a claim about it, and they break on screen the moment the engine
regresses. `test_apa_citations.py` asserts all nine character for character. They
are examples, not sources: nothing there is retrievable and nothing there enters a
project.

**The five heading levels**, each shown in its own actual formatting — centred
bold, flush-left bold, flush-left bold italic, and the two indented run-in levels
that end with a period.

**Every rule the exporter enforces**, twenty-two of them, grouped by layout, front
matter, structure, quotations, citations, references, and tables and figures, each
with its manual section. The list lives in `app/main.py` beside the code rather
than in the front end, because it is a claim about what the code does and should
be edited in the same commit as anything that would falsify it.

The distinction that matters: these are **enforced, not advised**. The margins,
the double spacing, the hanging indent and the page-number field are written into
the OOXML itself, and `test_docx_layout.py` asserts them against the *saved file*
rather than against the builder that wrote it.

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

### Spelling and grammar

You asked for the tab to "grammar/spell check properly". A general-purpose checker
pointed at a nursing note does not do that — it produces so much noise it gets
switched off within one shift, and a checker that is switched off catches nothing.
Three things are wrong with the naive version, and each is handled:

- **Nursing notes are deliberately fragmentary.** "Alert and oriented ×4." "Denies
  chest pain." "Bed low, brakes locked, call light within reach." All fragments,
  all correct charting. 17 rules are disabled, each with a stated reason.
- **Clinical vocabulary is not in a general dictionary.** PERRLA, hydromorphone,
  nasogastric, levophed, periwound — a spell-checker calls every one a mistake.
  Spelling hits are filtered against a ~1,750-term clinical dictionary that is
  **derived from this tab's own vocabulary** (every option label in `systems.py`,
  every scale item in `scales.py`, every drug in the closed-loop rules) plus a
  curated medication and abbreviation list. Deriving it means the checker can never
  start flagging words the tool itself put in the note.
- **Clinical notation looks like broken text.** `BP 84/50`, `SpO2 88%`,
  `0.5 mg/kg`, `1412`, `GCS 15 (E4 V5 M6)`, `2+`, `5/5`, `3.2 cm × 1.8 cm`. All
  masked at **equal length** before the request goes out — equal length because
  offsets come back as indexes into what was sent, so a substitution that changed
  the length would misplace every later issue.

Two smaller behaviours that matter: dictionary suppression applies to **spelling**
hits only, because a grammar rule flagging "are" is not claiming "are" is
misspelled; and a suggested correction that is itself a clinical term is dropped,
because offering "insulin" as the fix for a misspelling of something else is worse
than offering nothing.

It runs against the same self-hosted LanguageTool server as the research half, so
nothing leaves the machine, and it is **optional** — with no server the tab still
composes, still runs the objective-language filter, still enforces every interlock
and still exports, and it says so rather than silently skipping.

It is also not the important checker here, and the UI says that too. A misspelling
is embarrassing; "patient appears sleeping" is a lawsuit.

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

## Discovery, compliance and statistics

Six modules added for graduate and doctoral work, each answering a request in the
extended specification.

### PICO(T) and SPIDER, translated per database

A question written as prose retrieves prose. Framed as PICO it decomposes into
concept blocks — OR-ed inside, AND-ed between — and that is the search a
systematic review can defend.

The translation is **per database, because the syntax genuinely differs**:

| | PubMed | CINAHL | Cochrane | Scopus |
|---|---|---|---|---|
| Controlled vocabulary | `"term"[Mesh]` | `(MH "Term")` | `[mh term]` | none |
| Title/abstract | `[tiab]` | `TI x OR AB x` | `:ti,ab,kw` | `TITLE-ABS-KEY()` |

That table is the whole point. **CINAHL has no `[tiab]` field at all**, so a PubMed
string pasted into it returns almost nothing and the failure is silent. Six
translators, each checked in the tests for the tags it must emit *and* the ones it
must not.

Expansion is **opt-in per block** and comes from a small built-in thesaurus of
nursing concepts. It will not invent synonyms: a generated term you cannot source
is a liability in a methods section. SPIDER sits alongside PICO because forcing a
qualitative question into PICO leaves an empty comparison block and misses the
phenomenological literature.

### PRISMA 2020 flow diagram

Drawn with matplotlib from your counts, in the layout the 2020 statement
describes — not reproduced from the PRISMA group's template files, which are their
work. The reporting structure is the method and is freely usable; the artwork is
not.

Both columns are drawn: PRISMA 2020 separates records from databases and registers
from those found by citation searching, and a 2009-style single-column diagram is a
reviewer comment today.

**The arithmetic is walked the way a reader walks it** — identified minus removals
equals screened, screened minus excluded equals sought, and so on down. A mismatch
is **reported, never corrected**: silently adjusting the numbers to make the boxes
subtract would be fabricating a flow diagram, which is a research-integrity problem
rather than a formatting one. It also insists on full-text exclusion reasons with
counts, and catches the swapped studies/reports boxes.

### Statistical narrative translation

Paste SPSS or R output, get APA 7 results prose. The value is the dozen rules that
are individually trivial and collectively impossible at 2 a.m.:

- no leading zero on *p*, *r*, β, ηp² — **but a leading zero on *M*, *SD*, *t*, *F*, *d***, and getting that set wrong is how `M = .45` reaches a marker;
- `p < .001` rather than SPSS's `p = .000`, which is not small, it is false;
- degrees of freedom in parentheses, exact *p* rather than `p < .05`;
- italic Roman symbols, **upright Greek** — the rule people get backwards immediately after learning the first half.

Three things it refuses to do. It will not compute anything. It will not soften a
non-significant result into "approached significance" — the prose checker flags
that phrase, along with "proves". And **a missing *p* never renders as "not
statistically significant"**: the first version did exactly that, manufacturing a
confident wrong claim out of an absence, and a test now pins it.

SPSS output is column-oriented, so the ANOVA reader locates the "Between Groups"
row by its label and reads it positionally — there is no `F = ` anywhere in a real
SPSS table.

### Rubric and syllabus ingestion

Paste a rubric; get a checklist. The distinction that makes it work is between
**countable requirements** ("at least five peer-reviewed sources from the last five
years", "1,500–2,000 words", "a Level 1 heading per section") and **qualitative
criteria** ("demonstrates critical analysis"). Both are extracted; only the first
is checked. A tool that ticked a judgement would be inventing a grade.

Every requirement carries the rubric's own sentence, so anything misread is visible.
Real rubrics are wrapped text, and the extractor rejoins continuation lines — a bug
found by testing, where "published within the / last 5 years" lost its recency
requirement to a line break.

### The grading simulator

Runs on every preview against the claim ledger. Three states — met, not met,
cannot check — with the observed value beside each, so you can see *why* something
passed and catch a check that passed for the wrong reason.

**There is no predicted grade, deliberately.** A paper can meet every countable
requirement and fail on the qualitative ones, which carry most of the marks; a
number saying 94% on such a paper would stop you working on the part that mattered.
Word counts exclude the title page and reference list, because that is what a rubric
means. A section mentioned in the body but not as a heading is reported as *partly*
met, not met — a rubric asking for a section means a heading a marker can find.

### Journal guideline parser

Eight built-in profiles (JAN, IJNS, JCN, Nursing Research, Worldviews, BMJ Open,
The Lancet, AJN) plus a parser for anything else.

The structured abstract is the part that bites: JAN wants *Aim / Design / Methods /
Results / Conclusion / Impact / Reporting Method / Patient or Public Contribution*,
and an abstract missing one is returned without review. The checker names exactly
which headings are absent. It also flags the journals that want Vancouver rather
than APA and warns that the conversion changes in-text citations, not just the
reference list — that is not formatting, it is a day of work.

Profiles carry their compile date and a "verify against the current guidelines"
note, because journals change these without announcement and a stale profile
trusted as current is worse than none.

---

## Full text: anchoring and extraction

Step 4 of the workflow. Read a source's full text in — a PDF, a text file, or
pasted text — and it becomes a list of **anchored paragraphs**, each carrying
its page number, its position on that page, the section it falls under, and a
digest of its own text.

That anchor is the thing everything else here is built on.

### Extraction: a reader, not a model

`extract()` pulls the evidence-matrix fields out of the passages: design,
statistical analyses, sample size, response rate, follow-up, attrition,
statistical results, ethical approval, funding, conflicts of interest,
limitations.

**Everything it returns carries the page and the sentence it was read out of,
and it returns nothing it cannot point at.** That is a deliberate limit, and the
reason is the failure mode of the alternative. A language model asked to fill an
extraction table will fill it. A plausible unsourced sample size in a matrix is
worse than an empty cell, because an empty cell gets checked and a filled one
does not.

So it reports what it matched, says so, and lists what it could not find:

> Not found in the text: funding, conflicts. An absent funding or ethics
> statement is itself a finding — both are reporting requirements, and their
> absence belongs in your appraisal.

One button fills the empty cells of the evidence matrix from what it read.
Only the empty ones: anything you typed wins.

Two details that took a second pass to get right, both of which produce a
*wrong-looking* cell rather than a missing one:

- A confidence interval reads to its closing bracket, not to the first period.
  The first version turned `95% CI [0.45, 0.85]` into `95% CI [0` — which in a
  matrix looks like a transcription error you then have to go and chase.
- The name of a test is methodology, not a result. `chi-square test` goes in an
  **analysis** column; `χ²(3, N = 1,204) = 12.44` goes in the results column.

### Anchoring: every claim tied to the paragraph it came from

The Check screen runs the claim ledger against the ingested full text and sorts
every claim into one of four states:

| State | What it means |
|---|---|
| **anchored** | Found in the source it cites, with the locator |
| **verbatim overlap** | Repeats eight or more consecutive words — quote it and give the locator, or reword it |
| **not found in source** | Nothing in the cited work supports this sentence |
| **no full text** | Not checked, which is *not* the same as having passed |

The fourth row is the one that matters most for honesty. A claim that could not
be checked is reported as unchecked and is never counted as clean.

Matching is on **containment**, in two signals that are deliberately kept apart.
Content-word and trigram overlap catch a *paraphrase*, which is what
source-grounding actually needs; eight-word runs catch *verbatim* lifting, which
is a different problem with a different fix. The first version of this scored
eight-word shingles alone — which meant it could anchor exactly the sentences
that were already a plagiarism problem, and nothing that had been properly
reworded.

One thing it does not do, stated on the screen itself: matching finds where a
claim came from; it does not judge whether the source says what the claim says
it says. A green anchor means the sentence is traceable, not that it is true.
The excerpt is shown beside it so you can read it.

### PDFs are optional, on purpose

`pypdf` is in `requirements.txt` and imported lazily behind a guard. Without it
you lose PDF parsing and keep pasted text, and the interface says which. The
guard catches more than `ImportError`: on one machine `import pypdf` pulled in a
`cryptography` build whose Rust extension aborted, which arrives as a
`PanicException` inheriting from `BaseException`. A guard that caught only
`ImportError` turned a broken optional dependency into a 500 on the endpoint
that was merely asking whether the feature existed.

A scanned PDF has no text layer, and the tool says so by name rather than
returning nothing and leaving you to guess:

> The PDF opened but contained no extractable text. That almost always means it
> is a scan rather than a digital document — the pages are images. It needs OCR
> before anything here can read it.

---

## The four artefacts

An export produces four files.

**The paper** (`*-paper.docx`) is a real APA 7 manuscript: 1-inch margins,
double-spaced throughout, 0.5-inch first-line indents, page number in a header
field on every page, student *or* professional title page, the five heading
levels, hanging-indent reference list on its own page, and tables with
horizontal rules only. 85 automated checks assert this against the generated
OOXML rather than against the builder's return values, because everything that
goes wrong in Word export goes wrong between the API call and the file.

**The evidence matrix** (`*-evidence-matrix.xlsx`) is the matrix as a
spreadsheet rather than as a Word table, because it is the one artefact here that
is worked *on* rather than read: sorted by level of evidence, filtered to the
trials, a column pasted into a meta-analysis. Frozen header, auto-filter, numbers
typed as numbers so a sample size of 9 sorts before 1,204, and a second sheet
recording where every record came from and what was done to it. Written by
assembling the OOXML directly rather than by adding a spreadsheet library — the
same judgement `apa/ooxml.py` makes about Word — so it costs no dependency.

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

## Running it in a GitHub Codespace

It works there, and the security model is different enough to state rather than
imply.

The app still binds to `127.0.0.1` inside the container. GitHub forwards the
port over HTTPS, so the browser arrives with
`Host: <codespace>-8765.app.github.dev` — which the loopback-only allowlist used
to reject with a 421 that blamed your URL. That forwarded name is now
recognised, taken **from the environment and never from the request**, because a
Host header is attacker-controlled and the whole point of the allowlist is that
it is not. Only your codespace and only the port actually being served are
accepted; a different port, another codespace, or a suffix like
`…app.github.dev.evil.test` is still refused.

The startup banner prints the forwarded HTTPS URL rather than a localhost one
that would go nowhere, and says what governs access:

- **Port visibility is the boundary.** Private — the default — means your GitHub
  account only, which is the setting you want. Set it to Public and anyone with
  the URL can reach it, leaving the session token as the only protection; and a
  token in a URL leaks into history and logs.
- **The data is as durable as the codespace.** Your API keys and projects live
  in it and go when it does. Export anything you want to keep.

### The app starts with the container

Codespaces suspends a container after about thirty minutes idle. Coming back to
it, the forwarded URL resolved to nothing and the browser said 404 — a message
about a missing page for what was really a stopped process, and one you could
only fix from a terminal.

`.devcontainer/devcontainer.json` now starts the app on every container start,
detached so that the setup shell exiting does not take the server with it, with
output kept in `/tmp/koch-suite.log` so a failed start is diagnosable after the
fact. **This takes effect on a codespace rebuild**, not on the next start of an
existing one: Command Palette → *Codespaces: Rebuild Container*.

One port is forwarded now, not two. Two only ever produced a second candidate
URL to confuse with the first, and picking the wrong one is a 404 that looks
exactly like a broken application.

### If the forwarded URL still 404s

That is GitHub's proxy, not this app: nothing is listening on that port. The
three causes look identical from the browser and need different fixes, so ask
rather than guess:

```bash
python3 -m app.doctor
```

It reports each layer in order — not running, running on a different port,
bound to loopback where the forwarder cannot see it, or a port that was never
forwarded — and names the next step for whichever one is broken.

---

## The session token

Generated once and kept in `data/.session-token`, mode 0600. It is in the URL
the app prints, and the browser hands it back on every request.

It used to be regenerated on every run. That invalidated the open browser tab
every time the server restarted — after a code change, a Ctrl-C, a crash — and
produced a stream of "missing or invalid session token" that read as a bug in
the application rather than as the design working.

**Stability is not a weakening.** The token stops other processes on the machine,
and pages in other tabs, from driving the API. That is equally true of a stable
token: anything running as your user can read a rotating one too, including out
of the terminal it is printed in. The real boundary was always your OS account
plus the host allowlist. Jupyter's token works the same way for the same reason.

To rotate it, delete the file. To pin it — useful for a bookmark that must keep
working — set `RESEARCH_SUITE_TOKEN`.

### Why closing the tab used to cost you the token

The page kept the token in `sessionStorage`, which browsers clear when the tab
closes. So a stable token still meant every new tab was an unauthenticated tab,
and the only way back in was the launch URL out of the terminal — which in a
Codespace means finding the terminal, and, if the container had suspended in the
meantime, starting the app before the forwarded URL would resolve at all.

A token that arrives in the launch URL or a header is now written to a cookie:
`HttpOnly`, `SameSite=Lax`, `Secure` when the connection is HTTPS, thirty days.
**Bookmark the plain address without the `#token=` part** — after the first
visit it works on its own, in a new tab, after a restart, until the cookie
expires.

`HttpOnly` because the page never needs to read it back, and a token no script
can read is one no injected script can steal. A cookie does travel automatically
where a custom header did not, which is the property CSRF exploits, so it is not
carrying the security on its own: `SameSite=Lax` keeps it off cross-site writes,
the Origin check refuses cross-origin writes that carry it anyway, and the Host
allowlist refuses the DNS-rebinding case where the origin looks legitimate. The
cookie is convenience on top of three checks that do not depend on it.

A cookie the server rejects is **deleted by that rejection**. Without that, a
stale one is a trap with no exit: the page can neither read an `HttpOnly` cookie
nor delete it, so every reload would resend the same refused credential.

### Getting the address back

```bash
python3 -m app.doctor --url
```

Prints the launch URL and nothing else, works without the virtual environment,
and reports the port that is *actually* serving rather than the configured one —
which differ exactly when the link matters most.

### Reaching it from another machine

Running the suite on an always-on box — a Raspberry Pi, a spare laptop — means
the browser is not on the machine doing the serving, and two separate settings
have to agree before that works. Binding wide decides which network interface
accepts a connection. The `Host` allowlist decides who gets answered. They are
deliberately separate, because the allowlist is the DNS-rebinding defence and it
would be worthless if opening a port opened it too.

```bash
RESEARCH_SUITE_HOST=0.0.0.0 \
RESEARCH_SUITE_ALLOWED_HOSTS=pi-3bplus.local,192.168.1.50 \
bash run.sh
```

Set only the first and the port is open but every request from the other machine
comes back **421** — the port is listening, the app is healthy, and the address
looks fine, which is a miserable thing to debug. So the banner says so on
startup, and `python3 -m app.doctor` fails the check by name.

`RESEARCH_SUITE_ALLOWED_HOSTS` takes a comma-separated list and accepts whatever
you paste: a bare name, a name and port, or the whole URL out of the address
bar. It defaults to empty and is never filled in for you — not from the request
(a `Host` header is attacker-controlled, so inferring it would delete the
defence outright) and not from the machine's own hostname (which would quietly
admit a name you never chose). Naming the hosts is the point of them.

The launch URL follows the same rule. `http://0.0.0.0:8765/` is not an address —
`0.0.0.0` means "accept on every interface", and pasting it into a browser
reaches nothing — so with the app bound wide the banner prints the name you
allowlisted, and falls back to `localhost` when you have not named one.

None of this is a login. The token is still the only credential, and on a LAN it
is doing real work rather than backing up a loopback bind, so `## Security,
honestly` below applies with more force, not less: put an authenticating proxy
in front of this if the network is not one you control.

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

Binding wide does not widen who is admitted. The `Host` allowlist is unchanged
by it, so a request from another machine is refused until you name that address
in `RESEARCH_SUITE_ALLOWED_HOSTS` — see *Reaching it from another machine*
above. Two settings, two decisions, on purpose.

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
    workbook.py      the evidence matrix as .xlsx, OOXML written directly
    prisma.py        the PRISMA 2020 flow diagram, drawn and arithmetic-checked
  writing/
    draft.py         claim-ledger drafting, AI-use disclosure
    style.py         stylometric profiling from your own samples
    integrity.py     verbatim overlap, citation audit, export blockers
    proof.py         LanguageTool integration, the Grammarly answer
    statistics.py    SPSS and R output into APA 7 results prose
  research/
    pico.py          PICO(T)/SPIDER builders, six database translators
  compliance/
    rubric.py        rubric and syllabus into a checkable requirement list
    simulator.py     the draft against those requirements — no score, ever
    journals.py      eight journal profiles plus a guidelines parser
  charting/
    disclosure.py    not-the-record, no-PHI — read this one first
    models.py        Encounter, Entry, hash-chained audit, append-only revisions
    scales.py        23 scoring instruments, licensing register
    systems.py       8 body systems, 57 elements, WDL definitions
    language.py      the objective-language filter, quote exemption
    phi.py           identifier detection and redaction
    proofing.py      spelling and grammar, tuned and masked for clinical notes
    interlocks.py    the six blocks, chain of command, closed loops
    narrative.py     SBAR-SOAP composer, six macros, four handoff routes
    specialty.py     ER / ICU / peds / med-surg modules, timed bundles
    store.py         one JSON file per encounter, purge, chain verification
    export.py        shift record and audit appendix, struck-through revisions
    routes.py        the charting API — preview and save share one code path
  static/            the UI — vanilla JS, no build step, no CDN
                     app.js research · chart.js charting · shell.js the tab switch
tests/               3,736 checks, all offline
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
| `test_apa_citations.py` | 89 | Every APA 7 rule a tool gets wrong: et al. from the first citation, expanded et al. for clashing author groups, year letters, group-author first use, the 21-author ellipsis, sentence-case conversion that preserves COVID-19 and proper nouns, en-dash page ranges, elided range expansion; and the nine worked examples shown on the APA 7 screen, asserted character for character so that a demonstration cannot quietly become a wrong one |
| `test_docx_layout.py` | 85 | Assertions against the saved OOXML: margins, all four font attributes, double spacing, the `PAGE` **field** rather than a literal digit, running head presence by paper type, five distinct heading levels, hanging indents, horizontal-only table borders |
| `test_evidence.py` | 121 | Real CINAHL/Ovid/PubMed/Zotero/Scopus export shapes; `Review` ≠ systematic review; retraction excluded rather than graded; DOI/PMID/title dedupe; conflicting DOIs kept separate; retraction propagating through a merge |
| `test_sources.py` | 85 | Structured-abstract labels preserved, collective authors, `CommentsCorrections` retractions, JATS markup stripped, NCBI identification params sent, **API keys redacted from logs**, failures surfaced rather than swallowed |
| `test_charting_scales.py` | 1,456 | Every option key on every instrument resolves and is unique; non-overlapping bands; the awkward cases — an untestable GCS component reported as a floor, the CAM algorithm rejecting three-features-without-inattention, each Lund-Browder age column summing to 100%, all seven ESI decision paths, the PAT reported as a pattern rather than a total; and that no copyrighted instrument is used without its rights holder named |
| `test_charting_language.py` | 607 | **The negative assertions**: nothing fires inside a patient's quotation, `don't` does not open a quoted span, "pain management" is not a staffing complaint, "Pump serial checked" is not a device identifier, clinical numbers are not record numbers, and every objective replacement the tool suggests itself passes the filter |
| `test_security.py` | 168 | Both directions on every check that decides who can drive this: loopback and Codespaces hosts allowed, `[::1]:8765` allowed (stripping the brackets before the port left `::1]:8765` and locked out any machine resolving localhost to IPv6), and refused — another codespace, another port, a `…app.github.dev.evil.test` suffix, a spoofed Origin on a write, a missing token, and a half-configured environment that must not become a wildcard. Plus the LAN allowlist: a named host admitted while `pi-3bplus.local.evil.test` and an un-named neighbour are refused, an empty allowlist admitting nothing extra, the allowlist read from configuration and never from the request or `gethostname()` (asserted against the parsed module, because the comment explaining why we don't call it satisfied a substring search), that the app actually *passes* it through — `SecurityConfig` grew the parameter before anything supplied it, so the setting existed and did nothing — and that no printed URL ever contains `0.0.0.0` |
| `test_research_tools.py` | 273 | Each database translator checked for the tags it must emit **and the ones it must not** — a PubMed string in CINAHL fails silently; PRISMA arithmetic walked and mismatches reported rather than corrected; the leading-zero rule in both directions; that a missing *p* never renders as "not statistically significant"; that the simulator produces no score, grade or percentage; and that the guideline parser invents nothing when the text does not say — and that it *does* read a structured abstract stated as a sentence, which is the commonest way a journal writes it and which the parser used to miss entirely |
| `test_frontend.py` | 189 | **The suite that was missing.** `node --check` on every script — a syntax error takes out the whole UI and nothing in a Python test notices, which is exactly how `app.js` shipped with an unbalanced paren. Plus: shared globals resolve across files, no duplicate top-level `const` (a hard load error in classic scripts), every `getElementById` has a matching id, every API path the front end calls exists, and **no route is orphaned from the UI** — which is how the language-check endpoint was caught sitting unwired, and, once the same check was extended to the research half, how seven more were found, the whole figure generator among them; and that the screens which must work before anything exists — Settings, Question, Compliance and APA 7 — are not gated behind creating a project |
| `test_charting_proofing.py` | 122 | Clinical notation masked at **equal length** before it leaves; the masked-span guard tested against what the server saw rather than the original (it looked right and never fired until a test proved it); clinical vocabulary suppressed for spelling hits but **not** for grammar hits; suggested corrections that are themselves clinical terms dropped; and a missing server degrading this feature and nothing else |
| `test_fulltext.py` | 227 | Headings matched against the **whole line**, so "Abstract reasoning was assessed" does not re-section the paper; a section carrying across a page break, including a page that *ends* on a heading; a paraphrase located as well as a verbatim run, because a locator that only finds plagiarism is not a locator; an unrelated sentence finding nothing, which is the answer this exists to give; intervals not truncated and brackets balanced; the same number written two ways counted once; and a source that states nothing producing an empty matrix and a `missing` list rather than a filled one |
| `test_deck.py` | 45 | The class of defect where a feature exists, works, and is reachable from nothing: figures actually packaged into the .pptx, the evidence-level chart recorded on the project rather than only drawn, speaker notes as complete sentences carrying APA in-text citations (including a group-author abbreviation and a quotation locator), no citation invented for an uncited claim, and a deleted image not taking the whole deck with it |
| `test_charting_flow.py` | 269 | Each interlock as a **pair** — the note refused, then accepted once the missing element is supplied; future events refused and non-overridable; an override recording itself; corrections keeping the original; hash-chain detecting alteration and deletion separately; storage round-tripping every nested type; the stroke bundle anchoring on arrival; and both exported documents, including that the superseded text really carries strike-through |

---

## What is deliberately not built

- **Automated access to subscription databases.** Not a missing feature — a
  licence violation with real consequences for a hospital library.
- **An AI-detection gate.** See the table at the top.
- **AI-detection shielding.** Same table. It does not reliably work, and the
  honest answer to a flag is the claim ledger.
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
