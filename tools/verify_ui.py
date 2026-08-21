#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""截屏验证 KeySwitch v3 选项卡切换（PrintWindow 抓窗口内容，支持副屏）

用法：python tools/verify_ui.py [click_index]
  无参数   ：只截当前 KeySwitch 窗口 → ui_1.png
  click N  ：先截 ui_1.png → 点击左侧第 N 个选项卡 → 截 ui_2.png
"""
import ctypes
import ctypes.wintypes
import sys
import time

from PIL import Image

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

HWND = user32.FindWindowW(None, "KeySwitch - API Key 管理")


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", ctypes.c_uint32), ("biWidth", ctypes.c_int32),
        ("biHeight", ctypes.c_int32), ("biPlanes", ctypes.c_uint16),
        ("biBitCount", ctypes.c_uint16), ("biCompression", ctypes.c_uint32),
        ("biSizeImage", ctypes.c_uint32), ("biXPelsPerMeter", ctypes.c_int32),
        ("biYPelsPerMeter", ctypes.c_int32), ("biClrUsed", ctypes.c_uint32),
        ("biClrImportant", ctypes.c_uint32),
    ]


def capture_window(path):
    if not HWND:
        print("未找到 KeySwitch 窗口")
        return None
    rect = ctypes.wintypes.RECT()
    user32.GetWindowRect(HWND, ctypes.byref(rect))
    w, h = rect.right - rect.left, rect.bottom - rect.top
    hwnd_dc = user32.GetWindowDC(HWND)
    mfc_dc = gdi32.CreateCompatibleDC(hwnd_dc)
    bmp = gdi32.CreateCompatibleBitmap(hwnd_dc, w, h)
    gdi32.SelectObject(mfc_dc, bmp)
    ok = user32.PrintWindow(HWND, mfc_dc, 2)  # PW_RENDERFULLCONTENT
    bmi = BITMAPINFOHEADER()
    bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bmi.biWidth = w
    bmi.biHeight = -h
    bmi.biPlanes = 1
    bmi.biBitCount = 32
    buf = ctypes.create_string_buffer(w * h * 4)
    gdi32.GetDIBits(mfc_dc, bmp, 0, h, buf, ctypes.byref(bmi), 0)
    img = Image.frombuffer("RGBA", (w, h), buf.raw, "raw", "BGRA", 0, 1).convert("RGB")
    img.save(path)
    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(mfc_dc)
    user32.ReleaseDC(HWND, hwnd_dc)
    print(f"PrintWindow={ok} 已保存 {path} ({w}x{h})")
    return (rect.left, rect.top, w, h)


def click_abs(px, py):
    user32.SetCursorPos(px, py)
    time.sleep(0.1)
    user32.mouse_event(2, 0, 0, 0, 0)
    time.sleep(0.05)
    user32.mouse_event(4, 0, 0, 0, 0)
    print(f"已点击 ({px},{py})")
    time.sleep(0.6)


def main():
    pos = capture_window("ui_1.png")
    if not pos:
        sys.exit(1)
    x, y, w, h = pos
    if len(sys.argv) < 2:
        return
    idx = int(sys.argv[1])
    nav_btn_y = y + 96 + (idx - 1) * 41 + 20
    click_abs(x + 89, nav_btn_y)
    capture_window("ui_2.png")


if __name__ == "__main__":
    main()
