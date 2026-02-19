"""Base parser class for all file format parsers."""

from abc import ABC, abstractmethod


class BaseParser(ABC):
    """Base class for all file parsers."""
    
    @abstractmethod
    def parse(self, file_path: str) -> str:
        """
        Parse file and return text content.
        
        Args:
            file_path: Path to the file to parse
            
        Returns:
            Extracted text content as string
            
        Raises:
            Exception: If file cannot be parsed
        """
        pass
    
    @staticmethod
    def get_file_extension(filename: str) -> str:
        """Extract file extension from filename."""
        return filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
