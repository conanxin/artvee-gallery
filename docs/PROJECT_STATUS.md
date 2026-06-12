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
| **E2E** | Nightly Cron Auto-Run | ✅ PASS | 2026-06-12 | `<workspace>/reports/artvee-nightly-auto-run-verification-2026-06-12.md` |

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
