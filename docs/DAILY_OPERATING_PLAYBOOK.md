# Daily Operating Playbook

> Living document. Last updated: 2026-06-12 (P7A).
> This is the operational reference for the Artvee Gallery daily workflow.

---

## 1. Daily Timeline

```
01:30  refill_artvee_pending.py     → 补满种子池
02:00  run_artvee_nightly_batch.py  → 下载新 artwork
02:30  confirm_demo_refresh.sh      → 构建 public demo 候选包
03:00  (optional) publish approved candidate  → 推送到 GitHub Pages
```

- **Refill** and **Batch** are fully automated via cron.
- **Candidate refresh** is automated via cron (`--no-telegram` mode).
- **Approved publish** remains **manual** — requires `--approve` flag.
- **Daily health check** is manual or via cron (P7B pending).

---

## 2. Normal Healthy State

A healthy Artvee system looks like this:

| Metric | Healthy Value |
|--------|--------------|
| records | ~750–800 (grows slowly) |
| failed | 0 (or small transient) |
| known_retired | 4 (or small, audited) |
| blocking_unresolved | 0 |
| strict_integrity | PASS |
| candidate QA | PASS |
| public demo | 200 OK |
| public digest | 200 OK |

**Note:** `known_retired` is not a failure. It is an audited list of URLs that are intentionally not retried.

---

## 3. Daily Commands

### Full health check (with online + media)

```bash
cd <local-path>/artvee-library
bash scripts/artvee_daily_health_check.sh --online --media
```

### Health check (no Telegram, just report)

```bash
bash scripts/artvee_daily_health_check.sh --no-telegram
```

### Generate candidate manually

```bash
bash scripts/confirm_demo_refresh.sh --no-telegram
```

### Dry-run publish

```bash
bash scripts/publish_demo_refresh_candidate.sh --dry-run
```

### Approved publish

```bash
bash scripts/publish_demo_refresh_candidate.sh --date YYYY-MM-DD --approve
```

### Status report (standalone)

```bash
python3 scripts/build_artvee_status_report.py \
  --out-json reports/runtime/artvee-status-report.json \
  --out-md reports/runtime/artvee-status-report.md
```

### Integrity check (standalone)

```bash
python3 scripts/check_gallery_integrity.py --strict
```

---

## 4. What Not to Do

| Don't | Why |
|-------|-----|
| Run full batch manually | Unless intentionally testing; the nightly cron handles it |
| Publish without candidate QA | `confirm_demo_refresh.sh` must PASS first |
| Treat `known_retired` as active failure | These are audited, deliberately not retried |
| Commit runtime data | `reports/runtime/`, `dist/`, `logs/` are `.gitignore`d |
| Retry retired URLs | Use `mark_known_retired_urls.py` to audit, not retry |
| Run `--approve` without `--date` | Always specify the date to avoid ambiguity |

---

## 5. Failure Playbook

### Integrity FAIL

1. Run `check_gallery_integrity.py` without `--strict` to see details.
2. Check `index/artworks.csv` and `web/data/artworks.json` for duplicates.
3. If duplicates found, check if they are near-duplicates (see [NEAR_DUPLICATE_REVIEW.md](NEAR_DUPLICATE_REVIEW.md)).
4. If collision, follow P4B migration plan.
5. Do not modify source data manually — use the migration scripts.

### Candidate FAIL

1. Check `logs/confirm_demo_refresh/report_YYYY-MM-DD.md` for details.
2. Common causes: missing `artworks.json`, missing digest files, public JSON safety fail.
3. Fix the underlying issue and re-run `confirm_demo_refresh.sh`.

### Telegram / MEDIA Fail

1. Check `artvee_telegram_notify.py` token and chat ID.
2. Check `stage_report_for_telegram_media.py` whitelist paths.
3. Fallback: send plain text summary without `--media`.

### GitHub Pages Verification Fail

1. Check if Pages repo has the latest commit (`conanxin.github.io`).
2. Check CDN cache — wait 60–90s and retry.
3. Use `publish_demo_refresh_candidate.sh --cdn-wait 120` if needed.
4. Check GitHub Actions status for Pages build.

### Digest History Issue

1. Check `reports/runtime/digest-history.json` exists and is valid JSON.
2. Check `reports/runtime/digest-history.json` has `entries` array.
3. If corrupt, delete and re-run `build_artvee_daily_digest.py` with `--history-file`.
4. History is advisory — digest will still generate without it.

---

## 6. Current Open Issues

| Issue | Status | Notes |
|-------|--------|-------|
| Near-dup policy | Advisory | `review_near_duplicate_clusters.py` is read-only; no auto-deletion |
| Retired URLs | Non-blocking | `known_retired=4` is expected and audited |
| Manual publish | Approval-based | No auto-publish cron by design (P7A) |
| Daily health check | Manual | P7B will add optional cron |
| Digest history window | 30 days | Configurable via `--history-window` |

---

## 7. Quick Reference

### Report Locations

| Report | Path |
|--------|------|
| Daily health (JSON) | `reports/runtime/daily-health/artvee-daily-health-YYYY-MM-DD.json` |
| Daily health (MD) | `reports/runtime/daily-health/artvee-daily-health-YYYY-MM-DD.md` |
| Status report | `reports/runtime/artvee-status-report.json` / `.md` |
| Candidate QA | `logs/confirm_demo_refresh/report_YYYY-MM-DD.md` |
| Nightly batch | `logs/nightly_summary/nightly_summary_YYYY-MM-DD_HHMMSS.csv` |
| Digest history | `reports/runtime/digest-history.json` |
| Near-dup clusters | `reports/runtime/p6c-near-dup-clusters.json` |

### Public URLs

| Surface | URL |
|---------|-----|
| Gallery demo | https://conanxin.github.io/projects/artvee-gallery-demo/ |
| Digest demo | https://conanxin.github.io/projects/artvee-gallery-digest/ |

---

*Playbook generated by OpenClaw agent · P7A Daily Automation Hardening*

---

## 8. Telegram notify troubleshooting (P7A+1)

If the health check reports `telegram_notify.openclaw_status: missing`,
common causes are:

1. **PATH difference** — cron may not have `\u003cuser-home\u003e/.local/bin` in PATH.
   Fix: add `export PATH="$HOME/.local/bin:$PATH"` to the cron script,
   or pass `--openclaw-bin <openclaw-bin>` explicitly.
2. **ARTVEE_OPENCLAW_BIN env var** — set it in `.bashrc` or the cron
   environment to an absolute path.
3. **Interactive vs cron** — test with `bash scripts/artvee_daily_health_check.sh --no-telegram`
   to confirm the rest of the pipeline works, then debug Telegram separately.
4. **MEDIA path** — reports must be staged to an OpenClaw-allowed directory
   before attachment. The `stage_report_for_telegram_media.py` helper handles this.
   If it fails, the notifier falls back to plain text.

Resolution order: `--openclaw-bin` CLI arg > `ARTVEE_OPENCLAW_BIN` env >
`OPENCLAW_BIN` env > PATH lookup. See `docs/DEVELOPMENT.md` § 20 for full details.
