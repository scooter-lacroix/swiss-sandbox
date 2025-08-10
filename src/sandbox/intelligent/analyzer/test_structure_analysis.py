"""
Unit tests for structure analysis and language detection functionality.
"""

import os
import tempfile
import shutil
import json
from datetime import datetime
from unittest import TestCase
from unittest.mock import Mock, patch

from ..workspace.models import SandboxWorkspace, IsolationConfig
from ..types import WorkspaceStatus
from .analyzer import CodebaseAnalyzer
from .models import CodebaseStructure


class TestStructureAnalysis(TestCase):
    """Test cases for codebase structure analysis."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.analyzer = CodebaseAnalyzer()
        self.temp_dir = tempfile.mkdtemp()
        
        # Create a mock workspace
        self.workspace = SandboxWorkspace(
            id="test-workspace",
            source_path="/original/path",
            sandbox_path=self.temp_dir,
            isolation_config=IsolationConfig(),
            created_at=datetime.now(),
            status=WorkspaceStatus.ACTIVE
        )
    
    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def _create_file(self, relative_path: str, content: str = ""):
        """Helper to create a file in the temp directory."""
        full_path = os.path.join(self.temp_dir, relative_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(content)
    
    def test_language_detection_python(self):
        """Test detection of Python language."""
        # Create Python files
        self._create_file("main.py", "print('hello')")
        self._create_file("utils.py", "def helper(): pass")
        self._create_file("tests/test_main.py", "import unittest")
        
        structure = self.analyzer.analyze_structure(self.workspace)
        
        self.assertIn('python', structure.languages)
        self.assertEqual(structure.languages[0], 'python')  # Should be first due to frequency
    
    def test_language_detection_javascript(self):
        """Test detection of JavaScript language."""
        # Create JavaScript files
        self._create_file("index.js", "console.log('hello');")
        self._create_file("app.js", "const express = require('express');")
        self._create_file("src/component.jsx", "import React from 'react';")
        
        structure = self.analyzer.analyze_structure(self.workspace)
        
        self.assertIn('javascript', structure.languages)
    
    def test_language_detection_multiple(self):
        """Test detection of multiple languages."""
        # Create files in different languages
        self._create_file("main.py", "print('hello')")
        self._create_file("app.js", "console.log('hello');")
        self._create_file("style.css", "body { margin: 0; }")
        self._create_file("README.md", "# Project")
        
        structure = self.analyzer.analyze_structure(self.workspace)
        
        self.assertIn('python', structure.languages)
        self.assertIn('javascript', structure.languages)
        self.assertIn('css', structure.languages)
        self.assertIn('markdown', structure.languages)
    
    def test_framework_detection_react(self):
        """Test detection of React framework."""
        # Create React project structure
        self._create_file("package.json", json.dumps({
            "dependencies": {"react": "^18.0.0", "react-dom": "^18.0.0"}
        }))
        self._create_file("src/App.jsx", "import React from 'react';")
        self._create_file("public/index.html", "<div id='root'></div>")
        
        structure = self.analyzer.analyze_structure(self.workspace)
        
        self.assertIn('react', structure.frameworks)
    
    def test_framework_detection_django(self):
        """Test detection of Django framework."""
        # Create Django project structure
        self._create_file("manage.py", "#!/usr/bin/env python")
        self._create_file("settings.py", "DEBUG = True")
        self._create_file("urls.py", "urlpatterns = []")
        
        structure = self.analyzer.analyze_structure(self.workspace)
        
        self.assertIn('django', structure.frameworks)
    
    def test_framework_detection_express(self):
        """Test detection of Express.js framework."""
        # Create Express project structure
        self._create_file("package.json", json.dumps({
            "dependencies": {"express": "^4.18.0"}
        }))
        self._create_file("app.js", "const express = require('express');")
        
        structure = self.analyzer.analyze_structure(self.workspace)
        
        self.assertIn('express', structure.frameworks)
    
    def test_entry_point_detection(self):
        """Test detection of entry points."""
        # Create various entry point files
        self._create_file("main.py", "if __name__ == '__main__':")
        self._create_file("app.js", "const app = express();")
        self._create_file("src/index.ts", "console.log('start');")
        
        structure = self.analyzer.analyze_structure(self.workspace)
        
        self.assertIn("main.py", structure.entry_points)
        self.assertIn("app.js", structure.entry_points)
    
    def test_test_directory_detection(self):
        """Test detection of test directories."""
        # Create test files and directories
        self._create_file("tests/test_main.py", "import unittest")
        self._create_file("spec/app.spec.js", "describe('app', () => {});")
        self._create_file("src/__tests__/component.test.js", "test('component', () => {});")
        
        structure = self.analyzer.analyze_structure(self.workspace)
        
        self.assertIn("tests", structure.test_directories)
        self.assertIn("spec", structure.test_directories)
        self.assertIn("src/__tests__", structure.test_directories)
    
    def test_config_file_detection(self):
        """Test detection of configuration files."""
        # Create various config files
        self._create_file("package.json", "{}")
        self._create_file("requirements.txt", "flask==2.0.0")
        self._create_file("config.yaml", "debug: true")
        self._create_file(".env", "NODE_ENV=development")
        self._create_file("Dockerfile", "FROM ubuntu:20.04")
        
        structure = self.analyzer.analyze_structure(self.workspace)
        
        self.assertIn("package.json", structure.config_files)
        self.assertIn("requirements.txt", structure.config_files)
        self.assertIn("config.yaml", structure.config_files)
        self.assertIn(".env", structure.config_files)
        self.assertIn("Dockerfile", structure.config_files)
    
    def test_documentation_file_detection(self):
        """Test detection of documentation files."""
        # Create documentation files
        self._create_file("README.md", "# Project Documentation")
        self._create_file("CHANGELOG.md", "## Version 1.0.0")
        self._create_file("LICENSE", "MIT License")
        self._create_file("docs/api.md", "# API Documentation")
        
        structure = self.analyzer.analyze_structure(self.workspace)
        
        self.assertIn("README.md", structure.documentation_files)
        self.assertIn("CHANGELOG.md", structure.documentation_files)
        self.assertIn("LICENSE", structure.documentation_files)
        self.assertIn("docs/api.md", structure.documentation_files)
    
    def test_file_tree_structure(self):
        """Test file tree building."""
        # Create a nested directory structure
        self._create_file("main.py", "")
        self._create_file("src/app.py", "")
        self._create_file("src/utils/helper.py", "")
        self._create_file("tests/test_app.py", "")
        
        structure = self.analyzer.analyze_structure(self.workspace)
        
        # Check file tree structure
        self.assertIn("main.py", structure.file_tree)
        self.assertIn("src", structure.file_tree)
        self.assertIn("app.py", structure.file_tree["src"])
        self.assertIn("utils", structure.file_tree["src"])
        self.assertIn("helper.py", structure.file_tree["src"]["utils"])
        self.assertIn("tests", structure.file_tree)
        self.assertIn("test_app.py", structure.file_tree["tests"])
    
    def test_ignore_hidden_files(self):
        """Test that hidden files and directories are ignored."""
        # Create hidden files and directories
        self._create_file(".hidden_file", "")
        self._create_file(".git/config", "")
        self._create_file("node_modules/package/index.js", "")
        self._create_file("__pycache__/module.pyc", "")
        self._create_file("regular_file.py", "")
        
        structure = self.analyzer.analyze_structure(self.workspace)
        
        # Hidden files should be ignored
        self.assertNotIn(".hidden_file", structure.file_tree)
        self.assertNotIn(".git", structure.file_tree)
        self.assertNotIn("node_modules", structure.file_tree)
        self.assertNotIn("__pycache__", structure.file_tree)
        
        # Regular files should be included
        self.assertIn("regular_file.py", structure.file_tree)
    
    def test_empty_directory_handling(self):
        """Test handling of empty directories."""
        # Create an empty workspace
        structure = self.analyzer.analyze_structure(self.workspace)
        
        self.assertEqual(structure.root_path, self.temp_dir)
        self.assertEqual(structure.languages, [])
        self.assertEqual(structure.frameworks, [])
        self.assertEqual(structure.file_tree, {})
        self.assertEqual(structure.entry_points, [])
        self.assertEqual(structure.test_directories, [])
        self.assertEqual(structure.config_files, [])
        self.assertEqual(structure.documentation_files, [])
    
    def test_special_files_without_extensions(self):
        """Test detection of special files without extensions."""
        # Create special files
        self._create_file("Dockerfile", "FROM ubuntu:20.04")
        self._create_file("Makefile", "all:\n\techo 'build'")
        self._create_file("Gemfile", "gem 'rails'")
        
        structure = self.analyzer.analyze_structure(self.workspace)
        
        self.assertIn('dockerfile', structure.languages)
        self.assertIn('make', structure.languages)
        self.assertIn('ruby', structure.languages)
    
    def test_complex_project_structure(self):
        """Test analysis of a complex project structure."""
        # Create a complex project with multiple languages and frameworks
        self._create_file("package.json", json.dumps({
            "dependencies": {"react": "^18.0.0", "express": "^4.18.0"}
        }))
        self._create_file("src/App.jsx", "import React from 'react';")
        self._create_file("server/app.js", "const express = require('express');")
        self._create_file("api/main.py", "from flask import Flask")
        self._create_file("requirements.txt", "flask==2.0.0")
        self._create_file("tests/test_api.py", "import unittest")
        self._create_file("__tests__/App.test.js", "test('App', () => {});")
        self._create_file("README.md", "# Full Stack App")
        self._create_file("docker-compose.yml", "version: '3'")
        
        structure = self.analyzer.analyze_structure(self.workspace)
        
        # Should detect multiple languages
        self.assertIn('javascript', structure.languages)
        self.assertIn('python', structure.languages)
        
        # Should detect multiple frameworks
        self.assertIn('react', structure.frameworks)
        self.assertIn('express', structure.frameworks)
        self.assertIn('docker', structure.frameworks)
        
        # Should find entry points
        self.assertTrue(any('app.js' in ep for ep in structure.entry_points))
        self.assertTrue(any('main.py' in ep for ep in structure.entry_points))
        
        # Should find test directories
        self.assertIn('tests', structure.test_directories)
        self.assertIn('__tests__', structure.test_directories)
        
        # Should find config files
        self.assertIn('package.json', structure.config_files)
        self.assertIn('requirements.txt', structure.config_files)
        self.assertIn('docker-compose.yml', structure.config_files)
        
        # Should find documentation
        self.assertIn('README.md', structure.documentation_files)


if __name__ == '__main__':
    import unittest
    unittest.main()