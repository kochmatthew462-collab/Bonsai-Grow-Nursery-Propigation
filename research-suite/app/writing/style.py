"""
Authorial style profiling from the user's own writing samples.

Style matching here is **measurement plus retrieval**, not vibes. The tool reads
samples the user supplies, measures the features that actually distinguish
academic prose, and passes those numbers to the drafting layer as targets —
alongside a set of the user's own sentences as few-shot examples, which in
practice does more than any single number.

The features are the ones stylometry has long used to attribute authorship,
because they are the ones that stay stable across topics: sentence-length
distribution (mean *and* spread — a writer who alternates 12-word and 40-word
sentences reads nothing like one who writes 26-word sentences uniformly),
function-word and connective habits, hedging density, passive-voice rate,
first-person use, punctuation preferences, and lexical variety.

Two limits stated plainly:

* **This produces a close imitation, not authorship.** The tool can match how
  the user's sentences are shaped; it cannot supply their clinical judgement.
  What makes the output theirs is that they set the question, chose and appraised
  the sources, and reviewed every claim — which is what the claim ledger exists
  to make visible.
* **Under about 1,500 words of sample, the numbers are noise.** The profile says
  so rather than quietly reporting a confident-looking figure from three
  paragraphs.
"""

from __future__ import annotations

import math
import re
from collections import Counter

from ..models import StyleProfile

MIN_RELIABLE_WORDS = 1_500
MIN_USABLE_WORDS = 300

# Function words and connectives are the load-bearing signal in authorship
# attribution: writers are consistent about them and unaware that they are.
_CONNECTIVES = [
    "however", "therefore", "moreover", "furthermore", "nevertheless",
    "nonetheless", "consequently", "thus", "hence", "accordingly",
    "conversely", "similarly", "likewise", "additionally", "specifically",
    "notably", "importantly", "in addition", "in contrast", "for example",
    "for instance", "that said", "even so", "as such", "in turn",
    "by contrast", "on balance", "in practice", "taken together",
]

_HEDGES = [
    "may", "might", "could", "appears", "appear", "seems", "seem", "suggests",
    "suggest", "indicates", "indicate", "likely", "unlikely", "possibly",
    "potentially", "arguably", "somewhat", "relatively", "tends", "tend",
    "generally", "typically", "often", "largely", "broadly", "apparently",
    "presumably", "to some extent", "in part",
]

_BOOSTERS = [
    "clearly", "demonstrates", "demonstrate", "establishes", "establish",
    "confirms", "confirm", "proves", "prove", "shows", "show", "substantially",
    "markedly", "considerably", "strongly", "consistently", "robustly",
    "unequivocally", "definitively",
]

_FIRST_PERSON = ["i", "me", "my", "mine", "we", "us", "our", "ours"]

_BE_FORMS = {"is", "are", "was", "were", "be", "been", "being", "am"}

_STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "if", "then", "than", "that", "this",
    "these", "those", "of", "in", "on", "at", "to", "for", "with", "from", "by",
    "as", "is", "are", "was", "were", "be", "been", "being", "am", "it", "its",
    "he", "she", "they", "them", "their", "his", "her", "we", "our", "us", "i",
    "you", "your", "not", "no", "nor", "so", "such", "can", "could", "may",
    "might", "will", "would", "shall", "should", "must", "do", "does", "did",
    "have", "has", "had", "there", "here", "when", "where", "which", "who",
    "whom", "whose", "what", "how", "why", "all", "any", "both", "each", "more",
    "most", "other", "some", "only", "own", "same", "also", "very", "just",
    "about", "into", "through", "during", "before", "after", "above", "below",
    "between", "among", "over", "under", "again", "further", "once", "because",
    "while", "however", "therefore", "thus",
}


def sentences(text: str) -> list[str]:
    """Split into sentences without breaking on the abbreviations academic prose
    is full of — "et al.", "e.g.", "p. 14", "Dr.", "vs.", decimals."""
    protected = text
    for abbreviation in ("et al.", "e.g.", "i.e.", "cf.", "vs.", "Dr.", "Prof.",
                         "Mr.", "Mrs.", "Ms.", "St.", "Fig.", "No.", "Vol.",
                         "pp.", "p.", "para.", "ed.", "eds.", "approx."):
        protected = protected.replace(abbreviation, abbreviation.replace(".", "\x01"))
    # A lambda, not a template string: "\x01" is not a valid escape in a
    # replacement template and raises re.error at substitution time.
    protected = re.sub(r"(\d)\.(\d)",
                       lambda m: f"{m.group(1)}\x01{m.group(2)}", protected)

    parts = re.split(r"(?<=[.!?])[\s\n]+(?=[A-Z“\"(])", protected)
    return [p.replace("\x01", ".").strip() for p in parts if p.strip()]


def paragraphs(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n+", text) if p.strip()]


def words(text: str) -> list[str]:
    return re.findall(r"[A-Za-z][A-Za-z'-]*", text)


def build_profile(samples: list[str]) -> StyleProfile:
    """Measure a style profile from one or more writing samples.

    Samples should be the user's own finished academic prose — a previous paper,
    a discussion post, a clinical write-up. Text from other authors would train
    the drafting layer toward the wrong voice.
    """
    joined = "\n\n".join(s for s in samples if s and s.strip())
    profile = StyleProfile(sample_count=len([s for s in samples if s and s.strip()]))
    if not joined.strip():
        profile.notes = "No usable sample text was supplied."
        return profile

    # In-text citations must come out before measurement: "(Smith & Jones, 2023)"
    # would otherwise inflate sentence length, distort the word list and read as
    # a parenthetical habit rather than a citation convention.
    body = _strip_citations(joined)

    all_words = words(body)
    profile.word_count = len(all_words)
    sentence_list = [s for s in sentences(body) if len(words(s)) >= 3]
    paragraph_list = paragraphs(body)

    if sentence_list:
        lengths = [len(words(s)) for s in sentence_list]
        profile.mean_sentence_words = round(sum(lengths) / len(lengths), 1)
        profile.sentence_words_sd = round(_stdev(lengths), 1)

    if paragraph_list:
        counts = [max(1, len([s for s in sentences(p) if len(words(s)) >= 3]))
                  for p in paragraph_list]
        profile.mean_paragraph_sentences = round(sum(counts) / len(counts), 1)

    lowered = [w.lower() for w in all_words]
    total = max(1, len(lowered))

    # Type-token ratio is length-sensitive, so it is measured on a fixed window
    # rather than the whole sample — otherwise a longer sample always looks less
    # varied than a shorter one and the number cannot be compared.
    window = lowered[:2000]
    profile.type_token_ratio = round(len(set(window)) / max(1, len(window)), 3)

    profile.passive_rate = round(_passive_rate(sentence_list), 3)
    profile.hedge_rate = round(_phrase_rate(body, _HEDGES) / total * 1000, 2)
    profile.first_person_rate = round(
        sum(1 for w in lowered if w in _FIRST_PERSON) / total * 1000, 2
    )
    profile.semicolon_per_1k = round(body.count(";") / total * 1000, 2)

    profile.frequent_terms = _frequent_terms(lowered, limit=25)
    profile.frequent_connectives = _frequent_connectives(body, limit=10)
    profile.flesch_kincaid_grade = _readability(body)

    if profile.word_count < MIN_USABLE_WORDS:
        profile.notes = (
            f"Only {profile.word_count} words of sample. That is too little to "
            f"measure a style from — supply at least {MIN_USABLE_WORDS} words, "
            f"and ideally {MIN_RELIABLE_WORDS:,}, or the drafting layer will "
            f"fall back on generic academic prose."
        )
    elif profile.word_count < MIN_RELIABLE_WORDS:
        profile.notes = (
            f"{profile.word_count} words of sample. Usable, but the figures are "
            f"rough below {MIN_RELIABLE_WORDS:,} words — add another sample for a "
            f"closer match."
        )
    else:
        profile.notes = (
            f"{profile.word_count:,} words across {profile.sample_count} "
            f"sample(s). Enough for a stable profile."
        )
    return profile


def _strip_citations(text: str) -> str:
    """Remove in-text citations and reference lists before measuring."""
    # Parentheticals that look like citations: contain a 4-digit year, or n.d.
    text = re.sub(r"\((?:[^()]*?\b(?:19|20)\d{2}[a-z]?\b[^()]*?)\)", " ", text)
    text = re.sub(r"\((?:[^()]*?n\.d\.[^()]*?)\)", " ", text)
    text = re.sub(r"\b\w+\s+et al\.,?\s*\(?(?:19|20)\d{2}[a-z]?\)?", " ", text)
    # A trailing reference list, from a "References" heading to the end.
    text = re.split(r"\n\s*References?\s*\n", text, maxsplit=1)[0]
    text = re.sub(r"https?://\S+", " ", text)
    return text


def _stdev(values: list[int]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    return math.sqrt(sum((v - mean) ** 2 for v in values) / (len(values) - 1))


def _passive_rate(sentence_list: list[str]) -> float:
    """Share of sentences containing a passive construction.

    Heuristic: a form of "be" followed within two words by a past participle.
    It over-counts a little on adjectival participles ("was interested"), which
    is acceptable — the number is used as a relative target against the user's
    own baseline, not as a linguistic claim.
    """
    if not sentence_list:
        return 0.0
    hits = 0
    for sentence in sentence_list:
        tokens = [w.lower() for w in words(sentence)]
        for index, token in enumerate(tokens):
            if token not in _BE_FORMS:
                continue
            for candidate in tokens[index + 1:index + 3]:
                if _looks_like_participle(candidate):
                    hits += 1
                    break
            else:
                continue
            break
    return hits / len(sentence_list)


_IRREGULAR_PARTICIPLES = {
    "given", "taken", "shown", "seen", "found", "made", "done", "known",
    "written", "held", "kept", "left", "sent", "built", "brought", "thought",
    "drawn", "chosen", "begun", "run", "set", "put", "cut", "read", "led",
    "meant", "felt", "told", "become", "come", "gone", "spent",
}


def _looks_like_participle(token: str) -> bool:
    if token in _IRREGULAR_PARTICIPLES:
        return True
    return token.endswith("ed") and len(token) > 4


def _phrase_rate(text: str, phrases: list[str]) -> int:
    lowered = text.lower()
    return sum(len(re.findall(rf"\b{re.escape(p)}\b", lowered)) for p in phrases)


def _frequent_terms(lowered: list[str], limit: int) -> list[str]:
    counts = Counter(w for w in lowered if w not in _STOPWORDS and len(w) > 3)
    return [word for word, _ in counts.most_common(limit)]


def _frequent_connectives(text: str, limit: int) -> list[str]:
    lowered = text.lower()
    found = [
        (connective, len(re.findall(rf"\b{re.escape(connective)}\b", lowered)))
        for connective in _CONNECTIVES
    ]
    return [c for c, n in sorted(found, key=lambda kv: -kv[1]) if n][:limit]


def _count_syllables(word: str) -> int:
    """Approximate syllable count by counting vowel groups.

    Deliberately not a dictionary lookup. The obvious library for this
    (`textstat`) reaches for an NLTK corpus at import time, which means a tool
    that measures readability only when it has network access — and silently
    reports zero when it does not. Flesch–Kincaid is a closed formula, so
    computing it here keeps the profile working offline and makes the number
    reproducible.

    The heuristic, in order: count vowel groups; drop a silent trailing "e";
    add one back for a consonant + "-le" ending, where the "le" is its own
    syllable; drop one for a silent "-ed" (which is silent unless the stem ends
    in t or d). Never returns less than 1.

    "simple" is the case that shows why the order matters: two vowel groups,
    minus the silent final e, plus one for "-ple", gives 2 — sim-ple. Skipping
    the subtraction because the word ends in "le" gives 3, which is wrong.
    """
    word = re.sub(r"[^a-z]", "", word.lower())
    if not word:
        return 0
    groups = len(re.findall(r"[aeiouy]+", word))

    if word.endswith("e") and not word.endswith(("ee", "ye")):
        groups -= 1
    if re.search(r"[^aeiouy]le$", word):
        groups += 1
    # "walked" and "examined" have a silent -ed; "wanted" and "needed" do not.
    if word.endswith("ed") and len(word) > 4 and word[-3] not in "tdaeiouy":
        groups -= 1
    if word.endswith(("ism", "ist")):
        groups += 1
    return max(1, groups)


def _readability(text: str) -> float:
    """Flesch–Kincaid grade level: 0.39·(words/sentence) + 11.8·(syllables/word) − 15.59."""
    sentence_list = [s for s in sentences(text) if len(words(s)) >= 3]
    all_words = words(text)
    if not sentence_list or not all_words:
        return 0.0
    words_per_sentence = len(all_words) / len(sentence_list)
    syllables_per_word = sum(_count_syllables(w) for w in all_words) / len(all_words)
    grade = 0.39 * words_per_sentence + 11.8 * syllables_per_word - 15.59
    return round(max(0.0, grade), 1)


# ------------------------------------------------------------------- briefing


def style_brief(profile: StyleProfile, samples: list[str] | None = None) -> str:
    """Turn a measured profile into drafting instructions.

    Written as targets with tolerances rather than absolutes, because a draft
    that hits a mean sentence length exactly reads mechanical — the *spread*
    is what makes prose sound human, which is why the standard deviation is
    given as much weight as the mean.
    """
    if profile.word_count < MIN_USABLE_WORDS:
        return (
            "No usable style profile is available. Write in clear, formal "
            "academic prose suitable for a graduate health-sciences paper, and "
            "avoid the constructions that mark machine-written text: uniform "
            "sentence length, three-item lists everywhere, and openers such as "
            "“In today's world”, “It is important to note that”, “Moreover” at "
            "the start of consecutive paragraphs, and “delve into”."
        )

    lines = [
        "Match the author's measured writing style. These figures come from "
        "their own prior work:",
        "",
        f"- Sentence length: average {profile.mean_sentence_words} words, "
        f"standard deviation {profile.sentence_words_sd}. Vary length "
        f"deliberately — the spread matters more than the average. Do not write "
        f"a run of same-length sentences.",
        f"- Paragraphs: about {profile.mean_paragraph_sentences} sentences each.",
        f"- Passive voice: roughly {round(profile.passive_rate * 100)}% of "
        f"sentences. Do not push below this — health-sciences methods writing "
        f"uses the passive legitimately.",
        f"- Hedging ({', '.join(_HEDGES[:6])}…): about "
        f"{profile.hedge_rate} per 1,000 words. "
        + ("This author hedges heavily; keep claims appropriately cautious."
           if profile.hedge_rate > 12 else
           "This author states findings directly; do not over-qualify."),
        f"- First person (I, we, our): {profile.first_person_rate} per 1,000 "
        f"words. "
        + ("The author uses first person; APA 7 §4.16 permits it."
           if profile.first_person_rate > 2 else
           "The author avoids first person; keep to third person."),
        f"- Semicolons: {profile.semicolon_per_1k} per 1,000 words.",
        f"- Reading level: Flesch–Kincaid grade {profile.flesch_kincaid_grade}.",
    ]
    if profile.frequent_connectives:
        lines.append(
            f"- Connectives the author actually uses: "
            f"{', '.join(profile.frequent_connectives)}. Prefer these over "
            f"others, and do not open consecutive paragraphs with the same one."
        )
    if profile.frequent_terms:
        lines.append(
            f"- Recurring vocabulary: {', '.join(profile.frequent_terms[:15])}. "
            f"Use the author's own terms for concepts they have names for."
        )

    lines += [
        "",
        "Avoid the markers of machine-written prose regardless of the figures "
        "above: uniform sentence rhythm, tricolon lists as a default structure, "
        "“It is important to note that”, “plays a crucial role”, “delve into”, "
        "“navigate the complexities of”, “in today's rapidly evolving”, and "
        "closing paragraphs that restate the opening without adding anything.",
    ]

    if samples:
        excerpt = _representative_excerpt(samples, profile)
        if excerpt:
            lines += [
                "",
                "Here is the author writing in their own voice. Match this "
                "cadence and register — it is a better guide than any of the "
                "numbers above:",
                "",
                excerpt,
            ]
    return "\n".join(lines)


def _representative_excerpt(samples: list[str], profile: StyleProfile,
                            target_words: int = 320) -> str:
    """Pick the passage closest to the author's own average.

    A random excerpt might be an outlier paragraph. Choosing the one whose
    sentence length sits nearest the measured mean gives the drafting layer the
    author at their most typical.
    """
    candidates: list[tuple[float, str]] = []
    for sample in samples:
        for paragraph in paragraphs(_strip_citations(sample)):
            paragraph_words = words(paragraph)
            if not 60 <= len(paragraph_words) <= target_words * 1.6:
                continue
            sentence_lengths = [len(words(s)) for s in sentences(paragraph)
                                if len(words(s)) >= 3]
            if not sentence_lengths:
                continue
            mean = sum(sentence_lengths) / len(sentence_lengths)
            candidates.append((abs(mean - profile.mean_sentence_words), paragraph))
    if not candidates:
        return ""
    candidates.sort(key=lambda kv: kv[0])
    return "\n\n".join(text for _, text in candidates[:2])


def compare(draft_text: str, profile: StyleProfile) -> dict[str, object]:
    """Measure a draft against the target profile.

    Shown to the user after drafting so they can see where the output drifted,
    rather than being told it matches and having to take that on trust.
    """
    draft = build_profile([draft_text])
    if profile.word_count < MIN_USABLE_WORDS:
        return {"comparable": False,
                "note": "No reliable target profile to compare against."}

    def delta(name: str) -> dict[str, float]:
        target = float(getattr(profile, name) or 0)
        actual = float(getattr(draft, name) or 0)
        return {"target": target, "draft": actual, "difference": round(actual - target, 2)}

    metrics = {
        name: delta(name) for name in (
            "mean_sentence_words", "sentence_words_sd", "mean_paragraph_sentences",
            "passive_rate", "hedge_rate", "first_person_rate", "semicolon_per_1k",
            "type_token_ratio", "flesch_kincaid_grade",
        )
    }
    drifted = [
        name for name, values in metrics.items()
        if values["target"] and abs(values["difference"]) / max(values["target"], 0.01) > 0.35
    ]
    return {
        "comparable": True,
        "metrics": metrics,
        "drifted": drifted,
        "note": (
            "These metrics drifted more than 35% from your profile: "
            + ", ".join(drifted.copy())
            if drifted else
            "The draft sits within 35% of your profile on every measured feature."
        ),
    }
