# Claude-Mem vs Ariadne — 功能对比与 Session Memory 设计文档

> 版本：v1.0 · 日期：2026-04-24 · 作者：Ariadne Team

---

## 一、功能对比矩阵

| 维度 | Claude-Mem | Ariadne v0.6.2 | 差距 |
|------|-----------|----------------|------|
| **存储后端** | SQLite + ChromaDB | ChromaDB + NetworkX + SQLite | 基本持平 |
| **跨会话记忆** | ✅ 5钩子生命周期自动持久化 | ✅ L0-L3 四层记忆栈 | 钩子机制缺失 |
| **工具使用观测** | ✅ PostToolUse 自动捕获 | ❌ 无 | **缺失** |
| **语义摘要生成** | ✅ Stop钩子驱动LLM摘要 | ✅ LLM摘要模块（手动） | 自动触发缺失 |
| **上下文注入** | ✅ SessionStart自动注入 | ✅ WakeUpContext/Closet | 钩子自动化缺失 |
| **语义上下文检索** | ✅ UserPromptSubmit即时检索 | ✅ RAG流水线（手动） | 自动触发缺失 |
| **多模型支持** | ✅ Claude/Gemini/OpenRouter | ✅ 9个提供商 | Ariadne更广 |
| **MCP工具** | ✅ search/timeline/get/smart系列 | ✅ 13个工具 | 缺timeline工具 |
| **隐私标签** | ✅ `<private>` 标签剥离 | ❌ 无 | **缺失** |
| **平台适配器** | ✅ Claude Code/Cursor/Gemini/OpenClaw/raw | ❌ 无 | **缺失** |
| **渐进式披露搜索** | ✅ search→timeline→get_observations | ❌ 无 | **缺失** |
| **知识图谱** | ❌ 无 | ✅ NetworkX+SQLite时序KG | Ariadne独有 |
| **摄取格式** | ❌ 无（仅会话观测） | ✅ 30+格式 | Ariadne独有 |
| **Web UI** | ✅ 只读查看器 | ✅ 完整CRUD + SSE流式 | 基本持平 |
| **模式系统** | ✅ JSON模式文件（code/law等） | ❌ 无 | 可选借鉴 |
| **Worker守护进程** | ✅ Express HTTP后台服务 | ✅ FastAPI（Web模式） | 架构不同 |
| **WAL审计日志** | ❌ 无 | ✅ WAL模块 | Ariadne独有 |
| **Wiki系统** | ❌ 无 | ✅ Karpathy LLM Wiki | Ariadne独有 |

---

## 二、Claude-Mem 核心机制深度解析

### 2.1 五钩子生命周期

```
SessionStart      → 生成并注入上下文到对话头部
UserPromptSubmit  → 语义检索相关记忆，注入当前提示
PostToolUse       → 捕获工具调用 (tool_name/input/output/cwd)
Stop/Summary      → LLM生成会话摘要，提取结构化观测
SessionEnd        → 标记会话完成，清理待处理消息
```

### 2.2 观测流水线（Observation Pipeline）

```
PostToolUse hook
    → Worker HTTP /api/sessions/observations
        → PendingMessageStore (CLAIM-CONFIRM队列)
            → SDKAgent/GeminiAgent/OpenRouterAgent
                → LLM生成 <observation>/<summary> XML
                    → ResponseProcessor
                        → SQLite存储
                        → ChromaDB同步
                        → SSE广播到Web UI
```

**观测XML格式**：
```xml
<observation>
  <type>bugfix|feature|refactor|change|discovery|decision|security_alert</type>
  <summary>一句话描述</summary>
  <detail>详细内容</detail>
  <files>受影响的文件列表</files>
  <concepts>相关概念列表</concepts>
</observation>
```

### 2.3 渐进式披露搜索（Progressive Disclosure）

```
Step 1: search(query)         → 返回摘要列表（低token）
Step 2: timeline(session_id)  → 展开该会话时间线（中token）
Step 3: get_observations(ids) → 获取指定观测全文（按需）
```

这种3层设计避免了一次性加载全部数据，大幅减少LLM上下文消耗。

### 2.4 CLAIM-CONFIRM 队列模式

```
enqueue(message)      → pending状态
claimNextMessage()    → claimed状态（防并发重复处理）
confirmProcessed(id)  → processed状态
markFailed(id)        → failed状态（可重试）
```

### 2.5 隐私保护机制

Claude-Mem 在钩子层自动剥离以下标签：
- `<private>...</private>` — 用户标记的私密内容
- `<claude-mem-context>` — 已注入的上下文块（防循环摘要）
- `<system_instruction>` — 系统指令
- `<system-reminder>` — 系统提醒

---

## 三、Ariadne Session Memory 设计方案

### 3.1 设计目标

1. **不依赖特定AI平台** — 支持任何MCP客户端（Claude Code、Cursor、OpenClaw、通用CLI）
2. **自动观测捕获** — 工具调用自动记录，无需用户手动操作
3. **智能摘要** — 会话结束时LLM自动提炼关键观测
4. **上下文注入** — 会话开始时自动注入相关历史
5. **渐进式搜索** — 3层搜索减少token消耗
6. **隐私保护** — `<private>` 标签支持

### 3.2 新增模块架构

```
ariadne/
  session/                    ← 新增：Session Memory 核心
    __init__.py
    models.py                 ← 数据模型：Session, Observation, SessionSummary
    store.py                  ← SQLite CRUD（sessions表）
    observation_store.py      ← 观测存储 + ChromaDB同步
    summarizer.py             ← LLM驱动的摘要生成
    context_builder.py        ← 上下文注入生成器
    privacy.py                ← 隐私标签剥离
  hooks/                      ← 新增：平台钩子适配器
    __init__.py
    base.py                   ← BasePlatformAdapter 抽象类
    claude_code.py            ← Claude Code 适配器
    openclaw.py               ← OpenClaw 适配器
    cursor.py                 ← Cursor 适配器
    generic.py                ← 通用CLI适配器
    runner.py                 ← 钩子运行器（stdin→适配器→处理器）
```

### 3.3 数据库 Schema

```sql
-- 会话表
CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    project_path TEXT NOT NULL,
    platform TEXT NOT NULL,          -- claude_code/openclaw/cursor/generic
    started_at TEXT NOT NULL,
    ended_at TEXT,
    summary TEXT,                    -- L1叙事层摘要
    status TEXT DEFAULT 'active'     -- active/completed/summarized
);

-- 观测表
CREATE TABLE observations (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    obs_type TEXT NOT NULL,          -- bugfix/feature/refactor/change/discovery/decision
    summary TEXT NOT NULL,           -- 一句话摘要
    detail TEXT,                     -- 详细内容
    files TEXT,                      -- JSON数组：受影响文件
    concepts TEXT,                   -- JSON数组：相关概念
    tool_name TEXT,                  -- 触发观测的工具名
    tool_input TEXT,                 -- 工具输入（JSON）
    created_at TEXT NOT NULL,
    chroma_synced INTEGER DEFAULT 0,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

-- 待处理消息队列
CREATE TABLE pending_messages (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    payload TEXT NOT NULL,           -- JSON
    status TEXT DEFAULT 'pending',   -- pending/claimed/processed/failed
    created_at TEXT NOT NULL,
    claimed_at TEXT,
    processed_at TEXT
);
```

### 3.4 MCP 新增工具

| 工具名 | 功能 |
|--------|------|
| `ariadne_session_start` | 初始化会话，返回注入上下文 |
| `ariadne_session_observe` | 提交工具使用观测 |
| `ariadne_session_summarize` | 触发会话摘要生成 |
| `ariadne_session_end` | 结束会话 |
| `ariadne_session_search` | 搜索历史观测（渐进式） |
| `ariadne_session_timeline` | 获取会话时间线 |
| `ariadne_session_get` | 获取指定观测详情 |

### 3.5 Hook 配置文件格式

**Claude Code** (`~/.claude/settings.json`):
```json
{
  "hooks": {
    "SessionStart":     [{"hooks": [{"type": "command", "command": "ariadne hook --event session_start"}]}],
    "UserPromptSubmit": [{"hooks": [{"type": "command", "command": "ariadne hook --event user_prompt"}]}],
    "PostToolUse":      [{"hooks": [{"type": "command", "command": "ariadne hook --event post_tool"}]}],
    "Stop":             [{"hooks": [{"type": "command", "command": "ariadne hook --event stop"}]}]
  }
}
```

**OpenClaw** 通过 MCP Server 直接调用，无需外部钩子。

### 3.6 Web UI 新增面板

- **Session Timeline** 页面：显示所有会话列表 + 时间线
- **Observation Browser**：按类型/文件/概念筛选观测
- **SSE 实时更新**：新观测实时推送到前端

---

## 四、实施优先级

| 优先级 | 模块 | 原因 |
|--------|------|------|
| P0 | `session/models.py` + `session/store.py` | 所有功能的基础 |
| P0 | `session/observation_store.py` | 核心观测存储 |
| P0 | `session/summarizer.py` | 利用现有LLM工厂 |
| P1 | `session/context_builder.py` | 上下文注入 |
| P1 | `hooks/` 平台适配器 | 自动化触发 |
| P1 | MCP 新增工具 | 与AI客户端集成 |
| P2 | `session/privacy.py` | 隐私保护 |
| P2 | Web UI 面板 | 可视化 |

---

*本文档由 Ariadne Team 生成，参考 Claude-Mem v12.3.9 架构设计*
