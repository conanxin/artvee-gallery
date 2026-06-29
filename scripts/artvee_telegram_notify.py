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
    if returncode != 0 and not text:
        return "exit_nonzero"
    return "unknown"


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

    Looks for common patterns in stdout:
      - 'Message ID: 12345'
      - 'message_id: 12345'
      - 'message_id=12345'
    Returns the first hit, or None if not found.
    Safe: only reads the log file, never prints tokens or chat ids.
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
        r'Message ID[:\s]+(\d+)',
        r'message_id["\s:=]+(\d+)',
        r'"message_id"\s*:\s*"(\d+)"',
    ]
    for pat in patterns:
        m = re.search(pat, content)
        if m:
            return m.group(1)
    return None


def send_text(text: str, chat_id: str = None, wait: bool = False, media: str = None, openclaw_bin: str = None) -> dict:
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
                    'ok': rc == 0,
                    'pid': proc.pid,
                    'returncode': rc,
                    'log_path': log_path,
                }
                if message_id:
                    result['message_id'] = message_id
                if rc != 0:
                    log_text = ''
                    try:
                        with open(log_path, 'r', encoding='utf-8', errors='replace') as lf:
                            log_text = lf.read()
                    except Exception:
                        pass
                    result['error'] = f'openclaw exit {rc}'
                    result['error_kind'] = _classify_error(log_text, rc)
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
