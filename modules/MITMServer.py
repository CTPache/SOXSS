import asyncio
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import socksUtil

host = "localhost"
port = 8001
cache = {}


class MITMHTTPRequestHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        asyncio.run(self.performRequest('GET'))

    def do_POST(self):
        asyncio.run(self.performRequest('POST'))

    async def performRequest(self, method):
        
        skt = int(self.path.split('/')[1]) # índice del socket
        path = '/' + self.path.split('/')[2] # path que se va a consultar en el cliente, sin el índice
        response = {}
        cacheKey = str(skt) + path + method
        
        # no devolver el script del websocket para no crear nuevas conexiones
        if "websocket.js" in path.lower():
            return
        
        # Construye el objeto de la request
        request = {
            "comand": "mitm",
            "method": method,
            "url": path,
        }
        
        # Si es POST incluye el body
        if method == 'POST':
            request['body'] = self.rfile.read(
                int(self.headers["Content-Length"])).decode("utf-8")
        try:
            socket = socksUtil.sockets[skt]
            await socket.send(json.dumps(request))
            while cacheKey not in cache:
                pass
            response = cache[cacheKey]
            self.send_response(200)
            self.send_header("Content-type", response["type"])
        except:
            response["content"] = f'{method} Request error: no socket with id {skt}'
            self.send_response(404)
        self.send_header("Access-Control-Allow-Origin", "*")
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
