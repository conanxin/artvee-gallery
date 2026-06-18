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

The digest builder itself does not push to GitHub Pages. The public digest page is refreshed through the existing candidate flow (`confirm_demo_refresh.sh` + `publish_demo_refresh_candidate.sh`). The history file is a **local-only runtime artifact** that the public Pages repo never sees directly.

### P6F+1 Approved publish (2026-06-12)

The first approved publish after P6F shipped at commit `f419d31` on `conanxin.github.io`:
- Gallery: `https://conanxin.github.io/projects/artvee-gallery-demo/` (100 records, 5.7M)
- Digest: `https://conanxin.github.io/projects/artvee-gallery-digest/` (5 picks, 5 unique artists, 3 categories)
- The digest page includes `data/digests.json` with the `picks` array (including `near_dup_cluster_id` for each pick), demonstrating the near-dup awareness is live on the public surface.

### P8B Public archive (2026-06-18)

P8B surfaces the 30-day history as a real public page so the visitor
can browse *every day's picks* without waiting for tomorrow's digest.
The flow:

1. `scripts/build_artvee_daily_digest.py` writes / appends to
   `reports/runtime/digest-history.json` every day (already
   established in P6F).
2. `scripts/export_artvee_digest_public_page.py` reads the
   history file, strips the `digest_path` field (which contains
   a local-absolute path even after the digest builder's
   redaction), and emits:
   - `data/digest-history.json` — a *public-safe* copy (no
     `digest_path`, no `metadata/`, no `images/`, no local
     project-root substring, no absolute paths).
   - `archive.html` — a 30-day rolling table (date / strategy /
     picks / categories / near-dup cluster). Text-only by
     design; the per-pick 512-thumb is reached from
     `data/digests.json` and the per-day digest HTML.
3. The existing `confirm_demo_refresh.sh` adds a P8B archive QA
   step that asserts `archive.html` + `data/digest-history.json`
   exist, parse, and contain no forbidden substrings.
4. `scripts/publish_demo_refresh_candidate.sh --approve` rsyncs
   the digest candidate (now including `archive.html` and
   `data/digest-history.json`) into the Pages repo.

The archive page is **honest** about the history size: if the
digest has only run for N days, the page shows "History
entries currently available: N" rather than a fabricated 30
days. When the rolling history fills, the note disappears.

## 9. P8C navigation polish (cards + filters)

P8C upgraded the archive page from P8B's text-only table to a
**digest cards** layout with a **client-side filter** row.

Per-day card shape:

* Top row: date `<code>` + pick count + strategy chip
* Second row: category chips (one per unique category in the
  pick set) + near-dup cluster chip (when at least one pick
  carries a `near_dup_cluster_id`)
* Body: a 5-column auto-fill grid of pick thumbnails (256
  variant, lazy-loaded) with artist + category + near-dup
  cluster labels. Each pick image has `onerror="visibility:hidden"`
  so a single missing 256 thumb never 404s the page.

Filter row (vanilla `archive.js`, no framework, no external
CDN, ~4.3 KB):

* **Artist** `<select>` — populated dynamically from all
  cards' `data-artists` pipe-joined list
* **Category** `<select>` — same pattern over `data-categories`
* **Search** `<input type="text">` — matches date / strategy /
  pick-id substrings, all stored on `data-search`
* **Clear** button — resets all three
* **Jump to latest** — smooth-scrolls to the first visible
  `.day-card`

The page is **fully readable with JS disabled** — every card
and meta chip is server-rendered. JS only adds interactivity.
The `#no-results` notice is hidden by default and only appears
when filters hide every card.

The `data/digest-history.json` schema gained a `summary` block
(`total_days` / `total_picks` / `unique_artists` /
`top_categories`) and a top-level `available_range`
(`first_date` / `latest_date`) so downstream consumers don't
have to recompute them. The `entries[]` shape is unchanged
from P8B for backward compatibility; only the `digest_path`
field is stripped.

---

*Document version: P8C-1.0*  
*Last updated: 2026-06-18*
