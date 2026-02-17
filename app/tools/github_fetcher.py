"""GitHub API client for fetching repository contents - optimized for LLM context."""

import httpx
import base64
import asyncio
from typing import List, Tuple, Optional, Set, Dict
import logging
from app.errors import RepoNotFoundError, RepoAccessDeniedError, RateLimitError, EmptyRepoError

logger = logging.getLogger(__name__)


class GitHubFetcher:
    """Fetches repository contents from GitHub API with optimized content selection."""
    
    BASE_URL = "https://api.github.com"
    
    # Directories that never contain useful information for summarization
    EXCLUDED_DIRS: Set[str] = {
        # Package managers
        "node_modules", "bower_components", "jspm_packages",
        # Python
        "__pycache__", "venv", ".venv", "env", ".env", "site-packages",
        ".eggs", ".tox", ".nox", ".mypy_cache", ".pytest_cache", ".ruff_cache",
        # Build outputs
        "dist", "build", "out", "target", "_build", "public/build",
        # IDE/Editor
        ".idea", ".vscode", ".vs", ".eclipse", ".settings",
        # Version control
        ".git", ".svn", ".hg",
        # Coverage/Testing
        "coverage", ".nyc_output", "htmlcov", ".coverage",
        # Misc
        ".cache", ".tmp", "tmp", "temp", ".gradle", ".mvn",
        "vendor", "third_party", "external", "deps",
    }
    
    # Extensions that are binary or not useful for understanding code
    EXCLUDED_EXTENSIONS: Set[str] = {
        # Binary executables
        ".exe", ".dll", ".so", ".dylib", ".a", ".lib", ".o", ".obj",
        ".pyc", ".pyo", ".class", ".jar", ".war", ".ear",
        # Archives
        ".zip", ".tar", ".gz", ".bz2", ".xz", ".rar", ".7z", ".tgz",
        # Images
        ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".webp", 
        ".bmp", ".tiff", ".tif", ".psd", ".ai", ".eps",
        # Documents
        ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".odt",
        # Media
        ".mp3", ".mp4", ".wav", ".avi", ".mov", ".mkv", ".flv", ".wmv",
        ".ogg", ".webm", ".m4a", ".flac",
        # Fonts
        ".woff", ".woff2", ".ttf", ".eot", ".otf",
        # Data files
        ".sqlite", ".db", ".sqlite3", ".pickle", ".pkl", ".bin", ".dat",
        ".parquet", ".feather", ".arrow",
        # Minified/compiled
        ".min.js", ".min.css", ".bundle.js", ".chunk.js",
        ".map", ".d.ts.map",
        # Other
        ".DS_Store", ".ico", ".icns",
    }
    
    # Lock files - large and not informative
    LOCK_FILES: Set[str] = {
        "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "bun.lockb",
        "Pipfile.lock", "poetry.lock", "pdm.lock",
        "Cargo.lock", "go.sum",
        "composer.lock", "Gemfile.lock", "mix.lock",
        "shrinkwrap.yaml", "flake.lock", "pubspec.lock",
    }
    
    # Files to skip even if they match patterns
    SKIP_FILES: Set[str] = {
        ".gitignore", ".gitattributes", ".editorconfig", ".prettierrc",
        ".eslintignore", ".npmignore", ".dockerignore",
        "LICENSE", "LICENSE.md", "LICENSE.txt", "LICENCE",
        "CODEOWNERS", ".mailmap", "SECURITY.md",
    }
    
    # Priority files - ordered by information density for summarization
    # Priority 1: README - most important, contains project description
    # Priority 2: Package configs - dependencies, project metadata
    # Priority 3: Entry points - main application logic
    # Priority 4: Config files - build/CI setup
    # Priority 5: Docs - additional context
    PRIORITY_FILES: Dict[int, List[str]] = {
        1: [
            "README.md", "README.rst", "README.txt", "README",
            "readme.md", "Readme.md",
        ],
        2: [
            # JavaScript/TypeScript
            "package.json",
            # Python
            "pyproject.toml", "setup.py", "setup.cfg", "requirements.txt",
            # Rust
            "Cargo.toml",
            # Go
            "go.mod",
            # Java/Kotlin
            "pom.xml", "build.gradle", "build.gradle.kts",
            # Ruby
            "Gemfile",
            # PHP
            "composer.json",
            # .NET
            "*.csproj", "*.fsproj",
            # Elixir
            "mix.exs",
        ],
        3: [
            # Python entry points
            "main.py", "app.py", "__main__.py", "cli.py", "run.py",
            "src/main.py", "src/app.py", "src/__main__.py",
            "app/main.py", "app/__init__.py",
            # JavaScript/TypeScript
            "index.js", "index.ts", "main.js", "main.ts", "app.js", "app.ts",
            "src/index.js", "src/index.ts", "src/main.js", "src/main.ts",
            "src/app.js", "src/app.ts", "lib/index.js",
            # Go
            "main.go", "cmd/main.go",
            # Rust
            "src/main.rs", "src/lib.rs",
            # Ruby
            "lib/*.rb",
        ],
        4: [
            # CI/CD
            ".github/workflows/ci.yml", ".github/workflows/main.yml",
            ".github/workflows/test.yml", ".github/workflows/build.yml",
            ".gitlab-ci.yml", "Jenkinsfile", ".travis.yml", ".circleci/config.yml",
            # Docker
            "Dockerfile", "docker-compose.yml", "docker-compose.yaml",
            # Config
            "tsconfig.json", "vite.config.ts", "vite.config.js",
            "webpack.config.js", "rollup.config.js",
            "Makefile", "justfile",
        ],
        5: [
            "CONTRIBUTING.md", "CHANGELOG.md", "HISTORY.md",
            "docs/index.md", "docs/README.md", "docs/getting-started.md",
            "API.md", "ARCHITECTURE.md",
        ],
    }
    
    # Maximum file sizes (in characters) for different priority levels
    MAX_FILE_SIZES: Dict[int, int] = {
        1: 15000,  # README can be longer
        2: 8000,   # Config files
        3: 6000,   # Entry points
        4: 4000,   # CI/Docker
        5: 4000,   # Docs
        6: 3000,   # Source samples
    }
    
    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Gets or creates the HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                headers={
                    "Accept": "application/vnd.github.v3+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                }
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
        
        Uses GitHub's recursive tree API for efficiency (single request).
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
                raise EmptyRepoError(f"Repository {owner}/{repo} is empty")
            
            response.raise_for_status()
            data = response.json()
            
            if data.get("truncated"):
                logger.warning(f"File tree truncated for {owner}/{repo}")
            
            files = []
            for item in data.get("tree", []):
                if item["type"] == "blob":
                    path = item["path"]
                    if not self.should_skip_path(path):
                        files.append(path)
            
            if not files:
                raise EmptyRepoError(f"Repository {owner}/{repo} has no processable files")
            
            logger.info(f"Found {len(files)} relevant files in {owner}/{repo}")
            return files
            
        except httpx.HTTPStatusError as e:
            logger.error(f"GitHub API error: {e}")
            raise
    
    async def get_file_content(self, owner: str, repo: str, path: str, max_size: int = 10000) -> Optional[str]:
        """
        Fetches content of a specific file with size limit.
        """
        client = await self._get_client()
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/contents/{path}"
        
        try:
            response = await client.get(url)
            
            if response.status_code == 404:
                return None
            elif response.status_code == 403:
                if "rate limit" in response.text.lower():
                    raise RateLimitError()
                return None
            
            response.raise_for_status()
            data = response.json()
            
            # Skip files that are too large
            file_size = data.get("size", 0)
            if file_size > 500_000:  # 500KB hard limit
                logger.debug(f"Skipping large file: {path} ({file_size} bytes)")
                return None
            
            if data.get("encoding") == "base64" and data.get("content"):
                content = base64.b64decode(data["content"]).decode("utf-8", errors="replace")
                
                # Truncate if needed
                if len(content) > max_size:
                    content = content[:max_size] + "\n... [truncated]"
                
                return content
                
        except Exception as e:
            logger.debug(f"Failed to fetch {path}: {e}")
        
        return None
    
    async def get_files_parallel(
        self, 
        owner: str, 
        repo: str, 
        files: List[Tuple[str, int]],
        max_concurrent: int = 5
    ) -> List[Tuple[str, str, int]]:
        """
        Fetches multiple files in parallel for efficiency.
        
        Returns list of (path, content, priority) tuples.
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def fetch_one(path: str, priority: int) -> Optional[Tuple[str, str, int]]:
            async with semaphore:
                max_size = self.MAX_FILE_SIZES.get(priority, 4000)
                content = await self.get_file_content(owner, repo, path, max_size)
                if content:
                    return (path, content, priority)
                return None
        
        tasks = [fetch_one(path, priority) for path, priority in files]
        results = await asyncio.gather(*tasks)
        
        return [r for r in results if r is not None]
    
    def should_skip_path(self, path: str) -> bool:
        """Determines if a path should be skipped."""
        parts = path.split("/")
        filename = parts[-1]
        
        # Skip specific files
        if filename in self.SKIP_FILES:
            return True
        
        # Skip lock files
        if filename in self.LOCK_FILES:
            return True
        
        # Check excluded directories
        for part in parts[:-1]:
            if part in self.EXCLUDED_DIRS:
                return True
            if part.endswith((".egg-info", ".dist-info")):
                return True
        
        # Check excluded extensions
        path_lower = path.lower()
        for ext in self.EXCLUDED_EXTENSIONS:
            if path_lower.endswith(ext):
                return True
        
        return False
    
    def get_priority_files(self, file_tree: List[str]) -> List[Tuple[str, int]]:
        """
        Returns files sorted by priority for LLM context.
        
        Optimized to maximize information density within token budget.
        """
        result = []
        seen = set()
        
        # Match priority files
        for priority, patterns in self.PRIORITY_FILES.items():
            for pattern in patterns:
                pattern_lower = pattern.lower()
                
                # Handle wildcard patterns
                if "*" in pattern:
                    prefix = pattern_lower.split("*")[0]
                    suffix = pattern_lower.split("*")[-1] if "*" in pattern else ""
                    for file_path in file_tree:
                        file_lower = file_path.lower()
                        if file_lower.startswith(prefix) and file_lower.endswith(suffix):
                            if file_path not in seen:
                                result.append((file_path, priority))
                                seen.add(file_path)
                else:
                    for file_path in file_tree:
                        file_lower = file_path.lower()
                        if file_lower == pattern_lower or file_lower.endswith(f"/{pattern_lower}"):
                            if file_path not in seen:
                                result.append((file_path, priority))
                                seen.add(file_path)
        
        # Add representative source files (priority 6)
        # Pick files from different directories for diversity
        source_extensions = {".py", ".js", ".ts", ".go", ".rs", ".java", ".rb", ".php"}
        source_dirs_seen = set()
        max_source_files = 3
        source_count = 0
        
        for file_path in file_tree:
            if source_count >= max_source_files:
                break
            if file_path in seen:
                continue
            
            # Check if it's a source file
            for ext in source_extensions:
                if file_path.endswith(ext):
                    # Get directory for diversity
                    dir_path = "/".join(file_path.split("/")[:-1]) or "root"
                    if dir_path not in source_dirs_seen:
                        result.append((file_path, 6))
                        seen.add(file_path)
                        source_dirs_seen.add(dir_path)
                        source_count += 1
                    break
        
        # Sort by priority
        result.sort(key=lambda x: x[1])
        return result
    
    def extract_dependencies_only(self, content: str, file_path: str) -> str:
        """
        Extracts only dependency information from config files.
        
        This dramatically reduces token usage while preserving key info.
        """
        path_lower = file_path.lower()
        
        if path_lower.endswith("package.json"):
            return self._extract_package_json_deps(content)
        elif path_lower.endswith(("requirements.txt", "requirements-dev.txt")):
            return self._extract_requirements_deps(content)
        elif path_lower.endswith("pyproject.toml"):
            return self._extract_pyproject_deps(content)
        elif path_lower.endswith("cargo.toml"):
            return self._extract_cargo_deps(content)
        elif path_lower.endswith("go.mod"):
            return self._extract_go_deps(content)
        
        return content
    
    def _extract_package_json_deps(self, content: str) -> str:
        """Extract key fields from package.json."""
        import json
        try:
            data = json.loads(content)
            extracted = {
                "name": data.get("name"),
                "description": data.get("description"),
                "dependencies": data.get("dependencies", {}),
                "devDependencies": data.get("devDependencies", {}),
                "scripts": {k: v for k, v in data.get("scripts", {}).items() 
                          if k in ["start", "build", "test", "dev"]},
            }
            return json.dumps(extracted, indent=2)
        except:
            return content[:3000]
    
    def _extract_requirements_deps(self, content: str) -> str:
        """Extract package names from requirements.txt."""
        lines = []
        for line in content.split("\n"):
            line = line.strip()
            if line and not line.startswith("#") and not line.startswith("-"):
                # Get just the package name
                pkg = line.split("==")[0].split(">=")[0].split("<=")[0].split("[")[0]
                if pkg:
                    lines.append(pkg)
        return "\n".join(lines[:50])  # Limit to 50 packages
    
    def _extract_pyproject_deps(self, content: str) -> str:
        """Extract key sections from pyproject.toml."""
        lines = []
        in_deps = False
        in_project = False
        
        for line in content.split("\n"):
            if "[project]" in line or "[tool.poetry]" in line:
                in_project = True
                lines.append(line)
            elif "[project.dependencies]" in line or "[tool.poetry.dependencies]" in line:
                in_deps = True
                lines.append(line)
            elif line.startswith("[") and in_deps:
                in_deps = False
            elif line.startswith("[") and in_project:
                in_project = False
            elif in_deps or in_project:
                lines.append(line)
        
        return "\n".join(lines[:100])
    
    def _extract_cargo_deps(self, content: str) -> str:
        """Extract dependencies from Cargo.toml."""
        lines = []
        in_deps = False
        
        for line in content.split("\n"):
            if "[package]" in line:
                lines.append(line)
                in_deps = True
            elif "[dependencies]" in line or "[dev-dependencies]" in line:
                lines.append(line)
                in_deps = True
            elif line.startswith("[") and in_deps:
                in_deps = False
            elif in_deps:
                lines.append(line)
        
        return "\n".join(lines[:80])
    
    def _extract_go_deps(self, content: str) -> str:
        """Extract module info from go.mod."""
        lines = []
        for line in content.split("\n"):
            line = line.strip()
            if line.startswith("module ") or line.startswith("go "):
                lines.append(line)
            elif line and not line.startswith("//"):
                # Get require statements
                if "require" in line or (lines and not line.startswith(")")):
                    lines.append(line)
        return "\n".join(lines[:50])
    
    def score_entry_point(self, content: str, file_path: str, repo_name: str) -> int:
        """
        Scores a file's likelihood of being a representative entry point.
        
        Based on LARCH paper heuristics for identifying representative code.
        Higher score = more likely to be the main entry point.
        
        Args:
            content: File content
            file_path: Path to the file
            repo_name: Repository name for matching
            
        Returns:
            Score from 0-100
        """
        score = 0
        content_lower = content.lower()
        filename = file_path.split("/")[-1].lower()
        filename_no_ext = filename.rsplit(".", 1)[0] if "." in filename else filename
        
        # 1. Contains main function/entry point pattern (+25)
        main_patterns = [
            'if __name__ == "__main__"',
            "if __name__ == '__main__'",
            "def main(",
            "func main(",
            "public static void main(",
            "fn main(",
        ]
        for pattern in main_patterns:
            if pattern in content or pattern.lower() in content_lower:
                score += 25
                break
        
        # 2. Contains argument parser (+15)
        arg_patterns = ["argparse", "click", "typer", "fire", "docopt", "yargs", "commander"]
        for pattern in arg_patterns:
            if pattern in content_lower:
                score += 15
                break
        
        # 3. Contains web framework initialization (+15)
        web_patterns = [
            "fastapi(", "flask(__name__", "express()", "app = flask",
            "app = fastapi", "createapp", "gin.default", "echo.new",
            "fiber.new", "actix_web", "axum::router", "rocket::build"
        ]
        for pattern in web_patterns:
            if pattern in content_lower:
                score += 15
                break
        
        # 4. File name matches repo name (+20)
        repo_name_lower = repo_name.lower().replace("-", "_").replace(" ", "_")
        if filename_no_ext == repo_name_lower or filename_no_ext == repo_name_lower.replace("_", ""):
            score += 20
        
        # 5. Entry point-ish file names (+10)
        entry_names = {"main", "app", "cli", "run", "server", "index", "__main__"}
        if filename_no_ext in entry_names:
            score += 10
        
        # 6. Contains app/server startup code (+10)
        startup_patterns = [
            "uvicorn.run", "app.run(", "serve(", "listen(",
            ".listen(", "createserver", "http.server"
        ]
        for pattern in startup_patterns:
            if pattern in content_lower:
                score += 10
                break
        
        # 7. Penalty for test files (-20)
        if filename.startswith("test_") or filename.endswith("_test.py") or "/test" in file_path.lower():
            score -= 20
        
        # 8. Penalty for __init__.py (usually not representative) (-10)
        if filename == "__init__.py":
            score -= 10
        
        # 9. Penalty for very short files (-10)
        if len(content) < 200:
            score -= 10
        
        return max(0, min(100, score))
    
    def extract_signatures_and_docstrings(self, content: str, file_path: str) -> str:
        """
        Extracts function/class signatures and docstrings from source code.
        
        This dramatically reduces tokens while preserving semantic information.
        Supports Python, JavaScript/TypeScript, Go, Rust.
        
        Args:
            content: Full file content
            file_path: Path to determine language
            
        Returns:
            Extracted signatures and docstrings
        """
        path_lower = file_path.lower()
        
        if path_lower.endswith(".py"):
            return self._extract_python_signatures(content)
        elif path_lower.endswith((".js", ".ts", ".jsx", ".tsx")):
            return self._extract_js_signatures(content)
        elif path_lower.endswith(".go"):
            return self._extract_go_signatures(content)
        elif path_lower.endswith(".rs"):
            return self._extract_rust_signatures(content)
        
        # For other languages, return truncated content
        return content[:2000] if len(content) > 2000 else content
    
    def _extract_python_signatures(self, content: str) -> str:
        """Extract Python function/class signatures and docstrings."""
        import re
        lines = content.split("\n")
        result = []
        in_docstring = False
        docstring_char = None
        current_indent = 0
        
        # Get module docstring first
        for i, line in enumerate(lines[:20]):
            stripped = line.strip()
            if stripped.startswith('"""') or stripped.startswith("'''"):
                # Module docstring
                quote = stripped[:3]
                if stripped.count(quote) >= 2:
                    result.append(stripped)
                else:
                    result.append(stripped)
                    for j in range(i + 1, min(i + 10, len(lines))):
                        result.append(lines[j])
                        if quote in lines[j]:
                            break
                result.append("")
                break
            elif stripped and not stripped.startswith("#"):
                break
        
        # Extract class and function definitions
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # Class definition
            if stripped.startswith("class ") and ":" in stripped:
                result.append(line)
                # Get class docstring
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if next_line.startswith('"""') or next_line.startswith("'''"):
                        quote = next_line[:3]
                        if next_line.count(quote) >= 2:
                            result.append(lines[i + 1])
                        else:
                            result.append(lines[i + 1])
                            for j in range(i + 2, min(i + 8, len(lines))):
                                result.append(lines[j])
                                if quote in lines[j]:
                                    break
                result.append("")
            
            # Function/method definition
            elif (stripped.startswith("def ") or stripped.startswith("async def ")) and ":" in stripped:
                result.append(line)
                # Get function docstring
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if next_line.startswith('"""') or next_line.startswith("'''"):
                        quote = next_line[:3]
                        if next_line.count(quote) >= 2:
                            result.append(lines[i + 1])
                        else:
                            result.append(lines[i + 1])
                            for j in range(i + 2, min(i + 6, len(lines))):
                                result.append(lines[j])
                                if quote in lines[j]:
                                    break
                result.append("")
        
        extracted = "\n".join(result)
        return extracted if extracted.strip() else content[:1500]
    
    def _extract_js_signatures(self, content: str) -> str:
        """Extract JavaScript/TypeScript function signatures and JSDoc."""
        import re
        lines = content.split("\n")
        result = []
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # JSDoc comment
            if stripped.startswith("/**"):
                jsdoc_lines = [line]
                for j in range(i + 1, min(i + 15, len(lines))):
                    jsdoc_lines.append(lines[j])
                    if "*/" in lines[j]:
                        break
                result.extend(jsdoc_lines)
            
            # Function declarations
            elif any(p in stripped for p in ["function ", "const ", "let ", "export ", "async "]):
                if "=>" in stripped or "function" in stripped or "(" in stripped:
                    # Get just the signature line
                    result.append(line)
                    if not stripped.endswith("{") and not stripped.endswith("}"):
                        # Multi-line signature
                        for j in range(i + 1, min(i + 3, len(lines))):
                            result.append(lines[j])
                            if "{" in lines[j] or "=>" in lines[j]:
                                break
                    result.append("")
            
            # Class declarations
            elif stripped.startswith("class ") or stripped.startswith("export class "):
                result.append(line)
                result.append("")
            
            # Interface/Type declarations (TypeScript)
            elif stripped.startswith("interface ") or stripped.startswith("type ") or stripped.startswith("export interface ") or stripped.startswith("export type "):
                result.append(line)
                # Get the full interface/type
                if "{" in stripped and "}" not in stripped:
                    for j in range(i + 1, min(i + 20, len(lines))):
                        result.append(lines[j])
                        if "}" in lines[j]:
                            break
                result.append("")
        
        extracted = "\n".join(result)
        return extracted if extracted.strip() else content[:1500]
    
    def _extract_go_signatures(self, content: str) -> str:
        """Extract Go function signatures and comments."""
        lines = content.split("\n")
        result = []
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # Package declaration
            if stripped.startswith("package "):
                result.append(line)
                result.append("")
            
            # Comments before functions
            elif stripped.startswith("//"):
                # Check if next non-comment line is a function
                for j in range(i + 1, min(i + 5, len(lines))):
                    next_stripped = lines[j].strip()
                    if next_stripped.startswith("func ") or next_stripped.startswith("type "):
                        result.append(line)
                        break
                    elif next_stripped and not next_stripped.startswith("//"):
                        break
            
            # Function declarations
            elif stripped.startswith("func "):
                result.append(line)
                result.append("")
            
            # Type declarations
            elif stripped.startswith("type "):
                result.append(line)
                if "struct {" in stripped or "interface {" in stripped:
                    for j in range(i + 1, min(i + 20, len(lines))):
                        result.append(lines[j])
                        if lines[j].strip() == "}":
                            break
                result.append("")
        
        extracted = "\n".join(result)
        return extracted if extracted.strip() else content[:1500]
    
    def _extract_rust_signatures(self, content: str) -> str:
        """Extract Rust function signatures and doc comments."""
        lines = content.split("\n")
        result = []
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # Doc comments
            if stripped.startswith("///") or stripped.startswith("//!"):
                result.append(line)
            
            # Function declarations
            elif stripped.startswith("pub fn ") or stripped.startswith("fn ") or stripped.startswith("async fn "):
                result.append(line)
                result.append("")
            
            # Struct/Enum declarations
            elif stripped.startswith("pub struct ") or stripped.startswith("struct ") or \
                 stripped.startswith("pub enum ") or stripped.startswith("enum "):
                result.append(line)
                if "{" in stripped and "}" not in stripped:
                    for j in range(i + 1, min(i + 20, len(lines))):
                        result.append(lines[j])
                        if "}" in lines[j]:
                            break
                result.append("")
            
            # Impl blocks
            elif stripped.startswith("impl "):
                result.append(line)
                result.append("")
        
        extracted = "\n".join(result)
        return extracted if extracted.strip() else content[:1500]
