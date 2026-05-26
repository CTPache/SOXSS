hostScripts = "http://localhost:8000/"
async function loadDefaultScripts() {
    await sendConsole('load ' + hostScripts + 'scripts/screenshot.js');
    await sendConsole('load ' + hostScripts + 'scripts/html2canvas.min.js');
    await sendConsole('load ' + hostScripts + 'scripts/mitm.js');
    await sendConsole('load ' + hostScripts + 'scripts/logger.js');
    await sendConsole('load ' + hostScripts + 'scripts/link2fetch.js');
    await sendConsole('load ' + hostScripts + 'scripts/downloadFile.js');
    await sendConsole('console.log("Loaded all scripts")');
    console.log("Loaded all scripts");
}