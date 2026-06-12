# Artvee Gallery · Retrospective

> Phase-by-phase lessons, impact analysis, open questions, and the
> recommended next phase. This is the working partner to
> [CASE_STUDY.md](CASE_STUDY.md) — the case study tells the story,
> the retrospective extracts the lessons.

## 1. What changed

A 5-minute one-off `bash` downloader turned into a 41-file open-source
project with two public routes, a CI gate, and a daily digest — in
roughly one working day. The transformation was not just code; it
was the *vocabulary* of the project. "Scraped data" became "a local
archive". "Demo" became "two curated public routes". "Cron job"
became "an observable deterministic pipeline".

The single most useful question we kept asking was: **"what is the
shape of the smallest thing we can put in front of a stranger that
still represents this project honestly?"** The answer kept getting
smaller (1.4 GB → 5.7 MB → 324 KB), and each reduction surfaced a
new design question.

## 2. Key lessons

### 2.1 先稳定自动化，再做展示层 (Stabilize automation before showcase)

The first iteration of the nightly batch was unstable — random
network failures, no idempotency, no observability. We briefly
considered shipping the public demo before fixing the batch. That
would have been a mistake: a public demo of a broken pipeline is
worse than no demo at all, because it advertises a promise the
project cannot keep.

The right order was:

1. Make the batch **idempotent** (re-runs do not duplicate or skip).
2. Make the batch **observable** (a single log file, a single
   summary line, a single Telegram post).
3. Make the batch **deterministic** (a 02:00 run produces the same
   `digests/` output as a 14:00 run with the same input state).
4. **Only then** build the public surface on top of it.

### 2.2 通知文案也是系统可靠性的一部分 (Notification copy is part of system reliability)

A Telegram notification that says "20 success" with no context is
worse than no notification. We had to learn this the hard way: the
first wrapper post said "20" and we had to look at the log to
figure out which 20, from which categories, with what failure mode.
The second iteration added "统计 / 图库 / 灵感" headers and a
compact, greppable one-liner. After that, the Telegram channel
became a real signal, not noise.

The lesson generalizes: any human-readable surface in a system is a
*reliability component*, not a UI afterthought. If the message is
ambiguous, the operator will eventually misread it and the system
will fail in a way that is harder to debug because the failure
happened *in the operator's head*.

### 2.3 大资产项目必须区分 source code 和 generated assets (Big-asset projects must separate code from generated data)

This is the single most important rule. Once the local archive
crossed 100 MB, the temptation to "just commit the images, it's
easier" became real. We resisted. The `.gitignore` for
`images/`, `metadata/`, `thumbs/`, `dist/`, `digests/`, `logs/`,
`inbox/`, and `web/data/*.json` is not negotiable. The CI gate
makes it enforceable.

The general rule: **the git repo is the source-of-truth definition
of the project, and the source-of-truth must be small enough to
read in one sitting.** A 1.4 GB git repo is not a project; it is
a database pretending to be a repo.

### 2.4 Public demo 应该先轻量化，而不是直接公开完整数据 (Public demo should be lean first, not a direct dump of full data)

The naïve thing to do with an archive is to publish the archive.
We did not. The public demo is a curated 100-piece selection; the
daily digest is a 5-piece selection. The original 1.4 GB is the
private layer; 5.7 MB is the public gallery; 324 KB is the public
digest. Three tiers, three audiences:

- **1.4 GB** — the local archive (the maintainer, on one machine).
- **5.7 MB** — the public gallery (a curious stranger, with no
  context).
- **324 KB** — the daily digest (a returning visitor, who wants a
  small daily dose).

The 100× and 18,000× reductions are not optimizations. They are
*editing*. They are the answer to "what is this archive actually
for?".

### 2.5 Digest 让素材库变成内容系统 (Digest turns an archive into a content system)

This was the unlock. Once a day, 5 representative works are
selected from the archive and rendered as a digest page. The page
is small enough to read in 30 seconds, has a date in its URL, and
accumulates over time. After 30 days, the digest archive is a
*publication*, not a *log*.

The mental model shifts: the project is not "an archive you can
browse" but "a publication that publishes one issue per day". The
difference matters because it changes how the maintainer thinks
about growth — adding 760 more pieces is no longer "more archive";
it is "more future digest issues".

### 2.6 CI gate 的价值是防止未来误提交 generated data (CI gate's value is preventing future accidental commits of generated data)

The first time the CI gate failed, we had shipped the workflow
before the full code tree. The fix was trivial. The *value* of
the failure was not the fix; it was the **proof that the gate
works**. A gate that never fires is not a gate; it is a comment.

The 4-rule readiness check is intentionally narrow. It does not
lint, does not type-check, does not test. It only checks the
boundary between "code" and "everything else". That narrow focus
is what makes it trustworthy: it will not be flaky, it will not
be bypassed, and it will not be ignored.

### 2.7 Verify metadata field mapping after any migration (P5A)

P4B fixed the filename collision by renaming winners and copying
metadata files. We verified that image paths were correct and
integrity checks passed. But we did **not** verify that the
`source_url` inside the copied metadata still matched the index
row's `source_url`. The build script preferred `meta.get("url")`
over `row.get("source_url")`, so stale metadata copies leaked
their old URLs into the web data.

**Fix**: swapped priority in `build_artvee_gallery.py` so the
index (the current state) takes precedence over metadata (which
may be a stale copy). Also added a post-rebuild source_url dupe
check to catch this class of bug early.

**Rule**: after any migration that copies or renames metadata
files, always verify that the key mapped fields (source_url,
title, artist) in the rebuilt web data match the index, not the
old metadata.

### 2.8 Audit counts may include .gitkeep placeholders (P5C)

The P5A orphan audit (`reports/runtime/p5a-legacy-orphans-
report.json`) reported 46 orphan files: 11 images + 11
metadata + 12 thumbs (256) + 12 thumbs (512). The P5C cleanup
script correctly excluded 2 `.gitkeep` files (one in
`thumbs/256/`, one in `thumbs/512/`) because they are not
image or metadata files. The actual orphan count to delete
was 44, not 46.

**Fix**: the P5C script uses `IMAGE_EXT` + `META_EXT`
allowlists (not just "is file") when scanning, so it
correctly ignores `.gitkeep`. The audit discrepancy is
benign (saved 2 files from being deleted).

**Rule**: when auditing "files to delete", always apply a
file-type filter, not just "is_file()". `.gitkeep`,
`README.md`, and other non-data placeholders are
intentional directory anchors and must never be removed
by an orphan-cleanup pass.

### 2.9 Data correctness is necessary but not sufficient (P5D)

After P5A (content healing) fixed the Le_rêve source_url
mislabelling, every record's `source_url` was technically
correct. But "data correct" ≠ "visually good". A 1×1 white
pixel, a corrupt 0-byte JPEG, a 4:1 banner, or a near-mono
gradient all have valid metadata but should not appear in a
public gallery.

P5D introduced visual quality checks (perceptual aHash,
average brightness, color entropy, dimensions) to flag
these "data is fine, image is bad" cases. The current
gallery is clean (756/756 risk=none), but the script is
now in place to surface problems as the gallery grows
(P5E: curation filters, P6: automation).

**Rule**: any "data correctness" pass must be paired with
a "visual quality" pass before a record is approved for
public export. P5A fixes the data; P5D verifies the
image. Together they enable safe automatic public demos.

## 3. Phase-by-phase impact analysis

### P1 · Local Gallery Browser

- **修改影响**: introduced the local UI shell, the JSON shape, and
  the thumbnail pipeline. Established the "code in git, data in
  folders" convention.
- **风险控制**: thumbnails are derived, never edited by hand. If
  the pipeline breaks, the source images are still in `images/`.
- **未触碰范围**: artvee.com, the public web, the night batch.

### P2 · Public Demo Export

- **修改影响**: added the curated-export step. The first time the
  project touched the public surface.
- **风险控制**: 100-piece cap, 256/512 thumb-only, no
  `images/`, no `metadata/`. The export script is read-only on
  sources.
- **未触碰范围**: the public web (publishing was a separate step
  in P3A), the night batch, the local UI.

### P3A · Public Demo Publish (GitHub Pages)

- **修改影响**: the first public route went live. The Pages repo
  gained a 5.7 MB static bundle under `projects/artvee-gallery-demo/`.
- **风险控制**: rsync is one-way (local → Pages repo), Pages repo
  is its own git history (no risk of contaminating the source
  repo).
- **未触碰范围**: the source repo, the night batch, the local UI.

### P3B · Daily Inspiration Digest

- **修改影响**: introduced the deterministic 5-pick digest, the
  round-robin category strategy, and the digest index in
  `web/data/digests.json`.
- **风险控制**: digest generation is pure-function-of-input; the
  same archive produces the same digest for the same date.
- **未触碰范围**: the public web, the night batch.

### P3C · Open-Source Readiness

- **修改影响**: the source repo went from "private local project"
  to "MIT-licensed public repo". 25 tracked files at the end.
- **风险控制**: the readiness check + a path-leak grep on body
  text. No generated data in the repo.
- **未触碰范围**: the local archive, the public web.

### P3D · GitHub Public Repo + CI + Release

- **修改影响**: repo pushed to <https://github.com/conanxin/artvee-gallery>,
  CI workflow added, `v0.1.0-alpha` tagged + released.
- **风险控制**: CI gate enforces the boundary on every push. Tag
  is re-pointable if a future release is found broken.
- **未触碰范围**: the local archive, the public web route (still
  in P3A's Pages repo), the night batch logic.

### P3E · Public Daily Digest Page + README Showcase

- **修改影响**: the second public route went live
  (<https://conanxin.github.io/projects/artvee-gallery-digest/>).
  README gained badges and screenshots. Pages repo's
  `projects/data.json` grew from 28 to 29 entries.
- **风险控制**: 5-thumb cap, 324 KB total, no `images/`, no
  `metadata/`, no `digests/` history. The export script includes
  a post-export leak check.
- **未触碰范围**: the source repo's code (no new tracked code;
  only docs and screenshots), the local archive, the night batch.

### P3F · Case Study + Retrospective + Methodology (this phase)

- **修改影响**: docs-only. 3 new docs (`CASE_STUDY`,
  `RETROSPECTIVE`, `LOCAL_FIRST_AGENT_PROJECT_PATTERN`),
  README + ROADMAP + PROJECT_STATUS lightweight updates.
- **风险控制**: no code changes, no script changes, no public
  surface changes. CI is the only verification, and it
  re-validates everything P3C-P3E established.
- **未触碰范围**: the local archive, the public web, the night
  batch, the export scripts, the readiness check.

## 4. Open questions

### 4.1 Manifest vs disk (760 vs 747) — RESOLVED in P4A, GATED in P4A+1, FIXED in P4B

**Resolution (P4A).** P4A found that the manifest holds 760
*unique* URLs (0 duplicates). The 13 missing entries are not
double-downloads; they are 13 *index/web* records that share a
local filename with a sibling record, and last-write-wins
silently overwrote 11 source images. The 13 records now point
to a sibling's image while keeping their own metadata. The 760
manifest entries are 760 *real* artvee URLs; the disk has 747
*unique basenames*; the gap is fully explained by 11 filename
collisions. See the P4A audit report.

**Gate (P4A+1).** P4A+1 froze the 11/13 fingerprint inside
`scripts/check_gallery_integrity.py` and wired it into the CI
workflow. Any new pattern fails the gate immediately; the 13
historical extras are tolerated. The CI step is runtime-aware
(SKIP on the open-source repo with no runtime data).

**Fix (P4B, 2026-06-12).** P4B is the **healing** step: it
replaces the human-readable `Artist_Title_Cat_Variant`
filename rule with a source-url-hashed stable id
(`<slug_artist>_<slug_title>_<category>_<variant>_<sha1(url)[:8]>`).
The new helper lives in `scripts/artvee_identity.py` and is
re-used by `run_artvee_nightly_batch.py` and
`download_artvee_selected.py`. `build_artvee_gallery.py`
derives the record `id` from the basename stem of
`local_image_path`, so it needed no change. The executor
(`scripts/execute_gallery_collision_migration.py`) renamed
11 winners via `shutil.copy2` (source kept for recovery),
re-downloaded 9 of the 13 losers via playwright, and dropped
the 4 unresolvable losers from the index/web data
(Playwright `Page.goto` 30s timeouts on the 4 URLs). The
fingerprint is now empty and all three integrity modes
(default / `--allow-known-duplicates` / `--strict`) exit 0.
The 736 non-collision files keep the legacy basename format
(mixed naming is documented and accepted for the P4B
commit; new downloads always use the new format).

**Lesson.** Build scripts that derive filenames from
human-readable strings are a footgun: distinct source URLs can
resolve to the same filename and silently overwrite each
other. Always derive filenames from a content-addressable
hash of the *source URL* (globally unique by construction);
keep the slugified title for readability only. The same
lesson applies to any local-archive project where the data
sources are identified by a stable remote URL.

### 4.2 Auto-public-demo refresh

The two public routes are published via manual
`rsync + commit + push`. Automation is feasible but requires a
personal access token in cron or a GitHub Actions workflow on
the Pages repo. Both require a secret-rotation policy first.
This is a P4B candidate.

### 4.3 Full object storage for the archive

The local archive is 1.4 GB on a single disk. If we ever want
multi-device access, or backup, or sharing, the natural next
step is to put the archive in object storage (S3 / R2 / COS).
This is a P4D candidate and a significant architectural shift
(local-first → cloud-mirrored).

### 4.4 Visual-model analysis

The digest currently uses hand-coded heuristics (round-robin
category, recent-pick). A vision model could produce richer
picks (composition, palette clustering, semantic similarity).
This is a P4C candidate and depends on the user having local
or affordable access to a vision model.

### 4.5 README language coverage

The README is English-only. A Chinese mirror would help local
users. Trivial to produce; the question is whether to
auto-translate or hand-edit.

## 5. Recommended next phase

**P4A — Manifest duplicate-id audit (read-only)**.

Why this first:

- It is the **only** known correctness issue. The public surface
  depends on the manifest, and a manifest with 13 phantom
  entries is technically a bug.
- It is **read-only**. No new dependencies, no new infrastructure.
  Just a script that joins the manifest against the disk and
  reports the delta.
- It is **bounded**. We know the size of the problem (13 entries)
  and the answer shape (a Markdown report).

A 1-day P4A followed by P4B (auto-publish) and P4C (digest
history) gives the project a clean forward path. P4D (object
storage) is a long-arc architectural shift and should wait
until the local-first story is fully debugged.

## 6. See also

- [CASE_STUDY.md](CASE_STUDY.md) — the project story
- [LOCAL_FIRST_AGENT_PROJECT_PATTERN.md](LOCAL_FIRST_AGENT_PROJECT_PATTERN.md) —
  the reusable methodology extracted from this project
- [ROADMAP.md](ROADMAP.md) — what's next
