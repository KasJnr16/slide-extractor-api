"""
Background job processing and task queue management for slide-extractor-api
"""
import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from enum import Enum
import json
import os
from dataclasses import dataclass, asdict
from .structured_logger import logger


class JobStatus(Enum):
    """Job status enumeration."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobPriority(Enum):
    """Job priority levels."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4


@dataclass
class JobResult:
    """Job result data structure."""
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    output_files: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class Job:
    """Background job data structure."""
    id: str
    task_type: str
    parameters: Dict[str, Any]
    status: JobStatus = JobStatus.PENDING
    priority: JobPriority = JobPriority.NORMAL
    created_at: datetime = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress: float = 0.0
    result: Optional[JobResult] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()


class JobQueue:
    """In-memory job queue with priority support."""
    
    def __init__(self):
        self.jobs: Dict[str, Job] = {}
        self.pending_jobs: List[Job] = []
        self.running_jobs: Dict[str, Job] = {}
        self.completed_jobs: Dict[str, Job] = {}
        self._lock = asyncio.Lock()
    
    async def add_job(self, task_type: str, parameters: Dict[str, Any], 
                     priority: JobPriority = JobPriority.NORMAL) -> str:
        """Add a new job to the queue."""
        job_id = str(uuid.uuid4())
        job = Job(
            id=job_id,
            task_type=task_type,
            parameters=parameters,
            priority=priority
        )
        
        async with self._lock:
            self.jobs[job_id] = job
            self.pending_jobs.append(job)
            # Sort by priority (higher first) and creation time
            self.pending_jobs.sort(key=lambda j: (-j.priority.value, j.created_at))
        
        return job_id
    
    async def get_next_job(self) -> Optional[Job]:
        """Get the next job to process."""
        async with self._lock:
            if self.pending_jobs:
                job = self.pending_jobs.pop(0)
                job.status = JobStatus.RUNNING
                job.started_at = datetime.utcnow()
                self.running_jobs[job.id] = job
                return job
        return None
    
    async def update_job_progress(self, job_id: str, progress: float):
        """Update job progress."""
        async with self._lock:
            if job_id in self.running_jobs:
                self.running_jobs[job_id].progress = min(100.0, max(0.0, progress))
    
    async def complete_job(self, job_id: str, result: JobResult):
        """Mark a job as completed."""
        async with self._lock:
            if job_id in self.running_jobs:
                job = self.running_jobs.pop(job_id)
                job.status = JobStatus.COMPLETED
                job.completed_at = datetime.utcnow()
                job.progress = 100.0
                job.result = result
                self.completed_jobs[job_id] = job
    
    async def fail_job(self, job_id: str, error_message: str):
        """Mark a job as failed."""
        async with self._lock:
            if job_id in self.running_jobs:
                job = self.running_jobs.pop(job_id)
                job.status = JobStatus.FAILED
                job.completed_at = datetime.utcnow()
                job.error_message = error_message
                
                # Retry logic
                if job.retry_count < job.max_retries:
                    job.retry_count += 1
                    job.status = JobStatus.PENDING
                    job.started_at = None
                    self.pending_jobs.append(job)
                    self.pending_jobs.sort(key=lambda j: (-j.priority.value, j.created_at))
                else:
                    self.completed_jobs[job_id] = job
    
    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a job."""
        async with self._lock:
            # Remove from pending if not started
            for i, job in enumerate(self.pending_jobs):
                if job.id == job_id:
                    job.status = JobStatus.CANCELLED
                    job.completed_at = datetime.utcnow()
                    self.completed_jobs[job_id] = job
                    self.pending_jobs.pop(i)
                    return True
            
            # Cancel running job
            if job_id in self.running_jobs:
                job = self.running_jobs.pop(job_id)
                job.status = JobStatus.CANCELLED
                job.completed_at = datetime.utcnow()
                self.completed_jobs[job_id] = job
                return True
        
        return False
    
    async def get_job_status(self, job_id: str) -> Optional[Job]:
        """Get job status."""
        async with self._lock:
            return self.jobs.get(job_id)
    
    async def get_jobs_by_status(self, status: JobStatus) -> List[Job]:
        """Get jobs by status."""
        async with self._lock:
            return [job for job in self.jobs.values() if job.status == status]
    
    async def cleanup_old_jobs(self, days: int = 7):
        """Clean up old completed jobs."""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        async with self._lock:
            to_remove = []
            for job_id, job in self.completed_jobs.items():
                if job.completed_at and job.completed_at < cutoff_date:
                    to_remove.append(job_id)
            
            for job_id in to_remove:
                del self.completed_jobs[job_id]
                del self.jobs[job_id]


class JobProcessor:
    """Background job processor with task handlers."""
    
    def __init__(self, job_queue: JobQueue):
        self.job_queue = job_queue
        self.task_handlers: Dict[str, Callable] = {}
        self.worker_tasks: List[asyncio.Task] = []
        self.num_workers = 3  # Number of concurrent workers
        self.running = False
    
    def register_task_handler(self, task_type: str, handler: Callable):
        """Register a task handler."""
        self.task_handlers[task_type] = handler
    
    async def start_workers(self):
        """Start background workers."""
        self.running = True
        for i in range(self.num_workers):
            task = asyncio.create_task(self._worker(f"worker-{i}"))
            self.worker_tasks.append(task)
    
    async def stop_workers(self):
        """Stop background workers."""
        self.running = False
        for task in self.worker_tasks:
            task.cancel()
        
        await asyncio.gather(*self.worker_tasks, return_exceptions=True)
        self.worker_tasks.clear()
    
    async def _worker(self, worker_name: str):
        """Background worker process."""
        while self.running:
            try:
                job = await self.job_queue.get_next_job()
                if not job:
                    await asyncio.sleep(1)  # No jobs available, wait
                    continue

                logger.info(
                    "Processing background job",
                    worker=worker_name,
                    job_id=job.id,
                    task_type=job.task_type
                )
                
                # Get task handler
                handler = self.task_handlers.get(job.task_type)
                if not handler:
                    await self.job_queue.fail_job(job.id, f"No handler for task type: {job.task_type}")
                    continue
                
                try:
                    # Execute task with progress tracking
                    result = await self._execute_with_progress(job, handler)
                    await self.job_queue.complete_job(job.id, result)
                    logger.info(
                        "Completed background job",
                        worker=worker_name,
                        job_id=job.id,
                        task_type=job.task_type
                    )
                
                except Exception as e:
                    error_msg = f"Task execution failed: {str(e)}"
                    await self.job_queue.fail_job(job.id, error_msg)
                    logger.error(
                        "Failed background job",
                        worker=worker_name,
                        job_id=job.id,
                        task_type=job.task_type,
                        error=error_msg
                    )
            
            except Exception as e:
                logger.error(
                    "Background worker error",
                    worker=worker_name,
                    error=str(e)
                )
                await asyncio.sleep(5)  # Brief pause on error
    
    async def _execute_with_progress(self, job: Job, handler: Callable) -> JobResult:
        """Execute task with progress tracking."""
        # Create a progress callback
        async def progress_callback(progress: float):
            await self.job_queue.update_job_progress(job.id, progress)
        
        # Check if handler accepts progress callback
        try:
            import inspect
            sig = inspect.signature(handler)
            if 'progress_callback' in sig.parameters:
                result = await handler(job.parameters, progress_callback=progress_callback)
            else:
                result = await handler(job.parameters)
            
            return JobResult(success=True, data=result)
        
        except Exception as e:
            return JobResult(success=False, error=str(e))


# Global instances
job_queue = JobQueue()
job_processor = JobProcessor(job_queue)


# Task handler decorators and utilities
def task_handler(task_type: str):
    """Decorator to register task handlers."""
    def decorator(func):
        job_processor.register_task_handler(task_type, func)
        return func
    return decorator


async def submit_job(task_type: str, parameters: Dict[str, Any], 
                    priority: JobPriority = JobPriority.NORMAL) -> str:
    """Submit a job to the queue."""
    return await job_queue.add_job(task_type, parameters, priority)


async def get_job_status(job_id: str) -> Optional[Dict[str, Any]]:
    """Get job status as dictionary."""
    job = await job_queue.get_job_status(job_id)
    if not job:
        return None
    
    return {
        "id": job.id,
        "task_type": job.task_type,
        "status": job.status.value,
        "progress": job.progress,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "error_message": job.error_message,
        "retry_count": job.retry_count,
        "result": asdict(job.result) if job.result else None
    }


# Background task handlers for existing services
@task_handler("extract_file")
async def extract_file_task(parameters: Dict[str, Any], progress_callback=None) -> Dict[str, Any]:
    """Background file extraction task."""
    from services.file_router import FileRouter
    
    file_bytes = parameters["file_bytes"]
    filename = parameters["filename"]
    request_id = parameters.get("request_id")
    
    if progress_callback:
        await progress_callback(10.0)
    
    # Route to appropriate extractor
    file_type, content = await FileRouter.extract_file_content(file_bytes, filename, request_id=request_id)
    
    if progress_callback:
        await progress_callback(90.0)
    
    result = {
        "filename": filename,
        "file_type": file_type,
        "content": content
    }
    
    if progress_callback:
        await progress_callback(100.0)
    
    return result


@task_handler("extract_excel_advanced")
async def extract_excel_advanced_task(parameters: Dict[str, Any], progress_callback=None) -> Dict[str, Any]:
    """Background advanced Excel extraction task."""
    from services.file_router import FileRouter
    
    file_bytes = parameters["file_bytes"]
    filename = parameters["filename"]
    extract_images = parameters.get("extract_images", True)
    extract_charts = parameters.get("extract_charts", True)
    extract_formatting = parameters.get("extract_formatting", True)
    request_id = parameters.get("request_id")
    
    if progress_callback:
        await progress_callback(10.0)
    
    # Extract with advanced features
    extracted_data = await FileRouter.extract_excel_advanced(
        file_bytes,
        filename,
        extract_images=extract_images,
        extract_charts=extract_charts,
        extract_formatting=extract_formatting,
        request_id=request_id
    )
    
    if progress_callback:
        await progress_callback(90.0)
    
    result = {
        "filename": filename,
        "file_type": "excel",
        "extraction_flags": {
            "extract_images": extract_images,
            "extract_charts": extract_charts,
            "extract_formatting": extract_formatting
        },
        "content": extracted_data
    }
    
    if progress_callback:
        await progress_callback(100.0)
    
    return result


@task_handler("generate_document_package")
async def generate_document_package_task(parameters: Dict[str, Any], progress_callback=None) -> bytes:
    """Background document package generation task."""
    from services.document_generator import DocumentPackager, DocumentFormat, DocumentStyle
    
    document_name = parameters["document_name"]
    content = parameters["content"]
    format_type = parameters.get("format", "docx")
    font_family = parameters.get("font_family", "Arial")
    font_size = parameters.get("font_size", 12)
    line_spacing = parameters.get("line_spacing", 1.15)
    
    if progress_callback:
        await progress_callback(10.0)
    
    # Create document style
    style = DocumentStyle(
        font_family=font_family,
        font_size=font_size,
        heading1_size=font_size + 4,
        heading2_size=font_size + 2,
        line_spacing=line_spacing
    )
    
    if progress_callback:
        await progress_callback(30.0)
    
    # Determine format
    try:
        doc_format = DocumentFormat(format_type.lower())
    except ValueError:
        doc_format = DocumentFormat.DOCX
    
    # Generate documents
    documents = {}
    
    for i, (filename, doc_data) in enumerate(content.get("documents", {}).items()):
        if progress_callback:
            await progress_callback(30.0 + (i / len(content.get("documents", {}))) * 50.0)
        
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
            doc_data.get("title", filename),
            doc_content,
            doc_format
        )
        
        # Add file extension
        ext = doc_format.value
        documents[f"{filename}.{ext}"] = doc_bytes
    
    if progress_callback:
        await progress_callback(90.0)
    
    # Create package
    zip_bytes = DocumentPackager.create_package(documents, document_name)
    
    if progress_callback:
        await progress_callback(100.0)
    
    return zip_bytes


# Startup and shutdown functions
async def start_background_processor():
    """Start the background job processor."""
    await job_processor.start_workers()
    print("Background job processor started")


async def stop_background_processor():
    """Stop the background job processor."""
    await job_processor.stop_workers()
    print("Background job processor stopped")


# Cleanup task
async def cleanup_old_jobs():
    """Periodic cleanup of old jobs."""
    while True:
        try:
            await job_queue.cleanup_old_jobs()
            await asyncio.sleep(3600)  # Run every hour
        except Exception as e:
            print(f"Cleanup error: {e}")
            await asyncio.sleep(300)  # Retry after 5 minutes
