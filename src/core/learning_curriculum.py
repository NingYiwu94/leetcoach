from datetime import date


ROADMAP = [
    {
        "id": "array",
        "title": "数组与指针控制",
        "goal": "掌握数组边界、二分、双指针、滑动窗口和矩阵模拟。",
        "problem_ids": ["704", "27", "977", "209", "59"],
        "next_topic": "链表与指针重连"
    },
    {
        "id": "linked_list",
        "title": "链表与指针重连",
        "goal": "掌握 dummy 节点、反转、节点重连和链表快慢指针。",
        "problem_ids": ["203", "206", "24", "19", "160", "142"],
        "next_topic": "哈希表与快速查找"
    },
    {
        "id": "hash",
        "title": "哈希表与快速查找",
        "goal": "掌握集合、映射、计数和空间换时间。",
        "problem_ids": ["242", "349", "202", "1", "454", "383"],
        "next_topic": "字符串基础"
    },
    {
        "id": "string",
        "title": "字符串基础",
        "goal": "掌握字符串原地处理、反转、匹配和边界控制。",
        "problem_ids": ["344", "541", "151", "28"],
        "next_topic": "栈与队列"
    },
    {
        "id": "stack_queue",
        "title": "栈与队列",
        "goal": "掌握栈、队列、括号匹配、单调结构和表达式求值。",
        "problem_ids": ["232", "225", "20", "1047", "150", "239"],
        "next_topic": "二叉树"
    },
    {
        "id": "binary_tree",
        "title": "二叉树基础",
        "goal": "掌握递归、迭代遍历、层序遍历和树的基本性质。",
        "problem_ids": ["144", "145", "94", "102", "226", "101"],
        "next_topic": "回溯"
    }
]


def clean_problem_id(value):
    return str(value or "").strip()


def build_slug_index(problem_bank):
    index = {}
    for problem_id, problem in problem_bank.items():
        if not isinstance(problem, dict):
            continue
        slug = str(
            problem.get("slug") or problem.get("title_slug") or ""
        ).strip()
        if slug:
            index[slug] = str(problem_id)
    return index


def canonical_problem_id(record, problem_bank):
    problem_id = clean_problem_id(record.get("problem_id"))
    if problem_id in problem_bank:
        return problem_id

    slug = str(record.get("title_slug") or problem_id).strip()
    return build_slug_index(problem_bank).get(slug, problem_id)


def summarize_problem_history(records, problem_bank):
    history = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        problem_id = canonical_problem_id(record, problem_bank)
        if not problem_id:
            continue
        item = history.setdefault(problem_id, {
            "attempts": 0,
            "ac_count": 0,
            "assisted_count": 0,
            "failed_count": 0,
            "last_status": "未知"
        })
        status = str(record.get("status", "未知")).replace(" ", "")
        item["attempts"] += 1
        item["last_status"] = status
        if status == "AC":
            item["ac_count"] += 1
        elif status == "看提示后AC":
            item["assisted_count"] += 1
        elif status == "未通过":
            item["failed_count"] += 1
    return history


def select_current_topic(records, problem_bank, review_mastery=None):
    history = summarize_problem_history(records, problem_bank)
    review_mastery = (
        review_mastery
        if isinstance(review_mastery, dict)
        else {}
    )
    completed = {
        problem_id
        for problem_id, item in history.items()
        if item["ac_count"] or item["assisted_count"]
    }

    selected = ROADMAP[-1]
    for topic in ROADMAP:
        core_ids = topic["problem_ids"]
        blocked_ids = {
            problem_id
            for problem_id in core_ids
            if review_mastery.get(problem_id, {}).get(
                "latest_result"
            ) in {"not_mastered", "assisted"}
        }
        completed_count = sum(
            1
            for problem_id in core_ids
            if problem_id in completed and problem_id not in blocked_ids
        )
        completion_rate = completed_count / len(core_ids)
        if completion_rate < 0.7 or blocked_ids:
            selected = topic
            break

    return {
        **selected,
        "history": history,
        "review_mastery": review_mastery,
        "completed_problem_ids": completed,
        "completed_in_topic": [
            problem_id
            for problem_id in selected["problem_ids"]
            if problem_id in completed
        ],
        "remaining_in_topic": [
            problem_id
            for problem_id in selected["problem_ids"]
            if problem_id not in completed
        ]
    }


def _execution_steps(task_type):
    if task_type == "review":
        return [
            "不看旧代码，先口述核心思路和关键指针含义。",
            "独立重写并提交，失败后只定位错误类型。",
            "通过后写下可复用模板和一个易错边界。"
        ]
    if task_type == "summary":
        return [
            "整理本周题目的共同结构和差异。",
            "把核心模板压缩成不超过 10 行的伪代码。",
            "标记每题为独立写出、看提示写出或只能看懂。"
        ]
    return [
        "先独立思考 10 分钟，画出变量或指针变化。",
        "完成第一版并提交，记录第一个真实卡点。",
        "查看必要提示后关掉题解重写一次。",
        "用 3 至 5 句话总结模板、边界和复杂度。"
    ]


def _mastery_requirement(problem, is_first_new, is_last_new):
    difficulty = str(problem.get("difficulty", "Easy"))
    if is_last_new and difficulty == "Medium":
        return "第一遍理解即可"
    if difficulty == "Medium":
        return "看提示能写出"
    return "必须独立写出"


def build_plan_scaffold(
    records,
    problem_bank,
    learner_profile,
    reviews=None
):
    from core.learning_analyzer import summarize_review_mastery

    review_mastery = summarize_review_mastery(reviews)
    topic = select_current_topic(
        records,
        problem_bank,
        review_mastery
    )
    history = topic["history"]
    completed = topic["completed_in_topic"]
    remaining = topic["remaining_in_topic"]

    review_ids = []
    mastery_signal_ids = [
        problem_id
        for problem_id in topic["problem_ids"]
        if review_mastery.get(problem_id, {}).get("latest_result")
        in {"not_mastered", "assisted"}
    ]
    mastery_signal_ids.sort(
        key=lambda problem_id: (
            0
            if review_mastery[problem_id]["latest_result"]
            == "not_mastered"
            else 1,
            topic["problem_ids"].index(problem_id)
        )
    )
    review_ids.extend(mastery_signal_ids[:2])
    risky_completed = [
        problem_id
        for problem_id in completed
        if (
            history.get(problem_id, {}).get("assisted_count", 0)
            or history.get(problem_id, {}).get("failed_count", 0)
        )
    ]
    if risky_completed:
        risky_completed.sort(
            key=lambda problem_id: (
                -history.get(problem_id, {}).get("assisted_count", 0),
                -history.get(problem_id, {}).get("failed_count", 0)
            )
        )
        if risky_completed[0] not in review_ids:
            review_ids.append(risky_completed[0])
    elif completed:
        if completed[-1] not in review_ids:
            review_ids.append(completed[-1])

    review_ids = review_ids[:2]
    selected_new = remaining[:max(0, 5 - len(review_ids))]
    learning_days = []
    for review_id in review_ids:
        latest_result = review_mastery.get(
            review_id, {}
        ).get("latest_result")
        learning_days.append({
            "problem_id": review_id,
            "task_type": "review",
            "mastery_requirement": (
                "先做到不看完整题解写出"
                if latest_result == "not_mastered"
                else "必须独立写出"
            )
        })
    for index, problem_id in enumerate(selected_new):
        problem = problem_bank.get(problem_id, {})
        learning_days.append({
            "problem_id": problem_id,
            "task_type": "new",
            "mastery_requirement": _mastery_requirement(
                problem,
                is_first_new=index == 0,
                is_last_new=index == len(selected_new) - 1
            )
        })
    learning_days = learning_days[:5]

    days = {}
    previous_skill = ""
    for day_index in range(1, 6):
        if day_index <= len(learning_days):
            assignment = learning_days[day_index - 1]
            problem_id = assignment["problem_id"]
            problem = problem_bank.get(problem_id, {})
            skill = str(problem.get("skill", "")).strip()
            template = str(problem.get("template", "")).strip()
            relation_previous = (
                f"承接前一天的“{previous_skill}”，继续增加指针操作复杂度。"
                if previous_skill
                else f"从“{skill or topic['title']}”的基础动作开始。"
            )
            next_problem_id = (
                learning_days[day_index]["problem_id"]
                if day_index < len(learning_days)
                else ""
            )
            next_problem = problem_bank.get(next_problem_id, {})
            next_skill = (
                str(next_problem.get("skill", "")).strip()
                if isinstance(next_problem, dict)
                else ""
            )
            relation_next = (
                f"为下一步“{next_skill}”建立基础。"
                if next_skill
                else f"为后续“{topic['next_topic']}”做准备。"
            )
            days[str(day_index)] = {
                "date_note": f"Day {day_index}",
                "problems": [problem_id],
                "topic": skill or topic["title"],
                "goal": f"掌握{skill or problem.get('title', '本题核心方法')}",
                "reason": (
                    f"{relation_previous}{relation_next}"
                    f"本题应沉淀为“{template or skill}”模板。"
                ),
                "task_type": assignment["task_type"],
                "mastery_requirement": assignment["mastery_requirement"],
                "execution_steps": _execution_steps(
                    assignment["task_type"]
                ),
                "summary_focus": (
                    template or "记录核心变量、边界条件和复杂度"
                ),
                "relation_previous": relation_previous,
                "relation_next": relation_next
            }
            previous_skill = skill
        else:
            days[str(day_index)] = {
                "date_note": f"Day {day_index}",
                "problems": [],
                "topic": "弹性补做",
                "goal": "补齐本周未完成任务，不额外堆题",
                "reason": "新手阶段保留消化时间比增加题量更重要。",
                "task_type": "buffer",
                "mastery_requirement": "完成遗留任务",
                "execution_steps": [
                    "优先补做本周未完成题。",
                    "若已完成，则重写最不熟的一题。",
                    "更新每道题的掌握状态。"
                ],
                "summary_focus": "明确仍不能独立写出的步骤",
                "relation_previous": "承接本周已有任务。",
                "relation_next": "为周末复习清理遗留问题。"
            }

    core_review_ids = [
        item["problem_id"] for item in learning_days[:3]
    ]
    days["6"] = {
        "date_note": "Day 6",
        "problems": [],
        "review_problems": core_review_ids,
        "topic": "本周核心题复习",
        "goal": "不看题解重做本周最核心的三道题",
        "reason": "检查是否从“看懂”转化为“能独立写出”。",
        "task_type": "review_day",
        "mastery_requirement": "核心题至少两道能独立写出",
        "execution_steps": _execution_steps("review"),
        "summary_focus": "比较三道题的指针角色、循环不变量和边界",
        "relation_previous": "复用前五天形成的模板。",
        "relation_next": "为周总结提供真实验收结果。"
    }
    days["7"] = {
        "date_note": "Day 7",
        "problems": [],
        "topic": "周总结",
        "goal": f"形成“{topic['title']}”知识地图",
        "reason": "把零散题目整理为可迁移的模板，再决定是否进入下一专题。",
        "task_type": "summary",
        "mastery_requirement": "完成模板、错因和掌握度记录",
        "execution_steps": _execution_steps("summary"),
        "summary_focus": "题型识别、模板、易错点、复杂度和下周入口",
        "relation_previous": "汇总本周所有练习结果。",
        "relation_next": f"达到验收标准后进入“{topic['next_topic']}”。"
    }

    return {
        "curriculum_topic_id": topic["id"],
        "weekly_theme": topic["title"],
        "weekly_goal": topic["goal"],
        "days": days,
        "must_master": [
            item["problem_id"]
            for item in learning_days
            if item["mastery_requirement"] == "必须独立写出"
        ],
        "guided_mastery": [
            item["problem_id"]
            for item in learning_days
            if item["mastery_requirement"] == "看提示能写出"
        ],
        "understand_only": [
            item["problem_id"]
            for item in learning_days
            if item["mastery_requirement"] == "第一遍理解即可"
        ],
        "minimum_acceptance": (
            "必须掌握题可以在 25 分钟内独立写出；"
            "本周至少 70% 核心题达到“独立写出”；"
            "能够口述本周模板、边界条件和时间复杂度。"
        ),
        "transition_logic": (
            f"达到最低验收标准后进入“{topic['next_topic']}”；"
            "否则下一周前两天继续复习本专题，再减少新题量。"
        ),
        "completed_in_topic": list(topic["completed_in_topic"]),
        "remaining_in_topic": list(topic["remaining_in_topic"]),
        "selection_reason": (
            f"同步记录显示已完成本专题的 "
            f"{'、'.join(topic['completed_in_topic']) or '0 道基础题'}；"
            f"下一步按教学顺序学习 "
            f"{'、'.join(topic['remaining_in_topic']) or '本专题复习'}。"
            "本周保持单一专题，避免在不同数据结构之间频繁切换。"
            + (
                "最近复习反馈显示仍有未掌握或依赖提示的题，"
                "已减少新题并优先安排重做。"
                if mastery_signal_ids
                else ""
            )
        ),
        "mastery_review_ids": mastery_signal_ids[:2],
        "priority_review_ids": review_ids,
        "adaptive_reason": (
            "最近复习仍未掌握或需要提示，保持当前专题并减少新题。"
            if mastery_signal_ids
            else "当前没有新的复习掌握度阻塞信号。"
        ),
        "generated_on": str(date.today()),
        "learner_level": learner_profile.get("level", "beginner")
    }
