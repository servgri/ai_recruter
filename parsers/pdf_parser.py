"""Parser for PDF files."""

import os
import tempfile
from .base_parser import BaseParser


class PdfParser(BaseParser):
    """Parser for PDF files."""
    
    def parse(self, file_path: str) -> str:
        """
        Extract text from PDF file, including OCR from images.
        
        Args:
            file_path: Path to the PDF file
            
        Returns:
            Extracted text content with OCR text from images
            
        Raises:
            Exception: If file cannot be parsed
        """
        # Import OCR helper
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
        from utils.ocr_helper import OCRHelper
        
        text_parts = []
        
        try:
            import pdfplumber
            with pdfplumber.open(file_path) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    # Extract text from page
                    text = page.extract_text()
                    if text:
                        text_parts.append(text)
                    
                    # Extract images and perform OCR
                    images = page.images
                    if images:
                        image_texts = self._extract_text_from_pdf_images(
                            file_path, page_num, images, OCRHelper
                        )
                        if image_texts:
                            text_parts.append(image_texts)
            
            return '\n'.join(text_parts)
        except ImportError:
            # Fallback to PyPDF2 if pdfplumber is not available
            try:
                import PyPDF2
                text_parts = []
                with open(file_path, 'rb') as file:
                    pdf_reader = PyPDF2.PdfReader(file)
                    for page_num, page in enumerate(pdf_reader.pages):
                        text = page.extract_text()
                        if text:
                            text_parts.append(text)
                        
                        # Try to extract images using pdf2image
                        image_texts = self._extract_text_from_pdf_page_images(
                            file_path, page_num, OCRHelper
                        )
                        if image_texts:
                            text_parts.append(image_texts)
                
                return '\n'.join(text_parts)
            except ImportError:
                raise ImportError("pdfplumber or PyPDF2 is required for PDF parsing. Install with: pip install pdfplumber or pip install PyPDF2")
        except Exception as e:
            raise Exception(f"Error parsing PDF file: {str(e)}")
    
    def _extract_text_from_pdf_images(self, file_path: str, page_num: int, 
                                      images: list, ocr_helper) -> str:
        """
        Extract text from images in PDF page using OCR.
        
        Args:
            file_path: Path to PDF file
            page_num: Page number (0-indexed)
            images: List of image objects from pdfplumber
            ocr_helper: OCRHelper instance
            
        Returns:
            Text extracted from images
        """
        image_texts = []
        
        try:
            # For pdfplumber, images are already extracted
            # We need to use pdf2image to convert page to image and then OCR
            image_texts = self._extract_text_from_pdf_page_images(
                file_path, page_num, ocr_helper
            )
        except Exception:
            pass
        
        return image_texts
    
    def _extract_text_from_pdf_page_images(self, file_path: str, page_num: int, 
                                           ocr_helper) -> str:
        """
        Extract text from PDF page by converting to image and using OCR.
        
        Args:
            file_path: Path to PDF file
            page_num: Page number (0-indexed)
            ocr_helper: OCRHelper instance
            
        Returns:
            Text extracted from page image
        """
        try:
            from pdf2image import convert_from_path
            import tempfile
            
            # Convert PDF page to image
            images = convert_from_path(file_path, first_page=page_num+1, last_page=page_num+1)
            
            if not images:
                return ''
            
            # Perform OCR on the page image
            image = images[0]
            
            # Convert PIL Image to bytes
            from io import BytesIO
            img_bytes = BytesIO()
            image.save(img_bytes, format='PNG')
            img_bytes.seek(0)
            
            # Extract text using OCR
            ocr_text = ocr_helper.extract_text_from_image(img_bytes.read())
            
            # Filter out text that was already extracted by pdfplumber/PyPDF2
            # by checking if it's significantly different from regular text extraction
            if ocr_text and ocr_text.strip():
                return f"[Изображение на странице {page_num + 1}: {ocr_text}]"
            
            return ''
        except ImportError:
            # pdf2image not available, skip OCR
            return ''
        except Exception as e:
            # OCR failed, continue without it
            return ''
