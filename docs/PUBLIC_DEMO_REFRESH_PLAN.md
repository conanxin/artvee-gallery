# Public Demo Refresh Plan

> Companion doc to the P4C verification. Defines how the public
> Gallery Demo and Daily Digest Demo should be refreshed after
> local nightly runs. P4C only designed; P4D will implement.

## 1. Purpose

This document explains how the two public routes
([Gallery Demo](https://conanxin.github.io/projects/artvee-gallery-demo/)
and
[Daily Digest Demo](https://conanxin.github.io/projects/artvee-gallery-digest/))
should be refreshed when the local archive changes.

The aim is to keep the public surface **lightweight, curated, and
gated** — not to mirror the full local archive. The local archive
stays local-first; the public surface is a tasteful teaser.

## 2. Current state

- **Local gallery** updates automatically after the nightly batch
  (`scripts/run_artvee_nightly_batch.py`).
- **Daily digest** is generated locally after the nightly batch
  (`scripts/build_artvee_daily_digest.py`).
- **Public GitHub Pages demos** are currently **manually exported
  and published**:
  - `scripts/export_artvee_gallery_public_demo.py` →
    `dist/artvee-gallery-public-demo/`
  - `scripts/export_artvee_digest_public_page.py` →
    `dist/artvee-gallery-digest-public/`
  - `rsync` to `conanxin.github.io` repo, commit, push.
- **Full images and metadata are NOT published** — only the
  selected 100 records (gallery) or 5 picks (digest) and their
  256 / 512 thumbs.
- **No public-side leaks**: P4C path-integrity check verified
  100 / 100 records, 0 leaks, 0 missing files.

## 3. Why not auto-publish immediately

P4C explicitly does **not** auto-publish, for four reasons:

1. **Avoid pushing accidental runtime data.** The P3C readiness
   check blocks runtime data from being committed to
   `artvee-gallery`, but a misconfigured `rsync` or `cp` could
   leak `images/` / `metadata/` / `web/data/` to the public Pages
   repo. Manual approval is the only zero-config guard.
2. **Avoid publishing unresolved migration artifacts.** P4B had
   4 unresolved losers dropped from the index. If we auto-publish
   on the same commit, a transient 4-extra-records state could
   leak before the cleanup pass runs.
3. **Keep public demo lightweight and curated.** The current
   "100 diverse records" rule is hand-picked. Auto-publishing
   would tempt "just publish everything" which dilutes the demo.
4. **Allow post-migration observation first.** P4B / P4C changed
   filenames. A short observation window (1-2 days) before
   auto-publish catches regressions early.

## 4. Refresh modes

### Manual refresh (current)

```bash
# In the artvee-gallery repo
python3 scripts/build_artvee_gallery.py --mode local
python3 scripts/export_artvee_gallery_public_demo.py --limit 100 --strategy diverse
python3 scripts/export_artvee_digest_public_page.py
# Inspect dist/, then manually:
rsync -a --delete dist/artvee-gallery-public-demo/ <pages-repo>/projects/artvee-gallery-demo/
rsync -a --delete dist/artvee-gallery-digest-public/ <pages-repo>/projects/artvee-gallery-digest/
cd <pages-repo> && git add -A && git commit -m "demo: refresh from $(date -I)" && git push
```

- ✅ Simple, zero-config
- ✅ Reuses existing wrappers
- ❌ Requires user to remember to do it
- ❌ No audit trail beyond commit message

### Semi-automatic refresh (P4D target)

- Demo package is generated automatically (e.g. by the nightly
  wrapper at 02:30, after the 02:00 nightly batch)
- GitHub Pages push requires an explicit `git push` approval
  (manual command, possibly a `confirm-refresh.sh` script that
  prints a diff before pushing)
- All 5 mandatory gates (Section 5) must pass before the
  `confirm-refresh.sh` script is offered to the user

```bash
# Nightly wrapper end (02:30)
python3 scripts/build_artvee_gallery.py --mode local
python3 scripts/export_artvee_gallery_public_demo.py --limit 100 --strategy diverse
python3 scripts/export_artvee_digest_public_page.py
bash scripts/confirm_demo_refresh.sh   # prints diff, gates, asks for y/N
# User runs `cd <pages-repo> && git push` only if y
```

- ✅ Most checks happen automatically
- ✅ User still has the final say
- ✅ Audit trail is the git log of the Pages repo
- ❌ Still requires user attention daily

### Fully automatic refresh (long-term)

- Nightly batch success triggers a GitHub Actions workflow
  (`publish-demo.yml`) on the Pages repo via
  `repository_dispatch` or PAT cross-repo write
- Workflow pulls the latest `dist/` artifact from a
  `artvee-gallery` release or workflow run, rsyncs to
  `projects/`, commits, pushes
- All 5 mandatory gates (Section 5) must pass in the workflow
- A daily Telegram summary reports the push

```yaml
# conanxin.github.io/.github/workflows/sync-demo.yml
on:
  repository_dispatch:
    types: [artvee-demo-refresh]
jobs:
  pull:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
        with: {repository: 'conanxin/artvee-gallery', ref: main, path: 'src'}
      - run: |
          cp -r src/dist/artvee-gallery-public-demo projects/artvee-gallery-demo/
          cp -r src/dist/artvee-gallery-digest-public projects/artvee-gallery-digest/
      - run: |
          git add -A
          git commit -m "demo: refresh from artvee-gallery @ $(date -I)" || true
          git push
```

- ✅ Zero user attention
- ✅ Audit trail is the GitHub Actions log + Pages repo git log
- ❌ Needs a `repository_dispatch` token or PAT with
  cross-repo write
- ❌ Needs the secret-rotation policy (P4D prerequisite)

## 5. Required gates before publishing

Any refresh mode (manual, semi-auto, full-auto) must pass these
gates before any `git push` to `conanxin.github.io`:

1. **`check_gallery_integrity.py --strict` PASS** — no new
   duplicate-id / collision patterns.
2. **`check_open_source_ready.py` PASS** — no tracked runtime
   data, no path leaks, no secret keywords, no oversized files.
3. **No local path leaks in the demo package** — grep
   for the local-path forbidden substrings (defined in
   `scripts/check_open_source_ready.py`) recursively in the
   exported `dist/`; must return 0 matches.
4. **Demo package size threshold** — gallery ≤ 10 MB,
   digest ≤ 1 MB. Otherwise refuse to push.
5. **No full images / metadata copied** — only 256 / 512 thumbs
   for the selected records. `find dist/ -name "*.jpg" -size
   +50k` should return only the 5 digest full-size thumbs (if
   any).
6. **Unresolved losers not included** — check
   `reports/runtime/p4b-unresolved-losers.json` (and any future
   unresolved log) and confirm none of those
   `source_url`s appear in the exported `data/artworks.json`.

## 6. Proposed P4D

**P4D = semi-automatic public refresh with explicit approval.**

Concretely:

1. Add `scripts/confirm_demo_refresh.sh` that:
   - Re-runs all 5 mandatory gates
   - Prints a `git diff` of what would be pushed to Pages repo
   - Asks for explicit `y/N` confirmation
2. Extend `scripts/artvee_nightly_wrapper.sh` to call
   `confirm_demo_refresh.sh` after the digest step (so the user
   sees the prompt at 02:30 instead of having to remember to
   run it manually)
3. Document the manual refresh + the new auto-prompt in
   `docs/DEVELOPMENT.md`
4. **Pre-requisite (P4D blocker):** write
   `docs/SECRET_ROTATION_POLICY.md` for any future PAT / webhook
   token (full-auto mode only). P4D's semi-auto mode does NOT
   need secrets; it's just a local confirmation prompt.

### Why semi-auto first, not full-auto

- Semi-auto avoids secret management entirely (no PAT in cron,
  no webhook in CI)
- It still removes the "remember to refresh" friction
- It produces a daily audit trail (Pages repo commit log) that
  the full-auto mode can later consume
- Full-auto becomes a thin wrapper around the same `confirm_`
  script — once we have a secret-rotation policy

## 7. Open questions for P4D

- **Approval channel**: a terminal `y/N` prompt, or a Telegram
  inline keyboard (`[approve] [skip]`) in the nightly summary?
  The Telegram approach integrates with the existing notify
  bridge but requires a small server to receive the answer.
- **Diff size cap**: 50 MB? 100 MB? If a theme bundle is
  exported (a P4E / P4F candidate), the cap may need to flex.
- **Schedule**: only after nightly, or also on demand (e.g. a
  new artwork downloaded outside the nightly window)? The
  current plan only supports the post-nightly window.
- **Theme bundles**: when / if P4E (themed bundle exporter)
  lands, where do the bundles live in the Pages repo? The
  current `projects/` layout has only the gallery + digest.

## 7. P4D first semi-automatic refresh · 2026-06-12

The first end-to-end run of the refresh path landed on
2026-06-12. This section records the concrete command, the
post-push state, and what it proves about the design above.

**Exporter invocation (semi-automatic, no wrapper yet):**

```bash
cd <artvee-repo>     # e.g. the local clone of conanxin/artvee-gallery
rm -rf /tmp/artvee-gallery-demo-p4d
python3 scripts/export_artvee_gallery_public_demo.py \
    --limit 100 --strategy diverse \
    --out-dir /tmp/artvee-gallery-demo-p4d --base-url . \
    --exclude-duplicate-source-url-groups \
    --require-unique-source-url

rm -rf /tmp/artvee-gallery-digest-p4d
python3 scripts/build_artvee_daily_digest.py \
    --strategy diverse --select 5 --candidate-limit 20 \
    --out-dir digests
python3 scripts/export_artvee_digest_public_page.py \
    --out-dir /tmp/artvee-gallery-digest-p4d --base-url .
```

**Pre-publish gates (§ 5) result on 2026-06-12:**

| Gate | Result |
| --- | --- |
| 1. `check_gallery_integrity.py --strict` | PASS (post-P4B: 756 records, 0 dup ids) |
| 2. `check_open_source_ready.py` | PASS (no tracked runtime data; no leaks) |
| 3. Gallery /tmp leak grep | PASS (no forbidden substrings) |
| 4. Digest /tmp leak grep | PASS (no forbidden substrings) |
| 5. JSON validity | PASS (artworks, stats, digests all parse) |
| 6. No files >2M | PASS (largest single file is a 512 thumb) |
| 7. Public-safety guard (duplicate source_url group + uniqueness) | PASS (3 groups / 6 records dropped incl. Le_rêve URL label bug; 100/100 unique ids and unique source_urls) |

**Push + online verification:**

| Surface | Result |
| --- | --- |
| `conanxin.github.io` commit | `5a8d938` ("Refresh Artvee Gallery public demos after collision fix") |
| Gallery URL | <https://conanxin.github.io/projects/artvee-gallery-demo/> → `200` |
| Gallery `data/artworks.json` | `200`, 100 records |
| Gallery `data/gallery_stats.json` | `200` |
| Gallery `app.js`, `style.css` | `200` |
| Gallery thumbs (sample: 256 + 512) | `200` |
| Digest URL | <https://conanxin.github.io/projects/artvee-gallery-digest/> → `200` |
| Digest `digest.html`, `digest.md`, `data/digests.json` | `200` |
| Digest thumb (sample 512) | `200` |

**What P4D proved:**

- The semi-automatic path works end-to-end. Only the final
  `git push` to `conanxin.github.io` is human; everything else
  is script-driven and verifiable before the push.
- The public-safety flags work: the Le_rêve URL label bug
  (P4A+1 § 6.4) is not in the public gallery, even though it
  is still present in `web/data/artworks.json`.
- The 4 unresolved losers are still in
  `reports/runtime/p4b-unresolved-losers.json`; the P4D run
  did not retry them.
- The full 100-record Gallery stays at ~5.7M and the 5-record
  Digest stays at ~300K — both well under the GitHub Pages
  soft cap and CDN-friendly.

**What P4D did *not* prove yet (still open):**

- The `confirm_demo_refresh.sh` wrapper and the nightly
  02:30 hook in `artvee_nightly_wrapper.sh` are not yet
  implemented. P4D+1 (added in
  [ROADMAP.md](../ROADMAP.md) § 2) is the follow-up bucket
  for full unattended daily prompting.
- The Le_rêve URL label bug is still present in
  `web/data/artworks.json`; the build-script fix is deferred
  to P5+.
