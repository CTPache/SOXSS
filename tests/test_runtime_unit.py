import asyncio
import importlib
import os
import runpy
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import cryptoUtil
import socksUtil


def make_websocket(path="/sid-1", remote_ip="127.0.0.1", socket_id="socket-1"):
    websocket = SimpleNamespace(
        request=SimpleNamespace(path=path),
        remote_ip=remote_ip,
        id=socket_id,
    )
    websocket.send = AsyncMock()
    websocket.recv = AsyncMock()
    websocket.remote_address = (remote_ip, 12345)
    return websocket


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


class CryptoUtilStateMixin:
    def setUp(self):
        super().setUp()
        self._orig_sessions = dict(cryptoUtil._sessions)
        cryptoUtil._sessions.clear()
        self.addCleanup(self._restore_sessions)

    def _restore_sessions(self):
        cryptoUtil._sessions.clear()
        cryptoUtil._sessions.update(self._orig_sessions)


class TestCryptoUtil(CryptoUtilStateMixin, unittest.IsolatedAsyncioTestCase):
    def test_generate_key_iv_returns_valid_sizes(self):
        secret_key, iv = cryptoUtil.generate_key_iv()

        self.assertEqual(len(iv), 32)
        self.assertEqual(len(__import__("base64").b64decode(secret_key)), 16)

    def test_set_and_get_session_material(self):
        cryptoUtil.set_key_iv("sid-1", "secret", "iv")

        self.assertEqual(cryptoUtil.get_key("sid-1"), "secret")
        self.assertEqual(cryptoUtil.get_iv("sid-1"), "iv")
        self.assertIsNone(cryptoUtil.get_key("missing"))
        self.assertIsNone(cryptoUtil.get_iv("missing"))

    def test_encrypt_decrypt_roundtrip(self):
        secret_key, iv = cryptoUtil.generate_key_iv()
        cryptoUtil.set_key_iv("sid-1", secret_key, iv)

        ciphertext = cryptoUtil.encrypt("hello world", "sid-1")

        self.assertNotEqual(ciphertext, "hello world")
        self.assertEqual(cryptoUtil.decrypt(ciphertext, "sid-1"), "hello world")

    def test_encrypt_requires_existing_session(self):
        with self.assertRaises(ValueError):
            cryptoUtil.encrypt("hello", "missing")

    def test_decrypt_requires_existing_session(self):
        with self.assertRaises(ValueError):
            cryptoUtil.decrypt("payload", "missing")

    async def test_send_secret_message_uses_session_from_websocket_path(self):
        secret_key, iv = cryptoUtil.generate_key_iv()
        cryptoUtil.set_key_iv("sid-1", secret_key, iv)
        websocket = make_websocket(path="/sid-1")

        await cryptoUtil.sendSecretMessage(websocket, "payload")

        websocket.send.assert_awaited_once()
        encrypted_payload = websocket.send.await_args.args[0]
        self.assertEqual(cryptoUtil.decrypt(encrypted_payload, "sid-1"), "payload")


class TestSocksUtil(SocksUtilStateMixin, unittest.TestCase):
    def test_add_remove_and_get_current_socket(self):
        socket = make_websocket(path="/sid-1")

        socksUtil.addSocket(socket)
        self.assertIs(socksUtil.getCurrent(), socket)

        socksUtil.removeSocket(socket)
        self.assertIsNone(socksUtil.getCurrent())

    def test_list_sockets_serializes_socket_metadata(self):
        socksUtil.sockets.extend(
            [
                make_websocket(path="/sid-1", remote_ip="10.0.0.1", socket_id="sock-1"),
                SimpleNamespace(id="sock-2", remote_ip="10.0.0.2"),
            ]
        )

        result = socksUtil.listSockets()

        self.assertEqual(result["0"]["sid"], "sid-1")
        self.assertEqual(result["0"]["mitmUrl"], "http://localhost:8001/sid-1/")
        self.assertEqual(result["1"]["sid"], "unknown")
        self.assertEqual(result["1"]["ip"], "10.0.0.2")

    def test_get_socket_by_sid_returns_matching_socket(self):
        socket = make_websocket(path="/sid-match")
        socksUtil.sockets.extend([make_websocket(path="/sid-other"), socket])

        self.assertIs(socksUtil.getSocketBySid("sid-match"), socket)
        self.assertIsNone(socksUtil.getSocketBySid("missing"))


class SocxssImportMixin:
    @staticmethod
    def load_socxss_module():
        with patch("modules.MITMModule.threading.Thread"):
            get_modules_mod = importlib.import_module("modules.getModules")
            importlib.reload(get_modules_mod)
            socxss = importlib.import_module("Socxss")
            return importlib.reload(socxss)


class FakeConnectionClosed(Exception):
    pass


class TestSocxssRuntime(SocksUtilStateMixin, CryptoUtilStateMixin, SocxssImportMixin, unittest.IsolatedAsyncioTestCase):
    async def test_exec_routes_message_to_typed_module_and_cleans_up_socket(self):
        socxss = self.load_socxss_module()
        websocket = make_websocket(path="/sid-1", remote_ip="10.0.0.8")
        secret_key, iv = cryptoUtil.generate_key_iv()
        cryptoUtil.set_key_iv("sid-1", secret_key, iv)

        default_handler = SimpleNamespace(handleMessage=AsyncMock())
        log_handler = SimpleNamespace(handleMessage=AsyncMock())
        encrypted_msg = cryptoUtil.encrypt('{"type": "log", "msg": "hello"}', "sid-1")
        websocket.recv = AsyncMock(side_effect=[encrypted_msg, FakeConnectionClosed()])

        with patch.object(socxss, "modules", {0: default_handler, "log": log_handler}), patch.object(
            socxss, "defaultModule", 0
        ), patch.object(socxss.exceptions, "ConnectionClosed", FakeConnectionClosed), patch("builtins.print"):
            await socxss.exec(websocket)

        log_handler.handleMessage.assert_awaited_once_with(websocket, "hello")
        default_handler.handleMessage.assert_not_called()
        self.assertNotIn(websocket, socksUtil.sockets)
        self.assertEqual(websocket.remote_ip, "10.0.0.8")

    async def test_exec_uses_default_handler_when_message_has_no_msg(self):
        socxss = self.load_socxss_module()
        websocket = make_websocket(path="/sid-2")
        secret_key, iv = cryptoUtil.generate_key_iv()
        cryptoUtil.set_key_iv("sid-2", secret_key, iv)

        default_handler = SimpleNamespace(handleMessage=AsyncMock())
        encrypted_msg = cryptoUtil.encrypt('{"type": "unknown"}', "sid-2")
        websocket.recv = AsyncMock(side_effect=[encrypted_msg, FakeConnectionClosed()])

        with patch.object(socxss, "modules", {0: default_handler}), patch.object(socxss, "defaultModule", 0), patch.object(
            socxss.exceptions, "ConnectionClosed", FakeConnectionClosed
        ), patch("builtins.print"):
            await socxss.exec(websocket)

        default_handler.handleMessage.assert_awaited_once_with(websocket, {"msg": "OK"})

    async def test_exec_logs_processing_errors_and_continues_until_disconnect(self):
        socxss = self.load_socxss_module()
        websocket = make_websocket(path="/sid-3")
        secret_key, iv = cryptoUtil.generate_key_iv()
        cryptoUtil.set_key_iv("sid-3", secret_key, iv)

        default_handler = SimpleNamespace(handleMessage=AsyncMock(side_effect=RuntimeError("boom")))
        encrypted_msg = cryptoUtil.encrypt('{"type": 0, "msg": "hello"}', "sid-3")
        websocket.recv = AsyncMock(side_effect=[encrypted_msg, FakeConnectionClosed()])

        with patch.object(socxss, "modules", {0: default_handler}), patch.object(socxss, "defaultModule", 0), patch.object(
            socxss.exceptions, "ConnectionClosed", FakeConnectionClosed
        ), patch("builtins.print") as print_mock:
            await socxss.exec(websocket)

        self.assertTrue(any("Message processing error" in str(call.args[0]) for call in print_mock.call_args_list))
        self.assertNotIn(websocket, socksUtil.sockets)

    async def test_main_starts_http_console_and_websocket_services(self):
        socxss = self.load_socxss_module()
        console_module = object()
        fake_tasks = []
        real_create_task = asyncio.create_task

        class FakeServeContext:
            async def __aenter__(self_inner):
                return self_inner

            async def __aexit__(self_inner, exc_type, exc, tb):
                return False

        async def fake_http_server():
            return None

        async def fake_console_server(module):
            return None

        def fake_create_task(coro):
            task = real_create_task(coro)
            fake_tasks.append(task)
            return task

        loop = MagicMock()
        loop.create_future.side_effect = RuntimeError("stop main")

        with patch.object(socxss, "modules", {socxss.ConsoleInWeb.type: console_module}), patch.object(
            socxss.httpServer, "start_async_server", fake_http_server
        ), patch.object(socxss, "start_async_console_server", fake_console_server), patch.object(
            socxss, "serve", return_value=FakeServeContext()
        ) as serve_mock, patch.object(socxss.asyncio, "create_task", side_effect=fake_create_task), patch.object(
            socxss.asyncio, "get_running_loop", return_value=loop
        ):
            with self.assertRaisesRegex(RuntimeError, "stop main"):
                await socxss.main()

        serve_mock.assert_called_once_with(socxss.exec, socxss.config.WS_HOST, socxss.config.WS_PORT)
        self.assertEqual(len(fake_tasks), 2)
        for task in fake_tasks:
            await task

    def test_clean_console_removes_known_files(self):
        socxss = self.load_socxss_module()
        with tempfile.TemporaryDirectory() as tmpdir:
            previous_cwd = os.getcwd()
            os.chdir(tmpdir)
            try:
                Path("console/screenshots").mkdir(parents=True, exist_ok=True)
                Path("console/logs").mkdir(parents=True, exist_ok=True)
                screenshot = Path("console/screenshots/a.png")
                logfile = Path("console/logs/a.log")
                screenshot.write_text("x", encoding="utf-8")
                logfile.write_text("y", encoding="utf-8")

                with patch("builtins.print"):
                    socxss.clean_console()

                self.assertFalse(screenshot.exists())
                self.assertFalse(logfile.exists())
            finally:
                os.chdir(previous_cwd)

    def test_clean_console_reports_remove_errors_and_continues(self):
        socxss = self.load_socxss_module()

        with patch("glob.glob", return_value=["console/screenshots/a.png"]), patch("os.path.isfile", return_value=True), patch(
            "os.remove", side_effect=OSError("denied")
        ), patch("builtins.print") as print_mock:
            socxss.clean_console()

        printed = [call.args[0] for call in print_mock.call_args_list if call.args]
        self.assertTrue(any("ERROR: Failed to remove console/screenshots/a.png: denied" in str(msg) for msg in printed))
        self.assertIn("Done.", printed)


class TestSocxssMainGuard(unittest.TestCase):
    def test_main_guard_prints_intro_and_handles_keyboard_interrupt(self):
        original_argv = sys.argv[:]
        sys.argv = ["Socxss.py"]

        def fake_asyncio_run(coro):
            coro.close()
            raise KeyboardInterrupt

        try:
            with patch("modules.MITMModule.threading.Thread"), patch("asyncio.run", side_effect=fake_asyncio_run), patch(
                "builtins.print"
            ) as print_mock:
                runpy.run_module("Socxss", run_name="__main__")
        finally:
            sys.argv = original_argv

        printed = [call.args[0] for call in print_mock.call_args_list if call.args]
        self.assertTrue(any("XSS Command and control" in str(msg) for msg in printed))
        self.assertTrue(any("Shutting down" in str(msg) for msg in printed))

    def test_main_guard_runs_fresh_start_without_intro_when_quiet(self):
        original_argv = sys.argv[:]
        sys.argv = ["Socxss.py", "-f", "-q"]

        def fake_asyncio_run(coro):
            coro.close()
            return None

        try:
            with patch("modules.MITMModule.threading.Thread"), patch("asyncio.run", side_effect=fake_asyncio_run), patch(
                "glob.glob", return_value=[]
            ), patch("builtins.print") as print_mock:
                runpy.run_module("Socxss", run_name="__main__")
        finally:
            sys.argv = original_argv

        printed = [call.args[0] for call in print_mock.call_args_list if call.args]
        self.assertIn("Cleaning console screenshots and logs...", printed)
        self.assertIn("Done.", printed)
        self.assertFalse(any("XSS Command and control" in str(msg) for msg in printed))
