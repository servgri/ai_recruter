"""Parser for Markdown files."""

from .base_parser import BaseParser


class MdParser(BaseParser):
    """Parser for Markdown files."""
    
    def parse(self, file_path: str) -> str:
        """
        Read text from Markdown file.
        
        Args:
            file_path: Path to the Markdown file
            
        Returns:
            Text content of the file (raw markdown)
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except UnicodeDecodeError:
            # Try with different encoding if UTF-8 fails
            with open(file_path, 'r', encoding='cp1251') as f:
                return f.read()
