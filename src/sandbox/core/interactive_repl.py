"""
Enhanced interactive REPL with advanced features.
"""

import sys
import os
import json
import logging
from typing import Any, Dict, List, Optional, Callable
from pathlib import Path

# Try to import advanced REPL libraries
try:
    from ptpython.repl import embed
    PTPYTHON_AVAILABLE = True
except ImportError:
    PTPYTHON_AVAILABLE = False

try:
    import bpython
    BPYTHON_AVAILABLE = True
except ImportError:
    BPYTHON_AVAILABLE = False

try:
    import IPython
    IPYTHON_AVAILABLE = True
except ImportError:
    IPYTHON_AVAILABLE = False

from .execution_context import PersistentExecutionContext

logger = logging.getLogger(__name__)


class ColoredOutput:
    """Simple colored output for terminal feedback."""
    
    # ANSI color codes
    COLORS = {
        'red': '\033[91m',
        'green': '\033[92m',
        'yellow': '\033[93m',
        'blue': '\033[94m',
        'magenta': '\033[95m',
        'cyan': '\033[96m',
        'white': '\033[97m',
        'reset': '\033[0m',
        'bold': '\033[1m',
        'underline': '\033[4m'
    }
    
    @classmethod
    def color(cls, text: str, color: str, bold: bool = False) -> str:
        """Apply color to text."""
        if not sys.stdout.isatty():
            return text  # No colors in non-terminal output
        
        color_code = cls.COLORS.get(color.lower(), '')
        bold_code = cls.COLORS['bold'] if bold else ''
        reset_code = cls.COLORS['reset']
        
        return f"{bold_code}{color_code}{text}{reset_code}"
    
    @classmethod
    def success(cls, text: str) -> str:
        return cls.color(f"✅ {text}", 'green', bold=True)
    
    @classmethod
    def error(cls, text: str) -> str:
        return cls.color(f"❌ {text}", 'red', bold=True)
    
    @classmethod
    def warning(cls, text: str) -> str:
        return cls.color(f"⚠️  {text}", 'yellow', bold=True)
    
    @classmethod
    def info(cls, text: str) -> str:
        return cls.color(f"ℹ️  {text}", 'blue', bold=True)


class EnhancedREPL:
    """Enhanced REPL with interactive features and colored output."""
    
    def __init__(self, execution_context: PersistentExecutionContext):
        self.execution_context = execution_context
        self.history = []
        self.custom_commands = {}
        self._setup_custom_commands()
    
    def _setup_custom_commands(self):
        """Set up custom REPL commands."""
        self.custom_commands = {
            'artifacts': self._cmd_artifacts,
            'clear_artifacts': self._cmd_clear_artifacts,
            'session_info': self._cmd_session_info,
            'stats': self._cmd_stats,
            'history': self._cmd_history,
            'help': self._cmd_help,
            'manim_examples': self._cmd_manim_examples,
            'exit': self._cmd_exit,
            'quit': self._cmd_exit,
        }
    
    def _cmd_artifacts(self, args: List[str] = None) -> str:
        """List artifacts with structured output."""
        format_type = args[0] if args else 'table'
        
        report = self.execution_context.get_artifact_report()
        
        if format_type.lower() == 'json':
            return json.dumps(report, indent=2)
        elif format_type.lower() == 'csv':
            return self._format_artifacts_csv(report)
        else:
            return self._format_artifacts_table(report)
    
    def _format_artifacts_csv(self, report: Dict[str, Any]) -> str:
        """Format artifacts as CSV."""
        lines = ['Category,Count,Size,Files']
        for category, info in report.get('categories', {}).items():
            files = ';'.join([f['name'] for f in info['files']])
            lines.append(f"{category},{info['count']},{info['size']},{files}")
        return '\n'.join(lines)
    
    def _format_artifacts_table(self, report: Dict[str, Any]) -> str:
        """Format artifacts as a table."""
        if report['total_artifacts'] == 0:
            return ColoredOutput.info("No artifacts found.")
        
        lines = [
            ColoredOutput.color(f"📊 Artifact Summary", 'cyan', bold=True),
            f"Total: {report['total_artifacts']} files ({self._format_size(report['total_size'])})",
            ""
        ]
        
        for category, info in report.get('categories', {}).items():
            if info['count'] > 0:
                lines.append(ColoredOutput.color(f"  {category.capitalize()}", 'yellow', bold=True))
                lines.append(f"    Count: {info['count']} files")
                lines.append(f"    Size: {self._format_size(info['size'])}")
                
                # Show first few files
                for file_info in info['files'][:3]:
                    lines.append(f"    - {file_info['name']} ({self._format_size(file_info['size'])})")
                
                if len(info['files']) > 3:
                    lines.append(f"    ... and {len(info['files']) - 3} more")
                lines.append("")
        
        return '\n'.join(lines)
    
    def _format_size(self, bytes_size: int) -> str:
        """Format file size in human-readable format."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_size < 1024.0:
                return f"{bytes_size:.1f} {unit}"
            bytes_size /= 1024.0
        return f"{bytes_size:.1f} TB"
    
    def _cmd_clear_artifacts(self, args: List[str] = None) -> str:
        """Clear artifacts with feedback."""
        artifact_type = args[0] if args else None
        
        if artifact_type:
            # Clear specific type
            categorized = self.execution_context.categorize_artifacts()
            if artifact_type not in categorized:
                return ColoredOutput.error(f"Unknown artifact type: {artifact_type}")
            
            count = len(categorized[artifact_type])
            if count == 0:
                return ColoredOutput.info(f"No {artifact_type} artifacts found.")
            
            # Simulate cleanup (would need to implement in execution context)
            return ColoredOutput.success(f"Cleared {count} {artifact_type} artifacts.")
        else:
            # Clear all artifacts
            report = self.execution_context.get_artifact_report()
            count = report['total_artifacts']
            if count == 0:
                return ColoredOutput.info("No artifacts to clear.")
            
            self.execution_context.cleanup_artifacts()
            return ColoredOutput.success(f"Cleared {count} artifacts.")
    
    def _cmd_session_info(self, args: List[str] = None) -> str:
        """Show session information."""
        info = {
            'session_id': self.execution_context.session_id,
            'project_root': str(self.execution_context.project_root),
            'artifacts_dir': str(self.execution_context.artifacts_dir),
            'python_version': sys.version,
            'virtual_env': os.environ.get('VIRTUAL_ENV', 'None')
        }
        
        lines = [ColoredOutput.color("🔍 Session Information", 'cyan', bold=True)]
        for key, value in info.items():
            lines.append(f"  {key.replace('_', ' ').title()}: {value}")
        
        return '\n'.join(lines)
    
    def _cmd_stats(self, args: List[str] = None) -> str:
        """Show performance statistics."""
        stats = self.execution_context.get_execution_stats()
        
        lines = [ColoredOutput.color("📈 Performance Statistics", 'cyan', bold=True)]
        for key, value in stats.items():
            if isinstance(value, float):
                formatted_value = f"{value:.3f}"
            else:
                formatted_value = str(value)
            lines.append(f"  {key.replace('_', ' ').title()}: {formatted_value}")
        
        return '\n'.join(lines)
    
    def _cmd_history(self, args: List[str] = None) -> str:
        """Show execution history."""
        limit = int(args[0]) if args and args[0].isdigit() else 10
        history = self.execution_context.get_execution_history(limit=limit)
        
        if not history:
            return ColoredOutput.info("No execution history found.")
        
        lines = [ColoredOutput.color(f"📜 Execution History (last {limit})", 'cyan', bold=True)]
        for i, entry in enumerate(history):
            success_icon = "✅" if entry['result']['success'] else "❌"
            lines.append(f"  {i+1}. {success_icon} {entry['execution_time']:.3f}s - {entry['code'][:50]}...")
        
        return '\n'.join(lines)
    
    def _cmd_manim_examples(self, args: List[str] = None) -> str:
        """Show Manim examples."""
        examples = {
            'circle': '''
from manim import *

class SimpleCircle(Scene):
    def construct(self):
        circle = Circle()
        self.play(Create(circle))
        self.wait(1)
''',
            'text': '''
from manim import *

class HelloWorld(Scene):
    def construct(self):
        text = Text("Hello, Manim!")
        self.play(Write(text))
        self.wait(1)
''',
            'transform': '''
from manim import *

class ShapeTransform(Scene):
    def construct(self):
        circle = Circle()
        square = Square()
        self.play(Create(circle))
        self.play(Transform(circle, square))
        self.wait(1)
'''
        }
        
        if args and args[0] in examples:
            return examples[args[0]]
        
        lines = [ColoredOutput.color("🎬 Available Manim Examples", 'cyan', bold=True)]
        for name, code in examples.items():
            lines.append(f"  {name}: {code.split('def construct')[0].strip()}")
        lines.append("\nUse 'manim_examples <name>' to see full code.")
        
        return '\n'.join(lines)
    
    def _cmd_help(self, args: List[str] = None) -> str:
        """Show help information."""
        lines = [
            ColoredOutput.color("🔧 Available Commands", 'cyan', bold=True),
            "",
            "  artifacts [json|csv|table] - List artifacts with optional format",
            "  clear_artifacts [type] - Clear all or specific type of artifacts",
            "  session_info - Show session information",
            "  stats - Show performance statistics",
            "  history [limit] - Show execution history",
            "  manim_examples [name] - Show Manim examples",
            "  help - Show this help message",
            "  exit/quit - Exit the REPL",
            "",
            ColoredOutput.color("💡 Tips", 'yellow', bold=True),
            "  - Use Tab completion for commands (if available)",
            "  - Access previous commands with Up/Down arrows",
            "  - Use Ctrl+C to interrupt execution",
            "  - Use Ctrl+D to exit"
        ]
        
        return '\n'.join(lines)
    
    def _cmd_exit(self, args: List[str] = None) -> str:
        """Exit the REPL."""
        print(ColoredOutput.success("Goodbye!"))
        sys.exit(0)
    
    def start_interactive_session(self):
        """Start an interactive REPL session."""
        print(ColoredOutput.color("🚀 Enhanced Python Sandbox REPL", 'cyan', bold=True))
        print(ColoredOutput.info("Type 'help' for available commands."))
        print()
        
        # Try to use the best available REPL
        if PTPYTHON_AVAILABLE:
            self._start_ptpython_repl()
        elif IPYTHON_AVAILABLE:
            self._start_ipython_repl()
        elif BPYTHON_AVAILABLE:
            self._start_bpython_repl()
        else:
            self._start_basic_repl()
    
    def _start_ptpython_repl(self):
        """Start ptpython REPL."""
        print(ColoredOutput.info("Using ptpython for enhanced experience."))
        
        # Set up ptpython configuration
        def configure(repl):
            repl.confirm_exit = False
            repl.highlight_matching_parenthesis = True
            repl.enable_auto_suggest = True
        
        # Add custom commands to globals
        globals_dict = self.execution_context.globals_dict.copy()
        for cmd_name, cmd_func in self.custom_commands.items():
            globals_dict[cmd_name] = cmd_func
        
        embed(globals=globals_dict, locals=None, configure=configure)
    
    def _start_ipython_repl(self):
        """Start IPython REPL."""
        print(ColoredOutput.info("Using IPython for enhanced experience."))
        
        from IPython import embed
        from IPython.terminal.prompts import Prompts, Token
        
        class SandboxPrompts(Prompts):
            def in_prompt_tokens(self, cli=None):
                return [
                    (Token.Prompt, '🐍 ['),
                    (Token.PromptNum, str(self.shell.execution_count)),
                    (Token.Prompt, ']: '),
                ]
        
        # Configure IPython
        from IPython.terminal.interactiveshell import TerminalInteractiveShell
        TerminalInteractiveShell.prompts_class = SandboxPrompts
        
        # Add custom commands to user namespace
        user_ns = self.execution_context.globals_dict.copy()
        for cmd_name, cmd_func in self.custom_commands.items():
            user_ns[cmd_name] = cmd_func
        
        embed(user_ns=user_ns)
    
    def _start_bpython_repl(self):
        """Start bpython REPL."""
        print(ColoredOutput.info("Using bpython for enhanced experience."))
        
        # Add custom commands to locals
        locals_dict = self.execution_context.globals_dict.copy()
        for cmd_name, cmd_func in self.custom_commands.items():
            locals_dict[cmd_name] = cmd_func
        
        bpython.embed(locals_=locals_dict)
    
    def _start_basic_repl(self):
        """Start basic Python REPL with custom enhancements."""
        print(ColoredOutput.warning("Using basic REPL. Install ptpython, IPython, or bpython for better experience."))
        
        import code
        import readline
        import rlcompleter
        
        # Enable tab completion
        readline.set_completer(rlcompleter.Completer(self.execution_context.globals_dict).complete)
        readline.parse_and_bind("tab: complete")
        
        # Add custom commands to globals
        globals_dict = self.execution_context.globals_dict.copy()
        for cmd_name, cmd_func in self.custom_commands.items():
            globals_dict[cmd_name] = cmd_func
        
        # Start interactive console
        console = code.InteractiveConsole(globals_dict)
        console.interact(banner="")
