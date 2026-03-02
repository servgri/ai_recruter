"""
Evaluation service using eval_v6 (embeddings + criteria).
Replaces LLM-based scoring for tasks 1-3 with AnswerEvaluator from microsevice_eval.
"""

import json
import os
from typing import Any, Dict, List, Optional

from services.config import ETALON_HR_JSON, ETALON_AI_JSON


def _load_etalon(path: str) -> List[Dict[str, Any]]:
    """Load etalon JSON from path. Return [] if file missing or invalid."""
    if not path or not os.path.isfile(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            return []
        return data
    except Exception:
        return []


def _document_to_candidate_dict(document: Dict[str, Any]) -> Dict[str, Any]:
    """Build candidate dict with tasks from document (task_1..task_4)."""
    tasks = []
    for i in range(1, 5):
        key = f"task_{i}"
        content = (document.get(key) or "").strip()
        tasks.append({"task_number": i, "content": content})
    return {"tasks": tasks}


def run_eval_v6(document: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run eval_v6 evaluation for a document.

    Args:
        document: dict with task_1..task_4 (and optionally id, filename).

    Returns:
        dict with:
          - eval_v6_results: full JSON result (for DB and report)
          - task_1_score, task_2_score, task_3_score: float or None
          - task_4_score: float or None (eval_v6 also scores task 4)
          - average_score_tasks_1_3: float or None
    """
    # Import inside function to avoid loading sentence_transformers at app startup
    from services.evaluations.eval_v6_class import AnswerEvaluator

    candidate_dict = _document_to_candidate_dict(document)
    hr_list = _load_etalon(ETALON_HR_JSON)
    ai_list = _load_etalon(ETALON_AI_JSON)

    evaluator = AnswerEvaluator()
    out = evaluator.evaluate_from_data(candidate_dict, hr_list, ai_list)

    results = out.get("results") or []
    scores_by_q: Dict[str, Optional[float]] = {}
    for row in results:
        qid = str(row.get("Номер вопроса", ""))
        scores_by_q[qid] = row.get("Оценка (final)")

    task_1_score = scores_by_q.get("1")
    task_2_score = scores_by_q.get("2")
    task_3_score = scores_by_q.get("3")
    task_4_score = scores_by_q.get("4")

    counted = [s for s in [task_1_score, task_2_score, task_3_score] if s is not None]
    average_score_tasks_1_3 = round(sum(counted) / len(counted), 2) if counted else None

    # Serialize for DB (compact)
    eval_v6_results_json = json.dumps(out, ensure_ascii=False)

    return {
        "eval_v6_results": eval_v6_results_json,
        "task_1_score": task_1_score,
        "task_2_score": task_2_score,
        "task_3_score": task_3_score,
        "task_4_score": task_4_score,
        "average_score_tasks_1_3": average_score_tasks_1_3,
    }
