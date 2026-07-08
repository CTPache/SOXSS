import asyncio
import io
import importlib
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from aiohttp import web

import modules.ConsoleServer as console_server
import modules.MITMServer as mitm_server
import server.server as payload_server
import socksUtil


VALID_SID = "a" * 32


class DummyRequest:
    def __init__(self, body):
        self._body = body

    async def text(self):
        return self._body


class SocksUtilStateMixin:
    def setUp(self):
        super().setUp()
        self._orig_sockets = list(socksUtil.sockets)
        self._orig_current = socksUtil.current
        socksUtil.sockets.clear()
        socksUtil.current = 0
        self.addCleanup(self._restore_sockets)

    def _restore_sockets(self):
        socksUtil.sockets[:] = self._orig_sockets
        socksUtil.current = self._orig_current


class TestConsoleServer(SocksUtilStateMixin, unittest.IsolatedAsyncioTestCase):
    async def test_handle_post_sends_command_and_returns_updated_console_output(self):
        socket = SimpleNamespace(remote_ip="10.0.0.3")
        socksUtil.sockets.append(socket)
        request = DummyRequest("list")

        async def fake_send_message(target_socket, body):
            self.assertIs(target_socket, socket)
            self.assertEqual(body, "list")
            console_server.consoleOut = '{"outputType": "info", "text": "done"}'

        console_server.consoleMod = SimpleNamespace(sendMessage=AsyncMock(side_effect=fake_send_message))
        console_server.consoleOut = "old"

        response = await console_server.handle_post(request)

        self.assertEqual(response.status, 200)
        self.assertEqual(response.text, '{"outputType": "info", "text": "done"}')
        self.assertEqual(response.headers["Access-Control-Allow-Origin"], "*")

    async def test_handle_post_works_without_active_socket_and_timeout_change(self):
        request = DummyRequest("help")
        console_server.consoleMod = SimpleNamespace(sendMessage=AsyncMock())
        console_server.consoleOut = '{"outputType": "info", "text": "stale"}'

        with patch("modules.ConsoleServer.asyncio.sleep", new=AsyncMock()) as sleep_mock:
            response = await console_server.handle_post(request)

        console_server.consoleMod.sendMessage.assert_awaited_once_with("", "help")
        self.assertEqual(response.text, '{"outputType": "info", "text": "stale"}')
        self.assertEqual(sleep_mock.await_count, 1000)

    async def test_handle_post_returns_error_payload_when_send_message_raises(self):
        request = DummyRequest("eval 1")
        console_server.consoleMod = SimpleNamespace(sendMessage=AsyncMock(side_effect=RuntimeError("socket closed")))
        console_server.consoleOut = "old"

        with patch("modules.ConsoleServer.asyncio.sleep", new=AsyncMock()):
            response = await console_server.handle_post(request)

        payload = json.loads(response.text)
        self.assertEqual(payload["outputType"], "error")
        self.assertIn("command handling failed", payload["text"])

    async def test_handle_static_serves_existing_file(self):
        with TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "index.html"
            file_path.write_text("hello", encoding="utf-8")
            request = SimpleNamespace(match_info={"filename": "index.html"})

            with patch.object(console_server, "STATIC_DIR", tmpdir):
                response = await console_server.handle_static(request)

        self.assertIsInstance(response, web.FileResponse)
        self.assertEqual(response.headers["Access-Control-Allow-Origin"], "*")

    async def test_handle_static_returns_404_for_missing_file(self):
        request = SimpleNamespace(match_info={"filename": "missing.txt"})

        with TemporaryDirectory() as tmpdir, patch.object(console_server, "STATIC_DIR", tmpdir):
            response = await console_server.handle_static(request)

        self.assertEqual(response.status, 404)
        self.assertEqual(response.text, "Not found")

    def test_setup_routes_registers_handlers(self):
        app = MagicMock()
        app.router = MagicMock()

        console_server.setup_routes(app)

        app.router.add_post.assert_called_once_with('/', console_server.handle_post)
        self.assertEqual(app.router.add_get.call_count, 2)
        app.router.add_get.assert_any_call('/config', console_server.handle_config)
        app.router.add_get.assert_any_call('/{filename:.*}', console_server.handle_static)

    async def test_start_async_console_server_bootstraps_site(self):
        fake_runner = MagicMock()
        fake_runner.setup = AsyncMock()
        fake_site = MagicMock()
        fake_site.start = AsyncMock()
        console_module = object()

        with patch("modules.ConsoleServer.web.Application", return_value="app") as app_ctor, patch(
            "modules.ConsoleServer.setup_routes"
        ) as setup_routes, patch("modules.ConsoleServer.web.AppRunner", return_value=fake_runner) as runner_ctor, patch(
            "modules.ConsoleServer.web.TCPSite", return_value=fake_site
        ) as site_ctor, patch("modules.ConsoleServer.asyncio.sleep", new=AsyncMock(side_effect=RuntimeError("stop"))), patch(
            "builtins.print"
        ):
            with self.assertRaisesRegex(RuntimeError, "stop"):
                await console_server.start_async_console_server(console_module)

        self.assertIs(console_server.consoleMod, console_module)
        app_ctor.assert_called_once_with()
        setup_routes.assert_called_once_with("app")
        runner_ctor.assert_called_once_with(fake_runner.setup.call_args_list and "app" or "app")
        site_ctor.assert_called_once_with(fake_runner, console_server.config.CONSOLE_HOST, console_server.config.CONSOLE_PORT)
        fake_runner.setup.assert_awaited_once_with()
        fake_site.start.assert_awaited_once_with()

    async def test_handle_config_returns_public_http_settings(self):
        response = await console_server.handle_config(SimpleNamespace())

        data = json.loads(response.text)
        self.assertEqual(data["http_host"], console_server.config.PUBLIC_HTTP_HOST)
        self.assertEqual(data["http_port"], console_server.config.PUBLIC_HTTP_PORT)
        self.assertEqual(response.headers["Access-Control-Allow-Origin"], "*")

    def test_build_public_http_base_covers_host_and_port_variants(self):
        with patch.object(console_server.config, "PUBLIC_HTTP_HOST", ""):
            self.assertEqual(console_server._build_public_http_base(), "")

        with patch.object(console_server.config, "PUBLIC_HTTP_HOST", "example.com"), patch.object(
            console_server.config, "PUBLIC_HTTP_SCHEME", "https"
        ), patch.object(console_server.config, "PUBLIC_HTTP_PORT", None):
            self.assertEqual(console_server._build_public_http_base(), "https://example.com/")

        with patch.object(console_server.config, "PUBLIC_HTTP_HOST", "example.com"), patch.object(
            console_server.config, "PUBLIC_HTTP_SCHEME", "https"
        ), patch.object(console_server.config, "PUBLIC_HTTP_PORT", 9000):
            self.assertEqual(console_server._build_public_http_base(), "https://example.com:9000/")

        with patch.object(console_server.config, "PUBLIC_HTTP_HOST", "host:1234"), patch.object(
            console_server.config, "PUBLIC_HTTP_PORT", 9000
        ):
            # A host that already carries a port must not get a second one appended.
            self.assertTrue(console_server._build_public_http_base().endswith("host:1234/"))


class TestPayloadServerHelpers(unittest.IsolatedAsyncioTestCase):
    def test_clean_public_host_strips_schemes_and_slashes(self):
        self.assertEqual(payload_server._clean_public_host("http://example.com/"), "example.com")
        self.assertEqual(payload_server._clean_public_host("https://example.com"), "example.com")
        self.assertEqual(payload_server._clean_public_host("ws://example.com/"), "example.com")
        self.assertEqual(payload_server._clean_public_host("wss://example.com"), "example.com")
        self.assertEqual(payload_server._clean_public_host("  plain.host  "), "plain.host")
        self.assertEqual(payload_server._clean_public_host(None), "")

    def test_host_has_explicit_port_handles_ipv6_and_hostname(self):
        self.assertTrue(payload_server._host_has_explicit_port("[::1]:8080"))
        self.assertFalse(payload_server._host_has_explicit_port("[::1]"))
        self.assertTrue(payload_server._host_has_explicit_port("example.com:443"))
        self.assertFalse(payload_server._host_has_explicit_port("example.com"))

    def test_build_public_base_url_covers_all_branches(self):
        self.assertEqual(payload_server._build_public_base_url("https", "", None), "")
        self.assertEqual(payload_server._build_public_base_url("https", "example.com", 8443), "https://example.com:8443")
        self.assertEqual(payload_server._build_public_base_url("https", "example.com:443", 8443), "https://example.com:443")
        self.assertEqual(payload_server._build_public_base_url("https", "example.com", None), "https://example.com")

    async def test_cors_middleware_handles_preflight_and_passthrough(self):
        async def handler(_request):
            return web.Response(text="ok")

        passthrough = await payload_server.cors_middleware(SimpleNamespace(method="GET"), handler)
        self.assertEqual(passthrough.text, "ok")
        self.assertEqual(passthrough.headers["Access-Control-Allow-Origin"], "*")

        preflight = await payload_server.cors_middleware(SimpleNamespace(method="OPTIONS"), handler)
        self.assertEqual(preflight.status, 200)
        self.assertEqual(preflight.headers["Access-Control-Allow-Methods"], "GET,POST,PUT,DELETE,OPTIONS")


class TestPayloadServer(unittest.IsolatedAsyncioTestCase):
    async def test_handle_static_returns_404_for_missing_file(self):
        request = SimpleNamespace(match_info={"filename": "missing.txt"})

        with TemporaryDirectory() as tmpdir, patch.object(payload_server, "STATIC_DIR", tmpdir):
            response = await payload_server.handle_static(request)

        self.assertEqual(response.status, 404)
        self.assertEqual(response.text, "Not found")

    async def test_handle_static_serves_regular_file(self):
        with TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "plain.js"
            file_path.write_text("console.log('ok');", encoding="utf-8")
            request = SimpleNamespace(match_info={"filename": "plain.js"})

            with patch.object(payload_server, "STATIC_DIR", tmpdir):
                response = await payload_server.handle_static(request)

        self.assertIsInstance(response, web.FileResponse)
        self.assertEqual(response.headers["Access-Control-Allow-Origin"], "*")

    async def test_handle_static_injects_runtime_values_into_websocket_payload(self):
        with TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "webSocket.js"
            file_path.write_text("$key|$IV|$sid|$hbase|$wsbase|$hhost|$whost|$wport|$hport", encoding="utf-8")
            request = SimpleNamespace(match_info={"filename": "webSocket.js"})

            with patch.object(payload_server, "STATIC_DIR", tmpdir), patch(
                "server.server.cryptoUtil.generate_key_iv", return_value=("secret-key", "deadbeef")
            ), patch("server.server.cryptoUtil.set_key_iv") as set_key_iv, patch(
                "uuid.uuid4", return_value=SimpleNamespace(hex="sid-123")
            ):
                response = await payload_server.handle_static(request)

        self.assertEqual(response.status, 200)
        self.assertEqual(response.content_type, "application/javascript")
        self.assertIn("secret-key", response.text)
        self.assertIn("deadbeef", response.text)
        self.assertIn("sid-123", response.text)
        self.assertIn(payload_server.config.PUBLIC_HTTP_HOST, response.text)
        self.assertIn(payload_server.config.PUBLIC_WS_HOST, response.text)
        self.assertIn(payload_server.config.PUBLIC_HTTP_SCHEME, response.text)
        self.assertIn(payload_server.config.PUBLIC_WS_SCHEME, response.text)
        hport = '' if payload_server.config.PUBLIC_HTTP_PORT in (None, '', 0, '0') else str(payload_server.config.PUBLIC_HTTP_PORT)
        wport = '' if payload_server.config.PUBLIC_WS_PORT in (None, '', 0, '0') else str(payload_server.config.PUBLIC_WS_PORT)
        self.assertIn(hport, response.text)
        self.assertIn(wport, response.text)
        set_key_iv.assert_called_once_with("sid-123", "secret-key", "deadbeef")

    def test_setup_routes_registers_static_handler(self):
        app = MagicMock()
        app.router = MagicMock()

        payload_server.setup_routes(app)

        app.router.add_get.assert_called_once_with('/{filename:.*}', payload_server.handle_static)

    async def test_start_async_server_bootstraps_site(self):
        fake_runner = MagicMock()
        fake_runner.setup = AsyncMock()
        fake_site = MagicMock()
        fake_site.start = AsyncMock()

        with patch("server.server.web.Application", return_value="app") as app_ctor, patch(
            "server.server.setup_routes"
        ) as setup_routes, patch("server.server.web.AppRunner", return_value=fake_runner) as runner_ctor, patch(
            "server.server.web.TCPSite", return_value=fake_site
        ) as site_ctor, patch("server.server.asyncio.sleep", new=AsyncMock(side_effect=RuntimeError("stop"))), patch(
            "builtins.print"
        ):
            with self.assertRaisesRegex(RuntimeError, "stop"):
                await payload_server.start_async_server()

        app_ctor.assert_called_once()
        self.assertIn("middlewares", app_ctor.call_args.kwargs)
        setup_routes.assert_called_once_with("app")
        runner_ctor.assert_called_once_with("app")
        site_ctor.assert_called_once_with(fake_runner, payload_server.config.HTTP_HOST, payload_server.config.HTTP_PORT)
        fake_runner.setup.assert_awaited_once_with()
        fake_site.start.assert_awaited_once_with()


class TestMITMServer(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        super().setUp()
        mitm_server.cache.clear()
        self.addCleanup(mitm_server.cache.clear)

    async def test_perform_request_forwards_and_rewrites_links(self):
        handler = object.__new__(mitm_server.MITMHTTPRequestHandler)
        handler.path = f"/{VALID_SID}/path/to/resource"
        handler.headers = {}
        handler.rfile = io.BytesIO()
        handler.wfile = io.BytesIO()
        handler.send_response = MagicMock()
        handler.send_header = MagicMock()
        handler.end_headers = MagicMock()

        async def fake_send_message(socket, payload):
            mitm_server.cache["fixed-key"] = {
                "type": "text/html",
                "content": '<a href="/next">next</a>',
                "method": "GET",
            }

        with patch("modules.MITMServer.socksUtil.getSocketBySid", return_value=object()), patch(
            "modules.MITMServer.cryptoUtil.sendSecretMessage", new=AsyncMock(side_effect=fake_send_message)
        ), patch("modules.MITMServer.datetime.datetime") as datetime_mock, patch("builtins.print"):
            datetime_mock.now.return_value = "fixed-key"
            await mitm_server.MITMHTTPRequestHandler.performRequest(handler, "GET")

        handler.send_response.assert_called_once_with(200)
        handler.send_header.assert_any_call("Content-type", "text/html")
        handler.send_header.assert_any_call("Access-Control-Allow-Origin", "*")
        self.assertEqual(handler.wfile.getvalue().decode("utf-8"), f'<a href="/{VALID_SID}/next">next</a>')
        self.assertNotIn("fixed-key", mitm_server.cache)

    async def test_perform_request_returns_404_without_socket(self):
        handler = object.__new__(mitm_server.MITMHTTPRequestHandler)
        handler.path = "/page?__soxss_sid=missing-sid"
        handler.headers = {}
        handler.rfile = io.BytesIO()
        handler.wfile = io.BytesIO()
        handler.send_response = MagicMock()
        handler.send_header = MagicMock()
        handler.end_headers = MagicMock()

        with patch("modules.MITMServer.socksUtil.getSocketBySid", return_value=None), patch(
            "modules.MITMServer.datetime.datetime"
        ) as datetime_mock, patch("builtins.print"):
            datetime_mock.now.return_value = "fixed-key"
            await mitm_server.MITMHTTPRequestHandler.performRequest(handler, "GET")

        handler.send_response.assert_called_once_with(404)
        self.assertIn("Request error for SID missing-sid", handler.wfile.getvalue().decode("utf-8"))

    async def test_perform_request_ignores_favicon(self):
        handler = object.__new__(mitm_server.MITMHTTPRequestHandler)
        handler.path = "/favicon.ico"
        handler.send_response = MagicMock()

        await mitm_server.MITMHTTPRequestHandler.performRequest(handler, "GET")

        handler.send_response.assert_not_called()

    async def test_perform_request_returns_404_for_empty_path(self):
        handler = object.__new__(mitm_server.MITMHTTPRequestHandler)
        handler.path = "/"
        handler.headers = {}
        handler.rfile = io.BytesIO()
        handler.wfile = io.BytesIO()
        handler.send_response = MagicMock()
        handler.send_header = MagicMock()
        handler.end_headers = MagicMock()

        await mitm_server.MITMHTTPRequestHandler.performRequest(handler, "GET")

        handler.send_response.assert_called_once_with(404)
        self.assertEqual(handler.wfile.getvalue().decode("utf-8"), "Missing SID")
        handler.end_headers.assert_called_once_with()

    async def test_perform_request_ignores_websocket_js(self):
        handler = object.__new__(mitm_server.MITMHTTPRequestHandler)
        handler.path = "/webSocket.js?__soxss_sid=query-sid"
        handler.headers = {}
        handler.send_response = MagicMock()

        await mitm_server.MITMHTTPRequestHandler.performRequest(handler, "GET")

        handler.send_response.assert_not_called()

    async def test_perform_request_for_post_reads_body_and_writes_binary_content(self):
        handler = object.__new__(mitm_server.MITMHTTPRequestHandler)
        handler.path = f"/{VALID_SID}/upload"
        handler.headers = {"Content-Length": "7", "Content-Type": "application/json"}
        handler.rfile = io.BytesIO(b"payload")
        handler.wfile = io.BytesIO()
        handler.send_response = MagicMock()
        handler.send_header = MagicMock()
        handler.end_headers = MagicMock()

        async def fake_send_message(socket, payload):
            self.assertIn('"body": "payload"', payload)
            self.assertIn('"contentType": "application/json"', payload)
            mitm_server.cache["fixed-key"] = {
                "type": "application/octet-stream",
                "content": b"BIN",
                "method": "POST",
            }

        with patch("modules.MITMServer.socksUtil.getSocketBySid", return_value=object()), patch(
            "modules.MITMServer.cryptoUtil.sendSecretMessage", new=AsyncMock(side_effect=fake_send_message)
        ), patch("modules.MITMServer.datetime.datetime") as datetime_mock, patch("builtins.print"):
            datetime_mock.now.return_value = "fixed-key"
            await mitm_server.MITMHTTPRequestHandler.performRequest(handler, "POST")

        handler.send_response.assert_called_once_with(200)
        handler.send_header.assert_any_call("Content-type", "application/octet-stream")
        self.assertEqual(handler.wfile.getvalue(), b"BIN")

    async def test_perform_request_waits_until_cache_entry_exists(self):
        handler = object.__new__(mitm_server.MITMHTTPRequestHandler)
        handler.path = f"/{VALID_SID}/pending"
        handler.headers = {}
        handler.rfile = io.BytesIO()
        handler.wfile = io.BytesIO()
        handler.send_response = MagicMock()
        handler.send_header = MagicMock()
        handler.end_headers = MagicMock()

        async def fake_send_message(socket, payload):
            return None

        async def fake_sleep(_delay):
            mitm_server.cache["fixed-key"] = {
                "type": "text/plain",
                "content": "done",
                "method": "GET",
            }

        with patch("modules.MITMServer.socksUtil.getSocketBySid", return_value=object()), patch(
            "modules.MITMServer.cryptoUtil.sendSecretMessage", new=AsyncMock(side_effect=fake_send_message)
        ), patch("modules.MITMServer.asyncio.sleep", new=AsyncMock(side_effect=fake_sleep)) as sleep_mock, patch(
            "modules.MITMServer.datetime.datetime"
        ) as datetime_mock, patch("builtins.print"):
            datetime_mock.now.return_value = "fixed-key"
            await mitm_server.MITMHTTPRequestHandler.performRequest(handler, "GET")

        sleep_mock.assert_awaited()
        self.assertEqual(handler.wfile.getvalue().decode("utf-8"), "done")

    def test_do_http_verbs_delegate_to_asyncio_run(self):
        handler = object.__new__(mitm_server.MITMHTTPRequestHandler)

        async def fake_perform_request(method):
            return method

        handler.performRequest = fake_perform_request

        def fake_run(coro):
            coro.close()

        with patch("modules.MITMServer.asyncio.run", side_effect=fake_run) as run_mock:
            handler.do_GET()
            handler.do_POST()
            handler.do_PUT()
            handler.do_PATCH()
            handler.do_DELETE()

        self.assertEqual(run_mock.call_count, 5)

    def test_do_options_returns_cors_headers(self):
        handler = object.__new__(mitm_server.MITMHTTPRequestHandler)
        handler.send_response = MagicMock()
        handler.send_header = MagicMock()
        handler.end_headers = MagicMock()

        handler.do_OPTIONS()

        handler.send_response.assert_called_once_with(200)
        handler.send_header.assert_any_call("Access-Control-Allow-Origin", "*")
        handler.send_header.assert_any_call("Access-Control-Allow-Methods", "GET, POST, PUT, PATCH, DELETE, OPTIONS")
        handler.send_header.assert_any_call("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With")
        handler.send_header.assert_any_call("Access-Control-Max-Age", "86400")
        handler.end_headers.assert_called_once_with()

    def test_log_message_returns_empty_string(self):
        handler = object.__new__(mitm_server.MITMHTTPRequestHandler)
        self.assertEqual(handler.log_message("format %s", "x"), "")

    def test_start_server_bootstraps_http_server(self):
        fake_httpd = MagicMock()

        with patch("modules.MITMServer.HTTPServer", return_value=fake_httpd) as http_server, patch("builtins.print"):
            mitm_server.start_server(module=object())

        http_server.assert_called_once()
        fake_httpd.serve_forever.assert_called_once_with()


class TestMITMRewriters(unittest.TestCase):
    def test_prefix_root_relative_path_rules(self):
        self.assertEqual(mitm_server.prefix_root_relative_path("/a", "sid"), "/sid/a")
        self.assertEqual(mitm_server.prefix_root_relative_path("//cdn/x", "sid"), "//cdn/x")
        self.assertEqual(mitm_server.prefix_root_relative_path("relative", "sid"), "relative")
        self.assertIsNone(mitm_server.prefix_root_relative_path(None, "sid"))

    def test_rewrite_srcset_value_prefixes_each_candidate(self):
        out = mitm_server.rewrite_srcset_value("/a.png 1x, /b.png 2x , ,", "sid")
        self.assertEqual(out, "/sid/a.png 1x, /sid/b.png 2x")

    def test_rewrite_css_for_mitm_rewrites_imports_and_urls(self):
        css = "@import '/x.css'; a{background:url('/y.png')} b{background:url(/z.png)}"
        out = mitm_server.rewrite_css_for_mitm(css, "sid")
        self.assertIn("/sid/x.css", out)
        self.assertIn("/sid/y.png", out)
        self.assertIn("/sid/z.png", out)

    def test_rewrite_html_injects_base_and_bootstrap_with_head(self):
        html = '<html><head><base href="/old"><link href="/style.css"></head><body><a href="/p">x</a></body></html>'
        out = mitm_server.rewrite_html_for_mitm(html, "sid")
        self.assertIn('<base href="/sid/">', out)
        self.assertNotIn('href="/old"', out)
        self.assertIn('const sid = "sid"', out)  # build_proxy_bootstrap output
        self.assertIn('href="/sid/style.css"', out)

    def test_rewrite_html_injects_bootstrap_before_body_without_head(self):
        out = mitm_server.rewrite_html_for_mitm("<body><p>hi</p></body>", "sid")
        self.assertIn("normalizeVisibleUrl", out)
        self.assertIn("<body>", out)

    def test_rewrite_html_falls_back_when_markup_has_no_head_or_body(self):
        out = mitm_server.rewrite_html_for_mitm("<html>content</html>", "sid")
        self.assertIn('<base href="/sid/">', out)
        self.assertIn("normalizeVisibleUrl", out)

    def test_rewrite_html_returns_plain_text_unchanged(self):
        self.assertEqual(mitm_server.rewrite_html_for_mitm("just plain text", "sid"), "just plain text")


class TestMITMTargetParsing(unittest.TestCase):
    def test_extract_sid_from_referer_prefers_query_param_then_path(self):
        sid = "b" * 32
        query_referer = f"https://example.test/feed?__soxss_sid={sid}&x=1"
        path_referer = f"https://example.test/{sid}/profile"

        self.assertEqual(mitm_server.extract_sid_from_referer(query_referer), sid)
        self.assertEqual(mitm_server.extract_sid_from_referer(path_referer), sid)

    def test_extract_sid_from_referer_handles_invalid_values(self):
        with patch("modules.MITMServer.urlsplit", side_effect=ValueError("bad-url")):
            self.assertEqual(mitm_server.extract_sid_from_referer("http://["), "")

        self.assertEqual(mitm_server.extract_sid_from_referer(""), "")
        self.assertEqual(mitm_server.extract_sid_from_referer("https://example.test/no-sid"), "")

    def test_parse_mitm_target_uses_referer_sid_and_forwards_query(self):
        sid = "c" * 32
        parsed_sid, parsed_path = mitm_server.parse_mitm_target(
            "/target/path?foo=bar",
            {"Referer": f"https://example.test/page?__soxss_sid={sid}"},
        )

        self.assertEqual(parsed_sid, sid)
        self.assertEqual(parsed_path, "/target/path?foo=bar")


class TestResolveSocketForMITM(SocksUtilStateMixin, unittest.TestCase):
    def test_returns_direct_match(self):
        socket = SimpleNamespace(request=SimpleNamespace(path="/sid-1"))
        with patch("modules.MITMServer.socksUtil.getSocketBySid", return_value=socket):
            self.assertEqual(mitm_server.resolve_socket_for_mitm("sid-1"), (socket, "sid-1", False))

    def test_falls_back_to_current_socket(self):
        current = SimpleNamespace(request=SimpleNamespace(path="/sid-current"))
        with patch("modules.MITMServer.socksUtil.getSocketBySid", return_value=None), patch(
            "modules.MITMServer.socksUtil.getCurrent", return_value=current
        ):
            self.assertEqual(mitm_server.resolve_socket_for_mitm("stale"), (current, "sid-current", True))

    def test_falls_back_to_single_socket(self):
        only = SimpleNamespace(request=SimpleNamespace(path="/sid-only"))
        socksUtil.sockets.append(only)
        with patch("modules.MITMServer.socksUtil.getSocketBySid", return_value=None), patch(
            "modules.MITMServer.socksUtil.getCurrent", return_value=None
        ):
            self.assertEqual(mitm_server.resolve_socket_for_mitm("stale"), (only, "sid-only", True))

    def test_returns_none_when_no_socket_resolves(self):
        with patch("modules.MITMServer.socksUtil.getSocketBySid", return_value=None), patch(
            "modules.MITMServer.socksUtil.getCurrent", return_value=None
        ):
            self.assertEqual(mitm_server.resolve_socket_for_mitm("stale"), (None, "stale", False))


class TestMITMPerformRequestBranches(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        super().setUp()
        mitm_server.cache.clear()
        self.addCleanup(mitm_server.cache.clear)

    @staticmethod
    def _make_handler(path, headers=None, body=b""):
        handler = object.__new__(mitm_server.MITMHTTPRequestHandler)
        handler.path = path
        handler.headers = headers or {}
        handler.rfile = io.BytesIO(body)
        handler.wfile = io.BytesIO()
        handler.send_response = MagicMock()
        handler.send_header = MagicMock()
        handler.end_headers = MagicMock()
        return handler

    async def test_uses_query_sid_and_forwards_remaining_query(self):
        handler = self._make_handler("/page?__soxss_sid=querysid&foo=bar")
        captured = {}

        async def fake_send_message(socket, payload):
            captured["payload"] = payload
            mitm_server.cache["fixed-key"] = {"type": "text/html", "content": "ok", "method": "GET"}

        with patch("modules.MITMServer.socksUtil.getSocketBySid", return_value=object()), patch(
            "modules.MITMServer.cryptoUtil.sendSecretMessage", new=AsyncMock(side_effect=fake_send_message)
        ), patch("modules.MITMServer.datetime.datetime") as datetime_mock, patch("builtins.print"):
            datetime_mock.now.return_value = "fixed-key"
            await mitm_server.MITMHTTPRequestHandler.performRequest(handler, "GET")

        self.assertIn("foo=bar", captured["payload"])
        handler.send_response.assert_called_once_with(200)

    async def test_logs_sid_fallback_when_resolution_uses_fallback(self):
        handler = self._make_handler("/page?__soxss_sid=stale")

        async def fake_send_message(socket, payload):
            mitm_server.cache["fixed-key"] = {"type": "text/html", "content": "ok", "method": "GET"}

        with patch("modules.MITMServer.resolve_socket_for_mitm", return_value=(object(), "real-sid", True)), patch(
            "modules.MITMServer.cryptoUtil.sendSecretMessage", new=AsyncMock(side_effect=fake_send_message)
        ), patch("modules.MITMServer.datetime.datetime") as datetime_mock, patch("builtins.print") as print_mock:
            datetime_mock.now.return_value = "fixed-key"
            await mitm_server.MITMHTTPRequestHandler.performRequest(handler, "GET")

        self.assertTrue(any("MITM SID fallback" in str(call.args[0]) for call in print_mock.call_args_list if call.args))

    async def test_times_out_when_response_never_arrives(self):
        handler = self._make_handler(f"/{VALID_SID}/slow")
        times = iter([0.0, 100.0, 100.0])
        loop = SimpleNamespace(time=lambda: next(times))

        async def fake_send_message(socket, payload):
            return None

        with patch("modules.MITMServer.socksUtil.getSocketBySid", return_value=object()), patch(
            "modules.MITMServer.cryptoUtil.sendSecretMessage", new=AsyncMock(side_effect=fake_send_message)
        ), patch("modules.MITMServer.asyncio.get_running_loop", return_value=loop), patch(
            "modules.MITMServer.asyncio.sleep", new=AsyncMock()
        ), patch("modules.MITMServer.datetime.datetime") as datetime_mock, patch("builtins.print"):
            datetime_mock.now.return_value = "slow-key"
            await mitm_server.MITMHTTPRequestHandler.performRequest(handler, "GET")

        handler.send_response.assert_called_once_with(404)
        self.assertIn("Timed out", handler.wfile.getvalue().decode("utf-8"))

    async def test_rewrites_css_response_body(self):
        handler = self._make_handler(f"/{VALID_SID}/style.css")

        async def fake_send_message(socket, payload):
            mitm_server.cache["css-key"] = {
                "type": "text/css",
                "content": "a{background:url(/x.png)}",
                "method": "GET",
            }

        with patch("modules.MITMServer.socksUtil.getSocketBySid", return_value=object()), patch(
            "modules.MITMServer.cryptoUtil.sendSecretMessage", new=AsyncMock(side_effect=fake_send_message)
        ), patch("modules.MITMServer.datetime.datetime") as datetime_mock, patch("builtins.print"):
            datetime_mock.now.return_value = "css-key"
            await mitm_server.MITMHTTPRequestHandler.performRequest(handler, "GET")

        self.assertIn(f"/{VALID_SID}/x.png", handler.wfile.getvalue().decode("utf-8"))

    async def test_ignores_broken_pipe_when_writing_response(self):
        handler = self._make_handler(f"/{VALID_SID}/page")
        handler.wfile = SimpleNamespace(write=MagicMock(side_effect=BrokenPipeError))

        async def fake_send_message(socket, payload):
            mitm_server.cache["pipe-key"] = {
                "type": "text/plain",
                "content": "hello",
                "method": "GET",
            }

        with patch("modules.MITMServer.socksUtil.getSocketBySid", return_value=object()), patch(
            "modules.MITMServer.cryptoUtil.sendSecretMessage", new=AsyncMock(side_effect=fake_send_message)
        ), patch("modules.MITMServer.datetime.datetime") as datetime_mock, patch("builtins.print"):
            datetime_mock.now.return_value = "pipe-key"
            await mitm_server.MITMHTTPRequestHandler.performRequest(handler, "GET")

        handler.send_response.assert_called_once_with(200)
