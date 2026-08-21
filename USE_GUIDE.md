# KeySwitch 使用指南（v2）

> API Key 管理器：**每个软件（应用）可以独立选择不同 Provider 的不同 Key**，一个界面全部管好。
> 数据存在 `config/config.yaml`（与 exe 同目录 `config\config.yaml`），改界面自动写文件，也可手改。

---

## 一、界面速览

```
┌─ 管理：➕Provider ➕API Key ➕应用 ➖删除 ❓使用说明   ← 添加/删除入口
├─ Key 用量状态（各 key 实时用量/余额，可刷新）
├─ 软件 × Provider 表格
│     软件          当前生效key      opencode-go      deepseek
│     pi 工具       opencode-3      [opencode-1▾]    [不使用▾]
│     Hermes+DSH    opencode-1      [opencode-2▾]    [不使用▾]
│     ...                           每格独立下拉
└─ 💾保存并应用  🔄刷新实际状态  📂打开配置目录  📄打开日志
```

**基本流程**：每个格子下拉选 key → 点「💾 保存并应用」→ 程序把选择写入各软件的真实配置（自动备份）→ 提示哪些软件需重启。

---

## 二、添加 Provider（新渠道，如 Kimi / GLM / OpenRouter）

**界面方式**：点「➕ Provider」→ 填：

| 字段 | 说明 |
|---|---|
| Provider 标识 | 英文小写，如 `kimi`、`glm`、`openrouter` |
| Base URL | API 地址，如 `https://api.kimi.com/v1`（填到 /v1 级，按厂商文档） |
| 用量类型 | `percent`（查 `/usage` 返回百分比限额）或 `balance`（查 `/user/balance` 返回余额） |
| 告急阈值 | percent 填 0-100（默认 90）；balance 填金额下限（默认 5） |

添加后点「➕ API Key」给这个 Provider 填 key。

**配置文件方式**（等价）：
```yaml
providers:
  kimi:
    base_url: https://api.kimi.com/v1
    usage_type: percent        # 或 balance
    keys:
    - id: kimi-1
      key: sk-xxxxxxxx
      note: 备注
thresholds:
  kimi:
    percent: 90                # balance 型则写 balance_min: 5
```

> ⚠️ 用量检测要求厂商有 `/usage`（percent 型）或 `/user/balance`（balance 型）接口；
> 都没有的 Provider 仍可管理 key（用量区显示「查询失败」，不影响切换功能）。

---

## 三、添加 API Key

点「➕ API Key」→ 选 Provider、填标识（自动建议 `provider-N`）、粘贴 key 值、写备注。
删除：点「➖ 删除」→ 选 Provider 和 Key → 删除（会清掉引用它的应用映射）。

---

## 四、添加应用（把某个软件的 key 纳入管理）

点「➕ 应用」→ 填标识、显示名，**选适配器类型**（决定 key 写到该软件配置的什么位置）：

| 适配器 | 参数 | 说明 / 示例 |
|---|---|---|
| `pi` | 无 | 写 `~/.pi/agent/auth.json` 的 `opencode-go.key` |
| `env_var` | `env` 环境变量名 | Windows 用户环境变量（Hermes 用 `OPENCODE_GO_API_KEY`） |
| `openchatcut` | 无 | 写 `~/AppData/Roaming/OpenChatCut/.env.local` 的 `LLM_DEEPSEEK_*` |
| `workbuddy` | 无 | 写 `~/.workbuddy/models.json` 的 `apiKey` |
| `codex` | 无 | 写 `~/.codex/codex-router/opencode-go-api-key.secret` |
| `file_json` | `path` + `key_path` | 任意 JSON 配置文件；`key_path` 用点路径，如 `opencode-go.key`、`servers[0].apiKey` |
| `file_env` | `path` + `key_name` | 任意 `KEY=VALUE` 文件（.env 类） |
| `file_regex` | `path` + `pattern` | 正则替换兜底；`pattern` 必须含 1 个捕获组（读取用），如 `("apiKey":")([^"]+)(")` 写时自动替换 |

**示例 1**：把某桌面软件（配置在 `C:\App\settings.json`，key 在 `{"openai":{"key":"..."}}`）接入：
```
适配器: file_json
path: C:\App\settings.json
key_path: openai.key
```

**示例 2**：某 CLI 工具读环境变量 `MY_TOOL_API_KEY`：
```
适配器: env_var
env: MY_TOOL_API_KEY
```

**示例 3**：某工具配置是 .env 格式：
```
适配器: file_env
path: C:\App\.env
key_name: API_KEY
```

选完适配器后，下面勾选该应用**用哪些 Provider 的哪个 Key**（每个 Provider 一行下拉）。

**添加后**：新应用出现在表格 → 下拉选好 key → 「保存并应用」即写入其配置。
**删除应用**：「➖ 删除」→ 删除应用。

---

## 五、常见流程

1. **一个 key 分给多个软件**：表格里多行选同一个 key → 保存 → 各软件写入同一 key。
2. **同一软件不同 Provider 分开**：如 OpenChatCut 的 LLM 用 opencode-go 的 key、生图走 IMAGE_*（OpenChatCut 适配器已内置映射）。
3. **换 key**：只改某行的下拉 → 保存 → 只有该软件变，其他不动。
4. **key 告急**：用量区红色 = 状态异常/告急 → 在该软件行换一个 key → 保存。

---

## 六、智能切换（用量耗尽自动换 key）

「总览」页的⚡智能切换卡片：

| 设置 | 说明 |
|---|---|
| 启用开关 | 开 = 后台定时检测在用 key，耗尽自动切换 |
| 触发阈值(%) | 用量达到该百分比判定「耗尽」（默认 100，可调低提前切） |
| 检测间隔(分钟) | 每多少分钟检测一次（默认 5） |

**优先级**：「🔐 Key 池」页用 ↑↓ 按钮排序——**列表越靠上越优先**，智能切换时优先选用排在最前面的可用 key（同一 Provider 内比较）。

**切换规则**：
- 某个在用 key 达到阈值 → 自动切到该 Provider 优先级最高的可用 key
- **所有正在用这个 key 的软件会一起切换**（如 Hermes 和 OpenChatCut 都用 opencode-1，opencode-1 耗尽时两个一起切走）
- 切换后提示/记录「哪些软件切到哪个 key」，相关软件**需重启生效**
- 无可用 key 时保持现状并提示；不自动切回（避免来回抖），想用回原 key 手动选即可
- 切换动作记入 `keyswitch.log`，托盘菜单显示智能切换开关状态

---

## 六、特殊格式软件（需要写代码时）

90% 的软件用上表通用适配器即可。若某软件配置格式特殊（嵌套结构、多键联动、二进制等），
在项目 `adapters/` 下新建一个适配器（参照 `adapters/base.py`，实现 `write_key` / `read_key` / `restart_hint`），
然后在 `keyhub.py` 的 `ADAPTER_FACTORY` 注册一行，重打包即可。已有示例：`adapters/openchatcut.py`（多键联动）。

---

## 七、托盘

- 关闭主窗口 = 最小化到托盘（程序不退出）
- 双击托盘图标 = 打开主窗口
- 托盘右键菜单：打开主窗口 / 各 key 用量 / 刷新 / 退出
- 开机自启：KeySwitch 目前不默认自启，需要的话把它加进「启动文件夹」或注册表 Run 键
