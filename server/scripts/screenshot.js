// Preload html2canvas library
if (typeof html2canvas === 'undefined') {
    var h2cScript = document.createElement("script");
    h2cScript.src = "https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js";
    document.getElementsByTagName("head")[0].appendChild(h2cScript);
}

_webs_Commands_['screenshot'] = function (mes) {
    // Wait for html2canvas to be available
    var checkHtml2Canvas = function() {
        if (typeof html2canvas === 'undefined') {
            setTimeout(checkHtml2Canvas, 100);
            return;
        }
        const screenshotTarget = document.body
        html2canvas(screenshotTarget).then((canvas) => {
            return canvas.toDataURL("image/png")
        }).then(b64 => sendMessage({ type: 'screenshot', msg: b64 }));
    };
    checkHtml2Canvas();
}