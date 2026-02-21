import PyPDF2
import io
import re
from typing import Optional

def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Extract text from PDF file bytes"""
    try:
        pdf_file = io.BytesIO(pdf_bytes)
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"
        return text.strip()
    except Exception as e:
        raise Exception(f"Error extracting PDF text: {str(e)}")

def extract_text_from_txt(txt_bytes: bytes) -> str:
    """Extract text from TXT file bytes"""
    try:
        return txt_bytes.decode('utf-8').strip()
    except UnicodeDecodeError:
        # Try with different encoding
        return txt_bytes.decode('latin-1').strip()

def clean_text(text: str) -> str:
    """Clean and normalize text"""
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text)
    # Remove special characters but keep basic punctuation
    text = re.sub(r'[^\w\s\.\,\-\:\;\(\)]', '', text)
    return text.strip()

def truncate_text(text: str, max_length: int = 8000) -> str:
    """Truncate text to max_length for embedding"""
    if len(text) > max_length:
        return text[:max_length]
    return text