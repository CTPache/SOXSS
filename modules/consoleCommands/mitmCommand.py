import json
from modules.consoleCommands.abstractCommand import Command

# Deprecado, esto debería abrir una pestaña y la sintaxis ser:
# mitm <indexSocket>
class MITMCommand(Command):
    type = "mitm"

    def execute(self, payload):
        args = " ".join(payload.split(" ")[1:])
        return json.dumps({"Command": "mitm", "url": args})
