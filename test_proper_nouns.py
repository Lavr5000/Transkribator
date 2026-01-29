"""Test proper noun capitalization functionality."""

from src.proper_nouns import ProperNounDict

# Test 1: Load dictionary
print("=== Test 1: Load dictionary ===")
pn = ProperNounDict()
stats = pn.get_stats()
print(f"Stats: {stats}")
print(f"Total entries: {stats['total']}")

# Test 2: Check proper nouns
print("\n=== Test 2: Check proper nouns ===")
test_words = [
    ("москва", True),
    ("деннис", True),
    ("россия", True),
    ("стол", False),
    ("дом", False),
]

for word, expected in test_words:
    result = pn.is_proper_noun(word)
    status = "OK" if result == expected else "FAIL"
    print(f"{status} '{word}': {result} (expected {expected})")

# Test 3: Capitalize known proper nouns
print("\n=== Test 3: Capitalize known proper nouns ===")
test_texts = [
    "я живу в москве",
    "меня зовут денис",
    "я из россии",
    "поехали в санкт-петербург",
    "привет меня зовут александр",
    "я родился в киеве",
    "это город на карте",
]

for text in test_texts:
    result = pn.capitalize_known(text)
    print(f"'{text}' -> '{result}'")

# Test 4: Integration with EnhancedTextProcessor
print("\n=== Test 4: Integration with EnhancedTextProcessor ===")
from src.text_processor_enhanced import EnhancedTextProcessor

processor = EnhancedTextProcessor(
    language="ru",
    enable_corrections=True,
    enable_punctuation=False,  # Disable for faster testing
    enable_phonetics=False,
    enable_morphology=False,
    enable_proper_nouns=True
)

test_text = "я живу в москве и меня зовут денис"
result = processor.process(test_text)
print(f"'{test_text}' -> '{result}'")

print("\n=== All tests complete ===")
