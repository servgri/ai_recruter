"""Cheating detection utilities."""

import os
import re
from typing import Dict, List, Optional
import textstat


def calculate_readability(text: str) -> float:
    """
    Calculate Flesch Reading Ease score.
    
    Args:
        text: Input text
        
    Returns:
        Readability score (0-100, higher = easier to read)
    """
    if not text or len(text.strip()) < 10:
        return 0.0
    
    try:
        # For Russian text, use Flesch Reading Ease
        # Note: textstat may not be perfect for Russian, but gives a baseline
        score = textstat.flesch_reading_ease(text)
        return float(score)
    except Exception:
        return 0.0


def count_adjectives_and_adverbs(text: str) -> Dict[str, int]:
    """
    Count adjectives and adverbs in text.
    
    Args:
        text: Input text
        
    Returns:
        Dictionary with counts
    """
    try:
        import spacy
        
        # Try to load Russian model
        try:
            nlp = spacy.load("ru_core_news_sm")
        except OSError:
            # Fallback to English if Russian not available
            try:
                nlp = spacy.load("en_core_web_sm")
            except OSError:
                # If no models available, use simple regex
                return {
                    'adjectives': 0,
                    'adverbs': 0,
                    'total_words': len(text.split())
                }
        
        doc = nlp(text)
        adjectives = sum(1 for token in doc if token.pos_ == "ADJ")
        adverbs = sum(1 for token in doc if token.pos_ == "ADV")
        
        return {
            'adjectives': adjectives,
            'adverbs': adverbs,
            'total_words': len(doc)
        }
    except ImportError:
        # Fallback to simple word count
        words = text.split()
        return {
            'adjectives': 0,
            'adverbs': 0,
            'total_words': len(words)
        }
    except Exception:
        return {
            'adjectives': 0,
            'adverbs': 0,
            'total_words': len(text.split())
        }


def detect_special_characters(text: str) -> Dict[str, bool]:
    """
    Detect special characters (emojis, long dashes, etc.).
    
    Args:
        text: Input text
        
    Returns:
        Dictionary with detection results
    """
    # Emoji pattern
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F1E0-\U0001F1FF"  # flags
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "]+",
        flags=re.UNICODE
    )
    
    has_emoji = bool(emoji_pattern.search(text))
    
    # Long dash (—)
    has_long_dash = '—' in text or '–' in text
    
    # Other special Unicode characters
    has_special_unicode = bool(re.search(r'[^\w\s\.,;:!?\-\(\)\[\]{}"\']', text))
    
    return {
        'has_emoji': has_emoji,
        'has_long_dash': has_long_dash,
        'has_special_unicode': has_special_unicode,
        'special_chars_count': len(re.findall(r'[^\w\s\.,;:!?\-\(\)\[\]{}"\']', text))
    }


def check_punctuation_errors(text: str) -> Dict[str, int]:
    """
    Check for basic punctuation errors.
    
    Args:
        text: Input text
        
    Returns:
        Dictionary with error counts
    """
    errors = {
        'missing_spaces_after_punctuation': 0,
        'double_spaces': 0,
        'missing_capitalization': 0
    }
    
    # Check for missing spaces after punctuation
    missing_spaces = len(re.findall(r'[.,;:!?][А-Яа-яA-Za-z]', text))
    errors['missing_spaces_after_punctuation'] = missing_spaces
    
    # Check for double spaces
    double_spaces = len(re.findall(r'  +', text))
    errors['double_spaces'] = double_spaces
    
    # Check for missing capitalization after sentence end
    # (simplified check)
    sentences = re.split(r'[.!?]\s+', text)
    missing_caps = sum(1 for s in sentences[1:] if s and not s[0].isupper())
    errors['missing_capitalization'] = missing_caps
    
    errors['total_errors'] = sum(errors.values())
    
    return errors


# Default reference for BERT-score (typical formal/LLM-style Russian)
_DEFAULT_LLM_REFERENCE_RU = (
    "Следует отметить, что в соответствии с указанными требованиями необходимо "
    "учитывать следующие аспекты: во-первых, структура данных должна соответствовать "
    "принципам нормализации; во-вторых, важно обеспечить целостность и согласованность."
)


def _get_bertscore_references() -> List[str]:
    """Load reference line(s) for BERT-score from config file or return default."""
    try:
        from services.config import BERTSCORE_REFERENCE_FILE
    except ImportError:
        return [_DEFAULT_LLM_REFERENCE_RU]
    if not BERTSCORE_REFERENCE_FILE or not os.path.isfile(BERTSCORE_REFERENCE_FILE):
        return [_DEFAULT_LLM_REFERENCE_RU]
    refs = []
    with open(BERTSCORE_REFERENCE_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                refs.append(line)
    return refs if refs else [_DEFAULT_LLM_REFERENCE_RU]


def _detect_llm_likelihood_bertscore(text: str) -> float:
    """
    LLM likelihood via BERT-score: similarity of text to reference(s).
    Higher F1 with LLM-style reference = higher likelihood.

    Returns:
        Score 0.0..1.0 (higher = more LLM-like).
    """
    if not text or not text.strip():
        return 0.0
    try:
        from bert_score import score as bert_score_fn
    except ImportError:
        return _detect_llm_likelihood_heuristic(text)
    try:
        from services.config import BERTSCORE_MODEL
        model_type = BERTSCORE_MODEL
    except ImportError:
        model_type = "cointegrated/rubert-tiny2"
    refs = _get_bertscore_references()
    cands = [text.strip()]
    refs_list = [refs]  # one candidate, multiple refs: refs_list[i] = list of refs for cands[i]
    try:
        P, R, F1 = bert_score_fn(cands, refs_list, model_type=model_type, lang="ru", verbose=False)
        # F1: tensor of shape (1,); take max over refs (bert_score returns best match per ref set)
        f1_val = float(F1[0].item())
        return min(1.0, max(0.0, f1_val))
    except Exception:
        return _detect_llm_likelihood_heuristic(text)


def _detect_llm_likelihood_heuristic(text: str) -> float:
    """
    Heuristic-based LLM likelihood (numbered lists, bullet points, formal phrases).
    Uses gradual scoring so typical answers get non-zero values instead of always 0.
    """
    if not text or not text.strip():
        return 0.0
    score = 0.0
    # Numbered lists: gradual (1+ → 0.05, 2+ → 0.1, 3+ → 0.15, 4+ → 0.2)
    numbered_list_pattern = r'\d+[\.\)]\s+[А-Яа-яA-Z]'
    numbered_lists = len(re.findall(numbered_list_pattern, text))
    if numbered_lists >= 4:
        score += 0.2
    elif numbered_lists == 3:
        score += 0.15
    elif numbered_lists == 2:
        score += 0.1
    elif numbered_lists >= 1:
        score += 0.05
    # Bullet points: up to 0.2 (each 1–5 count adds ~0.04)
    bullet_points = min(text.count('•') + text.count('*') + len(re.findall(r'^\s*[-–]\s+', text, re.MULTILINE)), 10)
    if bullet_points >= 5:
        score += 0.2
    elif bullet_points >= 2:
        score += 0.05 + (bullet_points - 2) * 0.05
    elif bullet_points >= 1:
        score += 0.05
    # Formal LLM phrases (Russian/English)
    llm_phrases = [
        'следует отметить', 'необходимо отметить', 'важно отметить',
        'стоит отметить', 'можно отметить', 'it should be noted',
        'it is important to', 'it is necessary to', 'в заключение',
        'подводя итог', 'таким образом', 'с одной стороны', 'с другой стороны',
    ]
    phrase_count = sum(1 for phrase in llm_phrases if phrase.lower() in text.lower())
    if phrase_count >= 3:
        score += 0.3
    elif phrase_count == 2:
        score += 0.2
    elif phrase_count >= 1:
        score += 0.1
    # Section-style headers (Title: ...)
    section_headers = len(re.findall(r'^[А-Яа-яA-Z][^.!?]{0,50}:', text, re.MULTILINE))
    if section_headers >= 4:
        score += 0.2
    elif section_headers >= 2:
        score += 0.05 + (section_headers - 2) * 0.05
    elif section_headers >= 1:
        score += 0.05
    # Formal patterns (regex or literal; re.search works for both)
    formal_patterns = [
        r'в\s+связи\s+с\s+тем', r'в\s+соответствии\s+с', r'с\s+учетом\s+того',
        r'во-первых', r'во-вторых', r'in accordance with', r'with regard to',
    ]
    formal_count = sum(1 for p in formal_patterns if re.search(p, text, re.IGNORECASE))
    if formal_count >= 2:
        score += 0.1
    elif formal_count >= 1:
        score += 0.05
    # Slight baseline for longer structured text (multiple sentences)
    if len(text.strip()) >= 100 and ('. ' in text or '\n' in text):
        score = max(score, 0.05)
    out = min(1.0, max(0.0, score))
    # #region agent log
    try:
        _log_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        _log_path = os.path.join(_log_dir, "debug-72df92.log")
        with open(_log_path, "a", encoding="utf-8") as _f:
            _f.write('{"sessionId":"72df92","message":"LLM heuristic","data":{"text_len":%d,"score":%.3f,"numbered":%d,"bullet":%d,"phrase":%d,"formal":%d},"timestamp":%d}\n' % (
                len(text.strip()), out, numbered_lists, bullet_points, phrase_count, formal_count,
                __import__("time").time_ns() // 1000000))
    except Exception:
        pass
    # #endregion
    return out


def detect_llm_likelihood(text: str, method: Optional[str] = None) -> float:
    """
    Detect likelihood that text was generated by LLM.

    Method: "heuristic" (default) or "bertscore".
    Config: LLM_LIKELIHOOD_METHOD, BERTSCORE_MODEL, BERTSCORE_REFERENCE_FILE.

    Args:
        text: Input text
        method: Override config: "heuristic" or "bertscore" (None = use config)

    Returns:
        Score from 0.0 to 1.0 (higher = more likely LLM-generated)
    """
    if method is None:
        try:
            from services.config import LLM_LIKELIHOOD_METHOD
            method = LLM_LIKELIHOOD_METHOD or "heuristic"
        except ImportError:
            method = "heuristic"
    method = (method or "heuristic").strip().lower()
    if method == "bertscore":
        return _detect_llm_likelihood_bertscore(text)
    return _detect_llm_likelihood_heuristic(text)


def analyze_cheating(text: str) -> Dict:
    """
    Comprehensive cheating detection analysis.
    
    Args:
        text: Input text
        
    Returns:
        Dictionary with all analysis results
    """
    readability = calculate_readability(text)
    pos_counts = count_adjectives_and_adverbs(text)
    special_chars = detect_special_characters(text)
    punctuation_errors = check_punctuation_errors(text)
    llm_likelihood = detect_llm_likelihood(text)
    
    return {
        'readability': readability,
        'adjectives_count': pos_counts.get('adjectives', 0),
        'adverbs_count': pos_counts.get('adverbs', 0),
        'total_words': pos_counts.get('total_words', 0),
        'special_chars': special_chars,
        'punctuation_errors': punctuation_errors,
        'llm_likelihood': llm_likelihood
    }
