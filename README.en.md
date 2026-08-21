# KeySwitch 🔑

> **API Key Manager** — assign a Provider's Key to each app independently, and auto-switch by priority when usage runs out.
> Built end-to-end with **Pi (AI coding assistant) + DeepSeek V4 Flash**.

🌐 Languages: [简体中文](README.md) · **English** · [Français](README.fr.md) · [한국어](README.ko.md)

---

## What is this

KeySwitch solves a pain point: you have multiple API Keys across multiple AI providers, used by different apps (Pi, Codex, OpenChatCut, WorkBuddy, etc.). When a Key's quota runs out, you normally have to edit each app's config by hand.

KeySwitch automates it:

- **Per-app configuration** of which Provider and which Key to use;
- **Background periodic checks** on the in-use Key's usage, auto-switching to the next available Key when the threshold is hit;
- When a Key is switched, **all apps using it are switched together** — no need to edit one by one.

This is the Rust / Tauri 2 rewrite (replacing the Python version at `L:\00-projects\apikey-switcher`).

---

## ✨ Features

- **Left nav + right panel** (OneWork style, purple theme): Overview / Key Matrix / Providers / Key Pool / Apps / Settings
- **Per-app mapping**: an app × Provider table, each cell has its own Key dropdown. "Save & Apply" only writes changed cells (auto-backup before writing)
- **Smart switching**: a background timer checks in-use Key usage, auto-switches to the highest-priority available Key at the threshold (default 100%), switching all apps that use it
  - **Three-dimension check**: rolling / weekly / monthly — **any** dimension hitting the threshold marks the Key exhausted
  - **Cross-provider fallback**: when the same Provider has no available Key, fall back to other Providers in `prefer_providers` order (e.g. opencode-go first, DeepSeek as backup)
  - **Query-failure protection**: Keys whose usage query failed (403/network) are excluded from switch candidates; if the in-use Key fails to query, it switches to a Key that was **successfully queried this round** (same Provider first, otherwise cross-Provider), and only stays put when no usable target exists at all
- **Priority ordering**: reorder Keys in the Key Pool with ↑↓ (list order = priority)
- **Self-service management**: add/delete Providers, API Keys, and apps directly in the UI
- **Key editing**: change Provider / id / value / note / promo link / reward; cross-Provider moves auto-sync app mappings
- **ID masking**: emails and similar IDs display as `first4***@domain` outside edit mode; full value shown while editing
- **Usage visualization**: the Overview card shows rolling/weekly/monthly progress bars plus per-dimension reset countdowns (`resets in Xd Xh`)
- **System tray**: left-click / menu opens the main window; the menu shows a usage snapshot + smart-switch status; closing the window hides to tray (doesn't quit)
- **Usage detection**: opencode-go `/usage` (percent), DeepSeek `/user/balance` (balance)

---

## 📦 Installation

Download the release installer (Windows):

| Format | File | Notes |
|---|---|---|
| NSIS installer | `KeySwitch_0.3.1_x64-setup.exe` | Double-click to install, includes uninstaller |
| MSI package | `KeySwitch_0.3.1_x64_en-US.msi` | For enterprise deployment |

After installation it stays resident in the system tray.

---

## 🚀 Quick start

> For first-time use, follow this order — about 5 minutes to set up.

1. **(Optional) Migrate from the Python version**: `python tools/migrate_config.py` imports the old config in one shot.
2. **Add a Provider**: go to the "Providers" page → fill in name, `base_url`, and usage type (`percent` for percentage / `balance` for balance).
3. **Add Keys**: go to the "Key Pool" page → fill in id, Key value, optional note / promo link / reward; reorder priority with ↑↓.
4. **Add apps**: go to the "Apps" page → pick an adapter → fill in params → choose which Key each Provider uses for this app.
5. **Save & Apply**: go to the "Key Matrix" page to review the app × Provider matrix → click "Save & Apply" (only changed cells are written, with automatic backup).
6. **Enable smart switching**: go to the "Overview" page → set threshold / check interval / preferred Provider order → enable.

After that, the tray-resident background checker takes over. Note: **the affected app must be restarted** after a switch to pick up the new Key (see Gotchas below).

---

## 🔌 Supported adapters (8)

KeySwitch uses "adapters" to write Keys back to each app's real config location:

| Adapter | Target app / location | Required params |
|---|---|---|
| `pi` | Pi tool (`~/.pi/agent/auth.json`) | none |
| `env_var` | Windows user environment variable | `env` (variable name, default `OPENCODE_GO_API_KEY`) |
| `openchatcut` | OpenChatCut (`.env.local`) | none |
| `workbuddy` | WorkBuddy (`models.json`) | none |
| `codex` | Codex (codex-router secret file) | none |
| `file_json` | any JSON config file | `path` + `key_path` (dot path, e.g. `opencode-go.key`) |
| `file_env` | any `KEY=VALUE` file (.env-like) | `path` + `key_name` (default `API_KEY`) |
| `file_regex` | regex replacement in any file | `path` + `pattern` (with 1 capture group) + `replacement` (default `\1{key}\2`) |

---

## 🔄 Smart-switch mechanism

- **Trigger**: the timer ticks every 30 s, and decides whether to run based on `interval_min` (default 5 min). An in-use Key is considered exhausted when **any** of rolling/weekly/monthly usage ≥ `trigger_percent` (default 100%).
- **Switch target**: within the same Provider, pick the first available Key by Key Pool priority (list order); if none, fall back across Providers in `prefer_providers` order.
- **Consistency**: when a Key is switched, all apps whose `mapping` references it are switched together.
- **False-switch prevention**: Keys whose usage query failed (403 / network error) are always excluded from switch candidates (avoid switching to a dead Key); if the in-use Key fails to query, it switches to a Key that was **successfully queried this round** (same Provider first, otherwise cross-Provider such as DeepSeek), and only stays put when no usable target exists at all.
- **Logging**: each auto-check appends a line to `%APPDATA%\KeySwitch\auto-switch.log`, so you can confirm the timer is running.

---

## ⚙️ Configuration

- Path: `%APPDATA%\KeySwitch\config.toml` (auto-written by the UI; you can also edit it by hand)
- Key sections:

```toml
[auto_switch]
enabled = true          # enable smart switching
interval_min = 5        # check interval (minutes)
trigger_percent = 100   # trigger threshold (%)
prefer_providers = ["opencode-go", "deepseek"]  # cross-provider fallback order (optional)

[providers.opencode-go]
base_url = "https://api.opencode.ai"
usage_type = "percent"  # percent | balance
```

- Optional fields per Key: `note`, `promo_url`, `reward`.
- Optional fields per app (`targets`): `label`, `adapter`, adapter params (`env`/`path`/`key_path`/`key_name`/`pattern`/`replacement`), `mapping`.

---

## 🛠 Tech stack & how it was built

| Layer | Tech |
|---|---|
| Frontend | React 18 + TypeScript + Vite (`src/`) |
| Backend | Rust + Tauri 2 (`src-tauri/`) |
| Config | TOML (`%APPDATA%\KeySwitch\config.toml`) |

> **Built with**: this project was developed end-to-end with **Pi (AI coding assistant) + DeepSeek V4 Flash**, using a "first principles + adversarial review" engineering discipline at every layer.

---

## 🧪 Development & build

```bash
# install dependencies
npm install
# frontend dev (hot reload)
npm run tauri dev
# frontend type check
npx tsc --noEmit
# backend build + unit tests
cd src-tauri && cargo build && cargo test
# package (NSIS / MSI)
npx tauri build
```

Installer output:

- `src-tauri\target\release\bundle\nsis\KeySwitch_0.3.1_x64-setup.exe`
- `src-tauri\target\release\bundle\msi\KeySwitch_0.3.1_x64_en-US.msi`

> The app icon source is `app-icon.svg` in the repo root (gold key on purple). After editing, run `npx tauri icon app-icon.svg` to regenerate all platform icons.

---

## ⚠️ Gotchas (lessons learned)

1. **New opencode-go keys need China-hosted model opt-in**: some new accounts get `403 RegionError` when calling deepseek-v4-flash — open the workspace link in the error (`opencode.ai/workspace/<id>/go`) and accept it in the browser.
2. **Apps must be restarted after a switch**: KeySwitch edits config files / user environment variables; **already-running processes** (PI / DSH / apps) keep the old Key they loaded at startup — restart them to pick up the new Key.
3. **Tauri argument naming**: `invoke` params use camelCase (backend `key_id` ↔ frontend `keyId`); **command return fields are snake_case** (frontend must use `weekly_reset`, not `weeklyReset`) — the two directions are opposite, don't mix them up.
4. **Usage API may disagree with real limits**: opencode-go's `/usage` percentage doesn't guarantee usability (may return 429/403) and is intermittently blocked by Cloudflare; KeySwitch excludes Keys whose query failed this round (403/network) from switch candidates, and when the in-use Key fails to query it switches to a Key that was successfully queried (same Provider first, otherwise cross-Provider), staying put only when no usable target exists.
5. **Apps storing config in WebView storage (e.g. DSH)**: provider/key live in an internal leveldb and can't be edited as files — add them from within the app's UI instead.

---

## 📄 License

[MIT](LICENSE) © 2026 DongDong

## 🔗 Repository

GitHub: [dongdong-agent/KeySwitch](https://github.com/dongdong-agent/KeySwitch) (main branch)
