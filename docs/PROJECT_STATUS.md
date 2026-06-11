# Artvee Gallery · Project Status

> Quick-reference phase markers and the last-known-good nightly
> snapshot. For the broader plan, see
> [docs/ROADMAP.md](docs/ROADMAP.md). For deep-dive docs, see the
> `docs/GALLERY_*.md` series.

## Phase markers

| Phase | Description | Status | Date | Verification report |
| --- | --- | --- | --- | --- |
| **P1** | Local Gallery Browser | ✅ PASS | 2026-06-11 | `~/workspace/reports/artvee-gallery-p1-local-browser-20260611.md` |
| **P2** | Public Demo Export | ✅ PASS | 2026-06-11 | `~/workspace/reports/artvee-gallery-p2-public-demo-export-20260611.md` |
| **P3A** | Public Demo Publish (GitHub Pages) | ✅ PASS | 2026-06-11 | `~/workspace/reports/artvee-gallery-p3a-public-demo-publish-20260611.md` |
| **P3B** | Daily Inspiration Digest | ✅ PASS | 2026-06-11 | `~/workspace/reports/artvee-gallery-p3b-daily-digest-20260611.md` |
| **P3C** | Open-Source Readiness | ✅ PASS | 2026-06-12 | `~/workspace/reports/artvee-gallery-p3c-open-source-readiness-20260612.md` |
| **E2E** | Nightly Cron Auto-Run | ✅ PASS | 2026-06-12 | `~/workspace/reports/artvee-nightly-auto-run-verification-2026-06-12.md` |

## Last-known-good nightly snapshot

| Metric | Value |
| --- | --- |
| `downloaded` | 760 |
| `failed` | 0 |
| `pending` | 530 |
| `not_selected` (a.k.a. `skipped` in wrapper stats) | 1271 |
| Batch size | 20 (all SUCCESS) |
| Wall time | ~5 minutes |
| Cron entry | `0 2 * * * bash scripts/artvee_nightly_wrapper.sh batch` |
| Time zone | `CRON_TZ=Asia/Shanghai` |

## Public surfaces

| Surface | URL | Refresh cadence |
| --- | --- | --- |
| Public demo (curated subset, thumbnails only) | <https://conanxin.github.io/projects/artvee-gallery-demo/> | Manual re-export |
| Public daily digest | _planned (P3E)_ | — |
| Local gallery UI | `bash scripts/serve_artvee_gallery.sh` then `http://localhost:8000/` | On every local rebuild |

## Repository readiness (post-P3C)

| Check | Result |
| --- | --- |
| `LICENSE` present | ✅ MIT |
| `README.md` present and self-describing | ✅ |
| `.gitignore` consolidated | ✅ |
| `docs/` complete (architecture, boundaries, roadmap, dev, status, release notes) | ✅ |
| `examples/` present and valid | ✅ |
| `scripts/check_open_source_ready.py` exits 0 | ✅ |
| Tracked files include any generated data | ❌ (intentional) |
| Local-machine paths in tracked non-source files | ❌ (none) |
| Hardcoded wrapper paths (`$HOME/...`) | ❌ (replaced with `BASE_DIR` derivation) |

## Next planned phase

- **P3D** — Standalone public GitHub repository. See
  [docs/ROADMAP.md](docs/ROADMAP.md) § "Near-term".

## How to refresh this file

This file is hand-maintained and is updated whenever a new phase
lands or the nightly snapshot changes meaningfully. The next
refresh is expected on the P3D cut.
