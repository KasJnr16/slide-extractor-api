"""
File routing service to determine appropriate extractor for different file types
"""
from typing import Dict, Any, Tuple, Optional
from .text_extractor import extract_text_from_any
from .excel_extractor import ExcelExtractor
from .powerpoint_extractor import extract_powerpoint_text
from .structured_logger import logger, OperationTimer
from .file_validator import validate_file


class FileRouter:
    """Routes files to appropriate extractors based on file type"""
    
    @staticmethod
    def get_file_type(filename: str) -> str:
        """Determine file type category from filename"""
        filename = filename.lower()
        
        if filename.endswith(('.xlsx', '.xls', '.xlsm')):
            return 'excel'
        elif filename.endswith(('.pptx', '.ppt')):
            return 'powerpoint'
        elif filename.endswith(('.pdf', '.docx', '.txt', '.jpg', '.jpeg', '.png', '.tiff')):
            return 'text'
        else:
            return 'unknown'
    
    @staticmethod
    async def extract_file_content(file_bytes: bytes, filename: str, request_id: str = None) -> Tuple[str, Any]:
        """
        Route file to appropriate extractor and return content with type
        
        Args:
            file_bytes: File content as bytes
            filename: Name of the file
            request_id: Optional request ID for tracing
            
        Returns:
            Tuple of (file_type, extracted_content)
        """
        with OperationTimer("file_routing", filename=filename, request_id=request_id):
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
                        warnings=validation_result.get("warnings", []),
                        request_id=request_id
                    )
                    raise ValueError(f"File validation failed: {validation_result['errors']}")
                
                # Log warnings if any
                if validation_result.get("warnings"):
                    for warning in validation_result["warnings"]:
                        logger.warning(
                            "File validation warning",
                            filename=filename,
                            warning=warning,
                            request_id=request_id
                        )
                
                file_type = FileRouter.get_file_type(filename)
                
                logger.info(
                    "Routing file to extractor",
                    filename=filename,
                    file_type=file_type,
                    file_size=len(file_bytes),
                    request_id=request_id
                )
                
                # Process immediately
                if file_type == 'excel':
                    with OperationTimer("excel_extraction", filename=filename, request_id=request_id):
                        extractor = ExcelExtractor()
                        content = extractor.extract_from_bytes(file_bytes, filename)
                elif file_type == 'powerpoint':
                    with OperationTimer("powerpoint_extraction", filename=filename, request_id=request_id):
                        content = extract_powerpoint_text(file_bytes, filename, request_id=request_id)
                elif file_type == 'text':
                    with OperationTimer("text_extraction", filename=filename, request_id=request_id):
                        content = extract_text_from_any(file_bytes, filename, request_id=request_id)
                else:
                    raise ValueError(f"Unsupported file type: {filename}")
                
                logger.log_file_processing(
                    filename=filename,
                    file_size=len(file_bytes),
                    file_type=file_type,
                    operation="extraction",
                    success=True,
                    request_id=request_id
                )
                
                return file_type, content
                
            except Exception as e:
                logger.error(
                    "File routing failed",
                    filename=filename,
                    error=str(e),
                    request_id=request_id
                )
                raise
    
    @staticmethod
    async def extract_excel_advanced(
        file_bytes: bytes, 
        filename: str,
        extract_images: bool = True,
        extract_charts: bool = True,
        extract_formatting: bool = True,
        request_id: str = None
    ) -> Dict[str, Any]:
        """
        Advanced Excel extraction with configurable feature flags.
        
        Args:
            file_bytes: Excel file content as bytes
            filename: Name of the file
            extract_images: Whether to extract embedded images
            extract_charts: Whether to extract chart information
            extract_formatting: Whether to extract cell formatting
            request_id: Optional request ID for tracing
            
        Returns:
            Dictionary with extracted Excel data
        """
        with OperationTimer("excel_advanced_extraction", filename=filename, request_id=request_id):
            try:
                # Validate file
                validation_result = validate_file(
                    filename or "",
                    len(file_bytes),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
                
                if not validation_result["valid"]:
                    logger.log_validation_error(
                        filename=filename or "unknown",
                        errors=validation_result["errors"],
                        request_id=request_id
                    )
                    raise ValueError(f"File validation failed: {validation_result['errors']}")
                
                file_type = FileRouter.get_file_type(filename)
                
                if file_type != 'excel':
                    raise ValueError(f"Expected Excel file, got: {file_type}")
                
                logger.info(
                    "Starting advanced Excel extraction",
                    filename=filename,
                    extract_images=extract_images,
                    extract_charts=extract_charts,
                    extract_formatting=extract_formatting,
                    request_id=request_id
                )
                
                # Use advanced extractor with flags
                extractor = ExcelExtractor(
                    extract_images=extract_images,
                    extract_charts=extract_charts,
                    extract_formatting=extract_formatting
                )
                
                result = extractor.extract_from_bytes(file_bytes, filename)
                
                logger.log_file_processing(
                    filename=filename,
                    file_size=len(file_bytes),
                    file_type="excel",
                    operation="advanced_extraction",
                    success=True,
                    request_id=request_id
                )
                
                return result
                
            except Exception as e:
                logger.error(
                    "Advanced Excel extraction failed",
                    filename=filename,
                    error=str(e),
                    extract_images=extract_images,
                    extract_charts=extract_charts,
                    extract_formatting=extract_formatting,
                    request_id=request_id
                )
                raise
