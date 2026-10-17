#!/usr/bin/env python3
"""Serve this folder to the tablet: the page of the QLC+ Swiss Knife — Stage Monitor.

    python3 serve_stage.py            (Windows: py serve_stage.py)
    python3 serve_stage.py 8090       another port

At the gig this and QLC+ are all you need: QLC+ started with web access
(qlcplus -w), and this script in the exported folder.  Swiss Knife can stay
closed.  The script prints the addresses to open on the tablet, the one of the
computer's own Wi-Fi (Internet Sharing, a hotspot) first.  Open it with
http://, not https://.  Standard library only.  Ctrl+C stops it.
"""
import ipaddress
import os
import platform
import re
import socket
import subprocess  # nosec B404 — fixed commands, no shell, for the address list
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

DEFAULT_PORT = 8080
HERE = os.path.dirname(os.path.abspath(__file__))
HOTSPOT = ("192.168.2.", "10.42.0.", "192.168.137.")   # macOS Internet Sharing, Linux hotspot, Windows hotspot
_IPV4 = re.compile(r"(?<![\d.])(\d{1,3}(?:\.\d{1,3}){3})(?![\d.])")
_warned = set()
_lock = threading.Lock()


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


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=HERE, **k)

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
                host = self.server.server_address
                print(f"  ! {ip} asked for https://. Type http://{best_address()}:{host[1]}/ "
                      "on that device (with http, not https).", flush=True)
            self.close_connection = True
            return
        super().handle_one_request()

    def log_message(self, fmt, *args):
        if args and str(args[0]).startswith("GET / "):
            print(f"  {self.client_address[0]} opened the page", flush=True)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


def best_address():
    ips = addresses()
    return ips[0] if ips else "<this computer's address>"


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PORT
    srv = ThreadingHTTPServer(("0.0.0.0", port), Handler)  # nosec B104 — the tablet is on the LAN
    srv.daemon_threads = True
    ips = addresses()
    print("Stage Monitor is served. Open on the tablet (with http://):")
    for i, ip in enumerate(ips or ["<this computer's address>"]):
        note = "   ← this computer's own Wi-Fi" if ip.startswith(HOTSPOT) else ""
        print(f"  http://{ip}:{port}/{note}")
    print("QLC+ must run with web access (qlcplus -w). Ctrl+C to stop.", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()


if __name__ == "__main__":
    main()
