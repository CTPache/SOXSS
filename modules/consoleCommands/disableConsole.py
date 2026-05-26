import json
from modules.consoleCommands.abstractCommand import Command

class DisableConsoleCommand(Command):
    type = 'disable'

    def execute(self, payload):
        return json.dumps({"Command": "disable"})
