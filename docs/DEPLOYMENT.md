# Intelligent Sandbox System - Production Deployment Guide

## Table of Contents
1. [System Requirements](#system-requirements)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [MCP Server Setup](#mcp-server-setup)
5. [Security Configuration](#security-configuration)
6. [Performance Tuning](#performance-tuning)
7. [Monitoring and Maintenance](#monitoring-and-maintenance)
8. [Troubleshooting](#troubleshooting)
9. [API Reference](#api-reference)
10. [Best Practices](#best-practices)

## System Requirements

### Hardware Requirements
- **CPU**: Minimum 4 cores, recommended 8+ cores
- **RAM**: Minimum 8GB, recommended 16GB+
- **Storage**: Minimum 50GB available space
- **Network**: Stable internet connection for package installations

### Software Requirements
- **Operating System**: Linux (Ubuntu 20.04+, RHEL 8+, Fedora 35+) or macOS 11+
- **Python**: 3.9 or higher
- **Docker**: 20.10+ (optional but highly recommended for isolation)
- **Git**: 2.25+

### Python Dependencies
```bash
# Core dependencies
python >= 3.9
fastmcp >= 0.1.0
aiofiles >= 23.0.0
pydantic >= 2.0.0
jinja2 >= 3.1.0
psutil >= 5.9.0

# Optional dependencies for enhanced features
docker >= 6.0.0  # For Docker isolation
pytest >= 7.0.0  # For testing
black >= 22.0.0  # For code formatting
```

## Installation

### 1. Clone the Repository
```bash
git clone https://github.com/your-org/intelligent-sandbox.git
cd intelligent-sandbox
```

### 2. Create Virtual Environment
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### 3. Install Dependencies
```bash
# Install core dependencies
pip install -r requirements.txt

# Install development dependencies (optional)
pip install -r requirements-dev.txt
```

### 4. Install Docker (Recommended)

#### For Ubuntu/Debian:
```bash
sudo apt-get update
sudo apt-get install docker.io
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker $USER
# Log out and back in for group changes to take effect
```

#### For Fedora/RHEL:
```bash
sudo dnf install docker
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker $USER
# Log out and back in for group changes to take effect
```

#### For macOS:
```bash
# Install Docker Desktop from https://www.docker.com/products/docker-desktop
```

### 5. Verify Installation
```bash
python scripts/verify_installation.py
```

## Configuration

### Basic Configuration

Create a configuration file at `config/sandbox.yaml`:

```yaml
# Sandbox Configuration
sandbox:
  # Base directory for sandbox workspaces
  base_dir: /tmp/intelligent_sandbox
  
  # Maximum number of concurrent workspaces
  max_workspaces: 10
  
  # Workspace timeout in seconds
  workspace_timeout: 3600
  
  # Enable automatic cleanup
  auto_cleanup: true
  cleanup_interval: 300

# Isolation Configuration
isolation:
  # Use Docker for isolation (recommended)
  use_docker: true
  
  # Docker container image
  container_image: ubuntu:22.04
  
  # Fallback to process isolation if Docker unavailable
  fallback_isolation: true
  
  # Resource limits
  resource_limits:
    memory_mb: 2048
    cpu_cores: 2
    disk_mb: 5120
    max_processes: 100
    max_open_files: 1000

# Security Configuration
security:
  # Security level: low, medium, high
  level: medium
  
  # Enable network isolation
  network_isolation: true
  
  # Allowed network endpoints (whitelist)
  allowed_endpoints:
    - pypi.org
    - npmjs.org
    - github.com
    - docker.io
  
  # Enable audit logging
  audit_logging: true
  audit_log_path: /var/log/intelligent_sandbox/audit.log

# Logging Configuration
logging:
  # Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL
  level: INFO
  
  # Log format
  format: '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
  
  # Log file path
  file_path: /var/log/intelligent_sandbox/sandbox.log
  
  # Maximum log file size (MB)
  max_size_mb: 100
  
  # Number of backup files to keep
  backup_count: 5

# Cache Configuration
cache:
  # Enable caching
  enabled: true
  
  # Cache directory
  cache_dir: /var/cache/intelligent_sandbox
  
  # Maximum cache size (MB)
  max_size_mb: 1000
  
  # Cache TTL in seconds
  ttl: 3600
  
  # Cache cleanup interval
  cleanup_interval: 600

# Performance Configuration
performance:
  # Enable performance monitoring
  monitoring_enabled: true
  
  # Metrics collection interval (seconds)
  metrics_interval: 60
  
  # Enable profiling
  profiling_enabled: false
  
  # Maximum concurrent operations
  max_concurrent_operations: 20
  
  # Operation timeout (seconds)
  operation_timeout: 300
```

### Environment Variables

Create a `.env` file for sensitive configuration:

```bash
# API Keys and Secrets
SANDBOX_API_KEY=your-secure-api-key-here
SANDBOX_SECRET_KEY=your-secret-key-here

# Database Configuration (if using external database)
DATABASE_URL=postgresql://user:password@localhost/sandbox_db

# Redis Configuration (if using Redis for caching)
REDIS_URL=redis://localhost:6379/0

# Docker Registry (if using private registry)
DOCKER_REGISTRY_URL=registry.example.com
DOCKER_REGISTRY_USER=username
DOCKER_REGISTRY_PASSWORD=password

# External Service URLs
CODE_ANALYSIS_API=https://api.example.com/analyze
DEPENDENCY_CHECK_API=https://api.example.com/dependencies
```

## MCP Server Setup

### 1. Configure MCP Server

Create `mcp_config.json`:

```json
{
  "server": {
    "name": "intelligent-sandbox",
    "version": "1.0.0",
    "description": "Intelligent Sandbox MCP Server",
    "protocol_version": "1.0"
  },
  "transport": {
    "type": "stdio",
    "encoding": "utf-8"
  },
  "tools": [
    {
      "name": "create_workspace",
      "description": "Create a new isolated workspace",
      "parameters": {
        "source_path": "string",
        "workspace_id": "string"
      }
    },
    {
      "name": "analyze_codebase",
      "description": "Analyze codebase structure and dependencies",
      "parameters": {
        "workspace_id": "string"
      }
    },
    {
      "name": "create_task_plan",
      "description": "Create an intelligent task plan",
      "parameters": {
        "workspace_id": "string",
        "task_description": "string"
      }
    },
    {
      "name": "execute_task_plan",
      "description": "Execute a task plan",
      "parameters": {
        "plan_id": "string"
      }
    },
    {
      "name": "get_execution_history",
      "description": "Get execution history for a workspace",
      "parameters": {
        "workspace_id": "string"
      }
    },
    {
      "name": "destroy_workspace",
      "description": "Destroy a workspace and clean up resources",
      "parameters": {
        "workspace_id": "string"
      }
    },
    {
      "name": "get_sandbox_status",
      "description": "Get current sandbox system status",
      "parameters": {}
    }
  ],
  "authentication": {
    "enabled": true,
    "type": "api_key",
    "header": "X-API-Key"
  },
  "rate_limiting": {
    "enabled": true,
    "requests_per_minute": 60,
    "burst_size": 10
  }
}
```

### 2. Start MCP Server

```bash
# Start in development mode
python -m sandbox.intelligent.mcp.server --dev

# Start in production mode
python -m sandbox.intelligent.mcp.server --config mcp_config.json

# Start with systemd (recommended for production)
sudo systemctl start intelligent-sandbox-mcp
sudo systemctl enable intelligent-sandbox-mcp
```

### 3. Create systemd Service

Create `/etc/systemd/system/intelligent-sandbox-mcp.service`:

```ini
[Unit]
Description=Intelligent Sandbox MCP Server
After=network.target docker.service
Requires=docker.service

[Service]
Type=simple
User=sandbox
Group=sandbox
WorkingDirectory=/opt/intelligent-sandbox
Environment="PATH=/opt/intelligent-sandbox/.venv/bin:/usr/local/bin:/usr/bin:/bin"
EnvironmentFile=/opt/intelligent-sandbox/.env
ExecStart=/opt/intelligent-sandbox/.venv/bin/python -m sandbox.intelligent.mcp.server --config /opt/intelligent-sandbox/mcp_config.json
Restart=always
RestartSec=10
StandardOutput=append:/var/log/intelligent-sandbox/mcp.log
StandardError=append:/var/log/intelligent-sandbox/mcp-error.log

[Install]
WantedBy=multi-user.target
```

## Security Configuration

### 1. Create Sandbox User

```bash
# Create dedicated user for sandbox
sudo useradd -r -s /bin/bash -m -d /opt/intelligent-sandbox sandbox
sudo usermod -aG docker sandbox
```

### 2. Set File Permissions

```bash
# Set ownership
sudo chown -R sandbox:sandbox /opt/intelligent-sandbox
sudo chown -R sandbox:sandbox /var/log/intelligent-sandbox
sudo chown -R sandbox:sandbox /var/cache/intelligent-sandbox

# Set permissions
sudo chmod 750 /opt/intelligent-sandbox
sudo chmod 750 /var/log/intelligent-sandbox
sudo chmod 750 /var/cache/intelligent-sandbox
```

### 3. Configure Firewall

```bash
# Allow MCP server port (if using network transport)
sudo ufw allow 8080/tcp comment 'Intelligent Sandbox MCP'

# Enable firewall
sudo ufw enable
```

### 4. SELinux Configuration (RHEL/Fedora)

```bash
# Create SELinux policy
sudo semanage fcontext -a -t container_runtime_exec_t "/opt/intelligent-sandbox(/.*)?"
sudo restorecon -Rv /opt/intelligent-sandbox
```

### 5. AppArmor Configuration (Ubuntu/Debian)

Create `/etc/apparmor.d/intelligent-sandbox`:

```
#include <tunables/global>

/opt/intelligent-sandbox/.venv/bin/python {
  #include <abstractions/base>
  #include <abstractions/python>
  
  /opt/intelligent-sandbox/ r,
  /opt/intelligent-sandbox/** r,
  /opt/intelligent-sandbox/.venv/** mr,
  /tmp/intelligent_sandbox/** rw,
  /var/log/intelligent-sandbox/** w,
  /var/cache/intelligent-sandbox/** rw,
  
  # Docker socket access
  /var/run/docker.sock rw,
  
  # Network access
  network inet stream,
  network inet6 stream,
}
```

## Performance Tuning

### 1. System Kernel Parameters

Add to `/etc/sysctl.d/99-intelligent-sandbox.conf`:

```bash
# Increase file descriptor limits
fs.file-max = 2097152
fs.nr_open = 1048576

# Increase network buffers
net.core.rmem_max = 134217728
net.core.wmem_max = 134217728
net.ipv4.tcp_rmem = 4096 87380 134217728
net.ipv4.tcp_wmem = 4096 65536 134217728

# Increase memory limits
vm.max_map_count = 262144
vm.swappiness = 10
```

Apply changes:
```bash
sudo sysctl -p /etc/sysctl.d/99-intelligent-sandbox.conf
```

### 2. Docker Performance Tuning

Edit `/etc/docker/daemon.json`:

```json
{
  "storage-driver": "overlay2",
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  },
  "default-ulimits": {
    "nofile": {
      "Name": "nofile",
      "Hard": 65536,
      "Soft": 65536
    }
  },
  "debug": false,
  "experimental": true
}
```

### 3. Python Optimization

```bash
# Enable Python optimization
export PYTHONOPTIMIZE=1

# Use PyPy for better performance (optional)
pypy3 -m pip install -r requirements.txt
pypy3 -m sandbox.intelligent.mcp.server
```

### 4. Database Optimization (if using PostgreSQL)

```sql
-- Optimize for sandbox workloads
ALTER SYSTEM SET shared_buffers = '2GB';
ALTER SYSTEM SET effective_cache_size = '6GB';
ALTER SYSTEM SET maintenance_work_mem = '512MB';
ALTER SYSTEM SET checkpoint_completion_target = 0.9;
ALTER SYSTEM SET wal_buffers = '16MB';
ALTER SYSTEM SET default_statistics_target = 100;
ALTER SYSTEM SET random_page_cost = 1.1;

-- Reload configuration
SELECT pg_reload_conf();
```

## Monitoring and Maintenance

### 1. Set Up Monitoring

#### Prometheus Configuration

Add to `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'intelligent-sandbox'
    static_configs:
      - targets: ['localhost:9090']
    metrics_path: '/metrics'
```

#### Grafana Dashboard

Import the provided dashboard from `monitoring/grafana-dashboard.json`

### 2. Log Rotation

Create `/etc/logrotate.d/intelligent-sandbox`:

```
/var/log/intelligent-sandbox/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 0640 sandbox sandbox
    sharedscripts
    postrotate
        systemctl reload intelligent-sandbox-mcp
    endscript
}
```

### 3. Backup Strategy

```bash
#!/bin/bash
# backup-sandbox.sh

BACKUP_DIR="/backup/intelligent-sandbox/$(date +%Y%m%d)"
mkdir -p "$BACKUP_DIR"

# Backup configuration
cp -r /opt/intelligent-sandbox/config "$BACKUP_DIR/"

# Backup logs
cp -r /var/log/intelligent-sandbox "$BACKUP_DIR/logs/"

# Backup cache (optional)
cp -r /var/cache/intelligent-sandbox "$BACKUP_DIR/cache/"

# Backup database (if applicable)
pg_dump sandbox_db > "$BACKUP_DIR/database.sql"

# Compress backup
tar -czf "$BACKUP_DIR.tar.gz" "$BACKUP_DIR"
rm -rf "$BACKUP_DIR"

# Keep only last 30 days of backups
find /backup/intelligent-sandbox -name "*.tar.gz" -mtime +30 -delete
```

### 4. Health Checks

```python
#!/usr/bin/env python3
# health_check.py

import sys
import requests
import psutil
import docker

def check_mcp_server():
    """Check if MCP server is responding."""
    try:
        response = requests.get('http://localhost:8080/health', timeout=5)
        return response.status_code == 200
    except:
        return False

def check_docker():
    """Check if Docker is available."""
    try:
        client = docker.from_env()
        client.ping()
        return True
    except:
        return False

def check_resources():
    """Check system resources."""
    cpu_percent = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    return {
        'cpu_ok': cpu_percent < 80,
        'memory_ok': memory.percent < 80,
        'disk_ok': disk.percent < 80
    }

if __name__ == '__main__':
    checks = {
        'mcp_server': check_mcp_server(),
        'docker': check_docker(),
        'resources': check_resources()
    }
    
    all_ok = all([
        checks['mcp_server'],
        checks['docker'],
        all(checks['resources'].values())
    ])
    
    if not all_ok:
        print(f"Health check failed: {checks}")
        sys.exit(1)
    
    print("All health checks passed")
    sys.exit(0)
```

## Troubleshooting

### Common Issues and Solutions

#### 1. Docker Not Available

**Symptom**: Warning "Docker not available, falling back to process isolation"

**Solution**:
```bash
# Check Docker status
sudo systemctl status docker

# Start Docker if not running
sudo systemctl start docker

# Verify Docker permissions
docker run hello-world

# If permission denied
sudo usermod -aG docker $USER
# Log out and back in
```

#### 2. Workspace Creation Fails

**Symptom**: Error creating workspace

**Solution**:
```bash
# Check disk space
df -h /tmp

# Clean up old workspaces
rm -rf /tmp/intelligent_sandbox/workspace_*

# Check permissions
ls -la /tmp/intelligent_sandbox

# Recreate directory with correct permissions
sudo mkdir -p /tmp/intelligent_sandbox
sudo chown $USER:$USER /tmp/intelligent_sandbox
chmod 755 /tmp/intelligent_sandbox
```

#### 3. MCP Server Connection Issues

**Symptom**: Cannot connect to MCP server

**Solution**:
```bash
# Check if server is running
ps aux | grep mcp.server

# Check logs
tail -f /var/log/intelligent-sandbox/mcp.log

# Restart server
sudo systemctl restart intelligent-sandbox-mcp

# Check port binding
sudo netstat -tlnp | grep 8080
```

#### 4. High Memory Usage

**Symptom**: System running out of memory

**Solution**:
```bash
# Check current memory usage
free -h

# Find memory-hungry processes
ps aux --sort=-%mem | head

# Adjust memory limits in config
vim /opt/intelligent-sandbox/config/sandbox.yaml
# Reduce resource_limits.memory_mb

# Clear cache
rm -rf /var/cache/intelligent-sandbox/*

# Restart service
sudo systemctl restart intelligent-sandbox-mcp
```

#### 5. Performance Issues

**Symptom**: Slow task execution

**Solution**:
```python
# Run performance profiler
python -m cProfile -o profile.stats scripts/profile_performance.py

# Analyze profile
python -m pstats profile.stats
# sort cumtime
# stats 20

# Enable caching
vim /opt/intelligent-sandbox/config/sandbox.yaml
# Set cache.enabled: true

# Increase worker threads
# Set performance.max_concurrent_operations: 50
```

### Debug Mode

Enable debug logging for detailed troubleshooting:

```bash
# Set debug environment variable
export SANDBOX_DEBUG=1
export SANDBOX_LOG_LEVEL=DEBUG

# Run with verbose output
python -m sandbox.intelligent.mcp.server --debug --verbose

# Enable Python warnings
export PYTHONWARNINGS=default

# Enable asyncio debugging
export PYTHONASYNCIODEBUG=1
```

### Support Resources

- **Documentation**: See `/docs` directory
- **GitHub Issues**: https://github.com/scooter-lacroix/swiss-sandbox/issues
- **Email Support**: scooterlacroix@gmail.com

## API Reference

### REST API Endpoints

#### Create Workspace
```http
POST /api/v1/workspaces
Content-Type: application/json
X-API-Key: your-api-key

{
  "source_path": "/path/to/project",
  "workspace_id": "my-workspace",
  "isolation": {
    "use_docker": true,
    "resource_limits": {
      "memory_mb": 2048,
      "cpu_cores": 2
    }
  }
}
```

#### Analyze Codebase
```http
POST /api/v1/workspaces/{workspace_id}/analyze
X-API-Key: your-api-key
```

#### Create Task Plan
```http
POST /api/v1/workspaces/{workspace_id}/plans
Content-Type: application/json
X-API-Key: your-api-key

{
  "description": "Run tests and build project",
  "auto_approve": false
}
```

#### Execute Task Plan
```http
POST /api/v1/plans/{plan_id}/execute
X-API-Key: your-api-key
```

#### Get Execution History
```http
GET /api/v1/workspaces/{workspace_id}/history
X-API-Key: your-api-key
```

### Python SDK

```python
from sandbox.intelligent.client import IntelligentSandboxClient

# Initialize client
client = IntelligentSandboxClient(
    api_key="your-api-key",
    base_url="http://localhost:8080"
)

# Create workspace
workspace = client.create_workspace(
    source_path="/path/to/project",
    workspace_id="my-workspace"
)

# Analyze codebase
analysis = client.analyze_codebase(workspace.id)

# Create and execute task plan
plan = client.create_task_plan(
    workspace_id=workspace.id,
    description="Run comprehensive testing"
)

result = client.execute_plan(plan.id)

# Get history
history = client.get_execution_history(workspace.id)

# Cleanup
client.destroy_workspace(workspace.id)
```

## Best Practices

### 1. Resource Management

- **Always set resource limits** to prevent runaway processes
- **Use workspace timeouts** to automatically clean up abandoned workspaces
- **Enable auto-cleanup** to maintain system health
- **Monitor disk usage** and clean up regularly

### 2. Security

- **Always use Docker isolation** in production
- **Implement API key rotation** every 90 days
- **Enable audit logging** for compliance
- **Use network isolation** with whitelist approach
- **Run as non-root user** (sandbox user)
- **Keep dependencies updated** with regular security scans

### 3. Performance

- **Enable caching** for repeated operations
- **Use connection pooling** for database connections
- **Implement rate limiting** to prevent abuse
- **Use async operations** where possible
- **Profile regularly** to identify bottlenecks

### 4. Reliability

- **Implement health checks** with automatic restarts
- **Use systemd** for service management
- **Set up monitoring** with alerts
- **Maintain backup strategy** for critical data
- **Test disaster recovery** procedures regularly

### 5. Scalability

- **Use horizontal scaling** with load balancer
- **Implement distributed caching** with Redis
- **Use message queues** for async task processing
- **Consider microservices** architecture for large deployments
- **Monitor metrics** to plan capacity

### 6. Development Workflow

```bash
# Development setup
git clone https://github.com/your-org/intelligent-sandbox.git
cd intelligent-sandbox
make dev-setup

# Run tests
make test

# Run linting
make lint

# Build Docker image
make docker-build

# Deploy to staging
make deploy-staging

# Deploy to production
make deploy-prod
```

### 7. Maintenance Schedule

- **Daily**: Check logs, monitor metrics
- **Weekly**: Run security scans, update dependencies
- **Monthly**: Review performance metrics, optimize as needed
- **Quarterly**: Update documentation, conduct security audit
- **Annually**: Major version upgrades, architecture review

## Appendix

### A. Environment Variables Reference

| Variable | Description | Default |
|----------|-------------|---------|
| `SANDBOX_API_KEY` | API key for authentication | Required |
| `SANDBOX_BASE_DIR` | Base directory for workspaces | `/tmp/intelligent_sandbox` |
| `SANDBOX_LOG_LEVEL` | Logging level | `INFO` |
| `SANDBOX_DEBUG` | Enable debug mode | `false` |
| `SANDBOX_USE_DOCKER` | Use Docker isolation | `true` |
| `SANDBOX_MAX_WORKSPACES` | Maximum concurrent workspaces | `10` |
| `SANDBOX_TIMEOUT` | Workspace timeout (seconds) | `3600` |
| `DATABASE_URL` | Database connection string | SQLite default |
| `REDIS_URL` | Redis connection string | Optional |

### B. Configuration Files

| File | Purpose | Location |
|------|---------|----------|
| `sandbox.yaml` | Main configuration | `/opt/intelligent-sandbox/config/` |
| `mcp_config.json` | MCP server configuration | `/opt/intelligent-sandbox/` |
| `.env` | Environment variables | `/opt/intelligent-sandbox/` |
| `logging.conf` | Logging configuration | `/opt/intelligent-sandbox/config/` |

### C. Port Reference

| Port | Service | Protocol |
|------|---------|----------|
| 8080 | MCP Server HTTP API | TCP |
| 8081 | WebSocket connections | TCP |
| 9090 | Prometheus metrics | TCP |
| 6379 | Redis (if used) | TCP |
| 5432 | PostgreSQL (if used) | TCP |

### D. Directory Structure

```
/opt/intelligent-sandbox/
├── .venv/                 # Python virtual environment
├── config/                # Configuration files
│   ├── sandbox.yaml
│   └── logging.conf
├── src/                   # Source code
│   └── sandbox/
│       └── intelligent/
├── scripts/               # Utility scripts
├── tests/                 # Test suite
├── docs/                  # Documentation
├── monitoring/            # Monitoring configurations
└── .env                   # Environment variables

/var/log/intelligent-sandbox/  # Log files
├── sandbox.log
├── mcp.log
├── audit.log
└── error.log

/var/cache/intelligent-sandbox/  # Cache directory
├── analysis/
├── plans/
└── results/

/tmp/intelligent_sandbox/  # Workspace directory
└── workspace_*/           # Individual workspaces
```

---

**Version**: 1.0.0  
**Last Updated**: 2025-08-10  
**License**: MIT  
**Copyright**: © 2025 Intelligent Sandbox Team
