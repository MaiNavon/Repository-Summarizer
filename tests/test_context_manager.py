"""Tests for context manager."""

import pytest
from hypothesis import given, strategies as st, settings
from app.tools.context_manager import ContextManager, FileContent


class TestEstimateTokens:
    """Tests for token estimation."""
    
    @pytest.fixture
    def ctx(self):
        return ContextManager(max_tokens=8000)
    
    def test_empty_string(self, ctx):
        """Test empty string returns 0."""
        assert ctx.estimate_tokens("") == 0
    
    def test_short_string(self, ctx):
        """Test short string estimation."""
        # 12 characters / 4 = 3 tokens
        assert ctx.estimate_tokens("Hello World!") == 3
    
    def test_longer_string(self, ctx):
        """Test longer string estimation."""
        text = "a" * 400  # 400 chars / 4 = 100 tokens
        assert ctx.estimate_tokens(text) == 100
    
    @given(text=st.text(min_size=0, max_size=10000))
    @settings(max_examples=100)
    def test_property_estimation_consistency(self, text: str):
        """Property 5: Token estimation is deterministic."""
        ctx = ContextManager()
        result1 = ctx.estimate_tokens(text)
        result2 = ctx.estimate_tokens(text)
        assert result1 == result2
    
    @given(text=st.text(min_size=1, max_size=10000))
    @settings(max_examples=100)
    def test_property_estimation_non_negative(self, text: str):
        """Token estimation is always non-negative."""
        ctx = ContextManager()
        assert ctx.estimate_tokens(text) >= 0


class TestCanAddFile:
    """Tests for can_add_file."""
    
    def test_can_add_when_under_limit(self):
        """Test can add when under limit."""
        ctx = ContextManager(max_tokens=8000)
        assert ctx.can_add_file(1000) is True
    
    def test_cannot_add_when_at_limit(self):
        """Test cannot add when at limit."""
        ctx = ContextManager(max_tokens=8000)
        # 8000 - 1500 reserved = 6500 available
        assert ctx.can_add_file(6500) is False
    
    def test_cannot_add_when_over_limit(self):
        """Test cannot add when over limit."""
        ctx = ContextManager(max_tokens=8000)
        assert ctx.can_add_file(7000) is False
    
    @given(
        max_tokens=st.integers(min_value=2000, max_value=100000),
        current_tokens=st.integers(min_value=0, max_value=100000)
    )
    @settings(max_examples=100)
    def test_property_context_within_limits(self, max_tokens: int, current_tokens: int):
        """Property 4: Context management respects token limits."""
        ctx = ContextManager(max_tokens=max_tokens)
        can_add = ctx.can_add_file(current_tokens)
        
        if can_add:
            # If we can add, current must be under the available budget
            assert current_tokens < (max_tokens - ctx.reserved_tokens)


class TestTruncateContent:
    """Tests for content truncation."""
    
    @pytest.fixture
    def ctx(self):
        return ContextManager()
    
    def test_no_truncation_needed(self, ctx):
        """Test content under limit is not truncated."""
        content = "Short content"
        result = ctx.truncate_content(content, 100)
        assert result == content
        assert "[truncated]" not in result
    
    def test_truncation_adds_indicator(self, ctx):
        """Test truncated content has indicator."""
        content = "a" * 1000
        result = ctx.truncate_content(content, 50)
        assert "[truncated]" in result
    
    def test_truncation_respects_limit(self, ctx):
        """Test truncated content is within limit."""
        content = "a" * 10000
        max_tokens = 100
        result = ctx.truncate_content(content, max_tokens)
        
        # Result should be roughly within limit (with some buffer for indicator)
        assert len(result) < (max_tokens * 4) + 50
    
    @given(
        content=st.text(min_size=100, max_size=10000),
        max_tokens=st.integers(min_value=10, max_value=500)
    )
    @settings(max_examples=100)
    def test_property_truncation_within_limit(self, content: str, max_tokens: int):
        """Property 11: Content truncation respects limits."""
        ctx = ContextManager()
        result = ctx.truncate_content(content, max_tokens)
        
        # Result should be shorter than or equal to max length (with buffer)
        max_chars = max_tokens * 4 + 50  # Buffer for truncation indicator
        assert len(result) <= max_chars


class TestParseLlmResponse:
    """Tests for LLM response parsing."""
    
    @pytest.fixture
    def ctx(self):
        return ContextManager()
    
    def test_parse_valid_json(self, ctx):
        """Test parsing valid JSON response."""
        response = '{"summary": "Test", "technologies": ["Python"], "structure": "Simple"}'
        result = ctx.parse_llm_response(response)
        
        assert result["summary"] == "Test"
        assert result["technologies"] == ["Python"]
        assert result["structure"] == "Simple"
    
    def test_parse_json_in_code_block(self, ctx):
        """Test parsing JSON in markdown code block."""
        response = '''```json
{"summary": "Test", "technologies": ["Python"], "structure": "Simple"}
```'''
        result = ctx.parse_llm_response(response)
        assert result["summary"] == "Test"
    
    def test_parse_json_in_plain_code_block(self, ctx):
        """Test parsing JSON in plain code block."""
        response = '''```
{"summary": "Test", "technologies": ["Python"], "structure": "Simple"}
```'''
        result = ctx.parse_llm_response(response)
        assert result["summary"] == "Test"
    
    def test_parse_converts_string_technologies(self, ctx):
        """Test technologies string is converted to list."""
        response = '{"summary": "Test", "technologies": "Python", "structure": "Simple"}'
        result = ctx.parse_llm_response(response)
        assert result["technologies"] == ["Python"]
    
    def test_parse_missing_field_raises(self, ctx):
        """Test missing required field raises error."""
        response = '{"summary": "Test", "technologies": ["Python"]}'
        with pytest.raises(ValueError, match="Missing required field"):
            ctx.parse_llm_response(response)
    
    def test_parse_invalid_json_raises(self, ctx):
        """Test invalid JSON raises error."""
        response = "not valid json"
        with pytest.raises(ValueError, match="Invalid JSON"):
            ctx.parse_llm_response(response)
    
    def test_parse_empty_response_raises(self, ctx):
        """Test empty response raises error."""
        with pytest.raises(ValueError, match="Empty response"):
            ctx.parse_llm_response("")
