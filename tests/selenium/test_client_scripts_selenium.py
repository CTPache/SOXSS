"""Browser-level guards for the client payload scripts ``logger.js`` and ``link2fetch.js``.

Unlike ``test_soxss_selenium`` this suite does **not** boot the SOXSS/victim stack.
It loads the two real script files into a blank headless-Chrome page and drives the
DOM directly, so it stays fast and deterministic while still executing the shipped JS.

It exists to lock in the cleanup that removed the ``window.loadInputLogger`` stub from
``logger.js`` and the matching call inside ``link2fetch.js``'s ``notifyNavigationHooks``.
The invariant that made the stub unnecessary is that the logger binds a single
delegated ``focusout`` listener on ``document``, which survives the ``body.innerHTML``
replacement performed by link2fetch navigations. These tests prove input logging keeps
working across such a navigation with no re-initialisation hook.
"""

import json
import unittest
from pathlib import Path

from selenium import webdriver
from selenium.common.exceptions import WebDriverException


ROOT = Path(__file__).resolve().parents[2]
LOGGER_JS = ROOT / "server" / "scripts" / "logger.js"
LINK2FETCH_JS = ROOT / "server" / "scripts" / "link2fetch.js"

# Minimal page: one pre-existing input plus a container we can repopulate to emulate a
# link2fetch SPA navigation (which swaps document.body.innerHTML).
PAGE = "data:text/html,<body><input id='a'/><div id='root'></div></body>"


class ClientScriptsSeleniumTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.logger_src = LOGGER_JS.read_text(encoding="utf-8")
        cls.link2fetch_src = LINK2FETCH_JS.read_text(encoding="utf-8")

        options = webdriver.ChromeOptions()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-gpu")
        try:
            cls.driver = webdriver.Chrome(options=options)
        except WebDriverException as exc:  # no browser/driver available in this env
            raise unittest.SkipTest(f"Chrome WebDriver unavailable: {exc}")

    @classmethod
    def tearDownClass(cls):
        driver = getattr(cls, "driver", None)
        if driver is not None:
            driver.quit()

    def setUp(self):
        self.driver.get(PAGE)
        # Record every message the logger emits and every link2fetch:load event.
        self.driver.execute_script(
            "window.__sent = [];"
            "window.sendMessage = function (m) { window.__sent.push(m); };"
            "window.__l2fEvents = [];"
            "document.addEventListener('link2fetch:load',"
            "  function (e) { window.__l2fEvents.push(e.detail && e.detail.url); });"
        )
        self._inject(self.logger_src)
        self._inject(self.link2fetch_src)

    def _inject(self, source):
        self.driver.execute_script(
            "var s = document.createElement('script');"
            "s.textContent = arguments[0];"
            "document.body.appendChild(s);",
            source,
        )

    def _blur_input(self, element_id, value):
        self.driver.execute_script(
            "var i = document.getElementById(arguments[0]);"
            "i.value = arguments[1];"
            "i.dispatchEvent(new Event('focusout', { bubbles: true }));",
            element_id,
            value,
        )

    def _logged_values(self):
        msgs = self.driver.execute_script("return window.__sent.map(function (m) { return m.msg; });")
        return [json.loads(m)["log"] for m in msgs]

    def test_logger_captures_input_via_delegated_focusout(self):
        self._blur_input("a", "baseline_val")
        self.assertIn("baseline_val", self._logged_values())

    def test_input_logging_survives_link2fetch_navigation(self):
        # Log once before navigating.
        self._blur_input("a", "before_nav")
        self.assertIn("before_nav", self._logged_values())

        # Emulate a link2fetch navigation: swap the body (as loadPage does) then run the
        # navigation hooks. This must not throw even though loadInputLogger no longer exists.
        nav_error = self.driver.execute_script(
            "try {"
            "  document.body.innerHTML = '<input id=\"b\"/>';"
            "  window.notifyNavigationHooks(new URL(window.location.href));"
            "  return null;"
            "} catch (e) { return String(e); }"
        )
        self.assertIsNone(nav_error, f"notifyNavigationHooks raised: {nav_error}")

        # The compatibility stub is gone and is not needed.
        self.assertEqual(
            self.driver.execute_script("return typeof window.loadInputLogger;"),
            "undefined",
        )
        # The generic navigation hook still fires.
        self.assertTrue(self.driver.execute_script("return window.__l2fEvents.length > 0;"))

        # The freshly inserted input is still logged by the surviving delegated listener.
        self._blur_input("b", "after_nav")
        self.assertIn("after_nav", self._logged_values())

    def test_sources_do_not_reference_loadInputLogger(self):
        # Static guard so the removed hook cannot silently creep back in.
        self.assertNotIn("loadInputLogger", self.logger_src)
        self.assertNotIn("loadInputLogger", self.link2fetch_src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
