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
  cron, completes in ~5 minutes, posts a Telegram summary.
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

## 2. Up next

### P4A · Manifest duplicate-id audit (read-only)
- Manifest records 760 entries; disk has 747 files. The 13
  missing entries are likely duplicates under different IDs.
- Read-only audit: join the manifest against the disk and
  report the delta. No new dependencies; no new infrastructure.
- A 1-day scoped phase; output is a Markdown report.

### P4B · Automatic public demo refresh
- Both public routes are published via manual
  `rsync + commit + push`. Acceptable for now.
- Automation requires a personal access token in cron or a
  GitHub Actions workflow on the Pages repo, both of which
  require a secret-rotation policy first.

### P4C · Digest history index page
- The public digest route currently shows only the latest day.
- A 30-day rolling index would turn the digest into a
  *publication* rather than a daily log.

### P4D · Object storage planning
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
