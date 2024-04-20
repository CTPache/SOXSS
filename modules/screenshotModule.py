from modules.abstractModule import Module
from PIL import Image
import base64
import io

class ScreenshotModule(Module):
    type = 2

    async def handleMessage(self, websocket, msg):
        image = Image.open(io.BytesIO(base64.b64decode(msg.split("base64,")[1])))
        image.save("frame.png")
        await super().sendMessage(websocket)
