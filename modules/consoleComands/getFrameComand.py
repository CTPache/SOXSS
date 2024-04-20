import json
from modules.consoleComands.abstractComand import Comand

class GetFrameComand(Comand):
    type = 'getFrame'

    def execute(self, payload):
        return json.dumps({"command": "getFrame"})
