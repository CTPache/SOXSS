import asyncio
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from urllib.parse import parse_qs

host = "localhost"
port = 8001
mod = None
cache = {}


class MITMHTTPRequestHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        asyncio.run(self.get())

    def do_POST(self):
        asyncio.run(self.post())

    async def get(self):
        method = "GET"
        cacheKey = self.path + method
        if "websocket.js" in self.path.lower():
            return
        if hasattr(mod, "socket"):
            await mod.socket.send(
                json.dumps(
                    {
                        "comand": "mitm",
                        "method": method,
                        "url": self.path,
                    }
                )
            )
            while cacheKey not in cache:
                pass
            response = cache[cacheKey]
            self.send_response(200)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-type", response["type"])
            self.end_headers()
            self.wfile.write(response["content"].encode("utf-8"))

    async def post(self):
        method = "POST"
        cacheKey = self.path + method
        if "websocket.js" in self.path.lower():
            return
        if hasattr(mod, "socket"):
            contentLength = int(self.headers["Content-Length"])
            await mod.socket.send(
                json.dumps(
                    {
                        "comand": "mitm",
                        "method": method,
                        "url": self.path,
                        "body": self.rfile.read(contentLength).decode("utf-8"),
                    }
                )
            )
            while cacheKey not in cache:
                pass
            response = cache[cacheKey]
            self.send_response(200)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-type", response["type"])
            self.end_headers()
            self.wfile.write(response["content"].encode("utf-8"))

    def log_message(self, format: str, *args) -> None:
        return ""


def start_server(module):
    global mod
    mod = module
    server_address = (host, port)
    httpd = HTTPServer(server_address, MITMHTTPRequestHandler)
    httpd.serve_forever()
