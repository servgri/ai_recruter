"""Module for extracting tasks from parsed text."""

import re
from typing import List, Dict, Tuple, Optional


class TaskExtractor:
    """Extracts tasks/assignments from text content."""
    
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
        # Title case patterns (with optional dot)
        (r'Задание\s+(\d+)\.?', lambda m: int(m.group(1))),   # "Задание 1" or "Задание 1."
        (r'Вопрос\s+(\d+)\.?', lambda m: int(m.group(1))),   # "Вопрос 1" or "Вопрос 1."
        # With № symbol
        (r'задание\s*№\s*(\d+)', lambda m: int(m.group(1))),  # "задание №1", "задание № 1"
        (r'Задание\s*№\s*(\d+)', lambda m: int(m.group(1))),  # "Задание №1"
        (r'ЗАДАНИЕ\s*№\s*(\d+)', lambda m: int(m.group(1))),  # "ЗАДАНИЕ №1"
        (r'вопрос\s*№\s*(\d+)', lambda m: int(m.group(1))),   # "вопрос №1"
        (r'Вопрос\s*№\s*(\d+)', lambda m: int(m.group(1))),   # "Вопрос №1"
        (r'ВОПРОС\s*№\s*(\d+)', lambda m: int(m.group(1))),   # "ВОПРОС №1"
        # Just №
        (r'№\s*(\d+)', lambda m: int(m.group(1))),  # "№1", "№ 1"
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
        (r'Вопрос\s+(?:первый|первая|первое|первую)\s*:?', lambda m: 1),
        (r'Вопрос\s+(?:второй|вторая|второе|вторую)\s*:?', lambda m: 2),
        (r'Вопрос\s+(?:третий|третья|третье|третью)\s*:?', lambda m: 3),
        (r'Вопрос\s+(?:четвертый|четвертая|четвертое|четвертую|четвёртый|четвёртая|четвёртое|четвёртую)\s*:?', lambda m: 4),
        # Generic Russian ordinal pattern
        (r'(\w+)(?:ое|ая|ый|ую)\s+задание\s*:?', lambda m: TaskExtractor._parse_russian_ordinal(m.group(1))),
        (r'(\w+)(?:ое|ая|ый|ую)\s+вопрос\s*:?', lambda m: TaskExtractor._parse_russian_ordinal(m.group(1))),
        (r'Вопрос\s+(\w+)(?:ий|ая|ое|ую)\s*:?', lambda m: TaskExtractor._parse_russian_ordinal(m.group(1))),
        # Number + Question pattern
        (r'^(\d+)\s+Вопрос', lambda m: int(m.group(1))),  # "1 Вопрос"
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
        
        # If we have explicit markers, exclude numeric patterns that come after them
        if exclude_after_explicit:
            explicit_markers = self._find_explicit_markers(text)
            for pos, num, _ in explicit_markers:
                # Find next explicit marker or end of text
                next_pos = len(text)
                for next_pos_val, next_num, _ in explicit_markers:
                    if next_pos_val > pos and next_num > num:
                        next_pos = next_pos_val
                        break
                
                # Mark all numeric patterns between this explicit marker and next as excluded
                text_between = text[pos:next_pos]
                for pattern, _ in self.NUMERIC_TASK_PATTERNS:
                    for match in re.finditer(pattern, text_between, re.MULTILINE):
                        excluded_positions.add(pos + match.start())
        
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
                            if pos > 0:
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
                                        if curr_num <= prev_num or (curr_num == prev_num + 1 and prev_num > 0):
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
        
        # Ensure we always return exactly 4 tasks
        while len(tasks) < 4:
            tasks.append({
                "task_number": len(tasks) + 1,
                "content": ""
            })
        
        # Sort tasks by task_number to ensure correct order
        tasks.sort(key=lambda t: t.get('task_number', 0))
        
        return tasks[:4]
    
    def _detect_missing_task_4(self, text: str, found_tasks: List[Tuple[int, int, str]], 
                               extracted_tasks: List[Dict[str, str]]) -> Optional[Tuple[int, int]]:
        """
        Detect missing task 4 by context: look for pencil/wall mentions after SQL script.
        
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
        
        # Check if task 3 ends with SQL script (ends with ; or .)
        task_3_ends_with_sql = task_3_content.strip().endswith(';') or task_3_content.strip().endswith('.')
        
        if not task_3_ends_with_sql:
            return None
        
        # Find task 3 end position in text
        task_3_pos = None
        for pos, num, _ in found_tasks:
            if num == 3:
                task_3_pos = pos
                break
        
        if not task_3_pos:
            return None
        
        # Find where task 3 content actually ends in text
        # Look for the end of task 3 content (after SQL script)
        task_3_end_in_text = task_3_pos
        # Find task 3 marker end
        for pat, extractor in (self.EXPLICIT_TASK_PATTERNS + self.NUMERIC_TASK_PATTERNS):
            match = re.search(pat, text[task_3_pos:task_3_pos+100], re.IGNORECASE | re.MULTILINE)
            if match:
                task_3_end_in_text = task_3_pos + match.end()
                break
        
        # Skip whitespace after marker
        while task_3_end_in_text < len(text) and text[task_3_end_in_text] in ' \t\n\r':
            task_3_end_in_text += 1
        
        # Find end of task 3 content (look for ; or . followed by blank lines or end of text)
        text_after_task_3 = text[task_3_end_in_text:]
        
        # Look for SQL ending pattern: ; or . followed by blank lines
        sql_end_match = re.search(r'[.;]\s*\n\s*\n', text_after_task_3)
        if sql_end_match:
            potential_task_4_start = task_3_end_in_text + sql_end_match.end()
        else:
            # Look for end of task 3 content (ends with ; or .)
            end_match = re.search(r'[.;]\s*$', task_3_content)
            if end_match:
                # Find this position in full text
                task_3_content_in_text = text[task_3_end_in_text:]
                content_end_match = re.search(re.escape(task_3_content[-50:]), task_3_content_in_text)
                if content_end_match:
                    potential_task_4_start = task_3_end_in_text + content_end_match.end()
                else:
                    potential_task_4_start = task_3_end_in_text + len(task_3_content)
            else:
                potential_task_4_start = task_3_end_in_text + len(task_3_content)
        
        # Skip whitespace
        while potential_task_4_start < len(text) and text[potential_task_4_start] in ' \t\n\r':
            potential_task_4_start += 1
        
        # Get text after task 3
        text_after_sql = text[potential_task_4_start:].strip()
        
        # Check if text contains pencil/wall/room keywords
        pencil_keywords = ['карандаш', 'стен', 'стена', 'комнат', 'комната', 'pencil', 'wall', 'room']
        has_keywords = any(keyword.lower() in text_after_sql.lower() for keyword in pencil_keywords)
        
        if has_keywords and len(text_after_sql) > 20:  # Ensure there's substantial content
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
