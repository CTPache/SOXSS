# SOXSS

SOXSS is an XSS command-and-control lab that serves an injectable browser payload, maintains one encrypted WebSocket channel per victim session, and exposes a local web console for operator control. The repository also includes a realistic demo target, `twister/`, plus unit and Selenium coverage for the main runtime paths.

## What The Project Includes

- `Socxss.py`: starts the payload HTTP server, the WebSocket C2 server, and the local console server.
- `server/`: serves `webSocket.js` and related client-side scripts, injecting per-session crypto material and public endpoint settings on demand.
- `modules/`: screenshot, logger, MITM, console, and related message handlers.
- `console/`: browser UI for listing victims, selecting a target, issuing commands, and viewing output.
- `twister/`: demo social application used for local testing and XSS exercises.
- `tests/`: fast unit tests plus Selenium end-to-end tests.

## Requirements

- Python 3.10+
- A virtual environment is recommended
- `pip install -r requirements.txt`

Current Python dependencies in `requirements.txt` are:

- `websockets`
- `pillow`
- `pycryptodome`
- `aiohttp`
- `requests`
- `selenium`
- `coverage`

## Quick Start

1. Create and activate a virtual environment.
2. Install dependencies.
3. Adjust `config.py` if the default ports or public hosts are not suitable.
4. Start SOXSS.

Example:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python .\Socxss.py
```

Default local endpoints:

- Payload server: `http://0.0.0.0:8000/`
- WebSocket C2: `ws://0.0.0.0:8765/<sid>`
- Console: `http://127.0.0.1:8002/index.html`
- MITM proxy base: `http://localhost:8001/<sid>/`

Useful runtime flags:

- `-f`, `--fresh-start`: remove files under `console/screenshots/` and `console/logs/` before startup.
- `-q`, `--quiet`: suppress the startup banner.

## Runtime Configuration

All default network settings live in `config.py`:

- `HTTP_HOST`, `HTTP_PORT`: payload/script server
- `WS_HOST`, `WS_PORT`: WebSocket C2 listener
- `CONSOLE_HOST`, `CONSOLE_PORT`: local operator console
- `MITM_HOST`, `MITM_PORT`: per-session MITM proxy base
- `PUBLIC_HTTP_*`, `PUBLIC_WS_*`: externally visible host, scheme, and optional port used when generating the injected payload

In addition to editing `config.py`, SOXSS can override any uppercase config value directly from the command line at startup. Both standard and colon forms are accepted.

Examples:

```powershell
python .\Socxss.py --HTTP_HOST 127.0.0.1 --HTTP_PORT 9000
python .\Socxss.py --PUBLIC_HTTP_HOST attacker.example --PUBLIC_WS_HOST attacker.example
python .\Socxss.py --PUBLIC_HTTP_SCHEME https --PUBLIC_WS_SCHEME wss --PUBLIC_HTTP_PORT None --PUBLIC_WS_PORT None
python .\Socxss.py --HTTP_HOST: 192.168.1.20 --WS_PORT:8765
```

## How It Works

When a victim loads `server/webSocket.js`, the HTTP server generates a fresh session identifier (`sid`) and session-specific crypto material. That payload connects back to the configured WebSocket server, and incoming messages are routed to modules based on their `type` field.

The main built-in behaviors are:

- `screenshot`: captures browser screenshots and stores both latest and archived copies under `console/screenshots/`.
- `log`: appends captured lines to `console/logs/<sid>.log`.
- `mitm`: uses the victim browser as a session-bound proxy path.
- `console`: forwards command results back into the local operator UI.

The payload also ships helper scripts such as `link2fetch.js` so the injected session can survive same-origin navigation more reliably during demos.

## Console Commands

The current command registry is implemented in `modules/consoleCommands/`.

- `list`: show connected sockets with metadata such as SID, IP, and MITM URL.
- `change <index>`: switch the active target socket by list index.
- `eval <expression>`: execute JavaScript in the current victim context.
- `load <script>`: send inline JavaScript or a script-loading stub to the victim.
- `screenshot`: request a screenshot from the active victim.
- `downloadFile <local_path> <remote_name>`: send a local file to the victim, base64-encoded in the command payload.
- `disable`: instruct the active victim to close the session.
- `exit`: alias for `disable`.
- `ok`: send a basic acknowledgement payload.

The browser console UI also supports local-only clearing shortcuts such as `clear`, `cls`, and `Ctrl+L` without affecting the victim session.

## Demo Target: Twister

`twister/` is the bundled victim application used by the automated tests and local demonstrations. It is an `aiohttp` application with:

- register/login/logout flows
- server-side session handling
- a paginated feed
- per-user profile pages
- JSON registry files under `twister/registry/`

Run it locally with:

```powershell
python .\twister\server.py
```

By default it listens on `http://127.0.0.1:7070/` in the integrated Selenium workflow.

## Testing

Fast unit suite:

```powershell
python -m unittest tests.test_runtime_unit tests.test_modules_unit tests.test_console_commands_unit tests.test_server_modules_unit tests.test_twister_server_unit -v
```

Browser-based Selenium suite:

```powershell
python -m unittest tests.selenium.test_soxss_selenium -v
```

Coverage for the fast suite:

```powershell
coverage run -m unittest tests.test_runtime_unit tests.test_modules_unit tests.test_console_commands_unit tests.test_server_modules_unit tests.test_twister_server_unit -v
coverage report -m
```

The integrated Selenium runner starts both SOXSS and Twister through `tests/selenium/run_soxss_victim_local.py`, injects a deterministic stored XSS into the demo feed, then validates `screenshot`, `logger`, `mitm`, and `downloadFile` behavior end to end.

## Cloudflare Tunnel Workflow

The repository includes PowerShell helpers for exposing the lab with Cloudflare quick tunnels.

- `scripts/deploy_cloudflare.ps1`: starts tunnels for the payload server and WebSocket endpoint, prints the public URLs, and can optionally launch SOXSS with matching `PUBLIC_*` CLI overrides.
- `scripts/start_all_cloudflare.ps1`: prepares `.venv`, installs missing dependencies, starts `twister/server.py` on port `7070`, ensures `cloudflared` is available, and then calls the deploy script.
- `scripts/stop_all.ps1`: stops SOXSS, Twister, and tunnel processes. Use `-IncludeNode` if you also want to stop Node-based helpers.

Examples:

```powershell
.\scripts\deploy_cloudflare.ps1 -NoRun
.\scripts\start_all_cloudflare.ps1 -FreshStart
.\scripts\stop_all.ps1
```

## Repository Notes

- Screenshots are created on demand in `console/screenshots/`.
- Logger output is created on demand in `console/logs/`.
- The console is intentionally bound to `127.0.0.1` by default; keep it local unless you add your own access controls.
- The payload server injects session keys, IVs, and public endpoint data dynamically into `server/webSocket.js`; that file is not served as a static literal.

## Disclaimer

This project is for authorized security research, controlled demonstrations, and educational use only.
