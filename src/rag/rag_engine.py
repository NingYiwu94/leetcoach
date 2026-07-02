import json
import hashlib
import math
import os
import re
from datetime import datetime
from pathlib import Path


from app_paths import BASE_DIR
DATA_DIR = BASE_DIR / "data"

PROBLEM_BANK_PATH = DATA_DIR / "problem_bank.json"
RECORDS_PATH = DATA_DIR / "records.json"
REVIEWS_PATH = DATA_DIR / "reviews.json"
PROBLEM_NOTES_PATH = DATA_DIR / "problem_notes.json"
AI_SOLUTION_NOTES_PATH = DATA_DIR / "ai_solution_notes.json"
PLAN_TASK_STATE_PATH = DATA_DIR / "plan_task_state.json"
AGENT_MEMORY_PATH = DATA_DIR / "agent_memory.json"
SILENT_AGENT_MEMORY_PATH = DATA_DIR / "silent_agent_memory.json"
RAG_DEBUG_PATH = DATA_DIR / "rag_debug.json"
RAG_DEBUG_HISTORY_PATH = DATA_DIR / "rag_debug_history.json"
RAG_EMBEDDINGS_PATH = DATA_DIR / "rag_embeddings.json"
ENHANCED_PERSONALIZED_MEMORY_PATH = DATA_DIR / "rag_personalized_memory_enhanced.json"

SOURCE_WEIGHTS = {
    "records": 1.35,
    "problem_notes": 1.30,
    "reviews": 1.25,
    "ai_solution_notes": 1.15,
    "stage_summary": 1.10,
    "agent_memory": 1.08,
    "silent_agent_memory": 1.03,
    "personalized_memory": 1.22,
    "problem_bank": 0.82,
}

DOC_TYPE_ALIASES = {
    "records": "record",
    "record": "record",
    "reviews": "review",
    "review": "review",
    "problem_notes": "problem_note",
    "problem_note": "problem_note",
    "ai_solution_notes": "ai_solution_note",
    "ai_solution": "ai_solution_note",
    "ai_solution_note": "ai_solution_note",
    "stage_summary": "stage_summary",
    "agent_memory": "agent_memory",
    "silent_agent_memory": "silent_agent_memory",
    "personalized_memory": "personalized_memory",
    "mistake": "mistake",
    "ai_note": "ai_note",
    "problem_bank": "problem_bank",
    "topic_catalog": "topic_catalog",
    "curriculum": "curriculum",
}

PERSONALIZED_DOC_TYPES = {
    "record",
    "review",
    "mistake",
    "problem_note",
    "ai_solution_note",
    "ai_note",
    "stage_summary",
    "agent_memory",
    "silent_agent_memory",
    "personalized_memory",
}

BACKGROUND_DOC_TYPES = {
    "problem_bank",
    "topic_catalog",
    "curriculum",
}


def canonical_doc_type(value):
    return DOC_TYPE_ALIASES.get(str(value or "").strip(), str(value or "").strip() or "unknown")


def document_doc_type(document):
    if not isinstance(document, dict):
        return "unknown"
    metadata = document.get("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}
    return canonical_doc_type(
        document.get("doc_type")
        or document.get("source")
        or metadata.get("doc_type", "")
    )


def is_personalized_doc(document):
    return document_doc_type(document) in PERSONALIZED_DOC_TYPES


def is_background_doc(document):
    return document_doc_type(document) in BACKGROUND_DOC_TYPES


def evidence_group(document):
    if is_personalized_doc(document):
        return "personalized"
    if is_background_doc(document):
        return "background"
    return "unknown"


def load_json(path, default):
    if not path.exists():
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return default


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    with open(temporary_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    temporary_path.replace(path)


def clean_problem_id(problem_id):
    value = str(problem_id or "")
    for prefix in ("题号：", "题号:", "题号", "棰樺彿锛?", "棰樺彿:", "棰樺彿"):
        value = value.replace(prefix, "")
    return value.strip()


def as_list(value):
    if isinstance(value, list):
        return value
    if value in (None, ""):
        return []
    return [value]


def short_text(value, limit=260):
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


def tokenize(text):
    text = str(text or "").lower()
    tokens = set(re.findall(r"[a-z0-9_+-]+", text))
    chinese_chunks = re.findall(r"[\u4e00-\u9fff]{2,}", text)
    for chunk in chinese_chunks:
        tokens.add(chunk)
        for size in (2, 3, 4):
            for index in range(0, max(0, len(chunk) - size + 1)):
                tokens.add(chunk[index:index + size])
    return tokens


def make_document(source, title, content, problem_id="", metadata=None):
    problem_id = clean_problem_id(problem_id)
    title = str(title or "").strip()
    content = str(content or "").strip()
    metadata = metadata if isinstance(metadata, dict) else {}
    document_id = make_document_id(source, title, content, problem_id)
    doc_type = canonical_doc_type(source)
    document = {
        "id": document_id,
        "source": source,
        "doc_type": doc_type,
        "title": title,
        "content": content,
        "problem_id": problem_id,
        "metadata": metadata,
        "tokens": list(tokenize(" ".join([problem_id, title, content]))),
    }
    document["evidence_group"] = evidence_group(document)
    return document


def make_document_id(source, title, content, problem_id=""):
    raw = "|".join([
        str(source or ""),
        clean_problem_id(problem_id),
        str(title or ""),
        str(content or ""),
    ])
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]
    return f"{source}:{clean_problem_id(problem_id) or 'global'}:{digest}"


def content_hash(text):
    return hashlib.sha256(str(text or "").encode("utf-8")).hexdigest()


def _problem_bank_documents(problem_bank):
    documents = []
    if not isinstance(problem_bank, dict):
        return documents

    for problem_id, problem in problem_bank.items():
        if not isinstance(problem, dict):
            continue
        title = str(problem.get("title", "")).strip()
        topics = "、".join(str(item) for item in as_list(problem.get("topics")))
        key_points = "、".join(str(item) for item in as_list(problem.get("key_points")))
        content = "\n".join([
            f"题号：{problem_id}",
            f"题目：{title}",
            f"难度：{problem.get('difficulty', '')}",
            f"专题：{topics}",
            f"技巧：{problem.get('skill', '')}",
            f"模板：{problem.get('template', '')}",
            f"关键点：{key_points}",
        ])
        documents.append(
            make_document(
                "problem_bank",
                f"{problem_id} {title}",
                content,
                problem_id=problem_id,
                metadata={
                    "difficulty": problem.get("difficulty", ""),
                    "topics": as_list(problem.get("topics")),
                    "slug": problem.get("slug", ""),
                },
            )
        )
    return documents


def _record_documents(records):
    documents = []
    if not isinstance(records, list):
        return documents

    for record in records:
        if not isinstance(record, dict):
            continue
        problem_id = clean_problem_id(record.get("problem_id"))
        content = "\n".join([
            f"日期：{record.get('date', '')} {record.get('time', '')}",
            f"状态：{record.get('status', '')}",
            f"难度感受：{record.get('difficulty_feeling', '')}",
            f"错因：{record.get('mistake_type', '未分类')}",
            f"问题/收获：{record.get('mistake_note', '')}",
            f"来源：{record.get('source', 'manual')}",
        ])
        documents.append(
            make_document(
                "records",
                f"{problem_id} 刷题记录",
                content,
                problem_id=problem_id,
                metadata={
                    "date": record.get("date", ""),
                    "status": record.get("status", ""),
                    "source": record.get("source", "manual"),
                },
            )
        )
    return documents


def _review_documents(reviews):
    documents = []
    if not isinstance(reviews, list):
        return documents

    for review in reviews:
        if not isinstance(review, dict):
            continue
        problem_id = clean_problem_id(review.get("problem_id"))
        content = "\n".join([
            f"下次复习：{review.get('next_review_date', '')}",
            f"是否完成：{review.get('done', False)}",
            f"原因：{review.get('reason', '')}",
        ])
        documents.append(
            make_document(
                "reviews",
                f"{problem_id} 复习记录",
                content,
                problem_id=problem_id,
                metadata={
                    "next_review_date": review.get("next_review_date", ""),
                    "done": bool(review.get("done")),
                },
            )
        )
    return documents


def _problem_note_documents(problem_notes):
    documents = []
    if not isinstance(problem_notes, dict):
        return documents

    for problem_id, note in problem_notes.items():
        if not isinstance(note, dict):
            continue
        content = "\n".join([
            f"掌握程度：{note.get('mastery', 'unknown')}",
            f"我的笔记：{note.get('note', '')}",
            f"更新时间：{note.get('updated_at', '')}",
        ])
        documents.append(
            make_document(
                "problem_notes",
                f"{problem_id} 我的笔记",
                content,
                problem_id=problem_id,
                metadata={
                    "mastery": note.get("mastery", "unknown"),
                    "updated_at": note.get("updated_at", ""),
                },
            )
        )
    return documents


def _solution_note_documents(solution_notes):
    documents = []
    if not isinstance(solution_notes, list):
        return documents

    for note in solution_notes:
        if not isinstance(note, dict):
            continue
        problem_id = clean_problem_id(note.get("problem_id"))
        mistakes = []
        for item in as_list(note.get("common_mistakes")):
            if isinstance(item, dict):
                mistakes.append(
                    f"{item.get('point', '')}：{item.get('explanation', '')}"
                )
            else:
                mistakes.append(str(item))
        content = "\n".join([
            f"题解语言：{note.get('language', '')}",
            f"思路：{note.get('idea', '')}",
            f"易错点：{'；'.join(mistakes)}",
            f"复杂度：{note.get('time_complexity', '')}",
        ])
        documents.append(
            make_document(
                "ai_solution_notes",
                f"{problem_id} AI 题解笔记",
                content,
                problem_id=problem_id,
                metadata={
                    "language": note.get("language", ""),
                    "generated_at": note.get("generated_at", ""),
                },
            )
        )
    return documents


def _stage_summary_documents(plan_task_state):
    documents = []
    if not isinstance(plan_task_state, list):
        return documents

    for item in plan_task_state:
        if not isinstance(item, dict):
            continue
        summary = item.get("stage_summary")
        if not isinstance(summary, dict):
            continue
        week = summary.get("week", item.get("plan_week", ""))
        content = "\n".join([
            f"阶段：Week {week}",
            f"生成时间：{summary.get('generated_at', item.get('completed_at', ''))}",
            f"完成情况：{summary.get('completion_summary', '')}",
            f"主要薄弱点：{summary.get('main_weakness', '')}",
            f"复盘建议：{summary.get('review_suggestion', '')}",
        ])
        documents.append(
            make_document(
                "stage_summary",
                f"Week {week} 阶段总结",
                content,
                problem_id="",
                metadata={
                    "week": week,
                    "task_id": item.get("task_id", ""),
                    "completed_at": item.get("completed_at", ""),
                },
            )
        )
    return documents


def _agent_memory_documents(agent_memory, source="agent_memory"):
    documents = []
    if not isinstance(agent_memory, list):
        return documents

    for item in agent_memory:
        if not isinstance(item, dict):
            continue
        action_plan = "；".join(str(part) for part in as_list(item.get("action_plan")))
        content = "\n".join([
            f"日期：{item.get('date', '')}",
            f"阶段：{item.get('stage', '')}",
            f"进度状态：{item.get('progress_status', item.get('status', ''))}",
            f"主要问题：{item.get('main_problem', '')}",
            f"行动：{action_plan or item.get('action', '')}",
            f"信息：{item.get('message', '')}",
            f"错误：{item.get('error_message', '')}",
        ])
        documents.append(
            make_document(
                source,
                f"{item.get('date', '')} Agent 记忆",
                content,
                problem_id="",
                metadata={
                    "date": item.get("date", ""),
                    "stage": item.get("stage", ""),
                    "status": item.get("status", ""),
                    "trigger": item.get("trigger", ""),
                },
            )
        )
    return documents


def _enhanced_personalized_memory_documents(items):
    documents = []
    if not isinstance(items, list):
        return documents

    for item in items:
        if not isinstance(item, dict):
            continue
        content = str(item.get("text") or item.get("content") or "").strip()
        if not content:
            continue
        metadata = item.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}
        metadata = {
            **metadata,
            "source_doc_id": item.get("source_doc_id", ""),
            "original_doc_type": metadata.get("source_doc_type", ""),
            "generated_by": metadata.get("generated_by", "rule_based_memory_rewrite"),
        }
        document = make_document(
            "personalized_memory",
            item.get("title", "") or "增强个性化记忆",
            content,
            problem_id=item.get("problem_id", ""),
            metadata=metadata,
        )
        if item.get("doc_id"):
            document["id"] = str(item.get("doc_id"))
        document["source_doc_id"] = item.get("source_doc_id", "")
        document["tokens"] = list(tokenize(" ".join([
            document.get("problem_id", ""),
            document.get("title", ""),
            document.get("content", ""),
        ])))
        document["evidence_group"] = "personalized"
        documents.append(document)
    return documents


def build_rag_documents(use_enhanced_memory=False):
    documents = []
    documents.extend(_problem_bank_documents(load_json(PROBLEM_BANK_PATH, {})))
    documents.extend(_record_documents(load_json(RECORDS_PATH, [])))
    documents.extend(_review_documents(load_json(REVIEWS_PATH, [])))
    documents.extend(_problem_note_documents(load_json(PROBLEM_NOTES_PATH, {})))
    documents.extend(_solution_note_documents(load_json(AI_SOLUTION_NOTES_PATH, [])))
    documents.extend(_stage_summary_documents(load_json(PLAN_TASK_STATE_PATH, [])))
    documents.extend(_agent_memory_documents(load_json(AGENT_MEMORY_PATH, []), "agent_memory"))
    documents.extend(
        _agent_memory_documents(
            load_json(SILENT_AGENT_MEMORY_PATH, []),
            "silent_agent_memory",
        )
    )
    if use_enhanced_memory:
        documents.extend(
            _enhanced_personalized_memory_documents(
                load_json(ENHANCED_PERSONALIZED_MEMORY_PATH, [])
            )
        )
    return documents


def score_document(document, query_tokens, problem_id=""):
    doc_problem_id = clean_problem_id(document.get("problem_id"))
    source = str(document.get("source", "")).strip()
    source_weight = SOURCE_WEIGHTS.get(source, 1.0)

    score = 0.0
    if problem_id and doc_problem_id == clean_problem_id(problem_id):
        score += 120

    doc_tokens = set(document.get("tokens", []))
    matched = query_tokens & doc_tokens
    score += len(matched) * 8

    content = " ".join([
        str(document.get("title", "")),
        str(document.get("content", "")),
    ]).lower()
    for token in query_tokens:
        if len(token) >= 2 and token in content:
            score += 2

    if problem_id and clean_problem_id(problem_id) in content:
        score += 12

    return round(score * source_weight, 2)


def embedding_text(document):
    metadata = document.get("metadata", {})
    metadata_text = ""
    if isinstance(metadata, dict) and metadata:
        metadata_text = " ".join(f"{key}:{value}" for key, value in metadata.items())
    return short_text(
        "\n".join([
            f"来源：{document.get('source', '')}",
            f"题号：{document.get('problem_id', '')}",
            f"标题：{document.get('title', '')}",
            f"元数据：{metadata_text}",
            f"内容：{document.get('content', '')}",
        ]),
        1400,
    )


def load_embedding_cache():
    cache = load_json(RAG_EMBEDDINGS_PATH, {})
    if not isinstance(cache, dict):
        cache = {}
    cache.setdefault("items", {})
    return cache


def save_embedding_cache(cache):
    if not isinstance(cache, dict):
        return
    cache["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_json(RAG_EMBEDDINGS_PATH, cache)


def cosine_similarity(left, right):
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = 0.0
    left_norm = 0.0
    right_norm = 0.0
    for a, b in zip(left, right):
        try:
            a = float(a)
            b = float(b)
        except (TypeError, ValueError):
            return 0.0
        dot += a * b
        left_norm += a * a
        right_norm += b * b
    if left_norm <= 0 or right_norm <= 0:
        return 0.0
    return dot / (math.sqrt(left_norm) * math.sqrt(right_norm))


def ensure_document_embeddings(documents, client, rebuild=False):
    cache = load_embedding_cache()
    items = cache.setdefault("items", {})
    model = client.model

    missing_documents = []
    for document in documents:
        text = embedding_text(document)
        document["embedding_text"] = text
        document["content_hash"] = content_hash(text)
        cached = items.get(document.get("id", ""))
        if (
            not rebuild
            and isinstance(cached, dict)
            and cached.get("model") == model
            and cached.get("content_hash") == document["content_hash"]
            and isinstance(cached.get("embedding"), list)
            and cached.get("embedding")
        ):
            continue
        missing_documents.append(document)

    batch_size = 10
    for start in range(0, len(missing_documents), batch_size):
        batch = missing_documents[start:start + batch_size]
        vectors = client.embed([document["embedding_text"] for document in batch])
        for document, vector in zip(batch, vectors):
            items[document["id"]] = {
                "model": model,
                "content_hash": document["content_hash"],
                "source": document.get("source", ""),
                "problem_id": document.get("problem_id", ""),
                "title": document.get("title", ""),
                "embedding": vector,
                "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }

    save_embedding_cache(cache)
    return cache


def _select_diverse_documents(scored_documents, top_k):
    selected = []
    source_counts = {}
    problem_counts = {}
    for score, document in scored_documents:
        source = document.get("source", "")
        problem_id = document.get("problem_id", "")

        source_count = source_counts.get(source, 0)
        problem_count = problem_counts.get(problem_id, 0)
        adjusted_score = score - source_count * 8 - max(0, problem_count - 1) * 5

        item = {key: value for key, value in document.items() if key != "tokens"}
        item["score"] = score
        item["adjusted_score"] = round(adjusted_score, 2)
        selected.append(item)
        source_counts[source] = source_count + 1
        problem_counts[problem_id] = problem_count + 1

        selected.sort(key=lambda doc: doc.get("adjusted_score", 0), reverse=True)
        selected = selected[:top_k]
    return selected


def _scored_item(score, document, extra=None):
    item = {
        key: value for key, value in document.items()
        if key not in {"tokens", "embedding_text"}
    }
    item["doc_type"] = document_doc_type(item)
    item["evidence_group"] = evidence_group(item)
    item["score"] = score
    if isinstance(extra, dict):
        item.update(extra)
    return item


def _passes_plan_selection_limits(document, selected_ids, problem_counts):
    doc_id = str(document.get("id", "") or "")
    if doc_id and doc_id in selected_ids:
        return False
    problem_id = str(document.get("problem_id", "") or "").strip()
    if problem_id and problem_counts.get(problem_id, 0) >= 2:
        return False
    return True


def _add_plan_selection(document, selected, selected_ids, problem_counts):
    selected.append(document)
    doc_id = str(document.get("id", "") or "")
    if doc_id:
        selected_ids.add(doc_id)
    problem_id = str(document.get("problem_id", "") or "").strip()
    if problem_id:
        problem_counts[problem_id] = problem_counts.get(problem_id, 0) + 1


def select_rag_context_for_plan(
    retrieved_docs,
    total_top_k=10,
    personalized_limit=7,
    background_limit=3,
):
    """Prefer learner-specific memory while keeping a small amount of background."""
    try:
        total_top_k = max(1, int(total_top_k))
        personalized_limit = max(0, int(personalized_limit))
        background_limit = max(0, int(background_limit))
    except (TypeError, ValueError):
        total_top_k = 10
        personalized_limit = 7
        background_limit = 3

    candidates = []
    for raw in retrieved_docs or []:
        score = 0
        document = None
        extra = {}
        if isinstance(raw, tuple):
            score = raw[0] if raw else 0
            document = raw[1] if len(raw) > 1 else None
            if len(raw) > 2:
                extra["similarity"] = round(float(raw[2]), 4)
        elif isinstance(raw, dict):
            document = raw
            score = raw.get("score", 0)
        if not isinstance(document, dict):
            continue
        try:
            score = float(score)
        except (TypeError, ValueError):
            score = 0.0
        item = _scored_item(score, document, extra=extra)
        group = evidence_group(item)
        if group == "personalized":
            # A small lift keeps slightly lower-scored personal memory visible.
            item["adjusted_score"] = round(score + 18, 4)
        elif group == "background":
            item["adjusted_score"] = round(score - 8, 4)
        else:
            item["adjusted_score"] = round(score, 4)
        candidates.append(item)

    candidates.sort(key=lambda doc: doc.get("adjusted_score", 0), reverse=True)
    personalized = [doc for doc in candidates if is_personalized_doc(doc)]
    background = [doc for doc in candidates if is_background_doc(doc)]
    unknown = [
        doc for doc in candidates
        if not is_personalized_doc(doc) and not is_background_doc(doc)
    ]

    selected = []
    selected_ids = set()
    problem_counts = {}

    for group_docs, limit in (
        (personalized, personalized_limit),
        (background, background_limit),
    ):
        for document in group_docs:
            if len(selected) >= total_top_k or limit <= 0:
                break
            if not _passes_plan_selection_limits(document, selected_ids, problem_counts):
                continue
            _add_plan_selection(document, selected, selected_ids, problem_counts)
            limit -= 1

    # If learner-specific memory is sparse, let background or unknown evidence fill
    # the remaining room, but keep the overall context compact.
    for document in background + unknown:
        if len(selected) >= total_top_k:
            break
        if not _passes_plan_selection_limits(document, selected_ids, problem_counts):
            continue
        _add_plan_selection(document, selected, selected_ids, problem_counts)

    selected.sort(key=lambda doc: doc.get("adjusted_score", 0), reverse=True)
    return selected[:total_top_k]


def _trim_context_documents(documents, max_chars):
    trimmed = []
    used_chars = 0
    for document in documents:
        title = str(document.get("title", ""))
        content = str(document.get("content", ""))
        remaining = max_chars - used_chars - len(title) - 40
        if remaining <= 80:
            break
        item = dict(document)
        item["content"] = short_text(content, min(remaining, 520))
        used_chars += len(title) + len(item["content"]) + 40
        trimmed.append(item)
    return trimmed


def retrieve_rag_context(
    query,
    problem_id="",
    top_k=6,
    max_chars=1800,
    selection_strategy="default",
    use_enhanced_memory=False,
):
    try:
        top_k = max(1, int(top_k))
    except (TypeError, ValueError):
        top_k = 6
    try:
        max_chars = max(400, int(max_chars))
    except (TypeError, ValueError):
        max_chars = 1800

    documents = build_rag_documents(use_enhanced_memory=use_enhanced_memory)
    query_text = " ".join([str(query or ""), clean_problem_id(problem_id)])
    query_tokens = tokenize(query_text)

    scored = []
    for document in documents:
        score = score_document(document, query_tokens, problem_id=problem_id)
        if score > 0:
            scored.append((score, document))
    scored.sort(key=lambda item: item[0], reverse=True)

    if selection_strategy == "plan":
        selected = select_rag_context_for_plan(
            scored,
            total_top_k=top_k,
            personalized_limit=min(7, top_k),
            background_limit=min(3, top_k),
        )
    else:
        selected = _select_diverse_documents(scored, top_k=top_k)
    selected = _trim_context_documents(selected, max_chars=max_chars)
    context_text = format_rag_context(selected)

    debug_data = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "query": str(query or ""),
        "problem_id": clean_problem_id(problem_id),
        "top_k": top_k,
        "max_chars": max_chars,
        "selection_strategy": selection_strategy,
        "use_enhanced_memory": bool(use_enhanced_memory),
        "matched_count": len(selected),
        "total_candidate_count": len(scored),
        "documents": selected,
    }
    save_rag_debug(debug_data)
    return {
        "documents": selected,
        "context_text": context_text,
        "matched_count": len(selected),
        "total_candidate_count": len(scored),
        "mode": "keyword",
        "use_enhanced_memory": bool(use_enhanced_memory),
        "enhanced_memory_available": ENHANCED_PERSONALIZED_MEMORY_PATH.exists(),
    }


def retrieve_embedding_rag_context(
    query,
    problem_id="",
    top_k=6,
    max_chars=1800,
    rebuild=False,
    selection_strategy="default",
    use_enhanced_memory=False,
):
    try:
        from embedding_client import EmbeddingClient

        top_k = max(1, int(top_k))
        max_chars = max(400, int(max_chars))
        problem_id = clean_problem_id(problem_id)
        query_text = " ".join([str(query or ""), problem_id]).strip()

        documents = build_rag_documents(use_enhanced_memory=use_enhanced_memory)
        client = EmbeddingClient(timeout=45)
        cache = ensure_document_embeddings(documents, client, rebuild=rebuild)
        query_vector = client.embed(query_text)

        scored = []
        items = cache.get("items", {})
        for document in documents:
            cached = items.get(document.get("id", ""))
            if not isinstance(cached, dict):
                continue
            similarity = cosine_similarity(query_vector, cached.get("embedding", []))
            if similarity <= 0:
                continue
            source_weight = SOURCE_WEIGHTS.get(document.get("source", ""), 1.0)
            same_problem_bonus = (
                0.35
                if problem_id and clean_problem_id(document.get("problem_id")) == problem_id
                else 0.0
            )
            score = round((similarity + same_problem_bonus) * 100 * source_weight, 4)
            scored.append((score, document, similarity))

        scored.sort(key=lambda item: item[0], reverse=True)
        if selection_strategy == "plan":
            selected = select_rag_context_for_plan(
                scored,
                total_top_k=top_k,
                personalized_limit=min(7, top_k),
                background_limit=min(3, top_k),
            )
        else:
            selected = []
            for score, document, similarity in scored[:top_k]:
                item = _scored_item(
                    score,
                    document,
                    extra={"similarity": round(similarity, 4)},
                )
                selected.append(item)
        selected = _trim_context_documents(selected, max_chars=max_chars)

        context_text = format_rag_context(selected)
        debug_data = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "mode": "embedding",
            "embedding_model": client.model,
            "query": str(query or ""),
            "problem_id": problem_id,
            "top_k": top_k,
            "max_chars": max_chars,
            "selection_strategy": selection_strategy,
            "use_enhanced_memory": bool(use_enhanced_memory),
            "matched_count": len(selected),
            "total_candidate_count": len(scored),
            "documents": selected,
        }
        save_rag_debug(debug_data)
        return {
            "documents": selected,
            "context_text": context_text,
            "matched_count": len(selected),
            "total_candidate_count": len(scored),
            "mode": "embedding",
            "embedding_model": client.model,
            "use_enhanced_memory": bool(use_enhanced_memory),
            "enhanced_memory_available": ENHANCED_PERSONALIZED_MEMORY_PATH.exists(),
        }
    except Exception as error:
        fallback = retrieve_rag_context(
            query,
            problem_id=problem_id,
            top_k=top_k,
            max_chars=max_chars,
            selection_strategy=selection_strategy,
            use_enhanced_memory=use_enhanced_memory,
        )
        fallback["mode"] = "keyword_fallback"
        fallback["embedding_error"] = str(error)
        debug_data = load_last_rag_debug()
        if isinstance(debug_data, dict):
            debug_data["mode"] = "keyword_fallback"
            debug_data["embedding_error"] = str(error)
            save_rag_debug(debug_data)
        return fallback


def get_problem_rag_context(problem_id, top_k=6, max_chars=1800):
    problem_id = clean_problem_id(problem_id)
    problem_bank = load_json(PROBLEM_BANK_PATH, {})
    problem = problem_bank.get(problem_id, {}) if isinstance(problem_bank, dict) else {}
    if not isinstance(problem, dict):
        problem = {}
    query = " ".join([
        problem_id,
        str(problem.get("title", "")),
        " ".join(str(item) for item in as_list(problem.get("topics"))),
        str(problem.get("skill", "")),
        str(problem.get("template", "")),
        " ".join(str(item) for item in as_list(problem.get("key_points"))),
    ])
    rag_mode = os.getenv("LEETCOACH_RAG_MODE", "keyword").strip().lower()
    if rag_mode == "embedding":
        return retrieve_embedding_rag_context(
            query,
            problem_id=problem_id,
            top_k=top_k,
            max_chars=max_chars,
        )
    return retrieve_rag_context(
        query,
        problem_id=problem_id,
        top_k=top_k,
        max_chars=max_chars,
    )


def format_rag_context(documents):
    if not documents:
        return "暂无可用的本地学习资料。"

    lines = []
    for index, document in enumerate(documents, start=1):
        lines.append(
            f"[{index}] 来源：{document.get('source', '')} | "
            f"{document.get('title', '')}"
        )
        lines.append(short_text(document.get("content", ""), 520))
        lines.append("")
    return "\n".join(lines).strip()


def format_plan_rag_context(documents):
    if not documents:
        return "暂无可用的本地学习资料。"

    grouped = {
        "personalized": [],
        "background": [],
        "unknown": [],
    }
    for document in documents:
        if not isinstance(document, dict):
            continue
        grouped.setdefault(evidence_group(document), []).append(document)

    sections = [
        (
            "【用户个性化学习记忆】",
            grouped.get("personalized", []),
            "优先参考这些记录制定复习和新题安排。",
        ),
        (
            "【题库背景信息】",
            grouped.get("background", []),
            "仅用于理解题目专题和难度，不应替代用户历史记录。",
        ),
        (
            "【其他补充资料】",
            grouped.get("unknown", []),
            "仅在缺少明确历史证据时作为补充。",
        ),
    ]

    lines = []
    for title, items, note in sections:
        if not items:
            continue
        lines.append(title)
        lines.append(note)
        for index, document in enumerate(items, start=1):
            lines.append(
                f"[{index}] 来源：{document.get('source', '')} | "
                f"题号：{document.get('problem_id', '')} | "
                f"{document.get('title', '')}"
            )
            lines.append(short_text(document.get("content", ""), 520))
            lines.append("")
    return "\n".join(lines).strip()


def save_rag_debug(debug_data):
    try:
        save_json(RAG_DEBUG_PATH, debug_data)
        history = load_json(RAG_DEBUG_HISTORY_PATH, [])
        if not isinstance(history, list):
            history = []
        history.append(debug_data)
        save_json(RAG_DEBUG_HISTORY_PATH, history[-50:])
    except OSError:
        pass


def load_last_rag_debug():
    data = load_json(RAG_DEBUG_PATH, {})
    return data if isinstance(data, dict) else {}


def get_recent_rag_debug(limit=5):
    try:
        limit = max(1, int(limit))
    except (TypeError, ValueError):
        limit = 5
    history = load_json(RAG_DEBUG_HISTORY_PATH, [])
    if not isinstance(history, list):
        history = []
    return list(reversed(history[-limit:]))


def format_rag_debug(context):
    if not isinstance(context, dict) or not context:
        return "暂无 RAG 检索结果。"

    documents = context.get("documents", [])
    lines = [
        "===== RAG 检索结果 =====",
        "",
        f"时间：{context.get('timestamp', '未知')}",
        f"模式：{context.get('mode', 'keyword')}",
        f"Embedding 模型：{context.get('embedding_model', '未使用')}",
        f"题号：{context.get('problem_id', '') or '未指定'}",
        f"命中文档：{len(documents)} 条",
        f"候选文档：{context.get('total_candidate_count', '未知')} 条",
        "",
    ]
    if context.get("embedding_error"):
        lines.append(f"Embedding 回退原因：{context.get('embedding_error')}")
        lines.append("")
    for index, document in enumerate(documents, start=1):
        lines.append(f"{index}. {document.get('title', '')}")
        lines.append(f"   来源：{document.get('source', '')}")
        lines.append(f"   分数：{document.get('score', 0)}")
        if "similarity" in document:
            lines.append(f"   相似度：{document.get('similarity', 0)}")
        lines.append(f"   内容：{short_text(document.get('content', ''), 160)}")
        lines.append("")
    return "\n".join(lines).rstrip()


def format_recent_rag_debug(items):
    if not items:
        return "暂无 RAG 调试记录。"
    lines = ["===== 最近 RAG 检索 =====", ""]
    for index, item in enumerate(items, start=1):
        lines.append(
            f"{index}. {item.get('timestamp', '未知时间')} "
            f"题号：{item.get('problem_id', '') or '未指定'} "
            f"模式：{item.get('mode', 'keyword')} "
            f"命中：{item.get('matched_count', 0)} 条"
        )
        docs = item.get("documents", [])
        if isinstance(docs, list) and docs:
            top = docs[0]
            lines.append(
                f"   Top1：{top.get('source', '')} / {top.get('title', '')}"
            )
    return "\n".join(lines)
