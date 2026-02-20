"""Parser for DOCX files."""

import os
import tempfile
from .base_parser import BaseParser
import re


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
        result = self.parse_with_images(file_path)
        return result['text']
    
    def parse_with_images(self, file_path: str, doc_id: int = None, output_dir: str = None) -> dict:
        """
        Extract text and images from DOCX file.
        
        Args:
            file_path: Path to the DOCX file
            doc_id: Document ID for saving images (optional)
            output_dir: Directory to save images (optional)
            
        Returns:
            Dictionary with 'text' and 'images' keys
            - text: Extracted text content with OCR text from images
            - images: List of image info dicts with 'position', 'image_path', 'ocr_text'
            
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
            from PIL import Image
            from io import BytesIO
            
            # Import OCR helper
            import sys
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
            from utils.ocr_helper import OCRHelper
            
            doc = Document(file_path)
            text_parts = []
            images = []
            numbering_state = {}  # numId -> list[level] counters
            current_position = 0
            image_index = 0
            
            # Create output directory for images if doc_id is provided
            if doc_id and output_dir:
                image_dir = os.path.join(output_dir, str(doc_id))
                os.makedirs(image_dir, exist_ok=True)
            else:
                image_dir = None
            
            # Process all elements in document order
            for element in doc.element.body:
                if isinstance(element, CT_P):
                    # Paragraph
                    paragraph = Paragraph(element, doc)
                    text = paragraph.text
                    prefix = self._get_list_prefix(paragraph, numbering_state)
                    if prefix and text:
                        text = f"{prefix}{text}"
                    if text:
                        text_parts.append(text)
                        current_position += len(text) + 1  # +1 for newline
                    
                    # Check for images in paragraph
                    image_info = self._extract_images_from_paragraph_with_info(
                        paragraph, OCRHelper, current_position, image_dir, image_index
                    )
                    if image_info:
                        for img_info in image_info:
                            images.append(img_info)
                            image_index += 1
                            # Add OCR text to text_parts
                            if img_info.get('ocr_text'):
                                ocr_marker = f"[Изображение: {img_info['ocr_text']}]"
                                text_parts.append(ocr_marker)
                                current_position += len(ocr_marker) + 1
                        
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
                            row_text = ' | '.join(row_texts)
                            text_parts.append(row_text)
                            current_position += len(row_text) + 1
            
            return {
                'text': '\n'.join(text_parts),
                'images': images
            }
        except ImportError:
            raise ImportError("python-docx is required for DOCX parsing. Install it with: pip install python-docx")
        except Exception as e:
            raise Exception(f"Error parsing DOCX file: {str(e)}")
    
    def _get_list_prefix(self, paragraph, numbering_state) -> str:
        """
        Best-effort extraction of list numbering/bullets for DOCX.

        python-docx doesn't include automatic numbering in paragraph.text, so without this
        we often lose task markers like "1.", "2.", "3.", "4.".
        """
        try:
            p = paragraph._p
            pPr = getattr(p, "pPr", None)
            if pPr is None or getattr(pPr, "numPr", None) is None:
                return ""

            numPr = pPr.numPr
            numId_el = getattr(numPr, "numId", None)
            ilvl_el = getattr(numPr, "ilvl", None)
            if numId_el is None or numId_el.val is None:
                return ""

            num_id = int(numId_el.val)
            ilvl = int(ilvl_el.val) if (ilvl_el is not None and ilvl_el.val is not None) else 0
            if ilvl < 0:
                ilvl = 0
            if ilvl > 8:
                ilvl = 8

            # Don't prefix if the user already typed a marker
            txt = paragraph.text or ""
            if re.match(r'^\s*(\d+[\.\):]|[IVX]{1,6}[\)\.\:])', txt):
                return ""
            if re.match(r'^\s*[-–—•]\s+', txt):
                return ""

            counters = numbering_state.get(num_id)
            if counters is None:
                counters = [0] * 9
                numbering_state[num_id] = counters

            counters[ilvl] += 1
            # Reset deeper levels
            for lvl in range(ilvl + 1, len(counters)):
                counters[lvl] = 0

            n = counters[ilvl]
            indent = "  " * ilvl

            # Use a simple decimal prefix; this is sufficient for task extraction.
            return f"{indent}{n}. "
        except Exception:
            return ""

    def _extract_images_from_paragraph(self, paragraph, ocr_helper) -> str:
        """
        Extract images from paragraph and convert to text using OCR.
        
        Args:
            paragraph: Paragraph object from python-docx
            ocr_helper: OCRHelper instance
            
        Returns:
            Text extracted from images in paragraph
        """
        image_info = self._extract_images_from_paragraph_with_info(paragraph, ocr_helper, 0, None, 0)
        if image_info:
            return '\n'.join([f"[Изображение: {img.get('ocr_text', '')}]" for img in image_info if img.get('ocr_text')])
        return ''
    
    def _extract_images_from_paragraph_with_info(self, paragraph, ocr_helper, position: int, 
                                                   image_dir: str = None, image_index: int = 0) -> list:
        """
        Extract images from paragraph with full information.
        
        Args:
            paragraph: Paragraph object from python-docx
            ocr_helper: OCRHelper instance
            position: Current text position in document
            image_dir: Directory to save images (optional)
            image_index: Starting index for image filenames
            
        Returns:
            List of image info dictionaries
        """
        images = []
        
        try:
            from PIL import Image
            from io import BytesIO
            
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
                
                # Process image if found
                if image_data:
                    try:
                        # Perform OCR
                        ocr_text = ocr_helper.extract_text_from_image(image_data)
                        ocr_text = ocr_text.strip() if ocr_text else ''
                        
                        # Save image if directory is provided
                        image_path = None
                        if image_dir:
                            try:
                                # Save image
                                img = Image.open(BytesIO(image_data))
                                image_filename = f"image_{image_index}.png"
                                image_path = os.path.join(image_dir, image_filename)
                                img.save(image_path, 'PNG')
                                # Convert to relative path for storage
                                image_path = f"static/images/documents/{os.path.basename(image_dir)}/{image_filename}"
                            except Exception as e:
                                print(f"Error saving image: {e}")
                        
                        images.append({
                            'position': position,
                            'image_path': image_path,
                            'ocr_text': ocr_text
                        })
                        image_index += 1
                    except Exception as e:
                        print(f"Error processing image: {e}")
        except Exception as e:
            print(f"Error extracting images from paragraph: {e}")
        
        return images
