
host = 'http://localhost:8002'
async function sendConsole(comand, output = false) {
    return fetch(host, { method: 'POST', body: comand }).then(result => result.json())
}
function logComand(data) {
    $('#log').prepend($("<p class=inputMsg></p>").text($('#inputCommand').val()))
    let outputMsg = $("<pre></pre>")
    outputMsg.text((data.text))
    outputMsg.addClass(data.outputType)
    $('#log').prepend(outputMsg)
    $('#inputCommand').val('')
}
function checkSubmit(e) {
    if (e && e.keyCode == 13) {
        document.forms[0].submit();
    }
}