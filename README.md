# KeySwitch 🔑

> **API Key 管理器** —— 给每个软件独立选择 Provider 的 Key，用量耗尽时按优先级智能切换。
> 由 **Pi（AI 编程助手）+ DeepSeek V4 Flash** 端到端开发。

🌐 语言 / Languages：**简体中文** · [English](README.en.md)

---

## 这是什么

KeySwitch 解决一个痛点：你有多个 AI 服务商（Provider）的多个 API Key，分别给不同的软件用（Pi、Codex、OpenChatCut、WorkBuddy 等），某个 Key 的额度用完时，往往要手动挨个改配置。

KeySwitch 把这件事自动化了：

- **每个软件独立配置** 用哪个 Provider、哪个 Key；
- **后台定时检测** 在用 Key 的用量，接近/达到阈值自动切到下一个可用的 Key；
- 一个 Key 切换，**所有用它的软件一起切**，不用逐个改。

Rust / Tauri 2 重构版（替代 Python 版 `L:\00-projects\apikey-switcher`）。

---

## ✨ 功能特性

- **左侧导航 + 右侧操作区**（OneWork 风格，紫主题）：总览 / Key 配置 / Provider / Key 池 / 应用 / 设置
- **每软件独立映射**：软件 × Provider 表格，每格独立下拉选 Key，「保存并应用」只写变化的项（写前自动备份原文件）
- **智能切换**：后台定时检测在用 Key 用量，达到阈值（默认 100%）自动切到优先级最高的可用 Key，所有用它的软件一起切
  - **三维度判定**：滚动 / 周 / 月**任一**达阈值即判定耗尽
  - **跨 Provider 兜底**：同 Provider 无可用 key 时，按 `prefer_providers` 偏好顺序切到其它 Provider（如 opencode-go 优先、DeepSeek 兜底）
  - **查询失败保护**：用量查询失败（403/网络）不触发切换、回退最近一次成功数据，避免误切
- **优先级排序**：Key 池 ↑↓ 调整（列表顺序即优先级）
- **自助管理**：界面直接添加/删除 Provider、API Key、应用
- **Key 编辑**：可改 Provider / 标识 / 值 / 备注 / 推广链接 / 奖励额度；跨 Provider 迁移自动同步应用映射
- **标识脱敏**：邮箱等标识在非编辑态显示为 `前4字符***@域名`，编辑时完整显示
- **用量可视化**：总览卡片显示滚动/每周/每月三条进度条 + 各维度重置倒计时（`重置于 X 天 X 时`）
- **系统托盘**：左键单击/菜单打开主窗口，菜单显示用量快照 + 智能切换状态；关闭窗口 = 隐藏到托盘（不退出）
- **用量检测**：opencode-go `/usage`（percent）、DeepSeek `/user/balance`（balance）

---

## 📦 安装

直接下载 Release 安装包（Windows）：

| 格式 | 文件 | 说明 |
|---|---|---|
| NSIS 安装器 | `KeySwitch_0.3.1_x64-setup.exe` | 双击安装，含卸载程序 |
| MSI 安装包 | `KeySwitch_0.3.1_x64_en-US.msi` | 企业批量部署用 |

安装后会在系统托盘常驻运行。

---

## 🚀 快速上手

> 首次使用建议按下面顺序走一遍，5 分钟即可配好。

1. **（可选）从 Python 版迁移**：`python tools/migrate_config.py`，一键把旧配置导入。
2. **添加 Provider**：进入「Provider」页 → 填名称、`base_url`、用量类型（`percent` 查百分比 / `balance` 查余额）。
3. **添加 Key**：进入「Key 池」页 → 填标识、Key 值，可选备注 / 推广链接 / 奖励额度；用 ↑↓ 调整优先级。
4. **添加应用**：进入「应用」页 → 选适配器 → 填参数 → 指定该应用各 Provider 用哪个 Key。
5. **保存并应用**：进入「Key 配置」页核对 软件 × Provider 矩阵 → 点「保存并应用」（只写变化项，自动备份）。
6. **开启智能切换**：进入「总览」页 → 设阈值 / 检测间隔 / 偏好 Provider 顺序 → 启用。

之后就交给托盘常驻的后台检测即可；切换后**相关软件需重启**才会用新 Key（见下方常见坑）。

---

## 🔌 支持的适配器（8 种）

KeySwitch 通过「适配器」把 Key 写回各软件的真实配置位置：

| 适配器 | 目标软件/位置 | 需要填的参数 |
|---|---|---|
| `pi` | Pi 工具（`~/.pi/agent/auth.json`） | 无 |
| `env_var` | Windows 用户环境变量 | `env`（变量名，默认 `OPENCODE_GO_API_KEY`）|
| `openchatcut` | OpenChatCut（`.env.local`）| 无 |
| `workbuddy` | WorkBuddy（`models.json`）| 无 |
| `codex` | Codex（codex-router secret 文件）| 无 |
| `file_json` | 任意 JSON 配置文件 | `path` + `key_path`（点路径，如 `opencode-go.key`）|
| `file_env` | 任意 `KEY=VALUE` 文件（.env 类）| `path` + `key_name`（默认 `API_KEY`）|
| `file_regex` | 任意文件正则替换 | `path` + `pattern`（含 1 个捕获组）+ `replacement`（默认 `\1{key}\2`）|

---

## 🔄 智能切换机制

- **触发条件**：定时器每 30 秒 tick 一次，按配置的 `interval_min`（默认 5 分钟）决定是否执行检测；在用 Key 的滚动/周/月**任一维度**用量 ≥ `trigger_percent`（默认 100%）即判定耗尽。
- **切换目标**：同 Provider 内按 Key 池优先级（列表顺序）找第一个可用 Key；找不到时按 `prefer_providers` 顺序跨 Provider 兜底。
- **一致性**：一个 Key 被切换后，所有 `mapping` 里用了它的软件一并切换。
- **防误切**：用量查询失败（403 / 网络异常）时**不切换**，并回退最近一次成功数据判定，避免因查询失败误切。
- **日志**：每次自动检测落一行到 `%APPDATA%\KeySwitch\auto-switch.log`，便于确认定时器在跑。

---

## ⚙️ 配置文件

- 路径：`%APPDATA%\KeySwitch\config.toml`（界面操作自动写回，也可手改）
- 关键段：

```toml
[auto_switch]
enabled = true          # 是否启用智能切换
interval_min = 5        # 检测间隔（分钟）
trigger_percent = 100   # 触发阈值（%）
prefer_providers = ["opencode-go", "deepseek"]  # 跨 Provider 兜底顺序（可选）

[providers.opencode-go]
base_url = "https://api.opencode.ai"
usage_type = "percent"  # percent | balance
```

- 每 Key 可选字段：`note`（备注）、`promo_url`（推广链接）、`reward`（奖励额度）。
- 每应用（`targets`）可选字段：`label`、`adapter`、适配器参数（`env`/`path`/`key_path`/`key_name`/`pattern`/`replacement`）、`mapping`。

---

## 🛠 技术栈 & 开发方式

| 层 | 技术 |
|---|---|
| 前端 | React 18 + TypeScript + Vite（`src/`）|
| 后端 | Rust + Tauri 2（`src-tauri/`）|
| 配置 | TOML（`%APPDATA%\KeySwitch\config.toml`）|

> **开发方式**：本项目由 **Pi（AI 编程助手）+ DeepSeek V4 Flash** 模型全程开发，采用「第一性原理 + 对抗式审查」的工程方法逐层实现与验证。

---

## 🧪 开发与构建

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

安装包输出：

- `src-tauri\target\release\bundle\nsis\KeySwitch_0.3.1_x64-setup.exe`
- `src-tauri\target\release\bundle\msi\KeySwitch_0.3.1_x64_en-US.msi`

> 应用图标源文件为根目录的 `app-icon.svg`（金色钥匙 + 紫底），修改后用 `npx tauri icon app-icon.svg` 重新生成全平台图标。

---

## ⚠️ 常见坑（血泪教训）

1. **opencode-go 新 key 需中国托管模型 opt-in**：部分新账户调用 deepseek-v4-flash 返回 `403 RegionError`，需打开报错里的 workspace 链接在网页同意（`opencode.ai/workspace/<id>/go`）。
2. **切换后应用需重启才生效**：KeySwitch 改的是配置文件/用户环境变量；**已运行的进程**（PI / DSH / 各软件）仍用启动时的旧 key，重启对应进程才用新 key。
3. **Tauri 参数命名**：`invoke` 入参用 camelCase（后端 `key_id` ↔ 前端 `keyId`）；**命令返回值字段是 snake_case**（前端必须用 `weekly_reset` 而非 `weeklyReset`），两者方向相反，别混。
4. **用量接口与真实限制可能不一致**：opencode-go 的 `/usage` 返回百分比不代表一定能用（可能 429/403），且被 Cloudflare 间歇性拦截；KeySwitch 已做"查询失败不切换 + 回退最近数据"保护。
5. **WebView 存储的应用（如 DSH）** provider/key 存在内部 leveldb，无法直接改文件，需在应用界面添加。

---

## 📄 许可证

[MIT](LICENSE) © 2026 DongDong

## 🔗 仓库

GitHub: [dongdong-agent/KeySwitch](https://github.com/dongdong-agent/KeySwitch)（main 分支）
