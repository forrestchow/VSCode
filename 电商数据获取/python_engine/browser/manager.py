"""
Chrome 浏览器生命周期管理

- 自动发现察尔汗 Chrome profile
- 修复 Local State 确保正常进入 profile
- 检测 Chrome 是否已在运行（带 debug port）
- 启动察尔汗 Chrome 并连接 CDP
"""
import os
import sys
import json
import shutil
import subprocess
import socket
import asyncio
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from python_engine.config import (
    CDP_PORT,
    CHAYAN_PROFILE,
    CHAYAN_EXECUTABLE,
    CHAYAN_PROFILE_SEARCH_PATHS,
)


def _fix_local_state(user_data_dir: str, profile_directory: str) -> bool:
    """
    修复 Chrome Local State，确保：
    1. 退出状态标记为正常（避免显示"恢复页面"提示）
    2. 设置目标 profile 为上次使用的 profile（避免显示 profile 选择页）

    这是 --profile-directory + --remote-debugging-port 能正常工作的关键。
    """
    local_state_path = os.path.join(user_data_dir, "Local State")
    if not os.path.exists(local_state_path):
        return False

    try:
        # 备份
        backup = local_state_path + ".cdp_backup"
        if not os.path.exists(backup):
            shutil.copy2(local_state_path, backup)

        with open(local_state_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        profile = data.setdefault("profile", {})
        profile["exited_cleanly"] = True
        profile["exit_type"] = "Normal"
        profile["last_used"] = profile_directory

        # 确保 last_active_profiles 包含目标 profile
        active = profile.setdefault("last_active_profiles", [])
        if profile_directory not in active:
            active.insert(0, profile_directory)

        with open(local_state_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

        return True
    except Exception as e:
        print(f"[BrowserManager] Local State 修复失败: {e}")
        return False


def find_chayan_profile() -> Optional[dict]:
    """
    搜索察尔汗 Chrome profile

    Returns:
        {"user_data_dir": "...", "profile_directory": "Profile 2"} 或 None
        user_data_dir = Chrome User Data 根目录
        profile_directory = 子目录名（如 Profile 2）
    """
    # 策略1: 配置指定的路径
    if CHAYAN_PROFILE and os.path.isdir(CHAYAN_PROFILE):
        return {"user_data_dir": CHAYAN_PROFILE, "profile_directory": ""}

    # 策略2: 搜索 Google Chrome User Data 中名为"察尔汗"的 profile
    chrome_user_data = os.path.expandvars(
        r"%LOCALAPPDATA%\Google\Chrome\User Data"
    )
    if os.path.isdir(chrome_user_data):
        local_state_path = os.path.join(chrome_user_data, "Local State")
        if os.path.exists(local_state_path):
            try:
                with open(local_state_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                info_cache = data.get("profile", {}).get("info_cache", {})
                for dir_name, info in info_cache.items():
                    if info.get("name") in ("察尔汗",):
                        return {
                            "user_data_dir": chrome_user_data,
                            "profile_directory": dir_name,
                        }
            except (json.JSONDecodeError, KeyError):
                pass

    # 策略3: 搜索配置的路径列表
    for path in CHAYAN_PROFILE_SEARCH_PATHS:
        expanded = os.path.expandvars(path)
        if os.path.isdir(expanded):
            if os.path.exists(os.path.join(expanded, "Local State")):
                return {"user_data_dir": expanded, "profile_directory": ""}

    return None


def find_chayan_executable() -> Optional[str]:
    """查找 Chrome 可执行文件"""
    if CHAYAN_EXECUTABLE and os.path.exists(CHAYAN_EXECUTABLE):
        return CHAYAN_EXECUTABLE

    candidates = [
        os.path.expandvars(r"%PROGRAMFILES%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%PROGRAMFILES(X86)%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    ]

    for path in candidates:
        if os.path.exists(path):
            return path

    return None


def is_port_open(host: str = "localhost", port: int = 9222) -> bool:
    """检查 CDP 端口是否监听"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception:
        return False


def launch_chrome(
    user_data_dir: str,
    profile_directory: str = "",
    port: int = 9222,
    extra_args: list[str] | None = None,
) -> subprocess.Popen:
    """
    启动察尔汗 Chrome（带 CDP debug port）

    Args:
        user_data_dir: Chrome User Data 根目录
        profile_directory: profile 子目录名 (如 "Profile 2")
        port: CDP debug port
        extra_args: 额外启动参数
    """
    exe = find_chayan_executable()
    if not exe:
        raise FileNotFoundError("找不到 Chrome。设置环境变量 CHAYAN_EXECUTABLE")

    if not os.path.isdir(user_data_dir):
        raise FileNotFoundError(f"User Data 路径不存在: {user_data_dir}")

    # 修复 Local State（避免 profile 选择页）
    if profile_directory:
        _fix_local_state(user_data_dir, profile_directory)

    args = [
        exe,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={user_data_dir}",
        "--no-first-run",
        "--no-default-browser-check",
    ]

    if profile_directory:
        args.append(f"--profile-directory={profile_directory}")

    if extra_args:
        args.extend(extra_args)

    print(f"[BrowserManager] 启动 Chrome: {exe}")
    print(f"[BrowserManager] User Data: {user_data_dir}")
    if profile_directory:
        print(f"[BrowserManager] Profile: {profile_directory}")
    print(f"[BrowserManager] CDP Port: {port}")

    process = subprocess.Popen(
        args,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # 等待端口就绪
    import time
    for _ in range(30):
        if is_port_open(port=port):
            print(f"[BrowserManager] CDP 端口 {port} 已就绪")
            return process
        time.sleep(1)

    process.terminate()
    raise RuntimeError(f"Chrome 启动超时，{port} 端口未在 30 秒内就绪")


async def connect_or_launch(port: int | None = None) -> tuple:
    """
    智能连接：检测 Chrome 状态，自动连接或启动

    返回: (CDPClient, is_newly_launched: bool)
    """
    from python_engine.browser.cdp_client import CDPClient

    _port = port or CDP_PORT

    if is_port_open(port=_port):
        print(f"[BrowserManager] Chrome 已在运行 (port {_port})，直接连接...")
        client = CDPClient(port=_port)
        await client.connect()
        return client, False

    # 未运行 → 启动
    print("[BrowserManager] Chrome 未运行，正在启动...")
    info = find_chayan_profile()
    if not info:
        raise RuntimeError(
            "找不到察尔汗 Chrome profile。\n"
            "请确保察尔汗 Chrome profile 已创建，或设置环境变量 CHAYAN_PROFILE\n"
            "运行 scripts/find_chayan.py 可以帮你排查"
        )

    launch_chrome(
        user_data_dir=info["user_data_dir"],
        profile_directory=info.get("profile_directory", ""),
        port=_port,
    )

    client = CDPClient(port=_port)
    await client.connect()
    return client, True


# ─── CLI ───
if __name__ == "__main__":
    async def main():
        print("=== 察尔汗 Chrome 检测 ===")
        info = find_chayan_profile()
        if info:
            print(f"Profile: [OK] {info['user_data_dir']}")
            if info.get("profile_directory"):
                print(f"  Directory: {info['profile_directory']}")
        else:
            print("Profile: [FAIL] 未找到")
        print(f"Chrome: {find_chayan_executable() or '[FAIL] 未找到'}")
        status = "[OK] 已监听" if is_port_open(port=CDP_PORT) else "[FAIL] 未监听"
        print(f"CDP port {CDP_PORT}: {status}")

        if is_port_open(port=CDP_PORT):
            print("\n测试 CDP 连接...")
            from python_engine.browser.cdp_client import CDPClient
            client = CDPClient()
            await client.connect()
            title = await client.evaluate("document.title")
            print(f"[OK] 连接成功！当前页面: {title}")
            await client.close()

    asyncio.run(main())
