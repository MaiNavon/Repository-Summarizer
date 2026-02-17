"""Tests for file analyzer."""

import pytest
from hypothesis import given, strategies as st, settings
from app.tools.file_analyzer import FileAnalyzer


class TestDetectLanguages:
    """Tests for language detection."""
    
    @pytest.fixture
    def analyzer(self):
        return FileAnalyzer()
    
    def test_detect_python(self, analyzer):
        """Test detecting Python."""
        files = ["main.py", "utils.py", "tests/test_main.py"]
        result = analyzer.detect_languages(files)
        assert "Python" in result
    
    def test_detect_javascript(self, analyzer):
        """Test detecting JavaScript."""
        files = ["index.js", "src/app.js"]
        result = analyzer.detect_languages(files)
        assert "JavaScript" in result
    
    def test_detect_typescript(self, analyzer):
        """Test detecting TypeScript."""
        files = ["index.ts", "src/app.ts"]
        result = analyzer.detect_languages(files)
        assert "TypeScript" in result
    
    def test_detect_multiple_languages(self, analyzer):
        """Test detecting multiple languages."""
        files = ["main.py", "index.js", "app.go", "lib.rs"]
        result = analyzer.detect_languages(files)
        assert "Python" in result
        assert "JavaScript" in result
        assert "Go" in result
        assert "Rust" in result
    
    def test_result_is_sorted(self, analyzer):
        """Test result is sorted alphabetically."""
        files = ["main.py", "index.js", "app.go"]
        result = analyzer.detect_languages(files)
        assert result == sorted(result)


class TestDetectFrameworks:
    """Tests for framework detection."""
    
    @pytest.fixture
    def analyzer(self):
        return FileAnalyzer()
    
    def test_detect_react_from_package_json(self, analyzer):
        """Property 9: Detect React from package.json."""
        config = {
            "package.json": '{"dependencies": {"react": "^18.0.0", "react-dom": "^18.0.0"}}'
        }
        result = analyzer.detect_frameworks(config)
        assert "React" in result
    
    def test_detect_vue_from_package_json(self, analyzer):
        """Detect Vue.js from package.json."""
        config = {
            "package.json": '{"dependencies": {"vue": "^3.0.0"}}'
        }
        result = analyzer.detect_frameworks(config)
        assert "Vue.js" in result
    
    def test_detect_express_from_package_json(self, analyzer):
        """Detect Express.js from package.json."""
        config = {
            "package.json": '{"dependencies": {"express": "^4.18.0"}}'
        }
        result = analyzer.detect_frameworks(config)
        assert "Express.js" in result
    
    def test_detect_fastapi_from_requirements(self, analyzer):
        """Detect FastAPI from requirements.txt."""
        config = {
            "requirements.txt": "fastapi>=0.100.0\nuvicorn>=0.23.0"
        }
        result = analyzer.detect_frameworks(config)
        assert "FastAPI" in result
    
    def test_detect_django_from_requirements(self, analyzer):
        """Detect Django from requirements.txt."""
        config = {
            "requirements.txt": "django>=4.0\ndjango-rest-framework"
        }
        result = analyzer.detect_frameworks(config)
        assert "Django" in result
    
    def test_detect_langgraph_from_pyproject(self, analyzer):
        """Detect LangGraph from pyproject.toml."""
        config = {
            "pyproject.toml": '[project]\ndependencies = ["langgraph>=0.0.26"]'
        }
        result = analyzer.detect_frameworks(config)
        assert "LangGraph" in result
    
    def test_invalid_json_handled(self, analyzer):
        """Test invalid JSON is handled gracefully."""
        config = {
            "package.json": "not valid json"
        }
        result = analyzer.detect_frameworks(config)
        assert isinstance(result, list)


class TestDetectTools:
    """Tests for tool detection."""
    
    @pytest.fixture
    def analyzer(self):
        return FileAnalyzer()
    
    def test_detect_github_actions(self, analyzer):
        """Test detecting GitHub Actions."""
        files = [".github/workflows/ci.yml", "src/main.py"]
        result = analyzer.detect_tools(files, {})
        assert "GitHub Actions" in result
    
    def test_detect_docker(self, analyzer):
        """Test detecting Docker."""
        files = ["Dockerfile", "src/main.py"]
        result = analyzer.detect_tools(files, {})
        assert "Docker" in result
    
    def test_detect_docker_compose(self, analyzer):
        """Test detecting Docker Compose."""
        files = ["docker-compose.yml", "src/main.py"]
        result = analyzer.detect_tools(files, {})
        assert "Docker Compose" in result
    
    def test_detect_typescript_config(self, analyzer):
        """Test detecting TypeScript from tsconfig."""
        files = ["tsconfig.json", "src/index.ts"]
        result = analyzer.detect_tools(files, {})
        assert "TypeScript" in result
    
    def test_detect_makefile(self, analyzer):
        """Test detecting Make."""
        files = ["Makefile", "src/main.py"]
        result = analyzer.detect_tools(files, {})
        assert "Make" in result


class TestAnalyzeStructure:
    """Tests for structure analysis."""
    
    @pytest.fixture
    def analyzer(self):
        return FileAnalyzer()
    
    def test_detect_src_directory(self, analyzer):
        """Test detecting src directory."""
        files = ["src/main.py", "src/utils.py"]
        result = analyzer.analyze_structure(files)
        assert "src" in result
    
    def test_detect_tests_directory(self, analyzer):
        """Test detecting tests directory."""
        files = ["tests/test_main.py", "src/main.py"]
        result = analyzer.analyze_structure(files)
        assert "tests" in result
    
    def test_detect_docs_directory(self, analyzer):
        """Test detecting docs directory."""
        files = ["docs/index.md", "src/main.py"]
        result = analyzer.analyze_structure(files)
        assert "docs" in result
    
    def test_flat_structure(self, analyzer):
        """Test flat structure detection."""
        files = ["main.py", "utils.py", "README.md"]
        result = analyzer.analyze_structure(files)
        assert "flat structure" in result.lower() or "root" in result.lower()
