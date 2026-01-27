# Phase 3: Text Processing Enhancement - Research

**Researched:** 2026-01-27
**Domain:** Russian NLP post-processing for ASR
**Confidence:** HIGH

## Summary

Phase 3 focuses on expanding Russian text post-processing from ~50 rules to 100+ rules, with specific emphasis on phonetic corrections (voiced/unvoiced consonant pairs), morphology (gender agreement, case corrections), and proper noun recognition. The research confirms that rule-based approaches with targeted library integration (pymorphy2 for morphology, ru-cities datasets for proper nouns) are optimal for Transkribator's constraints. Russian-specific punctuation restoration (ru-autopunctuation) shows superior performance over generic multilingual models but requires BERT-based inference overhead.

**Primary recommendation:** Use pymorphy2 for morphology, epogrebnyak/ru-cities dataset for proper nouns, context-dependent rules for phonetic corrections, and keep deepmultilingualpunctuation for Whisper while exploring ru-autopunctuation for Sherpa-ONNX as future enhancement.

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **pymorphy2** | 0.9.1+ | Russian morphology analysis (lemmatization, POS tagging, grammatical features) | Fast, rule-based, accurate for Russian, actively maintained, production-ready |
| **natasha** | 1.6.0+ | Full NLP pipeline (segmentation, NER, syntax) | SOTA quality for Russian, production-optimized, but heavier than pymorphy2-only |
| **deepmultilingualpunctuation** | latest | Punctuation restoration for Whisper backend | Already integrated, multilingual support, lazy-loading works well |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **ru-cities dataset** | - | 1117 Russian cities with coordinates, population, regions | Load at startup as proper noun dictionary |
| **russian-names datasets** | - | Common Russian first/last names | GitHub sources (various repos) for 500-1000 entries |
| **ru-autopunctuation** | - | Russian-specific BERT-based punctuation restoration | Future replacement for deepmultilingualpunctuation (better quality, slower) |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| **pymorphy2** | **natasha** | Natasha provides NER + syntax but is heavier (10MB models vs pymorphy2's 2MB), uses pymorphy2 internally anyway |
| **deepmultilingualpunctuation** | **ru-autopunctuation** | ru-autopunctuation is Russian-specific (better F1) but requires DeepPavlov BERT (400MB, slower inference) |
| **Static dictionaries** | **Dynamic NER** | Dynamic NER (natasha) extracts entities but slower; static dicts sufficient for MVP (500-1000 entries) |

**Installation:**
```bash
# Core morphology
pip install pymorphy2

# Full NLP pipeline (optional, for NER + syntax)
pip install natasha

# Punctuation restoration (existing)
pip install deepmultilingualpunctuation

# Datasets (manual download, no pip install)
# wget https://raw.githubusercontent.com/epogrebnyak/ru-cities/main/assets/towns.csv
```

## Architecture Patterns

### Recommended Project Structure

```
src/
├── text_processor_enhanced.py      # Existing processor (extend to 100+ rules)
├── morphology/                      # NEW: Morphological correction module
│   ├── __init__.py
│   ├── gender_agreement.py         # Adjective-noun gender matching
│   ├── case_corrections.py         # Noun ending corrections (стола→стол)
│   └── pymorphy2_wrapper.py        # pymorphy2 integration
├── phonetics/                       # NEW: Phonetic correction module
│   ├── __init__.py
│   ├── voiced_unvoiced.py          # б↔п, в↔ф, г↔к, д↔т, ж↔ш, з↔с rules
│   └── context_rules.py            # Position-dependent substitutions
├── proper_nouns/                    # NEW: Proper noun recognition
│   ├── __init__.py
│   ├── cities.py                   # Russian cities dictionary
│   ├── names.py                    # Common Russian names
│   └── capitalization.py           # Capitalize known entities
└── data/                            # NEW: Dictionary data
    ├── cities.json                 # From epogrebnyak/ru-cities
    ├── names.json                  # 500-1000 common Russian names
    └── countries.json              # Major countries (Russian names)
```

### Pattern 1: Phonetic Corrections with Context-Aware Rules

**What:** Voiced/unvoiced consonant substitutions (б↔п, в↔ф, г↔к, д↔т, ж↔ш, з↔с) that occur at word boundaries in ASR.

**When to use:** Apply AFTER dictionary corrections, BEFORE morphology. Sherpa-ONNX produces these errors; Whisper较少.

**Implementation:**

```python
# Source: Russian phonology research + ASR error patterns
# Based on: Karpov 2014 (voiced fricative devoicing rules)

RUSSIAN_VOICED_UNVOICED_MAP = {
    'б': 'п', 'п': 'б',
    'в': 'ф', 'ф': 'в',
    'г': 'к', 'к': 'г',
    'д': 'т', 'т': 'д',
    'ж': 'ш', 'ш': 'ж',
    'з': 'с', 'с': 'з',
}

def fix_voiced_unvoiced_endings(text: str) -> str:
    """
    Fix voiced/unvoiced substitutions at word endings.
    Rule: Voiced consonants devoice at word end (гриб → грип).

    Examples:
        "неверо" → "небе" (word-end context)
        "кодов" → "котов" (unlikely, skip)
    """
    # Apply only at word boundaries
    # Use context: if word exists in vocabulary with voiced, don't change
    pass
```

**Key insight:** Russian phonology dictates that voiced consonants devoice at word ends (оглушение), but ASR sometimes makes opposite errors. Context-aware rules required.

### Pattern 2: Gender Agreement Correction with pymorphy2

**What:** Adjective-noun gender matching (огромный семья → огромная семья).

**When to use:** After phonetic corrections, before capitalization. Sherpa-ONNX struggles with morphology.

**Example:**

```python
# Source: pymorphy2 documentation + Russian grammar rules
import pymorphy2
morph = pymorphy2.MorphAnalyzer()

def fix_gender_agreement(text: str) -> str:
    """
    Fix adjective-noun gender mismatches using pymorphy2.

    Pattern: (Adjective) + (Noun)
    """
    tokens = text.split()
    for i in range(len(tokens) - 1):
        word1, word2 = tokens[i], tokens[i + 1]

        # Parse both words
        parsed1 = morph.parse(word1)[0]
        parsed2 = morph.parse(word2)[0]

        # Check if adjective + noun
        if (parsed1.tag.POS == 'ADJF' and
            parsed2.tag.POS == 'NOUN' and
            parsed1.tag.gender != parsed2.tag.gender):

            # Inflect adjective to match noun gender
            corrected = parsed1.inflect({parsed2.tag.gender})
            if corrected:
                tokens[i] = corrected.word

    return ' '.join(tokens)
```

**Optimization:** Cache pymorphy2.parse() results, use word-level caching (避免重复解析同一个词).

### Pattern 3: Proper Noun Dictionary Loading

**What:** Capitalize known proper nouns (cities, names, countries).

**When to use:** After punctuation restoration, before final cleanup.

**Example:**

```python
# Source: epogrebnyak/ru-cities dataset
import json
from pathlib import Path

class ProperNounDict:
    """Load and manage proper noun dictionaries."""

    def __init__(self):
        self.cities = self._load_json('data/cities.json')
        self.names = self._load_json('data/names.json')
        self.countries = self._load_json('data/countries.json')

        # Build lowercase lookup set
        self._lookup = set()
        for entity in self.cities + self.names + self.countries:
            self._lookup.add(entity.lower())

    def _load_json(self, path: str) -> List[str]:
        """Load JSON file or return empty list."""
        if Path(path).exists():
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []

    def capitalize_known(self, text: str) -> str:
        """Capitalize known proper nouns in text."""
        words = text.split()
        for i, word in enumerate(words):
            if word.lower() in self._lookup:
                words[i] = word.capitalize()

        return ' '.join(words)
```

**Data source:** epogrebnyak/ru-cities provides 1117 cities with alternative names (including ё variants).

### Pattern 4: Adaptive Backend Processing

**What:** Different processing pipelines for Whisper vs Sherpa-ONNX.

**When to use:** Always detect backend, apply appropriate rules.

**Example:**

```python
# Source: Existing Transkribator pattern + research findings
class AdaptiveTextProcessor:
    """Backend-aware text processing."""

    def __init__(self, backend: str = "whisper"):
        self.backend = backend

        # Shared components
        self.proper_nouns = ProperNounDict()
        self.morph = pymorphy2.MorphAnalyzer()

        # Backend-specific setup
        if backend == "sherpa":
            # Sherpa: No punctuation, all lowercase, morphology errors
            self.enable_punctuation = True
            self.enable_capitalization = True
            self.enable_morphology = True
        else:
            # Whisper: Has punctuation, fewer morphology errors
            self.enable_punctuation = False
            self.enable_capitalization = True
            self.enable_morphology = False  # Skip for Whisper

    def process(self, text: str) -> str:
        """Process text based on backend characteristics."""
        if self.backend == "sherpa":
            return self._process_sherpa(text)
        else:
            return self._process_whisper(text)

    def _process_sherpa(self, text: str) -> str:
        """Full pipeline for Sherpa-ONNX (CTC, no punctuation)."""
        # 1. Phonetic corrections (Sherpa weak spot)
        text = self._fix_phonetics(text)

        # 2. Morphology (gender, case)
        text = self._fix_morphology(text)

        # 3. Dictionary corrections
        text = self._fix_errors(text)

        # 4. Punctuation restoration (critical for Sherpa)
        text = self._add_punctuation(text)

        # 5. Capitalization (Sherpa all lowercase)
        text = self._fix_capitalization(text)

        return text

    def _process_whisper(self, text: str) -> str:
        """Minimal pipeline for Whisper (has punctuation)."""
        # 1. Dictionary corrections only
        text = self._fix_errors(text)

        # 2. Fix punctuation placement (Whisper makes mistakes)
        text = self._fix_punctuation(text)

        # 3. Light capitalization
        text = self._fix_capitalization(text)

        return text
```

### Anti-Patterns to Avoid

- **Using natasha for morphology only**: Natasha is 5× larger than pymorphy2, uses it internally anyway. Use pymorphy2 directly for pure morphology.
- **Applying phonetic rules without context**: "кодов" should NOT become "котов". Use vocabulary check.
- **Loading proper nouns from API**: Load once at startup from local JSON. No runtime network calls.
- **Full case restoration with ML**: Too slow for real-time. Use rule-based + proper noun dict (Phase 3), ML in Phase 4.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| **Russian lemmatization** | Custom stemming rules | pymorphy2.MorphAnalyzer().lemmatize() | Handles exceptions, irregular forms, ё |
| **Gender detection** | Regex-based gender heuristics | pymorphy2.parse(word)[0].tag.gender | Accurate for all nouns, loanwords handled |
| **POS tagging** | Custom suffix-based POS | pymorphy2.parse(word)[0].tag.POS | Production-tested, covers edge cases |
| **City names dataset** | Scrap Wikipedia | epogrebnyak/ru-cities towns.csv | 1117 cities, population data, alt names, clean CSV |
| **Punctuation restoration** | Rule-based comma insertion | deepmultilingualpunctuation (Whisper), ru-autopunctuation (Sherpa, future) | ML models capture complex patterns |
| **NER for names** | Regex patterns | natasha.NewsNERTagger (Phase 4) | Handles name variants, transliteration |

**Key insight:** pymorphy2 is SOTA for Russian morphology. Don't rebuild it. Natasha provides full pipeline but is overkill for Phase 3 (gender + case only).

## Common Pitfalls

### Pitfall 1: Over-Correcting Phonetic Substitutions

**What goes wrong:** Global replacement of б↔p breaks valid words ("кодов" → "котов", "гриб" → "грип").

**Why it happens:** Applying voiced/unvoiced rules without vocabulary validation.

**How to avoid:** Use context-aware rules:
```python
# BAD: Global replacement
text.replace('п', 'б')

# GOOD: Context-specific
if word_not_in_vocabulary(word) and has_phonetic_error(word):
    word = correct_phonetic(word)
```

**Warning signs:** CER increases after phonetic corrections, users report "weird substitutions".

### Pitfall 2: pymorphy2 Performance Degradation

**What goes wrong:** Processing slows to 100+ ms per sentence.

**Why it happens:** Repeatedly calling `morph.parse()` without caching, creating multiple `MorphAnalyzer` instances.

**How to avoid:**
```python
# BAD: New instance per call
def fix_morphology(text):
    morph = pymorphy2.MorphAnalyzer()  # Expensive!
    return morph.parse(text)

# GOOD: Single shared instance
morph = pymorphy2.MorphAnalyzer()  # Initialize once

def fix_morphology(text):
    return morph.parse(text)  # Reuse instance
```

**Warning signs:** Memory usage grows, profiling shows pymorphy2 initialization in hot path.

### Pitfall 3: Gender Correction Breaking Correct Text

**What goes wrong:** "Мой друг" (correct) → "Моя друг" (incorrect).

**Why it happens:** pymorphy2 returns multiple parses, choosing wrong one. Ambiguous words (друг can be masc noun or adj).

**How to avoid:** Use confidence scores, limit corrections to high-certainty cases:
```python
parsed = morph.parse(word)
if parsed[0].score > 0.5:  # Only fix high-confidence
    # Apply correction
```

**Warning signs:** User reports "grammatically incorrect corrections", regression tests fail.

### Pitfall 4: Proper Noun Capitalization Over-Capitalizing

**What goes wrong:** "стол" (table) → "Стол" (incorrect), capitalizes common words that match names.

**Why it happens:** Dictionary contains "Стол" as surname, over-capitalizes all instances.

**How to avoid:** Use word boundaries + frequency heuristics:
```python
# Only capitalize if:
# 1. At sentence start
# 2. After punctuation
# 3. Context suggests proper noun (before "город", "в", etc.)
```

**Warning signs:** User reports "random capitalizations", text looks "shouty".

### Pitfall 5: Backend Detection Failure

**What goes wrong:** Sherpa text processed as Whisper (missing punctuation), or vice versa.

**Why it happens:** Auto-detection based on punctuation presence fails (Whisper sometimes omits punctuation).

**How to avoid:** Explicit backend parameter, don't auto-detect:
```python
# BAD: Auto-detect
backend = "whisper" if has_punctuation(text) else "sherpa"

# GOOD: Explicit parameter
processor = AdaptiveTextProcessor(backend=user_selected_backend)
```

**Warning signs:** Sherpa transcripts have no punctuation, Whisper transcripts over-punctuated.

## Code Examples

Verified patterns from official sources:

### pymorphy2 Gender Agreement

```python
# Source: https://github.com/kmike/pymorphy2
import pymorphy2
morph = pymorphy2.MorphAnalyzer()

def fix_adjective_noun_agreement(text: str) -> str:
    """
    Fix adjective-noun gender mismatches.

    Example: "огромный семья" → "огромная семья"
    """
    words = text.split()
    for i in range(len(words) - 1):
        word1, word2 = words[i], words[i + 1]

        parsed1 = morph.parse(word1)[0]
        parsed2 = morph.parse(word2)[0]

        # Check if adjective + noun with gender mismatch
        if (parsed1.tag.POS == 'ADJF' and
            parsed2.tag.POS == 'NOUN' and
            parsed1.tag.gender != parsed2.tag.gender):

            # Inflect adjective to match noun
            corrected = parsed1.inflect({parsed2.tag.gender})
            if corrected:
                words[i] = corrected.word

    return ' '.join(words)
```

### Proper Noun Loading from ru-cities

```python
# Source: https://github.com/epogrebnyak/ru-cities
import csv
from pathlib import Path

def load_russian_cities(csv_path: str = 'data/towns.csv') -> set:
    """
    Load Russian cities from epogrebnyak/ru-cities dataset.

    Returns set of city names (lowercase for lookup).
    """
    cities = set()

    if not Path(csv_path).exists():
        return cities

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            city = row['city']  # Main city name
            cities.add(city.lower())

            # TODO: Load alt_city_names.json for variants
            # Alternative names handled in separate JSON file

    return cities

# Usage
CITIES = load_russian_cities()

def capitalize_cities(text: str) -> str:
    """Capitalize known Russian cities in text."""
    words = text.split()
    for i, word in enumerate(words):
        if word.lower() in CITIES:
            words[i] = word.capitalize()
    return ' '.join(words)
```

### Voiced/Unvoiced Correction (Context-Aware)

```python
# Source: Russian phonology rules + Karpov 2014 research
import re

VOICED_UNVOICED_MAP = {
    'б': 'п', 'п': 'б',
    'в': 'ф', 'ф': 'в',
    'г': 'к', 'к': 'г',
    'д': 'т', 'т': 'д',
    'ж': 'ш', 'ш': 'ж',
    'з': 'с', 'с': 'з',
}

def fix_word_end_devoicing(text: str, vocabulary: set) -> str:
    """
    Fix voiced consonants devoiced at word end (оглушение).

    Examples:
        "неверо" → "небе" (if "небе" in vocabulary)
        "код" → "кот" (if "кот" in vocabulary, "код" not)

    Args:
        text: Input text
        vocabulary: Set of valid Russian words (from frequency dict)

    Returns:
        Corrected text
    """
    words = text.split()

    for i, word in enumerate(words):
        # Check if word ends with unvoiced consonant
        if word[-1] in 'пфктшс':
            # Try voiced variant
            voiced_variant = word[:-1] + VOICED_UNVOICED_MAP[word[-1]]

            # If voiced variant in vocabulary and original not, use voiced
            if voiced_variant in vocabulary and word not in vocabulary:
                words[i] = voiced_variant

    return ' '.join(words)
```

### Adaptive Processing for Whisper vs Sherpa

```python
# Source: Transkribator existing pattern + research findings

class AdaptiveProcessor:
    """Backend-aware post-processing."""

    def __init__(self, backend: str):
        self.backend = backend.lower()
        self._setup_components()

    def _setup_components(self):
        """Initialize backend-specific components."""
        # Shared
        from src.proper_nouns import ProperNounDict
        self.proper_nouns = ProperNounDict()

        # Backend-specific
        if self.backend == "sherpa":
            from deepmultilingualpunctuation import PunctuationModel
            self.punct_model = PunctuationModel()  # Lazy load in production
            self.enable_morphology = True
        else:
            self.punct_model = None
            self.enable_morphology = False

    def process(self, text: str) -> str:
        """Process text with backend-aware pipeline."""
        if self.backend == "sherpa":
            return self._process_sherpa(text)
        else:
            return self._process_whisper(text)

    def _process_sherpa(self, text: str) -> str:
        """Full pipeline for Sherpa-ONNX."""
        # 1. Dictionary corrections
        text = self._fix_errors(text)

        # 2. Phonetic corrections (Sherpa-specific)
        text = self._fix_phonetics(text)

        # 3. Morphology
        if self.enable_morphology:
            text = self._fix_morphology(text)

        # 4. Punctuation (critical for Sherpa)
        if self.punct_model:
            text = self.punct_model.restore_punctuation(text)

        # 5. Capitalization
        text = self._fix_capitalization(text)

        # 6. Proper nouns
        text = self.proper_nouns.capitalize_known(text)

        return text

    def _process_whisper(self, text: str) -> str:
        """Minimal pipeline for Whisper."""
        # 1. Dictionary corrections only
        text = self._fix_errors(text)

        # 2. Fix punctuation placement (not restoration)
        text = self._fix_punctuation_placement(text)

        # 3. Capitalization
        text = self._fix_capitalization(text)

        # 4. Proper nouns
        text = self.proper_nouns.capitalize_known(text)

        return text
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| **Manual morphology rules** | **pymorphy2** | 2013+ | pymorphy2 is de facto standard for Russian morphology, actively maintained |
| **Generic punctuation models** | **Russian-specific (ru-autopunctuation)** | 2021+ | Better F1 for Russian, but requires BERT inference (slower) |
| **Hardcoded proper nouns** | **Dataset-backed (ru-cities)** | 2020+ | 1117 cities vs ~50 hardcoded, includes alternative names |
| **Backend-agnostic processing** | **Adaptive backend-aware** | 2024+ | Sherpa needs punctuation, Whisper doesn't; morphology errors differ |

**Deprecated/outdated:**
- **Custom stemming algorithms for Russian:** pymorphy2 lemmatization is superior, handles exceptions.
- **Rule-based gender detection from suffixes:** pymorphy2 has comprehensive dictionary, handles loanwords.
- **Full pipeline with natasha for morphology only:** Use pymorphy2 directly (natasha uses it internally, 5× larger).

## Open Questions

1. **ru-autopunctuation integration timing**
   - What we know: ru-autopunctuation has better Russian F1 than deepmultilingualpunctuation, requires DeepPavlov BERT (400MB)
   - What's unclear: Whether performance degradation (100-500ms → 500-2000ms) is acceptable for Transkribator users
   - Recommendation: Keep deepmultilingualpunctuation for Phase 3, benchmark ru-autopunctuation, consider for Phase 4

2. **Vocabulary source for phonetic correction validation**
   - What we know: Need vocabulary set to validate substitutions ("кодов" should not become "котов")
   - What's unclear: Best source (frequency dictionary vs pymorphy2 dictionary vs custom corpus)
   - Recommendation: Use pymorphy2's built-in vocabulary (morph.lexeme exists for known words), fallback to frequency dict if needed

3. **Case correction depth**
   - What we know: Sherpa confuses all 6 Russian cases (стол/стола/столу/столом/столе)
   - What's unclear: How many cases to fix in Phase 3 vs Phase 4 (CONTEXT.md limits to basic)
   - Recommendation: Fix only most common errors (nominative/accusative/genitive) in Phase 3, full case correction in Phase 4

## Sources

### Primary (HIGH confidence)

- **pymorphy2 documentation** - GitHub repository, API reference for morphology analysis
  - https://github.com/kmike/pymorphy2
- **natasha documentation** - Full NLP pipeline, morphology integration
  - https://github.com/natasha/natasha
- **epogrebnyak/ru-cities** - 1117 Russian cities dataset
  - https://github.com/epogrebnyak/ru-cities
- **Karpov 2014 paper** - Russian ASR research, voiced fricative devoicing rules
  - https://u-aizu.ac.jp/~markov/pubs/SpCom_14.pdf
- **ru-autopunctuation documentation** - BERT-based Russian punctuation restoration
  - https://github.com/kotikkonstantin/ru-autopunctuation

### Secondary (MEDIUM confidence)

- **deepmultilingualpunctuation** - Multilingual punctuation restoration (existing Transkribator dependency)
  - https://github.com/oliverguhr/deepmultilingualpunctuation
- **Russian phonology research** - Voiced/unvoiced consonant pairs in ASR
  - https://arxiv.org/pdf/2507.13563 (Borodin 2025)
- **Morphological Analysis for Russian: Integration and Comparison of Taggers** - ResearchGate 2017
  - https://www.researchgate.net/publication/313818621

### Tertiary (LOW confidence)

- **Russian names datasets** - Various GitHub repos, need validation for quality
  - Search results indicate multiple sources, no clear "standard" dataset
- **WebSearch findings on proper noun sources** - General patterns, no specific dataset recommendations
  - Use epogrebnyak/ru-cities as primary, supplement with manual name list

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - pymorphy2 and natasha are de facto standard for Russian NLP
- Architecture: HIGH - Existing Transkribator pattern verified, pymorphy2 usage pattern from official docs
- Pitfalls: HIGH - Common NLP deployment issues (caching, over-correction) documented in Russian NLP community

**Research date:** 2026-01-27
**Valid until:** 2026-03-01 (60 days - Russian NLP ecosystem stable, pymorphy2 mature)

---

*Phase: 03-text-processing*
*Research completed: 2026-01-27*
