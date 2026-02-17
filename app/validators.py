"""URL validation for GitHub repository URLs."""

from dataclasses import dataclass
import re


@dataclass
class RepoInfo:
    """Information extracted from a GitHub repository URL."""
    owner: str
    repo: str


def validate_github_url(url: str) -> RepoInfo:
    """
    Validates GitHub URL and extracts owner/repo.
    
    Args:
        url: GitHub repository URL
        
    Returns:
        RepoInfo with owner and repo name
        
    Raises:
        ValueError: For invalid URLs
    """
    if not url:
        raise ValueError("URL cannot be empty")
    
    # Normalize URL - remove trailing slashes and .git suffix
    url = url.rstrip("/")
    if url.endswith(".git"):
        url = url[:-4]
    
    # Pattern for GitHub repository URLs
    pattern = r"^https://github\.com/([a-zA-Z0-9][-a-zA-Z0-9]*)/([a-zA-Z0-9._-]+)$"
    match = re.match(pattern, url)
    
    if not match:
        raise ValueError("Invalid GitHub repository URL format. Expected: https://github.com/{owner}/{repo}")
    
    owner = match.group(1)
    repo = match.group(2)
    
    # Additional validation
    if owner.startswith("-") or repo.startswith("-"):
        raise ValueError("Invalid GitHub repository URL format")
    
    return RepoInfo(owner=owner, repo=repo)
