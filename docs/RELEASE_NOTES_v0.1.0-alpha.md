# Release Notes · v0.1.0-alpha

> The first open-source-facing release. The repository is now
> self-describing, has a single canonical ignore file, a privacy
> surface that is machine-checked, and a public MIT license.

## 1. What is in this release

### Documentation
- `README.md` rewritten as a self-contained entry point with a
  live demo link, a "what is and is not included" section, an
  architecture diagram, a quick-start section, and a docs index.
- `docs/ARCHITECTURE.md` — end-to-end data flow, per-script
  responsibilities, generated-vs-tracked boundary, nightly
  wrapper post-batch flow, public demo flow.
- `docs/OPEN_SOURCE_BOUNDARIES.md` — what ships in the repo, what
  does not, why the public demo is safe, the risk surface that
  is checked at release time, and a migration note for forks.
- `docs/ROADMAP.md` — past phases (P1, P2, P3A, P3B, P3C, E2E
  cron verification), near-term (P3D, P3E), mid-term, long-term.
- `docs/DEVELOPMENT.md` — local dev loop, syntax checks, the
  smoke flow, what **not** to run in dev, the readiness check,
  branch model, pre-commit checklist.
- `docs/PROJECT_STATUS.md` — current phase markers and the
  last-known-good nightly snapshot.
- `docs/RELEASE_NOTES_v0.1.0-alpha.md` — this file.
- Existing `docs/GALLERY_*.md` files retained for deep dives into
  data schema, local usage, public demo, and digest builder.

### License
- `LICENSE` — MIT, full standard text.

### Sample data
- `examples/artworks.sample.json` — 3 synthetic records.
- `examples/gallery_stats.sample.json` — minimal stats object.
- `examples/digest.sample.json` — minimal digest index entry.

All sample paths are relative (`./assets/thumbs/...`) and reference
non-existent files; the samples are shape references, not usable
artworks.

### Repo hygiene
- `.gitignore` consolidated; placeholders (`.gitkeep`) preserved for
  the empty `dist/`, `digests/`, `thumbs/{256,512}/`, `web/data/`
  directories.
- The legacy `.gitignore.local` (identical content, outdated
  comment) was removed.

### Wrapper path-agnosticism
- `scripts/artvee_nightly_wrapper.sh` now derives `BASE_DIR` from
  its own location via `$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)`,
  replacing the previous hardcoded `$HOME/...` paths.
- `PYTHON` defaults to `python3` from `PATH`; can be overridden by
  `ARTVEE_PYTHON` environment variable.

### Safety check
- `scripts/check_open_source_ready.py` — a pure-stdlib,
  read-only, exit-coded check that fails the build on:
  - tracked files in gitignored directories,
  - path leaks (`/home/`, `~/`, `hermes-agent`) in non-source text files,
  - real-looking secrets (`password = "..."`, `token = "..."`,
    `secret = "..."`),
  - tracked files > 1 MB.

## 2. Verification status

| Check | Result |
| --- | --- |
| `py_compile` on all shipped scripts | ✅ |
| `bash -n` on shipped shell scripts | ✅ |
| `python3 scripts/check_open_source_ready.py` | ✅ PASS |
| `git ls-files` against gitignore surface | ✅ no generated data tracked |
| Public demo live at <https://conanxin.github.io/projects/artvee-gallery-demo/> | ✅ |
| Nightly cron auto-run (2026-06-12 02:00) | ✅ PASS |
| Last-known-good nightly snapshot | 760 downloaded, 0 failed, 530 pending |

The most recent nightly verification report lives at
`~/workspace/reports/artvee-nightly-auto-run-verification-2026-06-12.md`
in the maintainer's local workspace; it is intentionally **not**
committed to this repository.

## 3. Limitations

- The repository does **not** include a corpus. To exercise the
  local UI shell, the user must populate `images/`, `metadata/`,
  and `index/` locally. This is by design — see
  [docs/OPEN_SOURCE_BOUNDARIES.md](docs/OPEN_SOURCE_BOUNDARIES.md).
- The Telegram notifier depends on a local OpenClaw CLI as the
  message bridge. Users without that bridge can simply skip the
  notify step (the wrapper isolates it with `|| true`).
- Source-code privacy is verified by code review and the readiness
  check; it is not enforced by `.gitignore` (which is correct:
  source files are tracked).
- The sample data uses fictitious IDs and categories; it is not
  a working subset of any real archive.

## 4. Next steps

See [docs/ROADMAP.md](docs/ROADMAP.md) § "Near-term":

- **P3D** — Standalone public GitHub repository: initialise, push
  only the open-source surface area, configure branch protection
  and a CI job that runs `check_open_source_ready.py` on every PR.
- **P3E** — Public daily-digest page, alongside the existing
  public gallery demo.

## 5. Acknowledgements

- Data source: [artvee.com](https://artvee.com) public-domain art
  archive.
- The local-first / open-source boundary pattern is inspired by
  the standard "thin shell, fat scripts" approach for data tooling.
