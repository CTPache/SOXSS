from modules.consoleCommands.downloadFileCommand import DownloadFileCommand
from modules.consoleCommands.disableConsole import DisableConsoleCommand
from modules.consoleCommands.evalCommand import EvalCommand
from modules.consoleCommands.screenshotCommand import GetFrameCommand
from modules.consoleCommands.okCommand import OkCommand
from modules.consoleCommands.loadCommand import LoadCommand
from modules.consoleCommands.exitCommand import ExitCommand
from modules.consoleCommands.changeCurrentCommand import ChangeCurrentSocketCommand, ListSocketsCommand

commands = {
    EvalCommand.type: EvalCommand(),
    OkCommand.type: OkCommand(),
    GetFrameCommand.type: GetFrameCommand(),
    LoadCommand.type: LoadCommand(),
    ExitCommand.type: ExitCommand(),
    DisableConsoleCommand.type: DisableConsoleCommand(),
    ChangeCurrentSocketCommand.type: ChangeCurrentSocketCommand(),
    ListSocketsCommand.type: ListSocketsCommand(),
    DownloadFileCommand.type: DownloadFileCommand()
}
default = EvalCommand.type


def getCommands():
    return commands
