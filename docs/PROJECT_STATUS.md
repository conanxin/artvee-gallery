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
