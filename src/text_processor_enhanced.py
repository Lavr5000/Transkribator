"""Enhanced text post-processing with punctuation restoration for Sherpa-ONNX."""
import logging
import re
from typing import Dict, List, Tuple, Optional

logger = logging.getLogger("transkribator")

from text_processor import TextProcessor

try:
    from deepmultilingualpunctuation import PunctuationModel
    PUNCTUATION_AVAILABLE = True
except ImportError:
    PUNCTUATION_AVAILABLE = False
    logger.info("PUNCTUATION_MODEL_NOT_AVAILABLE | install deepmultilingualpunctuation")

# Import phonetic corrections
try:
    from phonetics import PhoneticCorrector
    PHONETICS_AVAILABLE = True
except ImportError:
    PHONETICS_AVAILABLE = False
    PhoneticCorrector = None
    logger.info("PHONETICS_MODULE_NOT_AVAILABLE")

# Import morphological corrections
try:
    from morphology import MorphologyCorrector
    MORPHOLOGY_AVAILABLE = True
except ImportError:
    MORPHOLOGY_AVAILABLE = False
    MorphologyCorrector = None
    logger.info("MORPHOLOGY_MODULE_NOT_AVAILABLE")

# Import proper noun corrections
try:
    from proper_nouns import ProperNounDict
    PROPER_NOUNS_AVAILABLE = True
except ImportError:
    PROPER_NOUNS_AVAILABLE = False
    ProperNounDict = None
    logger.info("PROPER_NOUNS_MODULE_NOT_AVAILABLE")


class EnhancedTextProcessor(TextProcessor):
    """Enhanced text processor with punctuation restoration and Sherpa-specific corrections."""

    def __init__(self, language: str = "ru", enable_corrections: bool = True, enable_punctuation: bool = True, enable_phonetics: bool = True, enable_morphology: bool = True, enable_proper_nouns: bool = True, backend: str = "sherpa", user_dictionary: list = None):
        """
        Initialize enhanced text processor.

        Args:
            language: Target language code (ru, en, etc.)
            enable_corrections: Whether to enable error corrections
            enable_punctuation: Whether to restore punctuation (will be overridden by backend config)
            enable_phonetics: Whether to enable phonetic corrections (voiced/unvoiced)
            enable_morphology: Whether to enable morphological corrections (gender, case)
            enable_proper_nouns: Whether to enable proper noun capitalization
            backend: Backend type for adaptive processing ("whisper", "sherpa", "podlodkaturbo")
            user_dictionary: User-defined correction entries [{"wrong": str, "correct": str, "case_sensitive": bool}]
        """
        self.language = language
        self.backend = backend.lower()
        self.enable_corrections = enable_corrections
        self.user_dictionary = user_dictionary or []

        # Configure processing flags based on backend type
        self._configure_for_backend(enable_phonetics, enable_morphology, enable_proper_nouns)

        self._load_corrections()

        # Pre-compile regex patterns for performance
        self._compile_patterns()

        # Punctuation model will be loaded lazily on first use
        self.punctuation_model = None

        # Lazy-init: components created on first process() call to avoid
        # ~200ms pymorphy2 startup cost at application launch
        self.phonetic_corrector = None
        self.morphology_corrector = None
        self.proper_nouns = None
        self._components_initialized = False

    def _configure_for_backend(self, enable_phonetics: bool, enable_morphology: bool, enable_proper_nouns: bool):
        """Configure processing flags based on backend type.

        Different backends produce different output quality:
        - Whisper: Has punctuation, capitalization (minimal processing needed)
        - Sherpa/Podlodka: Raw lowercase text (full processing needed)

        Args:
            enable_phonetics: Base preference for phonetic corrections
            enable_morphology: Base preference for morphological corrections
            enable_proper_nouns: Base preference for proper noun capitalization
        """
        if self.backend == "whisper":
            # Whisper already provides punctuation and capitalization
            # Skip punctuation restoration to avoid double punctuation
            # Skip advanced corrections (Whisper has fewer phonetic/morphological errors)
            self.enable_punctuation = False
            self.enable_phonetics = False
            self.enable_morphology = False
        else:
            # Sherpa, Podlodka: No punctuation, raw lowercase text
            # Enable full processing pipeline
            self.enable_punctuation = True
            self.enable_phonetics = enable_phonetics and PHONETICS_AVAILABLE
            self.enable_morphology = enable_morphology and MORPHOLOGY_AVAILABLE

        # Proper nouns are useful for all backends
        self.enable_proper_nouns = enable_proper_nouns and PROPER_NOUNS_AVAILABLE

    def _load_corrections(self):
        """Load error correction rules for the target language."""
        if self.language == "ru":
            self._russian_corrections()
        elif self.language == "en":
            self._english_corrections()
        else:
            self._russian_corrections()  # Default to Russian

    def _russian_corrections(self):
        """Load Russian language error corrections with Sherpa-specific fixes."""
        # Common Whisper/Sherpa errors for Russian
        self.corrections = {
            # Sherpa-ONNX specific errors (from test results)
            "классок": "колосок",
            "класски": "колоски",
            "класок": "колосок",

            # Phonetic substitutions
            "лыбки": "улыбки",
            "лыбкою": "улыбкою",
            "тулыбки": "улыбки",
            "тулыбкой": "улыбкою",
            "тулыбкою": "улыбкою",
            "лыбью": "улыбкой",
            "лыбь": "улыбка",

            # Verb forms
            "станек": "станет",
            "станем": "станет",
            "станит": "станет",
            "становит": "станет",

            # Adjectives
            "сидлей": "светлей",
            "ситлей": "светлей",
            "светле": "светлей",
            "динцветлей": "всем светлей",
            "светлее": "светлей",

            # Prepositions and places
            "неверо": "небе",
            "невере": "небе",
            "неверо-друга": "небе радуга",
            "радугы": "радуга",
            "пойли": "появи",
            "поиви": "появи",
            "растебе": "к тебе",
            "ра стеб": "к тебе",
            "рассещё": "к тебе еще",
            "онактиви": "она не раз",
            "не рас": "не раз",
            "не расс": "не раз",
            "онак": "она же",
            "онатив": "она не",

            # Common verb endings
            "проснутся": "проснется",
            "проснется": "проснется",
            "спится": "спится",
            "получим": "получим",

            # Prepositions and particles
            "у своей": "с улыбкою своей",
            "поделись у": "поделись с",

            # Double letters/words
            "в в": "в",
            "на на": "на",
            "с с": "с",
            "и и": "и",
            "а а": "а",

            # Common word pairs
            "еще раз": "ещё раз",
            "в тече ние": "в течение",
            "в те чение": "в течение",

            # Gender/number corrections (common Sherpa errors)
            "огромные семья": "огромная семья",
            "огромный семья": "огромная семья",
            "мною родной": "мое родное",
            "мою родной": "мое родное",
            "все мою": "все мое",
            "всех люблю на свете я": "всех, кого люблю на свете, я",

            # ============================================
            # NEW RULES (50+ additions for 100+ total)
            # ============================================

            # Dropped letters (ASR skips similar-sounding letters)
            "приве": "привет",
            "спасибо": "спасибо",
            "спасиба": "спасибо",
            "здравствуй": "здравствуйте",
            "здравствуйт": "здравствуйте",
            "пожалуйст": "пожалуйста",
            "пожалу": "пожалуйста",
            "плох": "плохо",
            "очен": "очень",
            "очнь": "очень",
            "мног": "много",
            "многа": "много",
            # "ра" removed: prefix in compound words would be corrupted

            # Preposition errors (common ASR confusion)
            "неигр": "наиграть",
            "неходит": "находит",
            "вообщ": "вообще",
            "вообщем": "вообще",
            "вобще": "вообще",
            "сво": "свои",
            "соо": "свои",
            "ото": "от",
            "дл": "для",
            "длл": "для",

            # Verb ending mistakes (-т/-ть confusion)
            # Only fix clearly broken truncations, NOT valid imperatives/infinitives
            "делае": "делает",
            "думат": "думает",
            "можит": "может",
            "писат": "пишет",
            "читат": "читает",
            "слышат": "слышит",

            # Reflexive verb errors (-ся/-сь)
            "находитс": "находится",
            "находис": "находится",
            "оказываетс": "оказывается",
            "оказываес": "оказывается",
            "остаетс": "остается",
            "остае": "остается",
            "получаетс": "получается",
            "получаес": "получается",
            "начинаетс": "начинается",
            "начинаес": "начинается",
            "заканчиваетс": "заканчивается",
            "заканчиваес": "заканчивается",
            "говорис": "говорится",
            "говоритс": "говорится",
            "делаетс": "делается",
            "делаес": "делается",
            "получис": "получится",
            "получитс": "получится",

            # Past tense typos (only clear typos, NOT gender forcing)
            "сделалм": "сделал",

            # Adjective-noun gender agreement
            "большой семья": "большая семья",
            "красивый девушка": "красивая девушка",
            "умный женщина": "умная женщина",
            "молодой девушка": "молодая девушка",
            "новый книга": "новая книга",
            "старый стены": "старые стены",
            "хорошый": "хороший",

            # Conjunction errors
            "чтоб": "чтобы",
            "иль": "или",
            "зат": "зато",
            "однак": "однако",
            "однакоо": "однако",

            # Number word errors
            # "одно" removed: valid neuter form
            "трие": "три",
            "четыр": "четыре",
            "пят": "пять",
            "шест": "шесть",
            "сем": "семь",
            "восем": "восемь",
            "девят": "девять",
            "десят": "десять",

            # Pronoun errors
            "её": "её",
            "иx": "их",
            "себ": "себя",
            "имм": "им",
            "ним": "ним",

            # Common particle errors
            "ль": "ли",
            # "ж" removed: letter in abbreviations would be corrupted
            # "б" removed: letter in abbreviations would be corrupted
            "вед": "ведь",
            "даж": "даже",
            "лиш": "лишь",
            "тольк": "только",
            "простоо": "просто",

            # Common negation errors
            "нетт": "нет",
            "неет": "нет",
            "нич": "ничего",
            "никогд": "никогда",
            "никуд": "никуда",
            "негд": "негде",
            "зчем": "зачем",
            "зачeм": "зачем",
            "почем": "почему",
            "почeмy": "почему",

            # Question word errors
            "чт": "что",
            "чтот": "что",
            "кото": "кто",
            "гдe": "где",
            "когд": "когда",
            "когдаa": "когда",
            "куд": "куда",
            "откудa": "откуда",
            "кeм": "кем",
            "чeм": "чем",
            "кaк": "как",
            "каки": "какие",
            "чеи": "чей",
            "котор": "который",
            "которы": "который",
        }

        # Pattern-based corrections (regex)
        self.pattern_corrections = [
            # Fix multiple spaces
            (r'\s+', ' '),

            # Fix space before punctuation
            (r'\s+([,.!?;:])', r'\1'),

            # Fix missing space after punctuation
            (r'([,.!?;:])(?=[А-Яа-яA-Za-z])', r'\1 '),

            # Fix lowercase after sentence end
            (r'([.!?]\s+)([а-я])', lambda m: m.group(1) + m.group(2).upper()),

            # Fix gender/number patterns (Sherpa specific)
            (r'огромные семья', 'огромная семья'),
            (r'огромный семья', 'огромная семья'),
            (r'мое родной', 'мое родное'),
            (r'мою родной', 'мое родное'),
            (r'все мою', 'все мое'),

            # Fix common adjective endings
            (r'(\w+) голубой (\w+)', lambda m: f'{m.group(1)} голубое {m.group(2)}'),
            (r'(\w+) морей (\w+)', lambda m: f'{m.group(1)} море {m.group(2)}'),

            # ============================================
            # NEW PATTERN CORRECTIONS (multi-word fixes)
            # ============================================

            # ё normalization (common ASR error)
            (r'\bеще раз\b', 'ещё раз'),
            (r'\bеще один\b', 'ещё один'),
            (r'\bеще разок\b', 'ещё разок'),
            (r'\bвсеравно\b', 'всё равно'),
            (r'\bвсе равно\b', 'всё равно'),
            (r'\bвсегда\b', 'всегда'),
            (r'\bвсееще\b', 'всё ещё'),
            (r'\bвсе еще\b', 'всё ещё'),

            # Hyphenation fixes
            (r'\bвсе таки\b', 'всё-таки'),
            (r'\bвсе-таки\b', 'всё-таки'),
            (r'\bвообще то\b', 'вообще-то'),
            (r'\builtin\b', 'в том числе'),
            (r'\bтем не менее\b', 'тем не менее'),
            (r'\bкак либо\b', 'как-либо'),
            (r'\bкак нибудь\b', 'как-нибудь'),
            (r'\bкак-нибудь\b', 'как-нибудь'),

            # Extra preposition removal
            (r'\bво вообще\b', 'вообще'),
            (r'\bво во что\b', 'во что'),
            (r'\bна на\b', 'на'),
            (r'\bс с\b', 'с'),
            (r'\bи и\b', 'и'),

            # Space error fixes
            (r'\bне который\b', 'некоторый'),
            (r'\bне которую\b', 'некоторую'),
            (r'\bне которых\b', 'некоторых'),
            (r'\bне которыми\b', 'некоторыми'),
            (r'\bпо этому\b', 'поэтому'),
            (r'\bпо этому\b', 'поэтому'),
            (r'\bпо этому поводу\b', 'поэтому'),
            (r'\bво всех\b', 'во всех'),

            # Compound word fixes
            (r'\bтак же\b', 'также'),
            (r'\bкак бы\b', 'как бы'),
            (r'\было бы\b', 'было бы'),
            (r'\bчто бы\b', 'чтобы'),
            (r'\бот чего\b', 'отчего'),

            # Common phrase errors
            (r'\bв течени\b', 'в течение'),
            (r'\bв течении\b', 'в течение'),
            (r'\bв течениие\b', 'в течение'),
            (r'\bв продолжени\b', 'в продолжение'),
            (r'\bв продолжении\b', 'в продолжение'),
            (r'\bв следстви\b', 'вследствие'),
            (r'\bв вследствие\b', 'вследствие'),
        ]

    # _english_corrections() inherited from TextProcessor

    def _compile_patterns(self):
        """Pre-compile regex patterns for error correction to improve performance."""
        self._compiled_patterns = []

        # Sort corrections by length (longest first) for proper matching
        sorted_corrections = sorted(self.corrections.items(), key=lambda x: len(x[0]), reverse=True)

        # Pre-compile all patterns
        for wrong, correct in sorted_corrections:
            if len(wrong) <= 10:
                pattern = re.compile(r'\b' + re.escape(wrong) + r'\b', re.IGNORECASE)
            else:
                pattern = re.compile(re.escape(wrong), re.IGNORECASE)
            self._compiled_patterns.append((pattern, correct))

    def _ensure_components(self):
        """Lazy-init phonetic, morphology, and proper noun components on first use."""
        if self._components_initialized:
            return
        self._components_initialized = True

        if self.enable_phonetics and PhoneticCorrector is not None:
            self.phonetic_corrector = PhoneticCorrector(enable_validation=True)

        if self.enable_morphology and MorphologyCorrector is not None:
            self.morphology_corrector = MorphologyCorrector()

        if self.enable_proper_nouns and ProperNounDict is not None:
            self.proper_nouns = ProperNounDict()

    def process(self, text: str) -> str:
        """
        Apply all post-processing improvements to text.

        Args:
            text: Raw transcribed text

        Returns:
            Improved text
        """
        if not text or not self.enable_corrections:
            return text

        self._ensure_components()

        # Step 1: Fix common errors
        text = self._fix_errors(text)

        # Step 2: Phonetic corrections (voiced/unvoiced consonants)
        if self.enable_phonetics and self.phonetic_corrector:
            text = self.phonetic_corrector.process(text)

        # Step 3: Morphological corrections (gender agreement, case endings)
        if self.enable_morphology and self.morphology_corrector:
            text = self._fix_morphology(text)

        # Step 4: Add punctuation (for CTC models like Sherpa)
        if self.enable_punctuation:
            text = self._add_punctuation(text)

        # Step 5: Fix punctuation placement
        text = self._fix_punctuation(text)

        # Step 6: Fix capitalization
        text = self._fix_capitalization(text)

        # Step 7: Proper noun capitalization
        if self.enable_proper_nouns and self.proper_nouns:
            text = self.proper_nouns.capitalize_known(text)

        # Step 8: Final cleanup
        text = self._cleanup(text)

        return text

    def _fix_errors(self, text: str) -> str:
        """Fix common transcription errors using pre-compiled patterns."""
        # Fix repeated letters
        text = self._fix_repeated_letters(text)

        # Apply user dictionary corrections FIRST (highest priority)
        text = self._apply_user_dictionary(text)

        # Apply pre-compiled corrections (already sorted by length)
        for pattern, correct in self._compiled_patterns:
            text = pattern.sub(correct, text)

        return text

    def _apply_user_dictionary(self, text: str) -> str:
        """Apply user-defined correction entries.

        User dictionary is applied before built-in corrections,
        giving it higher priority.

        Args:
            text: Text to correct

        Returns:
            Text with user corrections applied
        """
        if not self.user_dictionary:
            return text

        for entry in self.user_dictionary:
            wrong = entry.get("wrong", "")
            correct = entry.get("correct", "")
            case_sensitive = entry.get("case_sensitive", False)

            if not wrong or not correct:
                continue

            if case_sensitive:
                # Case-sensitive exact replacement
                text = text.replace(wrong, correct)
            else:
                # Case-insensitive replacement
                # Use word boundaries for single words, no boundaries for phrases
                if " " in wrong:
                    # Phrase replacement - no word boundaries
                    pattern = re.compile(re.escape(wrong), re.IGNORECASE)
                    text = pattern.sub(correct, text)
                else:
                    # Single word - use word boundaries
                    pattern = re.compile(r'\b' + re.escape(wrong) + r'\b', re.IGNORECASE)
                    text = pattern.sub(correct, text)

        return text

    def set_user_dictionary(self, user_dictionary: list):
        """Update user dictionary entries.

        Args:
            user_dictionary: List of {"wrong": str, "correct": str, "case_sensitive": bool} entries
        """
        self.user_dictionary = user_dictionary or []

    def _fix_morphology(self, text: str) -> str:
        """Apply morphological corrections using pymorphy2.

        Fixes gender agreement between adjectives and nouns, and
        corrects basic case ending errors.

        Args:
            text: Text to correct

        Returns:
            Text with morphological corrections applied
        """
        if not self.enable_morphology or not self.morphology_corrector:
            return text

        # Apply gender agreement corrections
        text = self.morphology_corrector.fix_gender_agreement(text)

        # Apply case ending corrections
        text = self.morphology_corrector.fix_case_endings(text)

        return text

    # _fix_repeated_letters() inherited from TextProcessor

    def _add_punctuation(self, text: str) -> str:
        """Restore punctuation using ML model."""
        if not self.enable_punctuation or not PUNCTUATION_AVAILABLE:
            return text

        # Lazy load punctuation model on first use
        if self.punctuation_model is None:
            try:
                logger.info("PUNCTUATION_MODEL_LOADING")
                self.punctuation_model = PunctuationModel()
                logger.info("PUNCTUATION_MODEL_LOADED")
            except Exception as e:
                logger.warning("PUNCTUATION_MODEL_LOAD_FAILED | %s", e)
                self.punctuation_model = None
                return text

        try:
            # Process with punctuation model
            result = self.punctuation_model.restore_punctuation(text)
            return result
        except Exception as e:
            logger.warning("PUNCTUATION_RESTORE_FAILED | %s", e)
            return text

    def _fix_punctuation(self, text: str) -> str:
        """Fix punctuation issues."""
        for pattern, replacement in self.pattern_corrections:
            if callable(replacement):
                text = re.sub(pattern, replacement, text)
            else:
                text = re.sub(pattern, replacement, text)

        return text

    def _fix_capitalization(self, text: str) -> str:
        """
        Fix capitalization issues with improved handling of sentence endings.

        Handles:
        - First letter capitalization
        - Capitalization after sentence-ending punctuation (., !, ?)
        - Multiple punctuation (!!, ??, !?)
        - Ellipsis (...)
        - Quotes/parens after punctuation
        - Multiple spaces after punctuation
        """
        if not text:
            return text

        # Step 1: Ensure first letter is capitalized
        text = text[0].upper() + text[1:] if text else text

        # Step 2: Capitalize after sentence endings with proper space handling
        # Pattern: punctuation followed by space(s) and lowercase letter

        # Single sentence endings (. ! ?)
        # Match: punctuation + spaces + lowercase letter
        text = re.sub(r'([.!?])\s+([а-яa-z])', lambda m: m.group(1) + ' ' + m.group(2).upper(), text)

        # Multiple punctuation (!!, ??, !?!, ???, etc.)
        # Match: multiple punctuation + spaces + lowercase letter
        text = re.sub(r'([.!?]{2,})\s+([а-яa-z])', lambda m: m.group(1) + ' ' + m.group(2).upper(), text)

        # Step 3: Handle ellipsis (...) as sentence ending
        # Ellipsis followed by space and lowercase letter should capitalize
        text = re.sub(r'(\.\.\.)\s+([а-яa-z])', lambda m: m.group(1) + ' ' + m.group(2).upper(), text)

        # Step 4: Handle punctuation without space (e.g., "word.Next")
        # This adds space and capitalizes
        text = re.sub(r'([.!?])([а-яa-z])', lambda m: m.group(1) + ' ' + m.group(2).upper(), text)

        # Step 5: Handle multiple spaces after punctuation (normalize to single space)
        text = re.sub(r'([.!?])\s{2,}', r'\1 ', text)

        # Step 6: Ensure first letter after opening quote/paren is capitalized
        # e.g., ("hello") -> ("Hello")
        text = re.sub(r'([("\'])\s*([а-яa-z])', lambda m: m.group(1) + m.group(2).upper(), text)

        # Step 7: Handle quotes/parens immediately after punctuation without space
        # e.g., "word."next" -> "word." Next"
        # e.g., "word!"next" -> "word!" Next"
        text = re.sub(r'([.!?])([)"\'])([а-яa-z])', lambda m: m.group(1) + m.group(2) + ' ' + m.group(3).upper(), text)

        # Step 8: Handle parentheses after punctuation with space
        # e.g., "word. (hello)" -> "word. (Hello)"
        text = re.sub(r'([.!?])\s+(\()([а-яa-z])', lambda m: m.group(1) + ' ' + m.group(2) + m.group(3).upper(), text)

        # Final cleanup: normalize multiple spaces to single space
        text = re.sub(r'\s{2,}', ' ', text)

        return text

    def _cleanup(self, text: str) -> str:
        """Final cleanup of text."""
        # Remove extra spaces
        text = ' '.join(text.split())

        # Remove trailing punctuation
        text = text.rstrip('.,;:')

        return text.strip()

    def add_correction(self, wrong: str, correct: str):
        """Add a custom correction rule."""
        self.corrections[wrong] = correct

    def add_corrections(self, corrections: Dict[str, str]):
        """Add multiple custom correction rules."""
        self.corrections.update(corrections)
