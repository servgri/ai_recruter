"""Parser for SQL files."""

from .base_parser import BaseParser


class SqlParser(BaseParser):
    """Parser for SQL files (treated as text files)."""
    
    def parse(self, file_path: str) -> str:
        """
        Read text from SQL file.
        
        Args:
            file_path: Path to the SQL file
            
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
