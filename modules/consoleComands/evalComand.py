import json
from modules.consoleComands.abstractComand import Comand

class EvalComand(Comand):
    type = 'eval'

    def execute(self, payload):
        return json.dumps({"command": "eval", "expression": payload})
