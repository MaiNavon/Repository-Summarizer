"""Agent workflow nodes for LangGraph - optimized for efficiency."""

import logging
from typing import Dict, Any
from app.agent.state import AgentState
from app.tools.context_manager import FileContent, ContextManager
from app.tools.github_fetcher import GitHubFetcher
from app.tools.file_analyzer import FileAnalyzer
from app.llm.client import get_llm_client

logger = logging.getLogger(__name__)


async def fetch_repo_structure(state: AgentState) -> Dict[str, Any]:
    """
    Fetches repository file tree and priority files.
    
    Optimizations:
    - Single API call for file tree
    - Parallel file fetching
    - Smart file selection by priority
    - Entry point detection (LARCH heuristics)
    - Dependency extraction for config files
    - Function signature extraction for source files
    - Smart README truncation
    - Strict token budgeting
    """
    owner = state["repo_owner"]
    repo = state["repo_name"]
    logger.info(f"Fetching repo: {owner}/{repo}")
    
    fetcher = GitHubFetcher()
    context_mgr = ContextManager(max_tokens=state["max_tokens"])
    
    try:
        # Get file tree (single API call)
        if not state["file_tree"]:
            file_tree = await fetcher.get_file_tree(owner, repo)
            state["file_tree"] = file_tree
        
        # Get priority files to fetch
        files_to_fetch = fetcher.get_priority_files(state["file_tree"])
        
        # Limit files based on token budget
        max_files = 10  # Reasonable limit
        files_to_fetch = files_to_fetch[:max_files]
        
        # Fetch files in parallel
        fetched = await fetcher.get_files_parallel(owner, repo, files_to_fetch)
        
        # Process fetched files with optimizations
        fetched_files = []
        total_tokens = 0
        entry_point_scores = []
        
        for path, content, priority in fetched:
            original_content = content
            
            # Apply content optimization based on file type
            if priority == 1:  # README
                # Smart README truncation - keep valuable sections
                content = context_mgr.truncate_readme(content, 600)
                logger.debug(f"README truncated: {len(original_content)} -> {len(content)} chars")
            
            elif priority == 2:  # Config files
                # Extract dependencies only
                content = fetcher.extract_dependencies_only(content, path)
            
            elif priority in (3, 6):  # Entry points and source files
                # Score entry point likelihood
                score = fetcher.score_entry_point(original_content, path, repo)
                entry_point_scores.append((path, score))
                
                # Extract function signatures and docstrings
                content = fetcher.extract_signatures_and_docstrings(original_content, path)
                logger.debug(f"Signatures extracted from {path}: {len(original_content)} -> {len(content)} chars")
            
            token_count = context_mgr.estimate_tokens(content)
            
            # Check token budget
            if not context_mgr.can_add_file(total_tokens):
                logger.info(f"Token budget reached at {total_tokens} tokens")
                break
            
            fetched_files.append(FileContent(
                path=path,
                content=content,
                priority=priority,
                token_count=token_count
            ))
            total_tokens += token_count
        
        # Log entry point detection results
        if entry_point_scores:
            entry_point_scores.sort(key=lambda x: x[1], reverse=True)
            best_entry = entry_point_scores[0]
            logger.info(f"Best entry point candidate: {best_entry[0]} (score: {best_entry[1]})")
        
        state["fetched_files"] = fetched_files
        state["total_tokens"] = total_tokens
        state["iteration_count"] += 1
        
        logger.info(f"Fetched {len(fetched_files)} files, {total_tokens} tokens (optimized)")
        
    except Exception as e:
        logger.error(f"Fetch error: {e}")
        state["error"] = str(e)
        raise
    finally:
        await fetcher.close()
    
    return state


async def analyze_files(state: AgentState) -> Dict[str, Any]:
    """
    Analyzes fetched files for technologies and structure.
    
    Pre-computes information to reduce LLM workload.
    """
    logger.info("Analyzing files")
    
    analyzer = FileAnalyzer()
    
    # Detect languages from file extensions
    state["detected_languages"] = analyzer.detect_languages(state["file_tree"])
    
    # Detect frameworks from config files
    config_files = {
        f.path: f.content 
        for f in state["fetched_files"] 
        if f.priority <= 2
    }
    
    state["detected_frameworks"] = analyzer.detect_frameworks(config_files)
    state["detected_tools"] = analyzer.detect_tools(state["file_tree"], config_files)
    state["structure_analysis"] = analyzer.analyze_structure(state["file_tree"])
    
    # Check if we have enough context
    has_readme = any("readme" in f.path.lower() for f in state["fetched_files"])
    has_config = any(f.priority == 2 for f in state["fetched_files"])
    
    state["needs_more_context"] = (
        not (has_readme or has_config) 
        and state["iteration_count"] < state["max_iterations"]
    )
    
    logger.info(f"Languages: {state['detected_languages']}, Frameworks: {state['detected_frameworks']}")
    
    return state


async def generate_summary(state: AgentState) -> Dict[str, Any]:
    """
    Generates summary using LLM with optimized prompt.
    """
    logger.info("Generating summary")
    
    llm = get_llm_client()
    context_mgr = ContextManager(max_tokens=state["max_tokens"])
    
    # Build optimized prompt
    prompt = context_mgr.build_summary_prompt(
        repo_name=f"{state['repo_owner']}/{state['repo_name']}",
        file_tree=state["file_tree"],
        files=state["fetched_files"],
        detected_languages=state["detected_languages"],
        detected_frameworks=state["detected_frameworks"],
        detected_tools=state["detected_tools"],
        structure_analysis=state["structure_analysis"]
    )
    
    logger.debug(f"Prompt tokens: ~{context_mgr.estimate_tokens(prompt)}")
    
    try:
        response = await llm.ainvoke(prompt)
        result = context_mgr.parse_llm_response(response.content)
        
        state["final_summary"] = result["summary"]
        state["final_technologies"] = result["technologies"]
        state["final_structure"] = result["structure"]
        state["error"] = None
        
        logger.info("Summary generated")
        
    except ValueError as e:
        logger.error(f"Parse error: {e}")
        state["error"] = str(e)
    except Exception as e:
        logger.error(f"LLM error: {e}")
        state["error"] = f"LLM error: {e}"
    
    return state


async def validate_response(state: AgentState) -> Dict[str, Any]:
    """
    Validates and cleans up the LLM response.
    """
    if state.get("error"):
        return state
    
    # Validate required fields
    if not state.get("final_summary"):
        state["error"] = "Missing summary"
        return state
    if not state.get("final_technologies"):
        state["error"] = "Missing technologies"
        return state
    if not state.get("final_structure"):
        state["error"] = "Missing structure"
        return state
    
    # Deduplicate and sort technologies
    techs = state["final_technologies"]
    seen = set()
    unique = []
    for t in techs:
        t_lower = t.lower()
        if t_lower not in seen:
            seen.add(t_lower)
            unique.append(t)
    
    unique.sort(key=str.lower)
    state["final_technologies"] = unique
    
    logger.info("Validation passed")
    return state
