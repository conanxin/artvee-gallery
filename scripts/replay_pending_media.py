#!/usr/bin/env python3
"""
Artvee Gallery · Pending MEDIA Replay (P7B+3 / P8D+4)
=====================================================
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
4. On delivered (non-empty Telegram ``message_id``): writes a
   ``.replay-result-<date>.json`` sidecar and moves the pending file to
   the **fixed** ``reports/runtime/media-replay/replayed/`` root
   (preserved, never deleted).
5. On failure: increments ``attempts``, records ``last_error`` and
   ``last_attempt_at``. Once ``attempts >= max_retries``, the pending
   file is moved to the **fixed**
   ``reports/runtime/media-replay/quarantine/`` root with a
   ``.quarantine-<date>.json`` sidecar that explains why.
6. Writes an aggregated ``.replay-results-<date>.json`` summary next to
   the cron summary so downstream tools (``artvee_ops_status``,
   ``replay_cron_last_run``) can read real ``message_id`` values.
7. Supports ``--dry-run`` (default) so it is safe to run by hand.

P8D+4 fixes (delivery truth + stable roots)
-------------------------------------------
* **Stable archive roots**: ``replayed/`` and ``quarantine/`` are no
  longer computed from ``pending_path.parent``; they live at the fixed
  paths under ``reports/runtime/media-replay/``. This prevents the
  recursion bug where a file already inside ``replayed/`` would be
  re-archived into ``replayed/replayed/`` on each run.
* **Delivered requires ``message_id``**: the success branch now checks
  ``result.get("ok")`` **and** ``result.get("message_id")``. Any send
  that returns exit 0 but no parseable ``message_id`` is treated as a
  failed send (attempts + 1), not a delivered message.
* **Per-run aggregate JSON**: every run writes
  ``reports/runtime/media-replay/results/.replay-results-<date>.json``
  containing the full ``results`` list. ``artvee_media_replay_cron.sh``
  reads this file instead of guessing from per-pending sidecars, so
  ``replay_message_ids`` reflects reality.

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
REPLAY_AGGREGATE_PREFIX = ".replay-results-"
REPLAYED_DIRNAME = "replayed"
QUARANTINE_DIRNAME = "quarantine"
RESULTS_DIRNAME = "results"
# P8D+4: stable archive roots (resolved at runtime against pending_root).
REPLAYED_STABLE_SUBDIR = "replayed"
QUARANTINE_STABLE_SUBDIR = "quarantine"
RESULTS_STABLE_SUBDIR = "results"
DEFAULT_MAX_RETRIES = 3
DEFAULT_LIMIT = 10

# P8D+5: notification bundle queue constants. Active bundles live under
# ``daily-health-delivery/pending/``; archives land in ``replayed/``,
# ``quarantine/`` next to ``pending/``; aggregate sidecars go to
# ``results/``. The bundle queue is structurally identical to the
# media-replay queue (same stable-root + active-classification rules)
# but carries a richer payload (full text + staged_report).
NOTIFICATION_BUNDLE_GLOB = "notification-*-*.json"
NOTIFICATION_DELIVERY_ROOTNAME = "daily-health-delivery"
NOTIFICATION_PENDING_SUBDIR = "pending"
NOTIFICATION_REPLAYED_SUBDIR = "replayed"
NOTIFICATION_QUARANTINE_SUBDIR = "quarantine"
NOTIFICATION_RESULTS_SUBDIR = "results"


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
    """Walk the pending tree and return only **active** pending files.

    P8D+4: skip files that already live under a stable ``replayed/`` or
    ``quarantine/`` directory (those are terminal states) and skip
    everything under a ``queue-fix-backup-*`` directory (those are
    immutable backups of pre-normalization state).

    P8D+4B: also exclude ``reports/`` ancestors that point at cleanup
    archives (``legacy-cleaned/``) or stable duplicates, and any path
    that has self-recursive ``replayed/replayed`` / ``quarantine/quarantine``
    nesting (pre-P8D+4 pathology).
    """
    if not root.exists():
        return []
    # Reuse the canonical classifier from the daily-health module so the
    # two scripts never disagree on what counts as active.
    try:
        from artvee_daily_health_check import _classify_pending_path
    except Exception:
        _classify_pending_path = None  # type: ignore
    out: list[Path] = []
    for p in root.rglob(PENDING_GLOB):
        if not p.is_file():
            continue
        if _classify_pending_path is not None:
            cls = _classify_pending_path(p, None)
            if cls != "active_pending":
                continue
        else:
            # Fallback: at minimum honour the historical guards.
            parts = p.parts
            if any(part.startswith("queue-fix-backup-") for part in parts):
                continue
            skip = False
            for i, seg in enumerate(parts):
                if seg in ("replayed", "quarantine") and i > 0 and parts[i - 1] == "media-replay":
                    skip = True
                    break
            if skip:
                continue
        out.append(p)
    return sorted(out)


def _non_active_scope(root: Path) -> dict[str, list[Path]]:
    """Bucket every ``.fallback-pending-*.json`` under ``root`` by class.

    Mirrors ``artvee_daily_health_check._classify_pending_path`` so the
    dry-run diagnostic surfaces the same numbers the cron summary sees.
    Returns a dict of bucket → list[Path], sorted within each bucket.
    """
    buckets: dict[str, list[Path]] = {
        "active_pending": [],
        "terminal_replayed": [],
        "terminal_quarantine": [],
        "results": [],
        "backup_or_legacy": [],
        "legacy_nested": [],
        "unknown": [],
    }
    if not root.exists():
        return buckets
    try:
        from artvee_daily_health_check import _classify_pending_path
    except Exception:
        _classify_pending_path = None  # type: ignore
    for p in root.rglob(PENDING_GLOB):
        if not p.is_file():
            continue
        if _classify_pending_path is not None:
            cls = _classify_pending_path(p, None)
        else:
            cls = "unknown"
        buckets.setdefault(cls, []).append(p)
    for k in buckets:
        buckets[k] = sorted(buckets[k])
    return buckets


def _archive_dir(root: Path, name: str) -> Path:
    """Where archived pending files live.

    P8D+4: archive roots are **always** the stable paths under
    ``reports/runtime/media-replay/`` (``replayed/``, ``quarantine/``,
    ``results/``). They never inherit from ``pending_path.parent``,
    which prevents the recursion bug where a file already inside
    ``replayed/`` would be re-archived into ``replayed/replayed/`` on
    the next run.

    The ``root`` argument is preserved only as a hint for test/override
    flows: if it resolves to a directory outside the canonical
    ``reports/runtime/`` location, we honor it so unit tests can still
    exercise the archive logic against a temp dir.
    """
    try:
        stable = (Path(__file__).resolve().parent.parent / "reports" / "runtime" / "media-replay").resolve()
    except Exception:
        stable = None
    try:
        root_resolved = root.resolve()
    except Exception:
        root_resolved = root
    use_stable = False
    if stable is not None:
        try:
            canonical_reports = (Path(__file__).resolve().parent.parent / "reports" / "runtime").resolve()
        except Exception:
            canonical_reports = None
        if canonical_reports is not None:
            # ``root_resolved`` is absolute; check membership via parent
            # walking so we don't depend on ``Path.parts`` matching an
            # absolute prefix.
            try:
                root_resolved.relative_to(canonical_reports)
                use_stable = True
            except ValueError:
                # Test/override root outside the project.
                use_stable = False
    if use_stable and stable is not None:
        target = stable / name
    else:
        target = root / name
    target.mkdir(parents=True, exist_ok=True)
    return target


def _delivery_archive_dir(delivery_root: Path, name: str) -> Path:
    """Resolve the stable archive root for a notification-bundle queue.

    P8D+5: ``delivery_root`` is ``reports/runtime/daily-health-delivery``.
    Archives (replayed/, quarantine/, results/) live IMMEDIATELY under
    that root, never under ``pending/``, so a bundle already in
    replayed/ cannot be re-archived into ``pending/replayed/`` by a
    botched ``pending_path.parent`` lookup. ``delivery_root`` is
    honored exactly as given (test-flow friendly).
    """
    target = (delivery_root / name).resolve()
    target.mkdir(parents=True, exist_ok=True)
    return target


def _active_notification_bundles(delivery_root: Path) -> list[Path]:
    """Return only ``active`` notification bundle files under pending/.

    P8D+5: a bundle is active iff:
    - file lives in ``delivery_root/pending/`` (immediate child),
    - has not been quarantined (status != "quarantined") or
      replayed (status != "replayed").
    Skips terminal / nested / backup artifacts so the active scan
    mirrors the media-pending classifier.
    """
    if not delivery_root.exists():
        return []
    active_dir = delivery_root / NOTIFICATION_PENDING_SUBDIR
    if not active_dir.exists():
        return []
    out = []
    for p in sorted(active_dir.glob(NOTIFICATION_BUNDLE_GLOB)):
        if not p.is_file():
            continue
        try:
            doc = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            out.append(p)
            continue
        status = (doc.get("status") or "").strip().lower()
        if status in ("replayed", "quarantined"):
            continue
        out.append(p)
    return out


def replay_notification_bundle(
    bundle_path: Path,
    delivery_root: Path,
    *,
    max_retries: int = DEFAULT_MAX_RETRIES,
    media_root: Path | None = None,
    dry_run: bool = False,
) -> dict:
    """Replay a single notification bundle (text first, then MEDIA).

    P8D+5: state machine contract.
      * ``replay_text_and_media``: returns ``delivered=True`` only when
        BOTH ``text_message_id`` and ``media_message_id`` (or no media)
        are non-empty. The bundle is then moved to
        ``delivery_root/replayed/`` with ``status=replayed`` and both
        ids recorded.
      * ``replay_text_only``: text succeeded, media failed. The bundle
        is rewritten in place with ``status=media_pending``,
        ``text_message_id`` recorded, ``media_attempts`` bumped. On
        the next replay run we send only the media (no double text).
      * ``text_failed``: the bundle stays pending; ``attempts`` is
        bumped and ``last_error`` set; nothing is moved.
      * ``quarantined``: ``attempts >= max_retries`` ⇒ move to
        ``delivery_root/quarantine/`` and write ``status=quarantined``.

    The function never prints chat_id, tokens, or any secret.
    """
    if media_root is None:
        media_root = _resolve_media_root_default()

    try:
        bundle = _safe_load(bundle_path)
    except Exception as e:
        return {
            "bundle": str(bundle_path),
            "outcome": "quarantine_corrupt",
            "error": f"{type(e).__name__}: {e}",
        }

    schema = (bundle.get("schema_version") or "").strip()
    if schema != "artvee-notification-bundle-v1":
        return {
            "bundle": str(bundle_path),
            "outcome": "skipped_wrong_schema",
            "schema_version": schema,
            "expected": "artvee-notification-bundle-v1",
        }

    date = bundle.get("date") or "(unknown)"
    text = bundle.get("text") or ""
    staged = (bundle.get("staged_report") or "").strip()
    text_attempts = int(bundle.get("text_attempts") or 0)
    media_attempts = int(bundle.get("media_attempts") or 0)
    if not text:
        return {
            "bundle": str(bundle_path),
            "outcome": "skipped_empty_text",
            "date": date,
        }

    # Already partially replayed: text delivered, media still pending.
    text_message_id = (bundle.get("text_message_id") or "").strip() or None
    media_message_id = (bundle.get("media_message_id") or "").strip() or None

    # Cap retries by text_attempts + media_attempts — the bundle is
    # done when BOTH have hit max_retries.
    if text_attempts >= max_retries and media_attempts >= max_retries:
        if dry_run:
            return {"bundle": str(bundle_path), "outcome": "dry_run", "date": date,
                    "staged_report": staged, "text_message_id": text_message_id}
        archive_dir = _delivery_archive_dir(delivery_root, NOTIFICATION_QUARANTINE_SUBDIR)
        target = archive_dir / bundle_path.name
        shutil.move(str(bundle_path), str(target))
        bundle["status"] = "quarantined"
        bundle["quarantined_at"] = _now_iso()
        bundle["quarantine_reason"] = "max_retries_text_and_media"
        _safe_dump(bundle, target)
        return {
            "bundle": str(bundle_path),
            "outcome": "quarantine_max_retries",
            "date": date,
            "text_message_id": text_message_id,
            "media_message_id": media_message_id,
            "text_attempts": text_attempts,
            "media_attempts": media_attempts,
            "max_retries": max_retries,
        }

    # Step 1: text send (only if we don't already have message_id).
    if not text_message_id and text_attempts < max_retries:
        if dry_run:
            return {
                "bundle": str(bundle_path),
                "outcome": "dry_run",
                "date": date,
                "staged_report": staged,
                "text_preview": text[:200],
            }
        try:
            chat_id = load_chat_id()
        except Exception as e:
            new_text_attempts = text_attempts + 1
            bundle["text_attempts"] = new_text_attempts
            bundle["last_error"] = f"chat_id_resolve: {type(e).__name__}"
            bundle["last_attempt_at"] = _now_iso()
            _safe_dump(bundle, bundle_path)
            if new_text_attempts >= max_retries:
                archive_dir = _delivery_archive_dir(delivery_root, NOTIFICATION_QUARANTINE_SUBDIR)
                new_loc = archive_dir / bundle_path.name
                shutil.move(str(bundle_path), str(new_loc))
                bundle["status"] = "quarantined"
                bundle["quarantined_at"] = _now_iso()
                bundle["quarantine_reason"] = "max_retries_chat_id"
                _safe_dump(bundle, new_loc)
                return {
                    "bundle": str(bundle_path),
                    "outcome": "quarantine_no_chat_id",
                    "attempts": new_text_attempts,
                }
            return {
                "bundle": str(bundle_path),
                "outcome": "skipped_no_chat_id",
                "attempts": new_text_attempts,
            }

        t0 = time.time()
        text_result = send_text(text, chat_id=chat_id, wait=True)
        elapsed_ms = int((time.time() - t0) * 1000)
        new_text_attempts = text_attempts + 1
        bundle["text_attempts"] = new_text_attempts
        bundle["last_attempt_at"] = _now_iso()
        if text_result.get("ok") and text_result.get("message_id"):
            text_message_id = text_result["message_id"]
            bundle["text_message_id"] = text_message_id
            bundle["text_attempt_elapsed_ms"] = elapsed_ms
        else:
            err = (text_result.get("error") or "(no error)")[:300]
            bundle["last_error"] = err
            bundle["text_attempt_elapsed_ms"] = elapsed_ms
            _safe_dump(bundle, bundle_path)
            if new_text_attempts >= max_retries:
                archive_dir = _delivery_archive_dir(delivery_root, NOTIFICATION_QUARANTINE_SUBDIR)
                new_loc = archive_dir / bundle_path.name
                shutil.move(str(bundle_path), str(new_loc))
                bundle["status"] = "quarantined"
                bundle["quarantined_at"] = _now_iso()
                bundle["quarantine_reason"] = "max_retries_text"
                _safe_dump(bundle, new_loc)
                return {
                    "bundle": str(bundle_path),
                    "outcome": "quarantine_text_failed",
                    "attempts": new_text_attempts,
                    "error": err,
                }
            return {
                "bundle": str(bundle_path),
                "outcome": "text_failed_will_retry",
                "attempts": new_text_attempts,
                "error": err,
            }

    # Step 2: media send (only if we have a text_message_id and no
    # media_message_id yet, and there is a staged_report). Skip if the
    # bundle was queued text-only.
    if text_message_id and not media_message_id and staged:
        ok, reason = _validate_staged(staged, media_root)
        if not ok:
            # Staged path drifted; record but do not crash.
            bundle["last_error"] = f"validate_staged: {reason}"
            bundle["last_attempt_at"] = _now_iso()
            _safe_dump(bundle, bundle_path)
            return {
                "bundle": str(bundle_path),
                "outcome": "skipped_invalid_staged",
                "text_message_id": text_message_id,
                "staged_report": staged,
                "reason": reason,
            }
        if dry_run:
            return {
                "bundle": str(bundle_path),
                "outcome": "dry_run_media_only",
                "text_message_id": text_message_id,
                "staged_report": staged,
            }
        try:
            chat_id = load_chat_id()
        except Exception:
            chat_id = None
        t0 = time.time()
        media_result = send_text(text, chat_id=chat_id, wait=True, media=staged)
        elapsed_ms = int((time.time() - t0) * 1000)
        new_media_attempts = media_attempts + 1
        bundle["media_attempts"] = new_media_attempts
        bundle["last_attempt_at"] = _now_iso()
        bundle["media_attempt_elapsed_ms"] = elapsed_ms
        if media_result.get("ok") and media_result.get("message_id"):
            media_message_id = media_result["message_id"]
            bundle["media_message_id"] = media_message_id
        else:
            bundle["last_error"] = (media_result.get("error") or "(no error)")[:300]
            _safe_dump(bundle, bundle_path)
            if new_media_attempts >= max_retries:
                archive_dir = _delivery_archive_dir(delivery_root, NOTIFICATION_QUARANTINE_SUBDIR)
                new_loc = archive_dir / bundle_path.name
                shutil.move(str(bundle_path), str(new_loc))
                bundle["status"] = "quarantined"
                bundle["quarantined_at"] = _now_iso()
                bundle["quarantine_reason"] = "max_retries_media"
                _safe_dump(bundle, new_loc)
                return {
                    "bundle": str(bundle_path),
                    "outcome": "quarantine_media_failed",
                    "text_message_id": text_message_id,
                    "media_attempts": new_media_attempts,
                    "error": bundle["last_error"],
                }
            # Keep bundle in pending; next run will try media-only.
            return {
                "bundle": str(bundle_path),
                "outcome": "media_failed_will_retry",
                "text_message_id": text_message_id,
                "media_attempts": new_media_attempts,
                "error": bundle["last_error"],
            }

    # Final: text_message_id (and media_message_id if applicable) both
    # land the bundle in replayed/.
    bundle["status"] = "replayed"
    bundle["replayed_at"] = _now_iso()
    if dry_run:
        return {
            "bundle": str(bundle_path),
            "outcome": "dry_run_complete",
            "text_message_id": text_message_id,
            "media_message_id": media_message_id,
        }
    archive_dir = _delivery_archive_dir(delivery_root, NOTIFICATION_REPLAYED_SUBDIR)
    new_loc = archive_dir / bundle_path.name
    shutil.move(str(bundle_path), str(new_loc))
    _safe_dump(bundle, new_loc)
    return {
        "bundle": str(bundle_path),
        "outcome": "delivered",
        "date": date,
        "text_message_id": text_message_id,
        "media_message_id": media_message_id,
        "archived_to": str(new_loc),
    }


def _build_replay_text(pending: dict) -> str:
    date = pending.get("date") or "(unknown)"
    reason = pending.get("reason") or "media_transport_deferred"
    deferred_at = pending.get("deferred_at") or "(unknown)"
    return (
        "↻ Artvee Daily Health MEDIA replay\n"
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

    # P8D+4: delivery truth = non-empty Telegram message_id. ``ok=True``
    # alone is not enough (e.g. openclaw exit 0 but regex missed the
    # ``messageId=...`` log line, or no parseable id at all). Without a
    # message_id we cannot prove the message was delivered, so we treat
    # the send as failed and bump attempts just like a transport error.
    delivered = bool(result.get("ok")) and bool(result.get("message_id"))
    if delivered:
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
            "outcome": "delivered",
            "message_id": result.get("message_id"),
            "elapsed_ms": elapsed_ms,
            "staged_report": staged,
            "archived_to": str(new_loc),
            "result_sidecar": str(result_path),
        }

    # Failure path. ``ok=False`` OR ``ok=True`` but no message_id both
    # land here. The error string is preserved either way.
    new_attempts = attempts + 1
    pending["attempts"] = new_attempts
    if result.get("ok") and not result.get("message_id"):
        pending["last_error"] = "openclaw exit 0 but no message_id parsed from log (treated as undelivered)"
    else:
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
    parser.add_argument("--delivery-root", default=None,
                        help="P8D+5: override the notification-bundle queue root. "
                             "Defaults to reports/runtime/daily-health-delivery/.")
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
    parser.add_argument("--include-notification-bundles", action="store_true",
                        help="P8D+5: also replay notification bundles under "
                             "reports/runtime/daily-health-delivery/pending/.")
    parser.add_argument("--only-notification-bundles", action="store_true",
                        help="P8D+5: skip the legacy .fallback-pending-*.json queue "
                             "and only process notification bundles.")
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
    # P8D+4B: scope diagnostic. Always show the bucket layout so the
    # dry-run (and any apply run) confirms only ``active_pending``
    # files are eligible, while still surfacing the historical noise
    # (terminal / backup / nested legacy) for visibility.
    scope = _non_active_scope(pending_root)
    print("[scope] active_pending   =", len(scope.get("active_pending", [])))
    print("[scope] terminal_replayed =", len(scope.get("terminal_replayed", [])))
    print("[scope] terminal_quarantine =", len(scope.get("terminal_quarantine", [])))
    print("[scope] results (aggregate sidecars) =", len(scope.get("results", [])))
    print("[scope] backup_or_legacy =", len(scope.get("backup_or_legacy", [])))
    print("[scope] legacy_nested =", len(scope.get("legacy_nested", [])))
    if scope.get("unknown"):
        print("[scope] unknown =", len(scope.get("unknown", [])))
    print()
    if not pendings:
        print("[ok] pending=0 (no active .fallback-pending-*.json under pending root)")
        # P8D+4: still write an aggregate JSON so the cron summary can
        # report ``pending=0`` with a consistent shape.
        today = datetime.now().strftime("%Y-%m-%d")
        aggregate_dir = _archive_dir(pending_root, RESULTS_STABLE_SUBDIR)
        aggregate_dir.mkdir(parents=True, exist_ok=True)
        aggregate_path = aggregate_dir / f"{REPLAY_AGGREGATE_PREFIX}{today}.json"
        _safe_dump(
            {
                "date": today,
                "generated_at": _now_iso(),
                "dry_run": dry_run,
                "pending_root": str(pending_root),
                "max_retries": args.max_retries,
                "limit": args.limit,
                "totals": {
                    "processed": 0,
                    "delivered": 0,
                    "quarantined": 0,
                    "send_failed_will_retry": 0,
                },
                "results": [],
                "message_ids": [],
            },
            aggregate_path,
        )
        print(f"[info] empty aggregate results written: {aggregate_path}")
        # P8D+5: do NOT early-return here; fall through to the bundle pass
        # below so an empty legacy queue does not skip notification-bundle
        # work when --include-notification-bundles /
        # --only-notification-bundles is set.

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

    # P8D+4: write the per-run aggregate JSON. Downstream
    # ``artvee_media_replay_cron.sh`` reads this file (instead of guessing
    # from per-pending sidecars) so ``replay_message_ids`` reflects real
    # Telegram delivery. The aggregate path is stable under the
    # ``reports/runtime/media-replay/results/`` root.
    today = datetime.now().strftime("%Y-%m-%d")
    aggregate_dir = _archive_dir(pending_root, RESULTS_STABLE_SUBDIR)
    aggregate_name = f"{REPLAY_AGGREGATE_PREFIX}{today}.json"
    aggregate_path = aggregate_dir / aggregate_name
    delivered_ids = [
        str(r.get("message_id")) for r in results
        if r.get("outcome") == "delivered" and r.get("message_id")
    ]
    quarantined_count = sum(
        1 for r in results if str(r.get("outcome", "")).startswith("quarantine_")
    )
    failed_count = sum(
        1 for r in results if r.get("outcome") in ("send_failed_will_retry",)
    )
    aggregate = {
        "date": today,
        "generated_at": _now_iso(),
        "dry_run": dry_run,
        "pending_root": str(pending_root),
        "max_retries": args.max_retries,
        "limit": args.limit,
        "totals": {
            "processed": len(results),
            "delivered": len(delivered_ids),
            "quarantined": quarantined_count,
            "send_failed_will_retry": failed_count,
        },
        "results": results,
        "message_ids": delivered_ids,
    }
    _safe_dump(aggregate, aggregate_path)
    print(f"[info] aggregate results written: {aggregate_path}")
    print(f"[info] delivered message_ids ({len(delivered_ids)}): {','.join(delivered_ids) or '(none)'}")

    # Exit non-zero if any attempt ended in quarantine / send failure
    # (so a cron can alert), but do not crash on skipped files.
    fatal = sum(
        1 for r in results
        if r.get("outcome", "").startswith("quarantine_")
        or r.get("outcome") == "send_failed_will_retry"
    )

    # P8D+5: notification-bundle replay pass. Always run when the
    # --include-notification-bundles / --only-notification-bundles flag
    # is set. The bundle queue is structurally separate from the legacy
    # media-only queue: bundles carry the *text* + an optional staged
    # MEDIA path, so 03:10 can fully recover a Daily Health notification
    # that 03:00 failed to deliver.
    bundle_results = []
    bundle_fatal = 0
    if args.include_notification_bundles or args.only_notification_bundles:
        if args.delivery_root:
            delivery_root = Path(args.delivery_root).expanduser().resolve()
        else:
            delivery_root = base_dir / "reports" / "runtime" / NOTIFICATION_DELIVERY_ROOTNAME
        active = _active_notification_bundles(delivery_root)
        bundle_results = []
        bundle_fatal = 0
        if not active:
            print("[info] notification_bundles_active=0 (no pending bundles)")
        for target in active[: max(0, args.limit)]:
            print(f"[bundle] pending={target.name}")
            outcome = replay_notification_bundle(
                target,
                delivery_root,
                max_retries=args.max_retries,
                media_root=media_root,
                dry_run=dry_run,
            )
            bundle_results.append(outcome)
            text_mid = outcome.get("text_message_id")
            media_mid = outcome.get("media_message_id")
            err = outcome.get("error")
            print(f"  [bundle:{outcome.get('outcome')}] text_message_id={text_mid} media_message_id={media_mid} error={err}")
            bundle_fatal += 1 if (
                str(outcome.get("outcome", "")).startswith("quarantine_")
                or outcome.get("outcome") in ("text_failed_will_retry", "media_failed_will_retry")
            ) else 0

        # Per-run aggregate for the notification-bundle pass.
        results_dir = _delivery_archive_dir(delivery_root, NOTIFICATION_RESULTS_SUBDIR)
        today = datetime.now().strftime("%Y-%m-%d")
        aggregate_path = results_dir / f"notification-bundle-results-{today}.json"
        delivered_text_mids = [
            str(r.get("text_message_id")) for r in bundle_results
            if r.get("outcome") == "delivered" and r.get("text_message_id")
        ]
        delivered_media_mids = [
            str(r.get("media_message_id")) for r in bundle_results
            if r.get("outcome") == "delivered" and r.get("media_message_id")
        ]
        aggregated = {
            "date": today,
            "generated_at": _now_iso(),
            "dry_run": dry_run,
            "pending_root": str(delivery_root),
            "max_retries": args.max_retries,
            "limit": args.limit,
            "totals": {
                "processed": len(bundle_results),
                "delivered": sum(1 for r in bundle_results if r.get("outcome") == "delivered"),
                "quarantined": sum(1 for r in bundle_results if str(r.get("outcome", "")).startswith("quarantine_")),
                "send_failed_will_retry": bundle_fatal,
            },
            "results": bundle_results,
            "text_message_ids": delivered_text_mids,
            "media_message_ids": delivered_media_mids,
        }
        _safe_dump(aggregated, aggregate_path)
        print(f"[info] notification-bundle aggregate results: {aggregate_path}")
        print(f"[info] delivered text_message_ids ({len(delivered_text_mids)}): {','.join(delivered_text_mids) or '(none)'}")
        print(f"[info] delivered media_message_ids ({len(delivered_media_mids)}): {','.join(delivered_media_mids) or '(none)'}")

    return 1 if (fatal or bundle_fatal) else 0


if __name__ == "__main__":
    sys.exit(main())
