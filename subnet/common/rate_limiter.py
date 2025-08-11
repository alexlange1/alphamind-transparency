#!/usr/bin/env python3
"""
Rate limiting utilities for API endpoints
"""
import time
import os
from typing import Dict, Tuple
from functools import wraps
from fastapi import HTTPException, Request


class RateLimiter:
    def __init__(self, max_requests: int = 60, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[str, list] = {}
    
    def is_allowed(self, identifier: str) -> bool:
        """Check if request is allowed under rate limit"""
        now = time.time()
        
        # Initialize if first request from this identifier
        if identifier not in self.requests:
            self.requests[identifier] = []
        
        # Clean old requests outside the window
        self.requests[identifier] = [
            req_time for req_time in self.requests[identifier]
            if now - req_time < self.window_seconds
        ]
        
        # Check if we're already at the limit
        if len(self.requests[identifier]) >= self.max_requests:
            return False
        
        # Record this request and allow it
        self.requests[identifier].append(now)
        return True


# Global rate limiters for different endpoint types
_mint_limiter = RateLimiter(
    max_requests=int(os.environ.get("AM_MINT_RATE_LIMIT", "10")),
    window_seconds=int(os.environ.get("AM_MINT_WINDOW_SEC", "300"))  # 10 per 5 minutes
)

_aggregate_limiter = RateLimiter(
    max_requests=int(os.environ.get("AM_AGGREGATE_RATE_LIMIT", "30")),
    window_seconds=int(os.environ.get("AM_AGGREGATE_WINDOW_SEC", "60"))  # 30 per minute
)

_general_limiter = RateLimiter(
    max_requests=int(os.environ.get("AM_GENERAL_RATE_LIMIT", "100")),
    window_seconds=int(os.environ.get("AM_GENERAL_WINDOW_SEC", "60"))  # 100 per minute
)


def get_client_identifier(request: Request) -> str:
    """Extract client identifier from request"""
    # Try to get real IP from headers (for reverse proxy setups)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Take the first IP in the chain
        real_ip = forwarded_for.split(",")[0].strip()
        return real_ip
    
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    
    # Fallback to direct client IP
    if hasattr(request, "client") and request.client:
        return request.client.host
    
    return "unknown"


def rate_limit_mint(func):
    """Decorator for mint endpoints - strict rate limiting"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Extract request from args/kwargs
        request = None
        for arg in args:
            if isinstance(arg, Request):
                request = arg
                break
        for value in kwargs.values():
            if isinstance(value, Request):
                request = value
                break
        
        if request is None:
            raise HTTPException(status_code=500, detail="No request object found")
        
        client_id = get_client_identifier(request)
        
        if not _mint_limiter.is_allowed(client_id):
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded for mint operations",
                headers={"Retry-After": str(_mint_limiter.window_seconds)}
            )
        
        return func(*args, **kwargs)
    return wrapper


def rate_limit_aggregate(func):
    """Decorator for aggregate endpoints - moderate rate limiting"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        request = None
        for arg in args:
            if isinstance(arg, Request):
                request = arg
                break
        for value in kwargs.values():
            if isinstance(value, Request):
                request = value
                break
        
        if request is None:
            raise HTTPException(status_code=500, detail="No request object found")
        
        client_id = get_client_identifier(request)
        
        if not _aggregate_limiter.is_allowed(client_id):
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded for aggregate operations",
                headers={"Retry-After": str(_aggregate_limiter.window_seconds)}
            )
        
        return func(*args, **kwargs)
    return wrapper


def rate_limit_general(func):
    """Decorator for general endpoints - basic rate limiting"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        request = None
        for arg in args:
            if isinstance(arg, Request):
                request = arg
                break
        for value in kwargs.values():
            if isinstance(value, Request):
                request = value
                break
        
        if request is None:
            raise HTTPException(status_code=500, detail="No request object found")
        
        client_id = get_client_identifier(request)
        
        if not _general_limiter.is_allowed(client_id):
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded",
                headers={"Retry-After": str(_general_limiter.window_seconds)}
            )
        
        return func(*args, **kwargs)
    return wrapper
