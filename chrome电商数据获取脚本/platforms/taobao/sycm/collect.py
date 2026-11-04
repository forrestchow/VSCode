# -*- coding: utf-8 -*-
"""生意参谋多账号取数：CDP 读 Cookie → HTTP 取 token → 调 JSON 接口 → 存文件。

用法（从项目根目录）:
    python -m platforms.taobao.sycm.collect
    python -m platforms.taobao.sycm.collect --account 察尔汗
    python -m platforms.taobao.sycm.collect --item 731918476865 --date 2026-11-01
    python -m platforms.taobao.sycm.collect --endpoint sale_overview,flow_top
"""
from __future__ import annotations

import argparse
import asyncio
import json
import random
import re
import sys
import time
import urllib.parse
from dataclasses import dataclass, field
from datetime import date as date_cls
from pathlib import Path

import websockets

# 允许两种运行方式：python -m platforms.taobao.sycm.collect
# 或 python platforms/taobao/sycm/collect.py
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from core.browser_profiles import (
    CDP,
    JS_IDENTIFY,
    attach_page,
    decode_cookie,
    evaluate,
    http_json,
    pick_page,
    read_page_cookies,
    shop_hint,
)
from platforms.taobao.sycm.api import (
    BASE,
    ApiError,
    AuthError,
    MissingParamError,
    NoPermissionError,
    api_url,
    build_cookie_header,
    build_params,
    get_token,
    make_headers,
    request_json,
)

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

APP_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG = APP_DIR / "config.json"
ENDPOINTS_FILE = APP_DIR / "endpoints.json"

DEFAULT_ENDPOINTS = [
    "sale_overview",
    "sale_sku_list",
    "sale_trend",
    "flow_top",
    "searchword_top",
]

PAGE_HINTS = {
    "sale_overview": "activeKey=sale",
    "sale_sku_list": "activeKey=sale",
    "sale_trend": "activeKey=sale",
    "flow_top": "activeKey=flow",
    "searchword_top": "activeKey=flow",
}

INVALID_FILENAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


@dataclass
class Account:
    context_id: str
    shop: str
    login_user_id: str
    tracknick: str
    unb: str
    profile_name: str
    cookies: list[dict] = field(default_factory=list)
    headers: dict[str, str] = field(default_factory=dict)

    @property
    def key(self) -> str:
        return sanitize(f"{self.shop}_{self.login_user_id}")


@dataclass
class RunStats:
    success: int = 0
    skipped: int = 0
    failed: int = 0
    records: list[dict] = field(default_factory=list)
    started_at: str = ""
    finished_at: str = ""


def sanitize(name: str) -> str:
    cleaned = INVALID_FILENAME.sub("_", name or "").strip(" .")
    return cleaned[:80] or "unknown"


def log(message: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


def load_json(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(f"文件不存在: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"JSON 格式错误: {path}: {exc}")


def load_config(path: Path) -> dict:
    cfg = load_json(path)
    cfg.setdefault("port", 9223)
    cfg.setdefault("accounts", [])
    cfg.setdefault("items", [])
    cfg.setdefault("dates", [])
    cfg.setdefault("dateType", "day")
    cfg.setdefault("endpoints", DEFAULT_ENDPOINTS)
    cfg.setdefault("delay", [1, 3])
    cfg.setdefault("outputDir", "data")
    return cfg


def split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def as_str_list(value) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        return split_csv(value)
    return [str(item).strip() for item in value if str(item).strip()]


def parse_delay(value) -> tuple[float, float]:
    if isinstance(value, (int, float)):
        return float(value), float(value)
    if isinstance(value, str):
        if "-" in value:
            low, high = value.split("-", 1)
            return float(low), float(high)
        return float(value), float(value)
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return float(value[0]), float(value[1])
    return 1.0, 3.0


def build_page_url(page_key: str, item_id: str, date_type: str, date_range: str) -> str:
    """页面 URL 只用于取 token 和做 Referer，不会真的打开页面。"""
    url = BASE + page_key
    params = []
    if item_id:
        params.append(("itemId", item_id))
    if date_type:
        params.append(("dateType", date_type))
    if date_range and date_type != "today":
        params.append(("dateRange", date_range))
    if not params:
        return url
    separator = "&" if "?" in page_key else "?"
    return url + separator + urllib.parse.urlencode(params)


def resolve_endpoint(selector, endpoints_data: dict) -> tuple[str, str, dict]:
    """接口选择器：字符串，或 {"page": ..., "name": ..., "params": ...}。"""
    if isinstance(selector, str):
        name = selector
        page_key = ""
        overrides = {}
    elif isinstance(selector, dict):
        name = selector.get("name", "")
        page_key = selector.get("page", "")
        overrides = selector.get("params", {}) or {}
    else:
        raise SystemExit(f"endpoints 配置格式不对: {selector!r}")

    if not name:
        raise SystemExit(f"endpoints 配置缺少 name: {selector!r}")

    pages = endpoints_data.get("pages", {})
    if page_key:
        if page_key not in pages:
            raise SystemExit(f"endpoints.json 里没有页面: {page_key}")
        endpoint = pages[page_key].get("endpoints", {}).get(name)
        if not endpoint:
            raise SystemExit(f"页面 {page_key} 里没有接口: {name}")
        return page_key, name, {**endpoint, "overrides": overrides}

    # 只写了接口名时，同名接口优先选 PAGE_HINTS 对应的页面
    candidates = [
        (key, page["endpoints"][name])
        for key, page in pages.items()
        if name in page.get("endpoints", {})
    ]
    if not candidates:
        raise SystemExit(f"endpoints.json 里没有接口: {name}")
    hint = PAGE_HINTS.get(name, "")
    for key, endpoint in candidates:
        if hint and hint in key:
            return key, name, {**endpoint, "overrides": overrides}
    key, endpoint = candidates[0]
    return key, name, {**endpoint, "overrides": overrides}


async def identify_account(
    cdp: CDP, ctx: str, pages: list[dict], user_agent: str
) -> Account | None:
    info: dict = {}
    cookies: list[dict] = []

    for page in pick_page(pages):
        try:
            session_id = await asyncio.wait_for(
                attach_page(cdp, page["targetId"]), timeout=10
            )
            raw = await asyncio.wait_for(
                evaluate(cdp, session_id, JS_IDENTIFY), timeout=10
            )
            parsed = json.loads(raw or "{}")
            if isinstance(parsed, dict):
                info = parsed
            # 固定按 sycm 域取，不按当前页面的域取
            cookies = await asyncio.wait_for(
                read_page_cookies(cdp, session_id, "https://sycm.taobao.com/"),
                timeout=10,
            )
            if cookies or info.get("loginUserId"):
                break
        except Exception:
            continue

    if not cookies:
        try:
            response = await cdp.send(
                "Storage.getCookies",
                {"browserContextId": ctx} if ctx else {},
                timeout=10,
            )
            cookies = response.get("result", {}).get("cookies", [])
        except Exception:
            cookies = []

    def cookie_value(name: str) -> str:
        return next(
            (cookie.get("value", "") for cookie in cookies if cookie.get("name") == name),
            "",
        )

    tracknick = decode_cookie(cookie_value("tracknick"))
    unb = cookie_value("unb")
    login_user_id = info.get("loginUserId") or unb or tracknick
    shop = shop_hint(info.get("body", ""), info.get("runAsShopTitle", "")).strip() or tracknick
    if not shop:
        shop = f"账号_{login_user_id or ctx[:8]}"

    cookie_header = build_cookie_header(cookies)
    if not cookie_header:
        log(f"  ! context {ctx[:8] or '(default)'} 没有可用 Cookie，跳过")
        return None

    referer = info.get("url") or "https://sycm.taobao.com/"
    headers = make_headers(cookie_header, referer, user_agent)

    return Account(
        context_id=ctx or "(default)",
        shop=shop,
        login_user_id=login_user_id or "-",
        tracknick=tracknick,
        unb=unb,
        profile_name="",
        cookies=cookies,
        headers=headers,
    )


def fetch_endpoint(
    page_url: str,
    endpoint: dict,
    item_id: str,
    date_type: str,
    date_range: str,
    overrides: dict,
    headers: dict[str, str],
    token_cache: dict[tuple[str, str], str],
    token_key: tuple[str, str],
) -> tuple[dict, dict]:
    token = token_cache.get(token_key)
    if not token:
        token = get_token(page_url, headers)
        token_cache[token_key] = token

    params = build_params(endpoint, item_id, date_type, date_range, token, overrides)
    try:
        return request_json(api_url(endpoint["url"], params), headers), params
    except AuthError:
        # token 可能过期，重新取一次后再试
        log("    token 失效，重新获取后重试一次")
        token_cache.pop(token_key, None)
        token = get_token(page_url, headers)
        token_cache[token_key] = token
        params = build_params(endpoint, item_id, date_type, date_range, token, overrides)
        return request_json(api_url(endpoint["url"], params), headers), params


def save_payload(
    output_dir: Path,
    account: Account,
    item_id: str,
    date_str: str,
    page_key: str,
    endpoint_name: str,
    params: dict,
    response: dict,
) -> Path:
    path = (
        output_dir
        / account.key
        / sanitize(date_str)
        / sanitize(str(item_id))
        / f"{sanitize(endpoint_name)}.json"
    )
    path.parent.mkdir(parents=True, exist_ok=True)

    safe_params = {
        key: value for key, value in params.items() if key not in ("token", "_")
    }
    payload = {
        "account": {
            "shop": account.shop,
            "login_user_id": account.login_user_id,
            "tracknick": account.tracknick,
            "unb": account.unb,
            "browser_context_id": account.context_id,
            "profile_name": account.profile_name,
        },
        "item_id": item_id,
        "date": date_str,
        "page": page_key,
        "endpoint": endpoint_name,
        "request": safe_params,
        "response": response,
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return path


def write_summary(output_dir: Path, stats: RunStats, meta: dict) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    stats.finished_at = time.strftime("%Y-%m-%d %H:%M:%S")
    path = output_dir / f"_run_{time.strftime('%Y%m%d_%H%M%S')}.json"
    payload = {
        **meta,
        "started_at": stats.started_at,
        "finished_at": stats.finished_at,
        "success": stats.success,
        "skipped": stats.skipped,
        "failed": stats.failed,
        "records": stats.records,
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return path


async def collect_account(
    account: Account,
    items: list[str],
    dates: list[str],
    date_type: str,
    endpoints: list,
    endpoints_data: dict,
    output_dir: Path,
    delay: tuple[float, float],
    stats: RunStats,
) -> None:
    token_cache: dict[tuple[str, str], str] = {}
    log(
        f"账号：{account.shop} | loginUserId={account.login_user_id} "
        f"| cookies={len(account.cookies)}"
    )

    for item_id in items:
        for date_str in dates:
            date_range = f"{date_str}|{date_str}"
            log(f"  商品 {item_id} / {date_str}")

            for selector in endpoints:
                page_key, endpoint_name, endpoint = resolve_endpoint(
                    selector, endpoints_data
                )
                overrides = endpoint.get("overrides", {})
                page_url = build_page_url(page_key, item_id, date_type, date_range)
                headers = dict(account.headers)
                headers["Referer"] = page_url
                token_key = (account.key, page_key)
                label = f"{item_id} {date_str} {endpoint_name}"
                record = {
                    "account": account.shop,
                    "login_user_id": account.login_user_id,
                    "item_id": item_id,
                    "date": date_str,
                    "page": page_key,
                    "endpoint": endpoint_name,
                }

                try:
                    response, params = fetch_endpoint(
                        page_url,
                        endpoint,
                        item_id,
                        date_type,
                        date_range,
                        overrides,
                        headers,
                        token_cache,
                        token_key,
                    )
                except NoPermissionError as exc:
                    stats.skipped += 1
                    stats.records.append(
                        {**record, "status": "skip", "error": str(exc)}
                    )
                    log(f"    [跳过] {label}: {exc}")
                    await asyncio.sleep(random.uniform(*delay))
                    continue
                except MissingParamError as exc:
                    stats.failed += 1
                    stats.records.append(
                        {**record, "status": "failed", "error": str(exc)}
                    )
                    log(f"    [缺参数] {label}: {exc}")
                    await asyncio.sleep(random.uniform(*delay))
                    continue
                except ApiError as exc:
                    stats.failed += 1
                    stats.records.append(
                        {**record, "status": "failed", "error": str(exc)}
                    )
                    log(f"    [失败] {label}: {exc}")
                    await asyncio.sleep(random.uniform(*delay))
                    continue

                try:
                    path = save_payload(
                        output_dir,
                        account,
                        item_id,
                        date_str,
                        page_key,
                        endpoint_name,
                        params,
                        response,
                    )
                except OSError as exc:
                    stats.failed += 1
                    stats.records.append(
                        {**record, "status": "save_failed", "error": str(exc)}
                    )
                    log(f"    [保存失败] {label}: {exc}")
                    await asyncio.sleep(random.uniform(*delay))
                    continue

                stats.success += 1
                stats.records.append({**record, "status": "ok", "file": str(path)})
                log(f"    [OK] {label}")
                await asyncio.sleep(random.uniform(*delay))


async def run(args) -> int:
    cfg = load_config(Path(args.config))
    port = int(args.port or cfg.get("port", 9223))
    endpoints_data = load_json(ENDPOINTS_FILE)

    items = as_str_list(cfg.get("items"))
    if args.item:
        items = split_csv(args.item)

    dates = as_str_list(cfg.get("dates"))
    if args.date:
        dates = split_csv(args.date)

    if not items:
        log("config.items 为空，没有商品可采集")
        return 1
    if not dates:
        dates = [date_cls.today().isoformat()]

    if args.endpoint:
        endpoints = split_csv(args.endpoint)
    else:
        endpoints = cfg.get("endpoints") or DEFAULT_ENDPOINTS
        if isinstance(endpoints, str):
            endpoints = split_csv(endpoints)

    account_filters = as_str_list(cfg.get("accounts"))
    if args.account:
        account_filters = split_csv(args.account)

    delay = parse_delay(args.delay or cfg.get("delay", [1, 3]))
    date_type = str(cfg.get("dateType", "day"))

    output_dir = Path(args.output) if args.output else Path(cfg.get("outputDir", "data/taobao/sycm"))
    if not output_dir.is_absolute():
        output_dir = PROJECT_ROOT / output_dir

    try:
        version = http_json(f"http://localhost:{port}/json/version")
    except Exception as exc:
        log(f"无法连接 CDP 端口 {port}: {exc}")
        return 1

    user_agent = version.get("User-Agent", "Mozilla/5.0")
    stats = RunStats(started_at=time.strftime("%Y-%m-%d %H:%M:%S"))

    async with websockets.connect(
        version["webSocketDebuggerUrl"], max_size=2**26, open_timeout=10
    ) as websocket:
        cdp = CDP(websocket)
        targets = await cdp.send("Target.getTargets")
        pages = [
            target
            for target in targets["result"]["targetInfos"]
            if target.get("type") == "page"
        ]

        groups: dict[str, list[dict]] = {}
        for page in pages:
            groups.setdefault(page.get("browserContextId", ""), []).append(page)

        accounts: list[Account] = []
        seen_keys: set[str] = set()
        for ctx, ctx_pages in groups.items():
            account = await identify_account(cdp, ctx, ctx_pages, user_agent)
            if not account:
                continue
            if account_filters and not any(
                keyword in f"{account.shop} {account.tracknick} {account.login_user_id}"
                for keyword in account_filters
            ):
                continue
            if account.key in seen_keys:
                log(f"  ! 账号重复，跳过：{account.shop} {account.login_user_id}")
                continue
            seen_keys.add(account.key)
            accounts.append(account)

        if not accounts:
            log("没有匹配的账号。可先运行: python -m core.browser_profiles")
            return 1

        log(f"共 {len(accounts)} 个账号，{len(items)} 个商品，{len(dates)} 个日期")
        for account in accounts:
            try:
                await collect_account(
                    account,
                    items,
                    dates,
                    date_type,
                    endpoints,
                    endpoints_data,
                    output_dir,
                    delay,
                    stats,
                )
            except AuthError as exc:
                stats.failed += 1
                stats.records.append(
                    {
                        "account": account.shop,
                        "login_user_id": account.login_user_id,
                        "status": "auth_failed",
                        "error": str(exc),
                    }
                )
                log(f"账号 {account.shop} 登录态失效，跳过剩余：{exc}")
            except Exception as exc:
                stats.failed += 1
                stats.records.append(
                    {
                        "account": account.shop,
                        "login_user_id": account.login_user_id,
                        "status": "account_error",
                        "error": str(exc),
                    }
                )
                log(f"账号 {account.shop} 出错，跳过剩余：{exc}")
            await asyncio.sleep(random.uniform(3, 5))

    summary_path = write_summary(
        output_dir,
        stats,
        {
            "port": port,
            "items": items,
            "dates": dates,
            "date_type": date_type,
        },
    )
    log(f"完成：成功 {stats.success}，跳过 {stats.skipped}，失败 {stats.failed}")
    log(f"数据目录：{output_dir}")
    log(f"运行汇总：{summary_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生意参谋多账号取数")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument(
        "--account", default=None, help="只取包含该字符串的账号，逗号分隔"
    )
    parser.add_argument("--item", default=None, help="商品 ID，逗号分隔，覆盖 config")
    parser.add_argument(
        "--date", default=None, help="日期 YYYY-MM-DD，逗号分隔，覆盖 config"
    )
    parser.add_argument(
        "--endpoint", default=None, help="接口名，逗号分隔，覆盖 config"
    )
    parser.add_argument("--output", default=None, help="输出目录，覆盖 config")
    parser.add_argument("--delay", default=None, help="请求间隔，如 1-3")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        raise SystemExit(asyncio.run(run(args)))
    except KeyboardInterrupt:
        raise SystemExit(130)


if __name__ == "__main__":
    main()
