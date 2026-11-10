# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for QLC+ Stage Monitor, the companion app of QLC+ Swiss Knife.
#
#     pip install pyinstaller pywebview
#     pyinstaller --noconfirm packaging/stagemonitor.spec
#
# → dist/QLC Stage Monitor/ (Windows), dist/QLC Stage Monitor.app (macOS),
#   dist/QLC-Stage-Monitor/ (Linux).  Run it with --smoke to check the bundle.
#
# Only stage_app/ and the four core modules it may import go in (see
# stage_app/__init__.py); Flask and Swiss Knife's routes and pages stay out.
import os
import sys

ROOT = os.path.abspath(os.path.join(SPECPATH, '..'))

datas = [
    (os.path.join(ROOT, 'stage_app', 'ui'), os.path.join('stage_app', 'ui')),
    (os.path.join(ROOT, 'stage_app', 'i18n'), os.path.join('stage_app', 'i18n')),
    (os.path.join(ROOT, 'core', 'stage_page'), os.path.join('core', 'stage_page')),   # the template, for the smoke test
]

a = Analysis(
    [os.path.join(ROOT, 'qlc_stage_monitor.py')],
    pathex=[ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=['webview', 'stage_app', 'stage_app.app', 'stage_app.control', 'stage_app.folder',
                   'stage_app.qlc_probe', 'stage_app.settings', 'stage_app.setlist_pdf'],
    excludes=['tkinter', 'pytest', 'tests', 'flask', 'werkzeug', 'jinja2', 'routes', 'app'],
    noarchive=False,
)
pyz = PYZ(a.pure)

NAME = 'QLC-Stage-Monitor' if sys.platform.startswith('linux') else 'QLC Stage Monitor'

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name=NAME,
    console=(sys.platform != 'win32' and sys.platform != 'darwin'),
    upx=False,
    icon=(os.path.join(ROOT, 'packaging', 'icons', 'stage-monitor.ico') if sys.platform == 'win32' else None),
)
coll = COLLECT(exe, a.binaries, a.datas, name=NAME, upx=False)

if sys.platform == 'darwin':
    sys.path.insert(0, ROOT)
    from core.workspace import VERSION  # noqa: E402
    app = BUNDLE(
        coll,
        name='QLC Stage Monitor.app',
        icon=os.path.join(ROOT, 'packaging', 'icons', 'stage-monitor.icns'),
        bundle_identifier='io.github.giopas.qlc-stage-monitor',
        info_plist={
            'CFBundleDisplayName': 'QLC+ Stage Monitor',
            'CFBundleShortVersionString': VERSION,
            'CFBundleVersion': VERSION,
            'NSHighResolutionCapable': True,
            'LSMinimumSystemVersion': '11.0',
            'NSLocalNetworkUsageDescription': 'QLC+ Stage Monitor serves the Stage Monitor page to the tablets on your local network.',
        },
    )
