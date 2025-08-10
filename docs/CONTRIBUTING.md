# Contributing to Sandbox MCP

Thank you for your interest in contributing to the Sandbox MCP project! This guide will help you get started with contributing to the codebase.

## Getting Started

### Prerequisites

- Python 3.9 or higher
- Git
- uv (recommended) or pip

### Setting Up Development Environment

1. **Fork the repository** on GitHub

2. **Clone your fork:**
   ```bash
   git clone https://github.com/YOUR_USERNAME/sandbox-mcp.git
   cd sandbox-mcp
   ```

3. **Set up the development environment:**
   ```bash
   # Using uv (recommended)
   uv venv
   uv pip install -e ".[dev]"
   
   # Or using pip
   python -m venv .venv
   source .venv/bin/activate  # Linux/macOS
   # .venv\Scripts\activate  # Windows
   pip install -e ".[dev]"
   ```

4. **Run tests to ensure everything works:**
   ```bash
   uv run pytest tests/
   # or
   pytest tests/
   ```

## Development Workflow

### 1. Create a Feature Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/your-fix-name
```

### 2. Make Your Changes

- Follow the existing code style and patterns
- Add tests for new functionality
- Update documentation as needed
- Ensure all tests pass

### 3. Commit Your Changes

Use clear, descriptive commit messages:

```bash
git add .
git commit -m "feat: add new sandbox execution feature"
# or
git commit -m "fix: resolve memory leak in execution context"
# or
git commit -m "docs: update API documentation for new methods"
```

#### Commit Message Format

We follow the [Conventional Commits](https://conventionalcommits.org/) specification:

- `feat:` - New features
- `fix:` - Bug fixes
- `docs:` - Documentation changes
- `style:` - Code style changes (formatting, etc.)
- `refactor:` - Code refactoring
- `test:` - Adding or updating tests
- `chore:` - Maintenance tasks

### 4. Push and Create Pull Request

```bash
git push origin feature/your-feature-name
```

Then create a Pull Request on GitHub with:
- Clear title and description
- Reference to any related issues
- Screenshots or examples if applicable

## Code Standards

### Python Code Style

- Follow PEP 8 guidelines
- Use type hints where appropriate
- Write clear, descriptive docstrings
- Keep functions and classes focused and single-purpose

Example:

```python
def execute_code(self, code: str, cache_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Execute Python code with enhanced performance and caching.
    
    Args:
        code: Python code to execute
        cache_key: Optional cache key for compilation caching
        
    Returns:
        Dictionary containing execution results with keys:
        - success: Boolean indicating success
        - stdout: Captured stdout
        - stderr: Captured stderr
        - execution_time: Time taken for execution
        - artifacts: List of created artifacts
        
    Raises:
        SandboxExecutionError: If execution fails
    """
```

### Testing

- Write tests for all new functionality
- Use descriptive test names
- Include both positive and negative test cases
- Test edge cases and error conditions

Example:

```python
def test_execute_code_with_caching(self):
    """Test that code execution uses caching correctly."""
    context = PersistentExecutionContext()
    
    # First execution should be cache miss
    result1 = context.execute_code("x = 42", cache_key="test")
    self.assertFalse(result1['cache_hit'])
    
    # Second execution should be cache hit
    result2 = context.execute_code("x = 42", cache_key="test")
    self.assertTrue(result2['cache_hit'])
```

### Documentation

- Update README.md for significant changes
- Add docstrings to all public methods and classes
- Include examples in documentation
- Update API documentation in `docs/api.md`

## Types of Contributions

### Bug Reports

When reporting bugs, please include:
- Python version
- Operating system
- Steps to reproduce
- Expected vs actual behavior
- Full error traceback
- Minimal code example

### Feature Requests

For feature requests, please:
- Describe the use case
- Explain why the feature would be valuable
- Provide examples of how it would be used
- Consider backward compatibility

### Code Contributions

We welcome contributions for:
- Bug fixes
- New features
- Performance improvements
- Documentation improvements
- Test coverage improvements

### Priority Areas

Current areas where contributions are especially welcome:
- Additional language support (beyond Python and Node.js)
- Enhanced security features
- Performance optimizations
- More comprehensive error handling
- Additional MCP tools
- Better artifact management

## Code Review Process

1. **Automated Checks**: All PRs run automated tests and linting
2. **Peer Review**: At least one maintainer will review your PR
3. **Discussion**: We may ask questions or request changes
4. **Approval**: Once approved, your PR will be merged

### Review Criteria

- Code quality and style
- Test coverage
- Documentation completeness
- Backward compatibility
- Performance impact
- Security considerations

## Development Tips

### Running Tests

```bash
# Run all tests
uv run pytest tests/

# Run specific test file
uv run pytest tests/test_integration.py

# Run with coverage
uv run pytest tests/ --cov=sandbox

# Run with verbose output
uv run pytest tests/ -v
```

### Debugging

```bash
# Run with debug logging
SANDBOX_LOG_LEVEL=DEBUG uv run sandbox-server-stdio

# Interactive debugging
python -c "
from sandbox import LocalSandbox
import asyncio

async def debug():
    sandbox = LocalSandbox(name='debug')
    await sandbox.start()
    # Your debugging code here
    await sandbox.stop()

asyncio.run(debug())
"
```

### Code Formatting

```bash
# Format code with black
black src tests

# Check style with flake8
flake8 src tests
```

## Getting Help

- **Documentation**: Check the `docs/` directory
- **Issues**: Search existing GitHub issues
- **Discussions**: Start a GitHub discussion for questions
- **Email**: Contact maintainers for sensitive issues

## License

By contributing to this project, you agree that your contributions will be licensed under the Apache License 2.0, the same license as the project.

## Recognition

Contributors will be recognized in:
- GitHub contributor list
- Release notes for significant contributions
- Project documentation

Thank you for helping make Sandbox MCP better!
