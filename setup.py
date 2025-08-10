"""Setup configuration for Ultimate Swiss Army Knife MCP Server."""

from setuptools import setup, find_packages
import os
from pathlib import Path

# Read the README file
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text() if (this_directory / "README.md").exists() else ""

# Read requirements from requirements.txt
def read_requirements():
    requirements_path = this_directory / "requirements.txt"
    if requirements_path.exists():
        with open(requirements_path) as f:
            return [line.strip() for line in f if line.strip() and not line.startswith("#")]
    return []

setup(
    name="swiss-sandbox",
    version="3.0.0",
    author="Swiss Sandbox Team",
    author_email="team@swiss-sandbox.dev",
    description="Swiss Sandbox (SS) - AI-powered development environment with intelligent task automation and code search",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/swiss-sandbox/swiss-sandbox",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.10",
    install_requires=read_requirements(),
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.21.0",
            "pytest-cov>=4.0.0",
            "black>=23.0.0",
            "ruff>=0.1.0",
            "mypy>=1.0.0",
        ],
        "ml": [
            "transformers>=4.30.0",
            "torch>=2.0.0",
            "torchvision>=0.15.0",
        ],
        "search": [
            "elasticsearch>=8.0.0",
            "pika>=1.3.0",
        ],
        "web": [
            "selenium>=4.0.0",
            "playwright>=1.30.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "swiss-sandbox=sandbox.ultimate.server:main",
            "ss-server=sandbox.ultimate.server:main",
            "ss-canvas=sandbox.ultimate.canvas_display:main",
            "ss-export=sandbox.ultimate.workspace_export:main",
        ],
    },
    include_package_data=True,
    package_data={
        "sandbox": [
            "templates/*.html",
            "templates/*.j2",
            "static/*.css",
            "static/*.js",
            "configs/*.yaml",
            "configs/*.json",
        ],
    },
    zip_safe=False,
)
