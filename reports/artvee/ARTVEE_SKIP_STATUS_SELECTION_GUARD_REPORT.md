# ARTVEE_SKIP_STATUS_SELECTION_GUARD_REPORT

**STATUS:** PASS  
**HOST_SCOPE:** local_openclaw  
**TASK:** Artvee skipped/dead status selection guard

---

## PROJECT_DIR
`<artvee-repo>`

## FILES_MODIFIED
- `scripts/run_artvee_nightly_batch.py`

---

## CODE_SEMANTICS

### original condition meaning
```python
if status in ("", "pending", "failed"):
    candidates.append((idx, row, status))
else:
    # 未知状态当作 pending 处理
    candidates.append((idx, row, "pending"))
```
This is an **inclusion** condition (line 146 in original). It lists the statuses that are allowed into the candidate pool. Any status **not in** this list falls into the `else` branch and is reclassified as `pending`.

### why adding skipped to inclusion list is incorrect
Adding `"skipped"` to the inclusion list (`if status in ("", "pending", "failed", "skipped")`) would make `skipped` items enter the candidate pool — but treated as `pending` (from the `else` branch). This would select `skipped` items for retry every batch run, which is the opposite of the desired behavior.

### actual fix applied
Added an **explicit exclusion guard** before the inclusion check:
```python
# 显式排除终态（不再重试）
if status in ("skipped", "dead", "manual_review"):
    continue
```
This uses `continue` to remove these items from consideration **before** they reach the inclusion/exclusion logic. The inclusion list remains unchanged (`"", "pending", "failed"`), preserving all original semantics. Unknown statuses (not in either list) still fall through to the `else` → `pending` behavior.

---

## VALIDATION

| Check | Result |
|-------|--------|
| `python3 -m py_compile scripts/run_artvee_nightly_batch.py` | **PASS** |
| umbrellas-in-snow in manifest | `skipped` |
| umbrellas-in-snow in selected candidates (fixed logic) | **no** |
| umbrellas-in-snow in seen_candidates | `skipped` |
| skipped excluded from selection | **yes** |
| manifest downloaded | 640 |
| manifest failed | 0 |
| manifest skipped | 1 |
| manifest pending_or_empty | 0 |
| candidates selected (fixed logic, no index) | 0 |

**Selection simulation** confirms:
- `umbrellas-in-snow` (status=`skipped`) is NOT selected
- With empty index: `candidates=0, selected=0` — all 640 downloaded + 1 skipped = 641, no pending/failed/empty items remain

---

## GIT_DIFF_SUMMARY

The file `scripts/run_artvee_nightly_batch.py` exists only in the current branch (`integration/xai-oauth-official-20260517_215015`) and is not present in `main`. The diff against `main` shows the entire file as new.

**Local change from baseline:**
```diff
@@ +136,6 @@
         if status == "downloaded":
             continue

+        # 显式排除终态（不再重试）
+        if status in ("skipped", "dead", "manual_review"):
+            continue
+
         # 跳过 index 中已存在且本地文件仍存在的
```

**Lines added:** 3 (`skipped`, `dead`, `manual_review` guard)  
**Lines removed:** 0  
**Behavioral change:** Only items with status `skipped`/`dead`/`manual_review` are now excluded from retry pool. All other logic unchanged.

---

## RISK_LEVEL
**LOW** — Minimal, surgical change. Only adds a `continue` guard that filters out three known terminal statuses before the existing inclusion logic. No change to candidate sorting, limit, or download flow.

---

## NEXT_RECOMMENDED_ACTION

1. **Read-only verification after tonight's batch (Jun 3, 02:00)**
   - Check `logs/wrapper_runs/wrapper_batch_20260603_020000.log`
   - Confirm `umbrellas-in-snow` is **not** in selected candidates
   - Confirm `failed=0` in manifest after batch
   - Confirm Telegram notification shows no `failed=1`

2. **If tonight's batch still selects umbrellas** — the fix was not deployed (script not restarted/reloaded by cron). Verify the cron wrapper runs the correct script path.

3. **Longer-term (post tonight's verification)**
   - Playwright retry/backoff: Consider adding `viewport_changes` or `ad-block` filtering to reduce transient 403s
   - Telegram notification: The wrapper sends `⏸️ success (no new downloads)` when `exit=0` and `new_images=0`, which is correct; however, the `ERROR_SNIPPET` logic picks up `FAILED` from the batch log even with `exit=0`, so the notification correctly shows no error. No urgent fix needed.
   - Max retry cap per item: Consider a `retry_count` field in manifest to auto-skip after N consecutive failures, rather than manual skip.

> Do not execute any modifications during this session.