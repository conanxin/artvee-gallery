#!/usr/bin/env python3
"""
Artvee Telegram Notifier
发送文本消息到 Telegram，通过 OpenClaw CLI message send 命令。
由于当前 shell 无法直接访问 api.telegram.org，使用 OpenClaw Gateway 作为发送通道。
后台运行以避免阻塞 wrapper（openclaw CLI 启动需 120-180 秒）。

Ownership note:
- This file belongs to the local Hermes Artvee project.
- It uses local OpenClaw only as a Telegram notification bridge.
- Do not treat Artvee as an OpenClaw-owned project solely because this notifier calls OpenClaw CLI.
"""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ARTVEE_OPENCLAW_BIN = os.environ.get('ARTVEE_OPENCLAW_BIN', 'openclaw')
OPENCLAW_BIN = os.environ.get('OPENCLAW_BIN', '')

# P8D+5: bounded transport retry knobs. Defaults match the brief:
# 3 attempts, backoff 0/15/45 seconds. We only retry on transport-class
# failures (openclaw exit 1 transport, ws timeout, transport-unreachable,
# connection refused); we never retry on config / chat-id / argument
# failures. Each attempt records its own history row so callers can show
# exactly which attempt delivered and which failed.
def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, '').strip()
    if not raw:
        return default
    try:
        return max(1, int(raw))
    except Exception:
        return default


def _env_backoff(name: str, default: str) -> list:
    """Parse a comma-separated backoff list, falling back to the default."""
    raw = os.environ.get(name, '').strip()
    if not raw:
        return [int(x) for x in default.split(',')]
    out = []
    for piece in raw.split(','):
        piece = piece.strip()
        if not piece:
            continue
        try:
            out.append(max(0, int(piece)))
        except Exception:
            continue
    return out or [int(x) for x in default.split(',')]


DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_BACKOFF_SECONDS = '0,15,45'

CFG_PATH = Path.home() / '.openclaw' / 'openclaw.json'
# Chat ID resolution order (P7B+1: no hard-coded ids in the repo):
#   1. CLI argument --chat-id (most explicit; always wins)
#   2. ARTVEE_TELEGRAM_CHAT_ID environment variable
#   3. ~/.openclaw/openclaw.json channels.telegram.defaultChatId
#   4. ~/.openclaw/openclaw.json channels.telegram.targets[0]
#   5. Hard error — we never fall back to a literal id in source.
ARTVEE_TELEGRAM_CHAT_ID = os.environ.get('ARTVEE_TELEGRAM_CHAT_ID', '').strip()

# P8D+2: private env file for chat-id (repo-external, chmod 600, not in git)
# Resolution order:
#   1. CLI argument --chat-id (most explicit; always wins)
#   2. ARTVEE_TELEGRAM_CHAT_ID environment variable
#   3. Private env file: $ARTVEE_TELEGRAM_ENV_FILE or $HOME/.config/artvee-gallery/telegram.env
#   4. ~/.openclaw/openclaw.json channels.telegram.defaultChatId
#   5. ~/.openclaw/openclaw.json channels.telegram.targets[0]
#   6. Hard error — we never fall back to a literal id in source.
ARTVEE_TELEGRAM_ENV_FILE = os.environ.get(
    'ARTVEE_TELEGRAM_ENV_FILE',
    str(Path.home() / '.config' / 'artvee-gallery' / 'telegram.env')
)


def _load_chat_id_from_env_file():
    """Read ARTVEE_TELEGRAM_CHAT_ID from a private env file.
    Returns the value or None if the file does not exist / is unreadable.
    Never prints the value."""
    p = Path(ARTVEE_TELEGRAM_ENV_FILE)
    if not p.is_file():
        return None
    try:
        # Only read the first matching line; ignore comments and blanks
        with open(p, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if line.startswith('ARTVEE_TELEGRAM_CHAT_ID='):
                    # Handle optional quotes
                    val = line.split('=', 1)[1].strip().strip('"').strip("'")
                    return val if val else None
    except Exception:
        pass
    return None


def _check_config(redact=True):
    """Return a diagnostic dict about chat-id resolution (no secrets exposed).
    Safe to print / log."""
    result = {
        'env_ARTVEE_TELEGRAM_CHAT_ID': {'present': bool(ARTVEE_TELEGRAM_CHAT_ID), 'len': len(ARTVEE_TELEGRAM_CHAT_ID)},
        'env_file': {
            'path': ARTVEE_TELEGRAM_ENV_FILE,
            'exists': Path(ARTVEE_TELEGRAM_ENV_FILE).is_file(),
        },
        'openclaw_config': {'exists': CFG_PATH.is_file()},
    }
    # Try resolution without exposing the value
    try:
        cid = load_chat_id()
        result['resolved'] = True
        result['resolved_len'] = len(cid)
    except Exception as e:
        result['resolved'] = False
        result['error'] = str(e)[:200]
    return result


def load_chat_id():
    if ARTVEE_TELEGRAM_CHAT_ID:
        return ARTVEE_TELEGRAM_CHAT_ID
    cid = _load_chat_id_from_env_file()
    if cid:
        return cid
    if CFG_PATH.is_file():
        try:
            cfg = json.loads(CFG_PATH.read_text(encoding='utf-8'))
            cid = cfg.get('channels', {}).get('telegram', {}).get('defaultChatId')
            if cid:
                return str(cid)
            targets = cfg.get('channels', {}).get('telegram', {}).get('targets', [])
            if targets:
                return str(targets[0])
        except Exception:
            pass
    raise RuntimeError(
        'Telegram chat id not found. Set ARTVEE_TELEGRAM_CHAT_ID in the env, '
        'or create ~/.config/artvee-gallery/telegram.env with ARTVEE_TELEGRAM_CHAT_ID=..., '
        'or set channels.telegram.defaultChatId in '
        '~/.openclaw/openclaw.json. See docs/DAILY_OPERATING_PLAYBOOK.md.'
    )


def _resolve_openclaw_bin(cli_path: str = None) -> str:
    """
    Resolution order:
    1. CLI argument --openclaw-bin
    2. Environment variable ARTVEE_OPENCLAW_BIN
    3. Environment variable OPENCLAW_BIN
    4. PATH lookup for 'openclaw'
    5. None (not found)
    """
    import shutil
    candidates = []
    if cli_path and cli_path.strip():
        candidates.append(cli_path.strip())
    if ARTVEE_OPENCLAW_BIN and ARTVEE_OPENCLAW_BIN.strip():
        candidates.append(ARTVEE_OPENCLAW_BIN.strip())
    if OPENCLAW_BIN and OPENCLAW_BIN.strip():
        candidates.append(OPENCLAW_BIN.strip())
    # Also try bare 'openclaw' as last resort
    candidates.append('openclaw')
    for c in candidates:
        if os.path.isabs(c):
            if os.path.exists(c) and os.access(c, os.X_OK):
                return c
        else:
            found = shutil.which(c)
            if found:
                return found
    return None


def _classify_error(log_content: str, returncode: int) -> str:
    """
    P7B+2: classify a notifier failure so the caller can pick the right
    follow-up (retry / write local fallback / re-stage media). Never includes
    secrets — only the openclaw log text we just produced.

    Returns one of:
      - "binary_missing": the CLI could not be resolved at all
      - "transport":     gateway ws timeout / transport / network unreachable
      - "media_allowed": staged path is not under the openclaw allowlist
      - "timeout":       openclaw process exceeded the wait window
      - "exit_nonzero":  any other non-zero exit
      - "config_missing": chat-id / config cannot be resolved → NEVER retry
      - "unknown":       no log content to classify
    """
    text = (log_content or "").lower()
    if not text and returncode == 0:
        return "unknown"
    if "gateway" in text and ("timeout" in text or "transport" in text
                              or "websocket" in text or "unreachable" in text
                              or "urllib" in text or "connection refused" in text):
        return "transport"
    if "localmediaaccesserror" in text or "allowed directory" in text or "not under an allowed" in text:
        return "media_allowed"
    if "openclaw binary" in text or "no such file" in text:
        return "binary_missing"
    if "chat id" in text and "not found" in text:
        return "config_missing"
    if returncode != 0 and not text:
        return "exit_nonzero"
    return "unknown"


# Error kinds that are eligible for bounded retry. Transport-class failures
# are reasonably caused by transient gateway saturation; binary_missing and
# config_missing are deterministic and would just waste attempts.
_RETRYABLE_KINDS = {"transport", "timeout"}


def _redact_log(text: str, max_chars: int = 1200) -> str:
    """Strip secrets / chat-id / token-shaped substrings from a log blob.

    The notifier output occasionally echoes the chat id inline (e.g.
    ``message send --target 1540208324 ...``). We never write that to disk;
    everything that touches ``/tmp/artvee_notify_*.log`` already contains
    the literal id, but a future caller may copy this content into a
    queue / report file. Defensive redact is cheap.
    """
    import re as _re
    if not text:
        return ""
    out = text[:max_chars]
    # 9-13 digit chat ids.
    out = _re.sub(r'(?<!\d)\d{9,13}(?!\d)', '[REDACTED_CHAT_ID]', out)
    # Bare bot tokens (numeric:alnum patterns).
    out = _re.sub(r'\b\d{6,12}:[A-Za-z0-9_-]{30,}\b', '[REDACTED_TOKEN]', out)
    return out


def _check_openclaw_bin(cli_path: str = None):
    resolved = _resolve_openclaw_bin(cli_path)
    if not resolved:
        print(f'ERROR: OpenClaw binary not found. Tried: ARTVEE_OPENCLAW_BIN={ARTVEE_OPENCLAW_BIN!r}, OPENCLAW_BIN={OPENCLAW_BIN!r}, PATH lookup for openclaw.')
        return False
    if not os.path.exists(resolved):
        print(f'ERROR: OpenClaw binary not found at resolved path: {resolved}')
        return False
    if not os.access(resolved, os.X_OK):
        print(f'ERROR: OpenClaw binary not executable: {resolved}')
        return False
    return True


def _extract_message_id(log_path: str) -> str:
    """Read the OpenClaw send log and try to extract a Telegram message id.

    Looks for common patterns in stdout/stderr:
      - 'Message ID: 12345'
      - 'message_id: 12345' / 'message_id=12345'
      - 'messageId=12345' / 'MessageId=12345'   (OpenClaw default format)
      - '"message_id": "12345"'
    Returns the first hit, or None if not found.
    Safe: only reads the log file, never prints tokens or chat ids.

    P8D+4 note: previous version only matched snake_case ``message_id``.
    OpenClaw's actual log line uses camelCase ``messageId=NNN`` which caused
    ``replay_message_ids`` to come back empty even on a successful send
    (messageId=29012 was logged but never extracted).
    """
    if not log_path:
        return None
    try:
        with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
    except Exception:
        return None
    import re
    patterns = [
        r'\bMessage[ _]ID[:\s=]+(\d+)',
        r'\bmessage_id["\s:=]+(\d+)',
        r'\bmessageId["\s:=]+(\d+)',
        r'\bMessageId["\s:=]+(\d+)',
        r'"message_id"\s*:\s*"(\d+)"',
    ]
    for pat in patterns:
        m = re.search(pat, content)
        if m:
            return m.group(1)
    return None


def _read_log_text(log_path: str) -> str:
    """Read a notify log file as utf-8 text; return "" on any error."""
    try:
        with open(log_path, 'r', encoding='utf-8', errors='replace') as fh:
            return fh.read()
    except Exception:
        return ""


def _close_proc(proc):
    """Best-effort terminate + wait for the subprocess."""
    try:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
    except Exception:
        pass


def _run_one_attempt(text: str, chat_id: str, media, resolved: str, ts: str, attempt: int) -> dict:
    """Run a single openclaw send; return a structured per-attempt dict.

    P8D+5: every attempt is run synchronously with a 300s wait so we know
    whether the message actually landed before deciding to retry. A
    background-mode launch (wait=False) is intentionally NOT used here
    because we cannot tell whether it succeeded without parsing the log
    file, and a crash between launch + log-parse would burn an attempt
    silently.
    """
    cmd = [
        resolved, 'message', 'send',
        '--channel', 'telegram',
        '--target', chat_id,
        '--message', text,
    ]
    if media:
        cmd += ['--media', str(media)]

    log_path = f'/tmp/artvee_notify_{ts}_a{attempt}.log'
    started_at = datetime.now().isoformat() if False else time.strftime('%Y-%m-%dT%H:%M:%S')
    record: dict = {
        'attempt': attempt,
        'started_at': started_at,
        'ended_at': None,
        'duration_seconds': 0,
        'log_path': log_path,
        'pid': None,
        'returncode': None,
        'error_kind': None,
        'error': None,
        'message_id': None,
    }
    proc = None
    try:
        with open(log_path, 'w', encoding='utf-8') as log_fh:
            proc = subprocess.Popen(
                cmd,
                stdout=log_fh,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
            )
        record['pid'] = proc.pid
        try:
            proc.wait(timeout=300)
            rc = proc.returncode
        except subprocess.TimeoutExpired:
            record['error'] = 'timeout after 300s'
            record['error_kind'] = 'timeout'
            record['ended_at'] = time.strftime('%Y-%m-%dT%H:%M:%S')
            _close_proc(proc)
            return record
        record['returncode'] = rc
        log_text = _read_log_text(log_path)
        message_id = _extract_message_id(log_path)
        record['error_kind'] = _classify_error(log_text, rc) if rc != 0 else None
        if message_id:
            record['message_id'] = message_id
        # ok requires BOTH rc=0 AND a non-empty message_id. Either failure
        # is a candidate for retry (when retryable_kind) or terminal
        # (binary_missing / config_missing / media_allowed / exit_nonzero).
        record['ok'] = bool(rc == 0 and message_id)
        if rc != 0:
            record['error'] = f'openclaw exit {rc} (redacted)'
        elif not message_id:
            record['error'] = 'openclaw exit 0 but no message_id parsed (treated as undelivered)'
    except Exception as e:
        record['error'] = f'{type(e).__name__}: {e}'
        record['error_kind'] = 'exit_nonzero'
    finally:
        try:
            record['ended_at'] = time.strftime('%Y-%m-%dT%H:%M:%S')
            if record.get('started_at') and record.get('ended_at'):
                t0 = time.mktime(time.strptime(record['started_at'], '%Y-%m-%dT%H:%M:%S'))
                t1 = time.mktime(time.strptime(record['ended_at'], '%Y-%m-%dT%H:%M:%S'))
                record['duration_seconds'] = max(0, int(t1 - t0))
        except Exception:
            record['duration_seconds'] = 0
        if proc is not None:
            try:
                proc.wait(timeout=1)
            except Exception:
                pass
    return record


def send_text(text: str, chat_id: str = None, wait: bool = False, media: str = None, openclaw_bin: str = None) -> dict:
    """Single-shot send (kept for backwards compatibility).

    For new code prefer ``send_text_with_retry``, which adds bounded
    retry on transport-class failures. This function preserves the
    legacy behaviour: it either blocks until the underlying process
    returns (wait=True), or fires-and-forgets (wait=False).
    """
    resolved = _resolve_openclaw_bin(openclaw_bin)
    if not _check_openclaw_bin(openclaw_bin):
        return {'ok': False, 'error': f'OpenClaw binary missing or not executable. Tried: ARTVEE_OPENCLAW_BIN={ARTVEE_OPENCLAW_BIN!r}, OPENCLAW_BIN={OPENCLAW_BIN!r}, PATH lookup for openclaw, or --openclaw-bin if provided.', 'resolved': resolved}

    if chat_id is None:
        chat_id = load_chat_id()  # raises if not configured

    # 构建命令
    cmd = [
        resolved, 'message', 'send',
        '--channel', 'telegram',
        '--target', chat_id,
        '--message', text,
    ]
    if media:
        cmd += ['--media', str(media)]

    # 日志文件路径
    ts = time.strftime('%Y%m%d_%H%M%S')
    log_path = f'/tmp/artvee_notify_{ts}.log'

    try:
        # 使用 Popen 后台启动，创建新会话避免信号干扰
        with open(log_path, 'w') as log_fh:
            proc = subprocess.Popen(
                cmd,
                stdout=log_fh,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
            )

        if wait:
            # 等待完成（仅测试用）
            try:
                proc.wait(timeout=300)
                rc = proc.returncode
                message_id = _extract_message_id(log_path)
                result = {
                    'ok': bool(rc == 0 and message_id),
                    'pid': proc.pid,
                    'returncode': rc,
                    'log_path': log_path,
                }
                if message_id:
                    result['message_id'] = message_id
                if rc != 0:
                    log_text = _read_log_text(log_path)
                    result['error'] = f'openclaw exit {rc} (redacted)'
                    result['error_kind'] = _classify_error(log_text, rc)
                elif not message_id:
                    log_text = _read_log_text(log_path)
                    result['error'] = 'openclaw exit 0 but no message_id parsed (treated as undelivered)'
                    result['error_kind'] = 'unknown'
                return result
            except subprocess.TimeoutExpired:
                return {
                    'ok': False,
                    'error': 'timeout after 300s',
                    'error_kind': 'timeout',
                    'pid': proc.pid,
                    'log_path': log_path,
                }
        else:
            # 立即返回
            return {
                'ok': True,
                'pid': proc.pid,
                'log_path': log_path,
                'error_kind': 'not_waited',
                'note': 'background_send_started',
            }
    except Exception as e:
        return {
            'ok': False,
            'error': str(e),
        }


def send_text_with_retry(
    text: str,
    chat_id: str = None,
    media: str = None,
    openclaw_bin: str = None,
    *,
    max_attempts: int = None,
    backoff_seconds: list = None,
) -> dict:
    """Bounded-retry wrapper around ``send_text``.

    P8D+5: design contract.
    - ``error_kind`` ∈ ``{transport, timeout}`` ⇒ retry up to ``max_attempts``
      with the given per-attempt backoff. Any successful attempt (rc=0 AND
      non-empty ``message_id``) returns immediately with ``delivered: True``.
    - ``error_kind`` ∈ ``{binary_missing, config_missing, media_allowed,
      exit_nonzero, unknown}`` ⇒ stop on the first attempt; these are
      deterministic and re-running them will just burn time / fill logs.
    - ``error`` is set on every attempt; the final return merges the last
      attempt's error plus an explicit ``retry_history`` array so the caller
      has the full audit trail without needing to re-parse the per-attempt
      logs.
    - The function NEVER prints chat id, token, or any secret. Internal
      logging is sanitized via ``_redact_log`` before being captured into
      the returned dict's ``error`` field.
    """
    if max_attempts is None:
        max_attempts = _env_int('ARTVEE_NOTIFY_MAX_ATTEMPTS', DEFAULT_MAX_ATTEMPTS)
    if backoff_seconds is None:
        backoff_seconds = _env_backoff('ARTVEE_NOTIFY_BACKOFF_SECONDS', DEFAULT_BACKOFF_SECONDS)
    # Truncate the backoff list to the number of attempts we will run.
    if len(backoff_seconds) < max_attempts:
        backoff_seconds = list(backoff_seconds) + [backoff_seconds[-1]] * (max_attempts - len(backoff_seconds))

    resolved = _resolve_openclaw_bin(openclaw_bin)
    if not _check_openclaw_bin(openclaw_bin):
        return {
            'ok': False, 'delivered': False,
            'error': 'OpenClaw binary missing or not executable',
            'error_kind': 'binary_missing',
            'attempt_used': 0,
            'max_attempts': max_attempts,
            'retry_history': [],
            'resolved': resolved,
        }

    # Resolve chat id once up-front; missing config never retries.
    if chat_id is None:
        try:
            chat_id = load_chat_id()
        except Exception as e:
            return {
                'ok': False, 'delivered': False,
                'error': f'chat id resolution failed: {type(e).__name__}',
                'error_kind': 'config_missing',
                'attempt_used': 0,
                'max_attempts': max_attempts,
                'retry_history': [],
            }

    ts = time.strftime('%Y%m%d_%H%M%S')
    history: list = []
    for attempt_idx in range(1, max_attempts + 1):
        rec = _run_one_attempt(text, chat_id, media, resolved, ts, attempt_idx)
        # Record the attempt. Strip the redundant ``started_at`` from older
        # attempts to keep the final payload small, but keep ``log_path``
        # so support can read the per-attempt log later.
        rec_for_history = dict(rec)
        history.append(rec_for_history)
        if rec.get('ok') and rec.get('message_id'):
            return {
                'ok': True, 'delivered': True,
                'message_id': rec['message_id'],
                'error_kind': None,
                'attempt_used': attempt_idx,
                'max_attempts': max_attempts,
                'retry_history': history,
                'log_path': rec.get('log_path'),
            }
        kind = rec.get('error_kind') or 'unknown'
        # Non-retryable → stop.
        if kind not in _RETRYABLE_KINDS:
            return {
                'ok': False, 'delivered': False,
                'error': _redact_log(rec.get('error') or ''),
                'error_kind': kind,
                'attempt_used': attempt_idx,
                'max_attempts': max_attempts,
                'retry_history': history,
            }
        # Retryable. Sleep before next attempt unless this was the last.
        if attempt_idx < max_attempts:
            wait_seconds = backoff_seconds[attempt_idx - 1]
            if wait_seconds > 0:
                time.sleep(wait_seconds)

    # Out of attempts and still failing with a retryable kind.
    last = history[-1] if history else {}
    return {
        'ok': False, 'delivered': False,
        'error': _redact_log(last.get('error') or ''),
        'error_kind': last.get('error_kind') or 'transport',
        'attempt_used': max_attempts,
        'max_attempts': max_attempts,
        'retry_history': history,
    }


def main():
    parser = argparse.ArgumentParser(description='Send Telegram text notification for Artvee via OpenClaw Gateway')
    parser.add_argument('--text', required=False, help='Message text to send')
    parser.add_argument('--chat-id', default=None, help='Override chat_id')
    parser.add_argument('--check-config', action='store_true', help='Check chat-id resolution and print diagnostic (no send)')
    parser.add_argument('--media', default=None, help='Optional media path (must be in OpenClaw allowed dirs)')
    parser.add_argument('--wait', action='store_true', help='Wait for send to complete (slow, 120-180s)')
    parser.add_argument('--openclaw-bin', default=None, help='Path or command name for OpenClaw binary (overrides env vars)')
    args = parser.parse_args()

    if args.check_config:
        import json
        diag = _check_config()
        print(json.dumps(diag, indent=2, ensure_ascii=False))
        sys.exit(0 if diag.get('resolved') else 1)

    if not args.text:
        parser.error('--text is required unless --check-config is used')

    try:
        result = send_text(args.text, chat_id=args.chat_id, wait=args.wait, media=args.media, openclaw_bin=args.openclaw_bin)
        if result.get('ok'):
            # Print NOTIFY_OK on stdout for caller parsing. Never print tokens
            # or chat_id. Include message_id when --wait captured it.
            mid = result.get('message_id')
            mid_part = f' message_id={mid}' if mid else ''
            kind_part = f' error_kind={result.get("error_kind")}' if result.get('error_kind') and result.get('error_kind') != 'not_waited' else ''
            print(f'NOTIFY_OK pid={result.get("pid")} log={result.get("log_path")}{mid_part}{kind_part}')
            if args.wait and result.get('returncode') is not None:
                print(f'RETURN_CODE={result["returncode"]}')
            sys.exit(0)
        else:
            kind_part = f' error_kind={result.get("error_kind")}' if result.get('error_kind') else ''
            print(f'NOTIFY_FAIL: {result.get("error", "unknown")}{kind_part}')
            sys.exit(1)
    except Exception as e:
        print(f'NOTIFY_ERROR: {e}')
        sys.exit(2)


if __name__ == '__main__':
    main()
