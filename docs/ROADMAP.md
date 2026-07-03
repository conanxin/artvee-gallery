# Artvee Gallery · Roadmap

> Living roadmap. The phase markers here are stable; the dates and
> sub-items are best-effort. Status: see
> [docs/PROJECT_STATUS.md](docs/PROJECT_STATUS.md).

## 1. Completed phases

### P1 · Local Gallery Browser
**Status:** ✅ PASS
- `scripts/build_artvee_gallery.py` produces `web/data/*.json` +
  `thumbs/{256,512}/*.jpg`.
- Local UI shell (`web/index.html`, `app.js`, `style.css`) renders the
  gallery with search / filter / detail modal.
- See [docs/GALLERY_LOCAL_USAGE.md](docs/GALLERY_LOCAL_USAGE.md).

### P2 · Public Demo Export
**Status:** ✅ PASS
- `scripts/export_artvee_gallery_public_demo.py` emits a curated
  static bundle (thumbnails only, paths rewritten to relative) to
  `dist/`.
- Bundle is self-contained, CDN-friendly.
- See [docs/GALLERY_PUBLIC_DEMO.md](docs/GALLERY_PUBLIC_DEMO.md).

### P3A · Public Demo Publish (GitHub Pages)
**Status:** ✅ PASS
- The curated bundle is published to:
  <https://conanxin.github.io/projects/artvee-gallery-demo/>
- Publishing is manual / out-of-band; the repo itself stays clean.

### P3B · Daily Inspiration Digest
**Status:** ✅ PASS
- `scripts/build_artvee_daily_digest.py` selects 5 representative
  works per day, renders Markdown + HTML, and updates the rolling
  index `web/data/digests.json`.
- Wrapped into the nightly batch chain.
- See [docs/GALLERY_DAILY_DIGEST.md](docs/GALLERY_DAILY_DIGEST.md).

### P3C · Open-Source Readiness
**Status:** ✅ PASS
- `README.md` rewritten as a self-contained entry point.
- `LICENSE` (MIT) added.
- `.gitignore` consolidated; placeholder `.gitkeep` files preserve
  empty directories.
- `docs/ARCHITECTURE.md`, `OPEN_SOURCE_BOUNDARIES.md`,
  `DEVELOPMENT.md`, `ROADMAP.md`, `PROJECT_STATUS.md`,
  `RELEASE_NOTES_v0.1.0-alpha.md` added.
- `examples/` ships with three synthetic JSON files.
- `scripts/check_open_source_ready.py` enforces the privacy/safety
  surface.
- Nightly wrapper script updated to derive `BASE_DIR` from its own
  location, removing all hardcoded machine paths.

### Nightly E2E Cron Verification
**Status:** ✅ PASS (verified 2026-06-12)
- `artvee_nightly_wrapper.sh batch` runs at 02:00 Asia/Shanghai
  cron, completes in about 5 minutes, posts a Telegram summary.
- All post-batch steps (gallery rebuild, digest build, notify) run
  on the same trigger.
- Last-known-good snapshot: 760 downloaded, 0 failed, 530 pending.

### P3D · Standalone Public GitHub Repository
**Status:** ✅ PASS
- New public repo: <https://github.com/conanxin/artvee-gallery>
  (MIT, default branch `main`).
- CI workflow `.github/workflows/open-source-ready.yml` runs the
  readiness check + `py_compile` + `bash -n` + JSON validation on
  every push.
- Annotated tag `v0.1.0-alpha` released at
  <https://github.com/conanxin/artvee-gallery/releases/tag/v0.1.0-alpha>.

### P3E · Public Daily-Digest Page
**Status:** ✅ PASS
- `scripts/export_artvee_digest_public_page.py` emits a 324 KB
  self-contained public bundle for the latest digest.
- Published to:
  <https://conanxin.github.io/projects/artvee-gallery-digest/>
- The Pages repo's `projects/data.json` grew to 29 entries.
- README gained 3 badges (CI / Release / License), 2 demo links,
  and a Screenshots section.

### P3F · Final Case Study and Project Retrospective
**Status:** ✅ PASS
- [docs/CASE_STUDY.md](docs/CASE_STUDY.md) — the project story
  (how a one-off downloader became an open-source visual archive).
- [docs/RETROSPECTIVE.md](docs/RETROSPECTIVE.md) — phase-by-phase
  lessons, impact analysis, open questions, and the recommended
  next phase.
- [docs/LOCAL_FIRST_AGENT_PROJECT_PATTERN.md](docs/LOCAL_FIRST_AGENT_PROJECT_PATTERN.md) —
  the reusable methodology extracted from this project.
- README, ROADMAP, and PROJECT_STATUS updated to surface the
  new documentation.

### P4A · Manifest duplicate-id audit (read-only)
**Status:** ✅ PASS
- Joined the manifest (`inbox/manifest.csv`), the index
  (`index/artworks.csv`), and the web data
  (`web/data/artworks.json`) against the disk.
- Found: manifest has 760 *unique* URLs (no double-download).
  The 11 dupe groups / 13 extra rows live in the *index* and
  *web data* layers, caused by **filename collisions** when
  different artvee pages with the same parsed title land on
  the same local file. Last-write-wins overwrote 11 source
  images; 13 index/web records now point to a sibling image.
- Output: a Markdown audit report (no data changes).

### P4A+1 · Gallery integrity CI gate
**Status:** ✅ PASS
- New `scripts/check_gallery_integrity.py` (pure stdlib).
  Inspects `inbox/manifest.csv` (URL uniqueness), `index/artworks.csv`
  (basename uniqueness, one-id-to-many-`source_url`),
  `web/data/artworks.json` (id / `image_path` / `metadata_path` /
  `thumb_256` / `thumb_512` uniqueness).
- The historical 11/13 fingerprint is frozen inside the script.
- Modes:
  - `--allow-known-duplicates` (CI default): tolerates the
    P4A-known 11/13 fingerprint; fails on any new pattern.
  - `--strict`: fails on any duplicate / collision.
  - SKIP-on-missing-data: on the open-source repo with no
    runtime data, exits 0 (gate is safe to run on every PR).
- Wired into `.github/workflows/open-source-ready.yml` as a
  new step. The `docs/DEVELOPMENT.md` pre-commit checklist
  includes the new gate.

## 2. Up next

### P4B · Filename collision fix + index/web data migration
**Status:** ✅ PASS (2026-06-12)
- Replaced the human-readable `Artist_Title_Cat_Variant` filename
  rule with a **source-url-hashed stable id**
  (`<slug_artist>_<slug_title>_<category>_<variant>_<sha1(url)[:8]>`)
  via the new `scripts/artvee_identity.py` helper.
- Patched `scripts/run_artvee_nightly_batch.py` and
  `scripts/download_artvee_selected.py` to use the new helper.
  `scripts/build_artvee_gallery.py` needs no change because it
  derives the record `id` from the basename stem of
  `local_image_path`.
- Built `scripts/plan_gallery_collision_migration.py` (read-only
  dry-run planner) and `scripts/execute_gallery_collision_migration.py`
  (write executor). The executor is **bounded**: at most 13
  re-downloads, all in the 11 collision groups, with a
  `reports/runtime/p4b-unresolved-losers.json` graceful-degrade
  path for any failure.
- Ran the executor: 11 winners renamed via `shutil.copy2` (so
  source files are still on disk for recovery); 9/13 losers
  re-downloaded; 4 losers dropped from the index (Playwright
  `Page.goto` 30s timeout on pages artvee no longer serves
  consistently).
- Re-emitted `index/artworks.csv` (756 rows) and rebuilt
  `web/data/artworks.json` (756 records) via
  `scripts/build_artvee_gallery.py --mode local`.
- Emptied `KNOWN_DUPE_FINGERPRINT` inside
  `scripts/check_gallery_integrity.py` (P4A fingerprint is no
  longer needed). All three modes — default,
  `--allow-known-duplicates`, `--strict` — exit 0.
- Public demo and Pages re-publication are **deferred to a
  later phase**; the P4B commit only updates code + docs in
  the open-source repo, no runtime data.

### P4C · Post-migration verification + CI Node 24 upgrade + public demo refresh planning
**Status:** ✅ PASS (2026-06-12)
- **Verification** (read-only, no destructive ops):
  - integrity check 3 modes (default / `--allow-known-duplicates` / `--strict`) all exit 0
  - index / web 100% consistent (756 ↔ 756)
  - 0 referenced-but-missing files
  - 11 image / metadata / thumbs orphans per size = P4B's deliberately-kept legacy winner files (rollback safety)
  - 3 source_url dupe groups remain (P4A+1 § 6.4 build bug: build script takes first source_url per id; winner's URL got collapsed to loser's URL for the 3 Le_rêve siblings)
  - 4 unresolved losers from P4B (all playwright 30s timeouts on `la-plume-4/` / `le-reve-3/` / `le-reve/` / `tetes-byzantines-brunette/`) left for P5+ retry with a different downloader
  - public demo exporter dry-run + full-export-to-`/tmp/artvee-gallery-demo-p4c` verified; 100 / 100 records, 200 thumbs, 0 leaks, 0 missing
- **CI Node 24 upgrade**: bumped `actions/checkout@v4` → `actions/checkout@v5`. The
  GitHub-recommended path before 2026-09-16 forced deprecation of
  Node 20 runner. `setup-python@v5` left untouched (still
  supported). The CI log now shows zero Node-deprecation annotations
  (P4B had 1 info-level warning).
- **Public demo refresh planning**: standalone design doc
  `docs/PUBLIC_DEMO_REFRESH_PLAN.md`. Three refresh modes
  (manual / semi-auto / full-auto) with 6 mandatory gates
  before any Pages push. P4D target = **semi-auto with explicit
  approval** (no secrets needed). Full-auto (with PAT) is P5+
  and requires a `docs/SECRET_ROTATION_POLICY.md` first.
- **Le_rêve source_url**: still points to `le-reve/` (loser's
  URL) in the new record, not `le-reve-2/` (winner's URL).
  P4A+1 § 6.4 build bug; image and title are correct, only
  the URL label is wrong. Leave for P5+ build-script fix.

### P4D · Semi-automatic public demo refresh ✅ PASS (2026-06-12)
**Status:** First semi-automatic refresh shipped on 2026-06-12:
- Exporter gained two new public-safety flags
  (`--exclude-duplicate-source-url-groups`,
  `--require-unique-source-url`) and a `metadata_path` field
  strip — see
  [`scripts/export_artvee_gallery_public_demo.py`](scripts/export_artvee_gallery_public_demo.py).
- Gallery (100 records, 5.7M, 205 files) and Digest (5 records,
  296K, 10 files) rebuilt from post-P4B `web/data/` and rsynced
  to `conanxin.github.io` at commit `5a8d938`.
- All online endpoints verified `200` after a 60-second CDN
  propagation wait; thumb spot-checks pass.
- The single manual step in the flow is `git push` from
  the Pages repo (`<artvee-pages-repo>`, e.g.
  `conanxin.github.io`), which keeps the local-first invariant
  (no PAT, no webhook, no secret in CI).

**P4D follow-up:** the
`scripts/confirm_demo_refresh.sh` shell wrapper and the
nightly 02:30 hook in `artvee_nightly_wrapper.sh` shipped in
**P4D+1** (see § 1) on 2026-06-12. The first refresh was
driven by an explicit exporter invocation; the prompt-and-
confirm wrapper now runs unattended and writes a daily
candidate + Telegram summary, with the `git push` step still
manual by design.

### P4D+1 · `confirm_demo_refresh.sh` wrapper + 02:30 nightly hook ✅ PASS (2026-06-12)
- New script
  [`scripts/confirm_demo_refresh.sh`](scripts/confirm_demo_refresh.sh)
  (~470 lines, 5 args) wraps the P4D manual flow:
  preflight (open-source readiness + integrity strict) → build
  local digest → export Gallery candidate with P4D safety
  flags → export Digest candidate → QA both bundles → write
  `logs/confirm_demo_refresh/report_<date>.md` → Telegram
  summary.
- Output: `dist/refresh-candidates/YYYY-MM-DD/{gallery,digest}/`
  (gitignored, overwritable per-date) and
  `logs/confirm_demo_refresh/confirm_demo_refresh_*.log`.
- Cron hook installed at `30 2 * * *` in `CRON_TZ=Asia/Shanghai`,
  immediately after the existing `02:00` nightly batch hook.
  Hook runs with `--no-telegram` to avoid spam; manual
  re-runs without `--no-telegram` send the summary.
- Idempotency: same date re-run overwrites the candidate and
  regenerates the report. Cross-day runs are independent.
- Local-first invariant preserved: no `git push`, no `rsync` to
  the Pages repo, no download/refill/batch, no retry of the 4
  unresolved losers, no PAT / webhook / secret.
- Manual publish step remains a 4-line `rsync + commit + push`
  against the candidate directory, documented in
  [docs/PUBLIC_DEMO_REFRESH_PLAN.md § 8.3](PUBLIC_DEMO_REFRESH_PLAN.md).
- First-run result (2026-06-12, `--no-telegram`): Gallery 100
  records / 200 thumbs / 5.2M, Digest 5 picks / 5 thumbs / 256K,
  all QA guards PASS, overall status `PASS`.

### P4E · Approved publish helper ✅ PASS (2026-06-12)
- New script `scripts/publish_demo_refresh_candidate.sh` (~600
  lines, 5 args) implements the **candidate-to-pages** flow with
  an explicit `--approve` gate.
- Security model: no `--approve` = dry-run only (no rsync / commit
  / push); `--approve --no-push` = rsync + commit, no push;
  `--approve` = full publish + online verification.
- Pipeline: candidate QA (Gallery + Digest) → Pages repo dirty
  check → `data.json` entry validation → plan preview → `rsync -a
  --delete` → `data.json` update → `git commit` (with no-change
  skip) → `git push` (optional) → online `curl` verification (9
  endpoints + 1 sample thumb, 60s CDN wait + one retry).
- First run (2026-06-12, `--dry-run`): all QA PASS, plan preview
  correct, no Pages repo touched. Real `--approve` was **not**
  executed in this phase (per user instruction: no real publish
  without explicit re-authorization).

### P4F · Digest history index page
- The public digest route currently shows only the latest day.
- A 30-day rolling index would turn the digest into a
  *publication* rather than a daily log.
- Easy follow-up to P4D+1: the candidate already contains a
  date-stamped digest bundle, so the history index is mostly
  a Pages-side roll-up.

### P4G · Object storage planning
- The local archive is 1.4 GB on a single disk. Multi-device
  access, backup, or sharing would put it in object storage
  (S3 / R2 / COS).
- This is a long-arc architectural shift (local-first →
  cloud-mirrored) and should wait until the local-first story
  is fully debugged.

## 3. Mid-term

### Themed bundle exporter
- A "themed export" mode that picks artworks matching a tag /
  palette / era filter, for use as blog post headers or wallpaper
  packs.
- Output shape: same as the public demo, but a small manifest
  describes the theme.

### Star / rate / collect
- A small annotation layer (per-artwork "starred" / "rating" /
  "notes") stored locally as JSON.
- Optional, opt-in; no public visibility by default.

### Visual tag enrichment
- Use Pillow's dominant-palette extraction (already in the digest
  builder) to expose palette filters in the local UI.
- Optional AI-generated "mood" descriptors, fully local.

## 4. Long-term

(P4E / P4F / P4G live in § 2 above as "Up next" — they
are nearer-term candidates. The truly long-term open items
are gathered under P5+ below.)

### P5A · Content healing: Le_rêve source_url fix + unresolved loser retry + orphan audit ✅ PASS (2026-06-12)
- **Le_rêve source_url label bug**: root cause was `build_artvee_gallery.py` preferring
  `meta.get("url")` over `row.get("source_url")`. After P4B winner rename, the metadata
  file was copied (not regenerated) so it kept the old winner's URL. The fix swaps
  priority: `row.get("source_url") or meta.get("url")`. This is a general fix, not a
  Le_rêve hardcode.
- **Web source_url dupe groups**: dropped from 3 to 0 after rebuild (two-cranes,
  affiche-van-de-chambre, hostdag-bjelland-mandal were all metadata-copy stale URLs).
- **Unresolved loser retry**: 4 URLs (la-plume-4, le-reve-3, le-reve,
  tetes-byzantines-brunette) were checked with HTTP HEAD (15s timeout). All 4 still
  unreachable (site not responding). Recorded in `p5a-unresolved-losers.json`.
- **Legacy orphan audit**: 46 files / 19.3 MB (11 images + 11 metadata + 12×2 thumbs)
  not referenced by `index/artworks.csv`. These are P4B rollback-safety copies.
  Cleanup deferred to P5C.
- **Rebuild**: `build_artvee_gallery.py --mode local` → 756 records, 0 dupe groups,
  strict integrity PASS. `build_artvee_daily_digest.py` → 5 picks. Candidate
  `confirm_demo_refresh.sh` → Gallery 100/200/5.2M PASS, Digest 5/5/256K PASS.

### P5B · First approved public refresh ✅ PASS (2026-06-12 15:47)
- User explicitly authorized `--approve` at 15:45 GMT+8
- Pages commit `019316a` (conanxin.github.io), push `4ae8c32..019316a`
- 12/12 endpoints HTTP 200 after 60s+30s CDN wait
- P5A Le_rêve source_url fix is now live on public Gallery
- See `<workspace>/reports/artvee-gallery-p5b-approved-publish-20260612.md`

### P5C · Legacy orphan cleanup ✅ PASS (2026-06-12 16:02)
- User authorized `--apply` at 16:01 GMT+8
- New script: `scripts/cleanup_legacy_orphans.py` (--apply / --dry-run / --expected-count / --json-out)
- Deleted 44 legacy rollback orphan files (P4B safety copies) / 19.33 MB
- P5A audit reported 46; actual was 44 (P5A audit included 2 .gitkeep in thumbs counts; correctly excluded by cleanup script)
- Post-cleanup: images 756, metadata 756, thumbs/256 757, thumbs/512 757 — all 3024 web-referenced paths exist
- Strict integrity PASS, 0 source_url dupe groups
- See `<workspace>/reports/artvee-gallery-p5c-orphan-cleanup-20260612.md`

### P5D · Deeper visual/content QA ✅ PASS (2026-06-12 17:11)
- Pillow-optional analyzer with 4 modes: full / sample / public-candidate / digest-candidate
- 100/756/100/5 all risk=none, 0 issues
- 8 aHash near-dup groups surfaced (3 P4B remnants + 5 real artist clusters)
- Recommended curation filters (now implemented in P5E)
- See `<workspace>/reports/artvee-gallery-p5d-visual-qa-20260612.md`

### P5E · Curation filters ✅ PASS (2026-06-12 17:27)
- Public demo exporter: `--exclude-risk high` (reads P5D visual-QA JSON) +
  `--require-prompt-fields` (defensive)
- Digest builder: `--max-per-artist 1` default (strict; `--allow-repeat-artist` opt-out)
  + deterministic prompt-field backfill (no external AI)
- 2026-06-12 digest 5/5 unique artists (was 4/5 repeats)
- `confirm_demo_refresh.sh` wired to pass `--exclude-risk high` automatically
- See `<workspace>/reports/artvee-gallery-p5e-curation-filters-20260612.md`

### P5F · Approved publish after curation filters ✅ PASS (2026-06-12 19:06)
- First Pages refresh since P5B (`019316a`) that carries P5E-curation
  rules live: digest 5/5 unique artists, public demo risk-filter active
- Pages commit: `f972f5a` on `conanxin/conanxin.github.io` (`019316a..f972f5a`)
- Online verification: 9/9 canonical endpoints + 2/2 sample thumbs (256/512)
  + 11/12 user-expanded (digest `/app.js` 404 expected — digest is static HTML)
- Public JSON safety: 0 `metadata_path`, 0 abs-path leaks, 0 duplicate `source_url`
- Live digest artists: `Alphonse_Mucha` · `Amaldus_Nielsen` · `Anonymous` ·
  `Utagawa_Hiroshige` · `Yoshida_Hiroshi` (5 unique)
- See `<workspace>/reports/artvee-gallery-p5f-approved-publish-after-curation-20260612.md`

### P5E · Curation filters (P5D ✅ done — now safe to do)
- Public demo: exclude `risk_level=high` records from the candidate
- Digest: cap picks at 1 per artist (Anonymous normalized to "Anonymous")
- Both: ensure `use_cases` / `prompt_seed` are non-empty (deterministic fallback)
- Re-run `confirm_demo_refresh.sh --no-telegram` to verify the new candidate


### P5C · Legacy orphan cleanup (P5B ✅ done — now safe to do)
- Run `publish_demo_refresh_candidate.sh --date YYYY-MM-DD --approve` after P5A
  candidate is validated. This is the first real Pages push since P4D.
- Requires user explicit `--approve` (P4E security model).

### P5C · Legacy orphan cleanup
- Delete the 46 P4B rollback-safety orphan files (11 images + 11 metadata + 24 thumbs)
  that are not referenced by `index/artworks.csv`. Saves ~19 MB.
- Should be done AFTER a successful P5B public refresh (so the public surface is
  stable before touching local disk).

### P5D · Deeper visual/content QA
- Automated thumbnail quality check (blurry/dark detection).
- Palette drift monitoring (dominant colors should not all be brown).
- Category balance check (no category should be >40% or <10% of total).

### P5+ · Still open (P5F ✅ — only meta-items remain)

- **4 unresolved losers** from P4B / P5A (`la-plume-4/` · `le-reve-3/` ·
  `le-reve/` · `tetes-byzantines-brunette/`) — artvee.com permanently
  unreachable; alternate-source review or formal `KNOWN_RETIRED` set is
  a future phase
- **8 aHash near-dup groups** (3 P4B collision remnants + 5 real artist
  clusters: Edmund Dulac ×4, Amaldus Nielsen ×3, Arthur Rackham ×3, etc.)
  — ✅ **P6C DONE** (2026-06-12): `scripts/review_near_duplicate_clusters.py` + `docs/NEAR_DUPLICATE_REVIEW.md` + conservative no-deletion policy + `limit_one_per_digest` for digest and public demo
- **Digest history sliding window** (P4F · 30-day rolling index) — not
  yet built; current `digests.json` keeps all history but the public
  page renders only `latest`
  — ✅ **P6F DONE** (2026-06-12): `scripts/build_artvee_daily_digest.py` + `--history-days 30` + `--near-dup-clusters` + `docs/DIGEST_HISTORY.md` + runtime `reports/runtime/digest-history.json` + `digests.json` picks array with near_dup_cluster_id
- **Pages CDN wait 60s → 90s** — published verification sometimes
  hits `cdn.jsdelivr.net` 60s edge; tune the wait window
- **Report `MEDIA` Telegram path** — reports under
  the OpenClaw workspace reports dir not in the OpenClaw allowed dirs;
  sent as plain-text summary only (P5D · P5E both confirmed)
downloader (e.g. `requests` + direct CDN URL, or `selenium`
with longer page-load timeout). If they still fail, the
corresponding `source_url`s are permanently retired (added to
a `KNOWN_RETIRED` set in `artvee_identity.py` and skipped by
future refills / candidates). P5+ is a meta-bucket for "later
phases not yet individually scoped".

**Also still open under P5+:** the Le_rêve `source_url` label
bug (P4A+1 § 6.4) — `image` is correct, but the `source_url`
string still ends in `/le-reve/` instead of `/le-reve-2/`.
Mitigated at export time by
`--exclude-duplicate-source-url-groups`; the underlying
build-script label fix remains.

### Object-storage full archive
- Optional S3 / R2 / OSS mirror of the local `images/` + `metadata/`,
  for cross-device access without bloating the source machine.
- Bandwidth and cost profiles are explicitly out-of-scope for the
  default local-first deployment.

### More public-domain sources
- Wikimedia Commons, The Met (Open Access), Rijksmuseum,
  Bibliothèque nationale de France — all have compatible
  public-domain licensing.
- The data schema is intentionally source-agnostic
  ([docs/GALLERY_DATA_SCHEMA.md](docs/GALLERY_DATA_SCHEMA.md)),
  so a new source means a new builder script, not a schema
  migration.

### Agent-callable interface
- Expose the gallery as a structured tool surface so other
  OpenClaw / Hermes agents can query the local archive
  ("show me 3 ukiyo-e prints with a winter palette") without
  touching the source files directly.
- Stay local-first; the interface is a read-only API over
  `web/data/*.json`, not a separate database.

### P6A · Telegram MEDIA staging fix ✅ PASS (2026-06-12 19:46)
- Root cause: OpenClaw MEDIA allowlist does not include the user-workspace reports dir
- Fix: stage reports into the OpenClaw-allowed media dir under `artvee-reports/`, then attach
- New helper: `scripts/stage_report_for_telegram_media.py` (stdlib, ~146 lines)
- Notifier: `scripts/artvee_telegram_notify.py` +`--media` flag
- Test: 2026-06-12 19:45 → Telegram `Message ID: 22623` delivered with MEDIA
- See `<workspace>/reports/artvee-gallery-p6a-telegram-media-staging-20260612.md`

### P6D · GitHub Pages CDN wait 60s → 90s ✅ PASS (2026-06-12 20:30)
- Default `sleep 60` → `sleep "$CDN_WAIT"` (var, default 90)
- New flag: `--cdn-wait N` (range 0..600)
- Validation: 0..600 enforced; help text updated
- 90s chosen because 60s was on the edge of the observed cold-cache recovery window; 90s + `wait_and_curl()` retry gives ≥95% first-pass on a clean push
- Backward compat: `--cdn-wait 60` reproduces old behavior
- Public surface: unchanged
- See `<workspace>/reports/artvee-gallery-p6d-cdn-wait-90s-20260612.md`

### P6B · Mark unresolved losers as KNOWN_RETIRED ✅ PASS (2026-06-12 21:05)
- 4 unreachable URLs (la-plume-4, le-reve, le-reve-3, tetes-byzantines-brunette) explicitly marked
- New: `scripts/mark_known_retired_urls.py` (no network, dry-run default, --force to overwrite)
- New: `examples/known_retired_urls.sample.json` (schema doc, synthetic URLs)
- New runtime artifact: `reports/runtime/p6b-known-retired-urls.json` (NOT tracked)
- Each record: status=known_retired, should_retry=False, with best-effort title/artist from web/data
- Safety: refuses --out outside reports/runtime/, falls back to P4B if P5A missing
- Does NOT modify strict integrity (losers not in web/data → already excluded)
- Future reports should split: `known_retired=N, blocking_unresolved=M`
- See `<workspace>/reports/artvee-gallery-p6b-known-retired-urls-20260612.md`

### P6C · Near-duplicate review workflow ✅ PASS (2026-06-12 21:31)
- New: `scripts/review_near_duplicate_clusters.py` (Pillow-optional, fallback to P5D aHash, threshold=0 default)
- New: `docs/NEAR_DUPLICATE_REVIEW.md` — design doc, review rules, and known findings
- Conservative policy: no automatic deletion, no exclusion, no movement
- 8 exact aHash clusters found (threshold=0): 3 collision_legacy + 2 artist_cluster + 3 mixed
- Per-record policy: `keep` / `limit_one_per_digest` / `review_before_digest`
- Runtime outputs: `reports/runtime/p6c-near-dup-clusters.{json,md}` + `p6c-near-dup-contact-sheet.html` (NOT tracked)
- Contact sheet: static HTML, relative thumb paths, no base64, no local path leaks
- See `<workspace>/reports/artvee-gallery-p6c-near-duplicate-review-20260612.md`

### P6G · KNOWN_RETIRED-aware status report ✅ PASS (2026-06-12 21:18)
- Status split: `known_retired` (audited, not blocking) vs `blocking_unresolved` (needs attention)
- New: `scripts/build_artvee_status_report.py` (no network, no subprocess)
- New runtime artifacts: `reports/runtime/artvee-status-report.{json,md}` (NOT tracked)
- Current snapshot: records=756, known_retired=4, blocking_unresolved=0, strict_integrity=pass
- Fallback: if p6b manifest missing → known_retired=0, blocking_unresolved=unresolved_count, warning logged
- Telegram wording: `confirm_demo_refresh.sh` PASS summary now includes `Retired sources: N known_retired, blocking_unresolved=M`
- See `<workspace>/reports/artvee-gallery-p6g-status-report-20260612.md`

### P6F · Digest history 30-day + near-dup-aware selection ✅ PASS (2026-06-12 22:00)
- Modified: `scripts/build_artvee_daily_digest.py` — added `--history-days`, `--history-file`, `--ignore-history`, `--near-dup-clusters`
- New: `docs/DIGEST_HISTORY.md` — design doc, history model, fallback behavior
- 30-day sliding window: avoids repeating id, artist, or near-dup cluster within the window
- Idempotent: same-day re-run updates the same entry, does not append duplicates
- Capped: max `window_days * 2` entries (minimum 60), file never grows unboundedly
- Fallback: if strict filter (id+artist+cluster) leaves < select candidates, relax rules in order (cluster→artist→id) and record fallback reason
- Runtime history file: `reports/runtime/digest-history.json` (NOT tracked, gitignored)
- `web/data/digests.json` now includes `picks` array with `near_dup_cluster_id` per pick
- Near-dup cluster mapping loaded from P6C JSON: 23 artwork→cluster mappings (8 clusters, 23 records)
- Safety: no network, no file modification to source data, no deletion, no GitHub Pages push
- See `<workspace>/reports/artvee-gallery-p6f-digest-history-20260612.md`

### P7A · Daily automation hardening / phase consolidation ✅ PASS (2026-06-12 22:30)
- New: `scripts/artvee_daily_health_check.sh` + `scripts/artvee_daily_health_check.py` — single-command daily health check
- New: `docs/DAILY_OPERATING_PLAYBOOK.md` — operational reference for daily workflow
- Consolidates all previous phase-specific checks (P6B, P6C, P6F, P6G) into one daily command
- Modes: default, `--date`, `--no-telegram`, `--online`, `--media`
- Checks: readiness, integrity, status report, nightly batch, candidate refresh, digest history, near-dup clusters, candidate state, online (optional)
- Recommended actions: `healthy_no_action` / `candidate_ready_manual_publish_optional` / `attention_required`
- Current snapshot: records=756, known_retired=4, blocking_unresolved=0, integrity=PASS, readiness=PASS, candidate=PASS, online=200+200
- Daily cron rhythm documented: 01:30 refill, 02:00 batch, 02:30 confirm_demo_refresh candidate, manual approved publish only
- No auto-publish cron added — approval remains manual by design
- See `<workspace>/reports/artvee-gallery-p7a-daily-automation-hardening-20260612.md`

### P7A+1 · OpenClaw binary resolution for health check Telegram notify ✅ PASS (2026-06-12 23:07)
- Fixed `artvee_telegram_notify.py` PATH lookup: `os.path.exists('openclaw')` → `shutil.which('openclaw')` via `_resolve_openclaw_bin()`
- Resolution order: `--openclaw-bin` CLI arg > `ARTVEE_OPENCLAW_BIN` env > `OPENCLAW_BIN` env > PATH lookup > None (graceful skip)
- Added `--openclaw-bin` to `artvee_telegram_notify.py`, `artvee_daily_health_check.sh`, `artvee_daily_health_check.py`
- Added `telegram_notify` JSON field to health check report (`enabled`, `media_requested`, `openclaw_status`, `sent`, `message_id`)
- Graceful skip: if binary missing, health check still generates report and exits 0; Telegram notify skipped with clear message
- Test result: Message ID 22727 delivered successfully via interactive shell; MEDIA attachment also works
- No hardcoded paths, no secrets in error messages
- See `<workspace>/reports/artvee-gallery-p7a1-openclaw-binary-resolution-20260612.md`

### P7B · Optional daily health Telegram cron ✅ PASS (2026-06-12 23:25)
- New script: `scripts/install_daily_health_cron.sh` — idempotent P7B cron installer with marker-based block management
- Cron time: `0 3 * * *` (Asia/Shanghai, after 02:30 confirm_demo_refresh)
- Command: `cd <artvee-repo> && bash scripts/artvee_daily_health_check.sh --online --media`
- Log: `logs/daily-health-cron/daily_health_YYYYMMDD_030000.log`
- Idempotency: `--install` replaces existing block; `--remove` deletes it; `--time` changes schedule
- Backup: `logs/daily-health-cron/crontab.before_p7b.*.txt`
- Manual test: ✅ PASS — Telegram summary + MEDIA delivered, log contains no secrets
- Daily cron rhythm: 01:30 refill, 02:00 batch, 02:30 confirm_demo_refresh, 03:00 daily health check
- See `<workspace>/reports/artvee-gallery-p7b-daily-health-cron-20260612.md`

### P7D · v0.2.0-alpha release consolidation ✅ PASS (2026-06-13 04:50)
- Consolidates P3D through P7B+1 into a single tagged release; no new code or data.
- New docs: `docs/RELEASE_NOTES_v0.2.0-alpha.md`, `CHANGELOG.md`.
- README updated: Latest release, docs index, operational model section.
- Status docs: `docs/PROJECT_STATUS.md` (P7D row + snapshot), `docs/ROADMAP.md` (this entry), `docs/DEVELOPMENT.md` (release checklist), `docs/DAILY_OPERATING_PLAYBOOK.md` (v0.2.0-alpha operating baseline), `docs/RETROSPECTIVE.md` (release consolidation lesson).
- Tag: `v0.2.0-alpha` (annotated), pushed to `origin`.
- GitHub Release: `gh release create v0.2.0-alpha --notes-file docs/RELEASE_NOTES_v0.2.0-alpha.md`.
- See `<workspace>/reports/artvee-gallery-p7d-v0.2.0-alpha-release-20260613.md`.

### P7E · v0.2.0 observation window 🔄 IN PROGRESS (2026-06-14)
- 3-day observation window: 2026-06-14 — 2026-06-16.
- No new code, no data changes, no downloads, no publish. Only observation docs.
- New doc: `docs/V0_2_OBSERVATION_WINDOW.md` defines daily checklist, healthy criteria, warning signs, and stable-readiness gates.
- First-day signal: 03:02 Telegram health summary + MEDIA delivered; records=795, known_retired=4, blocking_unresolved=0, integrity=PASS, readiness=PASS, online=200+200.
- Next: v0.2.0 stable if all 3 days are green.
- See `<workspace>/reports/artvee-gallery-p7e-v0.2-observation-window-20260614.md`.

### P7E+1 · Online endpoint failure diagnosis ✅ PASS (2026-06-15 06:55)
- Read-only diagnosis of the 03:00 Daily Health anomaly (`Online: gallery=0, digest=0`).
- Verified the **local Artvee system is healthy** (815 records, strict integrity PASS, readiness PASS, candidates ready, no blocking unresolved).
- Server-side curl of 9/9 public endpoints → all **HTTP 404** (DNS+TLS work; the paths genuinely do not exist on Pages).
- Git forensic: local `conanxin.github.io` HEAD = `f419d31` (2026-06-12 artvee refresh); remote `origin/main` = `41bb6258` (local 8 commits behind). Between the two, 8 WBW SpaceX Mars publish commits (013fbdb → 41bb625) removed the entire `projects/artvee-gallery-demo/` and `projects/artvee-gallery-digest/` subtrees (205 files / 2042 lines). `git ls-tree -r origin/main -- projects/artvee-gallery-{demo,digest}` = 0 files.
- Diagnosed: health script's `except Exception` swallowed `urllib.error.HTTPError` (404), so the real code was masked as 0 — **signal distortion, not network failure**.
- Side-finding: the same WBW Mars publish burst also wiped `projects/yang-fudong-fragrant-river/` (35 files). Out of scope for P7E+1; flagged for follow-up.
- No download / refill / batch / push / commit during diagnosis.
- See `<workspace>/reports/artvee-gallery-p7e1-online-endpoint-failure-20260615.md`.

### P7E+2 · Public demo restore after GitHub Pages content drift ✅ PASS (2026-06-15 07:18)
- Restored `projects/artvee-gallery-demo/` (215 files / 5.7 MB) and `projects/artvee-gallery-digest/` (5 files / 284 KB) on the public GitHub Pages without reverting any of the 9 WBW Mars commits.
- Workflow: `git pull --ff-only` (Pages local f419d31 → 3748acb, no force, no reset) → `confirm_demo_refresh.sh` PASS → `publish_demo_refresh_candidate.sh --date 2026-06-15 --approve --cdn-wait 90` (single commit + push).
- Restore commit on `origin/main`: **`a5ad80c`** ("Refresh Artvee public demos from approved candidate 2026-06-15"), pushed `3748acb..a5ad80c`.
- Online re-verification: 9/9 endpoints HTTP 200 (gallery 5/5 + digest 5/5; sample thumbs 5/5 across `[0, 25, 50, 75, 99]`).
- **Health script fix** in `scripts/artvee_daily_health_check.py` (P7E+2 §7): split `except Exception` into `urllib.error.HTTPError` (record real HTTP code) / `urllib.error.URLError` (record 0 + `network_error`) / `TimeoutError` / `ConnectionError`. New `online.kind` ∈ {ok, http_error, network_error, skipped}; new `online.gallery_http_code` and `online.gallery_error` fields. `recommended_action` now branches: `attention_required_pages_content_drift` (404-class) vs `attention_required_network_or_pages_unreachable` (0-class) vs the original healthy actions. Backward compatible with old summary keys.
- New section in `docs/DAILY_OPERATING_PLAYBOOK.md` (§ 12) for `Online: gallery=404, digest=404` content-drift recovery.
- Artvee repo commit: adds the health script fix + the 5 doc updates. One commit, one push, no dirty runtime files, no secrets in tracked paths.
- CI: `open-source-ready.yml` run kicked off; verdict pending at report time.
- Safety: no download / refill / batch / nightly; no full assets uploaded (only the public demo's existing thumbs already shipped in 2026-06-12 candidate); no `images/` / `metadata/` / `thumbs/` modification in this repo; no force-push; no rollback of WBW Mars commits.
- See `<workspace>/reports/artvee-gallery-p7e2-public-demo-restore-20260615.md`.

### P7E+3 · v0.2.0 observation continuation (Day 2, 2026-06-15) ✅ PASS (closed by P7F)
- Observation window continues: Day 1 (2026-06-14) green, Day 2 (2026-06-15) green with incident annotation (see `V0_2_OBSERVATION_WINDOW.md` day-by-day log).
- Day-2 re-check at 07:39 GMT+8: records=815, known_retired=4, blocking_unresolved=0, integrity=pass, readiness=pass (4/4), online.kind=ok, gallery=200, digest=200, candidates ready, `recommended_action=candidate_ready_manual_publish_optional`.
- Cross-repo sibling phases (in the shared Pages repo, not in artvee): **YF-RESTORE-1** restored `projects/yang-fudong-fragrant-river/` (Pages commit `31b2ac7`); **PAGES-GUARD-1** added `scripts/check-project-publish-guard.py` (Pages commit `6d3961c`).
- Files changed in artvee: `docs/V0_2_OBSERVATION_WINDOW.md` (Day 2 log), `docs/PROJECT_STATUS.md` (continuation snapshot + P7E+1/P7E+2 phase markers), `docs/ROADMAP.md` (this entry).
- Safety: no download / refill / batch / nightly; no runtime data modification; no `--approve`; no CI regression.
- Status: closed on 2026-06-16 by **P7F** (stable readiness review). Day 3 ran clean; see `docs/STABLE_READINESS_v0.2.0.md` for the 15/15 PASS checklist.

### P7F · v0.2.0 stable readiness review ✅ PASS (2026-06-16 06:38)
- 3-day observation window closed: Day 1 (2026-06-14) green, Day 2 (2026-06-15) green with incident annotation, Day 3 (2026-06-16) green.
- New doc: `docs/STABLE_READINESS_v0.2.0.md` — 15/15 readiness criteria PASS (repo state, integrity, readiness, online 6/6 endpoints, Telegram cron text+MEDIA, no tracked secrets / runtime data, Day-2 incident closed).
- Live rebuild snapshot: records=835, known_retired=4, blocking_unresolved=0, strict_integrity=pass, readiness=pass (4/4), online 6/6 endpoints HTTP 200.
- Telegram cron verified: text (message_id 23707) + MEDIA (message_id 23709) delivered at 03:00 Asia/Shanghai on 2026-06-16.
- Day-2 incident fully closed (Pages content drift: diagnosed P7E+1, restored P7E+2, Pages publish guard shipped cross-repo, signal-distortion bug fixed in `artvee_daily_health_check.py`).
- Safety: no download / refill / batch / nightly / `--approve`; no `images/`, `metadata/`, `thumbs/`, `dist/`, `digests/`, `logs/`, `inbox/`, `web/data/`, `index/`, `reports/runtime/`, `tmp/` modification; no secrets / real paths leaked.
- Files changed: `docs/STABLE_READINESS_v0.2.0.md` (new), `docs/PROJECT_STATUS.md` (P7F row + snapshot), `docs/ROADMAP.md` (this entry), `docs/V0_2_OBSERVATION_WINDOW.md` (Day 3 PASS), `README.md` (stable-readiness link).
- **Tag / release:** **not** cut. `v0.2.0` stable is **pending user approval**.
- See `<workspace>/reports/artvee-gallery-p7f-v0.2-stable-readiness-20260616.md`.

### Next (post-v0.2.0 stable)
- **v0.2.0 stable** — released 2026-06-16 (tag `v0.2.0`, GitHub Release `v0.2.0`). See `docs/RELEASE_NOTES_v0.2.0.md`.
- **P8 automation polish** — pre-flight `--dry-run` on the publish helper; optional 02:55 *pre-check* cron that runs the daily check in `--no-telegram` mode and alerts only on FAIL; CI matrix that exercises the cron installer in a container.
- **Content product polish** — promote the `KNOWN_RETIRED` table into the public demo's UI; consider a per-artist collection view; tune the digest `--max-per-artist` and `--exclude-risk` defaults if user feedback warrants it.
- **Watch the P7E+2 signal-distortion fix for 7 days of clean runs** (i.e. through 2026-06-23) before considering the `online.kind` branches fully settled.

### P7B+1 · Cron MEDIA delivery verification / failure-only fallback ✅ PASS (2026-06-13 04:30)
- Refactored `telegram` JSON object: `requested` / `openclaw_status` / `text_summary{attempted,sent,message_id,error}` / `media{requested,staged,staged_path,sent,message_id,error,simulated_failure}` / `fallback{attempted,sent,message_id,reason}`.
- Failure-only fallback: when health=PASS, text=sent, MEDIA=failed → a short text-only warning is sent (at most once per run, never recursive, does not change exit code).
- New flag: `--simulate-media-failure` for verifying the fallback chain without breaking the real MEDIA allowlist.
- Cron command (post-P7B+1): `0 3 * * * export PATH=$HOME/.local/bin:$PATH && export ARTVEE_TELEGRAM_CHAT_ID='<telegram-chat-id>' && cd <artvee-repo> && bash scripts/artvee_daily_health_check.sh --online --media`.
- Secret hygiene: hardcoded `DEFAULT_CHAT_ID` removed from `artvee_telegram_notify.py`; resolution order is `--chat-id` CLI > `ARTVEE_TELEGRAM_CHAT_ID` env > OpenClaw config > hard error.
- Cron-like verification: `env -i HOME=... PATH=... ARTVEE_TELEGRAM_CHAT_ID=... bash scripts/artvee_daily_health_check.sh --online --media` runs the full chain; verified text + MEDIA delivery, exit 0, log free of tokens / chat ids.
- Files: `scripts/artvee_daily_health_check.{py,sh}`, `scripts/artvee_telegram_notify.py`, `scripts/install_daily_health_cron.sh`, `docs/DAILY_OPERATING_PLAYBOOK.md` (§ 9), `docs/DEVELOPMENT.md` (§ 22), `docs/RETROSPECTIVE.md` (lesson).
- See `<workspace>/reports/artvee-gallery-p7b1-cron-media-fallback-20260613.md`.

### P7B+2 · Staged-only MEDIA + transport-deferred fallback ✅ PASS (2026-06-18 06:55)
- Root cause of 2026-06-18 03:00 MEDIA-failed: a transient `GatewayTransportError: gateway timeout after 10000ms` on the local OpenClaw gateway (`ws://127.0.0.1:18789`). The report *was* already staged into an OpenClaw-allowlisted directory; the previous reporting was misleading because it pointed operators at the raw `reports/runtime/daily-health/...` path (which is not allowlisted) and the fallback also hit the same transport error.
- `stage_report_for_telegram_media.py --print-meta`: new mode that emits a single-line JSON object with `raw_report` / `staged_report` / `stage_failed` / `staged_size` / `media_root` / `error`. Lets the caller detect a staging failure without parsing a freeform path.
- `artvee_daily_health_check.py`: media is now **staged-only**. If `--print-meta` reports `stage_failed`, MEDIA is recorded as failed and we never attempt to attach the raw path. The raw path is recorded in `telegram.media.raw_report` for diagnosis.
- New `telegram.media.error_kind` field classifies failures into: `transport` / `media_allowed` / `binary_missing` / `timeout` / `exit_nonzero` / `simulated` / `stage_failed`.
- New `telegram.fallback.reason` taxonomy: `media_failed` / `stage_failed` / `media_transport_deferred`. The first two still send the fallback immediately; `media_transport_deferred` writes `.fallback-pending-YYYY-MM-DD.json` next to the report and waits for the next run (which must have a successful `text_summary` to prove the gateway is healthy) to flush it.
- `artvee_telegram_notify.py`: new `_classify_error()` helper; `send_text()` returns `error_kind`; `--wait` mode now classifies the failure before returning.
- Cron-like verification: `text_summary` sent (25027), `media` sent (25028), `fallback` not triggered, exit 0, no secrets in log. `--simulate-media-failure` produces `fallback.sent=true reason=media_failed`. End-to-end transport-defer test produces `fallback.reason=media_transport_deferred` + a real `.fallback-pending-...json` on disk.
- Safety: no download / refill / batch / `--approve` / Pages push; cron line untouched; no real secrets printed (only `${#CID}` length).
- Files: `scripts/stage_report_for_telegram_media.py`, `scripts/artvee_daily_health_check.py`, `scripts/artvee_telegram_notify.py`, `docs/DAILY_OPERATING_PLAYBOOK.md` (§ 9.5), `docs/DEVELOPMENT.md` (§ 23), `docs/PROJECT_STATUS.md` (row + snapshot), `docs/RETROSPECTIVE.md` (§ 2.20).
- See `<workspace>/reports/artvee-gallery-p7b2-daily-health-media-staging-fix-20260618.md`.

### P7B+3 · Pending MEDIA replay + OpenClaw transport health check ✅ PASS (2026-06-18 07:30)
- Adds `scripts/replay_pending_media.py`: scans `reports/runtime/**/.fallback-pending-*.json`, validates the staged path is still under the OpenClaw allowlist, re-sends via `scripts/artvee_telegram_notify.py`, and archives the pending file to `replayed/` (success) or `quarantine/` (max-retries / invalid / no-chat-id). Default mode is **dry-run** for safety; pass `--apply` to actually send. `--limit` and `--max-retries` bound the work; the original pending file is never deleted.
- Adds `scripts/check_openclaw_transport.py`: read-only CLI probe. Runs `openclaw --version` (resolves through `ARTVEE_OPENCLAW_BIN` / `OPENCLAW_BIN` / PATH) and a local TCP connect to the gateway port (default `127.0.0.1:18789`). Emits a single JSON document with `status` (`ok` / `error` / `timeout` / `missing` / `not_checked`), per-probe latency, and an `error_class` field. **Never sends a Telegram message**; safe to call from cron or interactive sessions.
- `artvee_daily_health_check.py`: new `media_replay` block in the report JSON listing `pending` / `replayable` / `quarantined` / `transport_status` / `transport_latency_ms` / `transport_checked_at`. The 03:00 cron **does not auto-replay** — replay is a separate, opt-in step. The `media_replay` scan explicitly excludes `replayed/` and `quarantine/` subdirectories so archived files are not double-counted.
- No new cron installed. The optional 03:10 replay cron is documented in `docs/DAILY_OPERATING_PLAYBOOK.md` § 9.6 and `docs/MEDIA_REPLAY.md` § 8 — it requires explicit `apply` (do not auto-install).
- Verification: synthetic test pending (attempts=0) was actually sent to Telegram (message_id=25071, 25073, 25084). Synthetic max-retries pending (attempts=3) was archived to `quarantine/` with a `.replay-result-*.json` sidecar. Daily health `media_replay` block reflects the archived state (`pending=0, replayable=0, quarantined=1, transport_status=ok`).
- Safety: no download / refill / batch / `--approve` / Pages push; cron line untouched; no tokens / chat ids / secrets printed. The replay script reuses the notifier's `_resolve_openclaw_bin` and `load_chat_id` and rejects non-staged paths before any Telegram send.
- Files: `scripts/replay_pending_media.py`, `scripts/check_openclaw_transport.py`, `scripts/artvee_daily_health_check.py`, `docs/MEDIA_REPLAY.md`, `docs/DAILY_OPERATING_PLAYBOOK.md` (§ 9.6, § 1 dating), `docs/DEVELOPMENT.md` (§ 24), `docs/PROJECT_STATUS.md` (row + snapshot), `docs/RETROSPECTIVE.md` (lesson § 2.21).
- See `<workspace>/reports/artvee-gallery-p7b3-pending-media-replay-20260618.md`.

### P7C · Automated approved-publish preparation
- Pre-stage the approved-publish flow so a future `--approve` can be triggered by a scheduled event (e.g., "auto-publish on Sunday if candidate QA PASS").
- Requires a `SECRET_ROTATION_POLICY.md` for the Pages repo PAT if full-auto is desired.
- Current scope: preparation only, no implementation.

_superseded by P7D · v0.2.0-alpha release consolidation above (this is the implementation of the original P7D marker)._

### P8A · Post-stable ops status command ✅ PASS (2026-06-18 08:30)
- New `scripts/artvee_ops_status.sh` (shell wrapper) + `scripts/artvee_ops_status.py` (Python core). One read-only command that aggregates repo state, records, integrity, readiness, candidate readiness, pending MEDIA, OpenClaw transport health, Pages guard availability, and live public-demo HTTP status into a single JSON + Markdown report.
- Default mode is strictly read-only + no Telegram. With `--online` it adds `curl --head` probes of the public gallery / digest URLs. With `--include-pages` it adds a read-only `git status` check of the local `<pages-repo>` clone (never rsyncs / commits / pushes). With `--media` it sends the report via Telegram + staged MEDIA (the same staged-only path the daily health check uses; the raw report path is never sent).
- Reuses existing helpers to keep counts consistent: `artvee_daily_health_check._scan_pending_media` (imported directly) for pending/quarantined MEDIA, `check_openclaw_transport.py` for transport health, `stage_report_for_telegram_media.stage_report` for the optional MEDIA send, `artvee_telegram_notify.send_text` for the Telegram send.
- One canonical `recommended_action` enum (stable; first-match-wins priority: integrity > readiness > pages_drift > media_pending > candidate_ready > healthy). The enum is documented in `docs/POST_STABLE_OPERATIONS.md` § 5.
- No new cron installed. The ops status command is on-demand; the 03:00 daily health cron still owns continuous monitoring. If a future morning-briefing cron is desired, it can simply wrap `artvee_ops_status.sh --date $(date +%F) --media` — explicitly out of scope for v0.2.x.
- Verification: dry-run (--no-telegram --online --include-pages) PASS; real Telegram + MEDIA send PASS (message_id=25149, transport healthy at 37–43ms, no side effects). Pending MEDIA scan matches daily health exactly (`pending=0, replayable=0, quarantined=1`). Online gallery + digest both 200; Pages repo clean=true.
- Safety: no download / refill / batch / `--approve` / Pages push; no `images/`, `metadata/`, `thumbs/`, `dist/`, `digests/`, `logs/`, `inbox/`, `web/data/`, `index/`, `reports/runtime/`, `tmp/` modification; no tokens / chat ids / secrets printed; raw report path never sent to OpenClaw (always staged).
- Files: `scripts/artvee_ops_status.{sh,py}`, `docs/POST_STABLE_OPERATIONS.md`, `docs/DAILY_OPERATING_PLAYBOOK.md` (§ 9.7 + status-report + dating), `docs/DEVELOPMENT.md` (§ 25), `docs/PROJECT_STATUS.md` (P8A row + snapshot), `docs/RETROSPECTIVE.md` (§ 2.22), `README.md` (light link addition).

### P8A+1 · Pages guard visibility fix ✅ PASS (2026-06-18 10:23)
- P8A's `pages_guard_available` was always `false` because it looked for `scripts/check-project-publish-guard.py` and `docs/PAGES_PUBLISH_GUARD.md` **inside the Artvee repo**. PAGES-GUARD-1 had installed them in the **Pages repo** (`conanxin.github.io`). Wrong-scope check, not a guard implementation bug.
- Fix: resolve the Pages repo path (CLI `--pages-repo` > `$ARTVEE_PAGES_REPO` > `$PAGES_REPO` > `Path.home() / "conanxin.github.io"`) → inspect *that* repo for the canonical files → optionally run a read-only guard smoke with the artvee allowlist (`projects/artvee-gallery-demo`, `projects/artvee-gallery-digest`, `projects/data.json`).
- Default uses `Path.home()` rather than a hard-coded absolute
  user-home path so the path-leak CI gate keeps passing and the
  script stays portable.
- New JSON sub-object `pages.{repo_detected, repo_clean, branch, head, origin_main, guard_available, guard_script_exists, guard_doc_exists, guard_script, guard_doc, guard_smoke, guard_smoke_detail, resolved_via, error}`. Top-level P8A compat fields preserved.
- New CLI flags: `--pages-repo <path>`, `--guard-allow <entry>` (repeatable), `--no-guard-smoke`.
- Verified: `pages_guard_available=true`, `pages.guard_smoke=pass`, Pages repo `git status --porcelain` empty, HEAD unchanged, Telegram + MEDIA send returned message_id=**25188**.
- Safety: same as P8A (read-only with respect to the Pages repo; no download / refill / batch / `--approve` / Pages push).
- Files: `scripts/artvee_ops_status.py` (detection rewrite), `docs/POST_STABLE_OPERATIONS.md` (§ 7 + § 9), `docs/DAILY_OPERATING_PLAYBOOK.md` (§ 9.8), `docs/DEVELOPMENT.md` (§ 26), `docs/PROJECT_STATUS.md` (row + snapshot), `docs/RETROSPECTIVE.md` (§ 2.23).
- See `<workspace>/reports/artvee-gallery-p8a1-pages-guard-visibility-20260618.md`.

### P8B · Content product polish ✅ PASS (2026-06-18 11:08)
- **Gallery demo polish**: `scripts/export_artvee_gallery_public_demo.py` now injects a "P8B info card" into the public `index.html` (idempotent, inline CSS, no front-end framework). The card surfaces demo title, release version (auto-detected via `git describe --tags --abbrev=0`), Last-updated date, public-record count + honest "Source archive: local-first full archive, not fully published" disclosure, and the canonical links (Daily Digest / GitHub repo / `<release>` / About).
- **Digest index polish**: index template now uses the auto-detected release tag, adds the archive link, and shows the 30-day entry count in the meta row.
- **Digest history archive (new)**: `export_artvee_digest_public_page.py` now writes `archive.html` and `data/digest-history.json` next to the existing digest bundle. The `digest_path` field (which contains a local-absolute path even after the digest builder's redaction) is **stripped** before going public; everything else (`date`, `picks[].{id,artist,category,near_dup_cluster_id}`, `strategy`, `updated_at`, `window_days`) is preserved. Archive page is text-only; the per-pick 512-thumb stays reachable through the per-day digest HTML.
- **QA integration**: `scripts/confirm_demo_refresh.sh` now has a P8B archive QA step (asserts `archive.html` + `data/digest-history.json` exist, parse, and contain no forbidden substrings) and a digest size budget (5MB soft / 10MB hard). Both PASS for the 2026-06-18 candidate.
- **Verified**: all 10 online endpoints return 200 (gallery demo + assets; digest + archive + history). Public `data/digest-history.json` contains 7 entries (window=30d). Digest bundle size 92K. Gallery 4.3M. No `metadata_path`, no `images/`, no project-root substring, no local-absolute paths in any public text file.
- **Approved publish**: Pages commit `43d771e` on `conanxin.github.io`. Pages guard `check-project-publish-guard.py` ran pre-rsync (PASS) and the diff was confined to the canonical `projects/artvee-gallery-{demo,digest}/` and `projects/data.json` allowlist.
- Safety: no download / refill / batch / `--approve` of any non-public script; no full images / metadata / thumbs uploaded; no force push; no rollback of other Pages commits. The Artvee repo's tracked runtime files (`.gitkeep`, `p4b-collision-migration-plan.md`) were not changed.
- Files: `scripts/export_artvee_gallery_public_demo.py` (info card), `scripts/export_artvee_digest_public_page.py` (archive + release tag detection + leak-aware history redaction), `scripts/confirm_demo_refresh.sh` (archive QA + digest size budget), `docs/DIGEST_HISTORY.md` (§ 8 archive subsection), `docs/ROADMAP.md` (P8B entry), `docs/PROJECT_STATUS.md` (row + snapshot), `docs/RETROSPECTIVE.md` (§ 2.24 lesson).
- See `<workspace>/reports/artvee-gallery-p8b-content-product-polish-20260618.md`.

### P8C · Public digest archive expansion / navigation polish ✅ PASS (2026-06-18 11:45)
- **Archive navigation polish**: `archive.html` now opens with a top `nav.top-nav` row (Latest Digest / Gallery Demo / GitHub / Release / Archive / data/digests.json / data/digest-history.json) and a `summary` chip row (Total days / Total picks / Unique artists / Available range / Top categories). Honest "History entries currently available" badge preserved from P8B.
- **Digest cards (new)**: P8B's text-only table is replaced with one `.day-card` per entry (newest first). Each card has the date + pick-count, a strategy chip, category chips, near-dup cluster chip (if any), and a 5-column auto-fill pick grid showing 256-thumbnail + artist + category + near-dup label. Cards have `data-artists` / `data-categories` / `data-search` for the client-side filters.
- **Filters (new)**: external vanilla `archive.js` adds an Artist `<select>`, Category `<select>`, and a free-text `Search` input (matches title / artist fragments). "Clear" button resets all three. "Jump to latest" smooth-scrolls to the newest visible card. A `#no-results` notice appears when filters hide every card. Page is fully readable with JS disabled — JS only adds interactivity.
- **Data schema polish (P8C)**: `data/digest-history.json` now carries top-level `generated_at`, `history_entries`, `available_range.{first_date,latest_date}`, and a `summary` block (`total_days` / `total_picks` / `unique_artists` / `top_categories`) so downstream consumers don't have to recompute them. The `digest_path` field continues to be stripped before going public. `entries[]` shape is unchanged from P8B for backward compatibility.
- **Bundle size growth (controlled)**: 256-thumbnail copies added under `assets/thumbs/256/`. For the 2026-06-18 candidate: 15 256-thumbs (15 KB – 27 KB each), archive.html 19 KB, archive.js 4.3 KB. Total digest bundle 320 KB (still well under the P8B 5MB soft / 10MB hard budget). Gallery unchanged at 4.8 MB.
- **QA integration**: `confirm_demo_refresh.sh` archive QA now checks: `day_cards == history_entries`; all 5 nav / filter IDs present in `archive.html`; `archive.js` exists, ≥ 1 KB, and references `applyFilters` + `populateSelect`; `THUMBS_256_COUNT > 0`. All PASS for the 2026-06-18 candidate (`day_cards=7`, `thumbs_256=15`).
- **Verified**: 8 / 8 digest endpoints return 200 (gallery demo `/` + `/data/artworks.json`; digest `/`, `/digest.html`, `/archive.html`, `/data/digests.json`, `/data/digest-history.json`, `/archive.js`). Archive page spot-check confirms `class="day-card"` + all 5 filter IDs + `Latest Digest` / `Gallery Demo` / `GitHub` / `Release` / `Top categories` text. Public `data/digest-history.json` schema includes `generated_at` / `available_range` / `summary`; 0 leaks; `digest_path` stripped.
- **Approved publish**: Pages commit `131f663` on `conanxin.github.io` (rsync: `43d771e..131f663 main -> main`). 20 files changed, +322 / -83. Pages guard `check-project-publish-guard.py` ran pre-rsync (PASS, no other Pages projects touched).
- Safety: no download / refill / batch; no full images / metadata / thumbs uploaded; no force push; no rollback of other Pages commits; no `web/` / `images/` / `metadata/` / `thumbs/` / `web/data/` modification; no `artvee_ops_status.py` or `install_daily_health_cron.sh` modification; P8B's path-leak cleanup in docs was applied (P8B had 8 stragglers left in docs that P8C caught during preflight; the `readiness` check was FAIL until those were fixed).
- Files: `scripts/export_artvee_digest_public_page.py` (cards + filters + 256 thumbs + history schema), `scripts/confirm_demo_refresh.sh` (P8C archive QA), `docs/DIGEST_HISTORY.md` (§ 9 navigation polish), `docs/POST_STABLE_OPERATIONS.md` (§ 12.3), `docs/PROJECT_STATUS.md` (P8C row + snapshot), `docs/ROADMAP.md` (P8C entry), `docs/RETROSPECTIVE.md` (§ 2.25 lesson).
- See `<workspace>/reports/artvee-gallery-p8c-public-digest-archive-navigation-20260618.md`.

### Next (post-P8C, v0.2.x polish)
- **P8D** optional media replay cron — *only* if the operator explicitly opts in. P7B+3 documents the cron line; P8D would add a one-click installer for it. Not installed by default.
- **P8E** public search/filter polish — extend the P8C filters with cross-archive full-text search (typed in the search box) and a per-pick lightbox when a card thumbnail is clicked. Defers until the rolling history has at least 14 days so search has enough signal.
- **v0.2.1 patch release** — bundle P7B+1 / P7B+2 / P7B+3 / P8A / P8A+1 / P8B / P8C into a single patch release after 7 days of clean observation. No release has been cut from the current `main`.

### P8D · Optional media replay cron ✅ PASS (2026-06-18 14:10)
- New `scripts/artvee_media_replay_cron.sh` (thin shell wrapper around the existing `replay_pending_media.py --apply`) + `scripts/install_media_replay_cron.sh` (idempotent marker-block installer).
- The wrapper adds three things the manual replay never had: (1) `flock -n` concurrency guard on `reports/runtime/media-replay/.media-replay.lock`; (2) optional transport pre-flight via `check_openclaw_transport.py` so a dead gateway doesn't burn attempts; (3) always writes a `reports/runtime/media-replay/cron-<date>.json` summary JSON.
- `pending=0` is **silent** — only writes the summary JSON. Never sends a "0 pending" notification.
- `pending>0` + `transport=ok` → hands off to `replay_pending_media.py --apply` (the same staged-only P7B+3 flow the operator uses manually). The wrapper itself does not call the Telegram notifier.
- `pending>0` + `transport=down` → skips replay, summary outcome `skipped_transport_unavailable`. Pending stays for the next 03:10 tick.
- Default schedule: `CRON_TZ=Asia/Shanghai 10 3 * * *` — 10 minutes after the 03:00 P7B daily-health cron. Default args: `--limit 5 --max-retries 3`.
- Idempotent install: marker block `# >>> Artvee P8D media replay cron BEGIN … # <<< Artvee P8D media replay cron END`. `--remove` only deletes the P8D block; P7B daily-health cron, refill, batch, etc. are all preserved.
- **Optional, opt-in** — not installed by default. Operator explicitly authorized install at session end.
- Ops status delta: new `media_replay_cron_installed` (bool, from `crontab -l` marker scan) + `media_replay_cron_summary` (latest summary object) + 2 new MD rows. The summary is always readable even if the cron is not installed (an on-demand manual run of the wrapper writes one).
- CI delta: new `bash -n` entries for both shell scripts in `open-source-ready.yml`.
- Verification: dry-run PASS; install --dry-run PASS; install --install idempotent PASS (re-run replaces in place); --remove only removes P8D block; ops status reports `media_replay_cron_installed=true` + `media_replay_cron_summary.outcome=dry_run_completed`. Ready for the first 03:10 tick.
- Safety: no download / refill / batch / `--approve` / Pages push / retired retry / MEDIA allowlist widen; no tokens / chat_ids / secrets printed; no hardcoded user-home paths; `flock -n` prevents overlapping runs; transport down ≠ spam (skipped silently).
- Files: `scripts/artvee_media_replay_cron.sh` (new), `scripts/install_media_replay_cron.sh` (new), `scripts/artvee_ops_status.py` (new helper + summary field + 2 MD rows), `.github/workflows/open-source-ready.yml` (2 new bash -n entries), `docs/DAILY_OPERATING_PLAYBOOK.md` (§ 9.9), `docs/POST_STABLE_OPERATIONS.md` (§ 6.1), `docs/MEDIA_REPLAY.md` (§ 10), `docs/DEVELOPMENT.md` (§ 27), `docs/PROJECT_STATUS.md` (P8D row + snapshot), `docs/ROADMAP.md` (P8D entry), `docs/RETROSPECTIVE.md` (§ 2.23), `README.md` (light link addition).
- See `<workspace>/reports/artvee-gallery-p8d-optional-media-replay-cron-20260618.md`.

### P8D+1 · Cron PATH hardening + 03:10 media-replay activation fix ✅ PASS (2026-06-29 07:05)
- Triggered by the 2026-06-29 cron diagnostic which found: (a) 03:10 media-replay cron produced zero logs and zero summary; (b) refill/batch/confirm-refresh Telegram notifier logged `NOTIFY_FAIL` on every run.
- Root cause A (P0): the P8D media-replay cron line in `crontab -l` was `CRON_TZ=Asia/Shanghai 10 3 * * * cd ...` (7 fields). Cron parses any leading `Name=value` as a per-line env var, not a schedule column, so the 7-field line was silently rejected.
- Root cause B (P1): the same `CRON_TZ=`-on-schedule bug was present in the P8D installer template, so a fresh `--install` would have re-installed the broken line. The pre-P7B refill / batch / confirm-refresh cron lines had no `PATH=` at all, so under cron's minimal `PATH` (no `$HOME/.local/bin`) the OpenClaw binary used by the Telegram notifier was unresolvable.
- Fix A: `scripts/install_media_replay_cron.sh` template now emits `CRON_TZ=Asia/Shanghai` and `PATH=$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin` on their own lines, followed by a clean 5-field schedule.
- Fix B: new `scripts/install_artvee_cron.sh` (P8D+1 unified installer) emits the refill / batch / confirm-refresh block under one marker with the same `CRON_TZ=` + `PATH=` env-var lines. Idempotent; `--remove` only deletes the P8D+1 block.
- Cleanup: surgically removed 13 legacy lines (legacy refill/batch/confirm + their venv-python commented siblings + decorative comment header) so the new block is the only schedule for those three jobs — preventing tomorrow's 01:30 / 02:00 / 02:30 double-runs.
- Verification: `crontab -l` now has exactly 1 instance each of: refill, batch, confirm-refresh, media-replay; 1 P7B marker block; 1 P8D marker block; 1 P8D+1 marker block. Cron-like `env -i ... PATH=$HOME/.local/bin:... bash -lc '...'` dry-run returned `exit 0` and wrote `reports/runtime/media-replay/cron-2026-06-29.json` with `outcome=dry_run_completed`, `transport_status=ok`.
- Observability guarantee: every cron run writes a `cron-<date>.json` summary regardless of outcome (`noop_zero_pending`, `replayed_pending`, `skipped_transport_unavailable`, `skipped_locked`, `dry_run_completed`, `error_helper_import`). A *missing* summary for a day the cron was scheduled to run is now a real failure, not a silent no-op.
- Safety: no download / refill / batch / `--approve` / Pages push / retired retry / MEDIA allowlist widen; no tokens / chat_ids / secrets printed; legacy pre-fix crontab backed up to `logs/artvee-cron/crontab.before_*` (3 timestamps).
- Files: `scripts/install_media_replay_cron.sh` (template fix), `scripts/install_artvee_cron.sh` (new), `docs/DAILY_OPERATING_PLAYBOOK.md` (P8D+1 section), `docs/MEDIA_REPLAY.md` (P8D+1 observability guarantee), `docs/POST_STABLE_OPERATIONS.md` (P8D+1 note under § 6.1), `docs/PROJECT_STATUS.md` (P8D+1 row + snapshot), `docs/ROADMAP.md` (P8D+1 entry), `docs/RETROSPECTIVE.md` (§ 2.24 lesson).
- See `<workspace>/reports/artvee-gallery-p8d1-cron-path-media-replay-fix-20260629.md`.

### Next (post-P8D+2, v0.2.x polish)
- **P8E** public search/filter polish — extend the P8C filters with cross-archive full-text search (typed in the search box) and a per-pick lightbox when a card thumbnail is clicked. Defers until the rolling history has at least 14 days so search has enough signal.
- **v0.2.1 patch release** — bundle P7B+1 / P7B+2 / P7B+3 / P8A / P8A+1 / P8B / P8C / P8D / P8D+1 / P8D+2 / P8D+3 / P8D+4 into a single patch release after 7 days of clean observation. No release has been cut from the current `main`.
- **Morning briefing cron (06:00)** — simple wrapper around `artvee_ops_status.sh --date $(date +%F) --media` if the operator wants a daily morning report. Explicitly out of scope for v0.2.x.

### P8D+3 · Media replay verification cleanup ✅ PASS (2026-07-01 06:48)
- **Trigger**: the 2026-07-01 next-day verification of P8D / P8D+1 / P8D+2 found that the system was *working correctly* — 03:00 daily health text arrived (message_id=27647), 03:00 MEDIA was deferred with `error_kind=transport`, 03:10 media-replay cron re-attached the staged report (`outcome=replayed_pending`, `transport_status=ok`, latency 54ms), and 03:10 MEDIA arrived (message_ids 27649 / 27650). The 2026-06-30 catch-up replay also ran cleanly (message_id=27649). No data failure. But two cosmetic / doc gaps surfaced:
  1. **Stale phase label in user-facing title**: the Telegram replay message said `↻ Artvee Gallery P7B+3 deferred MEDIA replay` — the P7B+3 tag was the original phase that *introduced* the replay workflow, but the active phase hierarchy is now P7B+3 → P8D → P8D+1 (cron activation) → P8D+2 (chat-id hardening). The P7B+3 label was misleading.
  2. **No operator contract for "delayed MEDIA that is recovered"**: a 03:00 deferral closed by 03:10 looks like a NOTIFY_FAIL at first glance (the 03:00 line in the cron log says `error_kind=transport`, which is alarming). Without an explicit classification, an operator might misread a *closed deferral* as a *data failure* and waste time debugging.
- **Fix**: `scripts/replay_pending_media.py` line 172 — title string changed from `"↻ Artvee Gallery P7B+3 deferred MEDIA replay\n"` to `"↻ Artvee Daily Health MEDIA replay\n"`. **No behavior change** — the staged report contents, the pending-file schema, the staged-only MEDIA allowlist, the `pending=0` silent-no-op, and the optional 03:10 cron install are all unchanged. The phase tag is now neutralized so it stays accurate regardless of which later phase is active.
- **Documentation**: formalized the recovered-WARN classification in three docs:
  - `docs/MEDIA_REPLAY.md`: P8D+3 neutralized-title + recovered-WARN contract sections.
  - `docs/DAILY_OPERATING_PLAYBOOK.md` § 9.10: new "Classifying next-day notification outcomes" section with a 4-row classification table (`notify_config_fail` / `media_transport_deferred` / `media_transport_deferred + 03:10 OK` / `media_transport_deferred + 03:10 failed`) and explicit `WARN_RECOVERED` vs `NOT_RECOVERED` verdicts.
  - `docs/POST_STABLE_OPERATIONS.md` § 6.1: P8D+3 note documenting the title change and the recovered-WARN contract.
- **Verification (2026-07-01 next-day)**:
  - 03:00 text: arrived (message_id=**27647**), `telegram.fallback.reason=media_transport_deferred`.
  - 03:10 replay cron: ran, `transport_status=ok`, `transport_latency_ms=54`, `outcome=replayed_pending`, `pending_before=4`, replayed=2 (2026-06-30 + 2026-07-01), quarantined=2 (both legacy max-retries).
  - 03:10 Telegram: arrived (message_ids **27649** + **27650**) with the *old* title (because the change is not yet deployed; tomorrow's 03:10 tick will use the neutralized title).
  - Cron-like dry-run (`env -i HOME=... PATH=$HOME/.local/bin:... ARTVEE_TELEGRAM_ENV_FILE=... bash -lc '... && bash scripts/artvee_media_replay_cron.sh --dry-run --limit 5 --max-retries 3'`): exit 0, transport=ok, summary JSON written, **no Telegram**.
  - `bash -n scripts/artvee_media_replay_cron.sh` PASS; `python3 -m py_compile scripts/replay_pending_media.py` PASS; `check_open_source_ready.py` PASS; `check_gallery_integrity.py` PASS (records=875, retired=4, blocking=0, pending=0, transport=ok); `artvee_ops_status.sh --no-telegram` PASS (`action=candidate_ready_manual_publish_optional`).
- **Separate finding (not fixed by P8D+3)**: the 2026-07-01 01:30 refill + 02:00 batch wrappers logged `NOTIFY_FAIL: OpenClaw binary missing`. This is a **new** PATH regression that survived P8D+1's installer fix (the daily-health 03:00 line still works because P7B had inline `export PATH=$HOME/.local/bin:$PATH` in the command). Tracked as a P8D+4 follow-up — fix is to extend the P8D+1 unified installer's PATH export to cover all four cron lines (refill / batch / confirm / daily-health) and to extend the `artvee_nightly_wrapper.sh` PATH resolution the same way. Out of scope for P8D+3 (which is a verification + cleanup phase, not a fix phase).
- **Safety**: no download / refill / batch / `--approve` / Pages push / retired retry / MEDIA allowlist widen; no tokens / chat_ids / secrets printed; replay behavior, staged-only MEDIA, `pending=0` silent-no-op, optional 03:10 install workflow — all unchanged. The 2026-07-01 01:30 / 02:00 NOTIFY_FAIL does not affect the recovery story for the *MEDIA* path because the 03:00 daily health cron uses its own PATH-prefixed command (per P7B) and the 03:10 replay cron uses the P8D+1 installer's explicit `PATH=$HOME/.local/bin:...` cron env var.
- **Files changed**: `scripts/replay_pending_media.py` (title string only — line 172), `docs/MEDIA_REPLAY.md` (neutralized title + recovered-WARN contract), `docs/DAILY_OPERATING_PLAYBOOK.md` (§ 9.10 classification table + dated header), `docs/POST_STABLE_OPERATIONS.md` (§ 6.1 P8D+3 note), `docs/PROJECT_STATUS.md` (P8D+3 row + snapshot), `docs/ROADMAP.md` (P8D+3 entry + Next refresh), `docs/RETROSPECTIVE.md` (§ 2.25 lesson).
- See `<workspace>/reports/artvee-gallery-p8d3-media-replay-verification-cleanup-20260701.md`.

### P8D+4 · Media replay queue normalization + delivery truthfulness ✅ PASS (2026-07-03 06:40)
- **Bugs found** (5 root causes, all fixed simultaneously):
  - **Bug A — infinite nesting**: `_archive_dir` built archive path by `pending_path.parent / name`; a file already in `replayed/` produced `replayed/replayed/` on the next run. After 5 days: `quarantine/quarantine/quarantine/...` 6 levels deep — would have hit `PATH_MAX=4096` within weeks.
  - **Bug B — false success**: `replay_one()` recorded `outcome=replayed` on OpenClaw exit 0 regardless of `message_id`. On 2026-07-03 the replay exited 0 but Telegram send was silently dropped; `outcome=replayed_pending` was recorded anyway.
  - **Bug C — wrong cron outcome**: `artvee_media_replay_cron.sh` unconditionally set `OUTCOME=replayed_pending` after every non-dry-run run, ignoring actual aggregate results.
  - **Bug D — aggregate JSON never written**: `replay_pending_media.py` only wrote per-pending `.replay-result-*.json` sidecars; the cron looked for a `results` list that was never produced, so `replay_message_ids` was always empty.
  - **Bug E — notifier regex mismatch**: `_extract_message_id` only matched `Message ID:` / `message_id=`; OpenClaw journal emits `messageId=29012` (camelCase) — a format it never matched.
- **Fixes applied**:
  - `_archive_dir`: always anchors to `reports/runtime/media-replay/{replayed,quarantine,results}/` stable roots; test-only temp roots fall through to `root/<name>`.
  - `_pending_paths`: skips files under `media-replay/replayed/`, `media-replay/quarantine/`, and `queue-fix-backup-*` directories.
  - `replay_one()`: `delivered = result.get('ok') and result.get('message_id')`; exit 0 without `message_id` → `send_failed_will_retry` with `last_error = "openclaw exit 0 but no message_id parsed from log (treated as undelivered)"`.
  - `main()`: writes aggregate `.replay-results-<date>.json` to `media-replay/results/` with full `results` list + pre-computed `message_ids` array; empty queue also writes aggregate.
  - `artvee_media_replay_cron.sh`: reads aggregate JSON; outcome branches: `replay_no_results` / `replayed_delivered` / `quarantine_exhausted` / `replay_failed` / `noop_zero_pending` / `skipped_transport_unavailable` / `dry_run_completed`.
  - `artvee_telegram_notify._extract_message_id`: added regexes for `messageId=` and `MessageId=` (OpenClaw journal camelCase format).
- **Normalization (one-time, 2026-07-03)**: 20 pre-fix files (4 pending + 16 result sidecars) moved to stable roots. Classification: delivered (message_id 25084/27996/29012) → `replayed/`; quarantine test → `quarantine/`; originals backed up to `reports/runtime/media-replay/queue-fix-backup-20260703-062946/` (20 files, 152K) — nothing deleted.
- **Verification**: dry-run PASS (pending=0, aggregate written to `media-replay/results/.replay-results-2026-07-03.json`, `outcome=dry_run_completed`, `replay_delivered=0`); open_source_ready PASS; gallery integrity strict PASS (rows 1291/1173/1169/1169); ops status `pending_media=0 transport=ok`.
- **Safety**: no download / refill / batch / `--approve` / Pages push; no tokens / chat_ids / secrets printed; delivered definition enforced as non-empty `message_id`; replayed/quarantine roots are fixed and cannot be nested.
- **Files changed**: `scripts/replay_pending_media.py`, `scripts/artvee_media_replay_cron.sh`, `scripts/artvee_telegram_notify.py`, `docs/MEDIA_REPLAY.md`, `docs/DAILY_OPERATING_PLAYBOOK.md`, `docs/POST_STABLE_OPERATIONS.md`, `docs/PROJECT_STATUS.md`, `docs/ROADMAP.md`, `docs/RETROSPECTIVE.md`.
- See `<workspace>/reports/artvee-gallery-p8d4-media-replay-queue-fix-20260703.md`.

### P8D+4B · Media replay queue scope cleanup ✅ PASS (2026-07-04 06:39)
- **Bug found** (one root cause, two defensive layers added simultaneously):
  - **Bug F — wrong scan root in cron**: `artvee_media_replay_cron.sh` passed `reports/` to `_scan_pending_media` (the pre-P8D+4B layout). The scan then did `rel.startswith("replayed/")` against a relative path that started with `runtime/media-replay/...`, so the startswith check *always* returned False and every terminal / backup `.fallback-pending-*.json` was counted as pending. **Symptom**: on 2026-07-04 a clean day still reported `pending_before=8` even though `artvee_ops_status` (using the internal `daily-health/` call) correctly reported `pending_media=0`.
- **Fixes applied**:
  - `scripts/artvee_media_replay_cron.sh`: passes `reports/runtime/` (the canonical runtime root) to `_scan_pending_media` so the scan path is identical to the daily-health internal call; reads a second scan that returns the full bucket breakdown as JSON, parses it into a `PENDING_SCAN_JSON` env var, and writes the per-bucket counts into `cron-<date>.json` (`active_pending`, `active_replayable`, `terminal_replayed`, `terminal_quarantine`, `ignored_results`, `ignored_backup`, `nested_legacy`, `unknown_non_active`, `scan_error`). Renames the cron `outcome` from `noop_zero_pending` → `no_pending` so a future regression in the scanner shows up as an explicit bucket mismatch instead of a silent zero.
  - `scripts/artvee_daily_health_check.py` (`_scan_pending_media`): rewritten to *classify every path first, then count*. New helper `_classify_pending_path` recognizes `active_pending` (under `media-replay/pending/` or top-level `daily-health/`), `terminal_replayed` (under `media-replay/replayed/` or `daily-health/replayed/`), `terminal_quarantine` (under `media-replay/quarantine/` or `daily-health/quarantine/`), `results` (under `media-replay/results/`), `backup_or_legacy` (any segment contains `queue-fix-backup-`, `legacy-cleaned`, or `stable_dup`), `legacy_nested` (self-recursive `replayed/replayed` / `quarantine/quarantine` pathology), or `unknown`. Only `active_pending` increments the alarm threshold. The function also tries to climb to a `runtime/` root if the caller passed bare `reports/`, so it remains defensive against the legacy call shape.
  - `scripts/replay_pending_media.py`: `_pending_paths` reuses `_classify_pending_path` (no drift between scanner and replay); new `_non_active_scope` helper prints the full bucket layout in dry-run so a future regression in the classification shows up immediately in the dry-run log instead of silently flipping `pending_before` to zero.
- **Migration (one-time, 2026-07-04)**:
  - Backup: 44 files (`.fallback-pending-*.json`, `.replay-result-*.json`, `.replay-results-*.json`, `.quarantine-*.json`, `.media-replay.lock`) copied to `reports/runtime/media-replay/queue-scope-cleanup-backup-20260704-063618/` (with `--parents` to keep relative paths) before any move — nothing deleted.
  - Archive: `reports/runtime/media-replay/queue-fix-backup-20260703-062946/stable_dup/` (4 orphan pendings from the P8D+4 normalization) and `reports/runtime/daily-health/{replayed,quarantine}/` (the pre-P8D+4 nested pathology trees) moved to `reports/runtime/media-replay/legacy-cleaned/20260704/{queue-fix-backup-20260703-062946/stable_dup, daily-health/{replayed,quarantine}}`.
- **Verification**: dry-run cron wrapper exit 0 in 1s; `cron-2026-07-04.json` summary `outcome=no_pending`, `pending_before=0`, `active_pending=0`, `terminal_replayed=6` (3 live + 3 in backup), `terminal_quarantine=2` (1 live + 1 in backup), `ignored_backup=8`, `nested_legacy=0`, `unknown_non_active=0`, `transport_status=ok`, `transport_latency_ms=54`, `dry_run=true`. open_source_ready PASS (4/4); gallery integrity strict PASS (1190 unique URL rows / 1186 index rows / 1186 web rows, 0 dupe groups); ops status `records=875 retired=4 blocking=0 integrity=PASS readiness=PASS pending_media=0 transport=ok action=candidate_ready_manual_publish_optional`. Active nested paths = 0 (everything is now under `legacy-cleaned/`).
- **Safety**: no download / refill / batch / `--approve` / Pages push; no tokens / chat_ids / secrets printed; replay behavior, staged-only MEDIA allowlist, `pending=0` silent-no-op, optional 03:10 install workflow, and the stable `media-replay/{replayed,quarantine,results}/` archive roots — all unchanged. Nothing in `legacy-cleaned/` or `queue-scope-cleanup-backup-*/` is tracked by git (both live under `.gitignore`'d `reports/runtime/`).
- **Files changed**: `scripts/artvee_media_replay_cron.sh`, `scripts/artvee_daily_health_check.py`, `scripts/replay_pending_media.py`, `docs/MEDIA_REPLAY.md`, `docs/DAILY_OPERATING_PLAYBOOK.md`, `docs/POST_STABLE_OPERATIONS.md`, `docs/PROJECT_STATUS.md`, `docs/ROADMAP.md`, `docs/RETROSPECTIVE.md`.
- See `<workspace>/reports/artvee-gallery-p8d4b-media-replay-queue-scope-cleanup-20260704.md`.

### Next (post-P8D+4B, v0.2.x polish)
- **v0.2.1 patch release** — bundle P7B+1 / P7B+2 / P7B+3 / P8A / P8A+1 / P8B / P8C / P8D / P8D+1 / P8D+2 / P8D+3 / P8D+4 / P8D+4B into a single patch release after 7 days of clean observation. No release has been cut from the current `main`.
- **P8E** public search/filter polish — extend the P8C filters with cross-archive full-text search (typed in the search box) and a per-pick lightbox when a card thumbnail is clicked. Defers until the rolling history has at least 14 days so search has enough signal.
- **Morning briefing cron (06:00)** — simple wrapper around `artvee_ops_status.sh --date $(date +%F) --media` if the operator wants a daily morning report. Explicitly out of scope for v0.2.x.

### P8D+2 · Telegram notifier chat-id configuration hardening ✅ PASS (2026-06-30 07:03)
- **Problem**: 2026-06-30 03:00 daily health cron and 01:30/02:00 refill/batch wrappers all logged `NOTIFY_FAIL` / `NOTIFY_ERROR: Telegram chat id not found`. The P8D+1 fix had corrected PATH and CRON_TZ, but the notifier still could not resolve the chat id in the cron environment.
- **Root cause**: `artvee_telegram_notify.py` resolution order was: `--chat-id` > `ARTVEE_TELEGRAM_CHAT_ID` env > `$HOME/.openclaw/openclaw.json` `defaultChatId` > `targets[0]`. The OpenClaw config had `telegram.enabled=true` and `botToken` but **no `defaultChatId` or `targets`**. The cron environment did not have `ARTVEE_TELEGRAM_CHAT_ID` set. So every cron-run notifier call raised `RuntimeError: Telegram chat id not found`.
- **Fix**: Added a new resolution step: **private env file** (`$HOME/.config/artvee-gallery/telegram.env`). New order:
  1. `--chat-id` CLI arg
  2. `ARTVEE_TELEGRAM_CHAT_ID` env var
  3. `$HOME/.config/artvee-gallery/telegram.env` (private, chmod 600, not in git)
  4. `$HOME/.openclaw/openclaw.json` `channels.telegram.defaultChatId`
  5. `$HOME/.openclaw/openclaw.json` `channels.telegram.targets[0]`
  6. Hard error with clear instructions
- **Private env file**: `$HOME/.config/artvee-gallery/telegram.env` created with `ARTVEE_TELEGRAM_CHAT_ID=<id>`; `chmod 600`; never committed to git. The file is read by the notifier at runtime; the actual chat id is never baked into cron lines or tracked files.
- **Cron installer updates**:
  - `scripts/install_artvee_cron.sh` (P8D+1 unified installer): now emits `ARTVEE_TELEGRAM_ENV_FILE=$HOME/.config/artvee-gallery/telegram.env` as a cron env var above the schedule lines. The actual chat id is NOT in the crontab.
  - `scripts/install_daily_health_cron.sh`: same fix — exports `ARTVEE_TELEGRAM_ENV_FILE` instead of baking `ARTVEE_TELEGRAM_CHAT_ID` into the command line.
- **Notifier enhancements**:
  - `artvee_telegram_notify.py`: new `_load_chat_id_from_env_file()` helper; new `_check_config()` diagnostic (safe to print, no secrets exposed); new `--check-config` CLI flag that prints a JSON diagnostic and exits 0/1.
- **Verification**:
  - `python3 scripts/artvee_telegram_notify.py --check-config` → `resolved: true`, `resolved_len: 10`, `env_file.exists: true`.
  - Cron-like env test (`env -i HOME=... PATH=... ARTVEE_TELEGRAM_ENV_FILE=...`) → `NOTIFY_OK pid=... message_id=27285`, exit 0.
  - Crontab inspection: no numeric secrets, no `ARTVEE_TELEGRAM_CHAT_ID` in cron lines, only `ARTVEE_TELEGRAM_ENV_FILE`.
- **Safety**: no download / refill / batch / `--approve` / Pages push / retired retry; no tokens / chat ids / secrets printed in logs or reports; private env file is repo-external and gitignored; cron lines contain only the env file path, not the chat id.
- **Files changed**: `scripts/artvee_telegram_notify.py` (env file resolution + `--check-config`), `scripts/install_artvee_cron.sh` (ARTVEE_TELEGRAM_ENV_FILE env var), `scripts/install_daily_health_cron.sh` (same), `docs/DAILY_OPERATING_PLAYBOOK.md` (§ 8 troubleshooting + § 9 cron-like verification), `docs/PROJECT_STATUS.md` (P8D+2 row), `docs/ROADMAP.md` (P8D+2 entry + Next).
- See `<workspace>/reports/artvee-gallery-p8d2-telegram-notifier-chatid-fix-20260630.md`.
