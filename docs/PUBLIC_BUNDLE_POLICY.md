# Public Bundle Policy

This document captures the official policy for what assets, metadata, and
schema fields the **public** Artvee Gallery bundle may ship. It is the
single source of truth for the public bundle surface area and replaces any
ad-hoc decisions captured in commit messages or operational reports.

This policy was first formalized in **P9G+2 (2026-07-12)** and is reviewed
before any phase that changes bundle composition (e.g., future record
counts or new thumb sizes).

## Quick contract

| Surface | Allowed | Forbidden |
| --- | --- | --- |
| Records | 300 selected works (diverse, all green-risk) | Any retired / blocker entry |
| `data/artworks.json` | `id`, `title`, `artist`, `category`, `source_url`, `tags`, `thumb_256` (`./assets/thumbs/256/<id>.jpg`), `image_path` (mirrors `thumb_256` under policy `none`), `download_variant`, `downloaded_at` | `metadata_path`, `digest_path`, raw `images/` paths |
| `data/gallery_stats.json` | `public_records` (== records count), `detail_thumb_policy`, `thumbs_256_count`, `thumbs_512_count`, `counts`, `categories` | Library record totals larger than the public bundle |
| Thumbnail set under `none` (default) | `assets/thumbs/256/` only | `assets/thumbs/512/` (whole directory) |
| Thumbnail set under `all` (legacy) | `assets/thumbs/256/` + `assets/thumbs/512/` | n/a |
| Page assets | `app.js`, `style.css`, `index.html` (≤ ~30 KB total) | any new dependency, build tools |
| Local Library artwork (`images/`, `metadata/`, `thumbs/`) | Untouched | Never replaced, never deleted by a public-bundle phase |
| Local Library full image / metadata | Not public | Never copied or referenced from `assets/` |

## Detail-thumb-policy

| Policy | Behaviour |
| --- | --- |
| `all` (legacy) | Ship `assets/thumbs/512/` alongside `assets/thumbs/256/`. `artworks.json` carries a non-null `thumb_512` for every record. Soft budget 15 MB / hard 20 MB. |
| `none` (default, since P9G+2) | Do not ship `assets/thumbs/512/`. `artworks.json` carries `thumb_512: null`. `image_path` mirrors `thumb_256` so the detail panel never requests a missing asset. Soft budget 5 MB / hard 8 MB. |

The policy is set by:

```bash
bash scripts/confirm_demo_refresh.sh \
  --gallery-limit N \
  --detail-thumb-policy {all,none}
```

`confirm_demo_refresh.sh` defaults to `--detail-thumb-policy=none` since
P9G+2. The previous P9G behaviour (default `all`) is still selectable
via the explicit flag.

## Detail-panel fallback chain

The front-end uses:

```js
const detailSrc = a.thumb_512 || a.image_path || a.thumb_256;
```

Because under `none` the exporter sets `thumb_512 = null` and remaps
`image_path` to the same path as `thumb_256`, the chain resolves to the
256 thumb for every record without producing a broken-image. The old `all`
behaviour is preserved by the same chain.

## Why this policy exists

The P9G+1 audit showed that the previous `all` policy made the public
bundle 14.88 MB even though:

- the Grid uses only 256 thumbnails (8.96 KB/file × 300 ≈ 3 MB);
- the 512 thumbnails (≈ 11 MB) were used **only** when a user clicked a
  card — and even then, only one card at a time;
- 500 records under `all` would project to 24.59 MB (over the 20 MB hard
  budget) without buying any visible improvement to Grid scrolling.

The policy frees the bundle for future record growth (400 records at
256-only project to ~4.55 MB; 500 records to ~5.62 MB — both within the
8 MB hard budget). Local 512 thumbnails continue to live in the local
Library `thumbs/512/` directory and are unaffected.

## When to revisit

This policy should be revisited **only** when:

- the local Library's image-source schema changes;
- the public record count is increased past 500;
- the front-end introduces new components that consume 512 thumbs.

Any change must update `PUBLIC_BUNDLE_POLICY.md`, bump the soft/hard
budgets accordingly, and queue a follow-up audit.

## Acceptance checklist (template)

For every public-bundle phase that touches the exporter or fallbacks:

- [ ] `check_open_source_ready.py` PASS
- [ ] `check_gallery_integrity.py --strict` PASS
- [ ] Bundle size within soft limit (warning if between soft and hard)
- [ ] Records == target (default 300)
- [ ] `thumbs/512/` references in `data/artworks.json` matches policy
- [ ] No forbidden substrings (`metadata_path`, `digest_path`, home-dir prefix,
      repo-name mention, `images/`, `metadata/`, `TOKEN`, `SECRET`, `CHAT_ID`)
- [ ] `check-project-publish-guard.py` PASS
- [ ] Online `gallery_stats.json` reflects the intended `detail_thumb_policy`
- [ ] Browser smoke test records `0 /512/ network requests` (when `none`)
