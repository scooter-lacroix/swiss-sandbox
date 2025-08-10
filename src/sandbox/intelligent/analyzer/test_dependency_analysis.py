"""
Unit tests for dependency analysis and mapping functionality.
"""

import os
import tempfile
import shutil
import json
from datetime import datetime
from unittest import TestCase

from ..workspace.models import SandboxWorkspace, IsolationConfig
from ..types import WorkspaceStatus
from .analyzer import CodebaseAnalyzer
from .models import DependencyGraph, DependencyInfo


class TestDependencyAnalysis(TestCase):
    """Test cases for dependency analysis and mapping."""
    
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
    
    def test_parse_package_json(self):
        """Test parsing of package.json dependencies."""
        package_json_content = json.dumps({
            "name": "test-project",
            "dependencies": {
                "react": "^18.0.0",
                "express": "^4.18.0"
            },
            "devDependencies": {
                "jest": "^28.0.0",
                "eslint": "^8.0.0"
            },
            "peerDependencies": {
                "react-dom": "^18.0.0"
            }
        })
        
        self._create_file("package.json", package_json_content)
        
        dependency_graph = self.analyzer.extract_dependencies(self.workspace)
        
        # Check that dependencies were found
        self.assertGreater(len(dependency_graph.dependencies), 0)
        self.assertIn("package.json", dependency_graph.dependency_files)
        
        # Check specific dependencies
        dep_names = [dep.name for dep in dependency_graph.dependencies]
        self.assertIn("react", dep_names)
        self.assertIn("express", dep_names)
        self.assertIn("jest", dep_names)
        self.assertIn("eslint", dep_names)
        self.assertIn("react-dom", dep_names)
        
        # Check dependency types
        react_dep = next(dep for dep in dependency_graph.dependencies if dep.name == "react")
        jest_dep = next(dep for dep in dependency_graph.dependencies if dep.name == "jest")
        react_dom_dep = next(dep for dep in dependency_graph.dependencies if dep.name == "react-dom")
        
        self.assertEqual(react_dep.type, "direct")
        self.assertEqual(jest_dep.type, "dev")
        self.assertEqual(react_dom_dep.type, "peer")
        self.assertEqual(react_dep.source, "npm")
    
    def test_parse_requirements_txt(self):
        """Test parsing of requirements.txt dependencies."""
        requirements_content = """
# This is a comment
Flask==2.0.0
Django>=3.2.0
requests~=2.25.0
pytest  # Another comment
-e git+https://github.com/user/repo.git#egg=package
"""
        
        self._create_file("requirements.txt", requirements_content)
        
        dependency_graph = self.analyzer.extract_dependencies(self.workspace)
        
        # Check that dependencies were found
        self.assertGreater(len(dependency_graph.dependencies), 0)
        self.assertIn("requirements.txt", dependency_graph.dependency_files)
        
        # Check specific dependencies
        dep_names = [dep.name for dep in dependency_graph.dependencies]
        self.assertIn("Flask", dep_names)
        self.assertIn("Django", dep_names)
        self.assertIn("requests", dep_names)
        self.assertIn("pytest", dep_names)
        
        # Check versions
        flask_dep = next(dep for dep in dependency_graph.dependencies if dep.name == "Flask")
        django_dep = next(dep for dep in dependency_graph.dependencies if dep.name == "Django")
        requests_dep = next(dep for dep in dependency_graph.dependencies if dep.name == "requests")
        pytest_dep = next(dep for dep in dependency_graph.dependencies if dep.name == "pytest")
        
        self.assertEqual(flask_dep.version, "==2.0.0")
        self.assertEqual(django_dep.version, ">=3.2.0")
        self.assertEqual(requests_dep.version, "~=2.25.0")
        self.assertEqual(pytest_dep.version, "*")
        self.assertEqual(flask_dep.source, "pip")
    
    def test_parse_pipfile(self):
        """Test parsing of Pipfile dependencies."""
        pipfile_content = """
[[source]]
url = "https://pypi.org/simple"
verify_ssl = true
name = "pypi"

[packages]
flask = "==2.0.0"
requests = "*"

[dev-packages]
pytest = "*"
black = "==21.0.0"

[requires]
python_version = "3.9"
"""
        
        self._create_file("Pipfile", pipfile_content)
        
        dependency_graph = self.analyzer.extract_dependencies(self.workspace)
        
        # Check that dependencies were found
        self.assertGreater(len(dependency_graph.dependencies), 0)
        self.assertIn("Pipfile", dependency_graph.dependency_files)
        
        # Check specific dependencies
        dep_names = [dep.name for dep in dependency_graph.dependencies]
        self.assertIn("flask", dep_names)
        self.assertIn("requests", dep_names)
        self.assertIn("pytest", dep_names)
        self.assertIn("black", dep_names)
        
        # Check dependency types
        flask_dep = next(dep for dep in dependency_graph.dependencies if dep.name == "flask")
        pytest_dep = next(dep for dep in dependency_graph.dependencies if dep.name == "pytest")
        
        self.assertEqual(flask_dep.type, "direct")
        self.assertEqual(pytest_dep.type, "dev")
    
    def test_parse_pyproject_toml(self):
        """Test parsing of pyproject.toml dependencies."""
        pyproject_content = """
[build-system]
requires = ["setuptools", "wheel"]

[project]
name = "test-project"
dependencies = [
    "flask>=2.0.0",
    "requests~=2.25.0"
]

[tool.poetry.dependencies]
python = "^3.9"
django = "^4.0.0"
celery = "^5.2.0"

[tool.poetry.dev-dependencies]
pytest = "^6.0.0"
"""
        
        self._create_file("pyproject.toml", pyproject_content)
        
        dependency_graph = self.analyzer.extract_dependencies(self.workspace)
        
        # Check that dependencies were found
        self.assertGreater(len(dependency_graph.dependencies), 0)
        self.assertIn("pyproject.toml", dependency_graph.dependency_files)
        
        # Check specific dependencies
        dep_names = [dep.name for dep in dependency_graph.dependencies]
        self.assertIn("flask", dep_names)
        self.assertIn("requests", dep_names)
        self.assertIn("django", dep_names)
        self.assertIn("celery", dep_names)
        
        # Python version should be excluded
        self.assertNotIn("python", dep_names)
    
    def test_parse_gemfile(self):
        """Test parsing of Gemfile dependencies."""
        gemfile_content = """
source 'https://rubygems.org'
git_source(:github) { |repo| "https://github.com/#{repo}.git" }

ruby '3.0.0'

gem 'rails', '~> 7.0.0'
gem 'sqlite3', '~> 1.4'
gem 'puma', '~> 5.0'
gem 'bootsnap', '>= 1.4.4', require: false

group :development, :test do
  gem 'byebug', platforms: [:mri, :mingw, :x64_mingw]
end
"""
        
        self._create_file("Gemfile", gemfile_content)
        
        dependency_graph = self.analyzer.extract_dependencies(self.workspace)
        
        # Check that dependencies were found
        self.assertGreater(len(dependency_graph.dependencies), 0)
        self.assertIn("Gemfile", dependency_graph.dependency_files)
        
        # Check specific dependencies
        dep_names = [dep.name for dep in dependency_graph.dependencies]
        self.assertIn("rails", dep_names)
        self.assertIn("sqlite3", dep_names)
        self.assertIn("puma", dep_names)
        self.assertIn("bootsnap", dep_names)
        self.assertIn("byebug", dep_names)
        
        # Check versions
        rails_dep = next(dep for dep in dependency_graph.dependencies if dep.name == "rails")
        self.assertEqual(rails_dep.version, "~> 7.0.0")
        self.assertEqual(rails_dep.source, "rubygems")
    
    def test_parse_cargo_toml(self):
        """Test parsing of Cargo.toml dependencies."""
        cargo_content = """
[package]
name = "test-project"
version = "0.1.0"
edition = "2021"

[dependencies]
serde = "1.0"
tokio = { version = "1.0", features = ["full"] }
reqwest = "0.11"

[dev-dependencies]
tokio-test = "0.4"
"""
        
        self._create_file("Cargo.toml", cargo_content)
        
        dependency_graph = self.analyzer.extract_dependencies(self.workspace)
        
        # Check that dependencies were found
        self.assertGreater(len(dependency_graph.dependencies), 0)
        self.assertIn("Cargo.toml", dependency_graph.dependency_files)
        
        # Check specific dependencies
        dep_names = [dep.name for dep in dependency_graph.dependencies]
        self.assertIn("serde", dep_names)
        self.assertIn("reqwest", dep_names)
        self.assertIn("tokio-test", dep_names)
        
        # Check dependency types
        serde_dep = next(dep for dep in dependency_graph.dependencies if dep.name == "serde")
        tokio_test_dep = next(dep for dep in dependency_graph.dependencies if dep.name == "tokio-test")
        
        self.assertEqual(serde_dep.type, "direct")
        self.assertEqual(tokio_test_dep.type, "dev")
        self.assertEqual(serde_dep.source, "crates.io")
    
    def test_parse_pom_xml(self):
        """Test parsing of pom.xml dependencies."""
        pom_content = """
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
    <modelVersion>4.0.0</modelVersion>
    
    <groupId>com.example</groupId>
    <artifactId>test-project</artifactId>
    <version>1.0.0</version>
    
    <dependencies>
        <dependency>
            <groupId>org.springframework</groupId>
            <artifactId>spring-core</artifactId>
            <version>5.3.0</version>
        </dependency>
        <dependency>
            <groupId>junit</groupId>
            <artifactId>junit</artifactId>
            <version>4.13.2</version>
            <scope>test</scope>
        </dependency>
        <dependency>
            <groupId>org.slf4j</groupId>
            <artifactId>slf4j-api</artifactId>
            <version>1.7.30</version>
        </dependency>
    </dependencies>
</project>
"""
        
        self._create_file("pom.xml", pom_content)
        
        dependency_graph = self.analyzer.extract_dependencies(self.workspace)
        
        # Check that dependencies were found
        self.assertGreater(len(dependency_graph.dependencies), 0)
        self.assertIn("pom.xml", dependency_graph.dependency_files)
        
        # Check specific dependencies
        dep_names = [dep.name for dep in dependency_graph.dependencies]
        self.assertIn("org.springframework:spring-core", dep_names)
        self.assertIn("junit:junit", dep_names)
        self.assertIn("org.slf4j:slf4j-api", dep_names)
        
        # Check dependency types
        spring_dep = next(dep for dep in dependency_graph.dependencies if dep.name == "org.springframework:spring-core")
        junit_dep = next(dep for dep in dependency_graph.dependencies if dep.name == "junit:junit")
        
        self.assertEqual(spring_dep.type, "direct")
        self.assertEqual(junit_dep.type, "dev")
        self.assertEqual(spring_dep.source, "maven")
    
    def test_parse_composer_json(self):
        """Test parsing of composer.json dependencies."""
        composer_content = json.dumps({
            "name": "test/project",
            "require": {
                "php": "^8.0",
                "laravel/framework": "^9.0",
                "guzzlehttp/guzzle": "^7.0"
            },
            "require-dev": {
                "phpunit/phpunit": "^9.0",
                "mockery/mockery": "^1.4"
            }
        })
        
        self._create_file("composer.json", composer_content)
        
        dependency_graph = self.analyzer.extract_dependencies(self.workspace)
        
        # Check that dependencies were found
        self.assertGreater(len(dependency_graph.dependencies), 0)
        self.assertIn("composer.json", dependency_graph.dependency_files)
        
        # Check specific dependencies
        dep_names = [dep.name for dep in dependency_graph.dependencies]
        self.assertIn("laravel/framework", dep_names)
        self.assertIn("guzzlehttp/guzzle", dep_names)
        self.assertIn("phpunit/phpunit", dep_names)
        self.assertIn("mockery/mockery", dep_names)
        
        # PHP version should be excluded
        self.assertNotIn("php", dep_names)
        
        # Check dependency types
        laravel_dep = next(dep for dep in dependency_graph.dependencies if dep.name == "laravel/framework")
        phpunit_dep = next(dep for dep in dependency_graph.dependencies if dep.name == "phpunit/phpunit")
        
        self.assertEqual(laravel_dep.type, "direct")
        self.assertEqual(phpunit_dep.type, "dev")
        self.assertEqual(laravel_dep.source, "packagist")
    
    def test_parse_go_mod(self):
        """Test parsing of go.mod dependencies."""
        go_mod_content = """
module example.com/test-project

go 1.19

require (
    github.com/gin-gonic/gin v1.8.1
    github.com/stretchr/testify v1.8.0
    golang.org/x/crypto v0.0.0-20220622213112-05595931fe9d
)

require github.com/gorilla/mux v1.8.0 // indirect
"""
        
        self._create_file("go.mod", go_mod_content)
        
        dependency_graph = self.analyzer.extract_dependencies(self.workspace)
        
        # Check that dependencies were found
        self.assertGreater(len(dependency_graph.dependencies), 0)
        self.assertIn("go.mod", dependency_graph.dependency_files)
        
        # Check specific dependencies
        dep_names = [dep.name for dep in dependency_graph.dependencies]
        self.assertIn("github.com/gin-gonic/gin", dep_names)
        self.assertIn("github.com/stretchr/testify", dep_names)
        self.assertIn("golang.org/x/crypto", dep_names)
        self.assertIn("github.com/gorilla/mux", dep_names)
        
        # Check versions
        gin_dep = next(dep for dep in dependency_graph.dependencies if dep.name == "github.com/gin-gonic/gin")
        self.assertEqual(gin_dep.version, "v1.8.1")
        self.assertEqual(gin_dep.source, "go")
    
    def test_dependency_conflict_detection(self):
        """Test detection of dependency conflicts."""
        # Create multiple files with conflicting versions
        package_json_content = json.dumps({
            "dependencies": {
                "lodash": "^4.17.0"
            }
        })
        
        requirements_content = "lodash==3.10.0"  # Different version of same package
        
        self._create_file("package.json", package_json_content)
        self._create_file("requirements.txt", requirements_content)
        
        dependency_graph = self.analyzer.extract_dependencies(self.workspace)
        
        # Should detect conflict
        self.assertGreater(len(dependency_graph.conflicts), 0)
        self.assertTrue(any("lodash" in conflict for conflict in dependency_graph.conflicts))
    
    def test_multiple_dependency_files(self):
        """Test parsing multiple dependency files in the same project."""
        # Create a polyglot project
        package_json_content = json.dumps({
            "dependencies": {"express": "^4.18.0"}
        })
        
        requirements_content = "flask==2.0.0"
        
        gemfile_content = "gem 'rails', '~> 7.0.0'"
        
        self._create_file("package.json", package_json_content)
        self._create_file("requirements.txt", requirements_content)
        self._create_file("Gemfile", gemfile_content)
        
        dependency_graph = self.analyzer.extract_dependencies(self.workspace)
        
        # Should find all dependency files
        self.assertEqual(len(dependency_graph.dependency_files), 3)
        self.assertIn("package.json", dependency_graph.dependency_files)
        self.assertIn("requirements.txt", dependency_graph.dependency_files)
        self.assertIn("Gemfile", dependency_graph.dependency_files)
        
        # Should find dependencies from all files
        dep_names = [dep.name for dep in dependency_graph.dependencies]
        self.assertIn("express", dep_names)
        self.assertIn("flask", dep_names)
        self.assertIn("rails", dep_names)
        
        # Should have different sources
        sources = {dep.source for dep in dependency_graph.dependencies}
        self.assertIn("npm", sources)
        self.assertIn("pip", sources)
        self.assertIn("rubygems", sources)
    
    def test_empty_project_dependencies(self):
        """Test dependency analysis on project with no dependencies."""
        # Create a project with no dependency files
        self._create_file("main.py", "print('hello world')")
        
        dependency_graph = self.analyzer.extract_dependencies(self.workspace)
        
        # Should return empty dependency graph
        self.assertEqual(len(dependency_graph.dependencies), 0)
        self.assertEqual(len(dependency_graph.dependency_files), 0)
        self.assertEqual(len(dependency_graph.conflicts), 0)
    
    def test_malformed_dependency_files(self):
        """Test handling of malformed dependency files."""
        # Create malformed files
        self._create_file("package.json", "{ invalid json")
        self._create_file("requirements.txt", "valid-package==1.0.0\n# This is fine")
        
        dependency_graph = self.analyzer.extract_dependencies(self.workspace)
        
        # Should parse valid files and skip invalid ones
        self.assertIn("requirements.txt", dependency_graph.dependency_files)
        self.assertNotIn("package.json", dependency_graph.dependency_files)
        
        # Should find dependencies from valid files
        dep_names = [dep.name for dep in dependency_graph.dependencies]
        self.assertIn("valid-package", dep_names)
    
    def test_dependency_graph_get_by_name(self):
        """Test the get_by_name method of DependencyGraph."""
        package_json_content = json.dumps({
            "dependencies": {"react": "^18.0.0"}
        })
        
        self._create_file("package.json", package_json_content)
        
        dependency_graph = self.analyzer.extract_dependencies(self.workspace)
        
        # Test get_by_name method
        react_dep = dependency_graph.get_by_name("react")
        self.assertIsNotNone(react_dep)
        self.assertEqual(react_dep.name, "react")
        self.assertEqual(react_dep.version, "^18.0.0")
        
        # Test non-existent dependency
        non_existent = dependency_graph.get_by_name("non-existent")
        self.assertIsNone(non_existent)


if __name__ == '__main__':
    import unittest
    unittest.main()