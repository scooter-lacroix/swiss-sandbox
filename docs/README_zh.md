# 增强沙盒 SDK

> 生产级 Python 沙盒执行环境，支持全面的 MCP 服务器集成，具备增强的工件管理、交互式 REPL 和 Manim 动画功能。

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![FastMCP](https://img.shields.io/badge/FastMCP-2.10.5-green.svg)](https://github.com/jlowin/fastmcp)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)

## 🚀 快速开始

```bash
# 克隆仓库
git clone https://github.com/scooter-lacroix/sandbox-mcp.git
cd sandbox-mcp

# 使用 uv 安装（推荐）
uv venv && uv pip install -e .

# 运行 MCP 服务器
uv run sandbox-server-stdio
```

## ✨ 功能特性

### 🔧 **增强的 Python 执行**
- **代码验证**：自动输入验证和格式化
- **虚拟环境**：自动检测并激活 `.venv`
- **持久化上下文**：变量在执行间保持
- **增强错误处理**：详细诊断和彩色输出
- **交互式 REPL**：实时 Python shell 与 Tab 补全

### 🎨 **智能工件管理**
- **自动捕获**：Matplotlib 图表和 PIL 图像
- **分类管理**：智能文件类型检测和组织
- **多种格式**：JSON、CSV 和结构化输出
- **递归扫描**：深度目录遍历
- **智能清理**：按类型或时间配置清理

### 🎬 **Manim 动画支持**
- **预编译示例**：一键动画执行
- **质量控制**：多种渲染预设
- **视频生成**：自动保存 MP4 动画
- **示例库**：内置模板和教程
- **环境验证**：自动依赖检查

### 🌐 **Web 应用程序托管**
- **Flask 和 Streamlit**：自动端口检测启动 Web 应用
- **进程管理**：跟踪和管理运行服务器
- **URL 生成**：返回可访问的端点

### 🔒 **安全性和安全**
- **命令过滤**：阻止危险操作
- **沙盒执行**：隔离环境
- **超时控制**：可配置执行限制
- **资源监控**：内存和 CPU 使用跟踪

### 🔌 **MCP 集成**
- **双重传输**：HTTP 和 stdio 支持
- **LM Studio 就绪**：插件式 AI 模型集成
- **FastMCP 驱动**：现代 MCP 实现
- **全面工具**：12+ 可用 MCP 工具

## 📦 安装

### 先决条件
- Python 3.9+
- uv（推荐）或 pip

### 使用 uv（推荐）

```bash
git clone https://github.com/scooter-lacroix/sandbox-mcp.git
cd sandbox-mcp
uv venv
uv pip install -e .
```

### 使用 pip

```bash
git clone https://github.com/scooter-lacroix/sandbox-mcp.git
cd sandbox-mcp
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate  # Windows
pip install -e .
```

## 🖥️ 使用

### 命令行界面

```bash
# 启动 HTTP 服务器（Web 集成）
sandbox-server

# 启动 stdio 服务器（LM Studio 集成）
sandbox-server-stdio
```

### LM Studio 集成

添加到您的 LM Studio MCP 配置：

```json
{
  "mcpServers": {
    "sandbox": {
      "command": "sandbox-server-stdio",
      "args": []
    }
  }
}
```

### 可用的 MCP 工具

| 工具 | 描述 |
|------|------|
| `execute` | 执行 Python 代码并捕获工件 |
| `shell_execute` | 安全地执行 shell 命令并过滤 |
| `list_artifacts` | 列出生成的工件 |
| `cleanup_artifacts` | 清理临时文件 |
| `get_execution_info` | 获取环境诊断信息 |
| `start_repl` | 启动交互式会话 |
| `start_web_app` | 启动 Flask/Streamlit 应用 |
| `cleanup_temp_artifacts` | 维护操作 |
| `create_manim_animation` | 使用 Manim 创建数学动画 |
| `list_manim_animations` | 列出所有创建的 Manim 动画 |
| `cleanup_manim_animation` | 清理特定动画文件 |
| `get_manim_examples` | 获取示例 Manim 代码片段 |

## 💡 示例

### 增强 SDK 使用

#### 本地 Python 执行

```python
import asyncio
from sandbox import PythonSandbox

async def local_example():
    async with PythonSandbox.create_local(name="my-sandbox") as sandbox:
        # 执行 Python 代码
        result = await sandbox.run("print('你好，来自本地沙盒！')")
        print(await result.output())
        
        # 执行带工件的代码
        plot_code = """
import matplotlib.pyplot as plt
import numpy as np

x = np.linspace(0, 10, 100)
y = np.sin(x)

plt.figure(figsize=(8, 6))
plt.plot(x, y)
plt.title('正弦波')
plt.show()  # 自动捕获为工件
"""
        result = await sandbox.run(plot_code)
        print(f"创建的工件: {result.artifacts}")
        
        # 执行 shell 命令
        cmd_result = await sandbox.command.run("ls", ["-la"])
        print(await cmd_result.output())

asyncio.run(local_example())
```

#### 远程 Python 执行（使用 microsandbox）

```python
import asyncio
from sandbox import PythonSandbox

async def remote_example():
    async with PythonSandbox.create_remote(
        server_url="http://127.0.0.1:5555",
        api_key="your-api-key",
        name="remote-sandbox"
    ) as sandbox:
        # 在安全微虚拟机中执行 Python 代码
        result = await sandbox.run("print('你好，来自微虚拟机！')")
        print(await result.output())
        
        # 获取沙盒指标
        metrics = await sandbox.metrics.all()
        print(f"CPU 使用率: {metrics.get('cpu_usage', 0)}%")
        print(f"内存使用: {metrics.get('memory_usage', 0)} MB")

asyncio.run(remote_example())
```

#### Node.js 执行

```python
import asyncio
from sandbox import NodeSandbox

async def node_example():
    async with NodeSandbox.create(
        server_url="http://127.0.0.1:5555",
        api_key="your-api-key",
        name="node-sandbox"
    ) as sandbox:
        # 执行 JavaScript 代码
        js_code = """
console.log('你好，来自 Node.js！');
const sum = [1, 2, 3, 4, 5].reduce((a, b) => a + b, 0);
console.log(`总和: ${sum}`);
"""
        result = await sandbox.run(js_code)
        print(await result.output())

asyncio.run(node_example())
```

#### 构建者模式配置

```python
import asyncio
from sandbox import LocalSandbox, SandboxOptions

async def builder_example():
    config = (SandboxOptions.builder()
              .name("configured-sandbox")
              .memory(1024)
              .cpus(2.0)
              .timeout(300.0)
              .env("DEBUG", "true")
              .build())
    
    async with LocalSandbox.create(**config.__dict__) as sandbox:
        result = await sandbox.run("import os; print(os.environ.get('DEBUG'))")
        print(await result.output())  # 应该输出: true

asyncio.run(builder_example())
```

### MCP 服务器示例

#### 基本 Python 执行

```python
# 执行简单代码
result = execute(code="print('你好，世界！')")
```

### Matplotlib 工件生成

```python
code = """
import matplotlib.pyplot as plt
import numpy as np

# 生成图表
x = np.linspace(0, 10, 100)
y = np.sin(x)

plt.figure(figsize=(8, 6))
plt.plot(x, y, 'b-', linewidth=2)
plt.title('正弦波')
plt.xlabel('x')
plt.ylabel('sin(x)')
plt.grid(True)
plt.show()  # 自动捕获为工件
"""

result = execute(code)
# 返回带有 base64 编码 PNG 的 JSON
```

### Flask Web 应用程序

```python
flask_code = """
from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/')
def home():
    return '<h1>沙盒 Flask 应用</h1>'

@app.route('/api/status')
def status():
    return jsonify({"status": "running", "server": "sandbox"})
"""

result = start_web_app(flask_code, "flask")
# 返回应用可访问的 URL
```

### Shell 命令执行

```python
# 通过 shell 安装包
result = shell_execute("uv pip install matplotlib")

# 检查环境
result = shell_execute("which python")

# 列出目录内容
result = shell_execute("ls -la")

# 自定义工作目录和超时
result = shell_execute(
    "find . -name '*.py' | head -10", 
    working_directory="/path/to/search",
    timeout=60
)
```

### Manim 动画创建

```python
# 简单圆圈动画
manim_code = """
from manim import *

class SimpleCircle(Scene):
    def construct(self):
        circle = Circle()
        circle.set_fill(PINK, opacity=0.5)
        self.play(Create(circle))
        self.wait(1)
"""

result = create_manim_animation(manim_code, quality="medium_quality")
# 返回带有视频路径和元数据的 JSON

# 数学图形可视化
math_animation = """
from manim import *

class GraphPlot(Scene):
    def construct(self):
        axes = Axes(
            x_range=[-3, 3, 1],
            y_range=[-3, 3, 1],
            x_length=6,
            y_length=6
        )
        axes.add_coordinates()
        
        graph = axes.plot(lambda x: x**2, color=BLUE)
        graph_label = axes.get_graph_label(graph, label="f(x) = x^2")
        
        self.play(Create(axes))
        self.play(Create(graph))
        self.play(Write(graph_label))
        self.wait(1)
"""

result = create_manim_animation(math_animation, quality="high_quality")

# 列出所有动画
animations = list_manim_animations()

# 获取示例代码片段
examples = get_manim_examples()
```

### 错误处理

```python
# 导入错误及详细诊断
result = execute(code="import nonexistent_module")
# 返回带有 sys.path 信息的结构化错误

# 安全阻止的 shell 命令
result = shell_execute("rm -rf /")
# 返回带有阻止模式信息的安全错误
```

## 🏗️ 架构

### 项目结构

```
sandbox-mcp/
├── src/
│   └── sandbox/                   # 主包
│       ├── __init__.py           # 包初始化
│       ├── mcp_sandbox_server.py # HTTP MCP 服务器
│       ├── mcp_sandbox_server_stdio.py # stdio MCP 服务器
│       ├── core/                 # 核心模块
│       │   ├── execution_context.py  # 执行上下文
│       │   ├── interactive_repl.py   # 交互式 REPL
│       │   ├── code_validator.py     # 代码验证器
│       │   └── manim_support.py      # Manim 支持
│       └── sdk/                  # SDK 模块
│           ├── local_sandbox.py  # 本地沙盒
│           └── execution.py      # 执行结果
├── docs/
│   └── FAQ_AND_LIMITATIONS.md   # 常见问题和限制
├── tests/
│   └── test_integration.py      # 集成测试
├── pyproject.toml                # 包配置
├── README.md                     # 英文文档
├── README_zh.md                  # 中文文档
└── .gitignore
```

### 核心组件

#### 执行上下文
管理执行环境：
- **项目根检测**：动态路径解析
- **虚拟环境**：自动检测和激活
- **sys.path 管理**：智能路径处理
- **工件管理**：临时目录生命周期
- **全局状态**：持久化执行上下文

#### 猴子补丁系统
非侵入式工件捕获：
- **matplotlib.pyplot.show()**：拦截并保存图表
- **PIL.Image.show()**：捕获图像显示
- **条件补丁**：仅在库可用时应用
- **原始功能**：通过包装函数保留

#### MCP 集成
FastMCP 驱动的服务器：
- **双重传输**：HTTP 和 stdio 协议
- **工具注册**：12+ 可用 MCP 工具
- **流支持**：准备实时交互
- **错误处理**：结构化错误响应

## 📚 文档

有关全面的使用信息、故障排除指南和高级功能：

- **[常见问题和限制](docs/FAQ_AND_LIMITATIONS.md)** - 常见问题和沙盒限制
- **[增强功能指南](ENHANCED_FEATURES.md)** - 高级功能和示例
- **[API 参考](src/sandbox/)** - 完整的 API 文档

## 🧪 测试

运行测试套件以验证安装：

```bash
uv run pytest tests/ -v
```

测试类别包括：
- 包导入和 sys.path 测试
- 错误处理和 ImportError 报告
- 工件捕获（matplotlib/PIL）
- Web 应用程序启动
- 虚拟环境检测

## 🤝 贡献

1. Fork 仓库
2. 创建功能分支
3. 运行测试：`uv run pytest`
4. 提交拉取请求

开发环境设置：
```bash
uv venv && uv pip install -e ".[dev]"
```

## 许可证

[Apache License](LICENSE)

## 致谢

该项目包含来自以下项目的少量灵感：

- **[Microsandbox](https://github.com/microsandbox/microsandbox.git)** - 安全微虚拟机隔离概念的参考

该项目中的大部分功能都是专注于 MCP 服务器集成和增强 Python 执行环境的原创实现。

## 更新日志

### v0.3.0（增强 SDK 版本）
- **🚀 增强 SDK**：与 microsandbox 功能完全集成
- **🔄 统一 API**：本地和远程执行的单一接口
- **🛡️ 微虚拟机支持**：通过 microsandbox 服务器的安全远程执行
- **🌐 多语言**：Python 和 Node.js 执行环境
- **🏗️ 构建者模式**：流畅的配置 API 与 SandboxOptions
- **📊 指标和监控**：实时资源使用跟踪
- **⚡ 异步/等待**：全面的现代 Python 异步支持
- **🔒 增强安全**：改进的命令过滤和验证
- **📦 工件管理**：全面的文件工件处理
- **🎯 命令执行**：带超时的安全 shell 命令执行
- **🔧 配置**：灵活的沙盒配置选项
- **📝 文档**：全面的示例和使用指南

### v0.2.0
- **Manim 集成**：完整的数学动画支持
- **4 个新 MCP 工具**：create_manim_animation、list_manim_animations、cleanup_manim_animation、get_manim_examples
- **质量控制**：多种动画质量预设
- **视频工件**：自动保存 MP4 动画到工件目录
- **示例库**：内置 Manim 代码示例
- **虚拟环境 Manim**：使用 venv 安装的 Manim 可执行文件

### v0.1.0
- 初始增强包结构
- 动态项目根检测
- 强大的虚拟环境集成
- 带详细追踪的增强错误处理
- 支持 matplotlib/PIL 的工件管理
- Web 应用程序启动（Flask/Streamlit）
- 全面的测试套件
- MCP 服务器集成（HTTP 和 stdio）
- CLI 入口点
- LM Studio 兼容性
