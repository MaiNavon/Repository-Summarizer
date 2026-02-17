"""FastAPI application for GitHub Repository Summarizer."""

import time
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from app.logging_config import setup_logging, get_logger
from app.models import SummarizeRequest, SummarizeResponse, ErrorResponse
from app.validators import validate_github_url, RepoInfo
from app.cache import cache_manager
from app.agent.graph import run_summarizer_agent
from app.errors import (
    GitHubError, RepoNotFoundError, RepoAccessDeniedError, 
    RateLimitError, EmptyRepoError, LLMError, LLMConfigError, 
    LLMResponseError, create_error_response
)

# Setup logging on module load
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info("Starting GitHub Repository Summarizer API")
    yield
    logger.info("Shutting down GitHub Repository Summarizer API")
    cache_manager.clear()


app = FastAPI(
    title="GitHub Repository Summarizer",
    description="API service that summarizes GitHub repositories using LLM",
    version="1.0.0",
    lifespan=lifespan
)


# Exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle Pydantic validation errors."""
    errors = exc.errors()
    if errors:
        message = errors[0].get("msg", "Validation error")
    else:
        message = "Invalid request"
    
    logger.warning(f"Validation error: {message}")
    return JSONResponse(
        status_code=400,
        content=create_error_response(message)
    )


@app.exception_handler(RepoNotFoundError)
async def repo_not_found_handler(request: Request, exc: RepoNotFoundError):
    """Handle repository not found errors."""
    return JSONResponse(
        status_code=404,
        content=create_error_response(str(exc) or exc.message)
    )


@app.exception_handler(RepoAccessDeniedError)
async def repo_access_denied_handler(request: Request, exc: RepoAccessDeniedError):
    """Handle repository access denied errors."""
    return JSONResponse(
        status_code=403,
        content=create_error_response(str(exc) or exc.message)
    )


@app.exception_handler(RateLimitError)
async def rate_limit_handler(request: Request, exc: RateLimitError):
    """Handle GitHub rate limit errors."""
    return JSONResponse(
        status_code=429,
        content=create_error_response(exc.message)
    )


@app.exception_handler(EmptyRepoError)
async def empty_repo_handler(request: Request, exc: EmptyRepoError):
    """Handle empty repository errors."""
    return JSONResponse(
        status_code=400,
        content=create_error_response(str(exc) or exc.message)
    )


@app.exception_handler(LLMConfigError)
async def llm_config_handler(request: Request, exc: LLMConfigError):
    """Handle LLM configuration errors."""
    return JSONResponse(
        status_code=500,
        content=create_error_response(exc.message)
    )


@app.exception_handler(LLMResponseError)
async def llm_response_handler(request: Request, exc: LLMResponseError):
    """Handle LLM response errors."""
    return JSONResponse(
        status_code=502,
        content=create_error_response(str(exc) or exc.message)
    )


@app.exception_handler(GitHubError)
async def github_error_handler(request: Request, exc: GitHubError):
    """Handle generic GitHub errors."""
    return JSONResponse(
        status_code=exc.status_code,
        content=create_error_response(str(exc) or exc.message)
    )


@app.exception_handler(LLMError)
async def llm_error_handler(request: Request, exc: LLMError):
    """Handle generic LLM errors."""
    return JSONResponse(
        status_code=exc.status_code,
        content=create_error_response(str(exc) or exc.message)
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Handle unexpected errors."""
    logger.exception(f"Unexpected error: {exc}")
    return JSONResponse(
        status_code=500,
        content=create_error_response("An unexpected error occurred")
    )


@app.post(
    "/summarize",
    response_model=SummarizeResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid URL or empty repository"},
        403: {"model": ErrorResponse, "description": "Repository is private"},
        404: {"model": ErrorResponse, "description": "Repository not found"},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
        500: {"model": ErrorResponse, "description": "Server configuration error"},
        502: {"model": ErrorResponse, "description": "External service error"},
    }
)
async def summarize(request: SummarizeRequest) -> SummarizeResponse:
    """
    Summarize a GitHub repository.
    
    Accepts a GitHub repository URL, fetches the repository contents,
    and returns a summary generated by an LLM.
    """
    start_time = time.time()
    github_url = request.github_url
    
    logger.info(f"Received summarize request for: {github_url}")
    
    # Validate URL and extract owner/repo
    try:
        repo_info: RepoInfo = validate_github_url(github_url)
    except ValueError as e:
        logger.warning(f"Invalid URL: {github_url} - {e}")
        raise HTTPException(status_code=400, detail=str(e))
    
    owner = repo_info.owner
    repo = repo_info.repo
    
    # Check cache
    cached = cache_manager.get(owner, repo)
    if cached:
        duration = time.time() - start_time
        logger.info(f"Returning cached result for {owner}/{repo} in {duration:.2f}s")
        return SummarizeResponse(**cached)
    
    # Run agent
    logger.info(f"Running summarizer agent for {owner}/{repo}")
    agent_start = time.time()
    
    result = await run_summarizer_agent(owner, repo)
    
    agent_duration = time.time() - agent_start
    logger.info(f"Agent completed in {agent_duration:.2f}s")
    
    # Cache result
    cache_manager.set(owner, repo, result)
    
    total_duration = time.time() - start_time
    logger.info(f"Request completed for {owner}/{repo} in {total_duration:.2f}s")
    
    return SummarizeResponse(**result)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
