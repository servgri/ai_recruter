"""File handling utilities."""

import os
import json
import csv
from typing import Optional, Dict

from parsers import (
    TxtParser, PdfParser, DocxParser, MdParser, SqlParser, 
    XlsxParser, DocParser, BaseParser
)


class FileHandler:
    """Handles file operations for services that use CSV (e.g. task cleaner, embedding, analysis)."""
    
    def __init__(self, csv_dir: str = "", csv_file: str = "loaded_data.csv"):
        """
        Initialize FileHandler.
        
        Args:
            csv_dir: Directory for CSV file (empty = current dir)
            csv_file: Name of CSV file used by cleaner/embedding/analysis services
        """
        self.csv_dir = csv_dir if csv_dir else "."
        self.csv_file = os.path.join(self.csv_dir, csv_file) if csv_dir else csv_file
    
    def _clean_text(self, text: str) -> str:
        """Clean text for CSV (remove newlines, normalize spaces)."""
        if not text:
            return ''
        cleaned = text.replace('\n', ' ').replace('\r', ' ')
        cleaned = ' '.join(cleaned.split())
        return cleaned
    
    def append_to_csv(self, filename: str, file_type: str, content: str, tasks: list) -> str:
        """
        Append a record to the main CSV file immediately.
        
        Args:
            filename: Original filename
            file_type: File extension/type
            content: Full text content
            tasks: List of extracted tasks
            
        Returns:
            Path to CSV file
        """
        fieldnames = [
            'full_filename', 'filename', 'type', 'task_1', 'task_2', 'task_3', 'task_4', 'content',
            'task_1_tails', 'task_2_tails', 'task_3_tails', 'task_4_tails',
            'tasks_count', 'cleaning_status',
            'embedding_task_1', 'embedding_task_2', 'embedding_task_3', 'embedding_task_4', 'embedding_content',
            'embedding_method',
            'similarity_with_reference', 'similarity_with_existing',
            'cheating_score', 'analysis_report'
        ]
        
        full_filename = filename
        filename_no_ext = os.path.splitext(full_filename)[0] if '.' in full_filename else full_filename
        
        # Create dictionary mapping task_number to content
        task_dict = {task.get('task_number', i+1): task.get('content', '') for i, task in enumerate(tasks)}
        
        # Get tasks by their actual numbers (not by order in list)
        task_1 = task_dict.get(1, '')
        task_2 = task_dict.get(2, '')
        task_3 = task_dict.get(3, '')
        task_4 = task_dict.get(4, '')
        
        # Count non-empty tasks
        non_empty_tasks = [task for task in tasks if task.get('content', '').strip()]
        tasks_count = len(non_empty_tasks)
        
        row = {
            'full_filename': full_filename,
            'filename': filename_no_ext,
            'type': file_type,
            'task_1': self._clean_text(task_1),
            'task_2': self._clean_text(task_2),
            'task_3': self._clean_text(task_3),
            'task_4': self._clean_text(task_4),
            'content': self._clean_text(content),
            # Cleaning fields (empty initially)
            'task_1_tails': '',
            'task_2_tails': '',
            'task_3_tails': '',
            'task_4_tails': '',
            'tasks_count': str(tasks_count),
            'cleaning_status': 'validated' if tasks_count == 2 else ('cleaned' if tasks_count == 4 else 'partial'),
            # Embedding fields (empty initially)
            'embedding_task_1': '',
            'embedding_task_2': '',
            'embedding_task_3': '',
            'embedding_task_4': '',
            'embedding_content': '',
            'embedding_method': '',
            # Analysis fields (empty initially)
            'similarity_with_reference': '',
            'similarity_with_existing': '',
            'cheating_score': '',
            'analysis_report': ''
        }
        
        # Append to CSV file
        with open(self.csv_file, 'a', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writerow(row)
        
        return self.csv_file

    def load_embeddings_from_csv(self, filename: str) -> Optional[Dict]:
        """
        Load embeddings from CSV for a specific file.
        
        Args:
            filename: Filename to look up
            
        Returns:
            Dictionary with embeddings or None if not found
        """
        if not os.path.exists(self.csv_file):
            return None
        
        import json
        from utils.embedding_utils import load_embeddings_from_json
        
        with open(self.csv_file, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get('full_filename') == filename or row.get('filename') == filename:
                    return {
                        'task_1': load_embeddings_from_json(row.get('embedding_task_1', '')),
                        'task_2': load_embeddings_from_json(row.get('embedding_task_2', '')),
                        'task_3': load_embeddings_from_json(row.get('embedding_task_3', '')),
                        'task_4': load_embeddings_from_json(row.get('embedding_task_4', '')),
                        'content': load_embeddings_from_json(row.get('embedding_content', ''))
                    }
        
        return None
    
    def load_cleaned_tasks_from_csv(self, filename: str) -> Optional[Dict]:
        """
        Load cleaned tasks and tails from CSV.
        
        Args:
            filename: Filename to look up
            
        Returns:
            Dictionary with cleaned tasks and tails or None if not found
        """
        if not os.path.exists(self.csv_file):
            return None
        
        import json
        
        with open(self.csv_file, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get('full_filename') == filename or row.get('filename') == filename:
                    return {
                        'task_1': row.get('task_1', ''),
                        'task_2': row.get('task_2', ''),
                        'task_3': row.get('task_3', ''),
                        'task_4': row.get('task_4', ''),
                        'task_1_tails': json.loads(row.get('task_1_tails', '[]')),
                        'task_2_tails': json.loads(row.get('task_2_tails', '[]')),
                        'task_3_tails': json.loads(row.get('task_3_tails', '[]')),
                        'task_4_tails': json.loads(row.get('task_4_tails', '[]')),
                        'tasks_count': row.get('tasks_count', ''),
                        'cleaning_status': row.get('cleaning_status', '')
                    }
        
        return None


def get_parser_for_file(filename: str) -> Optional[BaseParser]:
    """
    Get appropriate parser for file based on extension.
    
    Args:
        filename: Name of the file
        
    Returns:
        Parser instance or None if format not supported
    """
    extension = BaseParser.get_file_extension(filename)
    
    parser_map = {
        'txt': TxtParser(),
        'sql': SqlParser(),
        'md': MdParser(),
        'docx': DocxParser(),
        'pdf': PdfParser(),
        'xlsx': XlsxParser(),
        'doc': DocParser(),
    }
    
    return parser_map.get(extension)
