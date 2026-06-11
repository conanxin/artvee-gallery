# Artvee Gallery · Architecture

> Status: living document. Updated as phases land.
> Scope: end-to-end data flow, script responsibilities, and the
> generated-vs-tracked file boundary.

## 1. Data Flow (high level)

```
           (artvee.com — public-domain works)
                       │
                       ▼
        ┌──────────────────────────────┐
        │  seed scraping + candidate   │
        │  expansion (offline)         │
        └──────────────────────────────┘
                       │ inbox/manifest.csv
                       ▼
        ┌──────────────────────────────┐
        │  refill_artvee_pending.py    │  (cron @ 01:30, optional)
        │  → bump pending pool         │
        └──────────────────────────────┘
                       │ more pending rows
                       ▼
        ┌──────────────────────────────┐
        │  run_artvee_nightly_batch.py │  (cron @ 02:00)
        │  → download + parse + index  │
        │  → manifest + index/         │
        │  → images/, metadata/        │
        └──────────────────────────────┘
                       │ (read-only)
                       ▼
        ┌──────────────────────────────┐
        │  build_artvee_gallery.py     │  (post-batch, lightweight)
        │  → thumbs/{256,512}          │
        │  → web/data/artworks.json    │
        │  → web/data/gallery_stats    │
        └──────────────────────────────┘
                       │
            ┌──────────┴──────────┐
            ▼                     ▼
   ┌──────────────────┐   ┌──────────────────────────┐
   │  local web UI    │   │ export_artvee_gallery_   │
   │  (web/*.html,js) │   │   public_demo.py         │
   │  served by any   │   │  → dist/artvee-gallery-  │
   │  static server   │   │    public-demo/          │
   └──────────────────┘   └──────────────────────────┘
                                   │ (deployable)
                                   ▼
                         (any static host /
                          GitHub Pages / S3 / etc.)

   (parallel)

        ┌──────────────────────────────────────┐
        │ build_artvee_daily_digest.py         │  (post-gallery)
        │  → digests/artvee-digest-*.md        │
        │  → digests/artvee-digest-*.html      │
        │  → web/data/digests.json (index)     │
        └──────────────────────────────────────┘
                       │
                       ▼
        ┌──────────────────────────────────────┐
        │ artvee_telegram_notify.py            │  (optional, post-everything)
        │  → Telegram summary, Chinese keywords│
        │    "统计 / 图库 / 灵感"               │
        └──────────────────────────────────────┘
```

The wrapper (`scripts/artvee_nightly_wrapper.sh batch`) is the only
entry point a cron job should call. It orchestrates the **batch →
gallery rebuild → digest build → Telegram notify** chain.

## 2. Script Responsibilities

### `scripts/scrape_artvee_seeds.py`

- Reads artvee.com category index pages and emits seed URLs.
- **Side effects:** writes to `inbox/candidate_sources.csv` (gitignored).
- **Network:** yes (initial seed only).

### `scripts/add_artvee_candidates.py`

- Expands a list of source URLs into concrete `inbox/manifest.csv` rows.
- **Side effects:** writes to `inbox/manifest.csv` (gitignored).

### `scripts/refill_artvee_pending.py`

- Adjusts pending quota per category in `inbox/manifest.csv`.
- **Side effects:** mutates `inbox/manifest.csv` (gitignored).
- **Mode:** dry-run by default; `--execute` to apply.

### `scripts/run_artvee_nightly_batch.py`

- Walks `pending` rows in the manifest, downloads the original asset,
  parses the page for provenance, writes image + metadata + index
  updates.
- **Side effects:** writes to `images/`, `metadata/`, `index/`,
  updates `inbox/manifest.csv` (all gitignored).
- **Network:** yes (the main download loop).

### `scripts/build_artvee_gallery.py`

- Reads `index/artworks.csv` + `metadata/*.json` + `images/`.
- **Side effects:** writes `thumbs/256/*.jpg`, `thumbs/512/*.jpg`,
  `web/data/artworks.json`, `web/data/gallery_stats.json`
  (all gitignored).
- **Network:** none.
- **Idempotent:** existing thumbnails are skipped; only missing ones
  are generated.

### `scripts/export_artvee_gallery_public_demo.py`

- Reads P1 outputs (`web/data/*.json`, `thumbs/`).
- **Side effects:** writes to `dist/artvee-gallery-public-demo/`
  (gitignored).
- **Path rewriting:** local `../images/...` → `./assets/thumbs/...`.
- **No original images copied** — only thumbnails + metadata.

### `scripts/build_artvee_daily_digest.py`

- Reads P1 outputs + `logs/nightly_summary.csv`.
- **Side effects:** writes to `digests/artvee-digest-*.md`,
  `digests/artvee-digest-*.html`, updates `web/data/digests.json`
  (all gitignored).
- **Public-safe by construction:** defensive string check on every
  output path to ensure no absolute home path, user-home shorthand,
  or workspace-name substring
  substring.

### `scripts/artvee_nightly_wrapper.sh`

- Orchestrator. Supports three modes: `refill | batch | test`.
- Derives `BASE_DIR` from its own location (path-agnostic).
- Chains batch → gallery rebuild → digest build → Telegram notify.
- **Network:** indirectly, via the underlying scripts.
- **Logs:** writes to `logs/wrapper_runs/wrapper_<type>_<ts>.log`.

### `scripts/artvee_telegram_notify.py`

- Sends a single text message to Telegram via the OpenClaw Gateway
  CLI as a bridge. The actual send is fire-and-forget (background)
  so the wrapper never blocks on the upstream CLI startup cost.
- **Network:** only at the OpenClaw CLI level; the notifier itself
  is a thin wrapper.

### `scripts/check_open_source_ready.py`

- Read-only repo safety check (see
  [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)).
- **Side effects:** none.

## 3. Generated vs Tracked Boundary

| Path | Producer | Tracked? | Why |
| --- | --- | --- | --- |
| `images/` | nightly batch | ❌ | Source archive; large, machine-specific, public-domain works (not our copyright) |
| `metadata/` | nightly batch | ❌ | Derived from artvee.com pages; per-artwork detail |
| `previews/` | (legacy) | ❌ | Older preview thumbnails; superseded by `thumbs/` |
| `thumbs/256/`, `thumbs/512/` | gallery builder | ❌ | Regenerable; per-image; can be 100k+ files |
| `web/data/*.json` | gallery / digest | ❌ | Regenerable; large; contains per-run data |
| `dist/` | public demo exporter | ❌ | Regenerable; deployable bundle |
| `digests/` | digest builder | ❌ | Regenerable; per-day artefacts |
| `inbox/` | seed/candidate flows | ❌ | Local-only staging |
| `index/` | batch script | ❌ | Per-machine local index |
| `logs/` | wrapper | ❌ | Runtime logs; never useful to other users |
| `backups/`, `*.bak` | ad-hoc | ❌ | Local backups |
| `web/index.html`, `app.js`, `style.css` | (UI shell) | ✅ | Static local UI shell |
| `scripts/*.py`, `*.sh` | (source code) | ✅ | The actual product |
| `docs/*.md` | (documentation) | ✅ | Reference for users and contributors |
| `examples/*.json` | (synthetic samples) | ✅ | Tiny, no real paths; reference shapes |
| `.gitignore`, `LICENSE`, `README.md` | (project meta) | ✅ | Project-level |
| `dist/.gitkeep`, `digests/.gitkeep`, `thumbs/*/.gitkeep`, `web/data/.gitkeep` | (placeholders) | ✅ | Keep empty directories in git |

## 4. Nightly Wrapper — Post-Batch Flow

```
02:00 cron
    │
    ▼
artvee_nightly_wrapper.sh batch
    │
    ├─ 01: count images / metadata / dir size   (BEFORE)
    │
    ├─ 02: run_artvee_nightly_batch.py --limit 20
    │     └─ 20 SUCCESS / 0 FAILED (typical)
    │
    ├─ 03: count images / metadata / dir size   (AFTER)
    │     └─ NEW = AFTER - BEFORE
    │
    ├─ 04: parse stats: downloaded=… failed=… pending=… skipped=…
    │     └─ extract network errors / FAILED markers
    │
    ├─ 05: build_artvee_gallery.py --mode local
    │     └─ 解析 "图库: updated, records=N, thumbs +X/+Y"
    │
    ├─ 06: build_artvee_daily_digest.py --strategy diverse --select 5
    │     └─ 解析 "灵感: digest generated, selected=N, path=…"
    │
    ├─ 07: build Telegram message
    │     └─ 关键字：统计 / 图库 / 灵感
    │     └─ send via artvee_telegram_notify.py (background)
    │
    └─ 08: exit 0
```

The wrapper deliberately wraps each post-batch step in `|| true` and
isolates the failure modes: a gallery build failure never aborts the
main batch, and a digest build failure never aborts the gallery
update. The Telegram message then reflects the actual status of each
stage, so the operator can spot regressions at a glance.

## 5. Public Demo (deployable) Flow

```
web/data/*.json + thumbs/{256,512}/*.jpg
            │
            ▼
export_artvee_gallery_public_demo.py
            │  --limit N --strategy {recent|diverse} --out-dir dist/
            ▼
dist/artvee-gallery-public-demo/
    ├── index.html           (gallery UI, paths rewritten)
    ├── assets/thumbs/...    (256/512 thumbnails only)
    ├── data/artworks.json   (curated subset)
    └── data/gallery_stats.json
```

The public demo deliberately **omits**:

- `images/` (the original assets)
- `metadata/*.json` (full per-artwork detail)
- `inbox/`, `index/`, `logs/` (private staging)
- Any absolute home path, user-home shorthand, or workspace-name substring (defensive)

## 6. Open-Source Boundary

See [docs/OPEN_SOURCE_BOUNDARIES.md](docs/OPEN_SOURCE_BOUNDARIES.md)
for the full breakdown of what is and is not in the repository.
