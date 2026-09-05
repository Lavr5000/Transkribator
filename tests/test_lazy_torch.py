"""Importing the app must not drag torch/transformers into the tray process.

Regression for the 1.45 GB idle floor (2026-09-05): the top-level
`from deepmultilingualpunctuation import PunctuationModel` in
text_processor_enhanced loaded torch_cpu.dll at startup although the default
-punct model never uses the punctuation model.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_import_chain_does_not_load_torch():
    code = (
        "import sys; sys.path.insert(0, %r);"
        "import src.text_processor_enhanced, src.transcriber;"
        "print('torch' in sys.modules, 'transformers' in sys.modules)"
    ) % str(ROOT)
    out = subprocess.run([sys.executable, "-c", code], capture_output=True,
                         text=True, timeout=120)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "False False", out.stdout
