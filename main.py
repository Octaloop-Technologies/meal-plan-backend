"""
FastAPI main application
"""
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.middleware.base import BaseHTTPMiddleware
from contextlib import asynccontextmanager
from config import settings
from routes import api_router
from database import init_db
import traceback
import re


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize MongoDB
    try:
        await init_db()
        print("[INFO] MongoDB connection established")
    except Exception as e:
        print(f"[WARNING] MongoDB connection failed: {str(e)}")
        print("[WARNING] Server will start but database operations may fail")
        if settings.DEBUG:
            import traceback
            traceback.print_exc()
    yield
    # Shutdown: Cleanup if needed
    pass


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan
)

# CORS middleware - MUST be added before routes
# Allow localhost for development, ngrok URLs, and Shopify domains for production
# Support multiple clients: frontend, admin, and any configured origins
cors_origins = [
    "http://localhost:3000",  # Frontend (default Next.js port)
    "http://localhost:3001",  # Admin (alternative port)
    "http://localhost:3002",  # Additional client port
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3001",
    "http://127.0.0.1:3002",
    "https://inaudible-luise-noninverted.ngrok-free.dev",
] + settings.allowed_origins_list

# In development mode, allow all localhost origins
if settings.DEBUG:
    cors_origin_regex = r"http://localhost:\d+|http://127\.0\.0\.1:\d+|https://.*\.ngrok-free\.dev|https://.*\.ngrok\.io"
    # In debug mode, also allow all origins for easier development
    cors_origins.append("*")
else:
    cors_origin_regex = r"https://.*\.ngrok-free\.dev|https://.*\.ngrok\.io"

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,  # Specific origins list
    allow_origin_regex=cors_origin_regex,  # Regex for localhost and ngrok in dev mode
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,  # Cache preflight requests for 1 hour
)

# CORS logging middleware for debugging (after CORS middleware)
class CORSLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if settings.DEBUG and request.method == "OPTIONS":
            origin = request.headers.get("origin", "None")
            print(f"[CORS] Preflight request from origin: {origin}")
        response = await call_next(request)
        if settings.DEBUG:
            origin = request.headers.get("origin", "None")
            cors_header = response.headers.get("access-control-allow-origin", "None")
            print(f"[CORS] Request from {origin} -> Allowed: {cors_header}")
        return response

if settings.DEBUG:
    app.add_middleware(CORSLoggingMiddleware)

# Exception handlers to ensure CORS headers are sent even on errors
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle all exceptions and ensure CORS headers are included"""
    error_detail = str(exc)
    if settings.DEBUG:
        traceback_str = traceback.format_exc()
        print(f"[ERROR] Unhandled exception: {error_detail}")
        print(f"[ERROR] Traceback: {traceback_str}")
    
    # Get origin from request for CORS
    origin = request.headers.get("origin", "*")
    # In development, allow all localhost origins
    if settings.DEBUG:
        is_allowed_origin = (
            origin in cors_origins or 
            re.match(r"https://.*\.ngrok-free\.dev", origin) or 
            re.match(r"https://.*\.ngrok\.io", origin) or
            re.match(r"http://localhost:\d+", origin) or
            re.match(r"http://127\.0\.0\.1:\d+", origin)
        )
    else:
        is_allowed_origin = (
            origin in cors_origins or 
            re.match(r"https://.*\.ngrok-free\.dev", origin) or 
            re.match(r"https://.*\.ngrok\.io", origin)
        )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": error_detail if settings.DEBUG else "Internal server error",
            "type": type(exc).__name__
        },
        headers={
            "Access-Control-Allow-Origin": origin if is_allowed_origin else "*",
            "Access-Control-Allow-Methods": "*",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Allow-Credentials": "true",
        }
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors with CORS headers"""
    origin = request.headers.get("origin", "*")
    # In development, allow all localhost origins
    if settings.DEBUG:
        is_allowed_origin = (
            origin in cors_origins or 
            re.match(r"https://.*\.ngrok-free\.dev", origin) or 
            re.match(r"https://.*\.ngrok\.io", origin) or
            re.match(r"http://localhost:\d+", origin) or
            re.match(r"http://127\.0\.0\.1:\d+", origin)
        )
    else:
        is_allowed_origin = (
            origin in cors_origins or 
            re.match(r"https://.*\.ngrok-free\.dev", origin) or 
            re.match(r"https://.*\.ngrok\.io", origin)
        )
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors()},
        headers={
            "Access-Control-Allow-Origin": origin if is_allowed_origin else "*",
            "Access-Control-Allow-Methods": "*",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Allow-Credentials": "true",
        }
    )

# Include API routes
app.include_router(api_router, prefix="")


@app.get("/")
async def root():
    return {
        "message": "Custom Shopify Meal Plan API",
        "version": settings.APP_VERSION,
        "status": "running",
        "database": "MongoDB"
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.options("/{full_path:path}")
async def options_handler(full_path: str, request: Request):
    """Handle OPTIONS requests for CORS preflight - fallback handler"""
    origin = request.headers.get("origin", "*")
    # In debug mode, allow all origins
    if settings.DEBUG:
        allowed_origin = origin if origin != "*" else "*"
    else:
        # In production, check if origin is allowed
        allowed_origin = origin if (
            origin.startswith("http://localhost") or 
            origin.startswith("http://127.0.0.1") or 
            "ngrok" in origin or
            origin.endswith(".myshopify.com")
        ) else "*"
    
    return JSONResponse(
        content={},
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": allowed_origin,
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS, PATCH, HEAD",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Max-Age": "3600",
        }
    )
