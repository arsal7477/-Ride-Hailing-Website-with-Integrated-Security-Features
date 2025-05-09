import os
from functools import wraps
from flask import request, abort
import logging
from datetime import datetime, timedelta

class SecurityConfig:
    # Security headers middleware
    @staticmethod
    def apply_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:;"
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        return response

    # CSRF protection
    @staticmethod
    def csrf_protect(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if request.method == "POST":
                csrf_token = session.get('csrf_token')
                if not csrf_token or csrf_token != request.form.get('csrf_token'):
                    logging.warning(f"CSRF validation failed for {request.endpoint}")
                    abort(403)
            return f(*args, **kwargs)
        return decorated_function

    # Input validation
    @staticmethod
    def sanitize_input(data):
        if isinstance(data, str):
            # Remove potentially harmful characters
            data = data.replace('<', '&lt;').replace('>', '&gt;')
            data = data.replace("'", "''").replace('"', '&quot;')
            # Prevent SQL injection
            data = data.replace(';', '').replace('--', '')
        return data

    # Password policy
    @staticmethod
    def validate_password(password):
        if len(password) < 12:
            return False, "Password must be at least 12 characters long"
        if not any(char.isdigit() for char in password):
            return False, "Password must contain at least one number"
        if not any(char.isupper() for char in password):
            return False, "Password must contain at least one uppercase letter"
        if not any(char.islower() for char in password):
            return False, "Password must contain at least one lowercase letter"
        if not any(char in '!@#$%^&*()' for char in password):
            return False, "Password must contain at least one special character"
        return True, ""

    # Session security
    @staticmethod
    def secure_session(session):
        session.permanent = False
        session.modified = True

    # Rate limiting
    @staticmethod
    def rate_limit(key_func=None, limit=100, interval=60):
        def decorator(f):
            @wraps(f)
            def decorated_function(*args, **kwargs):
                # Implement Redis or database-backed rate limiting here
                pass
            return decorated_function
        return decorator