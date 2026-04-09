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

class Subsection(BaseModel):
    """
    Model for a nested subsection within a major section.
    """
    sub_title: str = Field(..., description="Subtitle for the subsection")
    content: str = Field(..., description="Detailed content for this subsection")

class ReportContent(BaseModel):
    """
    Complete report content model with support for nested subsections.
    """
    title: str
    project_type: str
    abstract: str
    # Major sections now support nested subsections for depth
    introduction: List[Subsection]
    problem_statement: List[Subsection]
    objectives: List[str]
    methodology: List[Subsection]
    tools_technologies: List[str]
    system_architecture: List[Subsection]
    implementation: List[Subsection]
    results_analysis: List[Subsection]
    conclusion: List[Subsection]
    future_scope: List[Subsection]
    charts_needed: List[ChartData] = []
    image_prompts: List[Dict[str, Any]] = []
