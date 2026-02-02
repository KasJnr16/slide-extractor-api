"""
Text extraction services for PDF, DOCX, TXT, and image files
Supports OCR for images and text extraction for various document formats
"""
import io
import os
from typing import Optional
from .structured_logger import logger, OperationTimer
from .file_validator import validate_file
from PyPDF2 import PdfReader
from PIL import Image
import pytesseract
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



def extract_text_from_any(file_bytes: bytes, filename: str, request_id: str = None):
    """
    Universal text extraction from various file formats
    
    Args:
        file_bytes: File content as bytes
        filename: Name of the file
        request_id: Optional request ID for tracing
        
    Returns:
        Extracted text content
    """
    with OperationTimer("text_extraction", filename=filename, request_id=request_id):
        try:
            # Validate file
            validation_result = validate_file(
                filename or "",
                len(file_bytes),
                "application/octet-stream"  # MIME type not available at this level
            )
            
            if not validation_result["valid"]:
                logger.log_validation_error(
                    filename=filename or "unknown",
                    errors=validation_result["errors"],
                    request_id=request_id
                )
                raise ValueError(f"File validation failed: {validation_result['errors']}")
            
            logger.info(
                "Starting text extraction",
                filename=filename,
                file_size=len(file_bytes),
                request_id=request_id
            )
            
            filename = filename.lower()

            # ----- Excel -----
            if filename.endswith(('.xlsx', '.xls', '.xlsm')):
                result = extract_excel_as_text(file_bytes, filename)
                
            # ----- PDF -----
            elif filename.endswith(".pdf"):
                extracted = extract_pdf_text(file_bytes)
                if extracted and len(extracted) > 20:
                    result = clean_text(extracted)
                else:
                    # Try OCR on PDF pages
                    try:
                        from pdf2image import convert_from_bytes
                        images = convert_from_bytes(file_bytes)
                        ocr_text = ""
                        for img in images:
                            ocr_text += ocr_image(img) + "\n"
                        result = clean_text(ocr_text)
                    except ImportError:
                        logger.warning(
                            "pdf2image not available, using basic PDF extraction",
                            filename=filename,
                            request_id=request_id
                        )
                        result = clean_text(extracted) if extracted else ""

            # ----- Images -----
            elif filename.endswith((".jpg", ".jpeg", ".png", ".tiff")):
                img = Image.open(io.BytesIO(file_bytes))
                result = clean_text(ocr_image(img))

            # ----- DOCX -----
            elif filename.endswith(".docx"):
                result = extract_docx_text(file_bytes)

            # ----- TXT -----
            elif filename.endswith(".txt"):
                result = extract_text_file(file_bytes)

            else:
                raise ValueError("Unsupported file type for extraction.")
            
            logger.log_file_processing(
                filename=filename,
                file_size=len(file_bytes),
                file_type="text",
                operation="extraction",
                success=True,
                request_id=request_id
            )
            
            return result
            
        except Exception as e:
            logger.error(
                "Text extraction failed",
                filename=filename,
                error=str(e),
                request_id=request_id
            )
            raise
