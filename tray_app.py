#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""KeySwitch v2 - 入口（托盘 + 主窗口）

启动即显示主窗口（每软件独立配置）；托盘常驻：
  - 双击/默认项 → 打开主窗口
  - 菜单显示各 key 用量
  - 退出

线程模型：tkinter 主窗口在主线程（mainloop），pystray 托盘在 daemon 线程。
托盘回调不直接碰 tkinter，通过 queue 投递命令，主线程 after 轮询执行。
日志：exe 同目录 keyswitch.log
"""
import os
import queue
import sys
import threading
import time

import pystray
from PIL import Image, ImageDraw

APP_DIR = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)
LOG_FILE = os.path.join(APP_DIR, "keyswitch.log")

import keyhub
from gui_app import KeySwitchApp

_cmd_queue: "queue.Queue[str]" = queue.Queue()
_quit_flag = [False]


def _log(msg: str):
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")
    except Exception:
        pass


def make_icon() -> Image.Image:
    img = Image.new("RGB", (64, 64), (58, 160, 217))
    d = ImageDraw.Draw(img)
    d.ellipse([10, 12, 30, 32], outline="white", width=4)
    d.rectangle([18, 24, 22, 46], fill="white")
    d.ellipse([36, 30, 56, 50], outline="white", width=4)
    d.rectangle([44, 42, 48, 56], fill="white")
    return img


def show_window(icon=None, item=None):
    _cmd_queue.put("show")


def refresh_menu(icon=None, item=None):
    try:
        icon.update_menu()
    except Exception:
        pass


def quit_app(icon=None, item=None):
    _log("退出")
    _quit_flag[0] = True
    _cmd_queue.put("quit")
    try:
        icon.stop()
    except Exception:
        pass


def build_menu(icon):
    """重建托盘菜单（打开时刷新用量）"""
    try:
        cfg = keyhub.load_config()
        statuses = keyhub.status_all(cfg)
    except Exception as e:
        _log(f"状态加载失败: {e}")
        return pystray.Menu(
            pystray.MenuItem("状态加载失败", None, enabled=False),
            pystray.MenuItem("退出", quit_app),
        )

    items = [pystray.MenuItem("打开 KeySwitch 主窗口", show_window, default=True)]
    items.append(pystray.Menu.SEPARATOR)
    for s in statuses:
        if s["usage"] is None:
            line = f"  {s['id']}: 未配置"
        else:
            u = s["usage"]
            line = f"  {s['id']}: {u['detail']} [{u['status']}]"
        items.append(pystray.MenuItem(line, None, enabled=False))
    auto = cfg.get("auto_switch", {})
    items.append(pystray.MenuItem(
        f"  智能切换: {'开' if auto.get('enabled') else '关'} "
        f"(阈值 {auto.get('trigger_percent', 100)}% / {auto.get('interval_min', 5)}分钟)",
        None, enabled=False))
    items.append(pystray.Menu.SEPARATOR)
    items.append(pystray.MenuItem("刷新状态", refresh_menu))
    items.append(pystray.MenuItem("打开配置目录", lambda i=None, it=None: os.startfile(os.path.dirname(keyhub.CONFIG_PATH))))
    items.append(pystray.MenuItem("退出", quit_app))
    return pystray.Menu(*items)


def main():
    try:
        sys.stdout = open(LOG_FILE, "a", encoding="utf-8")
        sys.stderr = sys.stdout
    except Exception:
        pass
    _log("=== KeySwitch v2 启动 ===")

    # 托盘线程
    icon = pystray.Icon("keyswitch", make_icon(), "API Key 管理器",
                        menu=pystray.Menu(lambda: build_menu(icon)))
    threading.Thread(target=icon.run, daemon=True).start()

    # 主窗口（主线程）
    import tkinter as tk
    root = tk.Tk()
    KeySwitchApp(root)

    def poll_queue():
        if _quit_flag[0]:
            try:
                root.destroy()
            except Exception:
                pass
            os._exit(0)
        try:
            while True:
                cmd = _cmd_queue.get_nowait()
                if cmd == "show":
                    root.deiconify()
                    root.lift()
                    root.focus_force()
                elif cmd == "quit":
                    try:
                        root.destroy()
                    except Exception:
                        pass
                    os._exit(0)
        except queue.Empty:
            pass
        root.after(200, poll_queue)

    root.after(200, poll_queue)
    root.mainloop()


if __name__ == "__main__":
    main()
