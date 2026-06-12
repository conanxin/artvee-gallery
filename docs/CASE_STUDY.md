# Artvee Gallery · Case Study

> How a one-off nightly downloader became a local-first, open-source,
> public-friendly visual archive in roughly one working day.

## 1. Project at a glance

- **Domain**: public-domain art archive (artvee.com)
- **Local archive size**: 760 artworks × 4 categories (Japanese prints,
  botanical, book illustrations, posters), 1.4 GB originals
- **Source**: `<project-root>/artvee-library/`
- **Public repo**: <https://github.com/conanxin/artvee-gallery>
- **License**: MIT (code) / public-domain (art)
- **Release**: `v0.1.0-alpha`
- **First public route**: <https://conanxin.github.io/projects/artvee-gallery-demo/>
- **Second public route**: <https://conanxin.github.io/projects/artvee-gallery-digest/>

## 2. The transformation arc

The project started as a "nightly downloader" — a single bash script
that pulled 20 new pieces from artvee.com, archived them, and called
it a day. That is the *natural* shape of a one-off data-collection
script: input is an API call, output is a folder. Useful, but
forgettable.

What changed it was a sequence of seven deliberate design decisions:

1. **Stop calling it "scraping", start calling it "a local archive"**.
   The shift in vocabulary made us treat the result as *data we own*
   rather than *data we happened to keep*. Owning data means
   indexing, curating, and revisiting it.
2. **Make the workflow deterministic**. The original script was
   "download whatever is new". The new builder picks 5 representative
   pieces per day using a round-robin across categories, so the daily
   digest is reproducible and explainable.
3. **Separate code from generated data**. `images/`, `metadata/`,
   `thumbs/`, `digests/`, `dist/`, `logs/`, `inbox/`, `web/data/*.json`
   are all derived. None of them belong in the source tree.
4. **Make the public surface a deliberate choice, not a side effect**.
   Don't just `rsync` the local folder to a server. Curate. Show 100
   pieces, not 760. Show 5 picks per day, not 100.
5. **Add a CI gate that knows the boundary**. The readiness check
   enforces "no generated data in tracked files, no private paths in
   body text, no 1 MB+ files". Future contributors cannot accidentally
   regress the open-source boundary.
6. **Treat the digest as a content system, not a log line**. One
   digest per day × the full archive = an actual publication. It
   deserves its own route on the public site.
7. **Capture the design reasons, not just the code**. The CI gate is
   the *implementation* of the boundary; the docs (`CASE_STUDY`,
   `RETROSPECTIVE`, `LOCAL_FIRST_AGENT_PROJECT_PATTERN`) are the
   *explanation* of the boundary. Both are necessary.

## 3. Key design decisions

### 3.1 Local-first, not cloud-first

Everything runs on one machine. The cloud is **only** for the
public-facing subset. The reasons:

- The local archive is the source of truth. Cloud storage would be a
  cache, and caches go stale.
- The nightly batch is bandwidth-cheap (20 works × 5 min), so we do
  not need distributed workers.
- The risk of leaking the local archive is reduced by definition
  (the public route only ever sees curated thumbnails).

### 3.2 Pure-stdlib, no new dependencies

Every script in `scripts/` imports only the Python standard library.
This is not Luddism; it is *boring on purpose*. We wanted the
nightly batch to run unattended on a cron schedule for months
without surprise dependency churn. Adding `requests` or `Pillow` or
`playwright` as a runtime dependency would have made the project
fragile to PyPI outages and version-pin drift.

The trade-off: we cannot use third-party libraries for HTML
parsing, image manipulation, or HTTP. In practice:

- The artvee downloader uses `urllib` and `html.parser` from stdlib.
- Thumbnail generation calls the system `convert` binary
  (ImageMagick), not Pillow. ImageMagick is the more battle-tested
  option for our use case (JPEG quality / size optimization).
- HTML rewriting is regex on a small known shape, not BeautifulSoup.

### 3.3 Data flow with explicit boundaries

```
[artvee.com]
   │ (nightly batch, 02:00 Asia/Shanghai)
   ▼
[images/]    [metadata/]              ◀── local archive (1.4 GB)
   │
   ▼ (build_artvee_gallery.py)
[thumbs/256/]   [thumbs/512/]         ◀── derived thumbnails
[web/data/artworks.json]
[web/data/gallery_stats.json]
   │
   ├──▶ [web/]                       ◀── local gallery UI
   │
   ├──▶ [scripts/export_artvee_gallery_public_demo.py]
   │     ▼
   │   [dist/artvee-gallery-public-demo/]   ◀── curated, 100 picks
   │     │
   │     ▼ (rsync to GitHub Pages)
   │   [https://conanxin.github.io/projects/artvee-gallery-demo/]
   │
   ├──▶ [scripts/build_artvee_daily_digest.py]
   │     ▼
   │   [digests/artvee-digest-YYYY-MM-DD.{md,html}]
   │   [web/data/digests.json]
   │     │
   │     ▼
   │   [scripts/export_artvee_digest_public_page.py]
   │     ▼
   │   [dist/artvee-gallery-digest-public/] ◀── 5 picks, 324 KB
   │     │
   │     ▼ (rsync to GitHub Pages)
   │   [https://conanxin.github.io/projects/artvee-gallery-digest/]
   │
   └──▶ [scripts/artvee_telegram_notify.py]  ◀── optional summary post
```

The boundary is **physical**: the only artefacts that ever leave the
machine are `dist/` directories and a Telegram message. There is no
direct path from `images/` to the public web.

### 3.4 The 4-rule CI gate

`scripts/check_open_source_ready.py` enforces four rules. Each rule
maps to a specific failure mode we wanted to prevent:

1. **generated-data check** — no real file under `images/`, `metadata/`,
   `thumbs/`, `dist/`, `digests/`, `logs/`, `inbox/`, or
   `web/data/*.json` may be tracked. (`.gitkeep` placeholders are OK.)
2. **path-leak check** — no tracked text file may contain any of the
   project-specific private-path patterns (e.g. user home, tilde
   expansion, or the local agent project directory). Body docs may
   mention forbidden patterns in *descriptive* context (e.g. the
   readiness script itself lists what to look for); commit-time
   grep is intentionally restricted to tracked text outside the
   readiness script.
3. **secret-keyword check** — no `token` / `secret` / `password`
   strings in tracked files (modulo the readiness script's own
   documentation of what it checks for).
4. **file-size check** — no single tracked file may exceed 1 MB.
   This forces screenshots to be viewport-bounded and binaries to
   stay out of the repo.

The gate is a `py_compile` + `bash -n` + readiness + JSON-shape check
in CI. It runs on every push. The first run failed because we
shipped the CI workflow before shipping the full code tree; the fix
was a one-commit follow-up. This is exactly the kind of regression
the gate is designed to catch.

### 3.5 Two public routes, not one

Most projects ship one demo. We shipped two:

- **Gallery demo** (curated 100 picks) — for casual browsing.
- **Daily digest** (5 picks per day) — for a daily visit ritual.

The two routes serve different reading modes. The gallery is
"browse a representative slice"; the digest is "give me five
artworks that represent the collection today, and let me come back
tomorrow". They share the same source data but emit different
shapes. The decision to ship both was driven by the observation
that an archive you visit once is an archive you forget.

## 4. What we shipped

### 4.1 Public surface

| Route | Source | Bundle | Updated |
| --- | --- | --- | --- |
| <https://github.com/conanxin/artvee-gallery> | repo | — | per-push |
| <https://github.com/conanxin/artvee-gallery/releases/tag/v0.1.0-alpha> | tag | — | once |
| <https://conanxin.github.io/projects/artvee-gallery-demo/> | `dist/artvee-gallery-public-demo/` | 5.7 MB | per-publish |
| <https://conanxin.github.io/projects/artvee-gallery-digest/> | `dist/artvee-gallery-digest-public/` | 324 KB | per-publish |
| <https://github.com/conanxin/conanxin.github.io> | Pages repo | — | per-publish |

### 4.2 Code surface

- 12 scripts in `scripts/` (all pure stdlib)
- 1 shell wrapper (`artvee_nightly_wrapper.sh`) for nightly orchestration
- 1 GitHub Actions workflow (`.github/workflows/open-source-ready.yml`)
- 1 readiness check (`check_open_source_ready.py`)
- 13 docs in `docs/`
- 3 sample data files in `examples/`
- 1 LICENSE (MIT)
- 1 README

Total tracked: 41 files at the end of P3F (was 37 at end of P3D; +4 docs
+ README/ROADMAP/PROJECT_STATUS updates).

## 5. What we'd do differently

A few things we noticed in retrospect that future iterations should
fix:

- **Manifest vs disk: 760 vs 747** *(resolved in P4A, gated in
  P4A+1, fully fixed in P4B)*. The 13-row gap turned out to be
  **filename collisions**: the build script derived local
  filenames from human-readable title strings, so distinct
  artvee URLs with the same parsed title silently overwrote
  each other. 11 source images were lost; 13 index/web records
  displayed a sibling's image with their own metadata. P4A
  documented the exact 11/13 fingerprint; P4A+1 froze it as a
  CI gate. P4B (2026-06-12) healed the underlying bug:
  filenames are now derived from a source-url hash via
  `scripts/artvee_identity.py`, 11 winners were renamed to
  stable ids, 9 of the 13 losers re-downloaded via playwright,
  and 4 unresolvable losers dropped from the index/web. The
  fingerprint is now empty and all three integrity check modes
  exit 0.
- **Path-leak rule is fuzzy in the docs**. The grep currently
  tolerates a small number of "descriptive" mentions in body docs,
  but the tolerance is implicit. Future work: make the rule explicit
  in the readiness script (e.g. "string-literal matches inside
  `scripts/check_open_source_ready.py` itself are exempt").
- **Public demo is not auto-updated**. Both public routes are
  published via manual `rsync + commit + push`. Acceptable for now;
  automation requires secret-rotation policy first.

## 6. The shape of the project after P3

In one line: **a 760-piece local visual archive, with a public
demo, a daily digest, an MIT-licensed code tree, a CI gate, and a
Telegram-friendly nightly summary — all running unattended on cron
and a single 5-minute batch.**

The most important number is not 760. It is **the gap between the
local archive (1.4 GB, 747 files on disk) and the public bundle
(5.7 MB gallery + 324 KB digest)**. That gap is the design. It is
what makes the project shareable without making it exposed.

## 7. See also

- [RETROSPECTIVE.md](RETROSPECTIVE.md) — phase-by-phase lessons
- [LOCAL_FIRST_AGENT_PROJECT_PATTERN.md](LOCAL_FIRST_AGENT_PROJECT_PATTERN.md) —
  the reusable methodology
- [ROADMAP.md](ROADMAP.md) — completed phases and what's next
- [PROJECT_STATUS.md](PROJECT_STATUS.md) — phase markers
- [ARCHITECTURE.md](ARCHITECTURE.md) — technical deep-dive
