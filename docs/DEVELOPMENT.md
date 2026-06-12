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
