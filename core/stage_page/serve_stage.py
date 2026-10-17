#!/usr/bin/env python3
"""Serve this folder to the tablet: the QLC+ Swiss Knife Stage Monitor page.

    python3 serve_stage.py            (Windows: py serve_stage.py)
    python3 serve_stage.py 8090       another port

Then open http://<this computer's address>:<port>/ on the tablet.  QLC+ must
run with web access (qlcplus -w); the page talks to it directly on port 9999.
Standard library only.  Ctrl+C stops it.
"""
import os
import socket
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

DEFAULT_PORT = 8080
HERE = os.path.dirname(os.path.abspath(__file__))


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=HERE, **k)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


def guess_address():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))     # sends nothing
            return s.getsockname()[0]
    except OSError:
        return "<this computer's address>"


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PORT
    srv = ThreadingHTTPServer(("0.0.0.0", port), Handler)  # nosec B104 — the tablet is on the LAN
    print(f"Stage Monitor: http://{guess_address()}:{port}/   (Ctrl+C to stop)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()


if __name__ == "__main__":
    main()
