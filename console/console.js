host = 'http://localhost:8002'

// Envía el mensaje al server por POST
async function sendConsole(comand) {
    return fetch(host, { method: 'POST', body: comand }).then(result => result.json())
}

// Incluye el comando y el valor de retorno, vacía el input
function logComand(data) {
    console.log(data)
    $('#log').prepend($("<pre class=inputMsg></pre>").text($('#inputText').val()))
    let outputMsg = $("<pre class=inputMsg>></pre>")
    outputMsg.text(data.host + "> " + data.text)
    outputMsg.addClass(data.outputType)
    $('#log').prepend(outputMsg)
    $('#inputcomand').val('')
}

//Envía el comando si detecta ENTER pulsada
function checkSubmit(e) {
    if (e && e.keyCode == 13) {
        document.forms[0].submit();
    }
}