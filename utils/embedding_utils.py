"""Utility functions for embeddings."""

import json
import numpy as np
from typing import List, Dict, Optional
from sklearn.metrics.pairwise import cosine_similarity


def cosine_similarity_vectors(vec1: List[float], vec2: List[float]) -> float:
    """
    Calculate cosine similarity between two vectors.
    
    Args:
        vec1: First vector
        vec2: Second vector
        
    Returns:
        Cosine similarity score (0-1)
    """
    if not vec1 or not vec2:
        return 0.0
    
    vec1_array = np.array(vec1).reshape(1, -1)
    vec2_array = np.array(vec2).reshape(1, -1)
    
    similarity = cosine_similarity(vec1_array, vec2_array)[0][0]
    return float(similarity)


def normalize_vector(vec: List[float]) -> List[float]:
    """
    Normalize vector to unit length.
    
    Args:
        vec: Input vector
        
    Returns:
        Normalized vector
    """
    vec_array = np.array(vec)
    norm = np.linalg.norm(vec_array)
    if norm == 0:
        return vec
    return (vec_array / norm).tolist()


def load_embeddings_from_json(json_str: str) -> Optional[List[float]]:
    """
    Load embeddings from JSON string.
    
    Args:
        json_str: JSON string containing embeddings
        
    Returns:
        List of floats or None if invalid
    """
    if not json_str or json_str.strip() == '':
        return None
    
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        return None


def save_embeddings_to_json(embeddings) -> str:
    """
    Save embeddings to JSON string.
    
    Args:
        embeddings: List of embedding values (or numpy array)
        
    Returns:
        JSON string
    """
    if embeddings is None:
        return ''
    
    # Convert numpy array to list if needed
    if hasattr(embeddings, 'tolist'):
        embeddings = embeddings.tolist()
    elif not isinstance(embeddings, list):
        embeddings = list(embeddings)
    
    return json.dumps(embeddings)


def load_reference_answers(file_path: str) -> Dict[int, str]:
    """
    Load reference answers from file and split into tasks.
    
    Args:
        file_path: Path to reference answers file
        
    Returns:
        Dictionary mapping task number to answer text
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        return {}
    
    # Split by "Ответ 1.", "Ответ 2.", etc.
    import re
    pattern = r'Ответ\s+(\d+)\.'
    matches = list(re.finditer(pattern, content, re.IGNORECASE))
    
    tasks = {}
    for i, match in enumerate(matches):
        task_num = int(match.group(1))
        start_pos = match.end()
        
        # Find end position (next "Ответ" or end of file)
        if i + 1 < len(matches):
            end_pos = matches[i + 1].start()
        else:
            end_pos = len(content)
        
        task_text = content[start_pos:end_pos].strip()
        tasks[task_num] = task_text
    
    return tasks
