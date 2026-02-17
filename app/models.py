"""Pydantic models for request/response validation."""

from pydantic import BaseModel, Field, field_validator
from typing import List, Literal


class SummarizeRequest(BaseModel):
    """Request model for the /summarize endpoint."""
    
    github_url: str = Field(
        ..., 
        description="URL of a public GitHub repository",
        examples=["https://github.com/psf/requests"]
    )
    
    @field_validator("github_url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("URL cannot be empty")
        v = v.strip()
        if not v.startswith("https://github.com/"):
            raise ValueError("URL must be a GitHub repository URL starting with https://github.com/")
        return v.rstrip("/")


class SummarizeResponse(BaseModel):
    """Response model for successful summarization."""
    
    summary: str = Field(..., description="Human-readable project description")
    technologies: List[str] = Field(..., description="List of technologies used")
    structure: str = Field(..., description="Brief project structure description")


class ErrorResponse(BaseModel):
    """Response model for errors."""
    
    status: Literal["error"] = "error"
    message: str = Field(..., description="Error description")
