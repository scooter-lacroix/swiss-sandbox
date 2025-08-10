"""
Unit tests for pattern recognition and metrics collection functionality.
"""

import os
import tempfile
import shutil
from datetime import datetime
from unittest import TestCase

from ..workspace.models import SandboxWorkspace, IsolationConfig
from ..types import WorkspaceStatus
from .analyzer import CodebaseAnalyzer
from .models import CodebaseStructure, Pattern, CodeMetrics


class TestPatternRecognitionAndMetrics(TestCase):
    """Test cases for pattern recognition and metrics collection."""
    
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
    
    def test_mvc_pattern_detection(self):
        """Test detection of MVC architectural pattern."""
        # Create MVC structure
        self._create_file("models/user.py", "class User: pass")
        self._create_file("views/user_view.py", "def user_view(): pass")
        self._create_file("controllers/user_controller.py", "def user_controller(): pass")
        
        structure = self.analyzer.analyze_structure(self.workspace)
        patterns = self.analyzer.identify_patterns(structure)
        
        # Should detect MVC pattern
        mvc_patterns = [p for p in patterns if "MVC" in p.name]
        self.assertEqual(len(mvc_patterns), 1)
        
        mvc_pattern = mvc_patterns[0]
        self.assertEqual(mvc_pattern.type, "architectural")
        self.assertGreater(mvc_pattern.confidence, 0.5)
        self.assertIn("Model-View-Controller", mvc_pattern.description)
    
    def test_microservices_pattern_detection(self):
        """Test detection of microservices architectural pattern."""
        # Create microservices structure
        self._create_file("services/user_service.py", "class UserService: pass")
        self._create_file("services/order_service.py", "class OrderService: pass")
        self._create_file("docker-compose.yml", "version: '3'")
        self._create_file("api/user_api.py", "def user_api(): pass")
        
        structure = self.analyzer.analyze_structure(self.workspace)
        patterns = self.analyzer.identify_patterns(structure)
        
        # Should detect microservices pattern
        microservice_patterns = [p for p in patterns if "Microservices" in p.name]
        self.assertEqual(len(microservice_patterns), 1)
        
        microservice_pattern = microservice_patterns[0]
        self.assertEqual(microservice_pattern.type, "architectural")
        self.assertGreater(microservice_pattern.confidence, 0.0)
    
    def test_layered_architecture_detection(self):
        """Test detection of layered architecture pattern."""
        # Create layered structure
        self._create_file("presentation/ui.py", "class UI: pass")
        self._create_file("business/logic.py", "class BusinessLogic: pass")
        self._create_file("data/repository.py", "class Repository: pass")
        self._create_file("service/user_service.py", "class UserService: pass")
        
        structure = self.analyzer.analyze_structure(self.workspace)
        patterns = self.analyzer.identify_patterns(structure)
        
        # Should detect layered architecture
        layered_patterns = [p for p in patterns if "Layered Architecture" in p.name]
        self.assertEqual(len(layered_patterns), 1)
        
        layered_pattern = layered_patterns[0]
        self.assertEqual(layered_pattern.type, "architectural")
        self.assertGreater(layered_pattern.confidence, 0.0)
    
    def test_rest_api_pattern_detection(self):
        """Test detection of REST API pattern."""
        # Create REST API structure
        self._create_file("api/users.py", "def get_users(): pass")
        self._create_file("routes.py", "from flask import Flask")
        self._create_file("endpoints/auth.py", "def login(): pass")
        
        structure = self.analyzer.analyze_structure(self.workspace)
        patterns = self.analyzer.identify_patterns(structure)
        
        # Should detect REST API pattern
        rest_patterns = [p for p in patterns if "REST API" in p.name]
        self.assertEqual(len(rest_patterns), 1)
        
        rest_pattern = rest_patterns[0]
        self.assertEqual(rest_pattern.type, "architectural")
        self.assertGreater(rest_pattern.confidence, 0.0)
    
    def test_repository_pattern_detection(self):
        """Test detection of repository design pattern."""
        # Create repository structure
        self._create_file("repository/user_repository.py", "class UserRepository: pass")
        self._create_file("repositories/order_repo.py", "class OrderRepo: pass")
        
        structure = self.analyzer.analyze_structure(self.workspace)
        patterns = self.analyzer.identify_patterns(structure)
        
        # Should detect repository pattern
        repo_patterns = [p for p in patterns if "Repository Pattern" in p.name]
        self.assertEqual(len(repo_patterns), 1)
        
        repo_pattern = repo_patterns[0]
        self.assertEqual(repo_pattern.type, "design")
        self.assertGreater(repo_pattern.confidence, 0.0)
    
    def test_factory_pattern_detection(self):
        """Test detection of factory design pattern."""
        # Create factory structure
        self._create_file("factory/user_factory.py", "class UserFactory: pass")
        self._create_file("factories.py", "def create_user(): pass")
        
        structure = self.analyzer.analyze_structure(self.workspace)
        patterns = self.analyzer.identify_patterns(structure)
        
        # Should detect factory pattern
        factory_patterns = [p for p in patterns if "Factory Pattern" in p.name]
        self.assertEqual(len(factory_patterns), 1)
        
        factory_pattern = factory_patterns[0]
        self.assertEqual(factory_pattern.type, "design")
        self.assertGreater(factory_pattern.confidence, 0.0)
    
    def test_observer_pattern_detection(self):
        """Test detection of observer design pattern."""
        # Create observer structure
        self._create_file("observer.py", "class Observer: pass")
        self._create_file("events.py", "class EventManager: pass")
        
        structure = self.analyzer.analyze_structure(self.workspace)
        patterns = self.analyzer.identify_patterns(structure)
        
        # Should detect observer pattern
        observer_patterns = [p for p in patterns if "Observer Pattern" in p.name]
        self.assertEqual(len(observer_patterns), 1)
        
        observer_pattern = observer_patterns[0]
        self.assertEqual(observer_pattern.type, "design")
        self.assertGreater(observer_pattern.confidence, 0.0)
    
    def test_feature_based_organization_detection(self):
        """Test detection of feature-based organization pattern."""
        # Create feature-based structure
        self._create_file("features/user/user.py", "class User: pass")
        self._create_file("features/order/order.py", "class Order: pass")
        self._create_file("modules/auth/auth.py", "def authenticate(): pass")
        
        structure = self.analyzer.analyze_structure(self.workspace)
        patterns = self.analyzer.identify_patterns(structure)
        
        # Should detect feature-based organization
        feature_patterns = [p for p in patterns if "Feature-based Organization" in p.name]
        self.assertEqual(len(feature_patterns), 1)
        
        feature_pattern = feature_patterns[0]
        self.assertEqual(feature_pattern.type, "organization")
        self.assertGreater(feature_pattern.confidence, 0.0)
    
    def test_tdd_pattern_detection(self):
        """Test detection of test-driven development pattern."""
        # Create structure with many test directories
        self._create_file("src/main.py", "def main(): pass")
        self._create_file("tests/test_main.py", "def test_main(): pass")
        self._create_file("spec/main_spec.py", "def test_main_spec(): pass")
        self._create_file("__tests__/main.test.js", "test('main', () => {});")
        
        structure = self.analyzer.analyze_structure(self.workspace)
        patterns = self.analyzer.identify_patterns(structure)
        
        # Should detect TDD pattern
        tdd_patterns = [p for p in patterns if "Test-driven Development" in p.name]
        self.assertEqual(len(tdd_patterns), 1)
        
        tdd_pattern = tdd_patterns[0]
        self.assertEqual(tdd_pattern.type, "organization")
        self.assertGreater(tdd_pattern.confidence, 0.0)
    
    def test_configuration_management_detection(self):
        """Test detection of configuration management pattern."""
        # Create multiple config files
        self._create_file("config.yaml", "debug: true")
        self._create_file("settings.json", "{}")
        self._create_file(".env", "NODE_ENV=development")
        self._create_file("docker-compose.yml", "version: '3'")
        self._create_file("package.json", "{}")
        
        structure = self.analyzer.analyze_structure(self.workspace)
        patterns = self.analyzer.identify_patterns(structure)
        
        # Should detect configuration management
        config_patterns = [p for p in patterns if "Configuration Management" in p.name]
        self.assertEqual(len(config_patterns), 1)
        
        config_pattern = config_patterns[0]
        self.assertEqual(config_pattern.type, "organization")
        self.assertGreater(config_pattern.confidence, 0.0)
    
    def test_basic_metrics_calculation(self):
        """Test basic code metrics calculation."""
        # Create files with different complexities
        simple_code = """
def simple_function():
    return "hello"
"""
        
        complex_code = """
def complex_function(x, y):
    if x > 0:
        if y > 0:
            for i in range(x):
                if i % 2 == 0:
                    while i < y:
                        i += 1
                        if i > 10:
                            break
                elif i % 3 == 0:
                    continue
    return x + y
"""
        
        self._create_file("simple.py", simple_code)
        self._create_file("complex.py", complex_code)
        self._create_file("test_simple.py", "def test_simple(): pass")
        
        metrics = self.analyzer.calculate_metrics(self.workspace)
        
        # Check basic metrics
        self.assertGreater(metrics.lines_of_code, 0)
        self.assertGreater(metrics.cyclomatic_complexity, 1.0)  # Should be > 1 due to complex code
        self.assertGreaterEqual(metrics.maintainability_index, 0)
        self.assertGreater(metrics.test_coverage, 0)  # Should detect test file
        self.assertGreaterEqual(metrics.technical_debt_ratio, 0)
        self.assertGreaterEqual(metrics.duplication_percentage, 0)
        
        # Check file-level metrics
        self.assertIn("simple.py", metrics.metrics_by_file)
        self.assertIn("complex.py", metrics.metrics_by_file)
        self.assertIn("test_simple.py", metrics.metrics_by_file)
        
        # Complex file should have higher complexity
        simple_complexity = metrics.metrics_by_file["simple.py"]["cyclomatic_complexity"]
        complex_complexity = metrics.metrics_by_file["complex.py"]["cyclomatic_complexity"]
        self.assertGreater(complex_complexity, simple_complexity)
    
    def test_cyclomatic_complexity_by_language(self):
        """Test cyclomatic complexity calculation for different languages."""
        # Python code
        python_code = """
def test_function(x):
    if x > 0:
        for i in range(x):
            if i % 2 == 0 and i > 5:
                return i
    return 0
"""
        
        # JavaScript code
        js_code = """
function testFunction(x) {
    if (x > 0) {
        for (let i = 0; i < x; i++) {
            if (i % 2 === 0 && i > 5) {
                return i;
            }
        }
    }
    return 0;
}
"""
        
        self._create_file("test.py", python_code)
        self._create_file("test.js", js_code)
        
        metrics = self.analyzer.calculate_metrics(self.workspace)
        
        # Both files should have similar complexity
        py_complexity = metrics.metrics_by_file["test.py"]["cyclomatic_complexity"]
        js_complexity = metrics.metrics_by_file["test.js"]["cyclomatic_complexity"]
        
        self.assertGreater(py_complexity, 1.0)
        self.assertGreater(js_complexity, 1.0)
    
    def test_test_file_detection(self):
        """Test detection of test files for coverage calculation."""
        # Create various test files
        self._create_file("main.py", "def main(): pass")
        self._create_file("test_main.py", "def test_main(): pass")
        self._create_file("main_test.py", "def test_main(): pass")
        self._create_file("spec/main.spec.js", "test('main', () => {});")
        self._create_file("__tests__/main.test.js", "test('main', () => {});")
        
        metrics = self.analyzer.calculate_metrics(self.workspace)
        
        # Should detect test files and calculate coverage
        self.assertGreater(metrics.test_coverage, 0)
        
        # Test files should be identified correctly
        self.assertTrue(self.analyzer._is_test_file("test_main.py"))
        self.assertTrue(self.analyzer._is_test_file("main_test.py"))
        self.assertTrue(self.analyzer._is_test_file("spec/main.spec.js"))
        self.assertTrue(self.analyzer._is_test_file("__tests__/main.test.js"))
        self.assertFalse(self.analyzer._is_test_file("main.py"))
    
    def test_empty_project_metrics(self):
        """Test metrics calculation for empty project."""
        # Create empty project
        metrics = self.analyzer.calculate_metrics(self.workspace)
        
        # Should return zero metrics
        self.assertEqual(metrics.lines_of_code, 0)
        self.assertEqual(metrics.cyclomatic_complexity, 0.0)
        self.assertEqual(metrics.test_coverage, 0.0)
        self.assertEqual(metrics.technical_debt_ratio, 0.0)
        self.assertEqual(len(metrics.metrics_by_file), 0)
    
    def test_no_patterns_detected(self):
        """Test pattern detection when no clear patterns exist."""
        # Create simple structure without clear patterns
        self._create_file("main.py", "print('hello')")
        self._create_file("utils.py", "def helper(): pass")
        
        structure = self.analyzer.analyze_structure(self.workspace)
        patterns = self.analyzer.identify_patterns(structure)
        
        # Should detect few or no patterns
        self.assertLessEqual(len(patterns), 2)  # Maybe config management if any config files
    
    def test_multiple_patterns_detection(self):
        """Test detection of multiple patterns in the same project."""
        # Create a complex project with multiple patterns
        self._create_file("models/user.py", "class User: pass")
        self._create_file("views/user_view.py", "def user_view(): pass")
        self._create_file("controllers/user_controller.py", "def user_controller(): pass")
        self._create_file("repository/user_repository.py", "class UserRepository: pass")
        self._create_file("factory/user_factory.py", "class UserFactory: pass")
        self._create_file("api/users.py", "def get_users(): pass")
        self._create_file("features/auth/auth.py", "def authenticate(): pass")
        self._create_file("tests/test_user.py", "def test_user(): pass")
        self._create_file("config.yaml", "debug: true")
        self._create_file("package.json", "{}")
        self._create_file(".env", "NODE_ENV=development")
        
        structure = self.analyzer.analyze_structure(self.workspace)
        patterns = self.analyzer.identify_patterns(structure)
        
        # Should detect multiple patterns
        self.assertGreaterEqual(len(patterns), 5)
        
        # Check for specific patterns
        pattern_names = [p.name for p in patterns]
        self.assertTrue(any("MVC" in name for name in pattern_names))
        self.assertTrue(any("Repository Pattern" in name for name in pattern_names))
        self.assertTrue(any("Factory Pattern" in name for name in pattern_names))
        self.assertTrue(any("REST API" in name for name in pattern_names))
        self.assertTrue(any("Feature-based Organization" in name for name in pattern_names))


if __name__ == '__main__':
    import unittest
    unittest.main()