import json
from modules.consoleCommands.abstractCommand import Command

class OkCommand(Command):
    type = 1

    def execute(self, payload):
        return json.dumps({"Command": "OK"})
