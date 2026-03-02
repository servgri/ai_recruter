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
        from utils.database import Database
        from utils.embedding_utils import save_embeddings_to_json
        db = Database()
        doc = db.get_document_by_filename(filename)
        if not doc:
            return jsonify({
                'error': 'Document not found',
                'status': 'error'
            }), 404

        texts = [
            doc.get('task_1') or '',
            doc.get('task_2') or '',
            doc.get('task_3') or '',
            doc.get('task_4') or '',
            doc.get('content') or ''
        ]
        embedder = get_embedder(method, use_api)
        embeddings = embedder.embed(texts)
        db.update_document(
            doc['id'],
            embedding_task_1=save_embeddings_to_json(embeddings[0]),
            embedding_task_2=save_embeddings_to_json(embeddings[1]),
            embedding_task_3=save_embeddings_to_json(embeddings[2]),
            embedding_task_4=save_embeddings_to_json(embeddings[3]),
            embedding_content=save_embeddings_to_json(embeddings[4]),
            embedding_method=f"{method}_{'api' if embedder.use_api else 'local'}"
        )
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
        from utils.database import Database
        from utils.embedding_utils import load_embeddings_from_json
        db = Database()
        doc = db.get_document_by_filename(filename)
        if not doc:
            return jsonify({
                'error': 'Document not found',
                'status': 'error'
            }), 404
        embeddings = {
            'task_1': load_embeddings_from_json(doc.get('embedding_task_1') or ''),
            'task_2': load_embeddings_from_json(doc.get('embedding_task_2') or ''),
            'task_3': load_embeddings_from_json(doc.get('embedding_task_3') or ''),
            'task_4': load_embeddings_from_json(doc.get('embedding_task_4') or ''),
            'content': load_embeddings_from_json(doc.get('embedding_content') or '')
        }
        return jsonify({
            'status': 'success',
            'filename': filename,
            'method': doc.get('embedding_method') or 'unknown',
            'embeddings': embeddings
        }), 200
    
    except Exception as e:
        return jsonify({
            'error': f'Error retrieving embeddings: {str(e)}',
            'status': 'error'
        }), 500
