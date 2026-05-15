"""
抖音视频解析 - 服务端
启动: python server.py
浏览器打开: http://127.0.0.1:5000
"""

import re
import json
from urllib.parse import unquote

import requests
from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__, static_folder=".", static_url_path="")


def parse_douyin_video(share_url):
    session = requests.Session()
    session.headers = {
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    }

    # 第一步: 先访问抖音首页获取 cookie
    try:
        session.get("https://www.douyin.com", timeout=10)
    except Exception:
        pass

    # 第二步: 跟随短链接重定向
    resp = session.get(share_url, allow_redirects=True, timeout=15)
    final_url = resp.url
    html = resp.text

    title = ""
    title_match = re.search(r'<title[^>]*>(.*?)</title>', html)
    if title_match:
        title = title_match.group(1).strip()

    # 提取 aweme_id (视频ID)
    video_id = None
    for pattern in [r'video/(\d+)', r'aweme_id[=:]\s*"?(\d+)', r'modal_id=(\d+)']:
        m = re.search(pattern, final_url + html[:5000])
        if m:
            video_id = m.group(1)
            break

    # 策略1: 用 aweme_id 调 API (需要 cookie 和 referer)
    if video_id:
        api_url = f"https://www.douyin.com/aweme/v1/web/aweme/detail/?aweme_id={video_id}"
        api_headers = {
            "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                           "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
            "Referer": f"https://www.douyin.com/video/{video_id}",
            "Accept": "application/json, text/plain, */*",
        }
        try:
            api_resp = session.get(api_url, headers=api_headers, timeout=15)
            if api_resp.status_code == 200 and api_resp.text.strip().startswith("{"):
                api_data = api_resp.json()
                aweme = api_data.get("aweme_detail", {})
                if not aweme:
                    # 也检查其他可能的结构
                    for key in api_data:
                        if isinstance(api_data[key], dict) and api_data[key].get("video"):
                            aweme = api_data[key]
                            break
                video_info = aweme.get("video", {})
                if video_info:
                    title = aweme.get("desc", title)
                    # 无水印地址
                    for addr_type in ["play_addr", "download_addr", "play_addr_h264"]:
                        addr = video_info.get(addr_type, {})
                        urls = addr.get("url_list", [])
                        if urls:
                            return {"title": title, "video_urls": urls}
                    # bit_rate 清晰度列表
                    for br in video_info.get("bit_rate", []):
                        u = br.get("play_addr", {}).get("url_list", [])
                        if u:
                            return {"title": title, "video_urls": u}
        except Exception:
            pass

    # 策略2: 从 HTML 的所有 JSON 嵌入数据中提取视频 URL
    all_addrs = []

    # 尝试各种 ID 格式的 script 标签
    for tag_id in ['RENDER_DATA', '__NEXT_DATA__', '__NUXT__']:
        match = re.search(
            r'<script[^>]*id="' + tag_id + r'"[^>]*>([^<]+)</script>', html
        )
        if match:
            try:
                raw = unquote(match.group(1))
                data = json.loads(raw)

                def find_play_addr(obj, depth=0):
                    if depth > 20 or obj is None:
                        return None
                    if isinstance(obj, dict):
                        for k in ['play_addr', 'playAddr', 'download_addr', 'downloadAddr',
                                  'play_addr_h264', 'play_addr_bytevc1']:
                            if k in obj and isinstance(obj[k], dict):
                                urls = obj[k].get('url_list', [])
                                if urls:
                                    return urls
                        if 'video' in obj and isinstance(obj['video'], dict):
                            r = find_play_addr(obj['video'], depth + 1)
                            if r: return r
                        if 'aweme' in obj and isinstance(obj['aweme'], dict):
                            r = find_play_addr(obj['aweme'], depth + 1)
                            if r: return r
                        for v in obj.values():
                            r = find_play_addr(v, depth + 1)
                            if r: return r
                    elif isinstance(obj, list):
                        for item in obj[:5]:
                            r = find_play_addr(item, depth + 1)
                            if r: return r
                    return None

                addrs = find_play_addr(data)
                if addrs:
                    return {"title": title, "video_urls": addrs}
            except Exception:
                pass

    # 策略3: 正则搜索所有 script 中的视频 url (过滤掉图片)
    seen = set()
    for script in re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL):
        for match in re.finditer(r'"url_list"\s*:\s*\[(.*?)\]', script):
            urls = re.findall(r'"(https?://[^"]+)"', match.group(1))
            for u in urls:
                u = u.replace('\\u0026', '&')
                # 只保留视频域名, 排除图片
                if any(d in u for d in ['douyinvod', 'zjcdn', 'pstatp', 'bytecdn',
                                          'byteicdn', 'douyincdn', 'ixigua', 'snssdk']):
                    if u not in seen:
                        seen.add(u)
                        all_addrs.append(u)

    if all_addrs:
        return {"title": title, "video_urls": all_addrs[:3]}

    # 策略4: video 标签
    video_src = re.search(r'<video[^>]+src="([^"]+)"', html)
    if video_src:
        return {"title": title, "video_urls": [unquote(video_src.group(1))]}

    return {"title": title, "video_urls": [], "error": "未找到视频地址"}


@app.route("/")
def index():
    return send_from_directory(".", "index.html")


@app.route("/api/parse", methods=["POST"])
def api_parse():
    data = request.get_json()
    url = data.get("url", "").strip()
    if not url:
        return jsonify({"error": "请输入链接"}), 400
    if "douyin.com" not in url and "iesdouyin.com" not in url:
        return jsonify({"error": "请输入抖音分享链接"}), 400

    result = parse_douyin_video(url)
    return jsonify(result)


if __name__ == "__main__":
    print("服务已启动: http://127.0.0.1:5000")
    app.run(host="0.0.0.0", port=5000, debug=True)
