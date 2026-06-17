#!/usr/bin/env python3
"""
Artvee Telegram MEDIA Staging Helper
====================================

P6A fix: the OpenClaw Telegram notifier accepts local media only from a
whitelisted set of system directories (e.g. ~/.openclaw/media/, ~/.openclaw/workspace/media/,
~/.openclaw/workspace/tmp/). Artvee reports live under
``~/workspace/reports/`` which is NOT whitelisted, so a previous attempt
to attach the report via ``--media <report-path>`` produced::

    LocalMediaAccessError: Local media path is not under an allowed directory

This helper bridges the gap by **copying** the report into a
project-namespaced subdirectory of an allowed media root, then printing
the staged path. The Telegram notifier can then use ``MEDIA: <staged>``
to attach the file.

P7B+2 extension: ``--print-meta`` mode emits a single-line JSON object
containing both the source (raw) report path and the staged path, plus
the file size and an explicit ``stage_failed`` boolean. This lets the
caller (artvee_daily_health_check.py) detect a staging failure cleanly
and avoid ever attempting to attach the raw (non-allowlisted) path.

Design choices
--------------

1. **Staging, not allowlist expansion.** We deliberately do NOT touch
   the OpenClaw allowlist. Copying the file is the smallest possible
   change and keeps the OpenClaw security boundary intact.
2. **Project-namespaced subdir.** Staged files go into
   ``<media_root>/artvee-reports/`` so multiple local projects can share
   the same media root without collision.
3. **No commit.** The staged copy lives outside the Artvee repo and is
   not tracked by any project.
4. **Idempotent overwrite.** Running twice with the same input overwrites
   the prior copy. File size and existence are checked before reporting
   success.
5. **Default media root = ``~/.openclaw/media/artvee-reports/``** —
   resolved at runtime so the helper is portable.
6. **P7B+2: no silent raw fallback.** If staging fails, ``--print-meta``
   emits ``stage_failed: true`` with the exact reason, and the caller is
   expected to record the failure rather than fall back to the raw path.

Safety
------

* Refuses to follow symlinks in the source path.
* Refuses to copy a directory.
* Refuses to copy outside the chosen ``<media_root>/artvee-reports/``
  prefix even if the user provides a tricky ``--media-root`` (the
  ``artvee-reports`` component is always appended).
* Never prints tokens, env vars, or paths inside ``~/.openclaw/openclaw.json``.
"""
import argparse
import json
import os
import shutil
import sys
import traceback
from pathlib import Path

DEFAULT_MEDIA_ROOT = Path.home() / ".openclaw" / "media"
STAGE_SUBDIR = "artvee-reports"


def _resolve_media_root(override: str) -> Path:
    """Pick the media root: override > $ARTVEE_MEDIA_ROOT > default."""
    if override:
        root = Path(override).expanduser().resolve()
    else:
        env_root = os.environ.get("ARTVEE_MEDIA_ROOT", "").strip()
        root = Path(env_root).expanduser().resolve() if env_root else DEFAULT_MEDIA_ROOT.resolve()
    final = (root / STAGE_SUBDIR).resolve()
    # Defense in depth: final must be a child of the root.
    if STAGE_SUBDIR not in final.parts:
        raise RuntimeError(f"refusing to use non-namespaced staging path: {final}")
    return final


def stage_report(report_path: Path, media_root: Path) -> Path:
    if not report_path.exists():
        raise FileNotFoundError(f"report not found: {report_path}")
    if report_path.is_symlink():
        raise RuntimeError(f"refusing to follow symlink: {report_path}")
    if report_path.is_dir():
        raise RuntimeError(f"refusing to stage a directory: {report_path}")
    if not report_path.is_file():
        raise RuntimeError(f"refusing to stage a non-regular file: {report_path}")

    media_root.mkdir(parents=True, exist_ok=True)
    target = media_root / report_path.name
    # Atomic-ish: copy to .tmp then rename. Avoids partial files on failure.
    tmp_target = target.with_suffix(target.suffix + ".staging")
    shutil.copy2(report_path, tmp_target)
    os.replace(tmp_target, target)

    # Verify
    if not target.is_file():
        raise RuntimeError(f"post-stage check failed: {target}")
    if target.stat().st_size <= 0:
        raise RuntimeError(f"staged file is empty: {target}")
    if target.stat().st_size != report_path.stat().st_size:
        raise RuntimeError(
            f"size mismatch: source={report_path.stat().st_size} staged={target.stat().st_size}"
        )
    return target


def _meta_ok(report: Path, staged: Path) -> dict:
    return {
        "ok": True,
        "stage_failed": False,
        "raw_report": str(report),
        "staged_report": str(staged),
        "staged_size": staged.stat().st_size,
        "raw_size": report.stat().st_size,
        "media_root": str(staged.parent.parent),
        "stage_subdir": staged.parent.name,
        "error": None,
    }


def _meta_fail(report: Path, root: Path, exc: BaseException) -> dict:
    return {
        "ok": False,
        "stage_failed": True,
        "raw_report": str(report) if report else None,
        "staged_report": None,
        "staged_size": 0,
        "raw_size": report.stat().st_size if report and report.exists() and report.is_file() else 0,
        "media_root": str(root.parent) if root else None,
        "stage_subdir": STAGE_SUBDIR,
        "error": f"{type(exc).__name__}: {exc}",
    }


def main():
    parser = argparse.ArgumentParser(
        description="Stage an Artvee report for Telegram MEDIA attachment (P6A, P7B+2 meta mode)"
    )
    parser.add_argument(
        "--report",
        required=True,
        help="Absolute path to the source report (e.g. ~/workspace/reports/foo.md)",
    )
    parser.add_argument(
        "--media-root",
        default=None,
        help="Override media root (default: ~/.openclaw/media). "
             "Project-namespaced subdir 'artvee-reports' is always appended.",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Do not copy; just print the would-be staged path under the chosen root.",
    )
    parser.add_argument(
        "--print-meta",
        action="store_true",
        help="Emit a single-line JSON object with raw_report / staged_report / size / "
             "stage_failed / error. Exit code is 0 only when staging succeeded; non-zero "
             "on any failure (the caller is expected to read the JSON to learn why).",
    )
    args = parser.parse_args()

    # Resolve the report path up front so --check-only / --print-meta can also
    # report the raw path even when it is missing.
    report_arg = Path(args.report).expanduser()
    try:
        report_resolved = report_arg.resolve()
    except Exception:
        report_resolved = report_arg

    try:
        root = _resolve_media_root(args.media_root)
    except Exception as e:
        if args.print_meta:
            print(json.dumps(_meta_fail(report_resolved, Path(DEFAULT_MEDIA_ROOT), e),
                             ensure_ascii=False))
        else:
            print(f"STAGE_FAIL: {e}", file=sys.stderr)
        return 1

    if args.check_only:
        target = root / report_resolved.name
        print(f"WOULD_STAGE {target}")
        return 0

    try:
        staged = stage_report(report_resolved, root)
    except Exception as e:
        if args.print_meta:
            # Always emit raw_report even on failure so the caller can record
            # the diagnostic context.
            print(json.dumps(_meta_fail(report_resolved, root, e), ensure_ascii=False))
        else:
            print(f"STAGE_FAIL: {e}", file=sys.stderr)
        return 1

    if args.print_meta:
        print(json.dumps(_meta_ok(report_resolved, staged), ensure_ascii=False))
        return 0

    # Legacy mode: print only the staged absolute path.
    print(staged)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        # Defense in depth: never let an uncaught exception crash the caller
        # without a structured --print-meta envelope.
        print(json.dumps({
            "ok": False,
            "stage_failed": True,
            "raw_report": None,
            "staged_report": None,
            "staged_size": 0,
            "raw_size": 0,
            "media_root": None,
            "stage_subdir": STAGE_SUBDIR,
            "error": f"FATAL: {type(e).__name__}: {e}",
            "traceback": traceback.format_exc().splitlines()[-3:],
        }, ensure_ascii=False))
        sys.exit(2)
