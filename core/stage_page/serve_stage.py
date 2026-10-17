#!/usr/bin/env python3
"""Serve this folder to the tablet: the page of the QLC+ Swiss Knife — Stage Monitor.

Double-click "Start Stage Monitor" in this folder, or:

    python3 serve_stage.py            (Windows: py serve_stage.py)
    python3 serve_stage.py 8090       another port
    python3 serve_stage.py --dir DIR  serve another exported folder

At the gig this and QLC+ are all you need: QLC+ started with web access
(qlcplus -w), and this server.  Swiss Knife can stay closed.  It prints the
address to open on the tablet (the computer's own Wi-Fi first) and says
whether QLC+ can be reached.  Open the address with http://, not https://.
Standard library only.  Close the window (or Ctrl+C) to stop.
"""
import ipaddress
import os
import platform
import re
import socket
import subprocess  # nosec B404 — fixed commands, no shell, for the address list
import sys
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

DEFAULT_PORT = 8080
QLC_PORT = 9999                       # QLC+ web access (set at export)
SHOW = ""                             # the show the page was exported from (set at export)
HOTSPOT = ("192.168.2.", "10.42.0.", "192.168.137.")   # macOS Internet Sharing, Linux hotspot, Windows hotspot
_IPV4 = re.compile(r"(?<![\d.])(\d{1,3}(?:\.\d{1,3}){3})(?![\d.])")
_warned = set()
_lock = threading.Lock()
FOLDER = os.path.dirname(os.path.abspath(__file__))


def _usable(ip):
    try:
        a = ipaddress.IPv4Address(ip)
    except ValueError:
        return False
    return not (a.is_loopback or a.is_unspecified or a.is_multicast or a.is_link_local or ip.endswith(".255"))


def addresses():
    """This computer's IPv4 addresses, the hotspot ones first."""
    system = platform.system()
    cmd = {"Darwin": ["ifconfig"], "Linux": ["ip", "-4", "addr"], "Windows": ["ipconfig"]}.get(system, ["ifconfig"])
    found = []
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=3, check=False).stdout or ""  # nosec B603
    except (OSError, subprocess.SubprocessError):
        out = ""
    for line in out.splitlines():
        low = line.lower()
        if system == "Windows":
            if "ipv4" not in low:
                continue
        else:
            if "inet " not in low:
                continue
            line = line.split("inet ", 1)[1].split()[0].split("/")[0]
        for ip in _IPV4.findall(line):
            if _usable(ip) and ip not in found:
                found.append(ip)
                break
    if not found:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("10.255.255.255", 1))     # sends nothing
                if _usable(s.getsockname()[0]):
                    found.append(s.getsockname()[0])
        except OSError:
            pass
    return sorted(found, key=lambda ip: 0 if ip.startswith(HOTSPOT) else 1)


def best_address():
    ips = addresses()
    return ips[0] if ips else "<this computer's address>"


def qlc_reachable(port=None):
    """True when QLC+ web access answers on this computer."""
    try:
        with socket.create_connection(("127.0.0.1", port or QLC_PORT), timeout=1):
            return True
    except OSError:
        return False


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=FOLDER, **k)

    def handle_one_request(self):
        # A browser that asks for https:// sends a TLS handshake (first byte 0x16), which a plain
        # http server cannot answer: say what to do instead of logging unreadable bytes.
        try:
            first = self.rfile.peek(1)[:1]
        except (OSError, ValueError):
            first = b""
        if first == b"\x16":
            ip = self.client_address[0]
            with _lock:
                new = ip not in _warned
                _warned.add(ip)
            if new:
                port = self.server.server_address[1]
                print(f"  ! {ip} asked for https://. Type http://{best_address()}:{port}/ "
                      "on that device (with http, not https).", flush=True)
            self.close_connection = True
            return
        super().handle_one_request()

    def log_message(self, fmt, *args):
        if args and str(args[0]).startswith("GET / "):
            print(f"  {time.strftime('%H:%M:%S')}  {self.client_address[0]} opened the page", flush=True)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


def watch_qlc(stop):
    """Say when QLC+ web access comes and goes."""
    last = None
    while not stop.is_set():
        up = qlc_reachable()
        if up != last:
            if up:
                print(f"  {time.strftime('%H:%M:%S')}  QLC+ web access: OK (port {QLC_PORT})", flush=True)
            else:
                print(f"  {time.strftime('%H:%M:%S')}  QLC+ web access: not reachable. Start QLC+ with -w, for example:", flush=True)
                print(f"       {qlc_command()}", flush=True)
            last = up
        stop.wait(3)


def qlc_command():
    show = f' -o "{SHOW}"' if SHOW else ""
    system = platform.system()
    if system == "Darwin":
        base = "/Applications/QLC+.app/Contents/MacOS"
        for name in ("qlcplus5", "qlcplus-qml", "qlcplus"):
            if os.path.exists(os.path.join(base, name)):
                return f'"{base}/{name}" -w{show}'
        return f'"{base}/qlcplus" -w{show}'
    if system == "Windows":
        return f'"C:\\QLC+\\qlcplus.exe" -w{show}'
    return f"qlcplus -w{show}"


def parse_args(argv):
    port, folder = DEFAULT_PORT, FOLDER
    it = iter(argv)
    for a in it:
        if a == "--dir":
            folder = os.path.abspath(os.path.expanduser(next(it, folder)))
        elif a.isdigit():
            port = int(a)
    return port, folder


def main(argv=None):
    global FOLDER
    port, FOLDER = parse_args(sys.argv[1:] if argv is None else argv)
    if not os.path.isfile(os.path.join(FOLDER, "index.html")):
        print(f"No index.html in {FOLDER}: export the page from Swiss Knife first.", flush=True)
        return 1
    try:
        srv = ThreadingHTTPServer(("0.0.0.0", port), Handler)  # nosec B104 — the tablet is on the LAN
    except OSError as e:
        print(f"Port {port} is busy ({e.strerror or e}). Is the Stage Monitor already running in another window?", flush=True)
        return 1
    srv.daemon_threads = True
    ips = addresses()
    print("QLC+ Swiss Knife — Stage Monitor")
    print(f"Serving {FOLDER}")
    print("Open on the tablet (with http://):")
    for ip in ips or ["<this computer's address>"]:
        note = "   ← this computer's own Wi-Fi" if ip.startswith(HOTSPOT) else ""
        print(f"  http://{ip}:{port}/{note}")
    if not any(ip.startswith(HOTSPOT) for ip in ips):
        print("  (no hotspot address: the tablet must be on the same network as this computer)")
    print("Close this window (or press Ctrl+C) to stop.", flush=True)
    stop = threading.Event()
    threading.Thread(target=watch_qlc, args=(stop,), daemon=True).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        srv.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
