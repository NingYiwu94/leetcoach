import json
import os
import subprocess
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


from app_paths import CHROME_EXTENSION_DIR
EXTENSION_DIR = CHROME_EXTENSION_DIR
BRIDGE_HOST = "127.0.0.1"
BRIDGE_PORT = 18777


def find_chrome_executable():
    candidates = [
        Path(os.environ.get("PROGRAMFILES", ""))
        / "Google" / "Chrome" / "Application" / "chrome.exe",
        Path(os.environ.get("PROGRAMFILES(X86)", ""))
        / "Google" / "Chrome" / "Application" / "chrome.exe",
        Path(os.environ.get("LOCALAPPDATA", ""))
        / "Google" / "Chrome" / "Application" / "chrome.exe"
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def open_chrome_extension_page():
    chrome_path = find_chrome_executable()
    if chrome_path is None:
        return False, "未找到 Google Chrome。"

    try:
        os.startfile(str(EXTENSION_DIR))
        subprocess.Popen(
            [str(chrome_path), "chrome://extensions/"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        return True, (
            "已打开 Chrome 扩展管理页和同步组件目录。"
            "请开启开发者模式，点击“加载已解压的扩展程序”，"
            "选择 extensions/chrome 目录。"
            "如果已经安装过，请点击扩展卡片上的“重新加载”，"
            "并确认版本为 1.2.0。"
        )
    except OSError as exc:
        return False, f"无法打开扩展安装页面：{exc}"


def _open_normal_chrome(username):
    chrome_path = find_chrome_executable()
    if chrome_path is None:
        return False

    try:
        subprocess.Popen(
            [str(chrome_path), f"https://leetcode.cn/u/{username}/"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        return True
    except OSError:
        return False


def open_leetcode_page(username=""):
    username = str(username or "").strip()
    chrome_path = find_chrome_executable()
    if chrome_path is None:
        return False, "未找到 Google Chrome。"

    url = (
        f"https://leetcode.cn/u/{username}/"
        if username
        else "https://leetcode.cn/"
    )
    try:
        subprocess.Popen(
            [str(chrome_path), url],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        return True, f"已打开 {url}"
    except OSError as exc:
        return False, f"无法打开力扣页面：{exc}"


class SyncBridge:
    def __init__(self, username, limit, mode="sync"):
        self.task = {
            "task_id": uuid.uuid4().hex,
            "username": username,
            "limit": max(1, int(limit)),
            "mode": mode
        }
        self.result = None
        self.result_event = threading.Event()
        self.server = None
        self.thread = None

    def start(self):
        bridge = self

        class Handler(BaseHTTPRequestHandler):
            def _send_json(self, status, data):
                body = json.dumps(
                    data,
                    ensure_ascii=False
                ).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header(
                    "Access-Control-Allow-Headers",
                    "Content-Type"
                )
                self.send_header(
                    "Access-Control-Allow-Methods",
                    "GET, POST, OPTIONS"
                )
                self.end_headers()
                self.wfile.write(body)

            def do_OPTIONS(self):
                self._send_json(200, {"ok": True})

            def do_GET(self):
                if self.path != "/task":
                    self._send_json(404, {"error": "not found"})
                    return

                if bridge.result_event.is_set():
                    self._send_json(200, {"task": None})
                else:
                    self._send_json(200, {"task": bridge.task})

            def do_POST(self):
                if self.path != "/result":
                    self._send_json(404, {"error": "not found"})
                    return

                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    payload = json.loads(
                        self.rfile.read(length).decode("utf-8")
                    )
                except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
                    self._send_json(400, {"error": "invalid json"})
                    return

                if payload.get("task_id") != bridge.task["task_id"]:
                    self._send_json(409, {"error": "task mismatch"})
                    return

                bridge.result = payload
                bridge.result_event.set()
                self._send_json(200, {"ok": True})

            def log_message(self, format_string, *args):
                return

        class ReusableServer(ThreadingHTTPServer):
            allow_reuse_address = True

        self.server = ReusableServer(
            (BRIDGE_HOST, BRIDGE_PORT),
            Handler
        )
        self.thread = threading.Thread(
            target=self.server.serve_forever,
            daemon=True
        )
        self.thread.start()

    def wait(self, timeout=45):
        self.result_event.wait(timeout)
        return self.result

    def close(self):
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
            self.server = None
        if self.thread is not None:
            self.thread.join(timeout=2)
            self.thread = None


def fetch_recent_submissions_with_browser(
    username,
    limit=20,
    allow_browser_open=True
):
    try:
        bridge = SyncBridge(username, limit, mode="sync")
        bridge.start()
    except OSError as exc:
        return {
            "success": False,
            "submissions": [],
            "error_type": "BrowserBridgeError",
            "error_message": f"本地同步端口启动失败：{exc}",
            "request_url": f"http://{BRIDGE_HOST}:{BRIDGE_PORT}",
            "raw_response_preview": ""
        }

    try:
        result = bridge.wait(timeout=6)
        if result is None and allow_browser_open:
            if not _open_normal_chrome(username):
                return {
                    "success": False,
                    "submissions": [],
                    "error_type": "BrowserStartError",
                    "error_message": "无法打开本机 Chrome。",
                    "request_url": f"http://{BRIDGE_HOST}:{BRIDGE_PORT}",
                    "raw_response_preview": ""
                }
            result = bridge.wait(timeout=42)
        elif result is None:
            return {
                "success": False,
                "submissions": [],
                "error_type": "SilentBrowserSessionUnavailable",
                "error_message": (
                    "未检测到可响应的力扣浏览器标签页。"
                    "为避免打断使用，本次未自动打开 Chrome。"
                ),
                "request_url": f"http://{BRIDGE_HOST}:{BRIDGE_PORT}",
                "raw_response_preview": ""
            }
        if not isinstance(result, dict):
            return {
                "success": False,
                "submissions": [],
                "error_type": "BrowserExtensionUnavailable",
                "error_message": (
                    "未收到 Chrome 同步组件响应。"
                    "请确认 extensions/chrome 已加载并启用。"
                ),
                "request_url": f"http://{BRIDGE_HOST}:{BRIDGE_PORT}",
                "raw_response_preview": ""
            }

        if not result.get("success"):
            return {
                "success": False,
                "submissions": [],
                "error_type": result.get(
                    "error_type",
                    "BrowserExtensionError"
                ),
                "error_message": result.get(
                    "error_message",
                    "Chrome 同步组件未能读取提交记录。"
                ),
                "request_url": result.get(
                    "request_url",
                    "https://leetcode.cn/graphql/"
                ),
                "raw_response_preview": str(
                    result.get("raw_response_preview", "")
                )[:500],
                "browser_attempts": result.get("attempts", [])
            }

        submissions = result.get("submissions", [])
        if not isinstance(submissions, list):
            submissions = []

        return {
            "success": True,
            "submissions": submissions,
            "error_type": "",
            "error_message": "",
            "request_url": result.get(
                "request_url",
                "https://leetcode.cn/graphql/"
            ),
            "raw_response_preview": str(
                result.get("raw_response_preview", "")
            )[:500],
            "browser_attempts": result.get("attempts", []),
            "from_cache": bool(result.get("from_cache")),
            "cache_time": str(result.get("cache_time", ""))
        }
    finally:
        bridge.close()


def diagnose_browser_sync(username, limit=20):
    try:
        bridge = SyncBridge(username, limit, mode="diagnose")
        bridge.start()
    except OSError as exc:
        return {
            "success": False,
            "error_type": "BrowserBridgeError",
            "error_message": f"本地同步端口启动失败：{exc}"
        }

    try:
        # The MV3 service worker may wake on the next poll/alarm cycle,
        # so diagnostics need a longer wait than interactive sync.
        result = bridge.wait(timeout=40)
        if result is None:
            return {
                "success": False,
                "error_type": "BrowserExtensionUnavailable",
                "error_message": (
                    "在等待 40 秒后仍未收到 Chrome 同步组件响应。"
                    "这通常表示扩展后台尚未唤醒，或当前 Chrome 会话"
                    "没有可用的力扣页面上下文。"
                )
            }
        if not isinstance(result, dict):
            return {
                "success": False,
                "error_type": "BrowserExtensionError",
                "error_message": "同步组件返回了无法识别的诊断结果。"
            }
        if (
            result.get("success")
            and not result.get("mode")
            and "extension_online" not in result
        ):
            return {
                "success": False,
                "error_type": "LegacyExtensionVersion",
                "error_message": (
                    "当前 Chrome 中运行的仍是旧版 LeetCoach 扩展。"
                    "请打开 chrome://extensions 刷新扩展后重试。"
                )
            }
        return result
    finally:
        bridge.close()
