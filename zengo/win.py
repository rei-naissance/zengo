"""Small Win32 helpers via ctypes (no pywin32 dependency)."""
from __future__ import annotations

import ctypes
import sys
import time
from ctypes import wintypes
from pathlib import Path

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
dwmapi = ctypes.windll.dwmapi

user32.GetClipboardData.restype = wintypes.HANDLE
user32.GetClipboardData.argtypes = [wintypes.UINT]
kernel32.GlobalLock.restype = ctypes.c_void_p
kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
user32.FindWindowW.restype = wintypes.HWND
user32.MonitorFromPoint.restype = wintypes.HMONITOR
user32.MonitorFromPoint.argtypes = [wintypes.POINT, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

CF_UNICODETEXT = 13


def get_clipboard_text() -> str:
    for _ in range(20):
        if user32.OpenClipboard(None):
            break
        time.sleep(0.02)
    else:
        return ""
    try:
        h = user32.GetClipboardData(CF_UNICODETEXT)
        if not h:
            return ""
        p = kernel32.GlobalLock(h)
        try:
            return ctypes.wstring_at(p) if p else ""
        finally:
            kernel32.GlobalUnlock(h)
    finally:
        user32.CloseClipboard()


def cursor_pos() -> tuple[int, int]:
    pt = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


class MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]


def work_area_at(x: int, y: int) -> tuple[int, int, int, int]:
    mon = user32.MonitorFromPoint(wintypes.POINT(x, y), 2)  # MONITOR_DEFAULTTONEAREST
    mi = MONITORINFO(cbSize=ctypes.sizeof(MONITORINFO))
    user32.GetMonitorInfoW(mon, ctypes.byref(mi))
    r = mi.rcWork
    return r.left, r.top, r.right, r.bottom


def find_window(title: str) -> int:
    return user32.FindWindowW(None, title) or 0


def window_rect(hwnd: int) -> tuple[int, int, int, int]:
    r = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    return r.left, r.top, r.right, r.bottom


def place_window(hwnd: int, x: int, y: int) -> None:
    SWP_NOSIZE, SWP_NOACTIVATE = 0x0001, 0x0010
    user32.SetWindowPos(hwnd, -1, x, y, 0, 0, SWP_NOSIZE | SWP_NOACTIVATE)  # HWND_TOPMOST


def force_foreground(hwnd: int) -> None:
    """Windows refuses focus to background apps; borrow the foreground thread's input."""
    fg = user32.GetForegroundWindow()
    fg_thread = user32.GetWindowThreadProcessId(fg, None)
    target_thread = user32.GetWindowThreadProcessId(hwnd, None)
    if fg_thread and fg_thread != target_thread:
        user32.AttachThreadInput(fg_thread, target_thread, True)
        user32.SetForegroundWindow(hwnd)
        user32.BringWindowToTop(hwnd)
        user32.AttachThreadInput(fg_thread, target_thread, False)
    else:
        user32.SetForegroundWindow(hwnd)


def style_window(hwnd: int, dark: bool, rounded: bool = True) -> None:
    """Windows 11: rounded corners + dark title bar."""
    val = ctypes.c_int(1 if dark else 0)
    dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(val), 4)  # DWMWA_USE_IMMERSIVE_DARK_MODE
    if rounded:
        pref = ctypes.c_int(2)  # DWMWCP_ROUND
        dwmapi.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(pref), 4)


def system_dark_mode() -> bool:
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as k:
            return winreg.QueryValueEx(k, "AppsUseLightTheme")[0] == 0
    except OSError:
        return False


def wait_process_exit(pid: int, timeout: float) -> bool:
    """True once the process is gone (or never existed), False on timeout."""
    SYNCHRONIZE = 0x00100000
    h = kernel32.OpenProcess(SYNCHRONIZE, False, pid)
    if not h:
        return True
    try:
        return kernel32.WaitForSingleObject(h, int(timeout * 1000)) == 0  # WAIT_OBJECT_0
    finally:
        kernel32.CloseHandle(h)


def message_box(text: str, title: str = "Zengo", error: bool = True) -> None:
    """Visible even under pythonw, where a traceback would vanish silently."""
    user32.MessageBoxW(None, text, title, 0x10 if error else 0x40)  # MB_ICONERROR / MB_ICONINFORMATION


_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def _launch_command() -> str:
    exe = Path(sys.executable)
    pythonw = exe.with_name("pythonw.exe") if exe.name.lower() == "python.exe" else exe
    script = Path(__file__).resolve().parent.parent / "zengo.pyw"
    return f'"{pythonw}" "{script}" --tray'


def _registered_command() -> str | None:
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as k:
            return winreg.QueryValueEx(k, "Zengo")[0]
    except OSError:
        return None


def repair_autostart() -> bool:
    """If "Start with Windows" points at a copy of Zengo that no longer exists (folder moved,
    reinstalled elsewhere, old venv deleted), point it at this one. Returns True if changed."""
    cmd = _registered_command()
    if not cmd or cmd == _launch_command():
        return False
    paths = [p for p in cmd.split('"') if p.strip() and not p.strip().startswith("--")]
    if paths and all(Path(p).exists() for p in paths):
        return False  # another valid install owns it; leave it alone
    set_autostart(True)
    return True


def get_autostart() -> bool:
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as k:
            winreg.QueryValueEx(k, "Zengo")
            return True
    except OSError:
        return False


def set_autostart(on: bool) -> None:
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if on:
            winreg.SetValueEx(k, "Zengo", 0, winreg.REG_SZ, _launch_command())
        else:
            try:
                winreg.DeleteValue(k, "Zengo")
            except OSError:
                pass
