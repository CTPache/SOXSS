// Lista de clientes conectados (simulación de ejemplo)
var clients
// Cargar la lista de clientes
async function loadClientList() {
    console.log("Loading clients")
    clients = await sendConsole('list').then(x => JSON.parse(x.text))
    const clientList = document.getElementById('clientList');
    clientList.innerHTML = '';
    for (const client in clients) {
        const clientButton = document.createElement('button');
        clientButton.textContent = client;
        clientButton.onclick = () => requestScreenshot(client);
        clientList.appendChild(clientButton);
        loadDefaultScripts();
    }
}

// Solicitar captura de pantalla al cliente específico
async function requestScreenshot(client) {
    sendConsole("change " + client)
    await sendConsole("screenshot")
    document.getElementById('previewImage').src = `cache/${clients[client]}.png`
}

// Ejecutar loadClientList solo cuando el DOM esté completamente cargado
document.addEventListener('DOMContentLoaded', function () {
    loadClientList().then(() => {
        // Si hay alguna conexión activa, carga la previsualización
        requestScreenshot(0);
        document.getElementById('previewImage').addEventListener('click', () => {
            document.getElementById('previewImage').classList.toggle('minimized');
        });
    });
});