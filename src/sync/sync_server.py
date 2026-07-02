import json
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from core.learning_analyzer import refresh_learning_analysis
from core.review_scheduler import reconcile_review_tasks
from sync.leetcode_sync import (
    RECORDS_PATH,
    REVIEWS_PATH,
    SYNC_STATE_PATH,
    _load_json,
    _record_key,
    _save_json,
    _sync_review,
    load_leetcode_config,
    normalize_synced_submission,
    repair_synced_identity_data,
)


HOST = "127.0.0.1"
PORT = 8765
from app_paths import BASE_DIR
STATE_PATH = BASE_DIR / "data" / "local_push_sync_state.json"

_server = None
_thread = None


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _write_state(data):
    state = _load_json(STATE_PATH, {})
    if not isinstance(state, dict):
        state = {}
    state.update(data)
    state["updated_at"] = _now()
    _save_json(STATE_PATH, state)
    return state


def get_local_push_status():
    state = _load_json(STATE_PATH, {})
    if not isinstance(state, dict):
        state = {}
    state["running"] = is_local_push_server_running()
    state["host"] = HOST
    state["port"] = PORT
    return state


def process_pushed_submissions(payload):
    if not isinstance(payload, dict):
        raise ValueError("payload must be object")

    config = load_leetcode_config()
    username = str(
        payload.get("username")
        or config.get("leetcode_username", "")
        or ""
    ).strip()
    site = str(config.get("site", "leetcode.cn") or "leetcode.cn")
    submissions = payload.get("submissions", [])
    if not isinstance(submissions, list):
        submissions = []

    normalized_submissions = []
    for item in submissions:
        if not isinstance(item, dict):
            continue
        normalized_submissions.append({
            "title": item.get("title", ""),
            "title_slug": (
                item.get("title_slug")
                or item.get("titleSlug")
                or item.get("slug")
                or ""
            ),
            "status": (
                item.get("status")
                or item.get("statusDisplay")
                or ""
            ),
            "language": item.get("language") or item.get("lang") or "",
            "submit_time": item.get("submit_time") or item.get("submitTime") or "",
            "timestamp": item.get("timestamp") or "",
        })

    records = _load_json(RECORDS_PATH, [])
    reviews = _load_json(REVIEWS_PATH, [])
    if not isinstance(records, list) or not isinstance(reviews, list):
        raise ValueError("records.json or reviews.json is not a list")

    records, reviews, identity_repaired = repair_synced_identity_data(
        records,
        reviews,
    )
    existing_keys = {
        _record_key(record)
        for record in records
        if isinstance(record, dict)
    }

    imported_records = []
    skipped = 0
    unmapped = 0
    for submission in sorted(
        normalized_submissions,
        key=lambda item: str(item.get("submit_time", "")),
    ):
        record = normalize_synced_submission(submission)
        if record is None:
            skipped += 1
            unmapped += 1
            continue
        record["source"] = "leetcode_auto_sync"
        record["sync_transport"] = "localhost_push"
        key = _record_key(record)
        if key in existing_keys:
            skipped += 1
            continue
        records.append(record)
        existing_keys.add(key)
        _sync_review(reviews, record, records)
        imported_records.append(record)

    reviews_changed = reconcile_review_tasks(reviews, records)
    if imported_records or identity_repaired:
        _save_json(RECORDS_PATH, records)
    if imported_records or reviews_changed or identity_repaired:
        _save_json(REVIEWS_PATH, reviews)

    try:
        refresh_learning_analysis()
    except Exception:
        pass

    state = {
        "success": True,
        "username": username,
        "site": site,
        "last_attempt_at": _now(),
        "last_success_at": _now(),
        "last_received_at": _now(),
        "transport": "localhost_push",
        "fetched": len(normalized_submissions),
        "imported": len(imported_records),
        "skipped": skipped,
        "unmapped": unmapped,
        "from_cache": False,
        "sync_source": "localhost_push",
        "consecutive_failures": 0,
        "last_error_type": "",
        "last_error_message": "",
        "recent_imported": [
            {
                "problem_id": item.get("problem_id", ""),
                "title": item.get("title", ""),
                "status": item.get("status", ""),
                "submit_time": item.get("submit_time", ""),
            }
            for item in imported_records[-10:]
        ],
    }
    _save_json(SYNC_STATE_PATH, state)
    _write_state({
        **state,
        "received": len(normalized_submissions),
        "message": "Localhost push sync completed.",
    })

    return {
        "success": True,
        "transport": "localhost_push",
        "received": len(normalized_submissions),
        "imported": len(imported_records),
        "skipped": skipped,
        "unmapped": unmapped,
        "recent_imported": state["recent_imported"],
        "message": "同步完成",
    }


class _Handler(BaseHTTPRequestHandler):
    def _send_json(self, status, data):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._send_json(200, {"ok": True})

    def do_GET(self):
        if self.path in {"/health", "/status"}:
            self._send_json(200, {
                "ok": True,
                "service": "LeetCoach Localhost Push Sync",
                **get_local_push_status(),
            })
            return
        self._send_json(404, {"ok": False, "error": "not found"})

    def do_POST(self):
        if self.path != "/leetcode-submissions":
            self._send_json(404, {"ok": False, "error": "not found"})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            result = process_pushed_submissions(payload)
            self._send_json(200, {"ok": True, **result})
        except Exception as error:
            _write_state({
                "success": False,
                "last_attempt_at": _now(),
                "last_failure_at": _now(),
                "transport": "localhost_push",
                "last_error_type": type(error).__name__,
                "last_error_message": str(error),
            })
            self._send_json(500, {
                "ok": False,
                "error_type": type(error).__name__,
                "error_message": str(error),
            })

    def log_message(self, format_string, *args):
        return


class _ReusableServer(ThreadingHTTPServer):
    allow_reuse_address = True


def is_local_push_server_running():
    return _server is not None


def start_local_push_server():
    global _server, _thread
    if _server is not None:
        return True, f"本地同步服务已运行：http://{HOST}:{PORT}"

    try:
        _server = _ReusableServer((HOST, PORT), _Handler)
        _thread = threading.Thread(target=_server.serve_forever, daemon=True)
        _thread.start()
        _write_state({
            "running": True,
            "host": HOST,
            "port": PORT,
            "started_at": _now(),
            "transport": "localhost_push",
            "last_error_type": "",
            "last_error_message": "",
            "message": "Localhost push server started.",
        })
        return True, f"本地同步服务已启动：http://{HOST}:{PORT}"
    except OSError as error:
        _server = None
        _thread = None
        _write_state({
            "running": False,
            "host": HOST,
            "port": PORT,
            "last_error_type": type(error).__name__,
            "last_error_message": str(error),
            "message": "Localhost push server failed to start.",
        })
        return False, f"本地同步服务启动失败：{error}"


def stop_local_push_server():
    global _server, _thread
    if _server is None:
        return
    _server.shutdown()
    _server.server_close()
    _server = None
    if _thread is not None:
        _thread.join(timeout=2)
        _thread = None
    _write_state({
        "running": False,
        "stopped_at": _now(),
        "message": "Localhost push server stopped.",
    })


def format_local_push_status(status=None):
    status = status if isinstance(status, dict) else get_local_push_status()
    running_text = "运行中" if status.get("running") else "未运行"
    lines = [
        "===== 本地推送同步服务 =====",
        "",
        f"状态：{running_text}",
        f"地址：http://{status.get('host', HOST)}:{status.get('port', PORT)}",
        f"最近成功：{status.get('last_success_at', '暂无')}",
        f"最近收到：{status.get('fetched', status.get('received', 0))} 条",
        f"新增记录：{status.get('imported', 0)} 条",
        f"跳过重复：{status.get('skipped', 0)} 条",
    ]
    if status.get("last_error_message"):
        lines.extend([
            "",
            "最近错误：",
            f"{status.get('last_error_type', 'Error')}：{status.get('last_error_message')}",
        ])
    lines.extend([
        "",
        "说明：",
        "打开 LeetCoach 后服务会自动启动。",
        "Chrome 扩展在力扣页面抓到提交记录后，会自动推送到这里。",
    ])
    return "\n".join(lines)


def format_local_push_status(status=None):
    status = status if isinstance(status, dict) else get_local_push_status()
    running_text = "运行中" if status.get("running") else "未启动"
    last_success = status.get("last_received_at") or status.get("last_success_at") or "暂无"
    received = status.get("received", status.get("fetched", 0))
    imported = status.get("imported", 0)
    skipped = status.get("skipped", 0)

    lines = [
        "===== 本地推送同步 =====",
        "",
        f"服务状态：{running_text}",
        f"服务地址：http://{status.get('host', HOST)}:{status.get('port', PORT)}",
        f"最近推送：{last_success}",
        f"本次读取：{received} 条",
        f"新增记录：{imported} 条",
        f"跳过重复：{skipped} 条",
    ]

    if status.get("last_error_message"):
        lines.extend([
            "",
            "最近错误：",
            f"{status.get('last_error_type', 'Error')}：{status.get('last_error_message')}",
        ])

    if status.get("running") and not status.get("last_success_at"):
        lines.extend([
            "",
            "当前状态：服务已启动，正在等待 Chrome 扩展推送。",
        ])
    elif status.get("last_success_at") and int(imported or 0) == 0:
        lines.extend([
            "",
            "当前状态：同步成功，但没有新增记录。通常表示最近提交已存在于本地。",
        ])
    elif int(imported or 0) > 0:
        lines.extend([
            "",
            "当前状态：同步成功，已写入新的刷题记录。",
        ])

    lines.extend([
        "",
        "说明：",
        "LeetCoach 打开后会启动本地服务。",
        "Chrome 扩展在力扣页面读取到最近提交后，会自动推送到这里。",
    ])
    return "\n".join(lines)


if __name__ == "__main__":
    ok, message = start_local_push_server()
    print(message)
    if ok:
        try:
            threading.Event().wait()
        except KeyboardInterrupt:
            stop_local_push_server()
