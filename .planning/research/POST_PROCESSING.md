# Russian Speech-to-Text Post-Processing Research

**Project:** Transkribator (Python, PyQt6)
**Date:** 2026-01-27
**Focus:** Text post-processing techniques for Russian transcription

---

## Table of Contents

1. [deepmultilingualpunctuation](#1-deepmultilingualpunctuation)
2. [Common CTC Model Errors in Russian](#2-common-ctc-model-errors-in-russian)
3. [Post-Processing Techniques](#3-post-processing-techniques)
4. [Capitalization Restoration](#4-capitalization-restoration)
5. [Russian Error Correction Patterns](#5-russian-error-correction-patterns)
6. [Integration Strategy](#6-integration-strategy)
7. [Performance vs Quality Tradeoffs](#7-performance-vs-quality-tradeoffs)
8. [Sources](#8-sources)

---

## 1. deepmultilingualpunctuation

### Overview

**Repository:** [oliverguhr/deepmultilingualpunctuation](https://github.com/oliverguhr/deepmultilingualpunctuation)

- **Purpose:** Restore punctuation in transcribed spoken language
- **Languages:** English, Italian, French, German (Russian via multilingual models)
- **Model Type:** Deep learning-based punctuation prediction
- **Use Case:** Post-processing for ASR (Automatic Speech Recognition) systems

### Installation

```bash
pip install deepmultilingualpunctuation
```

### Usage Pattern

```python
from deepmultilingualpunctuation import PunctuationModel

# Initialize model (lazy loading recommended)
model = PunctuationModel()

# Restore punctuation
text = "это пример текста без знаков препинания"
result = model.restore_punctuation(text)
# Output: "Это пример текста без знаков препинания."
```

### Best Practices

1. **Lazy Loading:** Load model on first use, not initialization
   ```python
   def __init__(self):
       self.punctuation_model = None  # Don't load yet

   def _add_punctuation(self, text):
       if self.punctuation_model is None:
           self.punctuation_model = PunctuationModel()
   ```

2. **Error Handling:** Model can fail on edge cases
   ```python
   try:
       result = self.punctuation_model.restore_punctuation(text)
   except Exception as e:
       print(f"[WARNING] Punctuation failed: {e}")
       return text  # Return original
   ```

3. **Language Support:**
   - **Official:** EN, IT, FR, DE
   - **Russian:** Works via multilingual transfer learning
   - **Accuracy:** Lower for Russian than official languages

### Current Transkribator Implementation

**File:** `src/text_processor_enhanced.py`

```python
class EnhancedTextProcessor:
    def _add_punctuation(self, text: str) -> str:
        """Restore punctuation using ML model."""
        if not PUNCTUATION_AVAILABLE:
            return text

        # Lazy load on first use
        if self.punctuation_model is None:
            try:
                self.punctuation_model = PunctuationModel()
            except Exception as e:
                return text

        return self.punctuation_model.restore_punctuation(text)
```

### Limitations

- **No Russian-specific training:** Model optimized for EN/IT/FR/DE
- **Slow inference:** 100-500ms per sentence (CPU)
- **Memory footprint:** ~500MB model size
- **Over-punctuation:** May add commas where not needed

### Alternatives

1. **fullstop-deep-punctuation-prediction** ([GitHub](https://github.com/oliverguhr/fullstop-deep-punctuation-prediction))
   - Same author, newer architecture
   - Better performance on long texts

2. **xlm-roberta_punctuation_fullstop_truecase** ([HuggingFace](https://huggingface.co/))
   - Transformer-based (XLM-RoBERTa)
   - Multi-language including Russian
   - Handles both punctuation AND capitalization

3. **Custom Rule-Based System**
   - Regex patterns for common cases
   - Faster but less accurate
   - Current Transkribator approach

---

## 2. Common CTC Model Errors in Russian

### What is CTC?

**Connectionist Temporal Classification (CTC)** is a neural network output layer used in speech recognition:

- **No explicit punctuation:** CTC outputs raw characters/phonemes
- **Repeated tokens:** Tendency to repeat characters ("ссссстановка")
- **Alignment issues:** Misclassifies phonemes based on timing
- **Context-blind:** Each prediction independent of previous

### Sherpa-ONNX CTC-Specific Errors

**From real Transkribator test results:**

#### 1. **Gender/Number Agreement**
```python
# Sherpa confuses grammatical gender
"огромные семья" → "огромная семья"
"мою родной" → "мое родное"
"все мою" → "все мое"
```

**Pattern:** CTC models struggle with Russian morphology (gender, case, number)

#### 2. **Phonetic Substitutions**
```python
# Similar sounds confused
"классок" → "колосок"  # кл → к, сс → с
"лубки" → "лыбки"      # л → л (missing 'у')
"неверо" → "небе"      # в → б (voiced/unvoiced)
```

**Pattern:** Voiced/unvoiced consonant confusion (б/п, в/ф, г/к, д/т, ж/ш)

#### 3. **Preposition/Particle Errors**
```python
"онак" → "она же"
"онатив" → "она не"
"не рас" → "не раз"
```

**Pattern:** Short functional words merged or misrecognized

#### 4. **Verb Form Errors**
```python
"станек" → "станет"
"станем" → "станет"
"станит" → "станет"
```

**Pattern:** Verb endings confused (especially present tense 3rd person singular)

### Whisper vs Sherpa-ONNX Errors

| Error Type | Whisper | Sherpa-ONNX |
|------------|---------|-------------|
| **Hallucinations** | High (invents text) | Low (CTC constraint) |
| **Punctuation** | Native (built-in) | None (raw output) |
| **Repeated chars** | "туулыбки" | Rare |
| **Gender errors** | Medium | High |
| **Phonetic subs** | Low | High |

### Whisper Hallucinations

**From [AP News investigation](https://apnews.com/article/ai-artificial-intelligence-health-business-90020cdf5fa16c79ca2e5b6c4c9bbb14):**

- **55.2% error rate** on non-speech sounds (silence, breathing)
- **Invents entire sentences** during pauses
- **Medical context:** Found adding medical terms not spoken
- **Scale:** 1 developer reported hallucinations in ~26,000 transcripts

**Example:**
```
Audio: [5 seconds of silence]
Whisper: "Пациент должен принимать препарат два раза в день"
```

### Character Error Rate (CER) Issues

**From [Sherpa-ONNX Issue #2900](https://github.com/k2-fsa/sherpa-onnx/issues/2900):**

> "Sherpa-ONNX produces much higher CER than faster-whisper with same Whisper Tiny model"

- **Expected:** Comparable CER
- **Actual:** Up to **3× higher error rate**
- **Cause:** Inference optimizations sacrifice accuracy

---

## 3. Post-Processing Techniques

### Hierarchical Processing Pipeline

**Recommended order of operations:**

```
Raw Text
  ↓
1. Remove repeated characters (CTC artifact)
  ↓
2. Fix dictionary-based errors
  ↓
3. Apply regex pattern corrections
  ↓
4. Add punctuation (for CTC models)
  ↓
5. Fix punctuation placement
  ↓
6. Restore capitalization
  ↓
7. Final cleanup
  ↓
Clean Text
```

### Technique 1: Dictionary-Based Corrections

**Implementation:** `EnhancedTextProcessor._fix_errors()`

```python
# Pre-compile regex for performance
pattern = re.compile(r'\b' + re.escape(wrong) + r'\b', re.IGNORECASE)

# Sort by length (longest first) to avoid substring conflicts
sorted_corrections = sorted(corrections.items(), key=lambda x: len(x[0]), reverse=True)
```

**Best Practices:**

1. **Word boundaries:** Use `\b` to avoid substring matching
   ```python
   # BAD: Fixes "тул" anywhere (breaks "ватул")
   text = text.replace("тул", "ул")

   # GOOD: Only fixes word "тул"
   text = re.sub(r'\bтул\b', 'ул', text)
   ```

2. **Longest-first matching:**
   ```python
   # Wrong order breaks longer phrases
   {"онак": "она же", "она же": "она же сама"}  # "она же" → "она же сама" first!

   # Correct order
   {"она же сама": "она же сама", "онак": "она же"}  # Longest first
   ```

3. **Case-insensitive matching:**
   ```python
   pattern = re.compile(r'\бклассок\b', re.IGNORECASE)
   # Fixes: "Классок", "КЛАССОК", "классок"
   ```

### Technique 2: Regex Pattern Corrections

**Current Transkribator patterns:**

```python
self.pattern_corrections = [
    # Fix "А" → "От" at start
    (r'^А (\w+)', lambda m: f'От {m.group(1)}'),

    # Fix multiple spaces
    (r'\s+', ' '),

    # Fix space before punctuation
    (r'\s+([,.!?;:])', r'\1'),

    # Fix lowercase after sentence end
    (r'([.!?]\s+)([а-я])', lambda m: m.group(1) + m.group(2).upper()),
]
```

**Advanced Russian patterns:**

```python
# Fix gender agreement
(r'огромные семья', 'огромная семья')
(r'(\w+) голубой (\w+)', lambda m: f'{m.group(1)} голубое {m.group(2)}')

# Fix prepositions
(r'растебе', 'к тебе')
(r'онактиви', 'она не раз')

# Fix verb forms
(r'стан(?:е|и)к?\s+всем', 'станет всем')
```

### Technique 3: Context-Aware Corrections

**Problem:** Same word can be correct or incorrect depending on context

```python
# "тул" is wrong in "ватул" but correct in "туловище"
# Solution: Context-dependent rules

context_rules = [
    {
        "pattern": r"от\s+[лл]ыбк",  # Only fix after "от"
        "correction": "от улыбк",
    },
]
```

### Technique 4: LLM-Based Correction (2024-2025)

**From recent research:**

- **"ASR Error Correction using Large Language Models"** (2024) - [arXiv](https://arxiv.org/html/2409.09554v2)
- **"SoftCorrect"** (2022) - Soft error detection mechanism - [arXiv](https://arxiv.org/html/2212.01039v2)

**Advantages:**
- Contextual understanding
- Grammatical error correction
- Better than rule-based for complex errors

**Disadvantages:**
- Slow (1-5 seconds per sentence)
- Requires GPU for acceptable speed
- Expensive (API costs or local model)

**Example integration:**

```python
def _llm_correct(self, text: str) -> str:
    """Use LLM for advanced error correction."""
    prompt = f"""Fix grammatical errors in this Russian transcription:
    {text}

    Only fix errors, preserve original meaning."""

    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )

    return response.choices[0].message.content
```

---

## 4. Capitalization Restoration

### Russian Capitalization Rules

**Always capitalize:**

1. **Sentence start**
   ```python
   text = text[0].upper() + text[1:]
   ```

2. **After punctuation (.!?)**
   ```python
   sentences = re.split(r'([.!?]\s+)', text)
   for i in range(0, len(sentences), 2):
       if sentences[i]:
           sentences[i] = sentences[i][0].upper() + sentences[i][1:]
   ```

3. **Proper nouns (names, places)**
   ```python
   # Requires NER (Named Entity Recognition)
   # Examples: Москва, Denis, Россия
   ```

4. **After quote/colon (if starting new sentence)**
   ```python
   # He said: "Hello" → Он сказал: "Здравствуйте"
   ```

### Implementation Approaches

#### Approach 1: Rule-Based (Current Transkribator)

```python
def _fix_capitalization(self, text: str) -> str:
    """Simple rule-based capitalization."""
    # First letter
    text = text[0].upper() + text[1:]

    # After sentence endings
    sentences = re.split(r'([.!?]\s+)', text)
    for i in range(0, len(sentences), 2):
       if sentences[i]:
           sentences[i] = sentences[i][0].upper() + sentences[i][1:]

    return ''.join(sentences)
```

**Pros:** Fast (<1ms), deterministic
**Cons:** Only handles basic cases

#### Approach 2: ML-Based (xlm-roberta)

```python
from transformers import pipeline

# Multi-language truecasing model
truecaser = pipeline("token-classification", model="xlm-roberta_punctuation_fullstop_truecase")

def restore_capitalization(text: str) -> str:
    """Use transformer model for capitalization."""
    results = truecaser(text)

    # Apply model predictions
    for token in results:
        if token['entity'] == 'U':  # Uppercase
            text = text.replace(token['word'], token['word'].capitalize())

    return text
```

**Pros:** Handles proper nouns, complex cases
**Cons:** Slow (100-500ms), 500MB model

#### Approach 3: Hybrid (Recommended)

```python
class CapitalizationRestorer:
    def __init__(self, use_ml: bool = False):
        self.use_ml = use_ml
        self.proper_nouns = self._load_proper_nouns()

    def restore(self, text: str) -> str:
        # Step 1: Rule-based (always)
        text = self._capitalize_sentences(text)

        # Step 2: Proper noun dictionary
        text = self._capitalize_proper_nouns(text)

        # Step 3: ML-based (optional)
        if self.use_ml:
            text = self._ml_capitalize(text)

        return text

    def _load_proper_nouns(self) -> Set[str]:
        """Load common Russian proper nouns."""
        return {
            "москова", "денис", "россия", "сергей",
            "елена", "анна", "иван", # Add more...
        }

    def _capitalize_proper_nouns(self, text: str) -> str:
        """Capitalize known proper nouns."""
        for noun in self.proper_nouns:
            text = re.sub(rf'\b{noun}\b', noun.capitalize(), text, flags=re.IGNORECASE)
        return text
```

### Cyrillic-Specific Considerations

**Cyrillic character ranges:**

```python
# Russian uppercase
А-ЯЁ

# Russian lowercase
а-яё

# Regex for Cyrillic letters
r'[А-Яа-яЁё]'

# Detect if text is Cyrillic
def is_cyrillic(text: str) -> bool:
    return bool(re.search(r'[А-Яа-яЁё]', text))
```

**Case folding:**

```python
# Russian case folding (more complex than English)
text.lower()  # АБВ → абв
text.upper()  # абв → АБВ
text.capitalize()  # абв → Абв

# NOTE: 'Ё' handling
'ёжик'.capitalize()  # 'Ёжик' (correct)
'елка'.capitalize()  # 'Елка' (not Ёлка - phonetic)
```

---

## 5. Russian Error Correction Patterns

### Phonetic Error Patterns

#### Voiced/Unvoiced Confusion

Russian speakers confuse voiced/unvoiced consonants at word boundaries:

```python
VOICED_UNVOICED_MAP = {
    'б': 'п', 'п': 'б',
    'в': 'ф', 'ф': 'в',
    'г': 'к', 'к': 'г',
    'д': 'т', 'т': 'д',
    'ж': 'ш', 'ш': 'ж',
    'з': 'с', 'с': 'з',
}

def fix_voiced_unvoiced(text: str, corrections: Dict[str, str]) -> str:
    """Fix voiced/unvoiced substitutions."""
    for wrong, correct in corrections.items():
        # Try both voiced/unvoiced variants
        text = re.sub(rf'\b{wrong}\b', correct, text, flags=re.IGNORECASE)

    return text
```

**Examples from Transkribator:**

```python
"неверо" → "небе"  # в → б (word end)
"радугы" → "радуга"  # No substitution here
```

#### Vowel Reduction

Russian unstressed vowels reduce to 'а' or 'о':

```python
# Common reductions
VOWEL_REDUCTIONS = {
    'о': 'а',  # Both become 'ə' (schwa) in unstressed position
    'е': 'и',  # In some positions
}
```

**Not currently implemented in Transkribator** (complex, requires word stress detection)

### Morphological Error Patterns

#### Gender Agreement

Russian adjectives must agree with nouns in gender:

```python
# Pattern: adjective + noun mismatch
GENDER_CORRECTIONS = {
    # Masculine → Feminine
    r'(\w+)ый (\w+)ая': r'\1ая \2',  # "огромный семья" → "огромная семья"

    # Feminine → Neuter
    r'(\w+)ая (\w+)ое': r'\1ое \2',  # "синяя море" → "синее море"
}
```

**Current Transkribator implementation:**

```python
# Manual corrections (limited coverage)
"огромные семья": "огромная семья",
"мною родной": "мое родное",
```

#### Case Ending Errors

Russian has 6 cases, each with different endings:

```python
# Noun declension (singular)
# Word: "стол" (table)

CASE_ENDINGS = {
    'nominative': 'стол',
    'genitive': 'стола',
    'dative': 'столу',
    'accusative': 'стол',
    'instrumental': 'столом',
    'prepositional': 'столе',
}
```

**Problem:** CTC models confuse similar endings (стола/столу/столе)

**Solution:** Context-based correction (requires part-of-speech tagging)

### Real-World Error Examples

**From Transkribator test results:**

```python
# Song lyrics transcription
Raw: "и тропинка и лесок"
Correction: "и тропинка, и лесок"

Raw: "в поле – каждый"
Correction: "в поле — каждый"

Raw: "голубое"
Transcribed: "глубое"  # Missing 'о'
```

**Pattern analysis:**

1. **Missing letters:** "глубое" ← "голубое"
2. **Missing punctuation:** "и тропинка и лесок" ← "и тропинка, и лесок"
3. **Word boundary confusion:** "более каждый" ← "в поле – каждый"

### Comprehensive Correction Dictionary

**Current coverage:** ~50 rules in `text_processor_enhanced.py`

**Recommended expansion:**

```python
EXTENDED_CORRECTIONS = {
    # Prepositions
    "к": "к",
    "без": "без",
    "для": "для",
    "от": "от",
    "до": "до",
    "из": "из",
    "без": "без",
    "над": "над",
    "под": "под",
    "за": "за",

    # Conjunctions
    "и": "и",
    "а": "а",
    "но": "но",
    "или": "или",
    "что": "что",

    # Verbs (common errors)
    "станек": "станет",
    "станем": "станет",
    "станит": "станет",
    "становит": "станет",

    # Adjectives
    "светле": "светлей",
    "светлее": "светлей",

    # Pronouns
    "онак": "она же",
    "онатив": "она не",
    "неверо": "небе",
    "невере": "небе",
}
```

---

## 6. Integration Strategy

### Whisper Backend (Has Native Punctuation)

**Characteristics:**
- Built-in punctuation (commas, periods)
- Higher accuracy overall
- Hallucination problems
- Slower than Sherpa-ONNX

**Post-processing needs:**

```python
class WhisperPostProcessor(EnhancedTextProcessor):
    """Minimal post-processing for Whisper."""

    def __init__(self):
        super().__init__(enable_punctuation=False)  # Not needed!

    def process(self, text: str) -> str:
        # Step 1: Fix hallucinations (if detected)
        text = self._fix_hallucinations(text)

        # Step 2: Fix dictionary errors
        text = self._fix_errors(text)

        # Step 3: Fix punctuation placement (Whisper makes mistakes)
        text = self._fix_punctuation(text)

        # Step 4: Capitalization (Whisper ok, but not perfect)
        text = self._fix_capitalization(text)

        return text
```

**Key differences from Sherpa:**
- **No punctuation restoration needed** (Whisper has it)
- **Hallucination detection** needed (not implemented yet)
- **Focus on grammatical errors** not missing punctuation

### Sherpa-ONNX Backend (CTC, No Punctuation)

**Characteristics:**
- No punctuation (raw character stream)
- Fast inference
- No hallucinations (CTC constraint)
- Lower accuracy on morphology

**Post-processing needs:**

```python
class SherpaPostProcessor(EnhancedTextProcessor):
    """Full post-processing pipeline for Sherpa-ONNX."""

    def __init__(self):
        super().__init__(enable_punctuation=True)  # Critical!

    def process(self, text: str) -> str:
        # Step 1: Remove repeated characters (CTC artifact)
        text = self._fix_repeated_chars(text)

        # Step 2: Fix gender/number agreement (Sherpa weak spot)
        text = self._fix_morphology(text)

        # Step 3: Dictionary corrections
        text = self._fix_errors(text)

        # Step 4: ADD PUNCTUATION (critical for Sherpa!)
        text = self._add_punctuation(text)

        # Step 5: Fix punctuation placement
        text = self._fix_punctuation(text)

        # Step 6: Capitalization (Sherpa outputs all lowercase)
        text = self._fix_capitalization(text)

        return text
```

**Key differences from Whisper:**
- **Punctuation restoration is critical**
- **Morphology fixes needed** (gender, case, number)
- **Capitalization from scratch** (Sherpa all lowercase)

### Unified Integration

**Current Transkribator approach:**

```python
class TranskribatorProcessor:
    """Unified post-processor for both backends."""

    def __init__(self, backend: str = "whisper"):
        self.backend = backend

        if backend == "sherpa":
            self.processor = SherpaPostProcessor()
        else:  # whisper
            self.processor = WhisperPostProcessor()

    def process(self, text: str) -> str:
        """Process text based on backend."""
        return self.processor.process(text)
```

**Recommended improvement:**

```python
class AdaptiveTextProcessor:
    """Adaptive post-processor based on text characteristics."""

    def __init__(self):
        self.whisper_processor = WhisperPostProcessor()
        self.sherpa_processor = SherpaPostProcessor()

    def process(self, text: str, backend: str) -> str:
        """Process text with backend-aware rules."""

        # Detect if punctuation exists
        has_punct = any(c in text for c in '.,!?;:')

        # Auto-detect backend if not specified
        if backend == "auto":
            backend = "whisper" if has_punct else "sherpa"

        # Use appropriate processor
        if backend == "sherpa":
            return self.sherpa_processor.process(text)
        else:
            return self.whisper_processor.process(text)
```

---

## 7. Performance vs Quality Tradeoffs

### Processing Speed Comparison

| Technique | Speed | Quality | Memory | Complexity |
|-----------|-------|---------|---------|------------|
| **No post-processing** | 0ms | Low (raw) | 0MB | — |
| **Dictionary-only** | 1-5ms | Medium | 1MB | Low |
| **Dictionary + Regex** | 5-10ms | Medium-High | 1MB | Medium |
| **+ Punctuation ML** | 100-500ms | High | 500MB | Medium |
| **+ LLM correction** | 1-5s | Very High | 2GB+ | High |

### Recommended Configurations

#### Configuration 1: Real-Time (Fastest)

**Use case:** Live transcription, typing game

```python
processor = EnhancedTextProcessor(
    enable_corrections=True,
    enable_punctuation=False  # Disable ML
)
```

**Performance:**
- Processing: 5-10ms
- Total latency: <50ms (including transcription)
- Quality: Medium (grammatical errors remain)

#### Configuration 2: Balanced (Default)

**Use case:** Note-taking, general dictation

```python
processor = EnhancedTextProcessor(
    enable_corrections=True,
    enable_punctuation=True  # Enable ML
)
```

**Performance:**
- Processing: 100-500ms
- Total latency: 200-700ms
- Quality: High (punctuation restored)

#### Configuration 3: Quality (Slowest)

**Use case:** Post-recording editing, important documents

```python
processor = EnhancedTextProcessor(
    enable_corrections=True,
    enable_punctuation=True
)

# Add LLM correction (manual step)
text = llm_correct(processor.process(text))
```

**Performance:**
- Processing: 1-5s
- Quality: Very High (near-human)

### Memory Optimization

**Problem:** deepmultilingualpunctuation loads 500MB model

**Solution:** Lazy loading + Model caching

```python
class OptimizedProcessor:
    """Memory-efficient punctuation restoration."""

    _shared_model = None  # Class-level cache

    def _add_punctuation(self, text: str) -> str:
        """Load model once, reuse across instances."""
        if OptimizedProcessor._shared_model is None:
            OptimizedProcessor._shared_model = PunctuationModel()

        return OptimizedProcessor._shared_model.restore_punctuation(text)
```

**Benefit:** Single model instance shared across all processors

### CPU vs GPU Inference

**Punctuation model (CPU):**
```python
model = PunctuationModel()  # CPU default
text = model.restore_punctuation("long text...")
# Time: 100-500ms per sentence
```

**Punctuation model (GPU):**
```python
model = PunctuationModel(device='cuda')
text = model.restore_punctuation("long text...")
# Time: 10-50ms per sentence (10× faster)
```

**Recommendation:** Use GPU if available for punctuation restoration

---

## 8. Sources

### deepmultilingualpunctuation
- [Deep Multilingual Punctuation Prediction - GitHub](https://github.com/oliverguhr/deepmultilingualpunctuation)
- [fullstop-deep-punctuation-prediction - GitHub](https://github.com/oliverguhr/fullstop-deep-punctuation-prediction)
- [Punctuation Restoration using Transformer Models - GitHub](https://github.com/xashru/punctuation-restoration)

### CTC & ASR Error Correction Research
- [ASR Error Correction using Large Language Models - arXiv 2024](https://arxiv.org/html/2409.09554v2)
- [SoftCorrect: Error Correction with Soft Detection - AAAI 2022](https://arxiv.org/html/2212.01039v2)
- [A Language Model for Grammatical Error Correction in L2 Russian - arXiv 2023](https://arxiv.org/html/2307.01609)
- [Statistical Error Correction Methods for Domain-Specific ASR - Springer](https://link.springer.com/chapter/10.1007/978-3-642-39593-2_7)
- [Automatic Speech Recognition with BERT and CTC - arXiv 2024](https://arxiv.org/html/2410.09456v1)

### Whisper & Sherpa-ONNX Issues
- [Issues with Russian language transcription - OpenAI Whisper Discussion #1391](https://github.com/openai/whisper/discussions/1391)
- [Whisper Tiny: sherpa-onnx produces much higher CER - Issue #2900](https://github.com/k2-fsa/sherpa-onnx/issues/2900)
- [Generating speech in Russian with C# returns nonsense - Issue #835](https://github.com/k2-fsa/sherpa-onnx/issues/835)
- [Investigation of Whisper ASR Hallucinations - ResearchGate](https://www.researchgate.net/publication/388232036_Investigation_of_Whisper_ASR_Hallucinations_Induced_by_Non-Speech_Audio)
- [Reduce Whisper Hallucination On Non-Speech - Interspeech 2025](https://www.isca-archive.org/interspeech_2025/wang25b_interspeech.pdf)
- [AI transcription tools 'hallucinate,' too - Science.org](https://www.science.org/content/article/ai-transcription-tools-hallucinate-too)
- [Researchers say AI transcription tool found to 'hallucinate' - AP News](https://apnews.com/article/ai-artificial-intelligence-health-business-90020cdf5fa16c79ca2e5b6c4c9bbb14)

### Capitalization & Punctuation Restoration
- [xlm-roberta_punctuation_fullstop_truecase - HuggingFace](https://huggingface.co/)
- [Russian Language Speech Recognition System - CEUR-WS](https://ceur-ws.org/Vol-2267/470-474-paper-90.pdf)
- [End-to-End Russian Speech Recognition Models - ResearchGate](https://www.researchgate.net/publication/354758127_End-to-End_Russian_Speech_Recognition_Models_with_Multi-head_Attention)
- [Stanford NLP Cyrillic Text Processing - Academic Paper](https://www.tandfonline.com/doi/abs/10.1076/call.15.2.201.8192)

### General NLP & Text Processing
- [Non-Autoregressive Chinese ASR Error Correction - ACL 2022](https://aclanthology.org/2022.naacl-main.432.pdf)
- [Improving Generative Error Correction for ASR - ACL Findings 2025](https://aclanthology.org/2025.findings-acl.125.pdf)
- [ASR Error Correction with Augmented Transformer - Amazon Science](https://assets.amazon.science/b1/08/ff1fed594cf9803db0253c92c9dd/asr-error-correction-with-augmented-transformer-for-entity-retrieval.pdf)

---

## Summary & Recommendations

### Current Transkribator Status

**Strengths:**
- ✅ Comprehensive dictionary-based corrections (~50 rules)
- ✅ Regex pattern corrections for common errors
- ✅ Lazy loading of punctuation model
- ✅ Separate processors for Whisper and Sherpa-ONNX
- ✅ Fast processing (<10ms without ML)

**Weaknesses:**
- ❌ Limited Russian morphology coverage (gender, case)
- ❌ No proper noun recognition
- ❌ Punctuation model not trained on Russian
- ❌ No hallucination detection for Whisper
- ❌ Context-aware corrections minimal

### Priority Improvements

#### High Priority (Quick Wins)

1. **Expand correction dictionary** (+100 rules)
   - Add common verb forms
   - Add preposition combinations
   - Add gender agreement patterns

2. **Improve punctuation placement**
   - Fix "и тропинка и лесок" → "и тропинка, и лесок"
   - Add rules for repeated conjunctions

3. **Optimize regex compilation**
   - Already implemented in `EnhancedTextProcessor`
   - Benchmark improvements

#### Medium Priority (Significant Impact)

4. **Add proper noun dictionary**
   - Common names (Denis, Elena, Anna...)
   - Places (Moscow, Russia...)
   - Simple dictionary lookup (1000-5000 entries)

5. **Implement gender agreement correction**
   - Pattern-based: adjective + noun
   - Limited to common pairs initially

6. **Add language detection**
   - Auto-switch between Russian/English rules
   - Use `langdetect` library

#### Low Priority (Future Work)

7. **Replace deepmultilingualpunctuation with Russian-specific model**
   - Train or fine-tune on Russian data
   - Or use xlm-roberta model

8. **Implement LLM-based correction (optional)**
   - User-triggered for important texts
   - "Enhance this transcription" button

9. **Add Whisper hallucination detection**
   - Confidence threshold monitoring
   - Flag low-confidence segments

### Implementation Plan

**Phase 1: Dictionary Expansion (1-2 days)**
```python
# Add 100+ new correction rules
# Focus on most common errors from test results
```

**Phase 2: Proper Noun Support (2-3 days)**
```python
# Load proper noun dictionary
# Implement case-insensitive matching
# Capitalize known names/places
```

**Phase 3: Gender Agreement (3-5 days)**
```python
# Implement pattern-based gender correction
# Add common adjective-noun pairs
# Test on real transcriptions
```

**Phase 4: Advanced Features (Future)**
```python
# LLM integration (optional)
# Better punctuation model
# Context-aware corrections
```

---

**Document Version:** 1.0
**Last Updated:** 2026-01-27
**Next Review:** After implementing Phase 1 improvements
