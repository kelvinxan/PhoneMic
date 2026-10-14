#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PhoneMic 统一构建脚本
用法:
    python build.py --mode standalone              # 编译 + 打包 (默认)
    python build.py --mode standalone --action compile   # 只编译
    python build.py --mode standalone --action package   # 只打包 (需已有编译结果)
    python build.py --mode onefile --action compile      # 只编译单文件
    python build.py --mode onefile                       # 编译单文件并复制到 dist
"""

import subprocess
import sys
import argparse
import shutil
from datetime import datetime
from pathlib import Path
import json
import tomllib

# ---------- 项目配置 ----------
PROJECT_ROOT = Path(__file__).parent
PYPROJECT_PATH = PROJECT_ROOT / "pyproject.toml"
DIST_DIR = PROJECT_ROOT / "dist"
BUILD_DIR = PROJECT_ROOT / "build" / "phonemic_nuitka"

# Nuitka 配置
ICON_PATH = PROJECT_ROOT / "phonemic" / "resources" / "favicon.ico"
MAIN_SCRIPT = PROJECT_ROOT / "phonemic" / "PhoneMic.py"

# LTO（链接期优化）开关，默认开启。Windows 上出现段错误时可 --lto no 排查
# （某些 MSVC 工具集的 LTO 会生成错误的机器码，表现为启动后随机崩溃）。
LTO_MODE = "yes"

# 调试构建开关（--debug）：关闭 C 优化、保留调试信息，用于定位打包版崩溃。
# 官方建议段错误排查先试它；代价是体积更大、运行更慢，不适合发布。
DEBUG_MODE = False

# NSIS 配置
NSIS_SCRIPT = PROJECT_ROOT / "makesetup.nsi"

# ---------- 第三方二进制依赖 ----------
VENDOR_CACHE = PROJECT_ROOT / "build" / "vendor"

VENDORS = [
    {
        "name": "cloudflared",
        "url": "https://github.com/cloudflare/cloudflared/releases/download/2026.9.1/cloudflared-windows-amd64.exe",
        "sha256": "2837888cc0f5d58f15b6dc478376de90b4d3ba5241c7947455d1e0a0df429712",
        "dest": "bin/cloudflared.exe",
    },
]

# ---------- 第三方二进制下载 ----------
def prepare_vendors() -> None:
    """下载并校验第三方二进制到缓存目录，然后拷贝到 standalone dist。"""
    import hashlib
    import urllib.request

    VENDOR_CACHE.mkdir(parents=True, exist_ok=True)
    standalone_dist = BUILD_DIR / "PhoneMic.dist"

    for v in VENDORS:
        filename = Path(v["dest"]).name
        cache_path = VENDOR_CACHE / filename

        if cache_path.exists():
            sha = hashlib.sha256(cache_path.read_bytes()).hexdigest()
            if sha == v["sha256"]:
                print(f"  ✓ {v['name']}: 缓存有效，跳过下载")
            else:
                print(f"  ↓ {v['name']}: SHA256 不匹配，重新下载...")
                urllib.request.urlretrieve(v["url"], cache_path)
        else:
            print(f"  ↓ {v['name']}: 下载中...")
            urllib.request.urlretrieve(v["url"], cache_path)

        sha = hashlib.sha256(cache_path.read_bytes()).hexdigest()
        if sha != v["sha256"]:
            print(f"  ✗ {v['name']}: SHA256 校验失败\n    期望: {v['sha256']}\n    实际: {sha}", file=sys.stderr)
            sys.exit(1)
        print(f"  ✓ {v['name']}: SHA256 校验通过")

        dest_path = standalone_dist / v["dest"]
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(cache_path, dest_path)
        print(f"  → {v['name']}: 已拷贝到 {dest_path.relative_to(PROJECT_ROOT)}")


# ---------- 辅助函数 ----------
def read_version_from_pyproject():
    """从 pyproject.toml 读取版本号（PEP 621）"""
    with open(PYPROJECT_PATH, "rb") as f:
        data = tomllib.load(f)
    try:
        version = data["project"]["version"]
        print(f"从 pyproject.toml 读取版本: {version}")
        return version
    except KeyError:
        print("错误: pyproject.toml 中缺少 [project] 下的 version 字段", file=sys.stderr)
        sys.exit(1)

def get_git_commit_short():
    """获取当前 Git 短哈希"""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, check=True, encoding="utf-8"
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("警告: 无法获取 Git commit，使用 'nogit'", file=sys.stderr)
        return "nogit"

def get_current_date():
    """返回当前日期字符串 YYYYMMDD"""
    return datetime.now().strftime("%Y%m%d")

def ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)

def clean_build_output():
    """清理旧的 Nuitka 构建产物（可选）"""
    if BUILD_DIR.exists():
        print(f"清理旧构建目录: {BUILD_DIR}")
        shutil.rmtree(BUILD_DIR)

def run_nuitka(onefile: bool, version: str, commit: str):
    """
    调用 Nuitka 编译
    :param onefile: True -> 单文件模式，False -> standalone 目录模式
    :param version: 版本号，用于嵌入可执行文件
    :param commit: git commit，用于 build_info.json
    """
    # 生成 build_info.json 到 BUILD_DIR
    build_info = {
        "version": version,
        "commit": commit,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    build_info_path = BUILD_DIR / "build_info.json"
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    with open(build_info_path, "w", encoding="utf-8") as f:
        json.dump(build_info, f, indent=2)

    cmd = [
        sys.executable, "-m", "nuitka",
        "--onefile" if onefile else "--standalone",
        "--windows-console-mode=disable",
        f"--windows-icon-from-ico={ICON_PATH}",
        f"--output-dir={BUILD_DIR}",
        f"--lto={LTO_MODE}",
        "--enable-plugin=pyside6",
        "--include-data-dir=./phonemic/resources=phonemic/resources",
        "--noinclude-data-files=*/test.html",
        f"--include-data-files={build_info_path}=build_info.json",
        "--include-data-files=./LICENSE=LICENSE",
        "--include-data-files=./LICENSE.LGPL.txt=LICENSE.LGPL.txt",
        "--include-data-files=./NOTICE.txt=NOTICE.txt",
        "--include-data-files=./README.md=README.md",
        "--include-data-files=./USER_GUIDE.md=USER_GUIDE.md",
        # uvicorn 的 ws 协议类是字符串动态导入（uvicorn.config.load → import_from_string），
        # Nuitka 静态分析看不到；Nuitka 自带的 uvicorn 包规则只硬编码了 auto /
        # websockets_impl / wsproto_impl 三个（standard.nuitka-package.config.yml），
        # 不含新版才有的 websockets_sansio_impl。api.py 传的是 ws="websockets-sansio"，
        # 不显式包含的话打包版启动即 ImportError（--windows-console-mode=disable 下
        # 无声无息），GUI 只能报「服务器启动超时，请检查端口是否可用」——端口是背锅的。
        "--include-module=uvicorn.protocols.websockets.websockets_sansio_impl",
        "--noinclude-default-mode=error",
        "--nofollow-import-to=tkinter,unittest,pydoc,test,distutils,setuptools,pdb",
        "--nofollow-import-to=PIL",
        # 已移除的旧依赖（防御性排除，防止残留引用）
        "--nofollow-import-to=fastapi,pydantic,tremolo,aiohttp,multidict,yarl,frozenlist,aiosignal",
        "--nofollow-import-to=jinja2,requests",
        # aiohttp 可选加速包（未安装，防御性排除）
        "--nofollow-import-to=aiodns,brotli,cchardet",
        # 注意: ssl/hashlib/http 不可排除，Starlette/Uvicorn 依赖它们
        "--nofollow-import-to=PySide6.QtWebEngineWidgets",
        "--nofollow-import-to=PySide6.QtNetworkAuth",
        "--nofollow-import-to=PySide6.QtQml",
        "--nofollow-import-to=PySide6.QtQuick",
        "--nofollow-import-to=PySide6.QtTest",
        "--nofollow-import-to=PySide6.QtXml",
        # 非交互构建（CI / 重定向输出的终端）：Nuitka 默认会询问是否下载
        # Dependency Walker，无 stdin 时按默认值 "No" 退出、编译直接失败。
        "--assume-yes-for-downloads",
        "--jobs=4",
        "--experimental=debug-report-traceback",
        "--product-name=PhoneMic",
        '--company-name="PhoneMic Team"',
        f"--file-version={version}",
        f"--product-version={version}",
        '--file-description="PhoneMic - 手机语音输入电脑端"',
        '--copyright="Copyright (c) 2026 PhoneMic Team. Licensed under Apache 2.0."',
        # --debug 必须放在主脚本之前，否则会被当成脚本参数传给程序本身
        # PySide6 会改写对象的 immortal 引用计数，故 --debug 下必须关掉该项检查
        *(["--debug", "--no-debug-immortal-assumptions"] if DEBUG_MODE else []),
        str(MAIN_SCRIPT)
    ]
    print("Running Nuitka command:")
    print(" ".join(cmd))
    subprocess.check_call(cmd)

def check_makensis():
    """检查 makensis 是否在 PATH 中，若不存在则退出"""
    if shutil.which("makensis") is None:
        print("错误: 找不到 makensis，请安装 NSIS 并将其添加到 PATH 环境变量中", file=sys.stderr)
        sys.exit(1)

def copy_to_dist_onefile(version: str, date_str: str, commit: str):
    """将生成的 single exe 复制到 dist/ 目录并重命名"""
    src_exe = BUILD_DIR / "PhoneMic.exe"
    if not src_exe.exists():
        print(f"错误: 找不到生成的 exe 文件 {src_exe}", file=sys.stderr)
        sys.exit(1)
    target_name = f"PhoneMic_{version}_{date_str}_{commit}.exe"
    target_path = DIST_DIR / target_name
    shutil.copy2(src_exe, target_path)
    print(f"✅ OneFile 已复制到: {target_path}")

def compile_standalone(version: str, commit: str):
    """只编译 standalone 模式，不打包"""
    run_nuitka(onefile=False, version=version, commit=commit)
    standalone_dist = BUILD_DIR / "PhoneMic.dist"
    if not standalone_dist.exists():
        print(f"错误: Nuitka standalone 输出目录不存在: {standalone_dist}", file=sys.stderr)
        sys.exit(1)
    print(f"✅ Standalone 编译完成，输出目录: {standalone_dist}")

def package_standalone(version: str, date_str: str, commit: str, vendor: bool = False):
    """只打包 NSIS 安装包（假设 standalone 目录已存在）"""
    check_makensis()
    standalone_dist = BUILD_DIR / "PhoneMic.dist"
    if not standalone_dist.exists():
        print(f"错误: standalone 输出目录不存在，请先运行编译: {standalone_dist}", file=sys.stderr)
        sys.exit(1)
    if not NSIS_SCRIPT.exists():
        print(f"错误: 找不到 NSIS 脚本 {NSIS_SCRIPT}", file=sys.stderr)
        sys.exit(1)

    suffix_parts = []
    if vendor:
        suffix_parts.append("bundled")
    suffix_parts.extend([date_str, version, commit])
    build_suffix = "_".join(suffix_parts)
    cmd = [
        "makensis",
        f"/DVERSION={version}",
        f"/DBUILD_DATE={date_str}",
        f"/DBUILD_COMMIT={commit}",
        f"/DBUILD_SUFFIX={build_suffix}",
        str(NSIS_SCRIPT)
    ]
    print("Running makensis:")
    print(" ".join(cmd))
    subprocess.check_call(cmd)
    print(f"✅ 安装包已生成到 {DIST_DIR}/PhoneMic_Setup_{build_suffix}.exe")

def build_standalone_installer(version: str, date_str: str, commit: str, action: str, vendor: bool = False):
    """
    根据 action 执行 standalone 构建流程
    """
    if action == "package":
        print("⚠️  package 模式将跳过编译，仅打包现有 standalone 目录")
    if action in ("all", "compile"):
        compile_standalone(version, commit)
    if vendor:
        print("📦 准备第三方二进制依赖...")
        prepare_vendors()
    if action in ("all", "package"):
        package_standalone(version, date_str, commit, vendor)

def build_onefile(version: str, date_str: str, commit: str, action: str):
    """
    根据 action 执行 onefile 构建流程
    """
    if action == "package":
        print("错误: onefile 模式不支持 package 动作（无 NSIS 打包）", file=sys.stderr)
        sys.exit(1)
    # compile 或 all 都执行编译
    run_nuitka(onefile=True, version=version, commit=commit)
    # 复制到 dist
    copy_to_dist_onefile(version, date_str, commit)
    print("✅ OneFile 构建完成")

# ---------- 主入口 ----------
def main():
    parser = argparse.ArgumentParser(description="PhoneMic 构建脚本")
    parser.add_argument(
        "--mode", choices=["standalone", "onefile"], default="standalone",
        help="构建模式: standalone (默认：生成安装包) 或 onefile (单文件)"
    )
    parser.add_argument(
        "--action", choices=["all", "compile", "package"], default="all",
        help="执行动作: all (默认，编译+打包), compile (只编译), package (只打包，仅 standalone 有效)"
    )
    parser.add_argument(
        "--vendor", action="store_true",
        help="编译后将第三方二进制（如 cloudflared）拷贝到 standalone dist 的 bin/ 目录"
    )
    parser.add_argument(
        "--lto", choices=["yes", "no"], default="yes",
        help="是否启用 Nuitka 的链接期优化（默认 yes；排查运行时段错误时可设为 no）"
    )
    parser.add_argument(
        "--debug", action="store_true",
        help="调试构建（关闭 C 优化、保留调试信息），用于定位打包版崩溃；与 --lto yes 互斥"
    )
    args = parser.parse_args()

    global LTO_MODE, DEBUG_MODE
    LTO_MODE = args.lto
    DEBUG_MODE = args.debug
    if DEBUG_MODE:
        LTO_MODE = "no"

    # 前置检查
    if not ICON_PATH.exists():
        print(f"错误: 图标文件不存在: {ICON_PATH}", file=sys.stderr)
        sys.exit(1)
    if not MAIN_SCRIPT.exists():
        print(f"错误: 主程序入口不存在: {MAIN_SCRIPT}", file=sys.stderr)
        sys.exit(1)

    # 读取版本号
    version = read_version_from_pyproject()
    date_str = get_current_date()
    commit = get_git_commit_short()

    # 确保输出目录存在
    ensure_dir(DIST_DIR)

    if args.mode == "onefile":
        print("🔧 构建模式: OneFile 单文件")
        build_onefile(version, date_str, commit, args.action)
    else:  # standalone
        print("🔧 构建模式: Standalone + NSIS 安装包")
        build_standalone_installer(version, date_str, commit, args.action, args.vendor)

if __name__ == "__main__":
    main()