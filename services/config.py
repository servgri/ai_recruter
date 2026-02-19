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
CSV_FILE = "data_loaded/loaded_data.csv"
