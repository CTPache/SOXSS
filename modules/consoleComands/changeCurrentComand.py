import json
from modules.consoleComands.abstractComand import Comand
import socksUtil


class ChangeCurrentSocketComand(Comand):
    type = 'change'
    sendsMessage = False

    def execute(self, payload):
        index = int(payload.split(' ')[1])
        if socksUtil.sockets.__len__() -1 < index:
            return {"text": "Index out of range: " + str(index) + ". Use the command 'list' to get a list of websockets.",
                    "outputType": "error"}
        socksUtil.current = index
        ip = socksUtil.getCurrent().remote_ip
        return {"text": "changed target to " + str(index) + ": " + ip}


class ListSocketsComand(Comand):
    type = 'list'
    sendsMessage = False

    def execute(self, payload):
        return {"text": "\n" + json.dumps(socksUtil.listSockets(), separators=[',', ': '],),
                "outputType": "info"}
