import json
import threading
import time
from cryptoUtil import sendSecretMessage
from modules.abstractModule import Module
import modules.consoleComands.getComands as comands
import pytimedinput
import modules.ConsoleServer as server

class ConsoleInWeb(Module):
    type = 0
    
    def __init__(self):

        # Iniciar el servidor en un hilo separado
        thread = threading.Thread(target=server.start_server, args=[self])
        thread.daemon = True
        thread.start()
        
    async def handleMessage(self, websocket, msg):
            self.socket = websocket
            msg['timestamp'] = time.time()
            server.consoleOut = json.dumps(msg)

    async def sendMessage(self, websocket, msg):
        if msg.split(" ")[0] in comands.getComands():
            await sendSecretMessage(websocket, comands.getComands()[msg.split(" ")[0]].execute(msg))
        else:
            await sendSecretMessage(websocket, comands.getComands()[comands.default].execute(msg))


# Obsoleto, mejor usar el módulo web

class ConsoleOut(Module):
    type = 0

    consoleColors = {
        'console':'\033[0m',
        'info':'\033[94m',
        'warning':'\033[93m',
        'error':'\033[91m',
        'end':'\033[0m'
    }

    async def handleMessage(self, websocket, msg):
        color = msg["outputType"]
        if "text" in msg:
            text = msg['text']
            print(f"{self.consoleColors[color] + str(text) +self.consoleColors['end']}")
        await super().sendMessage(websocket, "OK")

class ConsoleIn(Module):
    type = 1
    prompt = ""

    async def handleMessage(self, websocket, msg):
        nextPrompt, timedOut = pytimedinput.timedInput("> " + self.prompt, 1)
        if timedOut:
            await super().sendMessage(websocket)
            print("\x1b[1A" + "\x1b[2K" + "\x1b[1A")
            self.prompt += nextPrompt
        else:
            self.prompt += nextPrompt
            await self.sendMessage(websocket, self.prompt)
            self.prompt = ""

    async def sendMessage(self, websocket, msg):
        if msg.split(" ")[0] in comands.getComands():
            await sendSecretMessage(websocket, comands.getComands()[msg.split(" ")[0]].execute(msg))
        else:
            await sendSecretMessage(websocket, comands.getComands()[comands.default].execute(msg))
