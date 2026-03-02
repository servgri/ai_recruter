"""Database utilities for SQLite."""

import os
import sqlite3
import json
import csv
from typing import Dict, List, Optional
from datetime import datetime


class Database:
    """Database handler for SQLite."""
    
    def __init__(self, db_path: str = "data.db"):
        """
        Initialize database.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.init_db()
    
    def _get_connection(self):
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_db(self):
        """Initialize database schema."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_filename TEXT NOT NULL,
                filename TEXT NOT NULL,
                type TEXT NOT NULL,
                task_1 TEXT,
                task_2 TEXT,
                task_3 TEXT,
                task_4 TEXT,
                content TEXT,
                task_1_tails TEXT,
                task_2_tails TEXT,
                task_3_tails TEXT,
                task_4_tails TEXT,
                tasks_count INTEGER,
                cleaning_status TEXT,
                embedding_task_1 TEXT,
                embedding_task_2 TEXT,
                embedding_task_3 TEXT,
                embedding_task_4 TEXT,
                embedding_content TEXT,
                embedding_method TEXT,
                similarity_with_reference TEXT,
                similarity_with_existing TEXT,
                cheating_score TEXT,
                analysis_report TEXT,
                task_1_score REAL,
                task_2_score REAL,
                task_3_score REAL,
                task_4_score REAL,
                task_1_comment_student TEXT,
                task_2_comment_student TEXT,
                task_3_comment_student TEXT,
                task_4_comment_student TEXT,
                task_1_llm_comment TEXT,
                task_2_llm_comment TEXT,
                task_3_llm_comment TEXT,
                task_4_llm_comment TEXT,
                task_4_logic_score REAL,
                task_4_originality_score REAL,
                average_score_tasks_1_3 REAL,
                file_hash TEXT,
                report_generated INTEGER DEFAULT 0,
                processing_status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_filename ON documents(filename)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_processing_status ON documents(processing_status)
        """)
        
        conn.commit()
        conn.close()
        
        # Migrate existing tables to add new columns
        self._migrate_add_grading_columns()
        
        # Create index on file_hash after migration (if column exists)
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_file_hash ON documents(file_hash)
            """)
            conn.commit()
        except sqlite3.OperationalError:
            # Index might fail if column doesn't exist yet, that's OK
            pass
        conn.close()
    
    def _migrate_add_grading_columns(self):
        """Add grading columns to existing database if they don't exist."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Get existing columns
        cursor.execute("PRAGMA table_info(documents)")
        existing_columns = [row[1] for row in cursor.fetchall()]
        
        # Columns to add
        grading_columns = [
            ('task_1_score', 'REAL'),
            ('task_2_score', 'REAL'),
            ('task_3_score', 'REAL'),
            ('task_4_score', 'REAL'),
            ('task_1_comment_student', 'TEXT'),
            ('task_2_comment_student', 'TEXT'),
            ('task_3_comment_student', 'TEXT'),
            ('task_4_comment_student', 'TEXT'),
            ('task_1_llm_comment', 'TEXT'),
            ('task_2_llm_comment', 'TEXT'),
            ('task_3_llm_comment', 'TEXT'),
            ('task_4_llm_comment', 'TEXT'),
            ('task_4_logic_score', 'REAL'),
            ('task_4_originality_score', 'REAL'),
            ('average_score_tasks_1_3', 'REAL'),
            ('file_hash', 'TEXT'),
            ('report_generated', 'INTEGER'),
            ('approved', 'INTEGER DEFAULT 0'),
            ('candidate_status', 'TEXT DEFAULT "unread"'),
            ('messages_sent', 'INTEGER DEFAULT 0'),
            ('overall_impression', 'TEXT'),
            ('task_1_images', 'TEXT'),
            ('task_2_images', 'TEXT'),
            ('task_3_images', 'TEXT'),
            ('task_4_images', 'TEXT'),
            ('eval_v6_results', 'TEXT'),
            ('criteria_overrides', 'TEXT')
        ]
        
        # Add missing columns
        for col_name, col_type in grading_columns:
            if col_name not in existing_columns:
                try:
                    cursor.execute(f"ALTER TABLE documents ADD COLUMN {col_name} {col_type}")
                except sqlite3.OperationalError as e:
                    # Column might already exist or other error
                    print(f"Warning: Could not add column {col_name}: {e}")
        
        conn.commit()
        conn.close()
    
    def save_document(self, filename: str, file_type: str, content: str, 
                     tasks: List[Dict], processing_status: str = 'pending', 
                     file_hash: Optional[str] = None) -> int:
        """
        Save document to database.
        
        Args:
            filename: Original filename
            file_type: File extension/type
            content: Full text content
            tasks: List of extracted tasks
            processing_status: Status of processing
            
        Returns:
            Document ID
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        filename_no_ext = os.path.splitext(filename)[0] if '.' in filename else filename
        
        # Create dictionary mapping task_number to content
        task_dict = {task.get('task_number', i+1): task.get('content', '') 
                    for i, task in enumerate(tasks)}
        
        # Get tasks by their actual numbers
        task_1 = task_dict.get(1, '')
        task_2 = task_dict.get(2, '')
        task_3 = task_dict.get(3, '')
        task_4 = task_dict.get(4, '')
        
        # Count non-empty tasks
        non_empty_tasks = [task for task in tasks if task.get('content', '').strip()]
        tasks_count = len(non_empty_tasks)
        
        cursor.execute("""
            INSERT INTO documents (
                full_filename, filename, type, task_1, task_2, task_3, task_4, content,
                tasks_count, cleaning_status, processing_status, file_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            filename, filename_no_ext, file_type,
            task_1, task_2, task_3, task_4, content,
            tasks_count,
            'validated' if tasks_count == 2 else ('cleaned' if tasks_count == 4 else 'partial'),
            processing_status,
            file_hash or None
        ))
        
        doc_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return doc_id
    
    def update_document(self, doc_id: int, **kwargs) -> bool:
        """
        Update document fields.
        
        Args:
            doc_id: Document ID
            **kwargs: Fields to update
            
        Returns:
            True if updated successfully
        """
        if not kwargs:
            return False
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Build update query
        set_clauses = []
        values = []
        
        for key, value in kwargs.items():
            if key in ['task_1_tails', 'task_2_tails', 'task_3_tails', 'task_4_tails',
                      'embedding_task_1', 'embedding_task_2', 'embedding_task_3', 
                      'embedding_task_4', 'embedding_content',
                      'similarity_with_reference', 'similarity_with_existing',
                      'cheating_score', 'analysis_report']:
                # Convert to JSON string if it's a dict/list
                if value is None:
                    value = ''
                elif isinstance(value, (dict, list)):
                    value = json.dumps(value, ensure_ascii=False)
                elif not isinstance(value, str):
                    # If it's already a string (JSON), keep it; otherwise convert
                    value = str(value)
            set_clauses.append(f"{key} = ?")
            values.append(value)
        
        set_clauses.append("updated_at = CURRENT_TIMESTAMP")
        values.append(doc_id)
        
        query = f"UPDATE documents SET {', '.join(set_clauses)} WHERE id = ?"
        cursor.execute(query, values)
        
        conn.commit()
        updated = cursor.rowcount > 0
        conn.close()
        
        return updated
    
    def approve_document(self, doc_id: int) -> bool:
        """Approve a document."""
        return self.update_document(doc_id, approved=1)
    
    def block_document(self, doc_id: int) -> bool:
        """Block a document by setting processing_status to 'error'."""
        return self.update_document(doc_id, processing_status='error')
    
    def unblock_document(self, doc_id: int) -> bool:
        """Unblock a document by setting processing_status to 'completed'."""
        return self.update_document(doc_id, processing_status='completed')
    
    def delete_document(self, doc_id: int) -> bool:
        """Delete a document by ID."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
        conn.commit()
        deleted = cursor.rowcount > 0
        conn.close()
        return deleted
    
    def batch_approve_documents(self, doc_ids: List[int]) -> int:
        """Approve multiple documents."""
        if not doc_ids:
            return 0
        conn = self._get_connection()
        cursor = conn.cursor()
        placeholders = ','.join('?' * len(doc_ids))
        cursor.execute(f"UPDATE documents SET approved = 1, updated_at = CURRENT_TIMESTAMP WHERE id IN ({placeholders})", doc_ids)
        conn.commit()
        count = cursor.rowcount
        conn.close()
        return count
    
    def batch_unapprove_documents(self, doc_ids: List[int]) -> int:
        """Unapprove multiple documents."""
        if not doc_ids:
            return 0
        conn = self._get_connection()
        cursor = conn.cursor()
        placeholders = ','.join('?' * len(doc_ids))
        cursor.execute(f"UPDATE documents SET approved = 0, updated_at = CURRENT_TIMESTAMP WHERE id IN ({placeholders})", doc_ids)
        conn.commit()
        count = cursor.rowcount
        conn.close()
        return count
    
    def batch_block_documents(self, doc_ids: List[int]) -> int:
        """Block multiple documents."""
        if not doc_ids:
            return 0
        conn = self._get_connection()
        cursor = conn.cursor()
        placeholders = ','.join('?' * len(doc_ids))
        cursor.execute(f"UPDATE documents SET processing_status = 'error', updated_at = CURRENT_TIMESTAMP WHERE id IN ({placeholders})", doc_ids)
        conn.commit()
        count = cursor.rowcount
        conn.close()
        return count
    
    def batch_unblock_documents(self, doc_ids: List[int]) -> int:
        """Unblock multiple documents."""
        if not doc_ids:
            return 0
        conn = self._get_connection()
        cursor = conn.cursor()
        placeholders = ','.join('?' * len(doc_ids))
        cursor.execute(f"UPDATE documents SET processing_status = 'completed', updated_at = CURRENT_TIMESTAMP WHERE id IN ({placeholders})", doc_ids)
        conn.commit()
        count = cursor.rowcount
        conn.close()
        return count
    
    def batch_delete_documents(self, doc_ids: List[int]) -> int:
        """Delete multiple documents."""
        if not doc_ids:
            return 0
        conn = self._get_connection()
        cursor = conn.cursor()
        placeholders = ','.join('?' * len(doc_ids))
        cursor.execute(f"DELETE FROM documents WHERE id IN ({placeholders})", doc_ids)
        conn.commit()
        count = cursor.rowcount
        conn.close()
        return count
    
    def find_document_by_hash(self, file_hash: str) -> Optional[Dict]:
        """
        Find document by file hash.
        
        Args:
            file_hash: SHA256 hash of file content
            
        Returns:
            Document dictionary or None
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM documents WHERE file_hash = ? LIMIT 1", (file_hash,))
        row = cursor.fetchone()
        conn.close()
        
        return dict(row) if row else None
    
    def get_document(self, doc_id: int) -> Optional[Dict]:
        """
        Get document by ID.
        
        Args:
            doc_id: Document ID
            
        Returns:
            Document dictionary or None
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM documents WHERE id = ?", (doc_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return dict(row)
        return None
    
    def get_all_documents(self, limit: Optional[int] = None, 
                         offset: Optional[int] = None) -> List[Dict]:
        """
        Get all documents.
        
        Args:
            limit: Maximum number of documents
            offset: Offset for pagination
            
        Returns:
            List of document dictionaries
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        query = "SELECT * FROM documents ORDER BY created_at DESC"
        params = []
        
        if limit:
            query += " LIMIT ?"
            params.append(limit)
        if offset:
            query += " OFFSET ?"
            params.append(offset)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def update_document_status(self, doc_id: int, status: str) -> bool:
        """
        Update processing status.
        
        Args:
            doc_id: Document ID
            status: New status ('pending', 'processing', 'completed', 'error')
            
        Returns:
            True if updated successfully
        """
        return self.update_document(doc_id, processing_status=status)
    
    def sync_from_csv(self, csv_path: str = "") -> int:
        """
        Migrate data from CSV to database (one-time migration).
        
        Args:
            csv_path: Path to CSV file (empty = disabled)
            
        Returns:
            Number of records imported
        """
        if not csv_path or not os.path.exists(csv_path):
            return 0
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        imported = 0
        
        try:
            with open(csv_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                
                for row in reader:
                    # Check if document already exists
                    cursor.execute(
                        "SELECT id FROM documents WHERE full_filename = ?",
                        (row.get('full_filename', ''),)
                    )
                    if cursor.fetchone():
                        continue  # Skip if already exists
                    
                    # Insert document
                    cursor.execute("""
                        INSERT INTO documents (
                            full_filename, filename, type, task_1, task_2, task_3, task_4, content,
                            task_1_tails, task_2_tails, task_3_tails, task_4_tails,
                            tasks_count, cleaning_status,
                            embedding_task_1, embedding_task_2, embedding_task_3, 
                            embedding_task_4, embedding_content, embedding_method,
                            similarity_with_reference, similarity_with_existing,
                            cheating_score, analysis_report,
                            processing_status
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        row.get('full_filename', ''),
                        row.get('filename', ''),
                        row.get('type', ''),
                        row.get('task_1', ''),
                        row.get('task_2', ''),
                        row.get('task_3', ''),
                        row.get('task_4', ''),
                        row.get('content', ''),
                        row.get('task_1_tails', ''),
                        row.get('task_2_tails', ''),
                        row.get('task_3_tails', ''),
                        row.get('task_4_tails', ''),
                        row.get('tasks_count', ''),
                        row.get('cleaning_status', ''),
                        row.get('embedding_task_1', ''),
                        row.get('embedding_task_2', ''),
                        row.get('embedding_task_3', ''),
                        row.get('embedding_task_4', ''),
                        row.get('embedding_content', ''),
                        row.get('embedding_method', ''),
                        row.get('similarity_with_reference', ''),
                        row.get('similarity_with_existing', ''),
                        row.get('cheating_score', ''),
                        row.get('analysis_report', ''),
                        'completed'  # Migrated documents are considered completed
                    ))
                    imported += 1
                
                conn.commit()
        except Exception as e:
            print(f"Error migrating CSV: {str(e)}")
            conn.rollback()
        finally:
            conn.close()
        
        return imported
