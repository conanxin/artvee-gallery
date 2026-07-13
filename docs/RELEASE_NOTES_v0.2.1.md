# Artvee Gallery v0.2.1 Release Notes

> **Status:** Draft / release-prep 2026-07-05, **appended with P9F+1
> on 2026-07-11** and **P8D+5 on 2026-07-13** — not yet tagged, not
> yet published as a GitHub Release. Awaiting user approval before
> the `v0.2.1` tag is cut. See
> [`CHANGELOG.md`](../CHANGELOG.md) for the aggregated changelog and
> this file for the v0.2.1-specific narrative. The P8D+5 section
> below documents the end-to-end Telegram notification recovery
> that is the final prerequisite for the v0.2.1 release.

## P9F+1 — Metrics Normalization (REQUIRED for v0.2.1)

### Why this matters

The v0.2.0 → v0.2.1 gap included a partial ops-stabilization phase
that exposed a previously invisible bug: the Daily Health and Ops Status
text surfaces kept quoting `records=875` — a value frozen in
`artvee-status-report.json` on 2026-06-18 — while the local library
grew to its actual size. Worse, the integrity checker reported a
`records=1206` counter that was never "available works", and the public
gallery was repeatedly called "200 records" without explaining that
200 is an export limit, not a library size.

P9F+1 is **the blocker fix** for v0.2.1. It collapses all four numbers
under one canonical schema, one live collector, one freshness rule,
and one CI-enforced invariant.

### What ships in v0.2.1

- A canonical metrics model (`artvee-metrics-v1`) with named,
  unambiguous fields. See [`docs/METRICS_MODEL.md`](METRICS_MODEL.md)
  for the full schema and migration recipe.
- A single live collector (`scripts/artvee_metrics.py`) used by the
  Status Report, Daily Health, and Ops Status scripts.
- A 20-invariant regression
  (`scripts/check_artvee_metrics.py`) wired into CI so a stale
  snapshot can never reappear silently.
- Atomic writes for every on-disk status report. Readers cannot
  observe a half-written file.
- An explicit `recommended_action: attention_required_metrics_stale`
  channel for the Telegram operator when the live collector fails.
- One backward-compatibility alias (`records` →
  `metrics.library_records`) marked `records_deprecated: true`. It
  will be removed in v0.3.0.

### What stays the same

- The integrity checker still PASSes on the same data — its scope
  labels are renamed, but the gate logic does not change.
- The Public Gallery export is now **300 selected works** (a
  diverse sample, *not* the library size).

### Migration recipe

If your code is reading `artvee-status-report.json` looking for
`records`, see section 7 of
[`docs/METRICS_MODEL.md`](METRICS_MODEL.md#7-migration-recipe-for-callers).

### Operator-visible changes (Telegram / dashboards)

**Daily Health**:

```text
✅ Artvee Daily Health
Date: 2026-07-11
Library records: 1286                # <-- live, was "Records: 875" before
Manifest: downloaded=1290, pending=54, failed=10
Integrity: PASS (checked records: 1355)
Readiness: PASS
Metrics: LIVE, age=0s, stale=False
Retired: known_retired=4, blocking_unresolved=0
...
Public Gallery: 300 selected works     # <-- separate from HTTP code
Online HTTP: gallery=200, digest=200   # <-- explicit "HTTP" label
```

**Ops Status** (table excerpt):

| Metric | Value |
|---|---|
| Library records | 1286 |
| Indexed records | 1286 |
| Gallery records | 1286 |
| Disk images | 1286 |
| Manifest downloaded | 1290 |
| Manifest pending | 54 |
| Manifest failed | 10 |
| Public records | 300 |
| Integrity checked records | 1355 |
| Metrics source | live |
| Metrics age (seconds) | 0 |
| Metrics stale | False |
| Records alias | 1286 (semantics=library_records, deprecated=True) |
| Online HTTP gallery | 200 |
| Online HTTP digest | 200 |

### Resolved and disclosed observations

P9F+1 also writes the v0.2.1 release with full disclosure of the
following P9F audit findings:

- Acquisition is healthy (29/30 batch runs `EXIT_CODE=0` in the 30-day
  window; net +550 works over 30 days; `pending=54` is small enough to
  be healthy for ~3 days at current run rates).
- 10 currently-failed manifest rows have a clear split:
  - 1 × HTTP 404 candidate for `known_retired`;
  - 5 × SSL EOF and 1 × browser timeout are transient and become
    successes on the next batch;
  - 3 × filename-too-long failures are deterministic and need a
    `download_artvee_selected.py` slug-truncate fix (P9F+1 backlog,
  not a v0.2.1 blocker).

These observations are documented in the P9F audit report at
`<workspace>/reports/artvee-gallery-p9f-records-acquisition-audit-20260711.md`
(workspace-only artifact, not part of this repo).

### What v0.2.1 still does not do

- Does not delete `records` from the status report. The deprecated
  alias stays until v0.3.0.
- Does not retry any of the 10 currently-failed manifest rows.
- Does not push new GitHub Pages.
- Does not tag `v0.2.1` or publish a GitHub Release. Both happen on
  user approval.

## Summary

v0.2.1 is a **post-stable operations and public-demo polish patch
release** following v0.2.0 stable (2026-06-16). It does not change any
runtime / ingest behavior, does not modify `images/`, `metadata/`,
`thumbs/`, `dist/`, `digests/`, `web/data/`, `index/`, `inbox/`,
`logs/`, or `reports/runtime/`. Every change is local to scripts,
docs, and the public-demo UI shell.

Compared to v0.2.0, v0.2.1 ships:

| Aspect | v0.2.0 | v0.2.1 |
| --- | --- | --- |
| Media-replay cron | not yet available | optional 03:10 `media-replay` cron, idempotent installer, env-hardened PATH / `CRON_TZ`, full dry-run isolation |
| Public gallery public count | curated subset | **200 selected works** (up from the prior 100-cut) |
| Public digest archive | latest 5 only | full 30-day archive with cards, filters, and 9-entry history exposed online |
| Ops health snapshot | not available | one-shot `artvee_ops_status.sh` with `--include-pages` guard |
| Pending MEDIA fallback path | implicit in nightly health check | explicit MEDIA-replay queue with delivery-truth messaging, normalized `media-replay/{replayed,quarantine,results}/` tree, and active vs. terminal bucket classification |
| Dry-run summary isolation | not isolated | dry-run writes go to `reports/runtime/media-replay/dry-run/...`, never overwrite the production `cron-YYYY-MM-DD.json` |

## Highlights

- **Telegram MEDIA fallback hardening (P7B+1 → P7B+3)** — staged-only
  MEDIA delivery, transport-deferred fallback, and a pending-MEDIA
  replay queue that can be triggered manually or by an optional
  03:10 cron. `replay_pending_media.py` is queue-aware and reports
  per-bucket delivered / quarantined counts so a 2:30 candidate
  refresh that does not deliver the MEDIA does not silently leave a
  reported `delivered=3` on the operator's screen.

- **Optional 03:10 media-replay cron (P8D → P8D+4C)** — idempotent
  installer (`install_media_replay_cron.sh`), unified env hardening
  for `PATH` / `CRON_TZ` / `ARTVEE_TELEGRAM_CHAT_ID` (P8D+1), chat-id
  resolver hardening (P8D+2), verification-messaging cleanup
  (P8D+3), queue normalization + delivery truthfulness (P8D+4),
  queue scope cleanup (P8D+4B), and dry-run summary isolation
  (P8D+4C). The 2026-07-05 real cron run wrote
  `reports/runtime/media-replay/cron-2026-07-05.json` with
  `dry_run=false`, `outcome=no_pending`, `pending_before=0`,
  `transport_status=ok`, `transport_latency_ms=123`, and an empty
  `replay_message_ids` (semantically correct for `no_pending`).

- **Post-stable ops status command (P8A, P8A+1)** — one-shot
  `artvee_ops_status.sh --online --include-pages --pages-repo
  <pages-repo> --no-telegram` aggregates records, retired,
  blocking, integrity, readiness, pending media, transport health,
  Pages guard, and live public-endpoint HTTP status into a single
  JSON + Markdown report at
  `reports/runtime/ops/artvee-ops-status-YYYY-MM-DD.{json,md}`.
  Strictly read-only by default; Pages guard made visible via the
  `--include-pages` flag.

- **Public gallery expansion to 200 selected works (P8E)** —
  `confirm_demo_refresh.sh` gained a `--gallery-limit` parameter
  (default 100, configurable to 200+). Live count verified at 200
  via the published
  `https://conanxin.github.io/projects/artvee-gallery-demo/data/artworks.json`
  endpoint on 2026-07-05.

## Operational reliability

> v0.2.1 aggregate — same story as the prior release-prep. P9F+1
> brought fresh metrics tooling (scripts/artvee_metrics.py +
> scripts/check_artvee_metrics.py + docs/METRICS_MODEL.md); P9G+2 is
> a public-bundle change that does not touch reliability.

## P9G+2 — Public Gallery Bundle Optimization (2026-07-12)

> This section is part of the v0.2.1 release-prep narrative. Like
> P9F+1 above, P9G+2 rolls into v0.2.1 without changing the version
> number; the v0.2.1 observation window restarts from the P9G+2
> commit.

### Why this matters

P9G expanded the public Gallery to 300 selected works (was 200) and
left the public bundle at 14.88 MB. The P9G+1 audit pinned that
weight onto the 11 MB of `assets/thumbs/512/` files that the Grid
never loads (the Grid uses 256 thumbs, lazy-loaded, 300/300 cards).
512 thumbs were only requested once a user opened the detail panel,
and even then only one at a time — so the public bundle was paying
shipping cost for an asset no scrolling path ever paid rendering
cost for. P9G+2 turns that off.

### What ships in P9G+2

- **256-only public bundle.** The exporter stops writing
  `assets/thumbs/512/` under `--detail-thumb-policy=none`. Live
  bundle: 14.88 MB → **3.48 MB** (≈ –11.40 MB / –76.6%).
- **Detail panel falls back to 256 cleanly.** Front-end uses
  `thumb_512 || image_path || thumb_256`; under `none` the chain
  resolves to 256 with no broken image, no extra request.
- **`gallery_stats.json` records the policy.** New fields:
  `detail_thumb_policy`, `thumbs_256_count`, `thumbs_512_count`.
- **`docs/PUBLIC_BUNDLE_POLICY.md`** is the new single source of
  truth for what the public bundle ships.
- **Future expansion is unblocked.** 400 records at 256-only
  project to **4.55 MB**, 500 records to **5.62 MB**, both within
  the 5 MB soft / 8 MB hard budget.

### What stays the same (and why it matters)

- Local Library `images/` / `metadata/` / `thumbs/` / `web/data/`
  are **not** modified. The 512 thumbnails still live on disk in
  the local Library tree; only the public export stops including
  them.
- Full images / metadata / tokens / chat ids / local paths remain
  forbidden from the public bundle. Open-source readiness, integrity
  checker, and Pages Guard all keep enforcing it.
- The Pages allowlist is unchanged. Only `projects/artvee-gallery-demo/`
  is touched; old 512 thumbs are removed via `rsync -a --delete`.

### What v0.2.1 + P9G+2 still does not do

- Does **not** create the `v0.2.1` tag or the GitHub Release.
  Both happen on explicit user approval after a 7-day green
  observation window starts from the P9G+2 commit (2026-07-12).
- Does **not** widen the public bundle to 400/500 records. The
  capacity now exists, but record-count changes are a separate
  decision (P9H) that requires its own grid/strategy review.
- Does **not** download / refill / batch / retry retired URLs.
- Does **not** modify any local source path.

| Phase | Description | Status |
| --- | --- | --- |
| P7B+1 | Cron MEDIA delivery verification / failure-only fallback | ✅ PASS |
| P7B+2 | Staged-only MEDIA + transport-deferred fallback (2026-06-18 regression) | ✅ PASS |
| P7B+3 | Pending MEDIA replay + OpenClaw transport health check | ✅ PASS |
| P8D | Optional 03:10 media-replay cron | ✅ PASS |
| P8D+1 | Cron PATH hardening + unified installer / 03:10 activation fix | ✅ PASS |
| P8D+2 | Telegram notifier chat-id configuration hardening | ✅ PASS |
| P8D+3 | Media replay verification cleanup (next-day verification) | ✅ PASS |
| P8D+4 | Media replay queue normalization + delivery truthfulness | ✅ PASS |
| P8D+4B | Media replay queue scope cleanup (active vs. terminal buckets) | ✅ PASS |
| P8D+4C | Dry-run summary isolation (timestamped dry-run slot) | ✅ PASS |

Verification report paths live under
`<workspace>/reports/artvee-gallery-p7b*.md` and
`<workspace>/reports/artvee-gallery-p8d*.md`.

## Public demo improvements

- **Gallery info card** (P8B) — gallery demo shows a small info card
  with curated counts and a link into the digest archive.
- **Gallery 200 selected works** (P8E) — `--gallery-limit`
  parameter on `confirm_demo_refresh.sh` raises the live public
  gallery from the previous 100-cut to the current 200 selected
  works. The published count is now driven by `--gallery-limit`
  and re-confirmed by the public-endpoint probe in ops status.
- **Digest archive** (P8B, P8C) — public daily-digest page grew
  from a single latest-5 view into a 30-day archive with cards,
  filters, and an entry history. The JSON sidecar at
  `data/digest-history.json` now reports 9 entries (latest entry
  verified at `2026-06-12` on 2026-07-05).
- **Data minimization** (P5E, P8B follow-through) — public bundle
  still ships thumbnails only; no full images, no private
  metadata, no runtime paths.

## Safety boundaries

- **Full local archive remains local-first.** All `images/`,
  `metadata/`, `inbox/`, `index/`, `web/data/`, `logs/`, `thumbs/`,
  `dist/`, `digests/`, `tmp/`, and `reports/runtime/` artifacts
  continue to be gitignored. Nothing in this release modifies any
  of them.
- **Public demo publishes selected records and thumbnails only.**
  The public bundle never includes full-resolution images, the
  original metadata archive, or any local machine paths. Curated
  thumbnails only.
- **No full images or metadata are published.** Public endpoints
  serve 200 thumbnails and a 30-day digest history summary, both
  with relative paths and no private fields.
- **Runtime outputs are not tracked.** All `reports/runtime/**`
  paths remain local and out of the commit history; v0.2.1 release
  prep intentionally does **not** add `reports/runtime/` to git.

## Current verified status (2026-07-12, after P9G+2)

| Field | Value | Source |
| --- | --- | --- |
| Public Gallery | 300 selected works (256-only) | `https://conanxin.github.io/projects/artvee-gallery-demo/data/artworks.json` |
| Public Gallery bundle | 3.48 MB (–76.6% vs. P9G) | `du -sb` of the live Pages repo |
| `detail_thumb_policy` (public bundle) | `none` (P9G+2) | `data/gallery_stats.json` |
| Public 256 thumbs | 300 | `data/gallery_stats.json.thumbs_256_count` |
| Public 512 thumbs | 0 (gallery); 1 (digest preview, unchanged) | `data/gallery_stats.json.thumbs_512_count` + digest bundle |
| `known_retired` | 4 | ops status (`KNOW_RETIRED`-audited) |
| `blocking_unresolved` | 0 | ops status |
| `pending_media` | 0 | ops status + cron-2026-07-12.json |
| `transport` | `ok` | ops status + cron-2026-07-12.json |
| Public Digest history | 9 entries (latest 2026-07-12) | `https://conanxin.github.io/projects/artvee-gallery-digest/data/digest-history.json` |
| Strict integrity | PASS (0 duplicates) | `scripts/check_gallery_integrity.py --strict` |
| Open-source readiness | PASS (4/4) | `scripts/check_open_source_ready.py` |
| Pages commit | `33ff10b` (646abf3..33ff10b) | Pages repo `git log -1 --oneline` |

### A note on `records` numbers

If you compare the ops status snapshot to `check_gallery_integrity.py
--strict`, the two numbers may not match. That is **intentional** —
they are different measurements:

- **`records` in ops status (`875` on 2026-07-05)** — count of
  records in the **ops / public / current-status model**, which is
  the active ops snapshot used by daily-health and ops-status. It
  intentionally excludes certain terminal buckets (e.g. records that
  are *known retired* but tracked separately) and is the number
  that drives the public gallery's `200 selected works` view.
- **`records` in `check_gallery_integrity.py --strict` (`1206` on
  2026-07-05)** — count of records in the **strict-integrity
  checker's scope**, which is the wider index of duplicates /
  collisions across all stored artwork rows (including retired
  records that are deliberately kept in the archive for audit).

These are two different metrics. **Do not present them as the same
field.** Future reports may add a `ops_records` / `integrity_records`
split label to remove the ambiguity if it causes confusion.

## Known behavior / deferred items

- **Dry-run summary path overlap** — in real `no_pending`
  media-replay summaries, the
  `dry_run_summary_path` field equals the
  `production_summary_path` field (both point at the production
  slot). The authoritative signals are `dry_run=false` and
  `would_write_production_summary=true`; the
  `dry_run_summary_path` is informational and is intentionally
  permitted to alias the production path in this case. Cleanup of
  this semantic lives in **v0.2.2 / v0.3.0**; v0.2.1 documents it as
  known behavior so operators reading a no-pending summary do not
  raise a false alarm. (`dry-run` *flag*-driven writes go to
  `reports/runtime/media-replay/dry-run/cron-YYYY-MM-DD-YYYYMMDD-HHMMSS.json`
  and never overwrite the production slot — that path is fully
  isolated.)
- **PATH follow-up for refill / batch / notifier** — the local
  OpenClaw PATH resolution hardening done in P8D+1 made the
  refill / batch notifier rely on a machine-local resolution order;
  if a future environment changes the user's `$HOME` layout, the
  notifier may emit a `would_block` warning on first daily-health
  run after the change. Data artifacts are unaffected; the
  follow-up is reserved as P8D+4 follow-up if still unresolved at
  end of observation.

## Git commit and CI

The release-prep changes for v0.2.1 will be committed in one
documentation-only commit:

```text
Prepare v0.2.1 release notes
```

Files changed in the release-prep commit (no code, no runtime
data, no images / metadata / thumbs / dist / digests / web/data /
index / inbox / logs / reports/runtime):

- `docs/RELEASE_NOTES_v0.2.1.md` (new)
- `docs/PROJECT_STATUS.md` (P8D+4C verification PASS row +
  v0.2.1 release-prep row)
- `docs/ROADMAP.md` (v0.2.1 → release-prep; next: tag / release
  after final verification)
- `docs/POST_STABLE_OPERATIONS.md` (light v0.2.1 release-prep
  reference, only if missing)
- `README.md` (light note: 100 → 200 selected works, only if
  not already updated)
- `CHANGELOG.md` (top section `## v0.2.1 — 2026-07-05`, with
  Added / Changed / Fixed / Verified / Known behavior)

CI on `main` after push: `open-source-ready.yml` runs
`check_open_source_ready.py` + `py_compile` + `bash -n` on every
push. Local preflight before commit:

```bash
python3 scripts/check_open_source_ready.py
python3 scripts/check_gallery_integrity.py --strict
bash scripts/artvee_ops_status.sh \
  --online \
  --include-pages \
  --pages-repo <pages-repo> \
  --no-telegram
```

## Upgrade / verification

Operators on v0.2.0 or v0.2.0-alpha can upgrade in place; v0.2.1
adds scripts and docs but does not change data schemas, runtime
paths, or the cron command-line shape. Recommended verification
after pull:

```bash
# 1. Open-source readiness — tracked files + secret hygiene + size
python3 scripts/check_open_source_ready.py

# 2. Gallery integrity — duplicates, collisions, image-path duplicates
python3 scripts/check_gallery_integrity.py --strict

# 3. Live ops status — records, retired, blocking, integrity,
#    readiness, pending media, transport, public endpoint HTTP code
bash scripts/artvee_ops_status.sh \
  --online \
  --include-pages \
  --pages-repo <pages-repo> \
  --no-telegram
```

A healthy v0.2.1 installation reports:

- `check_open_source_ready.py`: 4/4 PASS, Overall PASS.
- `check_gallery_integrity.py --strict`: 0 duplicates, Overall
  PASS.
- `artvee_ops_status.sh --online --include-pages ... --no-telegram`:
  `records` (ops) ≈ 850-900, `known_retired=4`, `blocking=0`,
  `integrity=PASS`, `readiness=PASS`, `pending_media=0`,
  `transport=ok`, `recommended_action=candidate_ready_manual_publish_optional`
  (until the next approved publish).

## Safety boundaries (re-stated for operators)

- The optional 03:10 media-replay cron is opt-in only; it is **not**
  installed by `install_media_replay_cron.sh` unless the operator
  explicitly runs it. Existing 03:00 daily-health and other crons
  are unchanged.
- v0.2.1 does not introduce any auto-publish step. Approved Pages
  publish remains a manual `publish_demo_refresh_candidate.sh
  --approve` invocation.
- v0.2.1 does not introduce any `refill`, `batch`, or
  `retry_unresolved_losers` behavior. Retired URLs remain retired
  per P6B / P6G.
- v0.2.1 does not modify `images/`, `metadata/`, `thumbs/`,
  `dist/`, `digests/`, `web/data/`, `index/`, `inbox/`, `logs/`,
  `reports/runtime/`, or `tmp/`.
- v0.2.1 does not introduce any tracked secrets / real local paths.
  CI enforces this on every push.

## Next steps

- **7-day observation continuation** from 2026-07-05. Track daily
  health + ops status + the optional 03:10 media-replay cron log
  for one full week.
- **v0.2.2 / v0.3.0 cleanup candidates:** tighten the
  `dry_run_summary_path` semantics so it never aliases
  `production_summary_path`; revisit the per-bucket
  bucket-classifier as the queue grows; consider adding an
  `ops_records` vs. `integrity_records` split label to remove the
  `875 vs 1206` ambiguity documented above.
- **Future 400+ public gallery expansion** *only after* a
  performance review (page weight, first-paint time, CDN budget)
  to make sure the static bundle stays CDN-friendly.
- **Tag and GitHub Release.** After the 7-day observation window
  closes green and user approval is received, cut the `v0.2.1`
  annotated tag and publish the GitHub Release from this file.

---

*See also:*
- [`CHANGELOG.md`](../CHANGELOG.md) — aggregated changelog
- [`docs/RELEASE_NOTES_v0.2.0.md`](RELEASE_NOTES_v0.2.0.md) —
  prior stable release notes
- [`docs/RELEASE_NOTES_v0.2.0-alpha.md`](RELEASE_NOTES_v0.2.0-alpha.md)
  — pre-stable release notes
- [`docs/POST_STABLE_OPERATIONS.md`](POST_STABLE_OPERATIONS.md) —
  post-stable ops status command
- [`docs/DAILY_OPERATING_PLAYBOOK.md`](DAILY_OPERATING_PLAYBOOK.md)
  — daily operating timeline and commands
- [`docs/MEDIA_REPLAY.md`](MEDIA_REPLAY.md) — media-replay queue,
  cron, and dry-run semantics

---

## P8D+5 — End-to-End Telegram Notification Recovery (REQUIRED for v0.2.1)

### Why this matters

The 2026-07-09 / 07-12 / 07-13 03:00 daily-health Telegram sends
silently dropped the day's notification with
`NOTIFY_FAIL: openclaw exit 1 error_kind=transport`. Health and
integrity checks stayed PASS (`library_records=1326`,
`source_mode=live`, `age=0s`). The failure was on the notification
channel only — not data — but to a user it looked like v0.2.1 had
started failing daily. v0.2.1 cannot ship with this latent silent
failure; P8D+5 is the prerequisite that closes both the symptom
(the silent text loss) and the underlying two distinct failures.

### Two distinct failures, two distinct fixes

1. **Refill / batch wrapper PATH resolution** — the `01:30` /
   `02:00` wrapper logs reported
   `OpenClaw binary missing or not executable` because the legacy
   crontab block never exported `PATH=$HOME/.local/bin:...` to
   the bash session running the wrapper.

   **Fix**: `scripts/artvee_nightly_wrapper.sh` unconditionally
   prepends `$HOME/.local/bin` and exports
   `ARTVEE_TELEGRAM_ENV_FILE` before any notifier call. Canonical
   resolution priority (in `_resolve_openclaw_bin`) is, in order:
   `--openclaw-bin` → `ARTVEE_OPENCLAW_BIN` → `OPENCLAW_BIN` →
   `command -v openclaw` → `$HOME/.local/bin/openclaw` → hard
   `binary_missing` error.

2. **03:00 daily-health text transport** — the text send hit
   `openclaw exit 1 error_kind=transport` and no fallback existed
   for 03:10 to recover.

   **Fix 1 (bounded retry)**:
   `scripts/artvee_telegram_notify.py: send_text_with_retry(..., max_attempts=3, backoff_seconds=[0,15,45])`.
   Only transport-class failures retry;
   `binary_missing` / `config_missing` / `media_allowed` /
   `exit_nonzero` fail fast. `ok` requires **both** `rc == 0`
   **and** a non-empty parsed `message_id` (camelCase
   `messageId=` matched). A separate `_redact_log` helper scrubs
   9-13 digit chat-ids and bot-token shapes from anything that
   reaches the queue.

   **Fix 2 (full-notification bundle queue)**:
   `reports/runtime/daily-health-delivery/{pending,replayed,
   quarantine,results}/` anchored by stable root names. When the
   03:00 text send exhausts bounded retries on a healthy day,
   the bundle (`text + (already-staged) staged_report`) is
   persisted under `pending/` with schema
   `artvee-notification-bundle-v1`. Chat-id / token are never
   persisted; staged_report is re-validated against the
   `<home-dir>/.openclaw/media/artvee-reports/` allowlist before persistence.

   **Fix 3 (03:10 replay state machine)**:
   `scripts/replay_pending_media.py: replay_notification_bundle(...)`
   invoked from `scripts/artvee_media_replay_cron.sh` with
   `--include-notification-bundles` so one 03:10 run drains both
   queues. Sequence: send text → require non-empty
   `text_message_id` → send MEDIA with the staged path → require
   non-empty `media_message_id` → move to `replayed/`. Text
   success + MEDIA failure is preserved as media-only pending and
   retried without re-sending text. Excess retries move to
   `quarantine/`. Terminal / backup / nested paths never
   participate in the active scan.

3. **OpenClaw health probe** —
   `<home-dir>/.local/bin/openclaw-health-check.sh` previously collapsed
   every `systemctl --user` non-zero exit into a single
   `服务未运行` log line; that fired every minute when the cron
   ran the probe without a usable user-bus, masking actual
   state. The probe now distinguishes four mutually exclusive
   states — `active` / `degraded` / `unavailable` /
   `probe_error` — and writes a structured
   `<home-dir>/.local/share/openclaw/state/status.json`. The user-bus /
   namespace case is explicitly tagged
   `probe_error: user_bus_unavailable (DBUS_SESSION_BUS_ADDRESS
   unset)` instead of falsely claiming the service is down.

### Effect on the v0.2.1 release

P8D+5 is the final prerequisite for v0.2.1: without it, the
03:00 silent-drop would have repeated every day after the
release. With it, the worst case becomes "the 03:00 text drops,
03:10 replays both text and MEDIA atomically, and the user's day
is unbroken".

| P8D+5 verification | Result |
|---|---|
| `bash -n` (5 shell scripts) | PASS |
| `python3 -m py_compile` (5 Python files) | PASS |
| `scripts/test_p8d5.py -v` (18 unit + simulated tests) | PASS |
| Real-Telegram cron-like send (logged in workspace report only) | text `message_id` non-empty |
| Real-Telegram bundle replay E2E | both text and MEDIA delivered, bundle moved to `replayed/` |
| `check_open_source_ready.py` | PASS |
| `check_gallery_integrity.py --strict` | PASS |
| `check_artvee_metrics.py --strict` | 20/20 PASS |
| `artvee_ops_status.sh --online --no-telegram` | `action=candidate_ready_manual_publish_optional` |

### v0.2.1 observation window

The v0.2.1 observation window resets at the P8D+5 commit
(committed 2026-07-13, but **not yet tagged**). The user is the
only party who can authorize the `v0.2.1` tag and the
GitHub Release. Until that authorization arrives there is
**no tag and no GitHub Release** for v0.2.1.
