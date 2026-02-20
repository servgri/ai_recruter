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
        result = self.parse_with_images(file_path)
        return result['text']
    
    def parse_with_images(self, file_path: str, doc_id: int = None, output_dir: str = None) -> dict:
        """
        Extract text and images from PDF file.
        
        Args:
            file_path: Path to the PDF file
            doc_id: Document ID for saving images (optional)
            output_dir: Directory to save images (optional)
            
        Returns:
            Dictionary with 'text' and 'images' keys
        """
        # Import OCR helper
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
        from utils.ocr_helper import OCRHelper
        
        text_parts = []
        images = []
        current_position = 0
        image_index = 0
        
        # Create output directory for images if doc_id is provided
        if doc_id and output_dir:
            image_dir = os.path.join(output_dir, str(doc_id))
            os.makedirs(image_dir, exist_ok=True)
        else:
            image_dir = None
        
        try:
            import pdfplumber
            with pdfplumber.open(file_path) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    # Extract text from page
                    text = page.extract_text()
                    if text:
                        text_parts.append(text)
                        current_position += len(text) + 1
                    
                    # Extract images and perform OCR
                    page_images = page.images
                    if page_images or True:  # Always try OCR for pages with images or if text is sparse
                        image_info = self._extract_images_from_pdf_page_with_info(
                            file_path, page_num, OCRHelper, current_position, image_dir, image_index
                        )
                        if image_info:
                            for img_info in image_info:
                                images.append(img_info)
                                image_index += 1
                                if img_info.get('ocr_text'):
                                    ocr_marker = f"[Изображение на странице {page_num + 1}: {img_info['ocr_text']}]"
                                    text_parts.append(ocr_marker)
                                    current_position += len(ocr_marker) + 1
            
            return {'text': '\n'.join(text_parts), 'images': images}
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
                            current_position += len(text) + 1
                        
                        # Try to extract images using pdf2image
                        image_info = self._extract_images_from_pdf_page_with_info(
                            file_path, page_num, OCRHelper, current_position, image_dir, image_index
                        )
                        if image_info:
                            for img_info in image_info:
                                images.append(img_info)
                                image_index += 1
                                if img_info.get('ocr_text'):
                                    ocr_marker = f"[Изображение на странице {page_num + 1}: {img_info['ocr_text']}]"
                                    text_parts.append(ocr_marker)
                                    current_position += len(ocr_marker) + 1
                
                return {'text': '\n'.join(text_parts), 'images': images}
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
        image_info = self._extract_images_from_pdf_page_with_info(file_path, page_num, ocr_helper, 0, None, 0)
        if image_info and image_info[0].get('ocr_text'):
            return f"[Изображение на странице {page_num + 1}: {image_info[0]['ocr_text']}]"
        return ''
    
    def _extract_images_from_pdf_page_with_info(self, file_path: str, page_num: int, 
                                                ocr_helper, position: int, 
                                                image_dir: str = None, image_index: int = 0) -> list:
        """
        Extract images from PDF page with full information.
        
        Args:
            file_path: Path to PDF file
            page_num: Page number (0-indexed)
            ocr_helper: OCRHelper instance
            position: Current text position in document
            image_dir: Directory to save images (optional)
            image_index: Starting index for image filenames
            
        Returns:
            List of image info dictionaries
        """
        images = []
        
        try:
            from pdf2image import convert_from_path
            from io import BytesIO
            
            # Convert PDF page to image
            page_images = convert_from_path(file_path, first_page=page_num+1, last_page=page_num+1)
            
            if not page_images:
                return images
            
            # Process each image from the page
            for img in page_images:
                try:
                    # Convert PIL Image to bytes
                    img_bytes = BytesIO()
                    img.save(img_bytes, format='PNG')
                    img_bytes.seek(0)
                    image_data = img_bytes.read()
                    
                    # Extract text using OCR
                    ocr_text = ocr_helper.extract_text_from_image(image_data)
                    ocr_text = ocr_text.strip() if ocr_text else ''
                    
                    # Save image if directory is provided and OCR found text
                    image_path = None
                    if image_dir and ocr_text:
                        try:
                            image_filename = f"image_{image_index}.png"
                            image_path_full = os.path.join(image_dir, image_filename)
                            img.save(image_path_full, 'PNG')
                            # Convert to relative path for storage
                            image_path = f"static/images/documents/{os.path.basename(image_dir)}/{image_filename}"
                        except Exception as e:
                            print(f"Error saving PDF image: {e}")
                    
                    # Only add if OCR found text (meaningful content)
                    if ocr_text:
                        images.append({
                            'position': position,
                            'image_path': image_path,
                            'ocr_text': ocr_text
                        })
                        image_index += 1
                except Exception as e:
                    print(f"Error processing PDF page image: {e}")
        except ImportError:
            # pdf2image not available, skip OCR
            pass
        except Exception as e:
            print(f"Error extracting images from PDF page: {e}")
        
        return images
