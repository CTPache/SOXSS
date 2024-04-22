from modules.abstractModule import Module

class Logger(Module):
    type = 'log'
    
    def logToFile(self, log, ip):
        file = open(f"input_{ip}.log", "a")
        file.write(log + "\n")
        file.close()
    
    async def handleMessage(self, websocket, msg):
        self.logToFile(msg, websocket.remote_ip)
        await super().sendMessage(websocket)
        
