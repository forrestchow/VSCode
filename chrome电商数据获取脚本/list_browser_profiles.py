# -*- coding: utf-8 -*-
"""列出当前 Chrome 进程里的 browser context（profile 窗口）、当前页和账号。

用法:
    python list_browser_profiles.py
    python list_browser_profiles.py --json
    python list_browser_profiles.py --profile-path   # 额外开临时后台页读 chrome://version

说明:
    - browserContextId 是 CDP 层 ID，不是 Chrome profile 目录名。
    - 账号优先从页面 DOM / meta[microdata] 识别；Cookie 只作辅助。
    - --profile-path 会在每个 context 开一个后台 about:blank，
      再导航到 chrome://version 读取 Profile Path，读完立即关闭。
"""
import argparse
import asyncio
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

import websockets

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

DEFAULT_USER_DATA = r"E:\VS Code\浏览器控制方案\chrome_profile_full"
DEFAULT_PORT = 9223

JS_IDENTIFY = r"""
(() => {
  const metaEl = document.querySelector('meta[name=microdata]');
  const meta = metaEl ? metaEl.content : '';
  const get = (name) => {
    const m = meta.match(new RegExp('(?:^|;)' + name + '=([^;]*)'));
    return m ? m[1] : '';
  };
  return JSON.stringify({
    title: document.title,
    url: location.href,
    loginUserId: get('loginUserId'),
    mainUserId: get('mainUserId'),
    runAsUserId: get('runAsUserId'),
    runAsShopTitle: get('runAsShopTitle'),
    runAsShopId: get('runAsShopId'),
    body: (document.body && document.body.innerText || '').slice(0, 1200)
  });
})()
"""


def http_json(url: str, timeout: float = 10.0):
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", "replace"))


def load_profile_names(user_data_dir: str) -> dict[str, str]:
    """Local State -> {profile 目录: 显示名}。"""
    local_state = Path(user_data_dir) / "Local State"
    if not local_state.exists():
        return {}
    try:
        data = json.loads(local_state.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    info = data.get("profile", {}).get("info_cache", {})
    return {d: v.get("name", "") for d, v in info.items()}


def decode_cookie(value: str) -> str:
    """tracknick 里是 %5Cu5BDF... 这种形式，解码成中文。"""
    try:
        import codecs
        return codecs.decode(urllib.parse.unquote(value), "unicode_escape")
    except Exception:
        return value


def shop_hint(body: str, run_as_shop: str = "") -> str:
    if run_as_shop:
        return run_as_shop
    # 生意参谋: "生意参谋 察尔汗壹品盐专卖店 主店 ..."
    tokens = body.split()
    if "生意参谋" in tokens:
        idx = tokens.index("生意参谋")
        if idx + 1 < len(tokens):
            return tokens[idx + 1]
    # 淘工厂: "... 格尔木盐化(集团)有限责任公司 ..."
    m = re.search(r"([^\s]{2,30}有限责任公司)", body)
    if m:
        return m.group(1)
    return ""


def pick_page(pages: list[dict]) -> list[dict]:
    """优先选能读 DOM 的页面。"""
    priority = (
        "sycm.taobao.com",
        "tgc.tmall.com",
        "starliner.tmall.com",
        "detail.tmall.com",
    )
    ranked = []
    for prefix in priority:
        ranked.extend([p for p in pages if prefix in (p.get("url") or "")])
    ranked.extend(pages)
    # 去重，保持顺序
    seen, out = set(), []
    for p in ranked:
        tid = p.get("targetId")
        if tid not in seen:
            seen.add(tid)
            out.append(p)
    return out


class CDP:
    def __init__(self, ws):
        self.ws = ws
        self.pending = {}
        self.next_id = 0

    async def send(self, method, params=None, session_id=None, timeout=10.0):
        self.next_id += 1
        mid = self.next_id
        payload = {"id": mid, "method": method}
        if params is not None:
            payload["params"] = params
        if session_id:
            payload["sessionId"] = session_id
        fut = asyncio.get_running_loop().create_future()
        self.pending[mid] = fut
        await self.ws.send(json.dumps(payload))
        while True:
            msg = json.loads(await asyncio.wait_for(self.ws.recv(), timeout))
            if msg.get("id") == mid:
                return msg


async def attach_page(cdp: CDP, target_id: str) -> str:
    attached = await cdp.send("Target.attachToTarget", {"targetId": target_id, "flatten": True})
    return attached["result"]["sessionId"]


async def evaluate(cdp: CDP, session_id: str, expression: str, timeout: float = 10.0) -> str:
    resp = await cdp.send(
        "Runtime.evaluate",
        {"expression": expression, "returnByValue": True},
        session_id=session_id,
        timeout=timeout,
    )
    return resp.get("result", {}).get("result", {}).get("value", "")


async def read_page_cookies(cdp: CDP, session_id: str, page_url: str) -> list[dict]:
    """页面级 Network.getCookies；比 Storage.getCookies({browserContextId}) 更可靠。"""
    try:
        await cdp.send("Network.enable", {}, session_id=session_id, timeout=10)
        parsed = urllib.parse.urlparse(page_url)
        origin = f"{parsed.scheme}://{parsed.netloc}/"
        resp = await cdp.send(
            "Network.getCookies",
            {"urls": [origin]},
            session_id=session_id,
            timeout=10,
        )
        return resp.get("result", {}).get("cookies", [])
    except Exception:
        return []


async def read_profile_path(cdp: CDP, ctx: str) -> str:
    """在指定 context 后台打开 chrome://version，返回 Profile Path。"""
    params = {"url": "about:blank", "background": True}
    if ctx:
        params["browserContextId"] = ctx
    created = await cdp.send("Target.createTarget", params, timeout=10)
    target_id = created["result"]["targetId"]
    try:
        attached = await cdp.send("Target.attachToTarget", {"targetId": target_id, "flatten": True})
        sid = attached["result"]["sessionId"]
        await cdp.send("Page.enable", {}, session_id=sid, timeout=10)
        await cdp.send("Page.navigate", {"url": "chrome://version"}, session_id=sid, timeout=10)
        await asyncio.sleep(1.5)
        resp = await cdp.send(
            "Runtime.evaluate",
            {"expression": "document.body ? document.body.innerText : ''", "returnByValue": True},
            session_id=sid,
            timeout=10,
        )
        text = resp.get("result", {}).get("result", {}).get("value", "")
        m = re.search(r"(?:个人资料路径|Profile Path)\s*[:\t]?\s*(.+)", text)
        return m.group(1).strip() if m else ""
    finally:
        try:
            await cdp.send("Target.closeTarget", {"targetId": target_id}, timeout=10)
        except Exception:
            pass


async def run(args) -> int:
    try:
        version = http_json(f"http://localhost:{args.port}/json/version")
    except Exception as exc:
        print(f"无法连接 CDP 端口 {args.port}: {exc}")
        return 1

    profile_names = load_profile_names(args.user_data_dir)
    result = []

    async with websockets.connect(version["webSocketDebuggerUrl"], max_size=2**26, open_timeout=10) as ws:
        cdp = CDP(ws)
        tgt = await cdp.send("Target.getTargets")
        pages = [t for t in tgt["result"]["targetInfos"] if t.get("type") == "page"]

        groups = {}
        for p in pages:
            groups.setdefault(p.get("browserContextId", ""), []).append(p)

        for ctx, ctx_pages in groups.items():
            row = {
                "browserContextId": ctx or "(default)",
                "account": "",
                "loginUserId": "",
                "runAsShopTitle": "",
                "cookies": 0,
                "tracknick": "",
                "unb": "",
                "profile_dir": "",
                "profile_name": "",
                "pages": [
                    {"title": p.get("title"), "url": p.get("url")}
                    for p in ctx_pages
                ],
                "error": "",
            }

            # 1) 页面 DOM 识别账号 + 页面级 Cookie
            for page in pick_page(ctx_pages):
                try:
                    sid = await asyncio.wait_for(attach_page(cdp, page["targetId"]), timeout=10)
                    raw = await asyncio.wait_for(evaluate(cdp, sid, JS_IDENTIFY), timeout=10)
                    info = json.loads(raw or "{}")
                    row["account"] = shop_hint(info.get("body", ""), info.get("runAsShopTitle", ""))
                    row["loginUserId"] = info.get("loginUserId", "")
                    row["runAsShopTitle"] = info.get("runAsShopTitle", "")
                    row["page_title"] = info.get("title", "")
                    row["page_url"] = info.get("url", "")
                    cookies = await asyncio.wait_for(
                        read_page_cookies(cdp, sid, info.get("url") or page.get("url") or ""),
                        timeout=10,
                    )
                    row["cookies"] = len(cookies)
                    def cookie(name):
                        return next((c.get("value", "") for c in cookies if c.get("name") == name), "")
                    row["tracknick"] = decode_cookie(cookie("tracknick"))
                    row["unb"] = cookie("unb")
                    break
                except Exception:
                    continue

            # 2) 页面级 Cookie 不可用时，再尝试 Storage.getCookies
            if row["cookies"] == 0:
                try:
                    ck = await cdp.send(
                        "Storage.getCookies",
                        {"browserContextId": ctx} if ctx else {},
                        timeout=10,
                    )
                    cookies = ck.get("result", {}).get("cookies", [])
                    row["cookies"] = len(cookies)
                    def cookie2(name):
                        return next((c.get("value", "") for c in cookies if c.get("name") == name), "")
                    row["tracknick"] = decode_cookie(cookie2("tracknick"))
                    row["unb"] = cookie2("unb")
                except Exception:
                    pass

            # 3) 可选：读取 Profile Path
            if args.profile_path:
                try:
                    path = await asyncio.wait_for(read_profile_path(cdp, ctx), timeout=15)
                    if path:
                        profile_dir = path.replace("/", "\\").rstrip("\\").split("\\")[-1]
                        row["profile_dir"] = profile_dir
                        row["profile_name"] = profile_names.get(profile_dir, "")
                except Exception as exc:
                    row["error"] = f"profile path: {exc}"

            result.append(row)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    for row in result:
        ctx = row["browserContextId"]
        account = row["account"] or row["tracknick"] or "(未识别)"
        login_id = row["loginUserId"] or row["unb"] or "-"
        page_title = row.get("page_title") or (row["pages"][0].get("title") if row["pages"] else "")
        page_url = row.get("page_url") or (row["pages"][0].get("url") if row["pages"] else "")
        profile = ""
        if row["profile_dir"]:
            profile = f" | profile={row['profile_dir']} ({row['profile_name'] or '?'})"
        print(f"\ncontext: {ctx}{profile}")
        print(f"  account: {account}")
        print(f"  loginUserId: {login_id}")
        print(f"  cookies: {row['cookies']} | tracknick={row['tracknick'] or '-'} | unb={row['unb'] or '-'}")
        print(f"  page: {page_title} | {page_url}")
        if row["error"]:
            print(f"  ! {row['error']}")

    return 0


def build_parser():
    p = argparse.ArgumentParser(description="列出 Chrome browser context、当前页和账号")
    p.add_argument("--port", type=int, default=DEFAULT_PORT)
    p.add_argument("--user-data-dir", default=DEFAULT_USER_DATA)
    p.add_argument("--profile-path", action="store_true",
                   help="额外开后台页读 chrome://version 的 Profile Path")
    p.add_argument("--json", action="store_true")
    return p


if __name__ == "__main__":
    args = build_parser().parse_args()
    try:
        raise SystemExit(asyncio.run(run(args)))
    except KeyboardInterrupt:
        raise SystemExit(130)
