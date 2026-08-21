# API Key 切换器 - 开发计划

> 2026-08-17 制定。开发语言：Python（pystray 托盘 + PyInstaller 打包 exe，与 hiapi 代理同方案已验证）。

## 架构

```
apikey-switcher/
├── REQUIREMENTS.md / PLAN.md     # 需求与计划
├── config/
│   └── config.yaml               # ★配置中心：providers(key池) + targets(软件) + 阈值
├── keyhub.py                     # 核心引擎
│   ├── load_config()             #   读配置
│   ├── status_all()              #   查所有 key 用量（opencode-go usage / deepseek balance）
│   ├── set_active(provider, key) #   切换：写所有 target 适配器
│   ├── auto_check()              #   自动检测：用量告急 → 切下一个
│   └── next_key(provider)        #   轮询选择下一个可用 key
├── adapters/
│   ├── base.py                   # 适配器基类（name / write / read / restart_hint）
│   ├── pi.py                     #   ~/.pi/agent/auth.json
│   ├── env_var.py                #   用户环境变量 OPENCODE_GO_API_KEY（Hermes+DSH）
│   ├── openchatcut.py            #   ~/AppData/Roaming/OpenChatCut/.env.local
│   └── workbuddy.py              #   ~/.workbuddy/models.json
├── tray_app.py                   # 托盘 UI（菜单：状态/切换/自动开关/退出）
└── build.bat                     # 打包 exe 脚本
```

## 阶段

### 阶段 1：骨架与配置（0.5 天）
1. config.yaml：opencode-go ×3 key + deepseek ×1 key；targets：pi/env_var/openchatcut/workbuddy；阈值（opencode 90%、deepseek ¥5）
2. adapters/base.py + 四个适配器（读/写各自位置，带备份）
3. keyhub.py：load_config / set_active（全目标写入，返回每目标结果）

### 阶段 2：用量检测（0.5 天）
4. status_all：调 opencode-go /v1/usage（3 个 key）+ deepseek /user/balance
5. 判定：status != ok 或 percent ≥ 阈值 → 告急
6. 自动切换：auto_check 定时（默认每 10 分钟），告急 → next_key → set_active → 托盘通知

### 阶段 3：托盘 UI + 打包（0.5 天）
7. tray_app.py：托盘图标 + 菜单（当前激活/各 key 用量/切换子菜单/自动开关/打开日志/退出）
8. 切换后提示"以下软件需重启：Hermes/DSH"
9. PyInstaller 打包 exe（--onefile --noconsole），.env 方案同样适用
10. 开机自启注册 + 桌面快捷方式

### 阶段 4：验证（0.5 天）
11. 实测：切换 opencode-go key → 验证 pi/Hermes 环境变量/OpenChatCut 文件同步更新
12. 实测：usage 检测真实数据展示
13. 实测：自动切换模拟（把阈值临时设 1% 触发）

## 技术要点
- 环境变量切换：PowerShell `[Environment]::SetEnvironmentVariable(name, value, 'User')`
- 文件写入前一律备份（.bak-时间戳）
- 每个适配器实现 `restart_hint()` 返回哪些软件需要重启
- 与 hiapi 代理不冲突（不同端口/不同功能），可各自独立运行
