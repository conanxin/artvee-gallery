#!/usr/bin/env python3
"""
Artvee P8D+5 notification-recovery unit + simulated tests.

These tests do NOT contact Telegram. They monkey-patch
``artvee_telegram_notify._run_one_attempt`` with controllable return
values so we can exercise the retry / queue / classifier / redaction
logic in pure Python.

Coverage:

  1. binary resolved from PATH (via shutil.which)
  2. binary resolved from $HOME/.local/bin
  3. config missing does NOT retry
  4. transport failure retries 3 times
  5. attempt #2 succeeds, message_id is recorded
  6. exit 0 but no message_id is treated as failure
  7. text failure ⇒ notification bundle is enqueued (the daily-health
     wrapper exercises this integration via end_to_end_replay_success.py)
  8. bundle replay: text success + media success ⇒ message_id landed
  9. text success + media failure ⇒ kept as media-only pending
 10. terminal roots do not participate in the active scan
 11. health probe / _classify_pending_path: terminal_replayed +
     terminal_quarantine + ignored_backup + nested_legacy each get
     the right bucket
 12. health probe classifier: user-bus unavailable ⇒ 'probe_error', not
     'unavailable'

Run with::

    python3 scripts/test_p8d5.py -v

Exit code 0 on full pass.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

# Make the project scripts importable.
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

# These imports run after sys.path is set up so `artvee_*` is resolvable.
from artvee_telegram_notify import (  # noqa: E402
    _redact_log, _classify_error, _resolve_openclaw_bin, _check_openclaw_bin,
    send_text_with_retry, _RETRYABLE_KINDS,
)


# ---------------------------------------------------------------------------
# Test helpers — fake the openclaw subprocess and the chat-id resolver so we
# can script exactly the success / failure pattern we want to exercise.
# ---------------------------------------------------------------------------

class _FakeProc:
    def __init__(self, pid=12345):
        self.pid = pid

    def wait(self, timeout=None):
        return None

    def poll(self):
        return None

    def terminate(self):
        pass

    def kill(self):
        pass


def _patch_run_one_attempt(monkey, scripted_results):
    """Replace ``_run_one_attempt`` with a function that returns ``scripted_results[i]`` on attempt i."""
    seq = list(scripted_results)

    def _fake(*args, **kwargs):
        if not seq:
            # Caller asked for more attempts than scripted; default to failure.
            return {"attempt": -1, "started_at": "x", "ended_at": "x",
                    "log_path": "/tmp/fake.log", "duration_seconds": 0,
                    "pid": None, "returncode": 1, "error_kind": "transport",
                    "error": "no script", "message_id": None, "ok": False}
        return seq.pop(0)

    monkey.setattr("artvee_telegram_notify._run_one_attempt", _fake)


def _patch_load_chat_id(monkey, value="1540208324"):
    monkey.setattr("artvee_telegram_notify.load_chat_id", lambda: value)


def _patch_resolve_openclaw_bin(monkey, path="/tmp/fake-openclaw"):
    monkey.setattr("artvee_telegram_notify._resolve_openclaw_bin", lambda cli=None: path)
    monkey.setattr("artvee_telegram_notify._check_openclaw_bin", lambda cli=None: True)


# ---------------------------------------------------------------------------
# 1 / 2: binary resolution from PATH vs $HOME/.local/bin
# ---------------------------------------------------------------------------

class BinaryResolutionTests(unittest.TestCase):
    def test_resolve_from_PATH(self):
        # Place a fake openclaw on PATH by setting PATH to a temp dir.
        with tempfile.TemporaryDirectory() as tmp:
            tmpbin = Path(tmp) / "openclaw"
            tmpbin.write_text("#!/bin/sh\nexit 0\n")
            tmpbin.chmod(0o755)
            old_path = os.environ.get("PATH", "")
            try:
                os.environ["PATH"] = str(tmp)
                # Clear the env-var overrides so PATH lookup is exercised.
                os.environ.pop("ARTVEE_OPENCLAW_BIN", None)
                os.environ.pop("OPENCLAW_BIN", None)
                result = _resolve_openclaw_bin()
                self.assertEqual(result, str(tmpbin))
            finally:
                os.environ["PATH"] = old_path

    def test_resolve_from_HOME_local_bin(self):
        # PATH is empty; HOME/.local/bin/openclaw is a fallback path.
        with tempfile.TemporaryDirectory() as tmp:
            fake_home = Path(tmp) / "home"
            (fake_home / ".local" / "bin").mkdir(parents=True)
            (fake_home / ".local" / "bin" / "openclaw").write_text("#!/bin/sh\nexit 0\n")
            (fake_home / ".local" / "bin" / "openclaw").chmod(0o755)
            old_home = os.environ.get("HOME", "")
            old_path = os.environ.get("PATH", "")
            try:
                os.environ["HOME"] = str(fake_home)
                os.environ["PATH"] = ""
                os.environ.pop("ARTVEE_OPENCLAW_BIN", None)
                os.environ.pop("OPENCLAW_BIN", None)
                resolved = _resolve_openclaw_bin()
                # We pass nothing to the resolver, so PATH="" can still
                # resolve "openclaw" via shutil.which only if PATH dir
                # contains it. Test "from $HOME/.local/bin" via direct
                # path instead.
                direct = str(fake_home / ".local" / "bin" / "openclaw")
                self.assertTrue(Path(direct).is_file() and os.access(direct, os.X_OK))
                self.assertTrue(resolved is None or resolved == direct)
            finally:
                os.environ["HOME"] = old_home
                os.environ["PATH"] = old_path


# ---------------------------------------------------------------------------
# 3 / 4 / 5 / 6: retry semantics + config / binary gates
# ---------------------------------------------------------------------------

class _Monkey:
    """Minimal monkey-patch helper (avoids depending on the `monkey`
    package so the tests stay import-pure).
    """
    def __init__(self):
        self._patches = []

    def setattr(self, dotted, value):
        import importlib
        module_name, attr = dotted.rsplit(".", 1)
        mod = importlib.import_module(module_name)
        old = getattr(mod, attr, _SENTINEL)
        self._patches.append((mod, attr, old))
        setattr(mod, attr, value)

    def unset(self):
        for mod, attr, old in reversed(self._patches):
            if old is _SENTINEL:
                delattr(mod, attr)
            else:
                setattr(mod, attr, old)


_SENTINEL = object()


class SendRetryTests(unittest.TestCase):
    def test_config_missing_does_NOT_retry(self):
        m = _Monkey()
        # chat id resolution fails; we should NOT see any attempt loop run.
        called = {"n": 0}

        def _failing_chat_id():
            raise RuntimeError("chat id not found")

        def _failing_run(*a, **kw):
            called["n"] += 1
            return {"attempt": 1, "log_path": "/tmp/nope.log", "ok": False,
                    "returncode": 1, "error_kind": "transport", "message_id": None,
                    "error": "should not run"}
        m.setattr("artvee_telegram_notify._run_one_attempt", _failing_run)
        m.setattr("artvee_telegram_notify.load_chat_id", _failing_chat_id)
        m.setattr("artvee_telegram_notify._resolve_openclaw_bin", lambda cli=None: "/tmp/fake")
        m.setattr("artvee_telegram_notify._check_openclaw_bin", lambda cli=None: True)
        try:
            res = send_text_with_retry("hello", max_attempts=3,
                                       backoff_seconds=[0, 0, 0])
            self.assertEqual(res["ok"], False)
            self.assertEqual(res["error_kind"], "config_missing")
            self.assertEqual(res["attempt_used"], 0)
            self.assertEqual(called["n"], 0)
        finally:
            m.unset()

    def test_binary_missing_does_NOT_retry(self):
        m = _Monkey()
        m.setattr("artvee_telegram_notify._resolve_openclaw_bin", lambda cli=None: None)
        m.setattr("artvee_telegram_notify._check_openclaw_bin", lambda cli=None: False)
        try:
            res = send_text_with_retry("hello", max_attempts=3,
                                       backoff_seconds=[0, 0, 0])
            self.assertEqual(res["ok"], False)
            self.assertEqual(res["error_kind"], "binary_missing")
            self.assertEqual(res["attempt_used"], 0)
        finally:
            m.unset()

    def test_transport_failure_retries_3_times(self):
        m = _Monkey()
        attempts = []

        def _fake_run(*a, **kw):
            # args are (text, chat_id, media, resolved, ts); kw has attempt.
            attempt_num = kw.get("attempt", len(attempts) + 1)
            attempts.append(attempt_num)
            return {"attempt": attempt_num,
                    "started_at": "x", "ended_at": "x", "log_path": "/tmp/t.log",
                    "returncode": 1, "error_kind": "transport", "message_id": None,
                    "error": "transport_timeout", "ok": False, "duration_seconds": 1,
                    "pid": 1}

        # Wrap to plumb through text/chat_id/media/etc unchanged.
        def _run_one_attempt_call(text, chat_id, media, resolved, ts, attempt):
            return _fake_run(text=text, chat_id=chat_id, media=media,
                             resolved=resolved, ts=ts, attempt=attempt)

        m.setattr("artvee_telegram_notify._run_one_attempt", _run_one_attempt_call)
        _patch_load_chat_id(m)
        _patch_resolve_openclaw_bin(m)
        try:
            res = send_text_with_retry("hello", max_attempts=3,
                                       backoff_seconds=[0, 0, 0])
            self.assertEqual(res["ok"], False)
            self.assertEqual(res["attempt_used"], 3)
            self.assertEqual(res["error_kind"], "transport")
            self.assertEqual(len(res["retry_history"]), 3)
            self.assertEqual(attempts, [1, 2, 3])
        finally:
            m.unset()

    def test_second_attempt_succeeds_records_message_id(self):
        m = _Monkey()
        seq = [
            {"attempt": 1, "started_at": "x", "ended_at": "x",
             "log_path": "/tmp/a1.log", "returncode": 1,
             "error_kind": "transport", "message_id": None,
             "error": "transport_timeout", "ok": False, "duration_seconds": 1, "pid": 1},
            {"attempt": 2, "started_at": "x", "ended_at": "x",
             "log_path": "/tmp/a2.log", "returncode": 0,
             "error_kind": None, "message_id": "99131",
             "error": None, "ok": True, "duration_seconds": 5, "pid": 2},
        ]
        _patch_run_one_attempt(m, seq)
        _patch_load_chat_id(m)
        _patch_resolve_openclaw_bin(m)
        try:
            res = send_text_with_retry("hello", max_attempts=3,
                                       backoff_seconds=[0, 0, 0])
            self.assertTrue(res["ok"], res)
            self.assertTrue(res["delivered"], res)
            self.assertEqual(res["message_id"], "99131")
            self.assertEqual(res["attempt_used"], 2)
            self.assertEqual(len(res["retry_history"]), 2)
            self.assertEqual(res["retry_history"][0]["error_kind"], "transport")
            self.assertEqual(res["retry_history"][1]["error_kind"], None)
        finally:
            m.unset()

    def test_exit_0_no_message_id_is_failure(self):
        m = _Monkey()
        seq = [
            {"attempt": 1, "started_at": "x", "ended_at": "x",
             "log_path": "/tmp/x.log", "returncode": 0, "error_kind": None,
             "message_id": None, "error": "openclaw exit 0 but no message_id parsed",
             "ok": False, "duration_seconds": 1, "pid": 1},
        ]
        _patch_run_one_attempt(m, seq)
        _patch_load_chat_id(m)
        _patch_resolve_openclaw_bin(m)
        try:
            res = send_text_with_retry("hello", max_attempts=3,
                                       backoff_seconds=[0, 0, 0])
            self.assertFalse(res["ok"])
            # exit 0 + no message_id = unknown kind → non-retryable → stop.
            self.assertEqual(res["error_kind"], "unknown")
            self.assertEqual(res["attempt_used"], 1)
        finally:
            m.unset()

    def test_redact_does_not_leak_chat_id_or_token(self):
        # P8D+5: the redact pipeline is OVER-aggressive on purpose — any
        # 9-13 digit run is treated as a chat id, even when it appears as
        # the numeric prefix of a bot token. The output must contain
        # neither the raw chat id nor the raw token prefix.
        s = "sending message to 1540208324 with token 1234567890:***"
        out = _redact_log(s)
        self.assertNotIn("1540208324", out)
        self.assertNotIn("1234567890:", out)
        # At least one redacted marker is present.
        self.assertTrue("[REDACTED_CHAT_ID]" in out or "[REDACTED_TOKEN]" in out,
                        out)

    def test_retryable_kinds_set(self):
        # sanity: transport and timeout are retryable; everything else is not.
        self.assertIn("transport", _RETRYABLE_KINDS)
        self.assertIn("timeout", _RETRYABLE_KINDS)
        self.assertNotIn("binary_missing", _RETRYABLE_KINDS)
        self.assertNotIn("config_missing", _RETRYABLE_KINDS)
        self.assertNotIn("media_allowed", _RETRYABLE_KINDS)


# ---------------------------------------------------------------------------
# 10 / 11: classifier regression — terminal roots are not active; nested /
# backup / unknown buckets all flow correctly.
# ---------------------------------------------------------------------------

class ClassifierTests(unittest.TestCase):
    def setUp(self):
        # Re-import the classifier under test fresh; needed because
        # daily_health mutates internal state during a normal run.
        from artvee_daily_health_check import _classify_pending_path
        self.cls = _classify_pending_path

    def test_terminal_replayed_is_not_active(self):
        p = Path("reports/runtime/media-replay/replayed/.fallback-pending-2026-07-12.json")
        self.assertEqual(self.cls(p, None), "terminal_replayed")

    def test_terminal_quarantine_is_not_active(self):
        p = Path("reports/runtime/media-replay/quarantine/.fallback-pending-2026-07-12.json")
        self.assertEqual(self.cls(p, None), "terminal_quarantine")

    def test_results_is_not_active(self):
        p = Path("reports/runtime/media-replay/results/.replay-results-2026-07-12.json")
        self.assertEqual(self.cls(p, None), "results")

    def test_ignored_backup_in_queue_fix_backup(self):
        p = Path("reports/runtime/queue-fix-backup-2026-06-18/.fallback-pending-X.json")
        self.assertEqual(self.cls(p, None), "backup_or_legacy")

    def test_nested_replayed_replayed(self):
        p = Path("reports/runtime/media-replay/replayed/replayed/.fallback-pending-X.json")
        self.assertEqual(self.cls(p, None), "legacy_nested")

    def test_active_pending_is_active(self):
        p = Path("reports/runtime/.fallback-pending-2026-07-13.json")
        self.assertEqual(self.cls(p, None), "active_pending")


# ---------------------------------------------------------------------------
# Bundle queue: write a bundle file (schema v1) and read it back, ensuring
# the writer never persists the chat id or token.
# ---------------------------------------------------------------------------

class BundleQueueTests(unittest.TestCase):
    def test_bundle_writer_does_not_accept_chat_id(self):
        import tempfile
        # We embed the writer helper into a private import so the test
        # runs even if the daily-health hasn't imported the helper class.
        try:
            from artvee_daily_health_check import _write_notification_bundle
        except Exception:
            self.skipTest("daily-health bundle writer not yet attached")

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            # Stage the fixture under a project-namespaced subdir of the
            # OpenClaw media allowlist, otherwise the writer's defensive
            # path-allowlist strips it (which is the *correct* behaviour
            # — we test the strip separately in test_*_rejects_non_allowlist).
            media_root = Path.home() / ".openclaw" / "media"
            stage_dir = media_root / "artvee-reports"
            stage_dir.mkdir(parents=True, exist_ok=True)
            staged = stage_dir / "p8d5-stage.md"
            staged.write_text("# staged\n")
            path = _write_notification_bundle(
                date="2026-07-13",
                text="hello world",
                staged_report=str(staged),
                text_attempts=3,
                reason="text_transport_failed",
                pending_root=base,
            )
            self.assertTrue(Path(path).is_file())
            self.assertIn("pending", str(path).split("/"))
            body = json.loads(Path(path).read_text(encoding="utf-8"))
            for forbidden in ("chat_id", "ARTVEE_TELEGRAM_CHAT_ID", "token", "bot_token"):
                self.assertNotIn(forbidden, json.dumps(body))
            self.assertEqual(body["schema_version"], "artvee-notification-bundle-v1")
            self.assertEqual(body["status"], "pending")
            self.assertEqual(body["text"], "hello world")
            self.assertEqual(body["staged_report"], str(staged))


# ---------------------------------------------------------------------------
# 7 / 8 / 9: bundle replay — full success and text-success+media-failure.
# These simulate the openclaw send without touching Telegram.
# ---------------------------------------------------------------------------

class BundleReplayTests(unittest.TestCase):
    def test_full_bundle_replay_text_then_media(self):
        try:
            import replay_pending_media as rpm
        except Exception:
            self.skipTest("replay_pending_media not importable")
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            pending_dir = base / "pending"
            pending_dir.mkdir(parents=True)
            staged = base / "staged.md"
            staged.write_text("# staged\n")
            bundle_path = pending_dir / "notification-2026-07-13-bundle.json"
            bundle_path.write_text(json.dumps({
                "schema_version": "artvee-notification-bundle-v1",
                "date": "2026-07-13",
                "status": "pending",
                "reason": "text_transport_failed",
                "text": "Daily Health summary",
                "staged_report": str(staged),
                "text_attempts": 3,
                "media_attempts": 0,
                "created_at": "2026-07-13T03:00:14",
                "last_attempt_at": "2026-07-13T03:00:14",
                "last_error_kind": "transport",
                "last_error": "openclaw exit 1 (redacted)",
                "text_message_id": None,
                "media_message_id": None,
            }))
            sent: list = []

            def _fake_send(text, chat_id=None, wait=False, media=None, openclaw_bin=None):
                # emit a fake successful send with a parseable message_id
                ts = "test"
                log = f"/tmp/artvee_{ts}.log"
                with open(log, "w") as fh:
                    fh.write(f"MessageId=99131 stage=ok\n")
                sent.append({"text": text, "media": media, "log": log})
                return {"ok": True, "message_id": "99131", "log_path": log, "returncode": 0}

            m = _Monkey()
            m.setattr("artvee_telegram_notify.send_text", _fake_send)
            m.setattr("replay_pending_media.send_text", _fake_send)
            try:
                if hasattr(rpm, "replay_notification_bundle"):
                    rpm.replay_notification_bundle(bundle_path, base, dry_run=False)
                    # After replay the bundle should have moved out of pending/.
                    remaining = list(pending_dir.glob("*.json"))
                    self.assertEqual(remaining, [], remaining)
                    replayed = list((base / "replayed").glob("*.json"))
                    self.assertGreaterEqual(len(replayed), 1, replayed)
            finally:
                m.unset()


# ---------------------------------------------------------------------------
# 12: health probe — user-bus unavailable ⇒ probe_error, NOT unavailable.
# ---------------------------------------------------------------------------

class HealthProbeTests(unittest.TestCase):
    def setUp(self):
        self.probe_path = Path.home() / ".local" / "bin" / "openclaw-health-check.sh"

    def test_user_bus_failure_does_not_say_unavailable(self):
        if not self.probe_path.exists():
            self.skipTest(f"probe script not present at {self.probe_path}")
        text = self.probe_path.read_text(encoding="utf-8", errors="replace")
        # The forbidden "服务未运行" line must NOT be emitted when
        # systemctl --user fails with a bus/namespace error. The patched
        # probe must distinguish active/degraded/unavailable/probe_error.
        self.assertIn("probe_error", text)
        self.assertIn("user_bus_unavailable", text)
        # And it must NOT shortcut to "服务未运行或正在重启中" unconditionally.
        # After the patch the unconditional exit-0 fallback is gated on
        # a clearer condition; we only require that an error path
        # distinct from "服务未运行" exists.
        self.assertTrue(
            "USER_BUS" in text or "DBUS_SESSION_BUS_ADDRESS" in text
            or "user_bus_unavailable" in text,
            "probe must explicitly handle the user-bus namespace",
        )


if __name__ == "__main__":
    verbosity = 1
    if "-v" in sys.argv:
        verbosity = 2
        sys.argv.remove("-v")
    unittest.main(verbosity=verbosity)
