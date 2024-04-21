from modules.consoleComands.abstractComand import Comand


class ExitComand(Comand):
    type = 'exit'
    sendsMessage = True

    def execute(self, payload):
        exit()
