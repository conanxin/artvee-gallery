# MEDIA Replay (P7B+3)

> Artvee Gallery · Pending MEDIA replay workflow
> Authored: 2026-06-18
> Updated: 2026-07-04 (P8D+4B: pending scope cleanup — active vs terminal vs backup buckets)
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

After a successful replay, the file is moved to the **stable**
`reports/runtime/media-replay/replayed/` root (see § 11 P8D+4) and
gains:

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
to the **stable** `reports/runtime/media-replay/quarantine/` root and
gains:

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
file inside `reports/runtime/media-replay/results/` (the new
**aggregate** JSON is `.replay-results-<date>.json` and contains the
full `results` list — see § 11). No secrets.

## 5. Retry / quarantine behavior

| condition | outcome | file location |
|---|---|---|
| `attempts < max_retries` and **notifier returns a non-empty `message_id`** | `delivered` (success) | `media-replay/replayed/` (stable root) |
| `attempts < max_retries` and notifier exits 0 but `message_id` is empty | `send_failed_will_retry` (in place; attempts++) | unchanged |
| `attempts < max_retries` and notifier returns non-zero exit | `send_failed_will_retry` (in place; attempts++) | unchanged |
| `attempts >= max_retries` on load | `quarantine_max_retries` | `media-replay/quarantine/` (stable root) |
| staged file missing / not under allowlist / symlink / dir | `quarantine_invalid_staged` | `media-replay/quarantine/` |
| corrupt JSON | `quarantine_corrupt` | `media-replay/quarantine/` |
| chat id unresolvable | `quarantine_no_chat_id` | `media-replay/quarantine/` |
| `dry_run=True` (default) | `dry_run` (no send, no move) | unchanged |

In **all** outcomes, the original pending file is **never deleted** —
it is either moved to `media-replay/replayed/`, moved to
`media-replay/quarantine/`, or written back in place with `attempts`
bumped.

### Truth of `delivered`

P8D+4 enforces: a replay is recorded as **`delivered`** only when
`artvee_telegram_notify.send_text` returns `ok=True` **and** a
non-empty `message_id` was parsed from the OpenClaw journal/send
result. Exit code 0 alone is **not** sufficient — the OpenClaw
journal entry looks like
`... outbound send ok ... messageId=<digits> ...` and
`_extract_message_id` uses these regexes
(`Message ID:`, `MessageId`, `messageId`, `message_id`) to find it.
If `ok=True` but no `message_id` was parseable, the outcome is
recorded as `send_failed_will_retry` with
`last_error = "openclaw exit 0 but no message_id parsed from log
(treated as undelivered)"`, attempts++, and the file **stays in
place** — not in `replayed/`.

## 11. P8D+4: stable roots + delivery truthfulness (2026-07-03)

Before P8D+4 the per-pending archive path was built by joining the
current pending file's parent directory with `replayed/` or
`quarantine/`. Replays run inside `replayed/` produced
`replayed/replayed/`, and after 5 days deep nesting reached 6
levels (`quarantine/quarantine/quarantine/...`) and would have
climbed to `PATH_MAX=4096` within weeks.

P8D+4 fixes this with three **stable** archive roots:

| directory | role |
|---|---|
| `reports/runtime/media-replay/pending/` | active pending queue (when `attempts < max_retries` and not yet sent) |
| `reports/runtime/media-replay/replayed/` | **delivered** (non-empty `message_id`) |
| `reports/runtime/media-replay/quarantine/` | terminal failures (`max_retries` reached, invalid staged, corrupt JSON, chat id unresolvable) |
| `reports/runtime/media-replay/results/` | aggregate JSON `.replay-results-<date>.json` (full `results` list, `message_ids`) |

The archive path is no longer derived from `pending_path.parent`;
`_archive_dir(root, name)` in `scripts/replay_pending_media.py`
always anchors to `reports/runtime/media-replay/<name>/`. Test-only
overrides (a temp `--pending-root`) still fall through to
`root/<name>` so unit tests can exercise the logic.

The cron wrapper `scripts/artvee_media_replay_cron.sh` now reads
from the aggregate JSON — never from guessing per-pending sidecars.
Its `outcome` enum reflects actual delivery:

| aggregate reads | cron `outcome` |
|---|---|
| aggregate JSON missing / unreadable | `replay_no_results` |
| `totals.delivered > 0` | `replayed_delivered` |
| `totals.delivered == 0` and `totals.quarantined > 0` | `quarantine_exhausted` |
| `totals.delivered == 0` and `totals.send_failed_will_retry > 0` | `replay_failed` |
| `pending_before == 0` | `noop_zero_pending` |
| transport check failed with `pending > 0` | `skipped_transport_unavailable` |
| dry-run completed | `dry_run_completed` |

`replay_message_ids` now reflects real Telegram delivery because it
is sourced from the aggregate JSON's `message_ids` array.

### Queue normalization (one-time, 2026-07-03)

Pre-fix files nested in
`reports/runtime/daily-health/{replayed,quarantine}/{replayed,quarantine}/...`
were moved to the stable roots above. Classification used
`last_replay_message_id` (`delivered`) vs. `attempts` and
`quarantine_reason` (`quarantined`) vs. neither (`pending`). All
originals were first copied to
`reports/runtime/media-replay/queue-fix-backup-YYYYMMDD-HHMMSS/`
(20 files, 152K) — nothing was deleted.

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

**P8D+3 user-facing title**: the replay message Telegram title is
`↻ Artvee Daily Health MEDIA replay` (changed 2026-07-01). The
earlier `↻ Artvee Gallery P7B+3 deferred MEDIA replay` carried a
stale phase label that no longer reflected the active phase
hierarchy (replay is now P7B+3 → P8D → P8D+1, with P8D+2 chat-id
hardening, plus the optional 03:10 cron). P8D+3 neutralizes the
title so it stays accurate regardless of which later phase is
active. P7B+3 remains the *historical* source of the workflow in
this doc and in the changelog, but the user-visible Telegram copy
no longer carries the phase tag. The staged report contents, the
pending-file schema, and the replay behavior are unchanged.

**P8D+3 recovered-WARN contract**: a *delayed* MEDIA delivery is
not a data failure. The normal recovery path is:

1. 03:00 daily health text is sent (Telegram message_id recorded
   in `telegram_notify.message_id`).
2. 03:00 MEDIA is **deferred** because the OpenClaw transport
   is briefly unhealthy (gateway timeout / websocket error).
   The deferral writes
   `reports/runtime/daily-health/.fallback-pending-<date>.json`
   and `telegram.fallback.reason = media_transport_deferred`.
3. 03:10 media-replay cron runs `check_openclaw_transport.py`
   (transport is back to `ok`).
4. 03:10 replay cron hands off to `replay_pending_media.py --apply`
   which re-attaches the staged report.
5. 03:10 Telegram message arrives with the neutral
   `↻ Artvee Daily Health MEDIA replay` title and the
   `Date` / `Reason` / `Action` body.

This sequence is the **expected** behavior for a transient
transport blip. Operators should classify it as
`WARN_RECOVERED` (transport blip → deferred → replayed within
10 minutes) and **not** as a `NOTIFY_FAIL` data failure. The
text summary already landed; the MEDIA just got there 10 minutes
late. P8D+3 makes this contract explicit in
`docs/DAILY_OPERATING_PLAYBOOK.md` § 9.10.

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

## 12. P8D+4B: pending scope cleanup (2026-07-04)

The **active pending** scope is now strictly defined. Anything that
is *not* an actionable pending file is bucketed separately in the
cron summary so the alarm threshold (``pending_before > 0``) is never
falsely tripped by terminal state or historical backups.

### Active pending root (the only thing that drives ``pending_before``)

* ``reports/runtime/media-replay/pending/`` — top-level active queue
* ``reports/runtime/daily-health/.fallback-pending-*.json`` —
  top-level only (not nested under ``replayed/`` or ``quarantine/``)

### Non-active buckets (counted, but never trigger ``pending_before``)

| bucket | path | meaning |
|---|---|---|
| ``terminal_replayed`` | ``media-replay/replayed/*.json`` | already delivered (non-empty Telegram ``message_id``); append-only archive |
| ``terminal_quarantine`` | ``media-replay/quarantine/*.json`` | delivery exhausted (``max_retries`` reached, invalid staged, corrupt JSON); append-only archive |
| ``ignored_results`` | ``media-replay/results/.replay-results-*.json`` | aggregate JSON sidecars (not pending) |
| ``ignored_backup`` | any segment containing ``queue-fix-backup-``, ``legacy-cleaned``, ``stable_dup`` | historical snapshots from earlier queue-normalization runs (P8D+4) and P8D+4B cleanup |
| ``nested_legacy`` | any path segment with self-recursive ``replayed/replayed`` or ``quarantine/quarantine`` | pre-P8D+4 nesting pathology (now archived under ``legacy-cleaned/``) |

### Cron summary semantics

When the scanner succeeds and there is **no** active pending:

```jsonc
{
  "outcome": "no_pending",         // was "noop_zero_pending" pre-P8D+4B; renamed for clarity
  "pending_before": 0,
  "active_pending": 0,
  "active_replayable": 0,
  "terminal_replayed": N,          // historical record
  "terminal_quarantine": N,        // historical record
  "ignored_results": N,
  "ignored_backup": N,
  "nested_legacy": 0,
  "unknown_non_active": 0,
  "scan_error": ""
}
```

``pending_before`` and ``active_pending`` are **aliases** post-P8D+4B
(they must always be equal for a healthy run). The cron wrapper
passes ``reports/runtime`` (the canonical runtime root) to the
scanner, so the scan path is now identical between the cron wrapper
and ``artvee_ops_status._scan_pending_media``.

### Why the rename ``noop_zero_pending`` → ``no_pending``?

The pre-P8D+4B label was ambiguous: it read like a successful
"zero-action" outcome but the *cause* was hidden inside
``pending_before``. After scope cleanup the bucket layout is
explicit, so the new name describes the actual state of the queue
rather than the absence of side-effects. ``noop_zero_pending`` is
still emitted (as the aggregate outcome inside
``replay_pending_media.py`` when there is nothing to do) but the
cron wrapper emits the stricter ``no_pending`` so downstream
consumers can distinguish "nothing to do" from "tool wasn't reached".

### Migration: the 2026-07-04 cleanup (one-time)

A manual cleanup on 2026-07-04 moved all non-actionable
``.fallback-pending-*.json`` files into
``reports/runtime/media-replay/legacy-cleaned/20260704/``:

| from | to |
|---|---|
| ``media-replay/queue-fix-backup-20260703-062946/stable_dup/`` | ``legacy-cleaned/20260704/queue-fix-backup-20260703-062946/stable_dup/`` |
| ``daily-health/replayed/`` (and the nested pathology inside) | ``legacy-cleaned/20260704/daily-health/replayed/`` |
| ``daily-health/quarantine/`` (and the nested pathology inside) | ``legacy-cleaned/20260704/daily-health/quarantine/`` |

A full backup of all ``.fallback-pending-*.json``,
``.replay-result-*.json``, ``.replay-results-*.json``,
``.quarantine-*.json`` and ``.media-replay.lock`` files was written
to ``reports/runtime/media-replay/queue-scope-cleanup-backup-20260704-HHMMSS/``
(44 files, ~130K) before any move. Nothing in this directory tree is
ever tracked by git; both the backup and the legacy-cleaned tree
belong to ``reports/runtime/`` which is git-ignored.

### Diagnostic recipes (post-cleanup)

```bash
# What is the cron about to do? (the only number that matters)
python3 - <<'PY'
import sys, json
sys.path.insert(0, "scripts")
from artvee_daily_health_check import _scan_pending_media
from pathlib import Path
print(json.dumps(_scan_pending_media(Path("reports/runtime")), indent=2))
PY

# Same scope, but for ``daily-health/`` only (ops status view):
python3 - <<'PY'
import sys, json
sys.path.insert(0, "scripts")
from artvee_daily_health_check import _scan_pending_media
from pathlib import Path
print(json.dumps(_scan_pending_media(Path("reports/runtime/daily-health")), indent=2))
PY

# Dry-run the full cron wrapper (no Telegram, no file moves).
bash scripts/artvee_media_replay_cron.sh --dry-run --limit 5 --max-retries 3
```

### Lessons

* **Backup and terminal artifacts must be outside the active queue
  scan.** The pre-P8D+4B cron called ``_scan_pending_media(reports/)``
  (instead of ``reports/runtime/``), which silently counted
  ``replayed/`` and ``quarantine/`` files as pending because their
  relative path didn't start with the expected ``replayed/`` /
  ``quarantine/`` prefix. The crash was that the *caller* passed the
  wrong root and the *callee* trusted the prefix match; both halves
  need to be defensive.
* **The active pending scope must be a single, named directory** under
  which everything is unambiguously actionable. ``reports/runtime/
  media-replay/pending/`` (when present) and ``daily-health/`` (top
  level) are that scope. Anything else is a terminal artifact or a
  historical archive and must live elsewhere.

