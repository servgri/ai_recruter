import json
import os
import sys
from typing import Any, Dict, Optional

from services.report_text_service import build_hr_report_text


def generate_overall_impression(
    document: Dict[str, Any],
    eval_v6_results: Optional[Any] = None,
    doc_id: Optional[int] = None,
) -> str:
    """
    Build HR report text from document and eval_v6, then generate short HR summary (overall impression).

    Args:
        document: DB document dict (task_1..task_4, filename, etc.).
        eval_v6_results: Parsed eval_v6_results (dict) or JSON string. If None, uses document.get("eval_v6_results").
        doc_id: Document ID for report header.

    Returns:
        Generated overall impression text (for overall_impression field).
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

    hr_report_text = build_hr_report_text(document, eval_v6_results, doc_id)

    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _root not in sys.path:
        sys.path.insert(0, _root)
    from microsevice_eval.generate_comments.generator_comments_v2 import ReportCommentGenerator

    generator = ReportCommentGenerator()
    summary, generated = generator.generate_hr_summary(hr_report_text)
    return summary.strip() if summary else ""
