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

### 2.18 (P7B+1) Observability must distinguish text / media / fallback

When a "MEDIA failed" line shows up in a Telegram summary, it
is **not** the same as a health failure. P7A had a single
`telegram_notify.sent` flag that conflated three different
tracks:

- whether the short text summary delivered,
- whether the Markdown report attached,
- whether the OpenClaw binary even resolved.

A MEDIA failure inside the daily health check meant a partial
degradation (you still got the text block), but it was
indistinguishable from "the whole notification died" — which
made it impossible to tell what to fix.

**Rule**: any notification path that has more than one
delivery track must report each track independently, with
`attempted` / `sent` / `message_id` / `error` for each. The
JSON key shape is the contract; the on-screen wording is the
diagnosis aid.

**Operational rule**: if a system can fail in N independent
ways and only has one health bit, every N≥2 outage looks the
same. Surface the bits.

### 2.19 (P7D) Large automation projects need release consolidation after phase accumulation

When a project accumulates many small phases (P1–P7B+1 here,
26 phase markers in v0.2.0-alpha), the repo becomes hard to
*consume* even though it is well-instrumented. A new reader
sees `README.md` with badge fragments, scattered notes, and
several half-finished release notes; there is no single
document that says "this is what you get if you clone at this
tag".

The release consolidation pass is what fixes that. It is
**not** a new feature; it is a documentation + tag + GitHub
Release pass. The deliverables are:

- `docs/RELEASE_NOTES_v<version>.md` — a single document that
  answers "what is in this release, what is not, what changed
  since the last release, and what is the next step".
- `CHANGELOG.md` — an aggregated changelog with a stable
  format (Added / Changed / Fixed / Operational / Security).
- Updated `README.md` (Latest release, docs index, operational
  model), `docs/PROJECT_STATUS.md` (P7D row + snapshot),
  `docs/ROADMAP.md` (P7D completed, next section), and a
  release checklist in `docs/DEVELOPMENT.md`.
- An annotated tag (`v0.2.0-alpha`) on the release commit,
  and a `gh release create` with the release notes.

**Rule**: after the last "feature" phase before a release,
schedule a consolidation phase whose only deliverable is
docs, tag, and release. The CI gate keeps it cheap (the same
`check_open_source_ready.py` runs on the release commit), so
there is no reason to skip it.

**Operational rule**: the failure-only fallback from P7B+1 is
the safety net for the observation window after the release.
If MEDIA delivery starts regressing in the field, the
fallback text is the canary.

### 2.20 (P7B+2) Fallback text should report delivery-state, but MEDIA must always use the staged allowlisted path

The 2026-06-18 03:00 daily health run taught a sharp lesson
about the difference between a *delivery* failure and a *path*
failure. The report *was* correctly staged into an
OpenClaw-allowlisted directory; the actual failure was a
transient `GatewayTransportError: gateway timeout after
10000ms` on the local OpenClaw gateway. Yet the original
`Report: <raw-path>` line in the fallback text pointed
operators at the raw `reports/runtime/daily-health/...` path
— which is *not* in the allowlist — which made the regression
look like a path problem when it was actually a transport
problem. And because the fallback itself hit the same gateway
error, the operator was left with *zero* observability: the
fallback that was supposed to tell them "MEDIA failed" also
failed silently.

Three lessons emerged:

1. **Staging is a precondition, not an alternative.** If the
   staging helper fails, the right behavior is to record
   `stage_failed: true` and never attempt to attach the raw
   path. The raw path is recorded in the report for diagnosis
   but never sent. This is the single most important
   property of the fix — it prevents the misleading
   `Report: <raw-path>` from ever appearing in the fallback
   text again.

2. **Classify the failure before deciding the response.**
   `transport` and `exit_nonzero` and `media_allowed` are all
   "MEDIA failed" at the surface, but the right recovery
   action is different for each. `transport` is an
   environmental issue (gateway, ws, network); re-trying
   immediately burns cron time. `media_allowed` is a config
   issue that needs an operator. `exit_nonzero` may be a
   transient openclaw bug. Collapsing them into one bit
   forced the operator to re-curl and grep every time.

3. **Defer, don't retry, on transport errors.** When the
   gateway is unreachable, the *next* cron run will tell us
   whether it recovered (its `text_summary` will succeed or
   fail). If it succeeds, flush the deferred fallback then.
   This turns a 10-180s wait per failed attempt into one
   filesystem write + one eventual flush. Cron self-heals
   without operator intervention.

**Rule**: any cross-process delivery code path (Telegram, web
push, email) must distinguish "the message is well-formed but
the recipient is unreachable" from "the message itself is
malformed". A retry loop that doesn't distinguish them will
both waste time and hide bugs.

**Operational rule**: never embed a raw (non-allowlisted)
path in a fallback message that an operator is expected to
read. If the delivery is going to fail, the fallback must
point at the *staged* path (so the operator can verify the
allowlist by hand) or, if staging itself failed, the *helper
output* (so they can re-run it).

### 2.21 (P7B+3) Transport failures should be recoverable, not auto-flushed by the next health run

P7B+2 was correct to defer the fallback on a transport
timeout rather than retry immediately, but it coupled the
*recovery* to the *next* daily health run. That had two
problems:

1. **The 03:00 cron gained a hidden side effect.** A
   successful `text_summary` would silently re-send a
   yesterday's pending file. The cron line looked strictly
   "report + log"; in practice it was also "and maybe send a
   one-off MEDIA we forgot about". For an approval-gated,
   read-only-by-default pipeline that is the wrong place to
   put surprise work.

2. **Operators had no inspectable handle.** If the
   `.fallback-pending-*.json` got stuck (wrong staged path,
   chat id not configured, the file is corrupt), the only
   way to find out was to wait for the next run and read
   the cron log. There was no "what's pending *right now*?"
   answer, and no command to flush them on demand.

P7B+3 replaces that with an explicit, bounded workflow:

* A new `scripts/replay_pending_media.py` is the *only* thing
  that re-sends deferred MEDIA. It defaults to **dry-run**
  (plan + validate, no send, no move) and requires `--apply`
  to actually send. Bounded by `--limit` (default 10) and
  `--max-retries` (default 3). The original pending file is
  *always* preserved on disk in either `replayed/` (success)
  or `quarantine/` (exhausted / invalid). A `.replay-result-
  *.json` sidecar captures the full outcome.
* A new `scripts/check_openclaw_transport.py` is a
  side-effect-free probe (runs `openclaw --version` + a
  local TCP connect, never sends a message) that the daily
  health check calls and embeds in the report as
  `media_replay.transport_status`.
* The daily health JSON gets a `media_replay` block listing
  `pending` / `replayable` / `quarantined` / `transport_status`
  / `transport_latency_ms`. The 03:00 cron **only** reports
  these; it does not replay.

**Rule**: any "deferred for later" workflow must (a) have a
dedicated, named entry point that operators can call on
demand, (b) be opt-in (not auto-triggered by a side channel
like the next cron run), and (c) emit inspectable, bounded
state on disk (not just a log line). Auto-flush from a
seemingly-unrelated cron is a code smell: it turns "report"
into "recovery" and obscures both.

**Operational rule**: when adding a "deferred for later"
queue, the queue must surface in the *same* health report
the cron already emits, with at least a count and a
status. Operators should never have to `find` and `cat`
files to know whether anything is stuck.

### 2.22 (P8A+1) Ops status should detect cross-repo guards via explicit repo configuration, not assume local repo scope

P8A's `pages_guard_available` was always `false`, even though
the Pages publish guard was correctly installed and operational.
The bug was a **detection-path** mistake: P8A's helper looked for
`scripts/check-project-publish-guard.py` and
`docs/PAGES_PUBLISH_GUARD.md` **inside the Artvee repo**, but
PAGES-GUARD-1 had installed them in the **Pages repo**
(`conanxin.github.io`). The natural home of a guard script is
the repo it is supposed to protect, not the consuming project.
P8A made the wrong assumption.

Three lessons emerged:

1. **Cross-repo facts need explicit cross-repo config.** Any
   signal that lives in *another* repository must be resolved
   via an explicit configuration point (CLI flag, env var, or
   well-defined default). It must *not* be silently looked up in
   the local repo. The P8A+1 fix introduced
   `--pages-repo <pages-repo>` / `$ARTVEE_PAGES_REPO` /
   `$PAGES_REPO` with a `Path.home() / "conanxin.github.io"`
   default — that is the explicit cross-repo configuration
   point.

2. **`Path.home()` is the right default; hard-coded paths are
   the wrong default.** A script that hard-codes an absolute
   user-home path in source fails the path-leak CI gate and is
   not portable to any other operator. Using `Path.home()` keeps
   the path-leak gate green and the script copy-pasteable. P8A
   had defaulted to `Path.home() / "conanxin.github.io"` already;
   P8A+1 just *used* it correctly.

3. **A "false negative" guard detection is worse than "guard
   missing".** When P8A reported `pages_guard_available=false`,
   the operator had no way to know whether the guard was
   uninstalled (real problem) or whether P8A was looking in the
   wrong place (detection bug). The two states require very
   different fixes. P8A+1 separates them: `pages.repo_detected`
   tells you the repo was found, `pages.guard_available` tells
   you the guard files are present, and `pages.guard_smoke`
   tells you the guard actually runs. Three independent bits
   instead of one.

**Rule**: any cross-repo fact (a guard in another repo, a
status of another service, a peer repo's HEAD) must be exposed
through explicit configuration, never assumed to live in the
caller's repo. The CLI surface and the env vars are the
configuration. `Path.home()` is the default; hard-coded paths
are an anti-pattern.

**Operational rule**: when a status field can be one of
several states (repo-missing / guard-missing / guard-installed
/ guard-smoke-failed), report each state independently.
Collapsing them into a single boolean is a debugging
anti-pattern — the operator cannot tell which path is broken
and ends up reading source code.

### 2.23 (P8B) Public product polish needs both a UX card *and* a redaction-aware history export

P8B shipped two seemingly unrelated things: a *visible product
info card* on the public Gallery page, and a *digest history
archive* on the public Digest page. They share one underlying
theme — *the public bundle is a different surface than the local
archive, and that surface needs its own code path*.

Three lessons emerged:

1. **A public product card is part of the export, not part of
   `web/`.** The Gallery `web/index.html` is the *local* UI
   (subtitle: "数据来自 index/artworks.csv + metadata/"). The
   public bundle's `dist/.../index.html` is a *different*
   surface and the differences (no `metadata/` substring, no
   `images/` substring, plus the new info card with v0.2.0 /
   Last updated / 100 public demo records / canonical links)
   must be applied at export time, not by editing `web/`.
   Mixing the two surfaces in one file would either leak
   internal-only strings to the public, or pollute the local
   UI with public-only artifacts. P8B keeps the export
   layer responsible for the public surface.

2. **A history export is not a JSON copy.** The digest
   builder's `digest-history.json` already goes through a
   redaction pass (the digest builder strips
   `<home>/<user>/<machine>/...` substrings), but the
   redacted value still looks like `<redacted>conanxin/<redacted>/...`
   — a recognisable local-absolute path. The digest builder
   *had to* keep enough of the path for the operator to
   navigate the local file tree; the public bundle must not.
   P8B strips the `digest_path` field entirely before writing
   `data/digest-history.json`, and the post-export leak check
   re-asserts that nothing local-absolute slipped through.
   The same pattern should apply to any future "history"
   export: a separate output pipeline with its own
   leak-aware projection of the data.

3. **An honest archive shows what it has.** The archive page
   surfaces a "History entries currently available: 7" notice
   rather than padding the table to a fake 30 days. When the
   rolling history has not yet filled the window, the user
   sees the actual number. This is the same honesty principle
   as "Source archive: local-first full archive, not fully
   published" on the Gallery card: the public surface should
   never claim a richer state than the data actually
   supports.

**Rule**: the public bundle is not a "publish the local
state" operation; it is a "publish a curated, leak-aware
projection of the local state" operation. Every field that
is included must pass through the redaction + leak-check
pipeline, and every visible number that depends on
incomplete data must be honest about that incompleteness.

**Operational rule**: when a redaction pipeline already
exists (here: the digest builder's substring replacement),
it is tempting to assume the redacted output is safe to
publish. It is not — redaction that is *sufficient for
operator navigation* may still be *visible as a local
path pattern* in the public bundle. Treat the public export
as a separate pipeline with its own allow-list and
post-write leak check.

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

### 2.10 Visual QA findings should become automated curation rules (P5E)

The P5D visual-QA pass surfaced a curation flag: the 2026-06-12
digest had 2× Yoshida_Hiroshi and 2× Anonymous picks (4/5
repeats). A human reader would notice; a deterministic selector
would not.

P5E turns the P5D findings into **automated curation rules**:
- Public demo exporter: `--exclude-risk high` (reads P5D
  visual-QA JSON, drops records that meet the threshold)
- Digest builder: `--max-per-artist 1` default (strict cap,
  Anonymous normalized to the same bucket)
- Both: prompt-field non-empty validation with deterministic
  fallback (no external AI)

The re-run digest now ships 5/5 unique artists
(Alphonse_Mucha, Amaldus_Nielsen, Anonymous, Utagawa_Hiroshige,
Yoshida_Hiroshi), and the public-demo candidate is filtered
defensively even though P5D reports 0 high-risk records today.

**Rule**: when a visual-QA pass surfaces a quality concern, the
next phase should not just *document* the concern — it should
**wire the concern into the selection pipeline** so the issue
cannot recur. A contact-sheet is for humans; a CLI flag is for
the next build.

### 2.11 After bounded retries, retire unavailable sources rather than retry indefinitely (P6B)

P4B surfaced 4 URLs that timed out at 30s. P5A retried
them with a lightweight HTTP HEAD probe — all 4 still
unreachable. Rather than continue retrying every run, P6B
formalized a `KNOWN_RETIRED` set:

- 4 records marked `status=known_retired`, `should_retry=False`
- Schema versioned (`marker_version=1.0.0`) for forward compat
- Runtime artifact under `reports/runtime/`, sample schema
  tracked in `examples/known_retired_urls.sample.json`
- Public surface unaffected — losers never made it into
  `web/data/artworks.json` so the gallery / demo / digest
  are unchanged

**Rule**: when a source has been probed N times (here N=2:
P4B page.goto + P5A HTTP HEAD) and remains unreachable,
**stop retrying** and mark the source as audited-but-retired
rather than letting it occupy attention in every status
review. A future phase that needs the URL can
`--unretire <url>` explicitly; silent revival is not
allowed because it would corrupt the audit trail.

The "known_retired=N, blocking_unresolved=M" split is the
operational expression of this rule: N is bounded
historical state, M is what needs attention.

### 2.12 Near-duplicate is a curation concern, not necessarily a data integrity failure (P6C)

P5D surfaced 8 exact aHash near-dup groups. The first instinct
might be to "delete the duplicates" or "deduplicate the index".
That would be wrong for three reasons:

1. **Artistic intent is real.** Edmund Dulac's 4 book illustrations
   are intentionally similar — they are part of a single commission
   (e.g., a fairy-tale book). Amaldus Nielsen's 3 seascapes are
   different works from the same artist's lifelong study of the
   Norwegian coast. Deleting them would erase legitimate content.
2. **aHash collisions are not content duplicates.** Two different
   artists' black-and-white line drawings can produce the same
   8×8 grayscale average hash. This is a perceptual-hash limitation,
   not a data bug. Treating it as a bug would lead to false
   deletions.
3. **P4B collision legacy is data history, not data error.** The 3
   collision-legacy clusters (same title, unique id/source_url/path)
   are the trace of a bounded migration. They document that the
   gallery once had ambiguous filenames and now has stable ids.
   Removing them would erase the audit trail.

**Rule**: when a near-duplicate detector surfaces a group, the
first response should be **classification**, not **deletion**.
Classify by: artist consistency, source_url uniqueness, title
similarity, and id suffix pattern (hex suffix = collision legacy).
Then apply a **curation policy** (keep_all / limit_one_per_digest /
review_before_public) rather than a data-correction policy (delete /
merge / deduplicate).

The P6C workflow encodes this rule:
- `scripts/review_near_duplicate_clusters.py` → read-only, no file modification
- `docs/NEAR_DUPLICATE_REVIEW.md` → human review surface, not an automated gate
- `limit_one_per_digest` → curation limit, not a data deletion
- `collision_legacy` → documented history, not an error to fix

**The general principle**: integrity gates detect *errors* (duplicate
source_url, missing file, corrupt image). Near-duplicate detectors
surface *curation concerns* (artist series, hash collisions, legacy
artifacts). These concerns should be resolved by curation rules in
the digest / demo builder, not by data-deletion in the archive.

### 2.14 After many phase-specific scripts, consolidate into a daily operating layer (P7A)

By the end of P6F+1, the project had 20+ phase-specific scripts, each solving one problem well: collision migration, orphan cleanup, visual QA, near-dup review, digest history, status reports, Telegram staging, CDN tuning, and more. The scripts were correct individually, but the daily operator (the human or the cron) had to remember which scripts to run, in what order, and with what flags.

P7A consolidates the operational surface into a single command:
- `scripts/artvee_daily_health_check.sh` — one entry point
- `scripts/artvee_daily_health_check.py` — the implementation (Python, stdlib only)
- `docs/DAILY_OPERATING_PLAYBOOK.md` — the operational reference

The consolidation is not a new script that replaces the old ones; it is a **read-only aggregator** that runs the old scripts and reports their status in a single JSON + Markdown report. The old scripts remain the source of truth; the health check is just a lens.

**Rule**: when a project accumulates more than 5 phase-specific operational scripts, the next phase should be a **consolidation phase** that surfaces all of them through a single daily command. The consolidation should be read-only (never replace the underlying scripts), should generate a single report, and should recommend an action rather than take one. The goal is to reduce the cognitive load of the operator, not to automate the operator out of existence.

The P7A implementation encodes this rule:
- `scripts/artvee_daily_health_check.sh` → thin wrapper, parses flags, delegates to Python
- `scripts/artvee_daily_health_check.py` → stdlib-only, no network in default mode, no file modification
- `docs/DAILY_OPERATING_PLAYBOOK.md` → operational reference, not a design doc
- Recommended actions: `healthy_no_action` / `candidate_ready_manual_publish_optional` / `attention_required`
- No auto-publish, no auto-download, no auto-retry — the consolidation is observability, not automation

**The general principle**: a system with many correct parts is not a correct system. The parts must be wired together so that a single glance tells the operator whether the system is healthy. The daily health check is that glance.

P5E's `--max-per-artist 1` prevented a single digest from repeating an artist, but it did not prevent the same artist from appearing on consecutive days. The result: a subscriber who reads the digest every day would see Yoshida Hiroshi on Monday, Tuesday, and Wednesday — not because the gallery lacks variety, but because the builder optimized each day independently.

P6F fixes this by adding a **30-day history window** that deduplicates across runs, not just within one run. The builder now avoids three forms of repetition:

1. **Same artwork id**: an exact re-pick within 30 days.
2. **Same artist**: the same artist appearing on consecutive days (unless the candidate pool is too small).
3. **Same near-dup cluster**: two visually similar works from the same cluster appearing close together.

**Rule**: a content system's selection algorithm should optimize over the audience's expected consumption window, not just the current production batch. If a digest is daily, the dedup window should be multi-day. If a playlist is weekly, the dedup window should be multi-week. The audience experiences the system over time; the algorithm should too.

The P6F implementation encodes this rule:
- `scripts/build_artvee_daily_digest.py` → `--history-days 30` + `--near-dup-clusters` + `--history-file`
- `reports/runtime/digest-history.json` → runtime-only, idempotent, capped (max 60 entries)
- `web/data/digests.json` → now includes `picks` array with `near_dup_cluster_id` per pick
- Fallback: if strict filter leaves too few candidates, relax rules in order (cluster → artist → id) and record the reason
- No network, no file modification to source data, no deletion, no GitHub Pages push

**The general principle**: curation is not just about what you include; it is about what you exclude and when you exclude it. A time-aware exclusion rule is a feature, not a bug.

### 2.15 GitHub Pages shared-repo publish can delete unrelated project subtrees; health checks must distinguish HTTP 4xx from network 0 (P7E+1 / P7E+2, 2026-06-15)

The artvee public Gallery and Digest pages share a `projects/` namespace
with every other project on the same `conanxin.github.io` Pages site.
Between 2026-06-12 and 2026-06-15, 9 WBW SpaceX Mars publish commits
(013fbdb → 3748acb) were merged into the shared Pages repo. In the
process, the `projects/artvee-gallery-{demo,digest}/` subtrees
(**205 files, 2042 lines**) and the unrelated
`projects/yang-fudong-fragrant-river/` subtree (**35 files**) were
both removed. The artvee Daily Health cron detected the failure —
but it reported `Online: gallery=0, digest=0`, masking a content
problem as a network problem.

Two bugs compounded into one incident:

1. **The Pages publish flow used an over-broad `git add` / `rsync`
   pattern that replaced the `projects/` subtree as a whole rather
   than the specific new subdirectory.** When the unrelated WBW
   project publish replaced `projects/`, it deleted every other
   project. This is a *shared-namespace hazard* of using a single
   Pages repo for many projects; the immediate fix is to stage
   explicit paths (`git add projects/wbw-spacex-mars-cn ...`) and to
   forbid `git add .` in the publish scripts. The structural fix
   is to give each project its own Pages repo or its own GitHub
   Pages deployment (one repo per project, not one repo for all).

2. **The daily health check's online probe used a bare
   `except Exception`** which collapsed `urllib.error.HTTPError`
   (a *response*, with a real HTTP code) into the same `0` as
   `urllib.error.URLError` (a *transport failure*). The result:
   `0,0` was uninformative — the operator could not tell whether
   the public site was unreachable or whether the path was
   missing. The P7E+2 fix splits the exception handling into
   `HTTPError` (record the real code) vs `URLError` /
   `TimeoutError` / `ConnectionError` (record `0` + `network_error`),
   adds an `online.kind` discriminator, and routes the
   `recommended_action` through three branches: `pages_content_drift`
   (404-class) vs `network_or_pages_unreachable` (0-class) vs the
   original healthy actions.

**The general principle**: when many projects share one GitHub
Pages repo, the publish flow MUST be path-explicit and the
health check MUST distinguish "the server is unreachable" from
"the server returned a 4xx/5xx". A `0,0` report that *could* be
either is worse than a `404,404` report that is unambiguous; the
latter tells the operator exactly what to do (re-publish), while
the former only tells them to start guessing.

**Rules**:

- **For shared-namespace Pages repos**: every publish script must
  stage explicit paths. `git add .` in `conanxin.github.io` is
  forbidden; the dry-run output of the publish helper must
  enumerate the exact paths it intends to commit.
- **For health checks that probe the public site**: split
  `HTTPError` from `URLError`. The numeric code is a fact; the
  kind is a fact; never collapse them.
- **For daily summaries delivered to Telegram / Slack / email**:
  the summary must remain truthful even when the underlying
  signal is ambiguous. A `gallery=0, digest=0` summary that
  could mean either "DNS down" or "path missing" forces the
  operator to re-curl manually. A `gallery=404, digest=404`
  summary points them straight to the fix.
- **For the operator**: when `Online: gallery=404, digest=404`
  appears, do not re-run the cron. Re-publish the candidate
  (the local data is fine; the public site is missing the path).
  See `docs/DAILY_OPERATING_PLAYBOOK.md` § 12 for the recovery
  playbook.

### 2.22 (P8A) Post-stable needs one on-demand command, not more cron

After v0.2.0 stable shipped, the natural temptation was to add
more scheduled jobs: a morning briefing, a weekly digest review,
a Pages drift monitor. P8A rejected that.

The 03:00 daily health cron already covers continuous monitoring
(Telegram fallback, pending MEDIA scan, transport probe, online
checks). Adding a 06:00 ops status cron would have:

1. **Duplicated the 03:00 read** for one piece of state the
   operator could see on demand.
2. **Created another schedule to maintain** (time-zone, log path,
   failure alert destination).
3. **Promoted "review" into a scheduled event**, which means the
   operator eventually stops *looking at* the report and just
   *trusts* it.

Instead, P8A adds a single on-demand command that an operator
runs at the keyboard when they want a snapshot. It is strictly
read-only, never sends a Telegram message by default, never
touches the Pages repo (even with `--include-pages`, it only
runs `git status --porcelain`), and never auto-replays pending
MEDIA. With `--media` it sends one Telegram + MEDIA via the
same staged-only path the daily health check uses; the raw
report path is never sent to OpenClaw.

**Rule**: a "review" or "summary" command is almost always
better as an on-demand script than a cron. Crons should
*monitor*; operators should *review*. Conflating the two
slowly turns alerts into noise.

**Operational rule**: a single canonical `recommended_action`
enum (with first-match-wins priority) is the right level of
abstraction for an on-demand report. Freeform text recommendations
get paraphrased, mis-copied, and ignored. A closed enum with
6 values is small enough to memorize and large enough to cover
the actual decision space (PASS / candidate / 4 different
"attention required" branches).

**Rule for layering**: the ops status command *imports* the same
helpers the daily health check uses (`_scan_pending_media`,
`check_openclaw_transport`, `stage_report_for_telegram_media`,
`send_text`) rather than re-implementing the logic. If a count
ever drifts between the two reports, it is a bug; there is no
intentional divergence to debug.

### 2.25 (P8C) A public archive should be honest, navigable, and data-minimized

Three lessons from promoting the digest archive from a
text-only table (P8B) to a cards + filters grid (P8C):

1. **Honest first, navigable second, frameworked last.** A
   public archive is only useful if visitors can scan it
   without doing the math. P8B's text table was honest ("7 of
   30 days") but barely navigable. P8C added **digest cards**
   (one per day) and a **summary chip row** (Total days /
   Total picks / Unique artists / Available range / Top
   categories) so a visitor can answer the "what's here?"
   question in one glance — without scrolling. Only after
   that did P8C add the **filter row** (Artist / Category /
   Search) and the **Jump to latest** button. The honest
   summary stayed at the top, the filters stayed at the
   bottom, and the cards stayed in the middle. Reading order
   tracks usefulness for a *new* visitor.

2. **The page is the data, JS is sugar.** The archive page is
   fully readable with JavaScript disabled. Every card and
   meta chip is server-rendered from
   `data/digest-history.json`; the vanilla `archive.js` only
   adds the filter wiring and the `#no-results` notice. This
   has two payoffs: (a) the page degrades gracefully on any
   browser that blocks the script (corporate proxies,
   NoScript, archive crawlers); (b) the cards remain
   semantically rich for any future consumer that wants to
   skip the JS and read the DOM directly. Both payoffs fall
   out for free from "do the data work in the exporter, do
   the interactivity in the script".

3. **A history export's summary should live in the export,
   not in every consumer.** P8C moved the archive summary
   (total_days / total_picks / unique_artists /
   top_categories / available_range) into a top-level
   `summary` block in `data/digest-history.json` itself, so
   downstream consumers don't have to recompute them every
   time. P8B had only the per-entry shape; P8C keeps that
   shape (backward compatible) and adds the summary on top.
   The exporter is the only place that knows the data well
   enough to compute the summary cheaply and consistently —
   once the summary lives in the JSON, every reader gets
   the same numbers.

4. **Readiness checks can be tripped by honest documentation.**
   P8B had passed, but 8 path-leak stragglers (the literal
   project-root / home-dir substrings used in the readiness
   grep) had been left in 5 docs while *describing* the
   path-leak check policy. P8C's preflight caught them
   (readiness FAIL) and rewrote the meta-descriptions to
   refer to the abstract *project-root* / *home-dir*
   substrings. The lesson: a `readiness` check is supposed
   to keep *real* paths out of the public bundle, not to
   keep *any* mention of those substrings out of the
   documentation. The fix is to describe the policy in
   terms of *what it does* (strips local-absolute paths)
   rather than *what it forbids* (a literal substring that
   re-appears in the description). This is also a useful
   self-test: if the documentation is hard to write without
   mentioning the forbidden substring, the wording is
   probably too literal.

### 2.23 (P8D) Optional > automatic. Always.

After P7B+3 shipped the manual replay workflow, the obvious
"next step" was: "automate it — schedule a cron that calls
`replay_pending_media.py --apply` every day." P8D rejected
that, on principle:

1. **Pending MEDIA is a recovery signal, not a steady-state
   signal.** A daily cron that *always* calls replay
   transforms an alert ("you have 2 deferred MEDIA waiting")
   into a background task ("the cron will handle it"). When
   the cron later fails for any reason, the operator
   eventually stops *checking* pending and just *trusts* it.

2. **Auto-install widens the blast radius.** A typo in the
   cron wrapper that mis-archives a healthy MEDIA goes
   unnoticed because the cron ran "successfully". With a
   manual workflow, the operator sees the plan before
   approving; with an auto-cron, the plan never surfaces.

3. **Operators should opt in once they trust the flow.**
   "Optional + opt-in + one-command install" is the right
   ergonomic. P8D ships the cron command in
   `install_media_replay_cron.sh --dry-run` so the operator
   sees exactly what would be added before running
   `--install`.

**Rule**: any "review" / "summary" / "maintenance" step that
was previously manual should stay manual until the operator
explicitly asks for automation. The cron is a *shortcut*, not
a *replacement*. Shortcuts that replace the underlying habit
slowly erode it.

**Operational rule**: when you do install an "optional" cron,
make the install idempotent + marker-block-based + removable
in one command. P8D follows the same `MARKER_BEGIN / MARKER_END`
+ `sed`-in-place pattern P7B's `install_daily_health_cron.sh`
uses, so the operator can `--install` twice or `--remove`
without touching any other cron entry.

**Rule for transport-aware crons**: a cron that *acts* (not
just reports) must check transport before acting. P8D's
wrapper calls `check_openclaw_transport.py` by default; if
transport ≠ ok, it skips with `outcome=skipped_transport_unavailable`
and does **not** burn replay attempts. Without this check, a
4-hour gateway outage would quietly quarantine every pending
MEDIA. The transport pre-flight is the difference between a
"recovery" tool and a "destruction" tool.

**Rule for "silent success" crons**: pending=0 should be
silent. A cron that sends "nothing to do!" every day is
spam; the operator eventually mutes it. P8D's wrapper writes
a summary JSON to disk on every run (so ops status can read
it), but never sends a Telegram message when pending=0. The
operator still gets visibility via the 03:00 daily-health
cron's `media_replay` block.

### 2.24 (P8D+2) Cron-safe notification needs explicit chat-id config, not implicit interactive session state

The 2026-06-30 P8D+1 next-day verification found that the 01:30
refill, 02:00 batch, and 03:00 daily-health cron runs all logged
`NOTIFY_FAIL: Telegram chat id not found` — even though the
interactive shell test (`python3 scripts/artvee_telegram_notify.py
--text "..."`) worked perfectly. The difference was that the
interactive shell had `ARTVEE_TELEGRAM_CHAT_ID` set in `.bashrc`,
but the cron environment did not inherit it.

**Root cause**: `artvee_telegram_notify.py` resolved chat id from:
1. `--chat-id` CLI arg
2. `ARTVEE_TELEGRAM_CHAT_ID` env var
3. `$HOME/.openclaw/openclaw.json` `defaultChatId`
4. `$HOME/.openclaw/openclaw.json` `targets[0]`

The OpenClaw config had `telegram.enabled=true` and `botToken` but
**no `defaultChatId` or `targets`**. So in the cron environment
(where `.bashrc` is not sourced), the notifier had no chat id and
failed on every run. The data products were still produced; only
the Telegram notification was dropped.

**Fix**: Added a new resolution step — **private env file**
(`$HOME/.config/artvee-gallery/telegram.env`). The new order:
1. `--chat-id` CLI arg
2. `ARTVEE_TELEGRAM_CHAT_ID` env var
3. `$HOME/.config/artvee-gallery/telegram.env` (private, chmod 600, not in git)
4. `$HOME/.openclaw/openclaw.json` `defaultChatId`
5. `$HOME/.openclaw/openclaw.json` `targets[0]`
6. Hard error with clear instructions

The cron installers (`install_artvee_cron.sh`,
`install_daily_health_cron.sh`) now emit
`ARTVEE_TELEGRAM_ENV_FILE=$HOME/.config/artvee-gallery/telegram.env`
as a cron env var above the schedule lines. The actual chat id is
**never baked into the crontab** — only the path to the private env
file is. This preserves secret hygiene while making the notifier
work in the minimal cron environment.

**Rule**: any notification path that relies on an env var or config
value must have a **cron-safe fallback** that does not depend on
interactive shell state. `.bashrc` is not sourced by cron; `export`
in `.bashrc` is invisible to cron jobs. The right place for cron
secrets is a **private env file** that the cron line explicitly
references, or a config value in a file that the cron job can read
without interactive session state.

**Operational rule**: when a notifier works interactively but fails
in cron, the first diagnostic is "what env vars / config values does
the interactive shell have that cron does not?" — not "is the
notifier broken?". The `env -i HOME=... PATH=... ARTVEE_TELEGRAM_ENV_FILE=...
bash -lc '...'` test is the canonical way to reproduce the cron
environment and verify the fix.

**Secret hygiene rule**: never bake secrets (chat ids, tokens, API
keys) into crontab lines or tracked files. Crontabs are readable by
`crontab -l` (any user with cron access), and tracked files are in
git. The right pattern is: secret lives in a repo-external file
(chmod 600, not in git), crontab references the file path, the
notifier reads the file at runtime.

The 2026-06-29 cron diagnostic caught a silent regression: the
03:10 media-replay cron had been installed (in a real crontab)
but produced zero logs and zero summary for at least one full
day. Investigation found the cron line in `crontab -l` was:

```
CRON_TZ=Asia/Shanghai 10 3 * * * cd <artvee-repo> && bash scripts/artvee_media_replay_cron.sh --limit 5 --max-retries 3 >> ...
```

— i.e. **7 fields** instead of 5. Vixie-cron parses any leading
`Name=value` as a per-line env var assignment, so this line
looked like `CRON_TZ=Asia/Shanghai`, with the *real* schedule
parsed as `10 3 * * * cd <artvee-repo>` (the `cd` and the
rest of the line were misread as `dom`/`mon`/`dow` fields, and
the line was silently rejected because the field count did not
parse). No error, no log, no summary — the cron just never
fired.

The same bug was present in the installer's template, so a
fresh `--install` would have re-installed the broken line.
Two compounding lessons:

1. **`Name=value` belongs on its own line above the schedule.**
   The pre-P7B refill/batch/confirm-refresh lines had a *bare*
   `CRON_TZ=Asia/Shanghai` (no leading 7-field bug) but no
   `PATH=` line at all. The P7B daily-health line had
   `export PATH=...` inline *as part of the command* and worked.
   Two different conventions in the same crontab, neither fully
   correct. P8D+1 unifies on: env vars on their own lines,
   `CRON_TZ=Asia/Shanghai` then `PATH=$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin`
   then a clean 5-field schedule. The installer templates
   (`install_media_replay_cron.sh`, the new
   `install_artvee_cron.sh`) are the single source of truth.

2. **A cron that produces no logs is not "silent success" —
   it is silent *failure*.** The P8D `noop_zero_pending` design
   explicitly does *not* send a "0 pending" Telegram. But it
   *does* always write `reports/runtime/media-replay/cron-<date>.json`
   on every run, including no-op runs. That on-disk summary is
   the only way ops status can tell a *real no-op* (cron ran,
   found nothing to do, wrote a summary) from a *silent failure*
   (cron never ran, no summary, the operator is in the dark).
   P8D+1 makes this contract explicit in the docs ("If
   `cron-<date>.json` is missing for a day the cron was
   scheduled to run, treat that as a real failure, not a no-op").

**Rule**: cron schedule lines are exactly 5 (or 6, for `@`-prefixed
or named) fields. `Name=value` env-var assignments must be on
their own lines, above or below the schedule. When a cron's
on-disk artifact directory is empty after a scheduled run,
the bug is in the *crontab* (or the installer's template), not
in the wrapper — never "fix" the wrapper to "always write
something"; the wrapper is correct, the line is not being run.

**Diagnostic trap**: a Bash heredoc diagnostic that sets
`TODAY="$(date +%F)"` in the parent shell and then calls
`python3 <<'PY' ... os.environ.get("TODAY") ... PY` will
*always* show the env var as missing, because `os.environ` is
not inherited by `<<'PY'` heredocs that don't `export`. Either
`export TODAY=...` before the heredoc, or compute today/ymd
inside the Python block. The first 2026-06-29 diagnostic
incorrectly reported "ALL_EXPECTED_ARTIFACTS_MISSING" because
of this; a second pass that used `os.environ.setdefault(...)`
or re-derived the date inside Python gave the correct "all
present" verdict.

### 2.25 (P8D+3) User-facing copy should be phase-neutral once a workflow is stable

The 2026-07-01 next-day verification of P8D / P8D+1 / P8D+2
found the system working correctly — 03:00 text arrived
(message_id=27647), 03:00 MEDIA was deferred with
`error_kind=transport`, 03:10 media-replay cron re-attached the
staged report (`outcome=replayed_pending`, `transport_status=ok`),
and 03:10 MEDIA arrived (message_ids 27649 / 27650). No data
failure. But the user-facing Telegram title said
`↻ Artvee Gallery P7B+3 deferred MEDIA replay`, and the P7B+3
phase tag was misleading: P7B+3 was the phase that *introduced*
the replay workflow, but the active phase hierarchy is now
P7B+3 → P8D → P8D+1 (cron activation) → P8D+2 (chat-id hardening)
→ optional 03:10 cron. An operator looking at today's replay
message would wonder "why does this say P7B+3 when we're on
P8D+2?" — and the P7B+3 tag doesn't add useful information for
the *reader*; it only adds provenance for the *author*.

The right phase for the user-facing copy is **the workflow it
represents**, not the phase that first shipped it. The workflow
is now: daily-health MEDIA failed → fallback deferred → 03:10
media-replay cron re-attaches. The natural name is
"Artvee Daily Health MEDIA replay" — neutral, accurate, and
doesn't age out as more P8D / P9 phases accumulate. P7B+3
remains the historical source of the workflow in this doc and
in the changelog, but the Telegram title no longer carries the
phase tag.

**Pair with the recovered-WARN contract**: a 03:00 MEDIA
deferral closed by 03:10 looks alarming at first glance — the
03:00 line in the cron log says `error_kind=transport`, which
sounds like a failure. But the actual failure mode is "the
OpenClaw gateway was briefly unavailable; the next cron tick
flushed the deferred MEDIA." Without an explicit classification,
operators misread a closed deferral as a data failure and waste
time debugging. P8D+3 documents this in
`docs/DAILY_OPERATING_PLAYBOOK.md` § 9.10 with a 4-row
classification table (`notify_config_fail` /
`media_transport_deferred` / `media_transport_deferred + 03:10 OK`
/ `media_transport_deferred + 03:10 failed`) and explicit
`WARN_RECOVERED` vs `NOT_RECOVERED` verdicts. The on-disk
`reports/runtime/media-replay/cron-<date>.json` summary is the
single source of truth for "did 03:10 close the deferral?"

**Rule**: when a phase ships a workflow, the *next* phase's job
is not to add another `P{prev}` tag to the user-facing copy; it
is to neutralize the copy to the workflow name and document any
recoverable failure modes that the original phase couldn't have
foreseen. Stable systems earn neutral copy; unstable ones earn
phase tags because the reader needs to know which phase shipped
which behavior. P7B+3 earned its tag because the workflow was
new; P8D+3 neutralizes it because the workflow is now stable
across P8D / P8D+1 / P8D+2.

**Operational rule**: when reading a Telegram message with a
phase tag, ask "is the tag still accurate for the *current*
phase hierarchy, or is it just provenance?" If it's only
provenance, the message should be neutralized. If it's still
accurate (e.g., a v0.2.0 release note), keep it — but only for
*release surfaces*, not for *operational surfaces* (cron logs,
ops status, daily health Telegram text, replay messages).

**Diagnostic discipline**: when next-day verification finds the
system working correctly, the deliverable is *not* a fix — it
is a documentation cleanup that prevents the next operator
from misreading the same working behavior. The P8D+3 phase had
no bug to fix; it had a stale phase tag and an undocumented
classification to add. The cron-like dry-run was the proof
artifact, not a deliverable.

### § 2.26 · Delivery truth must be durable, not circumstantial (P8D+4, 2026-07-03)

**Trigger**: 2026-07-03 03:10 replay cron recorded
`outcome=replayed_pending` with `replay_message_ids=""` — a
contradiction. The replay had exited 0 (no exception), so the
success path fired, but Telegram never received the document.
The on-disk summary said "replayed" while the Telegram chat said
nothing.

**Root cause chain**:
1. `replay_one()` checked `result.get("ok")` — true for
   OpenClaw exit 0 — but OpenClaw exit 0 only means "the
   notifier script ran without throwing"; it says nothing about
   whether Telegram accepted the payload.
2. The OpenClaw journal line `outbound send ok ... messageId=29012`
   was the *only* evidence of real delivery. The notifier regex
   only matched `Message ID:` (capital) and `message_id=` (lowercase
   with underscore) — neither matched `messageId=` (camelCase),
   so `message_id` stayed null even when OpenClaw *had* delivered.
3. The cron unconditionally set `OUTCOME=replayed_pending` without
   checking the aggregate `results` list — so the false positive
   from step 1 propagated all the way to the summary JSON.

**Lesson**: in a system where OpenClaw is a transport wrapper
around a native binary, "exit 0" is a *necessary* but not
*sufficient* condition for delivery. The durable proof of delivery
is the Telegram `message_id` — a value that exists only when
Telegram's API actually accepted the payload. If the notifier
returns exit 0 but the journal does not contain a parseable
`message_id`, the replay is **not delivered**. This is not a
borderline case; it is the definition of undelivered.

**Operational rule**: any success判定 that does not require a
`message_id` (or equivalent Telegram-generated idempotency key)
is a bug. The `outcome` field in the summary JSON is the human
readable summary; the `message_ids` array is the durable proof.
An empty `message_ids` with `outcome=replayed_*` is a data
integrity failure, not an acceptable edge case.

**Second lesson — path stability**: building archive paths by
joining `pending_path.parent / name` is a latent infinite-nesting
bug whenever the pending root is inside the archive root (which
is the natural layout for `daily-health/` → `daily-health/replayed/`).
The safe pattern is *fixed* anchor directories that are never
descendants of each other: `reports/runtime/media-replay/pending/`,
`reports/runtime/media-replay/replayed/`, `reports/runtime/media-replay/quarantine/`.
If the pending root and the archive roots share a prefix, the
script must resolve the archive path from an absolute anchor,
not from `pending_path.parent`.

### § 2.27 · Backup and terminal artifacts must live outside the active queue scan (P8D+4B, 2026-07-04)

**Trigger**: the 2026-07-04 03:10 media-replay cron wrote
`pending_before=8, outcome=noop_zero_pending` on a day with zero
newly-deferred MEDIA. The same day's `artvee_ops_status` correctly
reported `pending_media=0` because `ops_status` called
`_scan_pending_media(reports/runtime/daily-health/)` (the daily-health
internal call) while the cron wrapper called
`_scan_pending_media(reports/)` (the bare-reports path). Two
scripts, one helper, two different counts — and the cron was the
one emitting the noisy number.

**Root cause chain**:
1. `_scan_pending_media(report_dir)` was originally written for
   `report_dir = reports/runtime/daily-health/`. The
   `rel.startswith("replayed/")` filter assumed the **first**
   segment of the relative path was already `replayed/` /
   `quarantine/`. That assumption broke silently when the cron
   wrapper (P8D-era) called it with `report_dir = reports/`
   instead of `reports/runtime/`. The relative path then started
   with `runtime/media-replay/replayed/...`, so the prefix
   match always returned False and every terminal file was counted.
2. The `queue-fix-backup-20260703-062946/stable_dup/` directory
   (P8D+4 normalization's snapshot) was never excluded by the
   scanner, so its 4 orphan `.fallback-pending-*.json` files
   joined the count.
3. `artvee_ops_status` (which scanned `daily-health/` directly,
   not `runtime/`) happened to miss all three buckets, so the
   two views disagreed by **8** on a clean day. Operators reading
   the ops status (the friendlier number) would not have noticed
   the cron summary was wrong — until they grepped the JSON.

**Lesson 1 — both ends of a contract must be defensive**: the
caller that passes the wrong root (`reports/` vs `reports/runtime/`)
was a bug, but the *callee* trusting the prefix match was also
a bug. A scan helper that filters by relative prefix without
verifying the *base* it is computing those prefixes against is a
latent foot-gun. From P8D+4B onward,
`_scan_pending_media` always classifies by absolute segment match
("does any segment equal `replayed` or `quarantine` *and* is its
parent `media-replay` or `daily-health`?") rather than trusting
the caller to pass the canonical root, and it tries to climb to
`runtime/` if the caller passed bare `reports/`.

**Lesson 2 — terminal states and snapshots are *not* pending**:
a queue scan that treats delivered / quarantined / backup files
as actionable will eventually emit a false-positive alarm. The
caller must:
- define a single, named *active pending root* (in our case
  `media-replay/pending/` plus top-level `daily-health/`),
- bucket everything else (`terminal_replayed`,
  `terminal_quarantine`, `results`, `backup_or_legacy`,
  `legacy_nested`, `unknown`) and surface those counts
  separately, and
- only let the *active* bucket drive the alarm threshold.

**Lesson 3 — diagnosis-first, archive-second**: before doing the
one-time cleanup, copy *everything* that the scanner could ever
touch to `reports/runtime/media-replay/queue-scope-cleanup-backup-
<timestamp>/` with `cp --parents` to preserve relative paths,
then archive (not delete!) the archived artifacts to
`reports/runtime/media-replay/legacy-cleaned/<YYYYMMDD>/`. The
backup lets the operator reverse the cleanup *byte-for-byte*
if a regression surfaces; the archive lets future scans
ignore everything in `legacy-cleaned/` because the directory
name itself is a `_NON_ACTIVE_ARCHIVE_HINTS` segment match.
Anything under either tree is `reports/runtime/` and therefore
git-ignored.

**Operational rule (P8D+4B going forward)**: a clean day reads
`pending_before=0, outcome=no_pending`. If the cron ever reports
`pending_before > 0`, that means real work is queued — open the
summary, look at `active_pending`, and decide whether to wait for
transport to fully recover or run `bash
scripts/artvee_media_replay_cron.sh --apply` manually. The
`terminal_*` and `ignored_*` counts are visibility, not alarms.

### § 2.28 · Dry-run must never overwrite production observability artifacts (P8D+4C, 2026-07-04)

**Trigger**: P8D+4B's verification dry-run rewrote today's
`reports/runtime/media-replay/cron-2026-07-04.json` (the file
slot reserved for the 03:10 real-cron run). The new file looked
indistinguishable from a real silent no-op (`pending_before=0,
transport=ok, outcome=no_pending`), but it was now a developer-time
artifact. There was no way for a future operator opening the file
tomorrow to know whether it was authentic or a sanity check.

**Root cause**: `artvee_media_replay_cron.sh` had a single
`SUMMARY_JSON="${SUMMARY_DIR}/cron-${RUN_DATE}.json"` slot used
by both the real 03:10 cron run and any `--dry-run` invocation.
The flock-held skip branch also wrote to the same slot.

**Lesson 1 — observability slots are partitioned by intent, not
by accident**: a slot labeled ``production summary`` must be
writable *only* by the run that owns it. Co-locating a dry-run
write to the same path is a class of bug that survives because
the dry-run's payload is usually *plausibly* valid; the failure
mode is silent and forensics-only. The safe pattern is:

* `PROD_SUMMARY_JSON` — always the slot the real cron owns.
* `DRY_RUN_DIR` — a sibling directory for dry-run outputs.
* `SUMMARY_JSON` — rebound to one or the other based on the
  `--dry-run` flag, with both paths emitted into the JSON itself
  (`production_summary_path`, `dry_run_summary_path`,
  `would_write_production_summary: bool`).

**Lesson 2 — dry-run relabel outcomes that overlap with
production labels**: a dry-run that reports `outcome=no_pending`
will be indistinguishable from a real silent no-op. Adding a
`dry_run` namespace prefix (`dry_run_no_pending`,
`dry_run_replayed_delivered`, `dry_run_skipped_locked`) plus a
`real_outcome` field for forensics lets dashboards distinguish
the two without parsing the path. When the production enum and
the dry-run enum *both* contain `no_pending`, anything
substring-matching on `no_pending` will count dev pre-flights —
exactly the bug we hit.

**Lesson 3 — negative tests should be exact, not approximate**:
the recipe ``ls $PROD; before=$(sha256sum); after=$(sha256sum);
[ "$before" = "$after" ] && echo PASS`` is the only way to
verify that dry-run *did not change anything* byte-for-byte.
Asserting ``$PROD exists`` is not enough. Asserting
``grep pending_before $PROD`` is not enough. Either would have
passed the buggy version.

**Lesson 4 — the bug-surfacing test was the verification
itself**: the same dry-run that exposed the P8D+4B scope bug
also exposed the dry-run overwrite bug. Two bugs found in one
verification cycle is a useful pattern: a successful fix is a
chance to look at every artifact the fix produced and ask "would
the next operator trust this?". Treat every successful
verification dry-run as evidence worth auditing.

**Operational rule (P8D+4C going forward)**: every observability
artifact slot must declare its **owner** (real cron | dry-run |
test-suite | operator) at the path level, and the JSON must
carry `dry_run` + `would_write_production_summary` + path
fields so a future regression cannot silently rewrite
production data. Two different artifacts (production + dry-run)
is the minimum cost; the alternative (one shared slot) is what
crashed auditability here.
