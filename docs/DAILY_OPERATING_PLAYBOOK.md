# Daily Operating Playbook

> Living document. Last updated: 2026-07-01 (P8D+3 media replay verification cleanup: neutralized replay title, recovered-WARN classification in § 9.10).
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

### Refill / Batch / Confirm-refresh cron (P8D+1 unified installer)

The three pre-P7B Artvee cron lines (01:30 refill, 02:00 batch,
02:30 confirm refresh) used to be hand-maintained and were missing
`PATH` / `CRON_TZ`. P8D+1 introduces a single source of truth:

```bash
# Install (or replace) the P8D+1 unified block
bash scripts/install_artvee_cron.sh --install

# Preview the new crontab without applying
bash scripts/install_artvee_cron.sh --dry-run

# Remove the P8D+1 block (leaves P7B and P8D marker blocks intact)
bash scripts/install_artvee_cron.sh --remove
```

The installer bakes two env-var lines above the schedules:

* `CRON_TZ=Asia/Shanghai` — must be on its own line. Prepending it to
  the schedule (e.g. `CRON_TZ=Asia/Shanghai 30 1 * * * ...`) produces
  a 7-field line that **cron silently rejects** (this was the root
  cause of the 2026-06-29 03:10 media-replay cron producing zero
  artifacts).
* `PATH=$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin` — required so
  the OpenClaw binary used by the Telegram notifier is resolvable
  under cron's minimal default PATH. Without this, every run logs
  `NOTIFY_FAIL: OpenClaw binary not found` (the data products are
  still produced; only the Telegram notification is dropped).

The P7B daily-health installer and the P8D media-replay installer
both already export `PATH=...` the same way. After upgrading, verify
all five Artvee lines resolve to a single canonical schedule:

```bash
crontab -l | grep -E 'artvee_nightly_wrapper|confirm_demo_refresh|daily_health_check|media_replay_cron'
# expect 4 distinct lines, no duplicates
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

### Ops status (post-stable, P8A)

After v0.2.0 stable, the canonical one-shot "is everything OK?"
command is:

```bash
bash scripts/artvee_ops_status.sh --online --include-pages
```

This aggregates repo state, records, integrity, readiness,
candidate readiness, pending MEDIA, OpenClaw transport health,
Pages guard availability, and live public-demo HTTP status into
one JSON + Markdown report. It is **strictly read-only by
default**; it never downloads, refills, runs nightly batch,
pushes Pages, or replays pending MEDIA. Add `--media` to send
the report via Telegram + staged MEDIA (the same path the daily
health check uses).

| task | command |
|---|---|
| One-shot ops snapshot (no Telegram) | `bash scripts/artvee_ops_status.sh --online --include-pages` |
| Send report to Telegram + MEDIA | `bash scripts/artvee_ops_status.sh --online --include-pages --media` |
| Custom date | `bash scripts/artvee_ops_status.sh --date 2026-06-18` |
| JSON to stdout (for piping) | `bash scripts/artvee_ops_status.sh --json` |

Output: `reports/runtime/ops/artvee-ops-status-<date>.{json,md}`.
The script and the full field reference live in
`docs/POST_STABLE_OPERATIONS.md`.

The ops status command is **complementary to** (not a replacement
for) the 03:00 daily health cron:

* **Daily health cron** is continuous monitoring: it runs every day
  at 03:00, writes to `reports/runtime/daily-health/`, optionally
  sends a Telegram summary, and owns the transport probe + the
  pending MEDIA scan.
* **Ops status** is on-demand review: it runs when the operator is
  already at the keyboard, gives one Markdown report to look at,
  and never alters the daily health schedule.

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

### 9.7. Ops status command (P8A)

P8A adds a single on-demand command that answers *"is everything
OK right now?"* without touching cron, without sending Telegram by
default, and without writing anything outside `reports/runtime/ops/`:

```bash
# Default — no Telegram, no online probe, no Pages-repo touch.
bash scripts/artvee_ops_status.sh

# Full picture — adds online gallery/digest HEAD probes and a
# read-only Pages-repo clean check.
bash scripts/artvee_ops_status.sh --online --include-pages

# Send the report via Telegram + staged MEDIA (same path as the
# daily health check; never sends the raw report path).
bash scripts/artvee_ops_status.sh --online --include-pages --media
```

The `recommended_action` field is a single canonical enum value
that the operator should read first:

| enum | meaning | operator action |
|---|---|---|
| `healthy_no_action` | everything green | nothing |
| `candidate_ready_manual_publish_optional` | both candidates ready, no failures | review + manual publish (see § 9.7) |
| `attention_required_media_pending` | pending MEDIA > 0 | see § 9.6 (replay) |
| `attention_required_pages_content_drift` | online gallery / digest returned 404 | see P7E+2 in § 9.5.x above |
| `attention_required_integrity_failure` | strict integrity FAIL | `python3 scripts/check_gallery_integrity.py --strict` |
| `attention_required_readiness_failure` | readiness FAIL | `python3 scripts/check_open_source_ready.py` |

`known_retired=4` and `quarantined_media_count>0` (a count of
files already archived, not pending) **do not** trigger any failure
action. They are documented state, not signals.

### 9.8. Pages guard visibility (P8A+1)

P8A originally looked for the Pages publish guard **inside the
Artvee repo** and reported `pages_guard_available=false` even
though PAGES-GUARD-1 had already installed the guard in the **Pages
repo** (`conanxin.github.io`). P8A+1 fixes the detection path so
ops status correctly reflects reality.

**How to tell the two states apart**

| Symptom | `pages_guard_available` | `pages.guard_smoke` | What it means |
|---|---|---|---|
| Guard present, smoke passes | `true` | `pass` | PAGES-GUARD-1 is installed and the read-only smoke verifies the Pages repo is clean against the artvee allowlist. **All good — do not act.** |
| Guard present, smoke fails | `true` | `fail` | The guard ran but found a problem (e.g. an untracked change in the Pages repo). Read `pages.guard_smoke_detail.stderr_tail` and `pages.error`; decide whether to follow the recovery procedure in the Pages repo's `docs/PAGES_PUBLISH_GUARD.md`. |
| Guard missing in Pages repo | `false` | `skipped` | The Pages repo does not contain the canonical guard files. The Pages repo is *not* expected to be checked in this state — PAGES-GUARD-1 is required for any Pages publish workflow. |
| Pages repo missing entirely | `false` | `skipped` | `pages.repo_detected=false`. Pass `--pages-repo <pages-repo>` (or set `$ARTVEE_PAGES_REPO` / `$PAGES_REPO`); or clone the Pages repo. |
| `--include-pages` not passed | `false` | `skipped` | The Pages section is opt-in. Re-run with `--include-pages` to populate it. |

**To inspect the Pages section in the JSON report:**

```bash
python3 - <<'PY'
import json
from pathlib import Path

p = sorted(Path('reports/runtime/ops').glob('artvee-ops-status-*.json'))[-1]
data = json.loads(p.read_text(encoding='utf-8'))
pages = data.get('pages', {})
print('pages.guard_available:', pages.get('guard_available'))
print('pages.guard_smoke:    ', pages.get('guard_smoke'))
print('pages.repo_clean:     ', pages.get('repo_clean'))
print('pages.branch:         ', pages.get('branch'))
print('pages.head:           ', pages.get('head'))
print('pages.origin_main:    ', pages.get('origin_main'))
print('pages.resolved_via:   ', pages.get('resolved_via'))
print('pages.error:          ', pages.get('error'))
PY
```

**Pages repo resolution order** (also documented in
`docs/POST_STABLE_OPERATIONS.md` § 7):

1. CLI `--pages-repo <pages-repo>`
2. env `ARTVEE_PAGES_REPO`
3. env `PAGES_REPO`
4. default: `Path.home() / "conanxin.github.io"`

The script never hard-codes an absolute user-home path in
source; the default is `Path.home()` so the path-leak CI gate
continues to pass and the script is portable to other operators.

The command is **strictly report-only** about pending MEDIA. It
never auto-replays. To actually replay, use the dedicated P7B+3
command (see § 9.6). The full field reference and design notes
live in `docs/POST_STABLE_OPERATIONS.md`.

### 9.9. Optional media replay cron (P8D)

P8D adds an **optional** 03:10 cron that flushes deferred MEDIA
*after* the 03:00 daily health cron has had a chance to write
any deferred fallback files. The cron:

* Reuses the staged-only P7B+3 replay flow (same `replay_pending_media.py --apply` + `artvee_telegram_notify.send_text` path the operator uses manually).
* `pending=0` is **silent** — only writes a local summary JSON to `reports/runtime/media-replay/cron-<date>.json`. Never sends a "0 pending" notification. Never spams the operator on healthy days.
* `transport_check` is on by default; if the OpenClaw transport is down, the cron skips replay (pending stays for next run), writes a `skipped_transport_unavailable` summary, and exits 0 — so cron never pages on transport outage either.
* Uses `flock -n` on `reports/runtime/media-replay/.media-replay.lock` to prevent overlapping runs.
* Never triggers download / refill / nightly batch / Pages push / `--approve`. Never retries retired URLs. Never widens the MEDIA allowlist.

**Install (idempotent, marker-block based):**

```bash
cd <artvee-repo>

# Dry-run preview
bash scripts/install_media_replay_cron.sh --dry-run

# Install with defaults (CRON_TZ=Asia/Shanghai, 10 3 * * *, --limit 5, --max-retries 3)
bash scripts/install_media_replay_cron.sh --install

# Custom time
bash scripts/install_media_replay_cron.sh --install --time "15 3 * * *"

# Remove (preserves other blocks: P7B daily-health cron, etc.)
bash scripts/install_media_replay_cron.sh --remove
```

The installer wraps the cron command in a marker block
(`# >>> Artvee P8D media replay cron BEGIN … # <<< Artvee P8D media replay cron END`)
and is fully idempotent — running `--install` twice replaces the
block in-place; `--remove` only deletes the P8D block and leaves
the P7B daily-health cron intact.

**Verify it ran (ops status reads the summary):**

```bash
# After 03:10, ops status will report:
#   Media replay cron installed | True
#   Media replay cron last run | 2026-06-19 (replayed_pending)  (or noop_zero_pending)

bash scripts/artvee_ops_status.sh --no-telegram
```

**Run the wrapper manually:**

```bash
# Dry-run
bash scripts/artvee_media_replay_cron.sh --dry-run

# Apply (same args the cron uses)
bash scripts/artvee_media_replay_cron.sh

# Inspect the summary
cat reports/runtime/media-replay/cron-$(date +%F).json
```

**Why P8D is *optional*** (not in P7B daily-health cron):

The P7B daily-health cron already does a MEDIA-fallback scan as
part of its primary job. P8D is a *follow-up* that flushes
*anything P7B deferred* 10 minutes later, when transport has
had a chance to recover. It is on-demand (default: not
installed) so operators can opt in once they trust the
replay flow. If you don't install it, P8A still reports
`pending_media_count>0` and the operator can replay manually
via § 9.6.

**Safety**:

* Installer has zero secret / chat_id / token output (no env vars baked into the cron command).
* The cron command path is `${HOME}`-relative so it works on any operator's machine.
* The wrapper has no hard-coded user-home paths.
* `flock -n` means even if a slow flush overlaps, only one run touches `reports/runtime/.../replayed/` / `quarantine/` at a time.

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

### 9.10. Classifying next-day notification outcomes (P8D+3)

The 2026-07-01 next-day verification (P8D+3) introduced an
explicit classification of the three failure modes that can
show up in the 01:30 / 02:00 / 03:00 / 03:10 cron logs.
Operators should look at the *combination* of what fired, what
the log says, and what arrived in Telegram, then pick one of
these labels:

| Failure mode | Symptom in log | Telegram arrival | Verdict | Action |
|---|---|---|---|---|
| `notify_config_fail` | `NOTIFY_FAIL: ... chat id not found` (or `binary missing`) | 03:00 text did **not** arrive | **NOT_RECOVERED** | investigate env / config; not a data problem |
| `media_transport_deferred` | `NOTIFY_FAIL: openclaw exit 1 error_kind=transport` only on MEDIA call | 03:00 text arrived; MEDIA did **not** arrive at 03:00 | **WARN_RECOVERED** (pending) | wait for 03:10 replay; do not manually replay unless 03:10 also fails |
| `media_transport_deferred` + 03:10 replay OK | 03:00 deferred log + 03:10 `outcome=replayed_pending` summary JSON | 03:00 text arrived; 03:10 MEDIA arrived with neutral title | **WARN_RECOVERED** (closed) | nothing — this is the expected recovery path |
| `media_transport_deferred` + 03:10 replay also failed | 03:00 deferred log + 03:10 `outcome=skipped_transport_unavailable` (or 03:10 not run) | 03:00 text arrived; MEDIA never arrived | **NOT_RECOVERED** | manually run `bash scripts/artvee_media_replay_cron.sh --apply` after transport is back; check `reports/runtime/media-replay/cron-<date>.json` |

The 2026-07-01 next-day observation fell into row 3: 03:00 text
arrived (message_id=**27647**), 03:00 MEDIA was deferred with
`error_kind=transport`, 03:10 replay cron ran with
`transport_status=ok` and `outcome=replayed_pending`, and 03:10
MEDIA arrived (message_ids **27649** for 2026-06-30 catch-up
and **27650** for 2026-07-01) under the neutral title
`↻ Artvee Daily Health MEDIA replay`. The 01:30 / 02:00
notification regressions were a *separate* symptom — a new
`openclaw binary missing` failure in the cron PATH (tracked
separately, see P8D+4 follow-up); the chat-id resolution from
P8D+2 is verified working.

**Rule**: a 03:00 MEDIA deferral that is closed by a 03:10
replay is *not* a data failure and does **not** require
operator action. A 03:00 MEDIA deferral that 03:10 *cannot*
close (transport still down, or replay outcome is
`skipped_transport_unavailable` / `skipped_locked` /
`error_helper_import` / missing summary) is a real failure and
*does* require operator action. The on-disk
`reports/runtime/media-replay/cron-<date>.json` summary is the
single source of truth for "did 03:10 close the deferral?".

See `docs/MEDIA_REPLAY.md` for the full P8D+3 neutralized-title
contract and the recovered-WARN contract.

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

## 8. Telegram notify troubleshooting (P7A+1 / P8D+2)

If the health check reports `telegram_notify.openclaw_status: missing`,
common causes are:

1. **PATH difference** — cron may not have `$HOME/.local/bin` in PATH.
   Fix: add `export PATH="$HOME/.local/bin:$PATH"` to the cron script,
   or pass `--openclaw-bin <openclaw-bin>` explicitly.
2. **ARTVEE_OPENCLAW_BIN env var** — set it in `.bashrc` or the cron
   environment to an absolute path.
3. **Chat id missing (P8D+2)** — the notifier cannot resolve the Telegram
   chat id. Resolution order:
   - `--chat-id` CLI argument
   - `ARTVEE_TELEGRAM_CHAT_ID` environment variable
   - `$HOME/.config/artvee-gallery/telegram.env` (private env file, chmod 600)
   - `$HOME/.openclaw/openclaw.json` `channels.telegram.defaultChatId`
   - `$HOME/.openclaw/openclaw.json` `channels.telegram.targets[0]`
   
   To fix: create `$HOME/.config/artvee-gallery/telegram.env`:
   ```bash
   mkdir -p $HOME/.config/artvee-gallery
   echo 'ARTVEE_TELEGRAM_CHAT_ID=<your-chat-id>' > $HOME/.config/artvee-gallery/telegram.env
   chmod 600 $HOME/.config/artvee-gallery/telegram.env
   ```
   Then re-run the cron installers so `ARTVEE_TELEGRAM_ENV_FILE` is set
   in the cron environment:
   ```bash
   bash scripts/install_artvee_cron.sh --install
   bash scripts/install_daily_health_cron.sh --install
   ```
   The cron lines will include `ARTVEE_TELEGRAM_ENV_FILE=$HOME/.config/artvee-gallery/telegram.env`
   but will NOT contain the actual chat id (secret hygiene).
4. **Interactive vs cron** — test with `bash scripts/artvee_daily_health_check.sh --no-telegram`
   to confirm the rest of the pipeline works, then debug Telegram separately.
5. **MEDIA path** — reports must be staged to an OpenClaw-allowed directory
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
  ARTVEE_TELEGRAM_ENV_FILE="$HOME/.config/artvee-gallery/telegram.env" \
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
