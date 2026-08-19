//! 智能切换：检测在用 key，耗尽的按优先级（keys 列表顺序）切到可用 key
//! ⚠️ 本模块只修改 cfg 内存，不写盘——由调用方确认后 save_config

use crate::models::Config;
use crate::usage;
use serde::Serialize;

#[derive(Serialize, Clone)]
pub struct SwitchEvent {
    pub provider: String,      // 原 provider
    pub to_provider: String,   // 切换到的 provider（跨 provider 兜底时与原不同）
    pub from: String,
    pub to: String,
    pub targets: Vec<String>,
    pub failed: Vec<String>,
}

#[derive(Serialize, Clone)]
pub struct SmartResult {
    pub switches: Vec<SwitchEvent>,
    pub exhausted: Vec<String>,
    pub checked: usize,
}

pub fn smart_switch_once(
    cfg: &mut Config,
    trigger_percent: Option<u64>,
) -> SmartResult {
    let trigger = trigger_percent.or(Some(cfg.auto_switch.trigger_percent));

    // 1) 一次查清所有 key 的用量（带缓存），并构建「可用 key」清单（列表顺序=优先级）
    let mut usage_all: std::collections::HashMap<(String, String), usage::UsageInfo> =
        std::collections::HashMap::new();
    for (pname, pcfg) in &cfg.providers {
        for k in &pcfg.keys {
            let u = usage::query_usage_cached(pname, &k.id, pcfg, &k.key);
            usage_all.insert((pname.clone(), k.id.clone()), u);
        }
    }
    let mut usable: std::collections::HashMap<String, Vec<String>> =
        std::collections::HashMap::new(); // provider -> 可用 key_id（按优先级）
    for (pname, pcfg) in &cfg.providers {
        let mut list = Vec::new();
        for k in &pcfg.keys {
            if k.key.is_empty() {
                continue;
            }
            let u = usage_all
                .get(&(pname.clone(), k.id.clone()))
                .cloned()
                .unwrap_or_default();
            // 查询失败（403/网络错误）≠ 耗尽：不做候选，避免误选可能仍可用的 key
            if u.status == "error" {
                continue;
            }
            if !usage::is_exhausted(cfg, pname, &u, trigger) {
                list.push(k.id.clone());
            }
        }
        usable.insert(pname.clone(), list);
    }

    // 2) 跨 provider 兜底的偏好顺序：prefer_providers 在前，其余按名称排序
    let mut provider_order: Vec<String> = cfg.providers.keys().cloned().collect();
    provider_order.sort();
    if !cfg.auto_switch.prefer_providers.is_empty() {
        let mut ordered: Vec<String> = Vec::new();
        for p in &cfg.auto_switch.prefer_providers {
            if cfg.providers.contains_key(p) && !ordered.contains(p) {
                ordered.push(p.clone());
            }
        }
        for p in &provider_order {
            if !ordered.contains(p) {
                ordered.push(p.clone());
            }
        }
        provider_order = ordered;
    }

    // 3) 收集在用 key -> 使用它的软件
    let mut usage_map: std::collections::HashMap<(String, String), Vec<String>> =
        std::collections::HashMap::new();
    for t in &cfg.targets {
        for (p, kid) in &t.mapping {
            if !kid.is_empty() {
                usage_map.entry((p.clone(), kid.clone())).or_default().push(t.name.clone());
            }
        }
    }

    let mut switches = Vec::new();
    let mut exhausted = Vec::new();
    let checked = usage_map.len();
    for ((provider, kid), targets) in usage_map {
        let u = match usage_all.get(&(provider.clone(), kid.clone())) {
            Some(u) => u.clone(),
            None => continue,
        };
        // 查询失败（403/网络错误）≠ 耗尽：不触发切换，保持现状（避免误切多花钱）
        if u.status == "error" {
            continue;
        }
        if !usage::is_exhausted(cfg, &provider, &u, trigger) {
            continue;
        }
        exhausted.push(format!("{provider}/{kid}"));

        // 候选：先同 provider 内（省钱优先），再跨 provider 兜底（按偏好顺序）
        let mut best: Option<(String, String)> = None; // (provider, key_id)
        if let Some(list) = usable.get(&provider) {
            if let Some(id) = list.iter().find(|id| **id != kid) {
                best = Some((provider.clone(), id.clone()));
            }
        }
        if best.is_none() {
            for p in &provider_order {
                if p == &provider {
                    continue;
                }
                if let Some(list) = usable.get(p) {
                    if let Some(id) = list.first() {
                        best = Some((p.clone(), id.clone()));
                        break;
                    }
                }
            }
        }
        let (best_provider, best_id) = match best {
            Some(b) => b,
            None => continue,
        };
        let new_val = cfg.key_value(&best_provider, &best_id);
        if new_val.is_empty() {
            continue;
        }

        // 4) 切换所有使用该 key 的软件：写真实 key + 更新 mapping
        let mut ok_targets = Vec::new();
        let mut fail_targets = Vec::new();
        for tname in targets {
            let t = match cfg.targets.iter_mut().find(|t| t.name == tname) {
                Some(t) => t,
                None => continue,
            };
            let adapter = match crate::adapters::build_adapter(t) {
                Ok(a) => a,
                Err(_) => {
                    fail_targets.push(tname);
                    continue;
                }
            };
            let r = adapter.write_key(&best_provider, &new_val);
            if r.ok {
                t.mapping.insert(best_provider.clone(), best_id.clone());
                if best_provider != provider {
                    // 原 provider 的 key 已耗尽：置空，避免下次又把它当在用
                    t.mapping.insert(provider.clone(), String::new());
                }
                ok_targets.push(tname);
            } else {
                fail_targets.push(tname);
            }
        }
        switches.push(SwitchEvent {
            provider: provider.clone(),
            to_provider: best_provider,
            from: kid,
            to: best_id,
            targets: ok_targets,
            failed: fail_targets,
        });
    }

    SmartResult {
        switches,
        exhausted,
        checked,
    }
}

/// 调整 key 优先级（keys 列表顺序 = 优先级）
pub fn move_key(cfg: &mut Config, provider: &str, key_id: &str, direction: &str) -> Result<String, String> {
    let keys = match cfg.providers.get_mut(provider) {
        Some(p) => &mut p.keys,
        None => return Err(format!("Provider 不存在: {provider}")),
    };
    let idx = keys.iter().position(|k| k.id == key_id);
    let idx = match idx {
        Some(i) => i,
        None => return Err(format!("未找到 {provider}/{key_id}")),
    };
    let ni = if direction == "up" {
        if idx == 0 {
            return Err(format!("{key_id} 已在最前"));
        }
        idx - 1
    } else {
        if idx + 1 >= keys.len() {
            return Err(format!("{key_id} 已在最后"));
        }
        idx + 1
    };
    keys.swap(idx, ni);
    Ok(format!("{provider}/{key_id} 已{}（顺序即优先级）", if direction == "up" { "上移" } else { "下移" }))
}
