from modules.consoleComands.downloadFileComand import DownloadFileComand
from modules.consoleComands.disableConsole import DisableConsoleComand
from modules.consoleComands.evalComand import EvalComand
from modules.consoleComands.screenshotComand import GetFrameComand
from modules.consoleComands.okComand import OkComand
from modules.consoleComands.loadComand import LoadComand
from modules.consoleComands.exitComand import ExitComand
from modules.consoleComands.changeCurrentComand import ChangeCurrentSocketComand, ListSocketsComand

comands = {
    EvalComand.type: EvalComand(),
    OkComand.type: OkComand(),
    GetFrameComand.type: GetFrameComand(),
    LoadComand.type: LoadComand(),
    ExitComand.type: ExitComand(),
    DisableConsoleComand.type: DisableConsoleComand(),
    ChangeCurrentSocketComand.type: ChangeCurrentSocketComand(),
    ListSocketsComand.type: ListSocketsComand(),
    DownloadFileComand.type: DownloadFileComand()
}
default = EvalComand.type


def getComands():
    return comands
