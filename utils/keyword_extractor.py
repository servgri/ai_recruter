"""Keyword extraction utilities for reference answers."""

import re
from typing import Dict, List
from sklearn.feature_extraction.text import TfidfVectorizer
from utils.embedding_utils import load_reference_answers
from services.config import REFERENCE_FILE


# Russian stop words
RUSSIAN_STOP_WORDS = {
    'и', 'в', 'во', 'не', 'что', 'он', 'на', 'я', 'с', 'со', 'как', 'а', 'то', 'все',
    'она', 'так', 'его', 'но', 'да', 'ты', 'к', 'у', 'же', 'вы', 'за', 'бы', 'по',
    'только', 'ее', 'мне', 'было', 'вот', 'от', 'меня', 'еще', 'нет', 'о', 'из',
    'ему', 'теперь', 'когда', 'даже', 'ну', 'вдруг', 'ли', 'если', 'уже', 'или',
    'ни', 'быть', 'был', 'него', 'до', 'вас', 'нибудь', 'опять', 'уж', 'вам', 'ведь',
    'там', 'потом', 'себя', 'ничего', 'ей', 'может', 'они', 'тут', 'где', 'есть',
    'надо', 'ней', 'для', 'мы', 'тебя', 'их', 'чем', 'была', 'сам', 'чтоб', 'без',
    'будто', 'чего', 'раз', 'тоже', 'себе', 'под', 'будет', 'ж', 'тогда', 'кто',
    'этот', 'того', 'потому', 'этого', 'какой', 'совсем', 'ним', 'здесь', 'этом',
    'один', 'почти', 'мой', 'тем', 'чтобы', 'нее', 'сейчас', 'были', 'куда', 'зачем',
    'всех', 'никогда', 'можно', 'при', 'наконец', 'два', 'об', 'другой', 'хоть',
    'после', 'над', 'больше', 'тот', 'через', 'эти', 'нас', 'про', 'всего', 'них',
    'какая', 'много', 'разве', 'три', 'эту', 'моя', 'впрочем', 'хорошо', 'свою',
    'этой', 'перед', 'иногда', 'лучше', 'чуть', 'том', 'нельзя', 'такой', 'им',
    'более', 'всегда', 'конечно', 'всю', 'между'
}

# English stop words
ENGLISH_STOP_WORDS = {
    'the', 'be', 'to', 'of', 'and', 'a', 'in', 'that', 'have', 'i', 'it', 'for',
    'not', 'on', 'with', 'he', 'as', 'you', 'do', 'at', 'this', 'but', 'his', 'by',
    'from', 'they', 'we', 'say', 'her', 'she', 'or', 'an', 'will', 'my', 'one',
    'all', 'would', 'there', 'their', 'what', 'so', 'up', 'out', 'if', 'about',
    'who', 'get', 'which', 'go', 'me', 'when', 'make', 'can', 'like', 'time',
    'no', 'just', 'him', 'know', 'take', 'people', 'into', 'year', 'your', 'good',
    'some', 'could', 'them', 'see', 'other', 'than', 'then', 'now', 'look', 'only',
    'come', 'its', 'over', 'think', 'also', 'back', 'after', 'use', 'two', 'how',
    'our', 'work', 'first', 'well', 'way', 'even', 'new', 'want', 'because', 'any',
    'these', 'give', 'day', 'most', 'us'
}

# Combined stop words
STOP_WORDS = RUSSIAN_STOP_WORDS | ENGLISH_STOP_WORDS


def extract_keywords_from_reference(file_path: str = None, num_keywords: int = 15) -> Dict[int, List[str]]:
    """
    Extract keywords from reference answers using TF-IDF.
    
    Args:
        file_path: Path to reference answers file (defaults to REFERENCE_FILE)
        num_keywords: Number of keywords to extract per task (default: 15)
        
    Returns:
        Dictionary mapping task number (1-4) to list of keywords
    """
    if file_path is None:
        file_path = REFERENCE_FILE
    
    # Load reference answers
    reference_answers = load_reference_answers(file_path)
    
    if not reference_answers:
        return {}
    
    keywords_dict = {}
    
    # Process each task separately
    for task_num in range(1, 5):
        if task_num not in reference_answers:
            keywords_dict[task_num] = []
            continue
        
        task_text = reference_answers[task_num]
        
        if not task_text or len(task_text.strip()) < 10:
            keywords_dict[task_num] = []
            continue
        
        # Clean and preprocess text
        cleaned_text = _preprocess_text(task_text)
        
        if not cleaned_text:
            keywords_dict[task_num] = []
            continue
        
        # Extract keywords using TF-IDF
        keywords = _extract_keywords_tfidf(cleaned_text, num_keywords)
        keywords_dict[task_num] = keywords
    
    return keywords_dict


def _preprocess_text(text: str) -> str:
    """
    Preprocess text for keyword extraction.
    
    Args:
        text: Input text
        
    Returns:
        Preprocessed text
    """
    # Remove special characters but keep spaces and basic punctuation
    text = re.sub(r'[^\w\s]', ' ', text)
    
    # Convert to lowercase
    text = text.lower()
    
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text


def _extract_keywords_tfidf(text: str, num_keywords: int = 15) -> List[str]:
    """
    Extract keywords from text using TF-IDF.
    
    Args:
        text: Input text
        num_keywords: Number of keywords to extract
        
    Returns:
        List of keywords sorted by TF-IDF score
    """
    if not text or len(text.strip()) < 10:
        return []
    
    # Custom tokenizer that handles both Russian and English
    def tokenize(text):
        # Split by whitespace and filter out stop words and short words
        tokens = text.split()
        tokens = [t for t in tokens if len(t) > 2 and t not in STOP_WORDS]
        return tokens
    
    try:
        # Tokenize first to check if we have enough words
        tokens = tokenize(text)
        if len(tokens) < 3:
            # Too few tokens, use simple extraction
            return _extract_keywords_simple(text, num_keywords)
        
        # Create TF-IDF vectorizer
        # Use unigrams and bigrams for better keyword extraction
        # For single document, use min_df=1 and max_df=1.0 to avoid conflicts
        vectorizer = TfidfVectorizer(
            max_features=num_keywords * 2,  # Get more features to filter
            ngram_range=(1, 2),  # Unigrams and bigrams
            tokenizer=tokenize,
            token_pattern=None,  # Use custom tokenizer
            lowercase=True,
            stop_words=None,  # We handle stop words in tokenizer
            min_df=1,  # Word must appear at least once (for single document)
            max_df=1.0  # For single document, allow all words (100%)
        )
        
        # Fit and transform
        tfidf_matrix = vectorizer.fit_transform([text])
        
        # Get feature names and scores
        feature_names = vectorizer.get_feature_names_out()
        scores = tfidf_matrix.toarray()[0]
        
        # Create list of (keyword, score) tuples
        keyword_scores = list(zip(feature_names, scores))
        
        # Sort by score (descending)
        keyword_scores.sort(key=lambda x: x[1], reverse=True)
        
        # Extract top keywords
        keywords = [kw for kw, score in keyword_scores[:num_keywords]]
        
        # Filter out very short keywords and ensure minimum length
        keywords = [kw for kw in keywords if len(kw) > 2]
        
        # Remove duplicates while preserving order
        seen = set()
        unique_keywords = []
        for kw in keywords:
            if kw not in seen:
                seen.add(kw)
                unique_keywords.append(kw)
        
        return unique_keywords[:num_keywords]
    
    except Exception as e:
        print(f"Error extracting keywords: {e}")
        # Fallback: simple word frequency
        return _extract_keywords_simple(text, num_keywords)


def _extract_keywords_simple(text: str, num_keywords: int = 15) -> List[str]:
    """
    Simple fallback keyword extraction based on word frequency.
    
    Args:
        text: Input text
        num_keywords: Number of keywords to extract
        
    Returns:
        List of keywords
    """
    # Tokenize
    words = re.findall(r'\b\w+\b', text.lower())
    
    # Filter stop words and short words
    words = [w for w in words if len(w) > 2 and w not in STOP_WORDS]
    
    # Count frequencies
    from collections import Counter
    word_freq = Counter(words)
    
    # Get top keywords
    top_words = [word for word, count in word_freq.most_common(num_keywords)]
    
    return top_words


def get_keywords_for_task(task_num: int, file_path: str = None) -> List[str]:
    """
    Get keywords for a specific task.
    
    Args:
        task_num: Task number (1-4)
        file_path: Path to reference answers file
        
    Returns:
        List of keywords for the task
    """
    keywords_dict = extract_keywords_from_reference(file_path)
    return keywords_dict.get(task_num, [])
