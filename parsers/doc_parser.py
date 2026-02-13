"""Parser for DOC files (legacy Microsoft Word format)."""

from .base_parser import BaseParser


class DocParser(BaseParser):
    """Parser for DOC files."""
    
    def parse(self, file_path: str) -> str:
        """
        Extract text from DOC file.
        
        Args:
            file_path: Path to the DOC file
            
        Returns:
            Extracted text content
            
        Raises:
            Exception: If file cannot be parsed
        """
        try:
            # Try using python-docx first (sometimes works for .doc)
            from docx import Document
            doc = Document(file_path)
            paragraphs = []
            for paragraph in doc.paragraphs:
                paragraphs.append(paragraph.text)
            return '\n'.join(paragraphs)
        except Exception:
            try:
                # Try using textract or antiword
                import subprocess
                import sys
                
                # Try antiword (requires system installation)
                result = subprocess.run(
                    ['antiword', file_path],
                    capture_output=True,
                    text=True,
                    encoding='utf-8'
                )
                if result.returncode == 0:
                    return result.stdout
                else:
                    raise Exception("antiword failed to parse file")
            except (FileNotFoundError, Exception):
                # Last resort: try to read as text (may not work well)
                try:
                    with open(file_path, 'rb') as f:
                        content = f.read()
                        # Try to extract readable text (basic approach)
                        text = content.decode('utf-8', errors='ignore')
                        # Remove non-printable characters
                        text = ''.join(char for char in text if char.isprintable() or char in '\n\r\t')
                        return text
                except Exception as e:
                    raise Exception(f"Error parsing DOC file. Install antiword or use textract. Error: {str(e)}")
