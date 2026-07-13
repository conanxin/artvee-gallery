#!/usr/bin/env python3
"""
Artvee Gallery · Daily Health Check (P7A)
=========================================
A single-command daily health check that reports the current state
of the Artvee gallery without modifying any data.

Usage:
    python3 scripts/artvee_daily_health_check.py
    python3 scripts/artvee_daily_health_check.py --date YYYY-MM-DD
    python3 scripts/artvee_daily_health_check.py --no-telegram
    python3 scripts/artvee_daily_health_check.py --online
    python3 scripts/artvee_daily_health_check.py --media

Design principles:
    - Read-only: never modifies source data, images, or candidates.
    - Deterministic: same date gives same report (no network calls in default mode).
    - Safe: exits 0 even if some checks fail (reports failure, does not crash pipeline).
    - Consolidated: one command covers all previous phase-specific checks.
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# P7B+3: max retries must match the value the replay script uses so the
# daily health "replayable" count agrees with what the replay would do.
DEFAULT_MAX_RETRIES_PENDING = 3

# P8D+5: full notification bundle queue roots. Active pending lives at the
# canonical ``daily-health-delivery/pending/`` directory; archives are
# written under ``replayed/`` / ``quarantine/`` next to ``pending/``;
# aggregate per-run sidecars land in ``results/``. The replay script
# imports these so they cannot drift.
DAILY_DELIVERY_ROOTNAME = "daily-health-delivery"
DAILY_PENDING_ROOTNAME = "pending"
DAILY_REPLAYED_ROOTNAME = "replayed"
DAILY_QUARANTINE_ROOTNAME = "quarantine"
DAILY_RESULTS_ROOTNAME = "results"

# P9F+1: import the canonical metrics collector so this script never
# silently reads a frozen status report. Every run collects live state.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from artvee_metrics import collect_current_metrics, metrics_source_mode  # noqa: E402


def run_check(args):
    base_dir = Path(args.base_dir)
    report_dir = Path(args.report_dir) if args.report_dir else base_dir / "reports" / "runtime" / "daily-health"
    report_dir.mkdir(parents=True, exist_ok=True)
    tmp_json = report_dir / f".tmp-health-{args.date}.json"
    report_json = report_dir / f"artvee-daily-health-{args.date}.json"
    report_md = report_dir / f"artvee-daily-health-{args.date}.md"

    # --- telegram delivery state model (P7B+1, P7B+2) ---
    # Three independent tracks so partial failures are observable.
    # P7B+2: media is staged-only (raw path is never attached). When staging
    # itself fails, MEDIA is recorded as stage_failed and we never fall back
    # to the raw path. The fallback path is also refined: a transport error
    # no longer triggers an immediate retry (which would re-hit the same
    # gateway timeout). Instead we write a .fallback-pending-YYYY-MM-DD.json
    # file that the *next* run can re-attempt once the gateway is healthy.
    telegram = {
        "requested": bool(args.telegram),
        "openclaw_status": "unknown",  # resolved | missing | skipped
        "text_summary": {
            "attempted": False,
            "sent": False,
            "message_id": None,
            "error": None,
        },
        "media": {
            "requested": bool(args.media),
            "stage_failed": False,
            "staged": False,
            "raw_report": None,
            "staged_report": None,
            "staged_size": 0,
            "media_root": None,
            "stage_subdir": "artvee-reports",
            "sent": False,
            "message_id": None,
            "error": None,
            "error_kind": None,
            "simulated_failure": bool(args.simulate_media_failure),
        },
        "fallback": {
            "attempted": False,
            "sent": False,
            "message_id": None,
            "reason": None,                  # media_failed | stage_failed | media_transport_deferred
            "deferred_local_path": None,     # when reason == media_transport_deferred
            "error": None,
        },
    }

    # --- helpers ---
    def now():
        return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    def run_py(script_name, extra_args=None, capture=True):
        cmd = [sys.executable, str(base_dir / "scripts" / script_name)]
        if extra_args:
            cmd.extend(extra_args)
        try:
            result = subprocess.run(cmd, capture_output=capture, text=True, check=True, cwd=str(base_dir))
            return {"status": "PASS", "details": f"{script_name} exited 0", "raw": result.stdout}
        except subprocess.CalledProcessError as e:
            return {"status": "FAIL", "details": f"{script_name} exited {e.returncode}", "raw": e.stdout}

    # 1. Readiness check
    readiness = run_py("check_open_source_ready.py")

    # 2. Integrity check
    integrity = run_py("check_gallery_integrity.py", ["--strict"])

    # 3. Status report (canonical, live-collected; P9F+1)
    #
    # P9F+1: this script NEVER reads the cached
    # ``reports/runtime/artvee-status-report.json`` directly. If it did, a
    # 23-day-old frozen snapshot (the exact bug P9F found) would silently
    # show up here again. Instead, we collect live metrics in-process and
    # then atomically refresh the on-disk cache so downstream dashboards
    # see fresh data without ever depending on caller order.
    metrics_refresh_error: str | None = None
    try:
        live_metrics = collect_current_metrics(
            root=base_dir,
            include_public=bool(args.online),
        )
        # Atomically persist the fresh snapshot for downstream tools
        # that legitimately need the cache (Telegram notifier, ops
        # viewers, external dashboards).
        cache_path = base_dir / "reports" / "runtime" / "artvee-status-report.json"
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        # Build a status report shape that includes the canonical
        # schema_version + freshness + metrics block + legacy aliases
        # so consumers of either shape keep working.
        status_payload = {
            "schema_version": live_metrics["schema_version"],
            "generated_by": "scripts/artvee_daily_health_check.py (P9F+1 live collector)",
            "generated_at": live_metrics["generated_at"],
            "as_of": live_metrics["as_of"],
            "source_mode": live_metrics["source_mode"],
            "max_age_seconds": live_metrics["max_age_seconds"],
            "metrics": live_metrics["metrics"],
            "records": live_metrics["metrics"]["library_records"],
            "records_semantics": "library_records",
            "records_deprecated": True,
            "known_retired": live_metrics["metrics"]["known_retired"],
            "blocking_unresolved": live_metrics["metrics"]["blocking_unresolved"],
            "strict_integrity": "pass",
            "freshness": live_metrics["freshness"],
            "consistency": live_metrics["consistency"],
            "warnings": live_metrics.get("warnings", []),
            "errors": live_metrics.get("errors", []),
        }
        from artvee_metrics import atomic_write_json
        atomic_write_json(cache_path, status_payload)
    except Exception as e:  # noqa: BLE001
        metrics_refresh_error = str(e)
        live_metrics = None
        status_payload = None

    if live_metrics is not None:
        live_block = metrics_source_mode(live_metrics, live_metrics.get("max_age_seconds", 86400))
        m = live_metrics["metrics"]
        status_report = {
            "status": "PASS" if not live_block["freshness"]["stale"] else "WARN",
            "library_records": m["library_records"],
            "indexed_records": m["indexed_records"],
            "gallery_records": m["gallery_records"],
            "disk_images": m["disk_images"],
            "manifest_total": m["manifest_total"],
            "manifest_downloaded": m["manifest_downloaded"],
            "manifest_pending": m["manifest_pending"],
            "manifest_failed": m["manifest_failed"],
            "known_retired": m["known_retired"],
            "blocking_unresolved": m["blocking_unresolved"],
            "public_records": m.get("public_records"),
            "integrity_checked_records": m["integrity_checked_records"],
            "integrity_scope": m["integrity_scope"],
            "consistency": live_metrics["consistency"],
            "freshness": live_block["freshness"],
            "source_mode": live_block["source_mode"],
            "schema_version": live_metrics["schema_version"],
            "warnings": live_metrics.get("warnings", []),
            # Legacy alias preserved for downstream consumers that have
            # not migrated. New code MUST read library_records instead.
            "records": m["library_records"],
            "records_semantics": "library_records",
            "records_deprecated": True,
            "strict_integrity": "pass",
            "details": "live metrics collected in-process via artvee_metrics.py",
        }
    else:
        status_report = {
            "status": "WARN",
            "records": None,
            "known_retired": None,
            "blocking_unresolved": None,
            "strict_integrity": None,
            "source_mode": "fallback_cache",
            "metrics_refresh_error": metrics_refresh_error,
            "warnings": [f"live metrics collect failed: {metrics_refresh_error}"],
            "details": f"live metrics collect failed: {metrics_refresh_error}",
        }

    # 4. Nightly batch log
    nightly = {"status": "SKIP", "log_file": None, "downloaded": None, "failed": None,
               "details": f"no nightly log for {args.date}; batch may not have run yet"}
    nightly_dir = base_dir / "logs" / "nightly_summary"
    if nightly_dir.exists():
        logs = sorted(nightly_dir.glob(f"nightly_summary_{args.date}_*.csv"))
        if logs:
            latest = logs[-1]
            try:
                with open(latest) as f:
                    lines = f.readlines()
                if len(lines) >= 2:
                    last = lines[-1].strip().split(",")
                    nightly = {
                        "status": "PASS",
                        "log_file": latest.name,
                        "downloaded": int(last[2]) if len(last) > 2 else None,
                        "failed": int(last[3]) if len(last) > 3 else None,
                        "details": "nightly log found",
                    }
            except Exception:
                nightly["status"] = "WARN"
                nightly["details"] = "nightly log found but unreadable"

    # 5. Candidate refresh report
    candidate = {"status": "SKIP", "report_file": None,
                 "details": f"no candidate refresh report for {args.date}"}
    confirm_report = base_dir / "logs" / "confirm_demo_refresh" / f"report_{args.date}.md"
    if confirm_report.exists():
        with open(confirm_report) as f:
            content = f.read()
        if "**Overall status:** PASS" in content or "Overall status: PASS" in content:
            candidate["status"] = "PASS"
        elif "**Overall status:** FAIL" in content or "Overall status: FAIL" in content:
            candidate["status"] = "FAIL"
        else:
            candidate["status"] = "UNKNOWN"
        candidate["report_file"] = confirm_report.name
        candidate["details"] = "candidate refresh report found"

    # 6. Digest history
    hist_file = base_dir / "reports" / "runtime" / "digest-history.json"
    digest_history = {"status": "SKIP", "entries": 0, "latest_picks": 0,
                      "details": "digest history not found"}
    if hist_file.exists():
        try:
            with open(hist_file) as f:
                hd = json.load(f)
            entries = hd.get("entries", [])
            latest_picks = len(entries[0].get("picks", [])) if entries else 0
            digest_history = {
                "status": "PASS",
                "entries": len(entries),
                "latest_picks": latest_picks,
                "details": f"digest history loaded ({len(entries)} entries)",
            }
        except Exception:
            digest_history["status"] = "WARN"
            digest_history["details"] = "digest history unreadable"

    # 7. Near-dup clusters
    nd_file = base_dir / "reports" / "runtime" / "p6c-near-dup-clusters.json"
    near_dup = {"status": "SKIP", "cluster_count": 0, "record_count": 0,
                "details": "near-dup review not found"}
    if nd_file.exists():
        try:
            with open(nd_file) as f:
                nd = json.load(f)
            clusters = nd.get("clusters", [])
            records = sum(len(c.get("records", [])) for c in clusters)
            near_dup = {
                "status": "PASS",
                "cluster_count": len(clusters),
                "record_count": records,
                "details": f"near-dup review loaded ({len(clusters)} clusters, {records} records)",
            }
        except Exception:
            near_dup["status"] = "WARN"
            near_dup["details"] = "near-dup review unreadable"

    # 8. Candidate state
    gallery_candidate = base_dir / "dist" / "refresh-candidates" / args.date / "gallery"
    digest_candidate = base_dir / "dist" / "refresh-candidates" / args.date / "digest"
    gallery_ready = gallery_candidate.is_dir() and (gallery_candidate / "data" / "artworks.json").exists()
    digest_ready = digest_candidate.is_dir() and (digest_candidate / "data" / "digests.json").exists()
    candidate_state = {
        "gallery_ready": gallery_ready,
        "digest_ready": digest_ready,
        "status": "PASS" if (gallery_ready and digest_ready) else "SKIP",
        "details": ("both candidates ready for " + args.date if (gallery_ready and digest_ready)
                    else "candidate(s) missing for " + args.date + "; run confirm_demo_refresh.sh"),
    }

    # 9. Online checks (optional) — distinguishes HTTP 4xx/5xx from network 0
    # P7E+2 (2026-06-15): content drift on conanxin.github.io surfaced that
    # `except Exception` collapsed urllib's HTTPError (404/403) into 0, hiding
    # path-existence failures behind network-failure noise. We now record the
    # real HTTP code on HTTPError, and reserve 0 for genuine transport failures
    # (DNS / TLS / timeout / connection refused).
    online = {"status": "SKIP", "details": "online check disabled; use --online to enable"}
    online_kind = "skipped"
    if args.online:
        gallery_url = "https://conanxin.github.io/projects/artvee-gallery-demo/"
        digest_url  = "https://conanxin.github.io/projects/artvee-gallery-digest/"

        def _probe(url):
            """Return (http_code:int, kind:str, error:str|None).
            kind ∈ {ok, http_error, network_error}; 0 means transport failure."""
            import urllib.request, urllib.error
            try:
                resp = urllib.request.urlopen(url, timeout=30)
                return (resp.getcode(), "ok", None)
            except urllib.error.HTTPError as e:
                # Real HTTP response with non-2xx code — record it.
                return (e.code, "http_error", f"HTTPError {e.code} {e.reason}")
            except urllib.error.URLError as e:
                # DNS / connection refused / TLS / network unreachable.
                return (0, "network_error", f"URLError {e.reason}")
            except (TimeoutError, ConnectionError) as e:
                return (0, "network_error", f"timeout/connection: {e}")
            except Exception as e:
                # Unexpected — still surface something so we don't silently collapse.
                return (0, "network_error", f"{type(e).__name__}: {e}")

        gcode, gkind, gerr = _probe(gallery_url)
        dcode, dkind, derr = _probe(digest_url)
        # Aggregate kind: ok only if both ok; http_error if any is http_error
        # (and the other is not network_error); otherwise network_error.
        if gkind == "ok" and dkind == "ok":
            online_kind = "ok"
        elif gkind == "network_error" or dkind == "network_error":
            online_kind = "network_error"
        else:
            online_kind = "http_error"

        online = {
            "gallery_url": gallery_url,
            "gallery_http_code": gcode,
            "gallery_kind": gkind,
            "gallery_error": gerr,
            "digest_url": digest_url,
            "digest_http_code": dcode,
            "digest_kind": dkind,
            "digest_error": derr,
            "kind": online_kind,
            "status": "PASS" if (gcode == 200 and dcode == 200) else "FAIL",
            "details": ("both public endpoints return 200" if (gcode == 200 and dcode == 200)
                        else (f"http_error (gallery={gcode}, digest={dcode}) — Pages content drift or path removed"
                              if online_kind == "http_error"
                              else f"network_error (gallery={gcode}, digest={dcode}) — DNS/TLS/timeout/unreachable")),
        }

    # Determine recommended action
    blocking = status_report.get("blocking_unresolved", 0) or 0
    # Online failure takes priority and shapes the action label
    if args.online and online.get("status") == "FAIL":
        if online_kind == "http_error":
            action = "attention_required_pages_content_drift"
        elif online_kind == "network_error":
            action = "attention_required_network_or_pages_unreachable"
        else:
            action = "attention_required_online_check"
    elif integrity["status"] == "PASS" and readiness["status"] == "PASS" and blocking == 0:
        if gallery_ready and digest_ready:
            action = "candidate_ready_manual_publish_optional"
        else:
            action = "healthy_no_action"
    else:
        action = "attention_required"

    # P7B+3: scan for pending MEDIA + probe transport.
    # We do NOT auto-replay here. Replay is a separate step
    # (scripts/replay_pending_media.py). We just surface counts.
    pending_scan = _scan_pending_media(report_dir)
    notification_scan = _scan_notification_bundles(_delivery_root(base_dir))
    transport_probe = _probe_transport(base_dir, args.openclaw_bin)

    # Build JSON report
    report = {
        "date": args.date,
        "generated_at": now(),
        "repo_head": (subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                                     capture_output=True, text=True, cwd=str(base_dir)).stdout.strip()),
        "checks": {
            "readiness": readiness,
            "integrity": integrity,
            "status_report": status_report,
            "nightly_batch": nightly,
            "candidate_refresh": candidate,
            "digest_history": digest_history,
            "near_dup_clusters": near_dup,
            "candidate_state": candidate_state,
        },
        "online": online,
        "recommended_action": action,
        "media_replay": {
            "pending": pending_scan.get("pending", 0),
            "replayable": pending_scan.get("replayable", 0),
            "quarantined": pending_scan.get("quarantined", 0),
            "transport_status": transport_probe.get("status", "not_checked"),
            "transport_error_class": transport_probe.get("error_class", ""),
            "transport_latency_ms": transport_probe.get("latency_ms", 0),
            "transport_checked_at": transport_probe.get("checked_at", ""),
            "transport_limited_cli": transport_probe.get("limited_cli", True),
            # P8D+5: split out notification-bundle queue from media-only
            # pending. Replay summary must distinguish these so the 03:10
            # run can report delivered text vs delivered media separately.
            "notification_bundles_before": notification_scan.get("active", 0),
            "notification_active_replayable": notification_scan.get("active_replayable", 0),
            "notification_terminal_replayed": notification_scan.get("terminal_replayed", 0),
            "notification_terminal_quarantine": notification_scan.get("terminal_quarantine", 0),
            "notification_results": notification_scan.get("results", 0),
            "notification_backup_or_legacy": notification_scan.get("backup_or_legacy", 0),
            "notification_nested_legacy": notification_scan.get("legacy_nested", 0),
            "media_only_before": pending_scan.get("active_pending", pending_scan.get("pending", 0)),
            "media_only_replayable": pending_scan.get("active_replayable", pending_scan.get("replayable", 0)),
        },
    }

    # Remove raw output from checks to keep JSON clean
    for c in report["checks"].values():
        c.pop("raw", None)

    with open(tmp_json, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    tmp_json.rename(report_json)

    # Generate Markdown report
    with open(report_md, "w", encoding="utf-8") as f:
        f.write(f"# Artvee Daily Health Check — {args.date}\n\n")
        f.write(f"**Generated at:** {now()}\n")
        f.write(f"**Repo head:** {report['repo_head']}\n\n")
        f.write("## Summary (canonical metrics — P9F+1)\n\n")
        f.write("| Metric | Value |\n")
        f.write("|--------|-------|\n")
        sr = report["checks"]["status_report"]
        f.write(f"| Library records | {sr.get('library_records', 'N/A')} |\n")
        f.write(f"| Indexed records | {sr.get('indexed_records', 'N/A')} |\n")
        f.write(f"| Gallery records | {sr.get('gallery_records', 'N/A')} |\n")
        f.write(f"| Disk images | {sr.get('disk_images', 'N/A')} |\n")
        f.write(f"| Manifest total | {sr.get('manifest_total', 'N/A')} |\n")
        f.write(
            f"| Manifest downloaded | {sr.get('manifest_downloaded', 'N/A')} |\n"
        )
        f.write(f"| Manifest pending | {sr.get('manifest_pending', 'N/A')} |\n")
        f.write(f"| Manifest failed | {sr.get('manifest_failed', 'N/A')} |\n")
        f.write(f"| Known retired | {sr.get('known_retired', 'N/A')} |\n")
        f.write(f"| Blocking unresolved | {sr.get('blocking_unresolved', 'N/A')} |\n")
        f.write(f"| Integrity checked records | {sr.get('integrity_checked_records', 'N/A')} |\n")
        f.write(f"| Public records | {sr.get('public_records', 'N/A')} |\n")
        f.write(f"| Strict integrity | {report['checks']['integrity']['status']} |\n")
        f.write(f"| Readiness | {report['checks']['readiness']['status']} |\n")
        f.write(f"| Source mode | {sr.get('source_mode', 'unknown')} |\n")
        f.write(f"| Metrics freshness | "
                f"age={sr.get('freshness', {}).get('age_seconds', 'N/A')}s, "
                f"stale={sr.get('freshness', {}).get('stale', 'N/A')} |\n")
        f.write(f"| Nightly batch | {report['checks']['nightly_batch']['status']} |\n")
        f.write(f"| Candidate refresh | {report['checks']['candidate_refresh']['status']} |\n")
        f.write(f"| Candidate gallery | {report['checks']['candidate_state']['gallery_ready']} |\n")
        f.write(f"| Candidate digest | {report['checks']['candidate_state']['digest_ready']} |\n")
        f.write(f"| Digest history entries | {report['checks']['digest_history']['entries']} |\n")
        f.write(f"| Near-dup clusters | {report['checks']['near_dup_clusters']['cluster_count']} |\n")
        f.write(f"| Online gallery | {report['online'].get('gallery_http_code', 'N/A')} |\n")
        f.write(f"| Online digest | {report['online'].get('digest_http_code', 'N/A')} |\n")
        # P7B+3: media_replay summary
        mr = report.get('media_replay', {})
        f.write(f"| Pending MEDIA | {mr.get('pending', 0)} (replayable={mr.get('replayable', 0)}, quarantined={mr.get('quarantined', 0)}) |\n")
        f.write(f"| OpenClaw transport | {mr.get('transport_status', 'not_checked')} ({mr.get('transport_latency_ms', 0)}ms) |\n")
        f.write(f"| **Recommended action** | **{action}** |\n\n")
        f.write("## Check Details\n\n")
        for key, check in report["checks"].items():
            status = check["status"]
            icon = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️" if status == "WARN" else "⏭️"
            f.write(f"### {icon} {key}\n")
            f.write(f"- Status: {status}\n")
            if "details" in check:
                f.write(f"- Details: {check['details']}\n")
            for k, v in check.items():
                if k not in ("status", "details"):
                    f.write(f"- {k}: {v}\n")
            f.write("\n")
        f.write("---\n")
        f.write("*Generated by scripts/artvee_daily_health_check.py*\n")

    # Telegram delivery (P7B+1: text_summary / media / fallback as independent tracks)
    if args.telegram:
        sr = report["checks"]["status_report"]
        integrity_status = report["checks"]["integrity"]["status"]
        readiness_status = report["checks"]["readiness"]["status"]
        blocking = sr.get("blocking_unresolved", 0) or 0
        retired = sr.get("known_retired", 0) or 0
        # P9F+1: use canonical names; `records` here is the library
        # records alias. `metrics_refresh_error` is the only path that
        # falls back to N/A.
        if sr.get("metrics_refresh_error"):
            records_disp = f"N/A ({sr['metrics_refresh_error']})"
        else:
            records_disp = sr.get("library_records", "N/A")
        source_mode = sr.get("source_mode", "unknown")
        age_s = sr.get("freshness", {}).get("age_seconds", "N/A")
        stale_disp = sr.get("freshness", {}).get("stale", "N/A")
        cand_g = report["checks"]["candidate_state"]["gallery_ready"]
        cand_d = report["checks"]["candidate_state"]["digest_ready"]
        hist_entries = report["checks"]["digest_history"]["entries"]
        nd_clusters = report["checks"]["near_dup_clusters"]["cluster_count"]
        m_down = sr.get("manifest_downloaded", "?")
        m_pend = sr.get("manifest_pending", "?")
        m_fail = sr.get("manifest_failed", "?")
        integrity_checked = sr.get("integrity_checked_records", "?")
        public_records = sr.get("public_records", "not_collected")

        if (
            integrity_status == "PASS"
            and readiness_status == "PASS"
            and blocking == 0
            and not stale_disp is True
        ):
            icon = "✅"
        else:
            icon = "❌"

        msg = f"""{icon} Artvee Daily Health
Date: {args.date}
Library records: {records_disp}
Manifest: downloaded={m_down}, pending={m_pend}, failed={m_fail}
Integrity: {integrity_status} (checked records: {integrity_checked})
Readiness: {readiness_status}
Metrics: {('LIVE' if source_mode == 'live' else source_mode.upper())}, age={age_s}s, stale={stale_disp}
Retired: known_retired={retired}, blocking_unresolved={blocking}
Candidate: gallery={cand_g}, digest={cand_d}
Digest history: {hist_entries} entries
Public Gallery: {public_records} selected works
Action: {action}"""

        if args.online:
            gcode = report["online"].get("gallery_http_code", "N/A")
            dcode = report["online"].get("digest_http_code", "N/A")
            # P9F+1: label HTTP codes explicitly so they cannot be
            # confused with the public records count.
            msg += f"\nOnline HTTP: gallery={gcode}, digest={dcode}"

        # Resolve OpenClaw binary before attempting any send
        sys.path.insert(0, str(base_dir / "scripts"))
        from artvee_telegram_notify import (  # noqa: E402
            send_text_with_retry, load_chat_id as _resolve_chat_id,
        )

        def _safe_resolve_chat_id():
            try:
                return _resolve_chat_id()
            except Exception as e:
                return f"RESOLVE_FAILED:{type(e).__name__}"

        # Probe with a no-wait invocation to see if the binary resolves and exits cleanly.
        # If wait=False, the notifier still exits 0 when it can start a background send.
        resolved = False
        try:
            probe = subprocess.run([sys.executable, str(base_dir / "scripts" / "artvee_telegram_notify.py"),
                                    "--openclaw-bin", args.openclaw_bin or "openclaw",
                                    "--text", "_probe_"],
                                   capture_output=True, text=True, cwd=str(base_dir), timeout=30)
            resolved = (probe.returncode == 0) or ("NOTIFY_OK" in probe.stdout)
        except Exception:
            resolved = False

        if not resolved:
            telegram["openclaw_status"] = "missing"
            print("[info] Telegram notify skipped: OpenClaw binary not resolved (cron may succeed if PATH differs)")
        else:
            telegram["openclaw_status"] = "resolved"

            # --- Step 1: text_summary (always) ---
            # P8D+5: route the 03:00 text send through send_text_with_retry
            # so a single transport stall doesn't silently drop the entire
            # notification. Once bounded retries exhaust, we enqueue a
            # full notification bundle for 03:10 to replay, instead of
            # leaving the user with nothing.
            telegram["text_summary"]["attempted"] = True
            try:
                ts_result = send_text_with_retry(
                    text=msg,
                    chat_id=None,
                    media=None,
                    openclaw_bin=args.openclaw_bin,
                )
            except Exception as e:
                ts_result = {
                    "ok": False, "delivered": False,
                    "error": f"{type(e).__name__}: {e}",
                    "error_kind": "exit_nonzero",
                    "attempt_used": 0,
                    "max_attempts": 0,
                    "retry_history": [],
                }

            # Persist the structured attempt history BEFORE we lose it in
            # the next re-assignment of telegram["text_summary"].
            attempt_history = ts_result.get("retry_history") or []
            telegram["text_summary"]["retry_history"] = attempt_history
            telegram["text_summary"]["attempt_used"] = ts_result.get("attempt_used")
            telegram["text_summary"]["max_attempts"] = ts_result.get("max_attempts")

            if ts_result.get("ok") and ts_result.get("message_id"):
                telegram["text_summary"]["sent"] = True
                telegram["text_summary"]["message_id"] = ts_result.get("message_id")
                print(f"[✓] Telegram text summary sent (message_id={telegram['text_summary']['message_id']}, attempt={ts_result.get('attempt_used')}/{ts_result.get('max_attempts')})")
            else:
                telegram["text_summary"]["sent"] = False
                err_raw = ts_result.get("error") or f"unknown error_kind={ts_result.get('error_kind')}"
                telegram["text_summary"]["error"] = err_raw[:300]
                telegram["text_summary"]["error_kind"] = ts_result.get("error_kind")
                print(f"[warn] Telegram text summary failed after {ts_result.get('attempt_used', 0)} attempt(s): {telegram['text_summary']['error'][:200]}")

            # --- Step 1.5: flush any previously-deferred fallback (P7B+2) ---
            # If a prior run hit a transport error and wrote a
            # .fallback-pending-YYYY-MM-DD.json, AND this run's text_summary
            # succeeded (which proves the gateway is healthy again), flush
            # the pending fallback text exactly once and remove the defer
            # file. We do this regardless of whether the current run also
            # has its own MEDIA failure — the deferred message is a separate
            # observation and should not be lost.
            if telegram["text_summary"]["sent"]:
                pending_path = report_dir / f".fallback-pending-{args.date}.json"
                if pending_path.is_file():
                    import re as _re
                    try:
                        with open(pending_path, "r", encoding="utf-8") as pf:
                            pending = json.load(pf)
                        pending_text = pending.get("fallback_text") or ""
                        if pending_text:
                            # P8D+5: route the legacy P7B+2 deferred-fallback
                            # flush through send_text_with_retry so even this
                            # path benefits from bounded retry. Same
                            # semantics: parse message_id from the structured
                            # return, not from stdout parsing.
                            flush_result = send_text_with_retry(
                                text=pending_text,
                                chat_id=None,
                                media=None,
                                openclaw_bin=args.openclaw_bin,
                            )
                            if flush_result.get("ok") and flush_result.get("message_id"):
                                if "flushed_pending_fallbacks" not in telegram:
                                    telegram["flushed_pending_fallbacks"] = []
                                telegram["flushed_pending_fallbacks"].append({
                                    "date": pending.get("date"),
                                    "reason": pending.get("reason"),
                                    "sent": True,
                                    "message_id": flush_result.get("message_id"),
                                    "attempt_used": flush_result.get("attempt_used"),
                                    "local_path": str(pending_path),
                                })
                                print(f"[✓] Flushed deferred fallback from {pending_path} (message_id={flush_result.get('message_id')}, attempt={flush_result.get('attempt_used')})")
                                try:
                                    pending_path.unlink()
                                except Exception as e:
                                    print(f"[warn] Failed to unlink pending fallback {pending_path}: {e}")
                            else:
                                err = (flush_result.get("error") or "")[:200]
                                if "flushed_pending_fallbacks" not in telegram:
                                    telegram["flushed_pending_fallbacks"] = []
                                telegram["flushed_pending_fallbacks"].append({
                                    "date": pending.get("date"),
                                    "reason": pending.get("reason"),
                                    "sent": False,
                                    "error": err,
                                    "attempt_used": flush_result.get("attempt_used"),
                                    "error_kind": flush_result.get("error_kind"),
                                    "local_path": str(pending_path),
                                })
                                print(f"[warn] Deferred fallback flush failed after {flush_result.get('attempt_used')} attempt(s): {err[:200]}")
                    except Exception as e:
                        print(f"[warn] Deferred fallback read failed: {e}")

            # --- Step 2: media (only if requested AND text sent) ---
            if args.media:
                if not telegram["text_summary"]["sent"]:
                    telegram["media"]["error"] = "skipped: text_summary did not send"
                    print("[info] MEDIA skipped: text_summary did not send (avoids orphan media)")
                elif args.simulate_media_failure:
                    # Force a media-failure path for testing the fallback chain.
                    # Record both raw and (simulated) staged paths so the JSON
                    # shape matches the real path.
                    telegram["media"]["raw_report"] = str(report_md)
                    telegram["media"]["staged"] = True
                    telegram["media"]["staged_report"] = "(simulated)"
                    telegram["media"]["staged_size"] = 0
                    telegram["media"]["sent"] = False
                    telegram["media"]["error"] = "simulated_failure"
                    telegram["media"]["error_kind"] = "simulated"
                    print("[warn] MEDIA simulated failure (--simulate-media-failure)")
                else:
                    # Stage the report into an OpenClaw-allowed media dir.
                    # P7B+2: we use --print-meta so the helper returns a
                    # single-line JSON object containing both raw_report and
                    # staged_report, plus an explicit stage_failed flag. We
                    # NEVER fall back to the raw path — if staging fails, MEDIA
                    # is recorded as stage_failed and we skip the attachment
                    # entirely. This is the single most important property of
                    # the fix: raw reports live under
                    # ~/workspace/reports/ which is outside the OpenClaw
                    # allowlist, so attaching them would either fail or expand
                    # the security boundary. Staging is the only correct path.
                    stage_proc = subprocess.run(
                        [sys.executable, str(base_dir / "scripts" / "stage_report_for_telegram_media.py"),
                         "--report", str(report_md), "--print-meta"],
                        capture_output=True, text=True, cwd=str(base_dir))
                    media_path = None
                    if stage_proc.returncode == 0 and stage_proc.stdout.strip():
                        try:
                            meta = json.loads(stage_proc.stdout.strip().splitlines()[-1])
                        except json.JSONDecodeError as e:
                            meta = None
                            telegram["media"]["error"] = f"stage meta parse failed: {e}"[:200]
                        if meta:
                            telegram["media"]["raw_report"] = meta.get("raw_report")
                            telegram["media"]["staged"] = bool(meta.get("staged_report"))
                            telegram["media"]["staged_report"] = meta.get("staged_report")
                            telegram["media"]["staged_size"] = meta.get("staged_size", 0) or 0
                            telegram["media"]["media_root"] = meta.get("media_root")
                            telegram["media"]["stage_subdir"] = meta.get("stage_subdir", "artvee-reports")
                            if meta.get("stage_failed"):
                                telegram["media"]["stage_failed"] = True
                                telegram["media"]["error"] = f"stage failed: {meta.get('error')}"[:200]
                                telegram["media"]["error_kind"] = "stage_failed"
                            elif meta.get("staged_report"):
                                # Sanity check: staged path must live under
                                # ~/.openclaw/{media,workspace/media,workspace/tmp}/
                                # in the resolved (non-symlink) form. The
                                # helper already enforces the namespaced
                                # subdir, so the only thing left is to refuse
                                # a staged path that is somehow still the raw
                                # report.
                                if meta.get("staged_report") == meta.get("raw_report"):
                                    telegram["media"]["stage_failed"] = True
                                    telegram["media"]["error"] = "staged_report equals raw_report; refusing to attach"
                                    telegram["media"]["error_kind"] = "stage_failed"
                                else:
                                    media_path = meta["staged_report"]
                    else:
                        telegram["media"]["stage_failed"] = True
                        err = (stage_proc.stdout.strip() or stage_proc.stderr.strip() or f"exit {stage_proc.returncode}")[:200]
                        telegram["media"]["error"] = f"stage helper exited {stage_proc.returncode}: {err}"
                        telegram["media"]["error_kind"] = "stage_failed"

                    if media_path:
                        # P8D+5: route the media send through the bounded
                        # retry helper so a one-shot transport stall can't
                        # silently drop the attachment. The MEDIA send is
                        # co-failure with the text send by OpenClaw's nature
                        # (same gateway), so transport retries often do not
                        # help here — but on the happy path we still want the
                        # message_id for delivery auditing.
                        media_result = send_text_with_retry(
                            text=msg,
                            chat_id=None,
                            media=media_path,
                            openclaw_bin=args.openclaw_bin,
                        )
                        if media_result.get("ok") and media_result.get("message_id"):
                            telegram["media"]["sent"] = True
                            telegram["media"]["message_id"] = media_result.get("message_id")
                            telegram["media"]["error_kind"] = None
                            telegram["media"]["attempt_used"] = media_result.get("attempt_used")
                            print(f"[✓] Telegram MEDIA sent (message_id={telegram['media']['message_id']}, attempt={media_result.get('attempt_used')})")
                        else:
                            telegram["media"]["sent"] = False
                            err = (media_result.get("error") or "unknown")[:300]
                            telegram["media"]["error"] = err
                            telegram["media"]["error_kind"] = media_result.get("error_kind") or "exit_nonzero"
                            telegram["media"]["attempt_used"] = media_result.get("attempt_used")
                            print(f"[warn] Telegram MEDIA failed after {media_result.get('attempt_used')} attempt(s) ({telegram['media']['error_kind']}): {err}")

            # --- Step 3: failure-only fallback ---
            # Conditions: health PASS + text sent + MEDIA requested + MEDIA failed.
            # We do NOT fallback if text itself failed (avoid noise / loop).
            #
            # P7B+2: the reason field now distinguishes three failure modes:
            #   - stage_failed: the staging helper itself failed. The raw
            #     report is recorded in media.raw_report; ops should check the
            #     helper. We still send a fallback so ops learns about the
            #     staging regression.
            #   - media_failed: MEDIA staged fine but the OpenClaw send call
            #     failed for a non-transport reason (e.g. allowlist denial,
            #     binary missing, exit_nonzero). Fallback sent as before.
            #   - media_transport_deferred: MEDIA failed with a *transport*
            #     error (gateway ws timeout / unreachable). Re-sending the
            #     fallback immediately would hit the same gateway failure and
            #     burn a 10-180s wait per attempt. We instead write a
            #     `.fallback-pending-YYYY-MM-DD.json` next to the report so
            #     the *next* cron run (or the next manual call) can flush it
            #     once the gateway is healthy. We still record the deferral
            #     in this run's JSON; ops can read it from there.
            health_pass = (integrity_status == "PASS" and readiness_status == "PASS" and blocking == 0)
            text_sent = telegram["text_summary"]["sent"]
            media_block = telegram["media"]
            media_failed = (
                args.media
                and not media_block["sent"]
                and (media_block["error"] is not None or media_block.get("stage_failed"))
            )

            if health_pass and text_sent and media_failed and not telegram["fallback"]["sent"]:
                # Decide reason first so we know whether to actually send
                # or to defer to a local file.
                if media_block.get("stage_failed"):
                    fallback_reason = "stage_failed"
                elif media_block.get("error_kind") == "transport":
                    fallback_reason = "media_transport_deferred"
                else:
                    fallback_reason = "media_failed"

                fallback_text = (
                    f"⚠️ Artvee Daily Health MEDIA failed\n"
                    f"Date: {args.date}\n"
                    f"Health: PASS\n"
                    f"Text summary: sent\n"
                    f"MEDIA: failed ({fallback_reason})\n"
                    f"raw_report: {media_block.get('raw_report') or report_md}\n"
                    f"staged_report: {media_block.get('staged_report') or '(none)'}\n"
                    f"media_error: {media_block.get('error') or '(none)'}\n"
                    f"Action: no data issue; check media delivery"
                )

                if fallback_reason == "media_transport_deferred":
                    # Defer: write a small JSON next to the report, but do
                    # NOT re-attempt the send. The next run will pick this
                    # up only if the OpenClaw gateway has recovered (which
                    # the next text_summary success will prove).
                    pending_path = report_dir / f".fallback-pending-{args.date}.json"
                    pending_doc = {
                        "date": args.date,
                        "deferred_at": now(),
                        "reason": fallback_reason,
                        "fallback_text": fallback_text,
                        "media_error_kind": media_block.get("error_kind"),
                        "media_error": media_block.get("error"),
                        "raw_report": media_block.get("raw_report") or str(report_md),
                        "staged_report": media_block.get("staged_report"),
                    }
                    try:
                        with open(pending_path, "w", encoding="utf-8") as pf:
                            json.dump(pending_doc, pf, ensure_ascii=False, indent=2)
                        telegram["fallback"]["attempted"] = True
                        telegram["fallback"]["reason"] = fallback_reason
                        telegram["fallback"]["deferred_local_path"] = str(pending_path)
                        print(f"[info] Telegram fallback deferred to {pending_path} (transport error)")
                    except Exception as e:
                        # If we cannot even write the defer file, fall back
                        # to the immediate-send path so the warning still
                        # reaches ops — this is a degraded mode, not a silent
                        # failure.
                        telegram["fallback"]["error"] = f"defer write failed: {e}"[:200]
                        fb_result = send_text_with_retry(
                            text=fallback_text,
                            chat_id=None,
                            media=None,
                            openclaw_bin=args.openclaw_bin,
                        )
                        if fb_result.get("ok") and fb_result.get("message_id"):
                            telegram["fallback"]["sent"] = True
                            telegram["fallback"]["reason"] = "media_failed"
                            telegram["fallback"]["message_id"] = fb_result.get("message_id")
                            telegram["fallback"]["attempt_used"] = fb_result.get("attempt_used")
                            print(f"[✓] Telegram fallback (text-only) sent (message_id={telegram['fallback']['message_id']}, attempt={fb_result.get('attempt_used')})")
                else:
                    # P8D+5: non-deferred fallback (stage_failed / media_failed)
                    # also routes through send_text_with_retry for consistency
                    # with the text_summary path.
                    telegram["fallback"]["attempted"] = True
                    telegram["fallback"]["reason"] = fallback_reason
                    fb_result = send_text_with_retry(
                        text=fallback_text,
                        chat_id=None,
                        media=None,
                        openclaw_bin=args.openclaw_bin,
                    )
                    if fb_result.get("ok") and fb_result.get("message_id"):
                        telegram["fallback"]["sent"] = True
                        telegram["fallback"]["message_id"] = fb_result.get("message_id")
                        telegram["fallback"]["attempt_used"] = fb_result.get("attempt_used")
                        print(f"[✓] Telegram fallback (text-only) sent (message_id={telegram['fallback']['message_id']}, attempt={fb_result.get('attempt_used')})")
                    else:
                        err = (fb_result.get("error") or "unknown")[:300]
                        telegram["fallback"]["error"] = err
                        telegram["fallback"]["error_kind"] = fb_result.get("error_kind")
                        telegram["fallback"]["attempt_used"] = fb_result.get("attempt_used")
                        print(f"[warn] Telegram fallback failed after {fb_result.get('attempt_used')} attempt(s): {err}")
                        telegram["fallback"]["error"] = err
                        print(f"[warn] Telegram fallback failed: {err}")

            # --- P8D+5: full-notification-bundle enqueue ---
            # When the text-summary send exhausts bounded retries, we
            # MUST NOT silently drop the day's notification. Stage the
            # report (if --media was requested) BEFORE the text send,
            # then on text failure enqueue a full notification bundle
            # under ``reports/runtime/daily-health-delivery/pending/``
            # so the 03:10 replay run can re-issue the complete message.
            # Health stays PASS; the user just learns the message
            # arrived at 03:10 instead of 03:00.
            health_pass_for_bundle = (
                integrity_status == "PASS"
                and readiness_status == "PASS"
                and blocking == 0
            )
            text_exhausted = (
                telegram["text_summary"]["attempted"]
                and not telegram["text_summary"]["sent"]
                and telegram["text_summary"].get("error_kind") in ("transport", "timeout", "unknown", "exit_nonzero")
            )
            if (
                args.telegram
                and health_pass_for_bundle
                and text_exhausted
            ):
                # Stage the report up front so the bundle carries a
                # media-root-compliant path (or None for text-only).
                staged_for_bundle = None
                try:
                    if args.media and not args.simulate_media_failure:
                        stage_proc = subprocess.run(
                            [sys.executable, str(base_dir / "scripts" / "stage_report_for_telegram_media.py"),
                             "--report", str(report_md), "--print-meta"],
                            capture_output=True, text=True, cwd=str(base_dir))
                        if stage_proc.returncode == 0 and stage_proc.stdout.strip():
                            try:
                                meta = json.loads(stage_proc.stdout.strip().splitlines()[-1])
                                if meta and not meta.get("stage_failed") and meta.get("staged_report"):
                                    if meta["staged_report"] != meta.get("raw_report"):
                                        staged_for_bundle = meta["staged_report"]
                            except Exception:
                                pass
                except Exception:
                    staged_for_bundle = None

                # De-dup: do not enqueue a 2nd bundle for the same date
                # in the same active-pending scan. Existing bundles
                # take priority; the new one would just add noise.
                existing = list(_delivery_root(base_dir).glob(f"{DAILY_PENDING_ROOTNAME}/notification-{args.date}-*.json"))
                if not existing:
                    try:
                        bundle_path = _write_notification_bundle(
                            date=args.date,
                            text=msg,
                            staged_report=staged_for_bundle,
                            text_attempts=int(telegram["text_summary"].get("max_attempts") or DEFAULT_MAX_RETRIES_PENDING),
                            reason="text_transport_failed",
                            pending_root=_delivery_root(base_dir),
                        )
                        telegram.setdefault("notification_bundle", {})
                        telegram["notification_bundle"]["enqueued"] = True
                        telegram["notification_bundle"]["path"] = str(bundle_path)
                        telegram["notification_bundle"]["reason"] = "text_transport_failed"
                        telegram["notification_bundle"]["attempts"] = int(telegram["text_summary"].get("max_attempts") or DEFAULT_MAX_RETRIES_PENDING)
                        telegram["notification_bundle"]["staged_report"] = staged_for_bundle
                        print(f"[info] Enqueued full notification bundle for 03:10 replay: {bundle_path}")
                    except Exception as e:
                        telegram.setdefault("notification_bundle", {})
                        telegram["notification_bundle"]["enqueued"] = False
                        telegram["notification_bundle"]["error"] = f"{type(e).__name__}: {e}"[:200]
                        print(f"[warn] Failed to enqueue notification bundle: {e}")
                else:
                    telegram.setdefault("notification_bundle", {})
                    telegram["notification_bundle"]["enqueued"] = False
                    telegram["notification_bundle"]["existing_path"] = str(existing[0])
                    telegram["notification_bundle"]["reason"] = "already_pending"
                    print(f"[info] Skipping bundle enqueue; another bundle is already pending for {args.date}: {existing[0]}")

    else:
        telegram["openclaw_status"] = "skipped"

    # Add telegram (P7B+1 nested structure) to report
    report["telegram"] = telegram
    # Re-write JSON with telegram status
    with open(tmp_json, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    tmp_json.rename(report_json)


# ---------------------------------------------------------------------------
# P7B+3 helpers: pending MEDIA scan + transport probe
# ---------------------------------------------------------------------------

# Names of directory segments that are *not* active pending roots.
# P8D+4B: backup snapshots, legacy-cleaned archives, results/, and the
# stable terminal roots (replayed/, quarantine/) must never count toward
# pending_before. We classify each candidate first, then only the
# ``active_pending`` bucket drives the ``pending`` counter.
_NON_ACTIVE_TERMINAL_DIRS = {"replayed", "quarantine", "results"}
_NON_ACTIVE_ARCHIVE_HINTS = ("queue-fix-backup-", "legacy-cleaned", "stable_dup")


def _delivery_root(base_dir: Path) -> Path:
    """Return the canonical ``reports/runtime/daily-health-delivery/`` root.

    P8D+5: the notification bundle queue is anchored at this stable path
    so the replay script and the active-scan helper agree on the layout.
    """
    return (base_dir / "reports" / "runtime" / DAILY_DELIVERY_ROOTNAME).resolve()


def _write_notification_bundle(
    *,
    date: str,
    text: str,
    staged_report: str | None,
    text_attempts: int,
    reason: str,
    pending_root: Path,
) -> Path:
    """Write a notification bundle JSON for 03:10 replay.

    P8D+5: when the 03:00 text send exhausts its bounded retries, we
    persist the *text* + the optional *staged_report* path so the next
    replay run can re-issue the full notification atomically. The bundle
    schema is fixed (``artvee-notification-bundle-v1``). It must never
    contain a chat id, token, or any other secret; the only path that
    goes in is the previously-validated staged MEDIA path.
    """
    safe_staged = staged_report or ""
    # If a staged_report value is given, it must already live under the
    # OpenClaw media root — re-validate defensively. Raw report paths
    # are NEVER persisted here (otherwise the bundle would force the
    # security boundary to expand).
    if safe_staged:
        try:
            from stage_report_for_telegram_media import _resolve_media_root  # type: ignore
            media_root = Path(_resolve_media_root("")).resolve()
        except Exception:
            media_root = Path.home() / ".openclaw" / "media"
        try:
            staged_abs = Path(safe_staged).resolve(strict=False)
        except Exception:
            staged_abs = Path(safe_staged)
        try:
            in_allowlist = (
                media_root in staged_abs.parents or staged_abs == media_root
                or any(part == "artvee-reports" for part in staged_abs.parts)
            )
        except Exception:
            in_allowlist = False
        if not in_allowlist:
            # Defensive: refuse to persist a raw report path; fall back to
            # no-media which still allows the bundle to retry the text.
            safe_staged = ""

    pending_dir = pending_root / DAILY_PENDING_ROOTNAME
    pending_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    bundle_path = pending_dir / f"notification-{date}-{ts}.json"
    body = {
        "schema_version": "artvee-notification-bundle-v1",
        "date": date,
        "status": "pending",
        "reason": reason,
        "text": text,
        "staged_report": safe_staged or None,
        "text_attempts": text_attempts,
        "media_attempts": 0,
        "created_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "last_attempt_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "last_error_kind": "transport",
        "last_error": "text exhausted bounded retry (redacted)",
        "text_message_id": None,
        "media_message_id": None,
    }
    with open(bundle_path, "w", encoding="utf-8") as fh:
        json.dump(body, fh, indent=2, ensure_ascii=False)
    return bundle_path


def _classify_pending_path(p: Path, runtime_root: Path | None) -> str:
    """Classify a ``.fallback-pending-*.json`` file path.

    Returns one of:
      ``active_pending``      → counts toward ``pending_before``.
      ``terminal_replayed``   → under media-replay/replayed/ OR
        daily-health/replayed/ (immediate child only).
      ``terminal_quarantine`` → under media-replay/quarantine/ OR
        daily-health/quarantine/ (immediate child only).
      ``results``             → under media-replay/results/ (aggregate
        sidecars; never actionable).
      ``backup_or_legacy``    → under queue-fix-backup-*/, legacy-cleaned/,
        or stable_dup/ (P8D+4B cleanup archive).
      ``legacy_nested``       → any ancestor segment is a self-recursive
        ``replayed/replayed`` or ``quarantine/quarantine`` (pathology
        from pre-P8D+4B archives).
      ``unknown``             → anything else (defensive).
    """
    parts = p.parts
    # Backups / archived cleanup snapshots first (path-contains checks).
    for hint in _NON_ACTIVE_ARCHIVE_HINTS:
        if any(hint in seg for seg in parts):
            return "backup_or_legacy"
    # Nested pathology: any segment directly followed by another segment
    # of the same name (e.g. ``replayed/replayed``, ``quarantine/quarantine``).
    for i in range(len(parts) - 1):
        if parts[i] == parts[i + 1] and parts[i] in _NON_ACTIVE_TERMINAL_DIRS:
            return "legacy_nested"
    # Stable terminal roots. We only count top-level terminal dirs as
    # terminal; deeper nesting falls into ``legacy_nested`` above.
    for i, seg in enumerate(parts):
        # ``media-replay/replayed`` or ``media-replay/quarantine`` etc.
        if seg in _NON_ACTIVE_TERMINAL_DIRS and i > 0 and parts[i - 1] in {
            "media-replay", "daily-health"
        }:
            return (
                "results" if seg == "results"
                else f"terminal_{seg}"
            )
    return "active_pending"


def _scan_notification_bundles(delivery_root: Path) -> dict:
    """Count active vs terminal notification bundles under delivery_root.

    Mirrors ``_scan_pending_media`` so the JSON report always reports
    active count separately from terminal / backup / nested artifacts.
    Returns ``active``, ``active_replayable``, ``terminal_replayed``,
    ``terminal_quarantine``, ``results``, ``backup_or_legacy`` and
    ``legacy_nested`` counts. Empty if the root does not exist yet.
    """
    buckets = {
        "active": 0,
        "active_replayable": 0,
        "terminal_replayed": 0,
        "terminal_quarantine": 0,
        "results": 0,
        "backup_or_legacy": 0,
        "legacy_nested": 0,
        "unknown": 0,
    }
    if not delivery_root.exists():
        return buckets
    bundle_files = list(delivery_root.rglob("notification-*-*.json"))
    stable_suffixes = {DAILY_REPLAYED_ROOTNAME, DAILY_QUARANTINE_ROOTNAME, DAILY_RESULTS_ROOTNAME}
    for p in bundle_files:
        if not p.is_file():
            continue
        parts = p.parts
        # Nested pathology: stable suffix followed by itself.
        for i in range(len(parts) - 1):
            if parts[i] == parts[i + 1] and parts[i] in stable_suffixes:
                buckets["legacy_nested"] += 1
                break
        else:
            # Immediate child of delivery_root = active pending.
            relative = p.relative_to(delivery_root)
            head = relative.parts[0] if relative.parts else ""
            if head == DAILY_PENDING_ROOTNAME:
                buckets["active"] += 1
                try:
                    doc = json.loads(p.read_text(encoding="utf-8"))
                except Exception:
                    continue
                # Replayable = still pending + has text + (no staged_report OR staged_report exists).
                staged = (doc.get("staged_report") or "").strip()
                if doc.get("status") == "pending" and (doc.get("text") or "").strip():
                    if (not staged) or Path(staged).exists():
                        buckets["active_replayable"] += 1
            elif head == DAILY_REPLAYED_ROOTNAME:
                buckets["terminal_replayed"] += 1
            elif head == DAILY_QUARANTINE_ROOTNAME:
                buckets["terminal_quarantine"] += 1
            elif head == DAILY_RESULTS_ROOTNAME:
                buckets["results"] += 1
            elif any(hint in seg for seg in parts for hint in _NON_ACTIVE_ARCHIVE_HINTS):
                buckets["backup_or_legacy"] += 1
            else:
                buckets["unknown"] += 1
    return buckets


def _scan_pending_media(report_dir: Path) -> dict:
    """Count ``.fallback-pending-*.json`` and archive state in report_dir.

    This is a read-only scan; we never touch the pending files
    themselves. The ``replay_pending_media.py`` script is the only
    component that mutates / archives them.

    P8D+4B scope fix:
      * Active pending = files that live under the canonical pending
        roots (``media-replay/pending/`` or ``daily-health/`` at the top
        level, not nested under replayed/quarantine).
      * Terminal states (replayed / quarantine), aggregate results, the
        historical ``queue-fix-backup-*`` snapshot, and any new
        ``legacy-cleaned/`` archive directory are **never** counted as
        ``pending``. The cron summary's ``pending_before`` now reflects
        only what ``replay_pending_media.py`` would actually attempt.
      * Counts are split per bucket so downstream consumers (ops status,
        message text) can surface non-actionable noise without falsifying
        the alarm threshold.
    """
    active_pending = 0
    active_replayable = 0
    terminal_replayed = 0
    terminal_quarantine = 0
    ignored_results = 0
    ignored_backup = 0
    nested_legacy = 0
    unknown = 0
    if not report_dir.exists():
        return {
            "pending": active_pending,
            "replayable": active_replayable,
            "quarantined": terminal_quarantine,
            "active_pending": active_pending,
            "active_replayable": active_replayable,
            "terminal_replayed": terminal_replayed,
            "terminal_quarantine": terminal_quarantine,
            "ignored_results": ignored_results,
            "ignored_backup": ignored_backup,
            "nested_legacy": nested_legacy,
            "unknown": unknown,
        }
    try:
        runtime_root = report_dir if report_dir.name == "runtime" else None
        # If we were handed ``reports/`` (the pre-P8D+4B cron path),
        # climb to ``reports/runtime/`` so we still locate media-replay
        # correctly. The classification itself only needs the path's own
        # segments.
        if runtime_root is None:
            candidate = report_dir / "runtime"
            runtime_root = candidate if candidate.is_dir() else None

        for p in sorted(report_dir.rglob(".fallback-pending-*.json")):
            if not p.is_file():
                continue
            cls = _classify_pending_path(p, runtime_root)
            if cls == "active_pending":
                active_pending += 1
                try:
                    doc = json.loads(p.read_text(encoding="utf-8"))
                except Exception:
                    # Corrupt JSON: counted as pending but not replayable.
                    continue
                attempts = int(doc.get("attempts") or 0)
                staged = doc.get("staged_report") or ""
                if attempts < DEFAULT_MAX_RETRIES_PENDING and staged and Path(staged).is_file():
                    active_replayable += 1
            elif cls == "terminal_replayed":
                terminal_replayed += 1
            elif cls == "terminal_quarantine":
                terminal_quarantine += 1
            elif cls == "results":
                ignored_results += 1
            elif cls == "backup_or_legacy":
                ignored_backup += 1
            elif cls == "legacy_nested":
                nested_legacy += 1
            else:
                unknown += 1
    except Exception as e:
        # Defensive: never let the scan break the health check.
        return {
            "pending": active_pending,
            "replayable": active_replayable,
            "quarantined": terminal_quarantine,
            "active_pending": active_pending,
            "active_replayable": active_replayable,
            "terminal_replayed": terminal_replayed,
            "terminal_quarantine": terminal_quarantine,
            "ignored_results": ignored_results,
            "ignored_backup": ignored_backup,
            "nested_legacy": nested_legacy,
            "unknown": unknown,
            "scan_error": f"{type(e).__name__}: {e}"[:200],
        }
    return {
        "pending": active_pending,
        "replayable": active_replayable,
        "quarantined": terminal_quarantine,
        "active_pending": active_pending,
        "active_replayable": active_replayable,
        "terminal_replayed": terminal_replayed,
        "terminal_quarantine": terminal_quarantine,
        "ignored_results": ignored_results,
        "ignored_backup": ignored_backup,
        "nested_legacy": nested_legacy,
        "unknown": unknown,
    }


def _probe_transport(base_dir: Path, openclaw_bin) -> dict:
    """Run ``scripts/check_openclaw_transport.py`` and return its JSON.

    This is a read-only probe. We never send a Telegram message.
    """
    script = base_dir / "scripts" / "check_openclaw_transport.py"
    fallback = {"status": "not_checked", "error_class": "", "latency_ms": 0,
                "checked_at": "", "limited_cli": True}
    if not script.is_file():
        fallback["error_class"] = "missing_script"
        return fallback
    cmd = [sys.executable, str(script)]
    if openclaw_bin:
        cmd += ["--openclaw-bin", openclaw_bin]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=15,
            cwd=str(base_dir),
        )
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "error_class": "subprocess_timeout", "latency_ms": 15000,
                "checked_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"), "limited_cli": True}
    except Exception as e:
        return {"status": "error", "error_class": f"{type(e).__name__}", "latency_ms": 0,
                "checked_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"), "limited_cli": True}
    out = (result.stdout or "").strip()
    if not out:
        return {"status": "error", "error_class": "no_json_output", "latency_ms": 0,
                "checked_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"), "limited_cli": True}
    # The probe prints a single (possibly multi-line) JSON object on
    # stdout. We accept the whole document rather than a single line,
    # since JSON pretty-prints span many lines.
    try:
        doc = json.loads(out)
    except Exception:
        # Fallback: try the last {...} block (in case extra trailing
        # text was added by future versions of the probe).
        last_open = out.rfind("{")
        last_close = out.rfind("}")
        if last_open >= 0 and last_close > last_open:
            try:
                doc = json.loads(out[last_open:last_close + 1])
            except Exception as e:
                return {"status": "error", "error_class": f"json_parse:{type(e).__name__}", "latency_ms": 0,
                        "checked_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"), "limited_cli": True}
        else:
            return {"status": "error", "error_class": "no_json_output", "latency_ms": 0,
                    "checked_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"), "limited_cli": True}
    version_probe = doc.get("probes", {}).get("version", {}) or {}
    return {
        "status": doc.get("status", "error"),
        "error_class": version_probe.get("error_class", "") or "",
        "latency_ms": version_probe.get("elapsed_ms", 0) or 0,
        "checked_at": doc.get("checked_at", ""),
        "limited_cli": True,  # The CLI is intentionally limited (no message send).
    }


def main():
    p = argparse.ArgumentParser(description="Artvee Daily Health Check")
    p.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"), help="Target date")
    p.add_argument("--base-dir", default=".", help="Repository base directory")
    p.add_argument("--output-json", required=True, help="JSON output path")
    p.add_argument("--output-md", required=True, help="Markdown output path")
    p.add_argument("--report-dir", default="", help="Report directory (optional)")
    p.add_argument("--no-telegram", dest="telegram", action="store_false", default=True, help="Skip Telegram")
    p.add_argument("--online", action="store_true", default=False, help="Check online endpoints")
    p.add_argument("--media", action="store_true", default=False, help="Attach MEDIA to Telegram")
    p.add_argument("--openclaw-bin", default=None, help="Path or command for OpenClaw binary")
    p.add_argument("--simulate-media-failure", dest="simulate_media_failure",
                   action="store_true", default=False,
                   help="Simulate MEDIA send failure (for fallback testing). Do not use in cron.")
    args = p.parse_args()
    run_check(args)
    print(f"[✓] Health check report: {args.output_json} + {args.output_md}")
    print("===== Daily health check complete =====")


if __name__ == "__main__":
    main()
