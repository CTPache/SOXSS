import json
from modules.consoleComands.abstractComand import Comand

class LoadComand(Comand):
    type = 'load'

    def execute(self, payload):
        args = " ".join(payload.split(" ")[1:])
        return json.dumps({"comand": "load", "script": args})
