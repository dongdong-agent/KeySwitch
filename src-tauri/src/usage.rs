//! 用量查询：opencode-go /usage（percent 型）与 DeepSeek /user/balance（balance 型）

use crate::models::{Config, Provider};
use serde::Serialize;
use std::collections::HashMap;
use std::sync::{LazyLock, Mutex};
use std::time::{Duration, Instant};

#[derive(Serialize, Clone, Default)]
pub struct UsageInfo {
    pub kind: String, // "percent" | "balance"
    pub percent: Option<u64>,
    pub weekly: Option<u64>,
    pub monthly: Option<u64>,
    pub balance: Option<f64>,
    pub status: String, // ok | error | disabled
    pub detail: String,
}

/// 用量缓存 TTL：用量（滚动/周/月）短期几乎不变，避免每次刷新/切页都重新 HTTP。
/// 5 分钟：进页/自动刷新多数直接命中缓存，只在主动点「刷新」或缓存过期时才打远程。
const CACHE_TTL: Duration = Duration::from_secs(300);

type CacheKey = (String, String); // (provider, key_id)

/// 全局用量缓存：key -> (最近查询时间, 结果)
static USAGE_CACHE: LazyLock<Mutex<HashMap<CacheKey, (Instant, UsageInfo)>>> =
    LazyLock::new(|| Mutex::new(HashMap::new()));

/// 读取缓存（未过期则命中）
fn cache_get(k: &CacheKey) -> Option<UsageInfo> {
    let c = USAGE_CACHE.lock().ok()?;
    let (t, v) = c.get(k)?;
    if t.elapsed() < CACHE_TTL {
        Some(v.clone())
    } else {
        None
    }
}

fn cache_set(k: CacheKey, v: UsageInfo) {
    if let Ok(mut c) = USAGE_CACHE.lock() {
        // 查询失败(403/网络错误)时保留最近一次成功数据，避免污染缓存
        if v.status == "error" {
            if let Some((_, old)) = c.get(&k) {
                if old.status != "error" {
                    return;
                }
            }
        }
        c.insert(k, (Instant::now(), v));
    }
}

/// 批量查询所有 key 的用量（并行 + 缓存）。
/// force=true 时强制绕过缓存重新查询；返回 (provider, key_id, note, usage)。
pub fn get_usage_batch(cfg: &Config, force: bool) -> Vec<(String, String, String, UsageInfo)> {
    // 1) 收集所有 key + 决定是否需真查
    let mut jobs: Vec<(String, String, Provider, String)> = Vec::new(); // (provider,id,pcfg,key)
    let mut out: Vec<(String, String, String, UsageInfo)> = Vec::new();
    for (pname, pcfg) in &cfg.providers {
        for k in &pcfg.keys {
            let ck = (pname.clone(), k.id.clone());
            if !force {
                if let Some(hit) = cache_get(&ck) {
                    out.push((pname.clone(), k.id.clone(), k.note.clone(), hit));
                    continue;
                }
            }
            if !k.key.is_empty() {
                jobs.push((pname.clone(), k.id.clone(), pcfg.clone(), k.key.clone()));
            } else {
                out.push((pname.clone(), k.id.clone(), k.note.clone(), UsageInfo {
                    kind: pcfg.usage_type.clone(), percent: None, weekly: None, monthly: None, balance: None,
                    status: "disabled".into(), detail: "未配置 key".into(),
                }));
            }
        }
    }

    // 2) 并行查询（每个 key 一个线程，避免串行累计超时），结果写回缓存
    if !jobs.is_empty() {
        let results: Mutex<Vec<(String, String, UsageInfo)>> = Mutex::new(Vec::new());
        std::thread::scope(|s| {
            let results = &results;
            for (pname, id, pcfg, key) in jobs {
                s.spawn(move || {
                    let u = query_usage(&pcfg, &key);
                    cache_set((pname.clone(), id.clone()), u.clone());
                    if let Ok(mut r) = results.lock() {
                        r.push((pname, id, u));
                    }
                });
            }
        });
        // 3) 合并新查询结果（顺序不影响展示）
        let drained: Vec<(String, String, UsageInfo)> = {
            let mut r = results.lock().unwrap_or_else(|e| e.into_inner());
            r.drain(..).collect()
        };
        for (pname, id, u) in drained {
            let note = cfg.providers
                .get(&pname)
                .and_then(|p| p.keys.iter().find(|k| k.id == id))
                .map(|k| k.note.clone())
                .unwrap_or_default();
            out.push((pname, id, note, u));
        }
    }
    out
}

/// 清空用量缓存（强制全部重新查询用；保留接口备用）
#[allow(dead_code)] // 备用：清空用量缓存
pub fn clear_usage_cache() {
    if let Ok(mut c) = USAGE_CACHE.lock() {
        c.clear();
    }
}

/// 全局共享 HTTP Agent：复用连接池（keep-alive），
/// 避免每次用量刷新都重建 TCP/TLS 连接（多次连续查询 / 智能切换时收益明显）。
/// 超时 8s：用量接口通常 <2s，慢/挂的远端快速降级，不拖累整体。
static AGENT: LazyLock<ureq::Agent> = LazyLock::new(|| {
    ureq::AgentBuilder::new()
        .timeout(Duration::from_secs(8))
        .build()
});

fn agent() -> &'static ureq::Agent {
    &AGENT
}

pub fn query_usage(pcfg: &Provider, key: &str) -> UsageInfo {
    if pcfg.usage_type == "balance" {
        query_balance(pcfg, key)
    } else {
        query_percent(pcfg, key)
    }
}

/// 带缓存的用量查询：命中（未过期）直接返回缓存，否则真实查询并回填。
/// 查询失败时回退到最近一次成功数据（若有），避免 403 导致无法判定。
/// 供智能切换等多次查询场景复用，避免重复 HTTP（用量短期几乎不变）。
pub fn query_usage_cached(provider: &str, id: &str, pcfg: &Provider, key: &str) -> UsageInfo {
    let ck = (provider.to_string(), id.to_string());
    if let Some(u) = cache_get(&ck) {
        return u;
    }
    let u = query_usage(pcfg, key);
    if u.status == "error" {
        // 本次查询失败：回退最近一次成功数据，保证判定有据可依
        if let Ok(c) = USAGE_CACHE.lock() {
            if let Some((_, old)) = c.get(&ck) {
                if old.status != "error" {
                    return old.clone();
                }
            }
        }
    }
    cache_set(ck, u.clone());
    u
}

fn query_balance(pcfg: &Provider, key: &str) -> UsageInfo {
    let url = format!("{}/user/balance", pcfg.base_url.trim_end_matches('/'));
    let req = agent().get(&url).set("Authorization", &format!("Bearer {key}"));
    match req.call() {
        Ok(resp) => match resp.into_json::<serde_json::Value>() {
            Ok(d) => {
                let infos = d.get("balance_infos").and_then(|v| v.as_array()).cloned().unwrap_or_default();
                let total: f64 = infos
                    .iter()
                    .filter_map(|i| i.get("total_balance").and_then(|b| b.as_str()))
                    .filter_map(|s| s.parse::<f64>().ok())
                    .sum();
                let avail = d.get("is_available").and_then(|v| v.as_bool()).unwrap_or(true);
                UsageInfo {
                    kind: "balance".into(),
                    percent: None, weekly: None, monthly: None,
                    balance: Some(total),
                    status: if avail { "ok".into() } else { "disabled".into() },
                    detail: format!("余额 ¥{total:.2}"),
                }
            }
            Err(_) => UsageInfo { kind: "balance".into(), percent: None, weekly: None, monthly: None, balance: None, status: "error".into(), detail: "解析失败".into() },
        },
        Err(e) => UsageInfo {
            kind: "balance".into(),
            percent: None, weekly: None, monthly: None,
            balance: None,
            status: "error".into(),
            detail: format!("查询失败: {e}"),
        },
    }
}

fn query_percent(pcfg: &Provider, key: &str) -> UsageInfo {
    let url = format!("{}/usage", pcfg.base_url.trim_end_matches('/'));
    let req = agent().get(&url).set("Authorization", &format!("Bearer {key}"));
    match req.call() {
        Ok(resp) => match resp.into_json::<serde_json::Value>() {
            Ok(d) => {
                let usage = d.get("usage").cloned().unwrap_or_default();
                let rolling = usage.get("rolling").cloned().unwrap_or_default();
                let pct = rolling.get("percent").and_then(|v| v.as_u64());
                let st = rolling.get("status").and_then(|v| v.as_str()).unwrap_or("ok").to_string();
                let weekly = usage.get("weekly").and_then(|v| v.get("percent")).and_then(|v| v.as_u64());
                let monthly = usage.get("monthly").and_then(|v| v.get("percent")).and_then(|v| v.as_u64());
                let detail = format!(
                    "滚动{}% / 周{}% / 月{}%",
                    pct.map(|p| p.to_string()).unwrap_or_else(|| "?".into()),
                    weekly.map(|p| p.to_string()).unwrap_or_else(|| "?".into()),
                    monthly.map(|p| p.to_string()).unwrap_or_else(|| "?".into())
                );
                UsageInfo {
                    kind: "percent".into(),
                    percent: pct,
                    weekly,
                    monthly,
                    balance: None,
                    status: st,
                    detail,
                }
            }
            Err(_) => UsageInfo { kind: "percent".into(), percent: None, weekly: None, monthly: None, balance: None, status: "error".into(), detail: "解析失败".into() },
        },
        Err(e) => UsageInfo {
            kind: "percent".into(),
            percent: None, weekly: None, monthly: None,
            balance: None,
            status: "error".into(),
            detail: format!("查询失败: {e}"),
        },
    }
}

/// 是否判定为「耗尽/不可用」。trigger_percent 覆盖（智能切换用，默认 100）。
pub fn is_exhausted(
    cfg: &crate::models::Config,
    provider: &str,
    usage: &UsageInfo,
    trigger_percent: Option<u64>,
) -> bool {
    if usage.status == "error" || usage.status == "disabled" {
        return true;
    }
    if usage.kind == "balance" {
        let min = cfg
            .thresholds
            .as_ref()
            .and_then(|t| t.get(provider))
            .and_then(|v| v.get("balance_min"))
            .and_then(|v| v.as_f64())
            .unwrap_or(5.0);
        return usage.balance.unwrap_or(999.0) < min;
    }
    // 滚动 / 周 / 月 任一维度达到阈值 → 判定耗尽（用户要求：三个都看）
    let pct = usage.percent;
    let weekly = usage.weekly;
    let monthly = usage.monthly;
    let max_pct = [pct, weekly, monthly].iter().flatten().max().copied();
    let limit = trigger_percent.unwrap_or_else(|| {
        cfg.thresholds
            .as_ref()
            .and_then(|t| t.get(provider))
            .and_then(|v| v.get("percent"))
            .and_then(|v| v.as_u64())
            .unwrap_or(90)
    });
    match max_pct {
        Some(p) => p >= limit,
        None => true,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::models::Config;

    fn pu(p: Option<u64>, w: Option<u64>, m: Option<u64>) -> UsageInfo {
        UsageInfo {
            kind: "percent".into(),
            percent: p,
            weekly: w,
            monthly: m,
            balance: None,
            status: "ok".into(),
            detail: "x".into(),
        }
    }

    #[test]
    fn any_dimension_reaching_threshold_triggers() {
        let cfg = Config::default(); // 默认 percent 阈值 90
        // 仅「周」达到 100 → 判定耗尽（用户要求三维度任一）
        assert!(is_exhausted(&cfg, "p", &pu(None, Some(100), None), None));
        // 仅「月」达到 95 → 判定耗尽
        assert!(is_exhausted(&cfg, "p", &pu(None, None, Some(95)), None));
        // 滚动 95 → 判定耗尽
        assert!(is_exhausted(&cfg, "p", &pu(Some(95), Some(10), Some(10)), None));
        // 三维都低 → 不耗尽
        assert!(!is_exhausted(&cfg, "p", &pu(Some(20), Some(30), Some(50)), None));
        // 有维度为 None 时取其余最大值
        assert!(!is_exhausted(&cfg, "p", &pu(None, Some(40), None), None));
    }

    #[test]
    fn trigger_percent_overrides_default_threshold() {
        let cfg = Config::default();
        // 默认阈值 90，故 80 不触发
        assert!(!is_exhausted(&cfg, "p", &pu(Some(80), None, None), None));
        // 手动覆盖阈值 70 → 80 触发
        assert!(is_exhausted(&cfg, "p", &pu(Some(80), None, None), Some(70)));
    }

    #[test]
    fn balance_below_min_is_exhausted() {
        let cfg = Config::default();
        let b = |v: f64| UsageInfo {
            kind: "balance".into(),
            percent: None,
            weekly: None,
            monthly: None,
            balance: Some(v),
            status: "ok".into(),
            detail: "".into(),
        };
        assert!(is_exhausted(&cfg, "p", &b(1.0), None)); // 1 < 5
        assert!(!is_exhausted(&cfg, "p", &b(100.0), None));
    }

    #[test]
    fn error_and_disabled_always_exhausted() {
        let cfg = Config::default();
        let mut e = pu(Some(10), None, None);
        e.status = "error".into();
        assert!(is_exhausted(&cfg, "p", &e, None));
        let mut d = pu(Some(10), None, None);
        d.status = "disabled".into();
        assert!(is_exhausted(&cfg, "p", &d, None));
    }
}
