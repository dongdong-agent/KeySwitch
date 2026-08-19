//! 智能切换：检测在用 key，耗尽的按优先级（keys 列表顺序）切到可用 key
//! ⚠️ 本模块只修改 cfg 内存，不写盘——由调用方确认后 save_config

use crate::models::Config;
use crate::usage;
use serde::Serialize;

#[derive(Serialize, Clone)]
pub struct SwitchEvent {
    pub provider: String,
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

    // 1) 收集在用 key -> 使用它的软件
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
        let pcfg = match cfg.providers.get(&provider) {
            Some(p) => p.clone(),
            None => continue,
        };
        let key = cfg.key_value(&provider, &kid);
        if key.is_empty() {
            continue;
        }
        // 带缓存查询（同 key 近 60s 内查过则复用，避免重复 HTTP）
        let u = usage::query_usage_cached(&provider, &kid, &pcfg, &key);
        if !usage::is_exhausted(cfg, &provider, &u, trigger) {
            continue;
        }
        exhausted.push(format!("{provider}/{kid}"));

        // 2) 按优先级（列表顺序）找第一个可用 key，跳过自身
        let mut best: Option<String> = None;
        for k in &pcfg.keys {
            if k.id == kid || k.key.is_empty() {
                continue;
            }
            let ku = usage::query_usage_cached(&provider, &k.id, &pcfg, &k.key);
            if !usage::is_exhausted(cfg, &provider, &ku, trigger) {
                best = Some(k.id.clone());
                break;
            }
        }
        let best = match best {
            Some(b) => b,
            None => continue,
        };

        // 3) 切换所有使用该 key 的软件（先换 mapping，再只写当前 provider）
        let new_val = cfg.key_value(&provider, &best);
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
            let r = adapter.write_key(&provider, &new_val);
            if r.ok {
                t.mapping.insert(provider.clone(), best.clone());
                ok_targets.push(tname);
            } else {
                // 写失败：保持原 mapping 不变，避免配置与真实 key 不一致
                fail_targets.push(tname);
            }
        }
        switches.push(SwitchEvent {
            provider: provider.clone(),
            from: kid,
            to: best,
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
