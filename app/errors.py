"""Custom exceptions and error handling for the GitHub Repository Summarizer."""

from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class GitHubError(Exception):
    """Base exception for GitHub-related errors."""
    status_code = 502
    message = "GitHub API error"


class RepoNotFoundError(GitHubError):
    """Repository not found."""
    status_code = 404
    message = "Repository not found"


class RepoAccessDeniedError(GitHubError):
    """Repository is private or access denied."""
    status_code = 403
    message = "Repository is private or access denied"


class RateLimitError(GitHubError):
    """GitHub API rate limit exceeded."""
    status_code = 429
    message = "GitHub API rate limit exceeded. Please try again later."


class EmptyRepoError(GitHubError):
    """Repository is empty."""
    status_code = 400
    message = "Repository is empty or has no content"


class LLMError(Exception):
    """Base exception for LLM-related errors."""
    status_code = 502
    message = "LLM service error"


class LLMConfigError(LLMError):
    """LLM configuration error."""
    status_code = 500
    message = "LLM service configuration error"


class LLMResponseError(LLMError):
    """LLM response error."""
    status_code = 502
    message = "Failed to generate summary from LLM"


def create_error_response(message: str) -> Dict[str, Any]:
    """
    Creates standardized error response.
    
    Args:
        message: Error description
        
    Returns:
        Dict with status="error" and message
    """
    logger.error(f"Error response: {message}")
    return {
        "status": "error",
        "message": message
    }
