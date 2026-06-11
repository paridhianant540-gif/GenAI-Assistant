import os
import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from dotenv import load_dotenv

# Load environmental variables first
load_dotenv()

from app.models.db import init_db
from app.routes import auth, chat, health
from app.services.embedding import EmbeddingService
from app.services.vector_store import VectorStore
from app.utils.logger import get_logger

logger = get_logger("main-app")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handles startup event (DB setup, RAG seeding) and shutdown cleanup."""
    logger.info("Starting up TRUEAILAB RAG Assistant backend...")
    
    # 1. Initialize SQLite Database Tables
    init_db()
    
    # 2. Seed Knowledge Base documents from docs.json if database is empty
    try:
        embedding_service = EmbeddingService()
        vector_store = VectorStore(embedding_service)
        
        # Check if we have documents indexed
        docs_file_path = "docs.json"
        if os.path.exists(docs_file_path):
            with open(docs_file_path, "r", encoding="utf-8") as f:
                documents = json.load(f)
                
            indexed_count = 0
            for doc in documents:
                title = doc.get("title")
                content = doc.get("content")
                if title and content:
                    # Index document (vector store skips automatically if title already exists)
                    if not vector_store.check_document_indexed(title):
                        # Verify we have API credentials before trying to embed
                        if (embedding_service.provider == "gemini" and not embedding_service.gemini_key) or \
                           (embedding_service.provider == "openai" and not embedding_service.openai_key):
                            logger.warning(f"Skipping indexing of '{title}' during startup: API keys are not yet configured in .env.")
                            continue
                            
                        vector_store.index_document(title, content)
                        indexed_count += 1
            if indexed_count > 0:
                logger.info(f"Seeded and indexed {indexed_count} new documents from {docs_file_path}.")
        else:
            logger.warning("docs.json file not found! Skipping database seeding.")
    except Exception as e:
        logger.error(f"Failed to complete startup document seeding: {str(e)}")
        
    yield
    logger.info("Shutting down TRUEAILAB RAG Assistant backend...")

# Create FastAPI instance with Lifespan
app = FastAPI(
    title="TRUEAILAB RAG Chat Assistant",
    description="Production-grade GenAI assistant using Retrieval-Augmented Generation.",
    version="1.0.0",
    lifespan=lifespan
)

# CORS Policy configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allow direct local browsing files to connect
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom Validation Exception Handler to return exact required JSON error structure
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    if errors:
        err = errors[0]
        msg = err.get("msg", "Validation error")
        loc = err.get("loc", [])
        field = loc[-1] if loc else "field"
        
        # Clean up Pydantic validation error prefixes
        msg = msg.replace("Value error, ", "")
        
        if "missing" in msg.lower() or "required" in msg.lower():
            error_message = f"{str(field).capitalize()} field is required"
        else:
            error_message = f"{str(field).capitalize()} field: {msg}"
    else:
        error_message = "Invalid request payload"
        
    logger.warning(f"Request payload validation failed: '{error_message}'")
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"error": error_message}
    )

from fastapi.staticfiles import StaticFiles

# Include Routers
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(chat.router)

# Serve the Glassmorphic Frontend statically on the root port
# Enables instant full-stack plug-and-play hosting on Render/Railway
if os.path.exists("frontend"):
    app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
