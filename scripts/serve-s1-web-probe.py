"""Serve only the two controlled-response QA assets, on IPv4 loopback."""

from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1] / "frontend_flutter"
ASSETS = {
    "/tool/local_web_transport_probe.html": (
        ROOT / "tool/local_web_transport_probe.html",
        "text/html; charset=utf-8",
    ),
    "/build/qa/local_web_transport_probe.js": (
        ROOT / "build/qa/local_web_transport_probe.js",
        "text/javascript; charset=utf-8",
    ),
}


class ProbeHandler(BaseHTTPRequestHandler):
    def log_message(self, _format: str, *args: object) -> None:
        # No request paths, query, headers, body or client diagnostics in logs.
        pass

    def _reply(self, *, head: bool = False) -> None:
        request = urlsplit(self.path)
        asset = ASSETS.get(request.path) if not request.query and not request.fragment else None
        status, body, content_type = 404, b"Not found", "text/plain; charset=utf-8"
        if asset is not None:
            try:
                body = asset[0].read_bytes()
            except OSError:
                status, body = 503, b"Compile the controlled probe first."
            else:
                status, content_type = 200, asset[1]
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'none'; script-src 'self' 'unsafe-inline'; "
            "style-src 'unsafe-inline'; connect-src 'none'; "
            "base-uri 'none'; frame-ancestors 'none'",
        )
        self.end_headers()
        if not head:
            self.wfile.write(body)

    def do_GET(self) -> None:
        self._reply()

    def do_HEAD(self) -> None:
        self._reply(head=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=3005)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("Choose an unused nonprivileged loopback port.")
    if any(not path.is_file() for path, _ in ASSETS.values()):
        parser.error("The test HTML and compiled build/qa JavaScript must both exist.")
    try:
        server = ThreadingHTTPServer(("127.0.0.1", args.port), ProbeHandler)
    except OSError:
        parser.exit(1, "Cannot bind the selected loopback port; leave existing listeners alone.\n")
    print(
        f"Controlled S1 probe: http://127.0.0.1:{args.port}/tool/local_web_transport_probe.html",
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
