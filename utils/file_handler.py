"""File handling utilities (parser selection only; data is stored in DB)."""

from typing import Optional

from parsers import (
    TxtParser, PdfParser, DocxParser, MdParser, SqlParser,
    XlsxParser, DocParser, BaseParser
)


def get_parser_for_file(filename: str) -> Optional[BaseParser]:
    """
    Get appropriate parser for file based on extension.
    
    Args:
        filename: Name of the file
        
    Returns:
        Parser instance or None if format not supported
    """
    extension = BaseParser.get_file_extension(filename)
    
    parser_map = {
        'txt': TxtParser(),
        'sql': SqlParser(),
        'md': MdParser(),
        'docx': DocxParser(),
        'pdf': PdfParser(),
        'xlsx': XlsxParser(),
        'doc': DocParser(),
    }
    
    return parser_map.get(extension)
