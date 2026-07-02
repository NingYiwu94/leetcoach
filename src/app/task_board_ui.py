import json
import math
import os
import re
import struct
import sys
import threading
import tkinter as tk
from datetime import date
from pathlib import Path
from tkinter import simpledialog, ttk

from agent.agent_memory import analyze_trend
from agent.agent_observer import collect_learning_observation, format_learning_observation
from agent.agent_policy import decide_next_agent_action, format_agent_decision
from agent.agent_decision_report import (
    format_agent_decision_summary,
    summarize_agent_decisions,
)
from agent.agent_tool_report import format_agent_tool_summary, summarize_agent_tool_calls
from agent.agent_tools import format_agent_tools
from agent.agent_pending_action_executor import (
    confirm_pending_action,
    get_first_active_pending_action,
    reject_pending_action,
    snooze_pending_action,
)
from agent.agent_pending_report import (
    format_pending_actions_report,
    summarize_pending_actions,
)
from agent.agent_feedback_memory import (
    analyze_user_feedback,
    format_user_feedback_report,
    load_user_learning_profile,
    save_user_learning_profile,
)
from agent.agent_policy_compare import (
    compare_rule_and_llm_policy,
    format_policy_comparison,
)
from agent.agent_policy_compare_report import (
    format_policy_comparison_summary,
    summarize_policy_comparisons,
)
from agent.agent_policy_benchmark import (
    format_agent_policy_benchmark_report,
    run_agent_policy_benchmark,
)
from agent.agent_policy_benchmark_report import (
    format_agent_policy_benchmark_summary,
    summarize_agent_policy_benchmarks,
)
from agent.agent_state import analyze_learning_state, format_agent_state
from ai.ai_solution import (
    format_solution,
    get_or_generate_solution,
    get_solution_note,
    get_solution_status,
)
from ai.ai_task_queue import get_recent_ai_tasks, log_ai_task
from ai.ai_plan_evaluator import (
    format_recent_plan_evaluations,
    get_recent_plan_evaluations,
)
from ai.ai_plan_adjuster import (
    format_ai_next_week_plan,
    generate_ai_next_week_plan,
)
from ai.ai_plan_generator import (
    apply_week_plan_next,
    format_ai_week_plan_next,
    generate_ai_week_plan_next,
)
from ai.ai_weekly_review import (
    format_ai_weekly_review,
    generate_ai_weekly_review,
)
from sync.browser_sync import open_chrome_extension_page, open_leetcode_page
from tools.data_validator import run_all_validations
from sync.leetcode_sync import (
    format_sync_brief,
    format_recent_synced_records,
    format_sync_diagnostics,
    get_recent_synced_records,
    get_auto_sync_decision,
    get_sync_diagnostics,
    get_sync_overview,
    load_leetcode_config,
    sync_leetcode_submissions,
)
from llm.llm_logger import format_recent_llm_logs, get_recent_llm_logs
from labs.llm_experiment_runner import (
    format_llm_experiment_batch_report,
    format_recent_llm_experiment_batch_reports,
    load_llm_experiment_batch_reports,
    run_llm_experiment_batch,
)
from labs.local_model_lab import (
    compare_cloud_vs_local_embedding,
    format_cloud_vs_local_embedding_comparison,
    format_local_embedding_test,
    format_local_embedding_warmup,
    format_local_service_status,
    test_local_embedding,
    test_local_embedding_warmup,
    test_local_service,
)
from labs.local_embedding_rag_experiment import (
    format_local_embedding_rag_experiment,
    run_local_embedding_rag_experiment,
)
from labs.local_embedding_rag_report import (
    format_local_embedding_rag_summary,
    summarize_local_embedding_rag_experiments,
)
from planning.plan_automation import (
    build_plan_context_fingerprint,
)
from planning.plan_manager import (
    format_current_plan,
    format_plan_archives,
    format_plan_backups,
    get_plan_management_data,
)
from library.problem_notes import (
    MASTERY_LABELS,
    get_problem_note,
    get_problem_review_summary,
    save_problem_note,
)
from library.problem_library import get_problem_library_data, get_topic_detail
from labs.prompt_experiment import (
    format_prompt_comparison_result,
    run_plan_prompt_comparison,
)
from labs.prompt_experiment_report import (
    format_prompt_experiment_summary,
    summarize_prompt_experiments,
)
from llm.prompt_loader import load_prompt_template
from core.recorder import (
    format_mistake_stats,
    format_records,
    generate_week_summary,
    get_all_records,
    get_mistake_stats,
)
from rag.rag_engine import (
    format_rag_debug,
    format_recent_rag_debug,
    get_problem_rag_context,
    get_recent_rag_debug,
    load_last_rag_debug,
)
from rag.rag_eval import (
    format_rag_eval_report,
    run_rag_retrieval_quality_test,
)
from rag.rag_trace import format_recent_rag_traces, get_recent_rag_traces
from rag.rag_trace_report import format_rag_trace_summary, summarize_rag_traces
from rag.rag_ab_experiment import (
    format_rag_ab_experiment_result,
    run_rag_plan_ab_experiment,
)
from rag.rag_ab_report import (
    format_rag_ab_summary,
    summarize_rag_ab_experiments,
)
from rag.rag_memory_quality import (
    format_rag_memory_quality_report,
    run_rag_memory_quality_audit,
)
from rag.rag_enhanced_memory_experiment import (
    format_enhanced_memory_ab_result,
    run_enhanced_memory_ab_experiment,
)
from rag.rag_enhanced_memory_report import (
    format_enhanced_memory_summary,
    summarize_enhanced_memory_experiments,
)
from sync.sync_server import (
    format_local_push_status,
    get_local_push_status,
    start_local_push_server,
)
from agent.silent_agent import run_silent_agent
from app.task_board import complete_task, get_task_board_data


BACKGROUND = "#FFFFFF"
PAGE_BG = "#F8F7F4"
SIDEBAR = "#F5F3EF"
CARD_BG = "#FEFEFD"
CARD_BORDER = "#E6E1DA"
CARD_HOVER_BORDER = "#D8D1C7"
TEXT = "#171717"
TEXT_SECONDARY = "#5F6368"
TEXT_WEAK = "#9AA0A6"
PLACEHOLDER = "#B0B4BA"
ACCENT = "#E53935"
ACCENT_DARK = "#D93025"
ACCENT_SOFT = "#FDECEA"
ACCENT_PRESSED = "#C62828"
SUCCESS = "#2EAD6B"
WARNING = "#F59E0B"
INFO = "#2563EB"
SOFT_FILL = "#F0EEE9"
SOFT_FILL_HOVER = "#E8E4DE"
SOFT_FILL_PRESSED = "#DDD7CE"
LINE = "#E9E4DD"
from app_paths import ASSETS_DIR, BASE_DIR as APP_DIR
APP_ICON_PATH = ASSETS_DIR / "leetcoach.ico"
RECORDS_PATH = APP_DIR / "data" / "records.json"
APP_SETTINGS_PATH = APP_DIR / "config" / "app_settings.json"


def _load_json_file(path, default):
    if not path.exists():
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return default


def _show_llm_lab():
    settings = _load_json_file(
        APP_SETTINGS_PATH,
        {"developer_mode": False, "show_llm_lab": False},
    )
    return bool(settings.get("developer_mode") or settings.get("show_llm_lab"))


def _clean_problem_id(value):
    text = str(value or "")
    for prefix in ("题号：", "题号:", "题号"):
        text = text.replace(prefix, "")
    return text.strip()


def _short_topic_title(value):
    text = str(value or "").strip()
    for keyword in [
        "数组",
        "链表",
        "哈希表",
        "字符串",
        "栈",
        "队列",
        "二叉树",
        "回溯",
        "动态规划",
        "贪心",
        "图论",
    ]:
        if keyword in text:
            return keyword
    for separator in ("：", ":", "-", "—", "与", "和", "基础", "入门", "巩固"):
        if separator in text:
            text = text.split(separator)[0].strip()
    return text or "计划"


def _problem_activity_summary(problem_id):
    problem_id = _clean_problem_id(problem_id)
    records = _load_json_file(RECORDS_PATH, [])
    if not isinstance(records, list):
        records = []

    matched = [
        record for record in records
        if (
            isinstance(record, dict)
            and _clean_problem_id(record.get("problem_id")) == problem_id
        )
    ]
    matched.sort(
        key=lambda record: (
            str(record.get("submit_time", "")),
            str(record.get("date", "")),
            str(record.get("time", "")),
        ),
        reverse=True,
    )

    latest = matched[0] if matched else {}
    mistake_counts = {}
    source_counts = {}
    for record in matched:
        mistake_type = str(record.get("mistake_type", "") or "未分类").strip()
        if not mistake_type:
            mistake_type = "未分类"
        mistake_counts[mistake_type] = mistake_counts.get(mistake_type, 0) + 1

        source = str(record.get("source", "") or "manual").strip()
        source_counts[source] = source_counts.get(source, 0) + 1

    mistake_items = [
        item for item in mistake_counts.items()
        if item[0] not in {"未分类", "未知", ""}
    ]
    if mistake_items:
        main_mistake = sorted(
            mistake_items,
            key=lambda item: item[1],
            reverse=True,
        )[0][0]
    elif mistake_counts:
        main_mistake = "暂无明确分类"
    else:
        main_mistake = "暂无"

    return {
        "count": len(matched),
        "latest": latest,
        "latest_status": str(latest.get("status", "") or "暂无"),
        "latest_time": (
            str(latest.get("submit_time", "")).strip()
            or " ".join(
                part for part in [
                    str(latest.get("date", "")).strip(),
                    str(latest.get("time", "")).strip(),
                ] if part
            )
            or "暂无"
        ),
        "main_mistake": main_mistake,
        "source": (
            sorted(source_counts.items(), key=lambda item: item[1], reverse=True)[0][0]
            if source_counts else "暂无"
        ),
        "recent_records": matched[:3],
    }


def _set_windows_app_id():
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "LeetCoach.TaskBoard"
        )
    except Exception:
        pass


def _ensure_app_icon():
    if APP_ICON_PATH.exists():
        return APP_ICON_PATH

    APP_ICON_PATH.parent.mkdir(parents=True, exist_ok=True)
    size = 32
    red = (0x35, 0x39, 0xE5, 0xFF)  # BGRA for #E53935
    white = (0xFF, 0xFF, 0xFF, 0xFF)

    rows = []
    for y in range(size):
        row = bytearray()
        for x in range(size):
            is_l_vertical = 9 <= x <= 13 and 7 <= y <= 24
            is_l_bottom = 9 <= x <= 23 and 21 <= y <= 24
            color = white if is_l_vertical or is_l_bottom else red
            row.extend(color)
        rows.append(row)

    xor_bitmap = b"".join(reversed(rows))
    and_mask = b"\x00" * (size * size // 8)
    bitmap_header = struct.pack(
        "<IIIHHIIIIII",
        40,
        size,
        size * 2,
        1,
        32,
        0,
        len(xor_bitmap),
        0,
        0,
        0,
        0,
    )
    image_data = bitmap_header + xor_bitmap + and_mask
    icon_header = struct.pack("<HHH", 0, 1, 1)
    directory = struct.pack(
        "<BBBBHHII",
        size,
        size,
        0,
        0,
        1,
        32,
        len(image_data),
        22,
    )
    APP_ICON_PATH.write_bytes(icon_header + directory + image_data)
    return APP_ICON_PATH


class TaskBoardApp:
    def __init__(self, root):
        self.root = root
        self.data = {}
        self.mode = "today"
        self.busy_task_id = None
        self.plan_generating = False
        self.solution_jobs = set()
        self.ai_job_status = {
            "state": "idle",
            "title": "",
            "message": "",
        }
        self.toast_after_id = None

        self.sync_output = None
        self.review_output = None
        self.ai_output = None
        self.more_output = None
        self.selected_topic = None
        self.selected_problem = None
        self.library_detail_view = None
        self.content_width = 820
        self.resize_after_id = None
        self.scroll_after_id = None
        self.pending_scroll_args = None
        self.scroll_refresh_after_id = None
        self.render_after_id = None

        self.nav_buttons = {}
        self.nav_labels = {}
        self.body = None
        self.body_window = None
        self.app_icon = None
        self.transition_overlay = None
        self.transition_after_id = None

        self.root.title("LeetCoach")
        self._apply_app_icon()
        self.root.geometry("1000x720")
        self.root.minsize(900, 640)
        self.root.configure(bg=BACKGROUND)
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(0, weight=1)

        self._configure_styles()
        self._build_sidebar()
        self._build_content()
        self._start_local_push_sync_service()
        self.refresh()
        self.root.after(400, self._auto_sync_on_start)
        self.root.after(1200, lambda: self._check_plan_generation_async("startup"))

    def _configure_styles(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure(
            "LeetCoach.Horizontal.TProgressbar",
            troughcolor=SOFT_FILL,
            background=ACCENT,
            bordercolor=SOFT_FILL,
            lightcolor=ACCENT,
            darkcolor=ACCENT,
            thickness=8,
        )

    def _start_local_push_sync_service(self):
        try:
            start_local_push_server()
        except Exception:
            pass

    def _apply_app_icon(self):
        try:
            icon_path = _ensure_app_icon()
            self.root.iconbitmap(str(icon_path))
        except Exception:
            pass

        try:
            self.app_icon = tk.PhotoImage(width=32, height=32)
            self.app_icon.put(ACCENT, to=(0, 0, 32, 32))
            self.app_icon.put("#FFFFFF", to=(9, 7, 14, 25))
            self.app_icon.put("#FFFFFF", to=(9, 21, 24, 25))
            self.root.iconphoto(True, self.app_icon)
        except Exception:
            pass

    def _build_sidebar(self):
        self.sidebar = tk.Frame(
            self.root,
            width=180,
            bg=SIDEBAR,
            padx=16,
            pady=18,
        )
        self.sidebar.grid(row=0, column=0, sticky="ns")
        self.sidebar.grid_propagate(False)

        brand = tk.Frame(self.sidebar, bg=SIDEBAR)
        brand.pack(fill="x", pady=(2, 26))
        tk.Label(
            brand,
            text="L",
            width=2,
            height=1,
            bg=ACCENT,
            fg="white",
            font=("Microsoft YaHei UI", 14, "bold"),
        ).pack(side="left")
        tk.Label(
            brand,
            text="LeetCoach",
            bg=SIDEBAR,
            fg=TEXT,
            font=("Microsoft YaHei UI", 13, "bold"),
        ).pack(side="left", padx=10)

        items = [
            ("today", "今天"),
            ("week", "计划"),
            ("library", "题库"),
            ("ai", "AI 解题"),
            ("sync", "同步"),
            ("more", "设置"),
        ]
        for key, label in items:
            button = self._nav_button(
                label,
                lambda selected=key: self.set_mode(selected),
                active=(key == "today"),
            )
            self.nav_buttons[key] = button
            self.nav_labels[key] = label

        tk.Button(
            self.sidebar,
            text="退出",
            command=self.root.destroy,
            relief="flat",
            anchor="w",
            bg=SIDEBAR,
            activebackground=ACCENT_SOFT,
            fg=TEXT_SECONDARY,
            font=("Microsoft YaHei UI", 10),
            padx=12,
            pady=10,
            cursor="hand2",
        ).pack(side="bottom", fill="x", pady=(12, 0))

    def _nav_button(self, text, command, active=False):
        button = tk.Button(
            self.sidebar,
            text=self._nav_text(text, active),
            command=command,
            relief="flat",
            anchor="w",
            bg=ACCENT_SOFT if active else SIDEBAR,
            activebackground=ACCENT_SOFT,
            fg=ACCENT if active else TEXT,
            font=(
                "Microsoft YaHei UI",
                11,
                "bold" if active else "normal",
            ),
            padx=12,
            pady=11,
            cursor="hand2",
            bd=0,
            highlightthickness=0,
        )
        button.pack(fill="x", pady=3)

        def on_enter(_event):
            if button is not self.nav_buttons.get(self._active_nav_key()):
                button.configure(bg=SOFT_FILL)

        def on_leave(_event):
            if button is not self.nav_buttons.get(self._active_nav_key()):
                button.configure(bg=SIDEBAR)

        button.bind("<Enter>", on_enter)
        button.bind("<Leave>", on_leave)
        return button

    def _nav_text(self, text, active=False):
        return f"▌  {text}" if active else f"   {text}"

    def _active_nav_key(self, mode=None):
        mode = mode or self.mode
        if mode in {"library_detail", "problem_detail"}:
            return "library"
        if mode == "plan":
            return "week"
        return mode

    def _build_content(self):
        shell = tk.Frame(self.root, bg=PAGE_BG)
        shell.grid(row=0, column=1, sticky="nsew")
        shell.columnconfigure(0, weight=1)
        shell.rowconfigure(0, weight=1)

        self.canvas = tk.Canvas(
            shell,
            bg=PAGE_BG,
            highlightthickness=0,
            bd=0,
            yscrollincrement=18,
        )
        scrollbar = tk.Scrollbar(
            shell,
            orient="vertical",
            command=self._scroll_canvas,
            relief="flat",
        )
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        self.body = tk.Frame(self.canvas, bg=PAGE_BG)
        self.body_window = self.canvas.create_window(
            (0, 0),
            window=self.body,
            anchor="nw",
        )
        self.body.bind("<Configure>", self._update_scroll_region)
        self.canvas.bind("<Configure>", self._resize_body)
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        self.toast = tk.Label(
            shell,
            text="",
            bg="#202124",
            fg="white",
            font=("Microsoft YaHei UI", 10, "bold"),
            padx=18,
            pady=10,
            bd=0,
            highlightthickness=1,
            highlightbackground="#2F3136",
        )
        self.transition_overlay = tk.Frame(shell, bg=PAGE_BG)

    def _update_scroll_region(self, _event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _scroll_canvas(self, *args):
        self.pending_scroll_args = args
        if self.scroll_after_id:
            return
        self.scroll_after_id = self.root.after(12, self._flush_canvas_scroll)

    def _flush_canvas_scroll(self):
        args = self.pending_scroll_args
        self.pending_scroll_args = None
        self.scroll_after_id = None
        if args:
            self.canvas.yview(*args)
        self._schedule_canvas_refresh()

    def _schedule_canvas_refresh(self):
        if self.scroll_refresh_after_id:
            return
        self.scroll_refresh_after_id = self.root.after_idle(
            self._refresh_canvas_after_scroll
        )

    def _refresh_canvas_after_scroll(self):
        self.scroll_refresh_after_id = None
        try:
            self.canvas.update_idletasks()
        except tk.TclError:
            pass

    def _resize_body(self, event):
        self.canvas.itemconfigure(self.body_window, width=event.width)
        old_width = self.content_width
        self.content_width = event.width
        if self.mode in {"library", "library_detail", "problem_detail"}:
            old_columns = self._responsive_columns(width=old_width)
            new_columns = self._responsive_columns(width=event.width)
            if old_columns != new_columns:
                if self.resize_after_id:
                    self.root.after_cancel(self.resize_after_id)
                self.resize_after_id = self.root.after(160, self.render)

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-event.delta / 120), "units")
        self._schedule_canvas_refresh()

    def _usable_content_width(self):
        return max(360, int(self.content_width or self.root.winfo_width()) - 80)

    def _responsive_columns(self, min_card_width=300, max_columns=3, width=None):
        usable_width = max(360, int(width or self.content_width) - 80)
        columns = max(1, usable_width // min_card_width)
        return min(max_columns, columns)

    def _bind_label_wrap(self, label, container, padding=0, min_width=80, max_width=None):
        def update_wrap(event=None):
            width = container.winfo_width()
            if event is not None and getattr(event, "width", 0):
                width = event.width
            wrap_width = max(min_width, int(width) - padding)
            if max_width is not None:
                wrap_width = min(wrap_width, max_width)
            label.configure(wraplength=wrap_width)

        container.bind("<Configure>", update_wrap, add="+")
        update_wrap()

    def _render_info_chips(
        self,
        parent,
        chips,
        accent_index=0,
        min_card_width=220,
        max_columns=4,
    ):
        target = parent
        if any(child.winfo_manager() == "pack" for child in parent.winfo_children()):
            try:
                bg = parent["bg"]
            except tk.TclError:
                bg = PAGE_BG
            target = tk.Frame(parent, bg=bg)
            target.pack(fill="x", pady=(10, 0))

        columns = self._responsive_columns(
            min_card_width=min_card_width,
            max_columns=min(max_columns, max(len(chips), 1)),
        )
        for column in range(columns):
            target.grid_columnconfigure(column, weight=1, uniform="info")

        for index, (label, value) in enumerate(chips):
            chip = self._info_chip(target, label, value, accent=(index == accent_index))
            chip.grid(
                row=index // columns,
                column=index % columns,
                sticky="nsew",
                padx=(0 if index % columns == 0 else 8, 0),
                pady=(0 if index < columns else 8, 0),
            )

    def set_mode(self, mode):
        if self.mode == mode:
            self.render()
            return
        self.mode = mode
        self._update_nav_state(mode)
        self._render_with_transition()

    def _update_nav_state(self, mode=None):
        mode = mode or self.mode
        active_nav_key = self._active_nav_key(mode)
        for key, button in self.nav_buttons.items():
            active = key == active_nav_key
            label = self.nav_labels.get(key, button.cget("text").strip("▌ "))
            button.configure(
                text=self._nav_text(label, active),
                bg=ACCENT_SOFT if active else SIDEBAR,
                fg=ACCENT if active else TEXT,
                font=(
                    "Microsoft YaHei UI",
                    11,
                    "bold" if active else "normal",
                ),
            )

    def _render_with_transition(self):
        if self.render_after_id:
            self.root.after_cancel(self.render_after_id)
        if self.transition_after_id:
            self.root.after_cancel(self.transition_after_id)
        try:
            self.canvas.yview_moveto(0)
        except tk.TclError:
            pass
        self._show_transition_overlay()
        self.root.configure(cursor="watch")
        self.render_after_id = self.root.after(36, self._finish_render_transition)

    def _finish_render_transition(self):
        self.render_after_id = None
        try:
            self.render()
        finally:
            self.root.configure(cursor="")
            self.transition_after_id = self.root.after(
                70,
                self._hide_transition_overlay,
            )

    def _show_transition_overlay(self):
        if not self.transition_overlay:
            return
        self.transition_overlay.lift()
        self.transition_overlay.place(relx=0, rely=0, relwidth=1, relheight=1)

    def _hide_transition_overlay(self):
        self.transition_after_id = None
        if not self.transition_overlay:
            return
        try:
            self.transition_overlay.place_forget()
        except tk.TclError:
            pass

    def refresh(self):
        try:
            self.data = get_task_board_data()
            self.render()
        except Exception as error:
            self._render_error(str(error))

    def render(self):
        for widget in self.body.winfo_children():
            widget.destroy()

        self.sync_output = None
        self.review_output = None
        self.ai_output = None
        self.more_output = None

        container = tk.Frame(self.body, bg=PAGE_BG)
        container.pack(fill="both", expand=True, padx=40, pady=(32, 48))

        if self.mode == "today":
            self._render_today(container)
        elif self.mode == "week":
            self._render_week(container)
        elif self.mode == "plan":
            self._render_plan_draft(container)
        elif self.mode == "sync":
            self._render_sync(container)
        elif self.mode == "library":
            self._render_library(container)
        elif self.mode == "library_detail":
            self._render_library_detail_page(container)
        elif self.mode == "problem_detail":
            self._render_problem_detail_page(container)
        elif self.mode == "ai":
            self._render_ai(container)
        else:
            self._render_more(container)
        self.root.after_idle(self._update_scroll_region)

    def _page_header(self, parent, title, subtitle):
        title_label = tk.Label(
            parent,
            text=title,
            bg=PAGE_BG,
            fg=TEXT,
            font=("Microsoft YaHei UI", 28, "bold"),
            justify="left",
        )
        title_label.pack(fill="x", anchor="w")
        self._bind_label_wrap(
            title_label,
            parent,
            padding=0,
            min_width=260,
            max_width=900,
        )
        if subtitle:
            subtitle_label = tk.Label(
                parent,
                text=subtitle,
                bg=PAGE_BG,
                fg=TEXT_SECONDARY,
                font=("Microsoft YaHei UI", 11),
                justify="left",
            )
            subtitle_label.pack(fill="x", anchor="w", pady=(6, 22))
            self._bind_label_wrap(
                subtitle_label,
                parent,
                padding=0,
                min_width=220,
                max_width=860,
            )
        else:
            tk.Frame(parent, bg=PAGE_BG, height=18).pack(fill="x")

    def _create_card(self, parent, title="", subtitle="", accent=False):
        frame = tk.Frame(
            parent,
            bg=CARD_BG if not accent else "#FFF7F5",
            highlightbackground=CARD_BORDER,
            highlightthickness=1,
            bd=0,
            padx=24,
            pady=20,
        )
        if title:
            tk.Label(
                frame,
                text=title,
                bg=frame["bg"],
                fg=TEXT,
                font=("Microsoft YaHei UI", 15, "bold"),
                anchor="w",
            ).pack(fill="x", anchor="w")
        if subtitle:
            subtitle_label = tk.Label(
                frame,
                text=subtitle,
                bg=frame["bg"],
                fg=TEXT_SECONDARY,
                font=("Microsoft YaHei UI", 10),
                justify="left",
                anchor="w",
            )
            subtitle_label.pack(fill="x", anchor="w", pady=(6, 0))
            self._bind_label_wrap(
                subtitle_label,
                frame,
                padding=36,
                min_width=180,
                max_width=760,
            )
        self._bind_card_hover(frame)
        return frame

    def _bind_card_hover(self, frame):
        def on_enter(_event):
            try:
                frame.configure(highlightbackground=CARD_HOVER_BORDER)
            except tk.TclError:
                pass

        def on_leave(_event):
            try:
                frame.configure(highlightbackground=CARD_BORDER)
            except tk.TclError:
                pass

        frame.bind("<Enter>", on_enter, add="+")
        frame.bind("<Leave>", on_leave, add="+")

    def _primary_button(self, parent, text, command):
        button = tk.Button(
            parent,
            text=text,
            command=command,
            bg=ACCENT,
            activebackground=ACCENT_DARK,
            fg="white",
            activeforeground="white",
            relief="flat",
            bd=0,
            padx=22,
            pady=10,
            font=("Microsoft YaHei UI", 10, "bold"),
            cursor="hand2",
        )
        self._bind_button_hover(button, ACCENT, ACCENT_DARK, ACCENT_PRESSED)
        return button

    def _secondary_button(self, parent, text, command):
        button = tk.Button(
            parent,
            text=text,
            command=command,
            bg=SOFT_FILL,
            activebackground=SOFT_FILL_HOVER,
            fg=TEXT,
            activeforeground=TEXT,
            relief="flat",
            bd=0,
            padx=18,
            pady=10,
            font=("Microsoft YaHei UI", 10),
            cursor="hand2",
        )
        self._bind_button_hover(button, SOFT_FILL, SOFT_FILL_HOVER, SOFT_FILL_PRESSED)
        return button

    def _tab_button(self, parent, text, active, command):
        bg = ACCENT if active else SOFT_FILL
        fg = "white" if active else TEXT
        hover = ACCENT_DARK if active else SOFT_FILL_HOVER
        pressed = ACCENT_PRESSED if active else SOFT_FILL_PRESSED
        button = tk.Button(
            parent,
            text=text,
            command=command,
            bg=bg,
            activebackground=hover,
            fg=fg,
            activeforeground=fg,
            relief="flat",
            bd=0,
            padx=16,
            pady=9,
            font=("Microsoft YaHei UI", 10, "bold" if active else "normal"),
            cursor="hand2",
        )
        self._bind_button_hover(button, bg, hover, pressed)
        return button

    def _pill(self, parent, text, kind="neutral"):
        styles = {
            "accent": (ACCENT_SOFT, ACCENT),
            "success": ("#ECFDF3", SUCCESS),
            "warning": ("#FFF7E6", WARNING),
            "info": ("#EEF4FF", INFO),
            "neutral": (SOFT_FILL, TEXT_SECONDARY),
        }
        bg, fg = styles.get(kind, styles["neutral"])
        label = tk.Label(
            parent,
            text=text,
            bg=bg,
            fg=fg,
            font=("Microsoft YaHei UI", 9, "bold"),
            padx=10,
            pady=4,
        )
        return label

    def _section_caption(self, parent, text):
        label = tk.Label(
            parent,
            text=text,
            bg=parent["bg"],
            fg=TEXT_WEAK,
            font=("Microsoft YaHei UI", 9),
            anchor="w",
        )
        label.pack(fill="x", anchor="w", pady=(4, 0))
        return label

    def _bind_button_hover(self, button, normal_bg, hover_bg, pressed_bg=None):
        pressed_bg = pressed_bg or hover_bg

        def on_enter(_event):
            button.configure(bg=hover_bg)

        def on_leave(_event):
            button.configure(bg=normal_bg)

        def on_press(_event):
            button.configure(bg=pressed_bg)

        def on_release(_event):
            button.configure(bg=hover_bg)

        button.bind(
            "<Enter>",
            on_enter,
            add="+",
        )
        button.bind(
            "<Leave>",
            on_leave,
            add="+",
        )
        button.bind(
            "<ButtonPress-1>",
            on_press,
            add="+",
        )
        button.bind(
            "<ButtonRelease-1>",
            on_release,
            add="+",
        )

    def _attach_placeholder(self, entry, placeholder):
        placeholder = str(placeholder or "")
        entry._leetcoach_placeholder = placeholder
        entry._leetcoach_placeholder_active = False

        def show_placeholder():
            if entry.get():
                return
            entry._leetcoach_placeholder_active = True
            entry.configure(fg=PLACEHOLDER)
            entry.insert(0, placeholder)

        def clear_placeholder(_event=None):
            if getattr(entry, "_leetcoach_placeholder_active", False):
                entry.delete(0, tk.END)
                entry.configure(fg=TEXT)
                entry._leetcoach_placeholder_active = False

        def restore_placeholder(_event=None):
            if not entry.get():
                show_placeholder()

        entry.bind("<FocusIn>", clear_placeholder, add="+")
        entry.bind("<FocusOut>", restore_placeholder, add="+")
        show_placeholder()

    def _entry_value(self, entry):
        value = entry.get().strip()
        if getattr(entry, "_leetcoach_placeholder_active", False):
            return ""
        if value == getattr(entry, "_leetcoach_placeholder", ""):
            return ""
        return value

    def _status_style(self, kind):
        styles = {
            "empty": ("○", "#F8F8F8", TEXT_SECONDARY, LINE),
            "loading": ("…", "#EEF4FF", INFO, "#D7E5FF"),
            "success": ("✓", "#ECFDF3", SUCCESS, "#D4F4E2"),
            "warning": ("!", "#FFF7E6", WARNING, "#FFE4B0"),
            "error": ("!", "#FFF1F0", ACCENT, "#FFD6D3"),
            "info": ("i", "#EEF4FF", INFO, "#D7E5FF"),
        }
        return styles.get(kind, styles["info"])

    def _render_state_block(
        self,
        parent,
        title,
        message="",
        kind="empty",
        action_text="",
        action=None,
    ):
        icon, bg, color, border = self._status_style(kind)
        block = tk.Frame(
            parent,
            bg=bg,
            highlightbackground=border,
            highlightthickness=1,
            bd=0,
            padx=16,
            pady=14,
        )
        block.pack(fill="x", pady=(10, 0))

        icon_label = tk.Label(
            block,
            text=icon,
            bg=color,
            fg="white",
            font=("Microsoft YaHei UI", 10, "bold"),
            width=2,
            height=1,
        )
        icon_label.pack(side="left", anchor="n", padx=(0, 12))

        text_area = tk.Frame(block, bg=bg)
        text_area.pack(side="left", fill="x", expand=True)
        title_label = tk.Label(
            text_area,
            text=title,
            bg=bg,
            fg=TEXT,
            font=("Microsoft YaHei UI", 10, "bold"),
            justify="left",
            anchor="w",
        )
        title_label.pack(fill="x", anchor="w")
        self._bind_label_wrap(title_label, text_area, min_width=140)
        if message:
            message_label = tk.Label(
                text_area,
                text=message,
                bg=bg,
                fg=TEXT_SECONDARY,
                font=("Microsoft YaHei UI", 9),
                justify="left",
                anchor="w",
            )
            message_label.pack(fill="x", anchor="w", pady=(4, 0))
            self._bind_label_wrap(message_label, text_area, min_width=140)

        if action_text and action is not None:
            self._secondary_button(block, action_text, action).pack(
                side="right",
                padx=(12, 0),
            )
        return block

    def _set_status_output(self, widget, title, message="", kind="info"):
        icon, _, _, _ = self._status_style(kind)
        text = f"{icon} {title}"
        if message:
            text += f"\n\n{message}"
        self._set_text_output(widget, text)

    def _set_loading_output(self, widget, message):
        self._set_status_output(widget, "正在处理", message, kind="loading")

    def _set_error_output(self, widget, title, error=None):
        detail = f"错误：{error}" if error else ""
        self._set_status_output(widget, title, detail, kind="error")

    def _center_dialog(self, dialog):
        dialog.update_idletasks()
        x = self.root.winfo_rootx() + (
            self.root.winfo_width() - dialog.winfo_reqwidth()
        ) // 2
        y = self.root.winfo_rooty() + (
            self.root.winfo_height() - dialog.winfo_reqheight()
        ) // 2
        dialog.geometry(f"+{max(x, 0)}+{max(y, 0)}")

    def _notify(self, title, message, kind="info"):
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.configure(bg=BACKGROUND)
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()

        icon, bg, color, _border = self._status_style(kind)
        shell = tk.Frame(dialog, bg=BACKGROUND, padx=24, pady=22)
        shell.pack(fill="both", expand=True)
        tk.Label(
            shell,
            text=icon,
            bg=color,
            fg="white",
            font=("Microsoft YaHei UI", 12, "bold"),
            width=2,
            height=1,
        ).pack(side="left", anchor="n", padx=(0, 14))
        body = tk.Frame(shell, bg=BACKGROUND)
        body.pack(side="left", fill="both", expand=True)
        tk.Label(
            body,
            text=title,
            bg=BACKGROUND,
            fg=TEXT,
            font=("Microsoft YaHei UI", 13, "bold"),
            justify="left",
            wraplength=420,
        ).pack(anchor="w")
        tk.Label(
            body,
            text=message,
            bg=BACKGROUND,
            fg=TEXT_SECONDARY,
            font=("Microsoft YaHei UI", 10),
            justify="left",
            wraplength=420,
        ).pack(anchor="w", pady=(8, 18))
        self._primary_button(body, "知道了", dialog.destroy).pack(anchor="e")
        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
        self._center_dialog(dialog)
        self.root.wait_window(dialog)

    def _confirm(self, title, message, confirm_text="确认", cancel_text="取消"):
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.configure(bg=BACKGROUND)
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()
        result = {"confirmed": False}

        shell = tk.Frame(dialog, bg=BACKGROUND, padx=24, pady=22)
        shell.pack(fill="both", expand=True)
        tk.Label(
            shell,
            text=title,
            bg=BACKGROUND,
            fg=TEXT,
            font=("Microsoft YaHei UI", 14, "bold"),
            justify="left",
            wraplength=460,
        ).pack(anchor="w")
        tk.Label(
            shell,
            text=message,
            bg=BACKGROUND,
            fg=TEXT_SECONDARY,
            font=("Microsoft YaHei UI", 10),
            justify="left",
            wraplength=460,
        ).pack(anchor="w", pady=(10, 18))

        actions = tk.Frame(shell, bg=BACKGROUND)
        actions.pack(fill="x")

        def confirm():
            result["confirmed"] = True
            dialog.destroy()

        self._secondary_button(actions, cancel_text, dialog.destroy).pack(
            side="right"
        )
        self._primary_button(actions, confirm_text, confirm).pack(
            side="right",
            padx=(0, 10),
        )
        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
        self._center_dialog(dialog)
        self.root.wait_window(dialog)
        return result["confirmed"]

    def _info_chip(self, parent, label, value, accent=False):
        chip = tk.Frame(
            parent,
            bg=ACCENT_SOFT if accent else CARD_BG,
            highlightbackground=CARD_BORDER,
            highlightthickness=1,
            bd=0,
            padx=14,
            pady=12,
        )
        tk.Label(
            chip,
            text=label,
            bg=chip["bg"],
            fg=TEXT_SECONDARY,
            font=("Microsoft YaHei UI", 9),
        ).pack(anchor="w")
        value_label = tk.Label(
            chip,
            text=value,
            bg=chip["bg"],
            fg=ACCENT if accent else TEXT,
            font=("Microsoft YaHei UI", 14, "bold"),
            justify="left",
        )
        value_label.pack(fill="x", anchor="w", pady=(6, 0))
        self._bind_label_wrap(value_label, chip, padding=28, min_width=90)
        self._bind_card_hover(chip)
        return chip

    def _render_today(self, parent):
        self._page_header(
            parent,
            "今天",
            "",
        )

        today_task_card = self._create_card(parent)
        today_task_card.pack(fill="both", expand=True, pady=(0, 16))
        self._render_task_group(
            today_task_card,
            self.data.get("today_tasks", []),
            empty_text="今天没有任务。",
        )

    def _render_task_group(self, parent, tasks, empty_text):
        body = tk.Frame(parent, bg=parent["bg"])
        body.pack(fill="both", expand=True, pady=(12, 0))
        if not tasks:
            self._render_state_block(
                body,
                empty_text,
                "保持节奏，明天再继续。",
                kind="empty",
            )
            return

        for index, task in enumerate(tasks):
            self._render_task_row(
                body,
                task,
                weekly=False,
                highlight=False,
                card_bg=parent["bg"],
            )
            if index != len(tasks) - 1:
                tk.Frame(body, height=1, bg=LINE).pack(fill="x", pady=8)

    def _render_week(self, parent):
        raw_plan_title = (
            self.data.get("weekly_theme")
            or self.data.get("plan_title")
            or "暂无计划"
        )
        plan_title = _short_topic_title(raw_plan_title)
        phase = self.data.get("plan_phase", {})
        phase_label = phase.get("label", "当前阶段")
        self._page_header(
            parent,
            plan_title,
            f"{phase_label} · 提前完成后可以直接进入下一阶段，不需要等自然周切换。",
        )

        stats = tk.Frame(parent, bg=PAGE_BG)
        stats.pack(fill="x", pady=(0, 16))

        total = len(self.data.get("week_tasks", []))
        completed = self.data.get("week_completed", 0)
        chips = [
            ("本周进度", f"{completed} / {total}" if total else "暂无"),
            ("当前阶段", phase_label),
            ("今日目标", self.data.get("today_goal", "暂无今日目标")),
        ]
        self._render_info_chips(stats, chips, accent_index=0, max_columns=3)

        progress_card = self._create_card(parent, "任务清单")
        progress_card.pack(fill="x", pady=(0, 16))
        if total:
            ttk.Progressbar(
                progress_card,
                style="LeetCoach.Horizontal.TProgressbar",
                maximum=max(total, 1),
                value=completed,
            ).pack(fill="x", pady=(12, 14))
        self._render_task_list(
            progress_card,
            self.data.get("week_tasks", []),
            weekly=True,
        )

        detail_grid = tk.Frame(parent, bg=PAGE_BG)
        detail_grid.pack(fill="x")
        detail_grid.grid_columnconfigure(0, weight=1)
        detail_grid.grid_columnconfigure(1, weight=1)

        goal_card = self._create_card(detail_grid, "本周目标")
        goal_card.grid(
            row=0, column=0, sticky="nsew", padx=(0, 8), pady=(0, 16)
        )
        tk.Label(
            goal_card,
            text=self.data.get("weekly_goal", "暂无本周目标"),
            bg=goal_card["bg"],
            fg=TEXT_SECONDARY,
            font=("Microsoft YaHei UI", 10),
            justify="left",
            wraplength=360,
        ).pack(anchor="w", pady=(10, 0))

        acceptance_card = self._create_card(detail_grid, "验收标准")
        acceptance_card.grid(
            row=0, column=1, sticky="nsew", padx=(8, 0), pady=(0, 16)
        )
        tk.Label(
            acceptance_card,
            text=self.data.get("minimum_acceptance", "暂无验收标准"),
            bg=acceptance_card["bg"],
            fg=TEXT_SECONDARY,
            font=("Microsoft YaHei UI", 10),
            justify="left",
            wraplength=360,
        ).pack(anchor="w", pady=(10, 0))

        ai_card = self._create_card(parent, "AI 计划辅助")
        ai_card.pack(fill="x", pady=(0, 16))
        tk.Label(
            ai_card,
            text="计划级 AI 放在这里：周总结、下一阶段计划草案和计划建议。",
            bg=ai_card["bg"],
            fg=TEXT_SECONDARY,
            font=("Microsoft YaHei UI", 10),
            justify="left",
        ).pack(fill="x", anchor="w", pady=(8, 12))
        ai_actions = tk.Frame(ai_card, bg=ai_card["bg"])
        ai_actions.pack(fill="x")
        self._primary_button(
            ai_actions,
            "查看 / 生成计划草案",
            lambda: self.set_mode("plan"),
        ).pack(side="left")
        self._secondary_button(
            ai_actions,
            "AI 周总结",
            self.generate_ai_weekly_review_output,
        ).pack(side="left", padx=10)
        self._secondary_button(
            ai_actions,
            "AI 计划建议",
            self.generate_ai_plan_suggestion_output,
        ).pack(side="left")

        self.ai_output = self._build_output_card(parent, "计划 AI 输出", height=12)
        self._set_ai_output("这里会显示 AI 周总结或 AI 计划建议。")

    def _render_plan_draft(self, parent):
        management = get_plan_management_data()
        draft = management.get("draft")

        self._page_header(
            parent,
            "AI 学习计划",
            "系统会根据你的同步记录、当前计划和复习情况生成下一阶段计划草案。",
        )

        actions = tk.Frame(parent, bg=PAGE_BG)
        actions.pack(fill="x", pady=(0, 18))
        self._secondary_button(
            actions,
            "返回计划",
            lambda: self.set_mode("week"),
        ).pack(side="left")
        self._secondary_button(
            actions,
            "重新生成",
            self.generate_plan_draft,
        ).pack(side="left", padx=10)
        if isinstance(draft, dict):
            self._primary_button(
                actions,
                "确认并启用计划",
                self.confirm_plan_draft,
            ).pack(side="left")

        if self.plan_generating:
            loading_card = self._create_card(parent)
            loading_card.pack(fill="x")
            self._render_state_block(
                loading_card,
                "正在生成计划",
                "正在读取本地题库、完成记录和当前计划，请稍候。",
                kind="loading",
            )
            return

        if not isinstance(draft, dict):
            empty_card = self._create_card(parent)
            empty_card.pack(fill="x")
            self._render_state_block(
                empty_card,
                "当前还没有计划草案",
                "LeetCoach 可以根据同步记录和学习状态生成下一阶段计划。",
                kind="empty",
                action_text="重新生成",
                action=self.generate_plan_draft,
            )
            return

        overview_card = self._create_card(parent, f"Week {draft.get('week', '')} - {draft.get('title', '学习计划')}")
        overview_card.pack(fill="x", pady=(0, 16))
        summary_lines = [
            f"建议开始日期：{draft.get('start_date', '未知')}（确认后从确认当天立即启用）",
            f"学习阶段：{draft.get('learner_level_label', '未判断')}",
            f"本周主题：{draft.get('weekly_theme', draft.get('title', '暂无'))}",
            f"本周目标：{draft.get('weekly_goal', '暂无')}",
        ]
        for line in summary_lines:
            line_label = tk.Label(
                overview_card,
                text=line,
                bg=overview_card["bg"],
                fg=TEXT_SECONDARY,
                font=("Microsoft YaHei UI", 10),
                justify="left",
            )
            line_label.pack(fill="x", anchor="w", pady=(3, 0))
            self._bind_label_wrap(
                line_label,
                overview_card,
                padding=36,
                min_width=180,
                max_width=760,
            )
        reason = str(draft.get("reason", "")).strip()
        if reason:
            reason_label = tk.Label(
                overview_card,
                text=f"生成原因：{reason}",
                bg=overview_card["bg"],
                fg=TEXT,
                font=("Microsoft YaHei UI", 10),
                justify="left",
            )
            reason_label.pack(fill="x", anchor="w", pady=(12, 0))
            self._bind_label_wrap(
                reason_label,
                overview_card,
                padding=36,
                min_width=180,
                max_width=760,
            )

        focus_card = self._create_card(parent, "推荐重点")
        focus_card.pack(fill="x", pady=(0, 16))
        focus_items = draft.get("recommended_focus", [])
        if focus_items:
            for item in focus_items:
                tk.Label(
                    focus_card,
                    text=f"• {item}",
                    bg=focus_card["bg"],
                    fg=TEXT_SECONDARY,
                    font=("Microsoft YaHei UI", 10),
                    anchor="w",
                ).pack(fill="x", pady=2)
        else:
            tk.Label(
                focus_card,
                text="暂无明确推荐重点。",
                bg=focus_card["bg"],
                fg=TEXT_SECONDARY,
                font=("Microsoft YaHei UI", 10),
            ).pack(anchor="w", pady=(8, 0))

        self._render_plan_quality_panel(parent, draft)

        days_card = self._create_card(parent, "每日安排")
        days_card.pack(fill="x")
        days = draft.get("days", {})
        for day_index in range(1, 8):
            day = days.get(str(day_index), {})
            item = tk.Frame(
                days_card,
                bg=days_card["bg"],
                highlightbackground=LINE,
                highlightthickness=1,
                bd=0,
                padx=12,
                pady=10,
            )
            item.pack(fill="x", pady=(10 if day_index == 1 else 8, 0))
            tk.Label(
                item,
                text=f"Day {day_index}",
                bg=item["bg"],
                fg=ACCENT,
                font=("Microsoft YaHei UI", 10, "bold"),
            ).pack(anchor="w")
            goal_label = tk.Label(
                item,
                text=f"目标：{day.get('goal', '暂无')}",
                bg=item["bg"],
                fg=TEXT,
                font=("Microsoft YaHei UI", 11, "bold"),
                justify="left",
            )
            goal_label.pack(fill="x", anchor="w", pady=(6, 0))
            self._bind_label_wrap(goal_label, item, padding=24, min_width=180)
            reason_label = tk.Label(
                item,
                text=f"原因：{day.get('reason', '暂无')}",
                bg=item["bg"],
                fg=TEXT_SECONDARY,
                font=("Microsoft YaHei UI", 10),
                justify="left",
            )
            reason_label.pack(fill="x", anchor="w", pady=(4, 0))
            self._bind_label_wrap(reason_label, item, padding=24, min_width=180)
            problems = day.get("problems", [])
            problem_text = "、".join(problems) if problems else "无新题，以复习或总结为主"
            problem_label = tk.Label(
                item,
                text=f"题目：{problem_text}",
                bg=item["bg"],
                fg=TEXT_WEAK,
                font=("Microsoft YaHei UI", 9),
                justify="left",
            )
            problem_label.pack(fill="x", anchor="w", pady=(4, 0))
            self._bind_label_wrap(problem_label, item, padding=24, min_width=180)

    def _render_plan_quality_panel(self, parent, draft):
        quality = draft.get("quality_check", {})
        schema = draft.get("llm_schema_check", {})
        evaluation = draft.get("llm_eval_result", {})
        fallback_used = bool(draft.get("llm_fallback_used"))
        rag_context = draft.get("rag_context", {})
        if not isinstance(rag_context, dict):
            rag_context = {}
        generated_by = str(draft.get("generated_by", "未知"))

        card = self._create_card(parent, "计划质量")
        card.pack(fill="x", pady=(0, 16))
        chips = tk.Frame(card, bg=card["bg"])
        chips.pack(fill="x", pady=(10, 0))
        self._render_info_chips(
            chips,
            [
                ("生成方式", "规则兜底" if fallback_used else generated_by),
                ("质量评分", str(quality.get("score", "未检查"))),
                ("结构校验", "通过" if schema.get("valid") else "未通过/未检查"),
            ],
            accent_index=1,
            max_columns=3,
        )
        self._render_state_block(
            card,
            "RAG",
            f"模式：{rag_context.get('mode', '未使用')}；命中：{rag_context.get('matched_count', 0)} 条；候选：{rag_context.get('total_candidate_count', 0)} 条",
            kind="info" if rag_context.get("matched_count", 0) else "empty",
        )

        issues = []
        for source in (quality, schema, evaluation):
            for key in ("errors", "warnings"):
                source_issues = source.get(key, [])
                if isinstance(source_issues, list):
                    issues.extend(str(item) for item in source_issues if item)
            if not any(key in source for key in ("errors", "warnings")):
                source_issues = source.get("issues", [])
                if isinstance(source_issues, list):
                    issues.extend(str(item) for item in source_issues if item)
        if draft.get("ai_generation_error"):
            issues.append("AI 调用信息：" + str(draft.get("ai_generation_error")))

        if issues:
            self._render_state_block(
                card,
                "需要注意",
                "\n".join(f"- {item}" for item in issues[:5]),
                kind="warning",
            )
        else:
            self._render_state_block(
                card,
                "计划检查通过",
                "题目顺序、周次和结构校验目前没有发现明显问题。",
                kind="success",
            )

        arranged = []
        for day in draft.get("days", {}).values():
            if not isinstance(day, dict):
                continue
            for problem_id in day.get("problems", []):
                problem_id = str(problem_id).strip()
                if problem_id and problem_id not in arranged:
                    arranged.append(problem_id)
        completed = [
            str(item).strip()
            for item in draft.get("completed_in_topic", [])
            if str(item).strip()
        ]
        excluded = []
        if isinstance(quality, dict):
            excluded = [
                str(item).strip()
                for item in quality.get("excluded_completed_as_new", [])
                if str(item).strip()
            ]
        remaining = [
            str(item).strip()
            for item in draft.get("remaining_in_topic", [])
            if str(item).strip()
        ]
        review_ids = [
            str(item).strip()
            for item in (
                draft.get("mastery_review_ids", [])
                or draft.get("priority_review_ids", [])
                or []
            )
            if str(item).strip()
        ]
        reason_lines = [
            "安排题目：" + ("、".join(arranged) if arranged else "暂无新题"),
            "已完成不重复安排：" + ("、".join(completed) if completed else "暂无"),
            "因已完成从新题中排除：" + ("、".join(excluded) if excluded else "暂无"),
            "因未掌握/需复习被安排：" + ("、".join(review_ids) if review_ids else "暂无"),
            "本专题剩余题：" + ("、".join(remaining) if remaining else "暂无"),
            "专题选择原因：" + str(draft.get("reason", "暂无")),
        ]
        evidence = rag_context.get("evidence", [])
        if isinstance(evidence, list) and evidence:
            top_evidence = []
            for item in evidence[:3]:
                if not isinstance(item, dict):
                    continue
                top_evidence.append(
                    f"{item.get('source', '')}:{item.get('problem_id', '')} {item.get('title', '')}"
                )
            if top_evidence:
                reason_lines.append("RAG 证据：" + "；".join(top_evidence))
        self._render_state_block(
            card,
            "安排依据",
            "\n".join(reason_lines),
            kind="info",
        )

    def _render_sync(self, parent):
        return self._render_sync_v2(parent)
        self._page_header(
            parent,
            "同步记录",
            "查看力扣记录是否同步到 LeetCoach。",
        )

        actions = tk.Frame(parent, bg=PAGE_BG)
        actions.pack(fill="x", pady=(0, 18))
        self._primary_button(
            actions,
            "启动本地同步服务",
            self.start_local_push_sync,
        ).pack(side="left")
        self._secondary_button(
            actions,
            "备用：主动同步",
            self.sync_now,
        ).pack(side="left", padx=10)
        self._secondary_button(
            actions,
            "最近记录",
            self.show_recent_synced_records,
        ).pack(side="left", padx=0)
        self._secondary_button(
            actions,
            "同步自检",
            self.run_sync_diagnostics,
        ).pack(side="left", padx=10)

        overview = get_sync_overview()
        self._render_local_push_status(parent)
        self._render_sync_status_cards(parent, overview)
        self._render_sync_record_sections(parent, overview)
        self.sync_output = self._build_output_card(parent, "同步记录", height=14)
        self._set_sync_output(format_sync_brief(overview))

    def _render_sync_v2(self, parent):
        self._page_header(
            parent,
            "同步记录",
            "Chrome 扩展会把力扣提交自动推送到 LeetCoach。",
        )

        actions = tk.Frame(parent, bg=PAGE_BG)
        actions.pack(fill="x", pady=(0, 18))
        self._primary_button(
            actions,
            "启动 / 刷新同步服务",
            self.start_local_push_sync,
        ).pack(side="left")
        self._secondary_button(
            actions,
            "打开力扣页面",
            self.open_leetcode_in_chrome,
        ).pack(side="left", padx=10)

        self._render_local_push_status_v2(parent)
        self._render_recent_push_records(parent)

    def _render_local_push_status_v2(self, parent):
        status = get_local_push_status()
        running = bool(status.get("running"))
        last_success = status.get("last_received_at") or status.get("last_success_at") or ""
        imported = int(status.get("imported", 0) or 0)
        received = int(status.get("received", status.get("fetched", 0)) or 0)
        skipped = int(status.get("skipped", 0) or 0)
        unmapped = int(status.get("unmapped", 0) or 0)
        last_error = status.get("last_error_message") or ""

        card = self._create_card(parent, "本地同步服务")
        card.pack(fill="x", pady=(0, 16))
        chips_frame = tk.Frame(card, bg=card["bg"])
        chips_frame.pack(fill="x", pady=(10, 0))
        self._render_info_chips(
            chips_frame,
            [
                ("服务状态", "运行中" if running else "未启动"),
                ("最近推送", last_success or "暂无"),
                ("本次读取", f"{received} 条"),
                ("新增记录", f"{imported} 条"),
                ("未映射", f"{unmapped} 条"),
            ],
            accent_index=0,
            max_columns=5,
        )

        if last_error:
            title = "同步遇到问题"
            message = (
                f"{last_error}\n\n"
                "请确认 LeetCoach 正在运行，Chrome 扩展版本为 1.2.0 或更高，"
                "然后刷新已登录的 leetcode.cn 页面。"
            )
            kind = "error"
        elif not running:
            title = "等待启动"
            message = "点击上方按钮启动本地同步服务，然后打开力扣页面。"
            kind = "warning"
        elif not last_success:
            title = "等待浏览器推送"
            message = (
                "服务已经运行。打开或刷新已登录的 leetcode.cn 页面后，"
                "Chrome 扩展会自动把最近提交推送到这里。"
            )
            kind = "info"
        elif imported > 0:
            title = "同步成功"
            message = f"读取 {received} 条，新增 {imported} 条，跳过重复 {skipped} 条。"
            kind = "success"
        else:
            title = "同步成功，没有新增"
            message = (
                f"读取 {received} 条，新增 0 条。"
                "这些提交已经存在于本地记录中。"
            )
            kind = "success"

        self._render_state_block(card, title, message, kind=kind)

    def _render_recent_push_records(self, parent):
        status = get_local_push_status()
        records = status.get("recent_imported", [])
        if not isinstance(records, list):
            records = []
        library = get_problem_library_data()
        problem_assets = {}
        for topic in library.get("topics", []):
            topic_name = topic.get("topic", "未分类")
            for problem in topic.get("problems", []):
                problem_id = str(problem.get("problem_id", "")).strip()
                if not problem_id:
                    continue
                asset = problem_assets.setdefault(problem_id, dict(problem))
                topics = asset.setdefault("topics", [])
                if topic_name and topic_name not in topics:
                    topics.append(topic_name)

        card = self._create_card(parent, "最近新增")
        card.pack(fill="x", pady=(0, 16))
        if not records:
            self._render_state_block(
                card,
                "暂无新增记录",
                "如果你今天有新提交，请刷新力扣页面，再回到这里查看。",
                kind="empty",
            )
            return

        for item in records[-5:][::-1]:
            row = tk.Frame(card, bg=card["bg"])
            row.pack(fill="x", pady=(10, 0))
            title = str(item.get("title") or item.get("problem_id") or "未知题目")
            problem_id = str(item.get("problem_id") or "")
            status_text = str(item.get("status") or "未知")
            submit_time = str(item.get("submit_time") or "")
            asset = problem_assets.get(problem_id, {})
            topics = asset.get("topics", [])
            topic_text = "、".join(topics[:2]) if topics else "未归入专题"
            review_summary = get_problem_review_summary(problem_id)
            review_text = (
                f"复习任务：待复习 {review_summary.get('pending', 0)} 次"
                if review_summary.get("pending", 0)
                else "复习任务：暂无待复习"
            )
            tk.Label(
                row,
                text=f"{problem_id} {title}".strip(),
                bg=card["bg"],
                fg=TEXT,
                font=("Microsoft YaHei UI", 11, "bold"),
                anchor="w",
            ).pack(fill="x")
            tk.Label(
                row,
                text=f"{status_text} · {submit_time}",
                bg=card["bg"],
                fg=TEXT_SECONDARY,
                font=("Microsoft YaHei UI", 10),
                anchor="w",
            ).pack(fill="x", pady=(3, 0))
            tk.Label(
                row,
                text=f"进入专题：{topic_text} · {review_text}",
                bg=card["bg"],
                fg=TEXT_WEAK,
                font=("Microsoft YaHei UI", 9),
                anchor="w",
                justify="left",
            ).pack(fill="x", pady=(3, 0))

    def _render_local_push_status(self, parent):
        status = get_local_push_status()
        card = self._create_card(parent, "本地推送同步")
        card.pack(fill="x", pady=(0, 16))
        running = bool(status.get("running"))
        self._render_info_chips(
            card,
            [
                ("服务", "运行中" if running else "未运行"),
                ("端口", str(status.get("port", 8765))),
                ("最近成功", str(status.get("last_success_at", "暂无"))),
                ("新增", f"{status.get('imported', 0)} 条"),
            ],
            accent_index=0,
            max_columns=4,
        )
        message = (
            "Chrome 扩展会把力扣页面里抓到的最近提交自动推送到本机服务。"
            if running
            else "本地服务未运行，点击“启动本地同步服务”后再打开力扣页面。"
        )
        self._render_state_block(
            card,
            "Localhost Push",
            message,
            kind="success" if running else "warning",
        )

    def _render_sync_status_cards(self, parent, overview):
        sync_state = overview.get("sync_state", {}) if isinstance(overview, dict) else {}
        mapped = overview.get("mapped_records", []) if isinstance(overview, dict) else []
        unmapped = overview.get("unmapped_records", []) if isinstance(overview, dict) else []
        success = bool(sync_state.get("success"))
        status_text = "成功" if success else "需要处理"
        last_time = (
            sync_state.get("last_success_at")
            or sync_state.get("last_attempt_at")
            or "暂无"
        )
        stats = tk.Frame(parent, bg=PAGE_BG)
        stats.pack(fill="x", pady=(0, 16))
        self._render_info_chips(
            stats,
            [
                ("同步状态", status_text),
                ("最近时间", str(last_time)),
                ("新增记录", f"{sync_state.get('imported', 0)} 条"),
                ("未映射", f"{len(unmapped)} 条"),
            ],
            accent_index=0,
            max_columns=4,
        )
        if not success:
            self._render_state_block(
                parent,
                "同步没有成功完成",
                "请先点击“同步自检”。如果扩展在线，再打开力扣页面后重试同步。",
                kind="warning",
            )

    def _render_sync_record_sections(self, parent, overview):
        if not isinstance(overview, dict):
            return

        records = overview.get("recent_records", [])
        unmapped_records = overview.get("unmapped_records", [])
        debug_data = overview.get("debug_data", {})
        if not isinstance(records, list):
            records = []
        if not isinstance(unmapped_records, list):
            unmapped_records = []
        if not isinstance(debug_data, dict):
            debug_data = {}

        recent_card = self._create_card(parent, "最近同步到的题目")
        recent_card.pack(fill="x", pady=(0, 16))
        if not records:
            self._render_state_block(
                recent_card,
                "还没有同步记录",
                "打开力扣页面后点击“立即同步”，成功后最近提交会出现在这里。",
                kind="empty",
            )
        else:
            for record in records[:5]:
                if not isinstance(record, dict):
                    continue
                row = tk.Frame(recent_card, bg=recent_card["bg"])
                row.pack(fill="x", pady=(8, 0))
                problem_id = str(record.get("problem_id", "")).strip() or "未知"
                title = str(record.get("title", "")).strip() or "未知题目"
                status = str(record.get("status", "")).strip() or "未知"
                submit_time = (
                    str(record.get("submit_time", "")).strip()
                    or str(record.get("date", "")).strip()
                    or "未知时间"
                )
                is_mapped = problem_id.isdigit()
                dot = tk.Canvas(
                    row,
                    width=18,
                    height=18,
                    bg=row["bg"],
                    highlightthickness=0,
                )
                dot.pack(side="left", padx=(0, 10))
                dot.create_oval(
                    4,
                    4,
                    14,
                    14,
                    fill=SUCCESS if is_mapped else WARNING,
                    outline=SUCCESS if is_mapped else WARNING,
                )
                text_frame = tk.Frame(row, bg=row["bg"])
                text_frame.pack(side="left", fill="x", expand=True)
                title_label = tk.Label(
                    text_frame,
                    text=f"{problem_id} {title}",
                    bg=text_frame["bg"],
                    fg=TEXT,
                    font=("Microsoft YaHei UI", 10, "bold"),
                    anchor="w",
                    justify="left",
                )
                title_label.pack(fill="x", anchor="w")
                self._bind_label_wrap(title_label, text_frame, min_width=180)
                meta_label = tk.Label(
                    text_frame,
                    text=f"{status} · {submit_time}",
                    bg=text_frame["bg"],
                    fg=TEXT_SECONDARY,
                    font=("Microsoft YaHei UI", 9),
                    anchor="w",
                    justify="left",
                )
                meta_label.pack(fill="x", anchor="w", pady=(3, 0))
                self._bind_label_wrap(meta_label, text_frame, min_width=180)

        if unmapped_records:
            issue_card = self._create_card(parent, "需要处理")
            issue_card.pack(fill="x", pady=(0, 16))
            self._render_state_block(
                issue_card,
                f"{len(unmapped_records)} 道题还没有映射到题号",
                "通常是 problem_bank.json 缺少这道题的 slug。补充 slug 后重新同步即可。",
                kind="warning",
            )
            for record in unmapped_records[:4]:
                if not isinstance(record, dict):
                    continue
                title = str(record.get("title", "")).strip() or "未知题目"
                slug = (
                    str(record.get("title_slug", "")).strip()
                    or str(record.get("problem_id", "")).strip()
                    or "未知 slug"
                )
                tk.Label(
                    issue_card,
                    text=f"- {title} · {slug}",
                    bg=issue_card["bg"],
                    fg=TEXT_SECONDARY,
                    font=("Microsoft YaHei UI", 9),
                    anchor="w",
                    justify="left",
                ).pack(fill="x", anchor="w", pady=(6, 0))
        elif debug_data.get("error_type"):
            issue_card = self._create_card(parent, "最近一次失败")
            issue_card.pack(fill="x", pady=(0, 16))
            self._render_state_block(
                issue_card,
                str(debug_data.get("error_type", "同步失败")),
                str(debug_data.get("error_message", "没有获得详细错误信息。"))[:180],
                kind="error",
            )

    def _render_library(self, parent):
        data = get_problem_library_data()
        topics = data.get("topics", [])

        self._page_header(
            parent,
            "题库",
            "把已经做过的题沉淀成能力地图。点击专题进入更详细的完成情况。",
        )

        stats = tk.Frame(parent, bg=PAGE_BG)
        stats.pack(fill="x", pady=(0, 16))

        cards = [
            (
                "已完成题目",
                f"{data.get('completed_problem_count', 0)} / {data.get('topic_total_sum', 0)}"
            ),
            ("专题模块", f"{data.get('topic_count', 0)} 个"),
            ("最近同步", self._library_sync_label()),
        ]
        self._render_info_chips(stats, cards, accent_index=0, max_columns=3)

        topic_card = self._create_card(parent, "专题进度")
        topic_card.pack(fill="x", pady=(0, 16))
        if not topics:
            self._render_state_block(
                topic_card,
                "题库暂无数据",
                "同步或记录几道题后，这里会自动生成专题能力地图。",
                kind="empty",
            )
            return

        topic_grid = tk.Frame(topic_card, bg=topic_card["bg"])
        topic_grid.pack(fill="x", pady=(12, 0))
        columns = self._responsive_columns(min_card_width=300, max_columns=3)
        for column in range(columns):
            topic_grid.grid_columnconfigure(column, weight=1, uniform="topic")

        for index, topic in enumerate(topics):
            topic_frame = self._render_topic_disc(topic_grid, topic)
            topic_frame.grid(
                row=index // columns,
                column=index % columns,
                sticky="nsew",
                padx=(0 if index % columns == 0 else 10, 0),
                pady=(0, 10),
            )

    def _render_topic_disc(self, parent, topic):
        completed = int(topic.get("completed", 0) or 0)
        total = int(topic.get("total", 0) or 0)
        ratio = min(completed / total, 1) if total else 0

        frame = tk.Frame(
            parent,
            bg=CARD_BG,
            highlightbackground=CARD_BORDER,
            highlightthickness=1,
            bd=0,
            padx=12,
            pady=12,
            cursor="hand2",
        )

        canvas = tk.Canvas(
            frame,
            width=76,
            height=76,
            bg=frame["bg"],
            highlightthickness=0,
            cursor="hand2",
        )
        canvas.pack(side="left", padx=(0, 12))
        self._draw_progress_ring(canvas, 38, 38, 30, ratio)
        canvas.create_text(
            38,
            38,
            text=f"{completed}/{total}",
            fill=TEXT,
            font=("Microsoft YaHei UI", 10, "bold"),
        )

        text_area = tk.Frame(frame, bg=frame["bg"])
        text_area.pack(side="left", fill="both", expand=True)
        title_label = tk.Label(
            text_area,
            text=topic.get("topic", "未分类"),
            bg=frame["bg"],
            fg=TEXT,
            font=("Microsoft YaHei UI", 12, "bold"),
            anchor="w",
            justify="left",
        )
        title_label.pack(fill="x", anchor="w")
        self._bind_label_wrap(title_label, text_area, padding=0, min_width=90)
        summary_label = tk.Label(
            text_area,
            text=f"完成 {completed} 道，共 {total} 道",
            bg=frame["bg"],
            fg=TEXT_SECONDARY,
            font=("Microsoft YaHei UI", 9),
            anchor="w",
            justify="left",
        )
        summary_label.pack(fill="x", anchor="w", pady=(5, 0))
        self._bind_label_wrap(summary_label, text_area, padding=0, min_width=90)
        description = str(topic.get("description", "")).strip()
        if description:
            description_label = tk.Label(
                text_area,
                text=description,
                bg=frame["bg"],
                fg=TEXT_WEAK,
                font=("Microsoft YaHei UI", 8),
                anchor="w",
                justify="left",
            )
            description_label.pack(fill="x", anchor="w", pady=(4, 0))
            self._bind_label_wrap(
                description_label,
                text_area,
                padding=0,
                min_width=90,
                max_width=260,
            )

        def select_topic(_event=None):
            self.selected_topic = topic.get("topic")
            self.library_detail_view = None
            self.mode = "library_detail"
            self.render()

        frame.bind("<Button-1>", select_topic)
        canvas.bind("<Button-1>", select_topic)
        text_area.bind("<Button-1>", select_topic)
        for child in text_area.winfo_children():
            child.bind("<Button-1>", select_topic)
        return frame

    def _draw_progress_ring(self, canvas, cx, cy, radius, ratio):
        canvas.create_oval(
            cx - radius,
            cy - radius,
            cx + radius,
            cy + radius,
            outline=SOFT_FILL,
            width=8,
        )
        if ratio <= 0:
            return

        ratio = min(max(ratio, 0), 1)
        end_angle = -90 + 360 * ratio
        steps = max(2, int(90 * ratio))
        points = []
        for index in range(steps + 1):
            angle = -90 + (end_angle + 90) * index / steps
            radians = math.radians(angle)
            points.extend([
                cx + radius * math.cos(radians),
                cy + radius * math.sin(radians),
            ])
        canvas.create_line(
            *points,
            fill=ACCENT,
            width=8,
            smooth=True,
        )

    def _render_topic_hero_card(
        self,
        parent,
        topic,
        completed,
        display_total,
        unfinished_count,
    ):
        hero = self._create_card(parent, accent=True)
        hero.pack(fill="x", pady=(0, 16))
        top = tk.Frame(hero, bg=hero["bg"])
        top.pack(fill="x")
        title_area = tk.Frame(top, bg=top["bg"])
        title_area.pack(side="left", fill="x", expand=True)
        tk.Label(
            title_area,
            text=topic.get("topic", "未分类"),
            bg=title_area["bg"],
            fg=TEXT,
            font=("Microsoft YaHei UI", 26, "bold"),
            anchor="w",
        ).pack(fill="x", anchor="w")
        description = str(topic.get("description", "")).strip()
        self._section_caption(
            title_area,
            description or "专题能力地图：完成进度、难度分布和题目资产。",
        )

        ratio = min(completed / display_total, 1) if display_total else 0
        ring = tk.Canvas(
            top,
            width=86,
            height=86,
            bg=top["bg"],
            highlightthickness=0,
        )
        ring.pack(side="right", padx=(18, 0))
        self._draw_progress_ring(ring, 43, 43, 32, ratio)
        ring.create_text(
            43,
            43,
            text=f"{completed}/{display_total}",
            fill=TEXT,
            font=("Microsoft YaHei UI", 10, "bold"),
        )

    def _render_library_detail_page(self, parent):
        data = get_problem_library_data()
        topic = get_topic_detail(self.selected_topic, data)
        if not isinstance(topic, dict):
            self.set_mode("library")
            return

        if self.library_detail_view == "completed":
            self.library_detail_view = None
        if self.library_detail_view == "unfinished":
            self.library_detail_view = None

        header_row = tk.Frame(parent, bg=PAGE_BG)
        header_row.pack(fill="x")
        self._secondary_button(
            header_row,
            "← 返回题库",
            lambda: self.set_mode("library"),
        ).pack(side="left", pady=(0, 18))

        completed = int(topic.get("completed", 0) or 0)
        display_total = int(topic.get("total", 0) or 0)
        unfinished_count = len(topic.get("unfinished_plan_problems", []))
        self._render_topic_hero_card(
            parent,
            topic,
            completed,
            display_total,
            unfinished_count,
        )

        detail = self._create_card(
            parent,
            "难度完成情况",
            "完成数量来自力扣同步记录和本地学习记录；难度分母来自专题配置。",
        )
        detail.pack(fill="x", pady=(0, 16))

        difficulty_frame = tk.Frame(detail, bg=detail["bg"])
        difficulty_frame.pack(fill="x", pady=(14, 12))
        difficulty_columns = self._responsive_columns(
            min_card_width=220,
            max_columns=3,
        )
        for column in range(difficulty_columns):
            difficulty_frame.grid_columnconfigure(
                column,
                weight=1,
                uniform="difficulty",
            )

        labels = [("Easy", "简单"), ("Medium", "中等"), ("Hard", "困难")]
        stats = topic.get("difficulty_stats", {})
        for index, (difficulty, label) in enumerate(labels):
            item = stats.get(
                difficulty,
                {"completed": 0, "local_total": 0, "catalog_total": None}
            )
            card = tk.Frame(
                difficulty_frame,
                bg="#FAFAFA",
                highlightbackground=LINE,
                highlightthickness=1,
                padx=12,
                pady=10,
            )
            card.grid(
                row=index // difficulty_columns,
                column=index % difficulty_columns,
                sticky="nsew",
                padx=(0 if index % difficulty_columns == 0 else 8, 0),
                pady=(0 if index < difficulty_columns else 8, 0),
            )
            tk.Label(
                card,
                text=label,
                bg=card["bg"],
                fg=TEXT_SECONDARY,
                font=("Microsoft YaHei UI", 9),
            ).pack(anchor="w")
            difficulty_total = item.get("catalog_total")
            has_difficulty_total = difficulty_total is not None
            completed = int(item.get("completed", 0) or 0)
            total = int(difficulty_total or 0)
            tk.Label(
                card,
                text=(
                    f"{completed} / {difficulty_total}"
                    if has_difficulty_total
                    else f"{completed} / -"
                ),
                bg=card["bg"],
                fg=TEXT,
                font=("Microsoft YaHei UI", 16, "bold"),
            ).pack(anchor="w", pady=(5, 8))
            ttk.Progressbar(
                card,
                style="LeetCoach.Horizontal.TProgressbar",
                maximum=max(total, 1),
                value=min(completed, total) if has_difficulty_total else 0,
            ).pack(fill="x")

        if not any(
            item.get("catalog_total") is not None
            for item in topic.get("difficulty_stats", {}).values()
        ):
            tk.Label(
                detail,
                text="当前专题暂未配置难度总量。",
                bg=detail["bg"],
                fg=TEXT_WEAK,
                font=("Microsoft YaHei UI", 9),
            ).pack(anchor="w", pady=(0, 8))

        self._render_problem_list_card(
            parent,
            "题目列表",
            topic.get("problems", []),
            empty_text="该专题暂时还没有题目。",
            show_completion=False,
        )

    def _show_library_detail_list(self, view):
        self.library_detail_view = view
        self.render()

    def _library_sync_label(self):
        sync_status = self.data.get("sync_status", {})
        text = str(sync_status.get("text", "")).strip()
        detail = str(sync_status.get("detail", "")).strip()
        combined = f"{text} {detail}"
        if any(keyword in combined for keyword in ("成功", "读取", "新增")):
            return "成功"
        if any(keyword in combined for keyword in ("失败", "无法", "错误")):
            return "失败"
        return "暂无"

    def _main_source_label(self, topic):
        source_counts = topic.get("source_counts", {})
        if not source_counts:
            return "暂无"
        source, _count = max(
            source_counts.items(),
            key=lambda item: item[1]
        )
        labels = {
            "leetcode_auto_sync": "力扣自动同步",
            "manual": "手动记录",
            "import": "导入记录",
            "leetcode_import": "导入记录"
        }
        return labels.get(source, source)

    def _render_recent_completed(self, parent, topic):
        recent = self._completed_problem_rows(topic)[:3]
        if not recent:
            self._render_state_block(
                parent,
                "该专题还没有完成记录",
                "完成该专题中的题目后，这里会显示最近沉淀的题。",
                kind="empty",
            )
            return

        for problem in recent:
            title = (
                f"{problem.get('problem_id', '')} "
                f"{problem.get('title', '未知题目')}"
            ).strip()
            tk.Label(
                parent,
                text=f"{title} · {problem.get('completed_at', '时间未知')}",
                bg=parent["bg"],
                fg=TEXT_SECONDARY,
                font=("Microsoft YaHei UI", 10),
                anchor="w",
            ).pack(fill="x", anchor="w", pady=(8, 0))

    def _completed_problem_rows(self, topic):
        return sorted(
            topic.get("completed_problems", []),
            key=lambda item: str(item.get("completed_at", "")),
            reverse=True
        )

    def _render_problem_list_card(
        self,
        parent,
        title,
        problems,
        empty_text,
        show_completion
    ):
        problem_card = self._create_card(parent, title)
        problem_card.pack(fill="x", pady=(0, 16))
        if not problems:
            self._render_state_block(
                problem_card,
                empty_text,
                "LeetCoach 会根据后续完成记录自动更新这里。",
                kind="empty",
            )
            return

        list_frame = tk.Frame(problem_card, bg=problem_card["bg"])
        list_frame.pack(fill="x", pady=(4, 0))
        problems = sorted(
            problems,
            key=lambda item: (
                str(item.get("completed_at", "")) if show_completion else "",
                item.get("difficulty", ""),
                item.get("problem_id", "")
            ),
            reverse=show_completion
        )
        for index, problem in enumerate(problems):
            self._render_library_problem_row(
                list_frame,
                problem,
                show_completion=show_completion
            )
            if index != len(problems) - 1:
                tk.Frame(list_frame, height=1, bg=LINE).pack(fill="x", pady=6)

    def _render_library_problem_row(self, parent, problem, show_completion=True):
        completed = bool(problem.get("completed"))
        row = tk.Frame(
            parent,
            bg=parent["bg"],
            padx=4,
            pady=7,
            cursor="hand2",
        )
        row.pack(fill="x")

        status_color = SUCCESS if completed else TEXT_WEAK
        canvas = tk.Canvas(
            row,
            width=24,
            height=24,
            bg=row["bg"],
            highlightthickness=0,
        )
        canvas.pack(side="left", padx=(0, 10))
        canvas.create_oval(
            5,
            5,
            19,
            19,
            outline=status_color,
            fill=status_color if completed else row["bg"],
            width=2,
        )
        if completed:
            canvas.create_text(
                12,
                12,
                text="✓",
                fill="white",
                font=("Microsoft YaHei UI", 8, "bold"),
            )

        text_area = tk.Frame(row, bg=row["bg"])
        text_area.pack(side="left", fill="x", expand=True)
        title = (
            f"{problem.get('problem_id', '')} "
            f"{problem.get('title', '未知题目')}"
        ).strip()
        if show_completion:
            completed_at = str(problem.get("completed_at", "")).strip()
            if completed_at:
                title = f"{title} · {completed_at}"
        title_label = tk.Label(
            text_area,
            text=title,
            bg=row["bg"],
            fg=TEXT,
            font=("Microsoft YaHei UI", 10, "bold"),
            anchor="w",
            cursor="hand2",
        )
        title_label.pack(fill="x", anchor="w")

        activity = _problem_activity_summary(problem.get("problem_id", ""))
        ai_label = "AI 题解已保存" if problem.get("has_ai_solution") else "暂无 AI 题解"
        if show_completion:
            meta = (
                f"难度：{problem.get('difficulty', 'Unknown')} · "
                f"提交 {activity.get('count', 0)} 次 · "
                f"最近：{activity.get('latest_status', '暂无')} · "
                f"{ai_label}"
            )
        else:
            skill = problem.get("skill") or problem.get("template") or "暂无能力标签"
            meta = (
                f"{skill} · "
                f"提交 {activity.get('count', 0)} 次 · "
                f"{ai_label}"
            )
        meta_label = tk.Label(
            text_area,
            text=meta,
            bg=row["bg"],
            fg=TEXT_SECONDARY,
            font=("Microsoft YaHei UI", 9),
            anchor="w",
            justify="left",
            cursor="hand2",
        )
        meta_label.pack(fill="x", anchor="w", pady=(3, 0))
        self._bind_label_wrap(meta_label, text_area, min_width=160)

        badge = tk.Label(
            row,
            text=problem.get("difficulty", "Unknown"),
            bg=ACCENT_SOFT if problem.get("difficulty") == "Hard" else SOFT_FILL,
            fg=ACCENT if problem.get("difficulty") == "Hard" else TEXT_SECONDARY,
            font=("Microsoft YaHei UI", 9, "bold"),
            padx=10,
            pady=4,
        )
        badge.pack(side="right", padx=(10, 0))
        if problem.get("has_ai_solution"):
            ai_badge = tk.Label(
                row,
                text="AI",
                bg=ACCENT_SOFT,
                fg=ACCENT,
                font=("Microsoft YaHei UI", 9, "bold"),
                padx=8,
                pady=4,
            )
            ai_badge.pack(side="right")

        def open_problem(_event=None):
            self.selected_problem = dict(problem)
            self.mode = "problem_detail"
            self.render()

        row.bind("<Button-1>", open_problem)
        canvas.bind("<Button-1>", open_problem)
        text_area.bind("<Button-1>", open_problem)
        title_label.bind("<Button-1>", open_problem)
        meta_label.bind("<Button-1>", open_problem)
        badge.bind("<Button-1>", open_problem)
        if problem.get("has_ai_solution"):
            ai_badge.bind("<Button-1>", open_problem)

    def _render_problem_hero_card(
        self,
        parent,
        problem,
        problem_id,
        title,
        activity,
        mastery_label,
    ):
        hero = self._create_card(parent, accent=True)
        hero.pack(fill="x", pady=(0, 16))

        top = tk.Frame(hero, bg=hero["bg"])
        top.pack(fill="x")
        title_area = tk.Frame(top, bg=top["bg"])
        title_area.pack(side="left", fill="x", expand=True)
        tk.Label(
            title_area,
            text=f"{problem_id} {title}".strip(),
            bg=title_area["bg"],
            fg=TEXT,
            font=("Microsoft YaHei UI", 26, "bold"),
            anchor="w",
            justify="left",
        ).pack(fill="x", anchor="w")
        self._section_caption(
            title_area,
            "学习资产卡：记录完成、掌握、题解、笔记和复习状态。",
        )

        status_kind = "success" if problem.get("completed") else "neutral"
        self._pill(
            top,
            "已完成" if problem.get("completed") else "未完成",
            status_kind,
        ).pack(side="right", padx=(12, 0), anchor="n")

        tag_row = tk.Frame(hero, bg=hero["bg"])
        tag_row.pack(fill="x", pady=(18, 0))
        self._pill(tag_row, problem.get("difficulty", "Unknown"), "info").pack(
            side="left",
            padx=(0, 8),
        )
        self._pill(tag_row, f"掌握：{mastery_label}", "neutral").pack(
            side="left",
            padx=(0, 8),
        )
        self._pill(
            tag_row,
            "AI 题解已保存" if problem.get("has_ai_solution") else "暂无 AI 题解",
            "accent" if problem.get("has_ai_solution") else "neutral",
        ).pack(side="left", padx=(0, 8))
        topics = "、".join(problem.get("topics", [])[:2]) or self.selected_topic or "暂无专题"
        self._pill(tag_row, topics, "neutral").pack(side="left", padx=(0, 8))

        quick = tk.Frame(hero, bg=hero["bg"])
        quick.pack(fill="x", pady=(18, 0))
        self._render_info_chips(
            quick,
            [
                ("提交", f"{activity.get('count', 0)} 次"),
                ("最近状态", activity.get("latest_status", "暂无")),
                ("主要错因", activity.get("main_mistake", "暂无")),
            ],
            accent_index=0,
            max_columns=3,
        )

    def _render_problem_detail_page(self, parent):
        problem = self.selected_problem if isinstance(self.selected_problem, dict) else {}
        problem_id = str(problem.get("problem_id", "")).strip()
        if not problem_id:
            self.set_mode("library")
            return

        title = problem.get("title", "未知题目")
        self._secondary_button(
            parent,
            "← 返回专题",
            lambda: self.set_mode("library_detail"),
        ).pack(anchor="w", pady=(0, 16))

        activity = _problem_activity_summary(problem_id)
        problem_note = get_problem_note(problem_id)
        mastery_label = MASTERY_LABELS.get(
            problem_note.get("mastery", "unknown"),
            "未评估",
        )
        self._render_problem_hero_card(
            parent,
            problem,
            problem_id,
            title,
            activity,
            mastery_label,
        )

        asset_card = self._create_card(parent, "解题资产")
        asset_card.pack(fill="x", pady=(0, 16))
        status = get_solution_status(problem_id, "Python")
        note = get_solution_note(problem_id)

        actions = tk.Frame(asset_card, bg=asset_card["bg"])
        actions.pack(fill="x", pady=(6, 0))
        if status["exists"]:
            self._secondary_button(
                actions,
                "重新生成 Python",
                lambda: self.generate_solution_for_problem(problem_id, "Python", force=True),
            ).pack(side="left")
        else:
            self._primary_button(
                actions,
                "生成 Python 题解",
                lambda: self.generate_solution_for_problem(problem_id, "Python", force=False),
            ).pack(side="left")
        self._secondary_button(
            actions,
            "生成 C++ 题解",
            lambda: self.generate_solution_for_problem(problem_id, "C++", force=False),
        ).pack(side="left", padx=10)
        if problem_id in self.solution_jobs:
            self._render_state_block(
                asset_card,
                "正在生成题解",
                "生成完成后会自动保存到这张题目卡。",
                kind="loading",
            )

        self._render_solution_sections(parent, note)
        self._render_problem_learning_card(parent, problem_id)

    def _render_problem_activity_card(self, parent, problem_id):
        summary = _problem_activity_summary(problem_id)
        card = self._create_card(parent, "学习轨迹")
        card.pack(fill="x", pady=(0, 16))
        self._render_info_chips(
            card,
            [
                ("提交次数", f"{summary.get('count', 0)} 次"),
                ("最近状态", summary.get("latest_status", "暂无")),
                ("主要错因", summary.get("main_mistake", "暂无")),
                ("主要来源", summary.get("source", "暂无")),
            ],
            accent_index=0,
            max_columns=4,
        )
        latest_time = summary.get("latest_time", "暂无")
        self._render_state_block(
            card,
            "最近提交",
            f"{latest_time}",
            kind="info" if summary.get("count", 0) else "empty",
        )

    def _render_problem_review_asset_card(self, parent, problem_id):
        review_summary = get_problem_review_summary(problem_id)
        card = self._create_card(parent, "复习安排")
        card.pack(fill="x", pady=(0, 16))

        pending_reviews = review_summary.get("pending_reviews", [])
        if pending_reviews:
            next_review = pending_reviews[0]
            self._render_info_chips(
                card,
                [
                    ("状态", f"待复习 {review_summary.get('pending', 0)} 次"),
                    ("下次复习", next_review.get("next_review_date", "暂无")),
                    ("轮次", f"第 {next_review.get('review_round', 1)} 轮"),
                    ("优先级", str(next_review.get("priority_level", "") or "普通")),
                ],
                accent_index=0,
                max_columns=4,
            )
            reason = next_review.get("reason", "") or "系统根据完成记录自动安排复习。"
            self._render_state_block(
                card,
                "为什么要复习",
                reason,
                kind="info",
            )
            return

        latest_reason = review_summary.get("latest_reason", "")
        message = latest_reason or "这道题目前没有待完成复习任务。"
        self._render_state_block(
            card,
            "暂无待复习",
            message,
            kind="empty",
        )

    def _render_problem_learning_card(self, parent, problem_id):
        note = get_problem_note(problem_id)
        card = self._create_card(parent, "我的笔记")
        card.pack(fill="x", pady=(0, 16))

        top = tk.Frame(card, bg=card["bg"])
        top.pack(fill="x", pady=(10, 8))
        tk.Label(
            top,
            text="掌握程度",
            bg=top["bg"],
            fg=TEXT_SECONDARY,
            font=("Microsoft YaHei UI", 9),
        ).pack(side="left")

        mastery_by_label = {
            label: key for key, label in MASTERY_LABELS.items()
        }
        current_mastery_label = MASTERY_LABELS.get(
            note.get("mastery", "unknown"),
            "未评估",
        )
        mastery_var = tk.StringVar(value=current_mastery_label)
        mastery_menu = ttk.OptionMenu(
            top,
            mastery_var,
            current_mastery_label,
            *MASTERY_LABELS.values(),
        )
        mastery_menu.pack(side="left", padx=(10, 18))

        tk.Label(
            top,
            text=f"最近保存：{note.get('updated_at', '') or '暂无'}",
            bg=top["bg"],
            fg=TEXT_SECONDARY,
            font=("Microsoft YaHei UI", 9),
        ).pack(side="left")

        tk.Label(
            card,
            text="我的笔记",
            bg=card["bg"],
            fg=TEXT_SECONDARY,
            font=("Microsoft YaHei UI", 9),
        ).pack(anchor="w", pady=(4, 4))
        note_box = tk.Text(
            card,
            wrap="word",
            relief="flat",
            bg="#FAFAFA",
            fg=TEXT,
            font=("Microsoft YaHei UI", 10),
            padx=12,
            pady=10,
            height=5,
        )
        note_box.pack(fill="x")
        note_box.insert("1.0", note.get("note", ""))

        action_row = tk.Frame(card, bg=card["bg"])
        action_row.pack(fill="x", pady=(10, 0))
        tk.Label(
            action_row,
            text="保存后会更新这张题目资产卡。",
            bg=action_row["bg"],
            fg=TEXT_WEAK,
            font=("Microsoft YaHei UI", 9),
        ).pack(side="left")

        def save_note():
            save_problem_note(
                problem_id,
                note_box.get("1.0", "end").strip(),
                mastery_by_label.get(mastery_var.get(), "unknown"),
            )
            self._show_toast("学习档案已保存")
            self.render()

        self._primary_button(
            action_row,
            "保存笔记",
            save_note,
        ).pack(side="right")

    def _text_card(self, parent, title, text, height=6, mono=False):
        card = self._create_card(parent, title)
        card.pack(fill="x", pady=(0, 16))
        frame = tk.Frame(card, bg="#FAFAFA")
        frame.pack(fill="both", expand=True, pady=(10, 0))
        scrollbar = tk.Scrollbar(frame, orient="vertical")
        output = tk.Text(
            frame,
            wrap="none" if mono else "word",
            relief="flat",
            bg="#FAFAFA",
            fg=TEXT,
            font=(
                "Consolas",
                10,
            ) if mono else ("Microsoft YaHei UI", 10),
            padx=14,
            pady=12,
            height=height,
            state="normal",
            yscrollcommand=scrollbar.set,
        )
        scrollbar.configure(command=output.yview)
        scrollbar.pack(side="right", fill="y")
        output.pack(side="left", fill="both", expand=True)
        output.insert("1.0", str(text or "暂无"))
        output.configure(state="disabled")
        return output

    def _copy_to_clipboard(self, text, message="已复制"):
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(str(text or ""))
            self._show_toast(message)
        except tk.TclError:
            self._show_toast("复制失败", kind="error")

    def _readable_text_card(self, parent, title, text, subtitle=""):
        card = self._create_card(parent, title, subtitle)
        card.pack(fill="x", pady=(0, 16))
        text_value = str(text or "暂无")
        body = tk.Text(
            card,
            wrap="word",
            relief="flat",
            bg=card["bg"],
            fg=TEXT,
            font=("Microsoft YaHei UI", 11),
            padx=2,
            pady=6,
            height=max(3, min(8, len(text_value) // 42 + 2)),
            cursor="xterm",
        )
        body.pack(fill="x", anchor="w", pady=(10, 0))
        body.insert("1.0", text_value)
        body.configure(state="disabled")
        body.bind(
            "<Control-a>",
            lambda event, widget=body: (
                widget.tag_add("sel", "1.0", "end"),
                "break",
            )[1],
        )
        return card

    def _code_card(self, parent, code, language=""):
        card = self._create_card(parent, "完整代码")
        card.pack(fill="x", pady=(0, 16))
        header = tk.Frame(card, bg=card["bg"])
        header.pack(fill="x", pady=(8, 10))
        self._pill(
            header,
            str(language or "Code"),
            "neutral",
        ).pack(side="left")
        copy_button = self._secondary_button(
            header,
            "复制代码",
            lambda: self._copy_code_with_feedback(copy_button, code),
        )
        copy_button.pack(side="right")

        frame = tk.Frame(
            card,
            bg="#FFFFFF",
            highlightthickness=1,
            highlightbackground=CARD_BORDER,
            highlightcolor=CARD_BORDER,
        )
        frame.pack(fill="both", expand=True)
        scrollbar = tk.Scrollbar(frame, orient="vertical")
        xscrollbar = tk.Scrollbar(frame, orient="horizontal")
        line_numbers = tk.Text(
            frame,
            width=4,
            wrap="none",
            relief="flat",
            bg="#FAFAFA",
            fg="#0070A8",
            font=("Consolas", 10),
            padx=8,
            pady=14,
            height=18,
            state="normal",
            takefocus=0,
        )
        output = tk.Text(
            frame,
            wrap="none",
            relief="flat",
            bg="#FFFFFF",
            fg="#111827",
            insertbackground=TEXT,
            font=("Consolas", 10),
            padx=16,
            pady=14,
            height=18,
            state="normal",
        )

        def sync_scrollbar(first, last):
            scrollbar.set(first, last)
            line_numbers.yview_moveto(first)

        def scroll_both(*args):
            output.yview(*args)
            line_numbers.yview(*args)

        output.configure(yscrollcommand=sync_scrollbar)
        output.configure(xscrollcommand=xscrollbar.set)
        scrollbar.configure(command=scroll_both)
        xscrollbar.configure(command=output.xview)
        scrollbar.pack(side="right", fill="y")
        xscrollbar.pack(side="bottom", fill="x")
        line_numbers.pack(side="left", fill="y")
        output.pack(side="left", fill="both", expand=True)
        code_text = str(code or "暂无代码。")
        line_count = max(1, len(code_text.splitlines()))
        line_numbers.insert(
            "1.0",
            "\n".join(str(index) for index in range(1, line_count + 1)),
        )
        output.insert("1.0", code_text)
        self._apply_code_highlighting(output, code_text, language)
        line_numbers.configure(state="disabled")
        output.configure(state="disabled")
        return output

    def _copy_code_with_feedback(self, button, code):
        self._copy_to_clipboard(code, "代码已复制")
        try:
            button.configure(text="已复制")
            self.root.after(1200, lambda: button.configure(text="复制代码"))
        except tk.TclError:
            pass

    def _apply_code_highlighting(self, widget, code, language=""):
        widget.tag_configure("keyword", foreground="#AF00DB")
        widget.tag_configure("definition", foreground="#0000FF")
        widget.tag_configure("string", foreground="#A31515")
        widget.tag_configure("comment", foreground="#008000")
        widget.tag_configure("number", foreground="#098658")
        widget.tag_configure("type", foreground="#267F99")
        widget.tag_configure("name", foreground="#001080")
        widget.tag_configure("function", foreground="#795E26")

        language_text = str(language or "").lower()
        if "c++" in language_text or "cpp" in language_text:
            keywords = {
                "class", "public", "private", "protected", "return", "if",
                "else", "for", "while", "do", "break", "continue", "const",
                "auto", "using", "namespace", "include", "true", "false",
                "nullptr", "new", "delete", "switch", "case", "default",
            }
            types = {
                "int", "long", "double", "float", "bool", "char", "void",
                "string", "vector", "unordered_map", "unordered_set", "map",
                "set", "queue", "stack", "pair",
            }
            comment_pattern = r"//.*?$|/\*.*?\*/"
        else:
            keywords = {
                "class", "def", "return", "if", "elif", "else", "for",
                "while", "break", "continue", "in", "not", "and", "or",
                "is", "None", "True", "False", "from", "import", "as",
                "with", "try", "except", "finally", "lambda", "pass",
            }
            types = {"int", "str", "bool", "list", "dict", "set", "tuple"}
            comment_pattern = r"#.*?$"

        def add_tag(tag, start, end):
            widget.tag_add(tag, f"1.0+{start}c", f"1.0+{end}c")

        for match in re.finditer(r"\b[A-Za-z_][A-Za-z0-9_]*\b", code):
            word = match.group(0)
            if word in keywords:
                tag = "definition" if word in {"class", "def"} else "keyword"
                add_tag(tag, match.start(), match.end())
            elif word in types:
                add_tag("type", match.start(), match.end())
            elif word in {"self", "cls", "this"}:
                add_tag("name", match.start(), match.end())

        for match in re.finditer(r"\b\d+(\.\d+)?\b", code):
            add_tag("number", match.start(), match.end())

        for match in re.finditer(
            r"(\"\"\".*?\"\"\"|'''.*?'''|\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*')",
            code,
            flags=re.DOTALL,
        ):
            add_tag("string", match.start(), match.end())

        for match in re.finditer(comment_pattern, code, flags=re.MULTILINE | re.DOTALL):
            add_tag("comment", match.start(), match.end())

        for match in re.finditer(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(", code):
            name = match.group(1)
            if name not in keywords:
                start = match.start(1)
                add_tag("function", start, start + len(name))

        for tag in ("keyword", "definition", "type", "name", "number", "function"):
            widget.tag_lower(tag)
        widget.tag_raise("string")
        widget.tag_raise("comment")

    def _mistake_cards(self, parent, mistakes):
        card = self._create_card(parent, "易错点")
        card.pack(fill="x", pady=(0, 16))
        if not isinstance(mistakes, list) or not mistakes:
            self._render_state_block(
                card,
                "暂无易错点",
                "这道题暂时没有保存易错点总结。",
                kind="empty",
            )
            return

        for index, item in enumerate(mistakes[:5], start=1):
            if not isinstance(item, dict):
                continue
            row = tk.Frame(
                card,
                bg="#FAFAFA",
                highlightbackground=LINE,
                highlightthickness=1,
                padx=14,
                pady=12,
            )
            row.pack(fill="x", pady=(10 if index == 1 else 8, 0))
            self._pill(row, f"{index}", "accent").pack(side="left", padx=(0, 12), anchor="n")
            text_area = tk.Frame(row, bg=row["bg"])
            text_area.pack(side="left", fill="x", expand=True)
            point = str(item.get("point", "易错点")).strip() or "易错点"
            explanation = str(item.get("explanation", "实现时重点检查。")).strip()
            tk.Label(
                text_area,
                text=point,
                bg=text_area["bg"],
                fg=TEXT,
                font=("Microsoft YaHei UI", 10, "bold"),
                anchor="w",
                justify="left",
            ).pack(fill="x", anchor="w")
            detail = tk.Label(
                text_area,
                text=explanation,
                bg=text_area["bg"],
                fg=TEXT_SECONDARY,
                font=("Microsoft YaHei UI", 10),
                anchor="w",
                justify="left",
            )
            detail.pack(fill="x", anchor="w", pady=(4, 0))
            self._bind_label_wrap(detail, text_area, min_width=220, max_width=780)

    def _complexity_card(self, parent, text):
        card = self._create_card(parent, "复杂度")
        card.pack(fill="x", pady=(0, 16))
        self._render_state_block(
            card,
            "时间 / 空间复杂度",
            str(text or "暂无复杂度说明。"),
            kind="info",
        )

    def _render_solution_sections(self, parent, solution):
        if not isinstance(solution, dict):
            card = self._create_card(parent, "AI 题解")
            card.pack(fill="x", pady=(0, 16))
            self._render_state_block(
                card,
                "还没有 AI 题解",
                "生成后，这里会直接显示解题思路、完整代码、易错点和复杂度。",
                kind="empty",
            )
            return

        self._readable_text_card(
            parent,
            "解题思路",
            solution.get("idea", "暂无思路说明。"),
            "先理解方法，再看代码实现。",
        )
        self._code_card(
            parent,
            solution.get("code", "暂无代码。"),
            solution.get("language", ""),
        )
        self._mistake_cards(parent, solution.get("common_mistakes", []))
        complexity_text = "\n".join(
            item for item in [
                "时间复杂度：" + str(solution.get("time_complexity", "")).strip()
                if solution.get("time_complexity")
                else "",
                "空间复杂度：" + str(solution.get("space_complexity", "")).strip()
                if solution.get("space_complexity")
                else "",
            ] if item
        )
        self._complexity_card(
            parent,
            complexity_text or "暂无复杂度说明。",
        )

    def _render_ai(self, parent):
        self._page_header(
            parent,
            "AI 助手",
            "输入题号后生成标准题解笔记，结果会自动保存到题库对应题目页面。",
        )

        if self.ai_job_status.get("state") != "idle":
            status_kind = {
                "running": "loading",
                "success": "success",
                "error": "error",
            }.get(self.ai_job_status.get("state"), "info")
            status_card = self._create_card(parent)
            status_card.pack(fill="x", pady=(0, 16))
            self._render_state_block(
                status_card,
                self.ai_job_status.get("title", "AI 任务"),
                self.ai_job_status.get("message", ""),
                kind=status_kind,
            )

        solution_card = self._create_card(parent, "生成题解笔记")
        solution_card.pack(fill="x", pady=(0, 16))
        intro_label = tk.Label(
            solution_card,
            text=(
                "LeetCoach 会按固定模板生成：解题思路、带详细注释的完整代码、"
                "易错点总结和时间复杂度。"
            ),
            bg=solution_card["bg"],
            fg=TEXT_SECONDARY,
            font=("Microsoft YaHei UI", 10),
            justify="left",
        )
        intro_label.pack(fill="x", anchor="w", pady=(10, 12))
        self._bind_label_wrap(
            intro_label,
            solution_card,
            padding=36,
            min_width=180,
            max_width=760,
        )

        form = tk.Frame(solution_card, bg=solution_card["bg"])
        form.pack(fill="x")
        form.grid_columnconfigure(0, weight=1)
        form.grid_columnconfigure(1, weight=0)
        tk.Label(
            form,
            text="题号",
            bg=form["bg"],
            fg=TEXT_SECONDARY,
            font=("Microsoft YaHei UI", 9),
        ).grid(row=0, column=0, sticky="w", pady=(0, 5))
        tk.Label(
            form,
            text="语言",
            bg=form["bg"],
            fg=TEXT_SECONDARY,
            font=("Microsoft YaHei UI", 9),
        ).grid(row=0, column=1, sticky="w", padx=(12, 0), pady=(0, 5))
        self.ai_problem_entry = tk.Entry(
            form,
            relief="flat",
            bd=0,
            font=("Microsoft YaHei UI", 11),
            bg="#F8F8F8",
            fg=TEXT,
            insertbackground=ACCENT,
            highlightthickness=1,
            highlightbackground=LINE,
            highlightcolor=ACCENT,
        )
        self.ai_problem_entry.grid(row=1, column=0, sticky="ew", ipady=8)
        self._attach_placeholder(self.ai_problem_entry, "例如 383")
        self.ai_language = tk.StringVar(value="Python")
        ttk.OptionMenu(
            form,
            self.ai_language,
            "Python",
            "Python",
            "C++",
        ).grid(row=1, column=1, sticky="ew", padx=(12, 0))
        self.ai_problem_entry.bind(
            "<Control-Return>",
            lambda _event: (
                self.generate_ai_hint(),
                "break",
            )[1],
        )
        self.ai_problem_entry.bind(
            "<Return>",
            lambda _event: (
                self.generate_ai_hint(),
                "break",
            )[1],
        )

        prompt_actions = tk.Frame(solution_card, bg=solution_card["bg"])
        prompt_actions.pack(fill="x", pady=(12, 0))
        tk.Label(
            prompt_actions,
            text="生成结果会保存为题库笔记，之后点击题库里的这道题即可复习。",
            bg=prompt_actions["bg"],
            fg=TEXT_WEAK,
            font=("Microsoft YaHei UI", 9),
        ).pack(side="left")
        self._primary_button(
            prompt_actions,
            "生成题解",
            self.generate_ai_hint,
        ).pack(side="right")

        self.ai_output = self._build_output_card(parent, "AI 题解笔记", height=24)
        self._set_ai_output(
            "输入题号后生成标准题解。\n\n"
            "输出包含：\n"
            "1. 解题思路\n"
            "2. 带详细注释的完整代码\n"
            "3. 易错点总结\n"
            "4. 时间复杂度"
        )
        self.ai_problem_entry.focus_set()

    def _render_ai_task_list(self, parent):
        tasks = get_recent_ai_tasks(limit=5)
        if not tasks:
            return
        card = self._create_card(parent, "最近 AI 任务")
        card.pack(fill="x", pady=(0, 16))
        for task in tasks:
            row = tk.Frame(card, bg=card["bg"])
            row.pack(fill="x", pady=(8, 0))
            status = task.get("status", "")
            status_text = {
                "running": "生成中",
                "success": "成功",
                "error": "失败",
            }.get(status, status or "未知")
            title = (
                f"{task.get('problem_id', '')} "
                f"{task.get('language', '')} · {status_text}"
            ).strip()
            tk.Label(
                row,
                text=title,
                bg=row["bg"],
                fg=TEXT,
                font=("Microsoft YaHei UI", 10, "bold"),
                anchor="w",
            ).pack(side="left")
            tk.Label(
                row,
                text=task.get("created_at", ""),
                bg=row["bg"],
                fg=TEXT_WEAK,
                font=("Microsoft YaHei UI", 9),
            ).pack(side="left", padx=(10, 0))
            problem_id = str(task.get("problem_id", "")).strip()
            language = str(task.get("language", "Python")).strip() or "Python"
            if problem_id and status == "error":
                self._secondary_button(
                    row,
                    "重试",
                    lambda p=problem_id, lang=language: self.retry_ai_task(p, lang),
                ).pack(side="right")
            elif problem_id and status == "success":
                self._secondary_button(
                    row,
                    "查看",
                    lambda p=problem_id: self.open_problem_from_ai_task(p),
                ).pack(side="right")

    def retry_ai_task(self, problem_id, language="Python"):
        if hasattr(self, "ai_problem_entry"):
            self.ai_problem_entry.delete(0, tk.END)
            self.ai_problem_entry.configure(fg=TEXT)
            self.ai_problem_entry._leetcoach_placeholder_active = False
            self.ai_problem_entry.insert(0, problem_id)
        if hasattr(self, "ai_language"):
            self.ai_language.set(language)
        self.generate_ai_hint(force=True)

    def open_problem_from_ai_task(self, problem_id):
        library = get_problem_library_data()
        for topic in library.get("topics", []):
            for problem in topic.get("problems", []):
                if str(problem.get("problem_id", "")) == str(problem_id):
                    self.selected_topic = topic.get("topic")
                    self.selected_problem = dict(problem)
                    self.mode = "problem_detail"
                    self.render()
                    return
        self._show_toast("题库中暂时找不到这道题")

    def _render_more(self, parent):
        self._page_header(
            parent,
            "设置",
            "只保留少量必要工具，日常学习不被打扰。",
        )

        actions = tk.Frame(parent, bg=PAGE_BG)
        actions.pack(fill="x", pady=(0, 16))
        buttons = [
            ("数据校验", self.run_data_validation),
            ("查看当前配置状态", self.show_public_config_status),
            ("查看同步状态", self.show_public_sync_status),
            ("打开数据目录", self.open_data_directory),
            ("关于 LeetCoach", self.show_about_leetcoach),
        ]
        for column in range(3):
            actions.grid_columnconfigure(column, weight=1)
        for index, (label, handler) in enumerate(buttons):
            button = self._secondary_button(actions, label, handler)
            button.grid(
                row=index // 3,
                column=index % 3,
                sticky="ew",
                padx=(0 if index % 3 == 0 else 8, 0),
                pady=(0 if index < 3 else 8, 0),
            )

        if not _show_llm_lab():
            self.more_output = self._build_output_card(parent, "工具输出", height=14)
            self._set_more_output(
                "这里保留日常维护工具。\n\n"
                "需要 PromptOps、RAG、Agent 或本地模型实验入口时，"
                "请在 config/app_settings.json 中开启 developer_mode 或 show_llm_lab。"
            )
            return

        lab_card = self._create_card(
            parent,
            "LLM Lab",
            "观察 Prompt、调用日志、质量评分和兜底情况。",
        )
        lab_card.pack(fill="x", pady=(0, 16))
        lab_actions = tk.Frame(lab_card, bg=CARD_BG)
        lab_actions.pack(fill="x", pady=(12, 0))
        lab_buttons = [
            ("生成用户反馈记忆", self.generate_user_feedback_memory),
            ("查看用户反馈记忆", self.show_user_feedback_memory),
            ("查看最近 LLM 调用", self.show_llm_logs),
            ("查看最近 AI 计划评估", self.show_plan_evaluations),
            ("查看当前 Prompt 模板", self.show_ai_plan_prompt_template),
            ("测试 AI 计划生成", self.test_ai_plan_generation_lab),
            ("Prompt 版本对比实验", self.run_prompt_comparison_lab),
            ("Prompt 实验统计报告", self.show_prompt_experiment_summary),
            ("RAG 检索质量测试", self.run_rag_eval_lab),
            ("RAG 有无对比实验", self.run_rag_ab_lab),
            ("RAG A/B 实验统计报告", self.show_rag_ab_summary),
            ("查看最近 RAG 证据链", self.show_recent_rag_traces),
            ("RAG 证据链统计报告", self.show_rag_trace_summary),
            ("RAG 个性化记忆质量报告", self.show_rag_memory_quality_report),
            ("增强记忆 RAG A/B 实验", self.run_enhanced_memory_ab_lab),
            ("增强记忆 RAG 统计报告", self.show_enhanced_memory_summary),
            ("批量运行 LLM 实验", self.run_llm_experiment_batch_lab),
            ("查看最近 LLM 综合实验报告", self.show_recent_llm_experiment_batch_reports),
        ]
        lab_buttons.insert(2, ("LLM 工具选择测试", self.run_llm_tool_selection_lab))
        lab_buttons.insert(3, ("Rule vs LLM Agent 对比报告", self.show_policy_comparison_summary))
        lab_buttons.insert(4, ("Agent 规则策略场景测试", self.run_agent_policy_rule_benchmark_lab))
        lab_buttons.insert(5, ("Agent Policy Benchmark", self.run_agent_policy_benchmark_lab))
        lab_buttons.insert(7, ("本地模型服务检查", self.show_local_model_service_lab))
        lab_buttons.insert(8, ("本地 Embedding Warmup", self.run_local_embedding_warmup_lab))
        lab_buttons.insert(9, ("本地 Embedding 测试", self.run_local_embedding_lab))
        lab_buttons.insert(10, ("云端 vs 本地 Embedding 对比", self.run_cloud_vs_local_embedding_lab))
        lab_buttons.insert(11, ("本地 Embedding RAG 对比实验", self.run_local_embedding_rag_lab))
        lab_buttons.insert(12, ("本地 Embedding RAG 统计报告", self.show_local_embedding_rag_summary))
        lab_buttons.insert(6, ("Agent Policy Benchmark 统计报告", self.show_agent_policy_benchmark_summary))
        for column in range(2):
            lab_actions.grid_columnconfigure(column, weight=1)
        for index, (label, handler) in enumerate(lab_buttons):
            button = self._secondary_button(lab_actions, label, handler)
            button.grid(
                row=index // 2,
                column=index % 2,
                sticky="ew",
                padx=(0 if index % 2 == 0 else 8, 0),
                pady=(0 if index < 2 else 8, 0),
            )

        self.more_output = self._build_output_card(parent, "工具输出", height=20)
        self._set_more_output(
            "这里保留低频工具和 LLM Lab。\n\n主流程仍然是：今天 -> 完成任务 -> 题库沉淀。"
        )

    def _build_output_card(self, parent, title, height=18):
        card = self._create_card(parent, title)
        card.pack(fill="both", expand=True)
        output_frame = tk.Frame(card, bg="#FAFAFA")
        output_frame.pack(fill="both", expand=True, pady=(12, 0))
        scrollbar = tk.Scrollbar(output_frame, orient="vertical")
        output = tk.Text(
            output_frame,
            wrap="word",
            relief="flat",
            bg="#FAFAFA",
            fg=TEXT,
            font=("Microsoft YaHei UI", 10),
            padx=14,
            pady=14,
            height=height,
            state="disabled",
            yscrollcommand=scrollbar.set,
        )
        scrollbar.configure(command=output.yview)
        scrollbar.pack(side="right", fill="y")
        output.pack(side="left", fill="both", expand=True)
        return output

    def _render_task_list(self, parent, tasks, weekly=False):
        if not tasks:
            self._render_state_block(
                parent,
                "当前没有任务",
                "可以先查看计划草案，或同步最近的力扣提交记录。",
                kind="empty",
            )
            return

        list_frame = tk.Frame(parent, bg=parent["bg"])
        list_frame.pack(fill="x", pady=(12, 0))
        current_day = self.data.get("plan_phase", {}).get("day_index", 0)
        for task in tasks:
            highlight = bool(
                weekly
                and current_day
                and current_day in task.get("scheduled_days", [])
                and not task.get("completed")
            )
            self._render_task_row(
                list_frame,
                task,
                weekly=weekly,
                highlight=highlight,
                card_bg=parent["bg"],
            )

    def _render_task_row(self, parent, task, weekly, highlight=False, card_bg=BACKGROUND):
        row_bg = ACCENT_SOFT if highlight else card_bg
        row = tk.Frame(parent, bg=row_bg, padx=8, pady=10)
        row.pack(fill="x", pady=4)

        circle = tk.Canvas(
            row,
            width=28,
            height=28,
            bg=row_bg,
            highlightthickness=0,
            cursor="hand2",
        )
        circle.pack(side="left", padx=(0, 12))
        completed = bool(task.get("completed"))
        circle.create_oval(
            4,
            4,
            24,
            24,
            outline=SUCCESS if completed else "#B7B7B7",
            width=2,
            fill=SUCCESS if completed else row_bg,
            tags="circle",
        )
        if completed:
            circle.create_text(
                14,
                14,
                text="✓",
                fill="white",
                font=("Microsoft YaHei UI", 11, "bold"),
                tags="check",
            )
        else:
            def paint_circle(outline, fill):
                circle.itemconfigure("circle", outline=outline, fill=fill)

            circle.bind(
                "<Button-1>",
                lambda _event, item=task, widget=circle: self._start_completion(item, widget),
            )
            circle.bind("<Enter>", lambda _event: paint_circle(ACCENT, ACCENT_SOFT))
            circle.bind("<Leave>", lambda _event: paint_circle("#B7B7B7", row_bg))
            circle.bind("<ButtonPress-1>", lambda _event: paint_circle(ACCENT_DARK, "#FADBD8"))

        text_frame = tk.Frame(row, bg=row_bg)
        text_frame.pack(side="left", fill="x", expand=True)
        problem_id = str(task.get("problem_id", "")).strip()
        title = task.get("title", "未知任务")
        display_title = f"{problem_id} {title}".strip()
        title_font = ("Microsoft YaHei UI", 11, "bold")
        title_label = tk.Label(
            text_frame,
            text=display_title,
            bg=row_bg,
            fg=TEXT_WEAK if completed else TEXT,
            font=title_font,
            anchor="w",
            justify="left",
        )
        title_label.pack(fill="x", anchor="w")
        self._bind_label_wrap(title_label, text_frame, min_width=160)

        if weekly:
            days = "、".join(f"Day {day}" for day in task.get("scheduled_days", []))
            detail = (
                task.get("difficulty", "未知")
                if task.get("kind") != "milestone"
                else task.get("label", "阶段任务")
            )
            meta = f"{days} · {detail}" if days else detail
        else:
            meta = task.get("label", "")
        status_text = "已完成" if completed else "待完成"
        meta_label = tk.Label(
            text_frame,
            text=f"{meta} · {status_text}" if meta else status_text,
            bg=row_bg,
            fg=TEXT_SECONDARY,
            font=("Microsoft YaHei UI", 9),
            anchor="w",
            justify="left",
        )
        meta_label.pack(fill="x", anchor="w", pady=(4, 0))
        self._bind_label_wrap(meta_label, text_frame, min_width=160)
        hover_targets = [row, text_frame, title_label, meta_label]

        reason = str(task.get("reason", "")).strip() if weekly else ""
        if reason:
            reason_label = tk.Label(
                text_frame,
                text=f"安排原因：{reason}",
                bg=row_bg,
                fg=TEXT_WEAK,
                font=("Microsoft YaHei UI", 9),
                justify="left",
                anchor="w",
            )
            reason_label.pack(fill="x", anchor="w", pady=(6, 0))
            self._bind_label_wrap(reason_label, text_frame, min_width=160)
            hover_targets.append(reason_label)

        if not completed and not highlight:
            def set_row_bg(color):
                for widget in hover_targets:
                    try:
                        widget.configure(bg=color)
                    except tk.TclError:
                        pass

            for widget in hover_targets:
                widget.bind("<Enter>", lambda _event: set_row_bg("#FBFAF8"), add="+")
                widget.bind("<Leave>", lambda _event: set_row_bg(row_bg), add="+")

    def _set_text_output(self, widget, text):
        if widget is None:
            return
        widget.configure(state="normal")
        widget.delete("1.0", tk.END)
        widget.insert("1.0", str(text))
        widget.configure(state="disabled")

    def _set_sync_output(self, text):
        self._set_text_output(self.sync_output, text)

    def _set_review_output(self, text):
        self._set_text_output(self.review_output, text)

    def _set_ai_output(self, text):
        self._set_text_output(self.ai_output, text)

    def _set_more_output(self, text):
        self._set_text_output(self.more_output, text)

    def generate_plan_draft(self):
        if self.plan_generating:
            return
        self.plan_generating = True
        self._show_toast("正在分析提交记录并生成计划...")
        self.set_mode("plan")

        def worker():
            try:
                plan = generate_ai_week_plan_next(
                    trigger="manual",
                    context_fingerprint=build_plan_context_fingerprint(),
                )
                message = f"Week {plan.get('week', '')} 计划草案已生成，请确认后启用"
            except Exception as error:
                message = f"计划生成失败：{error}"

            self.root.after(
                0,
                lambda: self._finish_plan_generation(message),
            )

        threading.Thread(target=worker, daemon=True).start()

    def _finish_plan_generation(self, message):
        self.plan_generating = False
        self._show_toast(message)
        self.set_mode("plan")

    def confirm_plan_draft(self):
        management = get_plan_management_data()
        draft = management.get("draft")
        if not isinstance(draft, dict):
            self._notify(
                "当前没有可确认的计划草案",
                "你可以先点击“重新生成”，让 LeetCoach 根据最新记录生成一份新计划。",
                kind="warning",
            )
            return

        confirmed = self._confirm(
            "确认学习计划",
            (
                f"确认启用 Week {draft.get('week', '')} - "
                f"{draft.get('title', '学习计划')}？\n\n"
                "启用后，今天将作为新计划 Day 1 开始，旧计划会自动备份。"
            ),
            confirm_text="启用计划",
        )
        if not confirmed:
            return

        result = apply_week_plan_next()
        if not result.get("success"):
            self._notify(
                "计划启用失败",
                result.get("message", "计划启用失败。"),
                kind="error",
            )
            return

        self.refresh()
        self.set_mode("today")
        self._show_toast("新计划已启用，今日任务已更新")

    def install_sync_extension(self):
        success, message = open_chrome_extension_page()
        if success:
            self._notify("已打开同步组件安装页面", message, kind="info")
        else:
            self._notify("无法打开同步组件安装页面", message, kind="error")

    def start_local_push_sync(self):
        success, message = start_local_push_server()
        toast = "同步服务已启动" if success else f"同步服务启动失败：{message}"
        self._show_toast(toast, kind="success" if success else "error")
        if self.mode == "sync":
            self.render()
            self._set_sync_output(format_local_push_status())

    def open_leetcode_in_chrome(self):
        username = load_leetcode_config().get("leetcode_username", "")
        success, message = open_leetcode_page(username)
        if success:
            self._show_toast("已打开力扣页面")
        else:
            self._notify("无法打开力扣页面", message, kind="error")

    def show_recent_synced_records(self):
        try:
            records = get_recent_synced_records()
            text = format_recent_synced_records(records)
        except Exception as error:
            text = f"！ 读取最近同步记录失败\n\n错误：{error}"
        self._set_sync_output(text)

    def run_sync_diagnostics(self):
        target = self.sync_output if self.mode == "sync" else self.more_output
        self._set_loading_output(
            target,
            "正在检查扩展、标签页和缓存状态，请稍候...\n扩展后台有时需要 30 到 40 秒完成一次诊断。",
        )

        def worker():
            try:
                result = get_sync_diagnostics()
                text = format_sync_diagnostics(result)
            except Exception as error:
                text = f"！ 同步自检失败\n\n错误：{error}"

            self.root.after(0, lambda: self._set_text_output(target, text))

        threading.Thread(target=worker, daemon=True).start()

    def show_records(self):
        try:
            text = format_records(get_all_records())
        except Exception as error:
            text = f"！ 读取刷题记录失败\n\n错误：{error}"
        self._set_text_output(self.review_output or self.more_output, text)

    def show_mistake_stats(self):
        try:
            text = format_mistake_stats(get_mistake_stats())
        except Exception as error:
            text = f"！ 读取错因统计失败\n\n错误：{error}"
        self._set_text_output(self.review_output or self.more_output, text)

    def show_week_summary(self):
        try:
            text = generate_week_summary()
        except Exception as error:
            text = f"！ 生成本周总结失败\n\n错误：{error}"
        self._set_text_output(self.review_output or self.more_output, text)

    def show_agent_observation(self):
        try:
            text = format_learning_observation(collect_learning_observation())
        except Exception as error:
            text = f"！Agent 当前观察读取失败\n\n错误：{error}"
        self._set_more_output(text)

    def show_agent_current_decision(self):
        try:
            observation = collect_learning_observation()
            decision = decide_next_agent_action(observation)
            text = "\n\n".join([
                format_learning_observation(observation),
                format_agent_decision(decision),
            ])
        except Exception as error:
            text = f"！Agent 当前决策生成失败\n\n错误：{error}"
        self._set_more_output(text)

    def show_agent_decision_logs(self):
        try:
            summary = summarize_agent_decisions(limit=50)
            text = format_agent_decision_summary(summary)
        except Exception as error:
            text = f"！Agent 决策日志读取失败\n\n错误：{error}"
        self._set_more_output(text)

    def show_agent_tools(self):
        try:
            text = format_agent_tools()
        except Exception as error:
            text = f"！Agent 工具列表读取失败\n\n错误：{error}"
        self._set_more_output(text)

    def show_agent_tool_logs(self):
        try:
            summary = summarize_agent_tool_calls(limit=50)
            text = format_agent_tool_summary(summary)
        except Exception as error:
            text = f"！Agent 工具调用日志读取失败\n\n错误：{error}"
        self._set_more_output(text)

    def show_agent_pending_actions(self):
        try:
            summary = summarize_pending_actions(limit=50)
            text = format_pending_actions_report(summary)
        except Exception as error:
            text = f"！Agent 待确认动作读取失败\n\n错误：{error}"
        self._set_more_output(text)

    def _first_pending_or_notice(self):
        action = get_first_active_pending_action()
        if not action:
            self._set_more_output("当前没有待确认动作。")
            self._show_toast("当前没有待确认动作")
            return None
        return action

    def confirm_first_pending_action(self):
        action = self._first_pending_or_notice()
        if not action:
            return
        confirmed = self._confirm(
            "确认执行 Agent 建议动作",
            (
                f"{action.get('title', '')}\n\n"
                f"工具：{action.get('tool_name', '')}\n"
                f"风险等级：{action.get('risk_level', '')}\n\n"
                "高风险动作可能修改计划，但会保留原有备份机制。确定执行吗？"
            ),
            confirm_text="确认执行",
        )
        if not confirmed:
            return
        try:
            result = confirm_pending_action(action.get("action_id"))
            self._set_more_output(
                "\n\n".join([
                    result.get("message", "待确认动作已处理。"),
                    format_pending_actions_report(summarize_pending_actions(limit=50)),
                ])
            )
            if result.get("success"):
                self.refresh()
                self._show_toast("Agent 待确认动作已执行")
            else:
                self._show_toast("Agent 待确认动作执行失败")
        except Exception as error:
            self._set_more_output(f"！确认待确认动作失败\n\n错误：{error}")

    def snooze_first_pending_action(self):
        action = self._first_pending_or_notice()
        if not action:
            return
        try:
            result = snooze_pending_action(
                action.get("action_id"),
                reason="用户选择稍后处理",
            )
            self._set_more_output(
                "\n\n".join([
                    result.get("message", "已暂缓该待确认动作。"),
                    format_pending_actions_report(summarize_pending_actions(limit=50)),
                ])
            )
            self._show_toast("已暂缓 Agent 待确认动作")
        except Exception as error:
            self._set_more_output(f"！暂缓待确认动作失败\n\n错误：{error}")

    def reject_first_pending_action(self):
        action = self._first_pending_or_notice()
        if not action:
            return
        try:
            result = reject_pending_action(
                action.get("action_id"),
                reason="用户拒绝该 Agent 建议",
            )
            self._set_more_output(
                "\n\n".join([
                    result.get("message", "已拒绝该待确认动作。"),
                    format_pending_actions_report(summarize_pending_actions(limit=50)),
                ])
            )
            self._show_toast("已拒绝 Agent 待确认动作")
        except Exception as error:
            self._set_more_output(f"！拒绝待确认动作失败\n\n错误：{error}")

    def generate_user_feedback_memory(self):
        try:
            profile = analyze_user_feedback(limit=100)
            save_user_learning_profile(profile)
            self._set_more_output(format_user_feedback_report(profile))
            self._show_toast("用户反馈记忆已更新")
        except Exception as error:
            self._set_more_output(f"！用户反馈记忆生成失败\n\n错误：{error}")

    def show_user_feedback_memory(self):
        try:
            profile = load_user_learning_profile()
            if not profile:
                self._set_more_output(
                    "===== 用户反馈记忆 =====\n\n暂无用户反馈记忆。\n请先点击“生成用户反馈记忆”。"
                )
                return
            self._set_more_output(format_user_feedback_report(profile))
        except Exception as error:
            self._set_more_output(f"！用户反馈记忆读取失败\n\n错误：{error}")

    def run_llm_tool_selection_lab(self):
        if self.plan_generating:
            self._show_toast("LLM 实验正在运行中")
            return
        self.plan_generating = True
        self.set_mode("more")
        self._set_loading_output(
            self.more_output,
            "正在运行 LLM 工具选择沙盒。\n\n这只会比较规则 Agent 和 LLM Agent，不会执行任何工具。",
        )

        def worker():
            try:
                result = compare_rule_and_llm_policy()
                text = format_policy_comparison(result)
            except Exception as error:
                text = f"！LLM 工具选择测试失败\n\n错误：{error}"

            def finish():
                self.plan_generating = False
                self._set_more_output(text)
                self._show_toast("LLM 工具选择测试完成")

            self.root.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()

    def show_policy_comparison_summary(self):
        try:
            summary = summarize_policy_comparisons(limit=50)
            text = format_policy_comparison_summary(summary)
        except Exception as error:
            text = f"！Rule vs LLM Agent 对比报告读取失败\n\n错误：{error}"
        self._set_more_output(text)

    def run_agent_policy_rule_benchmark_lab(self):
        self.set_mode("more")
        self._set_loading_output(
            self.more_output,
            "正在运行 Agent 规则策略场景测试。\n\n该测试不调用模型，不执行任何工具。",
        )

        def worker():
            try:
                result = run_agent_policy_benchmark(use_llm=False)
                text = format_agent_policy_benchmark_report(result)
            except Exception as error:
                text = f"！Agent 规则策略场景测试失败\n\n错误：{error}"
            self.root.after(0, lambda: self._set_more_output(text))

        threading.Thread(target=worker, daemon=True).start()

    def run_agent_policy_benchmark_lab(self):
        if self.plan_generating:
            self._show_toast("LLM 实验正在运行中")
            return
        confirmed = self._confirm(
            "Agent Policy Benchmark",
            "这会对多个场景调用大模型进行工具选择测试，可能产生 API 费用。\n\nBenchmark 不会执行任何工具，也不会修改计划。是否继续？",
            confirm_text="继续测试",
        )
        if not confirmed:
            return

        self.plan_generating = True
        self.set_mode("more")
        self._set_loading_output(
            self.more_output,
            "正在运行 Agent Policy Benchmark。\n\n这只会测试 LLM 工具选择，不会执行任何工具。",
        )

        def worker():
            try:
                result = run_agent_policy_benchmark(use_llm=True)
                text = format_agent_policy_benchmark_report(result)
            except Exception as error:
                text = f"！Agent Policy Benchmark 失败\n\n错误：{error}"

            def finish():
                self.plan_generating = False
                self._set_more_output(text)
                self._show_toast("Agent Policy Benchmark 完成")

            self.root.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()

    def show_agent_policy_benchmark_summary(self):
        try:
            summary = summarize_agent_policy_benchmarks(limit=20)
            text = format_agent_policy_benchmark_summary(summary)
        except Exception as error:
            text = f"！Agent Policy Benchmark 统计报告读取失败\n\n错误：{error}"
        self._set_more_output(text)

    def show_local_model_service_lab(self):
        try:
            result = test_local_service()
            text = format_local_service_status(result)
        except Exception as error:
            text = f"！本地模型服务检查失败\n\n错误：{error}"
        self._set_more_output(text)

    def run_local_embedding_lab(self):
        self.set_mode("more")
        self._set_loading_output(
            self.more_output,
            "正在测试本地 Embedding。\n\n这只是实验检查，不会改变正式 RAG 或 AI 计划策略。",
        )

        def worker():
            try:
                result = test_local_embedding()
                text = format_local_embedding_test(result)
            except Exception as error:
                text = f"！本地 Embedding 测试失败\n\n错误：{error}"
            self.root.after(0, lambda: self._set_more_output(text))

        threading.Thread(target=worker, daemon=True).start()

    def run_local_embedding_warmup_lab(self):
        self.set_mode("more")
        self._set_loading_output(
            self.more_output,
            "正在执行本地 Embedding Warmup。\n\n首次加载模型可能较慢，warmup 不会改变默认策略。",
        )

        def worker():
            try:
                result = test_local_embedding_warmup()
                text = format_local_embedding_warmup(result)
            except Exception as error:
                text = f"！本地 Embedding Warmup 失败\n\n错误：{error}"
            self.root.after(0, lambda: self._set_more_output(text))

        threading.Thread(target=worker, daemon=True).start()

    def run_cloud_vs_local_embedding_lab(self):
        self.set_mode("more")
        self._set_loading_output(
            self.more_output,
            "正在对比云端与本地 Embedding 排序。\n\n这只会运行固定测试样本，不会切换默认策略。",
        )

        def worker():
            try:
                result = compare_cloud_vs_local_embedding()
                text = format_cloud_vs_local_embedding_comparison(result)
            except Exception as error:
                text = f"！云端 vs 本地 Embedding 对比失败\n\n错误：{error}"
            self.root.after(0, lambda: self._set_more_output(text))

        threading.Thread(target=worker, daemon=True).start()

    def run_local_embedding_rag_lab(self):
        self.set_mode("more")
        self._set_loading_output(
            self.more_output,
            "正在运行本地 Embedding RAG 对比实验。\n\n实验会比较同一批 RAG 候选文档下的云端 / 本地排序，不会修改默认策略。",
        )

        def worker():
            try:
                result = run_local_embedding_rag_experiment()
                text = format_local_embedding_rag_experiment(result)
            except Exception as error:
                text = f"！本地 Embedding RAG 对比实验失败\n\n错误：{error}"
            self.root.after(0, lambda: self._set_more_output(text))

        threading.Thread(target=worker, daemon=True).start()

    def show_local_embedding_rag_summary(self):
        try:
            summary = summarize_local_embedding_rag_experiments(limit=20)
            text = format_local_embedding_rag_summary(summary)
        except Exception as error:
            text = f"！本地 Embedding RAG 统计报告读取失败\n\n错误：{error}"
        self._set_more_output(text)

    def show_agent_state(self):
        try:
            text = format_agent_state(analyze_learning_state())
        except Exception as error:
            text = f"！ Agent 状态分析失败\n\n错误：{error}"
        self._set_text_output(self.review_output or self.more_output, text)

    def show_agent_trend(self):
        try:
            text = analyze_trend()
        except Exception as error:
            text = f"！ Agent 趋势分析失败\n\n错误：{error}"
        self._set_text_output(self.review_output or self.more_output, text)

    def show_llm_logs(self):
        try:
            text = format_recent_llm_logs(get_recent_llm_logs(limit=5))
        except Exception as error:
            text = f"！ 读取 LLM 调用日志失败\n\n错误：{error}"
        self._set_more_output(text)

    def show_plan_evaluations(self):
        try:
            text = format_recent_plan_evaluations(
                get_recent_plan_evaluations(limit=5)
            )
        except Exception as error:
            text = f"！ 读取 AI 计划评估失败\n\n错误：{error}"
        self._set_more_output(text)

    def show_ai_plan_prompt_template(self):
        try:
            text = load_prompt_template("ai_plan_generator_v1")
        except Exception as error:
            text = f"！ 读取 Prompt 模板失败\n\n错误：{error}"
        self._set_more_output(text)

    def test_ai_plan_generation_lab(self):
        if self.plan_generating:
            self._show_toast("AI 计划正在生成中")
            return

        self.plan_generating = True
        self.set_mode("more")
        self._set_loading_output(
            self.more_output,
            "正在运行 AI 计划生成测试。不会自动应用计划。",
        )

        def worker():
            try:
                plan = generate_ai_week_plan_next(
                    trigger="llm_lab",
                    context_fingerprint=build_plan_context_fingerprint(),
                )
                eval_result = plan.get("llm_eval_result", {})
                errors = eval_result.get("errors", []) or []
                warnings = eval_result.get("warnings", []) or []
                infos = eval_result.get("infos", []) or []
                legacy_issues = eval_result.get("issues", []) or []
                lines = [
                    "===== LLM Lab：AI 计划生成测试 =====",
                    "",
                    plan.get("llm_lab_notice", "AI 计划生成流程已完成。"),
                    "",
                    f"计划：Week {plan.get('week', '')} - {plan.get('title', '')}",
                    f"生成方式：{plan.get('generated_by', '')}",
                    f"使用兜底：{plan.get('llm_fallback_used', False)}",
                    f"Prompt：{plan.get('prompt_version', '')}",
                    f"评分：{eval_result.get('score', '未评估')}",
                    "",
                    "严重问题：",
                ]
                if errors:
                    lines.extend(f"- {issue}" for issue in errors[:8])
                else:
                    lines.append("- 无")
                lines.append("")
                lines.append("质量提醒：")
                if warnings:
                    lines.extend(f"- {issue}" for issue in warnings[:8])
                else:
                    lines.append("- 无")
                lines.append("")
                lines.append("说明：")
                if infos:
                    lines.extend(f"- {issue}" for issue in infos[:8])
                elif legacy_issues:
                    lines.extend(f"- {issue}" for issue in legacy_issues[:8])
                else:
                    lines.append("- 无")
                lines.extend([
                    "",
                    "计划草案已保存到 config/week_plan_next.json。",
                    "这次测试不会自动应用计划。",
                ])
                text = "\n".join(lines)
            except Exception as error:
                text = f"！ AI 计划生成测试失败\n\n错误：{error}"

            def finish():
                self.plan_generating = False
                self._set_more_output(text)
                self._show_toast("LLM Lab 测试完成")

            self.root.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()

    def run_prompt_comparison_lab(self):
        if self.plan_generating:
            self._show_toast("AI 计划实验正在运行中")
            return

        self.plan_generating = True
        self.set_mode("more")
        self._set_loading_output(
            self.more_output,
            "正在用同一份学习上下文对比 Prompt v1 / v2。不会应用任何计划。",
        )

        def worker():
            try:
                result = run_plan_prompt_comparison()
                text = format_prompt_comparison_result(result)
            except Exception as error:
                text = f"！ Prompt 版本对比实验失败\n\n错误：{error}"

            def finish():
                self.plan_generating = False
                self._set_more_output(text)
                self._show_toast("Prompt 对比实验完成")

            self.root.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()

    def show_prompt_experiment_summary(self):
        try:
            summary = summarize_prompt_experiments(limit=20)
            text = format_prompt_experiment_summary(summary)
        except Exception as error:
            text = f"！ Prompt 实验统计报告读取失败\n\n错误：{error}"
        self._set_more_output(text)

    def run_rag_eval_lab(self):
        query = simpledialog.askstring(
            "RAG 检索质量测试",
            "请输入要测试的 RAG 查询：",
            initialvalue="双指针什么时候移动左指针",
            parent=self.root,
        )
        if not query:
            return
        self._set_loading_output(
            self.more_output,
            "正在检索本地学习资产并评估相关性。",
        )

        def worker():
            try:
                evaluation = run_rag_retrieval_quality_test(query=query, top_k=5)
                text = format_rag_eval_report(evaluation)
            except Exception as error:
                text = f"！ RAG 检索质量测试失败\n\n错误：{error}"
            self.root.after(0, lambda: self._set_more_output(text))

        threading.Thread(target=worker, daemon=True).start()

    def run_rag_ab_lab(self):
        if self.plan_generating:
            self._show_toast("AI / RAG 实验正在运行中")
            return
        self.plan_generating = True
        self.set_mode("more")
        self._set_loading_output(
            self.more_output,
            "正在运行 RAG 有无对比实验。不会应用任何计划。",
        )

        def worker():
            try:
                result = run_rag_plan_ab_experiment()
                text = format_rag_ab_experiment_result(result)
            except Exception as error:
                text = f"！ RAG 有无对比实验失败\n\n错误：{error}"

            def finish():
                self.plan_generating = False
                self._set_more_output(text)
                self._show_toast("RAG 对比实验完成")

            self.root.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()

    def show_rag_ab_summary(self):
        try:
            summary = summarize_rag_ab_experiments(limit=20)
            text = format_rag_ab_summary(summary)
        except Exception as error:
            text = f"！ RAG A/B 实验统计报告读取失败\n\n错误：{error}"
        self._set_more_output(text)

    def show_recent_rag_traces(self):
        try:
            records = get_recent_rag_traces(limit=5)
            text = format_recent_rag_traces(records)
        except Exception as error:
            text = f"！读取 RAG 证据链失败\n\n错误：{error}"
        self._set_more_output(text)

    def show_rag_trace_summary(self):
        try:
            summary = summarize_rag_traces(limit=20)
            text = format_rag_trace_summary(summary)
        except Exception as error:
            text = f"！读取 RAG 证据链统计报告失败\n\n错误：{error}"
        self._set_more_output(text)

    def show_rag_memory_quality_report(self):
        try:
            report = run_rag_memory_quality_audit()
            text = format_rag_memory_quality_report(report)
        except Exception as error:
            text = f"！RAG 个性化记忆质量报告生成失败\n\n错误：{error}"
        self._set_more_output(text)

    def run_enhanced_memory_ab_lab(self):
        if self.plan_generating:
            self._show_toast("AI / RAG 实验正在运行中")
            return
        confirmed = self._confirm(
            "增强记忆 RAG A/B 实验",
            "这会调用两次大模型 API，用于比较普通 RAG 和增强个性化记忆 RAG。\n\n实验不会应用任何计划，也不会改变默认 RAG 策略。是否继续？",
            confirm_text="继续实验",
        )
        if not confirmed:
            return
        self.plan_generating = True
        self.set_mode("more")
        self._set_loading_output(
            self.more_output,
            "正在运行增强记忆 RAG A/B 实验。\n\n不会应用任何计划，请稍候。",
        )

        def worker():
            try:
                result = run_enhanced_memory_ab_experiment()
                text = format_enhanced_memory_ab_result(result)
            except Exception as error:
                text = f"！增强记忆 RAG A/B 实验失败\n\n错误：{error}"

            def finish():
                self.plan_generating = False
                self._set_more_output(text)
                self._show_toast("增强记忆 RAG 实验完成")

            self.root.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()

    def show_enhanced_memory_summary(self):
        try:
            summary = summarize_enhanced_memory_experiments(limit=20)
            text = format_enhanced_memory_summary(summary)
        except Exception as error:
            text = f"！增强记忆 RAG 统计报告读取失败\n\n错误：{error}"
        self._set_more_output(text)

    def run_llm_experiment_batch_lab(self):
        if self.plan_generating:
            self._show_toast("LLM 实验正在运行中")
            return
        confirmed = self._confirm(
            "批量运行 LLM 实验",
            "这会调用多次大模型 API，可能产生费用。\n\n默认运行 3 次 Prompt 对比实验和 3 次 RAG A/B 实验。是否继续？",
            confirm_text="继续运行",
        )
        if not confirmed:
            return
        self.plan_generating = True
        self.set_mode("more")
        self._set_loading_output(
            self.more_output,
            "实验运行中，请稍候。\n\n本次实验不会应用任何计划，也不会修改 week_plan.json。",
        )

        def worker():
            try:
                result = run_llm_experiment_batch(prompt_runs=3, rag_runs=3)
                text = format_llm_experiment_batch_report(result)
            except Exception as error:
                text = f"！LLM 批量实验失败\n\n错误：{error}"

            def finish():
                self.plan_generating = False
                self._set_more_output(text)
                self._show_toast("LLM 批量实验已完成")

            self.root.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()

    def show_recent_llm_experiment_batch_reports(self):
        try:
            reports = load_llm_experiment_batch_reports(limit=3)
            text = format_recent_llm_experiment_batch_reports(reports)
        except Exception as error:
            text = f"！读取 LLM 综合实验报告失败\n\n错误：{error}"
        self._set_more_output(text)

    def show_recent_rag_debug(self):
        try:
            recent = get_recent_rag_debug(limit=5)
            if recent:
                text = format_recent_rag_debug(recent)
            else:
                text = format_rag_debug(load_last_rag_debug())
        except Exception as error:
            text = f"！ 读取 RAG 调试记录失败\n\n错误：{error}"
        self._set_more_output(text)

    def test_rag_by_problem_id(self):
        problem_id = simpledialog.askstring(
            "RAG 题号测试",
            "请输入要检索的力扣题号：",
            parent=self.root,
        )
        if not problem_id:
            return
        try:
            context = get_problem_rag_context(problem_id.strip(), top_k=8)
            text = format_rag_debug({
                "timestamp": "刚刚",
                "problem_id": problem_id.strip(),
                "matched_count": context.get("matched_count", 0),
                "total_candidate_count": context.get("total_candidate_count", 0),
                "documents": context.get("documents", []),
            })
        except Exception as error:
            text = f"！ RAG 检索失败\n\n错误：{error}"
        self._set_more_output(text)

    def generate_ai_hint(self, force=False):
        problem_id = self._entry_value(self.ai_problem_entry)
        language = (
            self.ai_language.get().strip()
            if hasattr(self, "ai_language")
            else "Python"
        ) or "Python"

        if not problem_id:
            self._notify(
                "还缺少题号",
                "请输入你正在做的力扣题号，例如 977。",
                kind="warning",
            )
            return

        self._set_loading_output(
            self.ai_output,
            "正在生成标准题解笔记，并保存到题库对应题目页面。",
        )
        self.ai_job_status = {
            "state": "running",
            "title": f"正在生成 {problem_id} 题解",
            "message": "结果会自动保存到题库对应题目页面。",
        }
        log_ai_task(
            "solution",
            problem_id=problem_id,
            language=language,
            status="running",
            message="开始生成题解",
        )
        self.render()

        def worker():
            try:
                solution = get_or_generate_solution(
                    problem_id,
                    language,
                    force=force,
                )
                text = format_solution(solution)
                if solution.get("cache_hit"):
                    text = "已读取题库中保存的 AI 题解。\n\n" + text
                self.ai_job_status = {
                    "state": "success",
                    "title": f"{problem_id} 题解已就绪",
                    "message": (
                        "已读取缓存。"
                        if solution.get("cache_hit")
                        else "已生成并保存到题库。"
                    ),
                }
                log_ai_task(
                    "solution",
                    problem_id=problem_id,
                    language=language,
                    status="success",
                    message=self.ai_job_status["message"],
                )
            except Exception as error:
                model_name = "未知"
                try:
                    from llm_client import LLMClient

                    model_name = LLMClient(
                        timeout=3,
                        model_env_key="LLM_MODEL_FAST"
                    ).model
                except Exception:
                    pass
                text = (
                    "！ AI 题解生成失败\n\n"
                    f"当前模型：{model_name}\n"
                    "题解生成属于长输出任务，如果只回复 OK 能成功，"
                    "这里仍可能因为模型响应慢而超时。\n\n"
                    f"错误：{error}"
                )
                self.ai_job_status = {
                    "state": "error",
                    "title": f"{problem_id} 题解生成失败",
                    "message": str(error),
                }
                log_ai_task(
                    "solution",
                    problem_id=problem_id,
                    language=language,
                    status="error",
                    message=str(error),
                )
            self.root.after(
                0,
                lambda: (
                    self.open_problem_from_ai_task(problem_id)
                    if self.ai_job_status.get("state") == "success"
                    else (
                        self.set_mode("ai"),
                        self._set_ai_output(text),
                    )
                ),
            )

        threading.Thread(target=worker, daemon=True).start()

    def generate_solution_for_problem(
        self,
        problem_id,
        language="Python",
        force=False,
    ):
        problem_id = str(problem_id or "").strip()
        if not problem_id:
            self._notify(
                "还缺少题号",
                "这道题缺少可识别的题号，暂时不能生成题解。",
                kind="warning",
            )
            return

        if problem_id in self.solution_jobs:
            self._show_toast("这道题的 AI 题解正在生成中")
            return

        cached = get_solution_note(problem_id, language)
        if cached and not force:
            self._show_toast("已读取题库中保存的 AI 题解")
            self.open_problem_from_ai_task(problem_id)
            return

        self.solution_jobs.add(problem_id)
        log_ai_task(
            "solution",
            problem_id=problem_id,
            language=language,
            status="running",
            message="开始生成题解",
        )
        self._show_toast("正在生成 AI 题解笔记...")
        if self.mode == "problem_detail":
            self.render()

        def worker():
            try:
                get_or_generate_solution(problem_id, language, force=force)

                def finish():
                    self.solution_jobs.discard(problem_id)
                    log_ai_task(
                        "solution",
                        problem_id=problem_id,
                        language=language,
                        status="success",
                        message="已生成并保存到题库",
                    )
                    self._show_toast("AI 题解已保存到题库")
                    self.open_problem_from_ai_task(problem_id)

                self.root.after(0, finish)
            except Exception as error:
                model_name = "未知"
                try:
                    from llm_client import LLMClient

                    model_name = LLMClient(
                        timeout=3,
                        model_env_key="LLM_MODEL_FAST"
                    ).model
                except Exception:
                    pass
                error_message = (
                    f"当前模型：{model_name}\n"
                    "题解生成属于长输出任务，如果只回复 OK 能成功，"
                    "这里仍可能因为模型响应慢而超时。\n\n"
                    f"错误：{error}"
                )
                self.solution_jobs.discard(problem_id)
                log_ai_task(
                    "solution",
                    problem_id=problem_id,
                    language=language,
                    status="error",
                    message=str(error),
                )
                self.root.after(
                    0,
                    lambda: (
                        self.render() if self.mode == "problem_detail" else None,
                        self._show_toast("AI 题解生成失败，可在当前题目页重试"),
                    ),
                )

        threading.Thread(target=worker, daemon=True).start()

    def generate_ai_weekly_review_output(self):
        self._set_loading_output(
            self.ai_output,
            "正在读取刷题记录、复习记录和阶段状态，生成 AI 周总结。",
        )

        def worker():
            try:
                review = generate_ai_weekly_review()
                text = (
                    format_ai_weekly_review(review)
                    if isinstance(review, dict)
                    else str(review)
                )
            except Exception as error:
                text = f"！ AI 周总结生成失败\n\n错误：{error}"
            self.root.after(0, lambda: self._set_ai_output(text))

        threading.Thread(target=worker, daemon=True).start()

    def generate_ai_plan_suggestion_output(self):
        self._set_loading_output(
            self.ai_output,
            "正在分析最近提交、提示使用和复习掌握情况，生成计划建议。",
        )

        def worker():
            try:
                plan = generate_ai_next_week_plan()
                text = (
                    format_ai_next_week_plan(plan)
                    if isinstance(plan, dict)
                    else str(plan)
                )
            except Exception as error:
                text = f"！ AI 计划建议生成失败\n\n错误：{error}"
            self.root.after(0, lambda: self._set_ai_output(text))

        threading.Thread(target=worker, daemon=True).start()

    def run_data_validation(self):
        try:
            text = run_all_validations()
        except Exception as error:
            text = f"！ 数据校验失败\n\n错误：{error}"
        self._set_more_output(text)

    def show_public_config_status(self):
        app_settings = _load_json_file(
            APP_SETTINGS_PATH,
            {"developer_mode": False, "show_llm_lab": False},
        )
        leetcode_config = _load_json_file(APP_DIR / "config" / "leetcode_config.json", {})
        local_config = _load_json_file(APP_DIR / "config" / "local_model_config.json", {})
        local_embedding = local_config.get("local_embedding", {})
        fallback = local_config.get("fallback", {})
        username_configured = bool(leetcode_config.get("leetcode_username"))

        text = (
            "===== 当前配置状态 =====\n\n"
            f"开发者模式：{'开启' if app_settings.get('developer_mode') else '关闭'}\n"
            f"LLM Lab 显示：{'开启' if _show_llm_lab() else '关闭'}\n"
            f"力扣用户名：{'已配置' if username_configured else '未配置'}\n"
            f"自动同步：{'开启' if leetcode_config.get('auto_sync_on_start') else '关闭'}\n"
            f"本地 Embedding：{'启用' if local_embedding.get('enabled') else '未启用'}\n"
            f"云端失败本地兜底：{'开启' if fallback.get('cloud_embedding_fallback_to_local') else '关闭'}\n\n"
            "说明：公开展示版本默认隐藏 LLM Lab。需要实验入口时，请修改 config/app_settings.json。"
        )
        self._set_more_output(text)

    def show_public_sync_status(self):
        try:
            overview = get_sync_overview()
            text = format_sync_brief(overview)
        except Exception as error:
            text = f"同步状态读取失败。\n\n错误：{error}"
        self._set_more_output(text)

    def open_data_directory(self):
        data_dir = APP_DIR / "data"
        try:
            os.startfile(data_dir)
            self._show_toast("已打开数据目录")
            text = f"已打开数据目录：\n{data_dir}"
        except Exception as error:
            text = f"无法打开数据目录。\n\n路径：{data_dir}\n错误：{error}"
        self._set_more_output(text)

    def show_about_leetcoach(self):
        self._set_more_output(
            "===== 关于 LeetCoach =====\n\n"
            "LeetCoach 是一个个人算法学习管家。\n"
            "它帮助你管理今日任务、学习计划、题库资产、AI 题解笔记和力扣同步记录。\n\n"
            "推荐运行方式：python coach_app.py\n"
            "备用命令行入口：python main.py\n\n"
            "公开版本默认隐藏 LLM Lab、PromptOps、RAG 实验和 Agent 调试入口。"
        )

    def show_current_plan_info(self):
        try:
            text = format_current_plan(get_plan_management_data())
        except Exception as error:
            text = f"！ 读取当前计划失败\n\n错误：{error}"
        self._set_more_output(text)

    def show_plan_backups(self):
        try:
            text = format_plan_backups(get_plan_management_data().get("backups", []))
        except Exception as error:
            text = f"！ 读取计划备份失败\n\n错误：{error}"
        self._set_more_output(text)

    def show_plan_archives(self):
        try:
            text = format_plan_archives(get_plan_management_data().get("archives", []))
        except Exception as error:
            text = f"！ 读取计划归档失败\n\n错误：{error}"
        self._set_more_output(text)

    def _start_completion(self, task, circle):
        task_id = task.get("task_id")
        if self.busy_task_id or task.get("completed"):
            return

        task_to_complete = dict(task)
        if task.get("kind") == "review":
            mastery_result = self._ask_review_mastery(task)
            if mastery_result is None:
                return
            task_to_complete["review_mastery"] = mastery_result
        elif (
            task.get("kind") == "milestone"
            and task.get("task_type") == "review_day"
        ):
            review_results = self._ask_review_day_mastery(task)
            if review_results is None:
                return
            task_to_complete["review_results"] = review_results
        elif (
            task.get("kind") == "milestone"
            and task.get("task_type") == "summary"
        ):
            pass

        self.busy_task_id = task_id
        circle.itemconfigure("circle", fill=ACCENT, outline=ACCENT)
        circle.create_text(
            14,
            14,
            text="✓",
            fill="white",
            font=("Microsoft YaHei UI", 11, "bold"),
        )
        self._completion_feedback()
        self.root.after(320, lambda: self._commit_completion(task_to_complete))

    def _ask_review_mastery(self, task):
        dialog = tk.Toplevel(self.root)
        dialog.title("复习结果")
        dialog.configure(bg=BACKGROUND)
        dialog.resizable(False, False)
        dialog.transient(self.root)

        result = {"value": None}
        problem_id = task.get("problem_id", "")
        title = task.get("title", "该题")

        tk.Label(
            dialog,
            text=f"{problem_id} {title}",
            bg=BACKGROUND,
            fg=TEXT,
            font=("Microsoft YaHei UI", 12, "bold"),
        ).pack(padx=28, pady=(22, 6))
        tk.Label(
            dialog,
            text="这次复习做到什么程度？",
            bg=BACKGROUND,
            fg=TEXT_SECONDARY,
            font=("Microsoft YaHei UI", 10),
        ).pack(padx=28, pady=(0, 16))

        def choose(value):
            result["value"] = value
            dialog.destroy()

        options = [
            ("独立写出", "independent", SUCCESS),
            ("看提示写出", "assisted", WARNING),
            ("仍未掌握", "not_mastered", "#8A8A8A"),
        ]
        for label, value, color in options:
            tk.Button(
                dialog,
                text=label,
                command=lambda selected=value: choose(selected),
                bg=color,
                activebackground=color,
                fg="white",
                activeforeground="white",
                relief="flat",
                width=22,
                pady=8,
                font=("Microsoft YaHei UI", 10, "bold"),
                cursor="hand2",
            ).pack(padx=28, pady=4)

        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
        dialog.update_idletasks()
        x = self.root.winfo_rootx() + (
            self.root.winfo_width() - dialog.winfo_reqwidth()
        ) // 2
        y = self.root.winfo_rooty() + (
            self.root.winfo_height() - dialog.winfo_reqheight()
        ) // 2
        dialog.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        dialog.grab_set()
        self.root.wait_window(dialog)
        return result["value"]

    def _ask_review_day_mastery(self, task):
        problem_ids = task.get("review_problems", [])
        if not problem_ids:
            return {}

        dialog = tk.Toplevel(self.root)
        dialog.title("本周核心题复习验收")
        dialog.configure(bg=BACKGROUND)
        dialog.resizable(False, False)
        dialog.transient(self.root)

        result = {"value": None}
        labels = {
            "请选择": "",
            "独立写出": "independent",
            "看提示写出": "assisted",
            "仍未掌握": "not_mastered",
        }
        selections = {}

        tk.Label(
            dialog,
            text="本周核心题复习验收",
            bg=BACKGROUND,
            fg=TEXT,
            font=("Microsoft YaHei UI", 13, "bold"),
        ).pack(padx=28, pady=(22, 5))
        tk.Label(
            dialog,
            text="为每道题选择这次复习的真实结果。",
            bg=BACKGROUND,
            fg=TEXT_SECONDARY,
            font=("Microsoft YaHei UI", 9),
        ).pack(padx=28, pady=(0, 14))

        form = tk.Frame(dialog, bg=BACKGROUND)
        form.pack(fill="x", padx=28)
        for row_index, problem_id in enumerate(problem_ids):
            tk.Label(
                form,
                text=f"题目 {problem_id}",
                bg=BACKGROUND,
                fg=TEXT,
                font=("Microsoft YaHei UI", 10),
                width=14,
                anchor="w",
            ).grid(row=row_index, column=0, sticky="w", pady=5)
            variable = tk.StringVar(value="请选择")
            selections[problem_id] = variable
            menu = tk.OptionMenu(form, variable, *labels.keys())
            menu.configure(
                width=14,
                bg=SOFT_FILL,
                activebackground="#EDEFF3",
                relief="flat",
                font=("Microsoft YaHei UI", 9),
            )
            menu.grid(row=row_index, column=1, padx=(12, 0), pady=5)

        error_label = tk.Label(
            dialog,
            text="",
            bg=BACKGROUND,
            fg=ACCENT,
            font=("Microsoft YaHei UI", 9),
        )
        error_label.pack(padx=28, pady=(8, 0))

        def confirm():
            values = {
                problem_id: labels[variable.get()]
                for problem_id, variable in selections.items()
            }
            if not all(values.values()):
                error_label.configure(text="请为每道题选择复习结果。")
                return
            result["value"] = values
            dialog.destroy()

        actions = tk.Frame(dialog, bg=BACKGROUND)
        actions.pack(padx=28, pady=(12, 22))
        self._secondary_button(actions, "取消", dialog.destroy).pack(side="left")
        self._primary_button(actions, "确认完成复习", confirm).pack(side="left", padx=(10, 0))

        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
        dialog.update_idletasks()
        x = self.root.winfo_rootx() + (
            self.root.winfo_width() - dialog.winfo_reqwidth()
        ) // 2
        y = self.root.winfo_rooty() + (
            self.root.winfo_height() - dialog.winfo_reqheight()
        ) // 2
        dialog.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        dialog.grab_set()
        self.root.wait_window(dialog)
        return result["value"]

    def _commit_completion(self, task):
        try:
            result = complete_task(task, self.data.get("plan"))
            if not result.get("success"):
                raise RuntimeError(result.get("message", "任务完成失败"))
            self._show_toast(result.get("message", "任务已完成"))
            self.busy_task_id = None
            self.refresh()
            self._check_plan_generation_async("task_completed")
        except Exception as error:
            self._notify(
                "任务完成失败",
                f"错误：{error}",
                kind="error",
            )
            self.busy_task_id = None
            self.refresh()

    def _completion_feedback(self):
        try:
            import winsound

            winsound.MessageBeep(winsound.MB_OK)
        except Exception:
            try:
                self.root.bell()
            except Exception:
                pass

        start_x = self.root.winfo_x()
        start_y = self.root.winfo_y()
        offsets = (0, -7, 7, -5, 5, -2, 2, 0)
        for index, offset in enumerate(offsets):
            self.root.after(
                index * 24,
                lambda value=offset: self.root.geometry(f"+{start_x + value}+{start_y}"),
            )

    def _show_toast(self, message, kind=None):
        if kind is None:
            text = str(message)
            if any(word in text for word in ("失败", "错误", "无法")):
                kind = "error"
            elif any(word in text for word in ("正在", "请稍候")):
                kind = "loading"
            else:
                kind = "success"
        icon, _bg, color, _border = self._status_style(kind)
        toast_bg = {
            "success": "#202124",
            "loading": "#1F2937",
            "error": "#3A1716",
            "warning": "#3A2A11",
            "info": "#1F2937",
        }.get(kind, "#202124")
        self.toast.configure(
            text=f"{icon}  {message}",
            bg=toast_bg,
            fg="white",
            highlightbackground=color,
        )
        self.toast.place(relx=0.5, rely=0.94, anchor="center")
        if self.toast_after_id:
            self.root.after_cancel(self.toast_after_id)
        delay = 2600 if kind == "error" else 1800
        self.toast_after_id = self.root.after(delay, self.toast.place_forget)

    def sync_now(self, interactive=True):
        self._show_toast("正在同步力扣记录...")
        if self.mode == "sync":
            self._set_loading_output(
                self.sync_output,
                "正在读取浏览器同步组件和最近提交记录，请稍候。",
            )

        def worker():
            try:
                report = sync_leetcode_submissions(interactive=interactive)
                success = bool(report.get("success"))
                imported = report.get("imported", 0)
                if success and report.get("from_cache"):
                    message = "已读取最近同步缓存，暂无新记录"
                elif success:
                    message = f"同步完成，新增 {imported} 条记录"
                else:
                    message = report.get("message", "同步失败，继续使用本地数据")
                if success:
                    agent_result = run_silent_agent(trigger="sync")
                    if agent_result.get("generated"):
                        message += "；计划草案已准备好"
            except Exception:
                message = "同步失败，继续使用本地数据"

            self.root.after(0, lambda: self._finish_sync(message))

        threading.Thread(target=worker, daemon=True).start()

    def _finish_sync(self, message):
        self._show_toast(message)
        self.refresh()
        if self.mode == "sync":
            self._set_sync_output(format_sync_brief(get_sync_overview()))

    def _check_plan_generation_async(self, trigger):
        def worker():
            try:
                result = run_silent_agent(trigger=trigger)
            except Exception:
                return

            if result.get("generated"):
                self.root.after(
                    0,
                    lambda: (
                        self._show_toast(result.get("message", "计划草案已准备好")),
                        self.refresh(),
                    ),
                )

        threading.Thread(target=worker, daemon=True).start()

    def _auto_sync_on_start(self):
        try:
            start_local_push_server()
        except Exception:
            pass

    def _render_error(self, detail):
        for widget in self.body.winfo_children():
            widget.destroy()
        error_container = tk.Frame(self.body, bg=PAGE_BG)
        error_container.pack(fill="both", expand=True, padx=40, pady=40)
        card = self._create_card(
            error_container,
            accent=True,
        )
        card.pack(fill="x")
        self._render_state_block(
            card,
            "暂时无法读取任务数据",
            f"请检查 data/ 和 config/ 中的 JSON 文件。\n{detail}",
            kind="error",
            action_text="重试",
            action=self.refresh,
        )


def main():
    _set_windows_app_id()
    root = tk.Tk()
    TaskBoardApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
