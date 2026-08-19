//! 配置模型：TOML 文件读写（%APPDATA%/KeySwitch/config.toml）

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::path::PathBuf;

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

pub fn load_config() -> Result<Config, String> {
    let path = config_path();
    if !path.exists() {
        return Err(format!("配置不存在: {}（请先运行迁移脚本导入）", path.display()));
    }
    let text = std::fs::read_to_string(&path)
        .map_err(|e| format!("读取配置失败: {e}"))?;
    toml::from_str(&text).map_err(|e| format!("解析配置失败: {e}"))
}

pub fn save_config(cfg: &Config) -> Result<(), String> {
    let path = config_path();
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent).map_err(|e| format!("创建配置目录失败: {e}"))?;
    }
    let text = toml::to_string_pretty(cfg).map_err(|e| format!("序列化配置失败: {e}"))?;
    std::fs::write(&path, text).map_err(|e| format!("写入配置失败: {e}"))
}

impl Config {
    pub fn key_value(&self, provider: &str, key_id: &str) -> String {
        self.providers
            .get(provider)
            .and_then(|p| p.keys.iter().find(|k| k.id == key_id))
            .map(|k| k.key.clone())
            .unwrap_or_default()
    }

    pub fn key_ids(&self, provider: &str) -> Vec<String> {
        self.providers
            .get(provider)
            .map(|p| p.keys.iter().map(|k| k.id.clone()).collect())
            .unwrap_or_default()
    }

    pub fn provider_names(&self) -> Vec<String> {
        self.providers.keys().cloned().collect()
    }

    pub fn target_mapping(&self, target_name: &str) -> HashMap<String, String> {
        self.targets
            .iter()
            .find(|t| t.name == target_name)
            .map(|t| t.mapping.clone())
            .unwrap_or_default()
    }
}
