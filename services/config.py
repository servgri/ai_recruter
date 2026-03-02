"""Configuration for services."""

import os

# Embedding method configuration
EMBEDDING_METHOD = os.getenv("EMBEDDING_METHOD", "sbert")  # "sbert" or "qwen"

# API priority configuration
API_PRIORITY = os.getenv("API_PRIORITY", "api_first")  # "api_first" or "local_first"

# Hugging Face API configuration
HF_API_TOKEN = os.getenv("HF_API_TOKEN", "")
HF_API_BASE_URL = "https://api-inference.huggingface.co/models"

# Local models directory
LOCAL_MODELS_DIR = os.getenv("LOCAL_MODELS_DIR", "models")
os.makedirs(LOCAL_MODELS_DIR, exist_ok=True)

# Model names
SBERT_MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
SBERT_MODEL_NAME_API = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

QWEN_MODEL_NAME = "Qwen/Qwen2.5-0.5B-Instruct"
QWEN_EMBEDDING_MODEL = "Qwen/Qwen2.5-0.5B-Instruct"  # For embeddings, may need different model

# Task cleaner configuration
TAIL_DETECTION_SIMILARITY_THRESHOLD = 0.75  # Cosine similarity threshold for tail detection
TAIL_DETECTION_MIN_LENGTH = 20  # Minimum length of text fragment to consider as tail

# Analysis configuration
REFERENCE_FILE = "Правильные ответы на задание.txt"

# Eval v6 etalon paths (JSON: [{"task_number": int, "content": str}, ...])
_etalon_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "microsevice_eval", "etalon_responses")
ETALON_HR_JSON = os.getenv("ETALON_HR_JSON", os.path.join(_etalon_dir, "etalon_hr.json"))
ETALON_AI_JSON = os.getenv("ETALON_AI_JSON", os.path.join(_etalon_dir, "etalon_ai.json"))

# LLM likelihood (cheating detection): "heuristic" or "bertscore"
LLM_LIKELIHOOD_METHOD = os.getenv("LLM_LIKELIHOOD_METHOD", "heuristic").strip().lower()
# BERT-score: model for embeddings (Russian-friendly)
BERTSCORE_MODEL = os.getenv("BERTSCORE_MODEL", "cointegrated/rubert-tiny2").strip()
# Optional: path to file with reference lines (one line = one reference); if empty, use built-in default
BERTSCORE_REFERENCE_FILE = os.getenv("BERTSCORE_REFERENCE_FILE", "").strip()
