import base64
import json
from modules.consoleComands.abstractComand import Comand

class DownloadFileComand(Comand):
    type = 'downloadFile'

    def execute(self, payload):
        args = payload.split(" ")[1:]
        print(args)
        return json.dumps({"comand": "downloadFile", "data": self.getFile(args[0]), "fileName": args[1]})
    
    def getFile(self, path):
        with open(path, 'br') as file:
            #return file as b64
            return base64.b64encode(file.read()).decode('utf-8')