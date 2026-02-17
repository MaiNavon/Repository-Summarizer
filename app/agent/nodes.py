"""Agent workflow nodes for LangGraph."""

import logging
from typing import Dict, Any
from app.agent.state import AgentState
from app.tools.context_manager import FileContent, ContextManager
from app.tools.github_fetcher import GitHubFetcher
from app.tools.file_analyzer import FileAnalyzer
from app.llm.client import get_llm_client
from app.errors import LLMResponseError

logger = logging.getLogger(__name__)


async def fetch_repo_structure(state: AgentState) -> Dict[str, Any]:
    """
    Fetches repository file tree and priority files.
    
    Priority order:
    1. README files
    2. Package configs (package.json, pyproject.toml, etc.)
    3. Entry points (main.py, index.js, etc.)
    4. CI/CD and Docker files
    5. Documentation files
    6. Sample source files (representative samples)
    
    Content selection strategy:
    - Select representative samples when multiple source files exist
    - Prefer smaller, information-dense files over large verbose files
    """
    owner = state["repo_owner"]
    repo = state["repo_name"]
    logger.info(f"Fetching repo structure for {owner}/{repo}")
    
    fetcher = GitHubFetcher()
    context_mgr = ContextManager(max_tokens=state["max_tokens"])
    
    try:
        # Get file tree (only on first iteration)
        if not state["file_tree"]:
            file_tree = await fetcher.get_file_tree(owner, repo)
            state["file_tree"] = file_tree
        
        # Fetch priority files within token budget
        files_to_fetch = fetcher.get_priority_files(state["file_tree"])
        fetched_files = list(state["fetched_files"])  # Copy existing
        seen_paths = {f.path for f in fetched_files}
        
        for file_path, priority in files_to_fetch:
            if file_path in seen_paths:
                continue
            
            if not context_mgr.can_add_file(state["total_tokens"]):
                logger.info("Token budget reached, stopping file fetch")
                break
            
            content = await fetcher.get_file_content(owner, repo, file_path)
            if content:
                token_count = context_mgr.estimate_tokens(content)
                
                # Skip very large files
                if token_count > 2000:
                    logger.debug(f"Skipping large file {file_path} ({token_count} tokens)")
                    continue
                
                fetched_files.append(FileContent(
                    path=file_path,
                    content=content,
                    priority=priority,
                    token_count=token_count
                ))
                state["total_tokens"] += token_count
                seen_paths.add(file_path)
                logger.debug(f"Fetched {file_path} ({token_count} tokens)")
        
        state["fetched_files"] = fetched_files
        state["iteration_count"] += 1
        
        logger.info(f"Fetched {len(fetched_files)} files, total tokens: {state['total_tokens']}")
        
    except Exception as e:
        logger.error(f"Error fetching repo structure: {e}")
        state["error"] = str(e)
        raise
    finally:
        await fetcher.close()
    
    return state


async def analyze_files(state: AgentState) -> Dict[str, Any]:
    """
    Analyzes fetched files for technologies and structure.
    Determines if more context is needed.
    """
    logger.info("Analyzing fetched files")
    
    analyzer = FileAnalyzer()
    
    # Detect languages from file extensions
    languages = analyzer.detect_languages(state["file_tree"])
    state["detected_languages"] = languages
    
    # Detect frameworks and tools from config files
    config_files = {
        f.path: f.content 
        for f in state["fetched_files"] 
        if f.priority <= 2  # README and config files
    }
    
    frameworks = analyzer.detect_frameworks(config_files)
    tools = analyzer.detect_tools(state["file_tree"], config_files)
    
    state["detected_frameworks"] = frameworks
    state["detected_tools"] = tools
    
    # Analyze structure
    state["structure_analysis"] = analyzer.analyze_structure(state["file_tree"])
    
    # Check if we have enough context
    has_readme = any(
        f.path.lower().startswith("readme") or "/readme" in f.path.lower()
        for f in state["fetched_files"]
    )
    has_config = any(f.priority == 2 for f in state["fetched_files"])
    has_enough_files = len(state["fetched_files"]) >= 3
    
    # We need more context if we don't have README or config and haven't maxed iterations
    state["needs_more_context"] = (
        not (has_readme or has_config or has_enough_files) 
        and state["iteration_count"] < state["max_iterations"]
    )
    
    logger.info(
        f"Analysis complete. Languages: {languages}, "
        f"Frameworks: {frameworks}, needs_more: {state['needs_more_context']}"
    )
    
    return state


async def generate_summary(state: AgentState) -> Dict[str, Any]:
    """
    Generates final summary using LLM.
    
    The LLM reasons about:
    - Which technologies are most relevant based on file contents
    - How to describe the project structure clearly
    - What the project does based on README and code analysis
    
    Uses structured prompt with examples for consistent output.
    """
    logger.info("Generating summary with LLM")
    
    llm = get_llm_client()
    context_mgr = ContextManager(max_tokens=state["max_tokens"])
    
    # Build prompt with prioritized content
    prompt = context_mgr.build_summary_prompt(
        repo_name=f"{state['repo_owner']}/{state['repo_name']}",
        file_tree=state["file_tree"],
        files=state["fetched_files"],
        detected_languages=state["detected_languages"],
        detected_frameworks=state["detected_frameworks"],
        detected_tools=state["detected_tools"],
        structure_analysis=state["structure_analysis"]
    )
    
    try:
        response = await llm.ainvoke(prompt)
        result = context_mgr.parse_llm_response(response.content)
        
        state["final_summary"] = result["summary"]
        state["final_technologies"] = result["technologies"]
        state["final_structure"] = result["structure"]
        state["error"] = None
        
        logger.info("Summary generated successfully")
        
    except ValueError as e:
        logger.error(f"Failed to parse LLM response: {e}")
        state["error"] = str(e)
    except Exception as e:
        logger.error(f"LLM error: {e}")
        state["error"] = f"LLM error: {str(e)}"
    
    return state


async def validate_response(state: AgentState) -> Dict[str, Any]:
    """
    Validates the LLM response matches expected schema.
    Deduplicates and sorts technologies.
    """
    if state.get("error"):
        logger.warning(f"Validation skipped due to error: {state['error']}")
        return state
    
    # Validate required fields
    if not state.get("final_summary"):
        state["error"] = "Missing summary in response"
        return state
    
    if not state.get("final_technologies"):
        state["error"] = "Missing technologies in response"
        return state
    
    if not state.get("final_structure"):
        state["error"] = "Missing structure in response"
        return state
    
    # Deduplicate and sort technologies (case-insensitive)
    technologies = state["final_technologies"]
    seen = set()
    unique_techs = []
    for tech in technologies:
        tech_lower = tech.lower()
        if tech_lower not in seen:
            seen.add(tech_lower)
            unique_techs.append(tech)
    
    unique_techs.sort(key=str.lower)
    state["final_technologies"] = unique_techs
    
    logger.info("Response validation passed")
    return state
