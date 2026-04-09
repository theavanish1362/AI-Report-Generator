# ai-report-generator/backend/run.py
#!/usr/bin/env python
"""
Script to run the FastAPI application.
"""
import uvicorn
import os
from app.config import settings

if __name__ == "__main__":
    # Create necessary directories
    os.makedirs(settings.OUTPUT_DIR, exist_ok=True)
    os.makedirs(settings.CHARTS_DIR, exist_ok=True)
    
    # Run the application with extended timeouts for long AI generation
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level="info",
        timeout_keep_alive=600,
        timeout_graceful_shutdown=600
    )