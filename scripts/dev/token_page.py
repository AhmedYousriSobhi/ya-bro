#!/usr/bin/env python3
"""Tiny page to try tab-scoped targets without workbench: `scripts/dev/token_page.py [port]`.

Then: `broctl targets allow demo --origin http://127.0.0.1:8099`, `broctl point`, and open the page.
The ring shows on this tab only; switch tabs and it disappears.
"""

import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

PAGE = b"""<!doctype html><title>Ya-Bro demo</title><h1>Ya-Bro demo page</h1>
<script>
const base = document.title;
fetch('http://127.0.0.1:47800/token', {headers: {'X-YaBro': '1'}})
  .then(r => r.ok ? r.text() : '').then(t => { if (t) document.title = base + ' ' + t; });
</script>"""


class H(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(PAGE)

    def log_message(self, *a):
        pass


port = int(sys.argv[1]) if len(sys.argv) > 1 else 8099
print(f"http://127.0.0.1:{port}/  (Ctrl+C to stop)")
HTTPServer(("127.0.0.1", port), H).serve_forever()
