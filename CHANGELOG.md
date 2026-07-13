# Changelog

All notable changes to Artvee Gallery are documented here. The
format is based on [Keep a Changelog](https://keepachangelog.com/),
and the project adheres to [Semantic Versioning](https://semver.org/)
in the form `vMAJOR.MINOR.PATCH-stage` (pre-1.0).

## v0.2.1 - 2026-07-05 (release-prep)

> **Status:** release-prep, **not yet tagged**. Awaiting user
> approval before the `v0.2.1` annotated tag is cut and before
> publishing the GitHub Release. No tag and no GitHub Release have
> been created in this phase. See
> [docs/RELEASE_NOTES_v0.2.1.md](docs/RELEASE_NOTES_v0.2.1.md) for
> the full narrative.

### v0.2.1 — P8D+5 (End-to-End Telegram Notification Recovery, appended 2026-07-13)

> **Status:** appended to v0.2.1 release-prep. v0.2.1 has not been
> tagged yet; this commit is included in the v0.2.1 cutoff. The
> P9F+1 metrics work already shipped in the v0.2.1 cutoff; this section
> adds the missing Telegram-notification recovery that the 03:00
> cron observed daily since 2026-07-09 (`NOTIFY_FAIL: openclaw exit 1
> error_kind=transport`). After this commit the 03:00 text failures
> can be fully recovered at 03:10 via a new notification-bundle queue.

#### Added
- **`scripts/artvee_telegram_notify.py: send_text_with_retry(...)`** — a
  bounded-retry wrapper over `send_text` that runs up to 3 attempts
  with a configurable backoff (default `0,15,45` seconds). Only
  transport-class failures retry (`error_kind ∈ {transport, timeout}`);
  binary_missing, config_missing, media_allowed and exit_nonzero fail
  fast. Every attempt's structured history is returned so callers can
  surface exactly which attempt delivered and which failed.
- **`scripts/artvee_daily_health_check.py` — full-notification-bundle
  queue:** `reports/runtime/daily-health-delivery/{pending,replayed,
  quarantine,results}/` plus `_write_notification_bundle(...)` and
  `_scan_notification_bundles(...)`. When the 03:00 text send exhausts
  bounded retries on a healthy day, the report + (already-staged)
  MEDIA path are persisted into a single bundle so 03:10 can replay
  the **entire** notification as one atomic unit.
- **`scripts/replay_pending_media.py: replay_notification_bundle(...)`
  + `--include-notification-bundles` / `--only-notification-bundles`
  / `--delivery-root` flags**: extends the legacy media-only replay
  queue with a notification-bundle state machine. Text is sent first;
  if MEDIA fails the bundle is preserved as media-pending and re-sent
  in the next replay without re-sending text.
- **`scripts/test_p8d5.py`** — 18 unit + simulated tests covering
  binary resolution from PATH and `$HOME/.local/bin`, config / binary
  non-retry, 3-attempt transport retry, attempt #2 success,
  exit-0-but-no-message_id, redactor leak-scan, classifier buckets
  (active vs terminal vs backup vs nested), bundle-writer secret scan,
  bundle replay end-to-end, and the health-probe `user_bus` semantics.
- **`docs/P8D+5 notifications section`** (this commit): DAILY_OPERATING_PLAYBOOK,
  MEDIA_REPLAY, POST_STABLE_OPERATIONS, DEVELOPMENT, PROJECT_STATUS,
  ROADMAP, RETROSPECTIVE and RELEASE_NOTES_v0.2.1 each gain a new
  "End-to-End Telegram Notification Recovery" subsection.

#### Changed
- **`scripts/artvee_telegram_notify.py`** — `send_text(wait=True)` now
  treats `openclaw exit 0 but no message_id parsed` as a failure, not a
  success. The redactor (`_redact_log`) scrubs 9-13 digit chat-id runs
  and bot-token-shaped substrings before they reach any queue file.
- **`scripts/artvee_daily_health_check.py`** — the 03:00 text send now
  routes through `send_text_with_retry`; text attempt history is
  recorded under `telegram.text_summary.retry_history` and the JSON
  report gains `media_replay.notification_bundles_before` /
  `notification_active_replayable` / `notification_terminal_replayed`
  / `notification_terminal_quarantine` / `notification_results`
  fields so the 03:10 summary distinguishes the two queues.
- **`scripts/artvee_nightly_wrapper.sh`** — unconditionally prepends
  `$HOME/.local/bin` to PATH and exports `ARTVEE_TELEGRAM_ENV_FILE`
  before every notifier call. Belt-and-suspenders against future
  crontab regressions that drop the env-block.
- **`scripts/artvee_media_replay_cron.sh`** — now invokes the replay
  script with `--include-notification-bundles` so a single 03:10 run
  drains both queues. The cron summary JSON gains
  `notification_bundles_before`, `notification_text_delivered`,
  `notification_media_delivered`, `notification_failed`,
  `notification_quarantined` and `notification_aggregate_path`.
- **`scripts/install_media_replay_cron.sh`** — the P8D cron block
  now also exports `ARTVEE_TELEGRAM_ENV_FILE` so the chat-id
  resolution works during the replay run (the previous block only
  set `PATH`).

#### Fixed
- **OpenClaw health probe (`<home-dir>/.local/bin/openclaw-health-check.sh`)** —
  the previous script collapsed every `systemctl --user` non-zero exit
  into a single `"服务未运行"` log line, which fired every minute when
  cron ran the probe without a usable user-bus. The patched probe
  distinguishes four mutually exclusive states (`active`, `degraded`,
  `unavailable`, `probe_error`) and writes a structured
  `<home-dir>/.local/share/openclaw/state/status.json` so dashboards and
  ops_status can read the probe outcome without parsing log lines.
  The probe_error path explicitly tags `user_bus_unavailable` when
  `DBUS_SESSION_BUS_ADDRESS` is unset, instead of falsely claiming the
  service is down.
- **Notification cron observability** — 03:00 text failures no longer
  silently drop the day's notification: a pending bundle is enqueued
  for 03:10 to replay atomically (text + MEDIA). All checks stayed
  PASS throughout (library_records=1326, integrity=PASS, readiness=PASS,
  metrics source=live).

#### Safety
- **No download / refill / nightly batch triggered** — daily health,
  notifier, replay and probe scripts only touch reports / runtime /
  log files. No `images/`, `metadata/`, `thumbs/`, `inbox/`, `index/`,
  `manifest`, `web/data/` or `dist/` was modified.
- **No GitHub Pages push** — the round does not touch pages.
- **No tag / GitHub Release** — round ends at the v0.2.1 release-prep
  branch, no `v0.2.1` Git tag was cut.
- **Stage MEDIA path allowlist enforced** — the bundle writer re-checks
  that the staged REPORT path lives under
  `<home-dir>/.openclaw/media/artvee-reports/`; raw report paths outside the
  allowlist are dropped from the bundle (never sent raw).
- **Secret redaction** — the redactor scrubs the queue log of any
  9-13 digit chat-id run or 6-12-digit-prefix token-shape. Real
  E2E test verified that both text and MEDIA landed with non-empty
  `message_id`s, without leaking secrets. Concrete message IDs
  live in `<workspace>/reports/artvee-gallery-p8d5-notification-recovery-20260713.md`
  (workspace report, not tracked).

#### Verification
- All 18 P8D+5 unit + simulated tests pass.
- Cron-like real Telegram send: `NOTIFY_OK message_id=<text>`.
- Bundle replay E2E (real Telegram): text_message_id=<text>,
  media_message_id=<media>; bundle moved `pending/` → `replayed/`.
- `bash -n` clean on all four `.sh` scripts; `py_compile` clean on
  five Python files; `check_open_source_ready.py` + `check_gallery_
  integrity.py --strict` + `check_artvee_metrics.py --strict` all PASS.

#### Observation window reset
- The P7B+3 / P8D + N observation windows are reset only when v0.2.1 is
  finally tagged and released. Until then, **v0.2.1 observation
  remains in flight** — this commit's recovery tooling is a hard
  prerequisite for tagging, but the final tag and Release await a
  separate user-authorized round.

### v0.2.1 — P9F+1 (Metrics Normalization, appended 2026-07-11)

> **Status:** appended to v0.2.1 release-prep. v0.2.1 has not been
> tagged yet; this commit is included in the v0.2.1 cutoff.

#### Added
- **`scripts/artvee_metrics.py`** — the single canonical collector
  (schema `artvee-metrics-v1`). Powers every caller below.
- **`scripts/check_artvee_metrics.py`** — 20-invariant regression
  runnable in CI; exits non-zero on any violation (mismatch,
  inconsistency, leak). Includes a `secret / path-leak` scan so
  hard-coded paths can never re-enter the schema.
- **`docs/METRICS_MODEL.md`** — the canonical model document
  (sources, fields, invariants, freshness, migration recipe).

#### Changed
- **`scripts/build_artvee_status_report.py`** — emits the canonical
  metrics block plus a deprecated top-level `records` alias. Atomic
  write. Honors `ARTVEE_STATUS_MAX_AGE_SECONDS`.
- **`scripts/artvee_daily_health_check.py`** — **live-collects in
  process every run** (no more silent read of the cached JSON).
  Telegram text now shows `Library records:` and `Online HTTP:`
  separately. **CI runnable in `--no-telegram --strict` mode.**
- **`scripts/artvee_ops_status.py`** — same; `recommended_action`
  enum gains `attention_required_metrics_stale` for fallback
  scenarios.
- **`scripts/check_gallery_integrity.py`** — labels per-source
  counters as `manifest_integrity_checked_records`,
  `index_integrity_checked_rows`, `web_integrity_checked_records`;
  JSON output gains an `integrity_checker_scope` block. **The
  integrity gate logic itself is unchanged** (no false PASS, no
  false FAIL).
- **`docs/PROJECT_STATUS.md`** + **`docs/ROADMAP.md`** + **`docs/POST_STABLE_OPERATIONS.md`** +
  **`docs/DAILY_OPERATING_PLAYBOOK.md`** + **`docs/RELEASE_NOTES_v0.2.1.md`** — removed
  references to frozen `records=875` and `1206` numbers, replaced
  with live count semantics.

#### Fixed
- **Stale status snapshots that could keep reporting an old library count
  while acquisition continued.** Pre P9F+1, `artvee-status-report.json`
  was last regenerated on 2026-06-18 and the Ops Status / Daily Health
  text surfaces kept quoting `records=875` while the local library was
  at the true live count. Every canonical caller now collects fresh
  state on every run and falls back to a clearly-labelled `fallback_cache`
  if the live collect fails (with `recommended_action =
  attention_required_metrics_stale` and a specific `stale_reason`).

#### Schema
- The metrics model is now `artvee-metrics-v1`. The single backward
  compatibility alias is `records` → `metrics.library_records`,
  with `records_semantics: "library_records"` and
  `records_deprecated: true`. The alias will be removed in v0.3.0.

### Added
- **`scripts/artvee_media_replay_cron.sh`** + **`scripts/install_media_replay_cron.sh`** — optional 03:10 Asia/Shanghai media-replay cron with idempotent installer and a marker so the operator sees the same install-state on every re-run (P8D).
- **`scripts/replay_pending_media.py`** — pending-MEDIA replay workflow with per-bucket `delivered` / `quarantined` reporting, normalized `media-replay/{replayed,quarantine,results}/` tree, and `message_id`-based delivery truth (P7B+3, P8D+4).
- **`scripts/check_openclaw_transport.py`** — pre-flight OpenClaw transport health check used by replay and by ops status (P7B+3, P8D+4).
- **`scripts/artvee_ops_status.sh`** + **`scripts/artvee_ops_status.py`** — one-shot post-stable ops status aggregator (records, retired, blocking, integrity, readiness, pending media, transport, Pages guard, public-endpoint HTTP probe) (P8A).
- **`scripts/install_artvee_cron.sh`** — unified installer for refill / batch / confirm / daily-health cron with shared PATH / `CRON_TZ` hardening (P8D+1).
- **`docs/MEDIA_REPLAY.md`** — media-replay queue, optional 03:10 cron, and dry-run semantics end-to-end (P8D → P8D+4C).
- **`docs/POST_STABLE_OPERATIONS.md`** — `artvee_ops_status.sh` reference (P8A, P8A+1).
- **`docs/DAILY_OPERATING_PLAYBOOK.md`** — daily operating timeline + commands + failure playbook (P7A → P8D+4C).
- **`docs/RETROSPECTIVE.md`** — phase-by-phase retrospective including post-stable automation polish (P7A → P8D+4C).
- **`docs/RELEASE_NOTES_v0.2.1.md`** — release-prep notes for this version.
- **`docs/DIGEST_HISTORY.md`** — 30-day digest history reference and selection semantics.

### Changed
- **`scripts/artvee_daily_health_check.py`** — gain (post v0.2.0) the `--include-pages` Pages-guard flag and the staged-MEDIA / transport-deferred fallback path. Strict-mode `--no-telegram` continues to be the CI baseline.
- **`scripts/artvee_telegram_notify.py`** — chat-id resolver: `--chat-id` CLI > `ARTVEE_TELEGRAM_CHAT_ID` env > OpenClaw config > hard error; `--check-config` flag added (P8D+2).
- **`scripts/stage_report_for_telegram_media.py`** — staged-only MEDIA delivery; transport-deferred fallback now treated as a normal sub-track (P7B+2).
- **`scripts/install_daily_health_cron.sh`** — exports `PATH=$HOME/.local/bin:$PATH` on its own line so cron does not strip it (P8D+1).
- **`scripts/confirm_demo_refresh.sh`** — `--gallery-limit` parameter (default 100, configurable up to 300+) (P8E).
- **`scripts/export_artvee_gallery_public_demo.py`** + **`scripts/export_artvee_digest_public_page.py`** — info card + 30-day archive cards + filters; data minimization unchanged (P8B, P8C).
- **`README.md`** — operational model row updated to include the optional 03:10 media-replay cron (manual install only); docs index now lists `docs/POST_STABLE_OPERATIONS.md`, `docs/DIGEST_HISTORY.md`, `docs/MEDIA_REPLAY.md`. *(The "300 selected works" light note is added as part of this release-prep; the status badge stays at v0.2.0 until v0.2.1 is tagged.)*

### Fixed
- **Cron `PATH` stripped by cron env** — P8D+1 splits `PATH=` and `CRON_TZ=` onto their own lines so the daily-health, refill, batch, and media-replay crons all see `$HOME/.local/bin`. The 03:10 media-replay cron had been silently failing because `openclaw` could not be resolved.
- **Chat-id silently dropped during `--check-config`** — `artvee_telegram_notify.py` no longer treats a missing chat-id as a silent success: it now surfaces the resolved / unresolved state (P8D+2).
- **Media-replay verification messaging** — neutralized the user-facing replay title so a successfully-replayed MEDIA does not look like a failure to the operator (P8D+3).
- **Media-replay queue infinite-nesting bug** — `_archive_dir` no longer appends `replayed/` repeatedly across runs; pre-fix files normalized to the stable `media-replay/{replayed,quarantine,results}/` tree (P8D+4).
- **Delivery truth in `replay_one`** — replay result is now computed from the `message_id` returned by OpenClaw, not from the candidate file's existence (P8D+4).
- **`_extract_message_id` regex** — updated for OpenClaw's `messageId=` journal format (P8D+4).
- **Cron `outcome` naming** — renamed `noop_zero_pending` to `no_pending`; per-bucket breakdown added to the cron summary JSON (P8D+4B).
- **Dry-run summary isolated** — `--dry-run` writes now go to `reports/runtime/media-replay/dry-run/cron-YYYY-MM-DD-YYYYMMDD-HHMMSS.json` and never overwrite the production slot; `flock`-held dry-runs record `dry_run_skipped_locked` to the dry-run slot only (P8D+4C).

### Verified (2026-07-05, real cron, `dry_run=false`)
- `scripts/check_open_source_ready.py` → **PASS** (4/4 sub-checks).
- `scripts/check_gallery_integrity.py --strict` → **PASS** (1206 records / 0 duplicates).
- `scripts/artvee_ops_status.sh --online --include-pages --pages-repo <pages-repo> --no-telegram` → `records=875 retired=4 blocking=0 integrity=PASS readiness=PASS pending_media=0 transport=ok action=candidate_ready_manual_publish_optional`.
- Public Gallery (live endpoint probe): **300 selected works**.
- Public Digest history (live endpoint probe): **9 entries** (latest 2026-06-12).
- `reports/runtime/media-replay/cron-2026-07-05.json` exists (1.1K, written 03:10 Asia/Shanghai):
  - `dry_run=false`, `outcome=no_pending`, `real_outcome=no_pending`,
  - `pending_before=0`, `pending_after=` (suppressed because no-pending),
  - `replay_delivered=0`, `replayed=0`, `quarantined=0`, `failed=0`,
  - `replay_message_ids=[]` (semantically correct for `no_pending`),
  - `transport_status=ok`, `transport_latency_ms=123`,
  - `production_summary_path` and `dry_run_summary_path` both point at the production slot (see **Known behavior**),
  - `would_write_production_summary=true`,
  - `started_at=2026-07-05T03:10:01+08:00`.

### v0.2.1 — P9G+2 (Public Bundle Optimization, appended 2026-07-12)

> **Status:** appended to v0.2.1 release-prep. v0.2.1 has not been
> tagged yet; this commit is included in the v0.2.1 cutoff. The
> v0.2.1 observation window restarts from the P9G+2 commit.

#### Changed
- **`scripts/export_artvee_gallery_public_demo.py`** — new
  `--detail-thumb-policy {all,none}` flag (default `none`).
  Under `none` the exporter omits `assets/thumbs/512/` from the
  candidate, sets `artworks.json.thumb_512 = null`, and remaps
  `image_path` to mirror `thumb_256` so the detail-panel fallback
  chain never requests a missing 512 asset.
- **`scripts/confirm_demo_refresh.sh`** — new
  `--detail-thumb-policy` argument (default `none`). QA is
  policy-aware: `thumbs_512_count` target is 300 under `all` and
  0 under `none`. Soft/hard size budgets switch to 5 MB / 8 MB
  under `none` (legacy 15 MB / 20 MB under `all`).
- **`web/app.js`** — explicit fallback chain
  `thumb_512 || image_path || thumb_256`. The Grid remains on
  256 (lazy). Detail-panel image now matches the policy: under
  `none` it serves the 256 thumb (no request to `/512/`); under
  `all` it still picks the 512 first as the previous release
  shipped.
- **Bundle size of the public Gallery:** 14.88 MB → 3.48 MB (a
  reduction of ≈ 11.40 MB / ≈ 76.6%, exact size measured on
  the live candidate; reports/audits may give slightly different
  numbers depending on `du` flags). The full 300-record Gallery
  (256 thumbs + base assets) is **6×** smaller than before.

#### Added
- **`docs/PUBLIC_BUNDLE_POLICY.md`** — single source of truth
  for the public-bundle contract: surface, allowed/forbidden
  fields, detail-thumb-policy semantics, detail-panel fallback
  chain, when to revisit, acceptance checklist.
- **`gallery_stats.json.detail_thumb_policy`** — explicit
  field recording which policy the bundle ships under
  (`all` / `none`).
- **`gallery_stats.json.thumbs_256_count`** and
  **`thumbs_512_count`** — explicit counts emitted in stats,
  redundant with the existing `counts.thumb_256_total` /
  `counts.thumb_512_total` (kept for back-compat with the
  artist / category dashboards).

#### QA & verification (P9G+2)
- Records 300 / 256 thumbs 300 / 512 thumbs **0** (policy=none).
- Bundle **3.48 MB** (well under soft 5 MB; well under hard 8 MB).
- Local HTTP + Playwright smoke: 300 cards, 0 `/512/`
  requests, 5 detail-panel clicks all load 256 thumbs, 0 broken
  images, 0 console errors, 0 page errors.
- Pages Guard: 305 changed / 305 allowed / 0 blocked (only
  `projects/artvee-gallery-demo/**` + `data.json` touched).
- Online `data/artworks.json`: 300 records, **0** `/512/`
  references, no `metadata_path`, no `home-dir` prefix, no
  `repo-name` mention, no `TOKEN` / `SECRET` / `CHAT_ID`.
- 7/7 endpoints HTTP 200, 10 sample 256 thumbs HTTP 200, sample
  512 paths HTTP 404 (verifying they were not just suppressed
  on the wire but actually deleted from Pages).

#### Safety (P9G+2)
- Local Library `images/` / `metadata/` / `thumbs/` untouched
  (full 1286 records + 512 thumbs remain on disk).
- No download / refill / batch / retired retry.
- No full image / metadata uploaded to Pages.
- No `v0.2.1` tag cut, no GitHub Release published.
- Pages commit `33ff10b` only touches the allow list.

#### Future expansion (now feasible)
- 400 records at 256-only → estimated **4.55 MB** (under soft 5
  MB, ready to ship without revisiting the bundle policy).
- 500 records at 256-only → estimated **5.62 MB** (under hard
  8 MB, shipping requires a fresh P9H or later phase that
  covers grid strategy as well as record count).

### Known behavior
- **Dry-run vs production summary path aliasing.** In real
  `no_pending` media-replay summaries, the
  `dry_run_summary_path` field equals the `production_summary_path`
  field (both point at the production
  `reports/runtime/media-replay/cron-YYYY-MM-DD.json` slot). The
  authoritative signals are `dry_run=false` and
  `would_write_production_summary=true`; the
  `dry_run_summary_path` is informational and is intentionally
  permitted to alias the production path in this case. **Cleanup
  of this semantic lives in v0.2.2 / v0.3.0**. `--dry-run` *flag*-driven
  writes go to
  `reports/runtime/media-replay/dry-run/cron-YYYY-MM-DD-YYYYMMDD-HHMMSS.json`
  and never overwrite the production slot — that path is fully
  isolated.
- **`records` count difference.** Ops status reports
  `records=875` while `check_gallery_integrity.py --strict`
  reports `1206`. These are two different metrics (ops / public /
  current-status scope vs. strict-integrity scope) and should not
  be presented as the same field. See the release notes
  "A note on `records` numbers" section.
- **Refill / batch notifier PATH follow-up.** P8D+1 hardens the
  cron PATH resolution; if a future environment changes the
  user's `$HOME` layout, the notifier may emit a `would_block`
  warning on the first daily-health run after the change. Data
  artifacts are unaffected. Reserved as P8D+4 follow-up if still
  unresolved at end of observation.

### Safety (release-prep only)
- No download / refill / batch / `--approve` / Pages push /
  retired retry / manual MEDIA replay during this release-prep.
- No `images/` / `metadata/` / `thumbs/` / `dist/` / `digests/`
  / `logs/` / `inbox/` / `web/data/` / `index/` /
  `reports/runtime/` / `tmp/` modification.
- No tokens / chat ids / real local paths in tracked code or
  docs; CI enforces this on every push.
- No `v0.2.1` tag cut in this phase (awaiting user approval).
- No GitHub Release published in this phase.

## v0.2.0 (stable, 2026-06-16)

> First **stable** daily-operable release. Identical surface to
> v0.2.0-alpha plus the post-observation hardening:
> 3-day observation window, Pages publish guard (cross-repo),
> daily-health online-check signal-distortion fix, and the
> stable tag itself. See
> [docs/RELEASE_NOTES_v0.2.0.md](docs/RELEASE_NOTES_v0.2.0.md)
> and [docs/STABLE_READINESS_v0.2.0.md](docs/STABLE_READINESS_v0.2.0.md)
> (15 / 15 PASS).

### Changed
- **Stable tag** — `v0.2.0` (annotated) on the v0.2.0-alpha
  surface plus the post-observation hardening commits.
- `scripts/artvee_daily_health_check.py` — split `except
  Exception` into `HTTPError` / `URLError` / `TimeoutError` /
  `ConnectionError`; new `online.kind` ∈ {ok, http_error,
  network_error, skipped}; new `online.gallery_error` and
  `online.digest_error`; `recommended_action` now branches on
  the kind. A future Pages content drift is reported with the
  correct HTTP code instead of being masked as `0, 0`.
- `README.md` — Latest release bumped from `v0.2.0-alpha` to
  `v0.2.0`; stable-readiness link added.

### Added
- [docs/RELEASE_NOTES_v0.2.0.md](docs/RELEASE_NOTES_v0.2.0.md)
  — the stable release notes.
- [docs/STABLE_READINESS_v0.2.0.md](docs/STABLE_READINESS_v0.2.0.md)
  — 15 / 15 readiness criteria that gate this release.
- [docs/V0_2_OBSERVATION_WINDOW.md](docs/V0_2_OBSERVATION_WINDOW.md)
  — Day 1 / Day 2 / Day 3 log; § 7 outcome block.
- `docs/PROJECT_STATUS.md` — `P7E+3` closed, `P7F` row added,
  `v0.2.0 stable release` row added.
- `docs/ROADMAP.md` — `P7F` moved to completed, `v0.2.0 stable`
  moved to completed, next: P8 automation polish + content
  product polish.

### Cross-repo follow-up (not in this repo)
- `scripts/check-project-publish-guard.py` +
  `docs/PAGES_PUBLISH_GUARD.md` shipped in the shared GitHub
  Pages repo so that future WBW SpaceX Mars publish runs cannot
  silently clobber the `projects/artvee-gallery-*` subtrees.

### Safety
- No download / refill / batch / `--approve` during this
  release-consolidation phase.
- No `images/` / `metadata/` / `thumbs/` / `dist/` / `digests/`
  / `logs/` / `inbox/` / `web/data/` / `index/` /
  `reports/runtime/` / `tmp/` modification.
- No tokens / chat ids / bot tokens / real local paths in
  tracked code; CI enforces this on every push.

## v0.2.0-alpha

> Daily-operable local-first visual archive system with public
> demos, curated daily digests, status reporting, and Telegram
> health delivery. See
> [docs/RELEASE_NOTES_v0.2.0-alpha.md](docs/RELEASE_NOTES_v0.2.0-alpha.md).

### Added
- **Public Gallery Demo** (P2, P3A) — curated thumbnails on
  GitHub Pages, no full archive.
- **Public Daily Digest page** (P3E, P6F+1) — separate GitHub
  Pages surface that exposes the 30-day digest history.
- **Daily health check** (P7A) — local-only report that records
  integrity, readiness, candidate state, digest history, and
  near-dup cluster counts.
- **Telegram notifier** (P6A) — local bridge to the OpenClaw
  CLI, with a flat → nested state model refactor (P7B+1).
- **Telegram MEDIA staging helper** (P6A) — copies a report
  into the OpenClaw-allowed media dir before attaching.
- **Daily health cron** (P7B) — idempotent, marker-based
  installer for the 03:00 Asia/Shanghai run.
- **Failure-only fallback** (P7B+1) — sends a short text-only
  warning when health is PASS but MEDIA delivery failed.
- **OpenClaw binary resolution** (P7A+1) — resolver chain
  `--openclaw-bin` > `ARTVEE_OPENCLAW_BIN` > `OPENCLAW_BIN` >
  `PATH` lookup.
- **Telegram delivery state model** (P7B+1) — nested object
  with `requested` / `openclaw_status` / `text_summary` /
  `media` / `fallback`, each track recording `attempted` /
  `sent` / `message_id` / `error` (and `reason` for fallback,
  `staged_path` for media).
- **Filename collision healing** (P4B) — deterministic
  rename-only plan for records whose filenames collide in the
  static bundle.
- **Audited KNOWN_RETIRED handling** (P6B, P6G) — explicit
  list of four source URLs that the upstream archive has
  removed, separated from the blocking-unresolved count.
- **Visual QA and curation filters** (P5D, P5E) — contact
  sheets and risk-aware selection.
- **Near-duplicate review workflow** (P6C) — clustering +
  contact sheets + audit trail.
- **30-day digest history** (P6F) — bounded history with
  near-dup-aware selection.
- **Approved-publish helper** (P6F+1) — pre-stages the GitHub
  Pages bundle and waits the 90-second CDN warm-up window.
- **Open-source readiness CI** (P3C, P3D) — fails the build
  on tracked runtime files, path leaks, real secrets, and
  oversized files.
- **Secret-hygiene policy** (P7B+1) — `chat_id` resolution
  order is `--chat-id` CLI > `ARTVEE_TELEGRAM_CHAT_ID` env >
  OpenClaw config > hard error; no chat id in tracked code.
- **`--simulate-media-failure` flag** (P7B+1) — testing-only
  shortcut that forces the MEDIA track to fail and triggers
  the fallback.

### Changed
- **Telegram state JSON** — `telegram_notify` (flat) replaced
  with `telegram` (nested). See
  [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) § 22.
- **Cron command** — now exports `PATH=$HOME/.local/bin:$PATH`
  and `ARTVEE_TELEGRAM_CHAT_ID` so OpenClaw resolves from the
  cron env. The script invocation is unchanged:
  `bash scripts/artvee_daily_health_check.sh --online --media`.
- **Status report split** — `KNOWN_RETIRED` (audited, not
  blocking) is reported separately from `BLOCKING_UNRESOLVED`,
  so the public-demo and digest readiness flags no longer flip
  on retired URLs.
- **Filename in `data/artworks.json`** — collision-migrated
  records keep their semantic id; the path field carries the
  renamed file. See
  [docs/RELEASE_NOTES_v0.1.0-alpha.md](docs/RELEASE_NOTES_v0.1.0-alpha.md)
  for the schema.

### Fixed
- The P7B daily health cron was running with `openclaw_status:
  missing` because the cron env did not include
  `$HOME/.local/bin` in `PATH`. P7B+1 adds the `export PATH=...`
  line to the cron command and re-installs the block.
- The P7A+1 cron probe used `--wait` on the notifier, which
  blocked the script for 2-3 minutes even when the binary was
  not resolvable. P7B+1 switches the probe to background send
  so a missing binary fails fast.
- A real chat id was hardcoded in
  `artvee_telegram_notify.py`; the resolution chain is now
  env / config only, and `check_open_source_ready.py` no
  longer flags the script for path leaks.

### Operational
- 01:30 refill · 02:00 nightly batch · 02:30 candidate
  refresh · 03:00 daily health cron · manual approved publish.
- Refill and nightly batch are the only cron jobs that touch
  the network; everything else is local.
- `bash scripts/artvee_daily_health_check.sh --no-telegram`
  works as a CI-style baseline that produces the JSON + MD
  report without sending anything.
- Cron-like verification (without waiting for 03:00):
  `env -i HOME=... PATH=$HOME/.local/bin:... ARTVEE_TELEGRAM_CHAT_ID=... bash -lc 'cd <artvee-repo> && bash scripts/artvee_daily_health_check.sh --online --media'`.

### Security / boundaries
- No tokens, chat ids, or bot tokens in tracked code or docs.
- Real local paths (`<artvee-repo>`) in docs are replaced
  with `<artvee-repo>`; system paths (`$HOME/.openclaw/...`) are
  kept because they are public OpenClaw config locations.
- `check_open_source_ready.py` is run by CI on every push and
  on every `git tag` push; failure blocks the release.

## v0.1.0-alpha

> The first open-source-facing release. The repository is
> self-describing, has a single canonical ignore file, a
> privacy surface that is machine-checked, and a public MIT
> license. See
> [docs/RELEASE_NOTES_v0.1.0-alpha.md](docs/RELEASE_NOTES_v0.1.0-alpha.md).

### Added
- `README.md`, `LICENSE` (MIT), `examples/` samples.
- `docs/ARCHITECTURE.md`, `docs/OPEN_SOURCE_BOUNDARIES.md`,
  `docs/ROADMAP.md`, `docs/DEVELOPMENT.md`, `docs/PROJECT_STATUS.md`.
- `scripts/check_open_source_ready.py` — pure-stdlib, read-only
  release gate.
- `.gitignore` consolidation; legacy `.gitignore.local` removed.
- Wrapper path-agnosticism via `BASH_SOURCE`-derived `BASE_DIR`.
- Local Gallery Browser (P1), Public Demo Export (P2),
  GitHub Pages Gallery Demo (P3A), Daily Digest (P3B),
  Open Source Readiness (P3C), Case Study / Retrospective
  (P3F).
