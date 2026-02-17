"""Tests for GitHub fetcher."""

import pytest
from hypothesis import given, strategies as st, settings
from app.tools.github_fetcher import GitHubFetcher


class TestShouldSkipPath:
    """Unit tests for should_skip_path."""
    
    @pytest.fixture
    def fetcher(self):
        return GitHubFetcher()
    
    def test_skip_node_modules(self, fetcher):
        """Test skipping node_modules directory."""
        assert fetcher.should_skip_path("node_modules/package/index.js") is True
    
    def test_skip_git_directory(self, fetcher):
        """Test skipping .git directory."""
        assert fetcher.should_skip_path(".git/config") is True
    
    def test_skip_pycache(self, fetcher):
        """Test skipping __pycache__ directory."""
        assert fetcher.should_skip_path("src/__pycache__/module.pyc") is True
    
    def test_skip_venv(self, fetcher):
        """Test skipping venv directory."""
        assert fetcher.should_skip_path("venv/lib/python3.10/site.py") is True
    
    def test_skip_binary_exe(self, fetcher):
        """Test skipping .exe files."""
        assert fetcher.should_skip_path("bin/program.exe") is True
    
    def test_skip_binary_pyc(self, fetcher):
        """Test skipping .pyc files."""
        assert fetcher.should_skip_path("module.pyc") is True
    
    def test_skip_image_png(self, fetcher):
        """Test skipping .png files."""
        assert fetcher.should_skip_path("assets/logo.png") is True
    
    def test_skip_image_jpg(self, fetcher):
        """Test skipping .jpg files."""
        assert fetcher.should_skip_path("images/photo.jpg") is True
    
    def test_skip_archive_zip(self, fetcher):
        """Test skipping .zip files."""
        assert fetcher.should_skip_path("downloads/archive.zip") is True
    
    def test_skip_lock_file_npm(self, fetcher):
        """Test skipping package-lock.json."""
        assert fetcher.should_skip_path("package-lock.json") is True
    
    def test_skip_lock_file_yarn(self, fetcher):
        """Test skipping yarn.lock."""
        assert fetcher.should_skip_path("yarn.lock") is True
    
    def test_skip_lock_file_poetry(self, fetcher):
        """Test skipping poetry.lock."""
        assert fetcher.should_skip_path("poetry.lock") is True
    
    def test_allow_readme(self, fetcher):
        """Test allowing README.md."""
        assert fetcher.should_skip_path("README.md") is False
    
    def test_allow_python_file(self, fetcher):
        """Test allowing .py files."""
        assert fetcher.should_skip_path("src/main.py") is False
    
    def test_allow_javascript_file(self, fetcher):
        """Test allowing .js files."""
        assert fetcher.should_skip_path("src/index.js") is False
    
    def test_allow_package_json(self, fetcher):
        """Test allowing package.json."""
        assert fetcher.should_skip_path("package.json") is False
    
    def test_allow_pyproject_toml(self, fetcher):
        """Test allowing pyproject.toml."""
        assert fetcher.should_skip_path("pyproject.toml") is False


class TestShouldSkipPathProperties:
    """Property-based tests for file filtering."""
    
    @given(
        dir_name=st.sampled_from([
            "node_modules", ".git", "__pycache__", "venv", ".venv",
            "dist", "build", "target", "vendor"
        ]),
        filename=st.from_regex(r"[a-z]+\.[a-z]+", fullmatch=True)
    )
    @settings(max_examples=100)
    def test_property_excluded_dirs_skipped(self, dir_name: str, filename: str):
        """Property 3: File filtering excludes unwanted directories."""
        fetcher = GitHubFetcher()
        path = f"{dir_name}/{filename}"
        assert fetcher.should_skip_path(path) is True
    
    @given(
        ext=st.sampled_from([
            ".exe", ".dll", ".pyc", ".class", ".jar",
            ".zip", ".tar", ".gz",
            ".png", ".jpg", ".gif", ".ico",
            ".pdf", ".doc"
        ])
    )
    @settings(max_examples=50)
    def test_property_excluded_extensions_skipped(self, ext: str):
        """Property 3: File filtering excludes unwanted extensions."""
        fetcher = GitHubFetcher()
        path = f"some/path/file{ext}"
        assert fetcher.should_skip_path(path) is True
    
    @given(
        lock_file=st.sampled_from([
            "package-lock.json", "yarn.lock", "poetry.lock",
            "Cargo.lock", "go.sum", "Gemfile.lock"
        ])
    )
    @settings(max_examples=20)
    def test_property_lock_files_skipped(self, lock_file: str):
        """Property 3: File filtering excludes lock files."""
        fetcher = GitHubFetcher()
        assert fetcher.should_skip_path(lock_file) is True


class TestGetPriorityFiles:
    """Tests for get_priority_files."""
    
    @pytest.fixture
    def fetcher(self):
        return GitHubFetcher()
    
    def test_readme_highest_priority(self, fetcher):
        """Test README has highest priority."""
        file_tree = ["src/main.py", "README.md", "package.json"]
        result = fetcher.get_priority_files(file_tree)
        
        # README should be first
        assert result[0][0] == "README.md"
        assert result[0][1] == 1
    
    def test_config_before_source(self, fetcher):
        """Test config files come before source files."""
        file_tree = ["src/main.py", "package.json", "index.js"]
        result = fetcher.get_priority_files(file_tree)
        
        paths = [r[0] for r in result]
        pkg_idx = paths.index("package.json")
        
        # package.json should have priority 2
        assert result[pkg_idx][1] == 2
    
    def test_priority_ordering(self, fetcher):
        """Property 10: File priority ordering is correct."""
        file_tree = [
            "src/utils.py",
            "README.md",
            "package.json",
            "main.py",
            "Dockerfile",
            "CONTRIBUTING.md"
        ]
        result = fetcher.get_priority_files(file_tree)
        
        # Verify sorted by priority
        priorities = [r[1] for r in result]
        assert priorities == sorted(priorities)
