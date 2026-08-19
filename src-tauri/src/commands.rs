//! Tauri 命令层：前端 invoke 的接口

use crate::adapters::{self, WriteResult};
use crate::models::{Config, KeyItem, Provider, Target};
use crate::smart;
use crate::usage;
use serde::Serialize;
use std::collections::HashMap;

#[derive(Serialize)]
pub struct KeyStatus {
    pub provider: String,
    pub id: String,
    pub key_prefix: String,
    pub note: String,
    pub usage: Option<usage::UsageInfo>,
}

#[derive(Serialize)]
pub struct ApplyResult {
    pub results: Vec<WriteResult>,
    pub restart: Vec<String>,
}

#[derive(Serialize)]
pub struct AdapterInfo {
    pub name: String,
    pub description: String,
}

// ---------- 配置 ----------

#[tauri::command]
pub async fn get_config() -> Result<Config, String> {
    // 文件读 + TOML 解析放后台线程，不占主界面线程（切页时反复调用）
    tauri::async_runtime::spawn_blocking(|| crate::models::load_config())
        .await
        .map_err(|e| e.to_string())?
}

#[tauri::command]
pub fn save_config_front(cfg: Config) -> Result<(), String> {
    crate::models::save_config(&cfg)
}

#[tauri::command]
pub async fn get_status(force: Option<bool>) -> Result<Vec<KeyStatus>, String> {
    let force = force.unwrap_or(false);
    // 异步命令 + spawn_blocking：并行查询集成在 usage::get_usage_batch（含缓存），
    // 阻塞逻辑跑在独立线程池，不占 async runtime 线程、不阻塞 WebView UI。
    tauri::async_runtime::spawn_blocking(move || -> Result<Vec<KeyStatus>, String> {
        let cfg = crate::models::load_config()?;
        let rows = usage::get_usage_batch(&cfg, force);
        Ok(rows
            .into_iter()
            .map(|(provider, id, note, usage)| KeyStatus {
                key_prefix: cfg
                    .providers
                    .get(&provider)
                    .and_then(|p| p.keys.iter().find(|k| k.id == id))
                    .map(|k| k.key.chars().take(8).collect())
                    .unwrap_or_default(),
                provider,
                id,
                note,
                usage: Some(usage),
            })
            .collect())
    })
    .await
    .map_err(|e| e.to_string())?
}

#[tauri::command]
pub async fn get_actual_keys() -> Result<HashMap<String, HashMap<String, String>>, String> {
    // 涉及到读文件 / powershell 等较重 IO，放后台线程避免阻塞主界面
    tauri::async_runtime::spawn_blocking(move || {
        let cfg = crate::models::load_config()?;
        let mut out = HashMap::new();
        for t in &cfg.targets {
            if let Ok(a) = adapters::build_adapter(t) {
                let mut m = HashMap::new();
                for p in cfg.provider_names() {
                    let v = a.read_key(&p);
                    if !v.is_empty() {
                        m.insert(p, v);
                    }
                }
                out.insert(t.name.clone(), m);
            }
        }
        Ok(out)
    })
    .await
    .map_err(|e| e.to_string())?
}

#[tauri::command]
pub fn list_adapters() -> Vec<AdapterInfo> {
    vec![
        AdapterInfo { name: "pi".into(), description: "pi 工具 (~/.pi/agent/auth.json)".into() },
        AdapterInfo { name: "env_var".into(), description: "Windows 用户环境变量".into() },
        AdapterInfo { name: "openchatcut".into(), description: "OpenChatCut (.env.local)".into() },
        AdapterInfo { name: "workbuddy".into(), description: "WorkBuddy (models.json)".into() },
        AdapterInfo { name: "codex".into(), description: "Codex (codex-router secret 文件)".into() },
        AdapterInfo { name: "file_json".into(), description: "任意 JSON 配置文件（点路径）".into() },
        AdapterInfo { name: "file_env".into(), description: "任意 KEY=VALUE 文件（.env 类）".into() },
        AdapterInfo { name: "file_regex".into(), description: "正则替换（pattern 含 1 个捕获组）".into() },
    ]
}

// ---------- 保存并应用 ----------

#[tauri::command]
pub async fn apply_targets(new_mappings: HashMap<String, HashMap<String, String>>) -> Result<ApplyResult, String> {
    // 写多个真实配置文件（文件 IO）较重，放后台线程
    tauri::async_runtime::spawn_blocking(move || -> Result<ApplyResult, String> {
        let mut cfg = crate::models::load_config()?;
    let mut results = Vec::new();
    let mut restart_set: Vec<String> = Vec::new();

    // key 值池（避免 iter_mut targets 时同时借用 cfg.providers）
    let key_values: HashMap<(String, String), String> = cfg
        .providers
        .iter()
        .flat_map(|(p, pc)| pc.keys.iter().map(|k| ((p.clone(), k.id.clone()), k.key.clone())))
        .collect();

    for t in cfg.targets.iter_mut() {
        let new = match new_mappings.get(&t.name) {
            Some(m) => m,
            None => continue,
        };
        let changed: Vec<(String, String)> = new
            .iter()
            .filter(|(p, kid)| t.mapping.get(*p).unwrap_or(&String::new()) != *kid)
            .map(|(p, kid)| (p.clone(), kid.clone()))
            .collect();
        if changed.is_empty() {
            continue;
        }
        // 写变化的 provider
        let adapter = match adapters::build_adapter(t) {
            Ok(a) => a,
            Err(e) => {
                results.push(WriteResult {
                    ok: false,
                    msg: e,
                    provider: None,
                    target: Some(t.name.clone()),
                });
                continue;
            }
        };
        for (provider, kid) in &changed {
            if kid.is_empty() {
                t.mapping.insert(provider.clone(), String::new());
                continue;
            }
            let key = key_values
                .get(&(provider.clone(), kid.clone()))
                .cloned()
                .unwrap_or_default();
            if key.is_empty() {
                results.push(WriteResult {
                    ok: false,
                    msg: format!("key 为空: {provider}/{kid}"),
                    provider: Some(provider.clone()),
                    target: Some(t.name.clone()),
                });
                continue;
            }
            let mut r = adapter.write_key(provider, &key);
            r.provider = Some(provider.clone());
            r.target = Some(t.name.clone());
            results.push(r);
            t.mapping.insert(provider.clone(), kid.clone());
        }
        for s in adapter.restart_hint() {
            if !restart_set.contains(&s) {
                restart_set.push(s);
            }
        }
    }

    crate::models::save_config(&cfg)?;
        Ok(ApplyResult { results, restart: restart_set })
    })
    .await
    .map_err(|e| e.to_string())?
}

// ---------- 智能切换 ----------

#[tauri::command]
pub async fn smart_check(trigger: Option<u64>) -> Result<smart::SmartResult, String> {
    tauri::async_runtime::spawn_blocking(move || {
        // 不清理用量缓存：查询失败时可回退最近一次成功数据判定（403 时有据可依）
        let mut cfg = crate::models::load_config()?;
        let r = smart::smart_switch_once(&mut cfg, trigger);
        if !r.switches.is_empty() {
            crate::models::save_config(&cfg)?;
        }
        Ok(r)
    })
    .await
    .map_err(|e| e.to_string())?
}

#[tauri::command]
pub fn save_auto_settings(enabled: bool, trigger_percent: u64, interval_min: u64) -> Result<(), String> {
    let mut cfg = crate::models::load_config()?;
    cfg.auto_switch.enabled = enabled;
    cfg.auto_switch.trigger_percent = trigger_percent;
    cfg.auto_switch.interval_min = interval_min;
    crate::models::save_config(&cfg)
}

// ---------- 管理（增删 / 排序） ----------

#[tauri::command]
pub fn add_provider(name: String, base_url: String, usage_type: String) -> Result<String, String> {
    let mut cfg = crate::models::load_config()?;
    if cfg.providers.contains_key(&name) {
        return Err(format!("Provider 已存在: {name}"));
    }
    cfg.providers.insert(name.clone(), Provider {
        base_url,
        usage_type: if usage_type == "balance" { "balance".into() } else { "percent".into() },
        keys: Vec::new(),
    });
    crate::models::save_config(&cfg)?;
    Ok(format!("已添加 Provider {name}（请接着添加 key）"))
}

#[tauri::command]
pub fn delete_provider(name: String) -> Result<String, String> {
    let mut cfg = crate::models::load_config()?;
    if cfg.providers.remove(&name).is_none() {
        return Err(format!("Provider 不存在: {name}"));
    }
    if let Some(t) = &mut cfg.thresholds {
        t.remove(&name);
    }
    for t in cfg.targets.iter_mut() {
        t.mapping.remove(&name);
    }
    crate::models::save_config(&cfg)?;
    Ok(format!("已删除 Provider {name}"))
}

#[tauri::command]
pub fn add_key(provider: String, key_id: String, key_value: String, note: String) -> Result<String, String> {
    let mut cfg = crate::models::load_config()?;
    let p = match cfg.providers.get_mut(&provider) {
        Some(p) => p,
        None => return Err(format!("Provider 不存在: {provider}")),
    };
    if p.keys.iter().any(|k| k.id == key_id) {
        return Err(format!("key id 已存在: {provider}/{key_id}"));
    }
    p.keys.push(KeyItem { id: key_id.clone(), key: key_value, note });
    crate::models::save_config(&cfg)?;
    Ok(format!("已添加 {provider}/{key_id}"))
}

/// 编辑一个 Key（改 provider / 标识 / 值 / 备注），并同步迁移引用它的应用映射。
/// 纯逻辑（不读写磁盘），便于单测；由 edit_key command 负责 load/save。
fn edit_key_inner(
    cfg: &mut Config,
    provider: &str,
    old_id: &str,
    new_provider: &str,
    new_id: &str,
    new_value: String,
    new_note: String,
) -> Result<String, String> {
    // 目标 provider 必须存在
    if !cfg.providers.contains_key(new_provider) {
        return Err(format!("Provider 不存在: {new_provider}"));
    }
    // 确认旧 key 存在，并记录其在列表中的位置（顺序即优先级）
    let old_index = cfg
        .providers
        .get(provider)
        .and_then(|p| p.keys.iter().position(|k| k.id == old_id));
    let old_index = match old_index {
        Some(i) => i,
        None => return Err(format!("未找到 {provider}/{old_id}")),
    };
    // 校验新标识在目标 provider 内不冲突（同 provider 时排除自身）
    let clash = cfg
        .providers
        .get(new_provider)
        .map(|p| {
            p.keys
                .iter()
                .any(|k| k.id == new_id && !(provider == new_provider && k.id == old_id))
        })
        .unwrap_or(false);
    if clash {
        return Err(format!("目标 Provider {new_provider} 已存在 Key 标识: {new_id}"));
    }

    // 移除旧项
    if let Some(p) = cfg.providers.get_mut(provider) {
        p.keys.retain(|k| k.id != old_id);
    }
    // 插入新项：同 provider 内放回原位置（保持优先级），跨 provider 追加到新 provider 末尾
    let item = KeyItem {
        id: new_id.to_string(),
        key: new_value,
        note: new_note,
    };
    if let Some(tp) = cfg.providers.get_mut(new_provider) {
        if provider == new_provider {
            let insert_at = old_index.min(tp.keys.len());
            tp.keys.insert(insert_at, item);
        } else {
            tp.keys.push(item);
        }
    }

    // 更新所有 target 的 mapping：原 (旧provider -> 旧id) 迁移为 (新provider -> 新id)
    for t in cfg.targets.iter_mut() {
        if t.mapping.get(provider).map(|s| s.as_str()) == Some(old_id) {
            if provider == new_provider {
                t.mapping.insert(provider.to_string(), new_id.to_string());
            } else {
                t.mapping.remove(provider);
                t.mapping.insert(new_provider.to_string(), new_id.to_string());
            }
        }
    }

    Ok(format!("已更新 {provider}/{old_id} → {new_provider}/{new_id}"))
}

#[tauri::command]
pub fn edit_key(
    provider: String,
    old_id: String,
    new_provider: String,
    new_id: String,
    new_value: String,
    new_note: String,
) -> Result<String, String> {
    let mut cfg = crate::models::load_config()?;
    let msg = edit_key_inner(
        &mut cfg,
        &provider,
        &old_id,
        &new_provider,
        &new_id,
        new_value,
        new_note,
    )?;
    crate::models::save_config(&cfg)?;
    Ok(msg)
}

#[tauri::command]
pub fn delete_key(provider: String, key_id: String) -> Result<String, String> {
    let mut cfg = crate::models::load_config()?;
    let p = match cfg.providers.get_mut(&provider) {
        Some(p) => p,
        None => return Err(format!("Provider 不存在: {provider}")),
    };
    let before = p.keys.len();
    p.keys.retain(|k| k.id != key_id);
    if p.keys.len() == before {
        return Err(format!("未找到 {provider}/{key_id}"));
    }
    for t in cfg.targets.iter_mut() {
        for v in t.mapping.values_mut() {
            if *v == key_id {
                v.clear();
            }
        }
    }
    crate::models::save_config(&cfg)?;
    Ok(format!("已删除 {provider}/{key_id}"))
}

#[tauri::command]
pub fn move_key(provider: String, key_id: String, direction: String) -> Result<String, String> {
    let mut cfg = crate::models::load_config()?;
    let msg = smart::move_key(&mut cfg, &provider, &key_id, &direction)?;
    crate::models::save_config(&cfg)?;
    Ok(msg)
}

#[tauri::command]
pub fn add_target(
    name: String,
    label: String,
    adapter: String,
    env: Option<String>,
    path: Option<String>,
    key_path: Option<String>,
    key_name: Option<String>,
    pattern: Option<String>,
    replacement: Option<String>,
    mapping: HashMap<String, String>,
) -> Result<String, String> {
    let mut cfg = crate::models::load_config()?;
    if cfg.targets.iter().any(|t| t.name == name) {
        return Err(format!("应用已存在: {name}"));
    }
    cfg.targets.push(Target {
        name: name.clone(),
        label,
        adapter,
        env,
        path,
        key_path,
        key_name,
        pattern,
        replacement,
        mapping,
    });
    crate::models::save_config(&cfg)?;
    Ok(format!("已添加应用「{name}」（去 Key 配置页核对映射并保存）"))
}

#[tauri::command]
pub fn delete_target(name: String) -> Result<String, String> {
    let mut cfg = crate::models::load_config()?;
    let before = cfg.targets.len();
    cfg.targets.retain(|t| t.name != name);
    if cfg.targets.len() == before {
        return Err(format!("未找到应用: {name}"));
    }
    crate::models::save_config(&cfg)?;
    Ok(format!("已删除应用 {name}"))
}

// ---------- 杂项 ----------

#[tauri::command]
pub fn open_path(kind: String) -> Result<(), String> {
    let target = match kind.as_str() {
        "config_dir" => crate::models::config_path()
            .parent()
            .map(|p| p.to_path_buf()),
        "config_file" => Some(crate::models::config_path()),
        _ => None,
    };
    let target = match target {
        Some(t) => t,
        None => return Err(format!("未知路径类型: {kind}")),
    };
    #[cfg(target_os = "windows")]
    {
        let _ = std::process::Command::new("explorer.exe")
            .arg("/select,")
            .arg(&target)
            .spawn();
    }
    #[cfg(not(target_os = "windows"))]
    {
        let _ = std::process::Command::new("xdg-open").arg(&target).spawn();
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    /// 构造含两个 provider、一个引用 p1/k1 的 target 的配置
    fn cfg_with_two_providers() -> Config {
        let mut cfg = Config::default();
        cfg.providers.insert(
            "p1".into(),
            Provider {
                base_url: "u".into(),
                usage_type: "percent".into(),
                keys: vec![
                    KeyItem { id: "k1".into(), key: "sk-a".into(), note: "".into() },
                    KeyItem { id: "k2".into(), key: "sk-b".into(), note: "".into() },
                ],
            },
        );
        cfg.providers.insert(
            "p2".into(),
            Provider {
                base_url: "u".into(),
                usage_type: "percent".into(),
                keys: vec![KeyItem { id: "k3".into(), key: "sk-c".into(), note: "".into() }],
            },
        );
        let mut t = Target::default();
        t.name = "app1".into();
        t.adapter = "file_env".into();
        t.mapping.insert("p1".into(), "k1".into());
        cfg.targets.push(t);
        cfg
    }

    #[test]
    fn rename_in_same_provider_keeps_priority_and_updates_mapping() {
        let mut cfg = cfg_with_two_providers();
        let r = edit_key_inner(&mut cfg, "p1", "k1", "p1", "k1x", "sk-zz".into(), "note".into());
        assert!(r.is_ok(), "{r:?}");
        let keys = &cfg.providers["p1"].keys;
        assert_eq!(keys.len(), 2);
        // 仍在原位置（index 0，保持优先级），标识/值/备注已更新
        assert_eq!(keys[0].id, "k1x");
        assert_eq!(keys[0].key, "sk-zz");
        assert_eq!(keys[0].note, "note");
        // mapping 已同步到新标识
        assert_eq!(cfg.targets[0].mapping.get("p1").map(|s| s.as_str()), Some("k1x"));
        // 其它 key 不受影响
        assert_eq!(cfg.providers["p1"].keys[1].id, "k2");
    }

    #[test]
    fn move_to_another_provider_migrates_mapping() {
        let mut cfg = cfg_with_two_providers();
        let r = edit_key_inner(&mut cfg, "p1", "k1", "p2", "k9", "sk-z".into(), "".into());
        assert!(r.is_ok(), "{r:?}");
        // key 已从 p1 移除、加入 p2
        assert!(cfg.providers["p1"].keys.iter().all(|k| k.id != "k1"));
        assert!(cfg.providers["p2"].keys.iter().any(|k| k.id == "k9" && k.key == "sk-z"));
        // mapping 从 p1 迁移到 p2:new id，并移除旧 p1 键
        assert_eq!(cfg.targets[0].mapping.get("p2").map(|s| s.as_str()), Some("k9"));
        assert!(!cfg.targets[0].mapping.contains_key("p1"));
    }

    #[test]
    fn rejects_missing_provider_conflict_and_unknown_old() {
        let mut cfg = cfg_with_two_providers();
        // 目标 provider 不存在
        assert!(edit_key_inner(&mut cfg, "p1", "k1", "NOPE", "kx", "v".into(), "".into()).is_err());
        // id 冲突：p1 内把 k2 改名为已存在的 k1
        let mut cfg2 = cfg_with_two_providers();
        assert!(edit_key_inner(&mut cfg2, "p1", "k2", "p1", "k1", "v".into(), "".into()).is_err());
        // 旧 key 不存在
        let mut cfg3 = cfg_with_two_providers();
        assert!(edit_key_inner(&mut cfg3, "p1", "ghost", "p2", "nx", "v".into(), "".into()).is_err());
    }
}
