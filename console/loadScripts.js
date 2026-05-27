let hostScripts = null;

async function getHostScripts() {
    if (hostScripts) return hostScripts;
    try {
        const res = await fetch(host + '/config');
        const cfg = await res.json();
        hostScripts = `http://${cfg.http_host}:${cfg.http_port}/`;
    } catch (e) {
        hostScripts = 'http://localhost:8000/';
    }
    return hostScripts;
}

async function loadDefaultScripts() {
    const base = await getHostScripts();
    await sendConsole('load ' + base + 'scripts/screenshot.js');
    await sendConsole('load ' + base + 'scripts/html2canvas.min.js');
    await sendConsole('load ' + base + 'scripts/mitm.js');
    await sendConsole('load ' + base + 'scripts/logger.js');
    await sendConsole('load ' + base + 'scripts/link2fetch.js');
    await sendConsole('load ' + base + 'scripts/downloadFile.js');
}