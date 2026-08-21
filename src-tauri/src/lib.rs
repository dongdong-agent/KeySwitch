//! KeySwitch (Rust/Tauri 2) 主入口：窗口 + 托盘 + 命令注册

mod adapters;
mod commands;
mod models;
mod smart;
mod usage;

use tauri::{
    menu::{Menu, MenuItem},
    tray::{MouseButton, TrayIconBuilder, TrayIconEvent},
    Manager,
};
use std::sync::atomic::{AtomicU64, Ordering};
use std::time::{Duration, SystemTime, UNIX_EPOCH};

/// 上次自动智能切换的时间戳（unix 秒，进程内）
static LAST_AUTO_SWITCH: AtomicU64 = AtomicU64::new(0);

fn unix_now() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs()
}

/// 自动切换运行日志：%APPDATA%/KeySwitch/auto-switch.log
/// 每次自动检测落一行，便于确认定时器确实在跑
fn log_auto_switch(line: &str) {
    let path = models::config_path()
        .parent()
        .unwrap_or_else(|| std::path::Path::new("."))
        .join("auto-switch.log");
    let now = unix_now();
    let days = now / 86400;
    let secs = now % 86400;
    let (h, m, s) = (secs / 3600, (secs % 3600) / 60, secs % 60);
    if let Some(parent) = path.parent() {
        let _ = std::fs::create_dir_all(parent);
    }
    if let Ok(mut f) = std::fs::OpenOptions::new().create(true).append(true).open(&path) {
        use std::io::Write;
        let _ = writeln!(f, "[t+{days}d {h:02}:{m:02}:{s:02}] {line}");
    }
}

#[tauri::command]
fn version() -> String {
    format!("KeySwitch v{}", env!("CARGO_PKG_VERSION"))
}

/// 刷新托盘菜单（用量快照 + 智能切换状态）
fn refresh_tray<R: tauri::Runtime>(app: &tauri::AppHandle<R>) {
    let Some(tray) = app.tray_by_id("main") else {
        return;
    };
    let cfg = models::load_config().unwrap_or_default();

    let mut items: Vec<Box<dyn tauri::menu::IsMenuItem<R>>> = Vec::new();
    // 打开主窗口（默认项）
    if let Ok(open) = MenuItem::with_id(app, "show", "打开 KeySwitch 主窗口", true, None::<&str>) {
        items.push(Box::new(open));
    }
    if let Ok(sep) = MenuItem::with_id(app, "sep1", "-", false, None::<&str>) {
        items.push(Box::new(sep));
    }
    // 用量快照（走批量+缓存，托盘刷新低频，阻塞主线程可接受）
    for (_provider, id, _note, u) in usage::get_usage_batch(&cfg, false) {
        let text = format!("  {id}: {} [{st}]", u.detail, st = u.status);
        if let Ok(mi) = MenuItem::with_id(app, format!("st-{id}"), text, false, None::<&str>) {
            items.push(Box::new(mi));
        }
    }
    let auto_state = if cfg.auto_switch.enabled { "开" } else { "关" };
    if let Ok(mi) = MenuItem::with_id(
        app,
        "auto",
        format!("  智能切换: {auto_state} (阈值 {}% / {}分钟)", cfg.auto_switch.trigger_percent, cfg.auto_switch.interval_min),
        false,
        None::<&str>,
    ) {
        items.push(Box::new(mi));
    }
    if let Ok(sep2) = MenuItem::with_id(app, "sep2", "-", false, None::<&str>) {
        items.push(Box::new(sep2));
    }
    if let Ok(refresh) = MenuItem::with_id(app, "refresh", "刷新状态", true, None::<&str>) {
        items.push(Box::new(refresh));
    }
    if let Ok(quit) = MenuItem::with_id(app, "quit", "退出", true, None::<&str>) {
        items.push(Box::new(quit));
    }

    let item_refs: Vec<&dyn tauri::menu::IsMenuItem<R>> =
        items.iter().map(|b| b.as_ref()).collect();
    if let Ok(menu) = Menu::with_items(app, &item_refs) {
        let _ = tray.set_menu(Some(menu));
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![
            version,
            commands::get_config,
            commands::save_config_front,
            commands::get_status,
            commands::get_actual_keys,
            commands::list_adapters,
            commands::apply_targets,
            commands::use_key,
            commands::smart_check,
            commands::save_auto_settings,
            commands::add_provider,
            commands::delete_provider,
            commands::add_key,
            commands::edit_key,
            commands::delete_key,
            commands::move_key,
            commands::add_target,
            commands::delete_target,
            commands::open_path,
        ])
        .setup(|app| {
            // 托盘
            let _ = TrayIconBuilder::with_id("main")
                .icon(app.default_window_icon().unwrap().clone())
                .show_menu_on_left_click(false)
                .on_menu_event(|app, event| match event.id.as_ref() {
                    "show" => {
                        if let Some(w) = app.get_webview_window("main") {
                            let _ = w.show();
                            let _ = w.unminimize();
                            let _ = w.set_focus();
                        }
                    }
                    "refresh" => refresh_tray(app),
                    "quit" => app.exit(0),
                    _ => {}
                })
                .on_tray_icon_event(|tray, event| {
                    if let TrayIconEvent::Click {
                        button: MouseButton::Left,
                        button_state: tauri::tray::MouseButtonState::Up,
                        ..
                    } = event
                    {
                        let app = tray.app_handle();
                        if let Some(w) = app.get_webview_window("main") {
                            let _ = w.show();
                            let _ = w.unminimize();
                            let _ = w.set_focus();
                        }
                    }
                })
                .build(app);
            refresh_tray(app.handle());

            // 自动智能切换定时器：每 30 秒 tick 一次，按配置 interval_min 决定是否执行
            // （interval 可在 UI 动态修改，故每轮重新读配置；enabled=false 时跳过）
            let app_handle = app.handle().clone();
            std::thread::spawn(move || loop {
                std::thread::sleep(Duration::from_secs(30));
                let cfg = match models::load_config() {
                    Ok(c) => c,
                    Err(_) => continue,
                };
                if !cfg.auto_switch.enabled {
                    continue;
                }
                let interval_secs = cfg.auto_switch.interval_min.max(1) * 60;
                let now = unix_now();
                let last = LAST_AUTO_SWITCH.load(Ordering::Relaxed);
                if now.saturating_sub(last) < interval_secs {
                    continue;
                }
                // 执行一次智能切换（重新 load 拿最新配置）
                let mut cfg2 = match models::load_config() {
                    Ok(c) => c,
                    Err(_) => continue,
                };
                let r = smart::smart_switch_once(&mut cfg2, None);
                if !r.switches.is_empty() {
                    let _ = models::save_config(&cfg2);
                    refresh_tray(&app_handle);
                }
                LAST_AUTO_SWITCH.store(now, Ordering::Relaxed);
                log_auto_switch(&format!(
                    "自动检测: 检查 {} 个在用 key, 切换 {} 个, 耗尽 {}",
                    r.checked,
                    r.switches.len(),
                    if r.exhausted.is_empty() {
                        "无".to_string()
                    } else {
                        r.exhausted.join(",")
                    }
                ));
            });

            Ok(())
        })
        .on_window_event(|window, event| {
            // 关闭窗口 = 隐藏到托盘（不退出）
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                if window.label() == "main" {
                    let _ = window.hide();
                    api.prevent_close();
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
