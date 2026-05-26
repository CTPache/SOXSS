import base64
import importlib
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import socksUtil
from modules.consoleCommands.abstractCommand import Command
from modules.consoleCommands.changeCurrentCommand import ChangeCurrentSocketCommand, ListSocketsCommand
from modules.consoleCommands.disableConsole import DisableConsoleCommand
from modules.consoleCommands.downloadFileCommand import DownloadFileCommand
from modules.consoleCommands.evalCommand import EvalCommand
from modules.consoleCommands.exitCommand import ExitCommand
from modules.consoleCommands.loadCommand import LoadCommand
from modules.consoleCommands.okCommand import OkCommand
from modules.consoleCommands.screenshotCommand import GetFrameCommand


def make_websocket(path="/sid-1", remote_ip="127.0.0.1", socket_id="socket-1"):
    return SimpleNamespace(
        request=SimpleNamespace(path=path),
        remote_ip=remote_ip,
        id=socket_id,
    )


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


class TestAbstractCommand(unittest.TestCase):
    def test_defaults(self):
        command = Command()
        self.assertEqual(command.type, "")
        self.assertTrue(command.sendsMessage)
        self.assertIsNone(command.execute("ignored"))


class TestSimpleCommands(unittest.TestCase):
    def test_disable_command(self):
        self.assertEqual(json.loads(DisableConsoleCommand().execute("disable")), {"Command": "disable"})

    def test_eval_command(self):
        self.assertEqual(
            json.loads(EvalCommand().execute("document.title")),
            {"Command": "eval", "expression": "document.title"},
        )

    def test_load_command_preserves_full_payload(self):
        script = "// comment\nconsole.log('loaded');"
        payload = f"load {script}"
        self.assertEqual(json.loads(LoadCommand().execute(payload)), {"Command": "load", "script": script})

    def test_ok_command(self):
        self.assertEqual(json.loads(OkCommand().execute("ok")), {"Command": "OK"})

    def test_screenshot_command(self):
        self.assertEqual(json.loads(GetFrameCommand().execute("screenshot")), {"Command": "screenshot"})

    def test_exit_command_returns_disable_payload(self):
        self.assertEqual(json.loads(ExitCommand().execute("exit")), {"Command": "disable"})


class TestDownloadFileCommand(unittest.TestCase):
    def test_execute_embeds_base64_file_payload(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "payload.bin"
            path.write_bytes(b"abc123")

            with patch("builtins.print"):
                result = json.loads(DownloadFileCommand().execute(f"downloadFile {path} export.bin"))

        self.assertEqual(result["Command"], "downloadFile")
        self.assertEqual(result["fileName"], "export.bin")
        self.assertEqual(base64.b64decode(result["data"]), b"abc123")


class TestSocketSelectionCommands(SocksUtilStateMixin, unittest.TestCase):
    def test_change_current_socket_updates_index(self):
        socksUtil.sockets.extend([
            make_websocket(path="/sid-1", remote_ip="10.0.0.1"),
            make_websocket(path="/sid-2", remote_ip="10.0.0.2"),
        ])

        result = ChangeCurrentSocketCommand().execute("change 1")

        self.assertEqual(socksUtil.current, 1)
        self.assertEqual(result, {"text": "changed target to 1: 10.0.0.2"})

    def test_change_current_socket_rejects_invalid_index(self):
        socksUtil.sockets.append(make_websocket())

        result = ChangeCurrentSocketCommand().execute("change 2")

        self.assertEqual(result["outputType"], "error")
        self.assertIn("Index out of range", result["text"])

    def test_list_sockets_returns_serialized_socket_info(self):
        socksUtil.sockets.extend([
            make_websocket(path="/sid-1", remote_ip="10.0.0.1", socket_id="sock-1"),
            make_websocket(path="/sid-2", remote_ip="10.0.0.2", socket_id="sock-2"),
        ])

        result = ListSocketsCommand().execute("list")

        self.assertEqual(result["outputType"], "info")
        payload = json.loads(result["text"].strip())
        self.assertEqual(payload["0"]["sid"], "sid-1")
        self.assertEqual(payload["1"]["ip"], "10.0.0.2")


class TestGetCommands(unittest.TestCase):
    def test_get_commands_includes_all_registered_commands(self):
        commands_mod = importlib.import_module("modules.consoleCommands.getCommands")
        commands = commands_mod.getCommands()

        self.assertEqual(commands_mod.default, EvalCommand.type)
        self.assertIn(EvalCommand.type, commands)
        self.assertIn(OkCommand.type, commands)
        self.assertIn(GetFrameCommand.type, commands)
        self.assertIn(LoadCommand.type, commands)
        self.assertIn(ExitCommand.type, commands)
        self.assertIn(DisableConsoleCommand.type, commands)
        self.assertIn(ChangeCurrentSocketCommand.type, commands)
        self.assertIn(ListSocketsCommand.type, commands)
        self.assertIn(DownloadFileCommand.type, commands)
