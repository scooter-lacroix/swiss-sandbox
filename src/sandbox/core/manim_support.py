"""
Enhanced Manim support with pre-compiled examples and one-click execution.
"""

import os
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class ManIMExamples:
    """Pre-compiled Manim examples with one-click execution."""
    
    def __init__(self, artifacts_dir: Path):
        self.artifacts_dir = artifacts_dir
        self.manim_dir = artifacts_dir / "manim"
        self.manim_dir.mkdir(exist_ok=True)
        
        # Pre-defined examples with expected outputs
        self.examples = {
            'basic_shapes': {
                'code': '''
from manim import *

class BasicShapes(Scene):
    def construct(self):
        # Create basic shapes
        circle = Circle(color=BLUE)
        square = Square(color=RED)
        triangle = Triangle(color=GREEN)
        
        # Position them
        circle.move_to(LEFT * 2)
        square.move_to(ORIGIN)
        triangle.move_to(RIGHT * 2)
        
        # Animate
        self.play(Create(circle), Create(square), Create(triangle))
        self.wait(1)
        
        # Transform
        self.play(circle.animate.set_color(YELLOW))
        self.play(square.animate.rotate(PI/4))
        self.play(triangle.animate.scale(1.5))
        self.wait(1)
''',
                'description': 'Basic shapes creation and transformation',
                'expected_output': 'MP4 video file showing circle, square, and triangle animations',
                'duration': '~4 seconds',
                'complexity': 'beginner'
            },
            
            'text_animation': {
                'code': '''
from manim import *

class TextAnimation(Scene):
    def construct(self):
        # Create text
        title = Text("Welcome to Manim!", font_size=48)
        subtitle = Text("Mathematical Animation Engine", font_size=32)
        
        # Position
        title.to_edge(UP)
        subtitle.next_to(title, DOWN, buff=0.5)
        
        # Animate
        self.play(Write(title))
        self.wait(0.5)
        self.play(FadeIn(subtitle))
        self.wait(1)
        
        # Transform
        self.play(title.animate.scale(0.8).set_color(BLUE))
        self.play(subtitle.animate.set_color(GREEN))
        self.wait(1)
''',
                'description': 'Text writing and formatting animations',
                'expected_output': 'MP4 video with text animations',
                'duration': '~5 seconds',
                'complexity': 'beginner'
            },
            
            'mathematical_plot': {
                'code': '''
from manim import *

class MathematicalPlot(Scene):
    def construct(self):
        # Create axes
        axes = Axes(
            x_range=[-3, 3, 1],
            y_range=[-2, 2, 1],
            x_length=6,
            y_length=4,
            axis_config={"color": BLUE},
        )
        
        # Create function
        func = axes.plot(lambda x: x**2, color=RED)
        func_label = axes.get_graph_label(func, label="f(x) = x^2")
        
        # Animate
        self.play(Create(axes))
        self.wait(0.5)
        self.play(Create(func))
        self.play(Write(func_label))
        self.wait(2)
''',
                'description': 'Mathematical function plotting',
                'expected_output': 'MP4 video showing axes and parabola animation',
                'duration': '~6 seconds',
                'complexity': 'intermediate'
            },
            
            'geometry_theorem': {
                'code': '''
from manim import *

class GeometryTheorem(Scene):
    def construct(self):
        # Pythagorean theorem visualization
        triangle = RightTriangle(side_length=3)
        triangle.set_color(BLUE)
        
        # Labels
        a_label = MathTex("a").next_to(triangle, DOWN)
        b_label = MathTex("b").next_to(triangle, RIGHT)
        c_label = MathTex("c").next_to(triangle.get_center(), UP+LEFT)
        
        # Theorem
        theorem = MathTex("a^2 + b^2 = c^2").to_edge(UP)
        
        # Animate
        self.play(Create(triangle))
        self.play(Write(a_label), Write(b_label), Write(c_label))
        self.wait(1)
        self.play(Write(theorem))
        self.wait(2)
''',
                'description': 'Pythagorean theorem visualization',
                'expected_output': 'MP4 video showing geometric proof',
                'duration': '~7 seconds',
                'complexity': 'intermediate'
            },
            
            'data_visualization': {
                'code': '''
from manim import *
import numpy as np

class DataVisualization(Scene):
    def construct(self):
        # Create data
        data = [3, 7, 2, 8, 5, 9, 1, 6]
        
        # Create bar chart
        chart = BarChart(
            values=data,
            y_range=[0, 10, 2],
            x_length=6,
            y_length=4,
            bar_colors=[BLUE, RED, GREEN, YELLOW, PURPLE, ORANGE, PINK, TEAL]
        )
        
        # Title
        title = Text("Sample Data Visualization", font_size=36)
        title.to_edge(UP)
        
        # Animate
        self.play(Write(title))
        self.play(Create(chart))
        self.wait(2)
        
        # Animate bars
        self.play(chart.animate.change_bar_values([1, 2, 3, 4, 5, 6, 7, 8]))
        self.wait(2)
''',
                'description': 'Dynamic bar chart visualization',
                'expected_output': 'MP4 video showing animated bar chart',
                'duration': '~8 seconds',
                'complexity': 'advanced'
            },
            
            'physics_simulation': {
                'code': '''
from manim import *

class PhysicsSimulation(Scene):
    def construct(self):
        # Create pendulum
        pivot = Dot(ORIGIN + UP * 2)
        bob = Circle(radius=0.2, color=BLUE, fill_opacity=1)
        bob.move_to(DOWN * 2)
        
        # String
        string = Line(pivot.get_center(), bob.get_center())
        
        # Animate pendulum swing
        self.play(Create(pivot), Create(bob), Create(string))
        
        # Swing animation
        for angle in [PI/6, -PI/6, PI/4, -PI/4, PI/8, -PI/8]:
            new_pos = pivot.get_center() + 2 * np.array([np.sin(angle), -np.cos(angle), 0])
            self.play(
                bob.animate.move_to(new_pos),
                string.animate.put_start_and_end_on(pivot.get_center(), new_pos),
                run_time=0.5
            )
        
        self.wait(1)
''',
                'description': 'Simple pendulum physics simulation',
                'expected_output': 'MP4 video showing pendulum motion',
                'duration': '~6 seconds',
                'complexity': 'advanced'
            }
        }
    
    def list_examples(self) -> Dict[str, Dict[str, Any]]:
        """List all available examples with metadata."""
        return {
            name: {
                'description': info['description'],
                'expected_output': info['expected_output'],
                'duration': info['duration'],
                'complexity': info['complexity']
            }
            for name, info in self.examples.items()
        }
    
    def get_example_code(self, name: str) -> Optional[str]:
        """Get the code for a specific example."""
        if name not in self.examples:
            return None
        return self.examples[name]['code']
    
    def execute_example(self, name: str, quality: str = 'medium') -> Tuple[bool, str, List[str]]:
        """
        Execute a pre-compiled example with one-click execution.
        
        Args:
            name: Example name
            quality: Video quality ('low', 'medium', 'high')
            
        Returns:
            Tuple of (success, message, output_files)
        """
        if name not in self.examples:
            return False, f"Example '{name}' not found", []
        
        try:
            # Create temporary file for the example
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(self.examples[name]['code'])
                temp_file = f.name
            
            # Set up quality parameters
            quality_params = {
                'low': ['-ql'],
                'medium': ['-qm'],
                'high': ['-qh']
            }
            
            # Execute manim
            cmd = [
                'manim', 
                temp_file,
                '--media_dir', str(self.manim_dir),
                '--disable_caching'
            ] + quality_params.get(quality, ['-qm'])
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=str(self.artifacts_dir.parent)
            )
            
            # Clean up temporary file
            os.unlink(temp_file)
            
            if result.returncode == 0:
                # Find generated files
                output_files = []
                for file_path in self.manim_dir.rglob('*'):
                    if file_path.is_file() and file_path.suffix in ['.mp4', '.png', '.gif']:
                        output_files.append(str(file_path))
                
                return True, f"Example '{name}' executed successfully", output_files
            else:
                return False, f"Manim execution failed: {result.stderr}", []
                
        except Exception as e:
            return False, f"Error executing example: {str(e)}", []
    
    def get_supported_animations(self) -> Dict[str, List[str]]:
        """Get list of supported animations by category."""
        return {
            'Creation': [
                'Create', 'Write', 'DrawBorderThenFill', 'ShowIncreasingSubsets',
                'ShowSubmobjectsOneByOne', 'AddTextWordByWord'
            ],
            'Transform': [
                'Transform', 'ReplacementTransform', 'TransformFromCopy',
                'ClockwiseTransform', 'CounterclockwiseTransform'
            ],
            'Movement': [
                'Rotate', 'Rotating', 'MoveToTarget', 'MoveAlongPath',
                'Homotopy', 'SmoothedVectorizedHomotopy'
            ],
            'Fading': [
                'FadeIn', 'FadeOut', 'FadeInFromDown', 'FadeOutAndShift',
                'FadeInFromPoint', 'FadeOutToPoint'
            ],
            'Growing': [
                'GrowFromCenter', 'GrowFromEdge', 'GrowFromPoint',
                'GrowArrow', 'SpinInFromNothing'
            ],
            'Indication': [
                'Indicate', 'Flash', 'CircleIndicate', 'ShowCreationThenDestruction',
                'ShowCreationThenFadeOut', 'AnimationOnSurroundingRectangle'
            ],
            'Specialized': [
                'Wiggle', 'TurnInsideOut', 'LaggedStart', 'LaggedStartMap',
                'Succession', 'AnimationGroup'
            ]
        }
    
    def create_custom_example(self, name: str, code: str, description: str) -> bool:
        """Create a custom example."""
        try:
            self.examples[name] = {
                'code': code,
                'description': description,
                'expected_output': 'Custom animation output',
                'duration': 'Variable',
                'complexity': 'custom'
            }
            return True
        except Exception as e:
            logger.error(f"Failed to create custom example: {e}")
            return False
    
    def export_example(self, name: str, file_path: str) -> bool:
        """Export an example to a file."""
        if name not in self.examples:
            return False
        
        try:
            with open(file_path, 'w') as f:
                f.write(self.examples[name]['code'])
            return True
        except Exception as e:
            logger.error(f"Failed to export example: {e}")
            return False


class ManIMHelper:
    """Helper class for Manim integration."""
    
    def __init__(self, artifacts_dir: Path):
        self.artifacts_dir = artifacts_dir
        self.examples = ManIMExamples(artifacts_dir)
    
    def check_manim_installation(self) -> Tuple[bool, str]:
        """Check if Manim is properly installed."""
        try:
            result = subprocess.run(['manim', '--version'], capture_output=True, text=True)
            if result.returncode == 0:
                return True, result.stdout.strip()
            else:
                return False, "Manim not found in PATH"
        except FileNotFoundError:
            return False, "Manim not installed"
    
    def get_manim_config(self) -> Dict[str, Any]:
        """Get current Manim configuration."""
        try:
            result = subprocess.run(['manim', 'cfg', 'show'], capture_output=True, text=True)
            if result.returncode == 0:
                # Parse configuration (simplified)
                return {'config': result.stdout, 'status': 'available'}
            else:
                return {'config': None, 'status': 'error'}
        except Exception:
            return {'config': None, 'status': 'unavailable'}
    
    def optimize_for_sandbox(self) -> Dict[str, Any]:
        """Optimize Manim settings for sandbox environment."""
        optimizations = {
            'quality': 'medium',
            'format': 'mp4',
            'disable_caching': True,
            'write_to_movie': True,
            'save_last_frame': True,
            'media_dir': str(self.artifacts_dir / 'manim'),
            'verbosity': 'WARNING'
        }
        
        return optimizations
    
    def get_troubleshooting_guide(self) -> Dict[str, str]:
        """Get troubleshooting guide for common Manim issues."""
        return {
            'installation': """
If Manim is not working:
1. Install with: pip install manim
2. For faster rendering: pip install manim[gui]
3. System dependencies may be required (see Manim docs)
            """,
            'rendering_slow': """
To speed up rendering:
1. Use lower quality: -ql flag
2. Disable caching: --disable_caching
3. Reduce frame rate: --frame_rate 15
            """,
            'memory_issues': """
For memory problems:
1. Keep scenes short
2. Use object pooling
3. Clear unused objects with self.remove()
            """,
            'file_not_found': """
If output files are missing:
1. Check media directory permissions
2. Verify file paths in artifacts
3. Check for rendering errors in logs
            """
        }
