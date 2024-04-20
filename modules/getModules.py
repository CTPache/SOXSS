from modules.loggerModule import Logger
from modules.consoleModule import ConsoleIn, ConsoleInWeb, ConsoleOut
from modules.screenshotModule import ScreenshotModule
from modules.MITMModule import MITMModule

modules = {
    Logger.type: Logger(),
#    ConsoleIn.type: ConsoleIn(),
    ConsoleInWeb.type: ConsoleInWeb(),
#    ConsoleOut.type: ConsoleOut(),
    ScreenshotModule.type: ScreenshotModule(),
    MITMModule.type: MITMModule()
}
defaultModule = ConsoleInWeb.type


def getModules():
    return modules, defaultModule
