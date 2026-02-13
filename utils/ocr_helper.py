"""OCR helper for extracting text from images."""

import os
import tempfile
from typing import Optional, List
from io import BytesIO


class OCRHelper:
    """Helper class for OCR (Optical Character Recognition) operations."""
    
    @staticmethod
    def extract_text_from_image(image_data: bytes, lang: str = 'rus+eng') -> str:
        """
        Extract text from image using OCR.
        
        Args:
            image_data: Image data as bytes
            lang: Language for OCR (default: 'rus+eng' for Russian and English)
            
        Returns:
            Extracted text from image
        """
        try:
            import pytesseract
            from PIL import Image
            
            # Open image from bytes
            image = Image.open(BytesIO(image_data))
            
            # Convert to RGB if necessary (some images might be in other modes)
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Perform OCR with config for better accuracy
            # Use --psm 6 for uniform block of text
            config = '--psm 6'
            
            try:
                text = pytesseract.image_to_string(image, lang=lang, config=config)
            except Exception:
                # If language-specific OCR fails, try without language
                try:
                    text = pytesseract.image_to_string(image, config=config)
                except Exception:
                    # Last resort: basic OCR
                    text = pytesseract.image_to_string(image)
            
            # Clean up text
            text = text.strip()
            
            # Remove excessive whitespace
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            text = '\n'.join(lines)
            
            return text
        except ImportError:
            # OCR libraries not available - return empty string to avoid cluttering output
            return ""
        except Exception as e:
            # OCR failed - return empty string
            return ""
    
    @staticmethod
    def extract_text_from_image_file(image_path: str, lang: str = 'rus+eng') -> str:
        """
        Extract text from image file using OCR.
        
        Args:
            image_path: Path to image file
            lang: Language for OCR (default: 'rus+eng')
            
        Returns:
            Extracted text from image
        """
        try:
            with open(image_path, 'rb') as f:
                image_data = f.read()
            return OCRHelper.extract_text_from_image(image_data, lang)
        except Exception as e:
            return f"[Изображение: Ошибка чтения файла - {str(e)}]"
    
    @staticmethod
    def is_ocr_available() -> bool:
        """
        Check if OCR is available.
        
        Returns:
            True if OCR libraries are available, False otherwise
        """
        try:
            import pytesseract
            from PIL import Image
            # Try to get version to verify installation
            pytesseract.get_tesseract_version()
            return True
        except (ImportError, Exception):
            return False
