#!/usr/bin/env python3
"""Pack the PyInstaller output (dist/) into the release file for this OS.

    python packaging/make_archive.py                       # → release/QLC-Swiss-Knife-<ver>-<os>-<arch>.<ext>
    python packaging/make_archive.py --app stage-monitor   # → release/QLC-Stage-Monitor-<ver>-<os>-<arch>.<ext>

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


# The two apps of the repository: Swiss Knife, and QLC+ Stage Monitor (its companion, 3.18.0).
APPS = {
    "swiss-knife": {"asset": "QLC-Swiss-Knife", "name": "QLC Swiss Knife", "linux": "QLC-Swiss-Knife",
                    "iss": "installer.iss"},
    "stage-monitor": {"asset": "QLC-Stage-Monitor", "name": "QLC Stage Monitor", "linux": "QLC-Stage-Monitor",
                      "iss": "stagemonitor.iss"},
}


CURRENT = "swiss-knife"          # the app main() packs


def asset_name(ext: str, os_name: str = None, arch: str = None, version: str = VERSION,
               app: str = None) -> str:
    o, a = (os_name, arch) if os_name else platform_key()
    return f"{APPS[app or CURRENT]['asset']}-{version}-{o}-{a}.{ext}"


def hdiutil_create(volname: str, src: str, dmg: str, tries: int = 5) -> None:
    """hdiutil create, tried again when the disk is busy.  On GitHub's macOS runners
    "hdiutil: create failed - Resource busy" comes and goes (a helper still holds the
    image of the build before): release v3.18.1 lost its Apple Silicon files to it."""
    import time
    cmd = ["hdiutil", "create", "-volname", volname, "-srcfolder", src, "-ov", "-format", "UDZO", dmg]
    for n in range(1, tries + 1):
        if subprocess.call(cmd) == 0:
            return
        if n == tries:
            raise subprocess.CalledProcessError(1, cmd)
        print(f"hdiutil busy, trying again in {5 * n} s ({n}/{tries - 1})", flush=True)
        subprocess.call(["hdiutil", "info"], stdout=subprocess.DEVNULL)   # lets diskimages-helper settle
        time.sleep(5 * n)


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    key = argv[argv.index("--app") + 1] if "--app" in argv else "swiss-knife"
    if key not in APPS:
        print(f"--app is one of: {', '.join(APPS)}")
        return 2
    global CURRENT
    CURRENT = key
    spec = APPS[key]
    NAME = spec["name"]
    dist, out = os.path.join(ROOT, "dist"), os.path.join(ROOT, "release")
    os.makedirs(out, exist_ok=True)
    system = platform.system()
    if system == "Darwin":
        app = os.path.join(dist, f"{NAME}.app")
        # The updater's archive is a .tar.gz, not a .zip: Python's zipfile writes the .app's
        # symlinks (Frameworks/, Resources/) as plain text files and the updated app then
        # cannot start (v2.8.3 → v2.8.4 try on the Mac).  tarfile keeps links and modes.
        with tarfile.open(os.path.join(out, asset_name("tar.gz")), "w:gz") as t:
            t.add(app, arcname=f"{NAME}.app")
        stage = os.path.join(out, "dmg-stage")
        shutil.rmtree(stage, ignore_errors=True)
        os.makedirs(stage)
        subprocess.check_call(["ditto", app, os.path.join(stage, f"{NAME}.app")])
        os.symlink("/Applications", os.path.join(stage, "Applications"))
        hdiutil_create(NAME, stage, os.path.join(out, asset_name("dmg")))
        shutil.rmtree(stage)
    elif system == "Windows":
        folder = os.path.join(dist, NAME)
        z = os.path.join(out, asset_name("zip"))
        with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
            for d, _dirs, files in os.walk(folder):
                for f in files:
                    p = os.path.join(d, f)
                    zf.write(p, os.path.join(NAME, os.path.relpath(p, folder)))
        iscc = shutil.which("ISCC") or next((c for c in (
            r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe", r"C:\Program Files\Inno Setup 6\ISCC.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe")) if os.path.exists(c)), None)
        if iscc:                                  # the installer (per-user, with an uninstaller)
            subprocess.check_call([iscc, f"/DAppVersion={VERSION}",
                                   os.path.join(ROOT, "packaging", "windows", spec["iss"])])
        else:
            print("Inno Setup (ISCC) not found — no installer built.")
    else:
        folder = os.path.join(dist, spec["linux"])
        with tarfile.open(os.path.join(out, asset_name("tar.gz")), "w:gz") as t:
            t.add(folder, arcname=spec["linux"])
    for f in sorted(os.listdir(out)):
        print(f, os.path.getsize(os.path.join(out, f)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
