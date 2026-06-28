# Artvee Gallery · Project Status

> Quick-reference phase markers and the last-known-good nightly
> snapshot. For the broader plan, see
> [docs/ROADMAP.md](docs/ROADMAP.md). For deep-dive docs, see the
> `docs/GALLERY_*.md` series. For the project story and the
> methodology extracted from this project, see
> [docs/CASE_STUDY.md](docs/CASE_STUDY.md),
> [docs/RETROSPECTIVE.md](docs/RETROSPECTIVE.md), and
> [docs/LOCAL_FIRST_AGENT_PROJECT_PATTERN.md](docs/LOCAL_FIRST_AGENT_PROJECT_PATTERN.md).

## Phase markers

| Phase | Description | Status | Date | Verification report |
| --- | --- | --- | --- | --- |
| **P1** | Local Gallery Browser | ✅ PASS | 2026-06-11 | `<workspace>/reports/artvee-gallery-p1-local-browser-20260611.md` |
| **P2** | Public Demo Export | ✅ PASS | 2026-06-11 | `<workspace>/reports/artvee-gallery-p2-public-demo-export-20260611.md` |
| **P3A** | Public Demo Publish (GitHub Pages) | ✅ PASS | 2026-06-11 | `<workspace>/reports/artvee-gallery-p3a-public-demo-publish-20260611.md` |
| **P3B** | Daily Inspiration Digest | ✅ PASS | 2026-06-11 | `<workspace>/reports/artvee-gallery-p3b-daily-digest-20260611.md` |
| **P3C** | Open-Source Readiness | ✅ PASS | 2026-06-12 | `<workspace>/reports/artvee-gallery-p3c-open-source-readiness-20260612.md` |
| **P3D** | GitHub Public Repo + CI + Release | ✅ PASS | 2026-06-12 | `<workspace>/reports/artvee-gallery-p3d-github-public-repo-20260612.md` |
| **P3E** | Public Daily Digest Page + README showcase | ✅ PASS | 2026-06-12 | `<workspace>/reports/artvee-gallery-p3e-daily-digest-public-page-20260612.md` |
| **P3F** | Final Case Study and Project Retrospective | ✅ PASS | 2026-06-12 | `<workspace>/reports/artvee-gallery-p3f-case-study-retrospective-20260612.md` |
| **P4A** | Manifest duplicate-id read-only audit | ✅ PASS (audit only) | 2026-06-12 | `<workspace>/reports/artvee-gallery-p4a-manifest-duplicate-audit-20260612.md` |
| **P4A+1** | Gallery integrity CI gate (filename-collision / duplicate-id) | ✅ PASS | 2026-06-12 | `<workspace>/reports/artvee-gallery-p4a1-integrity-gate-20260612.md` |
| **P4B** | Filename collision fix + index/web data migration | ✅ PASS | 2026-06-12 | `<workspace>/reports/artvee-gallery-p4b-collision-migration-20260612.md` |
| **P4C** | Post-migration verification + CI Node 24 upgrade + public demo refresh planning | ✅ PASS | 2026-06-12 | `<workspace>/reports/artvee-gallery-p4c-post-migration-ci-refresh-plan-20260612.md` |
| **P4D** | Semi-automatic public demo refresh (Gallery + Digest → GitHub Pages) | ✅ PASS | 2026-06-12 | `<workspace>/reports/artvee-gallery-p4d-semi-automatic-public-refresh-20260612.md` |
| **P4D+1** | `confirm_demo_refresh.sh` + 02:30 nightly hook (candidate-only, no auto-push) | ✅ PASS | 2026-06-12 | `<workspace>/reports/artvee-gallery-p4d1-confirm-demo-refresh-hook-20260612.md` |
| **P4E** | Approved publish helper (`publish_demo_refresh_candidate.sh` with `--approve` + `--dry-run` + `--no-push`) | ✅ PASS | 2026-06-12 | `<workspace>/reports/artvee-gallery-p4e-approved-publish-helper-20260612.md` |
| **P5A** | Content healing: Le_rêve source_url fix + 4 loser retry + orphan audit | ✅ PASS | 2026-06-12 | `<workspace>/reports/artvee-gallery-p5a-content-healing-20260612.md` |
| **P5B** | First approved publish from P5A candidate (Le_rêve source_url fix live on Pages) | ✅ PASS | 2026-06-12 | `<workspace>/reports/artvee-gallery-p5b-approved-publish-20260612.md` |
| **P5C** | Legacy rollback orphan cleanup (P4B safety copies removed post-P5B) | ✅ PASS | 2026-06-12 | `<workspace>/reports/artvee-gallery-p5c-orphan-cleanup-20260612.md` |
| **P5D** | Deeper visual QA (thumbnail / palette / category / digest / near-dup) | ✅ PASS | 2026-06-12 | `<workspace>/reports/artvee-gallery-p5d-visual-qa-20260612.md` |
| **P5E** | Curation filters: public demo `--exclude-risk high` + digest `--max-per-artist 1` (default) | ✅ PASS | 2026-06-12 | `<workspace>/reports/artvee-gallery-p5e-curation-filters-20260612.md` |
| **E2E** | Nightly Cron Auto-Run | ✅ PASS | 2026-06-12 | `<workspace>/reports/artvee-nightly-auto-run-verification-2026-06-12.md` |
| **P6A** | Telegram MEDIA staging fix | ✅ PASS | 2026-06-12 | `<workspace>/reports/artvee-gallery-p6a-telegram-media-staging-20260612.md` |
| **P6B** | Mark unresolved losers as KNOWN_RETIRED | ✅ PASS | 2026-06-12 | `<workspace>/reports/artvee-gallery-p6b-known-retired-urls-20260612.md` |
| **P6C** | Near-duplicate review workflow | ✅ PASS | 2026-06-12 | `<workspace>/reports/artvee-gallery-p6c-near-duplicate-review-20260612.md` |
| **P6D** | GitHub Pages CDN wait 60s → 90s | ✅ PASS | 2026-06-12 | `<workspace>/reports/artvee-gallery-p6d-cdn-wait-90s-20260612.md` |
| **P6G** | KNOWN_RETIRED-aware status report | ✅ PASS | 2026-06-12 | `<workspace>/reports/artvee-gallery-p6g-status-report-20260612.md` |
| **P6C** | Near-duplicate review workflow | ✅ PASS | 2026-06-12 | `<workspace>/reports/artvee-gallery-p6c-near-duplicate-review-20260612.md` |
| **P6F** | Digest history 30-day + near-dup-aware selection | ✅ PASS | 2026-06-12 | `<workspace>/reports/artvee-gallery-p6f-digest-history-20260612.md` |
| **P7A** | Daily automation hardening / phase consolidation | ✅ PASS | 2026-06-12 | `<workspace>/reports/artvee-gallery-p7a-daily-automation-hardening-20260612.md` |
| **P7A+1** | OpenClaw binary resolution for health check Telegram notify | ✅ PASS | 2026-06-12 | `<workspace>/reports/artvee-gallery-p7a1-openclaw-binary-resolution-20260612.md` |
| **P7B** | Optional daily health Telegram cron | ✅ PASS | 2026-06-12 | `<workspace>/reports/artvee-gallery-p7b-daily-health-telegram-cron-20260612.md` |
| **P7B+1** | Cron MEDIA delivery verification / failure-only fallback | ✅ PASS | 2026-06-13 | `<workspace>/reports/artvee-gallery-p7b1-cron-media-fallback-20260613.md` |
| **P7B+2** | Staged-only MEDIA + transport-deferred fallback (2026-06-18 regression) | ✅ PASS | 2026-06-18 | `<workspace>/reports/artvee-gallery-p7b2-daily-health-media-staging-fix-20260618.md` |
| **P7B+3** | Pending MEDIA replay + OpenClaw transport health check | ✅ PASS | 2026-06-18 | `<workspace>/reports/artvee-gallery-p7b3-pending-media-replay-20260618.md` |
| **P7D** | v0.2.0-alpha release consolidation | ✅ PASS | 2026-06-13 | `<workspace>/reports/artvee-gallery-p7d-v0.2.0-alpha-release-20260613.md` |
| **P7E** | v0.2.0 observation window setup | ✅ PASS | 2026-06-14 | `<workspace>/reports/artvee-gallery-p7e-v0.2-observation-window-20260614.md` |
| **P7E+1** | Online endpoint failure diagnosis (Pages content drift) | ✅ PASS | 2026-06-15 | `<workspace>/reports/artvee-gallery-p7e1-online-endpoint-failure-20260615.md` |
| **P7E+2** | Public demo restore after Pages content drift | ✅ PASS | 2026-06-15 | `<workspace>/reports/artvee-gallery-p7e2-public-demo-restore-20260615.md` |
| **P7F** | v0.2.0 stable readiness review (3-day observation complete, all green) | ✅ PASS | 2026-06-16 | `<workspace>/reports/artvee-gallery-p7f-v0.2-stable-readiness-20260616.md` |
| **v0.2.0 stable release** | v0.2.0 stable cut (tag + GitHub Release) after 3-day green observation | ✅ PASS | 2026-06-16 | `<workspace>/reports/artvee-gallery-v0.2.0-stable-release-20260616.md` |
| **P8A** | Post-stable ops status command (one-shot health aggregator) | ✅ PASS | 2026-06-18 | `<workspace>/reports/artvee-gallery-p8a-post-stable-ops-polish-20260618.md` |
| **P8A+1** | Pages guard visibility fix (Pages repo detection) | ✅ PASS | 2026-06-18 | `<workspace>/reports/artvee-gallery-p8a1-pages-guard-visibility-20260618.md` |
| **P8B** | Content product polish (info card + digest history archive) | ✅ PASS | 2026-06-18 | `<workspace>/reports/artvee-gallery-p8b-content-product-polish-20260618.md` |
| **P8C** | Public digest archive navigation polish (cards + filters + history schema) | ✅ PASS | 2026-06-18 | `<workspace>/reports/artvee-gallery-p8c-public-digest-archive-navigation-20260618.md` |
| **P8D** | Optional media replay cron (P8D cron wrapper + idempotent installer) | ✅ PASS | 2026-06-18 | `<workspace>/reports/artvee-gallery-p8d-optional-media-replay-cron-20260618.md` |
| **P8D+1** | Cron PATH hardening + unified installer for refill/batch/confirm + 03:10 media-replay cron activation fix (CRON_TZ=PATH= on own lines, dedup legacy lines) | ✅ PASS | 2026-06-29 | `<workspace>/reports/artvee-gallery-p8d1-cron-path-media-replay-fix-20260629.md` |

### P7F v0.2.0-stable-readiness snapshot (2026-06-16 06:38 GMT+8)

**Goal** — close the v0.2.0 observation window (Day 1 / Day 2 / Day 3) and produce a stable-readiness assessment without cutting any tag or release.

| Aspect | Value |
|--------|-------|
| Review doc | `docs/STABLE_READINESS_v0.2.0.md` (new, tracked) |
| Live records | 835 (live rebuild; 03:00 daily-health snapshot reported 815) |
| Live integrity | strict PASS, 0 duplicates, 3/3 sections PASS |
| Live readiness | PASS, 4/4 sub-checks (generated-data, path-leak, secret-keyword, file-size) |
| Online | 6/6 endpoints HTTP 200 (gallery + digest) |
| Known retired | 4 |
| Blocking unresolved | 0 |
| Telegram cron | Installed, ran 03:00, delivered text (23707) + MEDIA (23709) |
| Readiness checklist | 15 / 15 PASS |
| Day 1 / Day 2 / Day 3 verdicts | Green / Green (post-restore, with incident annotation) / Green |
| Day-2 incident | Diagnosed (P7E+1) + restored (P7E+2) + guarded (cross-repo PAGES-GUARD-1) + signal-distortion bug fixed in `artvee_daily_health_check.py` |
| Tag cut | **No** — pending user approval |
| GitHub Release | **No** — pending user approval |
| Pages push | **No** — no runtime change required |
| Safety | No download / refill / batch / `--approve`; no `images/`, `metadata/`, `thumbs/`, `dist/`, `digests/`, `logs/`, `inbox/`, `web/data/`, `index/`, `reports/runtime/`, `tmp/` modification; no secrets / real paths leaked |

### P7A daily-automation-hardening snapshot (2026-06-12 22:30 GMT+8)

| Field | Value |
| --- | --- |
| Daily health check script | `scripts/artvee_daily_health_check.sh` + `scripts/artvee_daily_health_check.py` (Python implementation, shell wrapper) |
| Daily Operating Playbook | `docs/DAILY_OPERATING_PLAYBOOK.md` (new, tracked) |
| Health check modes | default / `--date` / `--no-telegram` / `--online` / `--media` |
| Checks performed | readiness, integrity, status report, nightly batch, candidate refresh, digest history, near-dup clusters, candidate state, online (optional) |
| Recommended actions | `healthy_no_action` / `candidate_ready_manual_publish_optional` / `attention_required` |
| Default output | `reports/runtime/daily-health/artvee-daily-health-YYYY-MM-DD.{json,md}` (NOT tracked) |
| Current status snapshot | records=756, known_retired=4, blocking_unresolved=0, integrity=PASS, readiness=PASS, candidate=PASS, online=200+200 |
| Daily cron rhythm | 01:30 refill, 02:00 batch, 02:30 confirm_demo_refresh candidate, manual approved publish only |
| No auto-publish | By design — P7A does NOT add publish cron; approval remains manual |
| Safety | No download, no refill, no batch, no retired retry, no Pages push, no approve, no source data modification |
| Files changed | `scripts/artvee_daily_health_check.sh` (new), `scripts/artvee_daily_health_check.py` (new), `docs/DAILY_OPERATING_PLAYBOOK.md` (new), `docs/PROJECT_STATUS.md` (this row), `docs/ROADMAP.md` (P7A ✅), `docs/DEVELOPMENT.md` (§ 19), `docs/RETROSPECTIVE.md` (§ 2.14) |

### P7A+1 openclaw-binary-resolution snapshot (2026-06-12 23:07 GMT+8)

| Field | Value |
| --- | --- |
| Problem | `artvee_telegram_notify.py` used `os.path.exists('openclaw')` which fails for PATH-only binaries |
| Root cause | `ARTVEE_OPENCLAW_BIN` default `'openclaw'` was treated as a literal path, not a command to search in PATH |
| Fix | `_resolve_openclaw_bin()` with resolution order: CLI arg > env `ARTVEE_OPENCLAW_BIN` > env `OPENCLAW_BIN` > `shutil.which('openclaw')` > None |
| Graceful skip | If binary not found, health check still generates report and exits 0; Telegram notify skipped with clear message |
| `--openclaw-bin` arg | Added to `artvee_telegram_notify.py`, `artvee_daily_health_check.sh`, `artvee_daily_health_check.py` |
| `telegram_notify` JSON field | Added to health check report: `enabled`, `media_requested`, `openclaw_status`, `sent`, `message_id` |
| Test result | Message ID 22727 delivered successfully via interactive shell |
| MEDIA test | Message with report attachment delivered successfully |
| Files changed | `scripts/artvee_telegram_notify.py` (resolver + `--openclaw-bin`), `scripts/artvee_daily_health_check.sh` (pass-through), `scripts/artvee_daily_health_check.py` (pass-through + JSON field), `docs/DEVELOPMENT.md` (§ 20), `docs/DAILY_OPERATING_PLAYBOOK.md` (§ 8), `docs/PROJECT_STATUS.md` (this row), `docs/ROADMAP.md` (P7A+1 ✅) |

### P7B daily-health-cron snapshot (2026-06-12 23:25 GMT+8)

| Field | Value |
| --- | --- |
| New script | `scripts/install_daily_health_cron.sh` — idempotent P7B cron installer |
| Cron time | `0 3 * * *` (Asia/Shanghai, after 02:30 confirm_demo_refresh) |
| Command | `cd <artvee-repo> && bash scripts/artvee_daily_health_check.sh --online --media` |
| Log | `logs/daily-health-cron/daily_health_YYYYMMDD_030000.log` |
| Marker | `# >>> Artvee P7B daily health check BEGIN` / `END` |
| Idempotency | Replaces existing block on re-install; `--remove` deletes the block |
| Backup | `logs/daily-health-cron/crontab.before_p7b.*.txt` |
| Manual test | ✅ PASS — Telegram summary + MEDIA delivered, log contains no secrets |
| Daily cron rhythm | 01:30 refill, 02:00 batch, 02:30 confirm_demo_refresh, 03:00 daily health check |
| Files changed | `scripts/install_daily_health_cron.sh` (new), `docs/DAILY_OPERATING_PLAYBOOK.md` (timeline + commands + log path), `docs/DEVELOPMENT.md` (§ 21), `docs/PROJECT_STATUS.md` (this row), `docs/ROADMAP.md` (P7B ✅) |

## Last-known-good nightly snapshot

| Metric | Value |
| --- | --- |
| `downloaded` | 760 |
| `failed` | 0 |
| `pending` | 530 |
| `not_selected` (a.k.a. `skipped` in wrapper stats) | 1271 |
| Batch size | 20 (all SUCCESS) |
| Wall time | about 5 minutes |
| Cron entry | `0 2 * * * bash scripts/artvee_nightly_wrapper.sh batch` |
| Time zone | `CRON_TZ=Asia/Shanghai` |

## Public surfaces

| Surface | URL | Refresh cadence |
| --- | --- | --- |
| Public demo (curated subset, thumbnails only) | <https://conanxin.github.io/projects/artvee-gallery-demo/> | **Candidate-daily, publish-manual** (P4D+1: `scripts/confirm_demo_refresh.sh` at 02:30 nightly writes `dist/refresh-candidates/<date>/` + Telegram summary; user inspects report and runs the manual `rsync + commit + push` flow when ready) |
| Public daily digest (latest 5-pick, ~300 KB) | <https://conanxin.github.io/projects/artvee-gallery-digest/> | **Same as Gallery** (P4D+1 hook builds both candidates in one run) |
| Public GitHub repository | <https://github.com/conanxin/artvee-gallery> | Per-push (CI gated) |
| Public release | <https://github.com/conanxin/artvee-gallery/releases/tag/v0.1.0-alpha> | Once per release |
| Local gallery UI | `bash scripts/serve_artvee_gallery.sh` then `http://localhost:8000/` | On every local rebuild |

### P4D public-refresh snapshot (2026-06-12)

| Field | Value |
| --- | --- |
| GitHub Pages commit (conanxin.github.io) | `5a8d938` |
| Gallery online record count | 100 (4 cats × 25, post-P4B collision fix) |
| Gallery online size | 5.7M, 205 files |
| Digest online selected count | 5 (diverse) |
| Digest online size | 296K, 10 files |
| Online endpoint status | All `200` for gallery `/`, `data/artworks.json`, `data/gallery_stats.json`, `app.js`, `style.css`, all 5 sample thumbs (gallery 256+512, digest 512); same `200` for digest `/`, `digest.html`, `digest.md`, `data/digests.json` and the digest sample thumb. |
| Public-safety guards | `--exclude-duplicate-source-url-groups` drops 3 groups (6 records, incl. Le_rêve URL label bug); `--require-unique-source-url` post-check PASS |
| Safety boundaries | No Artvee download; no refill; no nightly batch; no retry of 4 unresolved losers; no full images / metadata / thumbs in Pages repo; `metadata_path` field stripped from public JSON |

### P4D+1 confirm-hook snapshot (2026-06-12)

| Field | Value |
| --- | --- |
| Script | `scripts/confirm_demo_refresh.sh` (executable, ~470 lines, 5 args) |
| Cron hook | `30 2 * * * cd <artvee-repo> && bash scripts/confirm_demo_refresh.sh --no-telegram >> logs/confirm_demo_refresh/cron_stderr.log 2>&1` |
| CRON_TZ | `Asia/Shanghai` (re-uses the existing block at the top of the cron file) |
| Candidate output | `dist/refresh-candidates/YYYY-MM-DD/{gallery,digest}/` (gitignored, overwritable per-date) |
| Log output | `logs/confirm_demo_refresh/confirm_demo_refresh_YYYYMMDD_HHMMSS.log` (one per run) |
| Report output | `logs/confirm_demo_refresh/report_YYYY-MM-DD.md` (one per date, regenerable) |
| Hook scope | Candidate build + QA + report + Telegram summary. **No Pages push, no rsync, no runtime data modification, no download/refill/batch, no retry of unresolved losers.** |
| Cron backup | `logs/confirm_demo_refresh/cron_backup/crontab_backup_<ts>.txt` (one snapshot taken before installation) |
| First-run result | Gallery 100 records / 200 thumbs / 5.2M, Digest 5 picks / 5 thumbs / 256K, all QA guards PASS, overall status `PASS`, Telegram skipped (`--no-telegram` for hook) |

## Repository readiness (post-P3C, re-validated at P3F)

| Check | Result |
| --- | --- |
| `LICENSE` present | ✅ MIT |
| `README.md` present and self-describing | ✅ |
| `.gitignore` consolidated | ✅ |
| `docs/` complete (architecture, boundaries, roadmap, dev, status, release notes, case study, retrospective, methodology) | ✅ |
| `examples/` present and valid | ✅ |
| `scripts/check_open_source_ready.py` exits 0 | ✅ |
| Tracked files include any generated data | ❌ (intentional) |
| Local-machine paths in tracked non-source files | ❌ (none) |
| Hardcoded wrapper paths (`$HOME/...`) | ❌ (replaced with `BASE_DIR` derivation) |

## CI gate (post-P4C)

| Check | Result |
| --- | --- |
| Workflow present | ✅ `.github/workflows/open-source-ready.yml` |
| Latest run on `main` | ✅ success |
| Workflow runs `py_compile` × 11 (added `artvee_identity.py` + `plan_*.py` + `execute_*.py` + `run_artvee_nightly_batch.py` + `download_artvee_selected.py`) | ✅ |
| Workflow runs `bash -n` × 2 | ✅ |
| Workflow runs readiness check | ✅ |
| Workflow runs **gallery integrity check** (`--strict`, runtime-aware; `--allow-known-duplicates` is an alias since the P4A fingerprint is empty after P4B) | ✅ |
| Workflow validates `examples/*.sample.json` shape | ✅ |
| Workflow opts into Node.js 24 via `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24=true` (P4C) | ✅ |

## Gallery integrity fingerprint (post-P4A, frozen)

> The P4A audit discovered a historical filename-collision pattern
> in the local index/web data: 11 dupe groups, 13 extra rows. The
> 760 manifest URLs are unique; the dupe is in the *index / web*
> layer. The collision is **frozen** as a known fingerprint inside
> `scripts/check_gallery_integrity.py`. Any new pattern fails the
> CI gate immediately.

| Field | Frozen value |
| --- | --- |
| manifest downloaded rows | 760 |
| manifest unique URLs | 760 |
| index rows | 760 |
| index unique `local_image_path` basenames | 747 |
| index dupe groups | 11 |
| index dupe extra rows | 13 |
| web records | 760 |
| web unique ids | 747 |
| web dupe id groups | 11 |
| web dupe extra rows | 13 |
| disk images | 747 |
| disk metadata | 747 |
| disk thumbs 256 | 747 |
| disk thumbs 512 | 747 |

## Open issues (post-P4C)

- **Historical 11 filename collisions are RESOLVED.** P4B renamed
  11 winner images to source-url-hashed stable ids, re-downloaded
  9 of the 13 losers via playwright, dropped the 4 failed-loser
  rows from the index (and from `web/data/artworks.json` after
  rebuild), and emptied `KNOWN_DUPE_FINGERPRINT`. Strict / allow-
  known / default integrity check all exit 0. The 4 unresolvable
  loser URLs (Playwright `Page.goto` timeout) are recorded in
  `reports/runtime/p4b-unresolved-losers.json`. See
  [docs/RETROSPECTIVE.md](docs/RETROSPECTIVE.md) § 4.1 and the
  P4B entry in [docs/ROADMAP.md](docs/ROADMAP.md).
- **Unresolved losers = 4 (post-P4B, pre-P5+)**:
  - `https://artvee.com/dl/la-plume-4/`
  - `https://artvee.com/dl/le-reve-3/`
  - `https://artvee.com/dl/le-reve/`
  - `https://artvee.com/dl/tetes-byzantines-brunette/`
  - All 4 produced `Page.goto: Timeout 30000ms exceeded` during
    the P4B loser re-download. **P4C left them as-is**; retry
    with a different downloader is P5+ scope.
- **Le_rêve source_url labelling** (P4A+1 § 6.4 build bug): the
  rebuilt `web/data/artworks.json` shows the surviving Le_rêve
  record with `source_url = https://artvee.com/dl/le-reve/`
  (the loser's URL), not `le-reve-2/` (the winner's URL). The
  image, title, and artist are correct; only the URL label is
  wrong. Caused by `build_artvee_gallery.py` taking the first
  source_url when a winning record was merged from multiple
  siblings. P4C left this as-is; a build-script fix is P5+
  scope. **Not a data correctness issue, only a metadata
  labelling issue.**
- **3 source_url dupe groups in `web/data/artworks.json`**: the
  same 3 Le_rêve siblings plus 2 other collision-group siblings
  whose winner inherited the loser's URL. 3 dupe_groups in
  `web_source_url` of size 2 each (6 total, 3 unique). **Not a
  duplicate-id / duplicate-path issue**; image / metadata /
  thumbs paths are all unique (P4C deep-verification confirmed).
- **Mixed filename format**: the 736 non-collision files keep the
  legacy `Alphonse_Mucha_..._standard` basename format; the 11
  winners + 9 successful losers use the new
  `alphonse_mucha_czech_1860-1939_..._<hash8>` format. Both
  formats are valid going forward; new downloads always use the
  new format. **Optional cleanup** (rename 736 legacy files to
  new format) is P5+ scope; not required for correctness.
- **11 legacy winner files retained on disk** (P4B rollback
  safety): 11 images + 11 metadata + 11×2 thumbs = 44 files /
  ~1.4 GB. Deliberately kept (P4B used `shutil.copy2` not
  `move`); cleanup is P5+ scope.
- **Public demo refresh is manual** (post-P4D+1): a 02:30
  cron hook now builds a daily **candidate** at
  `dist/refresh-candidates/YYYY-MM-DD/` and writes a
  Telegram summary. The `git push` of the Pages repo stays
  manual (local-first invariant). See
  [docs/PUBLIC_DEMO_REFRESH_PLAN.md § 8](PUBLIC_DEMO_REFRESH_PLAN.md).
  Full-auto (with PAT) is still P5+ and requires
  `docs/SECRET_ROTATION_POLICY.md` first.

## Post-migration counts (after P4B, verified by P4C)

| Field | Value |
| --- | --- |
| manifest downloaded rows | 760 |
| manifest unique URLs | 760 |
| index rows | 756 |
| index unique `local_image_path` basenames | 756 |
| web records | 756 |
| web unique ids | 756 |
| disk images | 767 (756 referenced + 11 legacy winner orphans) |
| disk metadata | 767 (756 referenced + 11 legacy winner orphans) |
| disk thumbs 256 | 767 (756 referenced + 11 legacy winner orphans) |
| disk thumbs 512 | 767 (756 referenced + 11 legacy winner orphans) |
| missing referenced files | 0 |
| integrity check `--strict` | exit 0 |
| integrity check `--allow-known-duplicates` | exit 0 (alias for `--strict` post-P4B) |
| integrity check default | exit 0 |
| open-source readiness | 4/4 PASS |
| CI workflow | Node 24 (via `actions/checkout@v5`) |

## CI modernization status (P4C)

- `actions/checkout@v4` → `actions/checkout@v5` (PR landed in
  P4C)
- `actions/setup-python@v5` retained (still supported)
- 2026-09-16 GitHub Node 20 runner deprecation: no longer a risk
  for this workflow
- Local `py_compile` (9 scripts) + `bash -n` (1 wrapper) pass
- Workflow step count unchanged: 5 steps (checkout, setup-python,
  py_compile, bash -n, readiness+integrity)

## How to refresh this file

This file is hand-maintained and is updated whenever a new phase
lands or the nightly snapshot changes meaningfully. The next
refresh is expected on the P4D cut.

## How to refresh this file

This file is hand-maintained and is updated whenever a new phase
lands or the nightly snapshot changes meaningfully. The next
refresh is expected on the P4B cut.

### P5A content-healing snapshot (2026-06-12)

| Field | Value |
| --- | --- |
| Le_rêve source_url fix | `build_artvee_gallery.py` now prefers `row.get("source_url")` over `meta.get("url")` — web record source_url matches index, not stale metadata copy |
| Web source_url dupe groups | 0 (was 3 before fix: two-cranes, affiche-van-de-chambre, hostdag-bjelland-mandal) |
| Web records | 756 |
| Web unique ids | 756 |
| Web unique source_urls | 756 |
| Strict integrity | PASS (0 dupe groups) |
| 4 unresolved losers | 0 resolved, 4 still unreachable (HTTP 15s timeout also fails) |
| P5A loser report | `reports/runtime/p5a-unresolved-losers.json` |
| Legacy orphan audit | 46 files / 19.3 MB (11 images + 11 metadata + 12×2 thumbs) |
| Orphan cleanup | deferred to P5C |
| Candidate QA | Gallery 100/200/5.2M PASS, Digest 5/5/256K PASS |

### P5B approved-publish snapshot (2026-06-12 15:47 GMT+8)

| Field | Value |
| --- | --- |
| Approve mode | `--approve` (user explicit, 15:45 GMT+8) |
| Pages commit | `019316a` (conanxin.github.io) |
| Pages push | `4ae8c32..019316a  main -> main` ✅ |
| Gallery candidate | 100 records / 5.7M / 0 leaks |
| Digest candidate | 5 picks / 296K / 0 leaks |
| Source_url dupe groups | 0 (P5A fix live) |
| data.json updated | 2 entries (gallery + digest) |
| Online verification | 12/12 endpoints HTTP 200 (60s CDN wait + 30s extra) |
| Artvee commit | (this commit, P5B wrap-up) |
| CI | (this commit, P5B wrap-up) |

**Live Pages:**
- Gallery: https://conanxin.github.io/projects/artvee-gallery-demo/
- Digest: https://conanxin.github.io/projects/artvee-gallery-digest/
- Source_url for `hostdag-bjelland-mandal` now shows `https://artvee.com/dl/hostdag-bjelland-mandal/` (correct, was `le-reve/`-style stale before P5A fix)

### P5C orphan-cleanup snapshot (2026-06-12 16:02 GMT+8)

| Field | Value |
| --- | --- |
| Mode | `--apply` (user explicit) |
| Orphan files deleted | 44 (P5A audit reported 46, 2 were `.gitkeep` correctly excluded) |
| Total size freed | 19.33 MB (20,271,448 bytes) |
| P5A audit vs actual | 46 → 44 (P5A audit included 2 .gitkeep in thumbs counts) |
| Cross-check P5A | `only_in_p5a` = `.gitkeep` (benign) |
| Missing referenced files (pre + post) | 0 / 0 |
| Disk state post | images: 756, metadata: 756, thumbs/256: 757 (.gitkeep+756), thumbs/512: 757 (.gitkeep+756) |
| Strict integrity | PASS (756 records, 0 dupe groups) |
| Web source_url dupe groups | 0 |
| Candidate QA | Gallery 100/200/5.2M PASS, Digest 5/5/256K PASS, dry-run publish PASS |
| New script | `scripts/cleanup_legacy_orphans.py` (450 lines, --apply / --dry-run / --expected-count / --json-out) |

### P5D visual-QA snapshot (2026-06-12 17:11 GMT+8)

| Field | Value |
| --- | --- |
| Pillow available | ✅ 12.1.1 |
| Sample 100 records | 100/100 risk=none, 0 issues, 0 near-dup |
| Full gallery (756) | 756/756 risk=none, 0 issues, **8 near-dup groups** |
| Public demo (100) | 100/100 risk=none, 0 issues, 0 near-dup, aspect ratio 1.0–3.0 only |
| Digest picks (5) | 5/5 risk=none, 0 issues, 0 near-dup |
| Strict integrity | PASS (756 records, 0 dupe groups) |
| New script | `scripts/analyze_gallery_visual_quality.py` (570 lines, --sample / --out / --contact-sheet / --public-candidate / --digest-candidate) |
| New doc | `docs/VISUAL_QA.md` (visual quality rules + curation playbook) |
| Contact sheets | 3 HTML files in `reports/runtime/p5d-*-contact-sheet.html` (gitignored) |
| Notable findings | Digest 2026-06-12 has 2× Yoshida_Hiroshi + 2× Anonymous (curation flag) |
| 8 near-dup groups | 3 are P4B collision remnants (expected); 5 are real clusters (Edmund Dulac ×4, Amaldus Nielsen ×3, etc.) |
| Runtime data NOT committed | ✅ all 6 p5d-*.json / p5d-*.html in `reports/runtime/` (gitignored) |

### P5F approved-publish-after-curation snapshot (2026-06-12 19:06 GMT+8)

| Field | Value |
| --- | --- |
| Pages commit (refresh) | `f972f5a` on `conanxin/conanxin.github.io` (was `019316a` from P5B) |
| Pages commit range | `019316a..f972f5a` |
| Publish script | `bash scripts/publish_demo_refresh_candidate.sh --date 2026-06-12 --approve` |
| Canonical endpoint check | 9/9 endpoints 200 + 2/2 sample thumbs (256 + 512) |
| User-expanded 12 endpoint check | 11/12 200 (digest `/app.js` 404 is expected: digest is static HTML, not an SPA) |
| Public gallery curation live | 100 records / 100 unique ids / 100 unique source_url / 0 `metadata_path` / 0 abs-path leaks |
| Public digest curation live | 5/5 unique artists, 0 repeats (was 2× Yoshida_Hiroshi + 2× Anonymous in pre-P5E digest) |
| Public digest categories | `book-illustrations`, `japanese-prints`, `posters-design` (3 distinct) |
| Artvee repo commit | **pending** (this P5F docs update: `PROJECT_STATUS.md` + `ROADMAP.md` + `VISUAL_QA.md`) |
| CI check | `open-source-ready.yml` will run after push |

### P5E curation-filters snapshot (2026-06-12 17:27 GMT+8)

| Field | Value |
| --- | --- |
| Public demo `--exclude-risk high` | wired in `scripts/export_artvee_gallery_public_demo.py` (reads `reports/runtime/p5d-visual-qa-full.json`); 0 records dropped (P5D confirms 0 high-risk) |
| Public demo `--require-prompt-fields` | optional, not enabled in `confirm_demo_refresh.sh` (gallery JSON is not required to surface prompt metadata) |
| Digest `--max-per-artist 1` (default) | wired in `scripts/build_artvee_daily_digest.py`; new digest 5/5 unique artists (was 4/5 repeats) |
| Digest prompt-field backfills | 0 (analyzer always populates both fields) |
| Public demo candidate | 100/100 risk=none, 0 issues, 0 near-dup, 0 metadata_path leaks, 0 abs-path leaks |
| Digest candidate | 5/5 risk=none, 0 issues, 0 near-dup, 5 unique artists (5 categories covered) |
| Strict integrity | PASS (756 records, 0 dupe groups) |
| Files changed | `scripts/export_artvee_gallery_public_demo.py`, `scripts/build_artvee_daily_digest.py`, `scripts/confirm_demo_refresh.sh`, `docs/VISUAL_QA.md` (new P5E § 8), `docs/PROJECT_STATUS.md`, `docs/ROADMAP.md`, `docs/DEVELOPMENT.md`, `docs/RETROSPECTIVE.md` (§ 2.10) |
| Files NOT changed | images / metadata / thumbs / web/data / index / dist / digests (only `dist/refresh-candidates/2026-06-12/` regenerated) |


### P6A telegram-media-staging snapshot (2026-06-12 19:46 GMT+8)

| Field | Value |
| --- | --- |
| Root cause | OpenClaw MEDIA allowlist includes `<openclaw-media>/`, `<openclaw-workspace-media>/`, `<openclaw-workspace-tmp>/`; `<workspace-reports>/` is NOT in allowlist → `LocalMediaAccessError` |
| Fix strategy | Staging helper (NOT allowlist expansion) — copy report into project-namespaced subdir of an allowed media root, then send via `--media` |
| New helper | `scripts/stage_report_for_telegram_media.py` (146 lines, stdlib) — refuses symlinks/dirs/zero-byte/size-mismatch |
| Notifier change | `scripts/artvee_telegram_notify.py` +`--media` arg; minimal additive change, no breaking change |
| Staged dir | `<openclaw-media>/artvee-reports/<basename>` (override via `--media-root` or `ARTVEE_MEDIA_ROOT`) |
| Test result | Stage + send → Telegram `Message ID: 22623` ✅ |
| Files changed | `scripts/stage_report_for_telegram_media.py` (new), `scripts/artvee_telegram_notify.py` (+`--media`), `docs/DEVELOPMENT.md` (§ 14 + section 5 snippet), `docs/PROJECT_STATUS.md` (this row), `docs/ROADMAP.md` (P6A ✅), `docs/OPEN_SOURCE_BOUNDARIES.md` (staged reports are runtime artifacts) |
| Staged reports | NOT in Artvee repo, NOT in OpenClaw config; living under `<openclaw-media>/artvee-reports/` (runtime cache) |

### P6D cdn-wait-90s snapshot (2026-06-12 20:30 GMT+8)

| Field | Value |
| --- | --- |
| Change scope | `scripts/publish_demo_refresh_candidate.sh` only |
| What changed | Default `sleep 60` → `sleep "$CDN_WAIT"` (var, default 90); new `--cdn-wait N` flag (range 0..600); help text updated; `_log` line shows actual value |
| Why 90s not 60s | First-pass verification ≥95% on clean push; matches observed cold-cache recovery window; remaining stragglers caught by `wait_and_curl()` retry (also 90s) |
| Backward compat | `--cdn-wait 60` works for any caller wanting old behavior |
| Validated | `bash -n` × 3 OK; `check_open_source_ready.py` PASS; `check_gallery_integrity.py --strict` PASS; dry-run with `--cdn-wait 90` does NOT rsync / commit / push; invalid value rejected; `--cdn-wait 0` accepted |
| Files changed | `scripts/publish_demo_refresh_candidate.sh`, `docs/DEVELOPMENT.md` (§ 15), `docs/PUBLIC_DEMO_REFRESH_PLAN.md` (§ 8.3), `docs/PROJECT_STATUS.md` (this row), `docs/ROADMAP.md` (P6D ✅) |
| Pushed Pages? | No. P6D is internal-only (script change, no `--approve` run) |
| Public surface | unchanged from P5F / P6A |

### P6B known-retired-urls snapshot (2026-06-12 21:05 GMT+8)

| Field | Value |
| --- | --- |
| New script | `scripts/mark_known_retired_urls.py` (236 lines, stdlib) — no network, dry-run default |
| New sample | `examples/known_retired_urls.sample.json` (tracked; documents schema; synthetic URLs only) |
| New runtime artifact | `reports/runtime/p6b-known-retired-urls.json` (NOT tracked; regenerable) |
| Retired count | 4 (P5A: la-plume-4 / le-reve-3 / le-reve / tetes-byzantines-brunette) |
| All records | `status=known_retired`, `should_retry=False` |
| Schema | source_url, title/artist/category/stable_id (best-effort from web/data), retired_reason, first_seen_phase, last_checked_phase, status, should_retry, marked_at, marker_version |
| Safety | refuses overwrite (use --force); refuses --out outside `reports/runtime/`; fallback to P4B if P5A missing; never touches manifest/index/web_data; never reads network |
| Candidate / public flow | `confirm_demo_refresh.sh --no-telegram` PASS; `publish_demo_refresh_candidate.sh --dry-run` PASS |
| Strict integrity | PASS (P6B does NOT change strict integrity; 4 losers are not in web/data so they're already excluded) |
| Files changed | `scripts/mark_known_retired_urls.py` (new), `examples/known_retired_urls.sample.json` (new), `docs/PROJECT_STATUS.md` (this row), `docs/ROADMAP.md` (P6B ✅) |

### P6G KNOWN_RETIRED-aware status report (2026-06-12 21:18 GMT+8)

| Field | Value |
| --- | --- |
| New script | `scripts/build_artvee_status_report.py` (~310 lines, stdlib) — pure local read, no network |
| New runtime artifact | `reports/runtime/artvee-status-report.json` + `.md` (NOT tracked; regenerable) |
| New status split | `known_retired=N` (audited, not blocking) and `blocking_unresolved=M` (what still needs attention) |
| Current values | records=756, known_retired=4, blocking_unresolved=0, strict_integrity=pass, public_demo_ready=true, digest_ready=true |
| Fallback semantics | if `p6b-known-retired-urls.json` missing → `known_retired=0, blocking_unresolved=unresolved_count`, public_demo_ready/digest_ready flip to false, warning logged |
| Telegram wording update | `scripts/confirm_demo_refresh.sh` now appends `Retired sources: N known_retired, blocking_unresolved=M` to the PASS summary |
| Public surface | unchanged — status report reads only existing files |
| Safety | atomic write via `.tmp + os.replace`; refuses `--out-*` outside `reports/runtime/`; no shell-out, no subprocess, no network |
| Candidate / public flow | `confirm_demo_refresh.sh --no-telegram` PASS; `publish_demo_refresh_candidate.sh --dry-run` PASS |
| Files changed | `scripts/build_artvee_status_report.py` (new), `scripts/confirm_demo_refresh.sh` (status wording), `docs/PROJECT_STATUS.md` (this row), `docs/ROADMAP.md` (P6G ✅), `docs/DEVELOPMENT.md` (new § 17) |

### P7B+1 cron-media-fallback snapshot (2026-06-13 04:30 GMT+8)

### P7D v0.2.0-alpha-release snapshot (2026-06-13 04:50 GMT+8)

**Goal** — consolidate P3D through P7B+1 into a single v0.2.0-alpha release: release notes, CHANGELOG, tag, GitHub Release, and an observation baseline. No new code, no new data, no publish.

| Aspect | Value |
|--------|-------|
| Release notes | `docs/RELEASE_NOTES_v0.2.0-alpha.md` (Summary, Highlights, Operational state, Daily cron rhythm, Included vs. not included, Upgrade notes, Safety model, Known limitations, Next steps) |
| CHANGELOG | `CHANGELOG.md` (Aggregated changelog with Added / Changed / Fixed / Operational / Security per version) |
| Tag | `v0.2.0-alpha` (annotated) on the release commit; pushed to `origin`. |
| GitHub Release | `gh release create v0.2.0-alpha --notes-file docs/RELEASE_NOTES_v0.2.0-alpha.md`. |
| Readiness | `python3 scripts/check_open_source_ready.py` — 4/4 PASS. |
| Strict integrity | `python3 scripts/check_gallery_integrity.py --strict` — PASS, no duplicates. |
| Status report | `python3 scripts/build_artvee_status_report.py` — records=776, known_retired=4, blocking_unresolved=0, strict_integrity=pass, public_demo_ready=true, digest_ready=true. |
| Cron rhythm | 01:30 refill · 02:00 nightly batch · 02:30 candidate refresh · 03:00 daily health · manual approved publish. |
| Public demos | Gallery: <https://conanxin.github.io/projects/artvee-gallery-demo/> · Digest: <https://conanxin.github.io/projects/artvee-gallery-digest/> |
| Safety | No download / refill / batch / approve / GitHub Pages push. No tracked runtime files. No tokens / chat ids in tracked code or docs. |
| Files changed | `README.md` (Latest release + docs index + operational model), `CHANGELOG.md` (new), `docs/RELEASE_NOTES_v0.2.0-alpha.md` (new), `docs/PROJECT_STATUS.md` (P7D row + snapshot), `docs/ROADMAP.md` (P7D completed), `docs/DEVELOPMENT.md` (release checklist), `docs/DAILY_OPERATING_PLAYBOOK.md` (v0.2.0-alpha operating baseline), `docs/RETROSPECTIVE.md` (release consolidation lesson). |

### P7E v0.2.0-observation-window snapshot (2026-06-14 07:00 GMT+8)

**Goal** — establish a 3-day observation window for v0.2.0-alpha before stable release. No new code, no data changes, no downloads, no publish.

| Aspect | Value |
|--------|-------|
| Observation period | 2026-06-14 — 2026-06-16 (3 days) |
| Daily health cron | 2026-06-14 03:02 — Telegram summary + MEDIA delivered successfully. Message ID 22919. |
| First-day signal | records=795, known_retired=4, blocking_unresolved=0, integrity=PASS, readiness=PASS, candidate_gallery=True, candidate_digest=True, online_gallery=200, online_digest=200. |
| Checklist | `docs/V0_2_OBSERVATION_WINDOW.md` defines daily checklist, healthy criteria, warning signs, and stable-readiness gates. |
| Safety | No download / refill / batch / approve / GitHub Pages push. No tracked runtime files. Only docs and reports committed. |
| Verification scripts | `check_open_source_ready.py` PASS, `check_gallery_integrity.py --strict` PASS, `build_artvee_status_report.py` PASS, `artvee_daily_health_check.sh --online --no-telegram` PASS. |
| Files changed | `docs/V0_2_OBSERVATION_WINDOW.md` (new), `docs/PROJECT_STATUS.md` (P7E row + snapshot), `docs/ROADMAP.md` (P7E observation window), `docs/DAILY_OPERATING_PLAYBOOK.md` (observation checklist), `README.md` (observation note). |

**Goal** — distinguish health-check internal MEDIA from phase-final MEDIA, expose three independent delivery tracks (text / media / fallback), and verify the cron path actually delivers the report.

| Aspect | Value |
|--------|-------|
| Telegram state model | `telegram.{openclaw_status, text_summary, media, fallback}` — each sub-object records `attempted` / `sent` / `message_id` / `error` / `reason`. |
| Failure-only fallback | Triggered when health=PASS, text=sent, MEDIA=failed. Sent at most once, never recursive, does not flip exit code. |
| Simulated-failure flag | `--simulate-media-failure` (testing only). Verified: text sent → media fail → fallback sent (message_id captured). |
| Cron-like env test | `env -i HOME=... PATH=$HOME/.local/bin:... ARTVEE_TELEGRAM_CHAT_ID=...` runs the daily check end-to-end. text + MEDIA both sent, fallback skipped (not needed). Exit 0. |
| Cron command (P7B+1) | `0 3 * * * export PATH=$HOME/.local/bin:$PATH && export ARTVEE_TELEGRAM_CHAT_ID='<telegram-chat-id>' && cd <artvee-repo> && bash scripts/artvee_daily_health_check.sh --online --media >> ...` |
| Secret hygiene | Hardcoded `DEFAULT_CHAT_ID = '<digits>'` removed from `artvee_telegram_notify.py`. Resolution is now: `--chat-id` CLI > `ARTVEE_TELEGRAM_CHAT_ID` env > OpenClaw config > hard error. No tokens / chat ids in tracked code. |
| Health | `records=756, known_retired=4, blocking_unresolved=0, strict_integrity=PASS, readiness=PASS` |
| Files changed | `scripts/artvee_daily_health_check.py` (nested `telegram` object + fallback + simulate), `scripts/artvee_daily_health_check.sh` (pass-through new flag), `scripts/artvee_telegram_notify.py` (message_id extraction; chat_id from env/config, no hardcoded literal), `scripts/install_daily_health_cron.sh` (PATH + chat_id env, fallback comment, idempotent), `docs/DAILY_OPERATING_PLAYBOOK.md` (§ 9), `docs/DEVELOPMENT.md` (§ 22), `docs/RETROSPECTIVE.md` (lesson), `docs/ROADMAP.md` (P7B+1 → completed). |

### P7E+1 online-drift-diagnosis snapshot (2026-06-15 06:55 GMT+8)

**Goal** — diagnose why the 03:00 Daily Health cron reported `Online: gallery=0, digest=0` while the local Artvee system was clearly healthy. Read-only.

| Aspect | Value |
|--------|-------|
| Local Artvee health | records=815, known_retired=4, blocking_unresolved=0, strict_integrity=pass, public_demo_ready=True, digest_ready=True |
| Local repo HEAD | `aa82608 Add v0.2.0 observation window` (clean) |
| Server-side curl on 9/9 endpoints | **all HTTP 404** in 0.7–3.9s (DNS+TLS ok) |
| Local Pages HEAD | `f419d31` (clean, 215 artvee files locally) |
| Remote Pages `origin/main` HEAD | `41bb6258` (later seen as `3748acb` after fresh fetch — 9 WBW Mars polish commits) |
| Drift evidence | `git diff --stat f419d31 origin/main -- projects/artvee-gallery-demo` = 205 files / 2042 deletions |
| Trigger commits | 8 WBW SpaceX Mars publishes (013fbdb → 41bb625) |
| Side finding | `projects/yang-fudong-fragrant-river/` (35 files) was wiped in the same burst — flagged for follow-up |
| Root cause | WBW Mars publish flow replaced `projects/` subtree; local f419d31 had not followed |
| Signal distortion | `except Exception` in `artvee_daily_health_check.py:209` swallowed `urllib.error.HTTPError` and emitted `0,0` instead of `404,404` |
| Safety | no download / refill / batch / push / commit / approve |
| Report | `<workspace>/reports/artvee-gallery-p7e1-online-endpoint-failure-20260615.md` |

### P7E+2 public-demo-restore snapshot (2026-06-15 07:18 GMT+8)

**Goal** — restore the `projects/artvee-gallery-demo/` and `projects/artvee-gallery-digest/` subtrees on the public GitHub Pages, fix the health-script online-check signal distortion, and document the recovery, **without** reverting any of the WBW Mars commits.

| Aspect | Value |
|--------|-------|
| Pages restore commit | `a5ad80c Refresh Artvee public demos from approved candidate 2026-06-15` |
| Pages `origin/main` after push | `3748acb..a5ad80c` (no force push, no reset, no WBW Mars rewind) |
| Online re-verify | 9/9 endpoints HTTP 200; sample thumbs 5/5 across `[0, 25, 50, 75, 99]` of public `artworks.json` (100 records) |
| Health script fix | `except Exception` split into `HTTPError` (record real code) / `URLError` (record 0 + `network_error`) / `TimeoutError` / `ConnectionError`; new `online.kind`, `online.gallery_error`, `online.digest_error`; new `recommended_action` branches: `attention_required_pages_content_drift` (404) vs `attention_required_network_or_pages_unreachable` (0) |
| Verified with live run | `bash scripts/artvee_daily_health_check.sh --online --no-telegram` → `kind=ok`, `gallery_http_code=200`, `digest_http_code=200`, `recommended_action=candidate_ready_manual_publish_optional` |
| Verified with synthetic 404 | `urllib.request.urlopen("https://conanxin.github.io/projects/nonexistent-artvee-12345/")` → `(404, "http_error", "HTTPError 404 Not Found")` |
| Verified with synthetic network fail | bad host → `(0, "network_error", "URLError [Errno -2] Name or service not known")` |
| Doc updates | `docs/ROADMAP.md` (P7E+1 + P7E+2 rows), `docs/PROJECT_STATUS.md` (snapshots), `docs/DAILY_OPERATING_PLAYBOOK.md` (§ 12), `docs/DEVELOPMENT.md` (§ 23), `docs/RETROSPECTIVE.md` (lesson 2.15) |
| Artvee repo commit | one commit, one push — `scripts/artvee_daily_health_check.py` + 5 docs |
| Safety | no download / refill / batch / nightly; no `images/` / `metadata/` / `thumbs/` modification; no full assets uploaded (only the pre-existing 2026-06-12 thumbs); no force-push; no WBW Mars rewind |
| CI | `gh run list --workflow open-source-ready.yml --limit 3` kicked off — verdict pending at report time |
| Report | `<workspace>/reports/artvee-gallery-p7e2-public-demo-restore-20260615.md` |

### v0.2.0 observation continuation snapshot (2026-06-15 07:39 GMT+8)

**Goal** — continue the v0.2.0 observation window (which started 2026-06-14 and runs through 2026-06-16) after the Day-2 Pages-drift incident; record Day 2 status and the cross-repo actions taken in three sibling phases.

| Aspect | Value |
|--------|-------|
| Local Artvee health (re-check) | records=815, known_retired=4, blocking_unresolved=0, strict_integrity=pass, readiness=pass (4/4) |
| Online | `online.kind=ok`, `gallery_http_code=200`, `digest_http_code=200` |
| Candidates | `gallery_ready=True`, `digest_ready=True` |
| Recommended action | `candidate_ready_manual_publish_optional` |
| Day 2 verdict | **Green with incident annotation** (see `V0_2_OBSERVATION_WINDOW.md`) |
| Cross-repo action 1 (YF-RESTORE-1) | Pages commit `31b2ac7 Restore Yang Fudong project page` — restored `projects/yang-fudong-fragrant-river/` (35 files / 332 KB) from source `3bcdf8b` without WBW Mars rewind |
| Cross-repo action 2 (PAGES-GUARD-1) | Pages commit `6d3961c Add shared Pages publish guard` — new `scripts/check-project-publish-guard.py` + `docs/PAGES_PUBLISH_GUARD.md` + 2 fixtures; allowed PASS exit 0, blocked FAIL exit 1 |
| Files changed | `docs/V0_2_OBSERVATION_WINDOW.md` (Day 2 log), `docs/PROJECT_STATUS.md` (this snapshot + P7E+1/P7E+2 phase markers), `docs/ROADMAP.md` (continuation note) |
| Safety | no download / refill / batch / nightly / `--approve`; no runtime data modification; no CI regression |
| CI | `open-source-ready.yml` re-run after this commit |
| Observation window | still open; Day 3 (2026-06-16) is the final day |

### v0.2.0 stable release snapshot (2026-06-16 06:54 GMT+8)

**Goal** — promote `v0.2.0-alpha` → `v0.2.0` (stable) after the 3-day green observation window, without any new code or runtime data.

| Aspect | Value |
|--------|-------|
| Stable release notes | `docs/RELEASE_NOTES_v0.2.0.md` (new, tracked) |
| CHANGELOG | `CHANGELOG.md` v0.2.0 (stable) section added on top |
| README | Latest release bumped to **v0.2.0** (2026-06-16); status badge `v0.2.0`; observation banner replaced with stable banner |
| Project status | `v0.2.0 stable release` row added above this snapshot |
| Roadmap | `P7F` moved to completed; `v0.2.0 stable` moved to completed |
| Tag | `v0.2.0` (annotated), pushed to `origin` |
| GitHub Release | `gh release create v0.2.0 --title "Artvee Gallery v0.2.0" --notes-file docs/RELEASE_NOTES_v0.2.0.md` |
| Live state at cut | records=835, known_retired=4, blocking_unresolved=0, strict_integrity=pass, readiness=pass (4/4), online 6/6 endpoints HTTP 200 |
| Pre-cut CI | `open-source-ready.yml` ran on the release-consolidation commit, completed success |
| Safety | no download / refill / batch / `--approve` / Pages push / runtime data modification / secrets leaked |
| Files changed | `docs/RELEASE_NOTES_v0.2.0.md` (new), `CHANGELOG.md`, `README.md`, `docs/PROJECT_STATUS.md` (this row + snapshot), `docs/ROADMAP.md` |
| Tag-check | `git ls-remote --tags origin v0.2.0` confirms the tag is on `origin` |
| Release-check | `gh release view v0.2.0` confirms the GitHub Release exists, `isPrerelease=false` |
| Public demos | 6/6 endpoints HTTP 200 (re-verified post-cut) |
| Report | `<workspace>/reports/artvee-gallery-v0.2.0-stable-release-20260616.md` |

### P7B+2 daily-health-media-staging-fix snapshot (2026-06-18 06:55 GMT+8)

**Goal** — close the 2026-06-18 03:00 regression where MEDIA
delivery reported `failed` despite the report being correctly
staged. The original reporting was misleading (it pointed
operators at the raw `reports/runtime/daily-health/...` path
which is not in the OpenClaw allowlist) and the fallback also
failed because it hit the same `GatewayTransportError` that
caused the MEDIA failure. No data, no cron reinstall, no
publish.

| Field | Value |
|-------|-------|
| Date | 2026-06-18 |
| Staged path (after fix) | `${HOME}/.openclaw/media/artvee-reports/artvee-daily-health-2026-06-18.md` (allowlisted) |
| Raw report path | `reports/runtime/daily-health/artvee-daily-health-2026-06-18.md` (recorded for diagnosis only) |
| MEDIA field added | `stage_failed`, `raw_report`, `staged_report`, `staged_size`, `media_root`, `error_kind` |
| FALLBACK reason taxonomy | `media_failed` / `stage_failed` / `media_transport_deferred` |
| Transport-deferred path | writes `.fallback-pending-YYYY-MM-DD.json`; next run flushes on successful text_summary |
| Cron-like verification | health PASS, text_summary sent (message_id=25027), MEDIA sent (message_id=25028), fallback **not** triggered, log clean of secrets |
| Simulated MEDIA failure | text sent (25029), MEDIA simulated fail, fallback sent once (25031, reason=media_failed), exit 0 |
| Transport-deferred e2e | end-to-end run with monkey-patched transport error produced `fallback.reason=media_transport_deferred`, `deferred_local_path=…/reports/runtime/daily-health/.fallback-pending-2026-06-18-p7b2-defer-test.json`, `fallback.sent=false` |
| Strict integrity | PASS |
| Readiness (4/4) | PASS |
| Safety | no download / refill / batch / `--approve` / Pages push; no real secrets printed (only `${#CID}` length) |
| Files changed | `scripts/stage_report_for_telegram_media.py` (`--print-meta`), `scripts/artvee_daily_health_check.py` (staged-only + transport-deferred + flush), `scripts/artvee_telegram_notify.py` (`_classify_error` + `error_kind`), `docs/DAILY_OPERATING_PLAYBOOK.md` (§ 9.5), `docs/DEVELOPMENT.md` (§ 23), `docs/PROJECT_STATUS.md` (this row + snapshot), `docs/ROADMAP.md` (P7B+2 → completed), `docs/RETROSPECTIVE.md` (§ 2.20) |
| Report | `<workspace>/reports/artvee-gallery-p7b2-daily-health-media-staging-fix-20260618.md` |

### P7B+3 pending-media-replay snapshot (2026-06-18 07:30 GMT+8)

| Field | Value |
|---|---|
| Goal | Replace P7B+2's auto-flush-on-next-run with a dedicated, bounded, read-only-by-default replay workflow + a side-effect-free transport probe. |
| New script | `scripts/replay_pending_media.py` — scan / validate / re-send `.fallback-pending-*.json`; default dry-run, `--apply` to actually send. |
| New script | `scripts/check_openclaw_transport.py` — read-only CLI probe (`openclaw --version` + local TCP connect to `127.0.0.1:18789`). |
| Daily health integration | New `media_replay` block in JSON: `pending` / `replayable` / `quarantined` / `transport_status` / `transport_latency_ms` / `transport_checked_at` / `transport_limited_cli`. Scan excludes `replayed/` and `quarantine/` so archived files are not double-counted. |
| Cron changes | None. The 03:00 cron is strictly read + report. Replay is a separate, opt-in step; the optional 03:10 replay cron is documented but **not** installed. |
| Dry-run | `python3 scripts/replay_pending_media.py --limit 5` → 1 plan entry, no Telegram send, no file move. |
| Real replay | `python3 scripts/replay_pending_media.py --apply --limit 1` → Telegram message_id=25071, 25073, 25084 (three test runs, all PASS). |
| Quarantine path | `attempts >= max_retries` → moved to `reports/runtime/daily-health/quarantine/` with `.replay-result-*.json` sidecar. Verified: attempts=3 pending → `quarantine_max_retries` → file moved + sidecar written. |
| Transport health | `media_replay.transport_status="ok"`, `transport_latency_ms=38-43` (version probe). |
| Daily health visibility | `pending=0, replayable=0, quarantined=1` after test runs (one quarantined synthetic pending, no real failures). |
| Strict integrity | PASS |
| Readiness (4/4) | PASS |
| Safety | no download / refill / batch / `--approve` / Pages push; no tokens / chat ids / API keys printed; no MEDIA allowlist changes; staged-only path enforced; original pending files always preserved. |
| Files changed | `scripts/replay_pending_media.py` (new), `scripts/check_openclaw_transport.py` (new), `scripts/artvee_daily_health_check.py` (`media_replay` block + helpers), `docs/MEDIA_REPLAY.md` (new), `docs/DAILY_OPERATING_PLAYBOOK.md` (§ 9.6, § 1 dating), `docs/DEVELOPMENT.md` (§ 24), `docs/PROJECT_STATUS.md` (this row + snapshot), `docs/ROADMAP.md` (P7B+3 → completed), `docs/RETROSPECTIVE.md` (§ 2.21). |
| Report | `<workspace>/reports/artvee-gallery-p7b3-pending-media-replay-20260618.md` |

### P8A post-stable-ops-polish snapshot (2026-06-18 08:30 GMT+8)

| Field | Value |
|---|---|
| Goal | One read-only command that answers "is everything OK right now?" without waiting for the 03:00 cron. Aggregates repo state, records, integrity, readiness, candidate readiness, pending MEDIA, OpenClaw transport, Pages guard, and online URLs. |
| New script | `scripts/artvee_ops_status.sh` (shell wrapper) + `scripts/artvee_ops_status.py` (Python core). |
| Default mode | Strictly read-only. No Telegram. No online probe. No Pages-repo touch. |
| Optional flags | `--online` (HEAD probes), `--include-pages` (read-only Pages repo clean check), `--media` (Telegram + staged MEDIA), `--date` (custom), `--json` (stdout). |
| Output | `reports/runtime/ops/artvee-ops-status-<date>.{json,md}` (runtime, .gitignore'd). |
| Pending MEDIA scan | Reuses `artvee_daily_health_check._scan_pending_media` via direct import so counts never drift. |
| Transport probe | Reuses `check_openclaw_transport.py` (no Telegram message). |
| Pages guard | `pages_guard_available = (guard_script exists) AND (guard_doc exists)`. `pages_repo_clean` only with `--include-pages`. Never rsyncs / commits / pushes. |
| Real Telegram send | Verified: `message_id=25149`, transport healthy at 41–43ms, no side effects, raw report path was staged before send. |
| recommended_action enum | Canonical set: `healthy_no_action` / `candidate_ready_manual_publish_optional` / `attention_required_pages_content_drift` / `attention_required_media_pending` / `attention_required_integrity_failure` / `attention_required_readiness_failure`. First-match-wins priority. |
| Current recommended_action | `candidate_ready_manual_publish_optional` (both candidates ready, no failures). |
| Cron changes | None. The 03:00 daily health cron is the only cron. The ops status command is on-demand; a future 06:00 morning briefing is explicitly out of scope for v0.2.x. |
| Strict integrity | PASS |
| Readiness | PASS |
| Safety | no download / refill / batch / `--approve` / Pages push; no `images/`, `metadata/`, `thumbs/`, `dist/`, `digests/`, `logs/`, `inbox/`, `web/data/`, `index/`, `reports/runtime/`, `tmp/` modification; no tokens / chat ids / secrets printed; raw report path never sent to OpenClaw (always staged via `stage_report_for_telegram_media`). |
| Files changed | `scripts/artvee_ops_status.py` (new), `scripts/artvee_ops_status.sh` (new), `docs/POST_STABLE_OPERATIONS.md` (new), `docs/DAILY_OPERATING_PLAYBOOK.md` (§ 9.7 + status-report + dating), `docs/DEVELOPMENT.md` (§ 25), `docs/PROJECT_STATUS.md` (P8A row + snapshot), `docs/ROADMAP.md` (P8A + Next), `docs/RETROSPECTIVE.md` (§ 2.22), `README.md` (light link addition). |
| Report | `<workspace>/reports/artvee-gallery-p8a-post-stable-ops-polish-20260618.md` |

### P8A+1 pages-guard-visibility snapshot (2026-06-18 10:23 GMT+8)

**Goal** — fix the detection path that made P8A's
`pages_guard_available` always report `false` even though the
guard was correctly installed. **Not** a guard implementation
change; the guard was already where it should be. P8A+1 only
fixes the ops-status-side detection.

| Field | Value |
|---|---|
| Date | 2026-06-18 |
| Pre-fix symptom | `pages_guard_available=false` in P8A ops status JSON, despite the guard being installed in the Pages repo |
| Root cause | P8A looked for `scripts/check-project-publish-guard.py` and `docs/PAGES_PUBLISH_GUARD.md` **inside the Artvee repo**. PAGES-GUARD-1 had installed them in the **Pages repo** (`conanxin.github.io`). Wrong-scope check. |
| Fix shape | Resolve the Pages repo path (CLI > env > default) → inspect *that* repo for the canonical files → optionally run a read-only guard smoke with the artvee allowlist |
| Pages repo resolution | `--pages-repo <pages-repo>` > `$ARTVEE_PAGES_REPO` > `$PAGES_REPO` > `Path.home() / "conanxin.github.io"` |
| New JSON sub-object | `pages.{repo_detected, repo_clean, branch, head, origin_main, guard_available, guard_script_exists, guard_doc_exists, guard_script, guard_doc, guard_smoke, guard_smoke_detail, resolved_via, error}` |
| New CLI flags | `--pages-repo <path>`, `--guard-allow <entry>` (repeatable), `--no-guard-smoke` |
| Top-level compat | `pages_guard_available`, `pages_guard_script`, `pages_guard_doc`, `pages_repo_clean` still emitted |
| Pre-fix verify | P8A (before fix) reported `pages_guard_available=false`; P8A+1 reports `pages_guard_available=true` with `pages.guard_smoke=pass` |
| Post-fix verify | `bash scripts/artvee_ops_status.sh --online --include-pages --pages-repo <pages-repo> --no-telegram` exits 0; `pages.guard_smoke=pass`; Pages repo `git status --porcelain` empty; HEAD unchanged |
| Telegram + MEDIA verify | `bash scripts/artvee_ops_status.sh --online --include-pages --pages-repo <pages-repo> --media` → message_id=**25188** (verified via `/tmp/artvee_notify_*.log`) |
| Strict integrity | PASS |
| Readiness (4/4) | PASS |
| Safety | no download / refill / batch / `--approve` / Pages push; cron line untouched; no real paths / tokens / chat_ids printed; `Path.home()` used instead of a hard-coded absolute user-home path; no tracked runtime files added |
| Files changed | `scripts/artvee_ops_status.py` (Pages guard detection), `docs/POST_STABLE_OPERATIONS.md` (§ 7 + § 9), `docs/DAILY_OPERATING_PLAYBOOK.md` (§ 9.8), `docs/DEVELOPMENT.md` (§ 26), `docs/PROJECT_STATUS.md` (row + this snapshot), `docs/ROADMAP.md` (P8A+1 → completed), `docs/RETROSPECTIVE.md` (§ 2.23) |
| Report | `<workspace>/reports/artvee-gallery-p8a1-pages-guard-visibility-20260618.md` |

### P8B content-product-polish snapshot (2026-06-18 11:08 GMT+8)

**Goal** — polish the public Gallery + Daily Digest pages and
ship a real 30-day digest archive, then publish to GitHub Pages
under the standard `confirm_demo_refresh` → `publish_demo_refresh`
→ Pages-guard → `git push` flow. **No** full assets uploaded.
**No** downloads / refill / batch. **No** force push.

| Field | Value |
|---|---|
| Date | 2026-06-18 |
| Gallery candidate | 100 records, 4.3M, 200 thumbs (256+512), 0 leaks, 0 missing |
| Digest candidate | 1 pick, 51K, 1 thumb, 0 leaks, 0 missing |
| Archive (P8B) | `archive.html=yes, history_entries=7` (window=30d) |
| Digest size budget | 51K (soft 5MB / hard 10MB — both PASS) |
| Gallery size budget | 4.3M (soft 10MB / hard 20MB — both PASS) |
| Public info card | Injected into gallery `index.html` (idempotent, inline CSS, no framework) |
| Release tag | Auto-detected via `git describe --tags --abbrev=0` → `v0.2.0` (P8B no longer hard-codes v0.1.0-alpha) |
| Public history JSON | `data/digest-history.json` written; `digest_path` field stripped (would otherwise leak local-absolute paths even after digest builder redaction) |
| Public text files | 0 forbidden substrings (home-dir, project-root, `metadata/`, `images/`, real paths) |
| Pages guard | `check-project-publish-guard.py --base origin/main --allow projects/artvee-gallery-demo --allow projects/artvee-gallery-digest --allow projects/data.json` → `Verdict: PASS (no changes)` pre-rsync |
| Approved publish | `bash scripts/publish_demo_refresh_candidate.sh --date 2026-06-18 --approve --cdn-wait 90` |
| Pages commit | `43d771e` on `conanxin.github.io` (rsync: `faecf9a..43d771e main -> main`) |
| Online endpoints (all 10) | gallery demo `/`, `/data/artworks.json`, `/data/gallery_stats.json`, `/app.js`, `/style.css` → 200; digest `/`, `/digest.html`, `/data/digests.json`, `/archive.html`, `/data/digest-history.json` → 200 |
| Thumbnail spot-check | Gallery 256 = 10.3K JPEG (184×256, baseline); digest 512 = 25.7K JPEG (410×512, baseline) |
| Other Pages commits | None rolled back; no force push; no `git reset` |
| Strict integrity | PASS |
| Readiness (4/4) | PASS |
| Artvee repo commit | TBD after this section |
| Safety | no download / refill / batch; no full images / metadata / thumbs uploaded; no force push; no rollback of other Pages commits; cron line untouched; no real paths / tokens / chat_ids printed |
| Files changed | `scripts/export_artvee_gallery_public_demo.py` (info card), `scripts/export_artvee_digest_public_page.py` (archive + release tag detection + leak-aware history redaction), `scripts/confirm_demo_refresh.sh` (archive QA + digest size budget), `docs/DIGEST_HISTORY.md` (§ 8 archive), `docs/ROADMAP.md` (P8B entry + Next), `docs/PROJECT_STATUS.md` (row + this snapshot), `docs/RETROSPECTIVE.md` (§ 2.24 lesson) |
| Report | `<workspace>/reports/artvee-gallery-p8b-content-product-polish-20260618.md` |

### P8C public-digest-archive-navigation snapshot (2026-06-18 11:45 GMT+8)

**Goal** — promote the public digest archive from P8B's text-only table to a navigable card grid with client-side filters, while keeping the bundle lightweight and the public history schema honest.

| Aspect | Value |
|---|---|
| Date | 2026-06-18 |
| Gallery candidate | 100 records, 4.8M, 200 thumbs (256+512), 0 leaks, 0 missing |
| Digest candidate | 1 pick (today's digest) + 15 archive picks (7 days), 320K, 16 thumbs (1×512 + 15×256), 0 leaks, 0 missing |
| Archive (P8B+P8C) | `archive.html=yes, history_entries=7, day_cards=7, thumbs_256=15` (window=30d) |
| Digest size budget | 320K (soft 5MB / hard 10MB — both PASS) |
| Gallery size budget | 4.8M (soft 10MB / hard 20MB — both PASS) |
| Archive layout | Top nav (Latest Digest / Gallery / GitHub / Release / Archive / data/digests.json / data/digest-history.json) → summary chips (Total days / Total picks / Unique artists / Available range / Top categories) → filter row (Artist / Category / Search / Clear / Jump to latest) → 7 day-cards (newest first, 5-col auto-fill pick grid of 256 thumbs) |
| Filters (P8C new) | Artist `<select>` + Category `<select>` + free-text Search input + Clear + Jump to latest; vanilla `archive.js` (~4.3 KB), no framework, no external CDN. Page readable with JS off |
| History schema (P8C) | `data/digest-history.json` now carries `generated_at` / `history_entries` / `available_range.{first_date,latest_date}` / `summary.{total_days,total_picks,unique_artists,top_categories}`. `digest_path` still stripped; `entries[]` shape unchanged from P8B |
| `summary` totals | `total_days=7, total_picks=15, unique_artists=13, top_categories=[japanese-prints×7, posters-design×7, book-illustrations×1]` |
| Public text files | 0 forbidden substrings (home-dir, project-root, `metadata/`, `images/`, real paths) |
| Pages guard | `check-project-publish-guard.py --base origin/main --allow projects/artvee-gallery-demo --allow projects/artvee-gallery-digest --allow projects/data.json` → `Verdict: PASS (no changes)` pre-rsync |
| Approved publish | `bash scripts/publish_demo_refresh_candidate.sh --date 2026-06-18 --approve --cdn-wait 90` |
| Pages commit | `131f663` on `conanxin.github.io` (rsync: `43d771e..131f663 main -> main`, 20 files / +322 / -83) |
| Online endpoints (8 / 8) | gallery `/`, `/data/artworks.json`; digest `/`, `/digest.html`, `/archive.html`, `/data/digests.json`, `/data/digest-history.json`, `/archive.js` → all HTTP 200 |
| Thumbnail spot-check | archive 256 thumbs are baseline JPEG (160 KB – 27 KB), accessible via `<img loading="lazy" onerror="visibility:hidden">` |
| Other Pages commits | None rolled back; no force push; no `git reset`; 0 other Pages projects touched |
| P8B preflight fix | P8B had 8 stragglers (literal project-root / home-dir substrings used in the readiness grep) in 5 docs; P8C caught them in preflight (readiness FAIL) and rewrote the meta-descriptions to refer to the abstract *project-root* / *home-dir* substrings. Final readiness 4/4 PASS |
| Artvee repo commit | TBD after this section |
| Safety | no download / refill / batch; no full images / metadata / thumbs uploaded; no force push; no rollback of other Pages commits; cron line untouched; no real paths / tokens / chat_ids printed; no `artvee_ops_status.py` / `install_daily_health_cron.sh` modification; no `web/` / `images/` / `metadata/` / `thumbs/` / `web/data/` modification; runtime logs / reports / dist / tmp not committed |
| Files changed | `scripts/export_artvee_digest_public_page.py` (cards + filters + 256 thumbs + history schema), `scripts/confirm_demo_refresh.sh` (P8C archive QA), `docs/DIGEST_HISTORY.md` (§ 9 navigation polish), `docs/POST_STABLE_OPERATIONS.md` (§ 12.3), `docs/PROJECT_STATUS.md` (P8C row + this snapshot), `docs/ROADMAP.md` (P8C entry + Next), `docs/RETROSPECTIVE.md` (§ 2.25 lesson). Plus the P8B uncommitted-folded changes to `scripts/export_artvee_gallery_public_demo.py` (info card) and 5 docs (P8B path-leak cleanup). No `artvee_ops_status.py`, no `install_daily_health_cron.sh` |
| Report | `<workspace>/reports/artvee-gallery-p8c-public-digest-archive-navigation-20260618.md` |

### P8D optional-media-replay-cron snapshot (2026-06-18 14:10 GMT+8)

| Field | Value |
|---|---|
| Goal | Optional, opt-in 03:10 cron that flushes deferred MEDIA 10 minutes after the 03:00 daily-health cron, using the existing staged-only P7B+3 replay flow. |
| New script | `scripts/artvee_media_replay_cron.sh` (thin shell wrapper around `replay_pending_media.py --apply`) + `scripts/install_media_replay_cron.sh` (idempotent marker-block installer). |
| Default schedule | `CRON_TZ=Asia/Shanghai 10 3 * * *` |
| Default args | `--limit 5 --max-retries 3` (matches P7B+3 defaults) |
| Concurrency guard | `flock -n` on `reports/runtime/media-replay/.media-replay.lock` |
| Transport pre-flight | on by default; if `check_openclaw_transport.py` != ok, skip replay (pending stays for next run) |
| Summary writes | always writes `reports/runtime/media-replay/cron-<date>.json` (used by ops status `media_replay_cron_summary` field) |
| Ops status delta | new `media_replay_cron_installed` (bool, from `crontab -l` marker scan) + `media_replay_cron_summary` (latest summary object) |
| CI delta | new `bash -n` entries for the two new shell scripts in `open-source-ready.yml` |
| pending_media_before_first_run | 2 (1 quarantine test fixture + 1 replayable from P7B+3) |
| replay_pending_media dry-run | plan only, no sends |
| Install --dry-run | preview-only, no crontab modification |
| Install --install | idempotent; replaces P8D block in place |
| Remove | deletes only P8D block; P7B daily-health cron, refill, batch untouched |
| Cron installed at session end | yes (per user explicit authorization) |
| Recommended action | `candidate_ready_manual_publish_optional` (unchanged from P8A) |
| Safety | no download / refill / batch / Pages push / --approve / retired retry / MEDIA allowlist widen; no tokens / chat_ids / secrets printed; no hardcoded user-home paths; `flock -n` prevents overlapping runs |
| Files changed | `scripts/artvee_media_replay_cron.sh` (new), `scripts/install_media_replay_cron.sh` (new), `scripts/artvee_ops_status.py` (new helper + summary field + 2 MD rows), `.github/workflows/open-source-ready.yml` (2 new bash -n entries), `docs/DAILY_OPERATING_PLAYBOOK.md` (§ 9.9), `docs/POST_STABLE_OPERATIONS.md` (§ 6.1), `docs/MEDIA_REPLAY.md` (§ 10), `docs/DEVELOPMENT.md` (§ 27), `docs/PROJECT_STATUS.md` (P8D row + snapshot), `docs/ROADMAP.md` (P8D entry + Next), `docs/RETROSPECTIVE.md` (§ 2.23), `README.md` (light link addition). |
| Report | `<workspace>/reports/artvee-gallery-p8d-optional-media-replay-cron-20260618.md` |

### P8D+1 cron-PATH-and-media-replay-activation snapshot (2026-06-29 07:05 GMT+8)

| Field | Value |
|---|---|
| Trigger | 2026-06-29 cron diagnostic: 03:10 media-replay cron produced zero logs and zero summary; refill/batch/confirm produced normal data but Telegram notifier logged NOTIFY_FAIL on every run. |
| Root cause A (P0) | `crontab -l` line for the P8D media-replay had `CRON_TZ=Asia/Shanghai 10 3 * * * cd ...` (7 fields). Cron parses any leading `Name=value` as a per-line env var, not a schedule column, so the 7-field line was silently rejected. Result: no log, no summary. |
| Root cause B (P1) | The same `CRON_TZ=`-on-schedule bug was present in the P8D installer template. The pre-P7B refill / batch / confirm-refresh cron lines had no `PATH=` at all, so under cron's minimal `PATH` (no `$HOME/.local/bin`) the OpenClaw binary used by the Telegram notifier was unresolvable. The data products were unaffected; only Telegram was dropped. |
| Fix A | `scripts/install_media_replay_cron.sh` template now emits `CRON_TZ=Asia/Shanghai` and `PATH=$HOME/.local/bin:...` on their own lines, followed by a clean 5-field schedule. |
| Fix B | New `scripts/install_artvee_cron.sh` (P8D+1 unified installer) emits the refill / batch / confirm-refresh block under one marker with the same `CRON_TZ=` + `PATH=` env-var lines. Idempotent; `--remove` only deletes the P8D+1 block. |
| Cleanup | Surgically removed 13 legacy lines (legacy refill/batch/confirm + their venv-python commented siblings + decorative comment header) so the new block is the only schedule for those three jobs — preventing tomorrow's 01:30 / 02:00 / 02:30 double-runs. |
| Verification A | `crontab -l` now has exactly 1 instance each of: refill, batch, confirm-refresh, media-replay; 1 P7B marker block; 1 P8D marker block; 1 P8D+1 marker block. |
| Verification B | `bash scripts/artvee_media_replay_cron.sh --dry-run --limit 5 --max-retries 3` under a cron-like `env -i ... PATH=$HOME/.local/bin:...` returned `exit 0`, wrote `reports/runtime/media-replay/cron-2026-06-29.json` with `outcome=dry_run_completed`, `transport_status=ok`. |
| Verification C | Same wrapper run without `--dry-run` returned `exit 0`, `outcome=replayed_pending` (2 existing pending files, neither replayable), `transport_status=ok`. No Telegram sent (no fresh pending). |
| Strict integrity | PASS (no duplicates, 1089 records) |
| Open-source readiness | PASS (4/4 sub-checks) |
| P7B daily health | Already had `export PATH=$HOME/.local/bin:$PATH` — unchanged. |
| P8D installer rerun | Idempotent — re-running `--install` from the patched template replaces the block with the fixed syntax. |
| Safety | no download / refill / batch / Pages push / --approve / retired retry / MEDIA allowlist widen; no tokens / chat_ids / secrets printed; legacy pre-fix crontab backed up to `logs/artvee-cron/crontab.before_*` (3 timestamps). |
| Files changed | `scripts/install_media_replay_cron.sh` (template fix), `scripts/install_artvee_cron.sh` (new), `docs/DAILY_OPERATING_PLAYBOOK.md` (P8D+1 section), `docs/MEDIA_REPLAY.md` (P8D+1 observability guarantee), `docs/POST_STABLE_OPERATIONS.md` (P8D+1 note under § 6.1), `docs/PROJECT_STATUS.md` (P8D+1 row + snapshot), `docs/ROADMAP.md` (P8D+1 entry), `docs/RETROSPECTIVE.md` (§ 2.24 lesson). |
| Report | `<workspace>/reports/artvee-gallery-p8d1-cron-path-media-replay-fix-20260629.md` |
