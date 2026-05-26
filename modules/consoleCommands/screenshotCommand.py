import json
from modules.consoleCommands.abstractCommand import Command

class GetFrameCommand(Command):
    type = 'screenshot'

    def execute(self, payload):
        return json.dumps({"Command": "screenshot"})
