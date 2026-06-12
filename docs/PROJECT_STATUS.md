# Artvee Gallery · Project Status

> Quick-reference phase markers and the last-known-good nightly
> snapshot. For the broader plan, see
> [docs/ROADMAP.md](docs/ROADMAP.md). For deep-dive docs, see the
> `docs/GALLERY_*.md` series. For the project story and the
> methodology extracted from this project, see
> [docs/CASE_STUDY.md](docs/CASE_STUDY.md),
> [docs/RETROSPECTIVE.md](docs/RETROSPECTIVE.md), and
> [docs/LOCAL_FIRST_AGENT_PROJECT_PATTERN.md](docs/LOCAL_FIRST_AGENT_PROJECT_PATTERN.md).

## Phase markers

| Phase | Description | Status | Date | Verification report |
| --- | --- | --- | --- | --- |
| **P1** | Local Gallery Browser | ✅ PASS | 2026-06-11 | `<workspace>/reports/artvee-gallery-p1-local-browser-20260611.md` |
| **P2** | Public Demo Export | ✅ PASS | 2026-06-11 | `<workspace>/reports/artvee-gallery-p2-public-demo-export-20260611.md` |
| **P3A** | Public Demo Publish (GitHub Pages) | ✅ PASS | 2026-06-11 | `<workspace>/reports/artvee-gallery-p3a-public-demo-publish-20260611.md` |
| **P3B** | Daily Inspiration Digest | ✅ PASS | 2026-06-11 | `<workspace>/reports/artvee-gallery-p3b-daily-digest-20260611.md` |
| **P3C** | Open-Source Readiness | ✅ PASS | 2026-06-12 | `<workspace>/reports/artvee-gallery-p3c-open-source-readiness-20260612.md` |
| **P3D** | GitHub Public Repo + CI + Release | ✅ PASS | 2026-06-12 | `<workspace>/reports/artvee-gallery-p3d-github-public-repo-20260612.md` |
| **P3E** | Public Daily Digest Page + README showcase | ✅ PASS | 2026-06-12 | `<workspace>/reports/artvee-gallery-p3e-daily-digest-public-page-20260612.md` |
| **P3F** | Final Case Study and Project Retrospective | ✅ PASS | 2026-06-12 | `<workspace>/reports/artvee-gallery-p3f-case-study-retrospective-20260612.md` |
| **P4A** | Manifest duplicate-id read-only audit | ✅ PASS (audit only) | 2026-06-12 | `<workspace>/reports/artvee-gallery-p4a-manifest-duplicate-audit-20260612.md` |
| **P4A+1** | Gallery integrity CI gate (filename-collision / duplicate-id) | ✅ PASS | 2026-06-12 | `<workspace>/reports/artvee-gallery-p4a1-integrity-gate-20260612.md` |
| **E2E** | Nightly Cron Auto-Run | ✅ PASS | 2026-06-12 | `<workspace>/reports/artvee-nightly-auto-run-verification-2026-06-12.md` |

## Last-known-good nightly snapshot

| Metric | Value |
| --- | --- |
| `downloaded` | 760 |
| `failed` | 0 |
| `pending` | 530 |
| `not_selected` (a.k.a. `skipped` in wrapper stats) | 1271 |
| Batch size | 20 (all SUCCESS) |
| Wall time | about 5 minutes |
| Cron entry | `0 2 * * * bash scripts/artvee_nightly_wrapper.sh batch` |
| Time zone | `CRON_TZ=Asia/Shanghai` |

## Public surfaces

| Surface | URL | Refresh cadence |
| --- | --- | --- |
| Public demo (curated subset, thumbnails only) | <https://conanxin.github.io/projects/artvee-gallery-demo/> | Manual re-export |
| Public daily digest (latest 5-pick, 324 KB) | <https://conanxin.github.io/projects/artvee-gallery-digest/> | Manual re-export |
| Public GitHub repository | <https://github.com/conanxin/artvee-gallery> | Per-push (CI gated) |
| Public release | <https://github.com/conanxin/artvee-gallery/releases/tag/v0.1.0-alpha> | Once per release |
| Local gallery UI | `bash scripts/serve_artvee_gallery.sh` then `http://localhost:8000/` | On every local rebuild |

## Repository readiness (post-P3C, re-validated at P3F)

| Check | Result |
| --- | --- |
| `LICENSE` present | ✅ MIT |
| `README.md` present and self-describing | ✅ |
| `.gitignore` consolidated | ✅ |
| `docs/` complete (architecture, boundaries, roadmap, dev, status, release notes, case study, retrospective, methodology) | ✅ |
| `examples/` present and valid | ✅ |
| `scripts/check_open_source_ready.py` exits 0 | ✅ |
| Tracked files include any generated data | ❌ (intentional) |
| Local-machine paths in tracked non-source files | ❌ (none) |
| Hardcoded wrapper paths (`$HOME/...`) | ❌ (replaced with `BASE_DIR` derivation) |

## CI gate (post-P4A+1)

| Check | Result |
| --- | --- |
| Workflow present | ✅ `.github/workflows/open-source-ready.yml` |
| Latest run on `main` | ✅ success |
| Workflow runs `py_compile` × 6 (added `export_artvee_digest_public_page.py` + `check_gallery_integrity.py`) | ✅ |
| Workflow runs `bash -n` × 2 | ✅ |
| Workflow runs readiness check | ✅ |
| Workflow runs **gallery integrity check** (`--allow-known-duplicates`, runtime-aware) | ✅ |
| Workflow validates `examples/*.sample.json` shape | ✅ |

## Gallery integrity fingerprint (post-P4A, frozen)

> The P4A audit discovered a historical filename-collision pattern
> in the local index/web data: 11 dupe groups, 13 extra rows. The
> 760 manifest URLs are unique; the dupe is in the *index / web*
> layer. The collision is **frozen** as a known fingerprint inside
> `scripts/check_gallery_integrity.py`. Any new pattern fails the
> CI gate immediately.

| Field | Frozen value |
| --- | --- |
| manifest downloaded rows | 760 |
| manifest unique URLs | 760 |
| index rows | 760 |
| index unique `local_image_path` basenames | 747 |
| index dupe groups | 11 |
| index dupe extra rows | 13 |
| web records | 760 |
| web unique ids | 747 |
| web dupe id groups | 11 |
| web dupe extra rows | 13 |
| disk images | 747 |
| disk metadata | 747 |
| disk thumbs 256 | 747 |
| disk thumbs 512 | 747 |

## Open issues (post-P4A+1)

- **Historical 11 filename collisions**: 13 winner/loser records
  in index/web show a sibling image (winner) with their own
  metadata (loser). The 13 dupe rows are frozen; the 11 underlying
  original images were silently overwritten and need re-download
  if the user wants full recovery. See
  [docs/RETROSPECTIVE.md](docs/RETROSPECTIVE.md) § 4.1 and the
  P4B entry in [docs/ROADMAP.md](docs/ROADMAP.md).
- **Public demo refresh is manual**: requires `rsync + commit +
  push` of the Pages repo. Auto-publish deferred to P4B-or-later
  pending a secret-rotation policy.

## How to refresh this file

This file is hand-maintained and is updated whenever a new phase
lands or the nightly snapshot changes meaningfully. The next
refresh is expected on the P4B cut.
