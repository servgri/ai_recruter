"""Parser for DOCX files."""

import os
import tempfile
from .base_parser import BaseParser


class DocxParser(BaseParser):
    """Parser for DOCX files."""
    
    def parse(self, file_path: str) -> str:
        """
        Extract text from DOCX file, including OCR from images.
        
        Args:
            file_path: Path to the DOCX file
            
        Returns:
            Extracted text content with OCR text from images
            
        Raises:
            Exception: If file cannot be parsed
        """
        try:
            from docx import Document
            from docx.document import Document as DocumentType
            from docx.oxml.text.paragraph import CT_P
            from docx.oxml.table import CT_Tbl
            from docx.table import _Cell, Table
            from docx.text.paragraph import Paragraph
            
            # Import OCR helper
            import sys
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
            from utils.ocr_helper import OCRHelper
            
            doc = Document(file_path)
            text_parts = []
            
            # Process all elements in document order
            for element in doc.element.body:
                if isinstance(element, CT_P):
                    # Paragraph
                    paragraph = Paragraph(element, doc)
                    text = paragraph.text
                    if text:
                        text_parts.append(text)
                    
                    # Check for images in paragraph
                    image_text = self._extract_images_from_paragraph(paragraph, OCRHelper)
                    if image_text:
                        text_parts.append(image_text)
                        
                elif isinstance(element, CT_Tbl):
                    # Table
                    table = Table(element, doc)
                    for row in table.rows:
                        row_texts = []
                        for cell in row.cells:
                            cell_text = cell.text
                            if cell_text:
                                row_texts.append(cell_text)
                        if row_texts:
                            text_parts.append(' | '.join(row_texts))
            
            return '\n'.join(text_parts)
        except ImportError:
            raise ImportError("python-docx is required for DOCX parsing. Install it with: pip install python-docx")
        except Exception as e:
            raise Exception(f"Error parsing DOCX file: {str(e)}")
    
    def _extract_images_from_paragraph(self, paragraph, ocr_helper) -> str:
        """
        Extract images from paragraph and convert to text using OCR.
        
        Args:
            paragraph: Paragraph object from python-docx
            ocr_helper: OCRHelper instance
            
        Returns:
            Text extracted from images in paragraph
        """
        image_texts = []
        
        try:
            # Get all runs in paragraph
            for run in paragraph.runs:
                # Check for images in run using different methods
                image_data = None
                
                # Method 1: Check for blip (embedded image)
                try:
                    blips = run._element.xpath('.//a:blip')
                    if blips:
                        blip = blips[0]
                        rId = blip.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed')
                        if rId and rId in run.part.related_parts:
                            image_part = run.part.related_parts[rId]
                            image_data = image_part.blob
                except Exception:
                    pass
                
                # Method 2: Check for linked images
                if not image_data:
                    try:
                        links = run._element.xpath('.//a:blip/@r:link')
                        if links:
                            rId = links[0]
                            if rId in run.part.related_parts:
                                image_part = run.part.related_parts[rId]
                                image_data = image_part.blob
                    except Exception:
                        pass
                
                # Perform OCR if image found
                if image_data:
                    try:
                        ocr_text = ocr_helper.extract_text_from_image(image_data)
                        if ocr_text and ocr_text.strip() and not ocr_text.startswith('[Изображение:'):
                            image_texts.append(f"[Изображение: {ocr_text}]")
                    except Exception:
                        # If OCR fails, just note that image was found
                        pass
        except Exception:
            # If image extraction fails, continue without it
            pass
        
        return '\n'.join(image_texts) if image_texts else ''
