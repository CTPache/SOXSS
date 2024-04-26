import json
from modules.consoleComands.abstractComand import Comand

# Deprecado, esto debería abrir una pestaña y la sintaxis ser:
# mitm <indexSocket>
class MITMComand(Comand):
    type = "mitm"

    def execute(self, payload):
        args = " ".join(payload.split(" ")[1:])
        return json.dumps({"comand": "mitm", "url": args})
