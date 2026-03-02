"""Analysis service for similarity and cheating detection."""

import json
from typing import Dict, List, Optional
from flask import Blueprint, request, jsonify

from services.config import REFERENCE_FILE
from services.embedding_service import get_embedder
from utils.database import Database
from utils.embedding_utils import (
    cosine_similarity_vectors, load_embeddings_from_json,
    load_reference_answers
)
from utils.cheating_detector import analyze_cheating

analysis_bp = Blueprint('analysis', __name__, url_prefix='/analysis')


class SimilarityAnalyzer:
    """Analyzer for similarity with reference and existing answers."""
    
    def __init__(self):
        self.reference_file = REFERENCE_FILE
        self.db = Database()
        self.reference_answers = None
        self.reference_embeddings = None
    
    def _load_reference(self):
        """Load reference answers and generate embeddings."""
        if self.reference_answers is None:
            self.reference_answers = load_reference_answers(self.reference_file)
            
            # Generate embeddings for reference answers
            if self.reference_answers:
                embedder = get_embedder("sbert")
                texts = [self.reference_answers.get(i, '') for i in range(1, 5)]
                self.reference_embeddings = embedder.embed(texts)
    
    def compare_with_reference(self, task_embeddings: List[List[float]]) -> Dict[str, float]:
        """
        Compare task embeddings with reference answers.
        
        Args:
            task_embeddings: List of embeddings for tasks 1-4
            
        Returns:
            Dictionary with similarity scores for each task
        """
        self._load_reference()
        
        if not self.reference_embeddings:
            return {}
        
        similarities = {}
        for i in range(min(len(task_embeddings), len(self.reference_embeddings))):
            task_num = i + 1
            if task_embeddings[i] and self.reference_embeddings[i]:
                similarity = cosine_similarity_vectors(
                    task_embeddings[i],
                    self.reference_embeddings[i]
                )
                similarities[f'task_{task_num}'] = similarity
        
        # Calculate average
        if similarities:
            similarities['average'] = sum(similarities.values()) / len(similarities)
        
        return similarities
    
    def compare_with_existing(self, task_embeddings: List[List[float]], 
                            current_filename: str, top_n: int = 3) -> Dict:
        """
        Compare with existing answers in database.
        
        Args:
            task_embeddings: List of embeddings for tasks 1-4 and content
            current_filename: Filename of current document
            top_n: Number of top similar documents to return
            
        Returns:
            Dictionary with top similar documents
        """
        similarities_list = []
        
        # Get all documents from database
        all_documents = self.db.get_all_documents()
        
        for doc in all_documents:
            filename = doc.get('full_filename') or doc.get('filename', '')
            if filename == current_filename:
                continue
            
            # Load embeddings from database
            existing_embeddings = {
                'task_1': load_embeddings_from_json(doc.get('embedding_task_1', '')),
                'task_2': load_embeddings_from_json(doc.get('embedding_task_2', '')),
                'task_3': load_embeddings_from_json(doc.get('embedding_task_3', '')),
                'task_4': load_embeddings_from_json(doc.get('embedding_task_4', '')),
                'content': load_embeddings_from_json(doc.get('embedding_content', ''))
            }
            
            # Skip if no embeddings
            if not any(existing_embeddings.values()):
                continue
            
            # Calculate similarities for each task
            task_similarities = {}
            for i in range(1, 5):
                task_key = f'task_{i}'
                if i-1 < len(task_embeddings) and task_embeddings[i-1] and existing_embeddings.get(task_key):
                    similarity = cosine_similarity_vectors(
                        task_embeddings[i-1],
                        existing_embeddings[task_key]
                    )
                    task_similarities[task_key] = similarity
            
            # Calculate content similarity
            content_similarity = 0.0
            if len(task_embeddings) > 4 and task_embeddings[4] and existing_embeddings.get('content'):
                content_similarity = cosine_similarity_vectors(
                    task_embeddings[4],
                    existing_embeddings['content']
                )
            
            # Average task similarity
            avg_task_similarity = 0.0
            if task_similarities:
                avg_task_similarity = sum(task_similarities.values()) / len(task_similarities)
            
            similarities_list.append({
                'filename': filename,
                'doc_id': doc.get('id'),
                'task_similarities': task_similarities,
                'content_similarity': content_similarity,
                'average_task_similarity': avg_task_similarity,
                'overall_similarity': (avg_task_similarity + content_similarity) / 2 if (avg_task_similarity + content_similarity) > 0 else 0.0
            })
        
        # Sort by overall similarity and get top N
        similarities_list.sort(key=lambda x: x['overall_similarity'], reverse=True)
        top_similar = similarities_list[:top_n]
        
        return {
            'top_similar': top_similar,
            'total_comparisons': len(similarities_list)
        }
    
    def recalculate_all_similarities(self, new_doc_id: int):
        """
        Recalculate similarities for all existing documents with the new document.
        
        Args:
            new_doc_id: ID of the newly added document
        """
        # Get new document
        new_doc = self.db.get_document(new_doc_id)
        if not new_doc:
            return
        
        # Load embeddings for new document
        new_embeddings = {
            'task_1': load_embeddings_from_json(new_doc.get('embedding_task_1', '')),
            'task_2': load_embeddings_from_json(new_doc.get('embedding_task_2', '')),
            'task_3': load_embeddings_from_json(new_doc.get('embedding_task_3', '')),
            'task_4': load_embeddings_from_json(new_doc.get('embedding_task_4', '')),
            'content': load_embeddings_from_json(new_doc.get('embedding_content', ''))
        }
        
        # Skip if no embeddings
        if not any(new_embeddings.values()):
            return
        
        # Get all existing documents (excluding the new one)
        all_documents = self.db.get_all_documents()
        
        for existing_doc in all_documents:
            if existing_doc.get('id') == new_doc_id:
                continue
            
            # Load existing document's embeddings
            existing_embeddings = {
                'task_1': load_embeddings_from_json(existing_doc.get('embedding_task_1', '')),
                'task_2': load_embeddings_from_json(existing_doc.get('embedding_task_2', '')),
                'task_3': load_embeddings_from_json(existing_doc.get('embedding_task_3', '')),
                'task_4': load_embeddings_from_json(existing_doc.get('embedding_task_4', '')),
                'content': load_embeddings_from_json(existing_doc.get('embedding_content', ''))
            }
            
            # Skip if no embeddings
            if not any(existing_embeddings.values()):
                continue
            
            # Calculate similarities
            task_similarities = {}
            for i in range(1, 5):
                task_key = f'task_{i}'
                if new_embeddings.get(task_key) and existing_embeddings.get(task_key):
                    similarity = cosine_similarity_vectors(
                        new_embeddings[task_key],
                        existing_embeddings[task_key]
                    )
                    task_similarities[task_key] = similarity
            
            # Calculate content similarity
            content_similarity = 0.0
            if new_embeddings.get('content') and existing_embeddings.get('content'):
                content_similarity = cosine_similarity_vectors(
                    new_embeddings['content'],
                    existing_embeddings['content']
                )
            
            # Average task similarity
            avg_task_similarity = 0.0
            if task_similarities:
                avg_task_similarity = sum(task_similarities.values()) / len(task_similarities)
            
            overall_similarity = (avg_task_similarity + content_similarity) / 2 if (avg_task_similarity + content_similarity) > 0 else 0.0
            
            # Get current similarity_with_existing for existing document
            current_similarity_data = existing_doc.get('similarity_with_existing', '{}')
            try:
                if isinstance(current_similarity_data, str):
                    if current_similarity_data.strip():
                        current_similarity = json.loads(current_similarity_data)
                    else:
                        current_similarity = {'top_similar': [], 'total_comparisons': 0}
                elif current_similarity_data is None:
                    current_similarity = {'top_similar': [], 'total_comparisons': 0}
                else:
                    current_similarity = current_similarity_data
            except Exception as e:
                current_similarity = {'top_similar': [], 'total_comparisons': 0}
            
            # Ensure current_similarity is a dict
            if not isinstance(current_similarity, dict):
                current_similarity = {'top_similar': [], 'total_comparisons': 0}
            
            # Add new document to top_similar if it's high enough
            top_similar = current_similarity.get('top_similar', [])
            
            # Create entry for new document
            new_entry = {
                'filename': new_doc.get('full_filename') or new_doc.get('filename', ''),
                'doc_id': new_doc_id,
                'task_similarities': task_similarities,
                'content_similarity': content_similarity,
                'average_task_similarity': avg_task_similarity,
                'overall_similarity': overall_similarity
            }
            
            # Add to list and sort
            top_similar.append(new_entry)
            top_similar.sort(key=lambda x: x.get('overall_similarity', 0), reverse=True)
            
            # Keep only top 3
            top_similar = top_similar[:3]
            
            # Update similarity_with_existing
            updated_similarity = {
                'top_similar': top_similar,
                'total_comparisons': current_similarity.get('total_comparisons', 0) + 1
            }
            
            self.db.update_document(
                existing_doc.get('id'),
                similarity_with_existing=updated_similarity
            )


class CheatingDetector:
    """Detector for cheating and LLM usage."""
    
    def analyze_document(self, tasks: Dict[int, str], content: str) -> Dict:
        """
        Analyze document for cheating indicators.
        
        Args:
            tasks: Dictionary mapping task number to task text
            content: Full document content
            
        Returns:
            Dictionary with cheating analysis results
        """
        results = {
            'tasks': {},
            'content': analyze_cheating(content)
        }
        
        # Analyze each task
        for task_num, task_text in tasks.items():
            if task_text and task_text.strip():
                results['tasks'][f'task_{task_num}'] = analyze_cheating(task_text)
        
        # Calculate overall scores
        task_scores = [v.get('llm_likelihood', 0.0) for v in results['tasks'].values()]
        if task_scores:
            results['average_llm_likelihood'] = sum(task_scores) / len(task_scores)
        else:
            results['average_llm_likelihood'] = 0.0
        
        results['content_llm_likelihood'] = results['content'].get('llm_likelihood', 0.0)
        
        return results


@analysis_bp.route('/similarity', methods=['POST'])
def calculate_similarity():
    """
    Calculate similarity with reference and existing answers.
    
    Expected JSON:
    {
        "filename": "example.docx",
        "compare_with_reference": true,
        "compare_with_existing": true
    }
    """
    data = request.get_json() or {}
    filename = data.get('filename')
    compare_ref = data.get('compare_with_reference', True)
    compare_existing = data.get('compare_with_existing', True)
    
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

        task_embeddings = [
            load_embeddings_from_json(doc.get('embedding_task_1') or ''),
            load_embeddings_from_json(doc.get('embedding_task_2') or ''),
            load_embeddings_from_json(doc.get('embedding_task_3') or ''),
            load_embeddings_from_json(doc.get('embedding_task_4') or '')
        ]
        content_embedding = load_embeddings_from_json(doc.get('embedding_content') or '')

        if not any(task_embeddings):
            return jsonify({
                'error': 'Embeddings not found for this file. Generate embeddings first.',
                'status': 'error'
            }), 404

        analyzer = SimilarityAnalyzer()
        result = {}
        if compare_ref:
            result['similarity_with_reference'] = analyzer.compare_with_reference(task_embeddings)
        if compare_existing:
            all_embeddings = task_embeddings + [content_embedding] if content_embedding else task_embeddings
            result['similarity_with_existing'] = analyzer.compare_with_existing(all_embeddings, filename)

        update_data = {}
        if compare_ref and result.get('similarity_with_reference'):
            update_data['similarity_with_reference'] = json.dumps(result['similarity_with_reference'], ensure_ascii=False)
        if compare_existing and result.get('similarity_with_existing'):
            update_data['similarity_with_existing'] = json.dumps(result['similarity_with_existing'], ensure_ascii=False)
        if update_data:
            db.update_document(doc['id'], **update_data)

        return jsonify({
            'status': 'success',
            'filename': filename,
            **result
        }), 200
    
    except Exception as e:
        return jsonify({
            'error': f'Error calculating similarity: {str(e)}',
            'status': 'error'
        }), 500


@analysis_bp.route('/cheating-detection', methods=['POST'])
def detect_cheating():
    """
    Detect cheating and LLM usage.
    
    Expected JSON:
    {
        "filename": "example.docx"
    }
    """
    data = request.get_json() or {}
    filename = data.get('filename')
    
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

        tasks = {
            1: doc.get('task_1') or '',
            2: doc.get('task_2') or '',
            3: doc.get('task_3') or '',
            4: doc.get('task_4') or ''
        }
        content = doc.get('content') or ''

        detector = CheatingDetector()
        result = detector.analyze_document(tasks, content)
        db.update_document(doc['id'], cheating_score=json.dumps(result, ensure_ascii=False))

        return jsonify({
            'status': 'success',
            'filename': filename,
            'cheating_analysis': result
        }), 200
    
    except Exception as e:
        return jsonify({
            'error': f'Error detecting cheating: {str(e)}',
            'status': 'error'
        }), 500


@analysis_bp.route('/report/<filename>', methods=['GET'])
def get_full_report(filename: str):
    """Get full analysis report for a file."""
    try:
        from utils.database import Database
        db = Database()
        doc = db.get_document_by_filename(filename)
        if not doc:
            return jsonify({
                'error': 'Document not found',
                'status': 'error'
            }), 404

        def _safe_json(s, default=None):
            if default is None:
                default = {}
            if not s or not isinstance(s, str):
                return default
            try:
                return json.loads(s)
            except json.JSONDecodeError:
                return default

        report = {
            'filename': filename,
            'tasks_count': doc.get('tasks_count', ''),
            'cleaning_status': doc.get('cleaning_status', ''),
            'embedding_method': doc.get('embedding_method', ''),
            'similarity_with_reference': _safe_json(doc.get('similarity_with_reference')),
            'similarity_with_existing': _safe_json(doc.get('similarity_with_existing')),
            'cheating_score': _safe_json(doc.get('cheating_score'))
        }
        return jsonify({
            'status': 'success',
            'report': report
        }), 200
    
    except Exception as e:
        return jsonify({
            'error': f'Error generating report: {str(e)}',
            'status': 'error'
        }), 500
