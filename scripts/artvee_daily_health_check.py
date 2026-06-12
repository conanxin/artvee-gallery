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


def run_check(args):
    base_dir = Path(args.base_dir)
    report_dir = Path(args.report_dir) if args.report_dir else base_dir / "reports" / "runtime" / "daily-health"
    report_dir.mkdir(parents=True, exist_ok=True)
    tmp_json = report_dir / f".tmp-health-{args.date}.json"
    report_json = report_dir / f"artvee-daily-health-{args.date}.json"
    report_md = report_dir / f"artvee-daily-health-{args.date}.md"

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

    # 9. Online checks (optional)
    online = {"status": "SKIP", "details": "online check disabled; use --online to enable"}
    if args.online:
        gallery_url = "https://conanxin.github.io/projects/artvee-gallery-demo/"
        digest_url = "https://conanxin.github.io/projects/artvee-gallery-digest/"
        try:
            import urllib.request
            gcode = urllib.request.urlopen(gallery_url, timeout=30).getcode()
            dcode = urllib.request.urlopen(digest_url, timeout=30).getcode()
        except Exception:
            gcode, dcode = 0, 0
        online = {
            "gallery_url": gallery_url,
            "gallery_http_code": gcode,
            "digest_url": digest_url,
            "digest_http_code": dcode,
            "status": "PASS" if (gcode == 200 and dcode == 200) else "FAIL",
            "details": ("both public endpoints return 200" if (gcode == 200 and dcode == 200)
                        else f"one or more public endpoints failed (gallery={gcode}, digest={dcode})"),
        }

    # Determine recommended action
    blocking = status_report.get("blocking_unresolved", 0) or 0
    if integrity["status"] == "PASS" and readiness["status"] == "PASS" and blocking == 0:
        if gallery_ready and digest_ready:
            action = "candidate_ready_manual_publish_optional"
        else:
            action = "healthy_no_action"
    else:
        action = "attention_required"

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

    # Telegram summary (if enabled)
    telegram_notify = {"enabled": args.telegram, "media_requested": args.media, "openclaw_status": "unknown", "sent": False, "message_id": None}
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

        # Resolve OpenClaw binary before trying to send
        notifier_cmd = [sys.executable, str(base_dir / "scripts" / "artvee_telegram_notify.py")]
        if args.openclaw_bin:
            notifier_cmd += ["--openclaw-bin", args.openclaw_bin]
        # Check if binary can be resolved
        check_cmd = notifier_cmd + ["--text", "probe", "--wait"]
        # Quick check: run notifier with --text probe to see if it resolves
        # Actually, better: use a dedicated dry-run or just try to send
        # The notifier itself will return error if binary missing
        resolved = False
        try:
            probe = subprocess.run([sys.executable, str(base_dir / "scripts" / "artvee_telegram_notify.py"),
                                    "--openclaw-bin", args.openclaw_bin or "openclaw",
                                    "--text", "_probe_", "--wait"],
                                   capture_output=True, text=True, cwd=str(base_dir), timeout=30)
            resolved = (probe.returncode == 0) or ("NOTIFY_OK" in probe.stdout)
        except Exception:
            resolved = False
        # If probe failed, mark as skipped but don't crash health check
        if not resolved:
            telegram_notify["openclaw_status"] = "missing"
            telegram_notify["sent"] = False
            print("[info] Telegram notify skipped: OpenClaw binary not resolved (cron may succeed if PATH differs)")
            # Continue without sending — health report is still generated
        else:
            telegram_notify["openclaw_status"] = "resolved"
            if args.media and report_md.exists():
                # Stage for Telegram MEDIA
                try:
                    subprocess.run([sys.executable, str(base_dir / "scripts" / "stage_report_for_telegram_media.py"),
                                    "--report", str(report_md), "--media-root", str(report_dir)],
                                   capture_output=True, text=True, check=True, cwd=str(base_dir))
                    staged = list(report_dir.glob(f"artvee-daily-health-{args.date}*.md"))
                    if staged:
                        media_path = str(staged[0])
                    else:
                        media_path = str(report_md)
                except Exception:
                    media_path = str(report_md)
                try:
                    send_cmd = notifier_cmd + ["--text", msg, "--media", media_path, "--wait"]
                    result = subprocess.run(send_cmd, capture_output=True, text=True, check=True, cwd=str(base_dir))
                    telegram_notify["sent"] = True
                    print("[✓] Telegram summary sent with MEDIA")
                except Exception as e:
                    telegram_notify["sent"] = False
                    print(f"[warn] Telegram notify failed: {e}")
            else:
                try:
                    send_cmd = notifier_cmd + ["--text", msg, "--wait"]
                    result = subprocess.run(send_cmd, capture_output=True, text=True, check=True, cwd=str(base_dir))
                    telegram_notify["sent"] = True
                    print("[✓] Telegram summary sent")
                except Exception as e:
                    telegram_notify["sent"] = False
                    print(f"[warn] Telegram notify failed: {e}")
    else:
        telegram_notify["openclaw_status"] = "skipped"
        telegram_notify["sent"] = False

    # Add telegram_notify to report
    report["telegram_notify"] = telegram_notify
    # Re-write JSON with telegram status
    with open(tmp_json, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    tmp_json.rename(report_json)


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
    args = p.parse_args()
    run_check(args)
    print(f"[✓] Health check report: {args.output_json} + {args.output_md}")
    print("===== Daily health check complete =====")


if __name__ == "__main__":
    main()
