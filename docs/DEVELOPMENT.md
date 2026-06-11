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
- [ ] Sample JSON under `examples/` is valid.
- [ ] Any new tracked file is **not** in a gitignored path.
- [ ] Docs updated for any user-visible change.
- [ ] No local-machine path is referenced in tracked files
      (other than `BASE_DIR` derivation in the wrapper).
