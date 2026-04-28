# AI 代理对话记忆实时向量化架构设计

> **作者**: Ariadne Agent
> **日期**: 2026-04-28
> **目的**: 为 Ariadne 的 AI 代理对话记忆实时向量化功能提供详细技术设计，增强 Ariadne 与用户日常 AI 工作流的无缝集成

---

## 1. 设计目标

### 1.1 核心目标

1. **AI 代理对话记忆实时向量化** — 自动将外部 AI 代理（WorkBuddy、OpenClaw 等）的对话记忆文件（如 MEMORY.md、YYYY-MM-DD.md）实时向量化并存入 Ariadne 知识库
2. **现有 Session Observations 向量化增强** — 确保现有的 Session Memory Hook 系统产生的观察记录（Observations）能够实时向量化到专用 ChromaDB 集合
3. **多源记忆文件支持** — 支持监控多个目录下的记忆文件，自动解析 Markdown、JSON、YAML 等格式
4. **去重与增量处理** — 基于内容哈希或文件修改时间，避免重复处理相同内容
5. **实时监控与手动触发** — 提供文件系统监控（watchdog）和手动触发两种摄入模式
6. **完整的 CLI 与 Web UI 接口** — 提供命令行和可视化界面进行监控管理、状态查看、手动触发

### 1.2 非目标

- 不替代现有的摄入系统（Ingest），而是作为其补充，专注于实时、增量、自动化的记忆文件处理
- 不修改现有记忆系统（MemoryManager）的核心存储逻辑，仅扩展其摄入源
- 不要求外部 AI 代理修改其记忆文件格式，保持向后兼容

---

## 2. 系统架构

### 2.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         External AI Agent Platforms                       │
│  (WorkBuddy / OpenClaw / QClaw / etc.)                                    │
├─────────────────────────────────────────────────────────────────────────┤
│                         Memory Files                                      │
│  MEMORY.md │ YYYY-MM-DD.md │ session_logs/ │ custom_memory/              │
└─────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        FileWatcher (ariadne/realtime/watcher.py)         │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                    Watchdog-based Monitoring                      │   │
│  │  Directory Watch │ Pattern Filter │ Event Queue │ Debounce        │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                  ObservationIngestor (ariadne/realtime/ingestor.py)      │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                    Parser Registry                                │   │
│  │  MarkdownParser │ JsonParser │ YamlParser │ TextParser            │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                    Document Converter                             │   │
│  │  File → Document(s) │ Metadata Extraction │ Chunking             │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│               RealtimeVectorizer (ariadne/realtime/vectorizer.py)       │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                    Coordinator                                   │   │
│  │  Watchdog Thread │ Ingestion Queue │ Status Reporting            │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    Ariadne Memory System                                 │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                    MemoryManager                                  │   │
│  │  Default Collection │ Session Observations Collection │ Custom    │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 组件详细说明

#### 2.2.1 FileWatcher

**职责**:
- 监控指定目录下的文件系统事件（创建、修改、删除）
- 支持通配符模式过滤（如 `*.md`, `MEMORY.md`, `YYYY-MM-DD.md`）
- 事件去抖（debounce）避免短时间内重复处理同一文件
- 将文件路径放入待处理队列

**接口**:
```python
class FileWatcher:
    def __init__(self, watch_dirs: List[str], patterns: List[str] = None, debounce_secs: float = 2.0):
        ...
    def start(self) -> None: ...
    def stop(self) -> None: ...
    def get_pending_files(self) -> List[Path]: ...
    def clear_pending(self) -> None: ...
    def is_running(self) -> bool: ...
```

#### 2.2.2 ObservationIngestor

**职责**:
- 将外部记忆文件解析为 Ariadne 的 Document 对象
- 支持多种文件格式（Markdown、JSON、YAML、纯文本）
- 提取元数据（源文件路径、修改时间、文件类型等）
- 可选地调用 LLM 进行实体提取和知识图谱丰富
- 将 Document 对象添加到指定的记忆系统（集合）

**接口**:
```python
class ObservationIngestor:
    def __init__(self, memory_system: str = "default", enrich: bool = False):
        ...
    def ingest_file(self, file_path: Path) -> List[Document]:
        """解析文件并返回 Document 列表"""
    def ingest_text(self, text: str, source: str = "manual") -> List[Document]:
        """解析文本并返回 Document 列表"""
    def save_to_store(self, documents: List[Document]) -> int:
        """将 Document 列表存入向量存储，返回成功数量"""
```

#### 2.2.3 RealtimeVectorizer

**职责**:
- 协调 FileWatcher 和 ObservationIngestor
- 管理监控线程和摄入队列
- 提供启动/停止监控的 API
- 状态报告（已监控文件数、已摄入文档数、最近错误等）
- 持久化配置（监控目录、文件模式、目标记忆系统）

**接口**:
```python
class RealtimeVectorizer:
    def __init__(self, config: Optional[Dict] = None):
        ...
    def start_watching(self, watch_dirs: List[str], patterns: List[str] = None) -> bool: ...
    def stop_watching(self) -> None: ...
    def ingest_now(self, file_path: Optional[Path] = None) -> Dict[str, Any]:
        """立即触发摄入（单个文件或所有待处理文件）"""
    def get_status(self) -> Dict[str, Any]: ...
    def get_history(self, limit: int = 100) -> List[Dict[str, Any]]: ...
```

### 2.3 与现有系统的集成

#### 2.3.1 与 Session Memory Hook 系统集成

现有的 Session Memory Hook 系统已经通过 `ObservationStore._sync_to_chroma()` 将 Observations 同步到 ChromaDB 集合 `session_observations`。实时向量化系统应：

1. **重用同步机制**：扩展 `ObservationStore` 以支持实时触发，或创建一个新的服务监听 Observation 创建事件。
2. **独立集合**：Session Observations 存储在专用集合，外部记忆文件存储在用户指定的集合（默认 "default"）。
3. **统一查询**：通过 RAG 搜索可以同时查询多个集合。

#### 2.3.2 与 MemoryManager 集成

`MemoryManager` 管理多个记忆系统（集合）。实时向量化系统应：

1. **使用 MemoryManager** 获取 VectorStore 实例。
2. **支持多目标集合**：允许用户指定将外部记忆文件摄入到哪个记忆系统。
3. **避免冲突**：确保并发访问的安全性。

#### 2.3.3 与 Ingest 系统集成

现有的 `ingest` 模块支持多种文件格式的批量摄入。实时向量化系统应：

1. **重用解析器**：使用现有的 `get_ingestor()` 函数解析文件。
2. **增量处理**：仅处理新增或修改的文件，而非全量摄入。
3. **轻量级**：避免启动完整的 LLM 增强流程，除非用户显式启用。

---

## 3. 数据流设计

### 3.1 实时监控流程

```
1. 用户配置监控目录和文件模式
2. RealtimeVectorizer 启动 FileWatcher
3. FileWatcher 检测到文件创建/修改事件
4. 事件经过去抖后放入待处理队列
5. RealtimeVectorizer 从队列取出文件路径
6. ObservationIngestor 解析文件为 Documents
7. Documents 通过 MemoryManager 存入指定集合
8. 状态更新（成功/失败计数、最后处理时间）
```

### 3.2 手动触发流程

```
1. 用户通过 CLI 或 Web UI 触发手动摄入
2. 指定文件或目录路径（可选，默认为所有监控目录）
3. ObservationIngestor 解析文件
4. Documents 存入向量存储
5. 返回处理结果统计
```

### 3.3 去重机制

为避免重复处理相同内容，采用两级去重：

1. **文件级别**：记录已处理文件的最后修改时间（mtime）和大小，仅当两者之一变化时才重新处理。
2. **内容级别**：计算文件内容的哈希值（如 SHA256），在短时间内（如24小时）跳过相同哈希值的文件。

---

## 4. API 设计

### 4.1 CLI 命令扩展

在现有的 `ariadne memory` 命令组下添加子命令：

```bash
# 启动实时监控
ariadne memory watch --dir ~/.workbuddy/memory --pattern "*.md" --collection external_memories

# 停止监控
ariadne memory watch --stop

# 手动摄入文件或目录
ariadne memory ingest-file ~/.workbuddy/memory/MEMORY.md --collection external_memories

# 手动摄入观察记录（从 Session Memory）
ariadne memory ingest-observation --session-id abc123 --limit 100

# 查看监控状态
ariadne memory watch-status

# 查看摄入历史
ariadne memory ingestion-history --limit 20
```

### 4.2 Web UI API 端点

新增 `/api/realtime/` 路由：

```
GET  /api/realtime/status                # 获取监控状态
POST /api/realtime/start                 # 启动监控 {watch_dirs: [], patterns: [], collection: "default"}
POST /api/realtime/stop                  # 停止监控
POST /api/realtime/ingest                # 手动触发摄入 {path?: string, collection?: string}
GET  /api/realtime/history               # 摄入历史记录
GET  /api/realtime/config                # 获取当前配置
PUT  /api/realtime/config                # 更新配置
```

### 4.3 MCP 工具扩展

检查现有 MCP 工具是否已覆盖所需功能。若未覆盖，可添加：

- `ariadne_realtime_watch`：启动/停止实时监控
- `ariadne_realtime_ingest`：手动触发文件摄入
- `ariadne_realtime_status`：获取监控状态

但考虑到 MCP 工具已相当丰富，可能优先通过 CLI 和 Web UI 提供功能，MCP 工具作为补充。

---

## 5. 配置与持久化

### 5.1 配置文件

实时向量化系统的配置存储于 `.ariadne/config/realtime.json`：

```json
{
  "watch_dirs": [
    "~/.workbuddy/memory",
    "~/.openclaw/sessions"
  ],
  "patterns": ["*.md", "MEMORY.md", "*.json"],
  "collection": "external_memories",
  "debounce_secs": 2.0,
  "enrich": false,
  "dedup_window_hours": 24,
  "max_file_size_mb": 10
}
```

### 5.2 状态持久化

记录处理历史于 `.ariadne/logs/realtime_history.jsonl`：

```json
{"timestamp": "2026-04-28T10:30:00Z", "file": "/path/to/MEMORY.md", "action": "ingest", "documents": 5, "success": true}
{"timestamp": "2026-04-28T10:31:00Z", "file": "/path/to/2026-04-28.md", "action": "skip", "reason": "content_unchanged"}
```

---

## 6. 错误处理与恢复

### 6.1 错误分类

1. **文件访问错误**：权限不足、文件不存在 → 记录警告，跳过该文件
2. **解析错误**：不支持的格式、损坏的文件 → 记录错误，跳过该文件
3. **存储错误**：ChromaDB 写入失败 → 重试机制（最多3次），然后记录失败
4. **监控错误**：Watchdog 异常 → 重启监控线程

### 6.2 恢复机制

- **断点续传**：记录最后成功处理的位置，重启后从断点继续
- **重试队列**：失败的任务放入重试队列，指数退避重试
- **健康检查**：定期检查监控线程和存储连接状态

---

## 7. 性能考虑

### 7.1 资源消耗

- **内存**：文件解析和文档转换需保持内存占用可控，大文件分块处理
- **CPU**：监控线程轻量，解析和向量化可异步进行
- **磁盘 I/O**：避免频繁读取同一文件，使用缓存和去重

### 7.2 可扩展性

- **多目录监控**：支持同时监控多个目录，每个目录独立线程
- **批量处理**：积累多个文件后批量处理，减少向量存储写入次数
- **异步处理**：使用 asyncio 或线程池处理文件解析和存储

---

## 8. 测试计划

### 8.1 单元测试

- `FileWatcher` 模拟文件系统事件
- `ObservationIngestor` 各种文件格式解析
- `RealtimeVectorizer` 启动/停止、状态报告

### 8.2 集成测试

- 完整流程：文件修改 → 监控检测 → 解析 → 存储 → 查询验证
- 与现有 Session Memory 系统集成
- 与 Web UI 和 CLI 交互

### 8.3 性能测试

- 大量文件同时修改时的处理能力
- 长时间运行的内存泄漏检测
- 恢复机制的有效性

---

## 9. 实施计划

### Phase 1：核心模块实现 (2-3天)
1. 实现 `ObservationIngestor` 和 `FileWatcher`
2. 实现 `RealtimeVectorizer` 协调器
3. 单元测试和基础集成测试

### Phase 2：CLI 与 Web UI 接口 (2天)
1. 扩展 `ariadne memory` CLI 命令
2. 实现 Web UI API 端点
3. 前端界面（监控状态面板、手动触发控件）

### Phase 3：集成与优化 (1-2天)
1. 与现有 Session Memory 系统集成
2. 配置持久化和错误恢复
3. 性能优化和压力测试

### Phase 4：文档与发布 (1天)
1. 更新 README、使用指南、变更日志
2. 推送到 GitHub 仓库
3. 创建发布版本

---

## 10. 风险与缓解

### 10.1 技术风险

- **文件锁冲突**：Windows 上 ChromaDB 文件锁可能阻碍文件删除/移动。缓解：使用 `MemoryManager` 的 `close_all_connections()` 和延迟重试。
- **监控遗漏**：Watchdog 在某些系统上可能不可靠。缓解：提供定期全量扫描作为后备。
- **解析兼容性**：外部记忆文件格式可能变化。缓解：提供灵活的解析器，支持用户自定义解析规则。

### 10.2 用户体验风险

- **资源占用**：实时监控可能消耗系统资源。缓解：提供资源限制配置，允许用户暂停监控。
- **误处理**：可能摄入用户不希望向量化的文件。缓解：提供排除模式、白名单/黑名单功能。

---

## 11. 后续演进

### 11.1 短期增强

- **实时搜索索引**：新文档摄入后立即更新 BM25 索引
- **跨集合联合搜索**：同时搜索 Session Observations 和外部记忆
- **智能分类**：自动将记忆分类到不同集合（如项目、日期、主题）

### 11.2 长期愿景

- **分布式监控**：监控网络存储、云同步文件夹（如 Dropbox、OneDrive）
- **智能摘要**：自动为摄入的记忆生成摘要
- **知识图谱自动丰富**：实时提取实体和关系，更新知识图谱

---

**文档版本**: 1.0  
**最后更新**: 2026-04-28  
**下一步**: 开始 Phase 1 核心模块实现