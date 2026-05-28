import asyncio
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from aiohttp import ClientSession, CookieJar, web
from yarl import URL


ROOT = Path(__file__).resolve().parents[1]
SERVER_PATH = ROOT / "testVictima" / "server.py"


def load_victim_server(unique_name="victim_server_test"):
    spec = importlib.util.spec_from_file_location(unique_name, SERVER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class VictimRegistryMixin:
    def setUp(self):
        super().setUp()
        self._tmpdir = tempfile.TemporaryDirectory()
        self.registry_dir = Path(self._tmpdir.name) / "registry"
        self.registry_dir.mkdir(parents=True, exist_ok=True)
        self.server = load_victim_server(f"victim_server_{id(self)}")
        self.server.REGISTRY_DIR = str(self.registry_dir)
        self.server.USERS_FILE = str(self.registry_dir / "user_registry.json")
        self.server.POSTS_FILE = str(self.registry_dir / "posts_registry.json")
        self.server.SESSIONS_FILE = str(self.registry_dir / "session_registry.json")
        self.addCleanup(self._tmpdir.cleanup)


class VictimServerAppMixin(VictimRegistryMixin):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.server.seed_if_needed()
        self.app = web.Application()
        self.server.setup_routes(self.app)
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, "127.0.0.1", 0)
        await self.site.start()
        sockets = self.site._server.sockets if self.site._server else []
        self.port = sockets[0].getsockname()[1]
        self.base_url = f"http://127.0.0.1:{self.port}"
        self.client = ClientSession(cookie_jar=CookieJar(unsafe=True))
        self.addAsyncCleanup(self.client.close)
        self.addAsyncCleanup(self.runner.cleanup)


class TestVictimRegistryPersistence(VictimRegistryMixin, unittest.TestCase):
    def test_load_json_file_falls_back_for_missing_and_invalid_data(self):
        missing = self.registry_dir / "missing.json"
        invalid = self.registry_dir / "invalid.json"
        invalid.write_text("not-json", encoding="utf-8")

        self.assertEqual(self.server.load_json_file(str(missing), ["fallback"]), ["fallback"])
        self.assertEqual(self.server.load_json_file(str(invalid), {"ok": True}), {"ok": True})

    def test_save_json_file_creates_registry_directory(self):
        target = self.registry_dir / "nested" / "data.json"

        self.server.save_json_file(str(target), {"value": 1})

        self.assertTrue(target.exists())
        self.assertEqual(json.loads(target.read_text(encoding="utf-8")), {"value": 1})

    def test_seed_if_needed_populates_default_registry_files(self):
        self.server.seed_if_needed()

        users = json.loads((self.registry_dir / "user_registry.json").read_text(encoding="utf-8"))
        posts = json.loads((self.registry_dir / "posts_registry.json").read_text(encoding="utf-8"))
        sessions = json.loads((self.registry_dir / "session_registry.json").read_text(encoding="utf-8"))

        self.assertGreaterEqual(len(users), 3)
        self.assertGreaterEqual(len(posts), 6)
        self.assertEqual(sessions, {"byToken": {}, "byUser": {}})

    def test_load_sessions_sync_recovers_from_corrupt_file(self):
        (self.registry_dir / "session_registry.json").write_text("{broken", encoding="utf-8")

        self.assertEqual(self.server.load_sessions_sync(), {"byToken": {}, "byUser": {}})


class TestVictimServerRoutes(VictimServerAppMixin, unittest.IsolatedAsyncioTestCase):
    async def _request_json(self, method, path, **kwargs):
        response = await self.client.request(method, self.base_url + path, **kwargs)
        self.addAsyncCleanup(response.release)
        payload = await response.json()
        return response, payload

    async def test_static_pages_and_public_routes_exist(self):
        response = await self.client.get(self.base_url + "/")
        self.addAsyncCleanup(response.release)
        self.assertEqual(response.status, 200)
        self.assertIn("Registro y login", await response.text())

        response = await self.client.get(self.base_url + "/feed")
        self.addAsyncCleanup(response.release)
        self.assertEqual(response.status, 200)
        self.assertIn("Feed global", await response.text())

        response = await self.client.get(self.base_url + "/profile")
        self.addAsyncCleanup(response.release)
        self.assertEqual(response.status, 200)
        self.assertIn("Editar mi perfil", await response.text())

        response = await self.client.get(self.base_url + "/profile/alice")
        self.addAsyncCleanup(response.release)
        self.assertEqual(response.status, 200)
        self.assertIn("Editar mi perfil", await response.text())

    async def test_register_login_session_and_profile_flow(self):
        username = f"selenium_{id(self) % 100000}"
        register_response, register_payload = await self._request_json(
            "POST",
            "/api/auth/register",
            json={
                "username": username,
                "password": "secret123",
                "displayName": "Selenium User",
                "bio": "Profile under test",
                "remember": True,
            },
        )
        self.assertEqual(register_response.status, 200)
        self.assertEqual(register_payload["user"]["username"], username)

        session_response, session_payload = await self._request_json("GET", "/api/session")
        self.assertEqual(session_response.status, 200)
        self.assertTrue(session_payload["active"])
        self.assertEqual(session_payload["user"]["username"], username)

        me_response, me_payload = await self._request_json("GET", "/api/me")
        self.assertEqual(me_response.status, 200)
        self.assertEqual(me_payload["user"]["username"], username)
        self.assertEqual(me_payload["stats"]["postsCount"], 0)

        update_response, update_payload = await self._request_json(
            "PUT",
            "/api/me",
            json={
                "displayName": "Selenium User Updated",
                "bio": "Updated bio",
                "avatarColor": "#3344aa",
            },
        )
        self.assertEqual(update_response.status, 200)
        self.assertEqual(update_payload["user"]["displayName"], "Selenium User Updated")

        post_response, post_payload = await self._request_json(
            "POST",
            "/api/posts",
            json={"content": "A first post from the new victim app tests."},
        )
        self.assertEqual(post_response.status, 200)
        self.assertEqual(post_payload["post"]["username"], username)

        feed_response, feed_payload = await self._request_json("GET", "/api/feed?page=1&pageSize=2")
        self.assertEqual(feed_response.status, 200)
        self.assertEqual(feed_payload["page"], 1)
        self.assertEqual(feed_payload["pageSize"], 2)
        self.assertTrue(feed_payload["total"] >= 1)

        user_response, user_payload = await self._request_json("GET", f"/api/users/{username}")
        self.assertEqual(user_response.status, 200)
        self.assertEqual(user_payload["user"]["username"], username)
        self.assertEqual(user_payload["posts"][0]["content"], "A first post from the new victim app tests.")

        user_posts_response, user_posts_payload = await self._request_json("GET", f"/api/users/{username}/posts")
        self.assertEqual(user_posts_response.status, 200)
        self.assertEqual(user_posts_payload["total"], 1)
        self.assertEqual(user_posts_payload["items"][0]["username"], username)

        posts_response, posts_payload = await self._request_json("GET", f"/api/posts?username={username}")
        self.assertEqual(posts_response.status, 200)
        self.assertEqual(len(posts_payload["items"]), 1)

        logout_response, logout_payload = await self._request_json("POST", "/api/auth/logout", json={})
        self.assertEqual(logout_response.status, 200)
        self.assertTrue(logout_payload["ok"])

        session_after_logout, _ = await self._request_json("GET", "/api/session")
        self.assertEqual(session_after_logout.status, 404)

    async def test_login_rejects_bad_credentials_and_refreshes_session(self):
        bad_response, bad_payload = await self._request_json(
            "POST",
            "/api/auth/login",
            json={"username": "alice", "password": "wrong", "remember": False},
        )
        self.assertEqual(bad_response.status, 401)
        self.assertEqual(bad_payload["error"], "Invalid credentials")

        good_response, good_payload = await self._request_json(
            "POST",
            "/api/auth/login",
            json={"username": "alice", "password": "alice123", "remember": False},
        )
        self.assertEqual(good_response.status, 200)
        self.assertEqual(good_payload["user"]["username"], "alice")

        me_response, me_payload = await self._request_json("GET", "/api/me")
        self.assertEqual(me_response.status, 200)
        self.assertEqual(me_payload["user"]["username"], "alice")

        session_response, session_payload = await self._request_json("GET", "/api/session")
        self.assertEqual(session_response.status, 200)
        self.assertEqual(session_payload["session"]["user"], "alice")

    async def test_session_expiry_invalidates_request_cookie(self):
        self.server.seed_if_needed()
        session_payload = {
            "user": "alice",
            "displayName": "Alice Rivera",
            "token": "expired-token",
            "remember": False,
            "createdAt": "2026-05-27T00:00:00",
            "lastSeen": "2026-05-27T00:00:00",
            "expiresAt": "2000-01-01T00:00:00",
        }
        await self.server.write_state(sessions={"byToken": {"expired-token": session_payload}, "byUser": {"alice": "expired-token"}})
        self.client.cookie_jar.update_cookies({self.server.SESSION_COOKIE_NAME: "expired-token"}, URL(self.base_url))

        response = await self.client.get(self.base_url + "/api/session")
        self.addAsyncCleanup(response.release)
        self.assertEqual(response.status, 404)


if __name__ == "__main__":
    unittest.main(verbosity=2)