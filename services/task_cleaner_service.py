"""Task cleaner service for detecting and redistributing task tails."""

import os
import json
import re
import requests
from typing import List, Dict, Optional, Tuple
from flask import Blueprint, request, jsonify

from services.config import (
    HF_API_TOKEN, HF_API_BASE_URL, API_PRIORITY,
    TAIL_DETECTION_SIMILARITY_THRESHOLD, TAIL_DETECTION_MIN_LENGTH
)
from services.embedding_service import get_embedder
from utils.embedding_utils import cosine_similarity_vectors

cleaner_bp = Blueprint('cleaner', __name__, url_prefix='/cleaner')


class TaskCleaner:
    """Cleans tasks by detecting and redistributing tails."""
    
    def __init__(self):
        self.similarity_threshold = TAIL_DETECTION_SIMILARITY_THRESHOLD
        self.min_length = TAIL_DETECTION_MIN_LENGTH
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """Split text into sentences."""
        # Simple sentence splitting
        sentences = re.split(r'[.!?]\s+', text)
        return [s.strip() for s in sentences if s.strip()]
    
    def _split_into_paragraphs(self, text: str) -> List[str]:
        """Split text into paragraphs."""
        paragraphs = re.split(r'\n\s*\n', text)
        return [p.strip() for p in paragraphs if p.strip() and len(p.strip()) >= self.min_length]
    
    def detect_tails_qwen(self, tasks: Dict[int, str], use_api: Optional[bool] = None) -> Dict[int, List[Dict]]:
        """
        Detect tails using QWEN via API or local model.
        
        Args:
            tasks: Dictionary mapping task number to task text
            use_api: Whether to use API (None = use config)
            
        Returns:
            Dictionary mapping task number to list of detected tails
        """
        tails = {task_num: [] for task_num in tasks.keys()}
        
        if use_api is None:
            use_api = API_PRIORITY == "api_first"
        
        # For each task, analyze if it contains fragments from other tasks
        for task_num, task_text in tasks.items():
            if not task_text or len(task_text.strip()) < 20:
                continue
            
            # Create prompt for QWEN
            other_tasks = {k: v for k, v in tasks.items() if k != task_num}
            other_tasks_text = "\n".join([f"Задание {k}:\n{v[:200]}..." for k, v in other_tasks.items()])
            
            prompt = f"""Проанализируй задание {task_num} и определи, содержит ли оно фрагменты текста, относящиеся к другим заданиям.

Задание {task_num}:
{task_text[:1000]}

Другие задания:
{other_tasks_text}

Определи, есть ли в задании {task_num} фрагменты, которые относятся к другим заданиям (1-4). Если да, выдели эти фрагменты и укажи к какому заданию они относятся.

Ответ в формате JSON:
{{
    "has_tails": true/false,
    "tails": [
        {{"text": "фрагмент текста", "belongs_to_task": 2}},
        ...
    ]
}}"""
            
            if use_api:
                result = self._query_qwen_api(prompt)
            else:
                result = self._query_qwen_local(prompt)
            
            if result and result.get('has_tails'):
                tails[task_num] = result.get('tails', [])
        
        return tails
    
    def _query_qwen_api(self, prompt: str) -> Optional[Dict]:
        """Query QWEN via HF API."""
        if not HF_API_TOKEN:
            return None
        
        try:
            headers = {"Authorization": f"Bearer {HF_API_TOKEN}"}
            payload = {
                "inputs": prompt,
                "parameters": {
                    "max_new_tokens": 500,
                    "return_full_text": False
                }
            }
            
            response = requests.post(
                f"{HF_API_BASE_URL}/Qwen/Qwen2.5-0.5B-Instruct",
                headers=headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                if isinstance(result, list) and len(result) > 0:
                    text = result[0].get('generated_text', '')
                    # Try to extract JSON from response
                    json_match = re.search(r'\{[^}]+\}', text, re.DOTALL)
                    if json_match:
                        try:
                            return json.loads(json_match.group())
                        except json.JSONDecodeError:
                            pass
            elif response.status_code == 503:
                import time
                time.sleep(5)
                response = requests.post(
                    f"{HF_API_BASE_URL}/Qwen/Qwen2.5-0.5B-Instruct",
                    headers=headers,
                    json=payload,
                    timeout=60
                )
                if response.status_code == 200:
                    result = response.json()
                    if isinstance(result, list) and len(result) > 0:
                        text = result[0].get('generated_text', '')
                        json_match = re.search(r'\{[^}]+\}', text, re.DOTALL)
                        if json_match:
                            try:
                                return json.loads(json_match.group())
                            except json.JSONDecodeError:
                                pass
            
            return None
        except Exception as e:
            print(f"QWEN API error: {str(e)}")
            return None
    
    def _query_qwen_local(self, prompt: str) -> Optional[Dict]:
        """Query QWEN local model."""
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer
            import torch
            
            model_name = "Qwen/Qwen2.5-0.5B-Instruct"
            model_path = os.path.join("models", model_name.replace('/', '_'))
            
            try:
                tokenizer = AutoTokenizer.from_pretrained(model_path)
                model = AutoModelForCausalLM.from_pretrained(model_path)
            except:
                tokenizer = AutoTokenizer.from_pretrained(model_name)
                model = AutoModelForCausalLM.from_pretrained(model_name)
            
            inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=1024)
            
            with torch.no_grad():
                outputs = model.generate(
                    **inputs,
                    max_new_tokens=500,
                    temperature=0.7,
                    do_sample=True
                )
            
            generated_text = tokenizer.decode(outputs[0], skip_special_tokens=True)
            # Extract JSON from response
            json_match = re.search(r'\{[^}]+\}', generated_text, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except json.JSONDecodeError:
                    pass
            
            return None
        except Exception as e:
            print(f"QWEN local error: {str(e)}")
            return None
    
    def detect_tails_sbert(self, tasks: Dict[int, str]) -> Dict[int, List[Dict]]:
        """
        Detect tails using SBERT semantic similarity.
        
        Args:
            tasks: Dictionary mapping task number to task text
            
        Returns:
            Dictionary mapping task number to list of detected tails
        """
        tails = {task_num: [] for task_num in tasks.keys()}
        
        # Get embedder
        embedder = get_embedder("sbert", use_api=API_PRIORITY == "api_first")
        
        # Generate embeddings for full tasks
        task_texts = [tasks.get(i, '') for i in range(1, 5)]
        task_embeddings = embedder.embed(task_texts)
        
        # For each task, split into fragments and check similarity
        for task_num, task_text in tasks.items():
            if not task_text or len(task_text.strip()) < 20:
                continue
            
            # Split task into fragments (sentences or paragraphs)
            fragments = self._split_into_paragraphs(task_text)
            if len(fragments) < 2:
                fragments = self._split_into_sentences(task_text)
            
            # Generate embeddings for fragments
            fragment_embeddings = embedder.embed(fragments)
            
            # Compare each fragment with other tasks
            task_idx = task_num - 1
            for frag_idx, fragment in enumerate(fragments):
                if len(fragment) < self.min_length:
                    continue
                
                frag_emb = fragment_embeddings[frag_idx]
                max_similarity = 0.0
                best_match_task = None
                
                # Compare with other tasks
                for other_task_num in range(1, 5):
                    if other_task_num == task_num:
                        continue
                    
                    other_task_idx = other_task_num - 1
                    other_task_emb = task_embeddings[other_task_idx]
                    
                    similarity = cosine_similarity_vectors(frag_emb, other_task_emb)
                    
                    if similarity > max_similarity:
                        max_similarity = similarity
                        best_match_task = other_task_num
                
                # If fragment is more similar to another task, it's a tail
                if max_similarity > self.similarity_threshold and best_match_task:
                    tails[task_num].append({
                        'text': fragment,
                        'belongs_to_task': best_match_task,
                        'similarity': max_similarity
                    })
        
        return tails
    
    def redistribute_tails(self, tasks: Dict[int, str], tails: Dict[int, List[Dict]]) -> Tuple[Dict[int, str], Dict[int, List[str]]]:
        """
        Redistribute tails to correct tasks.
        
        Args:
            tasks: Original tasks
            tails: Detected tails
            
        Returns:
            Tuple of (cleaned_tasks, task_tails_dict)
        """
        cleaned_tasks = tasks.copy()
        task_tails = {i: [] for i in range(1, 5)}
        
        # For each task, remove tails and add them to target tasks
        for task_num, tail_list in tails.items():
            if not tail_list:
                continue
            
            task_text = cleaned_tasks.get(task_num, '')
            
            for tail_info in tail_list:
                tail_text = tail_info.get('text', '')
                belongs_to = tail_info.get('belongs_to_task')
                
                if belongs_to and 1 <= belongs_to <= 4:
                    # Remove tail from source task
                    task_text = task_text.replace(tail_text, '').strip()
                    
                    # Add to target task tails
                    task_tails[belongs_to].append(tail_text)
            
            cleaned_tasks[task_num] = task_text
        
        return cleaned_tasks, task_tails
    
    def validate_task_count(self, tasks: Dict[int, str]) -> Tuple[int, str]:
        """
        Validate task count.
        
        Args:
            tasks: Dictionary of tasks
            
        Returns:
            Tuple of (tasks_count, cleaning_status)
        """
        non_empty_tasks = {k: v for k, v in tasks.items() if v and v.strip()}
        tasks_count = len(non_empty_tasks)
        
        if tasks_count == 2:
            status = "validated"
        elif tasks_count == 3:
            status = "partial"
        elif tasks_count == 4:
            status = "cleaned"
        else:
            status = "partial"
        
        return tasks_count, status
    
    def clean_tasks(self, tasks: Dict[int, str], method: str = "both", use_api: Optional[bool] = None) -> Dict:
        """
        Main method to clean tasks.
        
        Args:
            tasks: Dictionary mapping task number to task text
            method: "qwen", "sbert", or "both"
            use_api: Whether to use API (None = use config)
            
        Returns:
            Dictionary with cleaned tasks and metadata
        """
        # Detect tails
        tails = {}
        
        if method in ["qwen", "both"]:
            qwen_tails = self.detect_tails_qwen(tasks, use_api)
            # Merge tails
            for task_num, tail_list in qwen_tails.items():
                if task_num not in tails:
                    tails[task_num] = []
                tails[task_num].extend(tail_list)
        
        if method in ["sbert", "both"]:
            sbert_tails = self.detect_tails_sbert(tasks)
            # Merge tails (avoid duplicates)
            for task_num, tail_list in sbert_tails.items():
                if task_num not in tails:
                    tails[task_num] = []
                # Check for duplicates
                existing_texts = {t.get('text', '') for t in tails[task_num]}
                for tail in tail_list:
                    if tail.get('text', '') not in existing_texts:
                        tails[task_num].append(tail)
        
        # Redistribute tails
        cleaned_tasks, task_tails = self.redistribute_tails(tasks, tails)
        
        # Validate task count
        tasks_count, cleaning_status = self.validate_task_count(cleaned_tasks)
        
        return {
            'cleaned_tasks': cleaned_tasks,
            'task_tails': task_tails,
            'tasks_count': tasks_count,
            'cleaning_status': cleaning_status,
            'tails_detected': sum(len(v) for v in tails.values())
        }


@cleaner_bp.route('/clean-tasks', methods=['POST'])
def clean_tasks():
    """
    Clean tasks for a document.
    
    Expected JSON:
    {
        "filename": "example.docx",
        "method": "both",  # "qwen", "sbert", or "both"
        "use_api": true  # optional
    }
    """
    data = request.get_json() or {}
    filename = data.get('filename')
    method = data.get('method', 'both')
    use_api = data.get('use_api')
    
    if not filename:
        return jsonify({
            'error': 'filename is required',
            'status': 'error'
        }), 400
    
    try:
        from utils.database import Database
        db = Database()
        doc = db.get_document_by_filename(filename)
        if not doc:
            return jsonify({
                'error': 'Document not found',
                'status': 'error'
            }), 404

        tasks_data = {
            1: doc.get('task_1') or '',
            2: doc.get('task_2') or '',
            3: doc.get('task_3') or '',
            4: doc.get('task_4') or ''
        }
        cleaner = TaskCleaner()
        result = cleaner.clean_tasks(tasks_data, method, use_api)
        db.update_document(
            doc['id'],
            task_1=result['cleaned_tasks'].get(1, ''),
            task_2=result['cleaned_tasks'].get(2, ''),
            task_3=result['cleaned_tasks'].get(3, ''),
            task_4=result['cleaned_tasks'].get(4, ''),
            task_1_tails=json.dumps(result['task_tails'].get(1, []), ensure_ascii=False),
            task_2_tails=json.dumps(result['task_tails'].get(2, []), ensure_ascii=False),
            task_3_tails=json.dumps(result['task_tails'].get(3, []), ensure_ascii=False),
            task_4_tails=json.dumps(result['task_tails'].get(4, []), ensure_ascii=False),
            tasks_count=str(result['tasks_count']),
            cleaning_status=result['cleaning_status']
        )
        return jsonify({
            'status': 'success',
            'filename': filename,
            'method': method,
            'tasks_count': result['tasks_count'],
            'cleaning_status': result['cleaning_status'],
            'tails_detected': result['tails_detected']
        }), 200
    
    except Exception as e:
        return jsonify({
            'error': f'Error cleaning tasks: {str(e)}',
            'status': 'error'
        }), 500


def _safe_json_tails(s, default=None):
    if default is None:
        default = []
    if not s or not isinstance(s, str):
        return default
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        return default


@cleaner_bp.route('/status/<filename>', methods=['GET'])
def get_cleaning_status(filename: str):
    """Get cleaning status for a file."""
    try:
        from utils.database import Database
        db = Database()
        doc = db.get_document_by_filename(filename)
        if not doc:
            return jsonify({
                'error': 'Document not found',
                'status': 'error'
            }), 404
        return jsonify({
            'status': 'success',
            'filename': filename,
            'tasks_count': doc.get('tasks_count', ''),
            'cleaning_status': doc.get('cleaning_status', ''),
            'task_tails': {
                'task_1': _safe_json_tails(doc.get('task_1_tails')),
                'task_2': _safe_json_tails(doc.get('task_2_tails')),
                'task_3': _safe_json_tails(doc.get('task_3_tails')),
                'task_4': _safe_json_tails(doc.get('task_4_tails'))
            }
        }), 200
    
    except Exception as e:
        return jsonify({
            'error': f'Error retrieving status: {str(e)}',
            'status': 'error'
        }), 500
