# Live QLC+ check (`tools/qlc_check.py`)

Doctor reads the XML. This tool checks how **QLC+ itself behaves** with a generated workspace: it opens the file in a real QLC+ with web access (`-w`), presses Virtual Console buttons over the web-socket API and reads the DMX output.

It found these bugs (23–24 Sep 2026) that no XML check could see:

| Bug | QLC+ | Seen as |
|---|---|---|
| An empty `<Level/>` in a one-line file makes the slider loader swallow the slider's end tag, so every later VC widget is dropped (fixed on our side by writing indented XML) | 5.2.2 | VC empty except the slider |
| A *Level* slider at 255 on the dimmers holds them at full (HTP) | all | BLACKOUT / PANIC RESET can't darken |
| A script never ends on its own, so its Toggle button stays on | 5.x up to spring 2026 | every second PANIC RESET press does nothing |
| Script start/stop commands are dropped if the script code ends before the next engine tick | 5.2.2 (fixed upstream Aug 2026, `ca8ffd41`) | PANIC RESET does nothing (works when QLC+ runs slower, e.g. from Terminal with `-d`) |
| RGB matrices in RGB mode ignore *DimmerControl*, so fixtures with a master dimmer stay dark | all | matrix buttons do nothing |
| Fixture definition not found → fixture loaded as a plain dimmer | all | colours / matrices dark |

## What it checks

1. **VC loaded** — every widget in the file (pages excluded) is present in the running QLC+.
2. **Buttons light up + PANIC RESET** — for every Toggle button with a function: press it and check at least one fixture lights up (except BLACKOUT); press PANIC RESET and compare every fixture channel with the *Reset: neutral state* scene; press it again and compare again. After the first PANIC RESET the check waits for the longest fade-out of the button's function (and everything it runs) before comparing, so looks with a slow fade-out are not reported as stuck.

Fixtures that aren't in the QLC+ library need their `.qxf` next to the workspace (Quick Start writes them there for exactly those fixtures): without it QLC+ loads them as plain dimmers and check 2 reports dark buttons.

## Run it

```bash
pip install websocket-client          # once, in the venv
# macOS: quit QLC+ first (the tool starts its own copy on port 9999)
python3 tools/qlc_check.py tests/corpus/QuickStart_club.qxw
python3 tools/qlc_check.py tests/corpus/QuickStart_multiuni.qxw
```

Options: `--qlc /path/to/binary` (default: `$QLCPLUS_BIN`, then `/Applications/QLC+.app/Contents/MacOS/qlcplus-qml`, then `PATH`), `--no-launch` (use a QLC+ you started with `-w`), `--offscreen` (Linux/CI, no window), `--settle 0.8` (seconds per press). Exit code 0 = pass.

As a test (skipped unless `QLCPLUS_BIN` is set):

```bash
QLCPLUS_BIN=/Applications/QLC+.app/Contents/MacOS/qlcplus-qml pytest tests/test_qlc_live.py -v
```

## Testing other QLC+ versions (Linux)

QLC+ builds headless from source (Ubuntu 24.04, Qt 6.4):

```bash
apt-get install qt6-base-dev qt6-declarative-dev qt6-3d-dev qt6-multimedia-dev \
  qt6-websockets-dev qt6-serialport-dev qt6-svg-dev qt6-5compat-dev qt6-tools-dev \
  'qml6-module-*' libxkbcommon-dev libusb-1.0-0-dev libasound2-dev libfftw3-dev \
  libsndfile1-dev libudev-dev cmake g++
git clone https://github.com/mcallegari/qlcplus && cd qlcplus
git checkout QLC+_5.2.2                          # or any tag / commit
sed -i 's/^add_subdirectory(plugins)/#&/' CMakeLists.txt   # plugins not needed
mkdir b && cd b && cmake .. -Dqmlui=ON && make -j2 qlcplus-qml   # drop -Dqmlui for QLC+ 4
```

Run the binary with `LD_LIBRARY_PATH=b/engine/src:b/webaccess/src:b/engine/audio/src` and `--offscreen`. Install **that version's** RGB scripts (`resources/rgbscripts/*.js` of the same tag) into the scripts folder — QLC+ 4 and 5 scripts differ (e.g. Plasma's default preset), and testing with the wrong set hid a dark Plasma button once. Fixture definitions come from an installed QLC+ (`apt-get install qlcplus` puts them in `/usr/share/qlcplus`). Checked so far: 4.12.7, 4.14.5, 5.2.1, 5.2.2, 5.3.0-git.

**Notes:** in QLC+ 5 the web "press" toggles (like a click); QLC+ 4 reacts to the press only. The `getChannelsValues` reply has 3 fields per channel in 4.12 and 4 fields in 4.14 / 5.x — the tool handles both.
