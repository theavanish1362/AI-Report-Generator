# ai-report-generator/backend/app/models/report_schema.py
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any

class ReportRequest(BaseModel):
    """
    Request model for report generation.
    """
    title: str = Field(..., min_length=1, max_length=200, description="Project title")
    project_type: str = Field(..., description="Type of project: academic or industrial")
    description: str = Field(..., min_length=10, max_length=5000, description="Detailed project description")
    pages: int = Field(15, ge=5, le=30, description="Approximate number of pages to generate (5-30)")
    
    @validator('project_type')
    def validate_project_type(cls, v):
        if v.lower() not in ['academic', 'industrial']:
            raise ValueError('project_type must be either "academic" or "industrial"')
        return v.lower()

class ReportResponse(BaseModel):
    """
    Response model for report generation.
    """
    success: bool = Field(..., description="Whether report generation succeeded")
    message: str = Field(..., description="Status message")
    pdf_path: Optional[str] = Field(None, description="Path to generated PDF file")
    report_id: Optional[str] = Field(None, description="Unique report identifier")
    error_details: Optional[str] = Field(None, description="Error details if generation failed")

class ChartData(BaseModel):
    """
    Model for chart data.
    """
    type: str = Field(..., description="Chart type: bar, line, pie")
    title: str = Field(..., description="Chart title")
    data: Dict[str, Any] = Field(..., description="Chart data")
    
    @validator('type')
    def validate_chart_type(cls, v):
        if v not in ['bar', 'line', 'pie', 'scatter']:
            raise ValueError('Unsupported chart type')
        return v

class ReportContent(BaseModel):
    """
    Complete report content model.
    """
    title: str
    project_type: str
    abstract: str
    introduction: str
    problem_statement: str
    objectives: List[str]
    methodology: str
    tools_technologies: List[str]
    system_architecture: str
    implementation: str
    results_analysis: str
    conclusion: str
    future_scope: str
    charts_needed: List[ChartData] = []
