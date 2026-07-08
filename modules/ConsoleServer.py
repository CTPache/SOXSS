# Refactored to use aiohttp for async HTTP POST handling
import aiohttp
import asyncio
import json
from aiohttp import web
import os
import socksUtil
import config

consoleMod = None
consoleOut = ""

STATIC_DIR = os.path.join(os.path.dirname(__file__), '..', 'console')


def _build_public_http_base():
    scheme = str(getattr(config, 'PUBLIC_HTTP_SCHEME', 'http') or 'http').strip()
    host = str(getattr(config, 'PUBLIC_HTTP_HOST', '') or '').strip()
    port = getattr(config, 'PUBLIC_HTTP_PORT', None)
    if not host:
        return ''
    include_port = port not in (None, '', 0, '0')
    base = f"{scheme}://{host}"
    if include_port and ':' not in host:
        base = f"{base}:{port}"
    return f"{base}/"

async def handle_post(request):
    global consoleOut
    body = await request.text()
    socket = ''
    if len(socksUtil.sockets) > 0:
        socket = socksUtil.getCurrent()
    last = consoleOut
    try:
        await consoleMod.sendMessage(socket, body)
    except Exception as e:
        consoleOut = json.dumps({
            "outputType": "error",
            "text": f"command handling failed: {e}"
        })
    # Wait for consoleOut to change (simulate old busy-wait)
    for _ in range(1000):  # up to ~10s
        if last != consoleOut:
            break
        await asyncio.sleep(0.01)
    response = consoleOut
    return web.Response(text=response, content_type='application/json', headers={"Access-Control-Allow-Origin": "*"})

async def handle_config(request):
    return web.json_response(
        {
            "http_host": config.PUBLIC_HTTP_HOST,
            "http_port": config.PUBLIC_HTTP_PORT,
            "http_scheme": getattr(config, 'PUBLIC_HTTP_SCHEME', 'http'),
            "http_base": _build_public_http_base(),
        },
        headers={"Access-Control-Allow-Origin": "*"}
    )

async def handle_static(request):
    rel_path = request.match_info.get('filename', '')
    file_path = os.path.join(STATIC_DIR, rel_path)
    if not os.path.isfile(file_path):
        return web.Response(status=404, text="Not found")
    return web.FileResponse(file_path, headers={"Access-Control-Allow-Origin": "*"})

def setup_routes(app):
    app.router.add_post('/', handle_post)
    app.router.add_get('/config', handle_config)
    app.router.add_get('/{filename:.*}', handle_static)

async def start_async_console_server(consoleModule):
    global consoleMod
    consoleMod = consoleModule
    app = web.Application()
    setup_routes(app)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, config.CONSOLE_HOST, config.CONSOLE_PORT)
    await site.start()
    print(f"Console server running at http://{config.CONSOLE_HOST}:{config.CONSOLE_PORT}/index.html")
    while True:
        await asyncio.sleep(3600)
