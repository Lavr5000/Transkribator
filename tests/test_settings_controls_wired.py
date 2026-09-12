"""Regression test: every `_init_*_controls` in MainWindow is actually called.

`_init_vad_controls` and `_init_noise_controls` were defined, correct, and
never invoked from `_show_settings`. The VAD sensitivity and noise sliders
therefore opened at their Qt defaults, ignored the stored config, and dropped
every change the user made — the settings looked live but persisted nothing.
"""

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src" / "main_window.py"


def test_every_init_controls_method_is_called():
    tree = ast.parse(SRC.read_text(encoding="utf-8"))

    defined = {
        n.name
        for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef)
        and n.name.startswith("_init_")
        and n.name.endswith("_controls")
    }
    assert defined, "no _init_*_controls methods found — test is looking at the wrong file"

    called = {
        n.func.attr
        for n in ast.walk(tree)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
    }

    assert defined <= called, f"defined but never called: {sorted(defined - called)}"
