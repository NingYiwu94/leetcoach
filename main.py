import sys
from pathlib import Path


SRC_DIR = Path(__file__).resolve().parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from core.planner import show_today_tasks
from core.recorder import (
    get_all_records,
    format_records,
    get_mistake_stats,
    format_mistake_stats,
    generate_week_summary
)
from core.reviewer import get_today_reviews, format_today_reviews, mark_review_done
from ai.ai_solution import generate_and_save_solution, format_solution
from app.dashboard import get_dashboard_data, format_dashboard
from app.daily_check import get_daily_check_data, format_daily_check
from core.next_plan import generate_next_week_plan_draft
from agent.agent_state import analyze_learning_state, format_agent_state
from agent.agent_runtime import run_agent, format_agent_report
from agent.agent_memory import analyze_trend
from tools.data_validator import run_all_validations
from ai.ai_weekly_review import (
    generate_ai_weekly_review,
    format_ai_weekly_review
)
from ai.ai_plan_adjuster import (
    generate_ai_next_week_plan,
    format_ai_next_week_plan
)
from sync.leetcode_sync import (
    format_recent_synced_records,
    format_sync_report,
    get_recent_synced_records,
    sync_leetcode_submissions
)


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def show_today_task():
    show_today_tasks()

    reviews = get_today_reviews()
    print("\n===== 今日复习 =====\n")
    print(format_today_reviews(reviews))


def show_dashboard():
    data = get_dashboard_data()
    print(format_dashboard(data))


def show_agent_plan():
    data = run_agent()
    print(format_agent_report(data))


def show_daily_check():
    data = get_daily_check_data()
    print(format_daily_check(data))


def show_history():
    print("\n===== 历史刷题记录 =====\n")

    records = get_all_records()
    print(format_records(records))


def complete_review():
    problem_id = input("请输入要标记完成的题号：\n> ").strip()

    if mark_review_done(problem_id):
        print("本轮复习完成，下一轮复习已自动安排")
    else:
        print("没有找到该题的待完成复习记录")


def sync_leetcode_records():
    report = sync_leetcode_submissions()
    print(format_sync_report(report))


def show_recent_synced_records():
    records = get_recent_synced_records()
    print(format_recent_synced_records(records))


def show_mistake_stats():
    stats = get_mistake_stats()
    print(format_mistake_stats(stats))


def show_week_summary():
    print(generate_week_summary())


def show_next_week_plan():
    print(generate_next_week_plan_draft())


def show_agent_state():
    data = analyze_learning_state()
    print(format_agent_state(data))


def show_agent_trend():
    print(analyze_trend())


def show_data_validation():
    print(run_all_validations())


def show_ai_weekly_review():
    review = generate_ai_weekly_review()
    print(format_ai_weekly_review(review))


def show_ai_next_week_plan():
    plan = generate_ai_next_week_plan()
    print(format_ai_next_week_plan(plan))


def ask_ai_hint():
    print("\n===== AI 题解笔记 =====\n")

    problem_id = input("请输入题号：\n> ").strip()
    language = input("请选择语言（Python/C++，默认 Python）：\n> ").strip()
    if not language:
        language = "Python"

    try:
        solution = generate_and_save_solution(problem_id, language)
        print()
        print(format_solution(solution))
    except Exception:
        print("AI 题解生成失败，请检查 API 配置或网络")


def show_today_overview():
    show_agent_plan()
    print()
    show_dashboard()
    print()
    show_daily_check()


def data_sync_menu():
    while True:
        print("\n===== 数据同步 =====")
        print("1. 同步力扣记录")
        print("2. 查看最近同步记录")
        print("3. 标记复习完成")
        print("0. 返回主菜单")

        choice = input("请选择功能：\n> ").strip()

        if choice == "1":
            sync_leetcode_records()
        elif choice == "2":
            show_recent_synced_records()
        elif choice == "3":
            complete_review()
        elif choice == "0":
            break
        else:
            print("无效选择，请重新输入。")


def review_menu():
    while True:
        print("\n===== 查看复盘 =====")
        print("1. 查看历史记录")
        print("2. 查看错因统计")
        print("3. 规则版本周总结")
        print("4. 规则版下一周计划")
        print("5. Agent 状态分析")
        print("6. Agent 趋势分析")
        print("0. 返回主菜单")

        choice = input("请选择功能：\n> ").strip()

        if choice == "1":
            show_history()
        elif choice == "2":
            show_mistake_stats()
        elif choice == "3":
            show_week_summary()
        elif choice == "4":
            show_next_week_plan()
        elif choice == "5":
            show_agent_state()
        elif choice == "6":
            show_agent_trend()
        elif choice == "0":
            break
        else:
            print("无效选择，请重新输入。")


def ai_assistant_menu():
    while True:
        print("\n===== AI 助手 =====")
        print("1. AI 题解笔记")
        print("2. AI 周总结")
        print("3. AI 下周计划建议")
        print("0. 返回主菜单")

        choice = input("请选择功能：\n> ").strip()

        if choice == "1":
            ask_ai_hint()
        elif choice == "2":
            show_ai_weekly_review()
        elif choice == "3":
            show_ai_next_week_plan()
        elif choice == "0":
            break
        else:
            print("无效选择，请重新输入。")


def system_tools_menu():
    while True:
        print("\n===== 系统工具 =====")
        print("1. 数据校验")
        print("0. 返回主菜单")

        choice = input("请选择功能：\n> ").strip()

        if choice == "1":
            show_data_validation()
        elif choice == "0":
            break
        else:
            print("无效选择，请重新输入。")


def main():
    while True:
        print("\n==============================")
        print("欢迎使用 LeetCoach")
        print("==============================")
        print("1. 今天该做什么")
        print("2. 数据同步")
        print("3. 查看复盘")
        print("4. AI 助手")
        print("5. 系统工具")
        print("0. 退出")

        choice = input("请选择功能：\n> ").strip()

        if choice == "1":
            show_today_overview()
        elif choice == "2":
            data_sync_menu()
        elif choice == "3":
            review_menu()
        elif choice == "4":
            ai_assistant_menu()
        elif choice == "5":
            system_tools_menu()
        elif choice == "0":
            print("已退出 LeetCoach。")
            break
        else:
            print("无效选择，请重新输入。")


if __name__ == "__main__":
    main()
