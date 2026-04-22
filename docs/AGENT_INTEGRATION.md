# Agent 集成指南

> 为 Claude Code、Cursor、Windsurf、OpenClaw、WorkBuddy 等 AI Agent 集成 Ariadne Memory

---

## 一、MCP Server 集成

### 1.1 Claude Code

#### 安装 MCP SDK

Claude Code 通过 MCP 协议与服务器通信：

```bash
# 安装 Claude Code (如果尚未安装)
npm install -g @anthropic/claude-code

# 配置 MCP 服务器
claude --mcp-config
```

#### 配置 ariadne-memory

编辑 `~/.claude/mcp.json` 或项目级 `.claude/mcp.json`：

```json
{
  "mcpServers": {
    "ariadne-memory": {
      "command": "python",
      "args": ["-m", "ariadne.cli", "mcp", "run"],
      "env": {
        "PYTHONPATH": "/path/to/ariadne"
      }
    }
  }
}
```

#### 使用示例

```
/mcp tools list ariadne-memory

# 搜索
/mcp call ariadne-memory ariadne_search {"query": "machine learning optimization"}

/mcp call ariadne-memory ariadne_rag_search {"query": "transformer architecture", "top_k": 3}

/mcp call ariadne-memory ariadne_graph_query {"entity": "Deep Learning"}

/mcp call ariadne-memory ariadne_stats {"detailed": true}
```

### 1.2 Cursor

#### 配置步骤

1. 打开 Cursor 设置 (Cmd/Ctrl + ,)
2. 进入 "MCP Servers" 选项卡
3. 点击 "Add new MCP server"
4. 填写配置：

```json
{
  "name": "ariadne-memory",
  "command": "python",
  "args": ["-m", "ariadne.cli", "mcp", "run"],
  "env": {
    "PYTHONPATH": "/absolute/path/to/ariadne"
  }
}
```

#### 使用

在 Cursor 的 AI 对话中，可以直接调用工具：

```
@ariadne-memory
搜索关于分布式系统的文档
```

### 1.3 Windsurf (Codeium)

Windsurf 使用相同的 MCP 协议：

```json
{
  "mcpServers": {
    "ariadne-memory": {
      "command": "python",
      "args": ["-m", "ariadne.cli", "mcp", "run"]
    }
  }
}
```

配置文件位置：`~/.codeium/windsurf/mcp_config.json`

### 1.4 GitHub Copilot (via Extension)

创建 VSCode 扩展来桥接 Copilot 和 Ariadne：

```typescript
// ariadne-copilot-extension/src/extension.ts
import * as vscode from 'vscode';
import { spawn } from 'child_process';

export function activate(context: vscode.ExtensionContext) {
    // 启动 Ariadne MCP Server
    const mcpProcess = spawn('python', ['-m', 'ariadne.cli', 'mcp', 'run']);

    // 注册命令
    context.subscriptions.push(
        vscode.commands.registerCommand('ariadne.search', async () => {
            const query = await vscode.window.showInputBox({
                prompt: 'Enter search query:'
            });
            if (query) {
                // 调用 MCP 工具
                const result = await callMCPTool('ariadne_search', { query });
                vscode.window.showInformationMessage(`Found ${result.count} results`);
            }
        })
    );
}
```

---

## 二、HTTP REST API 集成

适用于所有支持 HTTP 请求的 Agent：

### 2.1 OpenClaw / WorkBuddy

在 Skill 中调用 Ariadne API：

```markdown
# OpenClaw Skill 配置

## API 调用

### 语义搜索
```javascript
const response = await fetch('http://localhost:8770/api/search/semantic', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    query: '{{query}}',
    top_k: 5
  })
});
const { results } = await response.json();
```

### RAG 搜索
```javascript
const response = await fetch('http://localhost:8770/api/search/rag', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    query: '{{query}}',
    top_k: 3,
    alpha: 0.7,
    include_citations: true
  })
});
```

### 图谱查询
```javascript
const response = await fetch('http://localhost:8770/api/graph/entity/{{entity}}', {
  method: 'GET'
});
```

### 文档摄入
```javascript
const formData = new FormData();
formData.append('files', fileInput.files[0]);
formData.append('memory', 'default');
formData.append('enrich', 'true');

const response = await fetch('http://localhost:8770/api/ingest/files', {
  method: 'POST',
  body: formData
});
```
```

### 2.2 自定义 Agent

```python
import requests
import json

class AriadneClient:
    def __init__(self, base_url="http://localhost:8770"):
        self.base_url = base_url

    def search(self, query, top_k=5):
        response = requests.post(
            f"{self.base_url}/api/search/semantic",
            json={"query": query, "top_k": top_k}
        )
        return response.json()

    def rag_search(self, query, top_k=5, alpha=0.5):
        response = requests.post(
            f"{self.base_url}/api/search/rag",
            json={
                "query": query,
                "top_k": top_k,
                "alpha": alpha,
                "include_citations": True
            }
        )
        return response.json()

    def graph_query(self, entity, depth=1):
        response = requests.get(
            f"{self.base_url}/api/graph/entity/{entity}",
            params={"depth": depth}
        )
        return response.json()

    def ingest(self, file_path, memory="default"):
        with open(file_path, 'rb') as f:
            files = {'files': f}
            data = {'memory': memory, 'enrich': 'true'}
            response = requests.post(
                f"{self.base_url}/api/ingest/files",
                files=files,
                data=data
            )
        return response.json()

    def summarize(self, query, language="en"):
        response = requests.post(
            f"{self.base_url}/api/system/summarize",
            json={"query": query, "output_lang": language}
        )
        return response.json()
```

---

## 三、CLI 集成

### 3.1 Shell 脚本

```bash
#!/bin/bash
# ariadne-search.sh

QUERY="$1"
TOP_K="${2:-5}"

ariadne search "$QUERY" -k "$TOP_K"
```

```bash
#!/bin/bash
# ariadne-ingest.sh

FILE="$1"
MEMORY="${2:-default}"

ariadne ingest "$FILE" -m "$MEMORY" --enrich
```

### 3.2 Python 脚本

```python
#!/usr/bin/env python3
"""
Ariadne CLI Wrapper for external tools
"""
import subprocess
import json
import sys

def run_ariadne(args):
    """Run ariadne CLI command and return parsed output."""
    cmd = ["python", "-m", "ariadne.cli"] + args
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    return result.stdout

def main():
    if len(sys.argv) < 2:
        print("Usage: ariadne-wrapper.py <command> [args...]")
        sys.exit(1)

    command = sys.argv[1]
    args = sys.argv[2:]

    if command == "search":
        query = args[0] if args else "test"
        output = run_ariadne(["search", query, "-k", "5"])
        print(output)
    elif command == "rag":
        query = args[0] if args else "test"
        output = run_ariadne(["rag", "search", query])
        print(output)
    elif command == "stats":
        output = run_ariadne(["info", "--stats"])
        print(output)
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)

if __name__ == "__main__":
    main()
```

---

## 四、环境变量配置

### 4.1 LLM API Keys

```bash
# DeepSeek
export DEEPSEEK_API_KEY="sk-xxxxx"

# OpenAI
export OPENAI_API_KEY="sk-xxxxx"

# Anthropic
export ANTHROPIC_API_KEY="sk-ant-xxxxx"

# Gemini
export GEMINI_API_KEY="xxxxx"
```

### 4.2 Ariadne 配置

```bash
# 数据目录
export ARIADNE_DATA_DIR="./data"

# 日志级别
export ARIADNE_LOG_LEVEL="INFO"

# 语言
export ARIADNE_LANGUAGE="zh_CN"
```

---

## 五、测试验证

### 5.1 MCP 连接测试

```bash
# 启动 MCP Server
ariadne mcp run &

# 测试 MCP info
curl http://localhost:8765/mcp -X POST \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":"1","method":"tools/list"}'
```

### 5.2 REST API 测试

```bash
# 健康检查
curl http://localhost:8770/api/health

# 系统信息
curl http://localhost:8770/api/system/info

# 搜索测试
curl -X POST http://localhost:8770/api/search/semantic \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "top_k": 5}'
```

---

## 六、故障排查

### 6.1 常见问题

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| MCP 连接失败 | Python 环境问题 | 检查 `python -m ariadne.cli mcp run` |
| API 503 | Web 服务未启动 | 运行 `ariadne web run` |
| 搜索无结果 | 记忆库为空 | 先摄入文档 `ariadne ingest <file>` |
| LLM 错误 | API Key 未配置 | 运行 `ariadne config set-api-key` |

### 6.2 日志位置

- CLI 日志: `.ariadne/logs/cli.log`
- Web 日志: `.ariadne/logs/web.log`
- MCP 日志: `.ariadne/logs/mcp.log`

---

## 七、性能优化

### 7.1 大规模部署

```bash
# 使用多进程处理摄入
ariadne ingest /path/to/files --batch-size 200 -r

# 重建索引优化
ariadne rag rebuild-index
```

### 7.2 缓存策略

```python
# 在客户端实现缓存
from functools import lru_cache

@lru_cache(maxsize=100)
def cached_search(query):
    return ariadne_client.search(query)
```

---

## 八、安全考虑

### 8.1 API 认证

```python
# 添加 API Key 认证
@app.middleware("http")
async def auth_middleware(request, call_next):
    api_key = request.headers.get("X-API-Key")
    if api_key != os.getenv("AROADNE_API_KEY"):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    return await call_next(request)
```

### 8.2 防火墙配置

```bash
# 只允许本地访问
ariadne web run --host 127.0.0.1

# 限制访问来源（生产环境）
ufw allow from 192.168.1.0/24 to any port 8770
```

---

## 九、WorkBuddy Skill 集成

### 9.1 安装 Skill

WorkBuddy Skill 存储在 `docs/WORKBUDDY-SKILL.md`，可用于 WorkBuddy 的智能体集成。

**安装步骤：**

1. 找到 WorkBuddy 的 skills 目录（通常在 `~/.workbuddy/skills/`）
2. 创建 `ariadne-memory` 目录
3. 将 `docs/WORKBUDDY-SKILL.md` 复制到该目录，重命名为 `SKILL.md`

```powershell
# Windows PowerShell
Copy-Item "path/to/Ariadne/docs/WORKBUDDY-SKILL.md" "$env:USERPROFILE\.workbuddy\skills\ariadne-memory\SKILL.md"
```

```bash
# Linux/macOS
cp path/to/Ariadne/docs/WORKBUDDY-SKILL.md ~/.workbuddy/skills/ariadne-memory/SKILL.md
```

### 9.2 触发词

WorkBuddy 会根据以下触发词自动调用 Ariadne Memory：

| 类别 | 触发词 |
|------|--------|
| 搜索相关 | 记忆、记忆库、搜索记忆、查记忆、知识库、知识检索、查询知识库、RAG、混合搜索、向量搜索、语义搜索 |
| 知识图谱 | 知识图谱、实体关系、图谱查询、实体探索 |
| 文档管理 | 摄入文档、添加记忆、存入记忆、上传文档 |
| 分析相关 | 摘要、总结、分析 |

### 9.3 使用方式

在 WorkBuddy 中直接对话：

```
用户：帮我查一下机器学习优化的内容
用户：把这份PDF添加到记忆库
用户：用RAG搜索"Transformer架构原理"
用户：探索一下知识图谱中"深度学习"相关的实体
```

### 9.4 前提条件

确保 Ariadne Web 服务已启动：

```bash
# 启动 Web UI（推荐）
python -m ariadne.cli web run

# 或仅启动 API 服务
ariadne web run
```

Web 服务默认地址：`http://localhost:8770`

---

## 十、相关文档

| 文档 | 路径 | 说明 |
|------|------|------|
| SKILL文件 | `docs/WORKBUDDY-SKILL.md` | WorkBuddy Skill 定义文件 |
| MCP文档 | `docs/MCP.md` | MCP Server 详细文档 |
| MCP配置示例 | `examples/mcp_config.json` | MCP 客户端配置模板 |
| 测试计划 | `docs/TEST_AND_EXTENSION_PLAN.md` | 测试方案和扩展计划 |
