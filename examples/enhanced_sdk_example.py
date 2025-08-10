"""
Enhanced Sandbox SDK Examples

This example demonstrates the merged capabilities of the enhanced sandbox SDK,
showing both local and remote execution capabilities.
"""

import asyncio
import os
from sandbox import PythonSandbox, NodeSandbox, LocalSandbox, RemoteSandbox, SandboxOptions


async def local_execution_example():
    """Example of local Python execution with artifact capture."""
    print("=== Local Python Execution Example ===")
    
    async with PythonSandbox.create_local(name="local-example") as sandbox:
        # Execute simple Python code
        exec_result = await sandbox.run("print('Hello from local sandbox!')")
        print(f"Output: {await exec_result.output()}")
        
        # Execute matplotlib example with artifact capture
        matplotlib_code = """
import matplotlib.pyplot as plt
import numpy as np

# Generate sample data
x = np.linspace(0, 10, 100)
y = np.sin(x)

# Create plot
plt.figure(figsize=(10, 6))
plt.plot(x, y, 'b-', linewidth=2, label='sin(x)')
plt.title('Sine Wave - Local Execution')
plt.xlabel('x')
plt.ylabel('sin(x)')
plt.legend()
plt.grid(True)
plt.show()  # This will automatically save to artifacts
"""
        
        exec_result = await sandbox.run(matplotlib_code)
        print(f"Matplotlib execution status: {exec_result.status}")
        print(f"Artifacts created: {exec_result.artifacts}")
        
        # Execute shell commands
        cmd_result = await sandbox.command.run("ls", ["-la"])
        print(f"Shell command output: {await cmd_result.output()}")


async def remote_execution_example():
    """Example of remote Python execution via microsandbox server."""
    print("\n=== Remote Python Execution Example ===")
    
    # Check if we have server configuration
    server_url = os.getenv("MSB_SERVER_URL", "http://127.0.0.1:5555")
    api_key = os.getenv("MSB_API_KEY")
    
    if not api_key:
        print("Skipping remote execution - no API key configured")
        return
    
    try:
        async with PythonSandbox.create_remote(
            server_url=server_url,
            api_key=api_key,
            name="remote-example"
        ) as sandbox:
            # Execute Python code remotely
            exec_result = await sandbox.run("print('Hello from remote sandbox!')")
            print(f"Remote output: {await exec_result.output()}")
            
            # Execute more complex code
            complex_code = """
import os
import sys
print(f"Python version: {sys.version}")
print(f"Current directory: {os.getcwd()}")
print("Remote execution successful!")
"""
            
            exec_result = await sandbox.run(complex_code)
            print(f"Complex code output: {await exec_result.output()}")
            
            # Get metrics
            metrics = await sandbox.metrics.all()
            print(f"Sandbox metrics: {metrics}")
            
    except Exception as e:
        print(f"Remote execution failed: {e}")


async def node_execution_example():
    """Example of Node.js execution via microsandbox server."""
    print("\n=== Node.js Execution Example ===")
    
    server_url = os.getenv("MSB_SERVER_URL", "http://127.0.0.1:5555")
    api_key = os.getenv("MSB_API_KEY")
    
    if not api_key:
        print("Skipping Node.js execution - no API key configured")
        return
    
    try:
        async with NodeSandbox.create(
            server_url=server_url,
            api_key=api_key,
            name="node-example"
        ) as sandbox:
            # Execute JavaScript code
            js_code = """
console.log('Hello from Node.js sandbox!');
const version = process.version;
console.log(`Node.js version: ${version}`);

// Simple calculation
const numbers = [1, 2, 3, 4, 5];
const sum = numbers.reduce((a, b) => a + b, 0);
console.log(`Sum of numbers: ${sum}`);
"""
            
            exec_result = await sandbox.run(js_code)
            print(f"JavaScript output: {await exec_result.output()}")
            
    except Exception as e:
        print(f"Node.js execution failed: {e}")


async def builder_pattern_example():
    """Example using the builder pattern for configuration."""
    print("\n=== Builder Pattern Configuration Example ===")
    
    # Create configuration using builder pattern
    config = (SandboxOptions.builder()
              .name("builder-example")
              .memory(1024)
              .cpus(2.0)
              .timeout(300.0)
              .env("EXAMPLE_VAR", "builder_value")
              .build())
    
    async with LocalSandbox.create(
        name=config.name,
        **config.__dict__
    ) as sandbox:
        # Test environment variable
        exec_result = await sandbox.run("import os; print(f'ENV VAR: {os.environ.get(\"EXAMPLE_VAR\", \"not_set\")}')")
        print(f"Environment test: {await exec_result.output()}")
        
        # Get execution info
        if hasattr(sandbox, 'get_execution_info'):
            info = sandbox.get_execution_info()
            print(f"Execution info: {info}")


async def error_handling_example():
    """Example of error handling in both local and remote execution."""
    print("\n=== Error Handling Example ===")
    
    async with LocalSandbox.create(name="error-example") as sandbox:
        # Test syntax error
        exec_result = await sandbox.run("print('hello'")  # Missing closing quote
        print(f"Syntax error detected: {exec_result.has_error()}")
        if exec_result.has_error():
            print(f"Error output: {await exec_result.error()}")
        
        # Test runtime error
        exec_result = await sandbox.run("1/0")  # Division by zero
        print(f"Runtime error detected: {exec_result.has_error()}")
        if exec_result.has_error():
            print(f"Error output: {await exec_result.error()}")


async def command_execution_example():
    """Example of command execution with security filtering."""
    print("\n=== Command Execution Example ===")
    
    async with LocalSandbox.create(name="command-example") as sandbox:
        # Safe command
        cmd_result = await sandbox.command.run("echo", ["Hello World"])
        print(f"Echo command: {await cmd_result.output()}")
        
        # Command with timeout
        cmd_result = await sandbox.command.run("sleep", ["1"], timeout=2)
        print(f"Sleep command completed: {not cmd_result.timeout}")
        
        # Blocked dangerous command
        cmd_result = await sandbox.command.run("rm", ["-rf", "/tmp"])
        print(f"Dangerous command blocked: {cmd_result.has_error()}")
        if cmd_result.has_error():
            print(f"Security message: {await cmd_result.error()}")


async def main():
    """Run all examples."""
    print("Enhanced Sandbox SDK Examples")
    print("=" * 50)
    
    # Local execution examples
    await local_execution_example()
    await builder_pattern_example()
    await error_handling_example()
    await command_execution_example()
    
    # Remote execution examples (if configured)
    await remote_execution_example()
    await node_execution_example()
    
    print("\n" + "=" * 50)
    print("All examples completed!")


if __name__ == "__main__":
    asyncio.run(main())
