"""
Enhanced health monitoring for the slide-extractor-api
"""
import asyncio
import psutil
import time
import os
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum


class HealthStatus(Enum):
    """Health status levels."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class ComponentStatus(Enum):
    """Component status levels."""
    UP = "up"
    DOWN = "down"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


@dataclass
class ComponentHealth:
    """Health information for a system component."""
    name: str
    status: ComponentStatus
    message: str
    response_time_ms: Optional[float] = None
    last_check: Optional[datetime] = None
    details: Optional[Dict[str, Any]] = None


@dataclass
class SystemMetrics:
    """System performance metrics."""
    cpu_percent: float
    memory_percent: float
    disk_usage_percent: float
    active_connections: int
    uptime_seconds: float
    load_average: Optional[List[float]] = None


@dataclass
class JobQueueMetrics:
    """Background job queue metrics."""
    pending_jobs: int
    running_jobs: int
    completed_jobs: int
    failed_jobs: int
    total_processed: int
    avg_processing_time_ms: float


class HealthMonitor:
    """Comprehensive health monitoring system."""
    
    def __init__(self):
        self.start_time = time.time()
        self.components: Dict[str, ComponentHealth] = {}
        self.last_system_check = None
        self.system_metrics: Optional[SystemMetrics] = None
        self.job_metrics: Optional[JobQueueMetrics] = None
        self.health_history: List[Dict[str, Any]] = []
        self.max_history_size = 100
        
        # Initialize component checks
        self._initialize_components()
    
    def _initialize_components(self):
        """Initialize default components to monitor."""
        self.components = {
            "database": ComponentHealth("database", ComponentStatus.UNKNOWN, "Not configured"),
            "redis": ComponentHealth("redis", ComponentStatus.UNKNOWN, "Not configured"),
            "file_system": ComponentHealth("file_system", ComponentStatus.UP, "File system accessible"),
            "job_processor": ComponentHealth("job_processor", ComponentStatus.UNKNOWN, "Checking..."),
            "ocr_service": ComponentHealth("ocr_service", ComponentStatus.UNKNOWN, "Checking..."),
            "document_generator": ComponentHealth("document_generator", ComponentStatus.UNKNOWN, "Checking..."),
        }
    
    async def check_all_components(self) -> Dict[str, ComponentHealth]:
        """Check health of all components."""
        # Check file system
        await self._check_file_system()
        
        # Check job processor
        await self._check_job_processor()
        
        # Check OCR service
        await self._check_ocr_service()
        
        # Check document generator
        await self._check_document_generator()
        
        # Check external services (if configured)
        await self._check_database()
        await self._check_redis()
        
        return self.components
    
    async def _check_file_system(self):
        """Check file system health."""
        try:
            start_time = time.time()
            
            # Test write permissions
            test_file = "health_check.tmp"
            with open(test_file, 'w') as f:
                f.write("health check")
            
            # Test read permissions
            with open(test_file, 'r') as f:
                content = f.read()
            
            # Clean up
            os.remove(test_file)
            
            response_time = (time.time() - start_time) * 1000
            
            self.components["file_system"] = ComponentHealth(
                name="file_system",
                status=ComponentStatus.UP,
                message="File system read/write OK",
                response_time_ms=response_time,
                last_check=datetime.utcnow(),
                details={"test_file_size": len(content)}
            )
            
        except Exception as e:
            self.components["file_system"] = ComponentHealth(
                name="file_system",
                status=ComponentStatus.DOWN,
                message=f"File system error: {str(e)}",
                last_check=datetime.utcnow()
            )
    
    async def _check_job_processor(self):
        """Check job processor health."""
        try:
            from services.job_processor import job_queue, job_processor
            
            start_time = time.time()
            
            # Check if job processor is running
            is_running = job_processor.running
            pending_count = len(job_queue.pending_jobs)
            running_count = len(job_queue.running_jobs)
            
            response_time = (time.time() - start_time) * 1000
            
            if is_running:
                status = ComponentStatus.UP
                message = f"Job processor running (pending: {pending_count}, running: {running_count})"
            else:
                status = ComponentStatus.DOWN
                message = "Job processor not running"
            
            self.components["job_processor"] = ComponentHealth(
                name="job_processor",
                status=status,
                message=message,
                response_time_ms=response_time,
                last_check=datetime.utcnow(),
                details={
                    "is_running": is_running,
                    "pending_jobs": pending_count,
                    "running_jobs": running_count,
                    "worker_count": job_processor.num_workers
                }
            )
            
        except Exception as e:
            self.components["job_processor"] = ComponentHealth(
                name="job_processor",
                status=ComponentStatus.DOWN,
                message=f"Job processor error: {str(e)}",
                last_check=datetime.utcnow()
            )
    
    async def _check_ocr_service(self):
        """Check OCR service availability."""
        try:
            start_time = time.time()
            
            # Try to import and test Tesseract
            import pytesseract
            from PIL import Image
            
            # Create a simple test image
            test_img = Image.new('RGB', (100, 100), color='white')
            
            # Test OCR (this will fail if Tesseract is not available)
            try:
                result = pytesseract.image_to_string(test_img)
                status = ComponentStatus.UP
                message = "OCR service available"
            except Exception as ocr_error:
                status = ComponentStatus.DOWN
                message = f"OCR service unavailable: {str(ocr_error)}"
            
            response_time = (time.time() - start_time) * 1000
            
            self.components["ocr_service"] = ComponentHealth(
                name="ocr_service",
                status=status,
                message=message,
                response_time_ms=response_time,
                last_check=datetime.utcnow()
            )
            
        except Exception as e:
            self.components["ocr_service"] = ComponentHealth(
                name="ocr_service",
                status=ComponentStatus.DOWN,
                message=f"OCR check failed: {str(e)}",
                last_check=datetime.utcnow()
            )
    
    async def _check_document_generator(self):
        """Check document generator health."""
        try:
            start_time = time.time()
            
            # Test document generation
            from services.document_generator import DocumentGenerator, DocumentFormat, Paragraph
            
            generator = DocumentGenerator()
            
            # Create a simple test document
            content = [Paragraph("Health check test")]
            doc_bytes = generator.create_document("health_check", content, DocumentFormat.TXT)
            
            response_time = (time.time() - start_time) * 1000
            
            if doc_bytes and len(doc_bytes) > 0:
                self.components["document_generator"] = ComponentHealth(
                    name="document_generator",
                    status=ComponentStatus.UP,
                    message="Document generator working",
                    response_time_ms=response_time,
                    last_check=datetime.utcnow(),
                    details={
                        "test_document_size": len(doc_bytes),
                        "supported_formats": [fmt.value for fmt in DocumentFormat]
                    }
                )
            else:
                self.components["document_generator"] = ComponentHealth(
                    name="document_generator",
                    status=ComponentStatus.DOWN,
                    message="Document generator returned empty result",
                    last_check=datetime.utcnow()
                )
            
        except Exception as e:
            self.components["document_generator"] = ComponentHealth(
                name="document_generator",
                status=ComponentStatus.DOWN,
                message=f"Document generator error: {str(e)}",
                last_check=datetime.utcnow()
            )
    
    async def _check_database(self):
        """Check database connectivity (placeholder)."""
        # This would be implemented based on your database setup
        self.components["database"] = ComponentHealth(
            name="database",
            status=ComponentStatus.UNKNOWN,
            message="Database not configured",
            last_check=datetime.utcnow()
        )
    
    async def _check_redis(self):
        """Check Redis connectivity (placeholder)."""
        # This would be implemented based on your Redis setup
        self.components["redis"] = ComponentHealth(
            name="redis",
            status=ComponentStatus.UNKNOWN,
            message="Redis not configured",
            last_check=datetime.utcnow()
        )
    
    def get_system_metrics(self) -> SystemMetrics:
        """Get current system metrics."""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_usage_percent = disk.percent
            
            # Network connections
            try:
                connections = len(psutil.net_connections())
            except (psutil.AccessDenied, OSError):
                connections = -1  # Permission denied
            
            # Uptime
            uptime_seconds = time.time() - self.start_time
            
            # Load average (Unix only)
            try:
                load_avg = list(os.getloadavg())
            except (AttributeError, OSError):
                load_avg = None
            
            self.system_metrics = SystemMetrics(
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                disk_usage_percent=disk_usage_percent,
                active_connections=connections,
                uptime_seconds=uptime_seconds,
                load_average=load_avg
            )
            
        except Exception as e:
            # Create default metrics on error
            self.system_metrics = SystemMetrics(
                cpu_percent=0.0,
                memory_percent=0.0,
                disk_usage_percent=0.0,
                active_connections=0,
                uptime_seconds=time.time() - self.start_time
            )
        
        return self.system_metrics
    
    def get_job_queue_metrics(self) -> JobQueueMetrics:
        """Get job queue metrics."""
        try:
            from services.job_processor import job_queue
            
            pending = len(job_queue.pending_jobs)
            running = len(job_queue.running_jobs)
            completed = len(job_queue.completed_jobs)
            failed = sum(1 for job in job_queue.completed_jobs.values() 
                        if job.status.value == "failed")
            
            # Calculate average processing time
            completed_jobs = [job for job in job_queue.completed_jobs.values() 
                             if job.status.value == "completed" and job.completed_at and job.started_at]
            
            if completed_jobs:
                avg_time = sum(
                    (job.completed_at - job.started_at).total_seconds() * 1000
                    for job in completed_jobs[-10:]  # Last 10 completed jobs
                ) / len(completed_jobs[-10:])
            else:
                avg_time = 0.0
            
            self.job_metrics = JobQueueMetrics(
                pending_jobs=pending,
                running_jobs=running,
                completed_jobs=completed,
                failed_jobs=failed,
                total_processed=completed + failed,
                avg_processing_time_ms=avg_time
            )
            
        except Exception as e:
            self.job_metrics = JobQueueMetrics(0, 0, 0, 0, 0, 0.0)
        
        return self.job_metrics
    
    def get_overall_health(self) -> Dict[str, Any]:
        """Get overall health status."""
        # Check components
        component_statuses = [comp.status for comp in self.components.values()]
        
        # Determine overall status
        if all(status == ComponentStatus.UP for status in component_statuses):
            overall_status = HealthStatus.HEALTHY
        elif any(status == ComponentStatus.DOWN for status in component_statuses):
            overall_status = HealthStatus.UNHEALTHY
        else:
            overall_status = HealthStatus.DEGRADED
        
        # Get metrics
        system_metrics = self.get_system_metrics()
        job_metrics = self.get_job_queue_metrics()
        
        # Create health report
        health_report = {
            "status": overall_status.value,
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": system_metrics.uptime_seconds,
            "version": "1.0.0",  # This could be read from a version file
            "components": {name: asdict(comp) for name, comp in self.components.items()},
            "system_metrics": asdict(system_metrics),
            "job_metrics": asdict(job_metrics),
            "checks": {
                "total_components": len(self.components),
                "healthy_components": sum(1 for comp in self.components.values() 
                                        if comp.status == ComponentStatus.UP),
                "degraded_components": sum(1 for comp in self.components.values() 
                                          if comp.status == ComponentStatus.DEGRADED),
                "unhealthy_components": sum(1 for comp in self.components.values() 
                                            if comp.status == ComponentStatus.DOWN)
            }
        }
        
        # Add to history
        self.health_history.append({
            "timestamp": health_report["timestamp"],
            "status": overall_status.value,
            "cpu_percent": system_metrics.cpu_percent,
            "memory_percent": system_metrics.memory_percent,
            "pending_jobs": job_metrics.pending_jobs
        })
        
        # Limit history size
        if len(self.health_history) > self.max_history_size:
            self.health_history.pop(0)
        
        return health_report
    
    def get_health_history(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get health history for the specified hours."""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        return [
            entry for entry in self.health_history
            if datetime.fromisoformat(entry["timestamp"]) > cutoff_time
        ]


# Global health monitor instance
health_monitor = HealthMonitor()
