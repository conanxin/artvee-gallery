#!/usr/bin/env bash
# Artvee Gallery 本地静态服务
# 用法：
#   bash scripts/serve_artvee_gallery.sh            # 默认端口 8877
#   PORT=9000 bash scripts/serve_artvee_gallery.sh  # 自定义端口
# 访问：http://127.0.0.1:8877/web/
#
# 仅依赖系统 Python 3，不引入额外服务。

set -euo pipefail

PORT="${PORT:-8877}"
HOST="${HOST:-127.0.0.1}"
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$BASE_DIR"

echo "[artvee-gallery] serving $BASE_DIR on http://$HOST:$PORT/"
echo "[artvee-gallery] 访问: http://$HOST:$PORT/web/"
echo "[artvee-gallery] Ctrl-C 停止"

# 端口占用快速检测（非强制，提示用户）
if command -v ss >/dev/null 2>&1 && ss -ltn 2>/dev/null | grep -q ":$PORT "; then
    echo "[artvee-gallery] WARNING: 端口 $PORT 已被占用。请用 PORT=9000 bash $0 换一个。" >&2
fi

exec python3 -m http.server "$PORT" --bind "$HOST"
