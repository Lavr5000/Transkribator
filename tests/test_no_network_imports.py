"""Negative network gate (A3): the product path cannot phone home.

Grepping for "groq" proves nothing — a rename or a fresh dependency would
walk straight past it. This walks the AST of every module under src/ and
fails on an import of anything that can open a socket or reach a cloud ASR.

The app has made zero network calls since 2026-08-24 (Groq retired after 24
timeouts); this test is what keeps that true.
"""

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "src"

# No allow-list. If a module ever legitimately needs one of these, the test
# must be changed deliberately, in the same commit, with a reason.
FORBIDDEN_ROOTS = {
    "socket",
    "requests",
    "httpx",
    "urllib",          # covers urllib.request
    "http",            # http.client
    "telethon",
    "groq",
    "faster_whisper",
    "whisper",
    "openai",
    "aiohttp",
}


def _module_files():
    return sorted(p for p in SRC.rglob("*.py") if "__pycache__" not in p.parts)


def _imported_roots(tree):
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level:      # relative import inside the package
                continue
            if node.module:
                roots.add(node.module.split(".")[0])
    return roots


def test_src_modules_import_nothing_that_can_reach_the_network():
    files = _module_files()
    assert files, "no source modules found — the walk is broken, not the code"

    offenders = []
    for path in files:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for root in sorted(_imported_roots(tree) & FORBIDDEN_ROOTS):
            offenders.append(f"{path.relative_to(SRC.parent)} imports {root}")

    assert not offenders, "network-capable imports in the product path:\n" + "\n".join(offenders)


def test_the_walk_actually_catches_a_planted_import(tmp_path):
    """Negative control: the same check must fail on a module that does import."""
    planted = tmp_path / "bad.py"
    planted.write_text("import requests\nfrom urllib.request import urlopen\n", encoding="utf-8")
    tree = ast.parse(planted.read_text(encoding="utf-8"))
    assert _imported_roots(tree) & FORBIDDEN_ROOTS == {"requests", "urllib"}
