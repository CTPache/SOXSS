let hostScripts = null;

async function getHostScripts() {
    if (hostScripts) return hostScripts;
    try {
        const res = await fetch(host + '/config');
        const cfg = await res.json();
        if (cfg.http_base) {
            hostScripts = cfg.http_base;
        } else {
            const scheme = cfg.http_scheme || 'http';
            const port = (cfg.http_port === null || cfg.http_port === undefined || cfg.http_port === '') ? '' : `:${cfg.http_port}`;
            hostScripts = `${scheme}://${cfg.http_host}${port}/`;
        }
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