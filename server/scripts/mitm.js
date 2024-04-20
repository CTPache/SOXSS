_webs_commands_['mitm'] = function (mes) {
    let msg = { url: mes.url, content: '<p>Not found</p>', contentType: 'text/html', method: mes.method ? mes.method : 'GET' }
    let toRequest = { method: msg['method'] }
    if (!(toRequest.method == 'GET'))
        toRequest.body = 'body' in mes ? mes.body : ''
    fetch(mes['url'], toRequest).then(
        response =>
            response.blob().then(
                blob => blob.text().then(text => { msg.contentType = blob.type; msg.content = text }))).then(() =>
                    sendMessage({ type: 'mitm', msg: msg }))
}