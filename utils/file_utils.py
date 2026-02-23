"""File utilities for hashing and file management."""

import os
import hashlib
from typing import Optional


def calculate_file_hash(file_path: str, short_hash: bool = False) -> str:
    """
    Calculate SHA256 hash of file content.
    
    Args:
        file_path: Path to the file
        short_hash: If True, return first 5 characters of hash (for filename)
        
    Returns:
        SHA256 hash as hexadecimal string (full or 5-char short)
    """
    sha256_hash = hashlib.sha256()
    
    try:
        with open(file_path, "rb") as f:
            # Read file in chunks to handle large files
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        
        full_hash = sha256_hash.hexdigest()
        if short_hash:
            return full_hash[:5]
        return full_hash
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
    Save file with 5-character hash-based filename.
    
    Args:
        content: File content as bytes
        extension: File extension (e.g., 'docx', 'pdf')
        original_filename: Original filename for reference
        loaded_dir: Directory to save files (default: 'loaded')
        
    Returns:
        Tuple of (file_path, full_file_hash) where filename uses 5-char hash
    """
    # Create directory if it doesn't exist
    os.makedirs(loaded_dir, exist_ok=True)
    
    # Calculate full hash for database
    sha256_hash = hashlib.sha256()
    sha256_hash.update(content)
    full_hash = sha256_hash.hexdigest()
    
    # Use first 5 characters for filename
    short_hash = full_hash[:5]
    
    # Create filename: {5-char-hash}.{extension}
    filename = f"{short_hash}.{extension}"
    file_path = os.path.join(loaded_dir, filename)
    
    # Check if file already exists (collision handling)
    if os.path.exists(file_path):
        # Verify it's the same file by comparing full hash
        existing_hash = calculate_file_hash(file_path)
        if existing_hash == full_hash:
            # Same file - return existing path
            return file_path, full_hash
        else:
            # Hash collision - append counter
            counter = 1
            while True:
                filename = f"{short_hash}_{counter}.{extension}"
                file_path = os.path.join(loaded_dir, filename)
                if not os.path.exists(file_path):
                    break
                # Check if existing file has same hash
                existing_hash = calculate_file_hash(file_path)
                if existing_hash == full_hash:
                    return file_path, full_hash
                counter += 1
    
    # Save file
    with open(file_path, 'wb') as f:
        f.write(content)
    
    return file_path, full_hash


def save_text_file_with_hash(content: str, extension: str, original_filename: str,
                            loaded_dir: str = "loaded") -> tuple[str, str]:
    """
    Save text file with 5-character hash-based filename.
    
    Args:
        content: Text content
        extension: File extension (e.g., 'txt', 'md')
        original_filename: Original filename for reference
        loaded_dir: Directory to save files (default: 'loaded')
        
    Returns:
        Tuple of (file_path, full_file_hash) where filename uses 5-char hash
    """
    # Create directory if it doesn't exist
    os.makedirs(loaded_dir, exist_ok=True)
    
    # Calculate full hash for database
    full_hash = calculate_content_hash(content)
    
    # Use first 5 characters for filename
    short_hash = full_hash[:5]
    
    # Create filename: {5-char-hash}.{extension}
    filename = f"{short_hash}.{extension}"
    file_path = os.path.join(loaded_dir, filename)
    
    # Check if file already exists (collision handling)
    if os.path.exists(file_path):
        # Verify it's the same file by comparing full hash
        existing_hash = calculate_content_hash(open(file_path, 'r', encoding='utf-8').read())
        if existing_hash == full_hash:
            # Same file - return existing path
            return file_path, full_hash
        else:
            # Hash collision - append counter
            counter = 1
            while True:
                filename = f"{short_hash}_{counter}.{extension}"
                file_path = os.path.join(loaded_dir, filename)
                if not os.path.exists(file_path):
                    break
                # Check if existing file has same hash
                existing_hash = calculate_content_hash(open(file_path, 'r', encoding='utf-8').read())
                if existing_hash == full_hash:
                    return file_path, full_hash
                counter += 1
    
    # Save file
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    return file_path, full_hash
