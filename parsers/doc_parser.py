"""Parser for DOC files (legacy Microsoft Word format)."""

from .base_parser import BaseParser
import os
import re


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
        # Prefer Word COM automation on Windows for reliable .doc parsing
        if os.name == "nt":
            text = self._parse_with_word_com(file_path)
            if text and text.strip():
                return text

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
                        # If it looks like OLE/binary junk, fail fast (better than polluting downstream split)
                        if self._is_gibberish(text):
                            raise Exception("Binary DOC content detected (gibberish). Use Word COM (pywin32 + MS Word) or install antiword.")
                        return text
                except Exception as e:
                    raise Exception(f"Error parsing DOC file. Install antiword or use textract. Error: {str(e)}")

    def _parse_with_word_com(self, file_path: str) -> str:
        """
        Parse .doc using Microsoft Word via COM automation (Windows only).
        Requires: pywin32 and installed Microsoft Word.
        """
        try:
            import pythoncom  # type: ignore
            import win32com.client  # type: ignore
        except Exception:
            return ""

        abs_path = os.path.abspath(file_path)

        word = None
        doc = None
        try:
            pythoncom.CoInitialize()
            word = win32com.client.Dispatch("Word.Application")
            word.Visible = False
            # 0 = wdAlertsNone
            word.DisplayAlerts = 0

            # Open parameters: https://learn.microsoft.com/en-us/office/vba/api/word.documents.open
            doc = word.Documents.Open(abs_path, ReadOnly=True, AddToRecentFiles=False)
            text = doc.Content.Text or ""
            return text
        except Exception:
            return ""
        finally:
            try:
                if doc is not None:
                    doc.Close(False)
            except Exception:
                pass
            try:
                if word is not None:
                    word.Quit()
            except Exception:
                pass
            try:
                pythoncom.CoUninitialize()
            except Exception:
                pass

    def _is_gibberish(self, text: str) -> bool:
        if not text:
            return True

        # Common OLE/container strings when decoding binary .doc as text
        if "Root Entry" in text and "WordDocument" in text:
            return True

        s = text.strip()
        if len(s) < 200:
            return False

        # Low ratio of alphabetic characters typically indicates binary junk
        non_space = sum(1 for c in s if not c.isspace())
        if non_space == 0:
            return True
        letters = sum(1 for c in s if c.isalpha())
        if len(s) > 1500 and (letters / non_space) < 0.10:
            return True

        # Excessive sequences of symbols
        if re.search(r'[#$%&\'()*+,./0-9]{40,}', s):
            return True

        return False
