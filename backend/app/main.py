# ai-report-generator/backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import report_routes
from app.config import settings

app = FastAPI(
    title="AI Report Generator",
    description="Generate professional PDF reports from project descriptions",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(report_routes.router, prefix="/api", tags=["reports"])

@app.get("/")
async def root():
    return {
        "message": "AI Report Generator API",
        "docs": "/docs",
        "version": "1.0.0"
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy"}