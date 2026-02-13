# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for MCPX Desktop App."""

import site
import sys
from pathlib import Path

# 项目根目录
project_root = Path(SPECPATH)

# 动态查找 site-packages 路径
site_packages = site.getsitepackages()[0]
if not Path(site_packages).exists():
    site_packages = site.getusersitepackages()

print(f"Using site-packages: {site_packages}")

# 收集所有依赖
block_cipher = None

a = Analysis(
    ['src/mcpx/desktop_app.py'],
    pathex=[str(project_root)],
    binaries=[],
    datas=[
        # 包含前端静态文件
        ('src/mcpx/web/static', 'web/static'),
        # 包含 package metadata（解决 PackageNotFoundError）
        # 使用 glob 匹配版本号
        (f'{site_packages}/fastmcp*.dist-info', '.'),
        (f'{site_packages}/mcp*.dist-info', '.'),
    ],
    hiddenimports=[
        # MCPX 核心模块
        'mcpx',
        'mcpx.__main__',
        'mcpx.config',
        'mcpx.config_manager',
        'mcpx.server',
        'mcpx.pool',
        'mcpx.description',
        'mcpx.errors',
        'mcpx.compression',
        'mcpx.schema_ts',
        'mcpx.content',
        'mcpx.health',
        'mcpx.port_utils',
        'mcpx.web',
        'mcpx.web.api',
        # FastMCP 和 MCP
        'fastmcp',
        'fastmcp.server',
        'fastmcp.tools',
        'fastmcp.resources',
        'mcp',
        'mcp.types',
        'mcp.client',
        'mcp.server',
        # Starlette/Uvicorn
        'starlette',
        'starlette.applications',
        'starlette.routing',
        'starlette.middleware',
        'starlette.middleware.cors',
        'starlette.requests',
        'starlette.responses',
        'uvicorn',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.websockets',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        # Pydantic
        'pydantic',
        'pydantic_core',
        # pywebview
        'webview',
        'webview.platforms',
        'webview.platforms.cocoa',
        # 其他
        'httpx',
        'httpcore',
        'anyio',
        'anyio._backends',
        'anyio._backends._asyncio',
        'sniffio',
        'toons',
        'json_schema_to_typescript',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'numpy',
        'pandas',
        'PIL',
        'cv2',
        'scipy',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='MCPX',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # 不显示控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # 可以添加图标: 'assets/icon.icns'
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='MCPX',
)

# macOS App Bundle
app = BUNDLE(
    coll,
    name='MCPX.app',
    icon=None,  # 可以添加图标: 'assets/icon.icns'
    bundle_identifier='com.mcpx.dashboard',
    info_plist={
        'CFBundleName': 'MCPX',
        'CFBundleDisplayName': 'MCPX Dashboard',
        'CFBundleVersion': '0.6.0',
        'CFBundleShortVersionString': '0.6.0',
        'CFBundleIdentifier': 'com.mcpx.dashboard',
        'NSHighResolutionCapable': True,
        'LSMinimumSystemVersion': '10.15',
        'NSPrincipalClass': 'NSApplication',
        'NSAppleScriptEnabled': False,
    },
)
