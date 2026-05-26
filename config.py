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
PUBLIC_HTTP_HOST = "192.168.1.10"
PUBLIC_WS_HOST = "192.168.1.10"
PUBLIC_HTTP_PORT = 8000
PUBLIC_WS_PORT = 8765