from modules.consoleComands.disableConsole import DisableConsoleComand
from modules.consoleComands.evalComand import EvalComand
from modules.consoleComands.getFrameComand import GetFrameComand
from modules.consoleComands.mitmComand import MITMComand
from modules.consoleComands.okComand import OkComand
from modules.consoleComands.loadComand import LoadComand
from modules.consoleComands.exitComand import ExitComand

comands = {
    EvalComand.type : EvalComand(),
    OkComand.type : OkComand(),
    GetFrameComand.type : GetFrameComand(),
    LoadComand.type : LoadComand(),
    ExitComand.type : ExitComand(),
    MITMComand.type : MITMComand(),
    DisableConsoleComand.type : DisableConsoleComand()
}
default = EvalComand.type


def getComands():
    return comands
