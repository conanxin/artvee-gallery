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
  — manual review workflow (de-dupe / keep-both) is a future phase
- **Digest history sliding window** (P4F · 30-day rolling index) — not
  yet built; current `digests.json` keeps all history but the public
  page renders only `latest`
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
