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
    /// 用量查询失败（403/网络错误）的 key，已按最近一次成功数据判定或无法判定
    pub query_failed: Vec<String>,
}

pub fn smart_switch_once(
    cfg: &mut Config,
    trigger_percent: Option<u64>,
) -> SmartResult {
    let trigger = trigger_percent.or(Some(cfg.auto_switch.trigger_percent));

    // 1) 一次查清所有 key 的用量（带缓存），并构建「可用 key」清单（列表顺序=优先级）
    let mut usage_all: std::collections::HashMap<(String, String), usage::UsageInfo> =
        std::collections::HashMap::new();
    // 本次查询失败（403/网络，数据为旧缓存）的 key：不能确认当前可用，排除出候选
    let mut usage_stale: std::collections::HashMap<(String, String), bool> =
        std::collections::HashMap::new();
    let mut query_failed: Vec<String> = Vec::new();
    for (pname, pcfg) in &cfg.providers {
        for k in &pcfg.keys {
            let (u, stale) = usage::query_usage_cached(pname, &k.id, pcfg, &k.key);
            if u.status == "error" || stale {
                // 本次确实查不到 / 回退旧数据：告知 UI
                query_failed.push(format!("{pname}/{}", k.id));
            }
            usage_stale.insert((pname.clone(), k.id.clone()), stale);
            usage_all.insert((pname.clone(), k.id.clone()), u);
        }
    }
    let usable = build_usable(cfg, trigger, &usage_all, &usage_stale);

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
        let ck = (provider.clone(), kid.clone());
        let u = match usage_all.get(&ck) {
            Some(u) => u.clone(),
            None => continue,
        };
        // 本次查询失败（403/网络）或回退旧数据（stale）→ 视为「不可用」，尝试切换；
        // 否则按三维度阈值判定是否耗尽。
        // 与候选不同：候选只选「本次查询成功」的 key；这里查询失败也触发切换，
        // 只要存在本次查询成功的可用 key（同 provider 优先，再跨 provider 如 DeepSeek）。
        let stale = usage_stale.get(&ck).copied().unwrap_or(false);
        let unavailable = u.status == "error"
            || stale
            || usage::is_exhausted(cfg, &provider, &u, trigger);
        if !unavailable {
            continue;
        }
        exhausted.push(format!("{provider}/{kid}"));

        // 候选：先同 provider 内（省钱优先），再跨 provider 兜底（按偏好顺序）
        let (best_provider, best_id) = match find_best(&usable, &provider, &kid, &provider_order) {
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
        query_failed,
    }
}

/// 构建「可用 key」清单：只保留本次查询成功（非 error / 非 stale）且未耗尽的 key。
/// 列表顺序 = keys 配置顺序 = 优先级。
/// 「本次查询失败（403/网络）」或「回退旧缓存数据」的 key 一律排除：
/// 无法确认当前可用，避免切到已失效的 key（如 opencode-go 整体 403）。
fn build_usable(
    cfg: &Config,
    trigger: Option<u64>,
    usage_all: &std::collections::HashMap<(String, String), usage::UsageInfo>,
    usage_stale: &std::collections::HashMap<(String, String), bool>,
) -> std::collections::HashMap<String, Vec<String>> {
    let mut usable: std::collections::HashMap<String, Vec<String>> =
        std::collections::HashMap::new(); // provider -> 可用 key_id（按优先级）
    for (pname, pcfg) in &cfg.providers {
        let mut list = Vec::new();
        for k in &pcfg.keys {
            if k.key.is_empty() {
                continue;
            }
            let ck = (pname.clone(), k.id.clone());
            let u = usage_all.get(&ck).cloned().unwrap_or_default();
            // 查询失败（403/网络错误）→ 不做候选
            if u.status == "error" {
                continue;
            }
            // 本次无最新成功数据（回退旧缓存）→ 不做候选
            if usage_stale.get(&ck).copied().unwrap_or(false) {
                continue;
            }
            if !usage::is_exhausted(cfg, pname, &u, trigger) {
                list.push(k.id.clone());
            }
        }
        usable.insert(pname.clone(), list);
    }
    usable
}

/// 找切换目标：先同 provider 内（排除在用 key，省钱优先），
/// 再按 provider_order 跨 provider 兜底（列表第一 = 最高优先级）。
fn find_best(
    usable: &std::collections::HashMap<String, Vec<String>>,
    provider: &str,
    kid: &str,
    provider_order: &[String],
) -> Option<(String, String)> {
    if let Some(list) = usable.get(provider) {
        if let Some(id) = list.iter().find(|id| **id != kid) {
            return Some((provider.to_string(), id.clone()));
        }
    }
    for p in provider_order {
        if p == provider {
            continue;
        }
        if let Some(list) = usable.get(p) {
            if let Some(id) = list.first() {
                return Some((p.clone(), id.clone()));
            }
        }
    }
    None
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

#[cfg(test)]
mod tests {
    use super::*;
    use crate::models::{Config, KeyItem, Provider};
    use crate::usage::UsageInfo;
    use std::collections::HashMap;

    fn pu(p: Option<u64>, w: Option<u64>, m: Option<u64>) -> UsageInfo {
        UsageInfo {
            kind: "percent".into(),
            percent: p, weekly: w, monthly: m,
            balance: None, rolling_reset: None, weekly_reset: None, monthly_reset: None,
            status: "ok".into(),
            detail: "x".into(),
        }
    }

    fn balance_ok(v: f64) -> UsageInfo {
        UsageInfo {
            kind: "balance".into(),
            percent: None, weekly: None, monthly: None,
            balance: Some(v), rolling_reset: None, weekly_reset: None, monthly_reset: None,
            status: "ok".into(),
            detail: "".into(),
        }
    }

    /// opencode-go: k1 本次查询成功可用(50%) / k2 回退旧数据(stale,50%) /
    /// k3 查询失败(error) / k4 三维度耗尽(100%)
    /// deepseek: d1 余额充足(100)
    fn basic_usable() -> (
        Config,
        HashMap<(String, String), UsageInfo>,
        HashMap<(String, String), bool>,
        HashMap<String, Vec<String>>,
    ) {
        let mut cfg = Config::default();
        cfg.providers.insert("opencode-go".into(), Provider {
            base_url: "u".into(), usage_type: "percent".into(),
            keys: (1..=4).map(|i| KeyItem {
                id: format!("k{i}"), key: format!("sk{i}"), note: "".into(), promo_url: None, reward: None,
            }).collect(),
        });
        cfg.providers.insert("deepseek".into(), Provider {
            base_url: "u".into(), usage_type: "balance".into(),
            keys: vec![KeyItem { id: "d1".into(), key: "skd".into(), note: "".into(), promo_url: None, reward: None }],
        });
        let mut usage_all = HashMap::new();
        usage_all.insert(("opencode-go".into(), "k1".into()), pu(Some(50), None, None));
        usage_all.insert(("opencode-go".into(), "k2".into()), pu(Some(50), None, None)); // stale
        let mut e3 = pu(None, None, None);
        e3.status = "error".into();
        usage_all.insert(("opencode-go".into(), "k3".into()), e3);
        usage_all.insert(("opencode-go".into(), "k4".into()), pu(Some(100), Some(100), Some(100))); // 耗尽
        usage_all.insert(("deepseek".into(), "d1".into()), balance_ok(100.0));
        let mut usage_stale = HashMap::new();
        usage_stale.insert(("opencode-go".into(), "k2".into()), true);
        let usable = build_usable(&cfg, Some(100), &usage_all, &usage_stale);
        (cfg, usage_all, usage_stale, usable)
    }

    #[test]
    fn usable_excludes_error_stale_and_exhausted() {
        let (_, _, _, usable) = basic_usable();
        // 只剩 k1（本次查询成功且未耗尽）；k2 stale、k3 error、k4 耗尽全被排除
        assert_eq!(usable.get("opencode-go"), Some(&vec!["k1".to_string()]));
        assert_eq!(usable.get("deepseek"), Some(&vec!["d1".to_string()]));
    }

    #[test]
    fn opencode_go_all_failed_falls_back_to_deepseek() {
        // 东哥场景：opencode-go 整体 403，全部回退旧缓存（stale）→
        // usable 中 opencode-go 为空，目标必须落到本次查询成功的 DeepSeek
        let mut cfg = Config::default();
        cfg.providers.insert("opencode-go".into(), Provider {
            base_url: "u".into(), usage_type: "percent".into(),
            keys: vec![KeyItem { id: "k1".into(), key: "sk1".into(), note: "".into(), promo_url: None, reward: None }],
        });
        cfg.providers.insert("deepseek".into(), Provider {
            base_url: "u".into(), usage_type: "balance".into(),
            keys: vec![KeyItem { id: "d1".into(), key: "skd".into(), note: "".into(), promo_url: None, reward: None }],
        });
        let mut usage_all = HashMap::new();
        // 旧缓存显示 80%（未耗尽），但本次查询失败 → stale
        usage_all.insert(("opencode-go".into(), "k1".into()), pu(Some(80), None, None));
        usage_all.insert(("deepseek".into(), "d1".into()), balance_ok(100.0));
        let mut usage_stale = HashMap::new();
        usage_stale.insert(("opencode-go".into(), "k1".into()), true);
        let usable = build_usable(&cfg, Some(100), &usage_all, &usage_stale);
        assert!(usable.get("opencode-go").unwrap().is_empty());
        assert_eq!(usable.get("deepseek"), Some(&vec!["d1".to_string()]));

        let order = vec!["opencode-go".to_string(), "deepseek".to_string()];
        let best = find_best(&usable, "opencode-go", "k1", &order);
        assert_eq!(best, Some(("deepseek".to_string(), "d1".to_string())));
    }

    #[test]
    fn find_best_prefers_same_provider_then_fallback() {
        let usable = HashMap::from([
            ("p1".to_string(), vec!["a".to_string(), "b".to_string()]),
            ("p2".to_string(), vec!["z".to_string()]),
        ]);
        let order = vec!["p1".to_string(), "p2".to_string()];
        // 在用 b → 同 provider 第一个 != b 的是 a
        assert_eq!(find_best(&usable, "p1", "b", &order), Some(("p1".to_string(), "a".to_string())));
        // 在用 a → p1 只剩 b
        assert_eq!(find_best(&usable, "p1", "a", &order), Some(("p1".to_string(), "b".to_string())));
        // 在用 key 不在 usable（已耗尽）→ 选 p1 第一个可用
        assert_eq!(find_best(&usable, "p1", "gone", &order), Some(("p1".to_string(), "a".to_string())));
    }

    #[test]
    fn find_best_cross_provider_follows_order() {
        let usable = HashMap::from([
            ("p1".to_string(), Vec::<String>::new()),
            ("p2".to_string(), vec!["z".to_string()]),
            ("p3".to_string(), vec!["y".to_string()]),
        ]);
        // 顺序 p3 在前 → 跨 provider 先看 p3
        let order = vec!["p3".to_string(), "p2".to_string()];
        assert_eq!(find_best(&usable, "p1", "a", &order), Some(("p3".to_string(), "y".to_string())));
        // 顺序里没有的 provider 跳过、全空 → None
        let order2 = vec!["nope".to_string()];
        assert_eq!(find_best(&usable, "p1", "a", &order2), None);
    }
}

