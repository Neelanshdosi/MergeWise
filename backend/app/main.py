import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .logging_config import setup_logging
from .routers.auth import auth_router
from .routers.recommendations import router as recommendations_router

# Initialize sensitive-token-redacting logger
logger = setup_logging()

app = FastAPI(
    title="MergeWise / OSS Match Agent API",
    description="Personalized open-source issue recommender backend",
    version="0.1.0",
)

# Strictly restrict CORS to configured frontend origins
allowed_origins = settings.get_allowed_origins()
logger.info(f"Configuring CORS for allowed origins: {allowed_origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "Origin", "User-Agent"],
)

# Register routers
app.include_router(auth_router)
app.include_router(recommendations_router)


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint for Cloud Run container probes."""
    return {
        "status": "healthy",
        "service": "mergewise-backend",
        "environment": settings.ENVIRONMENT,
        "gemini_model_id": settings.GEMINI_MODEL_ID,
    }


@app.get("/", tags=["Root"])
async def root():
    return {
        "name": "MergeWise API",
        "docs_url": "/docs",
        "health_url": "/health",
    }
