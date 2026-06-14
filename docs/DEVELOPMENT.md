
---

## 20. P7A+1 OpenClaw binary resolution

P7A+1 normalizes how the health check (and any other script) finds
the OpenClaw binary for Telegram notification. The goal is to make
Telegram notify work in both cron and interactive shell contexts
without hardcoding paths.

### Resolution order

The `scripts/artvee_telegram_notify.py` resolver tries, in order:

1. **CLI argument** `--openclaw-bin <path-or-command>`
2. **Environment variable** `ARTVEE_OPENCLAW_BIN`
3. **Environment variable** `OPENCLAW_BIN`
4. **PATH lookup** for `openclaw` (via `shutil.which`)
5. **None** — graceful skip, health check continues

### Why this matters

- Interactive shells (e.g., OpenClaw agent sessions) may have
different `PATH` than cron. The resolver tries both env vars and PATH.
- The default `'openclaw'` string is not treated as a valid resolved
path until `shutil.which('openclaw')` confirms it exists in PATH.
- If the binary is missing, the health check **still generates its report**
and exits 0. Telegram notify is skipped with a clear message.

### Usage examples

```bash
# Default: let resolver find openclaw in PATH
bash scripts/artvee_daily_health_check.sh

# Explicit binary path (useful in Docker, CI, or non-standard install)
bash scripts/artvee_daily_health_check.sh --openclaw-bin /usr/local/bin/openclaw

# No Telegram (report only)
bash scripts/artvee_daily_health_check.sh --no-telegram

# With online + media + explicit binary
bash scripts/artvee_daily_health_check.sh --online --media --openclaw-bin <openclaw-bin>
```

### Health check report field

The JSON report now includes a `telegram_notify` object:

```json
{
  "telegram_notify": {
    "enabled": true,
    "media_requested": true,
    "openclaw_status": "resolved",
    "sent": true,
    "message_id": null
  }
}
```

- `openclaw_status`: `resolved` | `missing` | `skipped`
- `sent`: `true` if the message was dispatched, `false` otherwise
- `message_id`: reserved for future enhancement (OpenClaw CLI currently
returns it in stdout, not structured JSON)

### Safety

- No hardcoded absolute paths in source code.
- No token or secret printed in error messages.
- Graceful degradation: missing binary ≠ failed health check.
- The `--openclaw-bin` argument is forwarded through the shell wrapper
to the Python script to the notifier, keeping the resolution logic in
one place (`artvee_telegram_notify.py`).

---

## 21. P7B Daily health cron

P7B installs the daily health check as a cron job that runs at 03:00
Asia/Shanghai, after the nightly batch (02:00) and candidate refresh
(02:30). The cron is idempotent and marker-based.

### Install the cron

```bash
bash scripts/install_daily_health_cron.sh --install
```

This adds a marker-delimited block to the user's crontab:

```
# >>> Artvee P7B daily health check BEGIN
# Artvee Daily Health Check (P7B)
0 3 * * * cd <repo-dir> && bash scripts/artvee_daily_health_check.sh --online --media >> logs/daily-health-cron/daily_health_$(date +\%Y\%m\%d)_030000.log 2>&1
# <<< Artvee P7B daily health check END
```

### Remove or modify the cron

```bash
# Remove the P7B block
bash scripts/install_daily_health_cron.sh --remove

# Change the time (e.g., to 09:00)
bash scripts/install_daily_health_cron.sh --install --time "0 9 * * *"
```

### Idempotency

Running `--install` twice replaces the existing block rather than
adding a duplicate. The script uses `sed` to remove the old block
before appending the new one.

### Safety

- The installer does not modify the Artvee repo (no data changes).
- It does not trigger downloads, refills, or batches.
- It backs up the crontab before modification (`logs/daily-health-cron/crontab.before_p7b.*.txt`).
- It does not print tokens, secrets, or chat IDs.

---

## 22. P7B+1 Telegram delivery state model + failure-only fallback

P7B+1 refactors the daily health check's Telegram reporting so that
**text summary**, **MEDIA attachment**, and **fallback** are independent
tracks. A MEDIA failure is observable but no longer silent.

### State model (JSON, in `reports/runtime/daily-health/*.json`)

```json
{
  "telegram": {
    "requested": true,
    "openclaw_status": "resolved | missing | skipped",
    "text_summary": {"attempted": true, "sent": true, "message_id": "22811", "error": null},
    "media": {
      "requested": true,
      "staged": true,
      "staged_path": "$HOME/.openclaw/media/artvee-reports/...",
      "sent": true,
      "message_id": "22813",
      "error": null,
      "simulated_failure": false
    },
    "fallback": {"attempted": false, "sent": false, "message_id": null, "reason": null}
  }
}
```

| Field | Type | Notes |
|-------|------|-------|
| `telegram.openclaw_status` | enum | `resolved` if notifier could start; `missing` if binary absent; `skipped` if `--no-telegram`. |
| `telegram.text_summary.sent` | bool | Whether the short ✅/❌ block was delivered. |
| `telegram.text_summary.message_id` | str | Telegram message id parsed from the notifier's log. |
| `telegram.media.staged_path` | str | Absolute path inside the OpenClaw allowlist (default root `$HOME/.openclaw/media/`). |
| `telegram.media.simulated_failure` | bool | True only when `--simulate-media-failure` was used (testing). |
| `telegram.fallback.reason` | enum | Currently only `media_failed`. |

### Failure-only fallback

When all of the following hold:

- `checks.integrity.status == "PASS"`
- `checks.readiness.status == "PASS"`
- `telegram.text_summary.sent == true`
- `telegram.media.sent == false` and `telegram.media.error != null`

…a single short text fallback is sent:

```
⚠️ Artvee Daily Health MEDIA failed
Date: YYYY-MM-DD
Health: PASS
Text summary: sent
MEDIA: failed
Report: <report-md-path>
Action: no data issue; check media delivery
```

Guarantees:

- Sent at most **once** per run.
- Never recurses (the fallback path does not call the health check).
- Does not change the script's exit code unless health itself failed.

### `--simulate-media-failure` (testing only)

To verify the fallback chain without breaking the real MEDIA allowlist:

```bash
cd <artvee-repo>
bash scripts/artvee_daily_health_check.sh --online --media --simulate-media-failure
```

This forces `media.sent=false` with `error=simulated_failure` and triggers
the fallback. **Do not** use this in cron; it is for one-off testing.

### How to inspect any day's Telegram status

```bash
# After a run:
python3 -c "
import json
d = json.load(open('reports/runtime/daily-health/artvee-daily-health-2026-06-13.json'))
print(json.dumps(d['telegram'], indent=2, ensure_ascii=False))
"
```

### Chat id resolution (P7B+1: no hardcoded ids in the repo)

`scripts/artvee_telegram_notify.py` resolves the chat id in this order:

1. `--chat-id` CLI argument
2. `ARTVEE_TELEGRAM_CHAT_ID` environment variable
3. `channels.telegram.defaultChatId` in `$HOME/.openclaw/openclaw.json`
4. `channels.telegram.targets[0]` in the same file
5. Hard error (no fallback to a literal id in source)

The cron installer bakes `ARTVEE_TELEGRAM_CHAT_ID` into the cron block
when the installer is run with that env var set. To re-install with a
new chat id, simply re-export and re-run the installer.

```bash
ARTVEE_TELEGRAM_CHAT_ID="<telegram-chat-id>" \
  bash scripts/install_daily_health_cron.sh --install
```

---

## 23. v0.2.0-alpha release checklist

This section is the in-repo runbook for cutting a release. It is
intentionally short and idempotent: every step is reproducible from
a clean clone + a working local data directory.

### Pre-flight
```bash
cd <artvee-repo>
git status --short                     # only runtime / untracked files; no in-progress edits
git log --oneline -3                   # HEAD is the release commit
git remote -v                          # origin = github.com/conanxin/artvee-gallery
```

### Build / readiness gates
```bash
python3 -m py_compile scripts/*.py
for s in scripts/artvee_daily_health_check.sh scripts/install_daily_health_cron.sh \
         scripts/confirm_demo_refresh.sh scripts/publish_demo_refresh_candidate.sh \
         scripts/artvee_nightly_wrapper.sh; do bash -n "$s"; done
python3 scripts/check_open_source_ready.py
python3 scripts/check_gallery_integrity.py --strict
python3 scripts/build_artvee_status_report.py \
  --out-json reports/runtime/artvee-status-report.json \
  --out-md reports/runtime/artvee-status-report.md
bash scripts/artvee_daily_health_check.sh --no-telegram
```

All six checks must pass. `git ls-files` must not show any tracked
runtime files; `grep` over the docs / source must not produce
real local paths, tokens, or chat ids.

### Create the tag and GitHub Release
```bash
# Tag (annotated, on the release commit)
git tag -a v0.2.0-alpha -m "Artvee Gallery v0.2.0-alpha"
git push origin v0.2.0-alpha

# GitHub Release (idempotent: re-running with the same tag fails loudly)
gh release view v0.2.0-alpha >/dev/null 2>&1 \
  || gh release create v0.2.0-alpha \
       --title "Artvee Gallery v0.2.0-alpha" \
       --notes-file docs/RELEASE_NOTES_v0.2.0-alpha.md
```

### Public demo verification
```bash
curl -I https://conanxin.github.io/projects/artvee-gallery-demo/
curl -I https://conanxin.github.io/projects/artvee-gallery-digest/
gh repo view conanxin/artvee-gallery --json name,visibility,url,defaultBranchRef
git ls-remote --tags origin v0.2.0-alpha
gh release view v0.2.0-alpha --json tagName,name,url,isPrerelease
```

### Safety rails
- The release commit must not include `images/`, `metadata/`,
  `thumbs/`, `dist/`, `digests/`, `logs/`, `inbox/`, `web/data/*.json`,
  `index/`, `reports/runtime/`, or `tmp/`.
- The release commit must not include tokens, chat ids, bot
  tokens, or real local paths in tracked files.
- The release must not trigger a download, refill, batch, or
  `publish_demo_refresh_candidate.sh --approve`. The publish
  step is always manual.

---

## 24. P7E+2 Online-check HTTPError / URLError semantics

P7E+1 (2026-06-15) found that the daily health check's online check
(`scripts/artvee_daily_health_check.py:200-219`) was masking a
content-drift incident as a network failure. The old code:

```python
try:
    gcode = urllib.request.urlopen(gallery_url, timeout=30).getcode()
    dcode = urllib.request.urlopen(digest_url,  timeout=30).getcode()
except Exception:
    gcode, dcode = 0, 0
```

collapsed *all* errors into `0, 0` — including `urllib.error.HTTPError`,
which is a *response* (404, 403, 500) and not a *transport* failure.
When a `--online` cron run then reports `Online: gallery=0, digest=0`,
the operator cannot tell whether the public site is unreachable (DNS
/ TLS / timeout) or simply missing the path (404).

P7E+2 splits the error handling so the two cases are distinguishable.

### 24.1 Three failure kinds, two numeric codes

| `online.kind`     | `gallery_http_code` | `gallery_error`                              | meaning                                    |
|-------------------|---------------------|----------------------------------------------|--------------------------------------------|
| `ok`              | `200`               | `null`                                       | both endpoints reachable, 200 OK           |
| `http_error`      | real code (`404`)   | `"HTTPError 404 Not Found"`                  | endpoint reachable, but path is wrong / removed / drift |
| `network_error`   | `0`                 | `"URLError [Errno -2] Name or service not known"` (or `"timeout/connection: ..."`) | DNS / TLS / connection refused / timeout / Pages down |
| `skipped`         | n/a                 | n/a                                          | `--online` was not passed                  |

### 24.2 Implementation

The new code is a small private helper:

```python
def _probe(url):
    """Return (http_code:int, kind:str, error:str|None)."""
    import urllib.request, urllib.error
    try:
        resp = urllib.request.urlopen(url, timeout=30)
        return (resp.getcode(), "ok", None)
    except urllib.error.HTTPError as e:
        return (e.code, "http_error", f"HTTPError {e.code} {e.reason}")
    except urllib.error.URLError as e:
        return (0, "network_error", f"URLError {e.reason}")
    except (TimeoutError, ConnectionError) as e:
        return (0, "network_error", f"timeout/connection: {e}")
    except Exception as e:
        return (0, "network_error", f"{type(e).__name__}: {e}")
```

Each endpoint is probed independently. The aggregate `online.kind` is
`ok` only if both are `ok`; otherwise it is `network_error` if either
is `network_error`; otherwise `http_error`.

### 24.3 Recommended action branches

The action label is now chosen by priority: an online FAIL beats any
internal check, and the kind shapes the wording.

| Condition                                | `recommended_action`                              |
|------------------------------------------|---------------------------------------------------|
| `online.status == "FAIL"` and `http_error` | `attention_required_pages_content_drift`         |
| `online.status == "FAIL"` and `network_error` | `attention_required_network_or_pages_unreachable` |
| `online.status == "FAIL"` (other)        | `attention_required_online_check`                 |
| internal integrity/readiness FAIL         | `attention_required`                              |
| gallery_ready AND digest_ready            | `candidate_ready_manual_publish_optional`        |
| otherwise                                 | `healthy_no_action`                               |

### 24.4 Backward compatibility

- The legacy `online.gallery_http_code` and `online.digest_http_code`
  fields are still present. For pre-fix reports they were `0` on
  every error; for post-fix reports they are the real code (200, 404,
  0, etc.). The Telegram summary template still emits
  `Online: gallery={gcode}, digest={dcode}`, but the meaning of
  `0` is now narrower: it means *transport failure only*.
- The legacy `online.details` field is still present, but its
  wording now distinguishes `http_error` from `network_error`.
- The legacy `recommended_action` strings (`healthy_no_action`,
  `candidate_ready_manual_publish_optional`, `attention_required`)
  are unchanged. The two new action strings are additive
  (`attention_required_pages_content_drift`,
  `attention_required_network_or_pages_unreachable`,
  `attention_required_online_check`).

### 24.5 Test recipes

| Test                                            | Expected                                                              |
|-------------------------------------------------|-----------------------------------------------------------------------|
| `bash scripts/artvee_daily_health_check.sh --online --no-telegram` (when sites are live) | `kind=ok`, `gallery_http_code=200`, `digest_http_code=200`, `action=candidate_ready_manual_publish_optional` |
| Synthetic 404: `urllib.request.urlopen("https://conanxin.github.io/projects/nonexistent-artvee-12345/")` | `(404, "http_error", "HTTPError 404 Not Found")` |
| Synthetic network: `urllib.request.urlopen("https://nonexistent-host-artvee-12345.invalid/")` | `(0, "network_error", "URLError [Errno -2] Name or service not known")` |

### 24.6 Lessons

- **Bare `except Exception` is a debugging anti-pattern in any code
  path that maps an exception to a status code.** It hides the
  semantic difference between "the server said no" and "we never
  reached the server". Always prefer at minimum
  `except urllib.error.HTTPError:` and `except urllib.error.URLError:`.
- **Cron + Telegram amplifies signal-distortion bugs.** Because the
  daily health summary is the operator's only glance, a 0/0 mask
  means *the operator is debugging in the dark* — even when the
  underlying data is fine. The lesson is to make every numeric
  field in the report truthful, even at the cost of a slightly
  noisier report.
- **Separate "transport failure" from "application-layer failure"**
  in any health check. They imply different fix paths:
  `network_error` → check DNS / Pages status; `http_error` → check
  path / namespace drift / explicit removal.
