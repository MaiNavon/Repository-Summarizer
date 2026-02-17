"""Tests for URL validation."""

import pytest
from hypothesis import given, strategies as st, settings
from app.validators import validate_github_url, RepoInfo


class TestValidateGitHubUrl:
    """Unit tests for validate_github_url."""
    
    def test_valid_simple_url(self):
        """Test valid simple GitHub URL."""
        result = validate_github_url("https://github.com/psf/requests")
        assert result.owner == "psf"
        assert result.repo == "requests"
    
    def test_valid_url_with_trailing_slash(self):
        """Test URL with trailing slash."""
        result = validate_github_url("https://github.com/psf/requests/")
        assert result.owner == "psf"
        assert result.repo == "requests"
    
    def test_valid_url_with_git_suffix(self):
        """Test URL with .git suffix."""
        result = validate_github_url("https://github.com/psf/requests.git")
        assert result.owner == "psf"
        assert result.repo == "requests"
    
    def test_valid_url_with_numbers(self):
        """Test URL with numbers in owner/repo."""
        result = validate_github_url("https://github.com/user123/repo456")
        assert result.owner == "user123"
        assert result.repo == "repo456"
    
    def test_valid_url_with_hyphens(self):
        """Test URL with hyphens."""
        result = validate_github_url("https://github.com/my-org/my-repo")
        assert result.owner == "my-org"
        assert result.repo == "my-repo"
    
    def test_valid_url_with_underscores(self):
        """Test URL with underscores in repo."""
        result = validate_github_url("https://github.com/owner/my_repo")
        assert result.owner == "owner"
        assert result.repo == "my_repo"
    
    def test_valid_url_with_dots(self):
        """Test URL with dots in repo name."""
        result = validate_github_url("https://github.com/owner/repo.js")
        assert result.owner == "owner"
        assert result.repo == "repo.js"
    
    def test_invalid_empty_url(self):
        """Test empty URL."""
        with pytest.raises(ValueError, match="cannot be empty"):
            validate_github_url("")
    
    def test_invalid_none_url(self):
        """Test None URL."""
        with pytest.raises(ValueError):
            validate_github_url(None)
    
    def test_invalid_http_url(self):
        """Test HTTP (not HTTPS) URL."""
        with pytest.raises(ValueError, match="Invalid GitHub"):
            validate_github_url("http://github.com/owner/repo")
    
    def test_invalid_wrong_domain(self):
        """Test wrong domain."""
        with pytest.raises(ValueError, match="Invalid GitHub"):
            validate_github_url("https://gitlab.com/owner/repo")
    
    def test_invalid_missing_repo(self):
        """Test URL missing repo."""
        with pytest.raises(ValueError, match="Invalid GitHub"):
            validate_github_url("https://github.com/owner")
    
    def test_invalid_missing_owner(self):
        """Test URL missing owner."""
        with pytest.raises(ValueError, match="Invalid GitHub"):
            validate_github_url("https://github.com//repo")
    
    def test_invalid_extra_path(self):
        """Test URL with extra path segments."""
        with pytest.raises(ValueError, match="Invalid GitHub"):
            validate_github_url("https://github.com/owner/repo/tree/main")
    
    def test_invalid_owner_starts_with_hyphen(self):
        """Test owner starting with hyphen."""
        with pytest.raises(ValueError, match="Invalid GitHub"):
            validate_github_url("https://github.com/-owner/repo")


class TestValidateGitHubUrlProperties:
    """Property-based tests for URL validation."""
    
    @given(
        owner=st.from_regex(r"[a-zA-Z][a-zA-Z0-9-]{0,38}", fullmatch=True),
        repo=st.from_regex(r"[a-zA-Z0-9][a-zA-Z0-9._-]{0,99}", fullmatch=True)
    )
    @settings(max_examples=100)
    def test_property_valid_urls_accepted(self, owner: str, repo: str):
        """Property 1: Valid GitHub URLs are accepted."""
        # Skip if owner ends with hyphen (GitHub doesn't allow)
        if owner.endswith("-"):
            return
        
        url = f"https://github.com/{owner}/{repo}"
        result = validate_github_url(url)
        
        assert isinstance(result, RepoInfo)
        assert result.owner == owner
        assert result.repo == repo
    
    @given(url=st.text(min_size=0, max_size=200))
    @settings(max_examples=100)
    def test_property_invalid_urls_raise_error(self, url: str):
        """Property 2: Invalid URLs return appropriate errors."""
        # Skip if it happens to be a valid GitHub URL
        if url.startswith("https://github.com/") and url.count("/") == 4:
            parts = url.replace("https://github.com/", "").split("/")
            if len(parts) == 2 and all(parts):
                return
        
        # Most random strings should fail validation
        try:
            validate_github_url(url)
            # If it didn't raise, it must be a valid-looking URL
            assert url.startswith("https://github.com/")
        except (ValueError, TypeError):
            pass  # Expected for invalid URLs
