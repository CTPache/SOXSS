from modules.loggerModule import Logger
from modules.consoleModule import  ConsoleInWeb 
from modules.screenshotModule import ScreenshotModule
from modules.MITMModule import MITMModule

modules = {
    Logger.type: Logger(),
    ConsoleInWeb.type: ConsoleInWeb(),
    ScreenshotModule.type: ScreenshotModule(),
    MITMModule.type: MITMModule()
}
defaultModule = ConsoleInWeb.type


def getModules():
    return modules, defaultModule
