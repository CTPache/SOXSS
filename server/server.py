#!/usr/bin/env python3
from http.server import HTTPServer, SimpleHTTPRequestHandler
import cryptoUtil

host = "localhost"  # You can change this to your server's IP address or domain name if needed.
hport = 8000  # Default port for HTTP server
wport = 8765  # Default port for WebSocket server


class CORSRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory="server", **kwargs)

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        basepath = self.path.split("?")[0]
        self.send_header("Content-Type", f"{self.guess_type(basepath)}; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        SimpleHTTPRequestHandler.end_headers(self)

    def do_GET(self) -> None:
        if self.path.endswith("webSocket.js"):
            file = (
                open("server/webSocket.js", "rb")
                .read()
                .decode("utf-8")
                .replace("$key", cryptoUtil.secret_key)
                .replace("$IV", cryptoUtil.iv)
                .encode("utf-8")
                .replace("$host", host)
                .replace("$vport", wport)
                .replace("$hport", hport)
            )
            self.wfile.write(file)
        else:
            return super().do_GET()


def main():
    """Run the server."""
    server_address = ("0.0.0.0", hport)  # Listen on all interfaces
    httpd = HTTPServer(server_address, CORSRequestHandler)
    httpd.serve_forever()
