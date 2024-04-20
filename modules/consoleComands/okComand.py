import json
from modules.consoleComands.abstractComand import Comand

class OkComand(Comand):
    type = 1

    def execute(self, payload):
        return json.dumps({"command": "OK"})
