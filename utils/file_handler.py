"""File handling utilities."""

import os
import json
import csv
from datetime import datetime
from typing import Optional, Dict
from pathlib import Path

from parsers import (
    TxtParser, PdfParser, DocxParser, MdParser, SqlParser, 
    XlsxParser, DocParser, BaseParser
)


class FileHandler:
    """Handles file operations and JSON saving."""
    
    def __init__(self, output_dir: str = "data_loaded", problem_dir: str = "problem", 
                 csv_dir: str = "data_loaded", csv_file: str = "loaded_data.csv", problem_csv_file: str = "problem.csv"):
        """
        Initialize FileHandler.
        
        Args:
            output_dir: Directory to save JSON files
            problem_dir: Directory to save problem files
            csv_dir: Directory to save CSV file for successfully recognized files
            csv_file: Name of main CSV file for exports
            problem_csv_file: Path to problem CSV file
        """
        self.output_dir = output_dir
        self.problem_dir = problem_dir
        self.csv_dir = csv_dir
        # Ensure CSV directory exists
        os.makedirs(self.csv_dir, exist_ok=True)
        self.csv_file = os.path.join(csv_dir, csv_file)
        self.problem_csv_file = os.path.join(problem_dir, problem_csv_file)
        self._ensure_output_dir()
        self._ensure_problem_dir()
        self._init_csv_files()
    
    def _ensure_output_dir(self):
        """Create output directory if it doesn't exist."""
        os.makedirs(self.output_dir, exist_ok=True)
    
    def _ensure_problem_dir(self):
        """Create problem directories if they don't exist."""
        os.makedirs(os.path.join(self.problem_dir, "original_files"), exist_ok=True)
        os.makedirs(os.path.join(self.problem_dir, "problem_reports"), exist_ok=True)
    
    def _init_csv_files(self):
        """Initialize CSV files with headers if they don't exist or have wrong format."""
        # Main CSV format (extended with embeddings, cleaning, analysis)
        main_fieldnames = [
            'full_filename', 'filename', 'type', 'task_1', 'task_2', 'task_3', 'task_4', 'content',
            'task_1_tails', 'task_2_tails', 'task_3_tails', 'task_4_tails',
            'tasks_count', 'cleaning_status',
            'embedding_task_1', 'embedding_task_2', 'embedding_task_3', 'embedding_task_4', 'embedding_content',
            'embedding_method',
            'similarity_with_reference', 'similarity_with_existing',
            'cheating_score', 'analysis_report'
        ]
        
        # Problem CSV format (with tasks_count and comment)
        problem_fieldnames = ['full_filename', 'filename', 'type', 'tasks_count', 'task_1', 'task_2', 'task_3', 'task_4', 'content', 'comment']
        
        # Initialize main CSV file
        if not os.path.exists(self.csv_file):
            with open(self.csv_file, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=main_fieldnames)
                writer.writeheader()
        else:
            # Check if file has correct headers (only check, don't recreate if data exists)
            try:
                with open(self.csv_file, 'r', encoding='utf-8-sig') as f:
                    reader = csv.DictReader(f)
                    existing_headers = set(reader.fieldnames or [])
                    if existing_headers != set(main_fieldnames):
                        # Only recreate if file is empty or has wrong format
                        # Read first line to check if there's data
                        f.seek(0)
                        lines = f.readlines()
                        if len(lines) <= 1:  # Only header or empty
                            with open(self.csv_file, 'w', newline='', encoding='utf-8-sig') as fw:
                                writer = csv.DictWriter(fw, fieldnames=main_fieldnames)
                                writer.writeheader()
            except Exception:
                # If error reading, try to recreate only if file seems empty
                try:
                    with open(self.csv_file, 'r', encoding='utf-8-sig') as f:
                        if len(f.read().strip()) == 0:
                            with open(self.csv_file, 'w', newline='', encoding='utf-8-sig') as fw:
                                writer = csv.DictWriter(fw, fieldnames=main_fieldnames)
                                writer.writeheader()
                except Exception:
                    pass  # If can't read, assume it's fine and let append handle it
        
        # Initialize problem CSV file
        if not os.path.exists(self.problem_csv_file):
            with open(self.problem_csv_file, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=problem_fieldnames)
                writer.writeheader()
        else:
            # Check if file has correct headers (only check, don't recreate if data exists)
            try:
                with open(self.problem_csv_file, 'r', encoding='utf-8-sig') as f:
                    reader = csv.DictReader(f)
                    existing_headers = set(reader.fieldnames or [])
                    if existing_headers != set(problem_fieldnames):
                        # Only recreate if file is empty or has wrong format
                        # Read first line to check if there's data
                        f.seek(0)
                        lines = f.readlines()
                        if len(lines) <= 1:  # Only header or empty
                            with open(self.problem_csv_file, 'w', newline='', encoding='utf-8-sig') as fw:
                                writer = csv.DictWriter(fw, fieldnames=problem_fieldnames)
                                writer.writeheader()
            except Exception:
                # If error reading, try to recreate only if file seems empty
                try:
                    with open(self.problem_csv_file, 'r', encoding='utf-8-sig') as f:
                        if len(f.read().strip()) == 0:
                            with open(self.problem_csv_file, 'w', newline='', encoding='utf-8-sig') as fw:
                                writer = csv.DictWriter(fw, fieldnames=problem_fieldnames)
                                writer.writeheader()
                except Exception:
                    pass  # If can't read, assume it's fine and let append handle it
    
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
    
    def append_to_problem_csv(self, filename: str, file_type: str, content: str, 
                             tasks: list, problem_details: Dict) -> str:
        """
        Append a record to the problem CSV file.
        Recognized tasks go to their columns, error info goes to comment column.
        
        Args:
            filename: Original filename
            file_type: File extension/type
            content: Full text content
            tasks: List of extracted tasks
            problem_details: Dictionary with problem information
            
        Returns:
            Path to problem CSV file
        """
        # Ensure problem directory exists
        os.makedirs(self.problem_dir, exist_ok=True)
        
        fieldnames = ['full_filename', 'filename', 'type', 'tasks_count', 'task_1', 'task_2', 'task_3', 'task_4', 'content', 'comment']
        
        full_filename = filename
        filename_no_ext = os.path.splitext(full_filename)[0] if '.' in full_filename else full_filename
        
        problem_reason = problem_details.get('problem_reason', 'Не удалось распознать задание')
        tasks_found = problem_details.get('tasks_found', 0)
        
        # Count non-empty tasks
        non_empty_tasks = [task for task in tasks if task.get('content', '').strip()]
        tasks_count = len(non_empty_tasks)
        
        # Create dictionary mapping task_number to content
        task_dict = {task.get('task_number', i+1): task.get('content', '') for i, task in enumerate(tasks)}
        
        # Get tasks by their actual numbers (not by order in list)
        task_1 = task_dict.get(1, '')
        task_2 = task_dict.get(2, '')
        task_3 = task_dict.get(3, '')
        task_4 = task_dict.get(4, '')
        
        # Only include recognized tasks (non-empty), leave empty for missing ones
        # Don't add problem comments to task columns - put them in comment column
        
        row = {
            'full_filename': full_filename,
            'filename': filename_no_ext,
            'type': file_type,
            'tasks_count': tasks_count,
            'task_1': self._clean_text(task_1) if task_1.strip() else '',
            'task_2': self._clean_text(task_2) if task_2.strip() else '',
            'task_3': self._clean_text(task_3) if task_3.strip() else '',
            'task_4': self._clean_text(task_4) if task_4.strip() else '',
            'content': self._clean_text(content),
            'comment': problem_reason
        }
        
        # Append to problem CSV file
        with open(self.problem_csv_file, 'a', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writerow(row)
        
        return self.problem_csv_file
    
    def save_to_json(self, filename: str, file_type: str, content: str, tasks: list) -> str:
        """
        Save parsed content to JSON file.
        
        Args:
            filename: Original filename
            file_type: File extension/type
            content: Full text content
            tasks: List of extracted tasks
            
        Returns:
            Path to saved JSON file
        """
        output_data = {
            "filename": filename,
            "file_type": file_type,
            "content": content,
            "tasks": tasks,
            "parsed_at": datetime.now().isoformat()
        }
        
        # Create JSON filename from original filename
        base_name = os.path.splitext(filename)[0]
        json_filename = f"{base_name}.json"
        json_path = os.path.join(self.output_dir, json_filename)
        
        # Save JSON file
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        
        return json_path
    
    def save_problem_file(self, file_path: str, filename: str) -> str:
        """
        Save original file to problem directory.
        
        Args:
            file_path: Path to the original file
            filename: Original filename
            
        Returns:
            Path to saved file in problem directory
        """
        # Ensure problem directories exist before saving
        self._ensure_problem_dir()
        
        problem_file_path = os.path.join(self.problem_dir, "original_files", filename)
        
        # Copy file
        import shutil
        shutil.copy2(file_path, problem_file_path)
        
        return problem_file_path
    
    def save_problem_json(self, filename: str, file_type: str, content: str, 
                         tasks: list, problem_details: dict) -> str:
        """
        Save problem report JSON file.
        
        Args:
            filename: Original filename
            file_type: File extension/type
            content: Full text content
            tasks: List of extracted tasks
            problem_details: Dictionary with problem information
            
        Returns:
            Path to saved JSON file
        """
        # Ensure problem directories exist before saving
        self._ensure_problem_dir()
        
        output_data = {
            "filename": filename,
            "file_type": file_type,
            "content": content,
            "tasks": tasks,
            "parsed_at": datetime.now().isoformat(),
            "has_problems": True,
            "problem_details": problem_details
        }
        
        # Create JSON filename from original filename
        base_name = os.path.splitext(filename)[0]
        json_filename = f"{base_name}.json"
        json_path = os.path.join(self.problem_dir, "problem_reports", json_filename)
        
        # Save JSON file
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        
        return json_path


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
