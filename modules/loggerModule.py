from modules.abstractModule import Module

class Logger(Module):
    type = 3
    logfilePath = "input.log"
    
    def logToFile(self, log):
        file = open(self.logfilePath, "a")
        file.write(log + "\n")
        file.close()
    
    async def handleMessage(self, websocket, msg):
        self.logToFile(msg)
        await super().sendMessage(websocket)
        
