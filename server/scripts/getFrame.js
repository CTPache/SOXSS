loadScript('scripts/html2canvas.min.js')
_webs_commands_['getFrame'] = function (mes) {
    const screenshotTarget = document.body
    html2canvas(screenshotTarget).then((canvas) => {
        return canvas.toDataURL("image/png")
    }).then(b64 => sendMessage({ type: 2, msg: b64 }));
}