from modules.consoleComands.abstractComand import Comand

class ExitComand(Comand):
    type = 'exit'

    def execute(self, payload):
        exit()
