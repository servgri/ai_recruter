"""Parser for TXT files."""

from .base_parser import BaseParser


class TxtParser(BaseParser):
    """Parser for plain text files."""
    
    def parse(self, file_path: str) -> str:
        """
        Read text from TXT file.
        
        Args:
            file_path: Path to the TXT file
            
        Returns:
            Text content of the file
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except UnicodeDecodeError:
            # Try with different encoding if UTF-8 fails
            with open(file_path, 'r', encoding='cp1251') as f:
                return f.read()
