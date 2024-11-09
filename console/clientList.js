// Lista de clientes conectados (simulación de ejemplo)
var clients
// Cargar la lista de clientes
async function loadClientList() {
    clients = await sendConsole('list').then(x => JSON.parse(x.text))
    const clientList = document.getElementById('clientList');
    clientList.innerHTML = '';
    for (const client in clients) {
        const clientButton = document.createElement('button');
        clientButton.textContent = client;
        clientButton.onclick = () => requestScreenshot(client);
        clientList.appendChild(clientButton);
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
    loadClientList();
    requestScreenshot(0);
    // Seleccionar el contenedor de vista previa
    const screenshotPreview = document.getElementById('previewImage');

    // Alternar minimización al hacer clic
    screenshotPreview.addEventListener('click', () => {
        screenshotPreview.classList.toggle('minimized');
    });
});




