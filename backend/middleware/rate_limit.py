"""
Rate limiting middleware for paper processing.

Limits: 3 papers per IP per 24 hours on the /api/process endpoint.
"""

import time
from collections import defaultdict
from fastapi import HTTPException, Request
from typing import Dict, Tuple


# In-memory rate limiting storage
# Format: {ip: (count, reset_timestamp)}
_rate_storage: Dict[str, Tuple[int, float]] = {}

# Configuration
MAX_REQUESTS = 3
WINDOW_SECONDS = 24 * 60 * 60  # 24 hours


def get_client_ip(request: Request) -> str:
    """Extract client IP from request, handling proxies."""
    # Check for forwarded header (behind proxy)
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    
    # Check for real IP header
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip
    
    # Fall back to direct client
    if request.client:
        return request.client.host
    
    return "unknown"


def check_rate_limit(request: Request) -> None:
    """
    Check and update rate limit for client.
    
    Raises HTTPException(429) if limit exceeded.
    """
    ip = get_client_ip(request)
    current_time = time.time()
    
    # Clean up expired entries periodically
    if len(_rate_storage) > 10000:
        expired = [k for k, v in _rate_storage.items() if v[1] < current_time]
        for k in expired:
            del _rate_storage[k]
    
    # Check existing entry
    if ip in _rate_storage:
        count, reset_time = _rate_storage[ip]
        
        # Check if within window
        if current_time < reset_time:
            if count >= MAX_REQUESTS:
                remaining_time = int(reset_time - current_time)
                hours = remaining_time // 3600
                minutes = (remaining_time % 3600) // 60
                
                raise HTTPException(
                    status_code=429,
                    detail={
                        "error": "Rate limit exceeded",
                        "message": f"You can process {MAX_REQUESTS} papers per 24 hours. Try again in {hours}h {minutes}m.",
                        "reset_at": reset_time,
                        "retry_after": remaining_time,
                    }
                )
            else:
                # Increment count, keep same reset time
                _rate_storage[ip] = (count + 1, reset_time)
        else:
            # Window expired, reset
            _rate_storage[ip] = (1, current_time + WINDOW_SECONDS)
    else:
        # New entry
        _rate_storage[ip] = (1, current_time + WINDOW_SECONDS)


def get_rate_limit_status(request: Request) -> dict:
    """Get current rate limit status for client."""
    ip = get_client_ip(request)
    current_time = time.time()
    
    if ip in _rate_storage:
        count, reset_time = _rate_storage[ip]
        if current_time < reset_time:
            remaining = MAX_REQUESTS - count
            return {
                "allowed": remaining > 0,
                "count": count,
                "limit": MAX_REQUESTS,
                "reset_at": reset_time,
                "remaining_requests": max(0, remaining),
            }
    
    return {
        "allowed": True,
        "count": 0,
        "limit": MAX_REQUESTS,
        "reset_at": None,
        "remaining_requests": MAX_REQUESTS,
    }