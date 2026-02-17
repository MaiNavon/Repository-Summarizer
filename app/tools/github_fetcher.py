"""GitHub API client for fetching repository contents."""

import httpx
import base64
from typing import List, Tuple, Optional, Set
import logging
from app.errors import RepoNotFoundError, RepoAccessDeniedError, RateLimitError, EmptyRepoError

logger = logging.getLogger(__name__)


class GitHubFetcher:
    """Fetches repository contents from GitHub API."""
    
    BASE_URL = "https://api.github.com"
    
    EXCLUDED_DIRS: Set[str] = {
        "node_modules", ".git", "__pycache__", "venv", ".venv",
        "dist", "build", "target", "vendor", ".idea", ".vscode",
        "coverage", ".nyc_output", ".pytest_cache", ".mypy_cache",
        ".tox", ".eggs", ".cache", ".tmp", "env", ".env",
        "site-packages", "bower_components", ".gradle", ".mvn"
    }
    
    EXCLUDED_EXTENSIONS: Set[str] = {
        # Binary
        ".exe", ".dll", ".so", ".dylib", ".pyc", ".pyo", ".class", ".jar", ".war",
        # Archives
        ".zip", ".tar", ".gz", ".rar", ".7z", ".bz2", ".xz",
        # Images
        ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".webp", ".bmp", ".tiff",
        # Documents
        ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
        # Media
        ".mp3", ".mp4", ".wav", ".avi", ".mov", ".mkv", ".flv",
        # Fonts
        ".woff", ".woff2", ".ttf", ".eot", ".otf",
        # Data
        ".sqlite", ".db", ".pickle", ".pkl", ".bin", ".dat",
        # Other
        ".min.js", ".min.css", ".map"
    }
    
    LOCK_FILES: Set[str] = {
        "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
        "Pipfile.lock", "poetry.lock", "Cargo.lock", "go.sum",
        "composer.lock", "Gemfile.lock", "shrinkwrap.yaml",
        "bun.lockb", "flake.lock"
    }
    
    # Priority levels: 1=highest (README), 5=lowest (source files)
    PRIORITY_FILES = {
        1: ["README.md", "README.rst", "README.txt", "README", "readme.md"],
        2: [
            "package.json", "pyproject.toml", "setup.py", "setup.cfg",
            "Cargo.toml", "go.mod", "pom.xml", "build.gradle", "build.gradle.kts",
            "composer.json", "Gemfile", "requirements.txt", "environment.yml"
        ],
        3: [
            "main.py", "app.py", "index.js", "index.ts", "main.go",
            "main.rs", "src/main.py", "src/index.js", "src/index.ts",
            "src/lib.rs", "src/main.rs", "lib/index.js", "app/main.py"
        ],
        4: [
            ".github/workflows/ci.yml", ".github/workflows/main.yml",
            ".github/workflows/test.yml", ".github/workflows/build.yml",
            ".gitlab-ci.yml", "Jenkinsfile", "Dockerfile",
            "docker-compose.yml", "docker-compose.yaml", ".dockerignore"
        ],
        5: ["CONTRIBUTING.md", "CHANGELOG.md", "docs/index.md", "docs/README.md"]
    }
    
    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Gets or creates the HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                headers={"Accept": "application/vnd.github.v3+json"}
            )
        return self._client
    
    async def close(self) -> None:
        """Closes the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def get_file_tree(self, owner: str, repo: str) -> List[str]:
        """
        Fetches the complete file tree of a repository.
        
        Args:
            owner: Repository owner
            repo: Repository name
            
        Returns:
            List of file paths (filtered)
            
        Raises:
            RepoNotFoundError: If repository doesn't exist
            RepoAccessDeniedError: If repository is private
            RateLimitError: If GitHub rate limit exceeded
            EmptyRepoError: If repository is empty
        """
        client = await self._get_client()
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/git/trees/HEAD?recursive=1"
        
        try:
            response = await client.get(url)
            
            if response.status_code == 404:
                raise RepoNotFoundError(f"Repository {owner}/{repo} not found")
            elif response.status_code == 403:
                if "rate limit" in response.text.lower():
                    raise RateLimitError()
                raise RepoAccessDeniedError(f"Access denied to {owner}/{repo}")
            elif response.status_code == 409:
                # Empty repository
                raise EmptyRepoError(f"Repository {owner}/{repo} is empty")
            
            response.raise_for_status()
            data = response.json()
            
            if data.get("truncated"):
                logger.warning(f"File tree for {owner}/{repo} was truncated by GitHub API")
            
            files = []
            for item in data.get("tree", []):
                if item["type"] == "blob":
                    path = item["path"]
                    if not self.should_skip_path(path):
                        files.append(path)
            
            if not files:
                raise EmptyRepoError(f"Repository {owner}/{repo} has no processable files")
            
            logger.info(f"Found {len(files)} files in {owner}/{repo}")
            return files
            
        except httpx.HTTPStatusError as e:
            logger.error(f"GitHub API error: {e}")
            raise
    
    async def get_file_content(self, owner: str, repo: str, path: str) -> Optional[str]:
        """
        Fetches content of a specific file.
        
        Args:
            owner: Repository owner
            repo: Repository name
            path: File path within repository
            
        Returns:
            File content as string, or None if fetch failed
        """
        client = await self._get_client()
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/contents/{path}"
        
        try:
            response = await client.get(url)
            
            if response.status_code == 404:
                logger.warning(f"File not found: {path}")
                return None
            elif response.status_code == 403:
                if "rate limit" in response.text.lower():
                    raise RateLimitError()
                logger.warning(f"Access denied to file: {path}")
                return None
            
            response.raise_for_status()
            data = response.json()
            
            # Handle file too large (GitHub returns download_url instead)
            if data.get("size", 0) > 1_000_000:  # 1MB limit
                logger.warning(f"File too large, skipping: {path}")
                return None
            
            if data.get("encoding") == "base64" and data.get("content"):
                content = base64.b64decode(data["content"]).decode("utf-8", errors="replace")
                return content
                
        except httpx.HTTPStatusError as e:
            logger.warning(f"Failed to fetch {path}: {e}")
        except UnicodeDecodeError:
            logger.warning(f"Failed to decode {path} as UTF-8")
        except Exception as e:
            logger.warning(f"Error fetching {path}: {e}")
        
        return None
    
    def should_skip_path(self, path: str) -> bool:
        """
        Determines if a path should be skipped.
        
        Args:
            path: File path to check
            
        Returns:
            True if path should be skipped
        """
        parts = path.split("/")
        filename = parts[-1]
        
        # Check excluded directories
        for part in parts[:-1]:
            if part in self.EXCLUDED_DIRS:
                return True
            # Also check for patterns like *.egg-info
            if part.endswith(".egg-info"):
                return True
        
        # Check lock files
        if filename in self.LOCK_FILES:
            return True
        
        # Check excluded extensions
        for ext in self.EXCLUDED_EXTENSIONS:
            if path.lower().endswith(ext):
                return True
        
        return False
    
    def get_priority_files(self, file_tree: List[str]) -> List[Tuple[str, int]]:
        """
        Returns files sorted by priority.
        
        Args:
            file_tree: List of file paths
            
        Returns:
            List of (path, priority) tuples, sorted by priority
        """
        result = []
        seen = set()
        
        # First, find priority files
        for priority, patterns in self.PRIORITY_FILES.items():
            for pattern in patterns:
                pattern_lower = pattern.lower()
                for file_path in file_tree:
                    file_lower = file_path.lower()
                    # Match exact path or path ending with /pattern
                    if file_lower == pattern_lower or file_lower.endswith(f"/{pattern_lower}"):
                        if file_path not in seen:
                            result.append((file_path, priority))
                            seen.add(file_path)
        
        # Add some source files at lowest priority (6) for additional context
        source_extensions = {".py", ".js", ".ts", ".go", ".rs", ".java", ".rb"}
        source_count = 0
        max_source_files = 5
        
        for file_path in file_tree:
            if source_count >= max_source_files:
                break
            if file_path not in seen:
                for ext in source_extensions:
                    if file_path.endswith(ext):
                        result.append((file_path, 6))
                        seen.add(file_path)
                        source_count += 1
                        break
        
        # Sort by priority
        result.sort(key=lambda x: x[1])
        return result
