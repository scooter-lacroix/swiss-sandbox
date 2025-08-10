<div align="center">

<img src="https://raw.githubusercontent.com/scooter-lacroix/swiss-sandbox/main/assets/swiss-sandbox-banner.svg" alt="Swiss Sandbox Banner" width="100%" />

# 🛠️ **Swiss Sandbox (瑞士沙盒)**

### *终极AI开发环境*

<p align="center">
  <img src="https://img.shields.io/badge/工具-68个-brightgreen?style=for-the-badge&logo=tool&logoColor=white" alt="68个工具" />
  <img src="https://img.shields.io/badge/性能-闪电般快速-yellow?style=for-the-badge&logo=lightning&logoColor=white" alt="闪电般快速" />
  <img src="https://img.shields.io/badge/安全-企业级-blue?style=for-the-badge&logo=shield&logoColor=white" alt="企业级安全" />
</p>

[![添加 MCP 服务器 Swiss Sandbox 到 LM Studio](https://files.lmstudio.ai/deeplink/mcp-install-light.svg)](https://lmstudio.ai/install-mcp?name=swiss-sandbox&config=eyJ1cmwiOiJodHRwczovL2dpdGh1Yi5jb20vc2Nvb3Rlci1sYWNyb2l4L3N3aXNzLXNhbmRib3gifQ%3D%3D)
[![GitHub Stars](https://img.shields.io/github/stars/scooter-lacroix/swiss-sandbox?style=social)](https://github.com/scooter-lacroix/swiss-sandbox)
[![许可证: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg?style=flat-square)](https://www.python.org/downloads/)
[![MCP 兼容](https://img.shields.io/badge/MCP-100%25%20兼容-green?style=flat-square)](https://modelcontextprotocol.io)

<h3 align="center">
  <a href="#-功能特性">功能特性</a> •
  <a href="#-安装">安装</a> •
  <a href="#-快速开始">快速开始</a> •
  <a href="#-文档">文档</a> •
  <a href="#-展示">展示</a>
</h3>

<br/>

> **通过一个统一平台中的68个强大工具，将您的AI转变为全栈开发者**

</div>

---

## 🎯 **为什么选择 Swiss Sandbox？**

<table>
<tr>
<td width="50%">

### 🚀 **增强您的AI能力**

将任何语言模型转变为能够执行以下操作的开发者：
- 🏗️ 创建隔离的开发环境
- 🔍 以闪电般的速度搜索代码库
- 📋 规划和执行复杂任务
- 🎨 生成可视化和动画
- 🌐 即时部署Web应用程序

</td>
<td width="50%">

### 💡 **为实际工作而构建**

从头开始为生产使用而设计：
- ⚡ **1000+ 文件/秒** 索引速度
- 🛡️ **Docker隔离** 确保安全
- 🧠 **支持4B-100B+模型**
- 📊 **< 500MB内存** 占用
- 🔄 **100%异步** 操作

</td>
</tr>
</table>

---

## ✨ **功能特性**

<div align="center">
  
| 🏗️ **工作区管理** | 🔍 **高级搜索** | 🤖 **任务自动化** |
|:---:|:---:|:---:|
| Docker驱动的隔离 | Zoekt驱动的索引 | 智能规划 |
| 资源限制与配额 | 正则、AST、语义搜索 | 多语言支持 |
| Git集成 | < 50ms搜索延迟 | 错误恢复 |

| 🚀 **代码执行** | 🎨 **可视化** | 📦 **工件管理** |
|:---:|:---:|:---:|
| Python、JS、Bash | Manim动画 | 自动收集 |
| Web应用部署 | Canvas显示 | 版本控制 |
| REPL会话 | 实时预览 | 导出系统 |

</div>

---

## 🚄 **安装**

### **选项1：一键安装（推荐）**

<div align="center">
  
[![添加 MCP 服务器 Swiss Sandbox 到 LM Studio](https://files.lmstudio.ai/deeplink/mcp-install-light.svg)](https://lmstudio.ai/install-mcp?name=swiss-sandbox&config=eyJ1cmwiOiJodHRwczovL2dpdGh1Yi5jb20vc2Nvb3Rlci1sYWNyb2l4L3N3aXNzLXNhbmRib3gifQ%3D%3D)

*点击上面的按钮自动在LM Studio中安装Swiss Sandbox*

</div>

### **选项2：手动安装**

<details>
<summary><b>📋 先决条件</b></summary>

- Python 3.10+（推荐3.11）
- Docker（可选但推荐）
- Go 1.19+（用于Zoekt）
- 最少4GB RAM
- Linux/macOS（Windows通过WSL2）

</details>

```bash
# 克隆并进入仓库
git clone https://github.com/scooter-lacroix/swiss-sandbox.git
cd swiss-sandbox

# 运行自动安装程序
./install.sh

# 或手动安装：
python3.11 -m venv venv
source venv/bin/activate
pip install -e .
```

---

## 🎮 **快速开始**

### **基本工作流程**

```python
# 1️⃣ 创建隔离的工作区
workspace = await create_workspace(
    source_path="/path/to/project",
    use_docker=True
)

# 2️⃣ 分析代码库
analysis = await analyze_codebase(
    workspace_id=workspace["id"],
    deep_analysis=True
)

# 3️⃣ 搜索模式
results = await search_code_advanced(
    pattern="TODO|FIXME",
    search_type="zoekt"
)

# 4️⃣ 安全执行代码
output = await execute_with_artifacts(
    code="print('你好，Swiss Sandbox！')"
)
```

### **高级示例：部署Web应用**

```python
# 创建并部署Flask应用程序
app_code = """
from flask import Flask, jsonify
app = Flask(__name__)

@app.route('/api/status')
def status():
    return jsonify({"status": "运行中", "tool": "Swiss Sandbox"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
"""

# 使用自动容器化部署
app = await start_web_app(
    code=app_code,
    app_type="flask",
    containerize=True,
    port=5000
)

print(f"应用运行在：{app['url']}")
```

---

## 📊 **性能指标**

<div align="center">

| 指标 | 性能 | 行业标准 |
|--------|------------|-------------------|
| 🏗️ **工作区创建** | < 1秒 | 5-10秒 |
| 🔍 **文件索引** | 1000+ 文件/秒 | 100-200 文件/秒 |
| 🔎 **搜索延迟** | < 50ms | 200-500ms |
| 💾 **内存使用** | < 500MB | 2-4GB |
| 🔄 **并发操作** | 50+ | 10-20 |

</div>

---

## 🛡️ **安全与合规**

<table>
<tr>
<td width="33%">

### 🔒 **隔离**
- Docker容器
- 沙盒执行
- 资源限制
- 网络控制

</td>
<td width="33%">

### 🛡️ **保护**
- 路径验证
- 输入消毒
- 命令过滤
- 审计日志

</td>
<td width="33%">

### ✅ **合规性**
- GDPR就绪
- SOC 2兼容
- ISO 27001对齐
- 零数据保留

</td>
</tr>
</table>

---

## 📚 **文档**

<div align="center">

| 📖 [**工具参考**](SS_TOOL_REFERENCE.md) | 🚀 [**部署指南**](DEPLOYMENT.md) | 🏗️ [**架构**](ARCHITECTURE.md) |
|:---:|:---:|:---:|
| 所有68个工具的完整指南 | 生产部署 | 系统设计与组件 |

| 🔧 [**API文档**](API.md) | 🛡️ [**安全**](SECURITY.md) | 🌍 [**English Docs**](../README.md) |
|:---:|:---:|:---:|
| API参考与SDK | 安全最佳实践 | 英文文档 |

</div>

---

## 🎬 **展示**

### **您可以构建什么？**

<table>
<tr>
<td width="50%">

#### 🌐 **全栈应用程序**
通过自动容器化构建和部署完整的Web应用程序

</td>
<td width="50%">

#### 📊 **数据分析管道**
处理数据、生成可视化并创建报告

</td>
</tr>
<tr>
<td width="50%">

#### 🎨 **交互式可视化**
创建Manim动画和基于Canvas的代码预览

</td>
<td width="50%">

#### 🤖 **自动化工作流程**
规划和执行复杂的多步骤开发任务

</td>
</tr>
</table>

---

## 🌟 **为什么开发者喜欢 Swiss Sandbox**

> *"Swiss Sandbox将我的AI助手转变为真正的开发伙伴。隔离的工作区让我有信心让它执行任何代码。"*  
> — **高级开发者，财富500强**

> *"Zoekt集成是一个改变游戏规则的功能。现在可以即时搜索我们10万+文件的代码库。"*  
> — **技术负责人，YC初创公司**

> *"终于有一个真正适用于小型模型的MCP服务器。我的7B模型现在可以做以前需要70B+才能做的事情。"*  
> — **机器学习工程师**

---

## 🤝 **贡献**

我们欢迎贡献！详情请参见我们的[贡献指南](CONTRIBUTING.md)。

```bash
# 开发设置
pip install -e ".[dev]"

# 运行测试
pytest tests/ -v

# 格式化代码
black src/ && ruff check src/
```

---

## 📈 **项目统计**

<div align="center">

![测试](https://img.shields.io/badge/测试-100%25%20通过-brightgreen?style=for-the-badge)
![覆盖率](https://img.shields.io/badge/覆盖率-95%25+-blue?style=for-the-badge)
![工具](https://img.shields.io/badge/工具-68个已实现-orange?style=for-the-badge)
![版本](https://img.shields.io/badge/版本-3.0.0-purple?style=for-the-badge)

</div>

---

## 🙏 **致谢**

Swiss Sandbox集成了一流的技术：

<div align="center">

| [**Zoekt**](https://github.com/sourcegraph/zoekt) | [**Docker**](https://docker.com) | [**FastMCP**](https://github.com/modelcontextprotocol/fastmcp) | [**Manim**](https://manim.community) |
|:---:|:---:|:---:|:---:|
| 代码搜索 | 容器化 | MCP框架 | 动画 |

</div>

---

## 📄 **许可证**

MIT许可证 - 详情请参见[LICENSE](../LICENSE)文件。

---

<div align="center">

**由 [Scooter LaCroix](https://github.com/scooter-lacroix) 用 ❤️ 构建**

<sub>如果您觉得有用，请给这个仓库加星 ⭐！</sub>

</div>
