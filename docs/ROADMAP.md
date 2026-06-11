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
**Status:** ✅ PASS (this release)
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

## 2. Near-term (P3D, P3E)

### P3D · Standalone Public GitHub Repository
- Initialise a fresh public repository (separate from any private
  parent).
- Push only the open-source surface area: `README.md`, `LICENSE`,
  `docs/`, `examples/`, `scripts/`, `web/` (UI shell), `.gitignore`.
- Configure branch protection, issue templates, and a CI smoke job
  that runs `check_open_source_ready.py` on every PR.

### P3E · Public Daily-Digest Page
- Extend the existing public demo URL with a second route that
  renders the latest daily digest (and a small archive).
- Same privacy guarantees as the public demo: no local paths, no
  full asset payloads.

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
