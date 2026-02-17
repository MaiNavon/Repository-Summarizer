"""Context management for LLM token limits - optimized for minimal token usage."""

from typing import List, Dict, Any
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
    """Manages content to fit within LLM context limits with maximum efficiency."""
    
    def __init__(self, max_tokens: int = 4000):
        """
        Initialize context manager.
        
        Args:
            max_tokens: Maximum tokens for LLM context (default 4000 for cost efficiency)
        """
        self.max_tokens = max_tokens
        self.reserved_tokens = 800  # Reserve for prompt template and response
    
    def estimate_tokens(self, text: str) -> int:
        """
        Estimates token count for text.
        
        Uses ~4 characters per token as approximation.
        """
        if not text:
            return 0
        return len(text) // 4
    
    def can_add_file(self, current_tokens: int) -> bool:
        """Checks if more content can be added within budget."""
        return current_tokens < (self.max_tokens - self.reserved_tokens)
    
    def truncate_content(self, content: str, max_tokens: int) -> str:
        """Truncates content while preserving structure."""
        if not content:
            return ""
        
        estimated = self.estimate_tokens(content)
        if estimated <= max_tokens:
            return content
        
        char_limit = max_tokens * 4
        truncated = content[:char_limit]
        
        # End at natural boundary
        last_newline = truncated.rfind("\n")
        if last_newline > char_limit * 0.7:
            truncated = truncated[:last_newline]
        
        return truncated + "\n..."
    
    def truncate_readme(self, content: str, max_tokens: int) -> str:
        """
        Smart README truncation - keeps valuable sections, skips noise.
        
        Keeps: Title, description, installation, usage, quick start
        Skips: Badges, contributing, license, detailed API docs
        
        Args:
            content: Full README content
            max_tokens: Maximum tokens to use
            
        Returns:
            Truncated README with high-value sections
        """
        if not content:
            return ""
        
        estimated = self.estimate_tokens(content)
        if estimated <= max_tokens:
            return content
        
        lines = content.split("\n")
        result_lines = []
        current_section = "intro"
        skip_section = False
        
        # Sections to keep (high value)
        keep_sections = {
            "intro", "description", "about", "overview", "what", "why",
            "installation", "install", "setup", "getting started", "quick start",
            "usage", "example", "examples", "how to", "basic usage",
            "features", "highlights", "key features",
            "requirements", "prerequisites", "dependencies",
        }
        
        # Sections to skip (low value for summarization)
        skip_sections = {
            "contributing", "contribute", "contributors", "contribution",
            "license", "licence", "licensing",
            "changelog", "change log", "history", "release",
            "acknowledgments", "acknowledgements", "credits", "thanks",
            "support", "sponsors", "funding", "donate",
            "code of conduct", "security", "vulnerability",
            "api reference", "api documentation", "detailed api",
            "faq", "troubleshooting", "known issues",
            "roadmap", "todo", "future",
            "badge", "badges", "status",
        }
        
        for line in lines:
            stripped = line.strip().lower()
            
            # Skip badge lines (usually at top)
            if stripped.startswith("[![") or stripped.startswith("![") and "badge" in stripped:
                continue
            if "shields.io" in stripped or "badge" in stripped and "http" in stripped:
                continue
            
            # Detect section headers
            if stripped.startswith("#"):
                # Remove # and get section name
                section_name = stripped.lstrip("#").strip()
                
                # Check if we should skip this section
                skip_section = False
                for skip in skip_sections:
                    if skip in section_name:
                        skip_section = True
                        break
                
                if not skip_section:
                    for keep in keep_sections:
                        if keep in section_name:
                            current_section = keep
                            break
            
            # Add line if not in skip section
            if not skip_section:
                result_lines.append(line)
        
        result = "\n".join(result_lines)
        
        # Final truncation if still too long
        if self.estimate_tokens(result) > max_tokens:
            result = self.truncate_content(result, max_tokens)
        
        return result
    
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
        Builds an optimized LLM prompt with prioritized content.
        
        Optimization strategies:
        1. README first (most informative)
        2. Compact directory tree (top-level only)
        3. Pre-detected info reduces LLM work
        4. Minimal file content (truncated)
        5. Clear, concise instructions
        """
        # Sort files by priority - README first
        sorted_files = sorted(files, key=lambda f: f.priority)
        
        # Compact directory tree - only top-level and key directories
        tree_summary = self._build_compact_tree(file_tree)
        
        # Build file contents - heavily truncated
        file_contents = []
        total_content_tokens = 0
        max_content_tokens = self.max_tokens - self.reserved_tokens - 500  # Leave room for structure
        
        for f in sorted_files:
            if total_content_tokens >= max_content_tokens:
                break
            
            # Allocate tokens based on priority
            max_file_tokens = {1: 600, 2: 300, 3: 200, 4: 150, 5: 100, 6: 100}.get(f.priority, 100)
            content = self.truncate_content(f.content, max_file_tokens)
            
            tokens = self.estimate_tokens(content)
            if total_content_tokens + tokens <= max_content_tokens:
                file_contents.append(f"### {f.path}\n```\n{content}\n```")
                total_content_tokens += tokens
        
        # Build detected info - already computed, saves LLM tokens
        langs = ', '.join(detected_languages[:5]) if detected_languages else 'Unknown'
        frameworks = ', '.join(detected_frameworks[:5]) if detected_frameworks else 'None'
        tools = ', '.join(detected_tools[:3]) if detected_tools else 'None'
        
        prompt = f"""Analyze this GitHub repository and return JSON.

## {repo_name}

## Structure
```
{tree_summary}
```

## Pre-detected
- Languages: {langs}
- Frameworks: {frameworks}
- Tools: {tools}
- Layout: {structure_analysis}

## Files
{chr(10).join(file_contents)}

## Output JSON only:
{{"summary": "**Name** does X. It provides Y.", "technologies": ["Lang", "Framework"], "structure": "Source in src/, tests in tests/."}}

Rules:
- summary: 2-3 sentences, start with **ProjectName**
- technologies: 3-6 most important items
- structure: 1 sentence about layout"""

        return prompt
    
    def _build_compact_tree(self, file_tree: List[str]) -> str:
        """Builds a compact directory tree showing only structure."""
        # Get unique top-level items and key subdirectories
        top_level = set()
        key_dirs = set()
        
        for path in file_tree:
            parts = path.split("/")
            if len(parts) == 1:
                top_level.add(parts[0])
            else:
                top_level.add(parts[0] + "/")
                if len(parts) >= 2 and parts[0] in ("src", "lib", "app", "pkg", "cmd"):
                    key_dirs.add(f"  {parts[0]}/{parts[1]}/")
        
        # Build compact tree
        lines = sorted(top_level)[:20]  # Limit top-level items
        if key_dirs:
            lines.extend(sorted(key_dirs)[:10])
        
        tree = "\n".join(lines)
        if len(file_tree) > 30:
            tree += f"\n... ({len(file_tree)} files total)"
        
        return tree
    
    def parse_llm_response(self, response: str) -> Dict[str, Any]:
        """Parses and validates LLM response."""
        if not response:
            raise ValueError("Empty response from LLM")
        
        response = response.strip()
        
        # Extract JSON from various formats
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
        
        # Find JSON object
        if not response.startswith("{"):
            json_start = response.find("{")
            if json_start >= 0:
                json_end = response.rfind("}") + 1
                if json_end > json_start:
                    response = response[json_start:json_end]
        
        try:
            result = json.loads(response)
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}")
            raise ValueError(f"Invalid JSON: {e}")
        
        # Validate and normalize
        required = ["summary", "technologies", "structure"]
        for field in required:
            if field not in result:
                raise ValueError(f"Missing field: {field}")
        
        if not isinstance(result["technologies"], list):
            result["technologies"] = [str(result["technologies"])]
        
        result["summary"] = str(result.get("summary", ""))
        result["structure"] = str(result.get("structure", ""))
        
        return result
