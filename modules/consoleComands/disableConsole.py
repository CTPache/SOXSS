import json
from modules.consoleComands.abstractComand import Comand

class DisableConsoleComand(Comand):
    type = 'disable'

    def execute(self, payload):
        return json.dumps({"comand": "disable"})
