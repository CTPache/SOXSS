

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


def _clean_public_host(host):
    value = str(host or '').strip()
    if value.startswith('http://'):
        value = value[len('http://'):]
    elif value.startswith('https://'):
        value = value[len('https://'):]
    elif value.startswith('ws://'):
        value = value[len('ws://'):]
    elif value.startswith('wss://'):
        value = value[len('wss://'):]
    return value.strip('/').strip()


def _host_has_explicit_port(host):
    if host.startswith('['):
        return ']:' in host
    return ':' in host


def _build_public_base_url(scheme, host, port):
    clean_host = _clean_public_host(host)
    if not clean_host:
        return ''

    include_port = port not in (None, '', 0, '0')
    base = f"{scheme}://{clean_host}"
    if include_port and not _host_has_explicit_port(clean_host):
        base = f"{base}:{port}"
    return base


@web.middleware
async def cors_middleware(request, handler):
    if request.method == 'OPTIONS':
        response = web.Response(status=200)
    else:
        response = await handler(request)

    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET,POST,PUT,DELETE,OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-Requested-With'
    response.headers['Access-Control-Max-Age'] = '86400'
    return response

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
        http_scheme = getattr(config, 'PUBLIC_HTTP_SCHEME', 'http')
        ws_scheme = getattr(config, 'PUBLIC_WS_SCHEME', 'ws')
        http_port = getattr(config, 'PUBLIC_HTTP_PORT', None)
        ws_port = getattr(config, 'PUBLIC_WS_PORT', None)
        http_base = _build_public_base_url(http_scheme, config.PUBLIC_HTTP_HOST, http_port)
        ws_base = _build_public_base_url(ws_scheme, config.PUBLIC_WS_HOST, ws_port)
        hport = '' if http_port in (None, '', 0, '0') else str(http_port)
        wport = '' if ws_port in (None, '', 0, '0') else str(ws_port)
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        content = (
            content.replace("$key", secret_key)
                   .replace("$IV", iv)
                   .replace("$sid", sid)
                   .replace("$hbase", f"{http_base}/" if http_base else "")
                   .replace("$wsbase", ws_base)
                   .replace("$hhost", config.PUBLIC_HTTP_HOST)
                   .replace("$whost", config.PUBLIC_WS_HOST)
                   .replace("$wport", wport)
                   .replace("$hport", hport)
        )
        return web.Response(text=content, content_type='application/javascript', headers={"Access-Control-Allow-Origin": "*"})
    # Serve other static files
    return web.FileResponse(file_path, headers={"Access-Control-Allow-Origin": "*"})

def setup_routes(app):
    app.router.add_get('/{filename:.*}', handle_static)

async def start_async_server():
    app = web.Application(middlewares=[cors_middleware])
    setup_routes(app)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, config.HTTP_HOST, config.HTTP_PORT)
    await site.start()
    print(f"HTTP server running at http://{config.HTTP_HOST}:{config.HTTP_PORT}/")
    # Keep running forever
    while True:
        await asyncio.sleep(3600)
