from modules.abstractModule import Module
import os

class Logger(Module):
    type = 'log'
    
    def logToFile(self, log, sid):
        file = open(f"console/logs/{sid}.log", "a")
        file.write(log + "\n")
        file.close()
    
    async def handleMessage(self, websocket, msg):
        sid = websocket.request.path.strip("/") if hasattr(websocket, "request") else "unknown"
        os.makedirs('console/logs', exist_ok=True)
        self.logToFile(msg, sid)
        await super().sendMessage(websocket)
        
