import json
from cryptoUtil import sendSecretMessage

class Module:
    async def sendMessage(self, websocket, msg="OK"):
        await sendSecretMessage(websocket, json.dumps({"comand": msg}))

    async def handleMessage(self, websocket, msg):
        self.sendMessage(websocket)
