# MEDIA Replay (P7B+3)

> Artvee Gallery · Pending MEDIA replay workflow
> Authored: 2026-06-18
> Status: **Live** — verified end-to-end with synthetic and real Telegram sends.

## 1. Purpose

When the daily health check cannot deliver the **MEDIA** attachment
(daily report + digest) to Telegram because the OpenClaw gateway
transport (`ws://127.0.0.1:18789`) is overloaded, restarting, or briefly
unreachable, the **text** summary still goes out (P7B+1) and the
deferred **MEDIA** is staged in a per-run *pending file* under
`<artvee-repo>/reports/runtime/`. This document describes how that
pending file is later re-attempted without losing the work, and how
operators can verify or force a replay.

The replay workflow is **read-only with respect to the gallery**
(images / metadata / thumbs / manifest / index / web/data are never
touched). It only re-sends the **staged** MEDIA file via Telegram.

## 2. Failure mode

`scripts/artvee_telegram_notify.py` classifies a notifier failure into:

| error_class | what it means | when we defer |
|---|---|---|
| `transport` | gateway ws timeout, transport error, websocket unreachable, urllib / connection refused | **yes** → write pending |
| `media_allowed` | staged path is not under the OpenClaw allowlist | **no** (config bug, fix path) |
| `binary_missing` | OpenClaw CLI not on PATH | **no** (config bug) |
| `timeout` | openclaw process exceeded wait window | **yes** → write pending |
| `exit_nonzero` | any other non-zero exit | **no** (caller decides) |
| `unknown` | no log content to classify | **no** (default safe) |

A pending file is therefore **only** written when the underlying
problem is *the transport* (recoverable on its own) or *a temporary
process timeout* (also recoverable). We do **not** defer media
delivery when the problem is *configuration* — deferring would just
hide the real issue.

The pending file is named:

```
reports/runtime/<date>/<date_or_health_run_path>/.fallback-pending-<YYYY-MM-DD>.json
```

The actual location is whatever directory the daily health run wrote
its report to. For the canonical cron run this is:

```
reports/runtime/daily-health/.fallback-pending-<YYYY-MM-DD>.json
```

## 3. Pending file schema

```jsonc
{
  "date": "2026-06-18",                       // run date
  "deferred_at": "2026-06-17T23:00:00Z",      // ISO-8601, when we wrote the pending
  "status": "media_transport_deferred",       // taxonomy
  "reason": "transport_timeout",              // free-form cause
  "fallback_text": "(...)",                   // what we already sent as the text-only fallback
  "media_error_kind": "transport",            // matches error_class
  "media_error": "...",                       // short error string
  "raw_report": "reports/runtime/.../artvee-...md",         // NEVER sent (allowlist-locked)
  "staged_report": "<openclaw-media-root>/artvee-reports/artvee-...md",  // only path we will ever send
  "attempts": 0                               // incremented on every replayed attempt
}
```

After a successful replay, the file is moved to
`reports/runtime/daily-health/replayed/` and gains:

```jsonc
{
  ...,
  "attempts": 1,
  "last_attempt_at": "2026-06-18T07:25:21",
  "last_replay_message_id": "25071",
  "last_error": null
}
```

After **max-retries** (default `3`) failed attempts, the file is moved
to `reports/runtime/daily-health/quarantine/` and gains:

```jsonc
{
  ...,
  "attempts": 3,
  "last_error": "(most recent error)",
  "quarantined_at": "2026-06-18T07:25:21",
  "quarantine_reason": "max_retries_reached"
}
```

A sidecar `.replay-result-<date>.json` is written next to the moved
file (in `replayed/` or `quarantine/`) capturing the full outcome
dictionary (no secrets).

## 4. Replay command

```bash
# Default: dry-run (plan + validate only). No Telegram send, no file move.
python3 scripts/replay_pending_media.py

# Real send + archive.
python3 scripts/replay_pending_media.py --apply

# Custom root / retries / limit.
python3 scripts/replay_pending_media.py --apply \
    --pending-root reports/runtime \
    --max-retries 3 \
    --limit 10

# OpenClaw binary override (rare; the notifier usually resolves it).
python3 scripts/replay_pending_media.py --apply --openclaw-bin /usr/local/bin/openclaw
```

The notifier will refuse to send anything that is not under the
OpenClaw media allowlist (`<openclaw-media-root>/...` by default). This is
intentional: replay **must not** bypass P7B+2's allowlist guarantee.

## 5. Retry / quarantine behavior

| condition | outcome | file location |
|---|---|---|
| `attempts < max_retries` and notifier returns 0 | `replayed` (success) | `replayed/` |
| `attempts < max_retries` and notifier returns non-zero | `send_failed_will_retry` (in place; attempts++) | unchanged |
| `attempts >= max_retries` on load | `quarantine_max_retries` | `quarantine/` |
| staged file missing / not under allowlist / symlink / dir | `quarantine_invalid_staged` | `quarantine/` |
| corrupt JSON | `quarantine_corrupt` | `quarantine/` |
| chat id unresolvable | `quarantine_no_chat_id` | `quarantine/` |
| `dry_run=True` (default) | `dry_run` (no send, no move) | unchanged |

In **all** outcomes, the original pending file is **never deleted** —
it is either moved to `replayed/`, moved to `quarantine/`, or written
back in place with `attempts` bumped.

## 6. Why replay is separate from daily health

The 03:00 daily health cron is the **first line of visibility** —
it reports:

```json
"media_replay": {
  "pending": 1,
  "replayable": 1,
  "quarantined": 0,
  "transport_status": "ok"
}
```

It does **not** replay. Replay is a separate step so that:

1. The cron is a read-only probe (no surprise side effects in 03:00 cron).
2. Operators can choose **when** to attempt replay — manually right
   after a transport incident, or via a dedicated 03:10 cron (not
   installed by default; requires explicit `apply`).
3. Replay is bounded: `--limit 10` per run, `--max-retries 3` per
   pending. There is no infinite loop.

The dedicated `scripts/check_openclaw_transport.py` is a **separate**
read-only probe that the daily health run calls and embeds in the
`media_replay.transport_status` field. It runs `openclaw --version`
and a local TCP connect to the gateway port (default `18789`). It
never sends a Telegram message.

## 7. Safety boundaries

The replay workflow is intentionally constrained:

* **Only sends staged paths** under `<openclaw-media-root>/artvee-reports/`
  (or the explicit `--media-root` override). The original
  `raw_report` path is never used.
* **No destructive operations.** The original pending file is always
  preserved (moved, never deleted). `replayed/` and `quarantine/` are
  append-only archives.
* **Bounded retries.** `--max-retries` (default 3) caps attempts per
  pending; `--limit` (default 10) caps pendings per run.
* **No chat-id leakage.** The notifier's `load_chat_id` is reused; no
  id is printed in logs or result sidecars.
* **No transport probing that consumes message budget.** The
  transport probe only runs `openclaw --version` + a TCP connect, no
  Telegram send.
* **No gallery side effects.** Replay never touches `images/`,
  `metadata/`, `thumbs/`, `dist/`, `digests/`, `inbox/`, `web/data/`,
  `index/`, or the `manifest`.

## 8. Operations quick reference

| task | command |
|---|---|
| Are there pending MEDIA? | `find <artvee-repo>/reports/runtime -name '.fallback-pending-*.json' -type f` |
| What's the transport status? | `python3 scripts/check_openclaw_transport.py` (or read `media_replay.transport_status` in latest daily health JSON) |
| Replay all (dry-run) | `python3 scripts/replay_pending_media.py` |
| Replay up to 5 (apply) | `python3 scripts/replay_pending_media.py --apply --limit 5` |
| Inspect a quarantined file | `cat <artvee-repo>/reports/runtime/daily-health/quarantine/.fallback-pending-*.json` |
| See last run results | read `<artvee-repo>/reports/runtime/daily-health/.replay-result-*.json` |

## 9. Related

* `scripts/artvee_telegram_notify.py` — failure classifier
  (`_classify_error`) and notifier.
* `scripts/stage_report_for_telegram_media.py` — produces the
  `staged_report` path that replay is allowed to send.
* `scripts/artvee_daily_health_check.py` — embeds `media_replay`
  block in the daily report.
* `docs/DAILY_OPERATING_PLAYBOOK.md` — operational procedures.
* `docs/RETROSPECTIVE.md` — lesson: transport failures should be
  recoverable, not silent.

## 10. Optional replay cron (P8D)

P7B+3 left replay as a manual workflow. P8D adds an **optional**
cron wrapper that operators can opt into:

```bash
# Preview the cron block that would be added to crontab
bash scripts/install_media_replay_cron.sh --dry-run

# Install with defaults (CRON_TZ=Asia/Shanghai, 10 3 * * *)
bash scripts/install_media_replay_cron.sh --install

# P8D+1: CRON_TZ and PATH are now baked on their own lines above the
# schedule. The earlier template had `CRON_TZ=Asia/Shanghai 10 3 * * *`
# (7 fields) which cron silently rejected — symptom was an empty
# logs/media-replay-cron/ + missing reports/runtime/media-replay/cron-*.json.
# If you see those symptoms on a fresh install, re-run --install; the
# template now produces a parseable 5-field schedule.

# Custom schedule
bash scripts/install_media_replay_cron.sh --install --time "15 3 * * *"

# Remove (preserves P7B daily-health cron, refill, batch, etc.)
bash scripts/install_media_replay_cron.sh --remove
```

**Why "optional" / not "auto-installed"**:

* Pending MEDIA is a *recovery* signal, not a *steady-state*
  signal. Auto-installing the cron would make "0 pending"
  disappear from the operator's view — and a missed replay
  (because the cron failed) would be silent.
* The 03:00 daily-health cron already does a MEDIA-fallback
  scan as part of its primary job. Adding a second cron that
  also touches MEDIA means operators must understand two
  failure surfaces.
* Some operators want to gate replay on manual approval
  (e.g. "I'm going to review each .fallback-pending-*.json
  before sending"). Auto-installing removes that option.

**Wrapper behavior** (`scripts/artvee_media_replay_cron.sh`):

| state | outcome | side effect |
|---|---|---|
| `pending=0` | `noop_zero_pending` | writes `cron-<date>.json` only |
| `pending>0`, transport=ok | `replayed_pending` | runs `replay_pending_media.py --apply` |
| `pending>0`, transport=down | `skipped_transport_unavailable` | writes summary; pending stays for next run |
| flock held by another run | `skipped_locked` | writes summary; pending stays |
| helper import fails | `error_helper_import` | writes summary; pending stays |
| `--dry-run` | `dry_run_completed` | no `--apply`; reports plan |

**Default args**: `--limit 5 --max-retries 3`.

**P8D+1 observability guarantee**: every cron run writes a
`reports/runtime/media-replay/cron-<date>.json` summary regardless
of outcome (`noop_zero_pending`, `replayed_pending`,
`skipped_transport_unavailable`, `skipped_locked`, `dry_run_completed`,
`error_helper_import`). The `--no-op / no Telegram` design is
preserved (no zero-pending notifications), but the local summary
is always written so ops status can detect a *missing* cron run
vs a *silent no-op* cron run. If `cron-<date>.json` is missing
for a day the cron was scheduled to run, treat that as a real
failure (not a no-op).

**Manual run**:

```bash
bash scripts/artvee_media_replay_cron.sh --dry-run
bash scripts/artvee_media_replay_cron.sh --limit 5
bash scripts/artvee_media_replay_cron.sh --max-retries 3
bash scripts/artvee_media_replay_cron.sh --no-transport-check
```

The wrapper always writes a summary JSON. Ops status reads the
latest summary so an operator can confirm the cron ran without
tailing log files.
