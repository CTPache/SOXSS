from modules.consoleCommands.abstractCommand import Command


class ExitCommand(Command):
    type = 'exit'
    sendsMessage = True

    def execute(self, payload):
        exit()
