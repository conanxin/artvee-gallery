# Daily Operating Playbook

> Living document. Last updated: 2026-06-18 (P7B+3 pending MEDIA replay + transport health).
> This is the operational reference for the Artvee Gallery daily workflow.

---

## 1. Daily Timeline

```
01:30  refill_artvee_pending.py     → 补满种子池
02:00  run_artvee_nightly_batch.py  → 下载新 artwork
02:30  confirm_demo_refresh.sh      → 构建 public demo 候选包
03:00  artvee_daily_health_check.sh → 日常健康检查 + Telegram 摘要
       (optional) publish approved candidate  → 推送到 GitHub Pages
```

- **Refill** and **Batch** are fully automated via cron.
- **Candidate refresh** is automated via cron (`--no-telegram` mode).
- **Daily health check** is automated via cron at 03:00 (P7B).
- **Approved publish** remains **manual** — requires `--approve` flag.

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

### Daily health cron (install / remove / modify)

```bash
# Install P7B daily health cron at 03:00
bash scripts/install_daily_health_cron.sh --install

# Remove the P7B cron block
bash scripts/install_daily_health_cron.sh --remove

# Change time (e.g., to 09:00)
bash scripts/install_daily_health_cron.sh --install --time "0 9 * * *"
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

### 9.5. MEDIA staging regression (P7B+2)

If the daily health message reports `MEDIA: failed` but the report
itself is fine, the failure mode lives in one of three places
listed below. Read them in order — the JSON file
`reports/runtime/daily-health/artvee-daily-health-YYYY-MM-DD.json`
contains all the data you need to triage.

1. **Staging failed (P7B+2)** — `telegram.media.stage_failed == true`
   - The staging helper itself could not copy the report into the
     allowlisted media root (default: `${HOME}/.openclaw/media/artvee-reports/`).
     The reason is in `telegram.media.error`.
   - Common cause: filesystem permission, disk full, source report
     missing. Verify the report exists at `telegram.media.raw_report`
     and that the media root is writable.
   - Action: re-run the staging helper manually:
     ```bash
     python3 scripts/stage_report_for_telegram_media.py \
       --report reports/runtime/daily-health/artvee-daily-health-YYYY-MM-DD.md \
       --print-meta
     ```
     The JSON envelope tells you whether it succeeded.

2. **Send failed, non-transport** — `telegram.media.error_kind ∈
   {media_allowed, binary_missing, exit_nonzero, timeout}`
   - The report *was* staged, but OpenClaw rejected the send.
   - `media_allowed` — staged path is not under the OpenClaw
     allowlist. Verify `telegram.media.staged_report` is under
     `${HOME}/.openclaw/{media,workspace/media,workspace/tmp}/`.
   - `binary_missing` — OpenClaw CLI was not on PATH. Add
     `export PATH=$HOME/.local/bin:$PATH` to the cron line.
   - `exit_nonzero` / `timeout` — openclaw process crashed or
     exceeded 300s. Inspect `/tmp/artvee_notify_*.log`.
   - Action: the fallback message *was* sent (reason:
     `media_failed` or `stage_failed`), so ops learned about the
     problem; the next run will retry normally.

3. **Transport error — gateway unreachable**
   - `telegram.media.error_kind == "transport"` and
     `telegram.fallback.reason == "media_transport_deferred"`.
   - This is a transient OpenClaw gateway issue (the local
     loopback ws port timing out). The fallback is **deferred**,
     not sent.
   - Check `telegram.fallback.deferred_local_path` — there is a
     `.fallback-pending-YYYY-MM-DD.json` on disk containing the
     exact fallback text that would have been sent.
   - Once the OpenClaw gateway recovers, the *next* health check
     run will flush the pending file (its `text_summary` must
     succeed first to prove the gateway is healthy again). The
     pending file is then unlinked.
   - Action: only intervene if the deferral is more than 24h old —
     the cron self-heals.
   - **P7B+3 (2026-06-18)**: replay is now a **separate, opt-in step**
     rather than auto-flushed by the next health run. This avoids
     the 03:00 cron doing surprise work and gives operators a
     dedicated `scripts/replay_pending_media.py` command. See
     `docs/MEDIA_REPLAY.md` for the full workflow. The daily
     health report now embeds a `media_replay` block listing
     `pending`, `replayable`, `quarantined`, and
     `transport_status` for at-a-glance visibility.

### 9.6. Replay pending MEDIA (P7B+3)

When `media_replay.pending > 0` in the latest daily health report:

```bash
# 1. Verify transport is healthy first.
python3 scripts/check_openclaw_transport.py --text

# 2. Plan the replay (dry-run, no send, no move).
python3 scripts/replay_pending_media.py --limit 10

# 3. Actually send.
python3 scripts/replay_pending_media.py --apply --limit 10
```

After `--apply`, original pending files are moved to
`reports/runtime/daily-health/replayed/` (success) or
`quarantine/` (max-retries or invalid). A `.replay-result-*.json`
sidecar is written next to each. Replay never deletes files and
never sends a non-staged path.

Optional dedicated cron (NOT installed by default; explicit `apply`
required):

```
# 03:10 optional media replay — install manually after P7B+3 sign-off.
10 3 * * * export PATH=$HOME/.local/bin:$PATH && export ARTVEE_TELEGRAM_CHAT_ID='<id>' && cd <artvee-repo> && python3 scripts/replay_pending_media.py --apply --limit 10 >> logs/daily-health-cron/replay_$(date +%Y%m%d)_031000.log 2>&1
```

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
| Daily health (cron log) | `logs/daily-health-cron/daily_health_YYYYMMDD_030000.log` |
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

---

## 9. Telegram delivery state model (P7B+1)

The daily health report tracks three independent delivery tracks inside
`telegram.*` of the JSON output. Inspect
`reports/runtime/daily-health/artvee-daily-health-YYYY-MM-DD.json` for any
day's outcome.

| Track | Field | Meaning |
|-------|-------|---------|
| Overall request | `telegram.requested` | Whether the run was asked to send. |
| OpenClaw binary | `telegram.openclaw_status` | `resolved` / `missing` / `skipped`. |
| Text summary | `telegram.text_summary.{attempted,sent,message_id,error}` | The short ✅/❌ block. |
| MEDIA attachment | `telegram.media.{requested,staged,staged_path,sent,message_id,error}` | The full Markdown report attachment. |
| Fallback | `telegram.fallback.{attempted,sent,message_id,reason}` | A short text-only warning if MEDIA failed. |

### Three states you will see in the wild

1. **All green** — `text_summary.sent=true` and `media.sent=true`. No fallback.
2. **MEDIA failed, fallback sent** — `text_summary.sent=true`, `media.sent=false`,
   `fallback.sent=true` with `reason=media_failed`. Health is still PASS; only
   the attachment delivery is broken. Action: inspect `media.error` and
   `media.staged_path`; check OpenClaw's media allowlist.
3. **OpenClaw binary missing** — `openclaw_status=missing`. Nothing was
   sent. The health check itself is still authoritative; this is a notify
   failure only.

`MEDIA failed` is **not** a health failure. The daily check's verdict is
`report.checks.*.status`; Telegram is a separate observation channel.

### Cron-like verification (no need to wait for 03:00)

```bash
cd <artvee-repo>
mkdir -p logs/daily-health-cron
env -i \
  HOME="$HOME" USER="$USER" LOGNAME="$USER" \
  SHELL=/bin/bash \
  PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin" \
  ARTVEE_TELEGRAM_CHAT_ID="<telegram-chat-id>" \
  bash -lc 'cd <artvee-repo> && bash scripts/artvee_daily_health_check.sh --online --media' \
  >> logs/daily-health-cron/daily_health_cronlike_test.log 2>&1
echo "exit=$?"
tail -10 logs/daily-health-cron/daily_health_cronlike_test.log
# Sanity check: must not print tokens / chat ids / home paths.
grep -RInE "TOKEN|SECRET|CHAT_ID|bot[0-9]+:" \
  logs/daily-health-cron/daily_health_cronlike_test.log || echo "OK no secrets"
```

### Simulate a MEDIA failure to test the fallback chain

```bash
cd <artvee-repo>
bash scripts/artvee_daily_health_check.sh --online --media --simulate-media-failure
```

Expected log lines (in order):

```
[✓] Telegram text summary sent (message_id=...)
[warn] MEDIA simulated failure (--simulate-media-failure)
[✓] Telegram fallback (text-only) sent (message_id=...)
```

The fallback is sent at most once per run, never recursively, and never
changes the script's exit code (unless health checks themselves fail).

---

## 10. v0.2.0-alpha operating baseline

This is the snapshot the system ships at v0.2.0-alpha. Use it
when you want to confirm the running host still matches the
release baseline.

| Metric | Value |
|--------|-------|
| Release | `v0.2.0-alpha` (tag on `main`, GitHub Release published) |
| Records | 776 |
| Known retired (audited) | 4 |
| Blocking unresolved | 0 |
| Strict integrity | PASS |
| Public demo ready | true |
| Digest ready | true |

---

## 11. v0.2.0 observation window checklist

During the observation window (2026-06-14 — 2026-06-16), run this each morning after the 03:00 health check arrives:

```markdown
- [ ] 03:00 Telegram message received
- [ ] MEDIA attachment present (or fallback text sent)
- [ ] records within ~750–800
- [ ] failed == 0
- [ ] known_retired == 4
- [ ] blocking_unresolved == 0
- [ ] integrity == PASS
- [ ] readiness == PASS
- [ ] candidate_gallery == True
- [ ] candidate_digest == True
- [ ] online_gallery == 200
- [ ] online_digest == 200
- [ ] No manual intervention needed
```

**Scoring:**
- All 12 checked → Green day, observation continues
- 1–2 yellow items → Yellow day, document and watch
- Any red item (integrity FAIL, readiness FAIL, blocking_unresolved > 0) → Red day, stop stable release planning

At the end of Day 3 (2026-06-16), if all 3 days are green, v0.2.0 stable is approved. If any day is yellow or red, extend observation by 1 day and re-evaluate.

See [docs/V0_2_OBSERVATION_WINDOW.md](V0_2_OBSERVATION_WINDOW.md) for full criteria, warning signs, and next steps.
| Gallery demo | <https://conanxin.github.io/projects/artvee-gallery-demo/> |
| Digest demo | <https://conanxin.github.io/projects/artvee-gallery-digest/> |
| Cron rhythm | 01:30 refill · 02:00 nightly batch · 02:30 candidate refresh · 03:00 daily health · manual approved publish |
| Public bundle | `dist/` (regenerable; never auto-pushed) |

### Quick baseline verification

```bash
cd <artvee-repo>
python3 scripts/build_artvee_status_report.py \
  --out-json reports/runtime/artvee-status-report.json \
  --out-md   reports/runtime/artvee-status-report.md
python3 -c "import json; d=json.load(open('reports/runtime/artvee-status-report.json')); \
  print('records:', d['records'], '| known_retired:', d['known_retired'], \
        '| blocking_unresolved:', d['blocking_unresolved'], \
        '| strict_integrity:', d['strict_integrity'], \
        '| public_demo_ready:', d['public_demo_ready'], \
        '| digest_ready:', d['digest_ready'])"
python3 scripts/check_open_source_ready.py
python3 scripts/check_gallery_integrity.py --strict
bash scripts/artvee_daily_health_check.sh --no-telegram
```

Expected output:

- records near 776 (± a few per nightly batch).
- `known_retired=4`, `blocking_unresolved=0`.
- `strict_integrity=pass`, `public_demo_ready=True`, `digest_ready=True`.
- Open-source readiness: 4/4 PASS.
- Strict integrity: 0 duplicates.
- Health report: `checks.integrity.status = PASS`, `checks.readiness.status = PASS`.

If any of these fail, see § 5 (Failure Playbook) before pulling
in a different phase.

---

## 12. Online-endpoint content drift (P7E+1 / P7E+2, 2026-06-15)

**Symptom** — Daily Health Telegram summary shows:

```
Online: gallery=404, digest=404
Action: attention_required_pages_content_drift
```

(After P7E+2, `gallery_http_code` and `digest_http_code` are real HTTP codes; before
P7E+2, the same symptom showed as `gallery=0, digest=0` because `except Exception`
collapsed `urllib.error.HTTPError` into 0.)

**What it means** — the local Artvee system is healthy (records pass strict
integrity, candidates are ready), but the public GitHub Pages site is missing
the `projects/artvee-gallery-demo/` or `projects/artvee-gallery-digest/`
directories. The path exists; the *content* doesn't. This is content drift,
not a network failure. `online.kind = "http_error"` and `gallery_error`
contains the real reason (`HTTPError 404 Not Found`).

**Recovery playbook** (read-only diagnosis, then approved publish):

```bash
# 1. Confirm: 9/9 endpoints HTTP 404 from this server
for url in \
  "https://conanxin.github.io/projects/artvee-gallery-demo/" \
  "https://conanxin.github.io/projects/artvee-gallery-demo/data/artworks.json" \
  "https://conanxin.github.io/projects/artvee-gallery-demo/data/gallery_stats.json" \
  "https://conanxin.github.io/projects/artvee-gallery-demo/app.js" \
  "https://conanxin.github.io/projects/artvee-gallery-demo/style.css" \
  "https://conanxin.github.io/projects/artvee-gallery-digest/" \
  "https://conanxin.github.io/projects/artvee-gallery-digest/digest.html" \
  "https://conanxin.github.io/projects/artvee-gallery-digest/digest.md" \
  "https://conanxin.github.io/projects/artvee-gallery-digest/data/digests.json"
do
  curl -L -I --max-time 10 -w '%{http_code} ' -o /dev/null -s "$url"
  echo "  $url"
done
# expect: 404 404 404 404 404 404 404 404 404
#         (NOT 0 0 0 0 0 0 0 0 0 — that would be network_error, different fix path)

# 2. Pages repo: check drift
cd <pages-repo>
git fetch origin main
git log --oneline f419d31..origin/main   # how far behind
git ls-tree -r --name-only origin/main -- \
  projects/artvee-gallery-demo projects/artvee-gallery-digest | wc -l   # expect 0

# 3. Sync to current main (ff-only, NEVER force)
git pull --ff-only

# 4. Rebuild candidate + restore (artvee repo)
cd <artvee-repo>
bash scripts/confirm_demo_refresh.sh --no-telegram
bash scripts/publish_demo_refresh_candidate.sh --date $(date +%F) --approve --cdn-wait 90

# 5. Online re-verify (wait ≥90s for CDN)
sleep 90
# repeat the curl loop from step 1 — expect 200 200 ... 200
```

**Key rules**:

- Do **not** revert the unrelated commits that triggered the drift (in the
  2026-06-15 incident, those were 9 WBW SpaceX Mars publish commits). They
  are correct work; they just share a `projects/` namespace with artvee.
- Do **not** use `git add .` in the Pages repo. Stage explicit paths only.
- Do **not** modify `images/` / `metadata/` / `thumbs/` / `inbox/` / `index/`
  / `web/data/` in the artvee repo during a content-drift restore. The
  candidate is already correct; the problem is upstream.
- If `online.kind = "network_error"` (i.e. real `0`s, not `404`s), the
  problem is DNS / TLS / Pages down / ISP — the recovery is *not* the
  same. Re-run `--online` after 5–10 min; if it persists, check
  `https://github.com/conanxin/conanxin.github.io/actions` for a Pages
  build failure.

**Related reports**:

- `<workspace>/reports/artvee-gallery-p7e1-online-endpoint-failure-20260615.md`
  — the diagnosis that surfaced the signal-distortion bug.
- `<workspace>/reports/artvee-gallery-p7e2-public-demo-restore-20260615.md`
  — the approved restore that shipped `a5ad80c` and the health-script fix.
