"""Nebius Token Factory LLM client."""

import os
from functools import lru_cache
import logging
from langchain_openai import ChatOpenAI
from app.errors import LLMConfigError

logger = logging.getLogger(__name__)


@lru_cache()
def get_llm_client() -> ChatOpenAI:
    """
    Creates LLM client configured for Nebius Token Factory.
    
    Uses Meta-Llama-3.1-70B-Instruct by default for:
    - Strong instruction following
    - Good JSON output formatting
    - Large context window
    - Cost-effective for this use case
    
    Returns:
        Configured ChatOpenAI client
        
    Raises:
        LLMConfigError: If NEBIUS_API_KEY is not set
    """
    api_key = os.environ.get("NEBIUS_API_KEY")
    if not api_key:
        logger.error("NEBIUS_API_KEY environment variable not set")
        raise LLMConfigError("NEBIUS_API_KEY environment variable not set")
    
    model = os.environ.get("NEBIUS_MODEL", "meta-llama/Meta-Llama-3.1-70B-Instruct")
    
    logger.info(f"Initializing LLM client with model: {model}")
    
    return ChatOpenAI(
        base_url="https://api.studio.nebius.com/v1/",
        api_key=api_key,
        model=model,
        temperature=0.3,  # Lower temperature for more consistent output
        max_tokens=2000,  # Sufficient for summary response
        timeout=60,       # 60 second timeout
    )


def clear_llm_cache() -> None:
    """Clears the cached LLM client (useful for testing)."""
    get_llm_client.cache_clear()
