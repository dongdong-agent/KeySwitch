#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""KeySwitch v3 - 主窗口（左侧选项卡 + 右侧操作区，OneWork 风格）

左侧导航（深色）：总览 / Key 配置 / Provider / Key 池 / 应用 / 设置
右侧内容区（浅色）：各页面独立操作区，切换即时刷新。

配色参考 OneWork：主紫 #7c3aed、导航深底 #1e2433、内容浅底 #f8fafc。
"""
import os
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox

APP_DIR = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

import keyhub

LOG_FILE = os.path.join(APP_DIR, "keyswitch.log")

# ---- OneWork 风格配色 ----
C_NAV = "#1e2433"          # 左侧导航底色
C_NAV_TEXT = "#94a3b8"     # 导航文字（未选中）
C_NAV_HOVER = "#2b3448"
C_NAV_ACTIVE = "#7c3aed"   # 选中项（主紫）
C_BG = "#f8fafc"           # 内容区底色
C_CARD = "#ffffff"
C_BORDER = "#e2e8f0"
C_TEXT = "#1e293b"
C_SUB = "#64748b"
C_OK = "#16a34a"
C_WARN = "#dc2626"


def _log(msg: str):
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")
    except Exception:
        pass


def _style(root):
    st = ttk.Style(root)
    try:
        st.theme_use("clam")
    except Exception:
        pass
    st.configure("TFrame", background=C_BG)
    st.configure("Card.TFrame", background=C_CARD)
    st.configure("TLabel", background=C_BG, foreground=C_TEXT, font=("Microsoft YaHei", 9))
    st.configure("Card.TLabel", background=C_CARD, foreground=C_TEXT, font=("Microsoft YaHei", 9))
    st.configure("Sub.TLabel", background=C_BG, foreground=C_SUB, font=("Microsoft YaHei", 8))
    st.configure("NavTitle.TLabel", background=C_NAV, foreground="#ffffff",
                 font=("Microsoft YaHei", 12, "bold"))
    st.configure("NavFooter.TLabel", background=C_NAV, foreground="#64748b",
                 font=("Microsoft YaHei", 8))
    st.configure("PageTitle.TLabel", background=C_BG, foreground=C_TEXT,
                 font=("Microsoft YaHei", 14, "bold"))
    st.configure("PageSub.TLabel", background=C_BG, foreground=C_SUB,
                 font=("Microsoft YaHei", 9))
    st.configure("Treeview", background=C_CARD, fieldbackground=C_CARD,
                 foreground=C_TEXT, rowheight=28, font=("Microsoft YaHei", 9))
    st.configure("Treeview.Heading", background="#eef2f7", foreground=C_TEXT,
                 font=("Microsoft YaHei", 9, "bold"))
    st.configure("TButton", font=("Microsoft YaHei", 9), padding=(10, 4))
    st.configure("Primary.TButton", background=C_NAV_ACTIVE, foreground="white",
                 font=("Microsoft YaHei", 9, "bold"))
    st.map("Primary.TButton", background=[("active", "#6d28d9")])
    st.configure("TCheckbutton", background=C_BG, font=("Microsoft YaHei", 9))
    st.configure("TCombobox", font=("Microsoft YaHei", 9))


class NavButton(tk.Button):
    """左侧导航按钮（扁平，选中紫色高亮）"""
    def __init__(self, master, text, command, **kw):
        super().__init__(master, text=text, command=command, bd=0, relief="flat",
                         bg=C_NAV, fg=C_NAV_TEXT, activebackground=C_NAV_ACTIVE,
                         activeforeground="#ffffff", anchor="w", padx=18, pady=9,
                         font=("Microsoft YaHei", 10), cursor="hand2", **kw)
        self._text = text
        self.bind("<Enter>", lambda e: self._hover(True))
        self.bind("<Leave>", lambda e: self._hover(False))

    def _hover(self, on):
        if self.cget("bg") == C_NAV_ACTIVE:
            return
        self.configure(bg=C_NAV_HOVER if on else C_NAV)

    def set_active(self, active):
        self.configure(bg=C_NAV_ACTIVE if active else C_NAV,
                       fg="#ffffff" if active else C_NAV_TEXT)


class KeySwitchApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("KeySwitch - API Key 管理")
        root.geometry("1120x660")
        root.minsize(960, 560)
        _style(root)

        self.cfg = keyhub.load_config()
        self.adapters = keyhub.build_adapters(self.cfg)
        self.providers = []
        self.targets = []
        self.vars = {}
        self.actual_labels = {}
        self.usage_labels = {}
        self.status_var = tk.StringVar(value="就绪")
        self._current_page = None
        self.nav_buttons = []

        self._build_layout()
        self.refresh_data()
        self._switch_page("overview")
        threading.Thread(target=self._auto_loop, daemon=True).start()

    # ================= 布局 =================
    def _build_layout(self):
        # 左侧导航
        self.nav = tk.Frame(self.root, bg=C_NAV, width=178)
        self.nav.pack(side="left", fill="y")
        self.nav.pack_propagate(False)

        ttk.Label(self.nav, text="🔑 KeySwitch", style="NavTitle.TLabel").pack(anchor="w", padx=18, pady=(22, 4))
        ttk.Label(self.nav, text="API Key 管理器", style="NavFooter.TLabel").pack(anchor="w", padx=18, pady=(0, 18))

        nav_items = [
            ("overview",  "📊  总览"),
            ("matrix",    "🔑  Key 配置"),
            ("providers", "🏷️   Provider"),
            ("keys",      "🔐  Key 池"),
            ("apps",      "📦  应用"),
            ("settings",  "⚙️   设置"),
        ]
        for pid, label in nav_items:
            btn = NavButton(self.nav, text=label, command=lambda p=pid: self._switch_page(p))
            btn.pack(fill="x")
            self.nav_buttons.append((pid, btn))
        ttk.Label(self.nav, text=f"v3.0  {time.strftime('%Y-%m')}", style="NavFooter.TLabel").pack(side="bottom", anchor="w", padx=18, pady=12)

        # 右侧内容区（页面堆栈）
        self.content = tk.Frame(self.root, bg=C_BG)
        self.content.pack(side="left", fill="both", expand=True)
        self.pages = {}
        for pid in ("overview", "matrix", "providers", "keys", "apps", "settings"):
            page = tk.Frame(self.content, bg=C_BG)
            self.pages[pid] = page

    def _switch_page(self, pid):
        self._current_page = pid
        for p, btn in self.nav_buttons:
            btn.set_active(p == pid)
        page = self.pages[pid]
        # 重建页面内容（保持简单可靠）
        for w in page.winfo_children():
            w.destroy()
        if pid == "overview":
            self._build_overview(page)
        elif pid == "matrix":
            self._build_matrix(page)
        elif pid == "providers":
            self._build_providers(page)
        elif pid == "keys":
            self._build_keys(page)
        elif pid == "apps":
            self._build_apps(page)
        else:
            self._build_settings(page)
        page.pack(fill="both", expand=True)
        for p in self.pages.values():
            if p is not page:
                p.pack_forget()

    # ================= 数据 =================
    def refresh_data(self):
        self.cfg = keyhub.load_config()
        self.adapters = keyhub.build_adapters(self.cfg)
        self.providers = keyhub.provider_names(self.cfg)
        self.targets = self.cfg.get("targets", [])

    def _page_header(self, page, title, subtitle=""):
        tk.Frame(page, bg=C_BG, height=12).pack()
        ttk.Label(page, text=title, style="PageTitle.TLabel").pack(anchor="w", padx=24)
        if subtitle:
            ttk.Label(page, text=subtitle, style="PageSub.TLabel").pack(anchor="w", padx=24, pady=(2, 10))
        else:
            tk.Frame(page, bg=C_BG, height=8).pack()

    # ================= 页面：总览 =================
    def _build_overview(self, page):
        self._page_header(page, "总览", "各 API Key 的用量 / 余额实时状态")
        self.usage_labels = {}
        grid = tk.Frame(page, bg=C_BG)
        grid.pack(fill="x", padx=24)
        statuses = keyhub.status_all(self.cfg)
        for i, s in enumerate(statuses):
            card = tk.Frame(grid, bg=C_CARD, highlightbackground=C_BORDER,
                            highlightthickness=1, padx=14, pady=12)
            card.grid(row=i // 2, column=i % 2, sticky="ew", padx=(0, 12), pady=6)
            grid.columnconfigure(i % 2, weight=1)
            tk.Label(card, text=f"{s['provider']} / {s['id']}", bg=C_CARD,
                     font=("Microsoft YaHei", 10, "bold"), fg=C_TEXT).pack(anchor="w")
            if s["usage"] is None:
                tk.Label(card, text="未配置", bg=C_CARD, fg=C_SUB).pack(anchor="w", pady=(4, 0))
            else:
                u = s["usage"]
                color = C_WARN if u["status"] in ("error", "disabled") else C_OK
                tk.Label(card, text=u["detail"], bg=C_CARD, fg=color,
                         font=("Microsoft YaHei", 10, "bold")).pack(anchor="w", pady=(4, 0))
                tk.Label(card, text=f"状态: {u['status']}  {s['note']}", bg=C_CARD,
                         fg=C_SUB, font=("Microsoft YaHei", 8)).pack(anchor="w")
            # ---- 手动切换按钮行 ----
            in_use = any(t.get("mapping", {}).get(s["provider"]) == s["id"]
                         for t in self.targets)
            btn_row = tk.Frame(card, bg=C_CARD)
            btn_row.pack(anchor="w", pady=(8, 0))
            if in_use:
                tk.Label(btn_row, text="✓ 使用中", bg=C_CARD, fg=C_OK,
                         font=("Microsoft YaHei", 8, "bold")).pack(side="left")
            else:
                tk.Button(btn_row, text="⚡ 使用此 key", bd=0, relief="flat",
                          bg="#eef2ff", fg=C_NAV_ACTIVE, activebackground=C_NAV_ACTIVE,
                          activeforeground="#ffffff", cursor="hand2",
                          font=("Microsoft YaHei", 8, "bold"), padx=8, pady=2,
                          command=lambda p=s["provider"], k=s["id"]: self._use_key(p, k)).pack(side="left")
            self.usage_labels[s["id"]] = card
        ttk.Button(page, text="🔄 刷新用量", style="Primary.TButton",
                   command=self.refresh_usage).pack(anchor="w", padx=24, pady=10)

        # ---- 智能切换卡片 ----
        auto = self.cfg.get("auto_switch", {})
        acard = tk.Frame(page, bg=C_CARD, highlightbackground=C_NAV_ACTIVE,
                         highlightthickness=1, padx=14, pady=10)
        acard.pack(fill="x", padx=24, pady=(0, 10))
        tk.Label(acard, text="⚡ 智能切换（用量耗尽自动换可用 key，按优先级）", bg=C_CARD,
                 fg=C_NAV_ACTIVE, font=("Microsoft YaHei", 10, "bold")).pack(anchor="w")
        self.auto_enabled = tk.BooleanVar(value=bool(auto.get("enabled", False)))
        ttk.Checkbutton(acard, text="启用智能切换：在用 key 达到阈值时，自动切换到优先级最高的可用 key",
                        variable=self.auto_enabled, command=self._save_auto_settings).pack(anchor="w", pady=(6, 2))
        row = tk.Frame(acard, bg=C_CARD)
        row.pack(anchor="w", pady=2)
        tk.Label(row, text="触发阈值(%)：", bg=C_CARD, fg=C_SUB).pack(side="left")
        self.auto_trigger = tk.StringVar(value=str(auto.get("trigger_percent", 100)))
        tk.Entry(row, textvariable=self.auto_trigger, width=6).pack(side="left", padx=(0, 16))
        tk.Label(row, text="检测间隔(分钟)：", bg=C_CARD, fg=C_SUB).pack(side="left")
        self.auto_interval = tk.StringVar(value=str(auto.get("interval_min", 5)))
        tk.Entry(row, textvariable=self.auto_interval, width=6).pack(side="left", padx=(0, 16))
        ttk.Button(row, text="保存设置", command=self._save_auto_settings).pack(side="left")
        bar2 = tk.Frame(acard, bg=C_CARD)
        bar2.pack(anchor="w", pady=(6, 2))
        self.auto_status = tk.Label(bar2, text="", bg=C_CARD, fg=C_SUB,
                                    font=("Microsoft YaHei", 8), width=52, anchor="w")
        self.auto_status.pack(side="left", padx=(0, 14))
        ttk.Button(bar2, text="立即检测并切换", command=self._smart_now).pack(side="left")
        self._set_auto_status()

        # 在用 key 概览
        tk.Frame(page, bg=C_BG, height=8).pack()
        ttk.Label(page, text="各软件当前配置", style="PageSub.TLabel").pack(anchor="w", padx=24)
        self._actual_summary(page)

    def _actual_summary(self, page):
        try:
            actual = keyhub.read_actual_all(self.cfg, self.adapters)
        except Exception:
            return
        for t in self.targets:
            name = t["name"]
            parts = []
            for p in self.providers:
                v = actual.get(name, {}).get(p, "")
                if v:
                    parts.append(f"{p}: {v[:5]}…{v[-4:]}")
            txt = "  |  ".join(parts) if parts else "(未配置)"
            row = tk.Frame(page, bg=C_BG)
            row.pack(fill="x", padx=24, pady=1)
            tk.Label(row, text=f"  {t.get('label', name)}", bg=C_BG, fg=C_TEXT,
                     font=("Microsoft YaHei", 9, "bold"), width=22, anchor="w").pack(side="left")
            tk.Label(row, text=txt, bg=C_BG, fg=C_SUB, anchor="w").pack(side="left")

    def refresh_usage(self):
        threading.Thread(target=self._usage_worker, daemon=True).start()

    # ---------- 手动切换（总览卡片上的“使用此 key”按钮） ----------
    def _use_key(self, provider, key_id):
        """把该 provider 下所有在用的软件统一切换到指定 key（自动切换失败时的手动兜底）"""
        targets = [t for t in self.targets if t.get("mapping", {}).get(provider)]
        if not targets:
            messagebox.showinfo("提示", f"当前没有软件在使用 {provider}，无需切换",
                                parent=self.root)
            return
        names = [t.get("label", t["name"]) for t in targets]
        ok = messagebox.askyesno(
            "确认切换",
            f"将把以下 {len(names)} 个软件切换到\n\n  {provider} / {key_id}\n\n" +
            "\n".join(f"  · {n}" for n in names) +
            "\n\n注意：相关软件需重启后才会使用新 key。\n继续吗？",
            parent=self.root)
        if not ok:
            return
        r = keyhub.use_key(self.cfg, self.adapters, provider, key_id)
        if r.get("error"):
            messagebox.showwarning("提示", r["error"], parent=self.root)
            return
        keyhub.save_config(self.cfg)
        _log(f"手动切换: {provider}/{key_id} → " + ", ".join(r["targets"]))
        lines = [f"✅ {t}" for t in r["targets"]] or ["（无软件在使用该 provider）"]
        restart_txt = "、".join(r["restart"]) if r["restart"] else "无"
        messagebox.showinfo(
            "切换完成",
            f"已切换到 {provider} / {key_id}\n\n" + "\n".join(lines) +
            f"\n\n⚠️ 需重启生效: {restart_txt}",
            parent=self.root)
        self.refresh_data()
        self._switch_page("overview")

    # ---------- 智能切换 ----------
    def _save_auto_settings(self):
        try:
            trigger = int(self.auto_trigger.get())
            interval = max(1, int(self.auto_interval.get()))
            if not (0 <= trigger <= 100):
                raise ValueError
        except ValueError:
            messagebox.showwarning("提示", "触发阈值需为 0-100 的数字，间隔为 ≥1 的整数", parent=self.root)
            return
        self.cfg.setdefault("auto_switch", {})
        self.cfg["auto_switch"].update({"enabled": self.auto_enabled.get(),
                                        "trigger_percent": trigger,
                                        "interval_min": interval})
        keyhub.save_config(self.cfg)
        _log(f"智能切换设置: 启用={self.auto_enabled.get()} 阈值={trigger}% 间隔={interval}分钟")
        self._set_auto_status()
        messagebox.showinfo("完成", f"智能切换已{'启用' if self.auto_enabled.get() else '停用'}\n"
                             f"触发阈值 {trigger}% · 检测间隔 {interval} 分钟", parent=self.root)

    def _set_auto_status(self, text=None):
        if not hasattr(self, "auto_status"):
            return
        if text is None:
            auto = self.cfg.get("auto_switch", {})
            state = "已启用" if auto.get("enabled") else "未启用"
            text = (f"状态: {state} ｜ 阈值 {auto.get('trigger_percent', 100)}% ｜ "
                    f"间隔 {auto.get('interval_min', 5)} 分钟")
        self.auto_status.configure(text=text)

    def _smart_now(self):
        if not hasattr(self, "auto_status"):
            return
        self.auto_status.configure(text="正在检测用量…")
        threading.Thread(target=self._smart_worker, daemon=True).start()

    def _smart_worker(self, silent=False):
        try:
            r = keyhub.smart_switch_once(self.cfg, self.adapters)
            if r["switches"]:
                keyhub.save_config(self.cfg)
        except Exception as e:
            _log(f"智能切换异常: {e}")
            self.root.after(0, lambda: self._set_auto_status(f"异常: {e}"))
            return

        def upd():
            self.refresh_data()
            self.refresh_actual()
            if r["switches"]:
                lines = [f"🔄 {s['provider']}: {s['from']} → {s['to']}"
                         f"（软件: {', '.join(s['targets']) or '无'}）"
                         for s in r["switches"]]
                self._set_auto_status("已切换: " + "; ".join(
                    f"{s['from']}→{s['to']}" for s in r["switches"]))
                _log("智能切换: " + " | ".join(lines))
                if not silent:
                    messagebox.showinfo(
                        "智能切换", "\n".join(lines) +
                        "\n\n注意：相关软件需重启后才会使用新 key", parent=self.root)
            elif r["exhausted"]:
                self._set_auto_status("告急但无可用 key: " + ", ".join(r["exhausted"]))
            else:
                self._set_auto_status(
                    f"检测完成：{r['checked']} 个在用 key 全部正常")

        self.root.after(0, upd)

    def _auto_loop(self):
        """后台智能切换线程：每 30 秒检查调度，enabled 且到间隔才执行"""
        self._last_auto = 0.0
        while True:
            time.sleep(30)
            try:
                cfg = keyhub.load_config()
                if not cfg.get("auto_switch", {}).get("enabled"):
                    continue
                interval = max(1, cfg["auto_switch"].get("interval_min", 5))
                if time.time() - self._last_auto < interval * 60:
                    continue
                self._last_auto = time.time()
                adapters = keyhub.build_adapters(cfg)
                r = keyhub.smart_switch_once(cfg, adapters)
                if r["switches"]:
                    keyhub.save_config(cfg)
                    sws = r["switches"]
                    _log("智能切换(自动): " + str([(s["provider"], s["from"], s["to"])
                                                   for s in sws]))
                    self.root.after(0, lambda: self._smart_worker(silent=True))
            except Exception as e:
                _log(f"[auto-loop] 异常: {e}")

    def _usage_worker(self):
        try:
            for s in keyhub.status_all(self.cfg):
                def upd(sid=s["id"], s_=s):
                    card = self.usage_labels.get(sid)
                    if not card:
                        return
                    for w in card.winfo_children():
                        if isinstance(w, tk.Label) and w.cget("font") == ("Microsoft YaHei", 10, "bold"):
                            if s_["usage"]:
                                u = s_["usage"]
                                w.configure(text=u["detail"],
                                            fg=C_WARN if u["status"] in ("error", "disabled") else C_OK)
                self.root.after(0, upd)
        except Exception:
            pass

    # ================= 页面：Key 配置（核心表格） =================
    def _build_matrix(self, page):
        self._page_header(page, "Key 配置",
                          "每个软件独立指定 Provider 用哪个 Key → 下拉选择 → 「保存并应用」")
        self.vars = {}
        self.actual_labels = {}

        box = tk.Frame(page, bg=C_CARD, highlightbackground=C_BORDER, highlightthickness=1)
        box.pack(fill="both", expand=True, padx=24, pady=4)

        # 表头
        tk.Label(box, text="软件", bg=C_CARD, font=("Microsoft YaHei", 9, "bold"),
                 fg=C_TEXT).grid(row=0, column=0, sticky="w", padx=10, pady=8)
        tk.Label(box, text="当前生效 key", bg=C_CARD, font=("Microsoft YaHei", 9, "bold"),
                 fg=C_TEXT).grid(row=0, column=1, sticky="w", padx=10, pady=8)
        for c, p in enumerate(self.providers, start=2):
            tk.Label(box, text=p, bg=C_CARD, font=("Microsoft YaHei", 9, "bold"),
                     fg=C_NAV_ACTIVE).grid(row=0, column=c, sticky="w", padx=10, pady=8)

        for r, t in enumerate(self.targets, start=1):
            name = t["name"]
            tk.Label(box, text=t.get("label", name), bg=C_CARD, fg=C_TEXT,
                     font=("Microsoft YaHei", 9)).grid(row=r, column=0, sticky="w", padx=10, pady=6)
            self.actual_labels[name] = tk.Label(box, text="…", bg=C_CARD, fg=C_SUB,
                                                font=("Microsoft YaHei", 8))
            self.actual_labels[name].grid(row=r, column=1, sticky="w", padx=10, pady=6)
            for c, p in enumerate(self.providers, start=2):
                cur = t.get("mapping", {}).get(p, "") or ""
                var = tk.StringVar(value=cur if cur else "__none__")
                self.vars[(name, p)] = var
                vals = keyhub.key_ids(self.cfg, p)
                disp = [v if v != "__none__" else "不使用" for v in (vals + ["__none__"])]
                cb = ttk.Combobox(box, textvariable=var, values=disp,
                                  state="readonly", width=14)
                cb.grid(row=r, column=c, sticky="w", padx=10, pady=4)

        if not self.targets:
            tk.Label(box, text="（还没有应用，去「📦 应用」页添加）", bg=C_CARD,
                     fg=C_SUB).grid(row=1, column=0, columnspan=3, padx=10, pady=12)

        # 按钮行
        bar = tk.Frame(page, bg=C_BG)
        bar.pack(fill="x", padx=24, pady=10)
        ttk.Button(bar, text="💾 保存并应用", style="Primary.TButton",
                   command=self.save_all).pack(side="left", padx=4)
        ttk.Button(bar, text="🔄 刷新实际状态", command=self.refresh_actual).pack(side="left", padx=4)
        tk.Label(bar, textvariable=self.status_var, fg=C_NAV_ACTIVE, bg=C_BG,
                 font=("Microsoft YaHei", 9)).pack(side="left", padx=14)

        self.refresh_actual()

    def save_all(self):
        new_mappings = {}
        for t in self.targets:
            name = t["name"]
            m = {}
            for p in self.providers:
                v = self.vars[(name, p)].get()
                m[p] = v if v and v != "__none__" else ""
            new_mappings[name] = m
        results = []
        restart = set()
        for t in self.targets:
            name = t["name"]
            old = dict(t.get("mapping", {}))
            new = new_mappings[name]
            changed = {p: kid for p, kid in new.items() if old.get(p, "") != kid}
            if not changed:
                results.append(f"[{t.get('label', name)}] 无变化")
                continue
            try:
                r = keyhub.apply_target(self.cfg, self.adapters, name, new)
                for res in r["results"]:
                    flag = "✅" if res["ok"] else "❌"
                    results.append(f"[{t.get('label', name)}] {res.get('provider', '')} {flag} {res['msg']}")
                restart.update(r["restart"])
            except Exception as e:
                results.append(f"[{t.get('label', name)}] ❌ {e}")
            t["mapping"] = new
        keyhub.save_config(self.cfg)
        self.status_var.set(f"已保存 {time.strftime('%H:%M:%S')}（{len(results)} 项）")
        _log("保存: " + " | ".join(results))
        self.refresh_actual()
        restart_txt = "、".join(sorted(restart)) if restart else "无"
        messagebox.showinfo("保存结果", "\n".join(results) + f"\n\n⚠️ 需重启生效: {restart_txt}")

    def refresh_actual(self):
        try:
            actual = keyhub.read_actual_all(self.cfg, self.adapters)
            for t in self.targets:
                name = t["name"]
                parts = []
                for p in self.providers:
                    v = actual.get(name, {}).get(p, "")
                    if v:
                        parts.append(f"{p}:{v[:5]}…{v[-4:]}")
                lbl = self.actual_labels.get(name)
                if lbl:
                    lbl.configure(text="  ".join(parts) if parts else "(未配置)",
                                  fg=C_TEXT if parts else C_SUB)
        except Exception as e:
            _log(f"读取实际 key 失败: {e}")

    # ================= 页面：Provider 管理 =================
    def _build_providers(self, page):
        self._page_header(page, "Provider 管理", "API 渠道：添加新渠道（如 Kimi / GLM / OpenRouter）")
        box = tk.Frame(page, bg=C_CARD, highlightbackground=C_BORDER, highlightthickness=1)
        box.pack(fill="both", expand=True, padx=24, pady=4)
        cols = ("provider", "base_url", "usage_type", "key_count", "threshold")
        tree = ttk.Treeview(box, columns=cols, show="headings", height=8)
        heads = {"provider": "Provider", "base_url": "Base URL", "usage_type": "用量类型",
                 "key_count": "Key 数", "threshold": "告急阈值"}
        for c in cols:
            tree.heading(c, text=heads[c])
            tree.column(c, width=200 if c == "base_url" else 90, anchor="w")
        tree.pack(fill="both", expand=True, padx=6, pady=6)
        for pname, pc in self.cfg.get("providers", {}).items():
            thr = self.cfg.get("thresholds", {}).get(pname, {})
            thr_txt = ", ".join(f"{k}={v}" for k, v in thr.items()) or "-"
            tree.insert("", "end", values=(pname, pc.get("base_url", ""),
                                           pc.get("usage_type", ""),
                                           len(pc.get("keys", [])), thr_txt))
        bar = tk.Frame(page, bg=C_BG)
        bar.pack(fill="x", padx=24, pady=8)
        ttk.Button(bar, text="➕ 添加 Provider", style="Primary.TButton",
                   command=self._dlg_add_provider).pack(side="left", padx=4)
        ttk.Button(bar, text="➖ 删除选中 Provider",
                   command=lambda: self._del_provider(tree)).pack(side="left", padx=4)
        ttk.Button(bar, text="🔄 刷新", command=lambda: self._switch_page("providers")).pack(side="left", padx=4)

    def _del_provider(self, tree):
        sel = tree.selection()
        if not sel:
            messagebox.showinfo("提示", "请先选中要删除的 Provider", parent=self.root)
            return
        name = tree.item(sel[0])["values"][0]
        if messagebox.askyesno("确认", f"删除 Provider「{name}」及其所有 key？", parent=self.root):
            ok, msg = keyhub.delete_provider(self.cfg, name)
            if ok:
                keyhub.save_config(self.cfg)
                _log(msg)
                self.refresh_data()
                self._switch_page("providers")
            else:
                messagebox.showwarning("提示", msg, parent=self.root)

    # ================= 页面：Key 池 =================
    def _build_keys(self, page):
        self._page_header(page, "Key 池", "所有 Provider 的 API Key 一览：排序 = 设置优先级（越靠上越优先，智能切换优先选用）")
        box = tk.Frame(page, bg=C_CARD, highlightbackground=C_BORDER, highlightthickness=1)
        box.pack(fill="both", expand=True, padx=24, pady=4)
        cols = ("prio", "provider", "id", "key", "note")
        tree = ttk.Treeview(box, columns=cols, show="headings", height=10)
        heads = {"prio": "优先级", "provider": "Provider", "id": "Key 标识",
                 "key": "Key（前缀…）", "note": "备注"}
        widths = {"prio": 70, "provider": 110, "id": 130, "key": 130, "note": 200}
        for c in cols:
            tree.heading(c, text=heads[c])
            tree.column(c, width=widths[c], anchor="w")
        tree.pack(fill="both", expand=True, padx=6, pady=6)
        for pname, pc in self.cfg.get("providers", {}).items():
            for i, k in enumerate(pc.get("keys", []), start=1):
                kv = k.get("key", "")
                disp = kv[:8] + "…" + kv[-4:] if kv else "(空)"
                tree.insert("", "end", values=(i, pname, k.get("id"), disp, k.get("note", "")))
        bar = tk.Frame(page, bg=C_BG)
        bar.pack(fill="x", padx=24, pady=6)
        ttk.Button(bar, text="➕ 添加 API Key", style="Primary.TButton",
                   command=self._dlg_add_key).pack(side="left", padx=4)
        ttk.Button(bar, text="➖ 删除选中 Key",
                   command=lambda: self._del_key(tree)).pack(side="left", padx=4)
        bar2 = tk.Frame(page, bg=C_BG)
        bar2.pack(fill="x", padx=24, pady=(0, 6))
        ttk.Button(bar2, text="↑ 提高优先级（前移）",
                   command=lambda: self._move_key(tree, "up")).pack(side="left", padx=4)
        ttk.Button(bar2, text="↓ 降低优先级（后移）",
                   command=lambda: self._move_key(tree, "down")).pack(side="left", padx=4)
        ttk.Button(bar2, text="🔄 刷新",
                   command=lambda: self._switch_page("keys")).pack(side="left", padx=4)
        ttk.Label(page, text="说明：选中某个 Key 后点 ↑↓ 调整优先级；智能切换时优先选用排在前面的可用 key（同一 Provider 内比较）",
                  style="Sub.TLabel").pack(anchor="w", padx=24, pady=(0, 4))

    def _move_key(self, tree, direction):
        sel = tree.selection()
        if not sel:
            messagebox.showinfo("提示", "请先选中要调整的 Key", parent=self.root)
            return
        vals = tree.item(sel[0])["values"]
        provider, kid = vals[1], vals[2]
        ok, msg = keyhub.move_key(self.cfg, provider, kid, direction)
        if ok:
            keyhub.save_config(self.cfg)
            _log(msg)
            self.refresh_data()
            self._switch_page("keys")
        else:
            messagebox.showwarning("提示", msg, parent=self.root)

    def _del_key(self, tree):
        sel = tree.selection()
        if not sel:
            messagebox.showinfo("提示", "请先选中要删除的 Key", parent=self.root)
            return
        vals = tree.item(sel[0])["values"]
        provider, kid = vals[0], vals[1]
        if messagebox.askyesno("确认", f"删除 {provider}/{kid}？（引用它的应用会自动改为不使用）", parent=self.root):
            ok, msg = keyhub.delete_key(self.cfg, provider, kid)
            if ok:
                keyhub.save_config(self.cfg)
                _log(msg)
                self.refresh_data()
                self._switch_page("keys")
            else:
                messagebox.showwarning("提示", msg, parent=self.root)

    # ================= 页面：应用管理 =================
    def _build_apps(self, page):
        self._page_header(page, "应用管理", "把新软件接入管理：选适配器 → 指定用哪个 Key")
        box = tk.Frame(page, bg=C_CARD, highlightbackground=C_BORDER, highlightthickness=1)
        box.pack(fill="both", expand=True, padx=24, pady=4)
        cols = ("name", "label", "adapter", "mapping")
        tree = ttk.Treeview(box, columns=cols, show="headings", height=8)
        heads = {"name": "标识", "label": "显示名", "adapter": "适配器", "mapping": "映射"}
        for c in cols:
            tree.heading(c, text=heads[c])
            tree.column(c, width=90 if c in ("name", "adapter") else 200, anchor="w")
        tree.pack(fill="both", expand=True, padx=6, pady=6)
        for t in self.targets:
            m = t.get("mapping", {})
            m_txt = ", ".join(f"{p}={kid}" for p, kid in m.items() if kid) or "(未指定)"
            tree.insert("", "end", values=(t["name"], t.get("label", ""),
                                           t.get("adapter", ""), m_txt))
        bar = tk.Frame(page, bg=C_BG)
        bar.pack(fill="x", padx=24, pady=8)
        ttk.Button(bar, text="➕ 添加应用", style="Primary.TButton",
                   command=self._dlg_add_app).pack(side="left", padx=4)
        ttk.Button(bar, text="➖ 删除选中应用",
                   command=lambda: self._del_app(tree)).pack(side="left", padx=4)
        ttk.Button(bar, text="🔄 刷新", command=lambda: self._switch_page("apps")).pack(side="left", padx=4)
        ttk.Label(page, text="适配器说明：pi=pi工具 / env_var=环境变量 / openchatcut / workbuddy / codex=codex-router / file_json=JSON文件 / file_env=.env文件 / file_regex=正则替换",
                  style="Sub.TLabel", wraplength=1000, justify="left").pack(anchor="w", padx=24, pady=(2, 6))

    def _del_app(self, tree):
        sel = tree.selection()
        if not sel:
            messagebox.showinfo("提示", "请先选中要删除的应用", parent=self.root)
            return
        name = tree.item(sel[0])["values"][0]
        if messagebox.askyesno("确认", f"删除应用「{name}」？（只移除管理，不删除软件配置）", parent=self.root):
            ok, msg = keyhub.delete_target(self.cfg, name)
            if ok:
                keyhub.save_config(self.cfg)
                _log(msg)
                self.refresh_data()
                self._switch_page("apps")
            else:
                messagebox.showwarning("提示", msg, parent=self.root)

    # ================= 页面：设置 =================
    def _build_settings(self, page):
        self._page_header(page, "设置", "配置文件、日志与使用说明")
        card = tk.Frame(page, bg=C_CARD, highlightbackground=C_BORDER, highlightthickness=1)
        card.pack(fill="x", padx=24, pady=4)
        tk.Label(card, text="配置文件：", bg=C_CARD, fg=C_TEXT,
                 font=("Microsoft YaHei", 9, "bold")).pack(anchor="w", padx=12, pady=(10, 0))
        tk.Label(card, text=keyhub.CONFIG_PATH, bg=C_CARD, fg=C_SUB,
                 font=("Microsoft YaHei", 9)).pack(anchor="w", padx=12)
        tk.Label(card, text="日志文件：", bg=C_CARD, fg=C_TEXT,
                 font=("Microsoft YaHei", 9, "bold")).pack(anchor="w", padx=12, pady=(8, 0))
        tk.Label(card, text=LOG_FILE, bg=C_CARD, fg=C_SUB,
                 font=("Microsoft YaHei", 9)).pack(anchor="w", padx=12)
        tk.Label(card, text="使用指南：", bg=C_CARD, fg=C_TEXT,
                 font=("Microsoft YaHei", 9, "bold")).pack(anchor="w", padx=12, pady=(8, 0))
        tk.Label(card, text=os.path.join(APP_DIR, "USE_GUIDE.md"), bg=C_CARD, fg=C_SUB,
                 font=("Microsoft YaHei", 9)).pack(anchor="w", padx=12, pady=(0, 10))
        bar = tk.Frame(page, bg=C_BG)
        bar.pack(fill="x", padx=24, pady=10)
        ttk.Button(bar, text="📂 打开配置目录", command=self._open_cfg_dir).pack(side="left", padx=4)
        ttk.Button(bar, text="📄 打开日志", command=self._open_log).pack(side="left", padx=4)
        ttk.Button(bar, text="❓ 打开使用指南", command=self._open_guide).pack(side="left", padx=4)

    # ================= 对话框（复用） =================
    def _dlg_add_provider(self):
        dlg = tk.Toplevel(self.root)
        dlg.title("添加 Provider")
        dlg.geometry("480x280")
        dlg.transient(self.root)
        dlg.grab_set()
        tk.Label(dlg, text="Provider 标识（英文，如 kimi / glm / openrouter）：").pack(anchor="w", padx=14, pady=(12, 2))
        e_name = tk.Entry(dlg, width=42)
        e_name.pack(anchor="w", padx=14)
        tk.Label(dlg, text="Base URL（如 https://api.kimi.com/v1）：").pack(anchor="w", padx=14, pady=(8, 2))
        e_url = tk.Entry(dlg, width=42)
        e_url.pack(anchor="w", padx=14)
        tk.Label(dlg, text="用量类型：").pack(anchor="w", padx=14, pady=(8, 2))
        v_type = tk.StringVar(value="percent")
        frm = tk.Frame(dlg)
        frm.pack(anchor="w", padx=14)
        tk.Radiobutton(frm, text="百分比限额 (percent, 查 /usage)", variable=v_type, value="percent").pack(side="left")
        tk.Radiobutton(frm, text="余额 (balance, 查 /user/balance)", variable=v_type, value="balance").pack(side="left", padx=10)
        tk.Label(dlg, text="告急阈值：percent 填 0-100（默认90）；balance 填金额下限（默认5）").pack(anchor="w", padx=14, pady=(8, 2))
        e_thr = tk.Entry(dlg, width=12)
        e_thr.pack(anchor="w", padx=14)
        e_thr.insert(0, "90")

        def ok():
            name = e_name.get().strip()
            if not name:
                messagebox.showwarning("提示", "Provider 标识不能为空", parent=dlg)
                return
            thr = e_thr.get().strip()
            threshold = {"percent": int(thr)} if v_type.get() == "percent" and thr else \
                        {"balance_min": float(thr)} if v_type.get() == "balance" and thr else None
            ok, msg = keyhub.add_provider(self.cfg, name, e_url.get().strip(), v_type.get(), threshold)
            if ok:
                keyhub.save_config(self.cfg)
                _log(msg)
                dlg.destroy()
                self.refresh_data()
                self._switch_page("providers")
                messagebox.showinfo("完成", msg + "\n接着去「🔐 Key 池」页添加 key", parent=self.root)
            else:
                messagebox.showwarning("提示", msg, parent=dlg)

        tk.Button(dlg, text="确定", width=10, command=ok).pack(pady=(14, 4))
        tk.Button(dlg, text="取消", width=10, command=dlg.destroy).pack()

    def _dlg_add_key(self):
        if not self.providers:
            messagebox.showwarning("提示", "还没有 Provider，请先添加", parent=self.root)
            return
        dlg = tk.Toplevel(self.root)
        dlg.title("添加 API Key")
        dlg.geometry("500x260")
        dlg.transient(self.root)
        dlg.grab_set()
        tk.Label(dlg, text="所属 Provider：").pack(anchor="w", padx=14, pady=(12, 2))
        v_provider = tk.StringVar(value=self.providers[0])
        ttk.Combobox(dlg, textvariable=v_provider, values=self.providers,
                     state="readonly", width=36).pack(anchor="w", padx=14)
        tk.Label(dlg, text="Key 标识（自动建议，可改）：").pack(anchor="w", padx=14, pady=(8, 2))
        e_id = tk.Entry(dlg, width=40)
        nxt = len(keyhub.key_ids(self.cfg, self.providers[0])) + 1
        e_id.insert(0, f"{self.providers[0]}-{nxt}")
        e_id.pack(anchor="w", padx=14)
        tk.Label(dlg, text="API Key 值：").pack(anchor="w", padx=14, pady=(8, 2))
        e_key = tk.Entry(dlg, width=54)
        e_key.pack(anchor="w", padx=14)
        tk.Label(dlg, text="备注（如：谁在用/用途）：").pack(anchor="w", padx=14, pady=(8, 2))
        e_note = tk.Entry(dlg, width=40)
        e_note.pack(anchor="w", padx=14)

        def ok():
            kid = e_id.get().strip()
            kv = e_key.get().strip()
            if not kid or not kv:
                messagebox.showwarning("提示", "Key 标识和值不能为空", parent=dlg)
                return
            ok, msg = keyhub.add_key(self.cfg, v_provider.get(), kid, kv, e_note.get().strip())
            if ok:
                keyhub.save_config(self.cfg)
                _log(msg)
                dlg.destroy()
                self.refresh_data()
                self._switch_page("keys")
            else:
                messagebox.showwarning("提示", msg, parent=dlg)

        tk.Button(dlg, text="确定", width=10, command=ok).pack(pady=(14, 4))
        tk.Button(dlg, text="取消", width=10, command=dlg.destroy).pack()

    def _dlg_add_app(self):
        dlg = tk.Toplevel(self.root)
        dlg.title("添加应用")
        dlg.geometry("580x540")
        dlg.transient(self.root)
        dlg.grab_set()

        tk.Label(dlg, text="应用标识（英文，如 my_app）：").pack(anchor="w", padx=14, pady=(12, 2))
        e_name = tk.Entry(dlg, width=30)
        e_name.pack(anchor="w", padx=14)
        tk.Label(dlg, text="显示名（如：我的软件）：").pack(anchor="w", padx=14, pady=(8, 2))
        e_label = tk.Entry(dlg, width=30)
        e_label.pack(anchor="w", padx=14)

        tk.Label(dlg, text="适配器类型（决定 key 写到哪）：").pack(anchor="w", padx=14, pady=(8, 2))
        adapters = keyhub.list_adapters()
        v_adapter = tk.StringVar(value=list(adapters.keys())[0])
        ttk.Combobox(dlg, textvariable=v_adapter, values=list(adapters.keys()),
                     state="readonly", width=24).pack(anchor="w", padx=14)
        desc = tk.Label(dlg, text=adapters[v_adapter.get()], foreground="#666",
                        wraplength=540, justify="left")
        desc.pack(anchor="w", padx=14, pady=(2, 0))

        param_frame = tk.Frame(dlg)
        param_frame.pack(fill="x", padx=14, pady=6)
        param_widgets = {}

        def show_params(*_):
            for w in param_frame.winfo_children():
                w.destroy()
            param_widgets.clear()
            a = v_adapter.get()
            desc.configure(text=adapters.get(a, ""))
            fields = {
                "env_var": [("env", "环境变量名（如 OPENAI_API_KEY）")],
                "file_json": [("path", "配置文件完整路径"), ("key_path", "JSON 点路径（如 opencode-go.key）")],
                "file_env": [("path", "配置文件完整路径"), ("key_name", "KEY=VALUE 的键名（如 API_KEY）")],
                "file_regex": [("path", "配置文件完整路径"), ("pattern", "正则（含1个捕获组，如 (sk-[A-Za-z0-9]+)）")],
            }.get(a, [])
            for i, (k, tip) in enumerate(fields):
                tk.Label(param_frame, text=f"{k}：{tip}").pack(anchor="w")
                e = tk.Entry(param_frame, width=54)
                e.pack(anchor="w", pady=(0, 4))
                param_widgets[k] = e

        v_adapter.trace_add("write", show_params)
        show_params()

        tk.Label(dlg, text="此应用使用哪些 Provider 的哪个 Key（可多选）：").pack(anchor="w", padx=14, pady=(8, 0))
        map_frame = tk.Frame(dlg)
        map_frame.pack(fill="x", padx=14)
        mapping_vars = {}
        for p in self.providers:
            row = tk.Frame(map_frame)
            row.pack(fill="x", pady=1)
            tk.Label(row, text=f"{p}:", width=14, anchor="w").pack(side="left")
            v = tk.StringVar(value="__none__")
            vals = keyhub.key_ids(self.cfg, p) + ["__none__"]
            disp = [x if x != "__none__" else "不使用" for x in vals]
            ttk.Combobox(row, textvariable=v, values=disp, state="readonly", width=15).pack(side="left")
            mapping_vars[p] = (v, vals)

        def ok():
            name = e_name.get().strip()
            label = e_label.get().strip() or name
            adapter = v_adapter.get()
            if not name:
                messagebox.showwarning("提示", "应用标识不能为空", parent=dlg)
                return
            params = {k: w.get().strip() for k, w in param_widgets.items() if w.get().strip()}
            mapping = {}
            for p, (v, vals) in mapping_vars.items():
                sel = v.get()
                mapping[p] = sel if sel != "不使用" else ""
            ok, msg = keyhub.add_target(self.cfg, name, label, adapter, params, mapping)
            if ok:
                keyhub.save_config(self.cfg)
                _log(msg)
                dlg.destroy()
                self.refresh_data()
                self._switch_page("apps")
                messagebox.showinfo("完成", msg + "\n再去「🔑 Key 配置」页核对映射并保存", parent=self.root)
            else:
                messagebox.showwarning("提示", msg, parent=dlg)

        tk.Button(dlg, text="确定", width=10, command=ok).pack(pady=(12, 4))
        tk.Button(dlg, text="取消", width=10, command=dlg.destroy).pack()

    # ================= 杂项 =================
    def _open_cfg_dir(self):
        try:
            os.startfile(os.path.dirname(keyhub.CONFIG_PATH))
        except Exception:
            pass

    def _open_log(self):
        try:
            os.startfile(LOG_FILE)
        except Exception:
            pass

    def _open_guide(self):
        guide = os.path.join(APP_DIR, "USE_GUIDE.md")
        if os.path.exists(guide):
            try:
                os.startfile(guide)
            except Exception:
                pass
        else:
            messagebox.showinfo("使用说明", "USE_GUIDE.md 未找到，请查看项目目录", parent=self.root)


def create_window(icon=None) -> tk.Tk:
    root = tk.Tk()
    KeySwitchApp(root)
    return root


if __name__ == "__main__":
    root = create_window()
    root.mainloop()
