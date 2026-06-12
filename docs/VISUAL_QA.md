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

## 8. Known limitations

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
