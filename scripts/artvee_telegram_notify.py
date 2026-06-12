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
DEFAULT_CHAT_ID = '1540208324'


def load_chat_id():
    if not CFG_PATH.is_file():
        return DEFAULT_CHAT_ID
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
    return DEFAULT_CHAT_ID


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


def send_text(text: str, chat_id: str = None, wait: bool = False, media: str = None, openclaw_bin: str = None) -> dict:
    resolved = _resolve_openclaw_bin(openclaw_bin)
    if not _check_openclaw_bin(openclaw_bin):
        return {'ok': False, 'error': f'OpenClaw binary missing or not executable. Tried: ARTVEE_OPENCLAW_BIN={ARTVEE_OPENCLAW_BIN!r}, OPENCLAW_BIN={OPENCLAW_BIN!r}, PATH lookup for openclaw, or --openclaw-bin if provided.', 'resolved': resolved}

    if chat_id is None:
        chat_id = load_chat_id()

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
                return {
                    'ok': True,
                    'pid': proc.pid,
                    'returncode': proc.returncode,
                    'log_path': log_path,
                }
            except subprocess.TimeoutExpired:
                return {
                    'ok': False,
                    'error': 'timeout after 300s',
                    'pid': proc.pid,
                    'log_path': log_path,
                }
        else:
            # 立即返回
            return {
                'ok': True,
                'pid': proc.pid,
                'log_path': log_path,
                'note': 'background_send_started',
            }
    except Exception as e:
        return {
            'ok': False,
            'error': str(e),
        }


def main():
    parser = argparse.ArgumentParser(description='Send Telegram text notification for Artvee via OpenClaw Gateway')
    parser.add_argument('--text', required=True, help='Message text to send')
    parser.add_argument('--chat-id', default=None, help='Override chat_id')
    parser.add_argument('--media', default=None, help='Optional media path (must be in OpenClaw allowed dirs)')
    parser.add_argument('--wait', action='store_true', help='Wait for send to complete (slow, 120-180s)')
    parser.add_argument('--openclaw-bin', default=None, help='Path or command name for OpenClaw binary (overrides env vars)')
    args = parser.parse_args()

    try:
        result = send_text(args.text, chat_id=args.chat_id, wait=args.wait, media=args.media, openclaw_bin=args.openclaw_bin)
        if result.get('ok'):
            print(f'NOTIFY_OK pid={result.get("pid")} log={result.get("log_path")}')
            if args.wait and result.get('returncode') is not None:
                print(f'RETURN_CODE={result["returncode"]}')
            sys.exit(0)
        else:
            print(f'NOTIFY_FAIL: {result.get("error", "unknown")}')
            sys.exit(1)
    except Exception as e:
        print(f'NOTIFY_ERROR: {e}')
        sys.exit(2)


if __name__ == '__main__':
    main()
