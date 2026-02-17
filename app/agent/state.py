"""Agent state definition for LangGraph workflow."""

from typing import TypedDict, Optional, List
from app.tools.context_manager import FileContent


class AgentState(TypedDict):
    """State that flows through the LangGraph workflow."""
    
    # Input
    repo_owner: str
    repo_name: str
    
    # Fetched data
    file_tree: List[str]
    fetched_files: List[FileContent]
    
    # Analysis results
    detected_languages: List[str]
    detected_frameworks: List[str]
    detected_tools: List[str]
    structure_analysis: str
    
    # Control flow
    needs_more_context: bool
    iteration_count: int
    max_iterations: int
    total_tokens: int
    max_tokens: int
    
    # Output
    final_summary: Optional[str]
    final_technologies: Optional[List[str]]
    final_structure: Optional[str]
    
    # Error handling
    error: Optional[str]


def create_initial_state(owner: str, repo: str, max_tokens: int = 8000) -> AgentState:
    """
    Creates initial agent state for a repository.
    
    Args:
        owner: Repository owner
        repo: Repository name
        max_tokens: Maximum tokens for context
        
    Returns:
        Initialized AgentState
    """
    return AgentState(
        repo_owner=owner,
        repo_name=repo,
        file_tree=[],
        fetched_files=[],
        detected_languages=[],
        detected_frameworks=[],
        detected_tools=[],
        structure_analysis="",
        needs_more_context=True,
        iteration_count=0,
        max_iterations=3,
        total_tokens=0,
        max_tokens=max_tokens,
        final_summary=None,
        final_technologies=None,
        final_structure=None,
        error=None
    )
