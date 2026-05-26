import base64
import importlib
import json
import os
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import socksUtil
from PIL import Image

import modules.ConsoleServer as console_server
from modules.MITMServer import cache
from modules.MITMModule import MITMModule
from modules.abstractModule import Module
from modules.consoleModule import ConsoleInWeb
from modules.loggerModule import Logger
from modules.screenshotModule import ScreenshotModule


def make_websocket(path="/test-sid", remote_ip="127.0.0.1", socket_id="socket-1"):
    return SimpleNamespace(
        request=SimpleNamespace(path=path),
        remote_ip=remote_ip,
        id=socket_id,
    )


def make_png_data_url(color="red"):
    image = Image.new("RGB", (2, 2), color=color)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    payload = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{payload}"


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


class WorkingDirectoryMixin:
    def setUp(self):
        super().setUp()
        self._cwd = os.getcwd()
        self._tmpdir = tempfile.TemporaryDirectory()
        os.chdir(self._tmpdir.name)
        self.addCleanup(self._restore_cwd)

    def _restore_cwd(self):
        os.chdir(self._cwd)
        self._tmpdir.cleanup()


class TestAbstractModule(unittest.IsolatedAsyncioTestCase):
    async def test_send_message_wraps_command_json(self):
        websocket = make_websocket()
        module = Module()

        with patch("modules.abstractModule.sendSecretMessage", new=AsyncMock()) as send_mock:
            await module.sendMessage(websocket, "disable")

        send_mock.assert_awaited_once_with(websocket, json.dumps({"Command": "disable"}))

    async def test_handle_message_delegates_to_send_message(self):
        websocket = make_websocket()
        module = Module()

        with patch.object(module, "sendMessage", new=AsyncMock()) as send_mock:
            await module.handleMessage(websocket, {"msg": "OK"})

        send_mock.assert_awaited_once_with(websocket)


class TestConsoleModule(SocksUtilStateMixin, unittest.IsolatedAsyncioTestCase):
    async def test_handle_message_uses_current_socket_host(self):
        current_socket = make_websocket(path="/current", remote_ip="10.0.0.5")
        socksUtil.sockets.append(current_socket)
        module = ConsoleInWeb()

        with patch("modules.consoleModule.time.time", return_value=123.456):
            await module.handleMessage(None, {"text": "hello", "outputType": "info"})

        payload = json.loads(console_server.consoleOut)
        self.assertEqual(payload["text"], "hello")
        self.assertEqual(payload["host"], "10.0.0.5")
        self.assertEqual(payload["timestamp"], 123.456)

    async def test_handle_message_marks_disconnected_without_socket(self):
        module = ConsoleInWeb()

        with patch("modules.consoleModule.time.time", return_value=10.0):
            await module.handleMessage(None, {"text": "hello"})

        payload = json.loads(console_server.consoleOut)
        self.assertEqual(payload["host"], "disconected")

    async def test_send_message_sends_remote_command_when_command_requires_socket(self):
        module = ConsoleInWeb()
        websocket = make_websocket()
        fake_command = SimpleNamespace(sendsMessage=True, execute=MagicMock(return_value='{"Command": "OK"}'))

        with patch("modules.consoleModule.commands_mod.getCommands", return_value={"list": fake_command}), patch(
            "modules.consoleModule.sendSecretMessage", new=AsyncMock()
        ) as send_mock:
            result = await module.sendMessage(websocket, "list")

        self.assertEqual(result, '{"Command": "OK"}')
        fake_command.execute.assert_called_once_with("list")
        send_mock.assert_awaited_once_with(websocket, '{"Command": "OK"}')

    async def test_send_message_uses_default_command_for_unknown_input(self):
        module = ConsoleInWeb()
        websocket = make_websocket()
        fallback_command = SimpleNamespace(sendsMessage=True, execute=MagicMock(return_value='{"Command": "eval"}'))

        with patch(
            "modules.consoleModule.commands_mod.getCommands",
            return_value={"eval": fallback_command},
        ), patch("modules.consoleModule.commands_mod.default", "eval"), patch(
            "modules.consoleModule.sendSecretMessage", new=AsyncMock()
        ) as send_mock:
            result = await module.sendMessage(websocket, "unknown command")

        self.assertEqual(result, '{"Command": "eval"}')
        fallback_command.execute.assert_called_once_with("unknown command")
        send_mock.assert_awaited_once()

    async def test_send_message_handles_local_only_command(self):
        module = ConsoleInWeb()
        fake_command = SimpleNamespace(sendsMessage=False, execute=MagicMock(return_value={"text": "done", "outputType": "info"}))

        with patch("modules.consoleModule.commands_mod.getCommands", return_value={"list": fake_command}), patch(
            "modules.consoleModule.time.time", return_value=77.0
        ):
            result = await module.sendMessage(make_websocket(), "list")

        self.assertEqual(result["text"], "done")
        self.assertEqual(result["outputType"], "info")
        self.assertEqual(result["timestamp"], 77.0)
        self.assertEqual(result["host"], "disconected")
        payload = json.loads(console_server.consoleOut)
        self.assertEqual(payload["text"], "done")
        self.assertEqual(payload["timestamp"], 77.0)

    async def test_send_message_without_websocket_and_non_dict_result_emits_empty_payload(self):
        module = ConsoleInWeb()
        fake_command = SimpleNamespace(sendsMessage=False, execute=MagicMock(return_value="raw-result"))

        with patch("modules.consoleModule.commands_mod.getCommands", return_value={"list": fake_command}), patch(
            "modules.consoleModule.time.time", return_value=88.0
        ):
            result = await module.sendMessage(None, "list")

        self.assertEqual(result, "raw-result")
        payload = json.loads(console_server.consoleOut)
        self.assertEqual(payload["timestamp"], 88.0)
        self.assertEqual(payload["host"], "disconected")

    async def test_send_message_without_websocket_and_dict_result_emits_result_payload(self):
        module = ConsoleInWeb()
        fake_command = SimpleNamespace(sendsMessage=False, execute=MagicMock(return_value={"text": "local", "outputType": "info"}))

        with patch("modules.consoleModule.commands_mod.getCommands", return_value={"list": fake_command}), patch(
            "modules.consoleModule.time.time", return_value=99.0
        ):
            result = await module.sendMessage(None, "list")

        self.assertEqual(result["text"], "local")
        payload = json.loads(console_server.consoleOut)
        self.assertEqual(payload["text"], "local")
        self.assertEqual(payload["timestamp"], 99.0)


class TestLoggerModule(WorkingDirectoryMixin, unittest.IsolatedAsyncioTestCase):
    async def test_handle_message_creates_log_file_and_appends_line(self):
        module = Logger()
        websocket = make_websocket(path="/logger-sid")

        with patch("modules.abstractModule.sendSecretMessage", new=AsyncMock()) as send_mock:
            await module.handleMessage(websocket, "captured line")

        log_path = Path("console/logs/logger-sid.log")
        self.assertTrue(log_path.exists())
        self.assertEqual(log_path.read_text(encoding="utf-8"), "captured line\n")
        send_mock.assert_awaited_once_with(websocket, json.dumps({"Command": "OK"}))

    async def test_log_to_file_appends_without_overwriting(self):
        module = Logger()
        Path("console/logs").mkdir(parents=True, exist_ok=True)

        module.logToFile("first", "abc")
        module.logToFile("second", "abc")

        self.assertEqual(Path("console/logs/abc.log").read_text(encoding="utf-8"), "first\nsecond\n")


class TestScreenshotModule(WorkingDirectoryMixin, unittest.IsolatedAsyncioTestCase):
    async def test_handle_message_persists_archive_and_latest_images(self):
        module = ScreenshotModule()
        websocket = make_websocket(path="/screen-sid", remote_ip="10.0.0.9")
        image_msg = make_png_data_url()

        with patch("modules.screenshotModule.time.time", return_value=1234), patch(
            "modules.abstractModule.sendSecretMessage", new=AsyncMock()
        ) as send_mock:
            await module.handleMessage(websocket, image_msg)

        latest_path = Path("console/screenshots/screen-sid.png")
        archive_path = Path("console/screenshots/screen-sid_1234.png")
        self.assertTrue(latest_path.exists())
        self.assertTrue(archive_path.exists())
        payload = json.loads(console_server.consoleOut)
        self.assertEqual(payload["outputType"], "info")
        self.assertEqual(payload["sid"], "screen-sid")
        self.assertEqual(payload["host"], "10.0.0.9")
        send_mock.assert_awaited_once_with(websocket, json.dumps({"Command": "OK"}))

    async def test_handle_message_reports_error_for_invalid_payload(self):
        module = ScreenshotModule()
        websocket = make_websocket(path="/screen-sid")

        with patch("modules.abstractModule.sendSecretMessage", new=AsyncMock()) as send_mock:
            await module.handleMessage(websocket, "not-a-data-url")

        payload = json.loads(console_server.consoleOut)
        self.assertEqual(payload["outputType"], "error")
        self.assertIn("Screenshot failed", payload["text"])
        send_mock.assert_awaited_once_with(websocket, json.dumps({"Command": "OK"}))


class TestMITMModule(SocksUtilStateMixin, unittest.IsolatedAsyncioTestCase):
    async def test_handle_message_stores_cache_entry_and_acknowledges(self):
        websocket = make_websocket(path="/mitm-sid")
        socksUtil.sockets.append(websocket)
        module = object.__new__(MITMModule)
        cache.clear()
        self.addCleanup(cache.clear)

        with patch("modules.abstractModule.sendSecretMessage", new=AsyncMock()) as send_mock:
            await module.handleMessage(
                websocket,
                {
                    "key": "cache-key",
                    "contentType": "text/html",
                    "content": "<html></html>",
                    "method": "GET",
                },
            )

        self.assertEqual(
            cache["cache-key"],
            {"type": "text/html", "content": "<html></html>", "method": "GET"},
        )
        send_mock.assert_awaited_once_with(websocket, json.dumps({"Command": "OK"}))

    def test_init_starts_daemon_thread(self):
        fake_thread = MagicMock()

        with patch("modules.MITMModule.threading.Thread", return_value=fake_thread) as thread_cls:
            module = MITMModule()

        thread_cls.assert_called_once()
        kwargs = thread_cls.call_args.kwargs
        self.assertEqual(kwargs["target"].__name__, "start_server")
        self.assertEqual(kwargs["args"], [module])
        self.assertTrue(fake_thread.daemon)
        fake_thread.start.assert_called_once_with()


class TestGetModules(unittest.TestCase):
    def test_get_modules_returns_expected_registry(self):
        with patch("modules.MITMModule.threading.Thread"):
            get_modules_mod = importlib.import_module("modules.getModules")
            get_modules_mod = importlib.reload(get_modules_mod)

        registry, default_module = get_modules_mod.getModules()
        self.assertEqual(default_module, ConsoleInWeb.type)
        self.assertIn(Logger.type, registry)
        self.assertIn(ConsoleInWeb.type, registry)
        self.assertIn(ScreenshotModule.type, registry)
        self.assertIn(MITMModule.type, registry)
        self.assertIsInstance(registry[Logger.type], Logger)
        self.assertIsInstance(registry[ConsoleInWeb.type], ConsoleInWeb)
        self.assertIsInstance(registry[ScreenshotModule.type], ScreenshotModule)
