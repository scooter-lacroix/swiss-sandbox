#!/bin/bash
# Swiss Sandbox (SS) Test Runner
# Ensures all dependencies are properly configured

echo "=========================================="
echo "Swiss Sandbox (SS) - Test Runner"
echo "=========================================="

# Ensure Zoekt is in PATH
export PATH="/home/stan/go/bin:$PATH"

# Verify Zoekt is accessible
if ! command -v zoekt-index &> /dev/null; then
    echo "ERROR: zoekt-index not found in PATH"
    echo "PATH is: $PATH"
    exit 1
fi

if ! command -v zoekt &> /dev/null; then
    echo "ERROR: zoekt not found in PATH"
    echo "PATH is: $PATH"
    exit 1
fi

echo "✓ Zoekt tools found in PATH"

# Check Docker
if command -v docker &> /dev/null; then
    echo "✓ Docker command available"
    docker --version
else
    echo "⚠ Docker command not found"
fi

# Activate virtual environment if not already active
if [[ "$VIRTUAL_ENV" != "" ]]; then
    echo "✓ Virtual environment already active: $VIRTUAL_ENV"
else
    if [ -f ".venv/bin/activate" ]; then
        source .venv/bin/activate
        echo "✓ Virtual environment activated"
    else
        echo "⚠ Virtual environment not found"
    fi
fi

# Run the tests
echo ""
echo "Running comprehensive E2E tests..."
echo "=========================================="

# Use the venv Python explicitly
.venv/bin/python tests/test_swiss_sandbox_e2e.py "$@"

exit_code=$?

if [ $exit_code -eq 0 ]; then
    echo ""
    echo "=========================================="
    echo "✅ All tests passed successfully!"
    echo "=========================================="
else
    echo ""
    echo "=========================================="
    echo "❌ Some tests failed. Exit code: $exit_code"
    echo "=========================================="
fi

exit $exit_code
