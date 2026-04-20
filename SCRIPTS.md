# Ariadne Scripts

快捷启动脚本 — 双击即可运行对应功能，无需打开终端输入命令。

## Scripts

| Script | 功能 | 默认端口/地址 |
|--------|------|-------------|
| `ariadne-cli.bat` | 启动 CLI 交互界面 | — |
| `ariadne-gui.bat` | 启动 Tkinter GUI 原型 | — |
| `ariadne-web.bat` | 启动 Web UI | http://127.0.0.1:8770 |

## 使用方式

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

## 注意事项

- 所有脚本需要在 Ariadne 安装目录下运行（`setup.py install` 或 `pip install .` 之后）
- Windows 用户：双击 `.bat` 文件即可
- Web UI 启动后会自动在浏览器中打开
- 关闭终端窗口即可停止服务器

## 卸载脚本

直接删除 `.bat` 文件即可，不影响 Ariadne 核心功能。
