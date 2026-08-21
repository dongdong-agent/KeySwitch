# KeySwitch 桌面版（Python 版）

> **API Key 管理器** —— 给每个软件独立选择 Provider 的 Key，用量耗尽时按优先级智能切换。
> 本分支/目录是 **Python / tkinter 经典桌面版**；新版（Rust/Tauri 2 重构）见仓库 **main 分支**。

## 快速开始

```bash
# 1. 安装依赖
pip install pyyaml

# 2. 运行（首次自动生成空配置模板 config/config.yaml）
python tray_app.py        # 托盘版（推荐）
# 或
python gui_app.py         # 窗口版
```

在界面中添加 Provider / Key / 应用并配置映射，或运行 `python scripts/init_config.py` 从本机自动收集。

## 打包桌面安装程序

```bash
python -m PyInstaller KeySwitch.spec --noconfirm --distpath dist
# 产物：dist/KeySwitch.exe（单文件，Windows x64）
```

> 🔒 打包前请用**空模板**替换 `config/config.yaml`（见仓库内 `config.example.yaml`），
> 避免把真实 API Key 打进公开分发的安装包。

## 功能

- 左侧导航 + 右侧操作区（OneWork 风格，紫主题）：总览 / Key 配置 / Provider / Key 池 / 应用 / 设置
- **每软件独立映射**：软件 × Provider 表格，每格独立下拉选 Key，「保存并应用」只写变化的项
- **总览页手动切换**：每个 Key 卡片带「⚡ 使用此 key」按钮，一键把所有在用软件切到指定 Key（自动切换失败时的兜底）
- **智能切换**：后台定时检测在用 Key 用量，达到阈值自动切到优先级最高的可用 Key
- **系统托盘**：左键单击/菜单打开主窗口，关闭窗口隐藏到托盘
- 用量检测：opencode-go `/usage`（percent）、DeepSeek `/user/balance`（balance）

## 结构

| 文件 | 说明 |
| --- | --- |
| `gui_app.py` | 主窗口（tkinter） |
| `keyhub.py` | 核心引擎（配置/映射/用量/智能切换） |
| `tray_app.py` | 系统托盘入口 |
| `adapters/` | 各软件写入适配器（pi / env_var / openchatcut / workbuddy / codex / file_*) |
| `scripts/` | 初始化与配置迁移脚本 |
| `config.example.yaml` | 配置模板（不含真实 Key） |

## 许可证

[MIT](LICENSE) © 2026 DongDong
