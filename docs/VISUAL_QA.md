# Visual QA

## 1. Purpose

This document defines the visual quality assurance process for the
Artvee Gallery. After data correctness (Phase P5A) and orphan cleanup
(P5C), the next dimension is **visual quality** of the curated
artworks. The visual QA analyzer checks image health, perceptual
diversity, metadata completeness, and digest pick quality.

The visual QA does not modify the source gallery. It is read-only
analysis, designed to surface curation rules for future
exporters / digest builders.

## 2. What P5D checks

The script `scripts/analyze_gallery_visual_quality.py` examines each
artwork record (or a sample) and produces per-record metrics:

### 2.1 File-system checks
- `image_path` / `metadata_path` / `thumb_256` / `thumb_512` presence
- Image file exists & size
- 256-thumb exists & size (≥ 1 KB)
- 512-thumb exists & size (≥ 3 KB)
- Original image size (≥ 5 KB)

### 2.2 Metadata checks
- `source_url` present
- `category` present
- `artist` present
- `title` present

### 2.3 Pillow-based visual checks
When Pillow is available (it is, in our environment):
- Image opens without errors
- Image dimensions (width × height)
- Image mode (RGB / L / etc.)
- Average brightness (0.0–1.0)
- Color entropy (Shannon, 0–8 bits)
- Perceptual aHash (8×8 → 64 bits) for near-duplicate grouping
- Detection of blank/white/black/near-monochrome risks

When Pillow is **unavailable**, the analyzer falls back to
file-size / path / extension / metadata-only checks and reports
`pillow_available=false`.

### 2.4 Risk classification

| Risk level | Triggers |
| --- | --- |
| `none` | All checks pass |
| `low` | Minor metadata gaps (missing artist/title/category) |
| `medium` | Notable issues (tiny files, near-monochrome, extreme aspect, missing source_url) |
| `high` | Serious issues (corrupt image, missing image/thumb file, blank/black/white risk) |

### 2.5 Suggested action
- `keep` — fits in public demo + digest
- `review` — needs manual review
- `exclude_from_public_demo` — not for public
- `exclude_from_digest` — not for digest

## 3. Quality risk levels

| Marker | Risk | Action |
| --- | --- | --- |
| `corrupt_or_unreadable_image` | high | `exclude_from_public_demo` |
| `image_file_missing` | high | `exclude_from_public_demo` |
| `thumb_256_file_missing` | high | `exclude_from_public_demo` |
| `thumb_512_file_missing` | high | `exclude_from_public_demo` |
| `blank_or_white_risk` (avg_brightness > 0.95) | high | `exclude_from_public_demo` |
| `blank_or_black_risk` (avg_brightness < 0.05) | high | `exclude_from_public_demo` |
| `near_monochrome` (entropy < 2.0) | medium | `review` |
| `extreme_aspect_ratio` (> 4:1) | medium | `review` |
| `tiny_image_file` (< 5 KB) | medium | `review` |
| `tiny_thumb_256` (< 1 KB) | medium | `review` |
| `tiny_thumb_512` (< 3 KB) | medium | `review` |
| `source_url_missing` | medium | `review` |
| `category_missing` | low | `keep` (but flag) |
| `artist_missing` | low | `keep` (but flag) |
| `title_missing` | low | `keep` (but flag) |

## 4. Public demo selection rules

The public demo exporter (`build_artvee_gallery.py --strategy diverse`)
already filters out:
- `Le_rêve` records (label-bug guard, P5A fix)
- Records with `source_url` in known timeout set
- Records with duplicate `source_url` within the gallery

**Recommended new rules for the exporter (P5E):**
1. Exclude records with `risk_level=high` (P5D analyzer output)
2. Demote records with `risk_level=medium` to lower selection priority
3. Avoid same-artist cluster > 2 in the public 100 (currently allowed)

## 5. Daily digest selection rules

The daily digest builder picks 5 from 20 candidates using the
`diverse` strategy. Current heuristics:
- Different categories
- Different artists (mostly)
- Distinct color palettes (informally)

**Recommended new rules (P5E):**
1. Skip picks where the artwork is `risk_level=high`
2. Avoid same-artist duplicates (current 2026-06-12 digest had
   2× Yoshida Hiroshi + 2× Anonymous — should re-roll)
3. Verify `use_case` field is non-empty (a digest pick without
   a use case is just decoration)

## 6. Recommended future filters

### 6.1 Pre-export perceptual filter
Before exporting the public demo, run the visual QA on the candidate
set and:
- Exclude any `risk=high` record
- Down-weight `risk=medium` records
- Log excluded-records to `dist/refresh-candidates/<date>/gallery/excluded.json`

### 6.2 Digest visual diversity check
After picking 5, run the visual QA on the picks and:
- Check no two picks share the same artist
- Check no two picks are near-duplicates (aHash distance > threshold)
- Check palette diversity (L1 distance of dominant-color histograms)

### 6.3 Auto-watch on near-dup accumulation
Track near-duplicate groups per gallery. If a group size > 3, flag
for manual review (may indicate duplicated source downloads or
near-identical artworks that should be linked).

## 7. Manual review workflow

When the visual QA flags a record:
1. Open the contact sheet (`reports/runtime/p5d-*-contact-sheet.html`)
2. Click the thumbnail to inspect the image
3. Decide: `keep` / `drop` / `replace`
4. For drop: tag in the record (e.g., add `"excluded": "low_quality"` field)
5. For replace: add to manual_replace set in P5E config

## 8. P5E curation filters

P5E turns the visual-QA findings into **automated curation rules**
for the public demo exporter and the daily digest builder.

### 8.1 Public demo exporter — `--exclude-risk high`

The exporter now reads a visual-QA JSON and drops any record whose
`risk_level` is at or above the supplied threshold. Records with no
`risk_level` (not yet audited) pass through defensively.

```
python3 scripts/export_artvee_gallery_public_demo.py \
    --limit 100 \
    --exclude-duplicate-source-url-groups \
    --require-unique-source-url \
    --exclude-risk high \
    --visual-qa reports/runtime/p5d-visual-qa-full.json
```

Risk rank: `none (0) < low (1) < medium (2) < high (3)`. The default
`--exclude-risk high` only blocks clearly broken images. Use
`--exclude-risk medium` to also demote tiny files / near-monochrome
/ extreme-aspect records.

### 8.2 Public demo exporter — `--require-prompt-fields`

If a record has any of `prompt_seed` / `use_cases` / `visual_notes`
and leaves one of them empty, the record is dropped. Records with
none of these fields pass through (the public gallery JSON is not
required to surface prompt metadata; the digest is).

### 8.3 Daily digest — `--max-per-artist 1` (default)

The digest builder now enforces a strict cap of one pick per artist
per digest. Anonymous artists are normalized to the literal string
`"Anonymous"` so the cap is enforced across them too. The
`--allow-repeat-artist` flag disables the cap.

```
python3 scripts/build_artvee_daily_digest.py \
    --strategy diverse \
    --select 5 \
    --candidate-limit 20 \
    --max-per-artist 1
```

If the candidate pool is too small to satisfy the cap, the digest
build still returns up to `--select` picks and logs a `WARN` line
listing which artists had to repeat. (For 5 picks from a 20-candidate
pool this has never triggered in practice.)

### 8.4 Daily digest — non-empty prompt fields

After visual analysis, the digest builder validates that
`prompt_seed` and `use_cases` are non-empty for every pick. If a
field is empty (e.g. Pillow unavailable and category hint missing),
a deterministic fallback is applied:

- `prompt_seed` → `"vintage art print, <id>, public domain"`
- `use_cases` → `["灵感参考", "设计素材", "印刷品参考"]`

The backfill count is reported in the build log; backfilled
digests are not flagged in the index (the on-disk content is
identical to a fully-analyzed digest from the consumer's point of
view).

### 8.5 P5E / P5F live verification (2026-06-12 19:06 GMT+8)

All four P5E curation rules are wired into the export pipeline
*and* verified live on the public surface after P5F approve-publish
(commit `f972f5a` on `conanxin/conanxin.github.io`):

| Rule | Wired in | Live verify (after P5F) |
| --- | --- | --- |
| `--exclude-risk high` | `export_artvee_gallery_public_demo.py` (reads `reports/runtime/p5d-visual-qa-full.json`); auto-enabled in `confirm_demo_refresh.sh` | 0/100 records dropped (P5D reports 0 high-risk); all 100 picks risk=none |
| `--require-prompt-fields` | same script, opt-in flag | n/a (gallery JSON omits prompt fields by design) |
| Digest `--max-per-artist 1` | `build_artvee_daily_digest.py` (default 1; `--allow-repeat-artist` to disable) | 5/5 unique artists live (was 2× Yoshida + 2× Anonymous pre-P5E) |
| Digest non-empty prompt fields | same script (deterministic fallback, no external AI) | backfills=0 (analyzer always populates) |

## 9. Known limitations

- **Perceptual aHash is 64-bit** — fast but not state-of-the-art.
  Two visually similar images with different crops may not collide.
  For fine-grained dedup, use dHash + wHash combination (future).
- **No semantic understanding** — visual QA cannot tell if a
  portrait vs landscape is "good" art; it only flags technical
  problems (blank, corrupt, extreme aspect).
- **No artist-style detection** — a monochromatic Hiroshige is a
  real artwork, not a defect. The "near-monochrome" risk may
  produce false positives for legitimate monochrome prints.
- **Threshold tuning** — current thresholds are conservative
  defaults; adjust after running on a larger gallery.
- **Hash collisions at 8×8** — common across many small thumbs.
  A near-dup group of 5+ is usually a real cluster, not a
  false positive.

## 10. KNOWN_RETIRED URLs and visual QA (P6B)

The 4 P5A unresolved-loser URLs
(`la-plume-4`, `le-reve`, `le-reve-3`,
`tetes-byzantines-brunette`) are explicitly
marked `KNOWN_RETIRED` in
`reports/runtime/p6b-known-retired-urls.json`.
They:

- Do **not** appear in `web/data/artworks.json` — they
  never made it past download, so the visual QA
  pipeline never saw them.
- Are **excluded by construction** from
  `analyze_gallery_visual_quality.py` outputs
  (it iterates `web/data/artworks.json`).
- Do **not** count toward the gallery total
  (756 records, 100% risk=none, unchanged).
- Do **not** count toward digest or public-demo
  selection (5/5 unique artist, 100/100 risk=none,
  unchanged).
- Are **never retried** by `analyze_gallery_visual_quality.py`
  or by `publish_demo_refresh_candidate.sh`.

Future state changes:

- If a KNOWN_RETIRED URL ever becomes reachable, the
  right move is to add it to `index/artworks.csv` as a
  *new* record. It will then naturally be excluded from
  the retired manifest (which is regenerated from the
  canonical unresolved report).
- The retired manifest is a runtime artifact under
  `reports/runtime/`, NOT in git. Re-running
  `python3 scripts/mark_known_retired_urls.py --apply`
  regenerates it from the canonical unresolved report
  (P5A primary, P4B fallback).

## 11. Near-duplicate review (P6C)

P6C extends the P5D visual QA pass into a **conservative
near-duplicate review workflow**. It does not modify the
gallery data; it produces runtime review artifacts for
human curation and future digest/demo selection rules.

### What P6C does

```bash
cd artvee-library
python3 scripts/review_near_duplicate_clusters.py
```

Outputs (all runtime, not tracked):

| Artifact | Path | Purpose |
| --- | --- | --- |
| JSON | `reports/runtime/p6c-near-dup-clusters.json` | Machine-readable cluster definitions + per-record policy |
| Markdown | `reports/runtime/p6c-near-dup-clusters.md` | Human-readable review report |
| HTML contact sheet | `reports/runtime/p6c-near-dup-contact-sheet.html` | Browser visual review (relative thumb paths, no base64) |

### Default behavior

- **Threshold = 0** (exact aHash match). This reproduces the P5D
  exact-match groups and is the most conservative filter.
- **Fallback:** if P5D visual QA JSON is available, reuses its
  aHashes instead of recomputing 756 thumbnails. This makes P6C
  run in seconds even on a large gallery.
- **No network, no downloads, no file modification.** Pure local read.

### Review policies (conservative, no deletion)

| Type | Trigger | Policy | Digest rule | Public demo rule |
| --- | --- | --- | --- | --- |
| `collision_legacy` | P4B migration artifact: same title, unique source_url/image_path/id, hex suffix id | `keep_all` | `limit_one_per_digest` | `limit_one_per_digest` |
| `artist_cluster` | Same artist, different works, same visual family (e.g., book-illustration series) | `keep_all` | `limit_one_per_digest` | `limit_one_per_digest` |
| `true_series` | Same artist, same series, intentionally similar | `keep_all` | `limit_one_per_digest` | `limit_one_per_digest` |
| `possible_duplicate` | Same source_url or same image_path (should not happen in strict integrity) | `review` | `review_before_digest` | `review_before_public` |
| `mixed` | Different artists, same aHash (perceptual hash collision) | `keep_all` | `review_before_digest` | `review_before_public` |

### Why not automatically delete near-dup groups?

1. **Artistic intent:** An artist may produce a series of similar works (Dulac book illustrations, Nielsen landscapes).
2. **Different editions:** Same artwork with different printings, colorings, or cropping are legitimate records.
3. **aHash collisions:** 8×8 grayscale average hash is a fast perceptual hash, not a semantic fingerprint. Two different images can collide.
4. **P4B collision legacy:** Past migration artifacts are data-state history, not errors. They have unique IDs, URLs, and paths.

### Integration with digest and public demo

Future builders should read `p6c-near-dup-clusters.json` and apply:

- `limit_one_per_digest` → select at most one work from the cluster per daily digest
- `review_before_digest` → flag for human curator; do not auto-select multiple works from the cluster
- `review_before_public` → same for public demo

The contact sheet is the human decision surface: open it in a browser, visually inspect the cluster, and document any overrides in `docs/NEAR_DUPLICATE_REVIEW.md`.
