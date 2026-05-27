var host = 'http://localhost:8002'
var commandHistory = [];
var historyIndex = 0;
var draftCommand = "";

function clearConsoleLog() {
    const log = document.getElementById('log');
    if (log) {
        log.innerHTML = '';
    }
}

// Envía el mensaje al server por POST
async function sendConsole(Command = "") {
    return fetch(host, { method: 'POST', body: Command })
        .then(res => res.json())
        .catch(err => ({ outputType: "error", text: "Server unreachable: " + err.message, host: "local" }));
}

function handleConsoleSubmit() {
    const input = document.getElementById('inputText');
    const val = input.value.trim();
    if (!val) return;

    const lowerVal = val.toLowerCase();
    if (lowerVal === 'clear' || lowerVal === 'cls') {
        clearConsoleLog();
        input.value = '';
        return;
    }

    commandHistory.push(val);
    historyIndex = commandHistory.length;
    draftCommand = "";
    
    // Add to log immediately as input
    appendLog({ outputType: 'input', text: val, host: 'you' });
    
    sendConsole(val).then(data => {
        appendLog(data);
    });
    
    input.value = '';
}

function handleHistoryNavigation(event) {
    const input = event.target;
    if (!input || input.id !== 'inputText') return;

    if (event.key === 'ArrowUp') {
        event.preventDefault();
        if (commandHistory.length === 0) return;

        if (historyIndex === commandHistory.length) {
            draftCommand = input.value;
        }

        historyIndex = Math.max(0, historyIndex - 1);
        input.value = commandHistory[historyIndex] || "";
        input.setSelectionRange(input.value.length, input.value.length);
    }

    if (event.key === 'ArrowDown') {
        event.preventDefault();
        if (commandHistory.length === 0) return;

        historyIndex = Math.min(commandHistory.length, historyIndex + 1);
        if (historyIndex === commandHistory.length) {
            input.value = draftCommand;
        } else {
            input.value = commandHistory[historyIndex] || "";
        }
        input.setSelectionRange(input.value.length, input.value.length);
    }
}

document.addEventListener('DOMContentLoaded', function () {
    const input = document.getElementById('inputText');
    if (!input) return;

    input.addEventListener('keydown', handleHistoryNavigation);
    document.addEventListener('keydown', function (event) {
        if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'l') {
            event.preventDefault();
            clearConsoleLog();
            input.focus();
        }
    });
});

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