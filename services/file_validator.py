"""
Configuration and validation utilities for the slide-extractor-api
"""
import os
from typing import List, Dict, Optional
from enum import Enum


class FileFormat(Enum):
    """Supported file formats."""
    PDF = "pdf"
    DOCX = "docx"
    XLSX = "xlsx"
    XLS = "xls"
    XLSM = "xlsm"
    PPTX = "pptx"
    PPT = "ppt"
    TXT = "txt"
    JPG = "jpg"
    JPEG = "jpeg"
    PNG = "png"
    TIFF = "tiff"
    GIF = "gif"


# Configuration constants
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB limit
MAX_FILES_PER_REQUEST = 50

# MIME type mappings
MIME_TYPE_MAP = {
    "application/pdf": [FileFormat.PDF],
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [FileFormat.DOCX],
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [FileFormat.XLSX],
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [FileFormat.XLSM],
    "application/vnd.ms-excel": [FileFormat.XLS],
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": [FileFormat.PPTX],
    "application/vnd.ms-powerpoint": [FileFormat.PPT],
    "text/plain": [FileFormat.TXT],
    "image/jpeg": [FileFormat.JPG, FileFormat.JPEG],
    "image/png": [FileFormat.PNG],
    "image/tiff": [FileFormat.TIFF],
    "image/gif": [FileFormat.GIF],
    "image/*": [FileFormat.JPG, FileFormat.JPEG, FileFormat.PNG, FileFormat.TIFF, FileFormat.GIF],
}

# File extension mappings
EXTENSION_MAP = {
    ".pdf": FileFormat.PDF,
    ".docx": FileFormat.DOCX,
    ".xlsx": FileFormat.XLSX,
    ".xls": FileFormat.XLS,
    ".xlsm": FileFormat.XLSM,
    ".pptx": FileFormat.PPTX,
    ".ppt": FileFormat.PPT,
    ".txt": FileFormat.TXT,
    ".jpg": FileFormat.JPG,
    ".jpeg": FileFormat.JPEG,
    ".png": FileFormat.PNG,
    ".tiff": FileFormat.TIFF,
    ".gif": FileFormat.GIF,
}

# Allowed MIME types for validation
ALLOWED_MIME_TYPES = list(MIME_TYPE_MAP.keys())


def get_file_format_from_filename(filename: str) -> Optional[FileFormat]:
    """Get file format from filename extension."""
    if not filename:
        return None
    
    _, ext = os.path.splitext(filename.lower())
    return EXTENSION_MAP.get(ext)


def get_file_format_from_mime_type(mime_type: str) -> List[FileFormat]:
    """Get possible file formats from MIME type."""
    return MIME_TYPE_MAP.get(mime_type, [])


def is_file_size_valid(file_size: int) -> bool:
    """Check if file size is within limits."""
    return file_size <= MAX_FILE_SIZE


def is_mime_type_allowed(mime_type: str) -> bool:
    """Check if MIME type is allowed."""
    return mime_type in ALLOWED_MIME_TYPES


def validate_file(filename: str, file_size: int, mime_type: str) -> Dict[str, any]:
    """
    Comprehensive file validation.
    
    Args:
        filename: Original filename
        file_size: File size in bytes
        mime_type: MIME type from upload
        
    Returns:
        Dict with validation results
    """
    result = {
        "valid": True,
        "errors": [],
        "warnings": [],
        "format": None
    }
    
    # Check file size
    if not is_file_size_valid(file_size):
        result["valid"] = False
        result["errors"].append(f"File size {file_size} bytes exceeds maximum {MAX_FILE_SIZE} bytes")
    
    # Check MIME type
    # Some internal call sites may not know the MIME type and pass application/octet-stream.
    # In that case, we skip strict MIME checking and rely on file extension validation.
    if mime_type and mime_type != "application/octet-stream":
        if not is_mime_type_allowed(mime_type):
            result["valid"] = False
            result["errors"].append(f"MIME type '{mime_type}' is not supported")
    
    # Get file format from filename
    file_format = get_file_format_from_filename(filename)
    if not file_format:
        result["valid"] = False
        result["errors"].append(f"File extension not supported: {filename}")
    else:
        result["format"] = file_format.value
        
        # Check MIME type matches extension (only when we have a reliable MIME type)
        if mime_type and mime_type != "application/octet-stream":
            mime_formats = get_file_format_from_mime_type(mime_type)
            if file_format not in mime_formats:
                result["warnings"].append(f"MIME type '{mime_type}' doesn't match file extension '{os.path.splitext(filename)[1]}'")

    return result


def validate_multiple_files(files_data: List[Dict]) -> Dict[str, any]:
    """
    Validate multiple files for batch operations.
    
    Args:
        files_data: List of dicts with filename, size, mime_type
        
    Returns:
        Dict with validation results
    """
    result = {
        "valid": True,
        "total_files": len(files_data),
        "valid_files": 0,
        "invalid_files": 0,
        "total_size": 0,
        "errors": [],
        "file_results": []
    }
    
    if len(files_data) > MAX_FILES_PER_REQUEST:
        result["valid"] = False
        result["errors"].append(f"Too many files: {len(files_data)} exceeds maximum {MAX_FILES_PER_REQUEST}")
    
    for i, file_data in enumerate(files_data):
        file_result = validate_file(
            file_data.get("filename", ""),
            file_data.get("size", 0),
            file_data.get("mime_type", "")
        )
        
        file_result["index"] = i
        result["file_results"].append(file_result)
        result["total_size"] += file_data.get("size", 0)
        
        if file_result["valid"]:
            result["valid_files"] += 1
        else:
            result["invalid_files"] += 1
            result["valid"] = False
            result["errors"].extend([f"File {i}: {error}" for error in file_result["errors"]])
    
    return result
