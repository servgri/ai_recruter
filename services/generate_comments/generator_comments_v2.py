import os
import re
import glob
from dataclasses import dataclass
from typing import Optional, Tuple, List, Dict, Any

from openai import OpenAI


DEFAULT_MODEL_FALLBACK = "moonshotai/Kimi-K2-Instruct-0905"


@dataclass
class GenerationConfig:
    model_id: str = ""
    temperature: float = 0.2
    top_p: float = 0.9
    max_tokens: int = 1200

    target_min_chars: int = 700
    target_max_chars: int = 10000
    enforce_char_limit: bool = False

    def resolved_model_id(self) -> str:
        return (self.model_id or os.getenv("HF_MODEL") or DEFAULT_MODEL_FALLBACK).strip()


class ReportCommentGenerator:
    """
    Генерирует комментарии для HR и кандидата из готовых txt-отчётов.
    Работает через OpenAI-совместимый API (Hugging Face Router и т.п.).
    При недоступности LLM возвращает исходный отчёт.
    """

    HR_PROMPT_RU = """\
Ты — помощник HR. Твоя задача: по входному отчёту (ниже) написать короткое резюме для HR.

Требования:
- Пиши по-русски, деловой тон.
- Объем: {min_chars}-{max_chars} символов.
- Сфокусируйся на: сильные стороны, слабые стороны/риски, что стоит перепроверить, итоговая оценка (если есть).
- Если в отчёте есть признаки расхождений/ошибок расчётов или предупреждения — упомяни их и что проверить.
- Не используй внутренние термины про модель/эмбеддинги/формулы. Только наблюдения из отчёта.
- Не добавляй фактов, которых нет в отчёте.
- Вывод без заголовков типа "Резюме:" — сразу текст. Можно использовать короткие маркированные строки.
- Не перечисляй все вопросы подряд; выдели самое важное.

ОТЧЁТ:
{report_text}
"""

    CANDIDATE_PROMPT_RU = """\
Ты — помощник, который формирует фидбек кандидату по результатам проверки.

Требования:
- Пиши по-русски, дружелюбно-нейтральный тон.
- Объем: {min_chars}-{max_chars} символов.
- Объясни: что было учтено в оценке (в терминах критериев/ожиданий), что чаще всего не хватило,
  и 3-5 конкретных направлений как улучшить ответы в следующий раз (без "внутренней кухни").
- Укажи итоговую оценку работы, если она есть.
- Не упоминай внутренние механики и не говори про эталоны/модели/формулы.
- Не добавляй фактов, которых нет в отчёте.
- Вывод без заголовков типа "Фидбек:" — сразу текст.

ОТЧЁТ:
{report_text}
"""

    def __init__(
        self,
        config: Optional[GenerationConfig] = None,
        hf_token: Optional[str] = None,
        check_dir: Optional[str] = None,
        reports_dir: Optional[str] = None,
        out_dir: Optional[str] = None,
        debug_errors: bool = False,
        base_url: Optional[str] = None,
    ):
        self.config = config or GenerationConfig()
        self.hf_token = (hf_token if hf_token is not None else os.getenv("HF_TOKEN", "")).strip() or None
        self.base_url = (base_url or os.getenv("HF_BASE_URL") or "https://router.huggingface.co/v1").strip()
        self.client: Optional[OpenAI] = (
            OpenAI(base_url=self.base_url, api_key=self.hf_token) if self.hf_token else None
        )
        self.check_dir = check_dir or os.path.join("check_eval", "check_files")
        self.reports_dir = reports_dir or os.path.join(self.check_dir, "reports")
        self.out_dir = out_dir or os.path.join("generate_comments", "comments")
        self.debug_errors = bool(debug_errors)
        self._last_error: Optional[str] = None

    def generate_hr_summary(self, hr_report_text: str, prompt_template: Optional[str] = None) -> Tuple[str, bool]:
        report_original = hr_report_text or ""
        report_for_prompt = self._sanitize_for_prompt(report_original)
        tmpl = prompt_template or self.HR_PROMPT_RU
        prompt = tmpl.format(
            min_chars=self.config.target_min_chars,
            max_chars=self.config.target_max_chars,
            report_text=report_for_prompt,
        )
        text, generated = self._call_llm_or_fallback(prompt, fallback_text=report_original)
        if generated:
            if self.config.enforce_char_limit:
                return self._postprocess_to_length(text), True
            return text.strip(), True
        return (report_original.strip() or "Отчёт пустой или не найден."), False

    def generate_candidate_summary(
        self, candidate_report_text: str, prompt_template: Optional[str] = None
    ) -> Tuple[str, bool]:
        report_original = candidate_report_text or ""
        report_for_prompt = self._sanitize_for_prompt(report_original)
        tmpl = prompt_template or self.CANDIDATE_PROMPT_RU
        prompt = tmpl.format(
            min_chars=self.config.target_min_chars,
            max_chars=self.config.target_max_chars,
            report_text=report_for_prompt,
        )
        text, generated = self._call_llm_or_fallback(prompt, fallback_text=report_original)
        if generated:
            if self.config.enforce_char_limit:
                return self._postprocess_to_length(text), True
            return text.strip(), True
        return (report_original.strip() or "Отчёт пустой или не найден."), False

    def _call_llm_or_fallback(self, prompt: str, fallback_text: str) -> Tuple[str, bool]:
        self._last_error = None
        if not self.client or not self.hf_token:
            self._last_error = "HF_TOKEN is missing; returning original report."
            return fallback_text, False
        try:
            completion = self.client.chat.completions.create(
                model=self.config.resolved_model_id(),
                messages=[{"role": "user", "content": prompt}],
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                top_p=self.config.top_p,
            )
            content = (completion.choices[0].message.content or "").strip()
            if not content:
                self._last_error = "Empty LLM response; returning original report."
                return fallback_text, False
            return content, True
        except Exception as e:
            msg = str(e)
            self._last_error = f"LLM call failed: {type(e).__name__}: {msg}"
            if self.debug_errors:
                print(self._last_error)
            return fallback_text, False

    @staticmethod
    def _sanitize_for_prompt(text: str) -> str:
        t = (text or "").strip()
        if not t:
            return "Отчёт пустой или не найден. Сформируй общий комментарий по результатам без деталей."
        t = t.replace("\r\n", "\n")
        t = re.sub(r"[ \t]+", " ", t)
        t = re.sub(r"\n{4,}", "\n\n\n", t)
        if len(t) > 12000:
            t = t[:12000] + "\n...\n(отчёт обрезан по длине)"
        return t

    def _postprocess_to_length(self, text: str) -> str:
        t = (text or "").strip()
        if not t:
            return "Не удалось сформировать комментарий: недостаточно данных в отчёте."
        t = re.sub(r"\n{3,}", "\n\n", t).strip()
        return t
