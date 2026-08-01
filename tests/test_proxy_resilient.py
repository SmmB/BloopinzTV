"""
Tests for the proxy's resilient streaming (scraping-agnostic).

A tiny local HTTP server simulates a flaky link (drops mid-transfer, then
honours Range on reconnect) and an expired token (403 until re-resolution
supplies a fresh one). resilient_body must always deliver the complete,
byte-identical body.
"""

import http.server
import re
import threading
import urllib.parse

from freeflix_cli import proxy

PAYLOAD = bytes([i % 256 for i in range(300000)])


def _serve(handler_cls):
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, srv.server_address[1]


def _range_start(headers):
    m = re.match(r"bytes=(\d+)-", headers.get("Range") or "")
    return int(m.group(1)) if m else 0


def test_resume_after_midstream_drop():
    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            start = _range_start(self.headers)
            body = PAYLOAD[start:]
            self.send_response(206 if start else 200)
            if start:
                self.send_header("Content-Range", f"bytes {start}-{len(PAYLOAD)-1}/{len(PAYLOAD)}")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if start == 0 and not getattr(self.server, "dropped", False):
                self.server.dropped = True
                try:
                    self.wfile.write(body[:len(body) // 2]); self.connection.close()
                except Exception:
                    pass
            else:
                try:
                    self.wfile.write(body)
                except Exception:
                    pass

        def log_message(self, *a):
            pass

    srv, port = _serve(H)
    try:
        got = b"".join(proxy.resilient_body(
            f"http://127.0.0.1:{port}/seg.ts", {}, first_resp=None))
    finally:
        srv.shutdown()
    assert got == PAYLOAD


def test_recover_from_expired_token():
    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            q = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(self.path).query))
            if q.get("t") != "NEW":
                self.send_response(403); self.end_headers(); self.wfile.write(b"expired"); return
            start = _range_start(self.headers)
            body = PAYLOAD[start:]
            self.send_response(206 if start else 200)
            if start:
                self.send_header("Content-Range", f"bytes {start}-{len(PAYLOAD)-1}/{len(PAYLOAD)}")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    srv, port = _serve(H)
    proxy.set_stream_refresher(lambda: f"http://127.0.0.1:{port}/master.m3u8?t=NEW&e=9")
    try:
        got = b"".join(proxy.resilient_body(
            f"http://127.0.0.1:{port}/seg.ts?t=OLD", {}, first_resp=None))
    finally:
        srv.shutdown()
        proxy.clear_stream_refresher()
    assert got == PAYLOAD


def test_refreshed_url_swaps_token():
    proxy.set_stream_refresher(lambda: "https://cdn/x/master.m3u8?t=NEW&e=9&f=1")
    try:
        out = proxy._refreshed_url("https://cdn/x/seg3.ts?t=OLD&e=1&f=1")
        assert "t=NEW" in out and "seg3.ts" in out
        assert proxy._refreshed_url("https://cdn/x/master.m3u8?t=OLD").endswith("t=NEW&e=9&f=1")
    finally:
        proxy.clear_stream_refresher()
