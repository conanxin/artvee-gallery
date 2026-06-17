#!/usr/bin/env python3
"""
Artvee Gallery · Pending MEDIA Replay (P7B+3)
=============================================
Re-attach previously-deferred MEDIA files after OpenClaw transport
recovers.

Why this exists
---------------
P7B+2 introduced a deferred-fallback path for ``media_transport_deferred``
failures: instead of hammering a flaky OpenClaw gateway, daily health
writes a small ``.fallback-pending-<date>.json`` file next to the report
and stops. The next run can flush the *text* portion of the fallback
(``P7B+2 flush``), but the actual MEDIA attachment is left untouched.

P7B+3 closes the loop by adding a separate replay step that re-uses the
existing ``staged_report`` path that P7B+2 already wrote into the
OpenClaw media allowlist. This script:

1. Scans ``reports/runtime/**`` for ``.fallback-pending-*.json`` files.
2. Validates each ``staged_report`` path: must exist, be a regular file,
   live under the OpenClaw media root, and not be a symlink.
3. Sends a short text + the staged MEDIA via the existing
   ``artvee_telegram_notify.send_text`` helper.
4. On success: writes a ``.replay-result-<date>.json`` next to the
   pending file and moves the pending file to
   ``reports/runtime/daily-health/replayed/`` (preserved, never deleted).
5. On failure: increments ``attempts``, records ``last_error`` and
   ``last_attempt_at``. Once ``attempts >= max_retries``, the pending
   file is moved to
   ``reports/runtime/daily-health/quarantine/`` with a
   ``.quarantine-<date>.json`` sidecar that explains why.
6. Supports ``--dry-run`` (default) so it is safe to run by hand.

Safety boundaries (deliberate, not configurable)
------------------------------------------------
* Will NOT touch ``images/``, ``metadata/``, ``thumbs/``, ``dist/``,
  ``digests/``, ``logs/``, ``inbox/``, ``web/data/``, ``index/``,
  ``manifest``, or the ``.git`` directory.
* Will NOT retry retired URLs / refill / nightly batch.
* Will NOT push GitHub Pages.
* Will NOT expand the OpenClaw MEDIA allowlist.
* Will NOT delete a pending file. Success → ``replayed/``, exhaustion
  → ``quarantine/``. Always preserved on disk.
* Will NOT print ``chat_id`` / token / cookie / any secret.

Usage
-----
::

    # Default: dry-run, scan the whole reports/runtime tree
    python3 scripts/replay_pending_media.py

    # Real replay (override dry-run)
    python3 scripts/replay_pending_media.py --apply

    # Tighten retries
    python3 scripts/replay_pending_media.py --apply --max-retries 3

    # Cap scope for cron / quick wins
    python3 scripts/replay_pending_media.py --apply --limit 5

    # Custom pending root (testing only)
    python3 scripts/replay_pending_media.py --pending-root /tmp/test-pending
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

# Re-use the existing notifier (same PYTHONPATH as the rest of the project)
sys.path.insert(0, str(Path(__file__).resolve().parent))
from artvee_telegram_notify import send_text, load_chat_id  # noqa: E402

# Allow importing the stage helper for media-root resolution
try:
    from stage_report_for_telegram_media import _resolve_media_root  # type: ignore
except Exception:  # pragma: no cover - we degrade gracefully below
    _resolve_media_root = None  # type: ignore

PENDING_GLOB = ".fallback-pending-*.json"
QUARANTINE_PREFIX = ".quarantine-"
REPLAY_RESULT_PREFIX = ".replay-result-"
REPLAYED_DIRNAME = "replayed"
QUARANTINE_DIRNAME = "quarantine"
DEFAULT_MAX_RETRIES = 3
DEFAULT_LIMIT = 10


def _now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def _safe_load(path: Path) -> dict:
    """Read JSON without leaking the file path back into logs."""
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _safe_dump(obj: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


def _resolve_media_root_default() -> Path:
    """Resolve the OpenClaw media root (allowlist dir)."""
    if _resolve_media_root is not None:
        try:
            return Path(_resolve_media_root(None)).resolve()
        except Exception:
            pass
    # Fallback: environment override, else ~/.openclaw/media
    env_root = os.environ.get("ARTVEE_MEDIA_ROOT")
    if env_root:
        return Path(env_root).expanduser().resolve()
    return Path.home() / ".openclaw" / "media"


def _validate_staged(staged: str, media_root: Path) -> tuple[bool, str]:
    """Ensure the staged path is a real file under the media allowlist.

    Returns ``(ok, reason)``. ``reason`` is empty when ``ok`` is True.
    """
    if not staged:
        return False, "staged_report missing"
    p = Path(staged)
    if not p.is_absolute():
        return False, f"staged_report not absolute: {staged!r}"
    # Reject symlink (allowlist must point at the real file).
    if p.is_symlink():
        return False, f"staged_report is a symlink: {staged!r}"
    if not p.exists():
        return False, f"staged_report missing on disk: {staged!r}"
    if not p.is_file():
        return False, f"staged_report is not a regular file: {staged!r}"
    try:
        p_resolved = p.resolve(strict=True)
    except Exception as e:
        return False, f"staged_report cannot resolve: {type(e).__name__}: {e}"
    if media_root and media_root not in p_resolved.parents and p_resolved != media_root:
        return False, f"staged_report outside media root ({media_root}): {p_resolved}"
    return True, ""


def _pending_paths(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(p for p in root.rglob(PENDING_GLOB) if p.is_file())


def _archive_dir(root: Path, name: str) -> Path:
    """Where archived pending files live (sibling of the daily-health dir)."""
    # Use the same parent as the daily-health dir by default; that keeps
    # archives under reports/runtime/daily-health/<replayed|quarantine>.
    target = root / name
    target.mkdir(parents=True, exist_ok=True)
    return target


def _build_replay_text(pending: dict) -> str:
    date = pending.get("date") or "(unknown)"
    reason = pending.get("reason") or "media_transport_deferred"
    deferred_at = pending.get("deferred_at") or "(unknown)"
    return (
        "↻ Artvee Gallery P7B+3 deferred MEDIA replay\n"
        f"Date: {date}\n"
        f"Reason: {reason} (deferred at {deferred_at})\n"
        f"Action: re-attached staged report after transport recovery"
    )


def _record_result(
    pending_path: Path,
    ok: bool,
    payload: dict,
    *,
    dry_run: bool,
) -> Path:
    """Write a ``.replay-result-<date>.json`` next to the pending file."""
    # pending_path stem looks like .fallback-pending-2026-06-18.json
    parts = pending_path.name.split("-")
    # .fallback_pend ing_2026_06_18.json  (split on '-')
    date_segment = "-".join(parts[3:]).rsplit(".", 1)[0]
    result_name = f"{REPLAY_RESULT_PREFIX}{date_segment}.json"
    result_path = pending_path.parent / result_name
    body = {
        "ok": ok,
        "dry_run": dry_run,
        "pending_path": str(pending_path),
        "recorded_at": _now_iso(),
        **payload,
    }
    _safe_dump(body, result_path)
    return result_path


def _archive_pending(pending_path: Path, archive_dir: Path) -> Path:
    archive_dir.mkdir(parents=True, exist_ok=True)
    target = archive_dir / pending_path.name
    # shutil.move is fine across same-filesystem; on cross-fs it falls
    # back to copy+remove. Either way the original is preserved under
    # the new location.
    shutil.move(str(pending_path), str(target))
    return target


def replay_one(
    pending_path: Path,
    *,
    max_retries: int,
    media_root: Path,
    dry_run: bool,
) -> dict:
    """Replay a single pending file. Returns a small dict for the caller."""
    try:
        pending = _safe_load(pending_path)
    except Exception as e:
        # Corrupt JSON: quarantine immediately so we do not loop on it.
        return {
            "pending": str(pending_path),
            "outcome": "quarantine_corrupt",
            "error": f"{type(e).__name__}: {e}",
        }

    attempts = int(pending.get("attempts") or 0)
    if attempts >= max_retries:
        # Defensive: archive to quarantine/ and preserve the file.
        if dry_run:
            return {
                "pending": str(pending_path),
                "outcome": "quarantine_max_retries",
                "attempts": attempts,
                "max_retries": max_retries,
                "dry_run": True,
            }
        archive_dir = _archive_dir(pending_path.parent, QUARANTINE_DIRNAME)
        new_loc = _archive_pending(pending_path, archive_dir)
        pending["quarantined_at"] = _now_iso()
        pending["quarantine_reason"] = "max_retries_reached_on_load"
        _safe_dump(pending, new_loc)
        _record_result(new_loc, ok=False, payload={"outcome": "quarantine_max_retries",
                                                    "attempts": attempts,
                                                    "max_retries": max_retries},
                        dry_run=dry_run)
        return {
            "pending": str(pending_path),
            "outcome": "quarantine_max_retries",
            "attempts": attempts,
            "max_retries": max_retries,
            "message_id": None,
            "error": None,
        }

    staged = pending.get("staged_report") or ""
    ok, reason = _validate_staged(staged, media_root)
    if not ok:
        # We still want this on record. Increment attempts and let
        # the next run decide (or, if exhausted, quarantine).
        new_attempts = attempts + 1
        pending["attempts"] = new_attempts
        pending["last_error"] = f"validate_staged: {reason}"
        pending["last_attempt_at"] = _now_iso()
        if new_attempts >= max_retries:
            archive_dir = _archive_dir(pending_path.parent, QUARANTINE_DIRNAME)
            new_loc = _archive_pending(pending_path, archive_dir)
            _safe_dump(pending, new_loc)
            return {
                "pending": str(pending_path),
                "outcome": "quarantine_invalid_staged",
                "attempts": new_attempts,
                "max_retries": max_retries,
                "reason": reason,
            }
        # Otherwise, write the bumped attempts back in place (no move).
        _safe_dump(pending, pending_path)
        return {
            "pending": str(pending_path),
            "outcome": "skipped_invalid_staged",
            "attempts": new_attempts,
            "reason": reason,
        }

    text = _build_replay_text(pending)
    if dry_run:
        return {
            "pending": str(pending_path),
            "outcome": "dry_run",
            "staged_report": staged,
            "text_preview": text,
        }

    # Resolve chat_id once; bail out gracefully if not configured.
    try:
        chat_id = load_chat_id()
    except Exception as e:
        # Same handling as validate_staged failure: bump attempts.
        new_attempts = attempts + 1
        pending["attempts"] = new_attempts
        pending["last_error"] = f"chat_id_resolve: {type(e).__name__}: {e}"
        pending["last_attempt_at"] = _now_iso()
        if new_attempts >= max_retries:
            archive_dir = _archive_dir(pending_path.parent, QUARANTINE_DIRNAME)
            new_loc = _archive_pending(pending_path, archive_dir)
            _safe_dump(pending, new_loc)
            return {
                "pending": str(pending_path),
                "outcome": "quarantine_no_chat_id",
                "attempts": new_attempts,
                "max_retries": max_retries,
            }
        _safe_dump(pending, pending_path)
        return {
            "pending": str(pending_path),
            "outcome": "skipped_no_chat_id",
            "attempts": new_attempts,
        }

    # Real send.
    t0 = time.time()
    result = send_text(text, chat_id=chat_id, wait=True, media=staged)
    elapsed_ms = int((time.time() - t0) * 1000)

    if result.get("ok"):
        # Move to replayed/ and write a result sidecar.
        new_attempts = attempts + 1
        pending["attempts"] = new_attempts
        pending["last_attempt_at"] = _now_iso()
        pending["last_replay_message_id"] = result.get("message_id")
        archive_dir = _archive_dir(pending_path.parent, REPLAYED_DIRNAME)
        new_loc = _archive_pending(pending_path, archive_dir)
        # Persist the bumped attempts in the archived copy.
        _safe_dump(pending, new_loc)
        result_path = _record_result(
            pending_path,
            ok=True,
            payload={
                "message_id": result.get("message_id"),
                "elapsed_ms": elapsed_ms,
                "staged_report": staged,
                "archived_to": str(new_loc),
            },
            dry_run=False,
        )
        return {
            "pending": str(pending_path),
            "outcome": "replayed",
            "message_id": result.get("message_id"),
            "elapsed_ms": elapsed_ms,
            "staged_report": staged,
            "archived_to": str(new_loc),
            "result_sidecar": str(result_path),
        }

    # Failure: bump attempts, decide quarantine.
    new_attempts = attempts + 1
    pending["attempts"] = new_attempts
    pending["last_error"] = str(result.get("error") or "(no error message)")[:300]
    pending["last_attempt_at"] = _now_iso()
    if new_attempts >= max_retries:
        archive_dir = _archive_dir(pending_path.parent, QUARANTINE_DIRNAME)
        new_loc = _archive_pending(pending_path, archive_dir)
        _safe_dump(pending, new_loc)
        result_path = _record_result(
            pending_path,
            ok=False,
            payload={
                "elapsed_ms": elapsed_ms,
                "error": pending["last_error"],
                "archived_to": str(new_loc),
            },
            dry_run=False,
        )
        return {
            "pending": str(pending_path),
            "outcome": "quarantine_send_failed",
            "attempts": new_attempts,
            "max_retries": max_retries,
            "error": pending["last_error"],
            "result_sidecar": str(result_path),
        }
    _safe_dump(pending, pending_path)
    return {
        "pending": str(pending_path),
        "outcome": "send_failed_will_retry",
        "attempts": new_attempts,
        "max_retries": max_retries,
        "error": pending["last_error"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--pending-root", default="reports/runtime",
                        help="Where to look for .fallback-pending-*.json (default: reports/runtime)")
    parser.add_argument("--max-retries", type=int, default=DEFAULT_MAX_RETRIES,
                        help=f"Archive to quarantine after this many failed attempts (default: {DEFAULT_MAX_RETRIES})")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT,
                        help=f"Maximum pending files to process per run (default: {DEFAULT_LIMIT})")
    parser.add_argument("--dry-run", action="store_true", default=True,
                        help="Plan + validate only, do NOT call Telegram and do NOT move files. (default)")
    parser.add_argument("--apply", action="store_true",
                        help="Actually send to Telegram and move files. Off by default for safety.")
    parser.add_argument("--openclaw-bin", default=None,
                        help="OpenClaw binary override (forwarded to the notifier).")
    parser.add_argument("--media-root", default=None,
                        help="Override the OpenClaw media allowlist root (advanced).")
    args = parser.parse_args()

    base_dir = Path(__file__).resolve().parent.parent
    pending_root = (base_dir / args.pending_root).resolve()
    media_root = (Path(args.media_root).expanduser().resolve()
                  if args.media_root else _resolve_media_root_default())

    # Default is dry-run. Pass --apply (or --no-dry-run) to actually send.
    dry_run = True
    if args.apply:
        dry_run = False

    print(f"[info] pending_root = {pending_root}")
    print(f"[info] media_root   = {media_root}")
    print(f"[info] max_retries  = {args.max_retries}")
    print(f"[info] limit        = {args.limit}")
    print(f"[info] mode         = {'dry-run' if dry_run else 'APPLY (real send)'}")
    print(f"[info] openclaw_bin = {args.openclaw_bin or '(use notifier default)'}")

    pendings = _pending_paths(pending_root)
    if not pendings:
        print("[ok] pending=0 (no .fallback-pending-*.json files under pending root)")
        return 0

    targets = pendings[: max(0, args.limit)]
    skipped = pendings[args.limit:]
    if skipped:
        print(f"[info] skipping {len(skipped)} extra pending file(s) due to --limit {args.limit}")

    results = []
    for p in targets:
        r = replay_one(
            p,
            max_retries=args.max_retries,
            media_root=media_root,
            dry_run=dry_run,
        )
        results.append(r)
        outcome = r.get("outcome", "?")
        msg = r.get("message_id")
        err = r.get("error")
        # NB: never print chat_id / tokens / secrets.
        print(f"[{outcome}] pending={r.get('pending')} message_id={msg} error={err}")

    # Summary
    by_outcome: dict[str, int] = {}
    for r in results:
        by_outcome[r.get("outcome", "?")] = by_outcome.get(r.get("outcome", "?"), 0) + 1
    print()
    print("=== replay summary ===")
    for k, v in sorted(by_outcome.items()):
        print(f"  {k}: {v}")
    print(f"  total processed: {len(results)}")
    print(f"  skipped due to --limit: {len(skipped)}")
    print(f"  dry_run: {dry_run}")

    # Exit non-zero if any attempt ended in quarantine / send failure
    # (so a cron can alert), but do not crash on skipped files.
    fatal = sum(
        1 for r in results
        if r.get("outcome", "").startswith("quarantine_")
        or r.get("outcome") == "send_failed_will_retry"
    )
    return 1 if fatal else 0


if __name__ == "__main__":
    sys.exit(main())
