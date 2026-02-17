"""Grading service for generating LLM comments on tasks."""

import os
import json
import re
import requests
from typing import Dict, Optional

from services.config import HF_API_TOKEN, HF_API_BASE_URL, API_PRIORITY, QWEN_MODEL_NAME, LOCAL_MODELS_DIR


class GradingService:
    """Service for generating LLM comments on student tasks."""
    
    def __init__(self):
        self.api_url = f"{HF_API_BASE_URL}/{QWEN_MODEL_NAME}"
        self.use_api = API_PRIORITY == "api_first"
        self.local_model = None
        self.local_tokenizer = None
    
    def generate_task_comment(self, task_num: int, task_text: str, 
                             similarity_ref: float, similarity_existing: Optional[Dict],
                             cheating_metrics: Optional[Dict]) -> str:
        """
        Generate LLM comment for a task.
        
        Args:
            task_num: Task number (1-4)
            task_text: Student's answer text
            similarity_ref: Similarity with reference answer (0-1)
            similarity_existing: Similarity with existing answers (dict with top_similar)
            cheating_metrics: Cheating detection metrics
            
        Returns:
            Generated comment text (1 paragraph)
        """
        # Build prompt
        prompt = self._build_prompt(task_num, task_text, similarity_ref, 
                                   similarity_existing, cheating_metrics)
        
        # Generate comment
        if self.use_api:
            comment = self._generate_api(prompt)
            if comment:
                return comment
        
        # Fallback to local
        comment = self._generate_local(prompt)
        if comment:
            return comment
        
        # Fallback to template if generation fails
        return self._generate_fallback_comment(similarity_ref, cheating_metrics)
    
    def _build_prompt(self, task_num: int, task_text: str, similarity_ref: float,
                     similarity_existing: Optional[Dict], cheating_metrics: Optional[Dict]) -> str:
        """Build prompt for LLM."""
        prompt = f"""Ты - опытный преподаватель, оценивающий ответ студента на задание {task_num}.

Задание {task_num}:
{task_text[:500]}

Метрики оценки:
- Схожесть с эталонным ответом: {similarity_ref:.1%}
"""
        
        if similarity_existing and similarity_existing.get('top_similar'):
            max_sim = similarity_existing['top_similar'][0].get('overall_similarity', 0)
            prompt += f"- Схожесть с другими ответами: {max_sim:.1%}\n"
        
        if cheating_metrics:
            llm_likelihood = cheating_metrics.get('llm_likelihood', 0)
            readability = cheating_metrics.get('readability', 0)
            prompt += f"- Вероятность использования LLM: {llm_likelihood:.1%}\n"
            prompt += f"- Читаемость текста: {readability:.1f}\n"
        
        prompt += """
Напиши краткий комментарий (1 абзац, 3-5 предложений) на русском языке, который:
1. Отмечает хорошие стороны решения
2. Указывает на недостатки или ошибки
3. Дает общую оценку качества ответа

Комментарий должен быть конструктивным и полезным для студента. Начни сразу с комментария, без предисловий:"""
        
        return prompt
    
    def _generate_api(self, prompt: str) -> Optional[str]:
        """Generate comment using HF API."""
        if not HF_API_TOKEN:
            return None
        
        try:
            headers = {"Authorization": f"Bearer {HF_API_TOKEN}"}
            payload = {
                "inputs": prompt,
                "parameters": {
                    "max_new_tokens": 200,
                    "temperature": 0.7,
                    "return_full_text": False
                }
            }
            
            response = requests.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                if isinstance(result, list) and len(result) > 0:
                    if isinstance(result[0], dict) and 'generated_text' in result[0]:
                        return self._extract_comment(result[0]['generated_text'])
                    elif isinstance(result[0], str):
                        return self._extract_comment(result[0])
                elif isinstance(result, dict) and 'generated_text' in result:
                    return self._extract_comment(result['generated_text'])
            elif response.status_code == 503:
                import time
                time.sleep(5)
                response = requests.post(
                    self.api_url,
                    headers=headers,
                    json=payload,
                    timeout=60
                )
                if response.status_code == 200:
                    result = response.json()
                    if isinstance(result, list) and len(result) > 0:
                        if isinstance(result[0], dict) and 'generated_text' in result[0]:
                            return self._extract_comment(result[0]['generated_text'])
                        elif isinstance(result[0], str):
                            return self._extract_comment(result[0])
            
            return None
        except Exception as e:
            print(f"Grading API error: {str(e)}")
            return None
    
    def _generate_local(self, prompt: str) -> Optional[str]:
        """Generate comment using local QWEN model."""
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer
            import torch
            
            if self.local_model is None or self.local_tokenizer is None:
                self._load_local_model()
            
            if self.local_model is None or self.local_tokenizer is None:
                return None
            
            inputs = self.local_tokenizer(
                prompt, 
                return_tensors="pt", 
                truncation=True, 
                max_length=1024
            )
            
            with torch.no_grad():
                outputs = self.local_model.generate(
                    **inputs,
                    max_new_tokens=200,
                    temperature=0.7,
                    do_sample=True,
                    pad_token_id=self.local_tokenizer.eos_token_id
                )
            
            generated_text = self.local_tokenizer.decode(outputs[0], skip_special_tokens=True)
            # Remove prompt from generated text
            if prompt in generated_text:
                generated_text = generated_text.replace(prompt, "").strip()
            
            return self._extract_comment(generated_text)
        except Exception as e:
            print(f"Grading local error: {str(e)}")
            return None
    
    def _load_local_model(self):
        """Load local QWEN model."""
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer
            
            model_path = os.path.join(LOCAL_MODELS_DIR, QWEN_MODEL_NAME.replace('/', '_'))
            
            if os.path.exists(model_path):
                self.local_tokenizer = AutoTokenizer.from_pretrained(model_path)
                self.local_model = AutoModelForCausalLM.from_pretrained(model_path)
            else:
                self.local_tokenizer = AutoTokenizer.from_pretrained(QWEN_MODEL_NAME)
                self.local_model = AutoModelForCausalLM.from_pretrained(QWEN_MODEL_NAME)
                self.local_tokenizer.save_pretrained(model_path)
                self.local_model.save_pretrained(model_path)
            
            self.local_model.eval()
        except ImportError:
            print("transformers not installed for grading")
        except Exception as e:
            print(f"Error loading local model: {str(e)}")
    
    def _extract_comment(self, text: str) -> str:
        """Extract comment from generated text."""
        # Clean up the text
        text = text.strip()
        
        # Remove common prefixes
        prefixes = [
            "Комментарий:",
            "Оценка:",
            "Ответ:",
            "Комментарий преподавателя:"
        ]
        for prefix in prefixes:
            if text.startswith(prefix):
                text = text[len(prefix):].strip()
        
        # Take first paragraph (up to 500 chars or first double newline)
        paragraphs = text.split('\n\n')
        if paragraphs:
            comment = paragraphs[0].strip()
            # Limit length
            if len(comment) > 500:
                comment = comment[:500].rsplit('.', 1)[0] + '.'
            return comment
        
        return text[:500] if len(text) > 500 else text
    
    def _generate_fallback_comment(self, similarity_ref: float, 
                                  cheating_metrics: Optional[Dict]) -> str:
        """Generate fallback comment when LLM generation fails."""
        comments = []
        
        if similarity_ref >= 0.8:
            comments.append("Ответ демонстрирует высокую схожесть с эталонным решением.")
        elif similarity_ref >= 0.6:
            comments.append("Ответ в целом соответствует эталону, но есть некоторые расхождения.")
        else:
            comments.append("Ответ имеет низкую схожесть с эталонным решением.")
        
        if cheating_metrics:
            llm_likelihood = cheating_metrics.get('llm_likelihood', 0)
            if llm_likelihood > 0.7:
                comments.append("Обнаружены признаки возможного использования автоматизированных инструментов.")
            elif llm_likelihood < 0.3:
                comments.append("Текст выглядит оригинальным и написанным самостоятельно.")
        
        comments.append("Рекомендуется обратить внимание на детали и полноту ответа.")
        
        return " ".join(comments)
    
    def evaluate_task_4_logic(self, task_text: str, similarity_ref: float,
                              cheating_metrics: Optional[Dict]) -> float:
        """
        Evaluate logic score (0-100%) for task 4.
        
        Args:
            task_text: Task 4 answer text
            similarity_ref: Similarity with reference (if available)
            cheating_metrics: Cheating detection metrics
            
        Returns:
            Logic score as percentage (0-100)
        """
        prompt = f"""Оцени логичность следующего ответа студента по шкале от 0 до 100%.

Ответ студента:
{task_text[:500]}

Оцени:
- Логическую последовательность мыслей
- Связность аргументов
- Структурированность изложения
- Соответствие логике рассуждения

Верни только число от 0 до 100 (процент логичности), без дополнительных комментариев:"""
        
        # Generate evaluation
        if self.use_api:
            result = self._generate_api(prompt)
            if result:
                score = self._extract_score(result)
                if score is not None:
                    return score
        
        # Fallback to local
        result = self._generate_local(prompt)
        if result:
            score = self._extract_score(result)
            if score is not None:
                return score
        
        # Fallback calculation based on metrics
        return self._calculate_logic_fallback(task_text, similarity_ref, cheating_metrics)
    
    def evaluate_task_4_originality(self, task_text: str, 
                                    similarity_existing: Optional[Dict],
                                    cheating_metrics: Optional[Dict]) -> float:
        """
        Evaluate originality score (0-100%) for task 4.
        
        Args:
            task_text: Task 4 answer text
            similarity_existing: Similarity with existing answers
            cheating_metrics: Cheating detection metrics
            
        Returns:
            Originality score as percentage (0-100)
        """
        # Calculate max similarity with existing
        max_similarity = 0.0
        if similarity_existing and similarity_existing.get('top_similar'):
            max_similarity = similarity_existing['top_similar'][0].get('overall_similarity', 0)
        
        prompt = f"""Оцени оригинальность следующего ответа студента по шкале от 0 до 100%.

Ответ студента:
{task_text[:500]}

Максимальная схожесть с другими ответами: {max_similarity:.1%}

Оцени:
- Уникальность формулировок
- Оригинальность подхода
- Неповторимость изложения
- Творческий подход

Верни только число от 0 до 100 (процент оригинальности), без дополнительных комментариев:"""
        
        # Generate evaluation
        if self.use_api:
            result = self._generate_api(prompt)
            if result:
                score = self._extract_score(result)
                if score is not None:
                    return score
        
        # Fallback to local
        result = self._generate_local(prompt)
        if result:
            score = self._extract_score(result)
            if score is not None:
                return score
        
        # Fallback calculation based on similarity
        return self._calculate_originality_fallback(max_similarity, cheating_metrics)
    
    def _extract_score(self, text: str) -> Optional[float]:
        """Extract numeric score from LLM response."""
        import re
        
        # Try to find number between 0 and 100
        numbers = re.findall(r'\b(\d+(?:\.\d+)?)\b', text)
        for num_str in numbers:
            try:
                num = float(num_str)
                if 0 <= num <= 100:
                    return num
            except ValueError:
                continue
        
        return None
    
    def _calculate_logic_fallback(self, task_text: str, similarity_ref: float,
                                 cheating_metrics: Optional[Dict]) -> float:
        """Fallback logic score calculation."""
        score = 50.0  # Base score
        
        # Adjust based on similarity
        if similarity_ref > 0:
            score += similarity_ref * 30  # Up to +30 for high similarity
        
        # Adjust based on structure
        if task_text:
            sentence_count = task_text.count('.') + task_text.count('!') + task_text.count('?')
            if sentence_count >= 3:
                score += 10  # Good structure
            elif sentence_count >= 1:
                score += 5
        
        # Adjust based on cheating metrics
        if cheating_metrics:
            llm_likelihood = cheating_metrics.get('llm_likelihood', 0.5)
            score -= llm_likelihood * 20  # Penalty for LLM-like text
        
        return max(0.0, min(100.0, score))
    
    def _calculate_originality_fallback(self, max_similarity: float,
                                       cheating_metrics: Optional[Dict]) -> float:
        """Fallback originality score calculation."""
        # Lower similarity = higher originality
        originality = (1.0 - max_similarity) * 100
        
        # Adjust based on cheating metrics
        if cheating_metrics:
            llm_likelihood = cheating_metrics.get('llm_likelihood', 0.5)
            # High LLM likelihood suggests less originality
            originality -= llm_likelihood * 20
        
        return max(0.0, min(100.0, originality))


# Global instance
_grading_service = None

def get_grading_service() -> GradingService:
    """Get global grading service instance."""
    global _grading_service
    if _grading_service is None:
        _grading_service = GradingService()
    return _grading_service
