# v0.2.0 Observation Window

## 1. Purpose

The v0.2.0-alpha release has been cut. Before promoting it to **v0.2.0 stable**, we run a 3-day observation window to confirm the daily automation is reliable and the system stays healthy without manual intervention.

**Safety rule:** During observation, we do not trigger downloads, refills, batches, or GitHub Pages pushes. We only observe and document.

## 2. Observation period

| Day | Date | Notes |
|-----|------|-------|
| Day 1 | 2026-06-14 | First day — health cron verified at 03:02 |
| Day 2 | 2026-06-15 | Mid-window — confirm consistency |
| Day 3 | 2026-06-16 | Final day — assess stable-readiness |

## 3. Daily expected timeline

All times are Asia/Shanghai (GMT+8).

| Time | Event | Expected outcome |
|------|-------|-----------------|
| 01:30 | `refill_artvee_pending.py` | Seed pool topped up (no-op if full) |
| 02:00 | `run_artvee_nightly_batch.py` | ~20 artworks downloaded, 0 failed |
| 02:30 | `confirm_demo_refresh.sh` | Candidate built at `dist/refresh-candidates/YYYY-MM-DD/` |
| 03:00 | `artvee_daily_health_check.sh --online --media` | Telegram summary + MEDIA report delivered |

## 4. Healthy state criteria

The system is healthy when **all** of the following are true:

| Criterion | Healthy value | Verification |
|-----------|--------------|------------|
| `records` | ~750–800 (slow growth) | `check_gallery_integrity.py` + status report |
| `failed` | 0 | Nightly batch log |
| `known_retired` | 4 (audited) | Status report |
| `blocking_unresolved` | 0 | Status report |
| `strict_integrity` | PASS | `check_gallery_integrity.py --strict` |
| `readiness` | PASS | `check_open_source_ready.py` |
| `candidate_gallery` | True | `confirm_demo_refresh.sh` output |
| `candidate_digest` | True | `confirm_demo_refresh.sh` output |
| `online_gallery` | 200 | HTTP check |
| `online_digest` | 200 | HTTP check |
| Telegram text | Sent | `message_id` present in health JSON |
| Telegram MEDIA | Sent | `media.sent=true` in health JSON |

## 5. Warning signs

If any of these appear, the observation window extends and the stable release is deferred:

| Warning | Action |
|---------|--------|
| `failed > 0` | Check if transient; if persistent, investigate Artvee source changes |
| `integrity = FAIL` | Stop. Investigate index/web consistency. Do not publish. |
| `readiness = FAIL` | Stop. Check for tracked secrets or leaked paths. |
| `blocking_unresolved > 0` | Investigate new unresolvable URLs. Mark as `known_retired` if needed. |
| `known_retired` grows unexpectedly | Audit new retirees before accepting. |
| `online_gallery != 200` or `online_digest != 200` | Check GitHub Pages CDN / repo status. |
| Telegram not delivered | Check `openclaw` binary, `ARTVEE_TELEGRAM_CHAT_ID`, token validity. |
| MEDIA not attached | Check OpenClaw media allowlist; fallback text should still send. |
| Records shrink or jump >50 | Investigate data loss or collision. |

## 6. Daily checklist

Run this checklist each morning after the 03:00 health check arrives.

```markdown
- [ ] 03:00 Telegram message received
- [ ] MEDIA attachment present (or fallback text sent)
- [ ] records within ~750–800
- [ ] failed == 0
- [ ] known_retired == 4
- [ ] blocking_unresolved == 0
- [ ] integrity == PASS
- [ ] readiness == PASS
- [ ] candidate_gallery == True
- [ ] candidate_digest == True
- [ ] online_gallery == 200
- [ ] online_digest == 200
- [ ] No manual intervention needed
```

**Scoring:**
- All 12 checked → Green day, observation continues
- 1–2 yellow items → Yellow day, document and watch
- Any red item (integrity FAIL, readiness FAIL, blocking_unresolved > 0) → Red day, stop stable release planning

## 7. Stable release readiness

At the end of Day 3 (2026-06-16), if all 3 days are green:

1. Update `docs/RELEASE_NOTES_v0.2.0.md` (drop "-alpha" suffix)
2. Tag `v0.2.0` on `main`
3. Update README badge from `v0.2.0-alpha` to `v0.2.0`
4. Close observation window

If any day is yellow or red, extend observation by 1 day and re-evaluate.

## 8. Next steps after observation

| Scenario | Action |
|----------|--------|
| 3 green days | Promote to v0.2.0 stable; update release notes; tag; announce |
| 1–2 yellow days | Extend observation; document root cause; fix if needed |
| Any red day | Halt stable release; open investigation phase; do not tag |

---

*Created by P7E observation window setup on 2026-06-14.*
