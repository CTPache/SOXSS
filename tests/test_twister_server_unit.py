import asyncio
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from unittest.mock import AsyncMock, MagicMock, patch

from aiohttp import ClientSession, CookieJar, web
from yarl import URL


ROOT = Path(__file__).resolve().parents[1]
SERVER_PATH = ROOT / "twister" / "server.py"


def load_twister_server(unique_name="twister_server_test"):
    spec = importlib.util.spec_from_file_location(unique_name, SERVER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class TwisterRegistryMixin:
    def setUp(self):
        super().setUp()
        self._tmpdir = tempfile.TemporaryDirectory()
        self.registry_dir = Path(self._tmpdir.name) / "registry"
        self.registry_dir.mkdir(parents=True, exist_ok=True)
        self.server = load_twister_server(f"twister_server_{id(self)}")
        self.server.REGISTRY_DIR = str(self.registry_dir)
        self.server.USERS_FILE = str(self.registry_dir / "user_registry.json")
        self.server.POSTS_FILE = str(self.registry_dir / "posts_registry.json")
        self.server.SESSIONS_FILE = str(self.registry_dir / "session_registry.json")
        self.addCleanup(self._tmpdir.cleanup)


class TwisterServerAppMixin(TwisterRegistryMixin):
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


class TestTwisterRegistryPersistence(TwisterRegistryMixin, unittest.TestCase):
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

    def test_load_sessions_sync_normalizes_non_dict_payload(self):
        (self.registry_dir / "session_registry.json").write_text("[]", encoding="utf-8")

        self.assertEqual(self.server.load_sessions_sync(), {"byToken": {}, "byUser": {}})


class TestTwisterServerRoutes(TwisterServerAppMixin, unittest.IsolatedAsyncioTestCase):
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

    async def test_users_list_and_unknown_user_endpoints(self):
        resp, payload = await self._request_json("GET", "/api/users")
        self.assertEqual(resp.status, 200)
        self.assertTrue(any(user["username"] == "alice" for user in payload))

        detail_resp, _ = await self._request_json("GET", "/api/users/ghost")
        self.assertEqual(detail_resp.status, 404)

        posts_resp, _ = await self._request_json("GET", "/api/users/ghost/posts")
        self.assertEqual(posts_resp.status, 404)

    async def test_register_validation_branches(self):
        invalid_json, _ = await self._request_json("POST", "/api/auth/register", data="not-json")
        self.assertEqual(invalid_json.status, 400)

        missing_fields, _ = await self._request_json(
            "POST", "/api/auth/register", json={"username": "", "password": ""}
        )
        self.assertEqual(missing_fields.status, 400)

        duplicate, _ = await self._request_json(
            "POST", "/api/auth/register", json={"username": "alice", "password": "whatever"}
        )
        self.assertEqual(duplicate.status, 409)

    async def test_login_invalid_json_returns_400(self):
        resp, _ = await self._request_json("POST", "/api/auth/login", data="not-json")
        self.assertEqual(resp.status, 400)

    async def test_me_and_update_me_require_authentication(self):
        me_resp, _ = await self._request_json("GET", "/api/me")
        self.assertEqual(me_resp.status, 401)

        update_resp, _ = await self._request_json("PUT", "/api/me", json={"displayName": "x"})
        self.assertEqual(update_resp.status, 401)

    async def test_update_me_invalid_json_after_login(self):
        await self._request_json("POST", "/api/auth/login", json={"username": "alice", "password": "alice123"})
        resp, _ = await self._request_json("PUT", "/api/me", data="not-json")
        self.assertEqual(resp.status, 400)

    async def test_posts_post_requires_auth_then_validates_content(self):
        unauth, _ = await self._request_json("POST", "/api/posts", json={"content": "hi"})
        self.assertEqual(unauth.status, 401)

        await self._request_json("POST", "/api/auth/login", json={"username": "alice", "password": "alice123"})

        invalid_json, _ = await self._request_json("POST", "/api/posts", data="not-json")
        self.assertEqual(invalid_json.status, 400)

        empty_content, _ = await self._request_json("POST", "/api/posts", json={"content": "   "})
        self.assertEqual(empty_content.status, 400)

    async def test_feed_tolerates_invalid_pagination(self):
        resp, payload = await self._request_json("GET", "/api/feed?page=abc&pageSize=xyz")
        self.assertEqual(resp.status, 200)
        self.assertEqual(payload["page"], 1)
        self.assertEqual(payload["pageSize"], self.server.DEFAULT_PAGE_SIZE)

    async def test_session_with_unknown_token_returns_404(self):
        self.client.cookie_jar.update_cookies({self.server.SESSION_COOKIE_NAME: "ghost-token"}, URL(self.base_url))
        resp = await self.client.get(self.base_url + "/api/session")
        self.addAsyncCleanup(resp.release)
        self.assertEqual(resp.status, 404)

    async def test_session_with_unparseable_expiry_is_tolerated(self):
        await self.server.write_state(
            sessions={
                "byToken": {"tok-bad": {"user": "alice", "token": "tok-bad", "expiresAt": "not-a-date"}},
                "byUser": {"alice": "tok-bad"},
            }
        )
        self.client.cookie_jar.update_cookies({self.server.SESSION_COOKIE_NAME: "tok-bad"}, URL(self.base_url))
        resp, payload = await self._request_json("GET", "/api/session")
        self.assertEqual(resp.status, 200)
        self.assertTrue(payload["active"])

    async def test_me_and_update_me_with_deleted_user_return_404(self):
        await self.server.write_state(
            sessions={
                "byToken": {"tok-ghost": {"user": "ghostuser", "token": "tok-ghost", "expiresAt": "2999-01-01T00:00:00"}},
                "byUser": {"ghostuser": "tok-ghost"},
            }
        )
        self.client.cookie_jar.update_cookies({self.server.SESSION_COOKIE_NAME: "tok-ghost"}, URL(self.base_url))

        me_resp, _ = await self._request_json("GET", "/api/me")
        self.assertEqual(me_resp.status, 404)

        update_resp, _ = await self._request_json("PUT", "/api/me", json={"displayName": "x"})
        self.assertEqual(update_resp.status, 404)

    async def test_handle_posts_rejects_unsupported_method(self):
        response = await self.server.handle_posts(SimpleNamespace(method="DELETE"))
        self.assertEqual(response.status, 405)

    async def test_handle_users_rejects_non_get_method(self):
        response = await self.server.handle_users(SimpleNamespace(method="POST"))
        self.assertEqual(response.status, 405)

    async def test_static_fallback_serves_file_and_reports_missing(self):
        served = await self.client.get(self.base_url + "/feed.html")
        self.addAsyncCleanup(served.release)
        self.assertEqual(served.status, 200)

        missing = await self.client.get(self.base_url + "/does-not-exist.zzz")
        self.addAsyncCleanup(missing.release)
        self.assertEqual(missing.status, 404)

    async def test_handle_static_empty_filename_serves_index(self):
        response = await self.server.handle_static(SimpleNamespace(match_info={"filename": ""}))
        self.assertEqual(response.status, 200)

    async def test_cors_middleware_preflight_and_passthrough(self):
        async def handler(_request):
            return web.Response(text="ok")

        passthrough = await self.server.cors_middleware(SimpleNamespace(method="GET"), handler)
        self.assertEqual(passthrough.text, "ok")
        self.assertEqual(passthrough.headers["Access-Control-Allow-Origin"], "*")

        preflight = await self.server.cors_middleware(SimpleNamespace(method="OPTIONS"), handler)
        self.assertEqual(preflight.status, 200)
        self.assertEqual(preflight.headers["Access-Control-Allow-Methods"], "GET,POST,PUT,DELETE,OPTIONS")

    async def test_start_async_server_bootstraps_site(self):
        fake_runner = MagicMock()
        fake_runner.setup = AsyncMock()
        fake_site = MagicMock()
        fake_site.start = AsyncMock()

        with patch.object(self.server.web, "Application", return_value="app"), patch.object(
            self.server, "setup_routes"
        ) as setup_routes, patch.object(self.server.web, "AppRunner", return_value=fake_runner), patch.object(
            self.server.web, "TCPSite", return_value=fake_site
        ), patch.object(self.server.asyncio, "sleep", new=AsyncMock(side_effect=RuntimeError("stop"))), patch.object(
            self.server, "seed_if_needed"
        ), patch("builtins.print"):
            with self.assertRaisesRegex(RuntimeError, "stop"):
                await self.server.start_async_server()

        setup_routes.assert_called_once_with("app")
        fake_site.start.assert_awaited_once_with()


if __name__ == "__main__":
    unittest.main(verbosity=2)