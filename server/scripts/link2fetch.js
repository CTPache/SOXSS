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

let nativeLocationNavigation = null;

function getPropertyDescriptor(target, propertyName) {
    let current = target;
    while (current) {
        const descriptor = Object.getOwnPropertyDescriptor(current, propertyName);
        if (descriptor) {
            return { owner: current, descriptor };
        }
        current = Object.getPrototypeOf(current);
    }
    return null;
}

function toNavigationUrl(value) {
    try {
        return sanitizeNavigationUrl(new URL(value, window.location.href));
    } catch (e) {
        return null;
    }
}

function shouldUseLink2fetchNavigation(url) {
    return !!url
        && /^https?:$/i.test(url.protocol)
        && url.origin === window.location.origin;
}

function shouldInterceptNavigationRequest(url) {
    if (!shouldUseLink2fetchNavigation(url)) {
        return false;
    }

    const currentUrl = new URL(window.location.href);
    return url.pathname !== currentUrl.pathname
        || url.search !== currentUrl.search;
}

function hardNavigate(url, replaceState) {
    if (!nativeLocationNavigation) {
        return;
    }

    if (replaceState && nativeLocationNavigation.replace) {
        nativeLocationNavigation.replace.call(window.location, url.toString());
        return;
    }

    if (nativeLocationNavigation.hrefSetter) {
        nativeLocationNavigation.hrefSetter.call(window.location, url.toString());
        return;
    }

    if (nativeLocationNavigation.assign) {
        nativeLocationNavigation.assign.call(window.location, url.toString());
    }
}

function interceptLocationNavigation(value, replaceState) {
    const safeUrl = toNavigationUrl(value);
    if (!shouldUseLink2fetchNavigation(safeUrl)) {
        return false;
    }

    loadPage(safeUrl.toString(), { replaceState: !!replaceState, fallbackToHardNavigation: true });
    return true;
}

function installLocationNavigationShim() {
    if (nativeLocationNavigation) {
        return;
    }

    const locationObject = window.location;
    if (!locationObject) {
        nativeLocationNavigation = {};
        return;
    }

    const hrefInfo = getPropertyDescriptor(locationObject, 'href');
    const assignInfo = getPropertyDescriptor(locationObject, 'assign');
    const replaceInfo = getPropertyDescriptor(locationObject, 'replace');

    const hrefDescriptor = hrefInfo && hrefInfo.descriptor;
    const assign = assignInfo && typeof assignInfo.descriptor.value === 'function' ? assignInfo.descriptor.value : locationObject.assign;
    const replace = replaceInfo && typeof replaceInfo.descriptor.value === 'function' ? replaceInfo.descriptor.value : locationObject.replace;

    nativeLocationNavigation = {
        assign: typeof assign === 'function' ? assign : null,
        replace: typeof replace === 'function' ? replace : null,
        hrefSetter: hrefDescriptor && typeof hrefDescriptor.set === 'function' ? hrefDescriptor.set : null,
    };

    if (assignInfo && assignInfo.owner && assignInfo.descriptor.writable && typeof assign === 'function') {
        assignInfo.owner.assign = function (value) {
            if (!interceptLocationNavigation(value, false)) {
                return assign.call(this, value);
            }
        };
    }

    if (replaceInfo && replaceInfo.owner && replaceInfo.descriptor.writable && typeof replace === 'function') {
        replaceInfo.owner.replace = function (value) {
            if (!interceptLocationNavigation(value, true)) {
                return replace.call(this, value);
            }
        };
    }

    if (hrefInfo && hrefInfo.owner && hrefDescriptor && hrefDescriptor.configurable && typeof hrefDescriptor.get === 'function' && typeof hrefDescriptor.set === 'function') {
        Object.defineProperty(hrefInfo.owner, 'href', {
            configurable: true,
            enumerable: hrefDescriptor.enumerable,
            get: function () {
                return hrefDescriptor.get.call(this);
            },
            set: function (value) {
                if (!interceptLocationNavigation(value, false)) {
                    return hrefDescriptor.set.call(this, value);
                }
            },
        });
    }
}

function installNavigationApiShim() {
    if (!window.navigation || typeof window.navigation.addEventListener !== 'function') {
        return;
    }

    window.navigation.addEventListener('navigate', function (event) {
        if (!event.canIntercept || event.hashChange || event.formData) {
            return;
        }

        const destinationUrl = toNavigationUrl(event.destination && event.destination.url);
        if (!shouldInterceptNavigationRequest(destinationUrl)) {
            return;
        }

        event.intercept({
            handler: function () {
                return loadPage(destinationUrl.toString(), {
                    fallbackToHardNavigation: true,
                    skipHistoryUpdate: true,
                });
            },
        });
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

function collectPageScripts(doc, baseUrl) {
    return Array.from(doc.querySelectorAll('head script, body script'))
        .map((node, index) => {
            const src = node.getAttribute('src');
            if (src && /websocket\.js/i.test(src)) {
                return null;
            }

            return {
                index: index,
                src: src ? new URL(src, baseUrl).toString() : null,
                text: src ? null : (node.textContent || ''),
            };
        })
        .filter(Boolean);
}

function stripPageScripts(doc) {
    doc.querySelectorAll('script').forEach(node => node.remove());
}

function buildPageScriptBundle(scripts) {
    return scripts.reduce((chain, scriptInfo) => {
        return chain.then(parts => {
            if (!scriptInfo.src) {
                parts.push('\n/* inline script ' + scriptInfo.index + ' */\n' + scriptInfo.text);
                return parts;
            }

            return fetch(scriptInfo.src, { credentials: 'include' })
                .then(response => response.text())
                .then(source => {
                    parts.push('\n/* ' + scriptInfo.src + ' */\n' + source + '\n//# sourceURL=' + scriptInfo.src);
                    return parts;
                });
        });
    }, Promise.resolve([])).then(parts => parts.join('\n;\n'));
}

function executePageScripts(scripts) {
    return buildPageScriptBundle(scripts).then(source => {
        if (!source.trim()) {
            return;
        }

        const script = document.createElement('script');
        script.textContent = '(function () {\n' + source + '\n})();';
        document.body.appendChild(script);
        script.remove();
    });
}

function notifyNavigationHooks(url) {
    document.dispatchEvent(new CustomEvent('link2fetch:load', {
        detail: { url: url.toString() },
    }));
}

function loadPage(url, options = {}) {
    const replaceState = !!options.replaceState;
    const fallbackToHardNavigation = !!options.fallbackToHardNavigation;
    const skipHistoryUpdate = !!options.skipHistoryUpdate;
    const safeUrl = sanitizeNavigationUrl(new URL(url, window.location.href));
    return fetch(safeUrl.toString(), { credentials: 'include' })
        .then(response => { return response.text() })
        .then(html => {
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, "text/html");
            const pageScripts = collectPageScripts(doc, safeUrl.toString());

            stripPageScripts(doc);

            if (doc.title) {
                document.title = doc.title;
            }
            document.body.innerHTML = doc.body.innerHTML;
            if (!skipHistoryUpdate && safeUrl.toString() != window.location.href) {
                const historyMethod = replaceState ? 'replaceState' : 'pushState';
                history[historyMethod]({ path: safeUrl.toString() }, '', safeUrl.toString());
            }

            return executePageScripts(pageScripts)
                .then(() => {
                    link2fetch();
                    notifyNavigationHooks(safeUrl);
                });
        })
        .catch(() => {
            if (fallbackToHardNavigation) {
                hardNavigate(safeUrl, replaceState);
            }
        });
}

window.addEventListener('popstate', function (event) {
    loadPage(sanitizeNavigationUrl(new URL(window.location.href)).toString());
});

installNavigationApiShim();
installLocationNavigationShim();
link2fetch();