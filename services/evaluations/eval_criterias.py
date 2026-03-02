from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Any, Optional

# ---------- РАСШИРЕННЫЕ КРИТЕРИИ ДЛЯ ВОПРОСА 1 (таблица clients) ----------
criteria_q1 = [
    {
        'name': 'Дополнительные поля',
        'keywords': [
            'добавить поле', 'новое поле', 'расширить',
            'date_of_birth', 'дата рождения', 'email', 'телефон', 'is_active',
            'контактная информация', 'номер телефона', 'мессенджеры',
            'статус аккаунта', 'язык интерфейса', 'флаги настроек',
            'статус', 'активен', 'active', 'удален', 'deleted',
            'время регистрации', 'timestamp', 'default',
            'phone', 'birth_date', 'gdpr_consent', 'updated_at', 'deleted_at'
        ]
    },
    {
        'name': 'Первичный/внешний ключи',
        'keywords': [
            'первичный ключ', 'primary key', 'внешний ключ', 'foreign key',
            'уникальность', 'unique', 'client_id', 'city_id',
            'not null', 'обязательный', 'constraint', 'ограничение',
            'ссылочная целостность', 'доменная целостность'
        ]
    },
    {
        'name': 'Типы данных',
        'keywords': [
            'тип данных', 'int', 'bigint', 'number', 'заменить', 'client_id',
            'вычислять через дату рождения', 'birth_date', 'возраст', 'дата рождения',
            'хранить', 'изменить', 'рекомендовать'
        ]
    },
    {
        'name': 'Нормализация',
        'keywords': [
            'нормализация', 'вынести', 'отдельная таблица', 'справочник',
            'боковая таблица', 'зависимая таблица', 'метаданные',
            'время сессии', 'дата последнего подключения',
            '3nf', 'третья нормальная форма', 'избыточно',
            'целостность', 'индекс', 'check'
        ]
    },
    {
        'name': 'Историчность',
        'keywords': [
            'историчность', 'история', 'дата изменения', 'версия',
            'valid_from', 'valid_to'
        ]
    }
]

# ---------- РАСШИРЕННЫЕ КРИТЕРИИ ДЛЯ ВОПРОСА 2 (история цен) ----------
criteria_q2 = [
    {
        'name': 'Понимание проблемы отчетности',
        'keywords': [
            'не построить отчетность', 'не хватает истории', 'цена меняется',
            'историческое хранение', 'переработать', 'дополнить боковыми таблицами',
            ' отдельную таблицу',  'создание отдельной таблицы','финансовой отчетности', 
            'нужна переработка','изменение цен', 'динамика цен', 'акции', 'скидки',
            'сезонные', 'повышение', 'понижение',
            'отчетность', 'финансовая отчетность', 'аналитика',
            'теряется история', 'только текущая цена', 'не сохраняет',
            'нельзя отследить', 'непригодна для аналитики'
        ]
    },
    {
        'name': 'Доработка под историчность',
        'keywords': [
            'историчность', 'таблица цен', 'price_history', 'scd',
            'медленно меняющиеся', 'история изменений', 'scd2', 'даты актуальности',
            'историчность цен', 'привести к scd2', 'scd4',
            'item_prices', 'cost_history',
            'valid_from', 'valid_to', 'start_date', 'end_date', 'date_from', 'date_to',
            'период действия', 'актуальна', 'текущая цена'
        ]
    },
    {
        'name': 'Нормализация и 3НФ',
        'keywords': [
            'нормализация', '3нф', '3НФ','третья нормальная форма', 'отдельная таблица',
            'звездно-снежинковая схема', 'декомпозиция', 'справочник категорий',
            'отдельная таблица поставщиков', 'вынести item_name', 'item_desc', 'item_vendor',
            'поставщик', 'vendor', 'категория', 'category',
            'валюта', 'currency', 'декомпозировать',
            'item_name', 'item_desc', 'item_vendor'
        ]
    },
    {
        'name': 'Внешние/первичные ключи',
        'keywords': [
            'внешний ключ', 'foreign key', 'первичный ключ', 'primary key',
            'ссылка', 'id валюты', 'id поставщика', 'ссылка на валюту'
        ]
    },
    {
        'name': 'Агрегаты для отчетности',
        'keywords': [
            'агрегаты', 'материализованное представление', 'витрина',
            'отдельные объекты', 'средневзвешенная', 'агрегация',
            'вычислять как средневзвешенную'
        ]
    }
]

# ---------- РАСШИРЕННЫЕ КРИТЕРИИ ДЛЯ ВОПРОСА 3 (SQL) ----------
criteria_q3 = [
    {'name': 'Алиасы атрибутов', 'keywords': ['алиас', 'псевдоним', 'ambiguous', 'отсутствие алиасов']},
    {'name': 'Избыточные атрибуты', 'keywords': ['избыточные атрибуты', 'не требуется id', 'лишние поля', 'не требуется выводить ID отдела и сумму зарплат']},
    {'name': 'Явный JOIN', 'keywords': ['явный join', 'join', 'inner join', 'вместо неявного', 'неявный джоин', 'устаревший синтаксис']},
    {'name': 'Название таблицы EMPLOYEE', 'keywords': ['employee', 'employees', 'неправильное название', 'таблица EMPLOYEE указана неверно']},
    {'name': 'Сравнение с NULL', 'keywords': ['is null', 'manager_id is null', '= null ошибка']},
    {'name': 'Подзапрос и IN', 'keywords': ['in', 'подзапрос вернет много', 'дедубликация', 'подзапрос вернет более одного значения', 'вернет несколько значений']},
    {'name': 'Регистр города', 'keywords': ['регистр', 'upper', 'lower', 'like', 'принудительно привести к верхнему регистру', 'использовать like']},
    {'name': 'HAVING', 'keywords': ['having', 'агрегация в where', 'агрегатная функция', 'sum']},
    {'name': 'Условие "более"', 'keywords': ['более', '>=', 'строго больше']},
    {'name': 'GROUP BY', 'keywords': ['group by', 'department_name', 'departments.id', 'атрибутивный состав в группировке не соответствует', 'не все поля', 'отсутствует']}
]

# ---------- РАСШИРЕННЫЕ КРИТЕРИИ ДЛЯ ВОПРОСА 4 (карандаш) ----------
criteria_q4 = [
    {
        'name': 'Скрытое условие',
        'keywords': [
            'стена', 'к стене', 'угол','в угол', 'другая комната','в другой комнате',
            'вплотную', 'препятствие', 'мебель', 'положили вплотную', 'рядом со стеной',
            'под шкаф', 'под стол', 'под комод', 'закатился', 'укатился'
            'не в той комнате', 'доступа нет', 'закрыта'
        ]
    },
    {
        'name': 'Конкретная причина',
        'keywords': [
            'нет места', 'не разбежаться', 'не приземлиться', 'блокирует',
            'проходить сквозь', 'вплотную к стене', 'стена мешает',
            'не могу прыгать', 'низкий потолок', 'нет смысла', 'незачем', 'перешагнуть'
        ]
    },
    {
        'name': 'Логическая обоснованность',
        'keywords': ['потому что', 'так как', 'следовательно', 'поэтому', 
            'в таком случае', 'из-за того что', 'тогда']
    },
    {
        'name': 'Отсутствие ошибок',
        'keywords': ['нельзя вообще', 'физически невозможно']   # инвертированный критерий
    }
]

# ---------- ДВИЖОК ОЦЕНКИ ПО КРИТЕРИЯМ ----------

@dataclass(frozen=True)
class CriterionResult:
    name: str
    matched: bool
    matched_keywords: List[str]


def _normalize_text(text: str) -> str:
    text = (text or "").lower()
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _keyword_hit(text_norm: str, kw: str) -> bool:
    kw_norm = _normalize_text(kw)
    if not kw_norm:
        return False

    # Если ключевое слово/фраза содержит пробелы или спецсимволы — ищем как подстроку
    # Иначе матчим по границам слова, чтобы "join" не ловился как часть "rejoin".
    if re.search(r"[^a-zа-я0-9_]+", kw_norm) or " " in kw_norm:
        return kw_norm in text_norm

    return re.search(rf"\b{re.escape(kw_norm)}\b", text_norm) is not None


def evaluate_criteria(answer_text: str, criteria: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Возвращает:
    {
      "criteria_score": passed_count (учитывает инверсию),
      "criteria_max": len(criteria),
      "criteria_details": [
          {"name": ..., "matched": bool, "matched_keywords": [...], "inverted": bool, "passed": bool}
      ],
      "passed_count": ...,
      "failed_count": ...
    }
    """
    text_norm = _normalize_text(answer_text)

    details = []
    passed = 0

    for c in criteria:
        name = c.get("name", "Unnamed criterion")
        keywords = c.get("keywords", []) or []

        inverted = bool(c.get("inverted", False))
        # Поддержка вашего комментария: "инвертированный критерий"
        # Если inverted не задан, но name == "Отсутствие ошибок" — считаем инвертированным
        if (not inverted) and name.strip().lower() == "отсутствие ошибок":
            inverted = True

        matched_kws = []
        for kw in keywords:
            try:
                if _keyword_hit(text_norm, str(kw)):
                    matched_kws.append(str(kw))
            except Exception:
                # на всякий случай пропускаем экзотические значения
                continue

        matched = len(matched_kws) > 0

        # Обычный критерий: passed = matched
        # Инвертированный: passed = NOT matched (т.е. отсутствие триггер-фраз)
        c_passed = (not matched) if inverted else matched
        if c_passed:
            passed += 1

        details.append(
            {
                "name": name,
                "matched": matched,
                "matched_keywords": matched_kws[:20],  # ограничим, чтобы не раздувать JSON
                "inverted": inverted,
                "passed": c_passed,
            }
        )

    total = len(criteria)
    return {
        "criteria_score": passed,
        "criteria_max": total,
        "criteria_details": details,
        "passed_count": passed,
        "failed_count": total - passed,
    }


def criteria_ratio_0_1(criteria_pack: Dict[str, Any]) -> float:
    mx = float(criteria_pack.get("criteria_max") or 0.0)
    sc = float(criteria_pack.get("criteria_score") or 0.0)
    if mx <= 0.0:
        return 0.0
    return max(0.0, min(1.0, sc / mx))


def criteria_score_1_10(criteria_pack: Dict[str, Any]) -> float:
    """
    Нормируем criteria в 1..10:
      1 + 9 * (passed/total)
    """
    r = criteria_ratio_0_1(criteria_pack)
    return 1.0 + 9.0 * r


def cosine_to_1_10(cosine: float) -> float:
    """
    Маппинг cosine [-1..1] -> [1..10]:
      1 + 9 * ((cos+1)/2)
    """
    c = max(-1.0, min(1.0, float(cosine)))
    return 1.0 + 9.0 * ((c + 1.0) / 2.0)


def final_score_variant_b(cosine: float, criteria_pack: Dict[str, Any]) -> Dict[str, float]:
    """
    Вариант (B):
      final = 0.7*cosine_1_10 + 0.3*criteria_1_10
    """
    cosine_1_10 = cosine_to_1_10(cosine)
    criteria_1_10 = criteria_score_1_10(criteria_pack)
    final_1_10 = 0.7 * cosine_1_10 + 0.3 * criteria_1_10
    return {
        "cosine_1_10": cosine_1_10,
        "criteria_1_10": criteria_1_10,
        "final_1_10": final_1_10,
    }


def get_criteria_for_question(question_key: str) -> List[Dict[str, Any]]:
    """
    Привязка критериев к ключу из JSON, например: 'Вопрос 1'
    """
    mapping = {
        "Вопрос 1": criteria_q1,
        "Вопрос 2": criteria_q2,
        "Вопрос 3": criteria_q3,
        "Вопрос 4": criteria_q4,
    }
    return mapping.get(str(question_key).strip(), [])

