"""Build a release ZIP from a clean git worktree.

Why a worktree and not the working directory: the repo root of a machine in
daily use carries debug.log, an owner's config, downloaded models and one-off
scripts. A build that reads the working tree can ship any of them. A worktree
checkout of the release commit contains, by construction, only what is
committed — the bundled models are copied in explicitly from an allow-list.

Steps
  1. git worktree add <tmp> <commit>            clean source
  2. copy allow-listed model directories in     (they are gitignored)
  3. python -m venv .venv-build + pip install   pinned interpreter, asserted
  4. pyinstaller transkribator.spec
  5. scan dist/ for logs, configs, audio, keys, user paths  -> hard fail
  6. zip + SHA256SUMS.txt, print sizes

Usage
    python scripts/build_release.py                 # HEAD
    python scripts/build_release.py --commit v2.4.0
    python scripts/build_release.py --dry-run       # build + scan, no ZIP
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# The interpreter that produced the working dist/ (measured 2026-09-02 from
# dist/transkribator/_internal/python313.dll -> 3.13.9, and the project
# interpreter's own sys.version). Not a guess: build with this or stop.
REQUIRED_PY = (3, 13)
REQUIRED_BITS = 64

# Model directories are gitignored (215 MB each), so the worktree has none.
# Everything that ships is named here — nothing else is copied in.
MODEL_ALLOW_LIST = [
    Path("models/sherpa/giga-am-v3-ru-punct"),
    Path("models/sherpa/silero-vad"),
]

# Anything matching these must never reach a user's machine.
FORBIDDEN_SUFFIXES = {".log", ".jsonl", ".wav", ".mp3", ".ogg", ".oga", ".m4a",
                      ".flac", ".session", ".env", ".bundle"}
FORBIDDEN_NAMES = {"config.json", "history.json", "events.jsonl", ".env",
                   "debug.log", "faulthandler.log"}
# Key prefixes and the owner's home path. Checked inside text-ish files only.
FORBIDDEN_STRINGS = [r"C:[\\/]+Users[\\/]+user", "sk-", "gsk_", "hf_", "AIza"]
SCANNED_TEXT_SUFFIXES = {".py", ".txt", ".json", ".cfg", ".ini", ".toml", ".md",
                         ".bat", ".ps1", ".yaml", ".yml", ""}


def run(cmd, cwd=None, env=None):
    print(f"  $ {' '.join(str(c) for c in cmd)}")
    subprocess.run(cmd, cwd=cwd, env=env, check=True)


def human(n: int) -> str:
    return f"{n / (1024 * 1024):.1f} MB"


def dir_size(path: Path) -> int:
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def project_version() -> str:
    text = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    m = re.search(r'^version\s*=\s*"([^"]+)"', text, re.M)
    if not m:
        raise SystemExit("cannot read version from pyproject.toml")
    return m.group(1)


def assert_interpreter():
    if sys.version_info[:2] != REQUIRED_PY or struct.calcsize("P") * 8 != REQUIRED_BITS:
        raise SystemExit(
            f"build interpreter must be CPython {REQUIRED_PY[0]}.{REQUIRED_PY[1]} "
            f"x{REQUIRED_BITS} (the one that produced the working dist/), "
            f"got {sys.version.split()[0]} x{struct.calcsize('P') * 8}")


def make_worktree(commit: str, target: Path):
    print(f"[1/6] clean worktree of {commit} -> {target}")
    run(["git", "worktree", "add", "--detach", str(target), commit], cwd=REPO)


def copy_models(target: Path):
    print("[2/6] copying allow-listed models")
    for rel in MODEL_ALLOW_LIST:
        src = REPO / rel
        if not src.is_dir():
            raise SystemExit(f"missing bundled model: {src}")
        dst = target / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src, dst, dirs_exist_ok=True)
        print(f"  {rel} ({human(dir_size(src))})")


def make_venv(target: Path) -> Path:
    print("[3/6] fresh build venv")
    venv = target / ".venv-build"
    run([sys.executable, "-m", "venv", str(venv)])
    py = venv / "Scripts" / "python.exe"
    if not py.exists():                       # non-Windows fallback
        py = venv / "bin" / "python"
    run([str(py), "-m", "pip", "install", "--upgrade", "pip", "--quiet"])
    run([str(py), "-m", "pip", "install", ".[nlp]", "pyinstaller", "--quiet"], cwd=target)

    # The build MUST run inside this venv, not the machine's global Python
    # with its hundreds of unrelated packages (that is how lxml, cryptography,
    # tiktoken and pypinyin ended up in the 2.2.0 release).
    check = subprocess.run(
        [str(py), "-c",
         "import sys, struct; print(sys.prefix); print(sys.version.split()[0]); "
         "print(struct.calcsize('P') * 8)"],
        capture_output=True, text=True, check=True)
    prefix, version, bits = [line.strip() for line in check.stdout.strip().splitlines()]
    if Path(prefix).resolve() != venv.resolve():
        raise SystemExit(f"venv assert failed: sys.prefix={prefix} != {venv}")
    if tuple(int(x) for x in version.split(".")[:2]) != REQUIRED_PY or int(bits) != REQUIRED_BITS:
        raise SystemExit(f"venv assert failed: python {version} x{bits}")
    print(f"  venv ok: {prefix} | python {version} x{bits}")
    return py


def write_build_info(py: Path, target: Path, dist: Path, commit: str):
    freeze = subprocess.run([str(py), "-m", "pip", "freeze"],
                            capture_output=True, text=True, check=True).stdout
    # This file ships to users, so no absolute paths: the tree scan (rightly)
    # fails the build on the builder's home directory, and `pip freeze` names
    # the local checkout as `whisper-typing @ file:///C:/Users/...`.
    freeze = "\n".join(line.split(" @ ")[0] if " @ file://" in line else line
                       for line in freeze.splitlines())
    info = (dist / "BUILD-INFO.txt")
    info.write_text(
        f"commit: {commit}\n"
        f"built: {time.strftime('%Y-%m-%d %H:%M:%S %z')}\n"
        f"interpreter: clean .venv-build (path and version asserted), python "
        f"{sys.version.split()[0]} x{struct.calcsize('P') * 8}\n\n"
        f"pip freeze:\n{freeze}\n",
        encoding="utf-8")
    return info


def scan_tree(root: Path):
    """Fail the build on anything private that slipped into dist/."""
    print("[5/6] scanning the built tree")
    problems = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if path.name in FORBIDDEN_NAMES:
            problems.append(f"{rel}: forbidden file name")
            continue
        if path.suffix.lower() in FORBIDDEN_SUFFIXES:
            problems.append(f"{rel}: forbidden extension {path.suffix}")
            continue
        if path.suffix.lower() in SCANNED_TEXT_SUFFIXES and path.stat().st_size < 2_000_000:
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for needle in FORBIDDEN_STRINGS:
                if re.search(needle, text):
                    problems.append(f"{rel}: contains {needle!r}")
                    break
    if problems:
        raise SystemExit("build tree scan FAILED:\n  " + "\n  ".join(problems))
    print(f"  clean: {sum(1 for _ in root.rglob('*') if _.is_file())} files, {human(dir_size(root))}")


def make_zip(app_dir: Path, out_dir: Path, version: str) -> Path:
    print("[6/6] zipping")
    zip_path = out_dir / f"Transkribator-v{version}-win64.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for f in sorted(app_dir.rglob("*")):
            if f.is_file():
                z.write(f, Path("Transkribator") / f.relative_to(app_dir))
    digest = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    sums = out_dir / "SHA256SUMS.txt"
    sums.write_text(f"{digest}  {zip_path.name}\n", encoding="utf-8")
    return zip_path


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--commit", default="HEAD", help="commit/tag to build (default: HEAD)")
    ap.add_argument("--dry-run", action="store_true", help="build and scan, skip the ZIP")
    ap.add_argument("--keep", action="store_true", help="keep the worktree for inspection")
    args = ap.parse_args()

    assert_interpreter()
    version = project_version()
    commit = subprocess.run(["git", "rev-parse", args.commit], cwd=REPO,
                            capture_output=True, text=True, check=True).stdout.strip()
    print(f"Transkribator {version} from {commit[:12]} ({args.commit})")

    target = Path(tempfile.mkdtemp(prefix="tk-build-")) / "src"
    try:
        make_worktree(commit, target)
        copy_models(target)
        py = make_venv(target)

        print("[4/6] pyinstaller")
        env = dict(os.environ, PYTHONHASHSEED="0")
        run([str(py), "-m", "PyInstaller", "--clean", "--noconfirm",
             "--log-level", "WARN", "transkribator.spec"], cwd=target, env=env)

        app_dir = target / "dist" / "transkribator"
        if not app_dir.is_dir():
            raise SystemExit(f"pyinstaller produced no {app_dir}")
        write_build_info(py, target, app_dir, commit)
        scan_tree(app_dir)

        exe = app_dir / "Transkribator.exe"
        print()
        print(f"  Transkribator.exe : {human(exe.stat().st_size)}")
        print(f"  folder            : {human(dir_size(app_dir))}")

        if args.dry_run:
            print("\ndry run: ZIP skipped")
            print(f"built tree: {app_dir}")
            args.keep = True
            return

        out_dir = REPO / "dist"
        out_dir.mkdir(exist_ok=True)
        zip_path = make_zip(app_dir, out_dir, version)
        print(f"  ZIP               : {human(zip_path.stat().st_size)}  {zip_path}")
        print(f"  SHA256SUMS.txt    : {out_dir / 'SHA256SUMS.txt'}")
    finally:
        if not args.keep:
            subprocess.run(["git", "worktree", "remove", "--force", str(target)],
                           cwd=REPO, check=False)
            shutil.rmtree(target.parent, ignore_errors=True)
        else:
            print(f"\nworktree kept: {target}")
            print(f"remove with: git worktree remove --force \"{target}\"")


if __name__ == "__main__":
    main()
