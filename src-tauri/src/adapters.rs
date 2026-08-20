//! 适配器：把 key 写入各软件的真实配置位置

use crate::models::{Config, Target};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::path::PathBuf;
use std::sync::{LazyLock, Mutex};
use std::time::{Duration, Instant};

#[derive(Serialize, Deserialize, Clone)]
pub struct WriteResult {
    pub ok: bool,
    pub msg: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub provider: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub target: Option<String>,
}

pub trait Adapter {
    fn write_key(&self, provider: &str, key: &str) -> WriteResult;
    fn read_key(&self, provider: &str) -> String;
    fn restart_hint(&self) -> Vec<String>;
}

// ---------- 工具 ----------

fn home() -> PathBuf {
    dirs::home_dir().unwrap_or_else(|| PathBuf::from("."))
}

/// 让子进程在后台静默运行、不弹出终端窗口。
/// release 版是 windows_subsystem = "windows"（无控制台），此时 spawn 控制台类程序
/// （如 powershell.exe）会被 Windows 强制新建一个黑色控制台窗口闪出——这里用
/// CREATE_NO_WINDOW 标志消除它，保存/读取配置都在后台完成。
#[cfg(target_os = "windows")]
fn no_window(cmd: &mut std::process::Command) -> &mut std::process::Command {
    use std::os::windows::process::CommandExt;
    cmd.creation_flags(0x0800_0000) // CREATE_NO_WINDOW
}
#[cfg(not(target_os = "windows"))]
fn no_window(cmd: &mut std::process::Command) -> &mut std::process::Command {
    cmd
}

fn backup(path: &std::path::Path) {
    if path.exists() {
        let ts = chrono_lite();
        let bak = path.with_extension(format!(
            "bak-{}",
            path.extension()
                .and_then(|e| e.to_str())
                .map(|_| "")
                .unwrap_or("")
        ));
        let _ = std::fs::copy(path, bak.with_file_name(format!(
            "{}",
            path.file_name().unwrap_or_default().to_string_lossy()
        ) + &format!(".bak-{ts}")));
    }
}

fn chrono_lite() -> String {
    // YYYYMMDDHHMMSS（不带外部 chrono 依赖）
    let now = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs();
    let days = now / 86400;
    let secs = now % 86400;
    let (h, m, s) = (secs / 3600, (secs % 3600) / 60, secs % 60);
    let (y, mo, d) = civil_from_days(days as i64);
    format!("{y:04}{mo:02}{d:02}{h:02}{m:02}{s:02}")
}

/// 从 UNIX 天数转公历（Howard Hinnant 算法）
fn civil_from_days(z: i64) -> (i64, u32, u32) {
    let z = z + 719468;
    let era = if z >= 0 { z } else { z - 146096 } / 146097;
    let doe = (z - era * 146097) as u64;
    let yoe = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365;
    let y = yoe as i64 + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = (doy - (153 * mp + 2) / 5 + 1) as u32;
    let m = if mp < 10 { mp + 3 } else { mp - 9 } as u32;
    (if m <= 2 { y + 1 } else { y }, m, d)
}

fn read_text(path: &std::path::Path) -> String {
    std::fs::read_to_string(path).unwrap_or_default()
}

fn write_text(path: &std::path::Path, text: &str) -> Result<(), String> {
    if let Some(p) = path.parent() {
        let _ = std::fs::create_dir_all(p);
    }
    std::fs::write(path, text).map_err(|e| e.to_string())
}

// ---------- pi 工具 ----------

pub struct PiAdapter;
impl Adapter for PiAdapter {
    fn write_key(&self, provider: &str, key: &str) -> WriteResult {
        let path = home().join(".pi/agent/auth.json");
        let mut d: serde_json::Value = if path.exists() {
            serde_json::from_str(&read_text(&path)).unwrap_or(serde_json::json!({}))
        } else {
            serde_json::json!({})
        };
        d[provider] = serde_json::json!({"type": "api_key", "key": key});
        backup(&path);
        match write_text(&path, &serde_json::to_string_pretty(&d).unwrap_or_default()) {
            Ok(_) => WriteResult { ok: true, msg: "pi auth.json 已更新".into(), provider: None, target: None },
            Err(e) => WriteResult { ok: false, msg: format!("pi 写入失败: {e}"), provider: None, target: None },
        }
    }
    fn read_key(&self, provider: &str) -> String {
        let path = home().join(".pi/agent/auth.json");
        if let Ok(d) = serde_json::from_str::<serde_json::Value>(&read_text(&path)) {
            d.get(provider)
                .and_then(|v| v.get("key"))
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string()
        } else {
            String::new()
        }
    }
    fn restart_hint(&self) -> Vec<String> {
        vec!["pi".into()]
    }
}

// ---------- Windows 用户环境变量 ----------

/// 用户环境变量读取缓存：一次 CU/总览刷新会对同一环境变量多次 read_key，
/// 每次都 spawn powershell.exe 开销很大。这里用短 TTL 缓存合并重复读取；
/// 写入（write_key）时会主动失效，保证保存后能读到新值，不影响一致性。
const ENV_READ_TTL: Duration = Duration::from_secs(1);
static ENV_CACHE: LazyLock<Mutex<HashMap<String, (Instant, String)>>> =
    LazyLock::new(|| Mutex::new(HashMap::new()));

fn read_env_cached(name: &str) -> String {
    if let Ok(c) = ENV_CACHE.lock() {
        if let Some((t, v)) = c.get(name) {
            if t.elapsed() < ENV_READ_TTL {
                return v.clone();
            }
        }
    }
    let val = read_env_powershell(name);
    if let Ok(mut c) = ENV_CACHE.lock() {
        c.insert(name.to_string(), (Instant::now(), val.clone()));
    }
    val
}

fn invalidate_env(name: &str) {
    if let Ok(mut c) = ENV_CACHE.lock() {
        c.remove(name);
    }
}

/// 真正读取用户级环境变量（spawn 一次 powershell）
fn read_env_powershell(name: &str) -> String {
    let ps = format!("[Environment]::GetEnvironmentVariable('{}','User')", name);
    let mut cmd = std::process::Command::new("powershell.exe");
    if let Ok(o) = no_window(&mut cmd)
        .args(["-NoProfile", "-Command", &ps])
        .output()
    {
        if o.status.success() {
            return String::from_utf8_lossy(&o.stdout).trim().to_string();
        }
    }
    String::new()
}

pub struct EnvVarAdapter {
    pub env_name: String,
    pub restart: Vec<String>,
}
impl Adapter for EnvVarAdapter {
    fn write_key(&self, _provider: &str, key: &str) -> WriteResult {
        let ps = format!(
            "[Environment]::SetEnvironmentVariable('{}','{}','User')",
            self.env_name, key
        );
        let mut cmd = std::process::Command::new("powershell.exe");
        let out = no_window(&mut cmd)
            .args(["-NoProfile", "-Command", &ps])
            .output();
        match out {
            Ok(o) if o.status.success() => {
                // 写成功后失效读取缓存，确保界面回读新值
                invalidate_env(&self.env_name);
                WriteResult {
                    ok: true,
                    msg: format!("环境变量 {} 已更新（需重启 Hermes/DSH 生效）", self.env_name),
                    provider: None,
                    target: None,
                }
            }
            Ok(o) => WriteResult {
                ok: false,
                msg: format!("环境变量设置失败: {}", String::from_utf8_lossy(&o.stderr)),
                provider: None,
                target: None,
            },
            Err(e) => WriteResult { ok: false, msg: format!("PowerShell 调用失败: {e}"), provider: None, target: None },
        }
    }
    fn read_key(&self, _provider: &str) -> String {
        read_env_cached(&self.env_name)
    }
    fn restart_hint(&self) -> Vec<String> {
        if self.restart.is_empty() {
            vec!["Hermes".into(), "DSH".into()]
        } else {
            self.restart.clone()
        }
    }
}

// ---------- OpenChatCut ----------

pub struct OpenChatCutAdapter;
impl Adapter for OpenChatCutAdapter {
    fn write_key(&self, provider: &str, key: &str) -> WriteResult {
        let (llm_provider, suffix, base) = match provider {
            "opencode-go" => ("deepseek", "DEEPSEEK", Some("https://opencode.ai/zen/go/v1")),
            "deepseek" => ("deepseek", "DEEPSEEK", None),
            _ => return WriteResult { ok: false, msg: format!("OpenChatCut 暂不支持 provider: {provider}"), provider: None, target: None },
        };
        let path = home().join("AppData/Roaming/OpenChatCut/.env.local");
        let mut lines: Vec<String> = if path.exists() {
            read_text(&path).lines().map(|l| l.to_string()).collect()
        } else {
            Vec::new()
        };
        let set = |lines: &mut Vec<String>, k: &str, v: &str| {
            if let Some(i) = lines.iter().position(|l| l.starts_with(&format!("{k}="))) {
                lines[i] = format!("{k}={v}");
            } else {
                lines.push(format!("{k}={v}"));
            }
        };
        set(&mut lines, "LLM_PROVIDER", llm_provider);
        set(&mut lines, &format!("LLM_{suffix}_API_KEY"), key);
        match base {
            Some(b) => set(&mut lines, &format!("LLM_{suffix}_BASE_URL"), b),
            None => {
                let key = format!("LLM_{suffix}_BASE_URL");
                lines.retain(|l| !l.starts_with(&format!("{key}=")));
            }
        }
        backup(&path);
        match write_text(&path, &(lines.join("\n") + "\n")) {
            Ok(_) => WriteResult { ok: true, msg: "OpenChatCut .env.local 已更新".into(), provider: None, target: None },
            Err(e) => WriteResult { ok: false, msg: format!("OpenChatCut 写入失败: {e}"), provider: None, target: None },
        }
    }
    fn read_key(&self, _provider: &str) -> String {
        let path = home().join("AppData/Roaming/OpenChatCut/.env.local");
        read_text(&path)
            .lines()
            .find(|l| l.starts_with("LLM_DEEPSEEK_API_KEY="))
            .map(|l| l.split_once('=').map(|(_, v)| v.trim().to_string()).unwrap_or_default())
            .unwrap_or_default()
    }
    fn restart_hint(&self) -> Vec<String> {
        vec!["OpenChatCut".into()]
    }
}

// ---------- WorkBuddy ----------

pub struct WorkBuddyAdapter;
impl Adapter for WorkBuddyAdapter {
    fn write_key(&self, _provider: &str, key: &str) -> WriteResult {
        let path = home().join(".workbuddy/models.json");
        let mut arr: Vec<serde_json::Value> = if path.exists() {
            serde_json::from_str(&read_text(&path)).unwrap_or_default()
        } else {
            Vec::new()
        };
        for m in arr.iter_mut() {
            if let Some(url) = m.get("url").and_then(|u| u.as_str()) {
                if url.contains("opencode.ai") {
                    m["apiKey"] = serde_json::Value::String(key.to_string());
                }
            }
        }
        backup(&path);
        match write_text(&path, &serde_json::to_string_pretty(&arr).unwrap_or_default()) {
            Ok(_) => WriteResult { ok: true, msg: "WorkBuddy models.json 已更新（重启 WorkBuddy 生效）".into(), provider: None, target: None },
            Err(e) => WriteResult { ok: false, msg: format!("WorkBuddy 写入失败: {e}"), provider: None, target: None },
        }
    }
    fn read_key(&self, _provider: &str) -> String {
        let path = home().join(".workbuddy/models.json");
        if let Ok(arr) = serde_json::from_str::<Vec<serde_json::Value>>(&read_text(&path)) {
            for m in arr {
                if let Some(k) = m.get("apiKey").and_then(|k| k.as_str()) {
                    return k.to_string();
                }
            }
        }
        String::new()
    }
    fn restart_hint(&self) -> Vec<String> {
        vec!["WorkBuddy".into()]
    }
}

// ---------- Codex (codex-router) ----------

pub struct CodexAdapter;
impl Adapter for CodexAdapter {
    fn write_key(&self, provider: &str, key: &str) -> WriteResult {
        let fname = match provider {
            "opencode-go" => "opencode-go-api-key.secret",
            "deepseek" => "deepseek-api-key.secret",
            _ => return WriteResult { ok: false, msg: format!("codex-router 暂不支持 provider: {provider}"), provider: None, target: None },
        };
        let path = home().join(format!(".codex/codex-router/{fname}"));
        backup(&path);
        match write_text(&path, key) {
            Ok(_) => WriteResult { ok: true, msg: format!("{fname} 已更新（重启 Codex CLI 生效）"), provider: None, target: None },
            Err(e) => WriteResult { ok: false, msg: format!("codex 写入失败: {e}"), provider: None, target: None },
        }
    }
    fn read_key(&self, provider: &str) -> String {
        let fname = match provider {
            "opencode-go" => "opencode-go-api-key.secret",
            _ => "opencode-go-api-key.secret",
        };
        read_text(&home().join(format!(".codex/codex-router/{fname}")))
            .trim()
            .to_string()
    }
    fn restart_hint(&self) -> Vec<String> {
        vec!["Codex CLI".into()]
    }
}

// ---------- 通用：JSON 文件（点路径） ----------

pub struct JsonFileAdapter {
    pub path: String,
    pub key_path: String,
}
impl Adapter for JsonFileAdapter {
    fn write_key(&self, _provider: &str, key: &str) -> WriteResult {
        let p = std::path::Path::new(&self.path);
        let mut d: serde_json::Value = serde_json::from_str(&read_text(p)).unwrap_or(serde_json::json!({}));
        let parts: Vec<&str> = self.key_path.split('.').collect();
        set_json_path(&mut d, &parts, serde_json::Value::String(key.into()));
        backup(p);
        match write_text(p, &serde_json::to_string_pretty(&d).unwrap_or_default()) {
            Ok(_) => WriteResult { ok: true, msg: format!("JSON {} 已更新", p.file_name().map(|f| f.to_string_lossy().to_string()).unwrap_or_default()), provider: None, target: None },
            Err(e) => WriteResult { ok: false, msg: format!("写入失败: {e}"), provider: None, target: None },
        }
    }
    fn read_key(&self, _provider: &str) -> String {
        let p = std::path::Path::new(&self.path);
        if let Ok(d) = serde_json::from_str::<serde_json::Value>(&read_text(p)) {
            if let Some(v) = get_json_path(&d, &self.key_path.split('.').collect::<Vec<_>>()) {
                return v.as_str().unwrap_or("").to_string();
            }
        }
        String::new()
    }
    fn restart_hint(&self) -> Vec<String> {
        Vec::new()
    }
}

fn get_json_path<'a>(d: &'a serde_json::Value, parts: &[&str]) -> Option<&'a serde_json::Value> {
    let mut cur = d;
    for p in parts {
        cur = match p.parse::<usize>() {
            Ok(i) => cur.get(i)?,
            Err(_) => cur.get(*p)?,
        };
    }
    Some(cur)
}

fn set_json_path(d: &mut serde_json::Value, parts: &[&str], val: serde_json::Value) {
    if parts.is_empty() {
        return;
    }
    if parts.len() == 1 {
        match parts[0].parse::<usize>() {
            Ok(i) => {
                if let Some(a) = d.as_array_mut() {
                    while a.len() <= i {
                        a.push(serde_json::Value::Null);
                    }
                    a[i] = val;
                }
            }
            Err(_) => {
                if let Some(o) = d.as_object_mut() {
                    o.insert(parts[0].to_string(), val);
                }
            }
        }
        return;
    }
    let next = parts[0];
    let child = match next.parse::<usize>() {
        Ok(i) => {
            if !d.is_array() {
                *d = serde_json::Value::Array(Vec::new());
            }
            let arr = d.as_array_mut().unwrap();
            while arr.len() <= i {
                arr.push(serde_json::Value::Object(Default::default()));
            }
            &mut arr[i]
        }
        Err(_) => {
            if !d.is_object() {
                *d = serde_json::Value::Object(Default::default());
            }
            d.as_object_mut()
                .unwrap()
                .entry(next.to_string())
                .or_insert_with(|| serde_json::Value::Object(Default::default()))
        }
    };
    set_json_path(child, &parts[1..], val);
}

// ---------- 通用：KEY=VALUE 文件 ----------

pub struct EnvFileAdapter {
    pub path: String,
    pub key_name: String,
}
impl Adapter for EnvFileAdapter {
    fn write_key(&self, _provider: &str, key: &str) -> WriteResult {
        let p = std::path::Path::new(&self.path);
        let mut lines: Vec<String> = if p.exists() {
            read_text(p).lines().map(|l| l.to_string()).collect()
        } else {
            Vec::new()
        };
        let prefix = format!("{}=", self.key_name);
        if let Some(i) = lines.iter().position(|l| l.trim_start().starts_with(&prefix)) {
            lines[i] = format!("{}{}", prefix, key);
        } else {
            lines.push(format!("{}{}", prefix, key));
        }
        backup(p);
        match write_text(p, &(lines.join("\n") + "\n")) {
            Ok(_) => WriteResult { ok: true, msg: format!("{} 已更新", p.file_name().map(|f| f.to_string_lossy().to_string()).unwrap_or_default()), provider: None, target: None },
            Err(e) => WriteResult { ok: false, msg: format!("写入失败: {e}"), provider: None, target: None },
        }
    }
    fn read_key(&self, _provider: &str) -> String {
        let p = std::path::Path::new(&self.path);
        read_text(p)
            .lines()
            .find(|l| l.trim_start().starts_with(&format!("{}=", self.key_name)))
            .map(|l| l.split_once('=').map(|(_, v)| v.trim().to_string()).unwrap_or_default())
            .unwrap_or_default()
    }
    fn restart_hint(&self) -> Vec<String> {
        Vec::new()
    }
}

// ---------- 通用：正则替换 ----------

pub struct RegexFileAdapter {
    pub path: String,
    pub pattern: String,
    pub replacement: String,
}
impl Adapter for RegexFileAdapter {
    fn write_key(&self, _provider: &str, key: &str) -> WriteResult {
        let p = std::path::Path::new(&self.path);
        let text = read_text(p);
        let re = match regex::Regex::new(&self.pattern) {
            Ok(r) => r,
            Err(e) => return WriteResult { ok: false, msg: format!("正则无效: {e}"), provider: None, target: None },
        };
        let repl = self.replacement.replace("{key}", key);
        let new = re.replace_all(&text, repl.as_str()).to_string();
        if new == text {
            return WriteResult { ok: false, msg: "正则未匹配到任何内容".into(), provider: None, target: None };
        }
        backup(p);
        match write_text(p, &new) {
            Ok(_) => WriteResult { ok: true, msg: format!("{} 已更新", p.file_name().map(|f| f.to_string_lossy().to_string()).unwrap_or_default()), provider: None, target: None },
            Err(e) => WriteResult { ok: false, msg: format!("写入失败: {e}"), provider: None, target: None },
        }
    }
    fn read_key(&self, _provider: &str) -> String {
        if let Ok(re) = regex::Regex::new(&self.pattern) {
            if let Some(c) = re.captures(&read_text(std::path::Path::new(&self.path))) {
                if c.len() > 1 {
                    return c.get(1).map(|m| m.as_str().to_string()).unwrap_or_default();
                }
            }
        }
        String::new()
    }
    fn restart_hint(&self) -> Vec<String> {
        Vec::new()
    }
}

// ---------- 工厂 ----------

/// 按 target 配置构建适配器
pub fn build_adapter(t: &Target) -> Result<Box<dyn Adapter>, String> {
    match t.adapter.as_str() {
        "pi" => Ok(Box::new(PiAdapter)),
        "env_var" => Ok(Box::new(EnvVarAdapter {
            env_name: t.env.clone().unwrap_or_else(|| "OPENCODE_GO_API_KEY".into()),
            restart: Vec::new(),
        })),
        "openchatcut" => Ok(Box::new(OpenChatCutAdapter)),
        "workbuddy" => Ok(Box::new(WorkBuddyAdapter)),
        "codex" => Ok(Box::new(CodexAdapter)),
        "file_json" => Ok(Box::new(JsonFileAdapter {
            path: t.path.clone().unwrap_or_default(),
            key_path: t.key_path.clone().unwrap_or_else(|| "api_key".into()),
        })),
        "file_env" => Ok(Box::new(EnvFileAdapter {
            path: t.path.clone().unwrap_or_default(),
            key_name: t.key_name.clone().unwrap_or_else(|| "API_KEY".into()),
        })),
        "file_regex" => Ok(Box::new(RegexFileAdapter {
            path: t.path.clone().unwrap_or_default(),
            pattern: t.pattern.clone().unwrap_or_default(),
            replacement: t.replacement.clone().unwrap_or_else(|| "\\1{key}\\2".into()),
        })),
        other => Err(format!("未知适配器: {other}")),
    }
}

/// 应用单个软件的 mapping（写该软件所有映射的 key）
#[allow(dead_code)] // 预留：批量应用单个 target（当前由 commands.apply_targets 覆盖）
pub fn apply_target(cfg: &Config, t: &Target) -> (Vec<WriteResult>, Vec<String>) {
    let mut results = Vec::new();
    let mut restart = Vec::new();
    let adapter = match build_adapter(t) {
        Ok(a) => a,
        Err(e) => {
            results.push(WriteResult {
                ok: false,
                msg: e,
                provider: None,
                target: Some(t.name.clone()),
            });
            return (results, restart);
        }
    };
    for (provider, key_id) in &t.mapping {
        if key_id.is_empty() {
            continue;
        }
        let key = cfg.key_value(provider, key_id);
        if key.is_empty() {
            results.push(WriteResult {
                ok: false,
                msg: format!("key 为空: {provider}/{key_id}"),
                provider: Some(provider.clone()),
                target: Some(t.name.clone()),
            });
            continue;
        }
        let mut r = adapter.write_key(provider, &key);
        r.provider = Some(provider.clone());
        r.target = Some(t.name.clone());
        results.push(r);
    }
    restart.extend(adapter.restart_hint());
    (results, restart)
}
