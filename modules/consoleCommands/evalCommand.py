import json

from modules.consoleCommands.abstractCommand import Command


class EvalCommand(Command):
    type = 'eval'

    def execute(self, payload):
        return json.dumps({"Command": "eval", "expression": payload})
