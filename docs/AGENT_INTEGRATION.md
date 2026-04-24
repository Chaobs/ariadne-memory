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

## 九、Agent Skill 集成

Ariadne-Memory-SKILL.md 定义了 Agent 集成规范，适用于 WorkBuddy、Claude Code、Cursor 等主流 Agent 工具。

### 9.1 安装 Skill

Skill 定义文件存储在 `docs/Ariadne-Memory-SKILL.md`。

**安装步骤：**

1. 找到你的 Agent 的 skills 目录
2. 创建 `ariadne-memory` 目录
3. 将 `docs/Ariadne-Memory-SKILL.md` 复制到该目录，重命名为 `SKILL.md`

```powershell
# Windows PowerShell (WorkBuddy)
Copy-Item "path/to/Ariadne/docs/Ariadne-Memory-SKILL.md" "$env:USERPROFILE\.workbuddy\skills\ariadne-memory\SKILL.md"
```

```bash
# Linux/macOS
cp path/to/Ariadne/docs/Ariadne-Memory-SKILL.md ~/.workbuddy/skills/ariadne-memory/SKILL.md
```

### 9.2 触发词

支持 Skill 的 Agent 会根据以下触发词自动调用 Ariadne Memory：

| 类别 | 触发词 |
|------|--------|
| 搜索相关 | 记忆、记忆库、搜索记忆、查记忆、知识库、知识检索、查询知识库、RAG、混合搜索、向量搜索、语义搜索 |
| 知识图谱 | 知识图谱、实体关系、图谱查询、实体探索 |
| 文档管理 | 摄入文档、添加记忆、存入记忆、上传文档 |
| 分析相关 | 摘要、总结、分析 |

### 9.3 使用方式

在支持 Skill 的 Agent 中直接对话：

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

### 9.5 支持的 Agent

| Agent | 安装方式 | 触发 |
|--------|----------|------|
| WorkBuddy | 复制 SKILL.md 到 `~/.workbuddy/skills/` | 自动 |
| Claude Code | MCP Server (推荐) 或 Skill | MCP 或 Skill |
| Cursor | MCP Server | MCP |
| Windsurf | MCP Server | MCP |

---

## 十、Session Memory Hook 集成

Ariadne 支持 5 钩子生命周期，参考 Claude-Mem 的设计，实现跨会话永久记忆。

### 10.1 钩子事件

| 事件 | 触发时机 | 输入数据 |
|------|----------|----------|
| `session_start` | 会话开始 | session_id, cwd, platform |
| `user_prompt` | 用户提交输入 | session_id, user_message |
| `post_tool` | 工具调用后 | session_id, tool_name, tool_input, tool_output |
| `stop` | 中途停止/保存 | session_id, transcript |
| `session_end` | 会话结束 | session_id |

### 10.2 CLI 钩子命令

```bash
# 启动新会话
ariadne session start --platform openclaw

# 查看最近的会话
ariadne session list --limit 10

# 搜索观察记录
ariadne session search "bug fix"

# 查看会话统计
ariadne session stats

# 结束会话并生成摘要
ariadne session end <session_id>

# 手动触发钩子（用于测试）
echo '{"session_id": "abc", "tool_name": "read_file"}' | ariadne hook run --event post_tool
```

### 10.3 平台适配器

Ariadne 支持多种平台的 hook 事件格式：

| 平台 | 适配器 | 特点 |
|------|--------|------|
| Claude Code | `ClaudeCodeAdapter` | 完整 hook 格式 |
| OpenClaw/WorkBuddy | `OpenClawAdapter` | MCP 工具调用跟踪 |
| Cursor | `CursorAdapter` | IDE 工具集成 |
| Windsurf | `WindsurfAdapter` | Codeium 生态 |
| 通用 | `GenericAdapter` | 回退适配 |

### 10.4 SSE 实时推送

Session Memory 支持 SSE (Server-Sent Events) 实时推送观察记录到 Web UI：

```javascript
// Web 前端 SSE 连接
const eventSource = new EventSource('/api/sse?session_id=your-session-id');

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.type === 'new_observation') {
    console.log('New observation:', data.data);
    // 更新 UI
  }
};
```

API 端点：
- `GET /api/sse` — SSE 实时流
- `GET /api/sse/stats` — 连接统计
- `GET /api/sse/dedup/stats` — 去重缓存统计

### 10.5 Content-Hash 去重

SHA256 内容哈希 + 30 秒滑动窗口防止重复观察：

```
hash = SHA256(session_id | title | narrative)
```

---

## 十一、相关文档

| 文档 | 路径 | 说明 |
|------|------|------|
| Skill文件 | `docs/Ariadne-Memory-SKILL.md` | Agent Skill 定义文件 |
| MCP文档 | `docs/MCP.md` | MCP Server 详细文档 |
| MCP配置示例 | `examples/mcp_config.json` | MCP 客户端配置模板 |
| 测试计划 | `docs/TEST_AND_EXTENSION_PLAN.md` | 测试方案和扩展计划 |
| Session Memory 设计 | `docs/SESSION_MEMORY_HOOK_DESIGN.md` | Hook 系统架构设计 |
| Claude-Mem对比 | `docs/CLAUDE_MEM_COMPARISON.md` | Claude-Mem 功能对比分析 |
