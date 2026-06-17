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

    # 3. Status report
    status_json_path = base_dir / "reports" / "runtime" / "artvee-status-report.json"
    status_report = {"status": "SKIP", "records": None, "known_retired": None,
                     "blocking_unresolved": None, "strict_integrity": None,
                     "details": "status report not found"}
    if status_json_path.exists():
        try:
            with open(status_json_path) as f:
                sr = json.load(f)
            status_report = {
                "status": "PASS",
                "records": sr.get("records"),
                "known_retired": sr.get("known_retired"),
                "blocking_unresolved": sr.get("blocking_unresolved"),
                "strict_integrity": sr.get("strict_integrity"),
                "details": f"status report loaded from {status_json_path.name}",
            }
        except Exception:
            status_report["status"] = "WARN"
            status_report["details"] = "status report unreadable"

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
        f.write("## Summary\n\n")
        f.write("| Metric | Value |\n")
        f.write("|--------|-------|\n")
        sr = report["checks"]["status_report"]
        f.write(f"| Records | {sr.get('records', 'N/A')} |\n")
        f.write(f"| Known retired | {sr.get('known_retired', 'N/A')} |\n")
        f.write(f"| Blocking unresolved | {sr.get('blocking_unresolved', 'N/A')} |\n")
        f.write(f"| Strict integrity | {report['checks']['integrity']['status']} |\n")
        f.write(f"| Readiness | {report['checks']['readiness']['status']} |\n")
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
        records = sr.get("records", "N/A")
        cand_g = report["checks"]["candidate_state"]["gallery_ready"]
        cand_d = report["checks"]["candidate_state"]["digest_ready"]
        hist_entries = report["checks"]["digest_history"]["entries"]
        nd_clusters = report["checks"]["near_dup_clusters"]["cluster_count"]

        if integrity_status == "PASS" and readiness_status == "PASS" and blocking == 0:
            icon = "✅"
        else:
            icon = "❌"

        msg = f"""{icon} Artvee Daily Health
Date: {args.date}
Records: {records}
Integrity: {integrity_status}
Readiness: {readiness_status}
Retired: known_retired={retired}, blocking_unresolved={blocking}
Candidate: gallery={cand_g}, digest={cand_d}
Digest history: {hist_entries} entries
Near-dup clusters: {nd_clusters}
Action: {action}"""

        if args.online:
            gcode = report["online"].get("gallery_http_code", "N/A")
            dcode = report["online"].get("digest_http_code", "N/A")
            msg += f"\nOnline: gallery={gcode}, digest={dcode}"

        # Resolve OpenClaw binary before attempting any send
        notifier_cmd = [sys.executable, str(base_dir / "scripts" / "artvee_telegram_notify.py")]
        if args.openclaw_bin:
            notifier_cmd += ["--openclaw-bin", args.openclaw_bin]
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
            telegram["text_summary"]["attempted"] = True
            ts_cmd = notifier_cmd + ["--text", msg, "--wait"]
            ts_result = subprocess.run(ts_cmd, capture_output=True, text=True, cwd=str(base_dir))
            if ts_result.returncode == 0 and "NOTIFY_OK" in ts_result.stdout:
                telegram["text_summary"]["sent"] = True
                # Parse message_id from the notifier stdout (format: NOTIFY_OK ... message_id=NNN)
                import re as _re
                m = _re.search(r"message_id=(\d+)", ts_result.stdout)
                if m:
                    telegram["text_summary"]["message_id"] = m.group(1)
                print(f"[✓] Telegram text summary sent (message_id={telegram['text_summary']['message_id']})")
            else:
                telegram["text_summary"]["sent"] = False
                telegram["text_summary"]["error"] = (ts_result.stdout.strip() or ts_result.stderr.strip() or f"exit {ts_result.returncode}")[:300]
                print(f"[warn] Telegram text summary failed: {telegram['text_summary']['error']}")

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
                            flush_cmd = notifier_cmd + ["--text", pending_text, "--wait"]
                            flush_result = subprocess.run(flush_cmd, capture_output=True, text=True, cwd=str(base_dir))
                            if flush_result.returncode == 0 and "NOTIFY_OK" in flush_result.stdout:
                                # We expose the flush under a dedicated field
                                # so it does not collide with the current
                                # run's fallback.
                                if "flushed_pending_fallbacks" not in telegram:
                                    telegram["flushed_pending_fallbacks"] = []
                                m = _re.search(r"message_id=(\d+)", flush_result.stdout)
                                telegram["flushed_pending_fallbacks"].append({
                                    "date": pending.get("date"),
                                    "reason": pending.get("reason"),
                                    "sent": True,
                                    "message_id": m.group(1) if m else None,
                                    "local_path": str(pending_path),
                                })
                                print(f"[✓] Flushed deferred fallback from {pending_path} (message_id={m.group(1) if m else '?'})")
                                try:
                                    pending_path.unlink()
                                except Exception as e:
                                    print(f"[warn] Failed to unlink pending fallback {pending_path}: {e}")
                            else:
                                err = (flush_result.stdout.strip() or flush_result.stderr.strip() or f"exit {flush_result.returncode}")[:200]
                                if "flushed_pending_fallbacks" not in telegram:
                                    telegram["flushed_pending_fallbacks"] = []
                                telegram["flushed_pending_fallbacks"].append({
                                    "date": pending.get("date"),
                                    "reason": pending.get("reason"),
                                    "sent": False,
                                    "error": err,
                                    "local_path": str(pending_path),
                                })
                                print(f"[warn] Deferred fallback flush failed: {err}")
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
                        media_cmd = notifier_cmd + ["--text", msg, "--media", media_path, "--wait"]
                        media_result = subprocess.run(media_cmd, capture_output=True, text=True, cwd=str(base_dir))
                        if media_result.returncode == 0 and "NOTIFY_OK" in media_result.stdout:
                            telegram["media"]["sent"] = True
                            import re as _re
                            m = _re.search(r"message_id=(\d+)", media_result.stdout)
                            if m:
                                telegram["media"]["message_id"] = m.group(1)
                            m2 = _re.search(r"error_kind=(\S+)", media_result.stdout)
                            if m2:
                                telegram["media"]["error_kind"] = m2.group(1)
                            print(f"[✓] Telegram MEDIA sent (message_id={telegram['media']['message_id']})")
                        else:
                            telegram["media"]["sent"] = False
                            err = (media_result.stdout.strip() or media_result.stderr.strip() or f"exit {media_result.returncode}")[:300]
                            telegram["media"]["error"] = err
                            import re as _re
                            m2 = _re.search(r"error_kind=(\S+)", media_result.stdout)
                            telegram["media"]["error_kind"] = m2.group(1) if m2 else "exit_nonzero"
                            print(f"[warn] Telegram MEDIA failed ({telegram['media']['error_kind']}): {err}")

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
                        fb_cmd = notifier_cmd + ["--text", fallback_text, "--wait"]
                        fb_result = subprocess.run(fb_cmd, capture_output=True, text=True, cwd=str(base_dir))
                        if fb_result.returncode == 0 and "NOTIFY_OK" in fb_result.stdout:
                            telegram["fallback"]["sent"] = True
                            telegram["fallback"]["reason"] = "media_failed"
                            import re as _re
                            m = _re.search(r"message_id=(\d+)", fb_result.stdout)
                            if m:
                                telegram["fallback"]["message_id"] = m.group(1)
                            print(f"[✓] Telegram fallback (text-only) sent (message_id={telegram['fallback']['message_id']})")
                else:
                    fb_cmd = notifier_cmd + ["--text", fallback_text, "--wait"]
                    telegram["fallback"]["attempted"] = True
                    telegram["fallback"]["reason"] = fallback_reason
                    fb_result = subprocess.run(fb_cmd, capture_output=True, text=True, cwd=str(base_dir))
                    if fb_result.returncode == 0 and "NOTIFY_OK" in fb_result.stdout:
                        telegram["fallback"]["sent"] = True
                        import re as _re
                        m = _re.search(r"message_id=(\d+)", fb_result.stdout)
                        if m:
                            telegram["fallback"]["message_id"] = m.group(1)
                        print(f"[✓] Telegram fallback (text-only) sent (message_id={telegram['fallback']['message_id']})")
                    else:
                        err = (fb_result.stdout.strip() or fb_result.stderr.strip() or f"exit {fb_result.returncode}")[:300]
                        telegram["fallback"]["error"] = err
                        print(f"[warn] Telegram fallback failed: {err}")
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

def _scan_pending_media(report_dir: Path) -> dict:
    """Count ``.fallback-pending-*.json`` and archive state in report_dir.

    This is a read-only scan; we never touch the pending files
    themselves. The ``replay_pending_media.py`` script is the only
    component that mutates / archives them.
    """
    pending = 0
    replayable = 0
    quarantined = 0
    if not report_dir.exists():
        return {"pending": pending, "replayable": replayable, "quarantined": quarantined}
    try:
        for p in sorted(report_dir.rglob(".fallback-pending-*.json")):
            if not p.is_file():
                continue
            # P7B+3: skip files already archived (replayed / quarantine).
            rel = p.relative_to(report_dir).as_posix() if report_dir in p.parents else ""
            if rel.startswith("replayed/") or rel.startswith("quarantine/"):
                continue
            pending += 1
            try:
                doc = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                # Corrupt JSON: not safely replayable. Count as pending
                # but not replayable.
                continue
            attempts = int(doc.get("attempts") or 0)
            staged = doc.get("staged_report") or ""
            if attempts < DEFAULT_MAX_RETRIES_PENDING and staged and Path(staged).is_file():
                replayable += 1
        # Count quarantine-archived pendings + sidecar records (for visibility).
        quarantine_dir = report_dir / "quarantine"
        if quarantine_dir.is_dir():
            for q in sorted(quarantine_dir.glob(".fallback-pending-*.json")):
                if q.is_file():
                    quarantined += 1
        for q in sorted(report_dir.rglob(".quarantine-*.json")):
            if q.is_file() and (q.parent.name != "quarantine" or q.name.startswith(".quarantine-")):
                if not (q.parent / ".fallback-pending-" + q.name[len(".quarantine-"):]).exists():
                    # Sidecar that doesn't have a corresponding pending
                    # — count it as quarantined record.
                    quarantined += 1
    except Exception as e:
        # Defensive: never let the scan break the health check.
        return {"pending": pending, "replayable": replayable, "quarantined": quarantined,
                "scan_error": f"{type(e).__name__}: {e}"[:200]}
    return {"pending": pending, "replayable": replayable, "quarantined": quarantined}


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
