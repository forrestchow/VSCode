"""
定位察尔汗 Chrome profile 和可执行文件

Usage:
    python scripts/find_chayan.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from python_engine.browser.manager import (
    find_chayan_profile,
    find_chayan_executable,
    is_port_open,
)
from python_engine.config import CDP_PORT


def main():
    print("=" * 50)
    print("  察尔汗 Chrome 检测")
    print("=" * 50)

    # Profile
    print("\n[1] Profile (user-data-dir):")
    info = find_chayan_profile()
    if info:
        print(f"    [OK] {info['user_data_dir']}")
        if info.get("profile_directory"):
            print(f"    -> 子 Profile: {info['profile_directory']}")
    else:
        print("    [FAIL] 未找到察尔汗 profile")
        print("\n    已搜索:")
        print("      - Google Chrome User Data (读取 Local State 中的 profile 名称)")
        print("      - 环境变量 CHAYAN_PROFILE")
        print("      - config.py 中的 CHAYAN_PROFILE_SEARCH_PATHS")
        print("\n    解决方法:")
        print("      在 Chrome 中创建一个名为「察尔汗」的用户配置")
        print("      或设置环境变量: set CHAYAN_PROFILE=C:\\path\\to\\User Data")
        print("      并在启动时用 --profile-directory 指定子目录")

    # Executable
    print("\n[2] 可执行文件 (chrome.exe):")
    exe = find_chayan_executable()
    if exe:
        print(f"    [OK] {exe}")
    else:
        print("    [FAIL] 未找到")
        print("\n    解决方法:")
        print("      设置环境变量: set CHAYAN_EXECUTABLE=C:\\path\\to\\chrome.exe")

    # CDP Port
    print(f"\n[3] CDP 端口 ({CDP_PORT}):")
    if is_port_open(port=CDP_PORT):
        print(f"    [OK] 端口 {CDP_PORT} 已监听 - Chrome 正在运行")
        print(f"    -> 可以直接 CDP 连接: http://localhost:{CDP_PORT}")
    else:
        print(f"    [WARN] 端口 {CDP_PORT} 未监听")
        print("    -> 需要启动 Chrome 或给快捷方式添加参数:")
        print(f"       --remote-debugging-port={CDP_PORT}")

    print("\n" + "=" * 50)


if __name__ == "__main__":
    main()
