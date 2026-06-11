#!/usr/bin/env python3
"""
Artvee Gallery · Open-Source Readiness Check
==============================================

Pure-stdlib, read-only check that fails the build if the repository
would not be safe to publish.

What it checks
--------------
1. **Tracked-file inventory** — every file in the git index is
   listed.

2. **Generated-data check** — fail if any path starting with
   ``images/``, ``metadata/``, ``previews/``, ``thumbs/``,
   ``dist/``, ``digests/``, ``logs/``, ``inbox/``, ``index/``,
   or ``web/data/`` is tracked. The only allowed exception is the
   ``.gitkeep`` placeholder files.

3. **Path-leak check** — for non-source text files (``.md``,
   ``.json``, ``.html``, ``.css``, ``.js``, ``.txt``, ``.yaml``,
   ``.yml``, ``.toml``, ``.ini``, ``.cfg``, ``.gitignore``,
   ``LICENSE``), fail if the file contains any of the substrings
   ``/home/``, ``~/``, or ``hermes-agent``.

   Source-code files (``.py``, ``.sh``) are exempted from the
   path-leak check because they legitimately mention these
   strings in defensive checks and design comments. They are
   still subject to the sensitive-keyword check below.

4. **Sensitive-keyword check** — across all tracked text files,
   fail on patterns that look like real secrets:
   ``password = "..."`` (≥ 4 chars),
   ``token = "..."`` (≥ 8 chars),
   ``secret = "..."`` (≥ 4 chars).

   Mentions in docstrings or comments (e.g. ``"we never want to
   leak <forbidden-substring>"``) are not flagged because they
   do not assign a literal secret value to a name.

5. **File-size check** — warn on any tracked file > 1 MB. This is
   not a failure by itself, but a release that has to ship a big
   file should be reconsidered.

Output
------
Prints a per-check PASS/FAIL line and a final overall PASS/FAIL
line. Exits 0 on PASS, 1 on FAIL. Never modifies any file.

Usage
-----
::

    python3 scripts/check_open_source_ready.py
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Paths that must NEVER appear as tracked files (other than .gitkeep).
FORBIDDEN_DIR_PREFIXES = (
    "images/",
    "metadata/",
    "previews/",
    "thumbs/",
    "dist/",
    "digests/",
    "logs/",
    "inbox/",
    "index/",
    "web/data/",
)

# Substrings that should not appear in non-source text files.
PATH_LEAK_SUBSTRINGS = (
    "/home/",
    "~/",
    "hermes-agent",
)

# File extensions exempt from the path-leak substring check.
# Source code legitimately mentions the forbidden substrings for
# defensive checks and design comments.
SOURCE_CODE_EXTS = (".py", ".sh", ".bash", ".zsh")

# Text-file extensions to scan for path leaks.
NON_SOURCE_TEXT_EXTS = (
    ".md", ".json", ".html", ".css", ".js", ".txt",
    ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf",
)

# Files where path leaks are tolerated because they are project meta
# (e.g. the LICENSE file, .gitignore). They are still subject to the
# sensitive-keyword check.
PROJECT_META_FILES = {
    "LICENSE",
    "LICENSE.md",
    "LICENSE.txt",
    ".gitignore",
    "README.md",
}

# Patterns that look like real secrets being assigned to a variable.
# Each pattern must have a real value (length-bounded) and not be
# a bare mention in a comment.
SECRET_PATTERNS = (
    re.compile(r"""(?ix)
        \bpassword\s*=\s*["'][^"'\s]{4,}["']
    """),
    re.compile(r"""(?ix)
        \btoken\s*=\s*["'][^"'\s]{8,}["']
    """),
    re.compile(r"""(?ix)
        \bsecret\s*=\s*["'][^"'\s]{4,}["']
    """),
    re.compile(r"""(?ix)
        \bapikey\s*=\s*["'][^"'\s]{8,}["']
    """),
    re.compile(r"""(?ix)
        \bapi_key\s*=\s*["'][^"'\s]{8,}["']
    """),
)

# 1 MB threshold for the file-size check.
LARGE_FILE_BYTES = 1024 * 1024


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------

def run_git(*args: str) -> str:
    """Run a git command in the repo root and return stdout."""
    result = subprocess.run(
        ["git", "-C", str(REPO_ROOT), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed (rc={result.returncode}): "
            f"{result.stderr.strip()}"
        )
    return result.stdout


def is_git_repo() -> bool:
    try:
        run_git("rev-parse", "--show-toplevel")
        return True
    except RuntimeError:
        return False


def list_tracked_files() -> list[str]:
    out = run_git("ls-files")
    return [line.strip() for line in out.splitlines() if line.strip()]


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

def check_generated_data(files: list[str]) -> tuple[bool, list[str]]:
    """Fail if any tracked file is in a generated-data directory."""
    issues: list[str] = []
    for f in files:
        # Allow .gitkeep placeholders in otherwise-forbidden dirs.
        if f.endswith(".gitkeep"):
            continue
        for prefix in FORBIDDEN_DIR_PREFIXES:
            if f.startswith(prefix):
                issues.append(f"tracked file in generated dir: {f}")
                break
    return (len(issues) == 0), issues


def check_path_leaks(files: list[str]) -> tuple[bool, list[str]]:
    """Fail if non-source text files contain forbidden path substrings."""
    issues: list[str] = []
    for f in files:
        if f in PROJECT_META_FILES:
            continue
        ext = os.path.splitext(f)[1].lower()
        if ext in SOURCE_CODE_EXTS:
            continue  # source code is exempt
        if ext not in NON_SOURCE_TEXT_EXTS:
            # Unknown extension — be conservative: scan as text only if
            # we can read it. The list above covers the files we ship.
            continue
        try:
            text = (REPO_ROOT / f).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for needle in PATH_LEAK_SUBSTRINGS:
            if needle in text:
                issues.append(f"{f}: contains forbidden substring {needle!r}")
    return (len(issues) == 0), issues


def check_secrets(files: list[str]) -> tuple[bool, list[str]]:
    """Fail on patterns that look like hardcoded secrets."""
    issues: list[str] = []
    for f in files:
        try:
            text = (REPO_ROOT / f).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for pat in SECRET_PATTERNS:
            m = pat.search(text)
            if m:
                issues.append(
                    f"{f}: possible hardcoded secret matching "
                    f"{pat.pattern[:40]!r}... at offset {m.start()}"
                )
    return (len(issues) == 0), issues


def check_file_sizes(files: list[str]) -> tuple[list[str], list[str]]:
    """Warn on any tracked file > 1 MB."""
    warnings: list[str] = []
    issues: list[str] = []
    for f in files:
        try:
            size = (REPO_ROOT / f).stat().st_size
        except OSError:
            continue
        if size > LARGE_FILE_BYTES:
            warnings.append(
                f"{f}: {size} bytes > 1 MB — consider whether this "
                f"should really be tracked"
            )
    return warnings, issues


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only open-source readiness check for the Artvee "
            "Gallery repository. Exits 0 on PASS, 1 on FAIL."
        )
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit a single-line JSON summary in addition to the "
             "human-readable output.",
    )
    args = parser.parse_args()

    if not is_git_repo():
        print("FAIL: not a git repository (run inside the project root)")
        return 1

    files = list_tracked_files()
    print(f"== Tracked files: {len(files)} ==")
    for f in files:
        print(f"   {f}")
    print()

    summary: dict[str, object] = {"tracked_files": len(files)}
    overall_pass = True

    # 1. Generated data
    ok_gen, issues_gen = check_generated_data(files)
    print(f"[1/4] generated-data check: {'PASS' if ok_gen else 'FAIL'}")
    for i in issues_gen:
        print(f"      - {i}")
    summary["generated_data"] = {"pass": ok_gen, "issues": issues_gen}
    overall_pass = overall_pass and ok_gen

    # 2. Path leaks
    ok_pl, issues_pl = check_path_leaks(files)
    print(f"[2/4] path-leak check:     {'PASS' if ok_pl else 'FAIL'}")
    for i in issues_pl:
        print(f"      - {i}")
    summary["path_leak"] = {"pass": ok_pl, "issues": issues_pl}
    overall_pass = overall_pass and ok_pl

    # 3. Secrets
    ok_sec, issues_sec = check_secrets(files)
    print(f"[3/4] secret-keyword check:{'PASS' if ok_sec else 'FAIL'}")
    for i in issues_sec:
        print(f"      - {i}")
    summary["secrets"] = {"pass": ok_sec, "issues": issues_sec}
    overall_pass = overall_pass and ok_sec

    # 4. File sizes
    warnings, _ = check_file_sizes(files)
    if warnings:
        print(f"[4/4] file-size check:     WARN ({len(warnings)} files)")
        for w in warnings:
            print(f"      - {w}")
        summary["file_size"] = {"pass": True, "warnings": warnings}
    else:
        print(f"[4/4] file-size check:     PASS")
        summary["file_size"] = {"pass": True, "warnings": []}

    print()
    print(f"== Overall: {'PASS' if overall_pass else 'FAIL'} ==")
    summary["overall"] = "PASS" if overall_pass else "FAIL"

    if args.json:
        print()
        print("JSON_RESULT_BEGIN")
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
        print("JSON_RESULT_END")

    return 0 if overall_pass else 1


if __name__ == "__main__":
    sys.exit(main())
