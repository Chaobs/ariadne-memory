# Ariadne MCP Server

Model Context Protocol (MCP) integration for Ariadne Memory System.

## 概述

Ariadne MCP Server 将知识库能力以 MCP 工具、资源和提示模板的形式暴露，可被任何 MCP 兼容客户端（如 Claude Desktop、Cursor、VS Code 等）消费。

## 功能特性

### MCP Tools（工具）

| 工具名 | 功能 | 参数 |
|--------|------|------|
| `ariadne_search` | 向量语义搜索 | query, limit, collection |
| `ariadne_ingest` | 摄入文档/URL | source, collection, extract_entities |
| `ariadne_graph_query` | 知识图谱查询 | entity, relation_type, depth, direction |
| `ariadne_stats` | 知识库统计 | collection, detailed |

### MCP Resources（资源）

| 资源 URI | 类型 | 说明 |
|----------|------|------|
| `ariadne://collections` | JSON | 可用集合列表 |
| `ariadne://stats` | JSON | 知识库统计信息 |
| `ariadne://config` | JSON | 系统配置 |

### MCP Prompts（提示模板）

| 提示名 | 功能 |
|--------|------|
| `ariadne_search` | 自然语言搜索模板 |
| `ariadne_ingest` | 文档摄入模板 |
| `ariadne_graph` | 图谱探索模板 |
| `ariadne_context` | 上下文获取模板 |
| `ariadne_compare` | 概念比较模板 |

## 安装

### 方式一：通过包安装

```bash
cd Ariadne
pip install -e .
```

### 方式二：直接运行

```bash
cd Ariadne
python -m ariadne.tools.mcp_server
```

## 配置

### Claude Desktop

在 `claude_desktop_config.json` 中添加：

```json
{
  "mcpServers": {
    "ariadne": {
      "command": "python",
      "args": [
        "-m",
        "ariadne.tools.mcp_server",
        "--vectors",
        "/path/to/your/vectors",
        "--graph",
        "/path/to/your/graph.db"
      ]
    }
  }
}
```

### 自定义配置

创建 `config.json`：

```json
{
  "vector_store": {
    "path": "./data/vectors"
  },
  "graph": {
    "path": "./data/graph.db"
  },
  "llm": {
    "provider": "deepseek",
    "model": "deepseek-chat",
    "api_key": "your-api-key"
  },
  "server": {
    "host": "127.0.0.1",
    "port": 8765
  }
}
```

## 使用方法

### 命令行启动

```bash
# Stdio 模式（默认，用于 Claude Desktop）
python -m ariadne.tools.mcp_server

# HTTP 模式
python -m ariadne.tools.mcp_server --transport http --port 8765

# 指定数据路径
python -m ariadne.tools.mcp_server --vectors ./data/vectors --graph ./data/graph.db

# 指定配置文件
python -m ariadne.tools.mcp_server --config config.json
```

### Python API

```python
from ariadne.mcp import create_server

# 创建服务器
server = create_server(
    vector_store_path="./data/vectors",
    graph_db_path="./data/graph.db",
)

# Stdio 模式
server.run_stdio()

# HTTP 模式
server.run(host="0.0.0.0", port=8765)
```

### 集成到现有应用

```python
from ariadne.mcp import AriadneMCPServer

server = AriadneMCPServer(
    vector_store_path="./vectors",
    graph_db_path="./graph.db",
)

# 处理 MCP 请求
response = server.handle_request({
    "jsonrpc": "2.0",
    "id": "1",
    "method": "tools/call",
    "params": {
        "name": "ariadne_search",
        "arguments": {"query": "What is quantum computing?"}
    }
})
```

## MCP 协议版本

- **协议版本**: 2024-11-05
- **服务器版本**: 2.0.0

## 示例对话

### 搜索知识库

```
用户: 搜索关于量子计算的信息
工具调用: ariadne_search({query: "quantum computing"})
结果: 返回相关文档列表及其相似度分数
```

### 摄入新文档

```
用户: 把这个PDF摄入到知识库
工具调用: ariadne_ingest({source: "/path/to/doc.pdf"})
结果: 返回摄入的文档数量和块数
```

### 探索关系

```
用户: 爱因斯坦和相对论有什么关系
工具调用: ariadne_graph_query({entity: "Albert Einstein", depth: 2})
结果: 返回实体及其关联关系图
```

## 故障排除

### 连接问题

```bash
# 检查端口占用
netstat -an | grep 8765

# 使用不同端口
python -m ariadne.tools.mcp_server --port 8766
```

### 调试模式

```bash
# 开启详细日志
python -m ariadne.tools.mcp_server --log-level DEBUG
```

### 数据路径问题

```bash
# 使用绝对路径
python -m ariadne.tools.mcp_server --vectors /absolute/path/to/vectors
```

## 开发

### 本地测试

```bash
# 测试服务器
python -m ariadne.tools.mcp_server

# 运行单元测试
python -m pytest tests/mcp/
```

## License

MIT License - 参见 LICENSE 文件
