import json
import os
from typing import Any, Dict, Optional

from services.report_text_service import build_organizer_report


def generate_overall_impression(
    document: Dict[str, Any],
    eval_v6_results: Optional[Any] = None,
    doc_id: Optional[int] = None,
) -> str:
    """
    Build detailed organizer report (criteria, scores, recommendation) for overall_impression.
    No LLM: rule-based text from build_organizer_report.
    """
    doc_id = doc_id or document.get("id")
    if eval_v6_results is None:
        raw = document.get("eval_v6_results")
        if isinstance(raw, str) and raw.strip():
            try:
                eval_v6_results = json.loads(raw)
            except json.JSONDecodeError:
                eval_v6_results = None
        else:
            eval_v6_results = None
    elif isinstance(eval_v6_results, str):
        try:
            eval_v6_results = json.loads(eval_v6_results) if eval_v6_results.strip() else None
        except json.JSONDecodeError:
            eval_v6_results = None

    return build_organizer_report(document, eval_v6_results, doc_id)
