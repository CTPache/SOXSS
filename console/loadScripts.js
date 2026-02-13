hostScripts = "http://localhost:8000/"
function loadDefaultScripts() {
    sendConsole('load ' + hostScripts + 'scripts/screenshot.js'); sendConsole('load ' + hostScripts + 'scripts/html2canvas.min.js')
    sendConsole('load ' + hostScripts + 'scripts/mitm.js')//.then(() => sendConsole('mitm'))
    sendConsole('load ' + hostScripts + 'scripts/logger.js')
    sendConsole('load ' + hostScripts + 'scripts/link2fetch.js')
    sendConsole('load ' + hostScripts + 'scripts/downloadFile.js')
}