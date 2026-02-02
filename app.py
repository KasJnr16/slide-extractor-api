"""Document Processing API with Clean, Consolidated Endpoints
"""

from fastapi import FastAPI, UploadFile, File, Request, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel

from services.file_router import FileRouter
from services.document_generator import DocumentPackager, DocumentFormat, DocumentStyle
from services.excel_creator import ExcelCreator
from services.excel_extractor import ExcelExtractor
from services.file_validator import validate_file, validate_multiple_files, MAX_FILE_SIZE, MAX_FILES_PER_REQUEST
from services.job_processor import (
    submit_job, get_job_status, JobPriority,
    start_background_processor, stop_background_processor
)
from services.rate_limiter import rate_limit_middleware
from services.structured_logger import logger, log_request_response, OperationTimer
from services.health_monitor import health_monitor
import services.batch_tasks  # Register batch task handlers

import os
import json
import io
import time
import uuid

app = FastAPI()

# ======================================================
# LIFECYCLE EVENTS
# ======================================================

@app.on_event("startup")
async def startup_event():
    """Initialize background services."""
    logger.log_system_event("startup", "Document Processing API starting up")
    await start_background_processor()
    await health_monitor.check_all_components()
    logger.log_system_event("startup_complete", "All services initialized successfully")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup background services."""
    logger.log_system_event("shutdown", "Document Processing API shutting down")
    await stop_background_processor()
    logger.log_system_event("shutdown_complete", "All services stopped")

# ======================================================
# MIDDLEWARE
# ======================================================

@app.middleware("http")
async def logging_and_rate_limiting_middleware(request, call_next):
    """Combined middleware for logging and rate limiting."""
    request_id = str(uuid.uuid4())
    start_time = time.time()
    request.state.request_id = request_id
    
    try:
        response = await rate_limit_middleware(request, call_next)
        duration_ms = (time.time() - start_time) * 1000
        await log_request_response(request, response, duration_ms, request_id)
        return response
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(
            "Request failed",
            request_id=request_id,
            method=request.method,
            path=str(request.url.path),
            error=str(e),
            duration_ms=duration_ms
        )
        raise

# ======================================================
# CORS MIDDLEWARE
# ======================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # restrict in production
    allow_methods=["*"],
    allow_headers=["*"],
)

# ======================================================
# FILE EXTRACTION ENDPOINTS
# ======================================================

@app.post("/extract_file/")
async def extract_file(request: Request, file: UploadFile = File(...)):
    """
    Universal file extraction endpoint that routes to appropriate extractor.
    
    Args:
        file: Uploaded file of any supported type
        
    Returns:
        JSON response with extracted content or job ID for background processing
    """
    request_id = request.state.request_id
    
    try:
        contents = await file.read()
        filename = file.filename
        
        # Log file processing start
        logger.log_file_processing(
            filename=filename or "unknown",
            file_size=len(contents),
            file_type="unknown",
            operation="validation",
            success=False,
            request_id=request_id
        )
        
        # Validate file
        with OperationTimer("file_validation", filename=filename, request_id=request_id):
            validation_result = validate_file(
                filename or "",
                len(contents),
                file.content_type or "application/octet-stream"
            )
        
        if not validation_result["valid"]:
            logger.log_validation_error(
                filename=filename or "unknown",
                errors=validation_result["errors"],
                warnings=validation_result.get("warnings", []),
                request_id=request_id
            )
            return {
                "error": "File validation failed",
                "details": validation_result["errors"]
            }
        
        # Check if file is large enough to need background processing
        if len(contents) > 10 * 1024 * 1024:  # 10MB threshold
            with OperationTimer("job_submission", filename=filename, request_id=request_id):
                job_id = await submit_job("extract_file", {
                    "file_bytes": contents,
                    "filename": filename
                })
            
            logger.log_job_event(
                job_id=job_id,
                event_type="submitted",
                status="pending",
                request_id=request_id
            )
            
            return {
                "job_id": job_id,
                "message": "File submitted for background processing",
                "status": "pending"
            }
        
        # Process immediately for small files
        with OperationTimer("file_extraction", filename=filename, request_id=request_id):
            file_type, extracted_content = await FileRouter.extract_file_content(contents, filename, request_id)
        
        # Log successful processing
        logger.log_file_processing(
            filename=filename or "unknown",
            file_size=len(contents),
            file_type=file_type,
            operation="extraction",
            success=True,
            request_id=request_id
        )
        
        return {
            "filename": filename,
            "file_type": file_type,
            "content": extracted_content,
            "validation": {
                "format": validation_result["format"],
                "warnings": validation_result["warnings"]
            }
        }
            
    except Exception as e:
        logger.error(
            "File extraction failed",
            filename=file.filename,
            error=str(e),
            request_id=request_id
        )
        return {"error": str(e)}

@app.post("/extract_excel/")
async def extract_excel(
    request: Request,
    file: UploadFile = File(...),
    extract_images: bool = True,
    extract_charts: bool = True,
    extract_formatting: bool = True
):
    """
    Advanced Excel extraction with configurable feature flags.
    
    Args:
        file: Uploaded Excel file
        extract_images: Whether to extract embedded images
        extract_charts: Whether to extract chart information
        extract_formatting: Whether to extract cell formatting
        
    Returns:
        Structured Excel data with full fidelity
    """
    try:
        contents = await file.read()
        filename = file.filename
        
        # Validate file type
        if not filename.lower().endswith(('.xlsx', '.xls', '.xlsm')):
            return {"error": "Please upload an Excel file (.xlsx, .xls, .xlsm)"}
        
        # Large files go to background processing
        if len(contents) > 10 * 1024 * 1024:  # 10MB threshold
            job_id = await submit_job(
                "extract_excel_advanced",
                {
                    "file_bytes": contents,
                    "filename": filename,
                    "extract_images": extract_images,
                    "extract_charts": extract_charts,
                    "extract_formatting": extract_formatting
                },
                priority=JobPriority.HIGH
            )
            return {
                "filename": filename,
                "file_type": "excel",
                "extraction_flags": {
                    "extract_images": extract_images,
                    "extract_charts": extract_charts,
                    "extract_formatting": extract_formatting
                },
                "job_id": job_id,
                "status": "pending"
            }
        
        # Use advanced extractor with flags via FileRouter
        extracted_data = await FileRouter.extract_excel_advanced(
            contents,
            filename,
            extract_images=extract_images,
            extract_charts=extract_charts,
            extract_formatting=extract_formatting,
            request_id=request.state.request_id
        )
        
        return {
            "filename": filename,
            "file_type": "excel",
            "extraction_flags": {
                "extract_images": extract_images,
                "extract_charts": extract_charts,
                "extract_formatting": extract_formatting
            },
            "content": extracted_data
        }
            
    except Exception as e:
        return {"error": str(e)}

# ======================================================
# EXCEL CREATION ENDPOINTS
# ======================================================

@app.post("/generate_excel/")
async def create_excel_from_data(data: dict):
    """
    Create Excel file from extracted data structure (reverse engineering).
    Supports: merged cells, images, charts, formatting, formulas, and more
    
    Args:
        data: Dictionary in the format produced by ExcelExtractor (with advanced features)
        
    Returns:
        StreamingResponse: Excel file download
    """
    try:
        creator = ExcelCreator()
        excel_bytes = creator.create_from_extracted_data(data)
        
        # Create BytesIO object for streaming
        excel_io = io.BytesIO(excel_bytes)
        
        # Return as downloadable file
        return StreamingResponse(
            excel_io,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=generated_excel.xlsx"}
        )
    except Exception as e:
        return {"error": str(e)}

@app.post("/create_excel/")
async def create_excel(json_data: str):
    """
    Create Excel file from JSON string containing extracted data.
    Supports: merged cells, images, charts, formatting, formulas, and more
    
    Args:
        json_data: JSON string with Excel data structure (from advanced extraction)
        
    Returns:
        StreamingResponse: Excel file download
    """
    try:
        creator = ExcelCreator()
        excel_bytes = creator.create_excel_from_json(json_data)
        
        return StreamingResponse(
            io.BytesIO(excel_bytes),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=from_json.xlsx"}
        )
    except Exception as e:
        return {"error": str(e)}

# ======================================================
# DOCUMENT GENERATION ENDPOINTS
# ======================================================

@app.post("/generate_exam_zip/")
async def generate_exam_zip(
    document_name: str,
    questions_file: UploadFile = File(...),
    answers_file: UploadFile = File(...),
    format: str = "docx",
    font_family: str = "Arial",
    font_size: int = 12
):
    """
    Accepts two text files (questions and answers) and returns a zip
    containing two documents (questions + answers) without saving them on disk.
    
    Args:
        document_name: Name for the document package
        questions_file: Text file containing questions
        answers_file: Text file containing answers
        format: Output format - "docx", "pdf", "txt", "md"
        font_family: Font family for styling
        font_size: Default font size
    """
    try:
        # Read uploaded text files
        questions_text = (await questions_file.read()).decode("utf-8").splitlines()
        answers_text = (await answers_file.read()).decode("utf-8").splitlines()
        
        # Create document style
        style = DocumentStyle(
            font_family=font_family,
            font_size=font_size,
            heading1_size=font_size + 4,
            heading2_size=font_size + 2
        )
        
        # Determine format
        try:
            doc_format = DocumentFormat(format.lower())
        except ValueError:
            doc_format = DocumentFormat.DOCX
        
        # Create zip in memory using new DocumentPackager
        zip_bytes = DocumentPackager.create_exam_package(
            document_name,
            questions_text,
            answers_text,
            doc_format,
            style
        )
        
        # Return as downloadable file
        return StreamingResponse(
            io.BytesIO(zip_bytes),
            media_type="application/x-zip-compressed",
            headers={"Content-Disposition": f"attachment; filename={document_name}.zip"}
        )
    except Exception as e:
        return {"error": str(e)}

@app.post("/generate_document/")
async def generate_document(
    document_name: str,
    content: dict,
    format: str = "docx",
    font_family: str = "Arial",
    font_size: int = 12,
    line_spacing: float = 1.15
):
    """
    Generate advanced document packages with custom content and styling.
    
    Args:
        document_name: Name for the document package
        content: Dict with document structure and content
        format: Output format - "docx", "pdf", "txt", "md"
        font_family: Font family for styling
        font_size: Default font size
        line_spacing: Line spacing multiplier
        
    Expected content format:
    {
        "documents": {
            "filename1": {
                "title": "Document Title",
                "content": [
                    {"type": "heading", "text": "Title", "level": 1},
                    {"type": "paragraph", "text": "Content", "bold": True}
                ]
            }
        }
    }
    """
    try:
        # Create document style
        style = DocumentStyle(
            font_family=font_family,
            font_size=font_size,
            heading1_size=font_size + 4,
            heading2_size=font_size + 2,
            line_spacing=line_spacing
        )
        
        # Determine format
        try:
            doc_format = DocumentFormat(format.lower())
        except ValueError:
            doc_format = DocumentFormat.DOCX
        
        # Generate single document (first document in the package)
        documents = content.get("documents", {})
        
        if not documents:
            return {"error": "No documents found in content"}
        
        # Get the first document
        first_doc_key = list(documents.keys())[0]
        doc_data = documents[first_doc_key]
        
        # Convert content to document blocks
        doc_content = []
        
        for block in doc_data.get("content", []):
            block_type = block.get("type", "paragraph")
            
            if block_type == "heading":
                from services.document_generator import Heading
                doc_content.append(Heading(
                    block.get("text", ""),
                    level=block.get("level", 1)
                ))
            elif block_type == "paragraph":
                from services.document_generator import Paragraph
                doc_content.append(Paragraph(
                    block.get("text", ""),
                    bold=block.get("bold", False),
                    italic=block.get("italic", False),
                    underline=block.get("underline", False),
                    font_size=block.get("font_size"),
                    alignment=block.get("alignment", "left")
                ))
        
        # Generate document
        from services.document_generator import DocumentGenerator
        generator = DocumentGenerator(style)
        doc_bytes = generator.create_document(
            doc_data.get("title", first_doc_key),
            doc_content,
            doc_format
        )
        
        # Add file extension
        ext = doc_format.value
        filename = f"{first_doc_key}.{ext}"
        
        # Determine media type based on format
        media_types = {
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "pdf": "application/pdf",
            "txt": "text/plain",
            "md": "text/markdown"
        }
        media_type = media_types.get(ext, "application/octet-stream")
        
        # Return as downloadable file
        return StreamingResponse(
            io.BytesIO(doc_bytes),
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        return {"error": str(e)}

# ======================================================
# BATCH PROCESSING ENDPOINTS
# ======================================================

@app.post("/extract_batch/")
async def extract_batch(files: List[UploadFile] = File(...)):
    """
    Batch file extraction endpoint for processing multiple files simultaneously.
    
    Args:
        files: List of uploaded files (max 50)
        
    Returns:
        Job ID for background processing
        
    Use Case:
        - Process hundreds of documents in one request
        - Enterprise document migration projects
        - Bulk data extraction from reports
        - Non-blocking batch processing with job tracking
    """
    try:
        # Validate files
        files_data = []
        for file in files:
            contents = await file.read()
            files_data.append({
                "filename": file.filename,
                "size": len(contents),
                "mime_type": file.content_type or "application/octet-stream",
                "contents": contents
            })
        
        validation_result = validate_multiple_files([
            {
                "filename": f["filename"],
                "size": f["size"],
                "mime_type": f["mime_type"]
            }
            for f in files_data
        ])
        
        if not validation_result["valid"]:
            return {
                "error": "Batch validation failed",
                "details": validation_result["errors"]
            }
        
        # Submit batch job
        job_id = await submit_job("extract_batch", {
            "files": files_data
        }, priority=JobPriority.NORMAL)
        
        return {
            "job_id": job_id,
            "message": f"Batch job submitted for {validation_result['valid_files']} files",
            "status": "pending",
            "total_files": validation_result["total_files"],
            "total_size": validation_result["total_size"]
        }
        
    except Exception as e:
        return {"error": str(e)}

# ======================================================
# JOB MANAGEMENT ENDPOINTS
# ======================================================

@app.get("/job_status/{job_id}")
async def get_job_status_endpoint(job_id: str):
    """Get the status of a background job."""
    try:
        job_status = await get_job_status(job_id)
        if not job_status:
            return {"error": "Job not found"}
        return job_status
    except Exception as e:
        return {"error": str(e)}

# ======================================================
# HEALTH CHECK ENDPOINTS
# ======================================================

@app.get("/health")
async def health_check():
    """Basic health check endpoint."""
    return {"status": "healthy", "service": "slide-extractor-api"}

@app.get("/health/detailed")
async def detailed_health_check():
    """Comprehensive health check with system metrics."""
    try:
        await health_monitor.check_all_components()
        health_report = health_monitor.get_overall_health()
        return health_report
    except Exception as e:
        logger.error(
            "Health check failed",
            error=str(e),
            request_id=getattr(getattr(health_monitor, 'request', None), 'request_id', None)
        )
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }

@app.get("/health/history")
async def health_history(hours: int = 24):
    """Get health history for monitoring."""
    try:
        history = health_monitor.get_health_history(hours)
        return {
            "status": "success",
            "hours": hours,
            "data_points": len(history),
            "history": history
        }
    except Exception as e:
        logger.error(
            "Health history retrieval failed",
            error=str(e),
            hours=hours
        )
        return {
            "status": "error",
            "error": str(e)
        }

@app.get("/metrics")
async def get_metrics():
    """Get system and application metrics."""
    try:
        system_metrics = health_monitor.get_system_metrics()
        job_metrics = health_monitor.get_job_queue_metrics()
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "system_metrics": system_metrics.__dict__,
            "job_metrics": job_metrics.__dict__,
            "api_info": {
                "version": "1.0.0",
                "uptime_seconds": system_metrics.uptime_seconds
            }
        }
    except Exception as e:
        logger.error("Metrics retrieval failed", error=str(e))
        return {
            "status": "error",
            "error": str(e)
        }

# ======================================================
# MAIN APPLICATION
# ======================================================

if __name__ == "__main__":
    import os
    import uvicorn

    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
