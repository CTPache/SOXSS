const webSocketScript = 'webSocket.js'

function link2fetch() {
    // Envenena los links
    var links = document.querySelectorAll('a');
    let local = new URL(window.location.href)
    links.forEach(a => {
        if (local.host == new URL(a.href).host) {
            let l_url = new URL(a.href)
            a.setAttribute('onclick', "loadPage(\"" + l_url + "\"); return false")
        }
        else
            a.setAttribute('target', '_blank')
    });
}
function loadPage(url) {
    fetch(url)
        .then(response => { return response.text() })
        .then(html => {
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, "text/html");
            document.body.innerHTML = doc.body.innerHTML;
            document.head.innerHTML = doc.head.innerHTML;
            history.pushState({ path: url }, '', url);
            link2fetch()
        })
}
link2fetch()