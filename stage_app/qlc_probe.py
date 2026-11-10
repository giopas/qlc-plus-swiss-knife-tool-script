"""stage_app/qlc_probe.py: is QLC+ ready for the Stage Monitor page?

One look at QLC+ on this computer, in the same way the page talks to it
(``docs/STAGE_MONITOR_PROTOCOL.md``):

* ``off``: nothing listens on the web port and no QLC+ is running;
* ``no_web``: QLC+ runs, but without web access (start it with ``-w``);
* ``not_qlc``: something else answers on that port;
* ``other_show``: QLC+ answers, but some cue lists of the page are not in the
  show it has open (another show, or an older version of it);
* ``ready``: QLC+ answers and has every cue list of the page.

Only ``getWidgetStatus`` is sent: it reads, it never moves a cue list.
Standard library only (a few lines of web socket client).
"""

from __future__ import annotations

import base64
import os
import platform
import socket
import struct
import subprocess  # nosec B404 — fixed commands, no shell, to see whether QLC+ runs
import time
from typing import Iterable, List, Optional, Tuple

WS_PATH = "/qlcplusWS"
API = "QLC+API|getWidgetStatus|"


class _WS:
    """The smallest web socket client that QLC+ needs: text frames, masked."""

    def __init__(self, host: str, port: int, timeout: float):
        self.sock = socket.create_connection((host, port), timeout=timeout)
        self.sock.settimeout(timeout)
        self.buf = b""
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        req = (f"GET {WS_PATH} HTTP/1.1\r\nHost: {host}:{port}\r\nUpgrade: websocket\r\n"
               f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n")
        self.sock.sendall(req.encode("ascii"))
        while b"\r\n\r\n" not in self.buf:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise ConnectionError("closed during the handshake")
            self.buf += chunk
            if len(self.buf) > 65536:
                raise ConnectionError("no web socket")
        head, self.buf = self.buf.split(b"\r\n\r\n", 1)
        status = head.split(b"\r\n", 1)[0].split()
        if len(status) < 2 or status[1] != b"101":
            raise ConnectionError("no web socket")

    def send(self, text: str) -> None:
        data = text.encode("utf-8")
        mask = os.urandom(4)
        n = len(data)
        head = bytearray([0x81])
        if n < 126:
            head.append(0x80 | n)
        elif n < 65536:
            head.append(0x80 | 126)
            head += struct.pack(">H", n)
        else:
            head.append(0x80 | 127)
            head += struct.pack(">Q", n)
        self.sock.sendall(bytes(head) + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))

    def _need(self, n: int) -> bytes:
        while len(self.buf) < n:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise ConnectionError("closed")
            self.buf += chunk
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def recv(self) -> Optional[str]:
        """The next text message (``None`` when QLC+ closes)."""
        parts = b""
        while True:
            b0, b1 = self._need(2)
            op, n = b0 & 0x0F, b1 & 0x7F
            if n == 126:
                n = struct.unpack(">H", self._need(2))[0]
            elif n == 127:
                n = struct.unpack(">Q", self._need(8))[0]
            mask = self._need(4) if b1 & 0x80 else b""
            data = self._need(n)
            if mask:
                data = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
            if op == 0x8:
                return None
            if op in (0x9, 0xA):          # ping, pong: not a message
                continue
            parts += data
            if b0 & 0x80:
                return parts.decode("utf-8", errors="replace")

    def close(self) -> None:
        try:
            self.sock.sendall(bytes([0x88, 0x80]) + os.urandom(4))
        except OSError:
            pass
        try:
            self.sock.close()
        except OSError:
            pass


def qlc_running() -> Optional[bool]:
    """Whether a QLC+ program runs on this computer (``None``: cannot tell)."""
    system = platform.system()
    try:
        if system == "Windows":
            out = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True,  # nosec B603 B607
                                 timeout=4, check=False).stdout or ""
        else:
            out = subprocess.run(["ps", "-A", "-o", "comm="], capture_output=True, text=True,  # nosec B603 B607
                                 timeout=4, check=False).stdout or ""
    except (OSError, subprocess.SubprocessError):
        return None
    for line in out.lower().splitlines():
        name = line.strip().strip('"').split('","')[0]
        base = name.replace("\\", "/").rsplit("/", 1)[-1]
        if base.startswith("qlcplus"):
            return True
    return False


def _status(ws: _WS, wid: str, deadline: float) -> Tuple[bool, str]:
    """(found, state) for one widget; QLC+ answers ``getWidgetStatus|`` alone when the ID is unknown."""
    ws.send(API + wid)
    while time.monotonic() < deadline:
        msg = ws.recv()
        if msg is None:
            raise ConnectionError("closed")
        if not msg.startswith(API):
            continue                         # a push from QLC+ (CUE, FUNCTION…)
        rest = msg[len(API):].split("|")
        if rest == [""]:
            return False, ""
        if rest[0] == wid:
            return True, (rest[1] if len(rest) > 1 else "")
    raise TimeoutError


def probe(port: int = 9999, ids: Iterable[str] = (), host: str = "127.0.0.1",
          timeout: float = 1.5, running=qlc_running) -> dict:
    """Look at QLC+ once.  Returns ``{state, port, found, missing, playing}``
    (see the module text for the states)."""
    ids = [str(i) for i in ids]
    out = {"state": "off", "port": port, "found": [], "missing": [], "playing": []}
    try:
        ws = _WS(host, port, timeout)
    except ConnectionRefusedError:
        out["state"] = "no_web" if running() else "off"
        return out
    except (socket.timeout, TimeoutError):
        out["state"] = "no_web" if running() else "off"
        return out
    except (ConnectionError, OSError):
        out["state"] = "not_qlc"
        return out
    deadline = time.monotonic() + max(timeout, 0.5) * 2
    found: List[str] = []
    missing: List[str] = []
    playing: List[str] = []
    try:
        for wid in ids:
            ok, state = _status(ws, wid, deadline)
            (found if ok else missing).append(wid)
            if ok and state == "PLAY":
                playing.append(wid)
    except (TimeoutError, socket.timeout):
        out["state"] = "not_qlc" if not found and not missing else "other_show"
        missing += [w for w in ids if w not in found and w not in missing]
    except (ConnectionError, OSError):
        out["state"] = "not_qlc"
        ws.close()
        return out
    else:
        out["state"] = "other_show" if missing else "ready"
    finally:
        ws.close()
    out.update(found=found, missing=missing, playing=playing)
    return out
