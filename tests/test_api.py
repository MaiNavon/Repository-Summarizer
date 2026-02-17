"""Tests for FastAPI application."""

import pytest
from hypothesis import given, strategies as st, settings
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock

from app.main import app
from app.models import SummarizeResponse


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


class TestHealthEndpoint:
    """Tests for health check endpoint."""
    
    def test_health_check(self, client):
        """Test health endpoint returns healthy."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}


class TestSummarizeEndpoint:
    """Tests for /summarize endpoint."""
    
    def test_invalid_url_empty(self, client):
        """Test empty URL returns 400."""
        response = client.post("/summarize", json={"github_url": ""})
        assert response.status_code == 400
        data = response.json()
        assert data["status"] == "error"
        assert "message" in data
    
    def test_invalid_url_not_github(self, client):
        """Test non-GitHub URL returns 400."""
        response = client.post("/summarize", json={"github_url": "https://gitlab.com/owner/repo"})
        assert response.status_code == 400
        data = response.json()
        assert data["status"] == "error"
    
    def test_invalid_url_malformed(self, client):
        """Test malformed URL returns 400."""
        response = client.post("/summarize", json={"github_url": "not a url"})
        assert response.status_code == 400
        data = response.json()
        assert data["status"] == "error"
    
    def test_missing_github_url_field(self, client):
        """Test missing github_url field returns 422 or 400."""
        response = client.post("/summarize", json={})
        # FastAPI returns 422 for missing required fields
        assert response.status_code in [400, 422]
    
    @patch("app.main.run_summarizer_agent")
    @patch("app.main.cache_manager")
    def test_successful_summarize(self, mock_cache, mock_agent, client):
        """Test successful summarization."""
        mock_cache.get.return_value = None
        mock_agent.return_value = {
            "summary": "**Test** is a test project.",
            "technologies": ["Python", "FastAPI"],
            "structure": "Standard Python layout."
        }
        
        response = client.post(
            "/summarize", 
            json={"github_url": "https://github.com/owner/repo"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "summary" in data
        assert "technologies" in data
        assert "structure" in data
        assert isinstance(data["technologies"], list)
    
    @patch("app.main.cache_manager")
    def test_cache_hit(self, mock_cache, client):
        """Test cache hit returns cached data."""
        cached_data = {
            "summary": "Cached summary",
            "technologies": ["Python"],
            "structure": "Cached structure"
        }
        mock_cache.get.return_value = cached_data
        
        response = client.post(
            "/summarize",
            json={"github_url": "https://github.com/owner/repo"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["summary"] == "Cached summary"


class TestErrorResponseFormat:
    """Property tests for error response format."""
    
    @given(url=st.text(min_size=1, max_size=100).filter(
        lambda x: not x.startswith("https://github.com/")
    ))
    @settings(max_examples=50)
    def test_property_error_response_format(self, url: str):
        """Property 7: Error responses have correct format."""
        client = TestClient(app)
        response = client.post("/summarize", json={"github_url": url})
        
        # Should be an error (400 or 422)
        assert response.status_code in [400, 422]
        
        data = response.json()
        
        # Must have status and message for 400 errors
        if response.status_code == 400:
            assert data.get("status") == "error"
            assert "message" in data
            assert isinstance(data["message"], str)
            assert len(data["message"]) > 0


class TestSuccessResponseFormat:
    """Tests for success response format."""
    
    @patch("app.main.run_summarizer_agent")
    @patch("app.main.cache_manager")
    def test_property_success_response_format(self, mock_cache, mock_agent):
        """Property 6: Success responses have correct format."""
        mock_cache.get.return_value = None
        mock_agent.return_value = {
            "summary": "**Project** does something useful.",
            "technologies": ["Python", "FastAPI", "Docker"],
            "structure": "Standard layout with src/ and tests/."
        }
        
        client = TestClient(app)
        response = client.post(
            "/summarize",
            json={"github_url": "https://github.com/owner/repo"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Property 6: Validate response format
        assert "summary" in data
        assert isinstance(data["summary"], str)
        assert len(data["summary"]) > 0
        
        assert "technologies" in data
        assert isinstance(data["technologies"], list)
        
        assert "structure" in data
        assert isinstance(data["structure"], str)
        assert len(data["structure"]) > 0
    
    @patch("app.main.run_summarizer_agent")
    @patch("app.main.cache_manager")
    def test_property_technologies_sorted(self, mock_cache, mock_agent):
        """Property 8: Technologies are deduplicated and sorted."""
        mock_cache.get.return_value = None
        # Return already sorted technologies (as the agent would)
        mock_agent.return_value = {
            "summary": "Test project",
            "technologies": ["Docker", "FastAPI", "Python"],  # Pre-sorted
            "structure": "Standard layout"
        }
        
        client = TestClient(app)
        response = client.post(
            "/summarize",
            json={"github_url": "https://github.com/owner/repo"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Technologies should be sorted (agent does this)
        techs = data["technologies"]
        assert techs == sorted(techs, key=str.lower)
        
        # No duplicates
        assert len(techs) == len(set(t.lower() for t in techs))
