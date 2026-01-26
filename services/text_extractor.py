"""
Text extraction services for various document formats
"""
import pytesseract
from pdf2image import convert_from_bytes
from PyPDF2 import PdfReader
from PIL import Image
import io
import re
import pandas as pd
from typing import Dict, Any
from .excel_extractor import ExcelExtractor


def clean_text(text):
    """Clean and normalize text content"""
    text = re.sub(r'\n\s*\n', '\n\n', text)
    text = text.replace("\t", " ")
    return text.strip()


def extract_pdf_text(pdf_bytes):
    """Extract text from PDF files"""
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""
        return text.strip()
    except:
        return ""


def ocr_image(image: Image.Image):
    """Perform OCR on images"""
    gray = image.convert("L")
    return pytesseract.image_to_string(gray, lang="eng")


def extract_docx_text(file_bytes):
    """Extract text from DOCX files"""
    try:
        from docx import Document
        file_stream = io.BytesIO(file_bytes)
        doc = Document(file_stream)
        full_text = [p.text for p in doc.paragraphs]
        return clean_text("\n".join(full_text))
    except Exception as e:
        raise ValueError(f"Error reading DOCX: {e}")


def extract_text_file(file_bytes):
    """Extract text from plain text files"""
    try:
        return clean_text(file_bytes.decode("utf-8"))
    except:
        return clean_text(file_bytes.decode("latin-1"))


def extract_excel_from_bytes(file_bytes: bytes, filename: str) -> Dict[str, Any]:
    """
    Extract Excel content with row/column references from bytes.
    
    Args:
        file_bytes: Excel file content as bytes
        filename: Name of the file (for format detection)
        
    Returns:
        Dictionary containing extracted data with structured format
    """
    extractor = ExcelExtractor()
    return extractor.extract_from_bytes(file_bytes, filename)


def extract_excel_as_text(file_bytes: bytes, filename: str) -> str:
    """
    Extract Excel content and return it in CELL-BY-CELL text format.
    
    Args:
        file_bytes: Excel file content as bytes
        filename: Name of the file (for format detection)
        
    Returns:
        Formatted text string with cell-by-cell data
    """
    extractor = ExcelExtractor()
    return extractor.extract_as_text(file_bytes, filename)



def extract_text_from_any(file_bytes: bytes, filename: str):
    """
    Universal text extraction from various file formats
    """
    filename = filename.lower()

    # ----- Excel -----
    if filename.endswith(('.xlsx', '.xls', '.xlsm')):
        return extract_excel_as_text(file_bytes, filename)

    # ----- PDF -----
    if filename.endswith(".pdf"):
        extracted = extract_pdf_text(file_bytes)
        if extracted and len(extracted) > 20:
            return clean_text(extracted)

        images = convert_from_bytes(file_bytes)
        ocr_text = ""
        for img in images:
            ocr_text += ocr_image(img) + "\n"
        return clean_text(ocr_text)

    # ----- Images -----
    if filename.endswith((".jpg", ".jpeg", ".png", ".tiff")):
        img = Image.open(io.BytesIO(file_bytes))
        return clean_text(ocr_image(img))

    # ----- DOCX -----
    if filename.endswith(".docx"):
        return extract_docx_text(file_bytes)

    # ----- TXT -----
    if filename.endswith(".txt"):
        return extract_text_file(file_bytes)

    raise ValueError("Unsupported file type for extraction.")
