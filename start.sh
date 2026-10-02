#!/usr/bin/env bash
# ============================================================
# PhoneMic 源码启动脚本（Git Bash / MSYS2 / Cygwin on Windows）
#
#   用法：
#     ./start.sh                      普通启动（日志直接打在当前终端）
#     ./start.sh --select-mode last   跳过「选择网卡」弹窗，沿用上次的网络
#     ./start.sh --silent             最小化启动，只留托盘图标
#
#   首次运行会自动创建 Python 3.13 虚拟环境并装依赖（需要先装 uv）。
#
#   ⚠️ Linux / macOS 上跑不起来：PhoneMic 目前是 Windows 专属 —— 
#   phonemic/gui/keyboard.py 顶层就 import win32con / win32gui，且 pyproject
#   无条件依赖 pywin32（它只发布 Windows 轮子）。下面的 POSIX 分支只是
#   在依赖将来跨平台时能直接用上，不作为当前支持。
# ============================================================
set -euo pipefail
cd "$(dirname "$0")"

# Windows 版 uv 建的 venv 是 Scripts/ 布局，POSIX 才是 bin/
find_python() {
    if [ -x ".venv/Scripts/python.exe" ]; then
        printf '%s' ".venv/Scripts/python.exe"
    elif [ -x ".venv/bin/python" ]; then
        printf '%s' ".venv/bin/python"
    fi
}

PY="$(find_python)"

if [ -z "$PY" ]; then
    if ! command -v uv >/dev/null 2>&1; then
        echo "[PhoneMic] 未找到 uv，请先安装：" >&2
        echo "    https://docs.astral.sh/uv/getting-started/installation/" >&2
        exit 1
    fi
    echo "[PhoneMic] 首次运行：创建 Python 3.13 虚拟环境并安装依赖，请稍候..."
    uv venv --python 3.13
    # 只装运行依赖：dev 组里的 nuitka 仅用于打包 exe，日常启动用不到
    uv sync --no-dev
    PY="$(find_python)"
fi

if [ -z "$PY" ]; then
    echo "[PhoneMic] 虚拟环境已创建，但仍找不到 python，请检查上面 uv 的输出。" >&2
    exit 1
fi

exec "$PY" -m phonemic.PhoneMic "$@"
