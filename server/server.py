#!/usr/bin/env python3
from http.server import HTTPServer, SimpleHTTPRequestHandler


class CORSRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory="server", **kwargs)

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        basepath = self.path.split("?")[0]
        self.send_header("Content-Type", f"{self.guess_type(basepath)}; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")

        SimpleHTTPRequestHandler.end_headers(self)

    def log_message(self, format: str, *args) -> None:
        return ""


def main():
    server_address = ("0.0.0.0", 8000)
    httpd = HTTPServer(server_address, CORSRequestHandler)
    httpd.serve_forever()
