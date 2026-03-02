"""Processing service for async file processing."""

import os
import tempfile
from typing import Dict, Optional
from threading import Thread
from datetime import datetime

from utils.database import Database
from utils import get_parser_for_file
from utils.logger import log_action
from extractors import TaskExtractor
from services.task_cleaner_service import TaskCleaner
from services.embedding_service import get_embedder
from services.analysis_service import SimilarityAnalyzer, CheatingDetector
from services.grading_service import get_grading_service
from services.answer_evaluator_service import run_eval_v6
from services.impression_service import generate_overall_impression
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
        processing_start_time = datetime.now()
        try:
            # Log processing start
            log_action("file_processing_start", doc_id=doc_id, 
                      details={"filename": filename, "file_type": file_type})
            
            # Update status to processing
            self.db.update_document_status(doc_id, 'processing')
            self._emit_update(doc_id, 'upload', 'completed', 'Файл загружен')
            
            # Stage 1: Parsing
            self._emit_update(doc_id, 'parsing', 'in_progress', 'Парсинг файла...')
            parser = get_parser_for_file(filename)
            if parser is None:
                raise ValueError(f"Parser not available for file type: {file_type}")
            
            # Try to use parse_with_images if available, otherwise fall back to parse
            images_dir = os.path.join(os.path.dirname(__file__), '..', 'static', 'images', 'documents')
            os.makedirs(images_dir, exist_ok=True)
            
            if hasattr(parser, 'parse_with_images'):
                parse_result = parser.parse_with_images(file_path, doc_id=doc_id, output_dir=images_dir)
                content = parse_result.get('text', '')
                all_images = parse_result.get('images', [])
            else:
                content = parser.parse(file_path)
                all_images = []
            
            self._emit_update(doc_id, 'parsing', 'completed', 'Парсинг завершен')
            
            # Stage 2: Task extraction
            self._emit_update(doc_id, 'task_extraction', 'in_progress', 'Разделение на задания...')
            tasks = self.task_extractor.extract_tasks(content, all_images=all_images)
            
            # Update tasks in database
            import json
            task_dict = {task.get('task_number', i+1): task.get('content', '') 
                        for i, task in enumerate(tasks)}
            task_images_dict = {task.get('task_number', i+1): task.get('images', []) 
                               for i, task in enumerate(tasks)}
            
            # Convert images to JSON strings
            task_1_images_json = json.dumps(task_images_dict.get(1, []), ensure_ascii=False)
            task_2_images_json = json.dumps(task_images_dict.get(2, []), ensure_ascii=False)
            task_3_images_json = json.dumps(task_images_dict.get(3, []), ensure_ascii=False)
            task_4_images_json = json.dumps(task_images_dict.get(4, []), ensure_ascii=False)
            
            self.db.update_document(
                doc_id,
                task_1=task_dict.get(1, ''),
                task_2=task_dict.get(2, ''),
                task_3=task_dict.get(3, ''),
                task_4=task_dict.get(4, ''),
                content=content,
                tasks_count=len([t for t in tasks if t.get('content', '').strip()]),
                task_1_images=task_1_images_json,
                task_2_images=task_2_images_json,
                task_3_images=task_3_images_json,
                task_4_images=task_4_images_json
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
            
            # Stage 7: Automatic scoring (eval_v6 for tasks 1-3, grading for task 4)
            self._emit_update(doc_id, 'scoring', 'in_progress', 'Автоматическое оценивание...')
            grading_service = get_grading_service()

            # Build document-like dict for eval_v6 (tasks 1-4 from cleaned_tasks)
            doc_for_eval = {f'task_{i}': cleaned_tasks.get(i, '') for i in range(1, 5)}
            eval_result = run_eval_v6(doc_for_eval)
            task_scores = {
                'task_1_score': eval_result.get('task_1_score'),
                'task_2_score': eval_result.get('task_2_score'),
                'task_3_score': eval_result.get('task_3_score'),
                'average_score_tasks_1_3': eval_result.get('average_score_tasks_1_3'),
                'eval_v6_results': eval_result.get('eval_v6_results'),
            }

            # Fill similarity_with_reference from eval_v6 (cosine with etalon) so the general report table shows % per task
            eval_v6_raw = eval_result.get('eval_v6_results')
            if eval_v6_raw and isinstance(eval_v6_raw, str):
                try:
                    import json as _json
                    eval_v6_data = _json.loads(eval_v6_raw)
                    results_list = eval_v6_data.get('results') or []
                    ref_from_eval = {}
                    for r in results_list:
                        qid = str(r.get('Номер вопроса', ''))
                        if not qid:
                            continue
                        chosen = r.get('Эталон выбран')
                        cos_hr = r.get('Cosine HR')
                        cos_ai = r.get('Cosine AI')
                        if chosen == 'hr' and cos_hr is not None:
                            ref_from_eval[f'task_{qid}'] = float(cos_hr)
                        elif chosen == 'ai' and cos_ai is not None:
                            ref_from_eval[f'task_{qid}'] = float(cos_ai)
                        elif cos_ai is not None:
                            ref_from_eval[f'task_{qid}'] = float(cos_ai)
                        elif cos_hr is not None:
                            ref_from_eval[f'task_{qid}'] = float(cos_hr)
                    if ref_from_eval:
                        task_scores['similarity_with_reference'] = ref_from_eval
                except Exception:
                    pass

            # Evaluate task 4 (logic and originality) via grading service
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

            if task_scores:
                self.db.update_document(doc_id, **task_scores)

            self._emit_update(doc_id, 'scoring', 'completed', 'Оценивание завершено')

            # Generate overall impression from eval_v6 HR report (generator_comments_v2)
            try:
                document_after = self.db.get_document(doc_id)
                if document_after and document_after.get("eval_v6_results"):
                    overall_text = generate_overall_impression(document_after, doc_id=doc_id)
                    if overall_text:
                        self.db.update_document(doc_id, overall_impression=overall_text)
            except Exception as imp_err:
                print(f"Impression generation failed for doc_id={doc_id}: {imp_err}")

            # Stage 8: Generate report (async)
            self._emit_update(doc_id, 'report_generation', 'in_progress', 'Генерация отчета...')
            self._generate_report_async(doc_id, cleaned_tasks, ref_similarity, existing_similarity, cheating_result)
            
            # Stage 9: Completed
            self.db.update_document_status(doc_id, 'completed')
            self._emit_update(doc_id, 'completed', 'completed', 'Обработка завершена')
            
            # Log successful processing completion
            processing_end_time = datetime.now()
            processing_duration = (processing_end_time - processing_start_time).total_seconds()
            document = self.db.get_document(doc_id)
            log_action("file_processing_complete", doc_id=doc_id, 
                      details={"filename": filename, "file_type": file_type,
                              "tasks_count": document.get('tasks_count', 0) if document else 0,
                              "processing_duration_seconds": round(processing_duration, 2)})
            
        except Exception as e:
            # Update status to error
            self.db.update_document_status(doc_id, 'error')
            self._emit_update(doc_id, 'error', 'error', f'Ошибка: {str(e)}')
            print(f"Error processing file {filename}: {str(e)}")
            
            # Log processing error
            processing_end_time = datetime.now()
            processing_duration = (processing_end_time - processing_start_time).total_seconds()
            log_action("file_processing_error", doc_id=doc_id, status="error",
                      details={"filename": filename, "file_type": file_type,
                              "error": str(e), "processing_duration_seconds": round(processing_duration, 2)})
        finally:
            # Clean up temporary file only if it's not in loaded/ directory
            # Files in loaded/ should be kept for reprocessing
            if os.path.exists(file_path):
                # Check if file is in loaded/ directory (permanent storage)
                loaded_dir = os.path.abspath("loaded")
                file_abs_path = os.path.abspath(file_path)
                is_in_loaded = file_abs_path.startswith(loaded_dir)
                
                # Only delete if it's a temporary file (not in loaded/)
                if not is_in_loaded:
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
                        continue
                    
                    task_text = cleaned_tasks.get(task_num, '')
                    
                    # Add OCR text from images to task text for analysis
                    task_images_key = f'task_{task_num}_images'
                    task_images_json = document.get(task_images_key)
                    if task_images_json:
                        try:
                            import json
                            task_images = json.loads(task_images_json) if isinstance(task_images_json, str) else task_images_json
                            if task_images:
                                ocr_texts = [img.get('ocr_text', '') for img in task_images if img.get('ocr_text')]
                                if ocr_texts:
                                    ocr_combined = '\n'.join(ocr_texts)
                                    task_text = f"{task_text}\n\n[Текст из изображений в ответе: {ocr_combined}]"
                        except Exception as e:
                            print(f"Error processing task images for task {task_num}: {e}")
                    
                    if not task_text:
                        continue
                    
                    sim_ref_val = ref_similarity.get(f'task_{task_num}', 0) if ref_similarity else 0
                    task_cheating = cheating_result.get('tasks', {}).get(f'task_{task_num}', {}) if cheating_result else {}
                    
                    try:
                        comment = grading_service.generate_task_comment(
                            task_num, task_text, sim_ref_val, existing_similarity, task_cheating
                        )
                        if comment:
                            llm_comments[llm_comment_key] = comment
                    except Exception as e:
                        print(f"Error generating comment for task {task_num}: {e}")
                
                # Generate overall impression if not exists
                if not document.get('overall_impression'):
                    try:
                        # Prepare data for overall impression
                        tasks_dict = {}
                        scores_dict = {}
                        comments_dict = {}
                        
                        for task_num in range(1, 5):
                            task_key = f'task_{task_num}'
                            task_text = cleaned_tasks.get(task_num, '')
                            if task_text:
                                tasks_dict[task_num] = task_text
                            
                            score_key = f'task_{task_num}_score'
                            if task_num == 4:
                                # For task 4, use logic_score
                                score_key = 'task_4_logic_score'
                            score = document.get(score_key)
                            if score is not None:
                                scores_dict[task_num] = float(score)
                            
                            comment_key = f'task_{task_num}_llm_comment'
                            comment = llm_comments.get(comment_key) or document.get(comment_key)
                            if comment:
                                comments_dict[task_num] = comment
                        
                        # Check if winner
                        is_winner = document.get('candidate_status') == 'winner'
                        
                        # Generate overall impression
                        overall_impression = grading_service.generate_overall_impression(
                            tasks_dict, scores_dict, comments_dict,
                            ref_similarity, existing_similarity, cheating_result,
                            is_winner=is_winner
                        )
                        
                        if overall_impression:
                            llm_comments['overall_impression'] = overall_impression
                    except Exception as e:
                        print(f"Error generating overall impression: {e}")
                
                # Save all comments at once
                if llm_comments:
                    llm_comments['report_generated'] = True
                    self.db.update_document(doc_id, **llm_comments)
                    self._emit_update(doc_id, 'report_generation', 'completed', 'Отчет сгенерирован')
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
            # Files are saved with 5-character hash, but database stores full hash
            # Use first 5 characters of hash for filename
            short_hash = file_hash[:5]
            filename = f"{short_hash}.{file_type}"
            # Use absolute path to avoid issues with working directory
            loaded_dir = os.path.abspath("loaded")
            file_path = os.path.join(loaded_dir, filename)
            
            # If file doesn't exist with 5-char hash, try with full hash (backward compatibility)
            if not os.path.exists(file_path):
                # Try with full hash (for old files)
                filename_full = f"{file_hash}.{file_type}"
                file_path_full = os.path.join(loaded_dir, filename_full)
                if os.path.exists(file_path_full):
                    file_path = file_path_full
                else:
                    # Try with counter suffixes (in case of hash collisions)
                    counter = 1
                    found = False
                    while counter <= 100:  # Limit search to prevent infinite loop
                        filename_collision = f"{short_hash}_{counter}.{file_type}"
                        file_path_collision = os.path.join(loaded_dir, filename_collision)
                        if os.path.exists(file_path_collision):
                            # Verify it's the same file by comparing full hash
                            from utils.file_utils import calculate_file_hash
                            existing_hash = calculate_file_hash(file_path_collision)
                            if existing_hash == file_hash:
                                file_path = file_path_collision
                                found = True
                                break
                        counter += 1
                    
                    if not found:
                        raise FileNotFoundError(f"File not found: {file_path}")
            
            # Get original filename for processing
            original_filename = document.get('full_filename', filename)
            
            # Start reprocessing
            self.process_file_async(doc_id, file_path, original_filename, file_type)
            
            return True
        except Exception as e:
            print(f"Error reprocessing document {doc_id}: {str(e)}")
            raise