"""Embedding service with SBERT and QWEN support."""

import os
import json
import requests
from typing import List, Optional, Dict
from flask import Blueprint, request, jsonify

from services.config import (
    HF_API_TOKEN, HF_API_BASE_URL, API_PRIORITY,
    SBERT_MODEL_NAME, SBERT_MODEL_NAME_API,
    QWEN_MODEL_NAME, QWEN_EMBEDDING_MODEL,
    LOCAL_MODELS_DIR
)

embedding_bp = Blueprint('embeddings', __name__, url_prefix='/embeddings')

# Global model instances (lazy loading)
_sbert_model = None
_qwen_model = None
_qwen_tokenizer = None


class SBERTEmbedder:
    """SBERT embedder with API and local support."""
    
    def __init__(self):
        self.api_url = f"{HF_API_BASE_URL}/{SBERT_MODEL_NAME_API}"
        self.local_model = None
        self.use_api = API_PRIORITY == "api_first"
    
    def _load_local_model(self):
        """Lazy load local SBERT model."""
        global _sbert_model
        if _sbert_model is None:
            try:
                from sentence_transformers import SentenceTransformer
                model_path = os.path.join(LOCAL_MODELS_DIR, SBERT_MODEL_NAME.replace('/', '_'))
                if os.path.exists(model_path):
                    _sbert_model = SentenceTransformer(model_path)
                else:
                    _sbert_model = SentenceTransformer(SBERT_MODEL_NAME)
                    _sbert_model.save(model_path)
            except ImportError:
                raise ImportError("sentence-transformers not installed. Install with: pip install sentence-transformers")
        self.local_model = _sbert_model
    
    def _embed_api(self, texts: List[str]) -> Optional[List[List[float]]]:
        """Generate embeddings via HF API."""
        if not HF_API_TOKEN:
            return None
        
        try:
            headers = {"Authorization": f"Bearer {HF_API_TOKEN}"}
            payload = {"inputs": texts}
            
            response = requests.post(
                f"{self.api_url}",
                headers=headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 503:
                # Model is loading, wait and retry
                import time
                time.sleep(5)
                response = requests.post(
                    f"{self.api_url}",
                    headers=headers,
                    json=payload,
                    timeout=60
                )
                if response.status_code == 200:
                    return response.json()
            
            return None
        except Exception as e:
            print(f"API error: {str(e)}")
            return None
    
    def _embed_local(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings using local model."""
        if self.local_model is None:
            self._load_local_model()
        
        embeddings = self.local_model.encode(texts, show_progress_bar=False)
        return embeddings.tolist()
    
    def embed(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for texts.
        
        Args:
            texts: List of text strings
            
        Returns:
            List of embedding vectors
        """
        if self.use_api:
            result = self._embed_api(texts)
            if result is not None:
                return result
            # Fallback to local
            if API_PRIORITY == "api_first":
                print("API failed, falling back to local model")
        
        return self._embed_local(texts)


class QWENEmbedder:
    """QWEN embedder with API and local support."""
    
    def __init__(self):
        self.api_url = f"{HF_API_BASE_URL}/{QWEN_MODEL_NAME}"
        self.local_model = None
        self.local_tokenizer = None
        self.use_api = API_PRIORITY == "api_first"
    
    def _load_local_model(self):
        """Lazy load local QWEN model."""
        global _qwen_model, _qwen_tokenizer
        if _qwen_model is None:
            try:
                from transformers import AutoModel, AutoTokenizer
                import torch
                
                model_path = os.path.join(LOCAL_MODELS_DIR, QWEN_MODEL_NAME.replace('/', '_'))
                if os.path.exists(model_path):
                    _qwen_tokenizer = AutoTokenizer.from_pretrained(model_path)
                    _qwen_model = AutoModel.from_pretrained(model_path)
                else:
                    _qwen_tokenizer = AutoTokenizer.from_pretrained(QWEN_MODEL_NAME)
                    _qwen_model = AutoModel.from_pretrained(QWEN_MODEL_NAME)
                    _qwen_tokenizer.save_pretrained(model_path)
                    _qwen_model.save_pretrained(model_path)
                
                _qwen_model.eval()
            except ImportError:
                raise ImportError("transformers not installed. Install with: pip install transformers torch")
        
        self.local_model = _qwen_model
        self.local_tokenizer = _qwen_tokenizer
    
    def _embed_api(self, texts: List[str]) -> Optional[List[List[float]]]:
        """Generate embeddings via HF API."""
        if not HF_API_TOKEN:
            return None
        
        try:
            headers = {"Authorization": f"Bearer {HF_API_TOKEN}"}
            # For QWEN, we need to use text-generation or feature-extraction endpoint
            # Try feature-extraction first
            payload = {"inputs": texts}
            
            response = requests.post(
                f"{self.api_url}",
                headers=headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                # API may return different formats
                if isinstance(result, list) and len(result) > 0:
                    if isinstance(result[0], list):
                        return result
                    elif isinstance(result[0], dict) and 'embedding' in result[0]:
                        return [item['embedding'] for item in result]
            elif response.status_code == 503:
                import time
                time.sleep(5)
                response = requests.post(
                    f"{self.api_url}",
                    headers=headers,
                    json=payload,
                    timeout=60
                )
                if response.status_code == 200:
                    result = response.json()
                    if isinstance(result, list) and len(result) > 0:
                        if isinstance(result[0], list):
                            return result
                        elif isinstance(result[0], dict) and 'embedding' in result[0]:
                            return [item['embedding'] for item in result]
            
            return None
        except Exception as e:
            print(f"API error: {str(e)}")
            return None
    
    def _embed_local(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings using local model."""
        if self.local_model is None:
            self._load_local_model()
        
        import torch
        
        # Tokenize and encode
        encoded = self.local_tokenizer(
            texts,
            padding=True,
            truncation=True,
            max_length=512,
            return_tensors='pt'
        )
        
        with torch.no_grad():
            outputs = self.local_model(**encoded)
            # Use mean pooling of last hidden state
            embeddings = outputs.last_hidden_state.mean(dim=1)
        
        return embeddings.tolist()
    
    def embed(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for texts.
        
        Args:
            texts: List of text strings
            
        Returns:
            List of embedding vectors
        """
        if self.use_api:
            result = self._embed_api(texts)
            if result is not None:
                return result
            # Fallback to local
            if API_PRIORITY == "api_first":
                print("API failed, falling back to local model")
        
        return self._embed_local(texts)


# Global embedder instances
_sbert_embedder = None
_qwen_embedder = None


def get_embedder(method: str = "sbert", use_api: Optional[bool] = None):
    """
    Get embedder instance.
    
    Args:
        method: "sbert" or "qwen"
        use_api: Override API priority (None = use config)
        
    Returns:
        Embedder instance
    """
    global _sbert_embedder, _qwen_embedder
    
    if method.lower() == "sbert":
        if _sbert_embedder is None:
            _sbert_embedder = SBERTEmbedder()
        embedder = _sbert_embedder
    elif method.lower() == "qwen":
        if _qwen_embedder is None:
            _qwen_embedder = QWENEmbedder()
        embedder = _qwen_embedder
    else:
        raise ValueError(f"Unknown embedding method: {method}")
    
    if use_api is not None:
        embedder.use_api = use_api
    
    return embedder


@embedding_bp.route('/generate', methods=['POST'])
def generate_embeddings():
    """
    Generate embeddings for a document.
    
    Expected JSON:
    {
        "filename": "example.docx",
        "method": "sbert",  # or "qwen"
        "use_api": true  # optional, overrides config
    }
    """
    data = request.get_json() or {}
    filename = data.get('filename')
    method = data.get('method', 'sbert')
    use_api = data.get('use_api')
    
    if not filename:
        return jsonify({
            'error': 'filename is required',
            'status': 'error'
        }), 400
    
    try:
        # Load tasks from CSV
        from utils.file_handler import FileHandler
        file_handler = FileHandler()
        
        # Read CSV to find the file
        import csv
        tasks_data = {}
        content = ""
        
        if os.path.exists(file_handler.csv_file):
            with open(file_handler.csv_file, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get('full_filename') == filename or row.get('filename') == filename:
                        tasks_data = {
                            'task_1': row.get('task_1', ''),
                            'task_2': row.get('task_2', ''),
                            'task_3': row.get('task_3', ''),
                            'task_4': row.get('task_4', '')
                        }
                        content = row.get('content', '')
                        break
        
        if not tasks_data:
            return jsonify({
                'error': f'File {filename} not found in CSV',
                'status': 'error'
            }), 404
        
        # Get embedder
        embedder = get_embedder(method, use_api)
        
        # Generate embeddings
        texts = [
            tasks_data.get('task_1', ''),
            tasks_data.get('task_2', ''),
            tasks_data.get('task_3', ''),
            tasks_data.get('task_4', ''),
            content
        ]
        
        embeddings = embedder.embed(texts)
        
        # Update CSV with embeddings
        from utils.embedding_utils import save_embeddings_to_json
        
        # Read all rows, update matching row
        rows = []
        updated = False
        
        if os.path.exists(file_handler.csv_file):
            with open(file_handler.csv_file, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                fieldnames = reader.fieldnames or []
                
                # Ensure embedding columns exist
                embedding_cols = ['embedding_task_1', 'embedding_task_2', 'embedding_task_3', 
                                 'embedding_task_4', 'embedding_content', 'embedding_method']
                for col in embedding_cols:
                    if col not in fieldnames:
                        fieldnames.append(col)
                
                for row in reader:
                    if row.get('full_filename') == filename or row.get('filename') == filename:
                        row['embedding_task_1'] = save_embeddings_to_json(embeddings[0])
                        row['embedding_task_2'] = save_embeddings_to_json(embeddings[1])
                        row['embedding_task_3'] = save_embeddings_to_json(embeddings[2])
                        row['embedding_task_4'] = save_embeddings_to_json(embeddings[3])
                        row['embedding_content'] = save_embeddings_to_json(embeddings[4])
                        row['embedding_method'] = f"{method}_{'api' if embedder.use_api else 'local'}"
                        updated = True
                    rows.append(row)
            
            # Write back
            if updated:
                with open(file_handler.csv_file, 'w', newline='', encoding='utf-8-sig') as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(rows)
        
        return jsonify({
            'status': 'success',
            'filename': filename,
            'method': method,
            'use_api': embedder.use_api,
            'embeddings_generated': True
        }), 200
    
    except Exception as e:
        return jsonify({
            'error': f'Error generating embeddings: {str(e)}',
            'status': 'error'
        }), 500


@embedding_bp.route('/<filename>', methods=['GET'])
def get_embeddings(filename: str):
    """Get saved embeddings for a file."""
    try:
        from utils.file_handler import FileHandler
        from utils.embedding_utils import load_embeddings_from_json
        
        file_handler = FileHandler()
        
        import csv
        if not os.path.exists(file_handler.csv_file):
            return jsonify({
                'error': 'CSV file not found',
                'status': 'error'
            }), 404
        
        with open(file_handler.csv_file, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get('full_filename') == filename or row.get('filename') == filename:
                    embeddings = {
                        'task_1': load_embeddings_from_json(row.get('embedding_task_1', '')),
                        'task_2': load_embeddings_from_json(row.get('embedding_task_2', '')),
                        'task_3': load_embeddings_from_json(row.get('embedding_task_3', '')),
                        'task_4': load_embeddings_from_json(row.get('embedding_task_4', '')),
                        'content': load_embeddings_from_json(row.get('embedding_content', ''))
                    }
                    
                    return jsonify({
                        'status': 'success',
                        'filename': filename,
                        'method': row.get('embedding_method', 'unknown'),
                        'embeddings': embeddings
                    }), 200
        
        return jsonify({
            'error': f'File {filename} not found',
            'status': 'error'
        }), 404
    
    except Exception as e:
        return jsonify({
            'error': f'Error retrieving embeddings: {str(e)}',
            'status': 'error'
        }), 500
