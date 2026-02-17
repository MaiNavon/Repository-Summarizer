"""LangGraph workflow for repository summarization."""

import logging
from typing import Dict, Any
from langgraph.graph import StateGraph, END
from app.agent.state import AgentState, create_initial_state
from app.agent.nodes import (
    fetch_repo_structure,
    analyze_files,
    generate_summary,
    validate_response
)
from app.errors import LLMResponseError

logger = logging.getLogger(__name__)


def should_fetch_more(state: AgentState) -> str:
    """
    Conditional edge: decides if more files needed.
    
    Returns:
        "fetch_more" if more context needed, "generate" otherwise
    """
    if state.get("error"):
        return "generate"  # Skip to generate to handle error
    
    if state["needs_more_context"] and state["iteration_count"] < state["max_iterations"]:
        logger.debug("Need more context, fetching more files")
        return "fetch_more"
    
    return "generate"


def should_retry_summary(state: AgentState) -> str:
    """
    Conditional edge: decides if summary needs retry.
    
    Returns:
        "retry" if should retry, "end" otherwise
    """
    if state.get("error") and state["iteration_count"] < state["max_iterations"]:
        logger.info(f"Retrying summary due to error: {state['error']}")
        state["iteration_count"] += 1
        state["error"] = None  # Clear error for retry
        return "retry"
    
    return "end"


def create_summarizer_graph() -> StateGraph:
    """
    Creates the LangGraph workflow for repository summarization.
    
    Workflow:
    1. fetch_repo_structure: Fetch file tree and priority files
    2. analyze_files: Detect technologies and analyze structure
    3. (conditional) fetch_more or generate_summary
    4. generate_summary: Call LLM to generate summary
    5. validate_response: Validate and clean up response
    6. (conditional) retry or end
    
    Returns:
        Compiled StateGraph
    """
    graph = StateGraph(AgentState)
    
    # Add nodes
    graph.add_node("fetch_repo_structure", fetch_repo_structure)
    graph.add_node("analyze_files", analyze_files)
    graph.add_node("generate_summary", generate_summary)
    graph.add_node("validate_response", validate_response)
    
    # Set entry point
    graph.set_entry_point("fetch_repo_structure")
    
    # Add edges
    graph.add_edge("fetch_repo_structure", "analyze_files")
    
    # Conditional: need more files or proceed to summary
    graph.add_conditional_edges(
        "analyze_files",
        should_fetch_more,
        {
            "fetch_more": "fetch_repo_structure",
            "generate": "generate_summary"
        }
    )
    
    graph.add_edge("generate_summary", "validate_response")
    
    # Conditional: retry summary or end
    graph.add_conditional_edges(
        "validate_response",
        should_retry_summary,
        {
            "retry": "generate_summary",
            "end": END
        }
    )
    
    return graph.compile()


async def run_summarizer_agent(owner: str, repo: str, max_tokens: int = 8000) -> Dict[str, Any]:
    """
    Run the summarizer agent for a repository.
    
    Args:
        owner: Repository owner
        repo: Repository name
        max_tokens: Maximum tokens for context
        
    Returns:
        Dict with final_summary, final_technologies, final_structure, or error
        
    Raises:
        Various exceptions from GitHub API or LLM
    """
    logger.info(f"Starting summarizer agent for {owner}/{repo}")
    
    graph = create_summarizer_graph()
    initial_state = create_initial_state(owner, repo, max_tokens)
    
    result = await graph.ainvoke(initial_state)
    
    if result.get("error"):
        logger.error(f"Agent completed with error: {result['error']}")
        raise LLMResponseError(result["error"])
    
    logger.info(f"Agent completed successfully for {owner}/{repo}")
    
    return {
        "summary": result["final_summary"],
        "technologies": result["final_technologies"],
        "structure": result["final_structure"]
    }
