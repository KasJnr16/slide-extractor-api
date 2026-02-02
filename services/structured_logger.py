"""
Structured logging configuration for the slide-extractor-api
"""
import logging
import json
import time
import traceback
from datetime import datetime
from typing import Dict, Any, Optional
from enum import Enum
import sys


class LogLevel(Enum):
    """Log levels with numeric values."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class StructuredLogger:
    """Structured logger with JSON formatting and context tracking."""
    
    def __init__(self, name: str = "slide-extractor-api"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        
        # Avoid duplicate handlers
        if not self.logger.handlers:
            self._setup_handlers()
    
    def _setup_handlers(self):
        """Setup console and file handlers with JSON formatting."""
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(JsonFormatter())
        self.logger.addHandler(console_handler)
        
        # File handler for errors
        file_handler = logging.FileHandler("api_errors.log")
        file_handler.setLevel(logging.ERROR)
        file_handler.setFormatter(JsonFormatter())
        self.logger.addHandler(file_handler)
    
    def _log(self, level: LogLevel, message: str, **kwargs):
        """Internal logging method."""
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": level.value,
            "message": message,
            "service": "slide-extractor-api",
            **kwargs
        }
        
        # Convert to JSON string
        log_line = json.dumps(log_data, default=str)
        
        # Log at appropriate level
        if level == LogLevel.DEBUG:
            self.logger.debug(log_line)
        elif level == LogLevel.INFO:
            self.logger.info(log_line)
        elif level == LogLevel.WARNING:
            self.logger.warning(log_line)
        elif level == LogLevel.ERROR:
            self.logger.error(log_line)
        elif level == LogLevel.CRITICAL:
            self.logger.critical(log_line)
    
    def debug(self, message: str, **kwargs):
        """Log debug message."""
        self._log(LogLevel.DEBUG, message, **kwargs)
    
    def info(self, message: str, **kwargs):
        """Log info message."""
        self._log(LogLevel.INFO, message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log warning message."""
        self._log(LogLevel.WARNING, message, **kwargs)
    
    def error(self, message: str, **kwargs):
        """Log error message."""
        self._log(LogLevel.ERROR, message, **kwargs)
    
    def critical(self, message: str, **kwargs):
        """Log critical message."""
        self._log(LogLevel.CRITICAL, message, **kwargs)
    
    def log_request(self, method: str, path: str, client_ip: str, 
                    user_agent: str = None, request_id: str = None, **kwargs):
        """Log HTTP request."""
        self.info(
            "HTTP request received",
            event_type="http_request",
            method=method,
            path=path,
            client_ip=client_ip,
            user_agent=user_agent,
            request_id=request_id,
            **kwargs
        )
    
    def log_response(self, method: str, path: str, status_code: int, 
                    duration_ms: float, request_id: str = None, **kwargs):
        """Log HTTP response."""
        self.info(
            "HTTP response sent",
            event_type="http_response",
            method=method,
            path=path,
            status_code=status_code,
            duration_ms=duration_ms,
            request_id=request_id,
            **kwargs
        )
    
    def log_file_processing(self, filename: str, file_size: int, file_type: str,
                          operation: str, success: bool, duration_ms: float = None,
                          request_id: str = None, **kwargs):
        """Log file processing operation."""
        level = LogLevel.INFO if success else LogLevel.ERROR
        message = f"File {operation} {'successful' if success else 'failed'}"
        
        self._log(
            level,
            message,
            event_type="file_processing",
            filename=filename,
            file_size=file_size,
            file_type=file_type,
            operation=operation,
            success=success,
            duration_ms=duration_ms,
            request_id=request_id,
            **kwargs
        )
    
    def log_job_event(self, job_id: str, event_type: str, status: str, 
                      progress: float = None, error: str = None, **kwargs):
        """Log background job event."""
        self.info(
            f"Job {event_type}",
            event_type="job_event",
            job_id=job_id,
            job_status=status,
            progress=progress,
            error=error,
            **kwargs
        )
    
    def log_validation_error(self, filename: str, errors: list, warnings: list = None,
                           request_id: str = None, **kwargs):
        """Log file validation errors."""
        self.warning(
            "File validation failed",
            event_type="validation_error",
            filename=filename,
            errors=errors,
            warnings=warnings or [],
            request_id=request_id,
            **kwargs
        )
    
    def log_rate_limit(self, client_ip: str, endpoint: str, limit: int, 
                       remaining: int, retry_after: int, **kwargs):
        """Log rate limiting event."""
        self.warning(
            "Rate limit exceeded",
            event_type="rate_limit",
            client_ip=client_ip,
            endpoint=endpoint,
            limit=limit,
            remaining=remaining,
            retry_after=retry_after,
            **kwargs
        )
    
    def log_system_event(self, event_type: str, message: str, **kwargs):
        """Log system-level events."""
        self.info(
            message,
            event_type="system_event",
            system_event=event_type,
            **kwargs
        )


class JsonFormatter(logging.Formatter):
    """JSON formatter for structured logging."""
    
    def format(self, record):
        """Format log record as JSON."""
        # Parse the JSON string from our structured logger
        try:
            log_data = json.loads(record.getMessage())
            return json.dumps(log_data, default=str)
        except (json.JSONDecodeError, AttributeError):
            # Fallback for non-structured logs
            return json.dumps({
                "timestamp": datetime.utcnow().isoformat(),
                "level": record.levelname,
                "message": record.getMessage(),
                "service": "slide-extractor-api",
                "module": record.module,
                "function": record.funcName,
                "line": record.lineno
            }, default=str)


# Global logger instance
logger = StructuredLogger()


# Request logging middleware helper
async def log_request_response(request, response, duration_ms, request_id=None):
    """Log HTTP request and response."""
    client_ip = request.headers.get("X-Forwarded-For", 
                                   request.headers.get("X-Real-IP", 
                                   request.client.host))
    
    logger.log_request(
        method=request.method,
        path=str(request.url.path),
        client_ip=client_ip,
        user_agent=request.headers.get("User-Agent"),
        request_id=request_id
    )
    
    logger.log_response(
        method=request.method,
        path=str(request.url.path),
        status_code=response.status_code,
        duration_ms=duration_ms,
        request_id=request_id
    )


# Context manager for timing operations
class OperationTimer:
    """Context manager for timing operations."""
    
    def __init__(self, operation_name: str, **context):
        self.operation_name = operation_name
        self.context = context
        self.start_time = None
        self.logger = StructuredLogger()
    
    def __enter__(self):
        self.start_time = time.time()
        self.logger.debug(
            f"Starting {self.operation_name}",
            operation=self.operation_name,
            phase="start",
            **self.context
        )
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration_ms = (time.time() - self.start_time) * 1000
        
        if exc_type is None:
            self.logger.info(
                f"Completed {self.operation_name}",
                operation=self.operation_name,
                phase="complete",
                duration_ms=duration_ms,
                success=True,
                **self.context
            )
        else:
            self.logger.error(
                f"Failed {self.operation_name}",
                operation=self.operation_name,
                phase="error",
                duration_ms=duration_ms,
                success=False,
                error=str(exc_val),
                error_type=exc_type.__name__,
                traceback=traceback.format_exc(),
                **self.context
            )
        
        return False  # Don't suppress exceptions


# Decorator for timing functions
def log_execution_time(operation_name: str = None, **context):
    """Decorator to log function execution time."""
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            name = operation_name or f"{func.__module__}.{func.__name__}"
            with OperationTimer(name, **context):
                return await func(*args, **kwargs)
        
        def sync_wrapper(*args, **kwargs):
            name = operation_name or f"{func.__module__}.{func.__name__}"
            with OperationTimer(name, **context):
                return func(*args, **kwargs)
        
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator
