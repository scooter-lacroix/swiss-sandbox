# Developer Guide

## Overview

This guide is intended for developers interested in contributing to, enhancing, or customizing the Sandbox MCP project.

### Codebase Structure

```
sandbox-mcp/
├── src/                        # Main source code directory
│   └── sandbox/               # Core sandbox package
│       ├── __init__.py       # Package initialization
│       ├── sdk/              # SDK and execution environments
│       │   ├── __init__.py   # SDK initialization
│       │   └── local_sandbox.py  # Local execution environment
│       └── core/             # Core utilities and execution context
│           ├── __init__.py   # Initialization
│           └── execution_context.py  # PersistentExecutionContext Implementation
├── tests/                     # Unit and integration tests
│   ├── __init__.py
│   ├── test_integration.py   # Integration tests
│   └── test_simple_integration.py  # Simple validation tests
├── docs/                      # Project documentation
├── pyproject.toml             # Project configuration
├── README.md                  # Main README file
└── .gitignore                 # Git ignore file
```

## Local Development Setup

1. **Fork and Clone the Repository**

```bash
git clone https://github.com/scooter-lacroix/sandbox-mcp.git
cd sandbox-mcp
```

2. **Setup Virtual Environment**

Create a virtual environment using `uv` or `venv`:

```bash
uv venv
uv pip install -e ".[dev]"

# OR using venv
python -m venv .venv
source .venv/bin/activate  # Or .venv\Scripts\activate on Windows
pip install -e ".[dev]"
```

3. **Run Tests**

Execute the test suite to ensure everything is functioning properly:

```bash
uv run pytest tests/

# OR using pytest directly
pytest tests/
```

## Development Workflow

### Adding New Features

1. **Plan and Document**
   - Describe the new feature in the `docs/changelog.md` and possibly add a new section in `README.md`.

2. **Implement**
   - Avoid hardcoding values; use configurations when possible.
   - Follow existing patterns.

3. **Testing**
   - Create tests for new features in the `tests/` directory.
   - Ensure full coverage for new functionality.

4. **Style and Conventions**
   - Run `flake8` for style checks.
   - Auto-format code with `black src tests`.

5. **Commit and Push**
   - Follow conventional commit messages (`feat:`, `fix:`, `docs:`, etc.).
   - Ensure the commit history is clean.

### Pull Requests

- Open a PR against the `main` branch.
- Include a clear description and link to any related issues.
- Use labels and reviewers effectively.

## Testing

- Use `pytest` in combination with `pytest-asyncio` for async code.
- Use `unittest.mock` for mocking dependencies and testing interactive code.

## Configuration

### Custom Settings

Settings can be adjusted via `pyproject.toml`, environment variables, or directly through the Python API.

### Logging

Adjust logging levels via the environment variable `SANDBOX_LOG_LEVEL`.

## Deployment

1. **Ensure Tests Pass**

   All tests should be passing before deployment.

2. **Tag Releases**

   - Use semantic versioning for tags: `vX.Y.Z`
   - Create a release on GitHub with release notes.

3. **Publish to Package Repository (Optional)**

   Instructions to publish a new version:

```bash
# Build package
uv build

# Publish
uv publish
```

4. **Announce Release**
   - Update stakeholders, users, and community channels.

## Continous Integration

- Make use of GitHub Actions for CI configuration.
- Run tests on multiple Python versions if possible.

## Community and Support

- Check GitHub issues for ways to contribute
- Join community discussions on forums or communication platforms
- Be mindful of the contribution guidelines in `CONTRIBUTING.md`

## License

This project is licensed under the Apache License, included here as `LICENSE` file.

