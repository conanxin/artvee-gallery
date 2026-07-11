# Artvee Metrics Model (P9F+1)

> Status: **canonical, v0.2.1+**. This document is the single source of
> truth for what every "records"-shaped number in the Artvee project
> means. It supersedes anything written in CHANGELOG, README, or older
> release notes that contradicts the schema below.

The story is short: the project had four different numbers all called
"records" (875 / 1093 / 1206 / 200 in one observed snapshot), and each
belonged to a different layer of the system. P9F+1 collapsed them into
one schema, one collector, one source of truth, and one freshness rule.

## 1. The four numbers explained

| Brief label | Real meaning | Source | Why we never want it as "library_records" |
|---|---|---|---|
| `875` | `artvee-status-report.json.records` (cached, frozen 2026-06-18) | `web/data/gallery_stats.json` via `build_artvee_status_report.py` | Stale 23 days relative to actual growth |
| `1093` | Manifest lifecycle cumulative (downloads ever accumulated) | `inbox/manifest.csv` `status=downloaded` count | Counts retries, known_retired placeholders, and successful first-tries |
| `1206` | `check_gallery_integrity.py --strict` row counters across three sources | `manifest.rows + index.rows + web.records` | Integrity checker's own scope; not a single library number |
| `300` | Public Gallery export limit | `export_artvee_gallery_public_demo.py --limit 300` | A diverse sample of the library, not its size |

## 2. Canonical schema — `artvee-metrics-v1`

```json
{
  "schema_version": "artvee-metrics-v1",
  "generated_at": "<ISO8601 UTC>",
  "as_of": "<ISO8601 UTC>",
  "source_mode": "live" | "fallback_cache",
  "max_age_seconds": 86400,
  "metrics": {
    "library_records":            1286,   // canonical available works
    "indexed_records":            1286,   // index unique source_url
    "gallery_records":            1286,   // web JSON unique ids
    "disk_images":                1286,
    "disk_metadata":              1286,
    "thumbs_256":                 1286,
    "thumbs_512":                 1286,

    "manifest_total":             1355,   // all lifecycle states
    "manifest_downloaded":        1290,
    "manifest_pending":             54,
    "manifest_failed":              10,
    "manifest_skipped":              1,

    "known_retired":                 4,
    "blocking_unresolved":           0,
    "digest_history_entries":       28,

    "public_records":             null,    // null when offline; int when --online
    "integrity_checked_records":  1355,    // manifest.rows (checker scope)
    "integrity_scope":            "manifest+index+web"
  },
  "consistency": {
    "library_layers_match":        true,
    "mismatches":                  []
  },
  "freshness": {
    "age_seconds":                  0,
    "stale":                    false,
    "stale_reason":                 "",
    "max_age_seconds":          86400
  },
  "warnings": [],
  "errors":   []
}
```

## 3. Definitions (P9F+1)

### `library_records` — the single canonical number

The size of the local library. P9F+1 reads `web/data/artworks.json`
first; if that file is missing (open-source-only CI environment), it
falls back to `index/artworks.csv`'s unique URL count, then to
`images/`'s file count. Every layer mentioned below MUST equal this
number when the local repo is fully populated.

This is the number that goes into Telegram, the Daily Health summary,
the Ops Status table, and the v0.2.1 release headline. Its synonym
inside the schema is `metrics.library_records` (top-level `records`
alias is preserved for legacy callers and is marked
`records_deprecated: True`).

### `indexed_records`

`len(unique(source_url for row in index/artworks.csv))`. Must equal
`library_records`.

### `gallery_records`

`len(unique(id for entry in web/data/artworks.json))`. Must equal
`library_records`.

### `disk_images` / `disk_metadata` / `thumbs_256` / `thumbs_512`

`find <dir> -type f ! -name .gitkeep | wc -l`. Each MUST equal
`library_records`.

### `manifest_total`

`len(rows in inbox/manifest.csv)`. Per P9F this can be larger than
`library_records` because `pending` / `failed` / `skipped` rows are
kept around as historical evidence. The canonical invariant is:

```
manifest_downloaded + manifest_pending + manifest_failed + manifest_skipped == manifest_total
```

### `manifest_downloaded`, `manifest_pending`, `manifest_failed`, `manifest_skipped`

`status==X` count in `inbox/manifest.csv`. Note that
`manifest_downloaded` is **larger** than `library_records` by the
number of `known_retired` URLs (currently 4): the manifest keeps them as
`status=downloaded` placeholders even though they have been formally
retired and excluded from the library. This is intentional and the
`check_artvee_metrics.py` regression keeps the invariant alive.

### `known_retired`

`len(records) in reports/runtime/p6b-known-retired-urls.json`. Audited,
not blocking.

### `blocking_unresolved`

`0` while `p6b-known-retired-urls.json` exists; otherwise equal to
`unresolved_total`. P9F+1 keeps the P6B invariant.

### `digest_history_entries`

`len(entries) in reports/runtime/digest-history.json`. Per-day picks,
distinct from "library records".

### `public_records`

`len(...)` of the public `https://conanxin.github.io/projects/artvee-gallery-demo/data/artworks.json`
fetched only when `include_public=True` is passed. Defaults to
`null` (offline) so consumers can distinguish "we didn't check" from
"checked and got 200".

### `integrity_checked_records` / `integrity_scope`

`manifest_total`. Documents the integrity checker's scope so JSON
consumers cannot mistake it for `library_records`.

## 4. `source_mode` and `freshness`

Every metrics dict carries:

- `source_mode`: `"live"` when the collector read from disk in this
  process; `"fallback_cache"` when a caller had to fall back to a
  cached snapshot.
- `freshness.age_seconds`: seconds between the snapshot's
  `generated_at` and now.
- `freshness.stale`: `true` when `age_seconds > max_age_seconds` or
  when `generated_at` is missing/unparseable. Default threshold is
  `86400` (24h); override via `ARTVEE_STATUS_MAX_AGE_SECONDS`
  (positive integer only).
- `freshness.stale_reason`: short string explaining why `stale=True`
  (e.g. `"age_2592000s_exceeds_max_86400s"`,
  `"generated_at_missing_or_unparseable"`,
  `"no_metrics_collected"`).

When `stale=True`, the Ops Status `recommended_action` becomes
`attention_required_metrics_stale` so Telegram operators see the issue
without scanning a log file.

## 5. Backward compatibility (`records` alias)

To avoid breaking older callers, every payload exposes a top-level
`records` field that always equals `metrics.library_records`:

```json
{
  "records":              1286,
  "records_semantics":    "library_records",
  "records_deprecated":   true
}
```

New code MUST use `metrics.library_records` directly; the alias will
be removed in v0.3.0 (see `docs/ROADMAP.md` for the schedule).

## 6. Where the model is enforced

| Path | Role |
|---|---|
| `scripts/artvee_metrics.py` | The collector. Single source of truth. |
| `scripts/build_artvee_status_report.py` | Builds `reports/runtime/artvee-status-report.json` from the collector. Atomic write. |
| `scripts/artvee_daily_health_check.py` | Telegram text + dashboard summary. Live-collects, no silent cache. |
| `scripts/artvee_ops_status.py` | Post-stable ops aggregator. Live-collects, surfaces `metrics_stale` and `attention_required_metrics_stale`. |
| `scripts/check_gallery_integrity.py` | Now annotates its output as `integrity_checker_scope` and never re-uses bare `records` for library counts. |
| `scripts/check_artvee_metrics.py` | Regression test. Runs 20 invariants on every CI push. |

## 7. Migration recipe for callers

If your code is reading `artvee-status-report.json` looking for
`records`:

```diff
- data = json.load(open("reports/runtime/artvee-status-report.json"))
- library_records = data["records"]
+ from artvee_metrics import collect_current_metrics
+ m = collect_current_metrics(root=Path("/path/to/artvee-repo"))
+ library_records = m["metrics"]["library_records"]
```

If you need offline-only fallback (don't want to read disk yourself):

```diff
+ from artvee_metrics import collect_current_metrics
+ m = collect_current_metrics(root=Path("/path/to/artvee-repo"))
+ if m["freshness"]["stale"]:
+     # Warn the operator; do not pretend the data is healthy.
+     log_warning(m["freshness"]["stale_reason"])
```

## 8. Why this matters

Before P9F+1:

- `records=875` was a 23-day-old cached snapshot still being shown as
  current on every Daily Health Telegram message.
- `records=1206` was the integrity checker's manifest rows, never the
  number of available works.
- `Online: gallery=200` and `Public Gallery: 200` were the same word in
  the same chat but meant different things.

After P9F+1:

- Every caller sees `library_records` (live, fresh, identical).
- The integrity checker is annotated; its numbers are unambiguous.
- HTTP codes and record counts are spelled out in full.
- Stale caches are flagged with an explicit `source_mode` and a
  dedicated `recommended_action`.
