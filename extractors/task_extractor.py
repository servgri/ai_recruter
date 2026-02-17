"""Module for extracting tasks from parsed text."""

import re
import os
import csv
from typing import List, Dict, Tuple, Optional


class TaskExtractor:
    """Extracts tasks/assignments from text content."""
    
    # Cache for task prompts
    _task_prompts_cache: Optional[Dict[int, str]] = None
    
    # Russian ordinal numbers mapping
    RUSSIAN_NUMBERS = {
        'перв': 1, 'втор': 2, 'трет': 3, 'четверт': 4, 'четвёрт': 4,
        'пят': 5, 'шест': 6, 'седьм': 7, 'восьм': 8, 'девят': 9, 'десят': 10
    }
    
    # Explicit task markers (highest priority)
    EXPLICIT_TASK_PATTERNS = [
        # Uppercase patterns (with optional dot)
        (r'ЗАДАНИЕ\s+(\d+)\.?', lambda m: int(m.group(1))),  # "ЗАДАНИЕ 1" or "ЗАДАНИЕ 1."
        (r'ВОПРОС\s+(\d+)\.?', lambda m: int(m.group(1))),   # "ВОПРОС 1" or "ВОПРОС 1."
        (r'ЗАДАЧА\s+(\d+)\.?', lambda m: int(m.group(1))),   # "ЗАДАЧА 1" or "ЗАДАЧА 1."
        # Title case patterns (with optional dot)
        (r'Задание\s+(\d+)\.?', lambda m: int(m.group(1))),   # "Задание 1" or "Задание 1."
        (r'Вопрос\s+(\d+)\.?', lambda m: int(m.group(1))),   # "Вопрос 1" or "Вопрос 1."
        (r'Задача\s+(\d+)\.?', lambda m: int(m.group(1))),   # "Задача 1" or "Задача 1."
        # Lowercase patterns
        (r'задание\s+(\d+)\.?', lambda m: int(m.group(1))),   # "задание 1" or "задание 1."
        (r'вопрос\s+(\d+)\.?', lambda m: int(m.group(1))),   # "вопрос 1" or "вопрос 1."
        (r'задача\s+(\d+)\.?', lambda m: int(m.group(1))),   # "задача 1" or "задача 1."
        # With № symbol
        (r'задание\s*№\s*(\d+)', lambda m: int(m.group(1))),  # "задание №1", "задание № 1"
        (r'Задание\s*№\s*(\d+)', lambda m: int(m.group(1))),  # "Задание №1"
        (r'ЗАДАНИЕ\s*№\s*(\d+)', lambda m: int(m.group(1))),  # "ЗАДАНИЕ №1"
        (r'вопрос\s*№\s*(\d+)', lambda m: int(m.group(1))),   # "вопрос №1"
        (r'Вопрос\s*№\s*(\d+)', lambda m: int(m.group(1))),   # "Вопрос №1"
        (r'ВОПРОС\s*№\s*(\d+)', lambda m: int(m.group(1))),   # "ВОПРОС №1"
        (r'задача\s*№\s*(\d+)', lambda m: int(m.group(1))),   # "задача №1"
        (r'Задача\s*№\s*(\d+)', lambda m: int(m.group(1))),   # "Задача №1"
        (r'ЗАДАЧА\s*№\s*(\d+)', lambda m: int(m.group(1))),   # "ЗАДАЧА №1"
        # Just №
        (r'№\s*(\d+)', lambda m: int(m.group(1))),  # "№1", "№ 1"
        # Number + dot/bracket + "задание/задача/вопрос" (e.g. "1.Задание", "1)Задача")
        (r'^(\d+)[\.\)]\s*(?:задание|Задание|ЗАДАНИЕ)\b', lambda m: int(m.group(1))),  # "1.Задание", "1)Задание"
        (r'^(\d+)[\.\)]\s*(?:вопрос|Вопрос|ВОПРОС)\b', lambda m: int(m.group(1))),   # "1.Вопрос", "1)Вопрос"
        (r'^(\d+)[\.\)]\s*(?:задача|Задача|ЗАДАЧА)\b', lambda m: int(m.group(1))),   # "1.Задача", "1)Задача"
        # Letter markers A/B/C/D (mapped to 1/2/3/4)
        (r'^[AА]\s*[\.\)\:\-]\s*', lambda m: 1),  # "A.", "A)", "A:", "A-"
        (r'^[BБ]\s*[\.\)\:\-]\s*', lambda m: 2),  # "B.", "B)", "B:", "B-"
        (r'^[CС]\s*[\.\)\:\-]\s*', lambda m: 3),  # "C.", "C)", "C:", "C-"
        (r'^[DД]\s*[\.\)\:\-]\s*', lambda m: 4),  # "D.", "D)", "D:", "D-"
        # Answer patterns
        (r'Ответ\s+на\s+(\d+)', lambda m: int(m.group(1))),  # "Ответ на 1"
        (r'ответ\s+на\s+(\d+)', lambda m: int(m.group(1))),  # "ответ на 1"
        (r'Ответ\s+(\d+)', lambda m: int(m.group(1))),      # "Ответ 1"
        (r'ответ\s+(\d+)', lambda m: int(m.group(1))),      # "ответ 1"
        # Image-separated answer patterns
        (r'картинка\s*[-–—]\s*ответ\s+(\d+)', lambda m: int(m.group(1))),  # "картинка- ответ 1", "картинка -ответ 1"
        (r'Картинка\s*[-–—]\s*ответ\s+(\d+)', lambda m: int(m.group(1))),  # "Картинка- ответ 1"
        (r'картинка\s*[-–—]\s*ответ\s*(\d+)', lambda m: int(m.group(1))),  # "картинка- ответ1"
        (r'рисунок\s*[-–—]\s*ответ\s+(\d+)', lambda m: int(m.group(1))),  # "рисунок- ответ 1"
        (r'Рисунок\s*[-–—]\s*ответ\s+(\d+)', lambda m: int(m.group(1))),  # "Рисунок- ответ 1"
        (r'изображение\s*[-–—]\s*ответ\s+(\d+)', lambda m: int(m.group(1))),  # "изображение- ответ 1"
        (r'Изображение\s*[-–—]\s*ответ\s+(\d+)', lambda m: int(m.group(1))),  # "Изображение- ответ 1"
        # Russian ordinal patterns
        (r'(?:Первое|Первая|Первый|Первую)\s+задание\s*:?', lambda m: 1),
        (r'(?:Второе|Вторая|Второй|Вторую)\s+задание\s*:?', lambda m: 2),
        (r'(?:Третье|Третья|Третий|Третью)\s+задание\s*:?', lambda m: 3),
        (r'(?:Четвертое|Четвертая|Четвертый|Четвертую|Четвёртое|Четвёртая|Четвёртый|Четвёртую)\s+задание\s*:?', lambda m: 4),
        (r'(?:Первое|Первая|Первый|Первую)\s+вопрос\s*:?', lambda m: 1),
        (r'(?:Второе|Вторая|Второй|Вторую)\s+вопрос\s*:?', lambda m: 2),
        (r'(?:Третье|Третья|Третий|Третью)\s+вопрос\s*:?', lambda m: 3),
        (r'(?:Четвертое|Четвертая|Четвертый|Четвертую|Четвёртое|Четвёртая|Четвёртый|Четвёртую)\s+вопрос\s*:?', lambda m: 4),
        (r'(?:Первое|Первая|Первый|Первую)\s+задача\s*:?', lambda m: 1),
        (r'(?:Второе|Вторая|Второй|Вторую)\s+задача\s*:?', lambda m: 2),
        (r'(?:Третье|Третья|Третий|Третью)\s+задача\s*:?', lambda m: 3),
        (r'(?:Четвертое|Четвертая|Четвертый|Четвертую|Четвёртое|Четвёртая|Четвёртый|Четвёртую)\s+задача\s*:?', lambda m: 4),
        (r'Вопрос\s+(?:первый|первая|первое|первую)\s*:?', lambda m: 1),
        (r'Вопрос\s+(?:второй|вторая|второе|вторую)\s*:?', lambda m: 2),
        (r'Вопрос\s+(?:третий|третья|третье|третью)\s*:?', lambda m: 3),
        (r'Вопрос\s+(?:четвертый|четвертая|четвертое|четвертую|четвёртый|четвёртая|четвёртое|четвёртую)\s*:?', lambda m: 4),
        # Generic Russian ordinal pattern
        (r'(\w+)(?:ое|ая|ый|ую)\s+задание\s*:?', lambda m: TaskExtractor._parse_russian_ordinal(m.group(1))),
        (r'(\w+)(?:ое|ая|ый|ую)\s+вопрос\s*:?', lambda m: TaskExtractor._parse_russian_ordinal(m.group(1))),
        (r'(\w+)(?:ое|ая|ый|ую)\s+задача\s*:?', lambda m: TaskExtractor._parse_russian_ordinal(m.group(1))),
        (r'Вопрос\s+(\w+)(?:ий|ая|ое|ую)\s*:?', lambda m: TaskExtractor._parse_russian_ordinal(m.group(1))),
        (r'Задача\s+(\w+)(?:ий|ая|ое|ую)\s*:?', lambda m: TaskExtractor._parse_russian_ordinal(m.group(1))),
        # Number + Question pattern
        (r'^(\d+)\s+Вопрос', lambda m: int(m.group(1))),  # "1 Вопрос"
        # Number + "задание/задача/вопрос" pattern (common in answers: "1 задание", "2 задача")
        (r'^\s*(\d+)\s*(?:задание|задача|вопрос)\b', lambda m: int(m.group(1))),
        # Number + ":" pattern (e.g. "1: ...", "2 : ...")
        (r'^\s*(\d+)\s*:\s*', lambda m: int(m.group(1))),
        # Roman numeral tasks (I, II, III, IV) - common in docx exports
        (r'^\s*(I{1,3}|IV)\s*[\)\.\:\-]\s*', lambda m: TaskExtractor._roman_to_int(m.group(1))),
        # "Ответ на задание 1" / "Ответ на вопрос 2" / "Ответ на задачу 3"
        (r'Ответ\s+на\s+(?:задание|вопрос|задача)\s+(\d+)\.?', lambda m: int(m.group(1))),
        (r'ответ\s+на\s+(?:задание|вопрос|задача)\s+(\d+)\.?', lambda m: int(m.group(1))),
    ]
    
    # Numeric patterns (lower priority, only if no explicit markers found)
    NUMERIC_TASK_PATTERNS = [
        # Pattern for "1." with tab after dot (highest priority for tab case)
        (r'^(\d+)\.\t+', lambda m: int(m.group(1))),   # "1. табуляция" - explicit tab after dot
        # Pattern for "1." with optional special characters (tabs, non-breaking spaces, etc.)
        (r'^(\d+)\.\s*[\t\u00A0\u2000-\u200B]*', lambda m: int(m.group(1))),   # "1.", "2." at start of line with special chars
        (r'^(\d+)\.\s+', lambda m: int(m.group(1))),   # "1. " with space after dot
        (r'^(\d+)\.\s*', lambda m: int(m.group(1))),   # "1.", "2." at start of line
        (r'^(\d+)\)\s*', lambda m: int(m.group(1))),  # "1)", "2)" at start of line
        (r'^(\d+)\s+\)', lambda m: int(m.group(1))),  # "1 )" at start of line
    ]
    
    @staticmethod
    def _parse_russian_ordinal(word: str) -> int:
        """Parse Russian ordinal word to number."""
        word_lower = word.lower()
        for key, value in TaskExtractor.RUSSIAN_NUMBERS.items():
            if word_lower.startswith(key):
                return value
        return 0

    @staticmethod
    def _roman_to_int(roman: str) -> int:
        roman = (roman or "").strip().upper()
        return {"I": 1, "II": 2, "III": 3, "IV": 4}.get(roman, 0)
    
    def _find_explicit_markers(self, text: str) -> List[Tuple[int, int, str]]:
        """Find explicit task markers in text."""
        task_positions = []
        seen_positions = set()
        
        for pattern, extractor in self.EXPLICIT_TASK_PATTERNS:
            for match in re.finditer(pattern, text, re.MULTILINE | re.IGNORECASE):
                pos = match.start()
                if pos not in seen_positions:
                    try:
                        task_num = extractor(match)
                        if 1 <= task_num <= 4:  # Only tasks 1-4
                            task_positions.append((pos, task_num, pattern))
                            seen_positions.add(pos)
                    except (AttributeError, IndexError, ValueError):
                        continue
        
        # Sort by position
        task_positions.sort(key=lambda x: x[0])
        
        # Remove duplicates by task number (keep first occurrence)
        unique_tasks = []
        seen_nums = set()
        for pos, num, pattern in task_positions:
            if num not in seen_nums:
                unique_tasks.append((pos, num, pattern))
                seen_nums.add(num)
        
        return unique_tasks
    
    def _find_numeric_markers(self, text: str, exclude_after_explicit: bool = True) -> List[Tuple[int, int, str]]:
        """Find numeric task markers, excluding list items inside tasks."""
        task_positions = []
        seen_positions = set()
        excluded_positions = set()
        explicit_markers = []
        
        # If we have explicit markers, we need to be smarter about exclusion
        if exclude_after_explicit:
            explicit_markers = self._find_explicit_markers(text)
            if explicit_markers:
                # Build task intervals: from marker start to next marker start (or end of text)
                task_intervals = []
                for i, (pos, num, _) in enumerate(explicit_markers):
                    # Find end of this task's content area
                    if i < len(explicit_markers) - 1:
                        next_pos = explicit_markers[i + 1][0]
                    else:
                        # Last explicit marker - don't exclude numeric patterns after it
                        # They might be the missing task 4
                        next_pos = len(text)
                    
                    # Only exclude numeric patterns that are clearly inside task content
                    # Don't exclude patterns after the last explicit marker (they might be missing task 4)
                    if i < len(explicit_markers) - 1:  # Not the last marker
                        text_between = text[pos:next_pos]
                        for pattern, extractor_func in self.NUMERIC_TASK_PATTERNS:
                            for match in re.finditer(pattern, text_between, re.MULTILINE):
                                match_pos = pos + match.start()
                                try:
                                    task_num = extractor_func(match)
                                    # Only exclude if it's a small number that looks like a sub-item
                                    # (same or smaller than current task number)
                                    if task_num and task_num <= num:
                                        excluded_positions.add(match_pos)
                                except (AttributeError, IndexError, ValueError):
                                    excluded_positions.add(match_pos)
        
        # Find numeric patterns
        for pattern, extractor in self.NUMERIC_TASK_PATTERNS:
            for match in re.finditer(pattern, text, re.MULTILINE):
                pos = match.start()
                if pos in excluded_positions:
                    continue
                if pos not in seen_positions:
                    try:
                        task_num = extractor(match)
                        if 1 <= task_num <= 4:
                            # Check if this is a list item (comes after another number pattern)
                            is_list_item = False
                            
                            # If we have explicit markers 1-3 and this is number 4, it's likely task 4
                            if explicit_markers:
                                found_nums = {n for _, n, _ in explicit_markers}
                                if found_nums == {1, 2, 3} and task_num == 4:
                                    is_list_item = False  # This is likely task 4, not a list item
                                elif pos > 0:
                                    # Look back for another numeric pattern
                                    lookback = text[max(0, pos-200):pos]
                                    # Check if there's a pattern like "1." followed by "1)" or "1." followed by "1."
                                    if re.search(r'\d+[\.\)]\s*\n\s*\d+[\.\)]', lookback + text[pos:pos+100]):
                                        # Check if numbers match or are sequential
                                        prev_match = re.search(r'(\d+)[\.\)]\s*\n\s*(\d+)[\.\)]', lookback + text[pos:pos+100])
                                        if prev_match:
                                            prev_num = int(prev_match.group(1))
                                            curr_num = int(prev_match.group(2))
                                            # If current number is same or smaller, it's likely a list item
                                            if curr_num <= prev_num:
                                                is_list_item = True
                                            elif curr_num == prev_num + 1 and prev_num > 0 and prev_num < 4:
                                                # Sequential numbers might be sub-items
                                                is_list_item = True
                            elif pos > 0:
                                # No explicit markers, use original logic
                                lookback = text[max(0, pos-200):pos]
                                if re.search(r'\d+[\.\)]\s*\n\s*\d+[\.\)]', lookback + text[pos:pos+100]):
                                    prev_match = re.search(r'(\d+)[\.\)]\s*\n\s*(\d+)[\.\)]', lookback + text[pos:pos+100])
                                    if prev_match:
                                        prev_num = int(prev_match.group(1))
                                        curr_num = int(prev_match.group(2))
                                        if curr_num <= prev_num:
                                            is_list_item = True
                            
                            if not is_list_item:
                                task_positions.append((pos, task_num, pattern))
                                seen_positions.add(pos)
                    except (AttributeError, IndexError, ValueError):
                        continue
        
        # Sort by position
        task_positions.sort(key=lambda x: x[0])
        
        # Remove duplicates by task number
        unique_tasks = []
        seen_nums = set()
        for pos, num, pattern in task_positions:
            if num not in seen_nums:
                unique_tasks.append((pos, num, pattern))
                seen_nums.add(num)
        
        return unique_tasks
    
    def _preprocess_text(self, text: str) -> str:
        """
        Preprocess text before task extraction: remove page numbers, normalize formatting.
        
        Args:
            text: Original text content
            
        Returns:
            Preprocessed text with page numbers removed
        """
        lines = text.split('\n')
        processed_lines = []
        
        for line in lines:
            # Remove page numbers (common patterns):
            # - Single number at start/end of line (likely page number)
            # - "Страница N" or "Page N"
            # - Numbers in corners (right-aligned numbers)
            
            # Remove "Страница N" or "Page N" patterns
            line = re.sub(r'(?i)(страница|page)\s+\d+', '', line)
            
            # Remove standalone numbers at start of line (if line is mostly empty or just number)
            if re.match(r'^\s*\d+\s*$', line):
                continue  # Skip lines that are just a number
            
            # Remove numbers at end of line if line is mostly empty (but be careful not to remove task numbers)
            # Only remove if line is very short and ends with just a number
            if len(line.strip()) <= 3 and re.match(r'^\s*\d+\s*$', line):
                continue  # Skip lines that are just a short number (likely page number)
            
            # Remove right-aligned page numbers (number at end with lots of space before)
            # But don't remove if it looks like part of content
            if re.match(r'^.{0,10}\s{15,}\d+\s*$', line):  # Very few chars, then 15+ spaces, then number
                line = re.sub(r'\s{15,}\d+\s*$', '', line)  # Remove right-aligned numbers with lots of space
            
            if line.strip():  # Only add non-empty lines
                processed_lines.append(line)
        
        return '\n'.join(processed_lines)
    
    def _load_task_prompts(self) -> Dict[int, str]:
        """
        Load task prompts from task_data.csv.
        
        Returns:
            Dictionary mapping task_number (1-4) to prompt text
        """
        if self._task_prompts_cache is not None:
            return self._task_prompts_cache
        
        prompts = {}
        
        # Try to find task_data.csv in common locations
        possible_paths = [
            os.path.join(os.path.dirname(__file__), '..', 'task_data.csv'),
            os.path.join(os.getcwd(), 'task_data.csv'),
            'task_data.csv',
        ]
        
        csv_path = None
        for path in possible_paths:
            if os.path.exists(path):
                csv_path = path
                break
        
        if not csv_path:
            # If file not found, return empty prompts (cleanup will be skipped)
            self._task_prompts_cache = prompts
            return prompts
        
        try:
            with open(csv_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                row = next(reader, None)  # Read first data row
                if row:
                    for task_num in range(1, 5):
                        task_key = f'task_{task_num}'
                        if task_key in row:
                            prompts[task_num] = row[task_key] or ''
        except Exception:
            # If reading fails, return empty prompts
            pass
        
        self._task_prompts_cache = prompts
        return prompts
    
    def _clean_answer(self, task_num: int, text: str) -> str:
        """
        Remove prompt text from answer while preserving baseline schemas/SQL.
        
        Args:
            task_num: Task number (1-4)
            text: Answer text to clean
            
        Returns:
            Cleaned text with prompt prose removed but schemas/SQL preserved
        """
        if not text or not text.strip():
            return text
        
        prompts = self._load_task_prompts()
        if task_num not in prompts or not prompts[task_num]:
            return text  # No prompt to clean against
        
        prompt = prompts[task_num]
        cleaned = text
        
        # Split prompt into lines for more granular matching
        prompt_lines = [line.strip() for line in prompt.split('\n') if line.strip()]
        
        # Protected patterns - these should NOT be removed even if they match prompt
        protected_patterns = []
        
        if task_num == 1:
            # Protect clients table schema
            protected_patterns.extend([
                r'clients\s*\([^)]*\)',
                r'client_id\s+\w+',
                r'client_name\s+\w+',
                r'client_surname\s+\w+',
            ])
        elif task_num == 2:
            # Protect items table schema
            protected_patterns.extend([
                r'items\s*\([^)]*\)',
                r'item_id\s+\w+',
                r'item_name\s+\w+',
                r'item_cost\s+\w+',
            ])
        elif task_num == 3:
            # Protect SQL query patterns
            protected_patterns.extend([
                r'SELECT\s+.*?FROM',
                r'EMPLOYEE\s+E',
                r'DEPARTMENTS\s+D',
                r'LOCATIONS',
                r'DEPARTMENT_ID',
                r'MANAGER_ID',
            ])
        elif task_num == 4:
            # For task 4, just remove the question text if it's verbatim
            question_text = "В некоторой комнате на пол уронили карандаш. Объясните почему вы не можете через него перепрыгнуть?"
            if question_text.lower() in cleaned.lower():
                # Remove the question but keep the answer
                cleaned = re.sub(re.escape(question_text), '', cleaned, flags=re.IGNORECASE)
            return cleaned.strip()
        
        # Remove common prompt prose patterns (but not protected content)
        # Remove "Представьте, что вы устроились..." type intros
        intro_patterns = [
            r'Представьте\s*,?\s*что\s+вы\s+устроились\s+работать.*?Дата-инженером.*?',
            r'До\s+вас\s+в\s+этой\s+компании.*?уволился\.',
            r'Ваша\s+задача\s+провести\s+проверку.*?',
            r'Вы\s+обратили\s+внимание\s+на\s+таблицу.*?',
            r'Таблица\s+имеет\s+следующую\s+схему\s*:',
            r'Считаете\s+ли\s+вы\s+данный\s+набор.*?',
            r'Если\s+нет\s*,?\s*то\s+напишите.*?',
            r'Требуется\s+проверить\s+запрос\s+на\s+корректность.*?',
            r'Существует\s+учебная\s+схема\s+HR.*?',
            r'Необходимо\s+получить\s+все\s+отделы.*?',
            r'Для\s+решения\s+задачи\s+был\s+написан\s+следующий\s+запрос\s*:',
        ]
        
        for pattern in intro_patterns:
            # Check if pattern matches protected content before removing
            matches = list(re.finditer(pattern, cleaned, re.IGNORECASE | re.DOTALL))
            for match in reversed(matches):  # Process from end to preserve indices
                match_text = match.group(0)
                # Check if this match overlaps with protected content
                is_protected = False
                for prot_pattern in protected_patterns:
                    if re.search(prot_pattern, match_text, re.IGNORECASE):
                        is_protected = True
                        break
                
                if not is_protected:
                    cleaned = cleaned[:match.start()] + cleaned[match.end():]
        
        # Remove task markers that might have been copied from prompt
        marker_patterns = [
            r'^Вопрос\s+\d+\s*\.?\s*',
            r'^Задание\s+\d+\s*\.?\s*',
            r'^Задача\s+\d+\s*\.?\s*',
            r'^Ответ\s+\d+\s*\.?\s*',
        ]
        
        for pattern in marker_patterns:
            cleaned = re.sub(pattern, '', cleaned, flags=re.MULTILINE | re.IGNORECASE)
        
        return cleaned.strip()
    
    def extract_tasks(self, text: str) -> List[Dict[str, str]]:
        """
        Extract tasks from text content with priority-based recognition.
        
        Args:
            text: Full text content of the file
            
        Returns:
            List of dictionaries with task_number and content
        """
        # Preprocess text: remove page numbers
        text = self._preprocess_text(text)
        
        # First pass: find explicit markers
        explicit_tasks = self._find_explicit_markers(text)
        
        # If we found 4 or more explicit tasks, use only them
        if len(explicit_tasks) >= 4:
            task_positions = explicit_tasks[:4]
        else:
            # Second pass: find numeric markers (only if we need more tasks)
            numeric_tasks = self._find_numeric_markers(text, exclude_after_explicit=len(explicit_tasks) > 0)
            
            # Combine explicit and numeric, prioritizing explicit
            all_tasks = explicit_tasks + numeric_tasks
            # Remove duplicates by position
            seen_pos = set()
            combined = []
            for pos, num, pattern in all_tasks:
                if pos not in seen_pos:
                    combined.append((pos, num, pattern))
                    seen_pos.add(pos)
            
            # Sort by position
            combined.sort(key=lambda x: x[0])
            
            # Take first 4 unique tasks by number
            task_positions = []
            seen_nums = set()
            for pos, num, pattern in combined:
                if num not in seen_nums and num <= 4:
                    task_positions.append((pos, num, pattern))
                    seen_nums.add(num)
                if len(task_positions) >= 4:
                    break
        
        # Extract task content
        tasks = []
        for i, (start_pos, task_num, pattern) in enumerate(task_positions):
            # Find end of marker
            marker_end = start_pos
            for pat, extractor in (self.EXPLICIT_TASK_PATTERNS + self.NUMERIC_TASK_PATTERNS):
                match = re.search(pat, text[start_pos:start_pos+100], re.IGNORECASE | re.MULTILINE)
                if match and extractor(match) == task_num:
                    marker_end = start_pos + match.end()
                    break
            
            # Skip whitespace, newlines, tabs, and special formatting characters after marker
            # Includes non-breaking spaces (U+00A0) and other Unicode spaces (U+2000-U+200B)
            # Tabs are explicitly handled as they may be used for indentation
            while marker_end < len(text):
                char = text[marker_end]
                if char in ': \t\n\r':
                    marker_end += 1
                elif ord(char) == 0x00A0 or (ord(char) >= 0x2000 and ord(char) <= 0x200B):
                    marker_end += 1
                else:
                    break
            
            # Find end position (start of next task or end of text)
            # Also check for image separators as task boundaries
            if i < len(task_positions) - 1:
                next_task_pos = task_positions[i + 1][0]
                # Check if there's an image marker between current and next task
                # If image marker is closer, use it as boundary
                text_between = text[marker_end:next_task_pos]
                image_marker = re.search(r'\[Изображение[:\s]', text_between)
                if image_marker:
                    # If image marker is followed by another task marker, use image as boundary
                    after_image = text[marker_end + image_marker.end():next_task_pos]
                    if re.search(r'(Задание|Вопрос|№)\s*\d+', after_image, re.IGNORECASE):
                        # Image is separator, end task before image
                        end_pos = marker_end + image_marker.start()
                    else:
                        # Image is part of current task, include it
                        end_pos = next_task_pos
                else:
                    end_pos = next_task_pos
            else:
                end_pos = len(text)
            
            task_content = text[marker_end:end_pos].strip()
            tasks.append({
                "task_number": task_num,
                "content": task_content
            })

        # Fallback: if markers are missing/weak, split by semantic anchors (clients/items/SQL/pencil)
        # This is tuned for the current interview task set and is used only when it improves results.
        fallback_tasks = self._fallback_split_by_anchors(text)
        non_empty_tasks = [t for t in tasks if t.get('content', '').strip()]
        fallback_non_empty = [t for t in fallback_tasks if t.get('content', '').strip()]
        if len(fallback_non_empty) > len(non_empty_tasks) and len(fallback_non_empty) >= 2:
            tasks = fallback_tasks
        
        # Check if we need to detect missing task 4 by context
        non_empty_tasks = [t for t in tasks if t.get('content', '').strip()]
        if len(non_empty_tasks) == 3:
            # Check if we have tasks 1, 2, 3 but missing 4
            found_numbers = {t.get('task_number') for t in non_empty_tasks}
            if found_numbers == {1, 2, 3}:
                # Try to detect task 4 by context
                task_4_info = self._detect_missing_task_4(text, task_positions, tasks)
                if task_4_info:
                    start_pos, end_pos = task_4_info
                    task_4_content = text[start_pos:end_pos].strip()
                    if task_4_content:
                        # Add task 4
                        tasks.append({
                            "task_number": 4,
                            "content": task_4_content
                        })
        
        # Normalize to exactly 4 unique task numbers (1..4) without duplicates.
        # NOTE: The naive padding-by-length can create duplicate task_number entries
        # (e.g. when only tasks 3 and 4 are detected). That breaks downstream CSV
        # mapping because later duplicates overwrite real content.
        by_num: Dict[int, List[str]] = {1: [], 2: [], 3: [], 4: []}
        for t in tasks:
            try:
                num = int(t.get("task_number", 0))
            except Exception:
                continue
            if num not in by_num:
                continue
            content = (t.get("content", "") or "").strip()
            by_num[num].append(content)

        normalized: List[Dict[str, str]] = []
        for num in (1, 2, 3, 4):
            # Prefer the first non-empty content; otherwise empty string.
            content = ""
            for c in by_num[num]:
                if c:
                    content = c
                    break
            # Clean prompt text from answer
            cleaned_content = self._clean_answer(num, content)
            normalized.append({"task_number": num, "content": cleaned_content})

        return normalized

    def _fallback_split_by_anchors(self, text: str) -> List[Dict[str, str]]:
        """
        Heuristic split into 4 tasks by common anchors when explicit markers are absent.

        Anchors are based on the recurring interview questions:
        1) clients table (internet-shop DB schema)
        2) items table / price history
        3) HR SQL query fix (Seoul, manager_id is null, HAVING SUM)
        4) pencil in the room
        """
        if not text or not text.strip():
            return [{"task_number": i, "content": ""} for i in range(1, 5)]

        import re

        lower = text.lower()

        def find_first(patterns: List[str], start_at: int = 0) -> int:
            best = -1
            for pat in patterns:
                m = re.search(pat, text[start_at:], re.IGNORECASE | re.MULTILINE)
                if not m:
                    continue
                pos = start_at + m.start()
                if best == -1 or pos < best:
                    best = pos
            return best

        # Task 4 (pencil) anchor - expanded patterns
        t4_patterns = [
            r'\bв\s+некоторой\s+комнате\b',
            r'\bобъясните\b.*\bкарандаш\b',
            r'\bкарандаш\b',
            r'\bперепрыг\w*\b',
            r'\bпрыг\w*\b.*\bкарандаш\b',
            r'\bкарандаш\b.*\bстен\w*\b',
            r'\bстен\w*\b.*\bкарандаш\b',
            r'\bуронили\b.*\bкарандаш\b',
            r'\bкарандаш\b.*\bупал\w*\b',
        ]

        # Task 3 (SQL/HR) anchor
        t3_patterns = [
            r'\bтребуется\s+проверить\s+запрос\b',
            r'\bучебн\w*\s+схем\w*\s+hr\b',
            r'\bselect\s+department_id\b',
            r'\bemployees\b.*\bdepartments\b.*\blocations\b',
        ]

        # Task 2 (items/price history) anchor
        t2_patterns = [
            r'\bтаблиц\w*\s+items\b',
            r'\bitems\s*\(',
            r'\bстоимост\w*\s+товар\w*\b',
            r'\bисторич\w*\s+хранен\w*\b.*\bцен\b',
        ]

        # Task 1 (clients) anchor - used only to avoid chopping early headers
        t1_patterns = [
            r'\bтаблиц\w*\s+clients\b',
            r'\bclients\s*\(',
            r'\bзарегистрировавш\w*\b.*\bклиент\w*\b',
        ]

        idx1 = find_first(t1_patterns, 0)
        idx2 = find_first(t2_patterns, 0)
        idx3 = find_first(t3_patterns, 0)
        idx4 = find_first(t4_patterns, 0)

        # Enforce order: 1 < 2 < 3 < 4 (best-effort)
        # If we detected task1 after task2, ignore task1 anchor.
        if idx1 != -1 and idx2 != -1 and idx1 > idx2:
            idx1 = -1
        # If task2 is after task3, ignore task2 anchor.
        if idx2 != -1 and idx3 != -1 and idx2 > idx3:
            idx2 = -1
        # If task4 is before task3, try to find pencil after task3.
        if idx4 != -1 and idx3 != -1 and idx4 < idx3:
            idx4 = find_first(t4_patterns, idx3)

        # Choose boundaries
        start1 = 0
        start2 = idx2 if idx2 != -1 else -1
        start3 = idx3 if idx3 != -1 else -1
        start4 = idx4 if idx4 != -1 else -1

        # If we only have SQL and pencil, split as: [before SQL]=1, [SQL..pencil]=3, [pencil..]=4
        if start2 == -1 and start3 != -1:
            start2 = -1
        # If we have items but no clients, task1 is from start..items
        # If no anchors at all, return empties (caller will keep marker-based)
        if start2 == -1 and start3 == -1 and start4 == -1:
            return [{"task_number": i, "content": ""} for i in range(1, 5)]

        # Build slices carefully
        def slice_text(a: int, b: int) -> str:
            if a == -1:
                return ""
            if b == -1:
                return text[a:].strip()
            if b <= a:
                return ""
            return text[a:b].strip()

        # Decide end positions
        end1 = start2 if start2 != -1 else (start3 if start3 != -1 else (start4 if start4 != -1 else -1))
        end2 = start3 if start3 != -1 else (start4 if start4 != -1 else -1)
        end3 = start4 if start4 != -1 else -1

        t1 = slice_text(start1, end1)
        t2 = slice_text(start2, end2) if start2 != -1 else ""
        t3 = slice_text(start3, end3) if start3 != -1 else ""
        t4 = slice_text(start4, -1) if start4 != -1 else ""

        return [
            {"task_number": 1, "content": t1},
            {"task_number": 2, "content": t2},
            {"task_number": 3, "content": t3},
            {"task_number": 4, "content": t4},
        ]
    
    def _detect_missing_task_4(self, text: str, found_tasks: List[Tuple[int, int, str]], 
                               extracted_tasks: List[Dict[str, str]]) -> Optional[Tuple[int, int]]:
        """
        Detect missing task 4 by context: look for pencil/wall mentions after task 3.
        
        Args:
            text: Full text content
            found_tasks: List of found tasks (position, task_number, pattern)
            extracted_tasks: List of already extracted tasks
            
        Returns:
            Tuple of (start_pos, end_pos) if task 4 detected, None otherwise
        """
        if not found_tasks:
            return None
        
        # Find task 3
        task_3 = next((t for t in extracted_tasks if t.get('task_number') == 3 and t.get('content', '').strip()), None)
        if not task_3:
            return None
        
        task_3_content = task_3.get('content', '')
        
        # Find task 3 position in text
        task_3_pos = None
        for pos, num, _ in found_tasks:
            if num == 3:
                task_3_pos = pos
                break
        
        if not task_3_pos:
            return None
        
        # Find where task 3 marker ends
        task_3_end_in_text = task_3_pos
        for pat, extractor in (self.EXPLICIT_TASK_PATTERNS + self.NUMERIC_TASK_PATTERNS):
            match = re.search(pat, text[task_3_pos:task_3_pos+100], re.IGNORECASE | re.MULTILINE)
            if match:
                task_3_end_in_text = task_3_pos + match.end()
                break
        
        # Skip whitespace after marker
        while task_3_end_in_text < len(text) and text[task_3_end_in_text] in ' \t\n\r':
            task_3_end_in_text += 1
        
        # Find end of task 3 content - look for various endings
        # 1. SQL ending: ; or . followed by blank lines
        text_after_marker = text[task_3_end_in_text:]
        sql_end_match = re.search(r'[.;]\s*\n\s*\n', text_after_marker)
        if sql_end_match:
            potential_task_4_start = task_3_end_in_text + sql_end_match.end()
        else:
            # 2. Look for end of task 3 content (ends with ; or .)
            end_match = re.search(r'[.;]\s*$', task_3_content)
            if end_match:
                # Find this position in full text
                task_3_content_in_text = text[task_3_end_in_text:]
                # Try to find a unique ending pattern
                content_suffix = task_3_content[-100:].strip()
                if content_suffix:
                    content_end_match = re.search(re.escape(content_suffix), task_3_content_in_text)
                    if content_end_match:
                        potential_task_4_start = task_3_end_in_text + content_end_match.end()
                    else:
                        potential_task_4_start = task_3_end_in_text + len(task_3_content)
                else:
                    potential_task_4_start = task_3_end_in_text + len(task_3_content)
            else:
                # 3. Use task 3 content length as fallback
                potential_task_4_start = task_3_end_in_text + len(task_3_content)
        
        # Skip whitespace
        while potential_task_4_start < len(text) and text[potential_task_4_start] in ' \t\n\r':
            potential_task_4_start += 1
        
        # Get text after task 3
        text_after_task_3 = text[potential_task_4_start:].strip()
        
        if len(text_after_task_3) < 20:  # Not enough content
            return None
        
        # Expanded list of keywords for task 4 (pencil problem)
        task_4_keywords = [
            'карандаш', 'стен', 'стена', 'стены', 'стене', 'стеной',
            'комнат', 'комната', 'комнате', 'комнату', 'комнатой',
            'перепрыг', 'перепрыгнуть', 'прыг', 'прыгать', 'прыжок',
            'прыгнуть', 'перешаг', 'перешагнуть',
            'pencil', 'wall', 'room', 'jump', 'jumping',
            'упал', 'упали', 'уронили', 'уронил', 'упало',
            'угол', 'углу', 'угла', 'corner',
            'некоторой', 'некоторой комнате',
            'объясните', 'объяснить', 'почему'
        ]
        
        # Check if text contains task 4 keywords
        text_lower = text_after_task_3.lower()
        keyword_matches = sum(1 for keyword in task_4_keywords if keyword in text_lower)
        
        # Need at least 2 keyword matches to be confident it's task 4
        if keyword_matches >= 2:
            # Return start and end positions (end is end of text)
            return (potential_task_4_start, len(text))
        
        return None
    
    def has_problems(self, tasks: List[Dict[str, str]], text: str) -> Optional[Dict]:
        """
        Check if there are problems with task extraction.
        
        Args:
            tasks: List of extracted tasks
            text: Original text content
            
        Returns:
            Dictionary with problem information or None if no problems
        """
        problems = {
            "has_problems": False,
            "tasks_found": 0,
            "tasks_expected": 4,
            "empty_tasks": [],
            "problem_reason": "",
            "detected_markers": []
        }
        
        # Use the same preprocessing as extraction so marker detection is consistent
        text = self._preprocess_text(text or "")

        # Count non-empty tasks
        non_empty_count = sum(1 for task in tasks if task.get('content', '').strip())
        problems["tasks_found"] = non_empty_count
        
        # Find empty tasks
        for i, task in enumerate(tasks, 1):
            if not task.get('content', '').strip():
                problems["empty_tasks"].append(i)
        
        # Check for problems
        if non_empty_count < 4:
            problems["has_problems"] = True
            problems["problem_reason"] = f"Найдено только {non_empty_count} заданий из 4"
            
            # Try to detect what markers were found
            explicit = self._find_explicit_markers(text)
            numeric = self._find_numeric_markers(text, exclude_after_explicit=False)
            
            detected = []
            for pos, num, pattern in explicit[:4]:
                # Extract the actual marker text
                marker_text = text[pos:pos+50].split('\n')[0].strip()
                detected.append(marker_text[:30])
            
            if len(detected) < 4:
                for pos, num, pattern in numeric[:4]:
                    if num not in [t[1] for t in explicit]:
                        marker_text = text[pos:pos+20].split('\n')[0].strip()
                        detected.append(marker_text[:20])
            
            problems["detected_markers"] = detected[:4]
            return problems
        else:
            # All 4 tasks found and non-empty - no problems
            return None
