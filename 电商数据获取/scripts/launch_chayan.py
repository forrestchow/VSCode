"""
启动察尔汗 Chrome（带 CDP debug port）

用法:
    python scripts/launch_chayan.py
"""
import subprocess
import time
import sys
import urllib.request
import json
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from python_engine.browser.manager import (
    find_chayan_profile,
    find_chayan_executable,
    is_port_open,
    _fix_local_state,
)
from python_engine.config import CDP_PORT


def main():
    # 如果已在运行，直接提示
    if is_port_open(port=CDP_PORT):
        print(f"[OK] Chrome 已在运行 (CDP port {CDP_PORT})")
        print(f"    http://localhost:{CDP_PORT}/json")
        return

    # 获取 profile 信息
    info = find_chayan_profile()
    if not info:
        print("[FAIL] 找不到察尔汗 Chrome profile")
        print("请运行 python scripts/find_chayan.py 排查")
        return

    user_data_dir = info["user_data_dir"]
    profile_dir = info.get("profile_directory", "")
    exe = find_chayan_executable()

    print(f"启动察尔汗 Chrome...")
    print(f"  Chrome: {exe}")
    print(f"  User Data: {user_data_dir}")
    if profile_dir:
        print(f"  Profile: {profile_dir}")
    print(f"  CDP Port: {CDP_PORT}")
    print()

    # 修复 Local State
    if profile_dir:
        _fix_local_state(user_data_dir, profile_dir)

    # 构建参数
    args = [
        exe,
        f"--remote-debugging-port={CDP_PORT}",
        f"--user-data-dir={user_data_dir}",
        "--no-first-run",
        "--no-default-browser-check",
    ]
    if profile_dir:
        args.append(f"--profile-directory={profile_dir}")

    subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # 等待端口就绪
    print("等待 CDP 端口就绪...")
    for i in range(30):
        time.sleep(1)
        try:
            resp = urllib.request.urlopen(
                f"http://127.0.0.1:{CDP_PORT}/json/version", timeout=1
            )
            data = json.loads(resp.read())
            print(f"\n[OK] CDP 就绪！({i+1}s)")
            print(f"  Browser: {data.get('Browser', '?')}")
            print(f"\n现在可以运行:")
            print(f"  python -m python_engine.main --snapshot   # 保存 HTML 快照")
            print(f"  python -m python_engine.main              # 采集数据并预览")
            print(f"  python -m python_engine.main --save-db    # 采集并写入数据库")
            return
        except Exception:
            print(f"  ...({i+1}s)", end="", flush=True)

    print("\n[FAIL] 启动超时")


if __name__ == "__main__":
    main()
