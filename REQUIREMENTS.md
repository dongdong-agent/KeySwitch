# API Key 切换器（KeySwitch）需求文档

> 项目位置：`L:\00-projects\apikey-switcher`
> 记录时间：2026-08-17
> 状态：开发中

## 一、背景与痛点

东哥有多个 AI API 渠道，各自有**用量限额**，且多个软件共用这些渠道：

| 渠道 | key 数量 | 限额特点 |
|---|---|---|
| opencode-go | 3 个（sk-xxx / sk-xxx / 第3个） | **5小时滚动限额**（如 DeepSeek V4 Flash 31,650 次）、周限额、月限额；高峰几小时就烧完 |
| DeepSeek 官方 | 1 个（sk-xxx，当前余额 ¥31.77） | 按余额扣费，可查询余额 |

痛点：**一个 key 用量耗尽时，各软件（pi / Hermes / DSH / OpenChatCut / OneWork / WorkBuddy）还在继续用这个 key → 报错、断流**。目前只能手动一个个改，非常麻烦。

## 二、目标

做一个**托盘小工具（exe）**：

1. **一键切换**：点击托盘菜单/按钮，把当前激活的 key 同步写入所有目标软件，切换即生效
2. **自动切换**：定时检测当前激活 key 的用量，**检测到用量耗尽（或达到阈值）→ 自动切换到下一个可用 key**
3. **用量可视化**：显示各 key 的用量状态（opencode-go：rolling/weekly/monthly 百分比；DeepSeek：余额）
4. **手动切换**：托盘菜单里点选任意 key 立即切换
5. **可扩展**：方便添加新厂商（如 Kimi、GLM、OpenRouter 等）和新目标软件

## 三、覆盖的目标软件（key 写入位置）

| 软件 | 存储位置 | 适配方式 |
|---|---|---|
| pi 工具 | `~/.pi/agent/auth.json` | 写 JSON（`opencode-go.key`） |
| Hermes Agent | Windows 用户环境变量 `OPENCODE_GO_API_KEY` | 写注册表 User 环境变量 |
| DeepSeek Harness (DSH) | 环境变量 `OPENCODE_GO_API_KEY`（与 Hermes 同源） | 随 Hermes 自动生效 |
| OpenChatCut | `~/AppData/Roaming/OpenChatCut/.env.local` | 写 `LLM_DEEPSEEK_API_KEY` 等 |
| WorkBuddy | `~/.workbuddy/models.json` | 写 `apiKey` 字段 |
| OneWork | 待确认（可能环境变量/独立配置） | 可扩展 |

## 四、用量检测接口（已实测）

### opencode-go
```
GET https://opencode.ai/zen/go/v1/usage
Authorization: Bearer <key>
```
返回：
```json
{"usage": {"rolling": {"status":"ok","percent":57,"resetsAt":"..."},
           "weekly":  {"status":"ok","percent":63,"resetsAt":"..."},
           "monthly": {"status":"ok","percent":33,"resetsAt":"..."}}}
```
- `percent`：已用百分比；`status`：`ok` 正常（耗尽时变为其他值）
- **判定规则**：`status != "ok"` 或 `percent >= 阈值（默认 90%）` → 判定该 key 用量告急，触发切换

### DeepSeek 官方
```
GET https://api.deepseek.com/user/balance
Authorization: Bearer <key>
```
返回：
```json
{"is_available": true, "balance_infos": [{"currency":"CNY","total_balance":"31.77",...}]}
```
- **判定规则**：`total_balance < 阈值（默认 ¥5）` → 判定告急

## 五、功能清单

### v1.0（第一版）
- [x] 配置中心：key 池（按 provider 分组）+ 目标软件列表（config.yaml 可编辑）
- [ ] 切换引擎：`set_active(provider, key_id)` → 写入所有目标适配器
- [ ] 适配器：pi / Hermes环境变量 / OpenChatCut / WorkBuddy
- [ ] 用量检测：opencode-go usage + DeepSeek balance
- [ ] 托盘 UI：显示各 key 用量 + 手动切换 + 自动切换开关 + 状态提示
- [ ] 打包 exe（PyInstaller + pystray，与 hiapi 代理同方案）

### v1.1（后续）
- [ ] 自动切换定时器（每 N 分钟检测，耗尽自动切）
- [ ] 切换历史/日志
- [ ] OneWork 适配
- [ ] 其他厂商接入模板（Kimi/GLM/OpenRouter…）

## 六、已知限制（诚实说明）

1. **运行中进程不感知环境变量变更**：Hermes/DSH 已在运行的进程仍用旧 key，需重启对应软件才生效（工具会提示"哪些软件需重启"）
2. **opencode-go 超限兜底**：官方支持「Use balance」自动转 Zen 余额续跑——如果开了这个，耗尽不一定报错而是静默扣 Zen 余额，检测到 percent 接近 100% 时切换仍是最优策略
3. 用量检测请求本身消耗极小（usage 端点是否计费待观察，默认按不计费处理）
