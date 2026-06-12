# Release Notes · v0.2.0-alpha

> v0.2.0-alpha turns Artvee Gallery from an open-source local
> gallery builder (v0.1.0-alpha) into a daily-operable local-first
> visual archive system with public demos, curated daily digests,
> status reporting, and Telegram health delivery.

## 1. Summary

This release consolidates P3D through P7B+1: a public GitHub
repository with a running CI gate, a public daily-digest page, a
content-healing pipeline, visual QA, near-duplicate review, a
30-day digest history, an approved-publish helper, a daily health
check, and a cron-installed Telegram delivery with MEDIA staging
and a failure-only fallback. The system is designed to be safe to
run unattended on a single host: nothing destructive is automatic,
the publish step is always manual, and the data surface is
machine-checked at every push.

## 2. Highlights

### Public surfaces (live)
- **Public Gallery Demo** — curated thumbnails only, served from
  GitHub Pages: <https://conanxin.github.io/projects/artvee-gallery-demo/>
- **Public Daily Digest** — a separate page that surfaces the
  30-day digest history: <https://conanxin.github.io/projects/artvee-gallery-digest/>

### Local capabilities
- Local-first gallery browser (P1) with thumbnails at 256 / 512 px
  and a search / filter / detail-modal UI shell.
- Daily inspiration digest with deterministic 30-day history and
  near-duplicate-aware selection (P3B, P6F).
- Filename collision healing (P4B) and audited KNOWN_RETIRED
  handling for sources the upstream archive has removed (P6B,
  P6G).
- Visual QA contact sheets and curation filters (P5D, P5E).
- Near-duplicate review workflow with contact sheets and an
  audit trail (P6C).
- Approved-publish helper (P6F+1) that pre-stages the GitHub
  Pages bundle and waits the 90-second CDN warm-up window.

### Operations
- Daily health check (P7A) with a JSON report that distinguishes
  integrity, readiness, candidate state, digest history, and
  near-dup cluster counts.
- Open-source readiness CI (P3C, P3D) that fails the build on
  path leaks, real secrets, tracked runtime files, or files
  > 1 MB.
- Daily health Telegram cron at 03:00 Asia/Shanghai (P7B) with
  a failure-only fallback (P7B+1): when MEDIA delivery fails but
  health is PASS, a short text-only warning is sent.
- Idempotent, marker-based cron installer (P7B) that bakes
  `PATH` and the chat id env into the cron line so OpenClaw
  resolves from the cron env.

## 3. Operational state at release time

| Metric | Value |
| --- | --- |
| records | 776 |
| known_retired | 4 (audited, not blocking) |
| blocking_unresolved | 0 |
| strict integrity | PASS |
| public demo ready | true |
| digest ready | true |
| latest nightly | 2026-06-13 02:00 — 20 selected, 0 failed |

## 4. Daily cron rhythm

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

## 5. What is included vs. not included

### Included
- Source code under `scripts/`, `web/`, `examples/`, `data/` (small).
- Documentation under `docs/`.
- CI workflow under `.github/workflows/`.
- `.gitignore`, `LICENSE` (MIT), `README.md`, `CHANGELOG.md`.

### Not included (by design)
- `images/` — full original image archive (large; regenerable).
- `metadata/` — full scraped metadata (large; regenerable).
- `thumbs/{256,512}/` — generated thumbnails (regenerable).
- `dist/` — exported public bundles (regenerable).
- `digests/` — generated daily digest corpus (regenerable).
- `logs/` — runtime logs (regenerable; deliberately not
  committed for privacy).
- `reports/runtime/` — runtime status and contact sheets
  (regenerable).
- `web/data/*.json` (except `.gitkeep` placeholders) — generated
  gallery / digest / stats JSON.
- Local machine paths, tokens, chat ids, or bot tokens.

The readiness CI enforces this boundary on every push; a
violation fails the build. See
[docs/OPEN_SOURCE_BOUNDARIES.md](docs/OPEN_SOURCE_BOUNDARIES.md).

## 6. Upgrade notes from v0.1.0-alpha

There is no in-place migration path because v0.1.0-alpha did
not include a corpus. The repo is regenerated from a working
data directory on the maintainer's local host and then pushed.
Forks should:

1. Clone the repo.
2. Populate their own `images/`, `metadata/`, and `index/`
   directories (any data source that conforms to the
   `data/artworks.json` schema in
   [docs/GALLERY_PUBLIC_USAGE.md](docs/GALLERY_PUBLIC_USAGE.md)).
3. Run the daily wrapper, then `confirm_demo_refresh.sh`, then
   the public-demo export, then (optionally) the manual
   `publish_demo_refresh_candidate.sh --approve`.

The new wrapper path-agnosticism from v0.1.0-alpha still
applies; nothing in this release adds machine-specific paths
back into the tracked code.

## 7. Safety model

- **No network is opened by the readiness check, the syntax
  checks, or the daily health cron.** The cron uses `--online`
  to check the public demo and digest URLs, but only via HTTP
  HEAD-style probes — no auth, no cookies.
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
  listed in `data/p6b-known-retired-urls.json` for
  transparency.
- The `--simulate-media-failure` flag on the daily health
  check is a testing-only convenience. It is **not** used
  in cron.

## 9. Next steps

- **v0.2.0 observation window** — let the cron run for a few
  days and watch for any MEDIA delivery regressions, with the
  failure-only fallback as the safety net.
- **P8 automation polish** — small follow-ups: a pre-flight
  `--dry-run` mode on the publish helper, a 02:55 *pre-check*
  cron that runs the daily check in `--no-telegram` mode and
  alerts only on FAIL, and a small CI matrix that exercises
  the cron installer in a container.
- **v0.2.0 stable** — after the observation window, cut a
  stable release with the `KNOWN_RETIRED` table moved into
  the public demo's UI.

See [docs/ROADMAP.md](docs/ROADMAP.md) for the long-term
direction.

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
