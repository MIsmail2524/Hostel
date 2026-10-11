"""Serve the exported web build (dist/) with SPA fallback. Dev/demo use only: python3 scripts/serve_web.py [port]"""
import http.server
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "dist"


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(ROOT), **kw)

    def send_head(self):
        path = Path(self.translate_path(self.path))
        if not path.exists() or (path.is_dir() and not (path / "index.html").exists()):
            self.path = "/index.html"  # client-side routing
        return super().send_head()

    def end_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.environ.get("PORT", 8082))
    http.server.ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
