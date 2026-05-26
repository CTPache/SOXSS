

import aiohttp
from aiohttp import web
import os
import asyncio
import cryptoUtil

import sys
import os
# Add parent directory to sys.path to allow importing config.py
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
import config

STATIC_DIR = os.path.join(os.path.dirname(__file__))

async def handle_static(request):
    rel_path = request.match_info.get('filename', '')
    file_path = os.path.join(STATIC_DIR, rel_path)
    if not os.path.isfile(file_path):
        return web.Response(status=404, text="Not found")
    # Special handling for webSocket.js to inject keys
    if rel_path.endswith('webSocket.js'):
        import uuid
        sid = uuid.uuid4().hex
        secret_key, iv = cryptoUtil.generate_key_iv()
        cryptoUtil.set_key_iv(sid, secret_key, iv)
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        content = (
            content.replace("$key", secret_key)
                   .replace("$IV", iv)
                   .replace("$sid", sid)
                   .replace("$hhost", config.PUBLIC_HTTP_HOST)
                   .replace("$whost", config.PUBLIC_WS_HOST)
                   .replace("$wport", str(config.PUBLIC_WS_PORT))
                   .replace("$hport", str(config.PUBLIC_HTTP_PORT))
        )
        return web.Response(text=content, content_type='application/javascript', headers={"Access-Control-Allow-Origin": "*"})
    # Serve other static files
    return web.FileResponse(file_path, headers={"Access-Control-Allow-Origin": "*"})

def setup_routes(app):
    app.router.add_get('/{filename:.*}', handle_static)

async def start_async_server():
    app = web.Application()
    setup_routes(app)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, config.HTTP_HOST, config.HTTP_PORT)
    await site.start()
    print(f"HTTP server running at http://{config.HTTP_HOST}:{config.HTTP_PORT}/")
    # Keep running forever
    while True:
        await asyncio.sleep(3600)
