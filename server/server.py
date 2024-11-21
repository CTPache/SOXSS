#!/usr/bin/env python3
from http.server import HTTPServer, SimpleHTTPRequestHandler

import cryptoUtil


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
            file = open("server/webSocket.js", "rb").read().decode("utf-8").replace("$key",cryptoUtil.secret_key).replace("$IV",cryptoUtil.iv).encode("utf-8")
            self.wfile.write(file)
        else:
            f = self.send_head()
            if f:
                try:
                    file = f.read()
                    file = file.decode("utf-8").replace("$name",self.headers.get("cookie")).encode("utf-8")
                    self.wfile.write(file)
                finally:
                    f.close()
            
            


def main():
    server_address = ("0.0.0.0", 8000)
    httpd = HTTPServer(server_address, CORSRequestHandler)
    httpd.serve_forever()
