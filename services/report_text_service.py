"""
Builds HR report text from document and eval_v6_results.
Used for display, PDF export, and overall impression generation.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional


def build_hr_report_text(
    document: Dict[str, Any],
    eval_v6_results: Optional[Dict[str, Any]] = None,
    doc_id: Optional[int] = None,
) -> str:
    """
    Build HR report text (plain text) from document and eval_v6 results.

    Args:
        document: DB document dict (filename, task_1..task_4, etc.).
        eval_v6_results: Parsed eval_v6_results JSON (with 'results' list).
        doc_id: Document ID for header.

    Returns:
        Full HR report as plain text.
    """
    lines: List[str] = []
    lines.append("=== ОТЧЁТ ДЛЯ HR ===")
    lines.append(f"Дата анализа: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    doc_id = doc_id or document.get("id")
    filename = document.get("filename") or document.get("full_filename") or "—"
    file_type = document.get("type") or "—"
    lines.append(f"Кандидат: {doc_id} (файл: {filename})")
    lines.append(f"Тип файла: {file_type}")
    lines.append("")

    if not eval_v6_results or not isinstance(eval_v6_results.get("results"), list):
        lines.append("Нет данных оценки (eval_v6).")
        return "\n".join(lines)

    results = eval_v6_results["results"]
    warnings = eval_v6_results.get("warnings") or []
    if warnings:
        lines.append("=== ПРЕДУПРЕЖДЕНИЯ ===")
        for w in warnings:
            lines.append(f"• {w}")
        lines.append("")

    counted_scores: List[float] = []

    for q_row in results:
        qid = str(q_row.get("Номер вопроса", ""))
        qid_int = int(qid) if qid.isdigit() else None
        is_counted = (qid_int is not None) and (qid_int <= 3)
        header = f"Вопрос {qid}" + (
            "" if is_counted else " (справочно, не учитывается в итоговой оценке)"
        )
        lines.append("=" * 50)
        lines.append(header)

        chosen = q_row.get("Эталон выбран")
        if chosen:
            etalon_type = "HR" if chosen == "hr" else ("AI" if chosen == "ai" else "неизвестно")
            cos_hr = q_row.get("Cosine HR")
            cos_ai = q_row.get("Cosine AI")
            sim = cos_hr if chosen == "hr" else cos_ai
            if sim is not None:
                lines.append(f"Семантическое сходство: выбран {etalon_type}-эталон ({sim:.4f})")
            else:
                lines.append(f"Семантическое сходство: выбран {etalon_type}-эталон")
        else:
            lines.append("Семантическое сходство: не рассчитано (нет эталона)")

        criteria_pack = q_row.get("Criteria pack")
        criteria_details = (criteria_pack or {}).get("criteria_details") or []
        passed = [c.get("name", "") for c in criteria_details if c.get("passed")]
        failed = [c.get("name", "") for c in criteria_details if not c.get("passed")]
        lines.append(f"Критерии: выполнено {len(passed)} из {len(criteria_details)}")
        if passed:
            s = "  - Выполненные: " + ", ".join(passed[:3])
            if len(passed) > 3:
                s += f" (+{len(passed) - 3} других)"
            lines.append(s)
        if failed:
            s = "  - Не выполненные: " + ", ".join(failed[:3])
            if len(failed) > 3:
                s += f" (+{len(failed) - 3} других)"
            lines.append(s)

        lines.append("Как рассчитана оценка:")
        cos_base = q_row.get("Cosine (1..10 base)")
        if cos_base is not None:
            lines.append(f"  - Семантическое сходство с эталоном (1..10): {float(cos_base):.1f}")
        else:
            lines.append("  - Семантическое сходство (1..10): не рассчитано")
        crit_1_10 = q_row.get("Criteria (1..10)")
        if crit_1_10 is not None:
            lines.append(f"  - Выполнение критериев (1..10): {float(crit_1_10):.1f}")
        else:
            lines.append("  - Выполнение критериев (1..10): не применялось/нет данных")
        combined = q_row.get("Combined (0.7*cosine + 0.3*criteria) before penalties")
        if combined is not None:
            lines.append(f"  - Взвешенный балл до штрафов (70% cosine + 30% criteria): {float(combined):.2f}")
        else:
            lines.append("  - Взвешенный балл до штрафов: нет данных")
        len_pack = q_row.get("Length vs AI etalon") or {}
        delta = float(len_pack.get("delta_score") or 0.0)
        if delta < 0:
            lines.append(f"  - Штраф за длину (короче AI-эталона): {delta:.2f}")
        elif delta > 0:
            lines.append(f"  - Бонус за длину (длиннее AI-эталона): +{delta:.2f}")
        else:
            lines.append("  - Поправка за длину: 0.00")
        final = q_row.get("Оценка (final)")
        if final is not None:
            lines.append(f"  - Итоговая оценка: {float(final):.1f}")
            if is_counted:
                counted_scores.append(float(final))
        else:
            lines.append("  - Итоговая оценка: нет данных")

        lines.append("")
        lines.append("Результат системы:")
        lines.append(str(q_row.get("Комментарий", "")))
        lines.append("")

    if counted_scores:
        overall = round(sum(counted_scores) / len(counted_scores), 2)
        lines.append("=" * 50)
        lines.append(f"Итоговая оценка работы: {overall:.2f} (среднее по вопросам 1–3)")
    else:
        lines.append("=" * 50)
        lines.append("Итоговая оценка работы: нет данных (не удалось посчитать среднее по вопросам 1–3)")

    return "\n".join(lines)
