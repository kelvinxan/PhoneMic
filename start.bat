@echo off
REM ============================================================
REM PhoneMic 源码启动脚本（Windows）
REM
REM   双击即可运行。首次运行会自动创建 Python 3.13 虚拟环境并装依赖
REM   （需要先装 uv，见 README 的「从源码运行」）。
REM
REM   参数会原样传给程序，例如：
REM     start.bat --select-mode last   跳过「选择网卡」弹窗，沿用上次的网络
REM     start.bat --silent             最小化启动，只留托盘图标
REM
REM   本脚本用 pythonw 启动，不额外挂控制台窗口，行为与 make_windows_lnk.ps1
REM   生成的桌面快捷方式一致。想在命令行看实时日志请手动跑：
REM     .venv\Scripts\python.exe -m phonemic.PhoneMic
REM ============================================================
REM 本文件是 UTF-8 编码，而 cmd 默认按系统 OEM 代码页（简中 Windows 是 936/GBK）
REM 解读输出，中文会变乱码——双击运行尤其明显（新控制台用系统默认代码页）。
REM 切到 65001 后 echo 才能正确显示。只影响本脚本所在的控制台。
chcp 65001 >nul

setlocal EnableExtensions
cd /d "%~dp0"

set "PY=%CD%\.venv\Scripts\python.exe"
set "PYW=%CD%\.venv\Scripts\pythonw.exe"

if exist "%PY%" goto run

where uv >nul 2>nul || goto no_uv

echo [PhoneMic] 首次运行：创建 Python 3.13 虚拟环境并安装依赖，请稍候...
REM 必须用 call：官方安装的 uv 是 .exe，但若将来变成 .bat/.cmd 包装脚本，
REM 不加 call 会把控制权移交出去、本脚本的后面几行（含失败提示）就再也执行不到
call uv venv --python 3.13 || goto venv_failed
REM 只装运行依赖：dev 组里的 nuitka 仅用于打包 exe，日常启动用不到
call uv sync --no-dev || goto sync_failed
goto run

:no_uv
echo [PhoneMic] 未找到 uv，请先安装 uv 再重试：
REM 管道符在双引号内不是特殊字符，不要写 ^| —— 引号里的 caret 会原样输出
echo     powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
echo   详见 https://docs.astral.sh/uv/getting-started/installation/
pause
exit /b 1

:venv_failed
echo [PhoneMic] 创建虚拟环境失败，请检查上面的 uv 输出。
pause
exit /b 1

:sync_failed
echo [PhoneMic] 安装依赖失败，请检查上面的 uv 输出。
pause
exit /b 1

:run
start "" "%PYW%" -m phonemic.PhoneMic %*
endlocal
