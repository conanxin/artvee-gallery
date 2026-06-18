#!/usr/bin/env python3
"""Artvee Gallery · Post-stable ops status aggregator (P8A).

This script is the *single* read-only command operators run after
the v0.2.0 stable release. It does **not** download, refill, run
nightly batch, push Pages, or trigger any approve. It only reads
state already on disk and online (optionally) and assembles one
JSON / Markdown report that captures:

  * repository head + latest tag + release version
  * records / known_retired / blocking_unresolved
  * readiness + strict integrity
  * candidate readiness (gallery + digest)
  * digest history + near-dup clusters
  * pending MEDIA + quarantined MEDIA
  * OpenClaw transport health
  * daily health cron installation
  * latest health report + telegram status
  * public gallery / digest URLs
  * online gallery / digest (only with --online)
  * Pages guard availability (read-only) + Pages repo clean status
  * recommended_action (one of the canonical enum values)

Default mode is read-only + no-telegram. With --media it sends the
generated MD report via the same staged-media / fallback pipeline
the daily health check uses. It never auto-replays pending MEDIA;
it only reports counts.

Output:
  reports/runtime/ops/artvee-ops-status-YYYY-MM-DD.json
  reports/runtime/ops/artvee-ops-status-YYYY-MM-DD.md
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
RUNTIME_OPS = REPO_ROOT / "reports" / "runtime" / "ops"
DAILY_HEALTH_DIR = REPO_ROOT / "reports" / "runtime" / "daily-health"
RUNTIME_REPORTS = REPO_ROOT / "reports" / "runtime"
PAGES_REPO_DEFAULT = Path.home() / "conanxin.github.io"
PUBLIC_GALLERY_URL = "https://conanxin.github.io/projects/artvee-gallery-demo/"
PUBLIC_DIGEST_URL = "https://conanxin.github.io/projects/artvee-gallery-digest/"

# Recommended action enum (must match docs/P8A model)
ACTION_HEALTHY = "healthy_no_action"
ACTION_CANDIDATE = "candidate_ready_manual_publish_optional"
ACTION_PAGES_DRIFT = "attention_required_pages_content_drift"
ACTION_MEDIA_PENDING = "attention_required_media_pending"
ACTION_INTEGRITY = "attention_required_integrity_failure"
ACTION_READINESS = "attention_required_readiness_failure"

# Helpers ---------------------------------------------------------------------


def _utcnow_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _run(cmd: list[str], cwd: Path | None = None, timeout: int = 8) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(
            cmd, cwd=str(cwd) if cwd else None, capture_output=True,
            text=True, timeout=timeout,
        )
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        return 124, "", f"timeout after {timeout}s"
    except FileNotFoundError as e:
        return 127, "", f"missing binary: {e}"


def _git_head() -> str:
    rc, out, _ = _run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO_ROOT)
    return out.strip() if rc == 0 else "unknown"


def _git_latest_tag() -> str:
    rc, out, _ = _run(["git", "describe", "--tags", "--abbrev=0"], cwd=REPO_ROOT)
    return out.strip() if rc == 0 else "none"


def _git_status_clean() -> bool:
    rc, out, _ = _run(["git", "status", "--porcelain"], cwd=REPO_ROOT)
    return rc == 0 and not out.strip()


def _is_cron_installed() -> bool:
    rc, out, _ = _run(["crontab", "-l"])
    if rc != 0:
        return False
    return "P7B daily health check" in out or "artvee_daily_health_check.sh" in out


def _pages_guard_available() -> dict[str, bool]:
    return {
        "guard_script": (REPO_ROOT / "scripts" / "check-project-publish-guard.py").exists(),
        "guard_doc": (REPO_ROOT / "docs" / "PAGES_PUBLISH_GUARD.md").exists(),
    }


def _pages_repo_clean(pages_repo: Path) -> str:
    """Read-only check whether the local Pages repo clone is clean."""
    if not (pages_repo / ".git").exists():
        return "unknown"
    rc, out, _ = _run(["git", "status", "--porcelain"], cwd=pages_repo)
    if rc != 0:
        return "unknown"
    return "true" if not out.strip() else "false"


def _latest_daily_health() -> tuple[Path | None, dict[str, Any] | None]:
    if not DAILY_HEALTH_DIR.exists():
        return None, None
    files = sorted(DAILY_HEALTH_DIR.glob("artvee-daily-health-*.json"))
    if not files:
        return None, None
    latest = files[-1]
    return latest, _read_json(latest)


def _scan_pending_media() -> dict[str, int]:
    """Scan .fallback-pending-*.json in the daily-health dir. Reuse
    the exact same helper artvee_daily_health_check uses so counts
    never drift."""
    try:
        from artvee_daily_health_check import _scan_pending_media as _dh_scan
    except ImportError:
        return {"pending": 0, "replayable": 0, "quarantined": 0}
    result = _dh_scan(DAILY_HEALTH_DIR)
    return {
        "pending": int(result.get("pending") or 0),
        "replayable": int(result.get("replayable") or 0),
        "quarantined": int(result.get("quarantined") or 0),
    }


def _probe_transport() -> dict[str, Any]:
    """Side-effect-free transport probe. Runs the existing
    check_openclaw_transport.py if available, never sends."""
    probe_script = REPO_ROOT / "scripts" / "check_openclaw_transport.py"
    if not probe_script.exists():
        return {"status": "not_checked", "latency_ms": 0, "error_class": "probe_script_missing"}
    try:
        proc = subprocess.run(
            [sys.executable, str(probe_script)],
            capture_output=True, text=True, timeout=15,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            payload = json.loads(proc.stdout)
            version_probe = (payload.get("probes") or {}).get("version") or {}
            return {
                "status": payload.get("status", "unknown"),
                "latency_ms": int(version_probe.get("elapsed_ms") or 0),
                "error_class": str(version_probe.get("error_class") or ""),
            }
    except (subprocess.TimeoutExpired, json.JSONDecodeError, ValueError) as e:
        return {"status": "error", "latency_ms": 0, "error_class": f"probe_{type(e).__name__}"}
    return {"status": "error", "latency_ms": 0, "error_class": "probe_failed"}


def _http_head(url: str, timeout: int = 4) -> int:
    try:
        proc = subprocess.run(
            ["curl", "-sS", "-o", "/dev/null", "-w", "%{http_code}",
             "-L", "--max-time", str(timeout), url],
            capture_output=True, text=True, timeout=timeout + 2,
        )
        return int(proc.stdout.strip() or "0")
    except (subprocess.TimeoutExpired, ValueError, FileNotFoundError):
        return 0


# Aggregation ----------------------------------------------------------------


def _build_status(args: argparse.Namespace) -> dict[str, Any]:
    status_report = _read_json(RUNTIME_REPORTS / "artvee-status-report.json") or {}
    daily_path, daily_doc = _latest_daily_health()
    daily_checks = (daily_doc or {}).get("checks", {}) if daily_doc else {}
    daily_media_replay = (daily_doc or {}).get("media_replay", {}) if daily_doc else {}
    daily_telegram = (daily_doc or {}).get("telegram", {}) if daily_doc else {}
    nightly = (daily_checks.get("nightly_batch") or {}) if daily_checks else {}
    candidate = (daily_checks.get("candidate_state") or {}) if daily_checks else {}
    digest = (daily_checks.get("digest_history") or {}) if daily_checks else {}
    clusters = (daily_checks.get("near_dup_clusters") or {}) if daily_checks else {}
    readiness = (daily_checks.get("readiness") or {}) if daily_checks else {}
    integrity = (daily_checks.get("integrity") or {}) if daily_checks else {}

    pending = _scan_pending_media()
    transport = _probe_transport()
    pages_guard = _pages_guard_available()
    pages_repo = _pages_repo_clean(PAGES_REPO_DEFAULT) if args.include_pages else "skipped"
    cron_installed = _is_cron_installed()

    online_gallery = None
    online_digest = None
    if args.online:
        online_gallery = _http_head(PUBLIC_GALLERY_URL)
        online_digest = _http_head(PUBLIC_DIGEST_URL)

    # Records: prefer status_report (counts artworks.json).
    # daily_health counts images/ which may include media/.
    records = status_report.get("records") or (daily_checks.get("status_report") or {}).get("records")
    known_retired = status_report.get("known_retired", 4)
    blocking_unresolved = status_report.get("blocking_unresolved", 0)

    # Recommended action (canonical enum; first matching wins, priority
    # is: integrity > readiness > pages > media > candidate > healthy).
    recommended = ACTION_HEALTHY
    if str(integrity.get("status", "")).upper() != "PASS":
        recommended = ACTION_INTEGRITY
    elif str(readiness.get("status", "")).upper() != "PASS":
        recommended = ACTION_READINESS
    elif online_gallery in (404,) or online_digest in (404,):
        recommended = ACTION_PAGES_DRIFT
    elif pending.get("pending", 0) > 0 or pending.get("replayable", 0) > 0:
        recommended = ACTION_MEDIA_PENDING
    elif (candidate.get("gallery_ready") and candidate.get("digest_ready")):
        recommended = ACTION_CANDIDATE

    return {
        "generated_at": _utcnow_iso(),
        "generated_by": "scripts/artvee_ops_status.py",
        "version": "1.0.0",
        "date": args.date,
        "repo_head": _git_head(),
        "release_version": _git_latest_tag(),
        "repo_clean": _git_status_clean(),
        "records": records,
        "records_source": "artvee-status-report.json" if status_report else "daily_health",
        "known_retired": known_retired,
        "blocking_unresolved": blocking_unresolved,
        "strict_integrity": str(integrity.get("status", "unknown")).upper() or "UNKNOWN",
        "readiness": str(readiness.get("status", "unknown")).upper() or "UNKNOWN",
        "candidate_gallery_ready": bool(candidate.get("gallery_ready")),
        "candidate_digest_ready": bool(candidate.get("digest_ready")),
        "digest_history_entries": int(digest.get("entries") or 0),
        "near_dup_clusters": int(clusters.get("cluster_count") or 0),
        "nightly_batch_status": str(nightly.get("status", "unknown")).upper(),
        "nightly_batch_downloaded": nightly.get("downloaded"),
        "nightly_batch_failed": nightly.get("failed"),
        "pending_media_count": pending.get("pending", 0),
        "pending_media_replayable": pending.get("replayable", 0),
        "quarantined_media_count": pending.get("quarantined", 0),
        "transport_status": transport.get("status", "not_checked"),
        "transport_latency_ms": transport.get("latency_ms", 0),
        "transport_error_class": transport.get("error_class", ""),
        "daily_health_cron_installed": cron_installed,
        "latest_health_report": str(daily_path) if daily_path else None,
        "latest_health_telegram_status": str(
            daily_telegram.get("text_summary", {}).get("sent")
            if daily_telegram.get("text_summary", {}).get("attempted")
            else "not_attempted"
        ) if daily_telegram else "unknown",
        "daily_health_media_replay": daily_media_replay,
        "public_gallery_url": PUBLIC_GALLERY_URL,
        "public_digest_url": PUBLIC_DIGEST_URL,
        "online_gallery_status": online_gallery,
        "online_digest_status": online_digest,
        "pages_guard_available": pages_guard["guard_script"] and pages_guard["guard_doc"],
        "pages_guard_script": pages_guard["guard_script"],
        "pages_guard_doc": pages_guard["guard_doc"],
        "pages_repo_clean": pages_repo,
        "recommended_action": recommended,
    }


# Output ----------------------------------------------------------------------


def _md(status: dict[str, Any]) -> str:
    rc = status["recommended_action"]
    online_g = status.get("online_gallery_status")
    online_d = status.get("online_digest_status")
    online_g_s = "N/A" if online_g is None else str(online_g)
    online_d_s = "N/A" if online_d is None else str(online_d)
    pg = status["pages_guard_available"]
    prc = status["pages_repo_clean"]
    return (
        f"# Artvee Ops Status — {status['date']}\n\n"
        f"**Generated at:** {status['generated_at']}\n"
        f"**Repo head:** {status['repo_head']}\n"
        f"**Release:** {status['release_version']}\n\n"
        f"## Summary\n\n"
        f"| Metric | Value |\n"
        f"|--------|-------|\n"
        f"| Records | {status['records']} (source: {status['records_source']}) |\n"
        f"| Known retired | {status['known_retired']} |\n"
        f"| Blocking unresolved | {status['blocking_unresolved']} |\n"
        f"| Strict integrity | {status['strict_integrity']} |\n"
        f"| Readiness | {status['readiness']} |\n"
        f"| Candidate gallery | {status['candidate_gallery_ready']} |\n"
        f"| Candidate digest | {status['candidate_digest_ready']} |\n"
        f"| Digest history entries | {status['digest_history_entries']} |\n"
        f"| Near-dup clusters | {status['near_dup_clusters']} |\n"
        f"| Nightly batch | {status['nightly_batch_status']} "
        f"(downloaded={status['nightly_batch_downloaded']}, "
        f"failed={status['nightly_batch_failed']}) |\n"
        f"| Online gallery | {online_g_s} |\n"
        f"| Online digest | {online_d_s} |\n"
        f"| Pending MEDIA | {status['pending_media_count']} "
        f"(replayable={status['pending_media_replayable']}, "
        f"quarantined={status['quarantined_media_count']}) |\n"
        f"| OpenClaw transport | {status['transport_status']} "
        f"({status['transport_latency_ms']}ms) |\n"
        f"| Daily health cron installed | {status['daily_health_cron_installed']} |\n"
        f"| Pages guard available | {pg} |\n"
        f"| Pages repo clean | {prc} |\n"
        f"| **Recommended action** | **{rc}** |\n\n"
        f"## Details\n\n"
        f"- Repo head: `{status['repo_head']}`\n"
        f"- Release tag: `{status['release_version']}`\n"
        f"- Repo working tree clean: {status['repo_clean']}\n"
        f"- Latest health report: `{status['latest_health_report']}`\n"
        f"- Latest health telegram status: "
        f"{status['latest_health_telegram_status']}\n"
        f"- Public gallery URL: {status['public_gallery_url']}\n"
        f"- Public digest URL: {status['public_digest_url']}\n"
        f"- Pages guard script: {status['pages_guard_script']}\n"
        f"- Pages guard doc: {status['pages_guard_doc']}\n"
    )


def _write_outputs(status: dict[str, Any]) -> tuple[Path, Path]:
    RUNTIME_OPS.mkdir(parents=True, exist_ok=True)
    json_path = RUNTIME_OPS / f"artvee-ops-status-{status['date']}.json"
    md_path = RUNTIME_OPS / f"artvee-ops-status-{status['date']}.md"
    json_path.write_text(json.dumps(status, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md_path.write_text(_md(status), encoding="utf-8")
    return json_path, md_path


def _send_via_telegram(md_path: Path, args: argparse.Namespace) -> dict[str, Any]:
    """Send the MD report through the same staged-MEDIA / fallback
    pipeline the daily health check uses. Reuses the notifier."""
    if args.no_telegram:
        return {"requested": False, "reason": "--no-telegram"}
    if not args.media:
        return {"requested": False, "reason": "no --media flag; report saved on disk"}
    try:
        from artvee_telegram_notify import send_text, load_chat_id
        from stage_report_for_telegram_media import stage_report
    except ImportError as e:
        return {"requested": True, "status": "error", "error": f"import: {e}"}
    try:
        chat_id = args.telegram_chat_id or load_chat_id()
    except Exception as e:
        return {"requested": True, "status": "skipped", "error": f"chat id resolve: {e}"}
    if not chat_id:
        return {"requested": True, "status": "skipped", "error": "no chat id resolved"}
    try:
        staged = stage_report(md_path, _resolve_openclaw_media_root())
    except Exception as e:
        return {"requested": True, "status": "staging_failed", "error": f"stage: {e}"}
    text = (
        f"✅ Artvee Ops Status ({args.date})\n"
        f"See attached report for full details."
    )
    return send_text(
        text=text, media=str(staged),
        openclaw_bin=args.openclaw_bin, chat_id=chat_id, wait=True,
    )


_DEFAULT_MEDIA_ROOT = Path("~/.openclaw/media").expanduser()


def _resolve_openclaw_media_root() -> Path:
    return _DEFAULT_MEDIA_ROOT


# CLI -------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="artvee_ops_status",
        description="Read-only post-stable ops status aggregator (P8A).",
    )
    p.add_argument("--date", default=_dt.date.today().isoformat(),
                   help="Status date (default: today)")
    p.add_argument("--online", action="store_true",
                   help="Probe public gallery/digest URLs (HEAD)")
    p.add_argument("--include-pages", action="store_true",
                   help="Run a read-only Pages repo clean check")
    p.add_argument("--include-pending-media", action="store_true",
                   help="(Reserved) include pending media scan — always on")
    p.add_argument("--media", action="store_true",
                   help="Send the generated MD report via Telegram + staged MEDIA")
    p.add_argument("--no-telegram", action="store_true",
                   help="Skip Telegram entirely (default if --media not set)")
    p.add_argument("--openclaw-bin", default=None,
                   help="Override OpenClaw binary path (rare)")
    p.add_argument("--telegram-chat-id", default=None,
                   help="Override Telegram chat id (rare)")
    p.add_argument("--simulate-media-failure", action="store_true",
                   help="Force notifier to simulate a MEDIA failure (testing only)")
    p.add_argument("--json", action="store_true",
                   help="Emit the JSON to stdout (for shell wrapper)")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    status = _build_status(args)
    json_path, md_path = _write_outputs(status)
    telegram = _send_via_telegram(md_path, args)
    if args.json:
        print(json.dumps({
            "status": status,
            "outputs": {"json": str(json_path), "md": str(md_path)},
            "telegram": telegram,
        }, indent=2, ensure_ascii=False))
    else:
        print(f"[✓] Ops status written: {json_path} + {md_path}")
        print(f"    records={status['records']} "
              f"retired={status['known_retired']} "
              f"blocking={status['blocking_unresolved']} "
              f"integrity={status['strict_integrity']} "
              f"readiness={status['readiness']} "
              f"pending_media={status['pending_media_count']} "
              f"transport={status['transport_status']} "
              f"action={status['recommended_action']}")
        if telegram.get("requested") or telegram.get("ok") is not None:
            ok = telegram.get("ok")
            mid = telegram.get("message_id") or ""
            err = telegram.get("error") or ""
            t = telegram.get("status", "ok" if ok else "error")
            print(f"    telegram: ok={ok} status={t} message_id={mid}"
                  + (f" error={err}" if err else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
