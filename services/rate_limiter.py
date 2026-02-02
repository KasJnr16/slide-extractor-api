"""
Rate limiting middleware for the slide-extractor-api
"""
import time
import asyncio
from typing import Dict, Optional
from collections import defaultdict, deque
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
import json


class RateLimiter:
    """In-memory rate limiter using sliding window algorithm."""
    
    def __init__(self):
        # Store client requests: {client_ip: deque of timestamps}
        self.requests: Dict[str, deque] = defaultdict(deque)
        # Rate limits: requests per window
        self.limits = {
            "default": {"requests": 100, "window": 60},  # 100 requests per minute
            "upload": {"requests": 20, "window": 60},     # 20 uploads per minute
            "batch": {"requests": 5, "window": 300},       # 5 batch requests per 5 minutes
        }
        self.cleanup_interval = 300  # Clean up old data every 5 minutes
        self.last_cleanup = time.time()
    
    def is_allowed(self, client_ip: str, endpoint_type: str = "default") -> tuple[bool, Dict[str, int]]:
        """
        Check if client is allowed to make a request.
        
        Args:
            client_ip: Client IP address
            endpoint_type: Type of endpoint for different limits
            
        Returns:
            Tuple of (allowed, info_dict)
        """
        current_time = time.time()
        limit_config = self.limits.get(endpoint_type, self.limits["default"])
        max_requests = limit_config["requests"]
        window_seconds = limit_config["window"]
        
        # Cleanup old data periodically
        if current_time - self.last_cleanup > self.cleanup_interval:
            self._cleanup_old_data(current_time, window_seconds * 2)
            self.last_cleanup = current_time
        
        # Get or create client request queue
        client_requests = self.requests[client_ip]
        
        # Remove requests outside the window
        window_start = current_time - window_seconds
        while client_requests and client_requests[0] < window_start:
            client_requests.popleft()
        
        # Check if under limit
        request_count = len(client_requests)
        allowed = request_count < max_requests
        
        if allowed:
            client_requests.append(current_time)
        
        # Calculate remaining requests and reset time
        remaining = max(0, max_requests - request_count)
        reset_time = int(window_start + window_seconds) if client_requests else int(current_time + window_seconds)
        
        return allowed, {
            "limit": max_requests,
            "remaining": remaining,
            "reset": reset_time,
            "retry_after": max(1, reset_time - int(current_time)) if not allowed else 0
        }
    
    def _cleanup_old_data(self, current_time: float, max_age: float):
        """Clean up old client data to prevent memory leaks."""
        cutoff_time = current_time - max_age
        to_remove = []
        
        for client_ip, requests in self.requests.items():
            # Remove old requests
            while requests and requests[0] < cutoff_time:
                requests.popleft()
            
            # Remove empty client entries
            if not requests:
                to_remove.append(client_ip)
        
        for client_ip in to_remove:
            del self.requests[client_ip]


# Global rate limiter instance
rate_limiter = RateLimiter()


def get_endpoint_type(request: Request) -> str:
    """Determine endpoint type for rate limiting."""
    path = request.url.path.lower()
    
    if "/extract_batch" in path or "/generate_document_package" in path:
        return "batch"
    elif any(endpoint in path for endpoint in ["/extract_", "/generate_"]):
        return "upload"
    else:
        return "default"


async def rate_limit_middleware(request: Request, call_next):
    """
    Rate limiting middleware for FastAPI.
    
    This should be added to the FastAPI middleware stack.
    """
    # Get client IP (considering proxies)
    client_ip = request.headers.get("X-Forwarded-For", 
                                   request.headers.get("X-Real-IP", 
                                   request.client.host))
    
    # Handle multiple IPs in X-Forwarded-For
    if client_ip and "," in client_ip:
        client_ip = client_ip.split(",")[0].strip()
    
    endpoint_type = get_endpoint_type(request)
    
    # Check rate limit
    allowed, info = rate_limiter.is_allowed(client_ip, endpoint_type)
    
    if not allowed:
        return JSONResponse(
            status_code=429,
            content={
                "error": "Rate limit exceeded",
                "message": f"Too many requests. Try again in {info['retry_after']} seconds.",
                "limit": info["limit"],
                "remaining": info["remaining"],
                "reset": info["reset"],
                "retry_after": info["retry_after"]
            },
            headers={
                "X-RateLimit-Limit": str(info["limit"]),
                "X-RateLimit-Remaining": str(info["remaining"]),
                "X-RateLimit-Reset": str(info["reset"]),
                "Retry-After": str(info["retry_after"])
            }
        )
    
    # Process the request
    response = await call_next(request)
    
    # Add rate limit headers to successful responses
    response.headers["X-RateLimit-Limit"] = str(info["limit"])
    response.headers["X-RateLimit-Remaining"] = str(info["remaining"])
    response.headers["X-RateLimit-Reset"] = str(info["reset"])
    
    return response


# Rate limiting decorator for specific endpoints
def rate_limit(endpoint_type: str = "default"):
    """Decorator for rate limiting specific endpoints."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # This is a simplified version - in practice, you'd need to extract
            # the request from the function args or use FastAPI's dependency injection
            return await func(*args, **kwargs)
        return wrapper
    return decorator
