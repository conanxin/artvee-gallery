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

## 8. P4D+1 · Confirm flow + 02:30 nightly hook · 2026-06-12

P4D+1 introduces `scripts/confirm_demo_refresh.sh` and a
**local-only nightly hook** that prepares a public demo
candidate every night at 02:30, but does **not** push it to
GitHub Pages. The hook bridges "what P4D did manually once"
to "what the user might do every morning".

### 8.1 What the hook does

At 02:30 Asia/Shanghai every day, the hook runs:

```bash
cd <artvee-repo> \
  && bash scripts/confirm_demo_refresh.sh --no-telegram \
       >> logs/confirm_demo_refresh/cron_stderr.log 2>&1
```

`--no-telegram` is used so the hook can be tested during the
day without spamming the channel; the script still writes the
report, and a separate manual `bash scripts/confirm_demo_refresh.sh`
without `--no-telegram` will send a Telegram summary.

The script's pipeline is:

1. **Preflight 1** — `check_open_source_ready.py` must PASS
   (no tracked runtime data, no leaks, no big files).
2. **Preflight 2** — `check_gallery_integrity.py --strict`
   must PASS (no id / image / thumb dupe groups).
3. **Build local digest** — `build_artvee_daily_digest.py`
   is idempotent on a given date; overwrites `digests/`.
4. **Export Gallery candidate** to
   `dist/refresh-candidates/YYYY-MM-DD/gallery/` using
   the P4D public-safety flags
   (`--exclude-duplicate-source-url-groups
   --require-unique-source-url`).
5. **Export Digest candidate** to
   `dist/refresh-candidates/YYYY-MM-DD/digest/`.
6. **QA · Gallery** — re-asserts: 100 records, 200 thumbs,
   0 dupe id / source_url groups, 0 Le_rêve records,
   0 local-path leaks, 0 missing thumbs, size < 20 MB
   hard / 10 MB soft.
7. **QA · Digest** — re-asserts: 5 picks, 5 thumbs,
   0 leaks, 0 missing thumbs.
8. **Write report** to
   `logs/confirm_demo_refresh/report_YYYY-MM-DD.md`.
9. **Telegram summary** (skipped with `--no-telegram`).

### 8.2 What the hook does *not* do

- ❌ No `git push` to `conanxin.github.io`.
- ❌ No `rsync` to the Pages repo.
- ❌ No modification of `web/data/` / `images/` / `metadata/`.
- ❌ No retry of the 4 unresolved losers.
- ❌ No download / refill / batch re-run.
- ❌ No use of PAT / webhook / CI cross-repo write.

The candidate is a **view-only snapshot** that the user can
inspect, then either publish manually (P4E) or discard.

### 8.3 Manual publishing flow

After the 02:30 hook writes a candidate, the user (in a daytime
session, with eyes on it) can publish it with:

```bash
rsync -a --delete \
  <artvee-repo>/dist/refresh-candidates/YYYY-MM-DD/gallery/ \
  <artvee-pages-repo>/projects/artvee-gallery-demo/
rsync -a --delete \
  <artvee-repo>/dist/refresh-candidates/YYYY-MM-DD/digest/ \
  <artvee-pages-repo>/projects/artvee-gallery-digest/
# Edit <artvee-pages-repo>/projects/data.json (updated + summary).
cd <artvee-pages-repo> \
  && git add projects/artvee-gallery-{demo,digest} projects/data.json \
  && git commit -m 'Refresh artvee public demo for YYYY-MM-DD' \
  && git push
# wait ~90s for CDN (P6D), then curl all 12 endpoints.
```

The 90s default (was 60s) reflects a measured cold-cache
recovery pattern on GitHub Pages + jsDelivr caching. In
practice we observed occasional 60s+30s manual follow-up
when 60s was insufficient. 90s brings the first-pass
verification to ≥95% success on a clean push, and the
remaining stragglers fall back to a 90s retry built into
`wait_and_curl()` — see the implementation in
`scripts/publish_demo_refresh_candidate.sh` (flag:
`--cdn-wait N`, default 90, range 0..600).

This is exactly the P4D publish path, but driven from a
**date-named candidate directory** instead of
`/tmp/artvee-gallery-demo-p4d/`.

### 8.4 Idempotency

- `dist/refresh-candidates/YYYY-MM-DD/` is overwritten each
  run for the same date. The first candidate of the day
  always wins; later runs are no-ops if nothing changed.
- `logs/confirm_demo_refresh/` is append-only, with one log
  per run (`*_YYYYMMDD_HHMMSS.log`) and one Markdown report
  per date (`report_YYYY-MM-DD.md`).
- The 02:30 hook is a candidate builder, not a publisher.
  Re-running it never produces a second publication.

### 8.5 Failure behavior

- If preflight 1 (open-source readiness) fails, the script
  exits non-zero and writes a `❌` Telegram summary
  (unless `--no-telegram`). No candidate is built.
- If preflight 2 (integrity) fails, same as above.
- If the gallery export itself fails, the candidate directory
  is left in an incomplete state and the report flags it.
- If QA fails (e.g. size > 20 MB, Le_rêve guard trips,
  leak detected), the report is written but the **Telegram
  summary flips to `❌`** and the overall exit is non-zero.
  The candidate is **not** auto-removed; the user can
  inspect the report and decide.

### 8.6 Open after P4D+1

- P4E (optional): the manual publish step in § 8.3 could be
  packaged into `scripts/publish_demo_refresh.sh --date ...`,
  but only after a secret-rotation policy is in place. Until
  then, publish stays manual.
- P5+ : retry the 4 unresolved losers, fix the Le_rêve
  source_url label bug in `web/data/artworks.json` build path,
  clean up the 11 legacy orphan files.
- Cron log retention: `logs/confirm_demo_refresh/` will grow
  ~10 KB / day. A monthly prune script is left for a future
  phase.

## 9. P4E · Approved publish helper (2026-06-12)

P4E turns the P4D+1 candidate into a real Pages publication,
with **explicit `--approve` required** and a `--dry-run` mode
that previews the exact `rsync` + `git` operations.

### 9.1 What the helper does

`scripts/publish_demo_refresh_candidate.sh` runs:

1. **Candidate QA** (re-read from `dist/refresh-candidates/`)
   - Gallery: 100 records, 200 thumbs, 0 dupe id/source_url,
     0 Le_rêve, 0 leaks, 0 missing, size < 20 MB.
   - Digest: 5 picks, 5 thumbs, 0 leaks, 0 missing, size < 5 MB.
2. **Pages repo check** — verify branch + working tree clean.
3. **`data.json` check** — verify `artvee-gallery-demo` and
   `artvee-gallery-digest` entries exist.
4. **Plan** — if QA passes, print the planned `rsync`, `git
   add`, `git commit`, `git push` commands.
5. **Rsync** (if `--approve`) — `rsync -a --delete` from
   candidate to Pages repo directories.
6. **Update `data.json`** (if `--approve`) — set `updated` and
   `summary` fields.
7. **Git commit** (if `--approve`) — commit with message
   `Refresh Artvee public demos from approved candidate YYYY-MM-DD`.
   If no changes, skip with a clear message.
8. **Git push** (if `--approve` and not `--no-push`) — push to
   `origin <branch>`.
9. **Online verification** (if pushed) — wait 60s for CDN,
   then `curl -I` all 9 gallery + digest endpoints + 1 sample
   thumb. If first check fails, wait 60s and retry once.
10. **Report** — write `logs/confirm_demo_refresh/publish_YYYY-MM-DD.md`.

### 9.2 Security model

| Flag | rsync | commit | push | online verify |
| --- | --- | --- | --- | --- |
| (none) / `--dry-run` | ❌ | ❌ | ❌ | ❌ |
| `--approve --no-push` | ✅ | ✅ | ❌ | ❌ |
| `--approve` | ✅ | ✅ | ✅ | ✅ |

Without `--approve` the script runs in **dry-run mode by
default** (no `--dry-run` needed, but `--dry-run` can be used
for extra clarity). This guarantees that a mistyped command
cannot accidentally publish.

### 9.3 Manual publish workflow

```bash
# 1. Inspect the candidate (generated by P4D+1 at 02:30)
ls dist/refresh-candidates/2026-06-12/

# 2. Dry-run: preview the publish plan without touching Pages
bash scripts/publish_demo_refresh_candidate.sh \
    --date 2026-06-12 --dry-run

# 3. Approve: rsync + commit + push + online verify
bash scripts/publish_demo_refresh_candidate.sh \
    --date 2026-06-12 --approve

# 4. Or commit-only (no push) for daytime review
bash scripts/publish_demo_refresh_candidate.sh \
    --date 2026-06-12 --approve --no-push
```

### 9.4 What the helper does *not* do

- ❌ No Artvee download / refill / batch.
- ❌ No retry of 4 unresolved losers.
- ❌ No modification of `web/data/` / `images/` / `metadata/` /
  `index/` / `thumbs/` in the Artvee repo.
- ❌ No commit of runtime data to the Artvee repo.
- ❌ No auto-publish without `--approve`.
- ❌ No infinite retry on online verification (one 60s wait +
  one retry max).

### 9.5 Open after P4E

- P4F: Digest history index (30-day rolling window).
- P4G: Object storage planning.
- P5+: Unresolved loser retry + Le_rêve build fix.
