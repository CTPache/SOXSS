import asyncio
import io
import importlib
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
        self.assertIn(str(payload_server.config.PUBLIC_HTTP_PORT), response.text)
        self.assertIn(str(payload_server.config.PUBLIC_WS_PORT), response.text)
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
        handler.path = "/sid-1/path/to/resource"
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
        self.assertEqual(handler.wfile.getvalue().decode("utf-8"), '<a href="/sid-1/next">next</a>')
        self.assertNotIn("fixed-key", mitm_server.cache)

    async def test_perform_request_returns_404_without_socket(self):
        handler = object.__new__(mitm_server.MITMHTTPRequestHandler)
        handler.path = "/missing-sid/page"
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
        handler.send_response = MagicMock()
        handler.end_headers = MagicMock()

        await mitm_server.MITMHTTPRequestHandler.performRequest(handler, "GET")

        handler.send_response.assert_called_once_with(404)
        handler.end_headers.assert_called_once_with()

    async def test_perform_request_ignores_websocket_js(self):
        handler = object.__new__(mitm_server.MITMHTTPRequestHandler)
        handler.path = "/sid-1/webSocket.js"
        handler.send_response = MagicMock()

        await mitm_server.MITMHTTPRequestHandler.performRequest(handler, "GET")

        handler.send_response.assert_not_called()

    async def test_perform_request_for_post_reads_body_and_writes_binary_content(self):
        handler = object.__new__(mitm_server.MITMHTTPRequestHandler)
        handler.path = "/sid-1/upload"
        handler.headers = {"Content-Length": "7"}
        handler.rfile = io.BytesIO(b"payload")
        handler.wfile = io.BytesIO()
        handler.send_response = MagicMock()
        handler.send_header = MagicMock()
        handler.end_headers = MagicMock()

        async def fake_send_message(socket, payload):
            self.assertIn('"body": "payload"', payload)
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
        handler.path = "/sid-1/pending"
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

    def test_do_get_and_do_post_delegate_to_asyncio_run(self):
        handler = object.__new__(mitm_server.MITMHTTPRequestHandler)

        async def fake_perform_request(method):
            return method

        handler.performRequest = fake_perform_request

        def fake_run(coro):
            coro.close()

        with patch("modules.MITMServer.asyncio.run", side_effect=fake_run) as run_mock:
            handler.do_GET()
            handler.do_POST()

        self.assertEqual(run_mock.call_count, 2)

    def test_log_message_returns_empty_string(self):
        handler = object.__new__(mitm_server.MITMHTTPRequestHandler)
        self.assertEqual(handler.log_message("format %s", "x"), "")

    def test_start_server_bootstraps_http_server(self):
        fake_httpd = MagicMock()

        with patch("modules.MITMServer.HTTPServer", return_value=fake_httpd) as http_server, patch("builtins.print"):
            mitm_server.start_server(module=object())

        http_server.assert_called_once()
        fake_httpd.serve_forever.assert_called_once_with()
