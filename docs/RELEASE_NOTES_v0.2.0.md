# Release Notes · v0.2.0 (stable)

> v0.2.0 is the **first stable** daily-operable release of
> Artvee Gallery. It is identical in surface area to
> **v0.2.0-alpha** (2026-06-13) and adds only the post-observation
> hardening: a 3-day observation window, a Pages publish guard,
> a fix for the daily health script's online-check signal
> distortion, and the explicit "stable" tag.
> See [docs/RELEASE_NOTES_v0.2.0-alpha.md](RELEASE_NOTES_v0.2.0-alpha.md)
> for the full feature list and [docs/STABLE_READINESS_v0.2.0.md](STABLE_READINESS_v0.2.0.md)
> for the 15 / 15 readiness checklist that gates this release.

## 1. Summary

v0.2.0 is the first release of Artvee Gallery that has been
**observed running unattended** on a single host for 3 consecutive
days (2026-06-14 → 2026-06-16) without manual intervention, with
the daily health cron, the Telegram text + MEDIA delivery, and
both public demos all green at the end of the window. Everything
that was true of v0.2.0-alpha is still true of v0.2.0; what
changed in between is documented under
[§ 6 "Upgrade notes from v0.2.0-alpha"](#6-upgrade-notes-from-v020-alpha)
below.

The system is designed to be safe to run unattended: nothing
destructive is automatic, the publish step is always manual
(`--approve` is required), and the data surface is
machine-checked at every push by `check_open_source_ready.py`.

## 2. Stable readiness

| Gate | Result | Evidence |
| --- | --- | --- |
| 3-day observation window | PASS | `docs/V0_2_OBSERVATION_WINDOW.md` |
| Day 1 (2026-06-14) | Green | `reports/runtime/daily-health/artvee-daily-health-2026-06-14.md` |
| Day 2 (2026-06-15) | Green (post-restore, with incident annotation) | `reports/runtime/daily-health/artvee-daily-health-2026-06-15.md`, `docs/PROJECT_STATUS.md` (P7E+1, P7E+2) |
| Day 3 (2026-06-16) | Green | `reports/runtime/daily-health/artvee-daily-health-2026-06-16.md` |
| Daily health cron | Installed, ran 03:00 daily | `logs/daily-health-cron/daily_health_*.log` |
| Telegram text | Delivered every day | message_ids 22919, 23150, 23707 |
| Telegram MEDIA | Delivered every day | message_ids 22921, 23151, 23709 |
| Public Gallery Demo | 6/6 endpoints HTTP 200 | live `curl -I` 2026-06-16 06:38 |
| Public Daily Digest | 6/6 endpoints HTTP 200 | live `curl -I` 2026-06-16 06:38 |
| `KNOWN_RETIRED` | 4 (audited, not blocking) | `reports/runtime/p6b-known-retired-urls.json` |
| `blocking_unresolved` | 0 | `reports/runtime/artvee-status-report.md` |
| Strict integrity | PASS | `scripts/check_gallery_integrity.py --strict` |
| Readiness CI | PASS (4/4) | `scripts/check_open_source_ready.py` |
| Readiness checklist | 15 / 15 PASS | `docs/STABLE_READINESS_v0.2.0.md` §6 |

## 3. Public demos

- **Gallery Demo** (curated thumbnail subset):
  <https://conanxin.github.io/projects/artvee-gallery-demo/>
- **Daily Digest** (latest 5-pick + 30-day history):
  <https://conanxin.github.io/projects/artvee-gallery-digest/>

Neither export contains the full local archive, the original
image assets, or any private metadata. The Pages publish guard
(P7E+2 follow-up, cross-repo) prevents the public GitHub Pages
repo from accidentally clobbering these subtrees during other
workstream publishes.

## 4. Key capabilities

### Local-first gallery
- Local gallery browser (P1) with thumbnails at 256 / 512 px and
  a search / filter / detail-modal UI shell.
- Strict integrity gate (P4A+1, P4B) that fails the build on
  duplicate ids, duplicate basenames, or one-id-many-URL
  anomalies.
- `KNOWN_RETIRED`-aware status report (P6G) that distinguishes
  audited retirees from blocking unresolved losers.

### Daily inspiration digest
- Deterministic 30-day digest history (P6F) with
  near-duplicate-aware selection.
- Public Daily Digest page (P3E, P6F+1) on a separate GitHub
  Pages surface.

### Public demo publishing
- Approved-publish helper
  (`scripts/publish_demo_refresh_candidate.sh --approve`) that
  pre-stages the GitHub Pages bundle and waits the 90-second
  CDN warm-up window.
- No auto-publish: the helper refuses to run without `--approve`.

### Operations
- Daily health check (P7A) with a JSON report that distinguishes
  integrity, readiness, candidate state, digest history, and
  near-dup cluster counts, plus a 6-endpoint online probe.
- Daily health Telegram cron at 03:00 Asia/Shanghai (P7B).
- Failure-only fallback (P7B+1): when health is PASS but MEDIA
  delivery failed, a short text-only warning is sent.
- Signal-distortion fix in `artvee_daily_health_check.py`
  (P7E+2): the online probe now distinguishes `HTTPError`
  (real HTTP code) from `URLError` (network error), so a
  future Pages content drift is reported correctly within
  24 h instead of masked as `0, 0`.
- Open-source readiness CI (P3C, P3D) that fails the build on
  path leaks, real secrets, tracked runtime files, or files
  > 1 MB.

## 5. Operational state at release time

| Metric | Value |
| --- | --- |
| `records` | 835 |
| `known_retired` | 4 (audited, not blocking) |
| `blocking_unresolved` | 0 |
| `strict integrity` | PASS |
| `readiness` | PASS (4/4) |
| `public_demo_ready` | true |
| `digest_ready` | true |
| latest nightly batch | 2026-06-16 02:00 — 20 selected, 0 failed |
| digest history entries | 5 |
| near-dup clusters | 8 (23 records) |
| online gallery | 200 (all 3 endpoints) |
| online digest | 200 (all 3 endpoints) |
| Telegram text | sent (message_id 23707) |
| Telegram MEDIA | sent (message_id 23709) |

### Daily cron rhythm

| Time (Asia/Shanghai) | What runs | Log |
| --- | --- | --- |
| 01:30 | `artvee_nightly_wrapper.sh refill` | `logs/wrapper_refill.log` |
| 02:00 | `artvee_nightly_wrapper.sh batch` | `logs/wrapper_batch.log` |
| 02:30 | `confirm_demo_refresh.sh --no-telegram` | `logs/confirm_demo_refresh/cron_stderr.log` |
| 03:00 | `artvee_daily_health_check.sh --online --media` | `logs/daily-health-cron/daily_health_YYYYMMDD_030000.log` |
| manual | `publish_demo_refresh_candidate.sh --approve` | (no auto-run) |

Refill and nightly batch are the only cron jobs that touch the
network; everything else is local. Publish to GitHub Pages is
**always** a manual `--approve` step, never a cron step.

## 6. Upgrade notes from v0.2.0-alpha

There is **no in-place migration path**, because the data
surface (images / metadata / thumbs / web/data) is intentionally
not tracked. The repo is regenerated from a working data
directory on the maintainer's local host and then pushed.
Forks or fresh clones should:

1. Clone the repo.
2. Populate their own `images/`, `metadata/`, and `index/`
   directories (any data source that conforms to the
   `web/data/artworks.json` schema in
   [docs/GALLERY_PUBLIC_USAGE.md](GALLERY_PUBLIC_USAGE.md) —
   see also [docs/GALLERY_DATA_SCHEMA.md](GALLERY_DATA_SCHEMA.md)).
3. Run the daily wrapper, then `confirm_demo_refresh.sh`, then
   the public-demo export, then (optionally) the manual
   `publish_demo_refresh_candidate.sh --approve`.

**What changed in the tracked code between v0.2.0-alpha and v0.2.0:**

| Change | Why | Files |
| --- | --- | --- |
| `artvee_daily_health_check.py` — split `except Exception` into `HTTPError` / `URLError` / `TimeoutError` / `ConnectionError`; new `online.kind`, `online.gallery_error`, `online.digest_error`; `recommended_action` branches by kind | During Day 2 the health script masked real HTTP 404s as `0, 0`. After this fix a future Pages content drift is reported with the correct code. | `scripts/artvee_daily_health_check.py` (only) |
| New `docs/STABLE_READINESS_v0.2.0.md` | Documents the 15 / 15 readiness criteria that gate this release. | `docs/STABLE_READINESS_v0.2.0.md` (new) |
| New `docs/V0_2_OBSERVATION_WINDOW.md` Day 3 log | Closes the 3-day observation window. | `docs/V0_2_OBSERVATION_WINDOW.md` |
| New `docs/RELEASE_NOTES_v0.2.0.md` (this file) | The stable release notes. | `docs/RELEASE_NOTES_v0.2.0.md` (new) |
| `CHANGELOG.md` — v0.2.0 section added | Records the post-alpha hardening. | `CHANGELOG.md` |
| `README.md` — Latest release bumped from `v0.2.0-alpha` to `v0.2.0` | Surfaces the new release. | `README.md` |
| `docs/PROJECT_STATUS.md` — `P7E+3` closed, `P7F` row added, `v0.2.0 stable release` row added | Phase markers and release snapshot. | `docs/PROJECT_STATUS.md` |
| `docs/ROADMAP.md` — `P7F` moved to completed, `v0.2.0 stable` moved to completed, next: P8 / content product polish | Roadmap updated. | `docs/ROADMAP.md` |

**Cross-repo follow-up (in the shared Pages repo, not in this
artvee repo):** the new `scripts/check-project-publish-guard.py`
+ `docs/PAGES_PUBLISH_GUARD.md` shipped in the Pages repo so
that future WBW SpaceX Mars publish runs cannot silently
clobber the `projects/artvee-gallery-*` subtrees. The artvee
repo itself is not affected.

## 7. Safety boundaries

The same boundaries documented in
[docs/OPEN_SOURCE_BOUNDARIES.md](OPEN_SOURCE_BOUNDARIES.md) and
the v0.2.0-alpha release notes still apply. Quick recap:

- **No network is opened by the readiness check, the syntax
  checks, or the daily health cron offline modes.** The
  `--online` flag adds an HTTP HEAD-style probe; no auth, no
  cookies.
- **No GitHub Pages push is automatic.** The publish helper
  refuses to run without `--approve` and writes its bundle to
  `dist/` for inspection first.
- **No tokens, chat ids, or bot tokens are tracked.** The
  Telegram notifier resolves the chat id from the
  `ARTVEE_TELEGRAM_CHAT_ID` env var, then from the OpenClaw
  config; resolution is hard-fail if neither is set.
- **MEDIA delivery failure is non-fatal.** A failure-only
  fallback sends a short text-only warning when health is
  PASS but the Markdown attachment was rejected.
- **No destructive commands run unattended.** `trash` is
  preferred over `rm` in dev scripts; the cron jobs are
  append-only by construction.
- **No runtime data is tracked.** `images/`, `metadata/`,
  `thumbs/`, `dist/`, `digests/`, `logs/`, `inbox/`,
  `web/data/*.json` (except `.gitkeep`), `index/`,
  `reports/runtime/`, and `tmp/` are git-ignored. The
  readiness CI fails the build if any of them appear in the
  tracked set.

## 8. Known limitations

- The Telegram notifier depends on a local OpenClaw CLI as the
  message bridge. Users without that bridge can simply skip
  the notify step (the wrapper isolates it with `|| true`).
- The repo does **not** include a corpus. To exercise the
  local UI shell, the user must populate `images/`,
  `metadata/`, and `index/` locally.
- The status report uses `KNOWN_RETIRED` to mark the four
  source URLs that have been removed from the upstream
  archive. They are audited, not blocking, and they are
  listed in `reports/runtime/p6b-known-retired-urls.json` for
  transparency. Promoting them into the public demo's UI is
  deferred to a follow-up.
- The `--simulate-media-failure` flag on the daily health
  check is a testing-only convenience. It is **not** used in
  cron.
- The signal-distortion fix in `artvee_daily_health_check.py`
  is new in v0.2.0; the daily cron has been running with it
  since 2026-06-15 07:39 (during the Day-2 recovery), and
  the first 7 days of clean runs are watched before the
  branch is considered "settled".

## 9. Next steps

- **P8 automation polish** — pre-flight `--dry-run` on the
  publish helper; optional 02:55 *pre-check* cron that runs
  the daily check in `--no-telegram` mode and alerts only on
  FAIL; CI matrix that exercises the cron installer in a
  container.
- **Content product polish** — promote the `KNOWN_RETIRED`
  table into the public demo's UI; consider a per-artist
  collection view; tune the digest `--max-per-artist` and
  `--exclude-risk` defaults if user feedback warrants it.
- **Watch the P7E+2 signal-distortion fix for 7 days of clean
  runs** (i.e. through 2026-06-23) before considering the
  `online.kind` branches fully settled.
- **Long-term direction** — see
  [docs/ROADMAP.md](ROADMAP.md) § 4 and onwards.

## 10. Acknowledgements

- Data source: [artvee.com](https://artvee.com) public-domain
  art archive.
- The local-first / open-source boundary pattern is inspired
  by the standard "thin shell, fat scripts" approach for data
  tooling.
- The Telegram delivery state model is the project-private
  "thin harness, fat skills" approach: each delivery track
  reports its own `attempted` / `sent` / `message_id` /
  `error`, so partial failures stay observable.

---

*Released 2026-06-16 as the first stable daily-operable release
of Artvee Gallery. See [CHANGELOG.md](../CHANGELOG.md) for the
chronological change log and
[docs/STABLE_READINESS_v0.2.0.md](STABLE_READINESS_v0.2.0.md)
for the readiness assessment.*