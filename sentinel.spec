# -*- mode: python ; coding: utf-8 -*-
"""
Port Sentinel — PyInstaller Spec File

Build with:  pyinstaller sentinel.spec
Output:      dist/PortSentinel.exe
"""

import os
import sys
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

block_cipher = None

# On Windows, skip Unix/BSD-only Scapy subtrees so PyInstaller does not import
# scapy.arch.linux (needs fcntl) and spam warnings.
def _scapy_collect_filter(name: str) -> bool:
    if sys.platform != 'win32':
        return True
    return not (
        name.startswith('scapy.arch.linux')
        or name.startswith('scapy.arch.bpf')
        or name.startswith('scapy.arch.solaris')
        or name == 'scapy.arch.unix'
    )

# Collect all submodules for complex packages
hiddenimports = []
hiddenimports += collect_submodules('uvicorn')
hiddenimports += collect_submodules('fastapi')
hiddenimports += collect_submodules('starlette')
hiddenimports += collect_submodules('socketio')
hiddenimports += collect_submodules('engineio')
hiddenimports += collect_submodules('scapy', filter=_scapy_collect_filter)
hiddenimports += collect_submodules('psutil')
hiddenimports += collect_submodules('msgpack')
hiddenimports += collect_submodules('dotenv')
hiddenimports += collect_submodules('anyio')
hiddenimports += collect_submodules('httptools')
hiddenimports += collect_submodules('h11')

# Add explicit hidden imports that auto-detection misses
hiddenimports += [
    'multiprocessing',
    'multiprocessing.shared_memory',
    'multiprocessing.synchronize',
    'multiprocessing.resource_tracker',
    'multiprocessing.popen_spawn_win32',
    'multiprocessing.spawn',
    'multiprocessing.forkserver',
    'multiprocessing.reduction',
    'multiprocessing.queues',
    'multiprocessing.managers',
    'sqlite3',
    'aiosqlite',
    'asyncio',
    'logging.handlers',
    'concurrent.futures',
    'email.mime.text',
    'json',
    'struct',
    'socket',
    'ctypes',
    'ctypes.wintypes',
    'backend',
    'backend.main',
    'backend.core',
    'backend.core.sniffer',
    'backend.core.metrics',
    'backend.core.db',
    'backend.core.policies',
    'backend.core.watchdog',
    'backend.core.exceptions',
    'backend.core.threat_intel',
    'backend.os_adapters',
    'backend.os_adapters.win32_bridge',
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespan',
    'uvicorn.lifespan.on',
    'uvicorn.lifespan.off',
]

# Collect data files for packages that need them
datas = []
datas += collect_data_files('uvicorn')
datas += collect_data_files('starlette')

# Add our project data files
# Frontend dist (built React app)
if os.path.isdir('frontend/dist'):
    datas.append(('frontend/dist', 'frontend_dist'))

# Backend data directory (for SQLite schema etc.)
if os.path.isdir('backend/data'):
    datas.append(('backend/data', 'backend/data'))

# .env file
if os.path.isfile('.env'):
    datas.append(('.env', '.'))

a = Analysis(
    ['launcher.py'],
    pathex=['.'],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter', '_tkinter',
        'matplotlib', 'numpy',
        'PIL', 'Pillow',
        'scipy', 'pandas',
        'test', 'tests',
        'unittest',
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='PortSentinel',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,       # Console mode so users can see logs
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    uac_admin=True,     # Request UAC elevation (needed for scapy/firewall)
)
