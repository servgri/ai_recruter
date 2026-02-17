"""Processing service for async file processing."""

import os
import tempfile
from typing import Dict, Optional
from threading import Thread

from utils.database import Database
from utils import get_parser_for_file
from extractors import TaskExtractor
from services.task_cleaner_service import TaskCleaner
from services.embedding_service import get_embedder
from services.analysis_service import SimilarityAnalyzer, CheatingDetector
from services.scoring_service import get_scoring_service
from services.grading_service import get_grading_service
from utils.embedding_utils import save_embeddings_to_json
from utils.cheating_detector import analyze_cheating


class ProcessingService:
    """Service for asynchronous file processing."""
    
    def __init__(self, socketio=None):
        """
        Initialize processing service.
        
        Args:
            socketio: Flask-SocketIO instance for WebSocket updates
        """
        self.db = Database()
        self.task_extractor = TaskExtractor()
        self.task_cleaner = TaskCleaner()
        self.socketio = socketio
    
    def _emit_update(self, doc_id: int, stage: str, status: str, message: str):
        """Emit WebSocket update."""
        if self.socketio:
            # Emit to room for this document and broadcast
            self.socketio.emit('processing_update', {
                'doc_id': doc_id,
                'stage': stage,
                'status': status,
                'message': message
            }, room=f"doc_{doc_id}")
            # Also broadcast to all clients
            self.socketio.emit('processing_update', {
                'doc_id': doc_id,
                'stage': stage,
                'status': status,
                'message': message
            })
    
    def process_file_async(self, doc_id: int, file_path: str, filename: str, file_type: str):
        """
        Process file asynchronously (runs in background thread).
        
        Args:
            doc_id: Document ID in database
            file_path: Path to temporary file
            filename: Original filename
            file_type: File extension
        """
        thread = Thread(target=self._process_file, args=(doc_id, file_path, filename, file_type))
        thread.daemon = True
        thread.start()
    
    def _process_file(self, doc_id: int, file_path: str, filename: str, file_type: str):
        """Process file (internal method, runs in thread)."""
        try:
            # Update status to processing
            self.db.update_document_status(doc_id, 'processing')
            self._emit_update(doc_id, 'upload', 'completed', 'Файл загружен')
            
            # Stage 1: Parsing
            self._emit_update(doc_id, 'parsing', 'in_progress', 'Парсинг файла...')
            parser = get_parser_for_file(filename)
            if parser is None:
                raise ValueError(f"Parser not available for file type: {file_type}")
            
            content = parser.parse(file_path)
            self._emit_update(doc_id, 'parsing', 'completed', 'Парсинг завершен')
            
            # Stage 2: Task extraction
            self._emit_update(doc_id, 'task_extraction', 'in_progress', 'Разделение на задания...')
            tasks = self.task_extractor.extract_tasks(content)
            
            # Update tasks in database
            task_dict = {task.get('task_number', i+1): task.get('content', '') 
                        for i, task in enumerate(tasks)}
            self.db.update_document(
                doc_id,
                task_1=task_dict.get(1, ''),
                task_2=task_dict.get(2, ''),
                task_3=task_dict.get(3, ''),
                task_4=task_dict.get(4, ''),
                content=content,
                tasks_count=len([t for t in tasks if t.get('content', '').strip()])
            )
            self._emit_update(doc_id, 'task_extraction', 'completed', 'Задания извлечены')
            
            # Stage 3: Task cleaning
            self._emit_update(doc_id, 'cleaning', 'in_progress', 'Очистка от хвостов...')
            tasks_dict = {i+1: task_dict.get(i+1, '') for i in range(4)}
            cleaning_result = self.task_cleaner.clean_tasks(tasks_dict, method='both')
            
            # Update cleaned tasks and tails
            cleaned_tasks = cleaning_result['cleaned_tasks']
            task_tails = cleaning_result['task_tails']
            
            self.db.update_document(
                doc_id,
                task_1=cleaned_tasks.get(1, ''),
                task_2=cleaned_tasks.get(2, ''),
                task_3=cleaned_tasks.get(3, ''),
                task_4=cleaned_tasks.get(4, ''),
                task_1_tails=task_tails.get(1, []),
                task_2_tails=task_tails.get(2, []),
                task_3_tails=task_tails.get(3, []),
                task_4_tails=task_tails.get(4, []),
                tasks_count=cleaning_result['tasks_count'],
                cleaning_status=cleaning_result['cleaning_status']
            )
            self._emit_update(doc_id, 'cleaning', 'completed', 'Очистка завершена')
            
            # Stage 4: Embeddings generation
            self._emit_update(doc_id, 'embeddings', 'in_progress', 'Генерация эмбеддингов...')
            embedder = get_embedder('sbert')
            
            texts = [
                cleaned_tasks.get(1, ''),
                cleaned_tasks.get(2, ''),
                cleaned_tasks.get(3, ''),
                cleaned_tasks.get(4, ''),
                content
            ]
            
            embeddings = embedder.embed(texts)
            
            # Ensure embeddings are lists (not numpy arrays)
            embeddings_list = []
            for emb in embeddings:
                if hasattr(emb, 'tolist'):
                    embeddings_list.append(emb.tolist())
                elif isinstance(emb, list):
                    embeddings_list.append(emb)
                else:
                    # Convert to list if needed
                    embeddings_list.append(list(emb) if emb is not None else [])
            
            # Save embeddings to database
            embedding_updates = {
                'embedding_method': 'sbert_local' if not embedder.use_api else 'sbert_api'
            }
            
            # Add embeddings if they exist
            if len(embeddings_list) > 0 and embeddings_list[0]:
                embedding_updates['embedding_task_1'] = save_embeddings_to_json(embeddings_list[0])
            if len(embeddings_list) > 1 and embeddings_list[1]:
                embedding_updates['embedding_task_2'] = save_embeddings_to_json(embeddings_list[1])
            if len(embeddings_list) > 2 and embeddings_list[2]:
                embedding_updates['embedding_task_3'] = save_embeddings_to_json(embeddings_list[2])
            if len(embeddings_list) > 3 and embeddings_list[3]:
                embedding_updates['embedding_task_4'] = save_embeddings_to_json(embeddings_list[3])
            if len(embeddings_list) > 4 and embeddings_list[4]:
                embedding_updates['embedding_content'] = save_embeddings_to_json(embeddings_list[4])
            
            self.db.update_document(doc_id, **embedding_updates)
            self._emit_update(doc_id, 'embeddings', 'completed', 'Эмбеддинги сгенерированы')
            
            # Stage 5: Similarity calculation
            self._emit_update(doc_id, 'similarity', 'in_progress', 'Вычисление схожести...')
            analyzer = SimilarityAnalyzer()
            
            # Compare with reference
            ref_similarity = analyzer.compare_with_reference(embeddings[:4])
            
            # Compare with existing (get current document to get filename)
            current_doc = self.db.get_document(doc_id)
            current_filename = current_doc.get('full_filename') if current_doc else filename
            existing_similarity = analyzer.compare_with_existing(embeddings, current_filename)
            
            self.db.update_document(
                doc_id,
                similarity_with_reference=ref_similarity,
                similarity_with_existing=existing_similarity
            )
            self._emit_update(doc_id, 'similarity', 'completed', 'Схожесть вычислена')
            
            # Recalculate similarities for all existing documents with the new document
            # This runs asynchronously to not block the main processing
            from threading import Thread
            def recalc_similarities():
                try:
                    analyzer.recalculate_all_similarities(doc_id)
                except Exception as e:
                    print(f"Error recalculating similarities: {e}")
            
            recalc_thread = Thread(target=recalc_similarities)
            recalc_thread.daemon = True
            recalc_thread.start()
            
            # Stage 6: Cheating detection
            self._emit_update(doc_id, 'cheating_detection', 'in_progress', 'Детекция читинга...')
            detector = CheatingDetector()
            cheating_result = detector.analyze_document(cleaned_tasks, content)
            
            self.db.update_document(
                doc_id,
                cheating_score=cheating_result
            )
            self._emit_update(doc_id, 'cheating_detection', 'completed', 'Анализ читинга завершен')
            
            # Stage 7: Automatic scoring
            self._emit_update(doc_id, 'scoring', 'in_progress', 'Автоматическое оценивание...')
            scoring_service = get_scoring_service()
            grading_service = get_grading_service()
            
            # Calculate scores for tasks 1-3
            task_scores = {}
            for task_num in range(1, 4):
                task_key = f'task_{task_num}'
                task_text = cleaned_tasks.get(task_num, '')
                if task_text:
                    sim_ref_val = ref_similarity.get(f'task_{task_num}', 0) if ref_similarity else 0
                    task_cheating = cheating_result.get('tasks', {}).get(f'task_{task_num}', {}) if cheating_result else {}
                    
                    score = scoring_service.calculate_task_score(
                        task_num, sim_ref_val, task_cheating, task_text
                    )
                    task_scores[f'task_{task_num}_score'] = score
            
            # Calculate average for tasks 1-3
            avg_score = scoring_service.calculate_average_score_tasks_1_3(
                task_scores.get('task_1_score'),
                task_scores.get('task_2_score'),
                task_scores.get('task_3_score')
            )
            if avg_score is not None:
                task_scores['average_score_tasks_1_3'] = avg_score
            
            # Evaluate task 4 (logic and originality)
            task_4_text = cleaned_tasks.get(4, '')
            if task_4_text:
                sim_ref_val_4 = ref_similarity.get('task_4', 0) if ref_similarity else 0
                task_4_cheating = cheating_result.get('tasks', {}).get('task_4', {}) if cheating_result else {}
                
                logic_score = grading_service.evaluate_task_4_logic(
                    task_4_text, sim_ref_val_4, task_4_cheating
                )
                originality_score = grading_service.evaluate_task_4_originality(
                    task_4_text, existing_similarity, task_4_cheating
                )
                
                task_scores['task_4_logic_score'] = logic_score
                task_scores['task_4_originality_score'] = originality_score
            
            # Save scores
            if task_scores:
                self.db.update_document(doc_id, **task_scores)
            
            self._emit_update(doc_id, 'scoring', 'completed', 'Оценивание завершено')
            
            # Stage 8: Generate report (async)
            self._emit_update(doc_id, 'report_generation', 'in_progress', 'Генерация отчета...')
            self._generate_report_async(doc_id, cleaned_tasks, ref_similarity, existing_similarity, cheating_result)
            
            # Stage 9: Completed
            self.db.update_document_status(doc_id, 'completed')
            self._emit_update(doc_id, 'completed', 'completed', 'Обработка завершена')
            
        except Exception as e:
            # Update status to error
            self.db.update_document_status(doc_id, 'error')
            self._emit_update(doc_id, 'error', 'error', f'Ошибка: {str(e)}')
            print(f"Error processing file {filename}: {str(e)}")
        finally:
            # Clean up temporary file
            if os.path.exists(file_path):
                try:
                    os.unlink(file_path)
                except Exception:
                    pass
    
    def _generate_report_async(self, doc_id: int, cleaned_tasks: Dict, 
                              ref_similarity: Dict, existing_similarity: Dict,
                              cheating_result: Dict):
        """Generate LLM comments for report asynchronously."""
        def generate_comments():
            try:
                grading_service = get_grading_service()
                document = self.db.get_document(doc_id)
                
                if not document:
                    return
                
                llm_comments = {}
                
                # Generate comments for each task
                for task_num in range(1, 5):
                    task_key = f'task_{task_num}'
                    llm_comment_key = f'task_{task_num}_llm_comment'
                    
                    # Skip if comment already exists
                    if document.get(llm_comment_key):
                        # #region agent log
                        try:
                            import json as json_lib
                            with open('c:\\Users\\Hedgehog\\Desktop\\interview\\.cursor\\debug.log', 'a', encoding='utf-8') as f:
                                f.write(json_lib.dumps({'location': 'processing_service.py:304', 'message': 'Comment already exists, skipping', 'data': {'doc_id': doc_id, 'task_num': task_num, 'existing_comment': str(document.get(llm_comment_key))[:50]}, 'timestamp': int(__import__('time').time() * 1000), 'hypothesisId': 'D'}) + '\n')
                        except: pass
                        # #endregion
                        continue
                    
                    task_text = cleaned_tasks.get(task_num, '')
                    if not task_text:
                        # #region agent log
                        try:
                            import json as json_lib
                            with open('c:\\Users\\Hedgehog\\Desktop\\interview\\.cursor\\debug.log', 'a', encoding='utf-8') as f:
                                f.write(json_lib.dumps({'location': 'processing_service.py:308', 'message': 'Task text empty, skipping', 'data': {'doc_id': doc_id, 'task_num': task_num}, 'timestamp': int(__import__('time').time() * 1000), 'hypothesisId': 'D'}) + '\n')
                        except: pass
                        # #endregion
                        continue
                    
                    sim_ref_val = ref_similarity.get(f'task_{task_num}', 0) if ref_similarity else 0
                    task_cheating = cheating_result.get('tasks', {}).get(f'task_{task_num}', {}) if cheating_result else {}
                    
                    try:
                        comment = grading_service.generate_task_comment(
                            task_num, task_text, sim_ref_val, existing_similarity, task_cheating
                        )
                        # #region agent log
                        try:
                            import json as json_lib
                            with open('c:\\Users\\Hedgehog\\Desktop\\interview\\.cursor\\debug.log', 'a', encoding='utf-8') as f:
                                f.write(json_lib.dumps({'location': 'processing_service.py:318', 'message': 'Comment generated', 'data': {'doc_id': doc_id, 'task_num': task_num, 'comment_is_none': comment is None, 'comment_empty': comment == '' if comment else None, 'comment_length': len(comment) if comment else 0, 'comment_preview': str(comment)[:50] if comment else None}, 'timestamp': int(__import__('time').time() * 1000), 'hypothesisId': 'D'}) + '\n')
                        except: pass
                        # #endregion
                        if comment:
                            llm_comments[llm_comment_key] = comment
                    except Exception as e:
                        print(f"Error generating comment for task {task_num}: {e}")
                        # #region agent log
                        try:
                            import json as json_lib
                            with open('c:\\Users\\Hedgehog\\Desktop\\interview\\.cursor\\debug.log', 'a', encoding='utf-8') as f:
                                f.write(json_lib.dumps({'location': 'processing_service.py:321', 'message': 'Error generating comment', 'data': {'doc_id': doc_id, 'task_num': task_num, 'error': str(e)}, 'timestamp': int(__import__('time').time() * 1000), 'hypothesisId': 'D'}) + '\n')
                        except: pass
                        # #endregion
                
                # Save all comments at once
                # #region agent log
                try:
                    import json as json_lib
                    with open('c:\\Users\\Hedgehog\\Desktop\\interview\\.cursor\\debug.log', 'a', encoding='utf-8') as f:
                        f.write(json_lib.dumps({'location': 'processing_service.py:340', 'message': 'Before saving comments', 'data': {'doc_id': doc_id, 'comments_count': len(llm_comments), 'comment_keys': list(llm_comments.keys()), 'will_save': len(llm_comments) > 0}, 'timestamp': int(__import__('time').time() * 1000), 'hypothesisId': 'D'}) + '\n')
                except: pass
                # #endregion
                if llm_comments:
                    llm_comments['report_generated'] = True
                    self.db.update_document(doc_id, **llm_comments)
                    # #region agent log
                    try:
                        import json as json_lib
                        with open('c:\\Users\\Hedgehog\\Desktop\\interview\\.cursor\\debug.log', 'a', encoding='utf-8') as f:
                            f.write(json_lib.dumps({'location': 'processing_service.py:346', 'message': 'LLM comments saved', 'data': {'doc_id': doc_id, 'comments_count': len(llm_comments), 'comment_keys': list(llm_comments.keys())}, 'timestamp': int(__import__('time').time() * 1000), 'hypothesisId': 'D'}) + '\n')
                    except: pass
                    # #endregion
                    self._emit_update(doc_id, 'report_generation', 'completed', 'Отчет сгенерирован')
                else:
                    # #region agent log
                    try:
                        import json as json_lib
                        with open('c:\\Users\\Hedgehog\\Desktop\\interview\\.cursor\\debug.log', 'a', encoding='utf-8') as f:
                            f.write(json_lib.dumps({'location': 'processing_service.py:352', 'message': 'No comments to save', 'data': {'doc_id': doc_id}, 'timestamp': int(__import__('time').time() * 1000), 'hypothesisId': 'D'}) + '\n')
                    except: pass
                    # #endregion
            except Exception as e:
                print(f"Error in async report generation: {e}")
                self._emit_update(doc_id, 'report_generation', 'error', f'Ошибка генерации отчета: {str(e)}')
        
        thread = Thread(target=generate_comments)
        thread.daemon = True
        thread.start()
    
    def reprocess_document(self, doc_id: int):
        """
        Reprocess a document by finding the file in loaded/ directory.
        
        Args:
            doc_id: Document ID in database
        """
        try:
            # Get document from database
            document = self.db.get_document(doc_id)
            if not document:
                raise ValueError(f"Document with ID {doc_id} not found")
            
            file_hash = document.get('file_hash')
            if not file_hash:
                raise ValueError(f"Document {doc_id} has no file_hash")
            
            file_type = document.get('type', '')
            if not file_type:
                raise ValueError(f"Document {doc_id} has no file type")
            
            # Find file in loaded/ directory
            # Format: {hash}.{extension}
            filename = f"{file_hash}.{file_type}"
            file_path = os.path.join("loaded", filename)
            
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")
            
            # Get original filename for processing
            original_filename = document.get('full_filename', filename)
            
            # Start reprocessing
            self.process_file_async(doc_id, file_path, original_filename, file_type)
            
            return True
        except Exception as e:
            print(f"Error reprocessing document {doc_id}: {str(e)}")
            raise