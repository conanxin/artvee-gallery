# Local-First Agent Project Pattern

> A reusable methodology for agent-driven projects that collect or
> curate local data and want to become shareable artifacts without
> exposing the underlying archive. Extracted from
> [Artvee Gallery](CASE_STUDY.md). The pattern is general; the
> project is one instance.

## 1. The pattern

```
Local data
   │
   ▼
Deterministic automation (cron / on-demand)
   │
   ▼
Observable wrapper (logs + compact human summary)
   │
   ▼
Local UI / browse surface
   │
   ▼
Public artifact (curated, lightweight, CDN-friendly)
   │
   ▼
Open-source boundary (license + .gitignore + secret/asset separation)
   │
   ▼
CI gate (forbidden-paths + path-leak + size + secret-keyword)
   │
   ▼
Public showcase (README badges, screenshots, methodology)
   │
   ▼
Methodology doc (← you are here)
```

Each arrow is a *deliberate boundary*, not an automatic one. The
project must consciously decide what crosses each boundary, in what
shape, and at what cost.

## 2. Why this pattern works

The pattern is essentially **progressive disclosure applied to a
software project**. The 1.4 GB archive is the maintainer's full
view; the 5.7 MB public gallery is the casual visitor's view; the
324 KB daily digest is the returning visitor's view. Each tier
answers a different question ("what is this?", "show me a
sample", "what changed today?") and exposes a different surface
area to the world.

Three properties make the pattern durable:

1. **Each tier is regenerated from the tier below it.** A bug fix
   in the local archive propagates upward; a redesign of the
   public demo does not require touching the local archive.
2. **Each tier is small enough to read in one sitting.** The
   maintainer can grep the entire source tree, audit the entire
   public bundle, and skim the entire daily digest without
   scrolling. Boredom is a feature.
3. **The boundary is enforced by a CI gate, not by discipline.**
   Discipline is renewable; the gate is permanent. Future
   contributors cannot accidentally regress the boundary because
   CI will reject the commit.

The pattern is also **composable**. You do not have to ship all
tiers at once. P1 (local UI) and P2 (public demo) are independent;
P3A (publish) is independent of P3B (digest). The pattern suggests
an order, not a requirement.

## 3. When to use it

Use this pattern when the project fits all four of the following:

- **Local data is the source of truth.** The project owns a folder
  that the maintainer can point at and say "this is what we have".
- **The data is too large, too personal, or too unstable to
  publish directly.** Examples: 1.4 GB of art, a personal
  document collection, a daily screenshot folder, a
  notes-and-screenshots second-brain, an agent task pipeline.
- **The project has or wants a public surface.** Either because
  the public-facing artifact is the point, or because the
  maintainer wants to share the methodology.
- **The work can be deterministic.** The data collection or
  curation can run on a schedule, produce the same output given
  the same input, and emit a single greppable summary.

If any of these is missing, the pattern is overkill. A pure
software project with no data does not need a "local archive"
tier. A pure data project with no public surface does not need a
"public artifact" tier. The pattern is for *data projects that
want to be shareable*.

### Concrete examples that fit

- **Auto-collected reading material** (e.g. a daily arxiv digest
  → a public daily email)
- **Personal media library** (e.g. a self-hosted photo curation
  → a public weekly pick)
- **Local knowledge base** (e.g. a personal wiki → a public FAQ
  for the topics that are shareable)
- **Agent task pipeline** (e.g. a job log → a public status page)
- **Open dataset derivation** (e.g. a public dataset → a
  derivative blog post)
- **Self-collected data** (e.g. daily temperature readings →
  a public weather visualization)

### Anti-examples

- **Pure SaaS products** — no local data, no real boundary
  problem; use a normal CI/CD pipeline.
- **Highly dynamic data** — if the data changes every second,
  the deterministic-automation tier breaks down.
- **Regulated data** — health, finance, PII. The pattern is
  for *content* projects where the maintainer can choose what
  to publish.

## 4. Stage template

For each stage, write down all six fields. This is the minimum
that survives the project into a public showcase.

| Field | Question to answer |
| --- | --- |
| **Goal** | What is this stage's deliverable, in one sentence? |
| **Design reason** | Why this shape and not another? |
| **Files changed** | What is added, modified, deleted? |
| **Verification** | What command proves it works? (py_compile, curl, readiness, etc.) |
| **Impact analysis** | What does this stage *not* touch? What is the blast radius? |
| **Human-readable current state** | One sentence a non-engineer can read. |

The "design reason" and "human-readable current state" fields are
the ones most projects skip. They are also the most important.
The design reason prevents the next maintainer from undoing the
boundary by accident. The human-readable state is what the
maintainer reads at 02:00 when the cron job fails.

### Worked example: P2 (Public Demo Export) for Artvee Gallery

| Field | Value |
| --- | --- |
| **Goal** | Emit a curated static bundle suitable for any static host. |
| **Design reason** | 100 picks × 2 thumb sizes is 5.7 MB — small enough to ship anywhere, large enough to feel like a real gallery. |
| **Files changed** | `scripts/export_artvee_gallery_public_demo.py` (new), `dist/artvee-gallery-public-demo/` (new, ignored). |
| **Verification** | `py_compile` + `curl -I` on a 1-minute local server + leak grep. |
| **Impact analysis** | Does not touch `images/`, `metadata/`, or the night batch. The export is read-only on sources. |
| **Human-readable current state** | "There is a 100-piece public gallery at `<demo-url>`, updated whenever we re-run the export." |

## 5. Checklist

A pre-commit checklist for any new stage in a local-first project.

### 5.1 Pre-design

- [ ] Have I named the *tier* this stage belongs to? (local / public
      artifact / open-source / showcase)
- [ ] Is the boundary between this tier and the next explicitly
      defined (in code, in docs, or both)?
- [ ] Is the data flow from the previous tier to this tier
      one-way, or are there feedback loops?

### 5.2 Code

- [ ] All new scripts use only the Python standard library (or
      document why a non-stdlib dependency is required).
- [ ] No script reads or writes paths it does not own.
- [ ] Idempotency: re-running the script does not duplicate,
      corrupt, or skip.
- [ ] Determinism: same input + same date = same output.
- [ ] Errors are caught at the boundary, with a non-zero exit
      code and a clear error message.

### 5.3 Public surface

- [ ] No `images/`, `metadata/`, `thumbs/`, `dist/`, `digests/`,
      `logs/`, `inbox/`, or `web/data/*.json` is tracked in git
      (except `.gitkeep` placeholders).
- [ ] No tracked text file contains private-path patterns
      (project-specific; typically user home, tilde expansion,
      and the local agent project directory).
- [ ] No single tracked file exceeds 1 MB.
- [ ] Public bundle is CDN-friendly: relative paths, no
      server-side logic, no auth.

### 5.4 Docs

- [ ] The new stage has a section in the project story
      (CASE_STUDY) and a section in the retrospective
      (RETROSPECTIVE).
- [ ] The new stage has at least one "design reason" sentence
      in the ROADMAP.
- [ ] The PROJECT_STATUS phase marker is updated to ✅ PASS
      (or ❌ FAIL with reasons).

### 5.5 Verification

- [ ] `python3 scripts/check_open_source_ready.py` returns
      `Overall: PASS`.
- [ ] `py_compile` of every Python script returns 0.
- [ ] `bash -n` of every shell script returns 0.
- [ ] The CI workflow runs all of the above and the green badge
      is showing.

### 5.6 Observability

- [ ] The night wrapper emits a single greppable summary line.
- [ ] The summary line includes: success count, failure count,
      date, and one stage-specific tag.
- [ ] Errors are visible without tailing the full log.

## 6. Common failure modes

These are the failure modes we saw, in order of severity.

1. **"Just commit the data, it's easier"**. The most common
   failure mode. Resisted by the `.gitignore` and the CI gate.
2. **"Just publish the archive, it's the same thing"**. Second
   most common. Resisted by the curated-export step.
3. **"The CI is too strict, let me bypass it for this one commit"**.
   The gate is permanent; bypassing it once creates a precedent
   that erodes the boundary. If the gate is too strict, fix the
   gate, do not bypass it.
4. **"The notification is too verbose, let me silence it"**. A
   silent failure is worse than a loud one. If the notification
   is too verbose, fix the notification, do not silence it.
5. **"Let's auto-publish from cron"**. Requires a personal access
   token in cron. A security regression. The pattern says: do
   the publish step manually until a secret-rotation policy
   exists.

## 7. See also

- [CASE_STUDY.md](CASE_STUDY.md) — the project that produced
  this pattern
- [RETROSPECTIVE.md](RETROSPECTIVE.md) — phase-by-phase lessons
- [OPEN_SOURCE_BOUNDARIES.md](OPEN_SOURCE_BOUNDARIES.md) — the
  specific boundary rules for the Artvee project
- [ARCHITECTURE.md](ARCHITECTURE.md) — the technical deep-dive
