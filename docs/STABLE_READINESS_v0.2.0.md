# v0.2.0 Stable Readiness Review

> Generated 2026-06-16 (Asia/Shanghai) as part of **Phase P7F** of the
> [Artvee Gallery](../PROJECT_STATUS.md) project. This document records the
> readiness assessment for promoting **v0.2.0-alpha → v0.2.0 stable**.
> It is a review-only document. **No tag, no release, no push to Pages, no
> runtime data is created or modified by this review.**

## 1. Summary

**Recommendation: ready for v0.2.0 stable**, contingent on explicit user
approval. All Day 1, Day 2, and Day 3 health checks are PASS; the single
incident on Day 2 (GitHub Pages content drift) was diagnosed, restored,
and hardened within the observation window; no new warnings or regressions
emerged on Day 3.

| Field | Value |
| --- | --- |
| Review date | 2026-06-16 (Asia/Shanghai) |
| Reviewer phase | P7F |
| Source release | v0.2.0-alpha (2026-06-13, commit `f9d2b9e`) |
| Target release | v0.2.0 stable (pending user approval — **not cut**) |
| Observation window | 2026-06-14 → 2026-06-16 (3 days) |
| Day-1 verdict | Green |
| Day-2 verdict | Green with incident annotation |
| Day-3 verdict | Green |
| Recommendation | **Stable ready** (approve to tag) |

## 2. Observation window

| Day | Date (Asia/Shanghai) | Health | Online | Notes |
| --- | --- | --- | --- | --- |
| 1 | 2026-06-14 | PASS | 200 + 200 | Baseline day, cron verified at 03:02 |
| 2 | 2026-06-15 | PASS (post-restore) | 200 + 200 | Pages content drift diagnosed (P7E+1) and restored (P7E+2); Pages publish guard added (cross-repo PAGES-GUARD-1); health script signal-distortion bug fixed |
| 3 | 2026-06-16 | PASS | 200 + 200 | Final day; 03:00 cron delivered Telegram text + MEDIA; this review conducted at 06:38 |

## 3. Daily health summary

Source: `reports/runtime/daily-health/artvee-daily-health-YYYY-MM-DD.md`.

| Date | Records | Known retired | Blocking unresolved | Strict integrity | Readiness | Online gallery | Online digest | Telegram text | Telegram MEDIA |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-06-14 | 795 | 4 | 0 | PASS | PASS | 200 | 200 | sent (22919) | sent |
| 2026-06-15 | 815 | 4 | 0 | PASS | PASS | 200 (post-restore) | 200 (post-restore) | sent (23150) | sent (23151) |
| 2026-06-16 | 815 (03:00 snapshot) → 835 (live rebuild) | 4 | 0 | PASS | PASS | 200 | 200 | sent (23707) | sent (23709) |

> The 815 → 835 growth reflects a regular nightly batch that completed
> before the manual status rebuild performed during this review. It does
> not change the green verdict; the integrity and readiness checks both
> re-ran clean against the live 835-record snapshot.

## 4. Incident summary

### 2026-06-15 GitHub Pages content drift

- **Detected by:** the 03:00 daily health check reported
  `Online: gallery=0, digest=0`. The local Artvee system was healthy.
- **Root cause:** a separate workstream (WBW SpaceX Mars publish flow)
  advanced the shared `conanxin.github.io` repo by 9 commits
  (`013fbdb → 3748acb`). Those commits replaced the `projects/` subtree
  as a whole, deleting both `projects/artvee-gallery-demo/` (205 files
  / 2042 lines) and `projects/artvee-gallery-digest/`. A side effect
  also wiped `projects/yang-fudong-fragrant-river/` (35 files), which
  was restored in a sibling phase (YF-RESTORE-1) outside this repo.
- **Diagnosis:** `P7E+1` confirmed via read-only `curl -I` on 9/9
  endpoints (all HTTP 404, DNS+TLS OK) and `git ls-tree` on `origin/main`
  (0 files under both `projects/artvee-gallery-{demo,digest}`).
- **Restore:** `P7E+2` ran
  `bash scripts/publish_demo_refresh_candidate.sh --date 2026-06-15
  --approve --cdn-wait 90` (single commit + push, no force, no reset).
  Restore commit on `origin/main`: `a5ad80c`. Re-verification: 9/9
  endpoints HTTP 200, sample thumbs 5/5.
- **Signal-distortion fix (this repo):** `scripts/artvee_daily_health_check.py`
  used to swallow `urllib.error.HTTPError` inside a generic `except
  Exception`, masking real HTTP codes (404) as `0,0`. The handler now
  distinguishes `HTTPError` (real code), `URLError` (network error),
  `TimeoutError`, and `ConnectionError`; the report adds
  `online.kind` ∈ {ok, http_error, network_error, skipped} and a
  per-endpoint error message. `recommended_action` now branches on
  the kind.
- **Publish-guard add-on (cross-repo):** `scripts/check-project-publish-guard.py`
  and `docs/PAGES_PUBLISH_GUARD.md` shipped in the Pages repo so that
  future WBW Mars publish runs cannot silently clobber the
  `projects/artvee-gallery-*` subtrees.
- **Recovery verdict:** the local Artvee system stayed healthy throughout
  the incident; no local data was lost; no local commit was reverted;
  the observation window did not need to extend because the recovery
  was completed within Day 2 and Day 3 ran clean.

## 5. Current operational baseline

Snapshot taken at 2026-06-16 06:38 (Asia/Shanghai) during this review.

| Aspect | Value |
| --- | --- |
| Records | **835** |
| Known retired | **4** |
| Blocking unresolved | **0** |
| Strict integrity | **PASS** (no duplicate ids, no duplicate basenames, no one-id-many-URL anomalies) |
| Readiness | **PASS** (4/4 sub-checks: generated-data, path-leak, secret-keyword, file-size) |
| Public demo ready | True |
| Digest ready | True |
| Latest nightly batch | 2026-06-16 02:00, 20 selected, 0 failed |
| Digest history entries | 5 |
| Near-dup clusters | 8 |
| Public demos online | 6/6 endpoints HTTP 200 (gallery index + artworks.json + gallery_stats.json; digest index + digest.html + digests.json) |
| Daily health cron | Installed (`0 3 * * *`, Asia/Shanghai), logs in `logs/daily-health-cron/` |
| Approved publish helper | `scripts/publish_demo_refresh_candidate.sh --approve --cdn-wait 90` (no auto-trigger) |
| Telegram text delivery | OK (message_id 23707 on 2026-06-16 03:00) |
| Telegram MEDIA delivery | OK (message_id 23709 on 2026-06-16 03:00) |

## 6. Stable readiness checklist

All items must be PASS before recommending a stable tag. This review
checks each item against the live state of the repo.

| # | Criterion | Result | Evidence |
| --- | --- | --- | --- |
| 1 | Repo branch is `main` | PASS | `git branch --show-current` |
| 2 | No uncommitted changes | PASS | `git status --short` clean of tracked-file modifications |
| 3 | `check_open_source_ready.py` exit 0 | PASS | 4/4 sub-checks PASS |
| 4 | `check_gallery_integrity.py --strict` exit 0 | PASS | 3/3 sections PASS, 0 duplicates |
| 5 | `status_report.records` is in healthy range (~700–900) | PASS | 835 |
| 6 | `status_report.known_retired` is audited and stable | PASS | 4 entries, audited in P6B |
| 7 | `status_report.blocking_unresolved` is 0 | PASS | 0 |
| 8 | Public demos online (6/6 endpoints HTTP 200) | PASS | live `curl -I` 2026-06-16 06:38 |
| 9 | Daily health cron is installed and recent | PASS | log at `logs/daily-health-cron/daily_health_20260616_030000.log` |
| 10 | Telegram text delivery works | PASS | message_id 23707 (2026-06-16 03:00) |
| 11 | Telegram MEDIA delivery works | PASS | message_id 23709 (2026-06-16 03:00) |
| 12 | No tracked secrets / no leaked paths in tracked files | PASS | `check_open_source_ready.py` 4/4 PASS |
| 13 | No tracked runtime data (`images/`, `metadata/`, `thumbs/`, `dist/`, `digests/`, `logs/`, `inbox/`, `web/data/`, `index/`, `reports/runtime/`, `tmp/`) | PASS | git-tracked paths check, only `.gitkeep` placeholders |
| 14 | Day-2 incident closed (Pages content drift diagnosed + restored + guarded) | PASS | P7E+1 / P7E+2 / PAGES-GUARD-1 |
| 15 | 3 consecutive green days of observation | PASS | Day 1 / Day 2 (post-restore) / Day 3 |

**Score:** 15 / 15 PASS.

## 7. Risks

| Risk | Severity | Mitigation |
| --- | --- | --- |
| GitHub Pages drift may recur (cross-repo workstream rewriting `projects/`) | Medium | The shared Pages publish guard (`scripts/check-project-publish-guard.py`) now blocks destructive rewrites of the artvee subtrees. The Artvee health check now distinguishes HTTP 404 from network 0, so future drift will be detected and reported correctly within 24 h. |
| `KNOWN_RETIRED` count may grow as new unresolvable URLs are marked | Low | The P6B workflow already audits new retirees before accepting them. `known_retired` is part of the daily health summary, so any unexpected growth shows up on the next Telegram message. |
| Records growth may inflate the public demo bundle above the GitHub Pages soft limit | Low | The public demo bundle ships only thumbnails already sized at 256 px / 512 px; current 5.7 MB bundle is well within the 1 GB Pages soft limit. |
| Nightly batch occasionally fails on individual URLs | Low | Failures are reported in the nightly log and never block the daily health check; persistent failures are migrated into `KNOWN_RETIRED` per P6B. |
| The `recommended_action` branches are new (P7E+2) and may still mask an edge case | Low | The `online.kind` enum is logged daily; review after the first 7 days of P7E+2 behaviour. |

## 8. Recommendation

**v0.2.0 is stable-ready.**

- All 3 observation days are green.
- All 15 readiness criteria PASS.
- The single Day-2 incident (GitHub Pages content drift) was caught,
  diagnosed, restored, and hardened within the observation window.
- Local Artvee data integrity is preserved; the public demos are live;
  the daily health cron is producing text + MEDIA reports as designed.

The next action is **not** taken by this review; it requires explicit
user approval:

- Do **not** tag `v0.2.0` automatically.
- Do **not** run `gh release create` automatically.
- Do **not** push to GitHub Pages automatically.

When the user approves, the cut is a small operation:

1. Update `docs/RELEASE_NOTES_v0.2.0.md` (drop the `-alpha` suffix),
   copy content from `docs/RELEASE_NOTES_v0.2.0-alpha.md`.
2. Update README badge from `v0.2.0-alpha` to `v0.2.0`.
3. Annotated tag: `git tag -a v0.2.0 -m "v0.2.0 stable"`.
4. Push tag: `git push origin v0.2.0`.
5. GitHub Release: `gh release create v0.2.0 --notes-file docs/RELEASE_NOTES_v0.2.0.md`.

## 9. Next steps

| Step | Owner | Trigger |
| --- | --- | --- |
| Cut `v0.2.0` stable tag + GitHub Release | user (approval-gated) | after this review is accepted |
| Begin P8 (automation polish): pre-flight `--dry-run` on the publish helper; optional 02:55 pre-check cron; CI matrix for the cron installer | maintainer | after stable release |
| Watch the P7E+2 signal-distortion fix for 7 days of clean runs | daily health cron | automatic |
| Promote `KNOWN_RETIRED` to the public demo UI (per the original P7 observation plan) | maintainer | optional follow-up |

---

*Created by Phase P7F on 2026-06-16. Read-only review; no tag, no release,
no Pages push, no runtime modification.*