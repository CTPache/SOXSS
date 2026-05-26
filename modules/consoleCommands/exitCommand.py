from modules.consoleCommands.abstractCommand import Command
import json


class ExitCommand(Command):
    type = 'exit'
    sendsMessage = True

    def execute(self, payload):
        # Keep the C2 process alive; request remote session shutdown instead.
        return json.dumps({"Command": "disable"})
