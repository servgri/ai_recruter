"""Scoring service for automatic task evaluation."""

from typing import Dict, Optional


class ScoringService:
    """Service for automatic scoring of tasks 1-3."""
    
    def calculate_task_score(self, task_num: int, similarity_ref: float, 
                            cheating_metrics: Optional[Dict], task_text: str) -> float:
        """
        Calculate automatic score (0-10) for tasks 1-3.
        
        Scoring formula:
        - 50% from similarity with reference
        - 30% from answer quality (readability, structure)
        - 20% from absence of cheating indicators
        
        Args:
            task_num: Task number (1-3)
            similarity_ref: Similarity with reference answer (0-1)
            cheating_metrics: Cheating detection metrics for the task
            task_text: Task text content
            
        Returns:
            Score from 0 to 10
        """
        # Component 1: Similarity with reference (50% weight)
        similarity_score = similarity_ref * 10 * 0.5
        
        # Component 2: Answer quality (30% weight)
        quality_score = self._calculate_quality_score(task_text, cheating_metrics)
        
        # Component 3: Absence of cheating (20% weight)
        cheating_score = self._calculate_anti_cheating_score(cheating_metrics)
        
        # Total score
        total_score = similarity_score + quality_score + cheating_score
        
        # Ensure score is between 0 and 10
        return max(0.0, min(10.0, total_score))
    
    def _calculate_quality_score(self, task_text: str, 
                                cheating_metrics: Optional[Dict]) -> float:
        """
        Calculate quality score based on readability and structure.
        
        Args:
            task_text: Task text content
            cheating_metrics: Cheating detection metrics
            
        Returns:
            Quality score (0-3.0, representing 30% of total)
        """
        if not task_text or len(task_text.strip()) < 10:
            return 0.0
        
        score = 0.0
        
        # Readability component (0-1.5)
        if cheating_metrics:
            readability = cheating_metrics.get('readability', 0)
            # Normalize readability (0-100 scale, target: 50-80 is good)
            if readability >= 50:
                readability_score = min(1.5, (readability - 50) / 30 * 1.5)
            else:
                readability_score = readability / 50 * 1.5
            score += readability_score
        
        # Structure component (0-1.5)
        # Check for proper structure: sentences, paragraphs, punctuation
        sentence_count = task_text.count('.') + task_text.count('!') + task_text.count('?')
        word_count = len(task_text.split())
        
        if word_count > 0:
            # Good structure: 10-20 words per sentence
            avg_words_per_sentence = word_count / max(1, sentence_count)
            if 10 <= avg_words_per_sentence <= 20:
                structure_score = 1.5
            elif 5 <= avg_words_per_sentence < 10 or 20 < avg_words_per_sentence <= 30:
                structure_score = 1.0
            else:
                structure_score = 0.5
            score += structure_score
        
        return min(3.0, score)
    
    def _calculate_anti_cheating_score(self, cheating_metrics: Optional[Dict]) -> float:
        """
        Calculate score based on absence of cheating indicators.
        
        Args:
            cheating_metrics: Cheating detection metrics
            
        Returns:
            Anti-cheating score (0-2.0, representing 20% of total)
        """
        if not cheating_metrics:
            return 1.0  # Default middle score if no metrics
        
        llm_likelihood = cheating_metrics.get('llm_likelihood', 0.5)
        
        # Lower LLM likelihood = higher score
        # Score ranges from 0 to 2.0
        anti_cheating_score = (1.0 - llm_likelihood) * 2.0
        
        # Bonus for low punctuation errors
        punctuation_errors = cheating_metrics.get('punctuation_errors', {})
        if isinstance(punctuation_errors, dict):
            total_errors = punctuation_errors.get('total_errors', 0)
            if total_errors == 0:
                anti_cheating_score += 0.2
            elif total_errors <= 2:
                anti_cheating_score += 0.1
        
        return min(2.0, max(0.0, anti_cheating_score))
    
    def calculate_average_score_tasks_1_3(self, task_1_score: Optional[float],
                                         task_2_score: Optional[float],
                                         task_3_score: Optional[float]) -> Optional[float]:
        """
        Calculate average score for tasks 1-3.
        
        Args:
            task_1_score: Score for task 1 (0-10)
            task_2_score: Score for task 2 (0-10)
            task_3_score: Score for task 3 (0-10)
            
        Returns:
            Average score or None if not all scores are available
        """
        scores = []
        if task_1_score is not None:
            scores.append(task_1_score)
        if task_2_score is not None:
            scores.append(task_2_score)
        if task_3_score is not None:
            scores.append(task_3_score)
        
        if len(scores) == 0:
            return None
        
        return sum(scores) / len(scores)


# Global instance
_scoring_service = None

def get_scoring_service() -> ScoringService:
    """Get global scoring service instance."""
    global _scoring_service
    if _scoring_service is None:
        _scoring_service = ScoringService()
    return _scoring_service
