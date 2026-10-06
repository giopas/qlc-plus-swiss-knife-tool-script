#!/usr/bin/env python3
"""Pack the PyInstaller output (dist/) into the release file for this OS.

    python packaging/make_archive.py            # → release/QLC-Swiss-Knife-<ver>-<os>-<arch>.<ext>

Names are what core/update.py looks for.  macOS also gets a .dmg for the first
install (the updater uses the .zip).  Run it after:  pyinstaller packaging/swissknife.spec
"""
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import zipfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
from core.update import platform_key  # noqa: E402
from core.workspace import VERSION     # noqa: E402


def asset_name(ext: str, os_name: str = None, arch: str = None, version: str = VERSION) -> str:
    o, a = (os_name, arch) if os_name else platform_key()
    return f"QLC-Swiss-Knife-{version}-{o}-{a}.{ext}"


def main() -> int:
    dist, out = os.path.join(ROOT, "dist"), os.path.join(ROOT, "release")
    os.makedirs(out, exist_ok=True)
    system = platform.system()
    if system == "Darwin":
        app = os.path.join(dist, "QLC Swiss Knife.app")
        z = os.path.join(out, asset_name("zip"))
        subprocess.check_call(["ditto", "-c", "-k", "--keepParent", app, z])      # keeps symlinks and modes
        stage = os.path.join(out, "dmg-stage")
        shutil.rmtree(stage, ignore_errors=True)
        os.makedirs(stage)
        subprocess.check_call(["ditto", app, os.path.join(stage, "QLC Swiss Knife.app")])
        os.symlink("/Applications", os.path.join(stage, "Applications"))
        subprocess.check_call(["hdiutil", "create", "-volname", "QLC Swiss Knife", "-srcfolder", stage,
                               "-ov", "-format", "UDZO", os.path.join(out, asset_name("dmg"))])
        shutil.rmtree(stage)
    elif system == "Windows":
        folder = os.path.join(dist, "QLC Swiss Knife")
        z = os.path.join(out, asset_name("zip"))
        with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
            for d, _dirs, files in os.walk(folder):
                for f in files:
                    p = os.path.join(d, f)
                    zf.write(p, os.path.join("QLC Swiss Knife", os.path.relpath(p, folder)))
    else:
        folder = os.path.join(dist, "QLC-Swiss-Knife")
        with tarfile.open(os.path.join(out, asset_name("tar.gz")), "w:gz") as t:
            t.add(folder, arcname="QLC-Swiss-Knife")
    for f in sorted(os.listdir(out)):
        print(f, os.path.getsize(os.path.join(out, f)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
