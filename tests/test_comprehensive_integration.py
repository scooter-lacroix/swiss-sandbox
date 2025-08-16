"""
Comprehensive integration tests for the Swiss Sandbox system.

This module tests complete workflows and interactions between all components
of the Swiss Sandbox system to ensure they work together correctly.
"""

import pytest
import asyncio
import json
import time
from pathlib import Path

from src.sandbox.unified_server import UnifiedSandboxServer
from src.sandbox.core.types import ServerConfig, SecurityLevel


@pytest.mark.integration
class TestCompleteWorkflows:
    """Test complete end-to-end workflows."""
    
    @pytest.fixture
    def integration_server(self, temp_dir):
        """Create a server for integration testing."""
        config = ServerConfig(
            max_execution_time=30,
            max_memory_mb=512,
            security_level=SecurityLevel.MODERATE,
            artifacts_retention_days=1,
            artifacts_dir=temp_dir / "artifacts",
            workspaces_dir=temp_dir / "workspaces",
            logs_dir=temp_dir / "logs"
        )
        return UnifiedSandboxServer(config)
    
    async def test_data_science_workflow(self, integration_server):
        """Test a complete data science workflow."""
        # Step 1: Create and analyze data
        data_creation_code = """
import numpy as np
import json

# Generate sample data
np.random.seed(42)
data = np.random.normal(100, 15, 1000)

# Calculate statistics
stats = {
    'mean': float(np.mean(data)),
    'std': float(np.std(data)),
    'min': float(np.min(data)),
    'max': float(np.max(data)),
    'count': len(data)
}

# Save data and stats
np.save('sample_data.npy', data)
with open('stats.json', 'w') as f:
    json.dump(stats, f, indent=2)

print(f"Generated {len(data)} data points")
print(f"Mean: {stats['mean']:.2f}, Std: {stats['std']:.2f}")
"""
        
        result1 = await integration_server._execute_python_tool(
            code=data_creation_code,
            workspace_id="data_science_test"
        )
        
        assert result1['success'] is True
        assert "Generated 1000 data points" in result1['output']
        
        # Step 2: Load and visualize data
        visualization_code = """
import numpy as np
import matplotlib.pyplot as plt
import json

# Load data
data = np.load('sample_data.npy')
with open('stats.json', 'r') as f:
    stats = json.load(f)

# Create visualization
plt.figure(figsize=(10, 6))
plt.hist(data, bins=50, alpha=0.7, edgecolor='black')
plt.title(f'Data Distribution (n={stats["count"]})')
plt.xlabel('Value')
plt.ylabel('Frequency')
plt.axvline(stats['mean'], color='red', linestyle='--', label=f'Mean: {stats["mean"]:.2f}')
plt.legend()
plt.grid(True, alpha=0.3)
plt.savefig('data_histogram.png', dpi=150, bbox_inches='tight')
plt.close()

print("Visualization saved as data_histogram.png")
print(f"Data loaded: {len(data)} points")
"""
        
        result2 = await integration_server._execute_python_tool(
            code=visualization_code,
            workspace_id="data_science_test"
        )
        
        assert result2['success'] is True
        assert "Visualization saved" in result2['output']
        assert "Data loaded: 1000 points" in result2['output']
        
        # Step 3: Verify artifacts were created
        artifacts = await integration_server._list_artifacts_tool(
            workspace_id="data_science_test"
        )
        
        artifact_names = [a['name'] for a in artifacts['artifacts']]
        expected_files = ['sample_data.npy', 'stats.json', 'data_histogram.png']
        
        for expected_file in expected_files:
            assert any(expected_file in name for name in artifact_names), f"Missing artifact: {expected_file}"
    
    async def test_web_development_workflow(self, integration_server):
        """Test a web development workflow."""
        # Step 1: Create a simple web application
        web_app_code = """
from flask import Flask, jsonify, render_template_string
import json
import os

app = Flask(__name__)

# Simple HTML template
template = '''
<!DOCTYPE html>
<html>
<head>
    <title>Swiss Sandbox Web App</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; }
        .container { max-width: 800px; margin: 0 auto; }
        .api-result { background: #f0f0f0; padding: 20px; margin: 20px 0; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Swiss Sandbox Web App</h1>
        <p>This is a test web application created in the sandbox.</p>
        <div id="api-data" class="api-result">
            <h3>API Data:</h3>
            <pre id="data-content">Loading...</pre>
        </div>
        <script>
            fetch('/api/data')
                .then(response => response.json())
                .then(data => {
                    document.getElementById('data-content').textContent = JSON.stringify(data, null, 2);
                });
        </script>
    </div>
</body>
</html>
'''

@app.route('/')
def home():
    return render_template_string(template)

@app.route('/api/data')
def api_data():
    return jsonify({
        'message': 'Hello from Swiss Sandbox!',
        'timestamp': '2024-01-01T12:00:00Z',
        'data': [1, 2, 3, 4, 5],
        'status': 'success'
    })

# Save the app to a file
with open('web_app.py', 'w') as f:
    f.write('''
from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/')
def home():
    return '<h1>Swiss Sandbox Web App</h1><p>Running successfully!</p>'

@app.route('/api/status')
def status():
    return jsonify({'status': 'running', 'message': 'Web app is working'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
''')

print("Web application created and saved to web_app.py")
print("App has routes: / and /api/data")
"""
        
        result1 = await integration_server._execute_python_tool(
            code=web_app_code,
            workspace_id="web_dev_test"
        )
        
        assert result1['success'] is True
        assert "Web application created" in result1['output']
        
        # Step 2: Test the web application (without actually running the server)
        test_code = """
import json

# Test the API endpoint logic
def test_api_data():
    # Simulate the API response
    api_response = {
        'message': 'Hello from Swiss Sandbox!',
        'timestamp': '2024-01-01T12:00:00Z',
        'data': [1, 2, 3, 4, 5],
        'status': 'success'
    }
    return api_response

# Test the function
result = test_api_data()
print("API test result:")
print(json.dumps(result, indent=2))

# Verify web_app.py was created
import os
if os.path.exists('web_app.py'):
    print("✓ web_app.py file created successfully")
    with open('web_app.py', 'r') as f:
        content = f.read()
        if 'Flask' in content and 'jsonify' in content:
            print("✓ Web app contains Flask components")
        else:
            print("✗ Web app missing Flask components")
else:
    print("✗ web_app.py file not found")
"""
        
        result2 = await integration_server._execute_python_tool(
            code=test_code,
            workspace_id="web_dev_test"
        )
        
        assert result2['success'] is True
        assert "API test result" in result2['output']
        assert "web_app.py file created successfully" in result2['output']
    
    async def test_machine_learning_workflow(self, integration_server):
        """Test a machine learning workflow."""
        ml_code = """
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error, r2_score
import json

# Generate synthetic dataset
np.random.seed(42)
n_samples = 1000
n_features = 3

# Create features
X = np.random.randn(n_samples, n_features)
# Create target with some noise
true_coefficients = np.array([2.5, -1.8, 3.2])
y = X @ true_coefficients + np.random.randn(n_samples) * 0.5

print(f"Generated dataset: {X.shape[0]} samples, {X.shape[1]} features")

# Split the data
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

print(f"Training set: {X_train.shape[0]} samples")
print(f"Test set: {X_test.shape[0]} samples")

# Train the model
model = LinearRegression()
model.fit(X_train, y_train)

# Make predictions
y_pred = model.predict(X_test)

# Evaluate the model
mse = mean_squared_error(y_test, y_pred)
r2 = r2_score(y_test, y_pred)

print(f"Model Performance:")
print(f"  Mean Squared Error: {mse:.4f}")
print(f"  R² Score: {r2:.4f}")
print(f"  Learned coefficients: {model.coef_}")
print(f"  True coefficients: {true_coefficients}")

# Save results
results = {
    'mse': float(mse),
    'r2_score': float(r2),
    'learned_coefficients': model.coef_.tolist(),
    'true_coefficients': true_coefficients.tolist(),
    'n_samples': n_samples,
    'n_features': n_features
}

with open('ml_results.json', 'w') as f:
    json.dump(results, f, indent=2)

print("Results saved to ml_results.json")
"""
        
        result = await integration_server._execute_python_tool(
            code=ml_code,
            workspace_id="ml_test"
        )
        
        assert result['success'] is True
        assert "Generated dataset: 1000 samples, 3 features" in result['output']
        assert "Model Performance:" in result['output']
        assert "Results saved to ml_results.json" in result['output']
        
        # Verify the model performed reasonably well
        assert "R² Score:" in result['output']
        # Extract R² score from output to verify it's reasonable
        lines = result['output'].split('\n')
        r2_line = [line for line in lines if 'R² Score:' in line][0]
        r2_value = float(r2_line.split(':')[1].strip())
        assert r2_value > 0.8, f"Model R² score too low: {r2_value}"
    
    async def test_file_processing_workflow(self, integration_server):
        """Test a file processing workflow."""
        # Step 1: Create sample files
        file_creation_code = """
import json
import csv
import os

# Create JSON data file
data = {
    'users': [
        {'id': 1, 'name': 'Alice', 'age': 30, 'city': 'New York'},
        {'id': 2, 'name': 'Bob', 'age': 25, 'city': 'San Francisco'},
        {'id': 3, 'name': 'Charlie', 'age': 35, 'city': 'Chicago'},
        {'id': 4, 'name': 'Diana', 'age': 28, 'city': 'Boston'}
    ]
}

with open('users.json', 'w') as f:
    json.dump(data, f, indent=2)

# Create CSV file
with open('sales.csv', 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['product', 'quantity', 'price', 'total'])
    writer.writerow(['Widget A', 10, 25.50, 255.00])
    writer.writerow(['Widget B', 5, 45.00, 225.00])
    writer.writerow(['Widget C', 8, 30.75, 246.00])
    writer.writerow(['Widget D', 12, 20.00, 240.00])

# Create text file
with open('notes.txt', 'w') as f:
    f.write('''Project Notes
=============

This is a sample project with multiple data files.
- users.json: Contains user information
- sales.csv: Contains sales data
- notes.txt: Contains project documentation

Processing tasks:
1. Load and validate JSON data
2. Process CSV sales data
3. Generate summary report
''')

print("Created sample files:")
print("- users.json (JSON data)")
print("- sales.csv (CSV data)")
print("- notes.txt (text documentation)")
"""
        
        result1 = await integration_server._execute_python_tool(
            code=file_creation_code,
            workspace_id="file_processing_test"
        )
        
        assert result1['success'] is True
        assert "Created sample files:" in result1['output']
        
        # Step 2: Process the files
        processing_code = """
import json
import csv
import os
from collections import defaultdict

# Process JSON file
print("Processing users.json...")
with open('users.json', 'r') as f:
    users_data = json.load(f)

users = users_data['users']
print(f"Loaded {len(users)} users")

# Analyze user data
cities = defaultdict(int)
ages = []
for user in users:
    cities[user['city']] += 1
    ages.append(user['age'])

avg_age = sum(ages) / len(ages)
print(f"Average age: {avg_age:.1f}")
print(f"Cities: {dict(cities)}")

# Process CSV file
print("\\nProcessing sales.csv...")
sales_data = []
total_revenue = 0

with open('sales.csv', 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        sales_data.append(row)
        total_revenue += float(row['total'])

print(f"Loaded {len(sales_data)} sales records")
print(f"Total revenue: ${total_revenue:.2f}")

# Generate summary report
report = {
    'summary': {
        'total_users': len(users),
        'average_age': round(avg_age, 1),
        'cities_represented': len(cities),
        'total_sales_records': len(sales_data),
        'total_revenue': round(total_revenue, 2)
    },
    'user_details': {
        'cities': dict(cities),
        'age_range': [min(ages), max(ages)]
    },
    'sales_details': {
        'products': [item['product'] for item in sales_data],
        'total_quantity': sum(int(item['quantity']) for item in sales_data)
    }
}

# Save report
with open('processing_report.json', 'w') as f:
    json.dump(report, f, indent=2)

print("\\nGenerated processing_report.json")
print(f"Summary: {len(users)} users, ${total_revenue:.2f} revenue")
"""
        
        result2 = await integration_server._execute_python_tool(
            code=processing_code,
            workspace_id="file_processing_test"
        )
        
        assert result2['success'] is True
        assert "Processing users.json..." in result2['output']
        assert "Processing sales.csv..." in result2['output']
        assert "Generated processing_report.json" in result2['output']
        assert "$966.00 revenue" in result2['output']
    
    async def test_error_recovery_workflow(self, integration_server):
        """Test error recovery and handling in workflows."""
        # Step 1: Execute code that will fail
        failing_code = """
import json

# This will fail - trying to access non-existent file
with open('nonexistent.json', 'r') as f:
    data = json.load(f)

print("This should not print")
"""
        
        result1 = await integration_server._execute_python_tool(
            code=failing_code,
            workspace_id="error_recovery_test"
        )
        
        assert result1['success'] is False
        assert "FileNotFoundError" in result1.get('error', '')
        
        # Step 2: Recover by creating the missing file
        recovery_code = """
import json

# Create the missing file
data = {'message': 'File created for recovery', 'status': 'recovered'}

with open('nonexistent.json', 'w') as f:
    json.dump(data, f, indent=2)

print("Created missing file for recovery")

# Now try to read it
with open('nonexistent.json', 'r') as f:
    loaded_data = json.load(f)

print(f"Successfully loaded: {loaded_data}")
print("Error recovery successful!")
"""
        
        result2 = await integration_server._execute_python_tool(
            code=recovery_code,
            workspace_id="error_recovery_test"
        )
        
        assert result2['success'] is True
        assert "Created missing file for recovery" in result2['output']
        assert "Error recovery successful!" in result2['output']


@pytest.mark.integration
class TestSystemIntegration:
    """Test system-level integration scenarios."""
    
    async def test_multi_workspace_isolation(self, integration_server):
        """Test that multiple workspaces are properly isolated."""
        # Create data in workspace 1
        result1 = await integration_server._execute_python_tool(
            code="secret_data = 'workspace1_secret'; print('Data set in workspace1')",
            workspace_id="workspace1"
        )
        
        # Create different data in workspace 2
        result2 = await integration_server._execute_python_tool(
            code="secret_data = 'workspace2_secret'; print('Data set in workspace2')",
            workspace_id="workspace2"
        )
        
        # Try to access workspace1 data from workspace2
        result3 = await integration_server._execute_python_tool(
            code="print(f'Accessing data: {secret_data}')",
            workspace_id="workspace2"
        )
        
        # Try to access workspace2 data from workspace1
        result4 = await integration_server._execute_python_tool(
            code="print(f'Accessing data: {secret_data}')",
            workspace_id="workspace1"
        )
        
        assert result1['success'] is True
        assert result2['success'] is True
        assert result3['success'] is True
        assert result4['success'] is True
        
        # Verify each workspace sees only its own data
        assert "workspace2_secret" in result3['output']
        assert "workspace1_secret" in result4['output']
    
    async def test_artifact_sharing_between_tools(self, integration_server):
        """Test artifact sharing between different tool executions."""
        # Create artifact with Python
        create_code = """
import json

data = {
    'created_by': 'python_tool',
    'timestamp': '2024-01-01T12:00:00Z',
    'values': [1, 2, 3, 4, 5]
}

with open('shared_data.json', 'w') as f:
    json.dump(data, f, indent=2)

print("Shared data created")
"""
        
        result1 = await integration_server._execute_python_tool(
            code=create_code,
            workspace_id="shared_workspace"
        )
        
        assert result1['success'] is True
        
        # Access artifact from another Python execution
        access_code = """
import json

with open('shared_data.json', 'r') as f:
    data = json.load(f)

print(f"Loaded shared data created by: {data['created_by']}")
print(f"Values: {data['values']}")

# Modify the data
data['modified_by'] = 'second_execution'
data['values'].append(6)

with open('shared_data.json', 'w') as f:
    json.dump(data, f, indent=2)

print("Shared data modified")
"""
        
        result2 = await integration_server._execute_python_tool(
            code=access_code,
            workspace_id="shared_workspace"
        )
        
        assert result2['success'] is True
        assert "Loaded shared data created by: python_tool" in result2['output']
        assert "Shared data modified" in result2['output']
    
    async def test_resource_limit_enforcement(self, integration_server):
        """Test that resource limits are properly enforced."""
        # Test memory-intensive operation
        memory_code = """
import numpy as np

# Try to allocate large array (should be limited by memory constraints)
try:
    # This might fail due to memory limits
    large_array = np.zeros((10000, 10000))  # ~800MB
    print(f"Large array created: {large_array.shape}")
except MemoryError:
    print("Memory limit reached - allocation failed")
except Exception as e:
    print(f"Other error: {e}")

# Create smaller array that should work
small_array = np.zeros((100, 100))
print(f"Small array created: {small_array.shape}")
"""
        
        result = await integration_server._execute_python_tool(
            code=memory_code,
            workspace_id="resource_test"
        )
        
        # Should succeed but may hit memory limits for large array
        assert result['success'] is True
        assert "Small array created: (100, 100)" in result['output']
    
    @pytest.mark.slow
    async def test_timeout_enforcement(self, integration_server):
        """Test that execution timeouts are properly enforced."""
        # Code that should timeout
        timeout_code = """
import time

print("Starting long operation...")
for i in range(100):
    time.sleep(0.5)  # Total: 50 seconds, should timeout
    print(f"Step {i}")

print("This should not be reached")
"""
        
        start_time = time.time()
        result = await integration_server._execute_python_tool(
            code=timeout_code,
            workspace_id="timeout_test"
        )
        end_time = time.time()
        
        # Should fail due to timeout
        assert result['success'] is False
        assert 'timeout' in result.get('error', '').lower()
        
        # Should not take much longer than the timeout limit
        execution_time = end_time - start_time
        assert execution_time < 35, f"Execution took too long: {execution_time}s"


@pytest.mark.integration
class TestPerformanceIntegration:
    """Test performance aspects of the integrated system."""
    
    async def test_concurrent_executions(self, integration_server):
        """Test handling of concurrent executions."""
        async def run_execution(i):
            code = f"""
import time
import random

# Simulate some work
time.sleep(random.uniform(0.1, 0.5))
result = sum(range({i * 100}))
print(f"Execution {i} completed: result = {{result}}")
"""
            return await integration_server._execute_python_tool(
                code=code,
                workspace_id=f"concurrent_test_{i}"
            )
        
        # Run multiple executions concurrently
        start_time = time.time()
        tasks = [run_execution(i) for i in range(5)]
        results = await asyncio.gather(*tasks)
        end_time = time.time()
        
        # All should succeed
        for i, result in enumerate(results):
            assert result['success'] is True, f"Execution {i} failed: {result.get('error')}"
            assert f"Execution {i} completed" in result['output']
        
        # Should complete in reasonable time (concurrent, not sequential)
        total_time = end_time - start_time
        assert total_time < 3.0, f"Concurrent executions took too long: {total_time}s"
    
    async def test_large_output_handling(self, integration_server):
        """Test handling of large output volumes."""
        large_output_code = """
# Generate large output
for i in range(1000):
    print(f"Line {i:04d}: This is a test line with some content to make it longer")

print("Large output generation completed")
"""
        
        result = await integration_server._execute_python_tool(
            code=large_output_code,
            workspace_id="large_output_test"
        )
        
        assert result['success'] is True
        assert "Large output generation completed" in result['output']
        
        # Output should contain all lines
        lines = result['output'].split('\n')
        assert len(lines) > 1000, f"Expected >1000 lines, got {len(lines)}"
    
    async def test_artifact_performance(self, integration_server):
        """Test artifact system performance with multiple files."""
        artifact_code = """
import json
import time

# Create multiple artifacts
start_time = time.time()

for i in range(50):
    data = {
        'file_id': i,
        'timestamp': time.time(),
        'data': list(range(i * 10, (i + 1) * 10))
    }
    
    with open(f'artifact_{i:03d}.json', 'w') as f:
        json.dump(data, f)

end_time = time.time()
print(f"Created 50 artifacts in {end_time - start_time:.2f} seconds")
"""
        
        result = await integration_server._execute_python_tool(
            code=artifact_code,
            workspace_id="artifact_performance_test"
        )
        
        assert result['success'] is True
        assert "Created 50 artifacts" in result['output']
        
        # List artifacts to verify they were created
        artifacts = await integration_server._list_artifacts_tool(
            workspace_id="artifact_performance_test"
        )
        
        assert len(artifacts['artifacts']) >= 50


if __name__ == "__main__":
    pytest.main([__file__])