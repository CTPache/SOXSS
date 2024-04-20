loadScript('scripts/html2canvas.min.js')
_webs_commands_['screenshot'] = function (mes) {
    const screenshotTarget = document.body
    html2canvas(screenshotTarget).then((canvas) => {
        return canvas.toDataURL("image/png")
    }).then(b64 => sendMessage({ type: 'screenshot', msg: b64 }));
}