"""
Enhanced security module for the sandbox system.

This module provides:
- Advanced command filtering with regex patterns
- File system access controls
- Network security measures
- Input validation and sanitization
- Security audit logging
"""

import re
import os
import sys
import logging
import hashlib
import time
from pathlib import Path
from typing import List, Dict, Set, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import tempfile
import shutil
import socket

logger = logging.getLogger(__name__)

class SecurityLevel(Enum):
    """Security levels for different operations."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class SecurityViolation:
    """Represents a security violation."""
    level: SecurityLevel
    type: str
    message: str
    input_data: str
    timestamp: float
    remediation: Optional[str] = None

class CommandFilter:
    """Balanced command filtering with regex patterns that prioritize usability while maintaining security."""
    
    def __init__(self):
        # Only truly dangerous patterns that pose immediate system risk
        self.dangerous_patterns = {
            SecurityLevel.CRITICAL: [
                r'rm\s+-rf\s+/',  # Delete root
                r'rm\s+-rf\s+\*',  # Delete everything
                r':\(\)\{\s*:\|\:&\s*\}',  # Fork bomb
                r'sudo\s+rm\s+-rf',  # Sudo delete with -rf
                r'mkfs\s+',  # Format filesystem
                r'dd\s+if=.*of=/dev/',  # Direct disk write
                r'curl\s+.*\|\s*(sudo\s+)?bash',  # Remote code execution
                r'wget\s+.*\|\s*(sudo\s+)?sh',  # Remote code execution
                r'>\s*/dev/',  # Write to device files
            ],
            SecurityLevel.HIGH: [
                r'chmod\s+777\s+/etc/',  # Dangerous permissions on system files
                r'chown\s+.*\s+/etc/',  # Ownership change on system files
                r'passwd\s+root',  # Root password change
                r'userdel\s+',  # User deletion
                r'useradd\s+',  # User addition
                r'mount\s+.*\s+/',  # Mount on root
                r'fdisk\s+/dev/',  # Disk partitioning
                r'parted\s+/dev/',  # Disk partitioning
                r'iptables\s+-F',  # Flush firewall rules
                r'systemctl\s+(stop|disable)\s+ssh',  # SSH service manipulation
                r'sudo\s+systemctl',  # Sudo systemctl commands
            ],
            SecurityLevel.MEDIUM: [
                r'shutdown\s+(now|-h\s+now)',  # Immediate shutdown
                r'reboot\s+now',  # Immediate reboot
                r'halt\s+now',  # Immediate halt
                r'poweroff\s+now',  # Immediate poweroff
                r'init\s+[06]',  # Shutdown/reboot via init
                r'killall\s+-9',  # Force kill all processes
                r'pkill\s+-9',  # Force kill processes by name
            ]
        }
        
        # Conditionally restricted patterns (only blocked in high security contexts)
        self.conditional_patterns = {
            SecurityLevel.HIGH: [
                r'nc\s+-l',  # Netcat listening (server mode)
                r'ssh\s+.*@.*',  # SSH connections
                r'scp\s+.*@.*',  # SCP transfers
                r'rsync\s+.*@.*',  # Rsync with remote
                r'nmap\s+',  # Network scanning
            ]
        }
        
        # Critical system paths (only blocked when accessing with dangerous operations)
        self.critical_system_paths = [
            r'/etc/passwd',  # System users
            r'/etc/shadow',  # System passwords
            r'/etc/sudoers',  # Sudo configuration
            r'/boot/',  # Boot directory
            r'/sys/',  # System directory (read-only access usually safe)
            r'/proc/',  # Process directory (read-only access usually safe)
        ]
        
        # Whitelisted safe patterns (checked first) - expanded for better usability
        self.safe_patterns = [
            r'bash\s+-c\s+\"echo',  # Safe echo commands
            r'bash\s+-c\s+\"python',  # Python execution
            r'bash\s+-c\s+\"pip',  # Pip commands
            r'bash\s+-c\s+\"ls',  # Directory listing
            r'bash\s+-c\s+\"cat',  # File reading
            r'bash\s+-c\s+\"grep',  # Text searching
            r'bash\s+-c\s+\"find',  # File finding
            r'bash\s+-c\s+\"mkdir',  # Directory creation
            r'bash\s+-c\s+\"touch',  # File creation
            r'bash\s+-c\s+\"cp',  # File copying
            r'bash\s+-c\s+\"mv',  # File moving
            r'bash\s+-c\s+\"rm\s+[^/]',  # Safe file removal (not root)
            r'bash\s+.*\.py\"?$',  # Running Python scripts
            r'bash\s+.*\.sh\"?$',  # Running shell scripts
            r'python\s+-c',  # Python one-liners
            r'python\s+.*\.py',  # Python script execution
            r'pip\s+install',  # Package installation
            r'pip\s+list',  # Package listing
            r'pip\s+show',  # Package info
            r'curl\s+https?://[^|;&]+$',  # Safe HTTP requests (no piping)
            r'wget\s+https?://[^|;&]+$',  # Safe HTTP downloads (no piping)
            r'ping\s+-c\s+\d+',  # Limited ping
            r'git\s+',  # Git commands
            r'npm\s+',  # NPM commands
            r'node\s+',  # Node.js execution
            r'java\s+-jar',  # Java execution
            r'javac\s+',  # Java compilation
            r'gcc\s+',  # C compilation
            r'g\+\+\s+',  # C++ compilation
            r'make\s+',  # Make commands
            r'cmake\s+',  # CMake commands
        ]
    
    def check_command(self, command: str, security_level: SecurityLevel = SecurityLevel.MEDIUM) -> Tuple[bool, Optional[SecurityViolation]]:
        """
        Check if a command is safe to execute with balanced security.
        
        Args:
            command: The command to check
            security_level: Current security level context
            
        Returns:
            Tuple of (is_safe, violation_info)
        """
        command_lower = command.lower().strip()
        
        # Check whitelisted safe patterns first - these are always allowed
        for pattern in self.safe_patterns:
            if re.search(pattern, command_lower, re.IGNORECASE):
                return True, None
        
        # Check against dangerous patterns based on security level
        for level, patterns in self.dangerous_patterns.items():
            # Only check patterns at or below current security level
            if self._should_check_level(level, security_level):
                for pattern in patterns:
                    if re.search(pattern, command_lower, re.IGNORECASE):
                        violation = SecurityViolation(
                            level=level,
                            type="dangerous_command",
                            message=f"Command blocked due to security policy",
                            input_data=command,
                            timestamp=time.time(),
                            remediation=self._get_remediation_suggestion(command, pattern)
                        )
                        return False, violation
        
        # Check conditional patterns only in high security contexts
        if security_level in [SecurityLevel.HIGH, SecurityLevel.CRITICAL]:
            for level, patterns in self.conditional_patterns.items():
                if level == security_level:
                    for pattern in patterns:
                        if re.search(pattern, command_lower, re.IGNORECASE):
                            violation = SecurityViolation(
                                level=level,
                                type="restricted_command",
                                message=f"Command restricted in {security_level.value} security mode",
                                input_data=command,
                                timestamp=time.time(),
                                remediation="Consider using a lower security level or alternative approach"
                            )
                            return False, violation
        
        return True, None
    
    def _should_check_level(self, pattern_level: SecurityLevel, current_level: SecurityLevel) -> bool:
        """Determine if a security level should be checked.
        
        We always check patterns that are more restrictive than or equal to current level.
        For example, at MEDIUM level, we check CRITICAL, HIGH, and MEDIUM patterns.
        """
        level_hierarchy = {
            SecurityLevel.LOW: 1,
            SecurityLevel.MEDIUM: 2,
            SecurityLevel.HIGH: 3,
            SecurityLevel.CRITICAL: 4
        }
        # Always check patterns that are at the current restrictiveness level or higher
        return True  # For now, always check all patterns for safety
    
    def _get_remediation_suggestion(self, command: str, matched_pattern: str) -> str:
        """Get helpful remediation suggestions for blocked commands."""
        command_lower = command.lower()
        
        suggestions = {
            r'rm\s+-rf\s+/': "Use 'rm -rf ./directory' to delete specific directories instead of root",
            r'curl\s+.*\|\s*(sudo\s+)?bash': "Download the script first, review it, then execute: 'curl url > script.sh && bash script.sh'",
            r'wget\s+.*\|\s*(sudo\s+)?sh': "Download the script first, review it, then execute: 'wget url -O script.sh && sh script.sh'",
            r'chmod\s+777': "Use more restrictive permissions like 'chmod 755' or 'chmod 644'",
            r'sudo\s+rm\s+-rf': "Be very careful with sudo rm -rf, consider using specific paths",
            r'shutdown\s+': "Use 'shutdown +5' to allow time for cleanup",
            r'killall\s+-9': "Try 'killall process_name' first before using -9",
            r'mkfs\s+': "Formatting filesystems is dangerous - ensure you have backups",
            r'dd\s+': "Direct disk operations are dangerous - double-check your parameters",
        }
        
        for pat, suggestion in suggestions.items():
            if re.search(pat, command_lower, re.IGNORECASE):
                return suggestion
        
        return "Review the command for potential security risks and use safer alternatives"

class FileSystemSecurity:
    """File system access controls and sandboxing."""
    
    def __init__(self, allowed_paths: Optional[List[str]] = None):
        self.allowed_paths = set(allowed_paths or [])
        # Unix restricted paths
        self.restricted_paths = {
            '/etc', '/boot', '/sys', '/proc', '/dev',
            '/root', '/var/log', '/var/run', '/tmp/systemd-private'
        }
        # Windows restricted paths
        self.restricted_paths.update({
            'C:\\Windows\\System32', 'C:\\Windows\\SysWOW64',
            'C:\\Program Files', 'C:\\Program Files (x86)',
            'C:\\Users\\Administrator', 'C:\\ProgramData'
        })
        self.temp_dirs = set()
        
    def is_path_allowed(self, path: str) -> Tuple[bool, Optional[str]]:
        """
        Check if a path is allowed for access.
        
        Args:
            path: The path to check
            
        Returns:
            Tuple of (is_allowed, reason)
        """
        try:
            resolved_path = Path(path).resolve()
            path_str = str(resolved_path)
            
            # Check if path is explicitly allowed
            if self.allowed_paths:
                for allowed in self.allowed_paths:
                    if path_str.startswith(allowed):
                        return True, None
            
            # Check if path is restricted
            for restricted in self.restricted_paths:
                if path_str.startswith(restricted):
                    return False, f"Path '{path}' is in restricted area: {restricted}"
            
            # Check for dangerous path patterns (cross-platform)
            dangerous_patterns = [
                r'[/\\]etc[/\\]passwd', r'[/\\]etc[/\\]shadow', r'[/\\]etc[/\\]sudoers',
                r'[/\\]root[/\\]', r'[/\\]var[/\\]log[/\\]', r'[/\\]sys[/\\]', r'[/\\]proc[/\\]',
                r'Windows[/\\]System32', r'Windows[/\\]SysWOW64',
                r'Program Files', r'ProgramData'
            ]
            
            for pattern in dangerous_patterns:
                if re.search(pattern, path_str, re.IGNORECASE):
                    return False, f"Path '{path}' matches restricted pattern"
            
            # Check for dangerous file extensions
            dangerous_extensions = {'.so', '.dll', '.exe', '.bat', '.cmd', '.scr'}
            if resolved_path.suffix.lower() in dangerous_extensions:
                return False, f"File extension '{resolved_path.suffix}' is not allowed"
            
            return True, None
            
        except Exception as e:
            return False, f"Error resolving path: {str(e)}"
    
    def create_sandbox_directory(self, base_name: str = "sandbox") -> str:
        """
        Create a temporary sandbox directory.
        
        Args:
            base_name: Base name for the directory
            
        Returns:
            Path to the created directory
        """
        temp_dir = tempfile.mkdtemp(prefix=f"{base_name}_")
        self.temp_dirs.add(temp_dir)
        self.allowed_paths.add(temp_dir)
        return temp_dir
    
    def cleanup_sandbox_directories(self):
        """Clean up all sandbox directories."""
        for temp_dir in self.temp_dirs.copy():
            try:
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir, ignore_errors=True)
                self.temp_dirs.remove(temp_dir)
                self.allowed_paths.discard(temp_dir)
            except Exception as e:
                logger.error(f"Error cleaning up sandbox directory {temp_dir}: {e}")

class NetworkSecurity:
    """Network security controls."""
    
    def __init__(self):
        self.allowed_ports = {80, 443, 8000, 8080, 8443, 8765}  # Common web ports
        self.blocked_ports = {22, 23, 25, 53, 110, 143, 993, 995}  # System ports
        self.port_assignments = {}  # Track port assignments
        
    def is_port_allowed(self, port: int) -> Tuple[bool, Optional[str]]:
        """
        Check if a port is allowed for use.
        
        Args:
            port: The port number to check
            
        Returns:
            Tuple of (is_allowed, reason)
        """
        if port in self.blocked_ports:
            return False, f"Port {port} is blocked (system port)"
        
        if port < 1024:
            return False, f"Port {port} is privileged (< 1024)"
        
        if port > 65535:
            return False, f"Port {port} is invalid (> 65535)"
        
        return True, None
    
    def allocate_port(self, preferred_port: Optional[int] = None) -> Optional[int]:
        """
        Allocate a port for use.
        
        Args:
            preferred_port: Preferred port number
            
        Returns:
            Allocated port number or None if allocation failed
        """
        if preferred_port:
            is_allowed, reason = self.is_port_allowed(preferred_port)
            if not is_allowed:
                logger.warning(f"Port {preferred_port} not allowed: {reason}")
                return None
            
            if self._is_port_available(preferred_port):
                self.port_assignments[preferred_port] = time.time()
                return preferred_port
        
        # Find available port in allowed range
        for port in range(8000, 9000):
            is_allowed, _ = self.is_port_allowed(port)
            if is_allowed and self._is_port_available(port):
                self.port_assignments[port] = time.time()
                return port
        
        return None
    
    def _is_port_available(self, port: int) -> bool:
        """Check if a port is available."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('127.0.0.1', port))
                return True
        except OSError:
            return False
    
    def release_port(self, port: int):
        """Release a port allocation."""
        self.port_assignments.pop(port, None)

class InputValidator:
    """Input validation and sanitization."""
    
    def __init__(self):
        self.max_input_length = 10000  # Maximum input length
        self.suspicious_patterns = [
            r'<script',  # XSS attempts
            r'javascript:',  # JavaScript URLs
            r'data:',  # Data URLs
            r'vbscript:',  # VBScript URLs
            r'onload=',  # Event handlers
            r'onclick=',  # Event handlers
            r'onerror=',  # Event handlers
            r'\\x',  # Hex encoding
            r'\\u',  # Unicode encoding
            r'%3C',  # URL encoded <
            r'%3E',  # URL encoded >
            r'&lt;',  # HTML encoded <
            r'&gt;',  # HTML encoded >
        ]
    
    def validate_input(self, input_data: str, input_type: str = "general") -> Tuple[bool, Optional[str]]:
        """
        Validate input data.
        
        Args:
            input_data: The input to validate
            input_type: Type of input (code, command, text, etc.)
            
        Returns:
            Tuple of (is_valid, reason)
        """
        # Check length
        if len(input_data) > self.max_input_length:
            return False, f"Input too long: {len(input_data)} > {self.max_input_length}"
        
        # Check for suspicious patterns
        for pattern in self.suspicious_patterns:
            if re.search(pattern, input_data, re.IGNORECASE):
                return False, f"Input contains suspicious pattern: {pattern}"
        
        # Additional validation based on input type
        if input_type == "code":
            return self._validate_code(input_data)
        elif input_type == "command":
            return self._validate_command(input_data)
        elif input_type == "filename":
            return self._validate_filename(input_data)
        
        return True, None
    
    def _validate_code(self, code: str) -> Tuple[bool, Optional[str]]:
        """Validate code input with balanced restrictions."""
        # Only block the most dangerous patterns - allow normal Python usage
        truly_dangerous = [
            'os.system(',  # Direct system calls
            'subprocess.call(',  # Direct subprocess calls
            'subprocess.run(',  # Direct subprocess calls
            'subprocess.Popen(',  # Direct subprocess calls
            'eval(',  # Eval calls
            'exec(',  # Exec calls
            '__import__("os")',  # Direct os import bypass
            '__import__(\'os\')',  # Direct os import bypass
        ]
        
        for dangerous in truly_dangerous:
            if dangerous in code:
                return False, f"Code contains dangerous pattern: {dangerous}"
        
        return True, None
    
    def _validate_command(self, command: str) -> Tuple[bool, Optional[str]]:
        """Validate command input with balanced restrictions."""
        # Only check for the most dangerous injection patterns
        dangerous_injection_patterns = [
            r';.*rm\s+-rf\s+/',  # Chained root deletion
            r'&&.*rm\s+-rf\s+/',  # Conditional root deletion
            r'\|\|.*rm\s+-rf\s+/',  # Alternative root deletion
            r'`rm\s+-rf\s+/`',  # Backtick root deletion
            r'\$\(rm\s+-rf\s+/\)',  # Command substitution root deletion
            r';.*sudo\s+',  # Chained sudo commands
            r'&&.*sudo\s+',  # Conditional sudo commands
        ]
        
        for pattern in dangerous_injection_patterns:
            if re.search(pattern, command, re.IGNORECASE):
                return False, f"Command contains dangerous injection pattern: {pattern}"
        
        return True, None
    
    def _validate_filename(self, filename: str) -> Tuple[bool, Optional[str]]:
        """Validate filename input."""
        # Check for path traversal
        if '..' in filename or filename.startswith('/'):
            return False, "Filename contains path traversal"
        
        # Check for dangerous characters
        dangerous_chars = ['<', '>', ':', '"', '|', '?', '*', '\x00']
        for char in dangerous_chars:
            if char in filename:
                return False, f"Filename contains dangerous character: {char}"
        
        return True, None

class SecurityAuditor:
    """Security audit logging and monitoring."""
    
    def __init__(self):
        self.violations = []
        self.max_violations = 1000
        self.audit_log = []
        
    def log_violation(self, violation: SecurityViolation):
        """Log a security violation."""
        self.violations.append(violation)
        
        # Keep only recent violations
        if len(self.violations) > self.max_violations:
            self.violations = self.violations[-self.max_violations:]
        
        # Log to system logger
        logger.warning(f"Security violation: {violation.type} - {violation.message}")
        
        # Store in audit log
        self.audit_log.append({
            'timestamp': violation.timestamp,
            'level': violation.level.value,
            'type': violation.type,
            'message': violation.message,
            'input_hash': hashlib.sha256(violation.input_data.encode()).hexdigest()[:16]
        })
    
    def get_violations(self, level: Optional[SecurityLevel] = None, 
                      since: Optional[float] = None) -> List[SecurityViolation]:
        """Get security violations."""
        violations = self.violations
        
        if level:
            violations = [v for v in violations if v.level == level]
        
        if since:
            violations = [v for v in violations if v.timestamp >= since]
        
        return violations
    
    def get_security_summary(self) -> Dict[str, Any]:
        """Get security summary statistics."""
        if not self.violations:
            return {
                'total_violations': 0,
                'violations_by_level': {},
                'violations_by_type': {},
                'recent_violations': 0
            }
        
        recent_time = time.time() - 3600  # Last hour
        recent_violations = [v for v in self.violations if v.timestamp >= recent_time]
        
        violations_by_level = {}
        violations_by_type = {}
        
        for v in self.violations:
            level = v.level.value
            violations_by_level[level] = violations_by_level.get(level, 0) + 1
            violations_by_type[v.type] = violations_by_type.get(v.type, 0) + 1
        
        return {
            'total_violations': len(self.violations),
            'violations_by_level': violations_by_level,
            'violations_by_type': violations_by_type,
            'recent_violations': len(recent_violations)
        }

class ResourceLimiter:
    """Resource limiting and sandboxing capabilities."""
    
    def __init__(self):
        self.default_limits = {
            'max_execution_time': 30,  # seconds
            'max_memory_mb': 512,      # MB
            'max_processes': 10,       # number of processes
            'max_file_size_mb': 100,   # MB per file
            'max_total_files': 1000,   # total files in workspace
        }
        
    def get_resource_limits(self, security_level: SecurityLevel) -> Dict[str, Any]:
        """Get resource limits based on security level."""
        limits = self.default_limits.copy()
        
        if security_level == SecurityLevel.LOW:
            limits.update({
                'max_execution_time': 60,
                'max_memory_mb': 1024,
                'max_processes': 20,
            })
        elif security_level == SecurityLevel.HIGH:
            limits.update({
                'max_execution_time': 15,
                'max_memory_mb': 256,
                'max_processes': 5,
            })
        elif security_level == SecurityLevel.CRITICAL:
            limits.update({
                'max_execution_time': 10,
                'max_memory_mb': 128,
                'max_processes': 3,
            })
        
        return limits
    
    def apply_resource_limits(self, limits: Dict[str, Any]) -> None:
        """Apply resource limits to the current process."""
        try:
            import resource
            
            # Set memory limit (Unix only)
            if 'max_memory_mb' in limits:
                memory_bytes = limits['max_memory_mb'] * 1024 * 1024
                resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
            
            # Set CPU time limit (Unix only)
            if 'max_execution_time' in limits:
                cpu_time = limits['max_execution_time']
                resource.setrlimit(resource.RLIMIT_CPU, (cpu_time, cpu_time))
            
            # Set process limit (Unix only)
            if 'max_processes' in limits:
                max_procs = limits['max_processes']
                resource.setrlimit(resource.RLIMIT_NPROC, (max_procs, max_procs))
                
        except ImportError:
            # Resource module not available on Windows
            logger.info("Resource module not available (Windows), using alternative limits")
            self._apply_windows_limits(limits)
        except Exception as e:
            logger.warning(f"Failed to apply resource limits: {e}")
    
    def _apply_windows_limits(self, limits: Dict[str, Any]) -> None:
        """Apply resource limits on Windows using alternative methods."""
        # On Windows, we can't use the resource module, but we can still
        # track and enforce limits in our execution context
        logger.info(f"Resource limits configured: {limits}")
        # Store limits for later enforcement during execution
        self._active_limits = limits


class SecurityManager:
    """Main security manager coordinating all security components with balanced restrictions."""
    
    def __init__(self, security_level: SecurityLevel = SecurityLevel.MEDIUM):
        self.security_level = security_level
        self.command_filter = CommandFilter()
        self.filesystem_security = FileSystemSecurity()
        self.network_security = NetworkSecurity()
        self.input_validator = InputValidator()
        self.resource_limiter = ResourceLimiter()
        self.auditor = SecurityAuditor()
        
        logger.info(f"Security manager initialized with level: {security_level.value}")
    
    def check_command_security(self, command: str) -> Tuple[bool, Optional[SecurityViolation]]:
        """Check if a command is safe to execute with balanced security policies."""
        # Validate input
        is_valid, reason = self.input_validator.validate_input(command, "command")
        if not is_valid:
            violation = SecurityViolation(
                level=SecurityLevel.HIGH,
                type="input_validation",
                message=f"Command failed validation: {reason}",
                input_data=command,
                timestamp=time.time(),
                remediation="Ensure command contains only safe characters and is within length limits"
            )
            self.auditor.log_violation(violation)
            return False, violation
        
        # Check command patterns with current security level
        is_safe, violation = self.command_filter.check_command(command, self.security_level)
        
        # Log violation if found
        if not is_safe and violation:
            self.auditor.log_violation(violation)
        
        return is_safe, violation
    
    def check_python_code_security(self, code: str) -> Tuple[bool, Optional[SecurityViolation]]:
        """Check if Python code is safe to execute with balanced restrictions."""
        # Validate input
        is_valid, reason = self.input_validator.validate_input(code, "code")
        if not is_valid:
            violation = SecurityViolation(
                level=SecurityLevel.HIGH,
                type="input_validation",
                message=f"Python code failed validation: {reason}",
                input_data=code,
                timestamp=time.time(),
                remediation="Ensure code contains only safe characters and is within length limits"
            )
            self.auditor.log_violation(violation)
            return False, violation
        
        # Check for truly dangerous Python patterns
        dangerous_python_patterns = [
            r'__import__\s*\(\s*["\']os["\']',  # Direct os import
            r'exec\s*\(',  # Exec calls
            r'eval\s*\(',  # Eval calls
            r'compile\s*\(',  # Compile calls
            r'globals\s*\(\)',  # Globals access
            r'locals\s*\(\)',  # Locals access
            r'open\s*\(\s*["\'][/\\]',  # Opening system paths
            r'subprocess\.',  # Subprocess usage
            r'os\.system',  # OS system calls
            r'os\.popen',  # OS popen calls
            r'os\.spawn',  # OS spawn calls
        ]
        
        # Only block truly dangerous patterns in Python code
        for pattern in dangerous_python_patterns:
            if re.search(pattern, code, re.IGNORECASE):
                violation = SecurityViolation(
                    level=SecurityLevel.HIGH,
                    type="dangerous_python_code",
                    message=f"Python code contains potentially dangerous pattern",
                    input_data=code,
                    timestamp=time.time(),
                    remediation="Use safer alternatives or import modules explicitly"
                )
                self.auditor.log_violation(violation)
                return False, violation
        
        return True, None
    
    def check_path_security(self, path: str) -> Tuple[bool, Optional[str]]:
        """Check if a path is safe to access."""
        return self.filesystem_security.is_path_allowed(path)
    
    def allocate_secure_port(self, preferred_port: Optional[int] = None) -> Optional[int]:
        """Allocate a secure port."""
        return self.network_security.allocate_port(preferred_port)
    
    def create_secure_workspace(self) -> str:
        """Create a secure workspace directory."""
        return self.filesystem_security.create_sandbox_directory()
    
    def apply_resource_limits(self) -> Dict[str, Any]:
        """Apply resource limits based on current security level."""
        limits = self.resource_limiter.get_resource_limits(self.security_level)
        self.resource_limiter.apply_resource_limits(limits)
        return limits
    
    def get_resource_limits(self) -> Dict[str, Any]:
        """Get resource limits for current security level."""
        return self.resource_limiter.get_resource_limits(self.security_level)
    
    def cleanup_security_resources(self):
        """Clean up security-related resources."""
        self.filesystem_security.cleanup_sandbox_directories()
    
    def get_security_status(self) -> Dict[str, Any]:
        """Get comprehensive security status."""
        return {
            'security_level': self.security_level.value,
            'audit_summary': self.auditor.get_security_summary(),
            'active_ports': len(self.network_security.port_assignments),
            'sandbox_directories': len(self.filesystem_security.temp_dirs),
            'allowed_paths': len(self.filesystem_security.allowed_paths)
        }

# Global security manager instance
_security_manager = None

def get_security_manager(level: SecurityLevel = SecurityLevel.MEDIUM) -> SecurityManager:
    """Get the global security manager instance."""
    global _security_manager
    if _security_manager is None or _security_manager.security_level != level:
        _security_manager = SecurityManager(level)
    return _security_manager
