"""
This is the main entry point for the FastAPI application. It sets up the FastAPI instance, configures middleware, and defines the root endpoint. The application is designed to handle user authentication, CORS, and other functionalities as defined in the various modules and configurations.
"""

from fastapi import FastAPI, Depends, HTTPException, status

# Import the CORSMiddleware class from the fastapi.middleware.cors module to handle Cross-Origin Resource Sharing (CORS) in the FastAPI application. This middleware allows the application to accept requests from different origins, which is useful for enabling communication between the frontend and backend of a web application.
from fastapi.middleware.cors import CORSMiddleware

# Import the settings instance from the config module to access the application configuration, such as database connection details, security settings, and CORS allowed origins. The settings instance is created using Pydantic's BaseSettings class, which reads configuration values from environment variables or a .env file.
from app.core.config import settings
from app.api.v1.api import api_router
from app.api.v1.endpoints.docs import setup_secure_docs

# Disable the default public endpoints by setting them to None
app = FastAPI(
    title=settings.APP_TITLE,
    version=settings.APP_VERSION,
    description=settings.APP_DESCRIPTION,
    docs_url=None,  # Disables default insecure /docs
    redoc_url=None,  # Disables default insecure /redoc
    openapi_url=None,  # CRITICAL: Disables default /openapi.json route completely
)

# Add CORS middleware to allow cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOWED_ORIGINS,  # Loads the allowed origins for CORS from the settings instance, which is configured to read from the .env file. This allows the application to accept requests from specified frontend domains.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount the unified API router to your application instance
app.include_router(api_router)

# Load your custom wrapper configurations
setup_secure_docs(app)


@app.get("/")
async def root_health_check():
    """Simple root endpoint for AWS ECS Load Balancer health checking."""
    return {"status": "healthy", "service": "dataceum-pass"}
