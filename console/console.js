host = 'http://localhost:8002'

// Envía el mensaje al server por POST
async function sendConsole(comand = "") {
    if (comand.includes("broadcast")) {
        sendConsoleBroadcast(comand.split(" ")[1], comand.split(" ").slice(2)).then(result => result)
    }
    else
        return fetch(host, { method: 'POST', body: comand }).then(result => result.json())
}

async function sendConsoleBroadcast(comand, _clients) {
    let broadcastClients = []
    let ret = []
    if (_clients == "all")
        broadcastClients = Object.keys(clients)
    else if (_clients.length > 0)
        broadcastClients = _clients
    broadcastClients.forEach(element => {
        sendConsole("change " + element)
        sendConsole(comand).then(x => {
            ret.push(x)
            logComand(x)
        })
    });
    sendConsole("change " + currentClient)
    return ret
}

// Incluye el comando y el valor de retorno
async function logComand(data) {
    if (data == undefined)
        return
    console.log(data)
    let outputMsg = $("<pre class=inputMsg>></pre>")
    outputMsg.text(data.host + "> " + data.text)
    outputMsg.addClass(data.outputType)
    $('#log').prepend(outputMsg)
}

//Envía el comando si detecta ENTER pulsada
function checkSubmit(e) {
    if (e && e.keyCode == 13) {
        document.forms[0].submit();
    }
}