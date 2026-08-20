//! 配置模型：TOML 文件读写（%APPDATA%/KeySwitch/config.toml）

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::path::PathBuf;
use std::sync::{LazyLock, Mutex};
use std::time::SystemTime;

#[derive(Serialize, Deserialize, Clone, Default)]
pub struct Config {
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub thresholds: Option<HashMap<String, serde_json::Value>>,
    #[serde(default)]
    pub providers: HashMap<String, Provider>,
    #[serde(default)]
    pub targets: Vec<Target>,
    #[serde(default)]
    pub auto_switch: AutoSwitch,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub active: Option<Active>,
}

#[derive(Serialize, Deserialize, Clone)]
pub struct Provider {
    pub base_url: String,
    #[serde(default = "default_usage_type")]
    pub usage_type: String, // "percent" | "balance"
    #[serde(default)]
    pub keys: Vec<KeyItem>,
}

fn default_usage_type() -> String {
    "percent".into()
}

#[derive(Serialize, Deserialize, Clone)]
pub struct KeyItem {
    pub id: String,
    pub key: String,
    #[serde(default)]
    pub note: String,
    /// 推广链接（如 opencode workspace URL），可选
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub promo_url: Option<String>,
    /// 奖励额度/说明（邀请/推广赠送），可选
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub reward: Option<String>,
}

#[derive(Serialize, Deserialize, Clone, Default)]
pub struct Target {
    pub name: String,
    #[serde(default)]
    pub label: String,
    pub adapter: String,
    // ---- 适配器参数（通用型） ----
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub env: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub path: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub key_path: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub key_name: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub pattern: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub replacement: Option<String>,
    // ---- 每软件独立映射：provider -> key_id ----
    #[serde(default)]
    pub mapping: HashMap<String, String>,
}

#[derive(Serialize, Deserialize, Clone)]
pub struct AutoSwitch {
    #[serde(default)]
    pub enabled: bool,
    #[serde(default = "default_interval")]
    pub interval_min: u64,
    #[serde(default = "default_trigger")]
    pub trigger_percent: u64,
    /// 跨 provider 兜底切换的偏好顺序（如 ["opencode-go","deepseek"]）；
    /// 空 = 仅同 provider 内切换。
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub prefer_providers: Vec<String>,
}

fn default_interval() -> u64 {
    5
}
fn default_trigger() -> u64 {
    100
}

impl Default for AutoSwitch {
    fn default() -> Self {
        Self {
            enabled: false,
            interval_min: default_interval(),
            trigger_percent: default_trigger(),
            prefer_providers: Vec::new(),
        }
    }
}

#[derive(Serialize, Deserialize, Clone)]
pub struct Active {
    pub provider: String,
    pub key_id: String,
}

/// 配置文件路径：%APPDATA%/KeySwitch/config.toml
pub fn config_path() -> PathBuf {
    let base = dirs::config_dir().unwrap_or_else(|| PathBuf::from("."));
    base.join("KeySwitch").join("config.toml")
}

/// 配置内存缓存：以文件修改时间(mtime)作为失效依据。
/// 文件没变就复用内存里的 Config（省去每次命令重复读盘 + TOML 解析），
/// 外部修改（手改 / 迁移脚本）会因 mtime 变化而自动重新加载，保证一致。
static CONFIG_CACHE: LazyLock<Mutex<Option<(Option<SystemTime>, Config)>>> =
    LazyLock::new(|| Mutex::new(None));

pub fn load_config() -> Result<Config, String> {
    let path = config_path();
    if !path.exists() {
        return Err(format!("配置不存在: {}（请先运行迁移脚本导入）", path.display()));
    }
    let mtime = std::fs::metadata(&path)
        .ok()
        .and_then(|m| m.modified().ok());
    // 命中缓存（文件未变）则直接复用
    if let Ok(c) = CONFIG_CACHE.lock() {
        if let Some((t, cfg)) = &*c {
            if *t == mtime {
                return Ok(cfg.clone());
            }
        }
    }
    let text = std::fs::read_to_string(&path).map_err(|e| format!("读取配置失败: {e}"))?;
    let cfg: Config = toml::from_str(&text).map_err(|e| format!("解析配置失败: {e}"))?;
    if let Ok(mut c) = CONFIG_CACHE.lock() {
        *c = Some((mtime, cfg.clone()));
    }
    Ok(cfg)
}

pub fn save_config(cfg: &Config) -> Result<(), String> {
    let path = config_path();
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent).map_err(|e| format!("创建配置目录失败: {e}"))?;
    }
    let text = toml::to_string_pretty(cfg).map_err(|e| format!("序列化配置失败: {e}"))?;
    std::fs::write(&path, text).map_err(|e| format!("写入配置失败: {e}"))?;
    // 写盘后更新缓存，避免下次 load 重复解析
    let mtime = std::fs::metadata(&path).ok().and_then(|m| m.modified().ok());
    if let Ok(mut c) = CONFIG_CACHE.lock() {
        *c = Some((mtime, cfg.clone()));
    }
    Ok(())
}

impl Config {
    pub fn key_value(&self, provider: &str, key_id: &str) -> String {
        self.providers
            .get(provider)
            .and_then(|p| p.keys.iter().find(|k| k.id == key_id))
            .map(|k| k.key.clone())
            .unwrap_or_default()
    }

    #[allow(dead_code)] // 预留
    pub fn key_ids(&self, provider: &str) -> Vec<String> {
        self.providers
            .get(provider)
            .map(|p| p.keys.iter().map(|k| k.id.clone()).collect())
            .unwrap_or_default()
    }

    pub fn provider_names(&self) -> Vec<String> {
        self.providers.keys().cloned().collect()
    }

    #[allow(dead_code)] // 预留
    pub fn target_mapping(&self, target_name: &str) -> HashMap<String, String> {
        self.targets
            .iter()
            .find(|t| t.name == target_name)
            .map(|t| t.mapping.clone())
            .unwrap_or_default()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn toml_roundtrip_preserves_providers_and_auto_switch() {
        let mut cfg = Config::default();
        cfg.providers.insert(
            "opencode-go".into(),
            Provider {
                base_url: "https://api.example.com".into(),
                usage_type: "percent".into(),
                keys: vec![KeyItem {
                    id: "k1".into(),
                    key: "sk-123".into(),
                    note: "测试".into(),
                    promo_url: None,
                    reward: None,
                }],
            },
        );
        cfg.auto_switch.enabled = true;
        cfg.auto_switch.trigger_percent = 100;
        let s = toml::to_string_pretty(&cfg).unwrap();
        let back: Config = toml::from_str(&s).unwrap();
        assert_eq!(back.providers["opencode-go"].keys[0].id, "k1");
        assert_eq!(back.providers["opencode-go"].keys[0].key, "sk-123");
        assert!(back.auto_switch.enabled);
        assert_eq!(back.auto_switch.trigger_percent, 100);
    }

    #[test]
    fn defaults_fill_in_missing_fields() {
        let s = "[auto_switch]\nenabled = true\n\n[[targets]]\nname = \"app\"\nadapter = \"file_env\"\nmapping = { opencode-go = \"k1\" }\n";
        let cfg: Config = toml::from_str(s).unwrap();
        assert!(cfg.auto_switch.enabled);
        assert_eq!(cfg.auto_switch.interval_min, 5); // 默认 5 分钟
        assert_eq!(cfg.auto_switch.trigger_percent, 100);
        assert_eq!(cfg.targets.len(), 1);
        assert_eq!(cfg.targets[0].mapping.get("opencode-go").map(|v| v.as_str()), Some("k1"));
        assert_eq!(cfg.targets[0].env, None); // 未提供字段默认 None
    }

    #[test]
    fn key_value_lookup() {
        let mut cfg = Config::default();
        cfg.providers.insert(
            "p".into(),
            Provider {
                base_url: "u".into(),
                usage_type: "percent".into(),
                keys: vec![KeyItem { id: "a".into(), key: "sk-x".into(), note: "".into(), promo_url: None, reward: None }],
            },
        );
        assert_eq!(cfg.key_value("p", "a"), "sk-x");
        assert_eq!(cfg.key_value("p", "nope"), ""); // 未知返回空
    }
}
