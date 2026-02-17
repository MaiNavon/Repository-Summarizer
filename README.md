# GitHub Repository Summarizer

An API service that takes a GitHub repository URL and returns a human-readable summary of the project, including what it does, what technologies are used, and how it's structured.

## Features

- Analyzes public GitHub repositories
- Extracts project description, technologies, and structure
- Uses LangGraph agentic architecture for intelligent content selection
- Caches results for improved performance
- Handles large repositories with smart context management

## Prerequisites

- Python 3.10+
- Nebius Token Factory API key

## Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd github-repo-summarizer
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set your Nebius API key:
```bash
export NEBIUS_API_KEY=your_api_key_here
```

## Running the Server

Start the server on port 8000:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Or using Python module:
```bash
python -m uvicorn app.main:app --port 8000
```

## Testing the Endpoint

```bash
curl -X POST http://localhost:8000/summarize \
  -H "Content-Type: application/json" \
  -d '{"github_url": "https://github.com/psf/requests"}'
```

Example response:
```json
{
  "summary": "**Requests** is a popular Python library for making HTTP requests...",
  "technologies": ["Python", "urllib3", "certifi"],
  "structure": "The project follows a standard Python package layout with the main source code in `src/requests/`, tests in `tests/`, and documentation in `docs/`."
}
```

## API Reference

### POST /summarize

Summarizes a GitHub repository.

**Request:**
```json
{
  "github_url": "https://github.com/owner/repo"
}
```

**Success Response (200):**
```json
{
  "summary": "Human-readable project description",
  "technologies": ["Language", "Framework", "Tool"],
  "structure": "Brief description of project structure"
}
```

**Error Response:**
```json
{
  "status": "error",
  "message": "Description of what went wrong"
}
```

### GET /health

Health check endpoint.

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `NEBIUS_API_KEY` | Yes | - | API key for Nebius Token Factory |
| `NEBIUS_MODEL` | No | `Qwen/Qwen2.5-Coder-32B-Instruct` | LLM model to use |
| `LOG_LEVEL` | No | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |

## Model Choice

This service uses **Qwen2.5-Coder-32B-Instruct** as the default model because:
- Optimized for code understanding and repository analysis
- Excellent at generating structured JSON output
- Large 128K context window for processing repository contents
- Cost-effective compared to larger 70B models

## Repository Content Handling

### What's Included (Priority Order)
1. **README files** - Primary source of project description
2. **Package configs** - package.json, pyproject.toml, Cargo.toml, etc. for technology detection
3. **Entry points** - main.py, index.js, etc. for understanding project structure
4. **CI/CD configs** - GitHub Actions, Dockerfile for tooling detection
5. **Documentation** - CONTRIBUTING.md, CHANGELOG.md for additional context
6. **Sample source files** - Representative code samples

### What's Skipped
- **Binary files** - .exe, .dll, .pyc, images, etc.
- **Lock files** - package-lock.json, yarn.lock, poetry.lock, etc.
- **Generated directories** - node_modules, __pycache__, dist, build, venv
- **Large files** - Files over 1MB are skipped
- **Archives** - .zip, .tar.gz, etc.

### Why This Approach
- **README first**: Most informative single file for understanding a project
- **Config files**: Reliable source for technology detection
- **Token budget**: Prioritizes information-dense files to maximize LLM context usage
- **Skip noise**: Excludes files that don't contribute to understanding the project

## Running Tests

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run all tests
pytest

# Run with coverage
pytest --cov=app

# Run specific test file
pytest tests/test_validators.py
```

## Project Structure

```
github-repo-summarizer/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application
│   ├── models.py            # Pydantic models
│   ├── validators.py        # URL validation
│   ├── errors.py            # Custom exceptions
│   ├── cache.py             # Cache manager
│   ├── logging_config.py    # Logging setup
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── state.py         # LangGraph state
│   │   ├── graph.py         # LangGraph workflow
│   │   └── nodes.py         # Workflow nodes
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── github_fetcher.py    # GitHub API client
│   │   ├── file_analyzer.py     # Technology detection
│   │   └── context_manager.py   # Token management
│   └── llm/
│       ├── __init__.py
│       └── client.py        # Nebius LLM client
├── tests/
│   ├── __init__.py
│   ├── test_validators.py
│   ├── test_github_fetcher.py
│   ├── test_file_analyzer.py
│   ├── test_context_manager.py
│   └── test_api.py
├── requirements.txt
├── pyproject.toml
├── README.md
└── .env.example
```

## License

MIT
