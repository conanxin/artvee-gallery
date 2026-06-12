# Artvee Gallery · Development Guide

> Local development loop, syntax checks, and the safety check you
> should run before any commit.

## 1. Prerequisites

- Python 3.9 or newer
- (Optional) `Pillow` for thumbnail generation and palette
  extraction in the digest builder
- A clean working tree (the readiness check requires this)

## 2. Repo layout (tracked only)

```
.
├── README.md
├── LICENSE
├── .gitignore
├── docs/        ← documentation (tracked)
├── examples/    ← tiny synthetic sample data (tracked)
├── scripts/     ← executable code (tracked)
└── web/         ← local UI shell (index.html, app.js, style.css tracked)
                  web/data/   ← generated JSON (gitignored)
```

Everything else (`images/`, `metadata/`, `thumbs/`, `dist/`,
`digests/`, `inbox/`, `index/`, `logs/`, `backups/`) is
gitignored — it is regenerated locally by the scripts in `scripts/`.

## 3. Syntax checks

Before any commit, run:

```bash
python3 -m py_compile scripts/build_artvee_gallery.py
python3 -m py_compile scripts/export_artvee_gallery_public_demo.py
python3 -m py_compile scripts/build_artvee_daily_digest.py
python3 -m py_compile scripts/check_open_source_ready.py
bash -n scripts/serve_artvee_gallery.sh
bash -n scripts/artvee_nightly_wrapper.sh
```

These are all **syntax-only** checks; they do not download, parse,
or write anything. They are safe in any environment.

## 4. Local end-to-end smoke

You can verify the public demo export without touching the network,
because the gallery rebuild step is local:

```bash
# Build the gallery from your local archive (no network)
python3 scripts/build_artvee_gallery.py --mode local

# Export a tiny demo bundle to /tmp (out of repo)
python3 scripts/export_artvee_gallery_public_demo.py \
    --limit 5 --strategy recent \
    --out-dir /tmp/artvee-gallery-demo-smoke

# Verify the bundle's data file is well-formed
python3 -m json.tool /tmp/artvee-gallery-demo-smoke/data/artworks.json > /dev/null
```

The smoke target lives entirely under `/tmp/` so it never accidentally
lands in the repo.

### Public-safety flags (P4D, public demo only)

The public demo exporter gained two optional guards that
*only* affect the public export — runtime `web/data/` is
untouched. Use both together when publishing to GitHub Pages:

```bash
# Skip whole source_url groups that map to multiple records
# (e.g. P4A+1 § 6.4 Le_rêve URL label bug, deferred to P5+),
# and refuse to write the export if any source_url still
# appears more than once.
python3 scripts/export_artvee_gallery_public_demo.py \
    --limit 100 --strategy diverse \
    --out-dir /tmp/artvee-gallery-demo-p4d \
    --base-url . \
    --exclude-duplicate-source-url-groups \
    --require-unique-source-url
```

* `--exclude-duplicate-source-url-groups` — reads the *global*
  `web/data/artworks.json`, finds `source_url` values that map
  to multiple records, and drops those *entire groups* before
  selection. The export then cannot leak a known buggy URL
  label by accident.
* `--require-unique-source-url` — post-selection, exits non-zero
  if any `source_url` appears more than once in the picked set.
  Pairs naturally with the first flag as a final safety net.
* The exporter also strips the `metadata_path` field from each
  record in the public JSON: the public demo has no
  `metadata/` folder, so the path is dangling in addition to
  leaking the local source-machine layout.
* The `index.html` subtitle is rewritten at copy time from the
  local "数据来自 index/artworks.csv + metadata/" text to a
  public-safe "数据来自 artvee.com 公共领域艺术作品库" line,
  so the public page does not advertise the local folder
  structure.

## 5. What you should **not** run in dev

These are wired into cron, not into the dev loop. **Do not** trigger
them from a dev session unless you know what you are doing:

```text
# Downloads from artvee.com — leave to the nightly cron:
python3 scripts/run_artvee_nightly_batch.py
python3 scripts/refill_artvee_pending.py --execute
python3 scripts/scrape_artvee_seeds.py
python3 scripts/download_artvee_selected.py
python3 scripts/add_artvee_candidates.py

# Telegram-bridge side effects:
python3 scripts/artvee_telegram_notify.py --text "..."

# Telegram MEDIA attachment (P6A) — reports under <workspace-reports>/ are
# NOT in the OpenClaw MEDIA allowlist; stage to <openclaw-media>/artvee-reports/
# first, then attach the staged path:
STAGED=$(python3 scripts/stage_report_for_telegram_media.py \
  --report <workspace-reports>/<your-report>.md)
python3 scripts/artvee_telegram_notify.py \
  --text "Summary" --media "$STAGED" --wait

# Full nightly chain (this is what 02:00 cron runs):
bash scripts/artvee_nightly_wrapper.sh batch
bash scripts/artvee_nightly_wrapper.sh refill
```

If you do run any of them, you should commit the *side effects* into
your own private copy, not back into the open-source repo.

## 6. Open-source readiness check

Before any commit that touches tracked files, run:

```bash
python3 scripts/check_open_source_ready.py
```

This is a **read-only** check. It:

1. Lists all tracked files.
2. Fails if any path starting with `images/`, `metadata/`, `thumbs/`,
   `dist/`, `digests/`, `logs/`, `inbox/`, or `web/data/` is tracked
   (excluding `.gitkeep` placeholders).
3. For non-source text files (`.md`, `.json`, `.html`, `.css`,
   `.js`, configs), fails if the file contains an absolute home
   path, user-home shorthand, or workspace-name substring. Source
   code is exempt — it legitimately mentions
   these strings for defensive checks and design comments.
4. Across all tracked text files, fails on patterns that look like
   real secrets (`password = "..."`, `token = "..."`, `secret = "..."`).
5. Warns on any tracked file > 1 MB.

The script prints PASS / FAIL with a per-check breakdown and a
non-zero exit on FAIL. It never modifies anything.

Run it as a pre-commit hook if you want it automatic:

```bash
ln -s ../../scripts/check_open_source_ready.py .git/hooks/pre-commit
```

Or as a CI step on every PR.

## 6.1. Gallery integrity check (P4B)

P4A discovered a historical 11-group filename collision pattern
(13 extra rows) and P4A+1 froze that as a known fingerprint. P4B
(2026-06-12) **healed** the underlying collision: filenames are
now derived from a source-url hash, the 11 winners have been
renamed to stable ids, 9 of the 13 losers re-downloaded, and
4 unresolvable losers dropped from the index/web data. The
`KNOWN_DUPE_FINGERPRINT` is now empty. All three modes
(`--strict`, `--allow-known-duplicates`, default) exit 0 on a
clean tree.

```bash
# CI default: alias for --strict (P4A fingerprint is empty after P4B).
python3 scripts/check_gallery_integrity.py --allow-known-duplicates

# Strict: fail on any duplicate / collision. Useful in dev.
python3 scripts/check_gallery_integrity.py --strict

# Machine-readable output (combine with any of the above):
python3 scripts/check_gallery_integrity.py --strict --json
```

The check inspects three runtime data sources when they exist:

| Source | What it checks |
| --- | --- |
| `inbox/manifest.csv` | `status=downloaded` URL is unique; no double-download. |
| `index/artworks.csv`  | `local_image_path` basename is unique; one basename never maps to many `source_url`. |
| `web/data/artworks.json` | `id` is unique; `image_path` / `metadata_path` / `thumb_256` / `thumb_512` is unique. |

Behaviour on the open-source / CI environment (no runtime data):

```
[1/3] inbox/manifest.csv   SKIP
[2/3] index/artworks.csv   SKIP
[3/3] web/data/artworks.json   SKIP
Overall: SKIP
```

So the gate is safe to run on every PR. The historical P4A
fingerprint (11 groups, 13 extra rows) is frozen inside the
script. Any *new* duplicate pattern fails the gate immediately.

## 6.2. Post-migration verification (P4C)

P4C adds a read-only verification harness for the
post-migration state. Run after every batch / migration / change
to the data layer.

```bash
# 1. integrity check (3 modes)
for mode in "" "--allow-known-duplicates" "--strict"; do
  echo "  mode='$mode': $(python3 scripts/check_gallery_integrity.py $mode >/dev/null 2>&1; echo $?)"
done

# 2. open-source readiness (4/4 must pass)
python3 scripts/check_open_source_ready.py

# 3. public demo dry-run (no real dist write)
python3 scripts/export_artvee_gallery_public_demo.py --dry-run --limit 100 --strategy diverse
python3 scripts/export_artvee_digest_public_page.py --dry-run

# 4. public demo full export to a temp dir (cleanup after)
rm -rf /tmp/artvee-gallery-demo-verify
python3 scripts/export_artvee_gallery_public_demo.py \
  --limit 100 --strategy diverse \
  --out-dir /tmp/artvee-gallery-demo-verify \
  --base-url .
python3 -m json.tool /tmp/artvee-gallery-demo-verify/data/artworks.json >/dev/null
python3 -m json.tool /tmp/artvee-gallery-demo-verify/data/gallery_stats.json >/dev/null
find /tmp/artvee-gallery-demo-verify/assets/thumbs/{256,512} -type f | wc -l
# 100 + 100 = expected
# 5. inline path-integrity check
python3 - <<'PY'
import json
from pathlib import Path
base = Path('/tmp/artvee-gallery-demo-verify')
arts = json.loads((base / 'data/artworks.json').read_text())
missing = []
seen = set()
for a in arts:
    if a.get('id') in seen:
        raise SystemExit('duplicate id: ' + a.get('id'))
    seen.add(a.get('id'))
    for k in ['thumb_256', 'thumb_512']:
        p = base / str(a.get(k, '')).replace('./', '')
        if not p.exists():
            missing.append((a.get('id'), k, str(p)))
print('exported:', len(arts), 'problems:', len(missing))
raise SystemExit(1 if missing else 0)
PY
rm -rf /tmp/artvee-gallery-demo-verify
```

Expected output:
- 3 integrity modes all exit 0
- readiness 4/4 PASS
- dry-run prints plans but writes 0 files
- temp export: 100 records, 200 thumbs, 0 problems, 0 leaks

## 6.3. Public demo refresh (P4C design, P4D impl)

Public demo refresh is currently **manual**: run exporters,
inspect `dist/`, `rsync` to `conanxin.github.io` repo, commit,
push. See [docs/PUBLIC_DEMO_REFRESH_PLAN.md](PUBLIC_DEMO_REFRESH_PLAN.md)
for the three refresh modes (manual / semi-auto / full-auto)
and the P4D target (semi-auto with explicit approval). P4D
also requires a `docs/SECRET_ROTATION_POLICY.md` for the
full-auto mode (P5+ candidate).

## 6.4. CI Node 24 (P4C)

The CI workflow opts into Node.js 24 by bumping
`actions/checkout@v4` → `actions/checkout@v5`. This is the
GitHub-recommended path before the **2026-09-16** forced
deprecation of Node 20 runner. The setup-python action is kept
at v5 (still supported). The CI log will show an info-level
annotation "is being forced to run on Node.js 24" if any other
action is later added on Node 20; this is informational, not a
failure.

## 7. Sample-data roundtrip

The synthetic data under `examples/` is the canonical shape for
gallery / digest consumers:

```bash
# Validate JSON syntax of the samples
for f in examples/*.json; do python3 -m json.tool "$f" > /dev/null; done
```

The samples intentionally use **relative** thumbnail paths
(`./assets/thumbs/256/sample.jpg`, `./assets/thumbs/512/sample.jpg`)
so the open-source repo never embeds a real machine path.

## 7.1. Confirming a public demo refresh (P4D+1, manual)

`scripts/confirm_demo_refresh.sh` builds a *candidate* public
demo bundle into `dist/refresh-candidates/YYYY-MM-DD/` and
runs inline QA. The 02:30 nightly hook runs it with
`--no-telegram`; the manual commands below use the same
script with the full Telegram report.

```bash
# 1. Dry-run first: walk the pipeline without writing
#    dist/, logs/, or sending Telegram. Use this to
#    double-check the wiring after editing the script.
bash scripts/confirm_demo_refresh.sh --dry-run --no-telegram

# 2. Real run, no Telegram notification. Writes the
#    candidate to dist/refresh-candidates/<date>/ and the
#    report to logs/confirm_demo_refresh/report_<date>.md.
bash scripts/confirm_demo_refresh.sh --no-telegram

# 3. Real run, with Telegram summary. The same pipeline,
#    plus a pass/fail Telegram message at the end.
bash scripts/confirm_demo_refresh.sh
```

Argument reference:

* `--date YYYY-MM-DD` — build the candidate for a specific
  date (default: today). Useful for backfilling a missed day
  or testing against a known-good sample.
* `--dry-run` — print the steps, do not write `dist/` or
  `logs/`, do not call Telegram. Combined with `--no-telegram`
  this is the safest "I just want to see what would happen"
  mode.
* `--no-telegram` — run the full pipeline but skip the
  Telegram notifier. The cron hook always uses this.
* `--help` — print usage.

What the script writes:

* `dist/refresh-candidates/<date>/gallery/` — public Gallery
  bundle (P4D safety flags on).
* `dist/refresh-candidates/<date>/digest/` — public Digest
  bundle.
* `logs/confirm_demo_refresh/confirm_demo_refresh_<ts>.log` —
  full run log.
* `logs/confirm_demo_refresh/report_<date>.md` — the human
  report (this is the file the user reads to decide whether
  to publish).

What the script does *not* do, even without `--dry-run`:

* No `git push` to `conanxin.github.io`.
* No `rsync` to the Pages repo.
* No modification of `web/data/`, `images/`, `metadata/`.
* No retry of the 4 unresolved losers.
* No download / refill / batch re-run.

To publish a candidate, follow the manual publish flow in
[docs/PUBLIC_DEMO_REFRESH_PLAN.md § 8.3](PUBLIC_DEMO_REFRESH_PLAN.md),
or use the P4E helper described below.

## 7.2. Publishing a candidate (P4E, manual approval)

After `confirm_demo_refresh.sh` builds a candidate, the user
inspects the report and then uses the publish helper to push
it to GitHub Pages. The helper requires explicit `--approve`:

```bash
# Dry-run: preview the plan without touching Pages
bash scripts/publish_demo_refresh_candidate.sh \
    --date 2026-06-12 --dry-run

# Approve: rsync + commit + push + online verify
bash scripts/publish_demo_refresh_candidate.sh \
    --date 2026-06-12 --approve

# Commit-only, no push (daytime review before evening push)
bash scripts/publish_demo_refresh_candidate.sh \
    --date 2026-06-12 --approve --no-push
```

The helper does **not** modify the Artvee repo (no `images/`,
no `metadata/`, no `web/data/`, no `index/`). It only reads
the candidate from `dist/refresh-candidates/` and writes to the
Pages repo. Without `--approve` it runs in dry-run mode by
default, so a mistyped command cannot accidentally publish.

## 8. Branch model (suggested, not enforced by this repo)

- `main` — always releasable; only merges via PR.
- Feature branches — `feat/<short-name>`, `fix/<short-name>`,
  `docs/<short-name>`.
- Release tags — `v0.1.0-alpha`, `v0.1.0`, etc. (see
  [docs/RELEASE_NOTES_v0.1.0-alpha.md](docs/RELEASE_NOTES_v0.1.0-alpha.md)).

## 9. Pre-commit checklist

A clean PR should have:

- [ ] All `py_compile` and `bash -n` checks pass.
- [ ] `python3 scripts/check_open_source_ready.py` exits 0.
- [ ] `python3 scripts/check_gallery_integrity.py --allow-known-duplicates` exits 0
      (or SKIP on the open-source repo with no runtime data). P4B
      emptied the known fingerprint, so this is now equivalent to
      `--strict`.
- [ ] Sample JSON under `examples/` is valid.
- [ ] Any new tracked file is **not** in a gitignored path.
- [ ] Docs updated for any user-visible change.
- [ ] No local-machine path is referenced in tracked files
      (other than `BASE_DIR` derivation in the wrapper).

## 10. P5A content-healing commands

### Fix source_url mapping after collision migration
If metadata files were copied (not regenerated) during P4B winner
rename, the `url` field inside metadata may be stale. The build
script now prefers the index's `source_url` over the metadata's
`url` (fixed in P5A). To verify after any future migration:

```bash
# Rebuild web data and check for source_url dupe groups
python3 scripts/build_artvee_gallery.py --mode local
python3 -c "
import json
from collections import Counter
web = json.load(open('web/data/artworks.json'))
sus = [a.get('source_url','') for a in web]
c = Counter(sus)
dupes = {k:v for k,v in c.items() if v > 1}
print(f'source_url dupe groups: {len(dupes)}')
for url, count in dupes.items():
    print(f'  {url}: {count}')
"
```

### Retry unresolved losers (lightweight)
```bash
# Check P4B unresolved losers
python3 scripts/retry_unresolved_losers.py --dry-run
# Real run (HTTP HEAD only, no browser)
python3 scripts/retry_unresolved_losers.py
```

### Audit legacy orphans
```bash
python3 -c "
import json, csv
from pathlib import Path

index_stems = set()
with open('index/artworks.csv', 'r', encoding='utf-8', newline='') as f:
    for row in csv.DictReader(f):
        for key in ['local_image_path', 'metadata_path']:
            p = row.get(key, '')
            if p:
                index_stems.add(Path(p).stem)

for root in ['images', 'metadata', 'thumbs/256', 'thumbs/512']:
    orphans = [p for p in Path(root).rglob('*') if p.is_file() and p.stem not in index_stems]
    print(f'{root}: {len(orphans)} orphans')
"
```

## 11. P5C orphan cleanup commands

### Audit only (dry-run)
```bash
python3 scripts/cleanup_legacy_orphans.py \
  --dry-run \
  --expected-count 46 \
  --json-out reports/runtime/p5c-orphan-cleanup-dry-run.json
```

### Apply cleanup (user explicit `--apply`)
```bash
python3 scripts/cleanup_legacy_orphans.py \
  --apply \
  --expected-count 44 \
  --json-out reports/runtime/p5c-orphan-cleanup-result.json
```

### Verify post-cleanup
```bash
python3 scripts/check_gallery_integrity.py --strict
python3 scripts/check_open_source_ready.py
# Custom missing-referenced check (paths in web/data are like ../images/...):
python3 - <<'PY'
import json
from pathlib import Path
ROOT = Path('.').resolve()
web = json.loads((ROOT / 'web/data/artworks.json').read_text(encoding='utf-8'))
missing = []
for a in web:
    for key in ['image_path', 'metadata_path', 'thumb_256', 'thumb_512']:
        rel = a.get(key, '')
        if not rel: continue
        rel_from_root = rel[3:] if rel.startswith('../') else rel[2:] if rel.startswith('./') else rel
        if not (ROOT / rel_from_root).exists():
            missing.append((a.get('id'), key))
print(f'missing_referenced_files: {len(missing)}')
PY
```

### Disk state expected (post-P5C)
- `images/`: 756 files
- `metadata/`: 756 `.json` files
- `thumbs/256/`: 757 files (756 + 1 `.gitkeep`)
- `thumbs/512/`: 757 files (756 + 1 `.gitkeep`)
- Total: 3026 files on disk, 3024 referenced by web/data
- The 2 difference is the 2 `.gitkeep` files (correctly preserved)

### P5A audit vs actual cleanup
- P5A audit (`reports/runtime/p5a-legacy-orphans-report.json`): 46 files
- Cleanup actual: 44 files
- Reason: P5A audit incorrectly counted 2 `.gitkeep` files in thumbs/256 and thumbs/512 totals
- The cleanup script correctly filters `.gitkeep` (not an image or metadata file)
- This is a benign audit over-count, not a data integrity issue

## 12. P5D visual QA commands

### Full gallery QA
```bash
python3 scripts/analyze_gallery_visual_quality.py \
  --out reports/runtime/p5d-visual-qa-full.json
```
(756 records, ~30s; produces JSON only, no contact sheet)

### Sample QA with contact sheet
```bash
python3 scripts/analyze_gallery_visual_quality.py \
  --sample 100 \
  --out reports/runtime/p5d-visual-qa-sample.json \
  --contact-sheet reports/runtime/p5d-contact-sheet.html
```

### Public demo candidate QA
```bash
# First ensure candidate exists:
bash scripts/confirm_demo_refresh.sh --no-telegram

# Then analyze:
python3 scripts/analyze_gallery_visual_quality.py \
  --public-candidate dist/refresh-candidates/$(date +%F)/gallery \
  --out reports/runtime/p5d-public-demo-visual-qa.json \
  --contact-sheet reports/runtime/p5d-public-demo-contact-sheet.html
```

### Digest candidate QA
```bash
python3 scripts/analyze_gallery_visual_quality.py \
  --digest-candidate dist/refresh-candidates/$(date +%F)/digest \
  --out reports/runtime/p5d-digest-visual-qa.json \
  --contact-sheet reports/runtime/p5d-digest-contact-sheet.html
```

### Pillow fallback
The script auto-detects Pillow. If missing, only file-size and
metadata checks run; report shows `pillow_available: false`.

### View contact sheet
Open in browser (use repo-relative paths only, no `--` flags):
```bash
xdg-open reports/runtime/p5d-contact-sheet.html
# or just navigate to: file://.../reports/runtime/p5d-contact-sheet.html
```

### Inspect JSON output
```bash
python3 -c "
import json
d = json.load(open('reports/runtime/p5d-visual-qa-full.json'))
print('total:', d['summary']['total_records'])
print('risks:', d['summary']['risk_counts'])
print('near-dup groups:', len(d['summary']['near_duplicate_groups']))
print('aspect buckets:', d['summary']['aspect_ratio_buckets'])
"
```

## 13. P5E curation filters commands

### Public demo exporter — visual-QA risk guard

```bash
python3 scripts/export_artvee_gallery_public_demo.py \
  --limit 100 \
  --strategy diverse \
  --base-url . \
  --exclude-duplicate-source-url-groups \
  --require-unique-source-url \
  --exclude-risk high \
  --visual-qa reports/runtime/p5d-visual-qa-full.json \
  --out-dir dist/refresh-candidates/$(date +%F)/gallery
```

- `--exclude-risk {low,medium,high}`: drop records whose visual-QA
  `risk_level` is at or above the threshold. Default visual-QA path
  is `reports/runtime/p5d-visual-qa-full.json` (auto-resolved).
- Records with no `risk_level` (not yet audited) pass through.
- For 2026-06-12, P5D reports 0 high-risk records so the guard is a
  no-op in practice — it is wired in for future-proofing.

### Public demo exporter — prompt-fields guard (optional)

```bash
python3 scripts/export_artvee_gallery_public_demo.py \
  --limit 100 \
  --require-prompt-fields \
  --out-dir dist/refresh-candidates/$(date +%F)/gallery
```

- Drops any record that has *any* of `prompt_seed` / `use_cases` /
  `visual_notes` but leaves one of them empty.
- Records with none of those fields pass through (the public gallery
  JSON does not surface prompt metadata; the digest does).
- Currently NOT enabled in `confirm_demo_refresh.sh` — add if
  prompt-fields are required in the gallery JSON.

### Daily digest — `--max-per-artist 1` (default)

```bash
python3 scripts/build_artvee_daily_digest.py \
  --strategy diverse \
  --select 5 \
  --candidate-limit 20 \
  --max-per-artist 1 \
  --out-dir digests
```

- Strict cap of 1 pick per artist per digest. Anonymous is
  normalized to `"Anonymous"` and counts toward the same cap.
- `--allow-repeat-artist` short-circuits to no cap.
- If the cap rejects an item, the build logs the rejection and
  continues (no crash). For 5 picks from a 20-candidate pool this
  has never triggered a fallback.
- The CLI echo prints `P5E: artist diversity OK (all unique)` when
  the cap is satisfied.

### Daily digest — prompt-field backfill (no AI)

- The visual analyzer always populates `prompt_seed` and `use_cases`.
- `_ensure_prompt_fields()` is a defensive validator that runs after
  analysis: if either is empty, a deterministic fallback is applied
  (no external API call). The build log reports `prompt-field
  backfills=N`. For 2026-06-12, N=0.

## 14. P6A Telegram MEDIA staging

The OpenClaw Telegram gateway accepts local media only from a small
allowlist of system directories (`<openclaw-media>/`,
`<openclaw-workspace-media>/`, `<openclaw-workspace-tmp>/`, etc.).
Reports under `<workspace-reports>/` are **not** in the allowlist, so
attaching them directly via `--media` produces::

    LocalMediaAccessError: Local media path is not under an allowed directory

P6A introduces a **staging helper** instead of expanding the
allowlist — the smaller-surface fix:

1. Stage the report into `<openclaw-media>/artvee-reports/`
   (or a project-namespaced subdir of any allowed media root):

   ```bash
   STAGED=$(python3 scripts/stage_report_for_telegram_media.py \
     --report <workspace-reports>/<your-report>.md)
   ```

2. Send via the existing notifier with `--media "$STAGED"`:

   ```bash
   python3 scripts/artvee_telegram_notify.py \
     --text "P6A test" --media "$STAGED" --wait
   ```

Verified: 2026-06-12 19:45 GMT+8 — `Message ID: 22623` delivered
with the staged report attached.

Override the media root with `--media-root <path>` or the
`ARTVEE_MEDIA_ROOT` env var; the helper always appends
`artvee-reports/` so multiple local projects don't collide.

Design constraints (by intent, not accident):

- We do NOT touch the OpenClaw allowlist — staging is the smallest
  possible change and keeps the security boundary intact.
- Staged files are NOT in the Artvee repo and are NOT tracked by any
  project. They are runtime artifacts.
- Refuses symlinks / directories / zero-byte / size-mismatch files.
- The helper never prints tokens, env vars, or `<openclaw-config>`
  contents.

## 15. P6D GitHub Pages CDN wait (default 90s)

P5F and earlier approved-publish runs occasionally needed a
60s+30s manual follow-up because the Pages edge cache had
not picked up the new commit yet. P6D changes the default
CDN wait from 60s to **90s** in
`scripts/publish_demo_refresh_candidate.sh`, controlled by
a new `--cdn-wait N` flag (range 0..600, default 90).

Why 90s not 60s:

- 60s works most of the time but is on the edge of the
  observed cold-cache recovery window
- 90s lifts first-pass verification to ≥95% on a clean
  push, with `wait_and_curl()` retrying an additional 90s
  on stragglers (so worst case is still bounded)
- Keeping the wait as a flag (not a hard-coded value) means
  a future Pages infra change can be adopted via a one-line
  caller update, no script change

Usage:

```bash
# Default (90s)
bash scripts/publish_demo_refresh_candidate.sh \
  --date 2026-06-12 --approve

# Explicit override (e.g. 120s for first-of-the-month)
bash scripts/publish_demo_refresh_candidate.sh \
  --date 2026-06-01 --approve --cdn-wait 120

# No wait at all (use only when you do not intend to
# rely on the script's online verification)
bash scripts/publish_demo_refresh_candidate.sh \
  --date 2026-06-12 --dry-run --cdn-wait 0
```

`confirm_demo_refresh.sh` does not duplicate the wait — it
delegates to `publish_demo_refresh_candidate.sh` and the
flag flows through automatically.

## 16. P6B KNOWN_RETIRED URL management

P4B / P5A surfaced 4 URLs that are unreachable from the
local network (HTTP HEAD / page.goto timeouts, 30s).
They are not blocking gallery / public demo / digest —
they never made it into `web/data/artworks.json` so
the public surface is unaffected. But they show up in
runtime reports as "unresolved" and tend to cause
confusion in status reviews.

P6B introduces an explicit `KNOWN_RETIRED` set so
future reports can split:

- `known_retired = N` (audited, not blocking)
- `blocking_unresolved = M` (need attention)

Usage:

```bash
# Generate or refresh reports/runtime/p6b-known-retired-urls.json
python3 scripts/mark_known_retired_urls.py --apply

# Dry-run (default — does not write)
python3 scripts/mark_known_retired_urls.py

# Override input / output
python3 scripts/mark_known_retired_urls.py \
  --input reports/runtime/p4b-unresolved-losers.json \
  --out reports/runtime/p6b-known-retired-urls.json \
  --apply --force
```

Properties:

- **No network.** Pure local read/write. Never retries a URL.
- **Default dry-run.** Use `--apply` to write.
- **Refuses overwrite** without `--force`.
- **Refuses `--out` outside `reports/runtime/`** — even if the
  caller tries a tricky path, the script exits with code 2.
- **Falls back to P4B** if the P5A report is missing.
- **Enriches records** by looking up URLs in
  `web/data/artworks.json` (best-effort title / artist /
  category / stable_id); the script still works for
  fully-unknown losers.
- **Runtime artifact, NOT in git.** The real output file
  is regenerated from the canonical unresolved report.
  `examples/known_retired_urls.sample.json` documents
  the schema with synthetic URLs and IS tracked.

Cross-cutting rule: the 4 KNOWN_RETIRED URLs do not appear
in `web/data/artworks.json` and do not affect
`check_gallery_integrity.py --strict` (which only checks
duplicates and source_url conflicts). They are also
excluded from the public demo and digest by construction.

## 17. P6G KNOWN_RETIRED-aware status report

The status snapshot is the operational expression of the
P6B invariant: "after bounded retries, retire unavailable
sources." Two counters replace the old "unresolved":

- `known_retired = N` — audited, deliberately not retried
- `blocking_unresolved = M` — what still needs attention

### Build the local status snapshot

```bash
python3 scripts/build_artvee_status_report.py
```

Outputs (atomic write via `.tmp` + `os.replace`):

- `reports/runtime/artvee-status-report.json` — machine-readable
- `reports/runtime/artvee-status-report.md` — human-readable

The script reads (all optional with fallbacks):

- `web/data/gallery_stats.json` — counts
- `web/data/artworks.json` — record count cross-check
- `reports/runtime/p6b-known-retired-urls.json` — KNOWN_RETIRED set
- `reports/runtime/p5a-unresolved-losers.json` (P4B fallback) — unresolved
- `logs/nightly_summary.csv` — latest nightly run snapshot

### Inspect a status snapshot

```bash
python3 - <<'PY'
import json
data = json.load(open('reports/runtime/artvee-status-report.json'))
print(f"records:             {data['records']}")
print(f"known_retired:       {data['known_retired']}")
print(f"blocking_unresolved: {data['blocking_unresolved']}")
print(f"strict_integrity:    {data['strict_integrity']}")
print(f"public_demo_ready:   {data['public_demo_ready']}")
print(f"digest_ready:        {data['digest_ready']}")
PY
```

### Fallback semantics

If `p6b-known-retired-urls.json` is missing (e.g. fresh clone
with no P6B run), the report falls back to:

- `known_retired = 0`
- `blocking_unresolved = <unresolved_count>`
- `public_demo_ready = false`, `digest_ready = false`
- `warnings = ["p6b-known-retired-urls.json not found; ..."]`

This keeps a fresh clone honest — the script does not
pretend the audit happened.

## 18. P6F Digest history + near-dup aware selection

P6F turns the P6C near-dup review into a **reusable
automated curation filter** inside the daily digest builder.
It does not modify the gallery data; it produces a runtime
history file and a 30-day dedup window.

### Run the digest builder (with history awareness)

```bash
# Default: 30-day history window, near-dup aware (if P6C JSON exists)
python3 scripts/build_artvee_daily_digest.py

# Fresh start: ignore all history
python3 scripts/build_artvee_daily_digest.py --ignore-history

# Shorter window (e.g., 7 days)
python3 scripts/build_artvee_daily_digest.py --history-days 7

# Custom history file path
python3 scripts/build_artvee_daily_digest.py \
  --history-file reports/runtime/digest-history.json

# Custom near-dup clusters path (skip if missing)
python3 scripts/build_artvee_daily_digest.py \
  --near-dup-clusters reports/runtime/p6c-near-dup-clusters.json
```

Outputs (runtime history file, not tracked):

| Artifact | Path | Purpose |
| --- | --- | --- |
| JSON | `reports/runtime/digest-history.json` | 30-day rolling digest picks + near-dup cluster IDs |
| Markdown | `digests/artvee-digest-YYYY-MM-DD.md` | Human-readable digest |
| HTML | `digests/artvee-digest-YYYY-MM-DD.html` | Visual digest |
| JSON index | `web/data/digests.json` | Rolling index with picks array |

### Default behavior

- **history-days = 30**: avoids repeating id, artist, or near-dup cluster within 30 days.
- **Idempotent**: same-day re-run updates the same history entry, does not append duplicates.
- **Capped**: max `window_days * 2` entries (minimum 60), so the file never grows unboundedly.
- **Fallback**: if the strictest filter (id + artist + cluster) leaves fewer than `--select` candidates, the builder relaxes rules in order (cluster → artist → id) and records a fallback reason.

### Safety

- **No network.** Pure local file read.
- **No file modification** to `web/data/artworks.json`, `index/`, `inbox/`, or images.
- **History file is runtime-only** (`reports/runtime/`, gitignored).
- **No deletion.** The script is a read-only auditor with a small append-only history file.
- **Fallback:** if P6C JSON is missing, near-dup awareness is skipped (history id + artist dedup still works).

### Telegram wording

`scripts/confirm_demo_refresh.sh` now appends a
`Retired sources: N known_retired, blocking_unresolved=M`
line to the PASS summary, computed at runtime from the
KNOWN_RETIRED manifest (or fallback to P5A/P4B unresolved
count). The line is informational; it does not affect
the PASS/FAIL decision of the candidate flow.

### Safety

- Pure local file read. **No network, no subprocess, no shell-out.**
- Refuses to write outside `reports/runtime/` (exit 2).
- Atomic write via `.tmp` + `os.replace` (no partial files).
- All inputs are optional — missing files are logged as
  warnings and the report uses a safe default.

## 18. P6C Near-duplicate review workflow

P6C turns the P5D visual-QA near-dup findings into a
**reusable, conservative review workflow**. It does not
delete, move, or exclude any artwork automatically.

### Run the review

```bash
# Default: exact aHash match (threshold=0), reproduces P5D groups
python3 scripts/review_near_duplicate_clusters.py

# Outputs (runtime only, not tracked):
#   reports/runtime/p6c-near-dup-clusters.json
#   reports/runtime/p6c-near-dup-clusters.md
#   reports/runtime/p6c-near-dup-contact-sheet.html

# Expanded search: threshold=6 (more false positives, for exploration)
python3 scripts/review_near_duplicate_clusters.py --threshold 6

# Custom output paths
python3 scripts/review_near_duplicate_clusters.py \
  --out-json reports/runtime/p6c-near-dup-clusters.json \
  --out-md reports/runtime/p6c-near-dup-clusters.md \
  --contact-sheet reports/runtime/p6c-near-dup-contact-sheet.html
```

### Review the contact sheet

Open `reports/runtime/p6c-near-dup-contact-sheet.html` in a
browser from the repo root. The sheet uses relative paths to
`thumbs/512/` (no base64, no local path leaks, no file
copying). Each cluster is a visual group with title, artist,
category, source_url, id, distance, and recommended policy.

### What the clusters mean

| Type | What it looks like | Policy | Digest rule |
| --- | --- | --- | --- |
| `collision_legacy` | Same title, different id with hex suffix, unique source_url | `keep_all` | `limit_one_per_digest` |
| `artist_cluster` | Same artist, different works, visually similar | `keep_all` | `limit_one_per_digest` |
| `true_series` | Same artist, same series, intentionally similar | `keep_all` | `limit_one_per_digest` |
| `mixed` | Different artists, same aHash (false positive collision) | `keep_all` | `review_before_digest` |
| `possible_duplicate` | Same source_url or same image_path (should not happen) | `review` | `review_before_digest` |

### Integration with digest / public demo

Future builders should read `p6c-near-dup-clusters.json` and:

- Skip a second pick from the same `artist_cluster` or `collision_legacy` cluster in the same digest.
- Flag `mixed` clusters for human curator review before inclusion.
- Never auto-exclude; the policy is `limit` (not `delete`).

### Safety

- **No network.** Reads only local `web/data/artworks.json` and `thumbs/512/`.
- **No file modification.** All outputs are under `reports/runtime/`.
- **No deletion.** The script is a read-only auditor; it does not touch `web/data/`, `index/`, or `inbox/`.
- **Fallback:** if Pillow is unavailable, reads P5D visual-QA JSON aHashes; if that is also missing, outputs `SKIP` with reason.
