# SOXSS
Advanced XSS Command and Control (C2) with WebSockets, Per-Session Encryption, and Premium Management Console.

## Requirements
* Python 3.10 or higher
* Recommended: `pip install -r requirements.txt` (includes `aiohttp`, `pycryptodomex`, `websockets`, `Pillow`)

## Installation

1. Clone the repository: `git clone https://github.com/ctpache/SOXSS.git`
2. Install the requirements: `pip install -r requirements.txt`
3. Configure your network settings in `config.py`.
4. Run the server: `python Socxss.py [-f] [-q]`
   - `-f`: Fresh start (cleans console logs and screenshots).
   - `-q`: Quiet mode (hides the banner).

## Testing
SOXSS includes both fast unit tests and browser-based Selenium E2E tests.

Fast suite:
```bash
python -m unittest tests.test_runtime_unit tests.test_modules_unit tests.test_console_commands_unit tests.test_server_modules_unit tests.test_twister_server_unit -v
```

Selenium E2E suite:
```bash
python -m unittest tests.selenium.test_soxss_selenium -v
```

Coverage report for the fast suite:
```bash
coverage run -m unittest tests.test_runtime_unit tests.test_modules_unit tests.test_console_commands_unit tests.test_server_modules_unit tests.test_twister_server_unit -v
coverage report -m
```

## Network Configuration (`config.py`)
All network settings are centralized in `config.py`. You can independently configure:
* **Payload Server**: Serves initial scripts and payloads (default port 8000).
* **C2 WebSockets**: Secure communication channel for victims (default port 8765).
* **Console Server**: Management panel, isolated to `127.0.0.1` by default for security (default port 8002).
* **MITM Server**: Proxy for victim traffic (default port 8001).

## Component Architecture

### 1. The Server (`Socxss.py`)
The heart of the C2. It manages:
- **Per-Session Security**: Uses a unique Session ID (`sid`) and a dedicated AES-256 (CBC) key/IV pair for every connection.
- **WebSocket Gateway**: High-performance async handling using `websockets.asyncio`.
- **Module Routing**: Dispatches messages to specialized modules (Screenshot, Logger, MITM, etc.).

### 2. Premium Management Console
![console](/docs/Terminal_Web.png)
Access it via `http://localhost:8002/` (default). 
Features:
- **Dark Glass UI**: Modern, premium aesthetic with real-time status tracking.
- **Live Victim Sidebar**: Automatically polls and updates with new connections. Shows IP and SID.
- **High-Precision Terminal**: Real-time feedback with timestamps and semantic color-coding.
- **Visual Previews**: Live screenshot gallery for the active victim.

### 3. The Payload (`server/webSocket.js`)
Injected via XSS. It establishes a secure link to the C2.
- **Dynamic Injection**: Payloads are auto-configured with the correct host/port from `config.py` upon request.
- **Persistence**: Includes `link2fetch.js` which "poisons" DOM links to use `fetch` + History API, keeping the session alive during navigation.

## Standard Commands
* `list`: Display all active victim metadata.
* `change <index>`: Switch control to a specific victim.
* `load <script_or_url>`: Inject a remote script URL or inline JavaScript into the victim.
* `screenshot`: Capture a real-time image of the victim's screen.
* `downloadFile <local> <remote>`: Push a file to the victim.
* `disable`: Close the selected victim WebSocket session.
* `exit`: Alias of `disable` in the current implementation.
* `eval <expression>`: Evaluate JavaScript in the victim context and return the result.

UI shortcuts:
- `clear` / `cls`: Clear terminal output in the browser UI only.
- `Ctrl+L`: Clear terminal output in the browser UI.

## Data Management
All session data is organized by `sid` for easy tracking:
- **Screenshots**: Saved in `console/screenshots/{sid}.png` (latest) and `{sid}_{timestamp}.png` (archive).
- **Logs**: Keystrokes and data captures saved in `console/logs/{sid}.log`.

## MITM Proxy
The MITM module allows you to use the victim's browser as a transparent proxy. Open the per-session URL from the console (`mitmUrl`) or use:

`http://<MITM_HOST>:<MITM_PORT>/<sid>/`

Then navigate from that tab to access victim-authenticated resources through the active session.

---
*Disclaimer: This tool is for educational and authorized security testing purposes only.*
