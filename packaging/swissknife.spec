# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for QLC+ Swiss Knife (v3.0.0).  One-folder build:
#
#     pip install pyinstaller flask pywebview
#     pyinstaller --noconfirm packaging/swissknife.spec
#
# → dist/QLC Swiss Knife/ (Windows), dist/QLC Swiss Knife.app (macOS),
#   dist/QLC-Swiss-Knife/ (Linux).  Run it with --smoke to check the bundle.
import os
import sys

ROOT = os.path.abspath(os.path.join(SPECPATH, '..'))

datas = [
    (os.path.join(ROOT, 'templates'), 'templates'),
    (os.path.join(ROOT, 'static'), 'static'),
    (os.path.join(ROOT, 'core', 'looks'), os.path.join('core', 'looks')),
    (os.path.join(ROOT, 'core', 'quick_start', 'profiles'), os.path.join('core', 'quick_start', 'profiles')),
]
# data files inside other core packages, if any
for sub in ('doctor', 'quick_start'):
    d = os.path.join(ROOT, 'core', sub)
    for f in os.listdir(d):
        if f.endswith(('.json', '.txt')):
            datas.append((os.path.join(d, f), os.path.join('core', sub)))

hidden = ['webview', 'routes', 'core', 'app']   # 'app': the MCP server imports it
for name in os.listdir(os.path.join(ROOT, 'routes')):
    if name.endswith('.py') and name != '__init__.py':
        hidden.append('routes.' + name[:-3])

a = Analysis(
    [os.path.join(ROOT, 'app.py')],
    pathex=[ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=hidden,
    excludes=['tkinter', 'pytest', 'tests'],
    noarchive=False,
)
pyz = PYZ(a.pure)

if sys.platform == 'win32':
    NAME = 'QLC Swiss Knife'
elif sys.platform == 'darwin':
    NAME = 'QLC Swiss Knife'
else:
    NAME = 'QLC-Swiss-Knife'

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name=NAME,
    console=(sys.platform != 'win32' and sys.platform != 'darwin'),
    upx=False,
    icon=(os.path.join(ROOT, 'packaging', 'icons', 'icon.ico') if sys.platform == 'win32' else None),
)
if sys.platform == 'win32':
    # Claude starts the MCP server and talks to it over stdin/stdout, which a
    # window-only exe does not have: a second, console exe in the same folder.
    exe_mcp = EXE(
        pyz, a.scripts, [],
        exclude_binaries=True,
        name='QLC Swiss Knife MCP',
        console=True,
        upx=False,
        icon=os.path.join(ROOT, 'packaging', 'icons', 'icon.ico'),
    )
    coll = COLLECT(exe, exe_mcp, a.binaries, a.datas, name=NAME, upx=False)
else:
    coll = COLLECT(exe, a.binaries, a.datas, name=NAME, upx=False)

if sys.platform == 'darwin':
    sys.path.insert(0, ROOT)
    from core.workspace import VERSION  # noqa: E402
    app = BUNDLE(
        coll,
        name='QLC Swiss Knife.app',
        icon=os.path.join(ROOT, 'packaging', 'icons', 'icon.icns'),
        bundle_identifier='io.github.giopas.qlc-swiss-knife',
        info_plist={
            'CFBundleShortVersionString': VERSION,
            'CFBundleVersion': VERSION,
            'NSHighResolutionCapable': True,
            'LSMinimumSystemVersion': '11.0',
        },
    )
