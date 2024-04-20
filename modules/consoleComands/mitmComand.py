import json
from modules.consoleComands.abstractComand import Comand


class MITMComand(Comand):
    type = "mitm"

    def execute(self, payload):
        args = " ".join(payload.split(" ")[1:])
        return json.dumps({"comand": "mitm", "url": args})
