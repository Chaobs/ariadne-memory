# Ariadne Scripts

快捷启动脚本 — 双击即可运行对应功能，无需打开终端输入命令。

## Windows (.bat)

| Script | 功能 | 默认端口/地址 |
|--------|------|-------------|
| `ariadne-cli.bat` | 启动 CLI 交互界面 | — |
| `ariadne-gui.bat` | 启动 Tkinter GUI 原型（已弃用） | — |
| `ariadne-web.bat` | 启动 Web UI（推荐） | http://127.0.0.1:8770 |

### ariadne-web.bat（推荐）

```bash
ariadne-web.bat          # 默认端口 8770
ariadne-web.bat 8080     # 自定义端口
```

### ariadne-cli.bat

```bash
ariadne-cli.bat
```

### ariadne-gui.bat

```bash
ariadne-gui.bat
```

## Linux / macOS (.sh)

| Script | 功能 | 默认端口/地址 |
|--------|------|-------------|
| `ariadne-web.sh` | 启动 Web UI（推荐） | http://127.0.0.1:8770 |
| `ariadne-cli.sh` | 启动 CLI 交互界面 | — |

### ariadne-web.sh

```bash
# 添加执行权限
chmod +x ariadne-web.sh

# 基本用法
./ariadne-web.sh           # 默认端口 8770
./ariadne-web.sh 8080      # 自定义端口
./ariadne-web.sh --port 9000  # 长参数格式

# 开发模式（Vite 热重载 + FastAPI 后端）
./ariadne-web.sh --dev
./ariadne-web.sh -d        # 简写

# 查看帮助
./ariadne-web.sh --help
./ariadne-web.sh -h        # 简写
```

**开发模式说明**：使用 `--dev` 时，会同时启动：
- 前端 Vite 开发服务器（http://localhost:5173）
- 后端 FastAPI 服务器（http://127.0.0.1:8770）
- 两个服务会自动代理 `/api` 请求到后端

### ariadne-cli.sh

```bash
chmod +x ariadne-cli.sh
./ariadne-cli.sh
```

## 跨平台使用

如果需要同时在 Windows、Linux、macOS 上使用，可以将脚本放在项目根目录：

```bash
# Linux/macOS
./ariadne-web.sh

# Windows PowerShell
.\ariadne-web.bat

# 或直接用 Python
python -m ariadne.cli web run
```

## 注意事项

- 所有脚本需要在 Ariadne 安装目录下运行（`setup.py install` 或 `pip install .` 之后）
- **Windows 用户**：双击 `.bat` 文件即可
- **Linux/macOS 用户**：首次使用需添加执行权限 `chmod +x *.sh`
- Web UI 启动后会自动在浏览器中打开
- 关闭终端窗口即可停止服务器

## 前置依赖

### Python 包

```bash
pip install 'ariadne[web]'
```

### 前端依赖（仅开发模式）

```bash
cd ariadne/web/frontend
npm install
```

## 卸载脚本

直接删除 `.bat` / `.sh` 文件即可，不影响 Ariadne 核心功能。
