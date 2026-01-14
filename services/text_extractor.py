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
import openpyxl
from openpyxl.utils import get_column_letter
from typing import Dict, Any


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
    try:
        if filename.lower().endswith(('.xlsx', '.xlsm')):
            return _extract_xlsx(file_bytes)
        elif filename.lower().endswith('.xls'):
            return _extract_xls(file_bytes)
        else:
            raise ValueError(f"Unsupported Excel format: {filename}")
    except Exception as e:
        raise ValueError(f"Error extracting Excel data: {str(e)}")


def _extract_xlsx(file_bytes: bytes) -> Dict[str, Any]:
    """Extract from modern Excel format (.xlsx) using openpyxl."""
    workbook = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
    
    sheets_data = []
    
    for sheet_name in workbook.sheetnames:
        sheet = workbook[sheet_name]
        sheet_data = []
        non_empty_count = 0
        
        for row_idx, row in enumerate(sheet.iter_rows(), 1):
            for col_idx, cell in enumerate(row, 1):
                value = _get_cell_value(cell)
                data_type = _get_cell_type(cell)
                
                if value is not None and str(value).strip():
                    non_empty_count += 1
                
                cell_info = {
                    "cell": f"{get_column_letter(col_idx)}{row_idx}",
                    "row": row_idx,
                    "col": col_idx,
                    "col_letter": get_column_letter(col_idx),
                    "value": str(value) if value is not None else "",
                    "data_type": data_type
                }
                sheet_data.append(cell_info)
        
        # Get dimensions
        max_row = sheet.max_row if sheet.max_row else 0
        max_col = sheet.max_column if sheet.max_column else 0
        
        sheets_data.append({
            "name": sheet_name,
            "data": sheet_data,
            "summary": {
                "total_rows": max_row,
                "total_cols": max_col,
                "non_empty_cells": non_empty_count
            }
        })
    
    return {
        "filename": "excel_file",
        "sheets": sheets_data
    }


def _extract_xls(file_bytes: bytes) -> Dict[str, Any]:
    """Extract from legacy Excel format (.xls) using pandas."""
    # Use pandas as fallback for .xls files
    excel_file = io.BytesIO(file_bytes)
    
    try:
        # Read all sheets
        xls = pd.ExcelFile(excel_file)
        sheets_data = []
        
        for sheet_name in xls.sheet_names:
            df = pd.read_excel(excel_file, sheet_name=sheet_name, header=None)
            sheet_data = []
            non_empty_count = 0
            
            for row_idx, row in df.iterrows():
                for col_idx, value in enumerate(row, 1):
                    if pd.notna(value) and str(value).strip():
                        non_empty_count += 1
                    
                    cell_info = {
                        "cell": f"{get_column_letter(col_idx)}{row_idx + 1}",
                        "row": row_idx + 1,
                        "col": col_idx,
                        "col_letter": get_column_letter(col_idx),
                        "value": str(value) if pd.notna(value) else "",
                        "data_type": _infer_data_type(value)
                    }
                    sheet_data.append(cell_info)
            
            sheets_data.append({
                "name": sheet_name,
                "data": sheet_data,
                "summary": {
                    "total_rows": len(df),
                    "total_cols": len(df.columns),
                    "non_empty_cells": non_empty_count
                }
            })
        
        return {
            "filename": "excel_file",
            "sheets": sheets_data
        }
        
    except Exception as e:
        raise ValueError(f"Error reading .xls file: {str(e)}")


def _get_cell_value(cell) -> Any:
    """Get the actual value from an openpyxl cell."""
    if cell.is_date:
        return cell.value
    elif cell.data_type == 'f':  # formula
        return cell.value if cell.value is not None else ""
    else:
        return cell.value


def _get_cell_type(cell) -> str:
    """Determine the data type of a cell."""
    if cell.data_type == 'f':
        return "formula"
    elif cell.is_date:
        return "date"
    elif cell.data_type == 'n':
        return "number"
    elif cell.data_type == 's':
        return "string"
    elif cell.data_type == 'b':
        return "boolean"
    else:
        return "empty"


def _infer_data_type(value) -> str:
    """Infer data type for pandas-based extraction."""
    if pd.isna(value) or value == "":
        return "empty"
    elif isinstance(value, (int, float)):
        return "number"
    elif isinstance(value, str):
        # Try to detect if it's a date
        try:
            pd.to_datetime(value)
            return "date"
        except:
            return "string"
    else:
        return "unknown"


def extract_text_from_any(file_bytes: bytes, filename: str):
    """
    Universal text extraction from various file formats
    """
    filename = filename.lower()

    # ----- Excel -----
    if filename.endswith(('.xlsx', '.xls', '.xlsm')):
        excel_data = extract_excel_from_bytes(file_bytes, filename)
        # Convert Excel data to text format for backward compatibility
        all_text = []
        for sheet in excel_data["sheets"]:
            all_text.append(f"=== Sheet: {sheet['name']} ===")
            for cell in sheet["data"]:
                if cell["value"].strip():
                    all_text.append(f"{cell['cell']}: {cell['value']}")
        return clean_text("\n".join(all_text))

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
