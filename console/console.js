var host = 'http://localhost:8002'

// Envía el mensaje al server por POST
async function sendConsole(Command = "") {
    let body = Command;
    if (Command.startsWith("load")) {
        try {
            const script = await fetch(Command.split("load ")[1]).then(s => s.text());
            body = "load " + script;
        } catch (e) {
            return { outputType: "error", text: "Failed to load local script: " + e.message, host: "local" };
        }
    }
    
    return fetch(host, { method: 'POST', body: body })
        .then(res => res.json())
        .catch(err => ({ outputType: "error", text: "Server unreachable: " + err.message, host: "local" }));
}

function handleConsoleSubmit() {
    const input = document.getElementById('inputText');
    const val = input.value.trim();
    if (!val) return;
    
    // Add to log immediately as input
    appendLog({ outputType: 'input', text: val, host: 'you' });
    
    sendConsole(val).then(data => {
        appendLog(data);
    });
    
    input.value = '';
}

function appendLog(data) {
    if (!data) return;
    
    const log = document.getElementById('log');
    const time = new Date().toLocaleTimeString([], { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
    
    const entry = document.createElement('div');
    entry.className = 'log-entry';
    
    entry.innerHTML = `
        <span class="log-time">[${time}]</span>
        <span class="log-content ${data.outputType}">${data.host ? data.host + '> ' : ''}${data.text || ''}</span>
    `;
    
    log.appendChild(entry);
    log.scrollTop = log.scrollHeight;
}

// Deprecated old logCommand
async function logCommand(data) { appendLog(data); }