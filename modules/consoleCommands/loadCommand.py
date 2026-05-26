import json
from modules.consoleCommands.abstractCommand import Command

class LoadCommand(Command):
    type = 'load'

    def execute(self, payload):
        args = " ".join(payload.split(" ")[1:])
        return json.dumps({"Command": "load", "script": args})
