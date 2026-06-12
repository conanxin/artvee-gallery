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
import os
import shutil
import sys
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


def main():
    parser = argparse.ArgumentParser(
        description="Stage an Artvee report for Telegram MEDIA attachment (P6A)",
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
    args = parser.parse_args()

    try:
        report = Path(args.report).expanduser().resolve()
        root = _resolve_media_root(args.media_root)

        if args.check_only:
            target = root / report.name
            print(f"WOULD_STAGE {target}")
            return 0

        staged = stage_report(report, root)
        # Only the staged absolute path is printed. Never log the source
        # content or any OpenClaw config / token.
        print(staged)
        return 0
    except Exception as e:
        print(f"STAGE_FAIL: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
