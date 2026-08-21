# KeySwitch (Rust 版)

> API Key 管理器 —— 每个软件独立选择 Provider 的 Key，用量耗尽智能切换（按优先级）。
> **Rust / Tauri 2 / React + TypeScript** 重构版（替代 Python 版 `L:\00-projects\apikey-switcher`）。

## 功能

- **左侧导航 + 右侧操作区**（OneWork 风格，紫主题）：总览 / Key 配置 / Provider / Key 池 / 应用 / 设置
- **每软件独立映射**：软件 × Provider 表格，每格独立下拉选 Key，「保存并应用」只写变化的项（先备份）
- **智能切换**：后台定时检测在用 Key 用量，达到阈值（默认 100%）自动切到优先级最高的可用 Key，所有用它的软件一起切
  - **三维度判定**：滚动 / 周 / 月**任一**达阈值即判定耗尽（用户要求）
  - **跨 Provider 兜底**：同 Provider 无可用 key 时，按 `prefer_providers` 偏好顺序切到其它 Provider（如 opencode-go 优先、DeepSeek 兜底）
  - **查询失败保护**：用量查询失败（403/网络）不触发切换、回退最近一次成功数据，避免误切
- **优先级排序**：Key 池 ↑↓ 调整（列表顺序即优先级）
- **自助管理**：界面直接添加/删除 Provider、API Key、应用（8 种适配器：pi / env_var / openchatcut / workbuddy / codex / file_json / file_env / file_regex）
- **Key 编辑**：可改 Provider / 标识 / 值 / 备注 / 推广链接 / 奖励额度；跨 Provider 迁移自动同步应用映射
- **标识脱敏**：邮箱等标识在非编辑态显示为 `前4字符***@域名`，编辑时完整显示
- **用量可视化**：总览卡片显示滚动/每周/每月三条进度条 + 各维度重置倒计时（`重置于 X 天 X 时`）
- **系统托盘**：左键单击/菜单打开主窗口，菜单显示用量快照 + 智能切换状态；关闭窗口 = 隐藏到托盘
- **用量检测**：opencode-go `/usage`（percent）、DeepSeek `/user/balance`（balance）

## 技术栈

| 层 | 技术 |
|---|---|
| 前端 | React 18 + TypeScript + Vite（`src/`） |
| 后端 | Rust + Tauri 2（`src-tauri/`） |
| 配置 | TOML（`%APPDATA%\KeySwitch\config.toml`） |

## 构建与运行

```bash
# 依赖安装
npm install
# 前端开发（热重载）
npm run tauri dev
# 前端类型检查
npx tsc --noEmit
# 后端编译 + 单测
cd src-tauri && cargo build && cargo test
# 打包（NSIS / MSI）
npx tauri build
```

安装包输出：`src-tauri\target\release\bundle\nsis\KeySwitch_0.3.1_x64-setup.exe`

## 配置说明

- 配置文件：`%APPDATA%\KeySwitch\config.toml`（界面操作自动写回，也可手改）
- `auto_switch` 段：`enabled` / `interval_min` / `trigger_percent` / `prefer_providers`
- 每 Provider 可配 `usage_type`：`percent`（查 /usage 百分比）或 `balance`（查 /user/balance 余额）
- 每 Key 可选字段：`note`（备注）、`promo_url`（推广链接）、`reward`（奖励额度）

## 常见坑（血泪教训）

1. **opencode-go 新 key 需中国托管模型 opt-in**：部分新账户调用 deepseek-v4-flash 返回 `403 RegionError`，需打开报错里的 workspace 链接在网页同意（`opencode.ai/workspace/<id>/go`）。
2. **切换后应用需重启才生效**：KeySwitch 改的是配置文件/用户环境变量；**已运行的进程**（PI / DSH / 各软件）仍用启动时的旧 key，重启对应进程才用新 key。
3. **Tauri 参数命名**：`invoke` 入参用 camelCase（后端 `key_id` ↔ 前端 `keyId`）；**命令返回值字段是 snake_case**（前端必须用 `weekly_reset` 而非 `weeklyReset`），两者方向相反，别混。
4. **用量接口与真实限制可能不一致**：opencode-go 的 `/usage` 返回百分比不代表一定能用（可能 429/403），且被 Cloudflare 间歇性拦截；KeySwitch 已做"查询失败不切换 + 回退最近数据"保护。
5. **WebView 存储的应用（如 DSH）** provider/key 存在内部 leveldb，无法直接改文件，需在应用界面添加。

## 仓库

GitHub: `https://github.com/dongdong-agent/KeySwitch`（main 分支）
