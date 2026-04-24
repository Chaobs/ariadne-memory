# Claude-Mem vs Ariadne Session Memory 对比分析报告

> **作者**: Ariadne Agent  
> **日期**: 2026-04-24  
> **目的**: 为 Ariadne 吸收 Claude-Mem 永久记忆功能提供技术路线图

---

## 1. 项目概览对比

| 维度 | Claude-Mem | Ariadne Session Memory |
|------|-----------|----------------------|
| **定位** | Claude CLI 专用记忆系统 | 跨平台通用记忆与知识系统 |
| **技术栈** | TypeScript + Node.js + Bun | Python + FastAPI + React |
| **存储** | SQLite + ChromaDB | SQLite + ChromaDB (相同) |
| **核心功能** | 5钩子生命周期 + SSE实时推送 | Hook系统 + RAG搜索 |
| **部署模式** | Worker Service (HTTP API) | 嵌入式库 + MCP Server |

---

## 2. 架构深度对比

### 2.1 生命周期钩子系统

**Claude-Mem 5钩子模型:**

```typescript
// src/shared/hook-constants.ts
export const HOOK_NAMES = {
  SESSION_START: "SessionStart",
  USER_PROMPT_SUBMIT: "UserPromptSubmit",
  POST_TOOL_USE: "PostToolUse",
  STOP: "Stop",
  SESSION_END: "SessionEnd",
} as const;
```

**Claude-Mem Hook 触发流程:**

```
┌─────────────────────────────────────────────────────────────────┐
│                     Claude-Mem 生命周期                          │
├─────────────────────────────────────────────────────────────────┤
│ 1. SessionStart ──→ 注入历史上下文 + session ID                  │
│ 2. UserPromptSubmit → 注入语义相关观察（每次用户输入时）            │
│ 3. PostToolUse ───→ 记录工具使用观察（每次工具调用后）             │
│ 4. Stop ───────────→ 停止钩子（每N条消息触发，可用于中途保存）       │
│ 5. SessionEnd ────→ 生成会话摘要 + 持久化                         │
└─────────────────────────────────────────────────────────────────┘
```

**Ariadne 现有钩子:**

```
ariadne/hooks/
├── base.py          # BasePlatformAdapter 基类
├── claude_code.py   # Claude Code 适配器
├── cursor.py        # Cursor 适配器
├── openclaw.py      # OpenClaw 适配器
├── generic.py       # 通用适配器
└── runner.py        # HookRunner 执行器
```

**Ariadne 事件类型:**
- `session_start` — 会话开始
- `post_tool` — 工具使用后
- `user_prompt` / `user_prompt_submit` — 用户输入提交
- `stop` / `summary` — 停止/摘要生成

✅ **结论**: Ariadne 已有完整的钩子基础设施，与 Claude-Mem 的5钩子模型高度对齐。

---

### 2.2 观察系统 (Observation System)

**Claude-Mem Observation 存储 (`src/services/sqlite/observations/store.ts`):**

```typescript
interface Observation {
  id: string;
  sessionId: string;
  type: string;           // "bugfix" | "feature" | "refactor" | "change" | ...
  title: string;
  subtitle: string;
  facts: string[];
  concepts: string[];
  filesRead: string[];
  filesModified: string[];
  createdAt: string;
}

// 去重: SHA256(content_hash) 30秒窗口
const contentHash = crypto
  .createHash('sha256')
  .update(`${sessionId}|${title}|${narrative}`)
  .digest('hex');
```

**Ariadne Observation 模型 (`ariadne/session/models.py`):**

```python
@dataclass
class Observation:
    id: str
    session_id: str
    obs_type: ObservationType      # BUGFIX, FEATURE, REFACTOR, ...
    summary: str                    # 对应 title
    detail: Optional[str] = None     # 对应 subtitle
    files: List[str] = field(...)   # files_modified + files_read
    concepts: List[str] = field(...) # concepts
    tool_name: Optional[str] = None
    tool_input: Optional[dict] = None
    tool_output: Optional[str] = None
    created_at: str
    chroma_synced: bool = False
```

**差异分析:**

| 特性 | Claude-Mem | Ariadne | 建议 |
|------|-----------|---------|------|
| 去重机制 | SHA256 30秒窗口 | 无 | **待实现** |
| 文件分类 | filesRead / filesModified | 合并为 files | **待改进** |
| 事实提取 | facts[] 数组 | detail 文本 | **结构化对齐** |

---

### 2.3 Worker Service 对比

**Claude-Mem Worker Service (`src/services/worker-service.ts`):**

```typescript
// 核心架构
class WorkerService {
  private dbManager: DBManager;           // SQLite 管理
  private sessionManager: SessionManager;  // 会话管理
  private sseBroadcaster: SSEBroadcaster; // SSE 实时推送
  private sdkAgent: SDKAgent;              // Claude API
  private geminiAgent: GeminiAgent;        // Gemini Fallback
  private openRouterAgent: OpenRouterAgent; // OpenRouter Fallback
}
```

**HTTP 路由 (`src/services/worker/http/routes/`):**

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/sessions` | GET/POST | 会话列表/创建 |
| `/api/sessions/:id/observations` | POST | 添加观察 |
| `/api/sessions/:id/summary` | GET | 获取摘要 |
| `/api/search` | GET | 混合搜索 |
| `/stream` | GET | SSE 实时流 |
| `/viewer` | GET | Web UI |

**Ariadne 现有服务:**

```
ariadne/web/
├── main.py           # FastAPI 应用
├── routes/           # API 路由
│   ├── sessions.py    # 会话管理
│   ├── observations.py # 观察管理
│   └── search.py      # 搜索
└── static/           # React SPA
```

✅ **Ariadne 已有 Web UI，但缺少 SSE 实时推送功能**

---

### 2.4 SSE 实时推送实现

**Claude-Mem SSE (`src/services/worker/http/routes/ViewerRoutes.ts`):**

```typescript
// SSE 端点
server.experimental_get("/stream", async (req, reply) => {
  const stream = new SSEStream();
  
  // SessionManager 事件监听
  sessionManager.on('newObservation', (obs) => {
    stream.push({ type: 'observation', data: obs });
  });
  
  sessionManager.on('newSummary', (summary) => {
    stream.push({ type: 'summary', data: summary });
  });
  
  return stream;
});
```

**事件驱动架构 (`src/services/worker/SessionManager.ts`):**

```typescript
class SessionManager extends EventEmitter {
  async queueObservation(sessionId: string, obs: Observation) {
    // 异步队列处理
    await this.dbManager.addObservation(obs);
    this.emit('newObservation', obs);  // 触发 SSE
  }
}
```

---

### 2.5 LLM 多提供商支持

**Claude-Mem 多提供商 (`src/services/worker/`):**

| 提供商 | 实现文件 | 用途 |
|--------|---------|------|
| Claude SDK | `sdk-agent.ts` | 主提供商 |
| Gemini | `gemini-agent.ts` | Fallback #1 |
| OpenRouter | `open-router-agent.ts` | Fallback #2 |

**Ariadne 现有 LLM 支持 (`ariadne/llm/`):**

```python
# 支持的提供商
- OpenAI (GPT-4, GPT-4o)
- DeepSeek (deepseek-chat / deepseek-v4-flash)
- Claude (via OpenAI兼容API)
- SiliconFlow
- SiliconFlow 本地模型
```

✅ **Ariadne 多提供商已完善，无需额外实现**

---

## 3. 功能差距分析

### 3.1 缺失功能清单

| 优先级 | 功能 | Claude-Mem 实现 | Ariadne 现状 | 实现方案 |
|--------|------|----------------|-------------|---------|
| 🔴 P0 | **SSE 实时推送** | SSEBroadcaster + EventEmitter | ❌ 无 | 新建 SSE 模块 |
| 🔴 P0 | **Content-Hash 去重** | SHA256 30s 窗口 | ❌ 无 | 新增去重逻辑 |
| 🟡 P1 | **Stop 钩子** | 每15条消息触发 | ⚠️ 框架有，逻辑待完善 | 增强 HookRunner |
| 🟡 P1 | **Web UI 观察页面** | 完整查看器 | ⚠️ 基础页面 | 增强 React 组件 |
| 🟡 P1 | **OpenClaw 插件** | `openclaw/src/index.ts` | ⚠️ 适配器有，插件待完善 | 完善 MCP 集成 |
| 🟢 P2 | **观察导出/导入** | XML 格式 | ❌ 无 | 新增工具脚本 |
| 🟢 P2 | **Pending 队列监控** | 健康检查脚本 | ⚠️ 基础队列有 | 增强监控 |

### 3.2 待实现的 SSE 实时推送

**目标文件:** `ariadne/session/sse_broadcaster.py`

```python
"""
SSE Broadcaster — real-time observation streaming to Web UI.

Inspired by Claude-Mem's SSEBroadcaster and SessionManager EventEmitter pattern.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, asdict
from typing import Callable, Dict, Set, Optional
from enum import Enum

class SSEEventType(str, Enum):
    NEW_OBSERVATION = "new_observation"
    NEW_SUMMARY = "new_summary"
    SESSION_ENDED = "session_ended"
    ERROR = "error"

@dataclass
class SSEEvent:
    type: SSEEventType
    session_id: Optional[str] = None
    data: Optional[dict] = None
    
    def to_sse(self) -> str:
        payload = json.dumps({
            "type": self.type.value,
            "session_id": self.session_id,
            "data": self.data,
        })
        return f"data: {payload}\n\n"

class SSEBroadcaster:
    """
    Manages SSE connections and broadcasts events to all clients.
    
    Usage:
        broadcaster = SSEBroadcaster()
        broadcaster.register(client_id)  # 新客户端连接
        broadcaster.broadcast(SSEEvent(SSEEventType.NEW_OBSERVATION, session_id, obs_data))
        broadcaster.unregister(client_id)  # 客户端断开
    """
    
    def __init__(self):
        self._clients: Dict[str, Set[Callable]] = {}  # session_id -> set of send functions
        self._global_clients: Set[Callable] = set()  # 订阅所有事件
        self._lock = asyncio.Lock()
        logger = logging.getLogger(__name__)
    
    async def subscribe(
        self,
        client_id: str,
        send_fn: Callable,
        session_filter: Optional[str] = None,
    ) -> None:
        """Register a new SSE client connection."""
        async with self._lock:
            if session_filter:
                if session_filter not in self._clients:
                    self._clients[session_filter] = set()
                self._clients[session_filter].add(send_fn)
            else:
                self._global_clients.add(send_fn)
    
    async def unsubscribe(self, client_id: str, send_fn: Callable) -> None:
        """Unregister a SSE client."""
        async with self._lock:
            # 从全局移除
            self._global_clients.discard(send_fn)
            # 从 session 过滤移除
            for clients in self._clients.values():
                clients.discard(send_fn)
    
    async def broadcast(self, event: SSEEvent) -> None:
        """Broadcast an event to all subscribed clients."""
        message = event.to_sse()
        
        # 发送给全局订阅者
        dead_clients = set()
        for send_fn in self._global_clients:
            try:
                await send_fn(message)
            except Exception:
                dead_clients.add(send_fn)
        
        # 发送给特定 session 订阅者
        if event.session_id and event.session_id in self._clients:
            for send_fn in self._clients[event.session_id]:
                try:
                    await send_fn(message)
                except Exception:
                    dead_clients.add(send_fn)
        
        # 清理失效连接
        for client in dead_clients:
            await self.unsubscribe("", client)
```

---

### 3.3 待实现的 Content-Hash 去重

**目标文件:** `ariadne/session/observation_store.py` (增强)

```python
# 在 ObservationStore 中添加去重逻辑

import hashlib
import time
from collections import OrderedDict

class DeduplicationCache:
    """
    Time-windowed content hash deduplication.
    
    Mirrors Claude-Mem's SHA256 content hash with 30-second window.
    """
    
    def __init__(self, window_seconds: float = 30.0):
        self._window = window_seconds
        self._cache: OrderedDict[str, float] = OrderedDict()  # hash -> timestamp
    
    def _compute_hash(self, session_id: str, title: str, narrative: str) -> str:
        content = f"{session_id}|{title}|{narrative}"
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
    
    def is_duplicate(self, session_id: str, title: str, narrative: str) -> bool:
        """Check if content is a duplicate within the time window."""
        hash_key = self._compute_hash(session_id, title, narrative)
        current_time = time.time()
        
        # 清理过期条目
        while self._cache and current_time - list(self._cache.values())[0] > self._window:
            self._cache.popitem(last=False)
        
        if hash_key in self._cache:
            return True  # 重复
        
        self._cache[hash_key] = current_time
        return False
    
    def clear(self) -> None:
        self._cache.clear()
```

---

## 4. 实现路线图

### Phase 1: SSE 实时推送 (优先级 P0)

```
📦 ariadne/session/sse_broadcaster.py    # 新建
📦 ariadne/web/routes/sse.py             # 新建 SSE 路由
📦 ariadne/web/static/js/               # 前端 SSE 客户端
```

**依赖文件更新:**
- `ariadne/session/manager.py` — 集成 SSEBroadcaster
- `ariadne/web/main.py` — 注册 SSE 路由

### Phase 2: Content-Hash 去重 (优先级 P0)

```
📝 ariadne/session/observation_store.py  # 增强
📝 ariadne/session/models.py             # 添加 hash 字段
```

### Phase 3: Web UI 观察页面 (优先级 P1)

```
📦 ariadne/web/static/js/observations/  # 观察列表/详情组件
📦 ariadne/web/routes/sse.py             # SSE 实时更新
```

### Phase 4: OpenClaw 深度集成 (优先级 P1)

```
📝 ariadne/hooks/openclaw.py             # 完善事件映射
📝 docs/OPENCLAW_INTEGRATION.md          # 集成文档
```

---

## 5. 关键差异与建议

### 5.1 设计哲学差异

| 维度 | Claude-Mem | Ariadne | 建议 |
|------|-----------|---------|------|
| 架构模式 | Worker Service 独立进程 | 嵌入式库 | 保持 Ariadne 模式 |
| 通信方式 | HTTP + SSE | HTTP + SSE (待实现) | 直接复用 |
| 平台适配 | TypeScript 多适配器 | Python 适配器 | 保持现状 |
| 配置方式 | JSON 配置文件 | JSON + 环境变量 | 保持现状 |

### 5.2 可直接复用的 Claude-Mem 设计

1. **EventEmitter 模式** — 用于 SSE 广播
2. **30秒 Content-Hash 去重** — 减少重复观察
3. **SessionManager 队列** — Pending 消息处理
4. **观察类型分类** — BUGFIX/FEATURE/REFACTOR 等

### 5.3 Ariadne 独有优势

1. **MCP Server 内置** — 无需额外 Worker Service
2. **RAG 混合搜索** — ChromaDB + BM25 + 重新排序
3. **知识图谱集成** — NetworkX 图谱
4. **多格式摄入** — 30+ 格式文档支持

---

## 6. 测试策略

### 6.1 单元测试

```python
# tests/test_sse_broadcaster.py
class TestDeduplicationCache:
    def test_same_content_within_window_is_duplicate(self):
        cache = DeduplicationCache(window_seconds=30.0)
        assert cache.is_duplicate("s1", "title", "narrative") == False
        assert cache.is_duplicate("s1", "title", "narrative") == True
    
    def test_different_content_not_duplicate(self):
        cache = DeduplicationCache(window_seconds=30.0)
        assert cache.is_duplicate("s1", "title1", "narrative") == False
        assert cache.is_duplicate("s1", "title2", "narrative") == False
```

### 6.2 集成测试

```python
# tests/test_sse_integration.py
async def test_sse_broadcast_flow():
    """Test complete SSE broadcast from observation to client."""
    broadcaster = SSEBroadcaster()
    received = []
    
    async def mock_send(msg):
        received.append(msg)
    
    await broadcaster.subscribe("client1", mock_send)
    await broadcaster.broadcast(SSEEvent(
        SSEEventType.NEW_OBSERVATION,
        session_id="s1",
        data={"id": "obs1", "summary": "test"}
    ))
    
    assert len(received) == 1
    assert "obs1" in received[0]
```

---

## 7. 附录

### A. Claude-Mem 核心文件索引

| 文件 | 用途 |
|------|------|
| `src/services/worker-service.ts` | Worker 主服务 |
| `src/services/worker/SessionManager.ts` | 会话生命周期 |
| `src/services/sqlite/observations/store.ts` | 观察存储 |
| `src/services/worker/http/routes/ViewerRoutes.ts` | Web UI 路由 |
| `src/shared/hook-constants.ts` | 钩子常量 |
| `openclaw/src/index.ts` | OpenClaw 插件 |

### B. Ariadne 现有文件

| 文件 | 用途 |
|------|------|
| `ariadne/session/manager.py` | 会话管理器 |
| `ariadne/session/models.py` | 数据模型 |
| `ariadne/session/observation_store.py` | 观察存储 |
| `ariadne/session/summarizer.py` | 摘要生成 |
| `ariadne/session/context_builder.py` | 上下文构建 |
| `ariadne/hooks/runner.py` | 钩子执行器 |

---

**报告生成时间**: 2026-04-24 14:40  
**下一步**: 进入 Task 2 — 架构设计（Session Memory Hook 系统详细设计）
