# Near-Duplicate Review

## 1. Purpose

This document defines the Artvee Gallery near-duplicate review workflow (Phase P6C).

Near-duplicate detection helps us:
- Understand which artworks share visual similarity
- Prevent over-representation of one visual cluster in daily digests and public demos
- Identify legacy data artifacts (e.g., P4B collision duplicates) without treating them as errors
- Make informed curation decisions **without** deleting, moving, or excluding any artwork automatically

## 2. What near-duplicate means

In this context, a **near-duplicate** is a group of artworks whose 8×8 average hash (aHash) produces the same hex value (threshold = 0 exact match) or falls within a small Hamming distance (threshold > 0 for expanded search).

Notes:
- aHash is a perceptual hash, not a cryptographic hash. Two different images can have the same aHash.
- Exact aHash match (threshold = 0) is the most conservative filter and is the default for P6C review.
- A cluster may contain artworks from different artists, different categories, or different source URLs.
- Similarity does **not** imply one is a copy of the other. It only means they are visually similar at 8×8 grayscale resolution.

## 3. Why near-dup is not automatically bad

**Keep all near-duplicates.** The gallery does not delete or exclude artworks based on visual similarity alone. Reasons:

1. **Artistic intent:** An artist may intentionally produce a series of similar works (e.g., Edmund Dulac book illustrations, Amaldus Nielsen Norwegian landscapes).
2. **Different editions/variations:** Different printings, colorings, or cropping of the same artwork are legitimate records.
3. **aHash collisions:** Different images can produce the same aHash, especially if they share dominant tones (e.g., black-and-white illustrations, blue seascapes).
4. **P4B collision legacy:** Past data migration may have created multiple stable IDs for the same artwork. These are data artifacts, not content errors. They are already distinguishable by unique `id`, `source_url`, and `image_path`.

## 4. Review policies

P6C uses a **conservative, no-deletion policy**:

| Rule | Condition | Default policy | Rationale |
|------|-----------|---------------|-----------|
| **Rule A** | Same artist + visually similar series (e.g., book illustrations) | `keep_all`, `limit_one_per_digest` | Artist series are legitimate content |
| **Rule B** | Different `source_url` + different `stable_id` | `keep_all` | Unique provenance = unique record |
| **Rule C** | Same `source_url` or same `image_path` | `review` | Strict integrity check should prevent this; flag if found |
| **Rule D** | P4B collision legacy (`id` has hex suffix, same title, unique paths) | `keep_all`, `do_not_treat_as_data_error` | Migration artifact, not a bug |
| **Rule E** | Mixed cluster (different artists, same aHash) | `keep_all`, `review_before_digest` | Likely aHash collision; do not auto-exclude |

All policies are recommendations. Human review is required before any exclusion action.

## 5. Digest rule

Near-duplicate groups may remain in the gallery, but **daily digest should avoid selecting multiple works from the same near-duplicate cluster**.

Implementation:
- Digest builder reads `p6c-near-dup-clusters.json`
- If a cluster is marked `artist_cluster` or `collision_legacy`, select **at most one** work from that cluster per digest
- If a cluster is `mixed` or `true_series`, apply `review_before_digest` flag and let human curator decide

## 6. Public demo rule

Public demo may include related works, but should **avoid overrepresenting one cluster**.

Implementation:
- Public demo builder reads `p6c-near-dup-clusters.json`
- For clusters with `limit_one_per_digest` policy, apply the same limit to public demo selection
- Goal: show breadth of collection, not 5 slight variations of the same illustration

## 7. Manual review workflow

### Step 1: Run review script (no side effects)
```bash
cd artvee-library
python3 scripts/review_near_duplicate_clusters.py
# Default: threshold=0, exact aHash match
# Optional: --threshold 6 for expanded search (more false positives)
```

Outputs (runtime only, not committed to git):
- `reports/runtime/p6c-near-dup-clusters.json` — structured data
- `reports/runtime/p6c-near-dup-clusters.md` — human-readable report
- `reports/runtime/p6c-near-dup-contact-sheet.html` — visual browser

### Step 2: Review contact sheet
Open `reports/runtime/p6c-near-dup-contact-sheet.html` from repo root (paths are relative). Check:
- Are the grouped images actually similar?
- Are different-artist clusters legitimate aHash collisions or data errors?
- Are collision-legacy clusters correctly identified?

### Step 3: Apply policy annotations
Do **not** modify `web/data/artworks.json`, `index/artworks.csv`, or `inbox/manifest.csv`.

If a cluster needs special handling, document it in:
- This file (`docs/NEAR_DUPLICATE_REVIEW.md`) under "Known P6C findings"
- Or a new `docs/NEAR_DUPLICATE_EXCEPTIONS.md` if the list grows

### Step 4: Update digest/demo builders
Modify `scripts/build_artvee_daily_digest.py` and `scripts/export_artvee_gallery_public_demo.py` to read the P6C JSON and apply `limit_one_per_digest` / `review_before_digest` rules.

## 8. Known P6C findings

Current dataset: **756 artworks**, **8 exact aHash near-duplicate clusters** (threshold = 0).

### Collision legacy (3 clusters)
These are P4B migration artifacts — same artwork, multiple stable IDs. All have unique `source_url`, `image_path`, and `stable_id`. **Do not treat as data errors.**

| Cluster | Size | Title | Artist |
|---------|------|-------|--------|
| `cluster-006` | 2 | Høstdag. Bjelland Mandal | Amaldus Nielsen |
| `cluster-007` | 2 | Affiche van de Chambre Syndicale… | Anonymous |
| `cluster-008` | 2 | Two cranes | Ohara Koson |

**Policy:** `keep_all`, `limit_one_per_digest`.

### Artist cluster (2 clusters)
Same artist, different works, visually similar (likely same palette or genre). These are legitimate series.

| Cluster | Size | Artist | Works |
|---------|------|--------|-------|
| `cluster-003` | 3 | Amaldus Nielsen | September, Skjærgård Gamle Hellesund, Sognejekter |
| `cluster-004` | 2 | Amaldus Nielsen | Morgenstemning Atlanterhavet, Regnstemning Jæren |

**Policy:** `keep_all`, `limit_one_per_digest`.

### Mixed clusters (3 clusters)
Different artists or categories grouped by the same aHash. These are **perceptual hash collisions**, not content duplicates. They should not be excluded.

| Cluster | Size | Artists | Notes |
|---------|------|---------|-------|
| `cluster-001` | 5 | Edmund Dulac ×4, Anonymous ×1 | Dulac book illustrations share black-and-white style; Anonymous poster may be a false positive |
| `cluster-002` | 5 | Arthur Rackham ×3, Jules Chéret ×1, Jean-Pierre-Marie Jazet ×1 | Rackham book illustrations share dark line-art style; other two are likely false positives |
| `cluster-005` | 2 | Edmund Dulac ×1, Jules Chéret ×1 | Both are dark-tone posters/illustrations; likely false positive |

**Policy:** `keep_all`, `review_before_digest`. Human curator may decide to exclude one from digest if visually redundant.

---

*Document version: P6C-1.0*
*Last updated: 2026-06-12*
*Generated by scripts/review_near_duplicate_clusters.py*
