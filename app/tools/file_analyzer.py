"""File analysis for technology detection."""

from typing import List, Dict, Set
import json
import re
import logging

logger = logging.getLogger(__name__)


class FileAnalyzer:
    """Analyzes files to detect technologies and patterns."""
    
    LANGUAGE_EXTENSIONS: Dict[str, str] = {
        ".py": "Python",
        ".js": "JavaScript",
        ".ts": "TypeScript",
        ".jsx": "React",
        ".tsx": "React",
        ".java": "Java",
        ".go": "Go",
        ".rs": "Rust",
        ".rb": "Ruby",
        ".php": "PHP",
        ".cs": "C#",
        ".cpp": "C++",
        ".c": "C",
        ".swift": "Swift",
        ".kt": "Kotlin",
        ".scala": "Scala",
        ".vue": "Vue.js",
        ".svelte": "Svelte",
        ".dart": "Dart",
        ".ex": "Elixir",
        ".exs": "Elixir",
        ".clj": "Clojure",
        ".hs": "Haskell",
        ".lua": "Lua",
        ".r": "R",
        ".R": "R",
        ".jl": "Julia",
        ".pl": "Perl",
        ".sh": "Shell",
        ".bash": "Bash",
        ".zsh": "Zsh",
    }
    
    def detect_languages(self, file_tree: List[str]) -> List[str]:
        """
        Detects programming languages from file extensions.
        
        Args:
            file_tree: List of file paths
            
        Returns:
            Sorted list of detected languages
        """
        languages: Set[str] = set()
        
        for file_path in file_tree:
            # Get extension
            if "." in file_path:
                ext = "." + file_path.rsplit(".", 1)[-1]
                if ext in self.LANGUAGE_EXTENSIONS:
                    languages.add(self.LANGUAGE_EXTENSIONS[ext])
        
        return sorted(list(languages))
    
    def detect_frameworks(self, config_files: Dict[str, str]) -> List[str]:
        """
        Detects frameworks from config file contents.
        
        Args:
            config_files: Dict mapping file paths to contents
            
        Returns:
            Sorted list of detected frameworks
        """
        frameworks: Set[str] = set()
        
        for path, content in config_files.items():
            path_lower = path.lower()
            
            # Check package.json
            if path_lower.endswith("package.json"):
                frameworks.update(self._detect_js_frameworks(content))
            
            # Check Python configs
            elif path_lower.endswith(("pyproject.toml", "requirements.txt", "setup.py", "setup.cfg")):
                frameworks.update(self._detect_python_frameworks(content))
            
            # Check Cargo.toml (Rust)
            elif path_lower.endswith("cargo.toml"):
                frameworks.update(self._detect_rust_frameworks(content))
            
            # Check go.mod
            elif path_lower.endswith("go.mod"):
                frameworks.update(self._detect_go_frameworks(content))
            
            # Check Gemfile (Ruby)
            elif path_lower.endswith("gemfile"):
                frameworks.update(self._detect_ruby_frameworks(content))
        
        return sorted(list(frameworks))
    
    def _detect_js_frameworks(self, content: str) -> Set[str]:
        """Detects JavaScript/TypeScript frameworks from package.json."""
        frameworks: Set[str] = set()
        
        try:
            pkg = json.loads(content)
            deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
            
            framework_map = {
                "react": "React",
                "react-dom": "React",
                "vue": "Vue.js",
                "@vue/": "Vue.js",
                "angular": "Angular",
                "@angular/": "Angular",
                "next": "Next.js",
                "nuxt": "Nuxt.js",
                "express": "Express.js",
                "fastify": "Fastify",
                "@nestjs/": "NestJS",
                "svelte": "Svelte",
                "gatsby": "Gatsby",
                "remix": "Remix",
                "electron": "Electron",
                "jest": "Jest",
                "mocha": "Mocha",
                "webpack": "Webpack",
                "vite": "Vite",
                "tailwindcss": "Tailwind CSS",
                "prisma": "Prisma",
                "mongoose": "MongoDB",
                "sequelize": "Sequelize",
                "typeorm": "TypeORM",
            }
            
            for dep in deps.keys():
                dep_lower = dep.lower()
                for pattern, framework in framework_map.items():
                    if pattern in dep_lower:
                        frameworks.add(framework)
                        break
        except json.JSONDecodeError:
            logger.warning("Failed to parse package.json")
        
        return frameworks
    
    def _detect_python_frameworks(self, content: str) -> Set[str]:
        """Detects Python frameworks from config files."""
        frameworks: Set[str] = set()
        content_lower = content.lower()
        
        framework_patterns = {
            "django": "Django",
            "flask": "Flask",
            "fastapi": "FastAPI",
            "pytorch": "PyTorch",
            "torch": "PyTorch",
            "tensorflow": "TensorFlow",
            "pandas": "Pandas",
            "numpy": "NumPy",
            "langchain": "LangChain",
            "langgraph": "LangGraph",
            "scikit-learn": "scikit-learn",
            "sklearn": "scikit-learn",
            "celery": "Celery",
            "sqlalchemy": "SQLAlchemy",
            "pytest": "pytest",
            "streamlit": "Streamlit",
            "gradio": "Gradio",
            "transformers": "Hugging Face Transformers",
            "openai": "OpenAI",
            "anthropic": "Anthropic",
            "pydantic": "Pydantic",
            "httpx": "HTTPX",
            "aiohttp": "aiohttp",
            "requests": "Requests",
            "beautifulsoup": "BeautifulSoup",
            "scrapy": "Scrapy",
            "selenium": "Selenium",
            "playwright": "Playwright",
        }
        
        for pattern, framework in framework_patterns.items():
            if pattern in content_lower:
                frameworks.add(framework)
        
        return frameworks
    
    def _detect_rust_frameworks(self, content: str) -> Set[str]:
        """Detects Rust frameworks from Cargo.toml."""
        frameworks: Set[str] = set()
        content_lower = content.lower()
        
        framework_patterns = {
            "actix-web": "Actix Web",
            "axum": "Axum",
            "rocket": "Rocket",
            "tokio": "Tokio",
            "serde": "Serde",
            "diesel": "Diesel",
            "sqlx": "SQLx",
        }
        
        for pattern, framework in framework_patterns.items():
            if pattern in content_lower:
                frameworks.add(framework)
        
        return frameworks
    
    def _detect_go_frameworks(self, content: str) -> Set[str]:
        """Detects Go frameworks from go.mod."""
        frameworks: Set[str] = set()
        content_lower = content.lower()
        
        framework_patterns = {
            "gin-gonic": "Gin",
            "echo": "Echo",
            "fiber": "Fiber",
            "gorilla/mux": "Gorilla Mux",
            "gorm": "GORM",
        }
        
        for pattern, framework in framework_patterns.items():
            if pattern in content_lower:
                frameworks.add(framework)
        
        return frameworks
    
    def _detect_ruby_frameworks(self, content: str) -> Set[str]:
        """Detects Ruby frameworks from Gemfile."""
        frameworks: Set[str] = set()
        content_lower = content.lower()
        
        framework_patterns = {
            "rails": "Ruby on Rails",
            "sinatra": "Sinatra",
            "rspec": "RSpec",
            "sidekiq": "Sidekiq",
        }
        
        for pattern, framework in framework_patterns.items():
            if pattern in content_lower:
                frameworks.add(framework)
        
        return frameworks
    
    def detect_tools(self, file_tree: List[str], config_files: Dict[str, str]) -> List[str]:
        """
        Detects build tools, CI/CD, containerization.
        
        Args:
            file_tree: List of file paths
            config_files: Dict mapping file paths to contents
            
        Returns:
            Sorted list of detected tools
        """
        tools: Set[str] = set()
        
        # CI/CD detection from file paths
        ci_patterns = {
            ".github/workflows": "GitHub Actions",
            ".gitlab-ci.yml": "GitLab CI",
            "Jenkinsfile": "Jenkins",
            ".circleci": "CircleCI",
            ".travis.yml": "Travis CI",
            "azure-pipelines": "Azure Pipelines",
            "bitbucket-pipelines": "Bitbucket Pipelines",
        }
        
        for file_path in file_tree:
            for pattern, tool in ci_patterns.items():
                if pattern in file_path:
                    tools.add(tool)
        
        # Containerization
        for file_path in file_tree:
            file_lower = file_path.lower()
            if "dockerfile" in file_lower:
                tools.add("Docker")
            if "docker-compose" in file_lower:
                tools.add("Docker Compose")
            if "kubernetes" in file_lower or "k8s" in file_lower:
                tools.add("Kubernetes")
            if file_lower.endswith(".tf"):
                tools.add("Terraform")
            if "helm" in file_lower:
                tools.add("Helm")
        
        # Build tools from file paths
        build_patterns = {
            "Makefile": "Make",
            "webpack.config": "Webpack",
            "vite.config": "Vite",
            "rollup.config": "Rollup",
            "tsconfig.json": "TypeScript",
            "babel.config": "Babel",
            ".eslintrc": "ESLint",
            ".prettierrc": "Prettier",
            "tox.ini": "tox",
            "noxfile.py": "nox",
            ".pre-commit": "pre-commit",
            "renovate.json": "Renovate",
            "dependabot.yml": "Dependabot",
        }
        
        for file_path in file_tree:
            for pattern, tool in build_patterns.items():
                if pattern in file_path:
                    tools.add(tool)
        
        return sorted(list(tools))
    
    def analyze_structure(self, file_tree: List[str]) -> str:
        """
        Analyzes and describes the project structure.
        
        Args:
            file_tree: List of file paths
            
        Returns:
            Human-readable structure description
        """
        # Get top-level directories
        top_dirs: Set[str] = set()
        for path in file_tree:
            parts = path.split("/")
            if len(parts) > 1:
                top_dirs.add(parts[0])
        
        # Common patterns
        patterns = []
        
        structure_hints = {
            "src": "source code in `src/`",
            "lib": "library code in `lib/`",
            "app": "application code in `app/`",
            "tests": "tests in `tests/`",
            "test": "tests in `test/`",
            "spec": "specs in `spec/`",
            "docs": "documentation in `docs/`",
            "doc": "documentation in `doc/`",
            "examples": "examples in `examples/`",
            "scripts": "scripts in `scripts/`",
            "bin": "binaries/scripts in `bin/`",
            "cmd": "commands in `cmd/`",
            "pkg": "packages in `pkg/`",
            "internal": "internal packages in `internal/`",
            "api": "API code in `api/`",
            "web": "web assets in `web/`",
            "public": "public assets in `public/`",
            "static": "static files in `static/`",
            "templates": "templates in `templates/`",
            "migrations": "database migrations in `migrations/`",
        }
        
        for dir_name, description in structure_hints.items():
            if dir_name in top_dirs:
                patterns.append(description)
        
        if patterns:
            return f"The project has {', '.join(patterns[:5])}."
        elif top_dirs:
            dirs_list = ', '.join(f'`{d}/`' for d in sorted(top_dirs)[:5])
            return f"Top-level directories include: {dirs_list}."
        else:
            return "The project has a flat structure with files in the root directory."
