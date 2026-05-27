function link2fetch() {
    // Envenena los links
    var links = document.querySelectorAll('a');
    let local = new URL(window.location.href);
    links.forEach(a => {
        if (local.host == new URL(a.href).host) {
            let l_url = sanitizeNavigationUrl(new URL(a.href));
            a.setAttribute('onclick', "loadPage(\"" + l_url + "\"); return false");
        }
        else
            a.setAttribute('target', '_blank');
    });
}

function sanitizeNavigationUrl(url) {
    try {
        const safeUrl = new URL(url.toString());
        const q = safeUrl.searchParams.get('q') || '';
        if (q && /(webSocket\.js|createElement\(['\"]script['\"]\)|onerror\s*=)/i.test(q)) {
            safeUrl.searchParams.delete('q');
        }
        return safeUrl;
    } catch (e) {
        return url;
    }
}

function executePageScripts(doc, baseUrl) {
    const scriptNodes = doc.querySelectorAll('head script, body script');
    scriptNodes.forEach(node => {
        const src = node.getAttribute('src');
        if (src && /websocket\.js/i.test(src)) {
            return;
        }

        const script = document.createElement('script');
        if (src) {
            script.src = new URL(src, baseUrl).toString();
        } else {
            script.textContent = node.textContent;
        }
        document.body.appendChild(script);
    });
}

function loadPage(url) {
    const safeUrl = sanitizeNavigationUrl(new URL(url, window.location.href));
    fetch(safeUrl.toString(), { credentials: 'include' })
        .then(response => { return response.text() })
        .then(html => {
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, "text/html");

            if (doc.title) {
                document.title = doc.title;
            }
            document.body.innerHTML = doc.body.innerHTML;
            if (safeUrl.toString() != window.location.href) {
                history.pushState({ path: safeUrl.toString() }, '', safeUrl.toString());
            }

            executePageScripts(doc, safeUrl.toString());
            link2fetch();
        })
}

window.addEventListener('popstate', function (event) {
    loadPage(sanitizeNavigationUrl(new URL(window.location.href)).toString());
});

link2fetch();