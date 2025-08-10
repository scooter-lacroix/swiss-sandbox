"""
Concrete implementation of codebase analysis functionality.
"""

import os
import re
import math
from pathlib import Path
from typing import List, Dict, Any, Set
from collections import defaultdict
from ..workspace.models import SandboxWorkspace
from .interfaces import CodebaseAnalyzerInterface
from .models import (
    CodebaseAnalysis, CodebaseStructure, DependencyGraph, DependencyInfo,
    Pattern, CodeMetrics
)


class CodebaseAnalyzer(CodebaseAnalyzerInterface):
    """
    Concrete implementation of codebase analysis with structure understanding,
    pattern recognition, and dependency mapping.
    """
    
    # Language detection patterns
    LANGUAGE_EXTENSIONS = {
        'python': ['.py', '.pyx', '.pyi'],
        'javascript': ['.js', '.jsx', '.mjs'],
        'typescript': ['.ts', '.tsx'],
        'java': ['.java'],
        'c': ['.c', '.h'],
        'cpp': ['.cpp', '.cxx', '.cc', '.hpp', '.hxx'],
        'csharp': ['.cs'],
        'go': ['.go'],
        'rust': ['.rs'],
        'php': ['.php'],
        'ruby': ['.rb'],
        'swift': ['.swift'],
        'kotlin': ['.kt', '.kts'],
        'scala': ['.scala'],
        'r': ['.r', '.R'],
        'matlab': ['.m'],
        'shell': ['.sh', '.bash', '.zsh'],
        'powershell': ['.ps1'],
        'sql': ['.sql'],
        'html': ['.html', '.htm'],
        'css': ['.css', '.scss', '.sass', '.less'],
        'xml': ['.xml'],
        'json': ['.json'],
        'yaml': ['.yml', '.yaml'],
        'markdown': ['.md', '.markdown'],
        'dockerfile': ['Dockerfile', 'dockerfile'],
    }
    
    # Framework detection patterns
    FRAMEWORK_INDICATORS = {
        'react': ['package.json', 'src/App.js', 'src/App.jsx', 'src/App.tsx', 'public/index.html'],
        'vue': ['package.json', 'src/App.vue', 'vue.config.js'],
        'angular': ['package.json', 'angular.json', 'src/app/app.module.ts'],
        'django': ['manage.py', 'settings.py', 'urls.py', 'wsgi.py'],
        'flask': ['app.py', 'application.py', 'run.py'],
        'fastapi': ['main.py', 'app.py'],
        'express': ['package.json', 'app.js', 'server.js'],
        'spring': ['pom.xml', 'build.gradle', 'src/main/java'],
        'rails': ['Gemfile', 'config/application.rb', 'app/controllers'],
        'laravel': ['composer.json', 'artisan', 'app/Http/Controllers'],
        'nextjs': ['package.json', 'next.config.js', 'pages/'],
        'nuxt': ['package.json', 'nuxt.config.js', 'pages/'],
        'gatsby': ['package.json', 'gatsby-config.js'],
        'svelte': ['package.json', 'svelte.config.js'],
        'electron': ['package.json', 'main.js', 'src/main.js'],
        'react-native': ['package.json', 'App.js', 'App.tsx', 'android/', 'ios/'],
        'flutter': ['pubspec.yaml', 'lib/main.dart'],
        'unity': ['Assets/', 'ProjectSettings/', '*.unity'],
        'docker': ['Dockerfile', 'docker-compose.yml', 'docker-compose.yaml'],
        'kubernetes': ['*.yaml', '*.yml', 'kustomization.yaml'],
    }
    
    # Common config file patterns
    CONFIG_PATTERNS = [
        r'.*\.config\.(js|ts|json|yaml|yml)$',
        r'.*\.conf$',
        r'.*\.ini$',
        r'.*\.toml$',
        r'.*\.properties$',
        r'.*\.ya?ml$',
        r'package\.json$',
        r'requirements\.txt$',
        r'Pipfile$',
        r'poetry\.lock$',
        r'pyproject\.toml$',
        r'Gemfile$',
        r'Cargo\.toml$',
        r'pom\.xml$',
        r'build\.gradle$',
        r'composer\.json$',
        r'\.env.*$',
        r'Dockerfile$',
        r'docker-compose\.ya?ml$',
        r'\.gitignore$',
        r'\.gitattributes$',
        r'README\.md$',
        r'LICENSE$',
        r'CHANGELOG\.md$',
    ]
    
    # Test directory patterns
    TEST_PATTERNS = [
        r'.*test.*',
        r'.*spec.*',
        r'.*__tests__.*',
        r'.*\.test\..*',
        r'.*\.spec\..*',
    ]
    
    # Documentation patterns
    DOC_PATTERNS = [
        r'.*README.*',
        r'.*CHANGELOG.*',
        r'.*LICENSE.*',
        r'.*CONTRIBUTING.*',
        r'.*docs?/.*',
        r'.*documentation/.*',
        r'.*\.md$',
        r'.*\.rst$',
        r'.*\.txt$',
    ]
    
    def analyze_structure(self, workspace: SandboxWorkspace) -> CodebaseStructure:
        """Analyze the structure of the codebase."""
        root_path = workspace.sandbox_path
        
        # Build file tree and collect file information
        file_tree = self._build_file_tree(root_path)
        all_files = self._get_all_files(root_path)
        
        # Detect languages
        languages = self._detect_languages(all_files)
        
        # Detect frameworks
        frameworks = self._detect_frameworks(root_path, all_files)
        
        # Find entry points
        entry_points = self._find_entry_points(root_path, all_files, languages)
        
        # Find test directories
        test_directories = self._find_test_directories(all_files)
        
        # Find config files
        config_files = self._find_config_files(all_files)
        
        # Find documentation files
        documentation_files = self._find_documentation_files(all_files)
        
        structure = CodebaseStructure(
            root_path=root_path,
            languages=languages,
            frameworks=frameworks,
            file_tree=file_tree,
            entry_points=entry_points,
            test_directories=test_directories,
            config_files=config_files,
            documentation_files=documentation_files
        )
        
        # Cache the file list for performance
        structure._cached_files = all_files
        return structure
    
    def _build_file_tree(self, root_path: str) -> Dict[str, Any]:
        """Build a hierarchical representation of the file tree."""
        tree = {}
        
        try:
            for root, dirs, files in os.walk(root_path):
                # Skip hidden directories and common ignore patterns
                dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['node_modules', '__pycache__', 'venv', '.venv', 'build', 'dist']]
                
                rel_root = os.path.relpath(root, root_path)
                if rel_root == '.':
                    current_level = tree
                else:
                    # Navigate to the correct level in the tree
                    current_level = tree
                    for part in rel_root.split(os.sep):
                        if part not in current_level:
                            current_level[part] = {}
                        current_level = current_level[part]
                
                # Add files to current level
                important_dotfiles = {'.env', '.gitignore', '.gitattributes', '.dockerignore', '.eslintrc', '.prettierrc'}
                for file in files:
                    # Include important dotfiles and non-hidden files
                    if not file.startswith('.') or file in important_dotfiles or any(file.startswith(df) for df in important_dotfiles):
                        current_level[file] = None  # None indicates it's a file
                
                # Add directories to current level
                for dir_name in dirs:
                    if dir_name not in current_level:
                        current_level[dir_name] = {}
        
        except Exception as e:
            # If we can't walk the directory, return empty tree
            return {}
        
        return tree
    
    def _get_all_files(self, root_path: str) -> List[str]:
        """Get all files in the codebase with relative paths."""
        all_files = []
        
        # Config files that start with . that we want to include
        important_dotfiles = {'.env', '.gitignore', '.gitattributes', '.dockerignore', '.eslintrc', '.prettierrc'}
        
        try:
            for root, dirs, files in os.walk(root_path):
                # Skip hidden directories and common ignore patterns
                dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['node_modules', '__pycache__', 'venv', '.venv', 'build', 'dist']]
                
                for file in files:
                    # Include important dotfiles and non-hidden files
                    if not file.startswith('.') or file in important_dotfiles or any(file.startswith(df) for df in important_dotfiles):
                        full_path = os.path.join(root, file)
                        rel_path = os.path.relpath(full_path, root_path)
                        all_files.append(rel_path)
        
        except Exception as e:
            # If we can't walk the directory, return empty list
            pass
        
        return all_files
    
    def _detect_languages(self, files: List[str]) -> List[str]:
        """Detect programming languages based on file extensions."""
        language_counts = defaultdict(int)
        
        for file_path in files:
            file_name = os.path.basename(file_path)
            file_ext = os.path.splitext(file_path)[1].lower()
            
            # Check for special files without extensions
            if file_name.lower() in ['dockerfile', 'makefile', 'rakefile', 'gemfile', 'vagrantfile']:
                if file_name.lower() == 'dockerfile':
                    language_counts['dockerfile'] += 1
                elif file_name.lower() == 'makefile':
                    language_counts['make'] += 1
                elif file_name.lower() in ['rakefile', 'gemfile']:
                    language_counts['ruby'] += 1
                elif file_name.lower() == 'vagrantfile':
                    language_counts['ruby'] += 1
                continue
            
            # Check extensions
            for language, extensions in self.LANGUAGE_EXTENSIONS.items():
                if file_ext in extensions or file_name in extensions:
                    language_counts[language] += 1
                    break
        
        # Return languages sorted by frequency
        return sorted(language_counts.keys(), key=lambda x: language_counts[x], reverse=True)
    
    def _detect_frameworks(self, root_path: str, files: List[str]) -> List[str]:
        """Detect frameworks and libraries based on file patterns and content."""
        detected_frameworks = set()
        
        # Convert files to set for faster lookup
        file_set = set(files)
        
        for framework, indicators in self.FRAMEWORK_INDICATORS.items():
            framework_score = 0
            
            for indicator in indicators:
                if indicator in file_set:
                    framework_score += 1
                elif indicator.endswith('/'):
                    # Directory indicator
                    dir_name = indicator.rstrip('/')
                    if any(f.startswith(dir_name + '/') for f in files):
                        framework_score += 1
                elif '*' in indicator:
                    # Pattern matching
                    pattern = indicator.replace('*', '.*')
                    if any(re.match(pattern, f) for f in files):
                        framework_score += 1
            
            # If we found enough indicators, consider the framework detected
            if framework_score >= min(2, len(indicators) // 2 + 1):
                detected_frameworks.add(framework)
        
        # Additional content-based detection for package.json
        if 'package.json' in file_set:
            try:
                package_json_path = os.path.join(root_path, 'package.json')
                if os.path.exists(package_json_path):
                    with open(package_json_path, 'r', encoding='utf-8') as f:
                        import json
                        package_data = json.load(f)
                        dependencies = {**package_data.get('dependencies', {}), **package_data.get('devDependencies', {})}
                        
                        # Check for framework-specific dependencies
                        if 'react' in dependencies or 'react-dom' in dependencies:
                            detected_frameworks.add('react')
                        if 'vue' in dependencies:
                            detected_frameworks.add('vue')
                        if '@angular/core' in dependencies:
                            detected_frameworks.add('angular')
                        if 'express' in dependencies:
                            detected_frameworks.add('express')
                        if 'next' in dependencies:
                            detected_frameworks.add('nextjs')
                        if 'nuxt' in dependencies:
                            detected_frameworks.add('nuxt')
                        if 'gatsby' in dependencies:
                            detected_frameworks.add('gatsby')
                        if 'svelte' in dependencies:
                            detected_frameworks.add('svelte')
                        if 'electron' in dependencies:
                            detected_frameworks.add('electron')
                        if 'react-native' in dependencies:
                            detected_frameworks.add('react-native')
            except:
                pass
        
        # Check for docker-compose files to detect Docker framework
        if any('docker-compose' in f for f in files):
            detected_frameworks.add('docker')
        
        return sorted(list(detected_frameworks))
    
    def _find_entry_points(self, root_path: str, files: List[str], languages: List[str]) -> List[str]:
        """Find likely entry points for the application."""
        entry_points = []
        
        # Common entry point patterns by language
        entry_patterns = {
            'python': ['main.py', 'app.py', 'run.py', 'server.py', 'manage.py', '__main__.py'],
            'javascript': ['index.js', 'main.js', 'app.js', 'server.js', 'start.js'],
            'typescript': ['index.ts', 'main.ts', 'app.ts', 'server.ts'],
            'java': ['Main.java', 'Application.java', 'App.java'],
            'go': ['main.go'],
            'rust': ['main.rs'],
            'c': ['main.c'],
            'cpp': ['main.cpp', 'main.cxx'],
        }
        
        # Look for common entry points
        for file_path in files:
            file_name = os.path.basename(file_path)
            
            # Check if it's a common entry point name
            for language in languages:
                if language in entry_patterns:
                    if file_name in entry_patterns[language]:
                        entry_points.append(file_path)
                        break
        
        # Look for files in root directory that might be entry points
        root_files = [f for f in files if '/' not in f and '\\' not in f]
        for file_path in root_files:
            if file_path not in entry_points:
                file_name = os.path.basename(file_path)
                if any(pattern in file_name.lower() for pattern in ['main', 'app', 'index', 'start', 'run']):
                    entry_points.append(file_path)
        
        return entry_points
    
    def _find_test_directories(self, files: List[str]) -> List[str]:
        """Find directories that contain tests."""
        test_dirs = set()
        
        for file_path in files:
            dir_path = os.path.dirname(file_path)
            file_name = os.path.basename(file_path)
            
            # Check if file or directory matches test patterns
            for pattern in self.TEST_PATTERNS:
                if re.search(pattern, file_path, re.IGNORECASE) or re.search(pattern, file_name, re.IGNORECASE):
                    if dir_path:
                        test_dirs.add(dir_path)
                    break
        
        return sorted(list(test_dirs))
    
    def _find_config_files(self, files: List[str]) -> List[str]:
        """Find configuration files."""
        config_files = []
        
        for file_path in files:
            file_name = os.path.basename(file_path)
            
            # Check against config patterns
            for pattern in self.CONFIG_PATTERNS:
                if re.search(pattern, file_name, re.IGNORECASE):
                    config_files.append(file_path)
                    break
        
        return sorted(config_files)
    
    def _find_documentation_files(self, files: List[str]) -> List[str]:
        """Find documentation files."""
        doc_files = []
        
        for file_path in files:
            file_name = os.path.basename(file_path)
            
            # Check against documentation patterns
            for pattern in self.DOC_PATTERNS:
                if re.search(pattern, file_path, re.IGNORECASE) or re.search(pattern, file_name, re.IGNORECASE):
                    doc_files.append(file_path)
                    break
        
        return sorted(doc_files)
    
    def _parse_package_json(self, file_path: str) -> tuple[List, bool]:
        """Parse package.json for Node.js dependencies."""
        dependencies = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                import json
                data = json.load(f)
                
                # Parse regular dependencies
                for name, version in data.get('dependencies', {}).items():
                    dependencies.append(DependencyInfo(
                        name=name,
                        version=version,
                        type='direct',
                        source='npm'
                    ))
                
                # Parse dev dependencies
                for name, version in data.get('devDependencies', {}).items():
                    dependencies.append(DependencyInfo(
                        name=name,
                        version=version,
                        type='dev',
                        source='npm'
                    ))
                
                # Parse peer dependencies
                for name, version in data.get('peerDependencies', {}).items():
                    dependencies.append(DependencyInfo(
                        name=name,
                        version=version,
                        type='peer',
                        source='npm'
                    ))
                
                return dependencies, True
        
        except Exception:
            return [], False
    
    def _parse_requirements_txt(self, file_path: str) -> tuple[List, bool]:
        """Parse requirements.txt for Python dependencies."""
        dependencies = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and not line.startswith('-'):
                        # Parse requirement line (e.g., "package==1.0.0", "package>=1.0.0")
                        name, version = self._parse_python_requirement(line)
                        if name:
                            dependencies.append(DependencyInfo(
                                name=name,
                                version=version,
                                type='direct',
                                source='pip'
                            ))
                
                return dependencies, True
        
        except Exception:
            return [], False
    
    def _parse_pipfile(self, file_path: str) -> tuple[List, bool]:
        """Parse Pipfile for Python dependencies."""
        dependencies = []
        
        try:
            # Simple TOML-like parsing for Pipfile
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
                # Extract [packages] section
                packages_match = re.search(r'\[packages\](.*?)(?:\[|$)', content, re.DOTALL)
                if packages_match:
                    packages_section = packages_match.group(1)
                    for line in packages_section.split('\n'):
                        line = line.strip()
                        if '=' in line and not line.startswith('#'):
                            parts = line.split('=', 1)
                            if len(parts) == 2:
                                name = parts[0].strip()
                                version = parts[1].strip().strip('"\'')
                                dependencies.append(DependencyInfo(
                                    name=name,
                                    version=version,
                                    type='direct',
                                    source='pip'
                                ))
                
                # Extract [dev-packages] section
                dev_packages_match = re.search(r'\[dev-packages\](.*?)(?:\[|$)', content, re.DOTALL)
                if dev_packages_match:
                    dev_packages_section = dev_packages_match.group(1)
                    for line in dev_packages_section.split('\n'):
                        line = line.strip()
                        if '=' in line and not line.startswith('#'):
                            parts = line.split('=', 1)
                            if len(parts) == 2:
                                name = parts[0].strip()
                                version = parts[1].strip().strip('"\'')
                                dependencies.append(DependencyInfo(
                                    name=name,
                                    version=version,
                                    type='dev',
                                    source='pip'
                                ))
                
                return dependencies, True
        
        except Exception:
            return [], False
    
    def _parse_pyproject_toml(self, file_path: str) -> tuple[List, bool]:
        """Parse pyproject.toml for Python dependencies."""
        dependencies = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
                # Extract dependencies from [project] section
                project_match = re.search(r'\[project\](.*?)(?:\n\s*\[|\Z)', content, re.DOTALL)
                if project_match:
                    project_section = project_match.group(1)
                    deps_match = re.search(r'dependencies\s*=\s*\[(.*?)\]', project_section, re.DOTALL)
                    if deps_match:
                        deps_content = deps_match.group(1)
                        # Extract dependencies from the array
                        dep_matches = re.findall(r'["\']([^"\']+)["\']', deps_content)
                        for dep_line in dep_matches:
                            if dep_line.strip():
                                name, version = self._parse_python_requirement(dep_line.strip())
                                if name:
                                    dependencies.append(DependencyInfo(
                                        name=name,
                                        version=version,
                                        type='direct',
                                        source='pip'
                                    ))
                
                # Extract dependencies from [tool.poetry.dependencies] section
                poetry_match = re.search(r'\[tool\.poetry\.dependencies\](.*?)(?:\n\s*\[|\Z)', content, re.DOTALL)
                if poetry_match:
                    poetry_section = poetry_match.group(1)
                    for line in poetry_section.split('\n'):
                        line = line.strip()
                        if '=' in line and not line.startswith('#') and line:
                            parts = line.split('=', 1)
                            if len(parts) == 2:
                                name = parts[0].strip()
                                version = parts[1].strip().strip('"\'')
                                if name != 'python':  # Skip python version requirement
                                    dependencies.append(DependencyInfo(
                                        name=name,
                                        version=version,
                                        type='direct',
                                        source='pip'
                                    ))
                
                return dependencies, True
        
        except Exception:
            return [], False
    
    def _parse_gemfile(self, file_path: str) -> tuple[List, bool]:
        """Parse Gemfile for Ruby dependencies."""
        dependencies = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('gem ') and not line.startswith('#'):
                        # Parse gem line (e.g., gem 'rails', '~> 6.0')
                        match = re.match(r"gem\s+['\"]([^'\"]+)['\"](?:\s*,\s*['\"]([^'\"]+)['\"])?", line)
                        if match:
                            name = match.group(1)
                            version = match.group(2) if match.group(2) else '*'
                            dependencies.append(DependencyInfo(
                                name=name,
                                version=version,
                                type='direct',
                                source='rubygems'
                            ))
                
                return dependencies, True
        
        except Exception:
            return [], False
    
    def _parse_cargo_toml(self, file_path: str) -> tuple[List, bool]:
        """Parse Cargo.toml for Rust dependencies."""
        dependencies = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
                # Extract [dependencies] section
                deps_match = re.search(r'\[dependencies\](.*?)(?:\n\s*\[|\Z)', content, re.DOTALL)
                if deps_match:
                    deps_section = deps_match.group(1)
                    for line in deps_section.split('\n'):
                        line = line.strip()
                        if '=' in line and not line.startswith('#') and line:
                            parts = line.split('=', 1)
                            if len(parts) == 2:
                                name = parts[0].strip()
                                version_part = parts[1].strip()
                                
                                # Handle simple version strings and complex objects
                                if version_part.startswith('"') and version_part.endswith('"'):
                                    version = version_part.strip('"')
                                elif version_part.startswith('{'):
                                    # Extract version from object like { version = "1.0", features = ["full"] }
                                    version_match = re.search(r'version\s*=\s*"([^"]+)"', version_part)
                                    version = version_match.group(1) if version_match else version_part
                                else:
                                    version = version_part.strip('"\'')
                                
                                dependencies.append(DependencyInfo(
                                    name=name,
                                    version=version,
                                    type='direct',
                                    source='crates.io'
                                ))
                
                # Extract [dev-dependencies] section
                dev_deps_match = re.search(r'\[dev-dependencies\](.*?)(?:\n\s*\[|\Z)', content, re.DOTALL)
                if dev_deps_match:
                    dev_deps_section = dev_deps_match.group(1)
                    for line in dev_deps_section.split('\n'):
                        line = line.strip()
                        if '=' in line and not line.startswith('#') and line:
                            parts = line.split('=', 1)
                            if len(parts) == 2:
                                name = parts[0].strip()
                                version_part = parts[1].strip()
                                
                                # Handle simple version strings and complex objects
                                if version_part.startswith('"') and version_part.endswith('"'):
                                    version = version_part.strip('"')
                                elif version_part.startswith('{'):
                                    # Extract version from object
                                    version_match = re.search(r'version\s*=\s*"([^"]+)"', version_part)
                                    version = version_match.group(1) if version_match else version_part
                                else:
                                    version = version_part.strip('"\'')
                                
                                dependencies.append(DependencyInfo(
                                    name=name,
                                    version=version,
                                    type='dev',
                                    source='crates.io'
                                ))
                
                return dependencies, True
        
        except Exception:
            return [], False
    
    def _parse_pom_xml(self, file_path: str) -> tuple[List, bool]:
        """Parse pom.xml for Java/Maven dependencies."""
        dependencies = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
                # Simple XML parsing for dependencies
                dep_matches = re.findall(r'<dependency>(.*?)</dependency>', content, re.DOTALL)
                for dep_match in dep_matches:
                    group_match = re.search(r'<groupId>(.*?)</groupId>', dep_match)
                    artifact_match = re.search(r'<artifactId>(.*?)</artifactId>', dep_match)
                    version_match = re.search(r'<version>(.*?)</version>', dep_match)
                    scope_match = re.search(r'<scope>(.*?)</scope>', dep_match)
                    
                    if group_match and artifact_match:
                        group_id = group_match.group(1).strip()
                        artifact_id = artifact_match.group(1).strip()
                        version = version_match.group(1).strip() if version_match else '*'
                        scope = scope_match.group(1).strip() if scope_match else 'compile'
                        
                        name = f"{group_id}:{artifact_id}"
                        dep_type = 'dev' if scope in ['test', 'provided'] else 'direct'
                        
                        dependencies.append(DependencyInfo(
                            name=name,
                            version=version,
                            type=dep_type,
                            source='maven'
                        ))
                
                return dependencies, True
        
        except Exception:
            return [], False
    
    def _parse_gradle(self, file_path: str) -> tuple[List, bool]:
        """Parse build.gradle for Java/Gradle dependencies."""
        dependencies = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
                # Extract dependencies block
                deps_match = re.search(r'dependencies\s*\{(.*?)\}', content, re.DOTALL)
                if deps_match:
                    deps_content = deps_match.group(1)
                    
                    # Parse dependency lines
                    dep_lines = re.findall(r'(implementation|compile|testImplementation|testCompile|api|runtimeOnly)\s+[\'"]([^\'"]+)[\'"]', deps_content)
                    for scope, dep_string in dep_lines:
                        # Parse group:artifact:version format
                        parts = dep_string.split(':')
                        if len(parts) >= 2:
                            group_id = parts[0]
                            artifact_id = parts[1]
                            version = parts[2] if len(parts) > 2 else '*'
                            
                            name = f"{group_id}:{artifact_id}"
                            dep_type = 'dev' if 'test' in scope.lower() else 'direct'
                            
                            dependencies.append(DependencyInfo(
                                name=name,
                                version=version,
                                type=dep_type,
                                source='maven'
                            ))
                
                return dependencies, True
        
        except Exception:
            return [], False
    
    def _parse_composer_json(self, file_path: str) -> tuple[List, bool]:
        """Parse composer.json for PHP dependencies."""
        dependencies = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                import json
                data = json.load(f)
                
                # Parse regular dependencies
                for name, version in data.get('require', {}).items():
                    if name != 'php':  # Skip PHP version requirement
                        dependencies.append(DependencyInfo(
                            name=name,
                            version=version,
                            type='direct',
                            source='packagist'
                        ))
                
                # Parse dev dependencies
                for name, version in data.get('require-dev', {}).items():
                    dependencies.append(DependencyInfo(
                        name=name,
                        version=version,
                        type='dev',
                        source='packagist'
                    ))
                
                return dependencies, True
        
        except Exception:
            return [], False
    
    def _parse_go_mod(self, file_path: str) -> tuple[List, bool]:
        """Parse go.mod for Go dependencies."""
        dependencies = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('//') and not line.startswith('module') and not line.startswith('go '):
                        # Parse require lines
                        if line.startswith('require'):
                            # Handle single line require
                            match = re.match(r'require\s+([^\s]+)\s+([^\s]+)', line)
                            if match:
                                name = match.group(1)
                                version = match.group(2)
                                dependencies.append(DependencyInfo(
                                    name=name,
                                    version=version,
                                    type='direct',
                                    source='go'
                                ))
                        elif re.match(r'^\s*[^\s]+\s+[^\s]+', line):
                            # Handle dependencies inside require block
                            parts = line.split()
                            if len(parts) >= 2:
                                name = parts[0]
                                version = parts[1]
                                dependencies.append(DependencyInfo(
                                    name=name,
                                    version=version,
                                    type='direct',
                                    source='go'
                                ))
                
                return dependencies, True
        
        except Exception:
            return [], False
    
    def _parse_python_requirement(self, requirement: str) -> tuple[str, str]:
        """Parse a Python requirement string (e.g., 'package==1.0.0')."""
        # Remove comments
        requirement = requirement.split('#')[0].strip()
        
        if not requirement:
            return None, None
        
        # Parse different version specifiers
        for op in ['==', '>=', '<=', '>', '<', '~=', '!=']:
            if op in requirement:
                parts = requirement.split(op, 1)
                if len(parts) == 2:
                    name = parts[0].strip()
                    version = f"{op}{parts[1].strip()}"
                    return name, version
        
        # No version specifier
        return requirement.strip(), '*'
    
    def _detect_dependency_conflicts(self, dependencies: List) -> List[str]:
        """Detect conflicts between dependencies (same package, different versions)."""
        conflicts = []
        name_versions = defaultdict(set)
        
        # Group dependencies by name
        for dep in dependencies:
            name_versions[dep.name].add(dep.version)
        
        # Find conflicts
        for name, versions in name_versions.items():
            if len(versions) > 1:
                # Filter out wildcard versions
                specific_versions = [v for v in versions if v != '*']
                if len(specific_versions) > 1:
                    conflicts.append(f"{name}: {', '.join(sorted(specific_versions))}")
        
        return conflicts
    
    def _detect_architectural_patterns(self, structure: CodebaseStructure) -> List[Pattern]:
        """Detect architectural patterns in the codebase."""
        patterns = []
        
        # MVC Pattern Detection
        mvc_indicators = {
            'models': ['models/', 'model/', 'entities/', 'entity/'],
            'views': ['views/', 'view/', 'templates/', 'template/'],
            'controllers': ['controllers/', 'controller/', 'handlers/', 'handler/']
        }
        
        mvc_score = 0
        mvc_locations = []
        
        # Get all file paths from the structure
        all_paths = self._get_all_paths_from_tree(structure.file_tree)
        
        for component, indicators in mvc_indicators.items():
            for indicator in indicators:
                if any(indicator in path for path in all_paths):
                    mvc_score += 1
                    mvc_locations.append(indicator)
                    break
        
        if mvc_score >= 2:
            patterns.append(Pattern(
                name="MVC (Model-View-Controller)",
                type="architectural",
                confidence=min(1.0, mvc_score / 3.0),
                description="Model-View-Controller architectural pattern detected",
                locations=mvc_locations
            ))
        
        # Microservices Pattern Detection
        microservice_indicators = [
            'services/', 'service/', 'microservices/', 'api/', 'apis/',
            'docker-compose.yml', 'kubernetes/', 'k8s/'
        ]
        
        microservice_score = 0
        microservice_locations = []
        
        for indicator in microservice_indicators:
            if (indicator in structure.file_tree or 
                any(indicator in path for path in all_paths) or
                indicator in structure.config_files):
                microservice_score += 1
                microservice_locations.append(indicator)
        
        if microservice_score >= 2:
            patterns.append(Pattern(
                name="Microservices",
                type="architectural",
                confidence=min(1.0, microservice_score / len(microservice_indicators)),
                description="Microservices architecture pattern detected",
                locations=microservice_locations
            ))
        
        # Layered Architecture Detection
        layer_indicators = [
            'presentation/', 'business/', 'data/', 'dal/', 'bll/', 'ui/',
            'service/', 'repository/', 'dao/'
        ]
        
        layer_score = 0
        layer_locations = []
        
        for indicator in layer_indicators:
            if any(indicator in path for path in all_paths):
                layer_score += 1
                layer_locations.append(indicator)
        
        if layer_score >= 3:
            patterns.append(Pattern(
                name="Layered Architecture",
                type="architectural",
                confidence=min(1.0, layer_score / len(layer_indicators)),
                description="Layered architecture pattern detected",
                locations=layer_locations
            ))
        
        # REST API Pattern Detection
        rest_indicators = ['api/', 'rest/', 'endpoints/', 'routes/']
        rest_files = ['routes.py', 'urls.py', 'api.py', 'endpoints.py']
        
        rest_score = 0
        rest_locations = []
        
        for indicator in rest_indicators:
            if any(indicator in path for path in all_paths):
                rest_score += 1
                rest_locations.append(indicator)
        
        for file_name in rest_files:
            if any(file_name in path for path in all_paths):
                rest_score += 1
                rest_locations.append(file_name)
        
        if rest_score >= 1:
            patterns.append(Pattern(
                name="REST API",
                type="architectural",
                confidence=min(1.0, rest_score / (len(rest_indicators) + len(rest_files))),
                description="REST API pattern detected",
                locations=rest_locations
            ))
        
        return patterns
    
    def _detect_design_patterns(self, structure: CodebaseStructure) -> List[Pattern]:
        """Detect design patterns in the codebase."""
        patterns = []
        
        # Repository Pattern Detection
        repo_indicators = ['repository/', 'repositories/', 'repo/', 'repos/']
        repo_files = ['repository.py', 'repo.py', 'repositories.py']
        
        repo_score = 0
        repo_locations = []
        
        # Get all file paths from the structure
        all_paths = self._get_all_paths_from_tree(structure.file_tree)
        
        for indicator in repo_indicators:
            if any(indicator in path for path in all_paths):
                repo_score += 1
                repo_locations.append(indicator)
        
        for file_name in repo_files:
            if any(file_name in path for path in all_paths):
                repo_score += 1
                repo_locations.append(file_name)
        
        if repo_score >= 1:
            patterns.append(Pattern(
                name="Repository Pattern",
                type="design",
                confidence=min(1.0, repo_score / (len(repo_indicators) + len(repo_files))),
                description="Repository design pattern detected",
                locations=repo_locations
            ))
        
        # Factory Pattern Detection
        factory_indicators = ['factory/', 'factories/']
        factory_files = ['factory.py', 'factories.py', 'Factory.java', 'Factory.cs']
        
        factory_score = 0
        factory_locations = []
        
        for indicator in factory_indicators:
            if any(indicator in path for path in all_paths):
                factory_score += 1
                factory_locations.append(indicator)
        
        for file_name in factory_files:
            if any(file_name in path for path in all_paths):
                factory_score += 1
                factory_locations.append(file_name)
        
        if factory_score >= 1:
            patterns.append(Pattern(
                name="Factory Pattern",
                type="design",
                confidence=min(1.0, factory_score / (len(factory_indicators) + len(factory_files))),
                description="Factory design pattern detected",
                locations=factory_locations
            ))
        
        # Observer Pattern Detection
        observer_files = ['observer.py', 'Observer.java', 'observer.js', 'events.py', 'event.py']
        
        observer_score = 0
        observer_locations = []
        
        for file_name in observer_files:
            if any(file_name in path for path in all_paths):
                observer_score += 1
                observer_locations.append(file_name)
        
        if observer_score >= 1:
            patterns.append(Pattern(
                name="Observer Pattern",
                type="design",
                confidence=min(1.0, observer_score / len(observer_files)),
                description="Observer design pattern detected",
                locations=observer_locations
            ))
        
        return patterns
    
    def _detect_organization_patterns(self, structure: CodebaseStructure) -> List[Pattern]:
        """Detect code organization patterns."""
        patterns = []
        
        # Feature-based Organization
        feature_indicators = ['features/', 'modules/', 'components/', 'domains/']
        
        feature_score = 0
        feature_locations = []
        
        # Get all file paths from the structure
        all_paths = self._get_all_paths_from_tree(structure.file_tree)
        
        for indicator in feature_indicators:
            if any(indicator in path for path in all_paths):
                feature_score += 1
                feature_locations.append(indicator)
        
        if feature_score >= 1:
            patterns.append(Pattern(
                name="Feature-based Organization",
                type="organization",
                confidence=min(1.0, feature_score / len(feature_indicators)),
                description="Code organized by features/modules",
                locations=feature_locations
            ))
        
        # Test-driven Development Pattern
        test_ratio = len(structure.test_directories) / max(1, len(structure.file_tree))
        
        if test_ratio > 0.1:  # More than 10% test directories
            patterns.append(Pattern(
                name="Test-driven Development",
                type="organization",
                confidence=min(1.0, test_ratio * 2),
                description="Strong test organization suggests TDD practices",
                locations=structure.test_directories
            ))
        
        # Configuration Management Pattern
        config_score = len(structure.config_files)
        
        if config_score >= 3:
            patterns.append(Pattern(
                name="Configuration Management",
                type="organization",
                confidence=min(1.0, config_score / 10),
                description="Well-organized configuration management",
                locations=structure.config_files[:5]  # Show first 5 config files
            ))
        
        return patterns
    
    def _calculate_file_metrics(self, file_path: str, relative_path: str) -> Dict[str, Any]:
        """Calculate metrics for a single file."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            lines = content.split('\n')
            lines_of_code = len([line for line in lines if line.strip() and not line.strip().startswith('#')])
            
            # Simple cyclomatic complexity calculation
            complexity = self._calculate_cyclomatic_complexity(content, relative_path)
            
            return {
                'lines_of_code': lines_of_code,
                'total_lines': len(lines),
                'cyclomatic_complexity': complexity,
                'file_size': len(content)
            }
        
        except Exception:
            return {}
    
    def _calculate_cyclomatic_complexity(self, content: str, file_path: str) -> float:
        """Calculate cyclomatic complexity for a file."""
        # Get file extension to determine language
        ext = os.path.splitext(file_path)[1].lower()
        
        # Define complexity keywords by language
        complexity_keywords = {
            '.py': ['if', 'elif', 'for', 'while', 'except', 'and', 'or'],
            '.js': ['if', 'else if', 'for', 'while', 'catch', '&&', '||', 'case'],
            '.ts': ['if', 'else if', 'for', 'while', 'catch', '&&', '||', 'case'],
            '.java': ['if', 'else if', 'for', 'while', 'catch', '&&', '||', 'case'],
            '.c': ['if', 'else if', 'for', 'while', '&&', '||', 'case'],
            '.cpp': ['if', 'else if', 'for', 'while', 'catch', '&&', '||', 'case'],
            '.cs': ['if', 'else if', 'for', 'while', 'catch', '&&', '||', 'case'],
            '.go': ['if', 'for', 'switch', 'case', '&&', '||'],
            '.rs': ['if', 'for', 'while', 'match', '&&', '||'],
        }
        
        keywords = complexity_keywords.get(ext, ['if', 'for', 'while'])
        
        # Count complexity-adding constructs
        complexity = 1  # Base complexity
        
        for keyword in keywords:
            # Use word boundaries to avoid partial matches
            pattern = r'\b' + re.escape(keyword) + r'\b'
            matches = re.findall(pattern, content, re.IGNORECASE)
            complexity += len(matches)
        
        return float(complexity)
    
    def _is_test_file(self, file_path: str) -> bool:
        """Check if a file is a test file."""
        test_patterns = [
            r'.*test.*',
            r'.*spec.*',
            r'.*__tests__.*',
            r'.*\.test\..*',
            r'.*\.spec\..*',
        ]
        
        for pattern in test_patterns:
            if re.search(pattern, file_path, re.IGNORECASE):
                return True
        
        return False
    
    def _calculate_technical_debt_ratio(self, metrics_by_file: Dict[str, Dict[str, Any]]) -> float:
        """Calculate technical debt ratio based on complexity and maintainability."""
        if not metrics_by_file:
            return 0.0
        
        total_complexity = sum(metrics.get('cyclomatic_complexity', 0) for metrics in metrics_by_file.values())
        total_files = len(metrics_by_file)
        
        if total_files == 0:
            return 0.0
        
        avg_complexity = total_complexity / total_files
        
        # Simple heuristic: higher complexity = higher technical debt
        # Normalize to 0-100 scale
        debt_ratio = min(100.0, (avg_complexity - 1) * 10)
        
        return max(0.0, debt_ratio)
    
    def _calculate_duplication_percentage(self, metrics_by_file: Dict[str, Dict[str, Any]]) -> float:
        """Calculate code duplication percentage (simplified heuristic)."""
        if not metrics_by_file:
            return 0.0
        
        # This is a simplified calculation
        # In a real implementation, you'd analyze actual code similarity
        total_lines = sum(metrics.get('lines_of_code', 0) for metrics in metrics_by_file.values())
        
        if total_lines == 0:
            return 0.0
        
        # Heuristic: assume some duplication based on project size
        # Larger projects tend to have more duplication
        file_count = len(metrics_by_file)
        
        if file_count < 10:
            return 5.0  # Small projects: 5% duplication
        elif file_count < 50:
            return 10.0  # Medium projects: 10% duplication
        else:
            return 15.0  # Large projects: 15% duplication
    
    def _get_all_paths_from_tree(self, tree: Dict[str, Any], prefix: str = "") -> List[str]:
        """Get all file and directory paths from the file tree."""
        paths = []
        
        for name, value in tree.items():
            current_path = os.path.join(prefix, name) if prefix else name
            paths.append(current_path)
            
            if isinstance(value, dict):
                # It's a directory, recurse
                paths.extend(self._get_all_paths_from_tree(value, current_path))
        
        return paths
    
    def identify_patterns(self, structure: CodebaseStructure) -> List[Pattern]:
        """Identify architectural and code patterns in the codebase."""
        patterns = []
        
        # Detect architectural patterns
        patterns.extend(self._detect_architectural_patterns(structure))
        
        # Detect design patterns
        patterns.extend(self._detect_design_patterns(structure))
        
        # Detect code organization patterns
        patterns.extend(self._detect_organization_patterns(structure))
        
        return patterns
    
    def extract_dependencies(self, workspace: SandboxWorkspace) -> DependencyGraph:
        """Extract and analyze dependencies from the codebase."""
        root_path = workspace.sandbox_path
        all_files = self._get_all_files(root_path)
        
        dependencies = []
        dependency_files = []
        conflicts = []
        outdated = []
        
        # Parse different types of dependency files
        for file_path in all_files:
            file_name = os.path.basename(file_path)
            full_path = os.path.join(root_path, file_path)
            
            try:
                if file_name == 'package.json':
                    deps, dep_file = self._parse_package_json(full_path)
                    dependencies.extend(deps)
                    if dep_file:
                        dependency_files.append(file_path)
                
                elif file_name == 'requirements.txt':
                    deps, dep_file = self._parse_requirements_txt(full_path)
                    dependencies.extend(deps)
                    if dep_file:
                        dependency_files.append(file_path)
                
                elif file_name == 'Pipfile':
                    deps, dep_file = self._parse_pipfile(full_path)
                    dependencies.extend(deps)
                    if dep_file:
                        dependency_files.append(file_path)
                
                elif file_name == 'pyproject.toml':
                    deps, dep_file = self._parse_pyproject_toml(full_path)
                    dependencies.extend(deps)
                    if dep_file:
                        dependency_files.append(file_path)
                
                elif file_name == 'Gemfile':
                    deps, dep_file = self._parse_gemfile(full_path)
                    dependencies.extend(deps)
                    if dep_file:
                        dependency_files.append(file_path)
                
                elif file_name == 'Cargo.toml':
                    deps, dep_file = self._parse_cargo_toml(full_path)
                    dependencies.extend(deps)
                    if dep_file:
                        dependency_files.append(file_path)
                
                elif file_name == 'pom.xml':
                    deps, dep_file = self._parse_pom_xml(full_path)
                    dependencies.extend(deps)
                    if dep_file:
                        dependency_files.append(file_path)
                
                elif file_name in ['build.gradle', 'build.gradle.kts']:
                    deps, dep_file = self._parse_gradle(full_path)
                    dependencies.extend(deps)
                    if dep_file:
                        dependency_files.append(file_path)
                
                elif file_name == 'composer.json':
                    deps, dep_file = self._parse_composer_json(full_path)
                    dependencies.extend(deps)
                    if dep_file:
                        dependency_files.append(file_path)
                
                elif file_name == 'go.mod':
                    deps, dep_file = self._parse_go_mod(full_path)
                    dependencies.extend(deps)
                    if dep_file:
                        dependency_files.append(file_path)
                
            except Exception as e:
                # Skip files that can't be parsed
                continue
        
        # Detect conflicts (same package with different versions)
        conflicts = self._detect_dependency_conflicts(dependencies)
        
        # Create dependency graph
        dependency_graph = DependencyGraph(
            dependencies=dependencies,
            dependency_files=dependency_files,
            conflicts=conflicts,
            outdated=outdated  # Would need external service to detect outdated packages
        )
        
        return dependency_graph
    
    def calculate_metrics(self, workspace: SandboxWorkspace) -> CodeMetrics:
        """Calculate code quality and complexity metrics."""
        root_path = workspace.sandbox_path
        all_files = self._get_all_files(root_path)
        
        # Calculate basic metrics
        total_lines = 0
        total_complexity = 0.0
        file_count = 0
        test_files = 0
        metrics_by_file = {}
        
        for file_path in all_files:
            full_path = os.path.join(root_path, file_path)
            file_metrics = self._calculate_file_metrics(full_path, file_path)
            
            if file_metrics:
                metrics_by_file[file_path] = file_metrics
                total_lines += file_metrics.get('lines_of_code', 0)
                total_complexity += file_metrics.get('cyclomatic_complexity', 0)
                file_count += 1
                
                if self._is_test_file(file_path):
                    test_files += 1
        
        # Calculate aggregate metrics
        avg_complexity = total_complexity / file_count if file_count > 0 else 0.0
        test_coverage = (test_files / file_count * 100) if file_count > 0 else 0.0
        
        # Calculate maintainability index (simplified version)
        maintainability_index = max(0, 171 - 5.2 * math.log(max(1, total_lines)) - 0.23 * avg_complexity)
        
        metrics = CodeMetrics(
            lines_of_code=total_lines,
            cyclomatic_complexity=avg_complexity,
            maintainability_index=maintainability_index,
            test_coverage=test_coverage,
            technical_debt_ratio=self._calculate_technical_debt_ratio(metrics_by_file),
            duplication_percentage=self._calculate_duplication_percentage(metrics_by_file),
            metrics_by_file=metrics_by_file
        )
        
        return metrics
    
    def generate_summary(self, analysis: CodebaseAnalysis) -> str:
        """Generate a comprehensive summary of the codebase analysis."""
        # TODO: Implement summary generation logic
        summary = f"""
        Codebase Analysis Summary:
        - Languages: {', '.join(analysis.structure.languages)}
        - Frameworks: {', '.join(analysis.structure.frameworks)}
        - Dependencies: {len(analysis.dependencies.dependencies)}
        - Patterns identified: {len(analysis.patterns)}
        - Lines of code: {analysis.metrics.lines_of_code}
        """
        return summary.strip()
    
    def analyze_codebase(self, workspace: SandboxWorkspace) -> CodebaseAnalysis:
        """Perform complete codebase analysis."""
        structure = self.analyze_structure(workspace)
        dependencies = self.extract_dependencies(workspace)
        patterns = self.identify_patterns(structure)
        metrics = self.calculate_metrics(workspace)
        
        analysis = CodebaseAnalysis(
            structure=structure,
            dependencies=dependencies,
            patterns=patterns,
            metrics=metrics,
            summary="",
            analysis_timestamp=None  # Will be set in __post_init__
        )
        
        analysis.summary = self.generate_summary(analysis)
        return analysis