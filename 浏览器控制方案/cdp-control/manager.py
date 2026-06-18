"""
Chrome 生命周期管理 — 独立版

- 搜索 Chrome User Data 中的 profile
- 修复 Local State 确保正常进入 profile
- 检测 Chrome 是否已在运行（带 debug port）
- 启动 Debug Chrome 并连接 CDP

用法:
    from manager import connect_or_launch
    client, is_new = await connect_or_launch()
"""
import os
import json
import shutil
import subprocess
import socket
import asyncio
from pathlib import Path
from typing import Optional

# ─── 配置（可按需修改） ──────────────────────────────────────────
CDP_PORT = 9222

# Chrome 可执行文件搜索路径
CHROME_EXE_CANDIDATES = [
    os.path.expandvars(r"%PROGRAMFILES%\Google\Chrome\Application\chrome.exe"),
    os.path.expandvars(r"%PROGRAMFILES(X86)%\Google\Chrome\Application\chrome.exe"),
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
]

# 本项目复制的 Chrome User Data（CDP debug 用）
PROFILE_DIR = str(Path(__file__).parent / "chrome_profile_full")


def _fix_local_state(user_data_dir: str, profile_directory: str) -> bool:
    """
    修复 Chrome Local State，确保：
    1. 退出状态标记为正常（避免显示"恢复页面"提示）
    2. 设置目标 profile 为上次使用的 profile
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

        active = profile.setdefault("last_active_profiles", [])
        if profile_directory not in active:
            active.insert(0, profile_directory)

        with open(local_state_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

        return True
    except Exception as e:
        print(f"[Manager] Local State 修复失败: {e}")
        return False


def find_chrome_exe() -> Optional[str]:
    """查找 Chrome 可执行文件"""
    for path in CHROME_EXE_CANDIDATES:
        if os.path.exists(path):
            return path
    return None


def find_profile(user_data_dir: str, profile_name: str = "察尔汗") -> Optional[str]:
    """
    在 User Data 中搜索指定名称的 profile 目录名。

    Returns:
        "Profile 2" 或 None
    """
    local_state_path = os.path.join(user_data_dir, "Local State")
    if not os.path.exists(local_state_path):
        return None

    try:
        with open(local_state_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        info_cache = data.get("profile", {}).get("info_cache", {})
        for dir_name, info in info_cache.items():
            if info.get("name") == profile_name:
                return dir_name
    except (json.JSONDecodeError, KeyError):
        pass
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
) -> subprocess.Popen:
    """
    启动 Chrome（带 CDP debug port）

    Args:
        user_data_dir: Chrome User Data 根目录
        profile_directory: profile 子目录名 (如 "Profile 2")
        port: CDP debug port
    """
    exe = find_chrome_exe()
    if not exe:
        raise FileNotFoundError(
            "找不到 Chrome。\n"
            "请确保 Chrome 已安装，或设置环境变量 CHROME_EXE"
        )

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

    print(f"[Manager] 启动 Chrome: {exe}")
    print(f"[Manager] User Data: {user_data_dir}")
    if profile_directory:
        print(f"[Manager] Profile: {profile_directory}")
    print(f"[Manager] CDP Port: {port}")

    process = subprocess.Popen(
        args,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # 等待端口就绪
    import time
    for _ in range(30):
        if is_port_open(port=port):
            print(f"[Manager] CDP 端口 {port} 已就绪")
            return process
        time.sleep(1)

    process.terminate()
    raise RuntimeError(f"Chrome 启动超时，{port} 端口未在 30 秒内就绪")


async def connect_or_launch(
    user_data_dir: str | None = None,
    profile_directory: str = "",
    port: int | None = None,
):
    """
    智能连接：检测 Chrome 状态，自动连接或启动

    Returns:
        (CDPClient, is_newly_launched: bool)
    """
    from cdp_client import CDPClient

    _port = port or CDP_PORT
    _user_data_dir = user_data_dir or PROFILE_DIR

    if is_port_open(port=_port):
        print(f"[Manager] Chrome 已在运行 (port {_port})，直接连接...")
        client = CDPClient(port=_port)
        await client.connect()
        return client, False

    # 未运行 → 启动
    print("[Manager] Chrome 未运行，正在启动...")

    if not os.path.isdir(_user_data_dir):
        raise FileNotFoundError(
            f"User Data 路径不存在: {_user_data_dir}\n"
            f"请先将日常 Chrome 的 User Data 复制到: {_user_data_dir}"
        )

    # 自动检测 profile 目录名
    _profile_dir = profile_directory
    if not _profile_dir:
        _profile_dir = find_profile(_user_data_dir) or ""

    launch_chrome(
        user_data_dir=_user_data_dir,
        profile_directory=_profile_dir,
        port=_port,
    )

    client = CDPClient(port=_port)
    await client.connect()
    return client, True


# ─── CLI ───
if __name__ == "__main__":
    async def main():
        print("=== Chrome 管理器 检测 ===")
        print(f"User Data: {PROFILE_DIR}")
        print(f"  exists: {os.path.isdir(PROFILE_DIR)}")
        print(f"Chrome exe: {find_chrome_exe() or '[NOT FOUND]'}")
        print(f"CDP port {CDP_PORT}: {'[OK]' if is_port_open(port=CDP_PORT) else '[NOT LISTENING]'}")

        if is_port_open(port=CDP_PORT):
            print("\n测试 CDP 连接...")
            from cdp_client import CDPClient
            client = CDPClient()
            await client.connect()
            title = await client.evaluate("document.title")
            print(f"[OK] 连接成功！当前页面: {title}")
            await client.close()

    asyncio.run(main())
