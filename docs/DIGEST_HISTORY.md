# Digest History

## 1. Purpose

`docs/DIGEST_HISTORY.md` defines the Artvee Gallery digest history and near-duplicate-aware selection workflow (Phase P6F).

The digest builder (`scripts/build_artvee_daily_digest.py`) maintains a **30-day sliding window** of past picks to avoid repeating the same artwork, the same artist, or the same near-duplicate cluster within a short time span. This turns a daily digest from a single-run snapshot into a **time-aware publication** that optimizes over a window.

## 2. 30-day sliding window

The default `history-days` is **30**. On every digest build, the script:

1. Loads `reports/runtime/digest-history.json` (runtime only, not tracked in git).
2. Collects all artwork `id`s, `artist`s, and `near_dup_cluster_id`s that appeared in the last 30 days.
3. Filters the candidate pool before selection, applying rules in order:
   - **Rule 1** (id): remove artworks already picked in the window.
   - **Rule 2** (artist): remove artworks whose artist was already picked in the window.
   - **Rule 3** (cluster): remove artworks whose near-dup cluster was already picked in the window.
4. If the filtered pool drops below the requested `select` count, the rule that caused the shortage is relaxed. If all rules are exhausted, a fallback reason is recorded and the best available pool is used.

### Why 30 days?

- Long enough to ensure genuine variety (a month of daily digests = ~150 unique artworks).
- Short enough that seasonal themes or artist retrospectives can still recur naturally after a pause.
- Matches the "publication" mental model: a magazine does not repeat the same cover artist within the same issue month.

## 3. Artist diversity

The existing `--max-per-artist 1` (P5E) curation filter continues to operate **within a single digest**. The 30-day history window extends this to **across digests**.

Example: if Yoshida Hiroshi appears in the 2026-06-01 digest, the 2026-06-02 digest will avoid picking Yoshida Hiroshi again unless the candidate pool is too small.

## 4. Near-duplicate cluster awareness

The digest builder reads `reports/runtime/p6c-near-dup-clusters.json` (produced by P6C `review_near_duplicate_clusters.py`) and builds an `artwork_id -> cluster_id` mapping.

If a cluster (e.g., `cluster-006` = Amaldus Nielsen "Høstdag" collision legacy) has already appeared in the 30-day window, the builder avoids picking another artwork from the same cluster. This prevents the digest from feeling repetitive when two visually similar works are separated by only a few days.

## 5. Fallback behavior

If the strictest filter (id + artist + cluster) leaves fewer than `select` candidates, the builder relaxes the rules in order:

1. Relax cluster filter only → id + artist.
2. Relax artist filter → id only.
3. Relax all filters → no history filtering.

Each relaxation is recorded in the digest metadata as a fallback reason, so the operator can see when the gallery is running low on fresh candidates.

## 6. Runtime history file

**Path:** `reports/runtime/digest-history.json` (gitignored, runtime only).

**Structure:**

```json
{
  "version": 1,
  "updated_at": "2026-06-12T21:51:00",
  "window_days": 30,
  "entries": [
    {
      "date": "2026-06-12",
      "digest_path": "digests/artvee-digest-2026-06-12.md",
      "picks": [
        {
          "id": "...",
          "artist": "...",
          "category": "...",
          "near_dup_cluster_id": "cluster-006"
        }
      ]
    }
  ]
}
```

**Properties:**
- **Idempotent**: running the digest builder twice on the same date updates the same entry, it does not append a duplicate.
- **Capped**: max `window_days * 2` entries (minimum 60), so the file never grows unboundedly.
- **Newest-first**: entries are sorted by date descending.
- **No local paths**: `digest_path` is relative (uses `_safe_rel` to strip any absolute path fragments).

## 7. Manual reset / ignore-history

```bash
# Rebuild today's digest ignoring all history (fresh start)
python3 scripts/build_artvee_daily_digest.py \
  --ignore-history \
  --strategy diverse --select 5

# Rebuild with a shorter window (e.g., 7 days)
python3 scripts/build_artvee_daily_digest.py \
  --history-days 7 \
  --strategy diverse --select 5

# Reset history file entirely (delete the runtime file)
rm reports/runtime/digest-history.json
```

## 8. Integration with public demo

The digest builder itself does not push to GitHub Pages. The public digest page is refreshed through the existing candidate flow (`confirm_demo_refresh.sh` + `publish_demo_refresh_candidate.sh`). The history file is a **local-only runtime artifact**; it does not travel to the public Pages repo.

---

*Document version: P6F-1.0*  
*Last updated: 2026-06-12*
