# Changelog

All notable changes to Artvee Gallery are documented here. The
format is based on [Keep a Changelog](https://keepachangelog.com/),
and the project adheres to [Semantic Versioning](https://semver.org/)
in the form `vMAJOR.MINOR.PATCH-stage` (pre-1.0).

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
