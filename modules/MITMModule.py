from modules.abstractModule import Module
import socksUtil
import threading
from modules.MITMServer import cache, start_server


class MITMModule(Module):
    type = "mitm"

    def __init__(self):

        # Iniciar el servidor en un hilo separado
        thread = threading.Thread(target=start_server, args=[self])
        thread.daemon = True
        thread.start()

    async def handleMessage(self, websocket, msg):
        index = socksUtil.sockets.index(websocket)
        cache[msg["key"]] = {
            "type": msg["contentType"],
            "content": msg["content"],
            "method": msg["method"],
        }
        await super().sendMessage(websocket)
