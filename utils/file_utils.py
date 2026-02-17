"""File utilities for hashing and file management."""

import os
import hashlib
from typing import Optional


def calculate_file_hash(file_path: str) -> str:
    """
    Calculate SHA256 hash of file content.
    
    Args:
        file_path: Path to the file
        
    Returns:
        SHA256 hash as hexadecimal string
    """
    sha256_hash = hashlib.sha256()
    
    try:
        with open(file_path, "rb") as f:
            # Read file in chunks to handle large files
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        
        return sha256_hash.hexdigest()
    except Exception as e:
        raise Exception(f"Error calculating file hash: {str(e)}")


def calculate_content_hash(content: str) -> str:
    """
    Calculate SHA256 hash of text content.
    
    Args:
        content: Text content to hash
        
    Returns:
        SHA256 hash as hexadecimal string
    """
    sha256_hash = hashlib.sha256()
    sha256_hash.update(content.encode('utf-8'))
    return sha256_hash.hexdigest()


def save_file_with_hash(content: bytes, extension: str, original_filename: str, 
                       loaded_dir: str = "loaded") -> tuple[str, str]:
    """
    Save file with hash-based filename.
    
    Args:
        content: File content as bytes
        extension: File extension (e.g., 'docx', 'pdf')
        original_filename: Original filename for reference
        loaded_dir: Directory to save files (default: 'loaded')
        
    Returns:
        Tuple of (file_path, file_hash)
    """
    # Create directory if it doesn't exist
    os.makedirs(loaded_dir, exist_ok=True)
    
    # Calculate hash
    sha256_hash = hashlib.sha256()
    sha256_hash.update(content)
    file_hash = sha256_hash.hexdigest()
    
    # Create filename: {hash}.{extension}
    filename = f"{file_hash}.{extension}"
    file_path = os.path.join(loaded_dir, filename)
    
    # Save file
    with open(file_path, 'wb') as f:
        f.write(content)
    
    return file_path, file_hash


def save_text_file_with_hash(content: str, extension: str, original_filename: str,
                            loaded_dir: str = "loaded") -> tuple[str, str]:
    """
    Save text file with hash-based filename.
    
    Args:
        content: Text content
        extension: File extension (e.g., 'txt', 'md')
        original_filename: Original filename for reference
        loaded_dir: Directory to save files (default: 'loaded')
        
    Returns:
        Tuple of (file_path, file_hash)
    """
    # Create directory if it doesn't exist
    os.makedirs(loaded_dir, exist_ok=True)
    
    # Calculate hash
    file_hash = calculate_content_hash(content)
    
    # Create filename: {hash}.{extension}
    filename = f"{file_hash}.{extension}"
    file_path = os.path.join(loaded_dir, filename)
    
    # Save file
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    return file_path, file_hash
