# Post-Stable Operations (P8A)

> Artvee Gallery · One-command ops status after v0.2.0 stable release
> Authored: 2026-06-18
> Status: **Live** — verified end-to-end with one real Telegram + MEDIA
> send (message_id=25149, transport healthy, no side effects).

## 1. Purpose

After the v0.2.0 stable release, operators need **one** read-only
command that answers the question *"is the gallery healthy and is
there anything for me to look at?"*. That command is:

```bash
bash scripts/artvee_ops_status.sh --online --include-pages
```

It aggregates repo state, gallery records, integrity, readiness,
candidate readiness, pending MEDIA, OpenClaw transport health,
Pages guard availability, and live public-demo HTTP status into a
single JSON + Markdown report.

The command is **strictly read-only by default**. It does not
download, refill, run nightly batch, push Pages, approve candidates,
replay pending media, or install new cron. With `--media` it sends
the generated report through the same staged-MEDIA / fallback
pipeline the daily health check uses.

## 2. Daily operating model

Two complementary commands, two different cadences:

| command | cadence | writes | purpose |
|---|---|---|---|
| `bash scripts/artvee_daily_health_check.sh --online --media` | 03:00 cron | `reports/runtime/daily-health/...` + optional Telegram | continuous monitoring, alerting, MEDIA fallback |
| `bash scripts/artvee_ops_status.sh --online --include-pages` | on-demand, before/after ops work | `reports/runtime/ops/...` | one-shot health snapshot for operator review |

The daily health cron still owns:

* running the 03:00 transport probe
* counting pending / quarantined MEDIA
* sending the daily report + digest fallback to Telegram
* flagging `recommended_action`

The new ops status command **only** adds an on-demand, one-shot
aggregator. It does not duplicate the cron; it just gives operators
a single number to look at when they're already at the keyboard.

## 3. Ops status command

```bash
# Default: read-only, no Telegram, no online probe, no Pages touch.
bash scripts/artvee_ops_status.sh

# Add public URL HEAD probes (gallery + digest).
bash scripts/artvee_ops_status.sh --online

# Add a read-only check of the local Pages repo working tree.
bash scripts/artvee_ops_status.sh --include-pages

# Both — closest to "full picture", still no Telegram.
bash scripts/artvee_ops_status.sh --online --include-pages

# Send the report to Telegram + MEDIA (staged via the same path the
# daily health check uses; never sends the raw report path).
bash scripts/artvee_ops_status.sh --online --include-pages --media

# Explicit skip Telegram (defensive; also the default if --media absent).
bash scripts/artvee_ops_status.sh --no-telegram

# Custom date (default: today).
bash scripts/artvee_ops_status.sh --date 2026-06-18

# Emit JSON to stdout for piping.
bash scripts/artvee_ops_status.sh --json
```

The command writes:

* `reports/runtime/ops/artvee-ops-status-<date>.json`
* `reports/runtime/ops/artvee-ops-status-<date>.md`

Both are runtime outputs (under `.gitignore`) and never committed.

## 4. Status fields

The JSON / Markdown report covers (no field is fabricated; missing
sources are reported as `unknown`):

| field | source | meaning |
|---|---|---|
| `date` | arg | Status date (default: today) |
| `repo_head` | `git rev-parse --short HEAD` | Current commit |
| `release_version` | `git describe --tags --abbrev=0` | Latest semver tag (`v0.2.0`) |
| `repo_clean` | `git status --porcelain` | Working tree clean? |
| `records` | `reports/runtime/artvee-status-report.json` | artworks.json count |
| `known_retired` | status_report | URLs marked retired (4 expected) |
| `blocking_unresolved` | status_report | unresolved losers (0 = healthy) |
| `strict_integrity` | latest daily health `checks.integrity` | strict integrity check |
| `readiness` | latest daily health `checks.readiness` | open-source readiness check |
| `candidate_gallery_ready` | latest daily health `checks.candidate_state` | gallery candidate publishable? |
| `candidate_digest_ready` | latest daily health `checks.candidate_state` | digest candidate publishable? |
| `digest_history_entries` | latest daily health `checks.digest_history` | cumulative digest count |
| `near_dup_clusters` | latest daily health `checks.near_dup_clusters` | cluster count |
| `nightly_batch_status` | latest daily health `checks.nightly_batch` | last nightly batch result |
| `pending_media_count` | `_scan_pending_media()` helper | pending MEDIA total |
| `pending_media_replayable` | helper | pending with attempts < 3 |
| `quarantined_media_count` | helper | pending with attempts >= 3 |
| `transport_status` | `check_openclaw_transport.py` | `ok` / `error` / `timeout` / `missing` / `not_checked` |
| `transport_latency_ms` | transport probe | version probe latency |
| `daily_health_cron_installed` | `crontab -l` | 03:00 cron present? |
| `latest_health_report` | glob | path to most recent daily health JSON |
| `latest_health_telegram_status` | daily health | `sent` / `not_attempted` / `error` |
| `public_gallery_url` | constant | live demo URL |
| `public_digest_url` | constant | live digest URL |
| `online_gallery_status` | `curl --head` (with `--online`) | HTTP code (200 / 404 / 0) |
| `online_digest_status` | `curl --head` (with `--online`) | HTTP code (200 / 404 / 0) |
| `pages_guard_available` | file presence | `scripts/check-project-publish-guard.py` and `docs/PAGES_PUBLISH_GUARD.md` both exist? |
| `pages_repo_clean` | `git status` (with `--include-pages`) | `true` / `false` / `unknown` (read-only) |
| `recommended_action` | derived | one of the canonical enum values |

## 5. Recommended actions

The `recommended_action` field is a single canonical enum value,
chosen by the first matching rule in this priority order:

1. `attention_required_integrity_failure` — `strict_integrity != PASS`
2. `attention_required_readiness_failure` — `readiness != PASS`
3. `attention_required_pages_content_drift` — online gallery or
   digest returns 404 (only checked with `--online`)
4. `attention_required_media_pending` — `pending > 0` or `replayable > 0`
5. `candidate_ready_manual_publish_optional` — both candidate gallery
   and candidate digest are ready, but no pending MEDIA / no failures
6. `healthy_no_action` — none of the above

Known retired URLs (4) and quarantined MEDIA (1 from P7B+3 test)
**do not** trigger any failure action. `known_retired` is a list of
documented, expected retirements. `quarantined` MEDIA is a record of
a past failure that has been safely archived; the original file
still lives under `reports/runtime/daily-health/quarantine/` and is
not pending replay.

The exact text of `recommended_action` is **stable** — adding new
values requires a docs + script change. The Markdown summary
re-states it on its own line so a quick scan of the report is
sufficient.

## 6. Media replay

`artvee_ops_status.sh` is **strictly report-only** about pending
MEDIA. It never auto-replays. The fields it exposes:

* `pending_media_count` — total `.fallback-pending-*.json` files
  awaiting replay
* `pending_media_replayable` — same as above, filtered to those
  with `attempts < 3` and a still-existing staged file
* `quarantined_media_count` — pendings archived to
  `reports/runtime/daily-health/quarantine/`
* `media_replay_cron_installed` — whether the optional P8D cron
  is registered (`crontab -l` marker scan)
* `media_replay_cron_summary` — the latest
  `reports/runtime/media-replay/cron-*.json` summary:
  `date`, `outcome` (`noop_zero_pending` / `replayed_pending` /
  `skipped_locked` / `skipped_transport_unavailable` /
  `dry_run_completed` / `error_helper_import`),
  `pending_before`, `transport_status`, `lock_held`, etc.

To actually replay, use the dedicated P7B+3 command:

```bash
python3 scripts/replay_pending_media.py           # dry-run, plan only
python3 scripts/replay_pending_media.py --apply   # real send, archive
```

See `docs/MEDIA_REPLAY.md` for the full workflow.

### 6.1 Optional media replay cron (P8D)

The P8D cron is **optional** and **not installed by default** (it is
opt-in via `bash scripts/install_media_replay_cron.sh --install`).
When installed, it runs at 03:10 (10 minutes after the 03:00
daily-health cron) under `CRON_TZ=Asia/Shanghai`, and only fires
when there is deferred pending MEDIA from a previous transport
failure.

> **P8D+1 (2026-06-29)**: the installer template was fixed to put
> `CRON_TZ=` and `PATH=` on their own lines above the schedule. The
> previous template produced `CRON_TZ=Asia/Shanghai 10 3 * * * cd ...`
> (7 fields) which cron silently rejected — symptom was an empty
> `logs/media-replay-cron/` and no `reports/runtime/media-replay/cron-*.json`.
> Re-running `--install` from the patched template produces a
> 5-field schedule that cron actually accepts. Refill / batch /
> confirm-refresh gained the same `CRON_TZ=` / `PATH=` lines via the
> new `scripts/install_artvee_cron.sh` (P8D+1 unified installer).
It exists for operators who want pending MEDIA to flush
automatically 10 minutes after the 03:00 daily-health cron.

| aspect | value |
|---|---|
| Default time | `10 3 * * *` (10 minutes after P7B 03:00 daily health) |
| Timezone | `CRON_TZ=Asia/Shanghai` |
| Cron command | `cd <artvee-repo> && bash scripts/artvee_media_replay_cron.sh --limit 5 --max-retries 3 >> logs/media-replay-cron/media_replay_cron.log 2>&1` |
| Default args | `--limit 5 --max-retries 3` |
| Concurrency guard | `flock -n` on `reports/runtime/media-replay/.media-replay.lock` |
| Transport pre-flight | on by default; if `check_openclaw_transport.py` ≠ ok, skip replay (pending stays for next run, no Telegram fallback spam) |
| `pending=0` behavior | silent — only writes `reports/runtime/media-replay/cron-<date>.json` |
| Side effects on success | `replay_pending_media.py --apply` runs, sends via staged-only MEDIA, moves pendings to `replayed/` or `quarantine/` |
| Side effects on failure | (a) transport down → log + skip; (b) transport up but send fails → `replay_pending_media.py` increments `attempts`; quarantine at 3 |
| NEVER | trigger download / refill / nightly batch / Pages push / `--approve` / retired URL retry / Telegram fallback text / MEDIA allowlist widen |

**Install (idempotent marker-block based):**

```bash
bash scripts/install_media_replay_cron.sh --dry-run      # preview
bash scripts/install_media_replay_cron.sh --install     # install with defaults
bash scripts/install_media_replay_cron.sh --install --time "15 3 * * *"
bash scripts/install_media_replay_cron.sh --remove       # preserves other cron blocks
```

The installer wraps its cron entry between
`# >>> Artvee P8D media replay cron BEGIN … # <<< Artvee P8D media replay cron END`
so re-installing replaces in-place, and `--remove` only deletes the
P8D block (P7B daily-health cron, refill / batch cron, etc. are
untouched).

## 7. Pages guard (P8A + P8A+1)

Pages guard is intentionally **read-only**. The command:

* **P8A+1 fix:** the guard files are looked up in the **Pages
  repo** (e.g. `<pages-repo>/scripts/check-project-publish-guard.py`
  and `<pages-repo>/docs/PAGES_PUBLISH_GUARD.md`), **not** in the
  Artvee repo. PAGES-GUARD-1 installed the guard in the Pages repo
  itself, which is its natural home; P8A originally looked inside
  the Artvee repo and reported a false `pages_guard_available=false`.
* Reports `pages_guard_available=true` (top-level) only if both
  the guard script and the doc are present *in the Pages repo*.
* With `--include-pages` and `--pages-repo <pages-repo>`, runs
  `git status --porcelain` in `<pages-repo>` and reports
  `pages_repo_clean=true|false|unknown`.
* With `--include-pages` and the guard present, also runs the
  guard in read-only mode (`--base origin/main` + the canonical
  artvee allowlist) and reports `pages.guard_smoke=pass|fail|skipped`.
* Never modifies the Pages repo, never runs `rsync`, never commits,
  never pushes, never executes the destructive half of any guard
  script. A guard-smoke failure does **not** make the script fail
  exit code; it is recorded under `pages.error` so a transient
  OpenClaw / Pages issue cannot prevent the rest of the report.

### Pages repo resolution order

1. CLI `--pages-repo <path>`
2. env `ARTVEE_PAGES_REPO`
3. env `PAGES_REPO`
4. default: `Path.home() / "conanxin.github.io"`

`pages.resolved_via` records which one yielded the path. If the
user passes an explicit path that does not exist, ops status falls
through to the next candidate and reports the resolved result
honestly (the explicit-but-missing path is not silently accepted).

If the operator needs to *act* on a Pages drift signal, they should
read `docs/PAGES_PUBLISH_GUARD.md` (in the Pages repo) and follow
the recovery procedure manually.

## 8. Manual approved publish

`artvee_ops_status.sh` does not publish, does not approve, and does
not invoke any candidate-publish script. The candidate state is
read and reported only.

When `recommended_action == candidate_ready_manual_publish_optional`,
the operator should still use the dedicated manual command:

```bash
bash scripts/publish_demo_refresh_candidate.sh --dry-run   # see what would happen
bash scripts/publish_demo_refresh_candidate.sh             # actually publish
```

The ops status command makes the readiness *visible*; it does not
remove the explicit `--approve` gate.

## 9. What not to automate yet

After v0.2.0 stable, several things are deliberately still manual:

* **Replaying pending MEDIA.** The cron at 03:00 reports; a separate
  step (operator or future 03:10 cron, not installed) replays.
  See `docs/MEDIA_REPLAY.md` § 6.
* **Publishing candidate demos.** `publish_demo_refresh_candidate.sh`
  requires explicit `--approve`. The ops status command makes the
  readiness *visible*; it does not auto-approve.
* **Pages repo restoration after content drift.** PAGES-GUARD-1
  has installed `scripts/check-project-publish-guard.py` and
  `docs/PAGES_PUBLISH_GUARD.md` *in the Pages repo*. The P8A+1
  ops status command can now run that guard in read-only mode
  (see § 7 above); the *destructive* half of the guard is still
  manual, controlled by the operator following the recovery doc.
  Pages drift recovery is a manual decision based on the
  `pages_repo_clean=false` or `pages.guard_smoke=fail` signal.
* **Adding new cron jobs.** The 03:00 daily health cron is the only
  cron this phase relies on. New crons are explicitly NOT installed
  by P8A.
* **Auto-aggregating ops status on a schedule.** The ops status
  command is on-demand. A future 06:00 "morning briefing" cron is
  out of scope for v0.2.x.

## 10. Troubleshooting

| symptom | likely cause | action |
|---|---|---|
| `records=0` | `artvee-status-report.json` missing | run `python3 scripts/build_artvee_status_report.py` (does not download; reads existing artefacts) |
| `readiness=UNKNOWN` | no daily health report yet | run the daily health check first; ops status depends on it for the readiness / integrity / candidate fields |
| `transport_status=error` | OpenClaw gateway not running or PATH wrong | see `docs/MEDIA_REPLAY.md` § 6 — does not block ops status, but you should fix before sending the next Telegram |
| `pages_repo_clean=unknown` | `<pages-repo>` not a git repo, or `--include-pages` not passed | re-run with `--include-pages`; or check the path |
| `telegram: status=skipped error=chat id resolve...` | `ARTVEE_TELEGRAM_CHAT_ID` not set | set the env var (or use the cron-style invocation); see `scripts/install_daily_health_cron.sh` for the canonical line |
| `recommended_action=attention_required_integrity_failure` | strict integrity check failed | run `python3 scripts/check_gallery_integrity.py --strict` to see why; fix and re-run |
| `recommended_action=attention_required_pages_content_drift` | online 404 | re-run `bash scripts/publish_demo_refresh_candidate.sh --dry-run`; do not auto-publish |
| `recommended_action=attention_required_media_pending` | real pending MEDIA exists | inspect `reports/runtime/daily-health/.fallback-pending-*.json`; if staged path still valid, `python3 scripts/replay_pending_media.py --apply` |
| Cron is installed locally but `daily_health_cron_installed=false` | `crontab -l` returned non-zero or the marker is missing | re-run `bash scripts/install_daily_health_cron.sh` (it is idempotent) |

## 11. Related

* `scripts/artvee_ops_status.sh` / `scripts/artvee_ops_status.py` — this command
* `scripts/artvee_daily_health_check.sh` — the 03:00 cron command
* `docs/DAILY_OPERATING_PLAYBOOK.md` — daily operating model
* `docs/MEDIA_REPLAY.md` — pending MEDIA replay workflow (P7B+3)
* `docs/DEVELOPMENT.md` § 25 — script design notes
* `docs/RETROSPECTIVE.md` § 2.22 — design lessons

## 12. Public content polish (P8B)

P8B ships two product-facing changes to the public Pages
bundle: a *product info card* on the Gallery page, and a
*30-day digest history archive* on the Digest page. Both
changes are applied at **export time**, not by editing
`web/` or `digests/`; this keeps the local UI and the public
bundle as two separate surfaces with their own code paths.

### 12.1 Gallery info card

`scripts/export_artvee_gallery_public_demo.py` injects a
small info card at the top of the public `index.html` (right
after the existing `.brand` block, before the `.stats`
block). The card surfaces:

* demo title (`Artvee Gallery Demo`)
* release version (auto-detected via `git describe --tags --abbrev=0`; falls back to `v0.2.0`)
* Last-updated date (`stats_src.last_downloaded_at` cast to `YYYY-MM-DD`)
* public-record count + honest "Source archive: local-first
  full archive, not fully published" disclosure
* canonical links (Daily Digest / GitHub repo / `<release>`
  / About this demo)

Constraints enforced at the export layer:

* No local-absolute path, no `metadata/`, no `images/`, no
  home-directory substring, no local project-root substring
  in any public text file (enforced by the post-export leak
  check).
* No front-end framework dependency — the card uses inline
  CSS so the existing `style.css` does not need to grow.
* The injection is **idempotent** — re-running the export
  does not stack cards.

### 12.2 Digest history archive

`scripts/export_artvee_digest_public_page.py` now writes
two new files alongside the existing digest bundle:

* `archive.html` — a 30-day rolling table (date / strategy /
  picks / categories / near-dup cluster). Text-only by
  design; the per-pick 512-thumb is reached from
  `data/digests.json` and the per-day digest HTML.
* `data/digest-history.json` — a *public-safe* projection of
  `reports/runtime/digest-history.json`. The `digest_path`
  field (which contains a local-absolute path even after the
  digest builder's substring redaction) is **stripped**
  before going public; everything else (`date`, `picks[].{id,
  artist, category, near_dup_cluster_id}`, `strategy`,
  `updated_at`, `window_days`) is preserved.

The archive page is **honest** about the history size: if
the digest has only run for N days, the page shows
"History entries currently available: N" rather than a
fabricated 30 days. When the rolling history fills, the
note disappears.

### 12.3 QA additions in `confirm_demo_refresh.sh`

* P8B archive QA: asserts `archive.html` +
  `data/digest-history.json` exist, parse, and contain no
  forbidden substrings. The QA also asserts that no
  `digest_path` field leaks into the public history.
* Digest size budget: 5MB soft / 10MB hard. A digest bundle
  is text + 1-5 thumbs; if it ever grows past 10MB something
  has gone wrong (a full image slipped in, or 1000 picks
  were exported by mistake).

### 12.4 The split between `web/` and the public bundle

| Surface | Source of truth | Modified by |
|---|---|---|
| Local UI (this repo) | `web/index.html`, `web/app.js`, `web/style.css` | Hand-edited, committed to Artvee |
| Local digest | `digests/artvee-digest-*.md` + `.html` | `build_artvee_daily_digest.py` (deterministic) |
| Public Gallery bundle | `dist/artvee-gallery-public-demo/` | `export_artvee_gallery_public_demo.py` |
| Public Digest bundle | `dist/artvee-gallery-digest-public/` | `export_artvee_digest_public_page.py` |
| Live Pages | `conanxin.github.io/projects/artvee-gallery-{demo,digest}/` | `publish_demo_refresh_candidate.sh --approve` + Pages guard |

The export layer is the **only** place where the public
bundle is touched. `web/` is for the local-first
single-user experience; the export layer is for the
public-curated subset. Mixing them in either direction
would either leak internal strings or strip them from the
local UI. P8B keeps that boundary clean by treating the
export layer as a separate pipeline with its own
allow-list, leak check, and redaction-aware projection.

### 12.5 What P8B does *not* do

* Does **not** publish the full local archive. The
  Gallery card says so explicitly.
* Does **not** fabricate archive rows. If the history
  is short, the archive page says so explicitly.
* Does **not** push to GitHub Pages without an explicit
  `--approve` to `publish_demo_refresh_candidate.sh`.
  The Pages guard (`scripts/check-project-publish-guard.py`
  in the Pages repo) is a separate, independent check
  that the publish helper does not auto-invoke.
* Does **not** widen the Pages allowlist. The allowlist
  remains `projects/artvee-gallery-demo`,
  `projects/artvee-gallery-digest`, and `projects/data.json`.

### 12.6 P8C public archive navigation polish

P8C extends P8B's archive by adding **digest cards**,
**client-side filters**, and **history schema polish** while
keeping the same allow-list and the same `readiness` /
`strict integrity` gates:

* `scripts/export_artvee_digest_public_page.py` now writes
  `archive.html` (cards + filters), `archive.js` (~4.3 KB,
  vanilla, no framework, no external CDN), and the same
  `data/digest-history.json` with a richer top-level
  `summary` block.
* `scripts/confirm_demo_refresh.sh` archive QA now asserts
  `day_cards == history_entries`, all 5 nav/filter IDs
  present in `archive.html`, `archive.js` size ≥ 1 KB and
  references `applyFilters` + `populateSelect`, and that
  `assets/thumbs/256/` is non-empty.
* `data/digest-history.json` schema additions (P8C):
  - `generated_at` (alias of `updated_at`)
  - `history_entries` (count)
  - `available_range.{first_date, latest_date}`
  - `summary.{total_days, total_picks, unique_artists, top_categories}`
  - `entries[]` shape **unchanged** from P8B for backward
    compatibility
* The archive page is fully readable with JS disabled.
* Bundle size stays well under the P8B 5MB soft / 10MB hard
  budget (320 KB for the 2026-06-18 candidate: 7 day-cards,
  15 × 256 thumbs, archive.html 19 KB, archive.js 4.3 KB).
* P8C caught and fixed 8 P8B stragglers in docs that
  triggered the `readiness` path-leak check (P8B had left
  literal project-root / home-dir substrings in 5 docs
  while describing the leak-check policy). P8C rewrote
  the meta-descriptions to refer to the abstract
  *project-root* / *home-dir* substrings.

P8C does **not** widen the Pages allowlist, does **not** add
external CDNs, does **not** depend on a JS framework, and
does **not** require a rebuild of the local gallery data.
