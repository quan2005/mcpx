#!/usr/bin/env python3
"""Build macOS .app bundle for MCPX Desktop.

使用方法:
    uv run python scripts/build_macos_app.py

依赖:
    uv pip install py2app

产物:
    dist/MCPX.app
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DIST_DIR = PROJECT_ROOT / "dist"
BUILD_DIR = PROJECT_ROOT / "build"
APP_NAME = "MCPX"


def run_command(cmd: list[str], cwd: Path | None = None) -> None:
    """运行命令并检查结果。"""
    print(f"  > {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd)
    if result.returncode != 0:
        print(f"命令失败: {result.returncode}")
        sys.exit(1)


def clean() -> None:
    """清理旧的构建产物。"""
    print("清理旧的构建产物...")
    for dir_path in [DIST_DIR, BUILD_DIR]:
        if dir_path.exists():
            shutil.rmtree(dir_path)
            print(f"  已删除: {dir_path}")


def create_setup_py() -> Path:
    """创建 py2app 的 setup.py 文件。"""
    setup_content = '''"""py2app setup script for MCPX Desktop."""

from setuptools import setup

APP = ["src/mcpx/__main__.py"]
DATA_FILES = [
    ("", ["config.example.json"]),
]

OPTIONS = {
    "argv_emulation": False,
    "iconfile": "scripts/MCPX.icns",
    "plist": {
        "CFBundleName": "MCPX",
        "CFBundleDisplayName": "MCPX Desktop",
        "CFBundleIdentifier": "com.mcpx.desktop",
        "CFBundleVersion": "0.5.0",
        "CFBundleShortVersionString": "0.5.0",
        "NSHighResolutionCapable": True,
        "LSMinimumSystemVersion": "10.15",
        "CFBundleDocumentTypes": [
            {
                "CFBundleTypeName": "JSON Configuration",
                "CFBundleTypeExtensions": ["json"],
                "CFBundleTypeRole": "Editor",
            }
        ],
    },
    "packages": [
        "mcpx",
        "fastmcp",
        "mcp",
        "pydantic",
        "toons",
        "uvicorn",
        "starlette",
        "httpx",
        "anyio",
        "webview",
    ],
    "includes": [
        "mcpx.web",
        "mcpx.web.api",
    ],
    "excludes": [
        "pytest",
        "pytest_asyncio",
        "pytest_cov",
        "ruff",
        "mypy",
    ],
}

setup(
    name="MCPX",
    app=APP,
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
'''
    setup_path = PROJECT_ROOT / "setup.py"
    setup_path.write_text(setup_content)
    print(f"  已创建: {setup_path}")
    return setup_path


def create_icon() -> None:
    """创建应用图标（如果不存在）。"""
    icns_path = PROJECT_ROOT / "scripts" / "MCPX.icns"
    if icns_path.exists():
        print(f"  图标已存在: {icns_path}")
        return

    # 创建一个简单的占位图标（使用 sips 从 PNG 转换）
    # 这里先创建一个脚本来生成图标
    iconset_dir = PROJECT_ROOT / "scripts" / "MCPX.iconset"
    iconset_dir.mkdir(parents=True, exist_ok=True)

    # 创建一个简单的 SVG 图标
    svg_content = '''<?xml version="1.0" encoding="UTF-8"?>
<svg width="512" height="512" viewBox="0 0 512 512" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#6366f1"/>
      <stop offset="100%" style="stop-color:#8b5cf6"/>
    </linearGradient>
  </defs>
  <rect width="512" height="512" rx="100" fill="url(#bg)"/>
  <text x="256" y="320" font-family="SF Pro Display, Helvetica, Arial, sans-serif"
        font-size="180" font-weight="bold" fill="white" text-anchor="middle">MCP</text>
  <text x="256" y="420" font-family="SF Pro Display, Helvetica, Arial, sans-serif"
        font-size="80" fill="rgba(255,255,255,0.8)" text-anchor="middle">X</text>
</svg>'''

    svg_path = PROJECT_ROOT / "scripts" / "MCPX.svg"
    svg_path.write_text(svg_content)

    # 使用 sips 和 iconutil 创建 icns（macOS 原生工具）
    print("  生成应用图标...")

    # 需要不同尺寸的 PNG
    sizes = [16, 32, 64, 128, 256, 512]
    for size in sizes:
        png_path = iconset_dir / f"icon_{size}x{size}.png"
        # 使用 sips 转换 SVG 到 PNG（如果系统支持）
        # 这里使用 ImageMagick 的 convert 或者跳过
        try:
            # 尝试使用 rsvg-convert
            run_command(
                ["rsvg-convert", "-w", str(size), "-h", str(size), str(svg_path), "-o", str(png_path)],
                cwd=PROJECT_ROOT,
            )
            # 2x 版本
            if size <= 256:
                png_2x_path = iconset_dir / f"icon_{size}x{size}@2x.png"
                run_command(
                    [
                        "rsvg-convert",
                        "-w",
                        str(size * 2),
                        "-h",
                        str(size * 2),
                        str(svg_path),
                        "-o",
                        str(png_2x_path),
                    ],
                    cwd=PROJECT_ROOT,
                )
        except Exception:
            print(f"    跳过图标生成（缺少 rsvg-convert），请手动放置 {icns_path}")
            return

    # 使用 iconutil 创建 icns
    try:
        run_command(["iconutil", "-c", "icns", str(iconset_dir)], cwd=PROJECT_ROOT / "scripts")
        print(f"  已创建: {icns_path}")
    except Exception:
        print("    跳过 icns 生成（iconutil 失败）")

    # 清理临时文件
    if iconset_dir.exists():
        shutil.rmtree(iconset_dir)
    if svg_path.exists():
        svg_path.unlink()


def build_app() -> None:
    """使用 py2app 构建 .app 包。"""
    print("构建 macOS 应用...")

    # 确保安装了 py2app
    try:
        import py2app  # noqa: F401
    except ImportError:
        print("  安装 py2app...")
        run_command(["uv", "pip", "install", "py2app"], cwd=PROJECT_ROOT)

    # 构建
    run_command(
        ["uv", "run", "python", "setup.py", "py2app", "--no-strip"],
        cwd=PROJECT_ROOT,
    )


def create_launcher_script() -> None:
    """创建启动脚本（不使用 py2app 的替代方案）。"""
    app_dir = DIST_DIR / f"{APP_NAME}.app"
    contents_dir = app_dir / "Contents"
    macos_dir = contents_dir / "MacOS"
    resources_dir = contents_dir / "Resources"

    # 创建目录结构
    for d in [macos_dir, resources_dir]:
        d.mkdir(parents=True, exist_ok=True)

    # 创建 Info.plist
    plist_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>{APP_NAME}</string>
    <key>CFBundleDisplayName</key>
    <string>MCPX Desktop</string>
    <key>CFBundleIdentifier</key>
    <string>com.mcpx.desktop</string>
    <key>CFBundleVersion</key>
    <string>0.5.0</string>
    <key>CFBundleShortVersionString</key>
    <string>0.5.0</string>
    <key>CFBundleExecutable</key>
    <string>MCPX</string>
    <key>CFBundleIconFile</key>
    <string>MCPX.icns</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>LSMinimumSystemVersion</key>
    <string>10.15</string>
    <key>CFBundleDocumentTypes</key>
    <array>
        <dict>
            <key>CFBundleTypeName</key>
            <string>JSON Configuration</string>
            <key>CFBundleTypeExtensions</key>
            <array>
                <string>json</string>
            </array>
            <key>CFBundleTypeRole</key>
            <string>Editor</string>
        </dict>
    </array>
</dict>
</plist>'''
    (contents_dir / "Info.plist").write_text(plist_content)

    # 创建启动脚本
    launcher_script = '''#!/bin/bash
# MCPX Desktop Launcher

# 获取应用包的路径
APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
RESOURCES_DIR="$APP_DIR/Resources"

# 配置文件路径（优先使用用户目录，其次使用 Resources）
CONFIG_FILE="$HOME/.config/mcpx/config.json"
if [ ! -f "$CONFIG_FILE" ]; then
    # 自动创建配置目录和示例配置
    mkdir -p "$HOME/.config/mcpx"
    if [ -f "$RESOURCES_DIR/config.example.json" ]; then
        cp "$RESOURCES_DIR/config.example.json" "$CONFIG_FILE"
    fi
fi

# 如果配置文件仍不存在，使用 Resources 中的示例
if [ ! -f "$CONFIG_FILE" ]; then
    CONFIG_FILE="$RESOURCES_DIR/config.example.json"
fi

# 检测命令是否可用的函数
has_command() {
    command -v "$1" &> /dev/null
}

# 运行 MCPX
run_mcpx() {
    # 优先使用 uvx（uv 的全局命令）
    if has_command uvx; then
        exec uvx mcpx-toolkit --gui --desktop "$CONFIG_FILE"
    fi

    # 尝试使用 pip 安装的版本
    if has_command mcpx-toolkit; then
        exec mcpx-toolkit --gui --desktop "$CONFIG_FILE"
    fi

    # 尝试使用 pipx 安装的版本
    if [ -x "$HOME/.local/bin/mcpx-toolkit" ]; then
        exec "$HOME/.local/bin/mcpx-toolkit" --gui --desktop "$CONFIG_FILE"
    fi

    # 回退到直接运行 Python 模块
    if has_command python3; then
        exec python3 -m mcpx --gui --desktop "$CONFIG_FILE"
    fi

    # 都失败了，显示错误
    osascript -e "display alert \\"MCPX 启动失败\\" message \\"请先安装 MCPX：\\n\\nuvx mcpx-toolkit\\n\\n或\\n\\npip install mcpx-toolkit[gui]\\""
    exit 1
}

run_mcpx
'''
    launcher_path = macos_dir / APP_NAME
    launcher_path.write_text(launcher_script)
    launcher_path.chmod(0o755)

    # 复制资源文件
    example_config = PROJECT_ROOT / "config.example.json"
    if example_config.exists():
        shutil.copy(example_config, resources_dir / "config.example.json")

    # 复制图标（如果存在）
    icns_path = PROJECT_ROOT / "scripts" / "MCPX.icns"
    if icns_path.exists():
        shutil.copy(icns_path, resources_dir / "MCPX.icns")

    print(f"  已创建: {app_dir}")


def install_to_applications() -> None:
    """安装到 /Applications 目录。"""
    app_src = DIST_DIR / f"{APP_NAME}.app"
    app_dst = Path("/Applications") / f"{APP_NAME}.app"

    if not app_src.exists():
        print(f"错误: {app_src} 不存在")
        sys.exit(1)

    # 删除旧版本
    if app_dst.exists():
        print(f"  删除旧版本: {app_dst}")
        shutil.rmtree(app_dst)

    # 复制新版本
    print(f"  安装到: {app_dst}")
    shutil.copytree(app_src, app_dst)
    print(f"  ✓ 安装完成！")


def main() -> None:
    """主函数。"""
    print("=" * 60)
    print("MCPX macOS 桌面应用打包脚本")
    print("=" * 60)
    print()

    # 检查是否在 macOS 上运行
    if sys.platform != "darwin":
        print("错误: 此脚本仅支持 macOS")
        sys.exit(1)

    # 清理
    clean()

    # 创建图标
    create_icon()

    # 使用简单的启动脚本方案（避免 py2app 的复杂性）
    print()
    print("创建应用包...")
    create_launcher_script()

    # 询问是否安装
    print()
    response = input("是否安装到 /Applications? [y/N] ").strip().lower()
    if response == "y":
        install_to_applications()

    print()
    print("=" * 60)
    print("打包完成！")
    print()
    print(f"应用位置: {DIST_DIR / f'{APP_NAME}.app'}")
    print()
    print("首次使用说明：")
    print("1. 确保已安装依赖: uv pip install pywebview")
    print("2. 创建配置文件: ~/.config/mcpx/config.json")
    print("3. 双击 MCPX.app 启动")
    print("=" * 60)


if __name__ == "__main__":
    main()
