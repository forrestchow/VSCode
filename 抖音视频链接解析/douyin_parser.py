"""
抖音视频链接解析
用法: python douyin_parser.py <抖音分享链接>
示例: python douyin_parser.py https://v.douyin.com/uxMp6QYsjW0/
"""

import sys
import re
import json
import requests
from urllib.parse import unquote


def parse_douyin_video(share_url):
    session = requests.Session()
    session.headers = {
        "User-Agent": ("Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
                       "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 "
                       "Mobile/15E148 Safari/604.1")
    }

    print(f"[1] 请求分享链接: {share_url}")

    # 第一步: 跟随302重定向, 获取真实页面
    resp = session.get(share_url, allow_redirects=True, timeout=15)
    final_url = resp.url
    print(f"[2] 重定向到: {final_url}")

    html = resp.text

    # 策略1: 在 HTML 中搜索 video_id
    video_id = re.search(r'video/(\d+)', final_url)
    if video_id:
        video_id = video_id.group(1)
        print(f"[3] 视频ID: {video_id}")

    # 策略2: 从页面 JSON 数据提取 (RENDER_DATA / __DATA__)
    # 抖音PC页面通常把数据藏在 RENDER_DATA 里
    match = re.search(r'<script[^>]*id="RENDER_DATA"[^>]*>([^<]+)</script>', html)
    if match:
        try:
            raw = unquote(match.group(1))
            data = json.loads(raw)
            # 深度搜索 video playAddr
            def find_video_url(obj, depth=0):
                if depth > 15:
                    return None
                if isinstance(obj, dict):
                    for key in ['playAddr', 'downloadAddr', 'bitRateList']:
                        if key in obj:
                            return obj[key]
                    if 'video' in obj and isinstance(obj['video'], dict):
                        return find_video_url(obj['video'], depth + 1)
                    if 'aweme' in obj and isinstance(obj['aweme'], dict):
                        url_list = obj['aweme'].get('video', {}).get('playAddr', [])
                        if url_list:
                            return url_list[0] if isinstance(url_list, list) else url_list
                    for v in obj.values():
                        result = find_video_url(v, depth + 1)
                        if result:
                            return result
                elif isinstance(obj, list):
                    for item in obj:
                        result = find_video_url(item, depth + 1)
                        if result:
                            return result
                return None

            video_url = find_video_url(data)
            if video_url:
                # 可能是个列表
                urls = video_url if isinstance(video_url, list) else [video_url]
                for i, u in enumerate(urls):
                    real_url = u.get('src') if isinstance(u, dict) else u
                    print(f"[4] 视频地址[{i}]: {real_url}")
                return urls
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            print(f"[!] RENDER_DATA 解析失败: {e}")

    # 策略3: 从页面嵌入的 video 标签提取
    video_src = re.search(r'<video[^>]+src="([^"]+)"', html)
    if video_src:
        url = unquote(video_src.group(1))
        print(f"[3] video标签地址: {url}")
        return [url]

    # 策略4: 从所有 script 标签中搜索 playAddr
    scripts = re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL)
    for script in scripts:
        addrs = re.findall(r'"playAddr":\s*"([^"]+)"', script)
        if addrs:
            urls = [a.replace('\\u0026', '&') for a in addrs]
            for i, u in enumerate(urls):
                print(f"[3] playAddr[{i}]: {u}")
            return urls

    print("[!] 未找到视频地址")
    return None


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python douyin_parser.py <抖音分享链接>")
        print("示例: python douyin_parser.py https://v.douyin.com/uxMp6QYsjW0/")
        sys.exit(1)

    url = sys.argv[1]
    video_urls = parse_douyin_video(url)

    if video_urls:
        print(f"\n✅ 解析完成, 共 {len(video_urls)} 个地址")
        # 保存到文件
        with open("video_url.txt", "w", encoding="utf-8") as f:
            for u in video_urls:
                real = u.get('src') if isinstance(u, dict) else u
                f.write(real + "\n")
        print("📁 已保存到 video_url.txt")
    else:
        print("\n❌ 解析失败")
