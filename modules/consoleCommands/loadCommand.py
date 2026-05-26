import json
from modules.consoleCommands.abstractCommand import Command

class LoadCommand(Command):
    type = 'load'

    def execute(self, payload):
        # Keep script body untouched (including newlines/comments) after first space.
        args = payload.split(" ", 1)[1] if " " in payload else ""
        return json.dumps({"Command": "load", "script": args})
