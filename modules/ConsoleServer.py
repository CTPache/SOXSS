import asyncio
from http.server import BaseHTTPRequestHandler, HTTPServer

host = "localhost"
port = 8002
cache = {}
consoleMod = None
consoleOut = ''

class ConsoleHTTPRequestHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        asyncio.run(self.get())

    def do_POST(self):
        asyncio.run(self.post())

    async def get(self):
        response = bytes("GET not supported", "utf-8")
        self.send_response(402)
        self.send_header("Content-type", 'text')
        self.end_headers()
        self.wfile.write(response)

    async def post(self):
        
        contentLength = int(self.headers["Content-Length"])
        body = self.rfile.read(contentLength).decode('utf-8')
        if hasattr(consoleMod, "socket"):
            last = consoleOut
            await consoleMod.sendMessage(consoleMod.socket, body)
            while last == consoleOut:
                pass
            response = bytes(consoleOut, "utf-8")
            self.send_response(200)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-type", 'application/json')
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
