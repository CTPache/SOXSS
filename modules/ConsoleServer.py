import asyncio
from http.server import SimpleHTTPRequestHandler, HTTPServer
import socksUtil
host = "localhost"
port = 8002
cache = {}
consoleMod = None
consoleOut = ""
defaultPAth = "console.html"


class ConsoleHTTPRequestHandler(SimpleHTTPRequestHandler):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory="console/", **kwargs)

    def do_POST(self):
        asyncio.run(self.post())

    async def post(self):

        contentLength = int(self.headers["Content-Length"])
        body = self.rfile.read(contentLength).decode("utf-8")
        if socksUtil.sockets.__len__() > 0:
            last = consoleOut
            await consoleMod.sendMessage(socksUtil.getCurrent(), body)
            while last == consoleOut:
                pass
            response = bytes(consoleOut, "utf-8")
            self.send_response(200)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(response)

    def log_message(self, format: str, *args) -> None:
        return ""


def start_server(consoleModule):
    server_address = (host, port)

    httpd = HTTPServer(server_address, ConsoleHTTPRequestHandler)
    global consoleMod
    consoleMod = consoleModule
    httpd.serve_forever()
