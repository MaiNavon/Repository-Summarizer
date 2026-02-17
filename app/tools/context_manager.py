"""Context management for LLM token limits."""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import json
import logging

logger = logging.getLogger(__name__)


@dataclass
class FileContent:
    """Represents fetched file content with metadata."""
    path: str
    content: str
    priority: int  # 1=highest (README), 6=lowest (source files)
    token_count: int


class ContextManager:
    """Manages content to fit within LLM context limits."""
    
    def __init__(self, max_tokens: int = 8000):
        """
        Initialize context manager.
        
        Args:
            max_tokens: Maximum tokens for LLM context
        """
        self.max_tokens = max_tokens
        self.reserved_tokens = 1500  # Reserve for prompt template and response
    
    def estimate_tokens(self, text: str) -> int:
        """
        Estimates token count for text (rough approximation).
        
        Uses ~4 characters per token as a conservative estimate.
        
        Args:
            text: Text to estimate
            
        Returns:
            Estimated token count
        """
        if not text:
            return 0
        return len(text) // 4
    
    def can_add_file(self, current_tokens: int) -> bool:
        """
        Checks if more content can be added.
        
        Args:
            current_tokens: Current total token count
            
        Returns:
            True if more content can be added
        """
        return current_tokens < (self.max_tokens - self.reserved_tokens)
    
    def truncate_content(self, content: str, max_tokens: int) -> str:
        """
        Truncates content while preserving structure.
        
        Tries to end at natural boundaries (newlines).
        
        Args:
            content: Content to truncate
            max_tokens: Maximum tokens allowed
            
        Returns:
            Truncated content with indicator if truncated
        """
        if not content:
            return ""
        
        estimated = self.estimate_tokens(content)
        if estimated <= max_tokens:
            return content
        
        # Truncate to approximate token limit
        char_limit = max_tokens * 4
        truncated = content[:char_limit]
        
        # Try to end at a natural boundary (newline)
        last_newline = truncated.rfind("\n")
        if last_newline > char_limit * 0.7:  # Only if we keep at least 70%
            truncated = truncated[:last_newline]
        
        return truncated + "\n... [truncated]"

    def build_summary_prompt(
        self,
        repo_name: str,
        file_tree: List[str],
        files: List[FileContent],
        detected_languages: List[str],
        detected_frameworks: List[str],
        detected_tools: List[str],
        structure_analysis: str
    ) -> str:
        """
        Builds the LLM prompt with prioritized content.
        
        Places high-priority content (README, key findings) at the beginning
        of the prompt to leverage LLM attention patterns.
        
        Args:
            repo_name: Repository name (owner/repo)
            file_tree: List of all file paths
            files: List of fetched file contents
            detected_languages: Detected programming languages
            detected_frameworks: Detected frameworks
            detected_tools: Detected tools
            structure_analysis: Structure description
            
        Returns:
            Formatted prompt string
        """
        # Sort files by priority (highest first) - README comes first
        sorted_files = sorted(files, key=lambda f: f.priority)
        
        # Build file tree summary (truncated if needed)
        tree_lines = file_tree[:100]
        tree_summary = "\n".join(tree_lines)
        if len(file_tree) > 100:
            tree_summary += f"\n... and {len(file_tree) - 100} more files"
        
        # Build file contents section with truncation
        file_contents = []
        for f in sorted_files:
            # Truncate individual files to reasonable size
            content = self.truncate_content(f.content, 500)
            file_contents.append(f"### {f.path}\n```\n{content}\n```")
        
        # Build detected info strings
        languages_str = ', '.join(detected_languages) if detected_languages else 'Unknown'
        frameworks_str = ', '.join(detected_frameworks) if detected_frameworks else 'None detected'
        tools_str = ', '.join(detected_tools) if detected_tools else 'None detected'
        
        prompt = f"""Analyze this GitHub repository and provide a structured summary.

## Repository: {repo_name}

## Directory Structure
```
{tree_summary}
```

## Detected Information
- Languages: {languages_str}
- Frameworks: {frameworks_str}
- Tools: {tools_str}
- Structure: {structure_analysis}

## Key Files
{chr(10).join(file_contents)}

## Instructions
Based on the above information, provide a JSON response with exactly these fields:

1. "summary": A human-readable description of what this project does (2-4 sentences). Start with the project name in bold using markdown (**ProjectName**).
2. "technologies": An array of the main technologies, languages, and frameworks used. Include only the most important ones (typically 3-8 items).
3. "structure": A brief description of how the project is organized (1-2 sentences).

## Important Notes
- If the README is missing or unclear, infer the project purpose from the code and config files.
- For technologies, prioritize: main programming language, key frameworks, databases, and major tools.
- For structure, describe the main directories and their purposes.

## Example Response Format
```json
{{
  "summary": "**ProjectName** is a Python library that does X. It provides Y functionality and is commonly used for Z.",
  "technologies": ["Python", "FastAPI", "PostgreSQL"],
  "structure": "The project follows a standard Python package layout with source code in `src/`, tests in `tests/`, and documentation in `docs/`."
}}
```

Respond ONLY with valid JSON, no additional text before or after the JSON object."""

        return prompt
    
    def parse_llm_response(self, response: str) -> Dict[str, Any]:
        """
        Parses and validates LLM response.
        
        Handles markdown code blocks and validates required fields.
        
        Args:
            response: Raw LLM response string
            
        Returns:
            Parsed dict with summary, technologies, structure
            
        Raises:
            ValueError: If response is invalid or missing required fields
        """
        if not response:
            raise ValueError("Empty response from LLM")
        
        response = response.strip()
        
        # Handle markdown code blocks
        if "```json" in response:
            start = response.find("```json") + 7
            end = response.find("```", start)
            if end > start:
                response = response[start:end].strip()
        elif "```" in response:
            start = response.find("```") + 3
            end = response.find("```", start)
            if end > start:
                response = response[start:end].strip()
        
        # Try to find JSON object if there's extra text
        if not response.startswith("{"):
            json_start = response.find("{")
            if json_start >= 0:
                json_end = response.rfind("}") + 1
                if json_end > json_start:
                    response = response[json_start:json_end]
        
        try:
            result = json.loads(response)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            logger.debug(f"Response was: {response[:500]}")
            raise ValueError(f"Invalid JSON response from LLM: {e}")
        
        # Validate required fields
        required = ["summary", "technologies", "structure"]
        for field in required:
            if field not in result:
                raise ValueError(f"Missing required field in LLM response: {field}")
        
        # Ensure technologies is a list
        if not isinstance(result["technologies"], list):
            if isinstance(result["technologies"], str):
                result["technologies"] = [result["technologies"]]
            else:
                result["technologies"] = []
        
        # Ensure summary and structure are strings
        if not isinstance(result["summary"], str):
            result["summary"] = str(result["summary"])
        if not isinstance(result["structure"], str):
            result["structure"] = str(result["structure"])
        
        return result
