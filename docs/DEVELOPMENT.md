
---

## 20. P7A+1 OpenClaw binary resolution

P7A+1 normalizes how the health check (and any other script) finds
the OpenClaw binary for Telegram notification. The goal is to make
Telegram notify work in both cron and interactive shell contexts
without hardcoding paths.

### Resolution order

The `scripts/artvee_telegram_notify.py` resolver tries, in order:

1. **CLI argument** `--openclaw-bin <path-or-command>`
2. **Environment variable** `ARTVEE_OPENCLAW_BIN`
3. **Environment variable** `OPENCLAW_BIN`
4. **PATH lookup** for `openclaw` (via `shutil.which`)
5. **None** — graceful skip, health check continues

### Why this matters

- Interactive shells (e.g., OpenClaw agent sessions) may have
different `PATH` than cron. The resolver tries both env vars and PATH.
- The default `'openclaw'` string is not treated as a valid resolved
path until `shutil.which('openclaw')` confirms it exists in PATH.
- If the binary is missing, the health check **still generates its report**
and exits 0. Telegram notify is skipped with a clear message.

### Usage examples

```bash
# Default: let resolver find openclaw in PATH
bash scripts/artvee_daily_health_check.sh

# Explicit binary path (useful in Docker, CI, or non-standard install)
bash scripts/artvee_daily_health_check.sh --openclaw-bin /usr/local/bin/openclaw

# No Telegram (report only)
bash scripts/artvee_daily_health_check.sh --no-telegram

# With online + media + explicit binary
bash scripts/artvee_daily_health_check.sh --online --media --openclaw-bin <openclaw-bin>
```

### Health check report field

The JSON report now includes a `telegram_notify` object:

```json
{
  "telegram_notify": {
    "enabled": true,
    "media_requested": true,
    "openclaw_status": "resolved",
    "sent": true,
    "message_id": null
  }
}
```

- `openclaw_status`: `resolved` | `missing` | `skipped`
- `sent`: `true` if the message was dispatched, `false` otherwise
- `message_id`: reserved for future enhancement (OpenClaw CLI currently
returns it in stdout, not structured JSON)

### Safety

- No hardcoded absolute paths in source code.
- No token or secret printed in error messages.
- Graceful degradation: missing binary ≠ failed health check.
- The `--openclaw-bin` argument is forwarded through the shell wrapper
to the Python script to the notifier, keeping the resolution logic in
one place (`artvee_telegram_notify.py`).

---

## 21. P7B Daily health cron

P7B installs the daily health check as a cron job that runs at 03:00
Asia/Shanghai, after the nightly batch (02:00) and candidate refresh
(02:30). The cron is idempotent and marker-based.

### Install the cron

```bash
bash scripts/install_daily_health_cron.sh --install
```

This adds a marker-delimited block to the user's crontab:

```
# >>> Artvee P7B daily health check BEGIN
# Artvee Daily Health Check (P7B)
0 3 * * * cd <repo-dir> && bash scripts/artvee_daily_health_check.sh --online --media >> logs/daily-health-cron/daily_health_$(date +\%Y\%m\%d)_030000.log 2>&1
# <<< Artvee P7B daily health check END
```

### Remove or modify the cron

```bash
# Remove the P7B block
bash scripts/install_daily_health_cron.sh --remove

# Change the time (e.g., to 09:00)
bash scripts/install_daily_health_cron.sh --install --time "0 9 * * *"
```

### Idempotency

Running `--install` twice replaces the existing block rather than
adding a duplicate. The script uses `sed` to remove the old block
before appending the new one.

### Safety

- The installer does not modify the Artvee repo (no data changes).
- It does not trigger downloads, refills, or batches.
- It backs up the crontab before modification (`logs/daily-health-cron/crontab.before_p7b.*.txt`).
- It does not print tokens, secrets, or chat IDs.

---

## 22. P7B+1 Telegram delivery state model + failure-only fallback

P7B+1 refactors the daily health check's Telegram reporting so that
**text summary**, **MEDIA attachment**, and **fallback** are independent
tracks. A MEDIA failure is observable but no longer silent.

### State model (JSON, in `reports/runtime/daily-health/*.json`)

```json
{
  "telegram": {
    "requested": true,
    "openclaw_status": "resolved | missing | skipped",
    "text_summary": {"attempted": true, "sent": true, "message_id": "22811", "error": null},
    "media": {
      "requested": true,
      "staged": true,
      "staged_path": "$HOME/.openclaw/media/artvee-reports/...",
      "sent": true,
      "message_id": "22813",
      "error": null,
      "simulated_failure": false
    },
    "fallback": {"attempted": false, "sent": false, "message_id": null, "reason": null}
  }
}
```

| Field | Type | Notes |
|-------|------|-------|
| `telegram.openclaw_status` | enum | `resolved` if notifier could start; `missing` if binary absent; `skipped` if `--no-telegram`. |
| `telegram.text_summary.sent` | bool | Whether the short ✅/❌ block was delivered. |
| `telegram.text_summary.message_id` | str | Telegram message id parsed from the notifier's log. |
| `telegram.media.staged_path` | str | Absolute path inside the OpenClaw allowlist (default root `$HOME/.openclaw/media/`). |
| `telegram.media.simulated_failure` | bool | True only when `--simulate-media-failure` was used (testing). |
| `telegram.fallback.reason` | enum | Currently only `media_failed`. |

### Failure-only fallback

When all of the following hold:

- `checks.integrity.status == "PASS"`
- `checks.readiness.status == "PASS"`
- `telegram.text_summary.sent == true`
- `telegram.media.sent == false` and `telegram.media.error != null`

…a single short text fallback is sent:

```
⚠️ Artvee Daily Health MEDIA failed
Date: YYYY-MM-DD
Health: PASS
Text summary: sent
MEDIA: failed
Report: <report-md-path>
Action: no data issue; check media delivery
```

Guarantees:

- Sent at most **once** per run.
- Never recurses (the fallback path does not call the health check).
- Does not change the script's exit code unless health itself failed.

### `--simulate-media-failure` (testing only)

To verify the fallback chain without breaking the real MEDIA allowlist:

```bash
cd <artvee-repo>
bash scripts/artvee_daily_health_check.sh --online --media --simulate-media-failure
```

This forces `media.sent=false` with `error=simulated_failure` and triggers
the fallback. **Do not** use this in cron; it is for one-off testing.

### How to inspect any day's Telegram status

```bash
# After a run:
python3 -c "
import json
d = json.load(open('reports/runtime/daily-health/artvee-daily-health-2026-06-13.json'))
print(json.dumps(d['telegram'], indent=2, ensure_ascii=False))
"
```

### Chat id resolution (P7B+1: no hardcoded ids in the repo)

`scripts/artvee_telegram_notify.py` resolves the chat id in this order:

1. `--chat-id` CLI argument
2. `ARTVEE_TELEGRAM_CHAT_ID` environment variable
3. `channels.telegram.defaultChatId` in `$HOME/.openclaw/openclaw.json`
4. `channels.telegram.targets[0]` in the same file
5. Hard error (no fallback to a literal id in source)

The cron installer bakes `ARTVEE_TELEGRAM_CHAT_ID` into the cron block
when the installer is run with that env var set. To re-install with a
new chat id, simply re-export and re-run the installer.

```bash
ARTVEE_TELEGRAM_CHAT_ID="<telegram-chat-id>" \
  bash scripts/install_daily_health_cron.sh --install
```

---

## 23. v0.2.0-alpha release checklist

This section is the in-repo runbook for cutting a release. It is
intentionally short and idempotent: every step is reproducible from
a clean clone + a working local data directory.

### Pre-flight
```bash
cd <artvee-repo>
git status --short                     # only runtime / untracked files; no in-progress edits
git log --oneline -3                   # HEAD is the release commit
git remote -v                          # origin = github.com/conanxin/artvee-gallery
```

### Build / readiness gates
```bash
python3 -m py_compile scripts/*.py
for s in scripts/artvee_daily_health_check.sh scripts/install_daily_health_cron.sh \
         scripts/confirm_demo_refresh.sh scripts/publish_demo_refresh_candidate.sh \
         scripts/artvee_nightly_wrapper.sh; do bash -n "$s"; done
python3 scripts/check_open_source_ready.py
python3 scripts/check_gallery_integrity.py --strict
python3 scripts/build_artvee_status_report.py \
  --out-json reports/runtime/artvee-status-report.json \
  --out-md reports/runtime/artvee-status-report.md
bash scripts/artvee_daily_health_check.sh --no-telegram
```

All six checks must pass. `git ls-files` must not show any tracked
runtime files; `grep` over the docs / source must not produce
real local paths, tokens, or chat ids.

### Create the tag and GitHub Release
```bash
# Tag (annotated, on the release commit)
git tag -a v0.2.0-alpha -m "Artvee Gallery v0.2.0-alpha"
git push origin v0.2.0-alpha

# GitHub Release (idempotent: re-running with the same tag fails loudly)
gh release view v0.2.0-alpha >/dev/null 2>&1 \
  || gh release create v0.2.0-alpha \
       --title "Artvee Gallery v0.2.0-alpha" \
       --notes-file docs/RELEASE_NOTES_v0.2.0-alpha.md
```

### Public demo verification
```bash
curl -I https://conanxin.github.io/projects/artvee-gallery-demo/
curl -I https://conanxin.github.io/projects/artvee-gallery-digest/
gh repo view conanxin/artvee-gallery --json name,visibility,url,defaultBranchRef
git ls-remote --tags origin v0.2.0-alpha
gh release view v0.2.0-alpha --json tagName,name,url,isPrerelease
```

### Safety rails
- The release commit must not include `images/`, `metadata/`,
  `thumbs/`, `dist/`, `digests/`, `logs/`, `inbox/`, `web/data/*.json`,
  `index/`, `reports/runtime/`, or `tmp/`.
- The release commit must not include tokens, chat ids, bot
  tokens, or real local paths in tracked files.
- The release must not trigger a download, refill, batch, or
  `publish_demo_refresh_candidate.sh --approve`. The publish
  step is always manual.

---

## 24. P7E+2 Online-check HTTPError / URLError semantics

P7E+1 (2026-06-15) found that the daily health check's online check
(`scripts/artvee_daily_health_check.py:200-219`) was masking a
content-drift incident as a network failure. The old code:

```python
try:
    gcode = urllib.request.urlopen(gallery_url, timeout=30).getcode()
    dcode = urllib.request.urlopen(digest_url,  timeout=30).getcode()
except Exception:
    gcode, dcode = 0, 0
```

collapsed *all* errors into `0, 0` — including `urllib.error.HTTPError`,
which is a *response* (404, 403, 500) and not a *transport* failure.
When a `--online` cron run then reports `Online: gallery=0, digest=0`,
the operator cannot tell whether the public site is unreachable (DNS
/ TLS / timeout) or simply missing the path (404).

P7E+2 splits the error handling so the two cases are distinguishable.

### 24.1 Three failure kinds, two numeric codes

| `online.kind`     | `gallery_http_code` | `gallery_error`                              | meaning                                    |
|-------------------|---------------------|----------------------------------------------|--------------------------------------------|
| `ok`              | `200`               | `null`                                       | both endpoints reachable, 200 OK           |
| `http_error`      | real code (`404`)   | `"HTTPError 404 Not Found"`                  | endpoint reachable, but path is wrong / removed / drift |
| `network_error`   | `0`                 | `"URLError [Errno -2] Name or service not known"` (or `"timeout/connection: ..."`) | DNS / TLS / connection refused / timeout / Pages down |
| `skipped`         | n/a                 | n/a                                          | `--online` was not passed                  |

### 24.2 Implementation

The new code is a small private helper:

```python
def _probe(url):
    """Return (http_code:int, kind:str, error:str|None)."""
    import urllib.request, urllib.error
    try:
        resp = urllib.request.urlopen(url, timeout=30)
        return (resp.getcode(), "ok", None)
    except urllib.error.HTTPError as e:
        return (e.code, "http_error", f"HTTPError {e.code} {e.reason}")
    except urllib.error.URLError as e:
        return (0, "network_error", f"URLError {e.reason}")
    except (TimeoutError, ConnectionError) as e:
        return (0, "network_error", f"timeout/connection: {e}")
    except Exception as e:
        return (0, "network_error", f"{type(e).__name__}: {e}")
```

Each endpoint is probed independently. The aggregate `online.kind` is
`ok` only if both are `ok`; otherwise it is `network_error` if either
is `network_error`; otherwise `http_error`.

### 24.3 Recommended action branches

The action label is now chosen by priority: an online FAIL beats any
internal check, and the kind shapes the wording.

| Condition                                | `recommended_action`                              |
|------------------------------------------|---------------------------------------------------|
| `online.status == "FAIL"` and `http_error` | `attention_required_pages_content_drift`         |
| `online.status == "FAIL"` and `network_error` | `attention_required_network_or_pages_unreachable` |
| `online.status == "FAIL"` (other)        | `attention_required_online_check`                 |
| internal integrity/readiness FAIL         | `attention_required`                              |
| gallery_ready AND digest_ready            | `candidate_ready_manual_publish_optional`        |
| otherwise                                 | `healthy_no_action`                               |

### 24.4 Backward compatibility

- The legacy `online.gallery_http_code` and `online.digest_http_code`
  fields are still present. For pre-fix reports they were `0` on
  every error; for post-fix reports they are the real code (200, 404,
  0, etc.). The Telegram summary template still emits
  `Online: gallery={gcode}, digest={dcode}`, but the meaning of
  `0` is now narrower: it means *transport failure only*.
- The legacy `online.details` field is still present, but its
  wording now distinguishes `http_error` from `network_error`.
- The legacy `recommended_action` strings (`healthy_no_action`,
  `candidate_ready_manual_publish_optional`, `attention_required`)
  are unchanged. The two new action strings are additive
  (`attention_required_pages_content_drift`,
  `attention_required_network_or_pages_unreachable`,
  `attention_required_online_check`).

### 24.5 Test recipes

| Test                                            | Expected                                                              |
|-------------------------------------------------|-----------------------------------------------------------------------|
| `bash scripts/artvee_daily_health_check.sh --online --no-telegram` (when sites are live) | `kind=ok`, `gallery_http_code=200`, `digest_http_code=200`, `action=candidate_ready_manual_publish_optional` |
| Synthetic 404: `urllib.request.urlopen("https://conanxin.github.io/projects/nonexistent-artvee-12345/")` | `(404, "http_error", "HTTPError 404 Not Found")` |
| Synthetic network: `urllib.request.urlopen("https://nonexistent-host-artvee-12345.invalid/")` | `(0, "network_error", "URLError [Errno -2] Name or service not known")` |

### 24.6 Lessons

- **Bare `except Exception` is a debugging anti-pattern in any code
  path that maps an exception to a status code.** It hides the
  semantic difference between "the server said no" and "we never
  reached the server". Always prefer at minimum
  `except urllib.error.HTTPError:` and `except urllib.error.URLError:`.
- **Cron + Telegram amplifies signal-distortion bugs.** Because the
  daily health summary is the operator's only glance, a 0/0 mask
  means *the operator is debugging in the dark* — even when the
  underlying data is fine. The lesson is to make every numeric
  field in the report truthful, even at the cost of a slightly
  noisier report.
- **Separate "transport failure" from "application-layer failure"**
  in any health check. They imply different fix paths:
  `network_error` → check DNS / Pages status; `http_error` → check
  path / namespace drift / explicit removal.

---

## 23. P7B+2 Staged-only MEDIA + transport-deferred fallback

P7B+2 closes the regression where a 2026-06-18 03:00 daily health
run saw `MEDIA: failed` even though the report was *already
correctly staged* into an OpenClaw-allowlisted directory. The
root cause was a transient `GatewayTransportError: gateway timeout
after 10000ms` on the local OpenClaw gateway, not a path problem
— but the original reporting collapsed both into a generic
`openclaw exit 1` and the fallback text still pointed operators at
the raw `reports/runtime/daily-health/...` path, making the
investigation misleading.

### Three small changes

1. **`stage_report_for_telegram_media.py --print-meta`** — emits a
   single-line JSON object with both `raw_report` and
   `staged_report`, plus `stage_failed`, `staged_size`,
   `media_root`, and an `error` string. The caller no longer has to
   parse a freeform path from stdout. If staging itself fails, the
   JSON is still emitted (with `stage_failed=true`) and the helper
   returns exit code 1.

2. **artvee_daily_health_check.py**: media is now **staged-only**.
   If `--print-meta` reports `stage_failed`, MEDIA is recorded as
   failed and we never attempt to attach the raw path. The raw
   path is recorded in `telegram.media.raw_report` so the report
   itself remains diagnosable. The fallback text now reports
   `raw_report`, `staged_report`, and `media_error` as separate
   lines so operators do not have to grep the JSON.

3. **Transport-deferred fallback**: if MEDIA fails with
   `error_kind=transport` (gateway ws timeout / unreachable), the
   fallback is *not* sent immediately. Instead we write a
   `.fallback-pending-YYYY-MM-DD.json` next to the report and
   `telegram.fallback.reason="media_transport_deferred"`. The
   *next* run, if its `text_summary` succeeds (proving the
   gateway is healthy again), flushes that pending file exactly
   once and unlinks it. This avoids burning 10-180s of cron time
   re-hitting the same gateway timeout for a fallback that would
   have failed anyway.

### Failure-mode taxonomy (P7B+2)

| `media.error_kind`     | `fallback.reason`              | Behaviour |
|------------------------|--------------------------------|-----------|
| `null` (success)       | `null`                         | normal: media sent, no fallback |
| `simulated`            | `media_failed`                 | simulate path, fallback sent (test only) |
| `stage_failed`         | `stage_failed`                 | staging helper error; fallback sent once with `stage_failed` reason |
| `media_allowed`        | `media_failed`                 | allowlist rejection; fallback sent once |
| `binary_missing`       | `media_failed`                 | openclaw not on PATH; fallback sent once |
| `exit_nonzero`         | `media_failed`                 | unknown send failure; fallback sent once |
| `timeout`              | `media_failed`                 | openclaw process timeout; fallback sent once |
| `transport`            | `media_transport_deferred`     | gateway unreachable; **fallback deferred to local file** |

### Manual staging test

```bash
# Show the would-be staged path (no copy)
python3 scripts/stage_report_for_telegram_media.py \
  --report reports/runtime/daily-health/artvee-daily-health-2026-06-18.md \
  --check-only
# → WOULD_STAGE ${HOME}/.openclaw/media/artvee-reports/artvee-daily-health-2026-06-18.md

# Stage and emit the JSON metadata envelope
python3 scripts/stage_report_for_telegram_media.py \
  --report reports/runtime/daily-health/artvee-daily-health-2026-06-18.md \
  --print-meta
# → {"ok":true,"stage_failed":false,"raw_report":"...","staged_report":"...","staged_size":1651,...}

# Negative test
python3 scripts/stage_report_for_telegram_media.py \
  --report reports/runtime/daily-health/does-not-exist.md --print-meta
# → {"ok":false,"stage_failed":true,...,"error":"FileNotFoundError: ..."}  (exit 1)
```

See `docs/DAILY_OPERATING_PLAYBOOK.md` § 9.5 for the daily
operating diagnosis flow.

## 24. P7B+3 Pending MEDIA replay + transport health

P7B+3 closes the final gap from P7B+2: the transport-deferred
fallback file (`.fallback-pending-*.json`) was previously flushed
opportunistically by the *next* daily health run. That coupled
recovery to a cron, hid what was actually happening, and gave
operators no clean way to inspect or trigger a replay. P7B+3
replaces that with a dedicated, read-only-by-default workflow.

### Three new pieces

1. **`scripts/replay_pending_media.py`** — scan, validate, and
   re-send pending MEDIA. Default is **dry-run** (no send, no
   file move); pass `--apply` to actually send. Always archives
   the original pending file (never deletes) to either
   `replayed/` (success) or `quarantine/` (max-retries / invalid
   staged path / no chat id / corrupt JSON).

   ```bash
   # Plan only (default; no Telegram send, no file move).
   python3 scripts/replay_pending_media.py

   # Real replay, bounded.
   python3 scripts/replay_pending_media.py --apply --limit 10 --max-retries 3

   # Custom OpenClaw binary + custom pending root.
   python3 scripts/replay_pending_media.py --apply \
       --openclaw-bin /usr/local/bin/openclaw \
       --pending-root reports/runtime
   ```

   All work is bounded by `--limit` (default 10) and
   `--max-retries` (default 3). The original pending file is
   preserved on disk in either `replayed/` or `quarantine/`; a
   `.replay-result-<date>.json` sidecar captures the full
   outcome (no secrets, no chat id).

2. **`scripts/check_openclaw_transport.py`** — a separate,
   read-only CLI probe. Runs `openclaw --version` and a local
   TCP connect to `127.0.0.1:18789` (overridable). Emits a
   single JSON document with `status` / per-probe latency /
   `error_class`. **Never sends a Telegram message**, so it is
   safe to call from cron, from the daily health check, or
   interactively.

   ```bash
   python3 scripts/check_openclaw_transport.py
   python3 scripts/check_openclaw_transport.py --extended --text
   python3 scripts/check_openclaw_transport.py --openclaw-bin /opt/openclaw/bin/openclaw
   ```

3. **`artvee_daily_health_check.py`** — embeds a new
   `media_replay` block in the daily report JSON. The cron does
   **not** auto-replay; it just *reports*. The `media_replay`
   block includes:

   ```json
   "media_replay": {
     "pending": 0,
     "replayable": 0,
     "quarantined": 1,
     "transport_status": "ok",
     "transport_error_class": "",
     "transport_latency_ms": 41,
     "transport_checked_at": "2026-06-18T07:25:29",
     "transport_limited_cli": true
   }
   ```

   The scan explicitly excludes `replayed/` and `quarantine/`
   subdirectories so archived files are not double-counted.

### Why this is separate from the daily health cron

* The 03:00 cron is now strictly **read + report**. No surprise
  side effects, no extra Telegram sends beyond the canonical
  daily report + digest.
* Recovery is **explicit** — operators (or a separate 03:10 cron,
  not installed by default) decide when to attempt replay.
* The transport probe runs on every daily health check at near-
  zero cost (a subprocess and a TCP connect) and gives at-a-
  glance visibility into whether the gateway is healthy.

### Manual end-to-end test (replay)

```bash
# 1. Build a tiny staged report.
mkdir -p reports/runtime/daily-health
cat > reports/runtime/daily-health/artvee-pending-replay-test.md <<EOF
# Artvee Pending MEDIA Replay Test
This is a small staged report replay test.
EOF
STAGED=$(python3 scripts/stage_report_for_telegram_media.py \
    --report reports/runtime/daily-health/artvee-pending-replay-test.md)

# 2. Write a synthetic pending JSON.
python3 - <<PY
import json
from pathlib import Path
p = Path('reports/runtime/daily-health/.fallback-pending-test.json')
p.write_text(json.dumps({
    "date": "2026-06-18",
    "deferred_at": "2026-06-17T23:30:00Z",
    "status": "media_transport_deferred",
    "reason": "test_pending_replay",
    "raw_report": "reports/runtime/daily-health/artvee-pending-replay-test.md",
    "staged_report": "$STAGED",
    "attempts": 0,
}, indent=2), encoding='utf-8')
print(p)
PY

# 3. Replay (dry-run first, then apply).
export ARTVEE_TELEGRAM_CHAT_ID='<telegram-chat-id>'
python3 scripts/replay_pending_media.py --dry-run --limit 5
python3 scripts/replay_pending_media.py --apply --limit 1
# → [replayed] pending=... message_id=<n>
#   pending file moved to reports/runtime/daily-health/replayed/
#   sidecar .replay-result-*.json written.
```

See `docs/MEDIA_REPLAY.md` for the full schema and operations
quick-reference.

## 25. P8A Post-stable ops status command

After v0.2.0 stable, the operator needs one command that answers
*"is everything OK right now?"* without waiting for the 03:00 cron.
That command is `scripts/artvee_ops_status.sh` (shell wrapper around
`scripts/artvee_ops_status.py`).

### Design

* **Single read-only aggregator.** It does not download, refill, run
  nightly batch, push Pages, approve candidates, or replay pending
  MEDIA. It only reads state already on disk and (optionally) probes
  public URLs with `curl --head`.
* **Reuses existing helpers instead of duplicating logic.** It calls:
  * `artvee_status_report.json` for `records` / `known_retired` /
    `blocking_unresolved` / `unresolved_phase`.
  * The latest `artvee-daily-health-*.json` for `readiness` /
    `integrity` / `candidate_state` / `digest_history` /
    `near_dup_clusters` / `nightly_batch` / `latest_health_*`.
  * `artvee_daily_health_check._scan_pending_media` (imported
    directly) for `pending_media_*` and `quarantined_media_count`
    so counts never drift from what the cron reports.
  * `check_openclaw_transport.py` for `transport_status` /
    `transport_latency_ms` (no Telegram message, no side effect).
  * `crontab -l` for `daily_health_cron_installed`.
  * `stage_report_for_telegram_media.stage_report` +
    `artvee_telegram_notify.send_text` for the optional `--media`
    send. The MD report is **always** staged via the same path
    the daily health check uses; the raw report path is never
    passed to `openclaw message send` (this preserves the P7B+2
    staged-only invariant).
* **One canonical `recommended_action` enum.** First-match-wins
  priority: `integrity_failure` > `readiness_failure` > `pages_drift`
  > `media_pending` > `candidate_ready` > `healthy`. The enum is
  *stable*; adding values requires a docs + script change.
* **Pages guard is read-only.** Reports `pages_guard_available`
  based on file presence only. With `--include-pages`, runs
  `git status --porcelain` in the Pages repo and reports
  `true|false|unknown`. Never runs `rsync`, never commits, never
  pushes, never executes the destructive half of any guard script.

### Why this is a separate command, not a cron

* The 03:00 daily health cron already covers continuous monitoring
  (Telegram fallback, pending MEDIA scan, transport probe, online
  checks). Adding a 06:00 ops status cron would mostly duplicate
  that — and the values rarely change between 03:00 and 06:00.
* The ops status command is for **operator review** at the
  keyboard. It runs on demand, gives a one-page Markdown report
  to look at, and is gone.
* If a future "morning briefing" cron is desired, it can simply
  wrap this command with `--date $(date +%F) --media`. That is
  explicitly out of scope for v0.2.x.

### End-to-end test (real Telegram send)

```bash
export ARTVEE_TELEGRAM_CHAT_ID='<telegram-chat-id>'

# 1. No-Telegram default.
bash scripts/artvee_ops_status.sh --online --include-pages
# → records=875 retired=4 blocking=0 integrity=PASS readiness=PASS
#   pending_media=0 transport=ok action=candidate_ready_manual_publish_optional

# 2. Real send (verified message_id=25149, 2026-06-18).
bash scripts/artvee_ops_status.sh --online --include-pages --media
# → telegram: ok=True status=ok message_id=25149
```

See `docs/POST_STABLE_OPERATIONS.md` for the full field reference,
recommended-action enum, troubleshooting, and "what not to automate
yet" list.
