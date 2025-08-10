#!/usr/bin/env python3
"""
Enhanced Sandbox System Demonstration

This script demonstrates the complete enhanced sandbox system with:
1. Enhanced artifact management with categorization
2. Improved REPL with IPython support  
3. Complete Manim support with virtual environment integration
4. Performance monitoring and caching
5. Detailed error handling and feedback

Usage:
    python enhanced_sandbox_demo.py
"""

import sys
import asyncio
import json
from pathlib import Path

# Add the sandbox package to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sandbox.sdk import PythonSandbox


async def demo_enhanced_artifact_management():
    """Demo enhanced artifact management system."""
    print("🎨 Enhanced Artifact Management System Demo")
    print("=" * 50)
    
    sandbox_cm = await PythonSandbox.create_local()
    async with sandbox_cm as sandbox:
        await sandbox.start()
        
        # Create various types of artifacts
        code = """
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image
import json

# Create a plot
x = np.linspace(0, 10, 100)
y = np.sin(x)
plt.figure(figsize=(8, 6))
plt.plot(x, y, 'b-', linewidth=2)
plt.title('Sine Wave')
plt.xlabel('X')
plt.ylabel('Y')
plt.grid(True)
plt.show()

# Create an image
img = Image.new('RGB', (200, 200), color='red')
img.save('artifacts/images/sample_image.png')

# Create data file
data = {'x': x.tolist(), 'y': y.tolist()}
with open('artifacts/data/sine_data.json', 'w') as f:
    json.dump(data, f)

print("Created various artifacts!")
"""
        
        result = await sandbox.run(code)
        output = await result.output()
        print(f"Execution output: {output}")
        
        # Get artifact report
        report = sandbox.get_artifact_report()
        print(f"\n📊 Artifact Report:")
        print(f"Total artifacts: {report['total_artifacts']}")
        print(f"Total size: {report['total_size'] / 1024:.2f} KB")
        
        for category, info in report['categories'].items():
            print(f"  {category}: {info['count']} files ({info['size'] / 1024:.2f} KB)")
        
        # Get categorized artifacts
        categorized = sandbox.categorize_artifacts()
        print(f"\n📁 Categorized Artifacts:")
        for category, files in categorized.items():
            if files:
                print(f"  {category}:")
                for file_info in files:
                    print(f"    - {file_info['name']} ({file_info['size']} bytes)")
        
        # Get human-readable summary
        summary = sandbox.get_artifact_summary()
        print(f"\n📝 Artifact Summary:")
        print(summary)


async def demo_manim_support():
    """Demo enhanced Manim support."""
    print("\n🎬 Enhanced Manim Support Demo")
    print("=" * 50)
    
    sandbox_cm = await PythonSandbox.create_local()
    async with sandbox_cm as sandbox:
        await sandbox.start()
        
        # Create a simple Manim animation
        manim_code = """
from manim import *

class SimpleAnimation(Scene):
    def construct(self):
        # Create a circle
        circle = Circle(radius=2, color=BLUE)
        circle.set_fill(BLUE, opacity=0.5)
        
        # Create text
        text = Text("Hello, Manim!", font_size=48)
        text.set_color(WHITE)
        text.move_to(UP * 2.5)
        
        # Animate
        self.play(Create(circle))
        self.play(Write(text))
        self.play(circle.animate.set_color(RED))
        self.play(text.animate.scale(1.5))
        self.wait(2)
"""
        
        result = await sandbox.run(manim_code)
        output = await result.output()
        print(f"Manim code execution: {output}")
        
        # Get Manim-specific artifacts
        manim_artifacts = sandbox.get_manim_artifacts()
        print(f"\n🎥 Manim Artifacts:")
        for artifact in manim_artifacts:
            print(f"  - {artifact['name']}: {artifact['size']} bytes")


async def demo_performance_monitoring():
    """Demo performance monitoring and caching."""
    print("\n⚡ Performance Monitoring Demo")
    print("=" * 50)
    
    sandbox_cm = await PythonSandbox.create_local()
    async with sandbox_cm as sandbox:
        await sandbox.start()
        
        # Execute some code multiple times to show caching
        code = """
import time
import numpy as np

# Some computational work
data = np.random.randn(1000, 1000)
result = np.linalg.svd(data)
print(f"SVD computation completed")
"""
        
        # Run first time
        print("First execution:")
        result1 = await sandbox.run(code)
        stats1 = sandbox.get_performance_stats()
        print(f"Cache hits: {stats1['cache_hits']}, Cache misses: {stats1['cache_misses']}")
        
        # Run second time (should use cache)
        print("\nSecond execution:")
        result2 = await sandbox.run(code)
        stats2 = sandbox.get_performance_stats()
        print(f"Cache hits: {stats2['cache_hits']}, Cache misses: {stats2['cache_misses']}")
        print(f"Cache hit ratio: {stats2['cache_hit_ratio']:.2%}")
        
        # Get execution history
        history = sandbox.get_execution_history(limit=5)
        print(f"\n📈 Execution History (last 5):")
        for i, entry in enumerate(history):
            print(f"  {i+1}. Success: {entry['result']['success']}, "
                  f"Time: {entry['execution_time']:.3f}s")


async def demo_error_handling():
    """Demo enhanced error handling and feedback."""
    print("\n🚨 Enhanced Error Handling Demo")
    print("=" * 50)
    
    sandbox_cm = await PythonSandbox.create_local()
    async with sandbox_cm as sandbox:
        await sandbox.start()
        
        # Test import error
        code_with_import_error = """
import nonexistent_module
print("This won't run")
"""
        
        print("Testing import error:")
        result = await sandbox.run(code_with_import_error)
        if result.exception:
            print(f"Error handled: {result.exception}")
        
        # Test syntax error
        code_with_syntax_error = """
def broken_function(
    print("Missing closing parenthesis")
"""
        
        print("\nTesting syntax error:")
        result = await sandbox.run(code_with_syntax_error)
        if result.exception:
            print(f"Error handled: {result.exception}")
        
        # Test runtime error
        code_with_runtime_error = """
x = 1 / 0
"""
        
        print("\nTesting runtime error:")
        result = await sandbox.run(code_with_runtime_error)
        if result.exception:
            print(f"Error handled: {result.exception}")


async def demo_session_management():
    """Demo session management and persistence."""
    print("\n💾 Session Management Demo")
    print("=" * 50)
    
    sandbox_cm = await PythonSandbox.create_local()
    async with sandbox_cm as sandbox:
        await sandbox.start()
        
        # Set up some session variables
        setup_code = """
import numpy as np
import matplotlib.pyplot as plt

# Create some session variables
session_data = {
    'user_name': 'Demo User',
    'project_name': 'Enhanced Sandbox Demo',
    'data': np.random.randn(100)
}

counter = 0
print(f"Session initialized: {session_data['project_name']}")
"""
        
        await sandbox.run(setup_code)
        
        # Save session
        sandbox.save_session()
        print(f"Session saved with ID: {sandbox.session_id}")
        
        # Use session variables
        use_session_code = """
counter += 1
print(f"Counter: {counter}")
print(f"User: {session_data['user_name']}")
print(f"Data shape: {session_data['data'].shape}")

# Create a plot using session data
plt.figure(figsize=(10, 6))
plt.hist(session_data['data'], bins=20, alpha=0.7)
plt.title(f"{session_data['project_name']} - Data Distribution")
plt.xlabel('Value')
plt.ylabel('Frequency')
plt.show()
"""
        
        result = await sandbox.run(use_session_code)
        output = await result.output()
        print(f"Session usage result: {output}")
        
        # Get execution info
        info = sandbox.get_execution_info()
        print(f"\n🔍 Execution Environment Info:")
        print(f"Python version: {info['python_version']}")
        print(f"Virtual env: {info['virtual_env']}")
        print(f"Project root: {info['project_root']}")
        print(f"Artifacts dir: {info['artifacts_dir']}")


async def demo_cleanup_management():
    """Demo cleanup and management features."""
    print("\n🧹 Cleanup Management Demo")
    print("=" * 50)
    
    sandbox_cm = await PythonSandbox.create_local()
    async with sandbox_cm as sandbox:
        await sandbox.start()
        
        # Create various artifacts
        code = """
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

# Create multiple plots
for i in range(3):
    plt.figure(figsize=(6, 4))
    plt.plot(np.random.randn(100))
    plt.title(f'Plot {i+1}')
    plt.show()

# Create multiple images
for i in range(2):
    img = Image.new('RGB', (100, 100), color=(i*50, 100, 200))
    img.save(f'artifacts/images/image_{i}.png')

print("Created multiple artifacts")
"""
        
        await sandbox.run(code)
        
        # Show initial artifact count
        report = sandbox.get_artifact_report()
        print(f"Initial artifacts: {report['total_artifacts']}")
        
        # Cleanup specific type
        cleaned_plots = sandbox.cleanup_artifacts_by_type('plots')
        print(f"Cleaned {cleaned_plots} plot artifacts")
        
        # Show updated count
        report = sandbox.get_artifact_report()
        print(f"Remaining artifacts: {report['total_artifacts']}")
        
        # Clear cache
        sandbox.clear_cache()
        print("Cache cleared")
        
        # Get final stats
        stats = sandbox.get_performance_stats()
        print(f"Final stats: {stats}")


async def main():
    """Run all demos."""
    print("🚀 Enhanced Sandbox System - Complete Demo")
    print("=" * 60)
    
    try:
        await demo_enhanced_artifact_management()
        await demo_manim_support()
        await demo_performance_monitoring()
        await demo_error_handling()
        await demo_session_management()
        await demo_cleanup_management()
        
        print("\n✅ All demos completed successfully!")
        print("\nKey Features Demonstrated:")
        print("✓ Enhanced artifact management with categorization")
        print("✓ Improved Manim support with virtual environment")
        print("✓ Performance monitoring and caching")
        print("✓ Comprehensive error handling")
        print("✓ Session management and persistence")
        print("✓ Cleanup and management tools")
        
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
