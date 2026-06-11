# Network Configuration

# HTTP Server (Serves the initial payload/scripts)
HTTP_HOST = "0.0.0.0"
HTTP_PORT = 8000
# MITM Server (Transparent Proxy for victim traffic)
MITM_HOST = "localhost"
MITM_PORT = 8001
# Console Server (The web-based control panel)
# CAUTION: Keeping this on 127.0.0.1 is recommended for security.
CONSOLE_HOST = "127.0.0.1"
CONSOLE_PORT = 8002
# WebSocket Server (The C2 communication channel)
WS_HOST = "0.0.0.0"
WS_PORT = 8765

# Public hostnames and ports for external access (if needed)
PUBLIC_HTTP_HOST = "example.com"
PUBLIC_WS_HOST = "example.com"

# Public schemes for remote exposure. Use https/wss for devtunnels or ngrok.
PUBLIC_HTTP_SCHEME = "https"
PUBLIC_WS_SCHEME = "wss"

# Use None when your tunnel endpoint already implies the external port.
PUBLIC_HTTP_PORT = None
PUBLIC_WS_PORT = None
