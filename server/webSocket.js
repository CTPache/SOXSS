const host = 'localhost'
const httpPort = "8000"

function sendMessage(msg) {
    mes = JSON.stringify(msg)
    webSocket.send(mes);
}

function loadScript(url) {
    if (!(/(http(s?)):\/\//i.test(url))) {
        url = 'http://' + host + ':' + httpPort + '/' + url
    }
    return fetch(url).then(response => {
        if (response.ok) {
            var node = document.createElement("script");
            node.setAttribute("src", url);
            document.getElementsByTagName("head")[0].appendChild(node);
        }
        return response.ok
    })
}

const webSocket = new WebSocket("ws://" + host + ":8765");
webSocket.onopen = (event) => {
    sendMessage({ type: 1 });
};

/* Esta es un diccionario de tipo {'string':function}, la string es el comando que recibirá el onmessage, la función será el comando.

Para cargar más funcionalidades que interactúen con módulos en el backend se debe cargar en un script que incluya el comando al
diccionario. Importante mandar un mensaje en algún momento de la ejecución.
Comandos por defecto:
    OK - keep alive la conexión
    eval - ejecuta lo que venga en el comando y devuelve lo que retorno
    load - carga un fichero desde un URL.
 */
var _webs_commands_ = {
    'OK': function (mes) { sendMessage({ type: 1 }) },
    'eval': function (mes) {
        sendMessage({ type: 0, msg: { outputType: "console", text: eval(mes["expression"]) } })
    },
    'load': function (mes) {
        loadScript(mes["script"]).then(ok => {
            if (ok)
                sendMessage({ type: 0, msg: { outputType: "info", text: "loaded" } })
            else
                sendMessage({ type: 0, msg: { outputType: "error", text: "could not load " + mes['script'] } })
        })
    },
    'disable': function (mes) { }
}

webSocket.onmessage = (event) => {
    try {
        let mes = JSON.parse(event.data)
        _webs_commands_[mes["command"]](mes)
    } catch (e) { sendMessage({ type: 0, msg: { outputType: "error", text: e.toString() } }) }

};
