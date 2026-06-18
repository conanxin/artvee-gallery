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
# PAGES_REPO_DEFAULT is resolved at runtime via _resolve_pages_repo(); do not
# pin it to a hard-coded /home/... path in source. The default is
# Path.home() / "conanxin.github.io" which is portable.
PUBLIC_GALLERY_URL = "https://conanxin.github.io/projects/artvee-gallery-demo/"
PUBLIC_DIGEST_URL = "https://conanxin.github.io/projects/artvee-gallery-digest/"

# Canonical relative paths for the Pages publish guard inside a Pages repo.
PAGES_GUARD_SCRIPT = "scripts/check-project-publish-guard.py"
PAGES_GUARD_DOC = "docs/PAGES_PUBLISH_GUARD.md"

# Default allowlist used for the guard smoke when --guard-allow is not
# supplied. Mirrors docs/PAGES_PUBLISH_GUARD.md and is intentionally a list
# of *project-relative* paths (no absolute paths).
PAGES_GUARD_DEFAULT_ALLOW = (
    "projects/artvee-gallery-demo",
    "projects/artvee-gallery-digest",
    "projects/data.json",
)
PAGES_GUARD_DEFAULT_BASE = "origin/main"

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


def _is_media_replay_cron_installed() -> bool:
    rc, out, _ = _run(["crontab", "-l"])
    if rc != 0:
        return False
    return "P8D media replay cron" in out or "artvee_media_replay_cron.sh" in out


def _read_media_replay_cron_summary() -> dict[str, Any]:
    """Read the latest media-replay cron summary if it exists (P8D).

    Reads the most recent reports/runtime/media-replay/cron-*.json.
    Returns a dict; missing file yields an explicit unknown field.
    """
    import glob
    base = Path(REPO_ROOT) / "reports" / "runtime" / "media-replay"
    if not base.exists():
        return {"available": False, "path": "", "date": "", "outcome": "unknown", "started_at": "", "ended_at": "", "pending_before": None, "transport_status": "", "lock_file": str(base / ".media-replay.lock"), "lock_held": False}
    files = sorted(glob.glob(str(base / "cron-*.json")))
    if not files:
        return {"available": False, "path": "", "date": "", "outcome": "unknown", "started_at": "", "ended_at": "", "pending_before": None, "transport_status": "", "lock_file": str(base / ".media-replay.lock"), "lock_held": False}
    latest = files[-1]
    try:
        data = json.loads(Path(latest).read_text())
    except Exception as e:
        return {"available": False, "path": latest, "date": "", "outcome": "parse_error", "started_at": "", "ended_at": "", "pending_before": None, "transport_status": "", "lock_file": str(base / ".media-replay.lock"), "lock_held": (base / ".media-replay.lock").exists(), "parse_error": str(e)}
    lock_path = Path(data.get("lock_file") or (base / ".media-replay.lock"))
    return {
        "available": True,
        "path": latest,
        "date": data.get("date", ""),
        "outcome": data.get("outcome", "unknown"),
        "started_at": data.get("started_at", ""),
        "ended_at": data.get("ended_at", ""),
        "pending_before": data.get("pending_before"),
        "transport_status": data.get("transport_status", ""),
        "lock_file": str(lock_path),
        "lock_held": lock_path.exists(),
        "limit": data.get("limit"),
        "max_retries": data.get("max_retries"),
        "replay_quarantined": data.get("replay_quarantined", 0),
    }


def _resolve_pages_repo(args: argparse.Namespace) -> dict[str, Any]:
    """Resolve the Pages repo path from CLI / env / default.

    Resolution order (P8A+1):
      1. CLI --pages-repo <path>
      2. env ARTVEE_PAGES_REPO
      3. env PAGES_REPO
      4. Path.home() / "conanxin.github.io"
      5. missing (no value, repo_detected=false)

    `resolved_via` reports the source that *yielded* the returned
    path (or the closest source we attempted). When the user
    passes --pages-repo <bad-path>, the returned `path` is the
    resolved Path and `resolved_via="cli"` — the caller can then
    report that the explicitly-given path was missing.
    """
    candidates = []
    if getattr(args, "pages_repo", None):
        candidates.append(("cli", args.pages_repo))
    for env_name in ("ARTVEE_PAGES_REPO", "PAGES_REPO"):
        val = os.environ.get(env_name, "").strip()
        if val:
            candidates.append((f"env:{env_name}", val))
    # Default — never hard-code /home/... in source; the home lookup is
    # portable.
    candidates.append(("default", str(Path.home() / "conanxin.github.io")))

    for source, raw in candidates:
        p = Path(raw).expanduser()
        if p.is_dir() and (p / ".git").exists():
            return {
                "path": str(p),
                "resolved_via": source,
                "exists": True,
            }
    # No candidate existed as a git checkout. Report the *first*
    # candidate (the explicit override) so the caller can show what
    # was attempted; if there was no override, fall back to the
    # default label.
    if not candidates:
        return {"path": None, "resolved_via": "missing", "exists": False}
    first_source, first_raw = candidates[0]
    return {
        "path": str(Path(first_raw).expanduser()),
        "resolved_via": first_source,
        "exists": False,
    }


def _pages_repo_clean_status(pages_repo: Path) -> str:
    """Read-only check whether the local Pages repo clone is clean.

    Returns one of: "true" | "false" | "unknown" | "skipped".
    Never modifies the Pages repo.
    """
    if not (pages_repo / ".git").exists():
        return "unknown"
    rc, out, _ = _run(["git", "status", "--porcelain"], cwd=pages_repo)
    if rc != 0:
        return "unknown"
    return "true" if not out.strip() else "false"


def _pages_repo_branch_head(pages_repo: Path) -> tuple[str | None, str | None, str | None]:
    """Return (branch, head, origin_main) for a Pages repo. None on error."""
    rc1, b, _ = _run(["git", "branch", "--show-current"], cwd=pages_repo)
    rc2, h, _ = _run(["git", "rev-parse", "--short", "HEAD"], cwd=pages_repo)
    rc3, om, _ = _run(["git", "rev-parse", "--short", "origin/main"], cwd=pages_repo)
    return (
        b.strip() if rc1 == 0 else None,
        h.strip() if rc2 == 0 else None,
        om.strip() if rc3 == 0 else None,
    )


def _pages_guard_files(pages_repo: Path) -> dict[str, bool]:
    """Whether the canonical guard files exist inside a Pages repo.

    P8A+1: the PAGES-GUARD-1 guard lives in the *Pages* repo
    (conanxin.github.io), not in the Artvee repo. Earlier P8A
    logic looked inside the Artvee repo and reported false
    positives. This helper checks the Pages repo only — that is
    where the guard is installed and where it must run.
    """
    return {
        "guard_script": (pages_repo / PAGES_GUARD_SCRIPT).is_file(),
        "guard_doc": (pages_repo / PAGES_GUARD_DOC).is_file(),
    }


def _pages_guard_smoke(pages_repo: Path, allow: tuple[str, ...] = PAGES_GUARD_DEFAULT_ALLOW) -> dict[str, Any]:
    """Run the guard in read-only mode against the Pages repo.

    The guard is invoked with --base origin/main and the supplied
    allowlist (default = the canonical artvee set in
    docs/PAGES_PUBLISH_GUARD.md). It must never modify the Pages
    repo. The function returns a structured record; callers must
    never treat a guard failure as fatal.
    """
    guard = pages_repo / PAGES_GUARD_SCRIPT
    if not guard.is_file():
        return {
            "ran": False,
            "verdict": "skipped",
            "exit_code": None,
            "stdout_tail": "",
            "stderr_tail": "",
            "error": "guard script not found",
        }
    cmd = [sys.executable, str(guard), "--base", PAGES_GUARD_DEFAULT_BASE]
    for entry in allow:
        cmd += ["--allow", entry]
    try:
        proc = subprocess.run(
            cmd, cwd=str(pages_repo), capture_output=True, text=True,
            timeout=20,
        )
        out_tail = "\n".join((proc.stdout or "").splitlines()[-8:])
        err_tail = "\n".join((proc.stderr or "").splitlines()[-4:])
        verdict = "pass" if proc.returncode == 0 else "fail"
        return {
            "ran": True,
            "verdict": verdict,
            "exit_code": proc.returncode,
            "stdout_tail": out_tail,
            "stderr_tail": err_tail,
            "error": None if verdict == "pass" else (err_tail or "non-zero exit"),
        }
    except subprocess.TimeoutExpired:
        return {"ran": True, "verdict": "fail", "exit_code": 124,
                "stdout_tail": "", "stderr_tail": "",
                "error": "timeout after 20s"}
    except Exception as e:
        return {"ran": False, "verdict": "fail", "exit_code": None,
                "stdout_tail": "", "stderr_tail": "",
                "error": f"{type(e).__name__}: {e}"}


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
    cron_installed = _is_cron_installed()
    media_replay_cron_installed = _is_media_replay_cron_installed()
    media_replay_cron_summary = _read_media_replay_cron_summary()

    # --- Pages repo + guard detection (P8A+1) --------------------------
    # Earlier P8A only looked inside the Artvee repo for the guard
    # files, which produced a false pages_guard_available=false even
    # though PAGES-GUARD-1 had already shipped the guard into the
    # conanxin.github.io Pages repo. P8A+1 resolves the Pages repo
    # path first (CLI > env > default), then inspects the Pages repo
    # for the canonical guard files, and optionally runs a read-only
    # smoke. The Pages repo is *never* modified by this script.
    pages_resolution = _resolve_pages_repo(args) if args.include_pages else {
        "path": None, "resolved_via": "skipped", "exists": False,
    }
    pages: dict[str, Any]
    if not args.include_pages:
        pages = {
            "included": False,
            "repo_detected": False,
            "repo_clean": "skipped",
            "branch": None,
            "head": None,
            "origin_main": None,
            "guard_available": False,
            "guard_script_exists": False,
            "guard_doc_exists": False,
            "guard_script": None,
            "guard_doc": None,
            "guard_smoke": "skipped",
            "guard_smoke_detail": {},
            "resolved_via": "skipped",
            "error": None,
        }
    else:
        pages_path = Path(pages_resolution["path"]) if pages_resolution["exists"] else None
        if pages_path is None:
            pages = {
                "included": True,
                "repo_detected": False,
                "repo_clean": "unknown",
                "branch": None,
                "head": None,
                "origin_main": None,
                "guard_available": False,
                "guard_script_exists": False,
                "guard_doc_exists": False,
                "guard_script": None,
                "guard_doc": None,
                "guard_smoke": "skipped",
                "guard_smoke_detail": {},
                "resolved_via": pages_resolution["resolved_via"],
                "error": f"pages repo not found at {pages_resolution['path']}",
            }
        else:
            clean = _pages_repo_clean_status(pages_path)
            branch, head, omain = _pages_repo_branch_head(pages_path)
            files = _pages_guard_files(pages_path)
            guard_ok = bool(files["guard_script"] and files["guard_doc"])
            if guard_ok and not args.no_guard_smoke:
                allow = tuple(args.guard_allow) if args.guard_allow else PAGES_GUARD_DEFAULT_ALLOW
                smoke = _pages_guard_smoke(pages_path, allow=allow)
            elif not guard_ok:
                smoke = {
                    "ran": False, "verdict": "skipped",
                    "exit_code": None, "stdout_tail": "", "stderr_tail": "",
                    "error": "guard files missing",
                }
            else:
                smoke = {
                    "ran": False, "verdict": "skipped",
                    "exit_code": None, "stdout_tail": "", "stderr_tail": "",
                    "error": "smoke skipped via --no-guard-smoke",
                }
            pages = {
                "included": True,
                "repo_detected": True,
                "repo_clean": clean,
                "branch": branch,
                "head": head,
                "origin_main": omain,
                "guard_available": guard_ok,
                "guard_script_exists": files["guard_script"],
                "guard_doc_exists": files["guard_doc"],
                "guard_script": PAGES_GUARD_SCRIPT if files["guard_script"] else None,
                "guard_doc": PAGES_GUARD_DOC if files["guard_doc"] else None,
                "guard_smoke": smoke.get("verdict", "skipped"),
                "guard_smoke_detail": smoke,
                "resolved_via": pages_resolution["resolved_via"],
                "error": smoke.get("error") if smoke.get("verdict") == "fail" else None,
            }

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
        "media_replay_cron_installed": media_replay_cron_installed,
        "media_replay_cron_summary": media_replay_cron_summary,
        "latest_health_report": str(daily_path) if daily_path else None,
        "latest_health_telegram_status": (
            str(
                daily_telegram.get("text_summary", {}).get("sent")
                if daily_telegram.get("text_summary", {}).get("attempted")
                else "not_attempted"
            )
            if daily_telegram
            else "unknown"
        ),
        "daily_health_media_replay": daily_media_replay,
        "public_gallery_url": PUBLIC_GALLERY_URL,
        "public_digest_url": PUBLIC_DIGEST_URL,
        "online_gallery_status": online_gallery,
        "online_digest_status": online_digest,
        # Top-level compatibility fields (preserved from P8A).
        "pages_guard_available": pages["guard_available"],
        "pages_guard_script": bool(pages["guard_script_exists"]),
        "pages_guard_doc": bool(pages["guard_doc_exists"]),
        "pages_repo_clean": pages["repo_clean"],
        # New structured Pages sub-object (P8A+1).
        "pages": pages,
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
        f"| Media replay cron installed | {status['media_replay_cron_installed']} |\n"
        f"| Media replay cron last run | {status['media_replay_cron_summary'].get('date') or '-'} "
        f"({status['media_replay_cron_summary'].get('outcome', 'unknown')}) |\n"
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


def _md_pages_block(pages: dict[str, Any]) -> str:
    """Render the P8A+1 pages sub-object as a small markdown block.

    Never echoes a real Pages repo path. The path is summarised
    via `resolved_via` (`cli` / `env:ARTVEE_PAGES_REPO` /
    `env:PAGES_REPO` / `default` / `missing` / `skipped`).
    """
    if not pages.get("included", False):
        return ""
    rv = pages.get("resolved_via", "skipped")
    if not pages.get("repo_detected", False):
        return (
            "\n## Pages guard (P8A+1)\n\n"
            f"- included: true\n"
            f"- resolved_via: `{rv}`\n"
            f"- repo_detected: false\n"
            f"- error: `{pages.get('error') or 'pages repo not found'}`\n"
        )
    smoke = pages.get("guard_smoke_detail") or {}
    return (
        "\n## Pages guard (P8A+1)\n\n"
        f"- repo_detected: {pages.get('repo_detected')}\n"
        f"- resolved_via: `{rv}`\n"
        f"- branch: `{pages.get('branch')}`\n"
        f"- head: `{pages.get('head')}`\n"
        f"- origin_main: `{pages.get('origin_main')}`\n"
        f"- repo_clean: {pages.get('repo_clean')}\n"
        f"- guard_available: {pages.get('guard_available')}\n"
        f"- guard_script: `{pages.get('guard_script')}`\n"
        f"- guard_doc: `{pages.get('guard_doc')}`\n"
        f"- guard_smoke: {pages.get('guard_smoke')}\n"
        f"- guard_smoke.ran: {smoke.get('ran')}\n"
        f"- guard_smoke.exit_code: {smoke.get('exit_code')}\n"
    )

def _write_outputs(status: dict[str, Any]) -> tuple[Path, Path]:
    RUNTIME_OPS.mkdir(parents=True, exist_ok=True)
    json_path = RUNTIME_OPS / f"artvee-ops-status-{status['date']}.json"
    md_path = RUNTIME_OPS / f"artvee-ops-status-{status['date']}.md"
    json_path.write_text(json.dumps(status, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md_path.write_text(_md(status) + _md_pages_block(status.get("pages") or {}), encoding="utf-8")
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
                   help="Run a read-only Pages repo clean check + guard detect")
    p.add_argument("--pages-repo", default=None,
                   help="Path to the Pages repo (e.g. ~/conanxin.github.io). "
                        "Resolution order: --pages-repo > $ARTVEE_PAGES_REPO > "
                        "$PAGES_REPO > default. The Pages repo is read-only.")
    p.add_argument("--guard-allow", action="append", default=None,
                   help="Extra --allow entry for the guard smoke "
                        "(repeatable). Default is the canonical artvee set "
                        "from docs/PAGES_PUBLISH_GUARD.md.")
    p.add_argument("--no-guard-smoke", action="store_true",
                   help="Skip running the guard's read-only smoke (default: run it).")
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
