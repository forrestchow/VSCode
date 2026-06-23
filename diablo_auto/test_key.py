# ============================================
# 按键测试工具 - 独立验证 SendInput 是否工作
# 用法: py test_key.py [按键名]
# 默认发送字母 A
# ============================================
import ctypes
from ctypes import wintypes
import sys
import time

# --- Windows API ---
user32 = ctypes.windll.user32

INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk",          wintypes.WORD),
        ("wScan",        wintypes.WORD),
        ("dwFlags",      wintypes.DWORD),
        ("time",         wintypes.DWORD),
        ("dwExtraInfo",  ctypes.c_void_p),
    ]

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx",           ctypes.c_long),
        ("dy",           ctypes.c_long),
        ("mouseData",    wintypes.DWORD),
        ("dwFlags",      wintypes.DWORD),
        ("time",         wintypes.DWORD),
        ("dwExtraInfo",  ctypes.c_void_p),
    ]

class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg",         wintypes.DWORD),
        ("wParamL",      wintypes.WORD),
        ("wParamH",      wintypes.WORD),
    ]

class _INPUT_UNION(ctypes.Union):
    _fields_ = [
        ("mi", MOUSEINPUT),
        ("ki", KEYBDINPUT),
        ("hi", HARDWAREINPUT),
    ]

class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [
        ("type", wintypes.DWORD),
        ("u",    _INPUT_UNION),
    ]

# --- 按键映射 ---
VK = {
    'A': 0x41, 'B': 0x42, 'C': 0x43, 'D': 0x44,
    'E': 0x45, 'F': 0x46, 'G': 0x47, 'H': 0x48,
    'I': 0x49, 'J': 0x4A, 'K': 0x4B, 'L': 0x4C,
    'M': 0x4D, 'N': 0x4E, 'O': 0x4F, 'P': 0x50,
    'Q': 0x51, 'R': 0x52, 'S': 0x53, 'T': 0x54,
    'U': 0x55, 'V': 0x56, 'W': 0x57, 'X': 0x58,
    'Y': 0x59, 'Z': 0x5A,
    '1': 0x31, '2': 0x32, '3': 0x33, '4': 0x34,
    '5': 0x35, '6': 0x36, '7': 0x37, '8': 0x38,
    'F1': 0x70, 'F2': 0x71, 'F3': 0x72, 'F4': 0x73,
    'F5': 0x74, 'F6': 0x75, 'F7': 0x76, 'F8': 0x77,
    'SPACE': 0x20, 'ENTER': 0x0D, 'TAB': 0x09,
    'SHIFT': 0x10, 'CTRL': 0x11,
}

def send_key(vk_code):
    """发送按键，返回是否成功"""
    inp = (INPUT * 2)()
    inp[0].type = INPUT_KEYBOARD
    inp[0].ki.wVk = vk_code
    inp[0].ki.dwFlags = 0  # key down
    inp[1].type = INPUT_KEYBOARD
    inp[1].ki.wVk = vk_code
    inp[1].ki.dwFlags = KEYEVENTF_KEYUP  # key up
    result = user32.SendInput(2, inp, ctypes.sizeof(INPUT))
    return result  # 返回实际注入的输入事件数

def get_foreground_info():
    """获取前台窗口信息"""
    hwnd = user32.GetForegroundWindow()

    # 获取窗口标题
    length = user32.GetWindowTextLengthW(hwnd) + 1
    buf = ctypes.create_unicode_buffer(length)
    user32.GetWindowTextW(hwnd, buf, length)
    title = buf.value

    # 获取进程 PID
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

    # 获取进程名
    import os
    try:
        proc = ctypes.windll.kernel32.OpenProcess(0x0400 | 0x0010, False, pid.value)
        # 这需要额外的 API，先跳过
        proc_name = "?"
    except:
        proc_name = "?"

    return title, pid.value

# --- 主程序 ---
def main():
    key_name = sys.argv[1].upper() if len(sys.argv) > 1 else 'A'

    if key_name not in VK:
        print("不支持的按键:", key_name)
        print("支持的按键:", ', '.join(VK.keys()))
        return

    vk_code = VK[key_name]

    print("=" * 50)
    print("  按键测试工具")
    print("=" * 50)
    print()

    # 获取当前前台窗口
    title, pid = get_foreground_info()
    print(f"  当前前台窗口: 「{title}」")
    print(f"  进程 PID: {pid}")
    print()

    # 检查管理员权限
    try:
        is_admin = ctypes.windll.shell32.IsUserAnAdmin()
        print(f"  管理员权限: {'是' + chr(0x2705) if is_admin else '否 (游戏以管理员运行时可能注入失败)'}")
    except:
        print("  管理员权限: 未知")
    print()

    print(f"  准备发送按键: {key_name} (VK=0x{vk_code:02X})")
    print(f"  请在 3 秒内切换到目标窗口...")
    print()

    for i in range(3, 0, -1):
        print(f"    {i}...")
        time.sleep(1)

    print()
    print(f"  发送中...")

    # 连续发 3 次，确保能观察到
    total = 0
    for i in range(3):
        result = send_key(vk_code)
        total += result
        time.sleep(0.3)

    print(f"  SendInput 返回: {total}/3 次成功")
    print(f"  (返回 3 = 全部成功, 返回 0 = 全部失败)")
    print()

    title2, pid2 = get_foreground_info()
    print(f"  发送后前台窗口: 「{title2}」")
    print()

    if result > 0:
        print(" 结论: SendInput 正常工作 ✅")
        print("      如果目标窗口没有反应，可能原因:")
        print("      1. 游戏以管理员运行而本工具不是 → 以管理员身份运行本工具")
        print("      2. 游戏使用 DirectInput/RawInput 特殊处理 → 需尝试其他注入方式")
        print("      3. 按键被游戏内部拦截")
    else:
        print(" 结论: SendInput 返回 0，按键注入失败 ❌")
        print("      可能原因: 权限不足或目标窗口拒绝输入")

if __name__ == '__main__':
    main()
