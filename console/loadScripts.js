function loadDefaultScripts() {
    sendConsole('load scripts/screenshot.js'); sendConsole('load scripts/html2canvas.min.js')
    sendConsole('load scripts/mitm.js')//.then(() => sendConsole('mitm'))
    sendConsole('load scripts/logger.js')
    sendConsole('load scripts/link2fetch.js')
    sendConsole('load scripts/downloadFile.js')
}