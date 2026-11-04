# -*- coding: utf-8 -*-
"""万相台无界版（one.alimama.com）取数：CDP 读 Cookie → checkAccess → JSON 接口 → 存文件。

用法（从项目根目录）:
    python -m platforms.taobao.alimama.collect
    python -m platforms.taobao.alimama.collect --account 察尔汗 --date 2026-11-02
    python -m platforms.taobao.alimama.collect --reports item_promotion
    python -m platforms.taobao.alimama.collect --reports item_promotion_campaign,item_promotion_adgroup
    python -m platforms.taobao.alimama.collect --days 7
    python -m platforms.taobao.alimama.collect --port 9222 --output data/taobao/alimama --delay 1-3

不开 tab、不渲染页面；只要求对应店铺的 Chrome 以 debug 端口启动且已登录万相台。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import random
import re
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date as date_cls
from datetime import timedelta
from pathlib import Path

import websockets

# 允许两种运行方式：python -m platforms.taobao.alimama.collect
# 或 python platforms/taobao/alimama/collect.py
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from platforms.taobao.alimama.api import (
    REPORT_LIST_SPECS,
    AlimamaError,
    ApiError,
    AuthError,
    build_cookie_header,
    campaign_find_page,
    check_access,
    make_headers,
    report_list,
    report_query,
)
from core.browser_profiles import CDP, http_json

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

APP_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG = APP_DIR / "config.json"
INVALID_FILENAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


@dataclass
class RunStats:
    success: int = 0
    failed: int = 0
    records: list[dict] = field(default_factory=list)
    started_at: str = ""
    finished_at: str = ""


def sanitize(name: str) -> str:
    cleaned = INVALID_FILENAME.sub("_", str(name or "")).strip(" .")
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
    if not path.exists():
        cfg: dict = {}
    else:
        cfg = load_json(path)
    cfg.setdefault("port", 9222)
    cfg.setdefault("accounts", [])
    cfg.setdefault("dates", [])
    cfg.setdefault("campaignPageSize", 40)
    cfg.setdefault("reportPageSize", 100)
    cfg.setdefault("reports", [])
    cfg.setdefault("delay", [1, 3])
    cfg.setdefault("outputDir", "data/taobao/alimama")
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


def resolve_dates(args, cfg: dict) -> list[str]:
    if args.days:
        if args.date:
            raise SystemExit("--date 和 --days 只能二选一")
        days = int(args.days)
        if days <= 0:
            raise SystemExit("--days 必须是正整数")
        today = date_cls.today()
        return [(today - timedelta(days=i)).isoformat() for i in range(days - 1, -1, -1)]

    raw = args.date if args.date else cfg.get("dates")
    items = as_str_list(raw)
    if not items:
        return [date_cls.today().isoformat()]
    dates = []
    for item in items:
        try:
            date_cls.fromisoformat(item)
        except ValueError:
            raise SystemExit(f"日期格式不对，应为 YYYY-MM-DD: {item}")
        dates.append(item)
    return dates


async def read_browser_cookies(port: int) -> tuple[str, list[dict]]:
    """浏览器级 CDP 读 Cookie；不创建 tab、不导航。"""
    version = http_json(f"http://localhost:{port}/json/version")
    user_agent = version.get("User-Agent", "Mozilla/5.0")
    async with websockets.connect(
        version["webSocketDebuggerUrl"], max_size=2**26, open_timeout=10
    ) as websocket:
        cdp = CDP(websocket)
        response = await cdp.send("Storage.getCookies", {})
    cookies = response.get("result", {}).get("cookies", []) or []
    return user_agent, cookies


def call_with_refresh(fn, headers: dict[str, str], auth: dict):
    """csrfId 失效时重新 checkAccess 并重试一次。"""
    try:
        return fn()
    except AuthError:
        log("  csrfId 可能过期，重新 checkAccess 后重试")
        auth.update(check_access(headers))
        return fn()


def fetch_campaigns(
    headers: dict[str, str],
    auth: dict,
    date_str: str,
    is_today: bool,
    page_size: int,
    delay: tuple[float, float],
) -> dict:
    items: list[dict] = []
    offset = 0
    count = 0
    while True:
        data = call_with_refresh(
            lambda: campaign_find_page(
                headers, auth, date_str, date_str, offset, page_size, is_today
            ),
            headers,
            auth,
        )
        page_items = data.get("list") or []
        items.extend(page_items)
        count = data.get("count") or count
        time.sleep(random.uniform(*delay))
        if len(page_items) < page_size:
            break
        if count and len(items) >= count:
            break
        offset += page_size
    return {"count": count or len(items), "list": items}


def fetch_report_list(
    headers: dict[str, str],
    auth: dict,
    report_type: str,
    date_str: str,
    is_today: bool,
    page_size: int,
    delay: tuple[float, float],
) -> dict:
    """按 offset 翻页取完一个报表页的列表。"""
    items: list[dict] = []
    total_data: list[dict] = []
    count = 0
    offset = 0
    while True:
        data = call_with_refresh(
            lambda off=offset: report_list(
                headers, auth, report_type, date_str, date_str, off, page_size, is_today
            ),
            headers,
            auth,
        )
        page_items = data.get("list") or []
        items.extend(page_items)
        total_data = data.get("totalData") or total_data
        count = data.get("count") or count
        time.sleep(random.uniform(*delay))
        if len(page_items) < page_size:
            break
        if count and len(items) >= count:
            break
        offset += page_size
    return {
        "count": count or len(items),
        "totalData": total_data,
        "list": items,
        "pageSize": page_size,
    }


def save_payload(
    output_dir: Path,
    account: dict,
    date_str: str,
    endpoint: str,
    request: dict,
    response,
) -> Path:
    path = (
        output_dir
        / sanitize(f"{account.get('shop')}_{account.get('memberId')}")
        / sanitize(date_str)
        / f"{sanitize(endpoint)}.json"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "account": {
            "shop": account.get("shop"),
            "member_id": account.get("memberId"),
        },
        "date": date_str,
        "endpoint": endpoint,
        "request": request,
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
        "failed": stats.failed,
        "records": stats.records,
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return path


def collect_date(
    headers: dict[str, str],
    auth: dict,
    date_str: str,
    output_dir: Path,
    page_size: int,
    reports: list[str],
    report_page_size: int,
    delay: tuple[float, float],
    with_hourly: bool,
    with_campaigns: bool,
    full_day: bool,
    stats: RunStats,
) -> None:
    is_today = date_str == date_cls.today().isoformat()
    all_day = bool(full_day and not is_today)
    suffix = "（今天，实时）" if is_today else ("（全天口径）" if all_day else "（页面口径：截至当前小时）")
    log(f"  日期 {date_str}{suffix}")

    jobs: list[tuple[str, str, dict, Callable[[], object]]] = []
    jobs.append((
        "overview",
        "总览",
        {"startTime": date_str, "endTime": date_str, "splitType": "sum", "allDay": all_day},
        lambda: report_query(headers, auth, date_str, date_str, "sum", is_today, all_day),
    ))
    if with_hourly:
        jobs.append((
            "hourly",
            "分时",
            {"startTime": date_str, "endTime": date_str, "splitType": "hour"},
            lambda: report_query(headers, auth, date_str, date_str, "hour", is_today),
        ))
    if with_campaigns:
        jobs.append((
            "campaigns",
            "计划列表",
            {"startTime": date_str, "endTime": date_str, "pageSize": page_size},
            lambda: fetch_campaigns(headers, auth, date_str, is_today, page_size, delay),
        ))
    for report_type in reports:
        spec = REPORT_LIST_SPECS[report_type]
        jobs.append((
            report_type,
            spec["label"],
            {
                "startTime": date_str,
                "endTime": date_str,
                "pageSize": report_page_size,
                "rptType": spec.get("rpt_type", report_type),
                "queryDomains": list(spec["query_domains"]),
                "fromRealTime": is_today,
            },
            lambda rt=report_type: fetch_report_list(
                headers, auth, rt, date_str, is_today, report_page_size, delay
            ),
        ))

    for name, label, request, fn in jobs:
        try:
            response = call_with_refresh(fn, headers, auth)
        except ApiError as exc:
            stats.failed += 1
            stats.records.append({
                "date": date_str,
                "endpoint": name,
                "status": "failed",
                "error": str(exc),
            })
            log(f"    [失败] {label}: {exc}")
            time.sleep(random.uniform(*delay))
            continue
        except AlimamaError as exc:
            stats.failed += 1
            stats.records.append({
                "date": date_str,
                "endpoint": name,
                "status": "failed",
                "error": str(exc),
            })
            log(f"    [失败] {label}: {exc}")
            time.sleep(random.uniform(*delay))
            continue

        try:
            path = save_payload(output_dir, auth, date_str, name, request, response)
        except OSError as exc:
            stats.failed += 1
            stats.records.append({
                "date": date_str,
                "endpoint": name,
                "status": "save_failed",
                "error": str(exc),
            })
            log(f"    [保存失败] {label}: {exc}")
            time.sleep(random.uniform(*delay))
            continue

        stats.success += 1
        stats.records.append({
            "date": date_str,
            "endpoint": name,
            "status": "ok",
            "file": str(path),
        })
        if name == "campaigns":
            log(f"    [OK] {label}: {response.get('count')} 个计划")
        elif name in REPORT_LIST_SPECS:
            log(f"    [OK] {label}: {response.get('count')} 条")
        elif name == "hourly":
            log(f"    [OK] {label}: {len(response)} 行")
        else:
            log(f"    [OK] {label}")
        time.sleep(random.uniform(*delay))


async def run(args) -> int:
    cfg = load_config(Path(args.config))
    port = int(args.port or cfg.get("port", 9222))
    page_size = int(args.page_size or cfg.get("campaignPageSize", 40))
    report_page_size = int(args.report_page_size or cfg.get("reportPageSize", 100))
    raw_reports = args.reports if args.reports is not None else cfg.get("reports")
    reports = as_str_list(raw_reports)
    unknown_reports = [name for name in reports if name not in REPORT_LIST_SPECS]
    if unknown_reports:
        raise SystemExit(
            f"未知报表类型: {', '.join(unknown_reports)}"
            f"（可选：{', '.join(REPORT_LIST_SPECS)}）"
        )
    delay = parse_delay(args.delay or cfg.get("delay", [1, 3]))
    dates = resolve_dates(args, cfg)

    output_dir = Path(args.output) if args.output else Path(cfg.get("outputDir", "data/taobao/alimama"))
    if not output_dir.is_absolute():
        output_dir = PROJECT_ROOT / output_dir

    account_filters = as_str_list(cfg.get("accounts"))
    if args.account:
        account_filters = split_csv(args.account)

    try:
        user_agent, cookies = await read_browser_cookies(port)
    except Exception as exc:
        log(f"无法连接 CDP 端口 {port}: {exc}")
        return 1

    cookie_header = build_cookie_header(cookies)
    if not cookie_header:
        log("没有可用的 alimama / taobao Cookie，请确认该 profile 已登录万相台")
        return 1

    headers = make_headers(cookie_header, user_agent)
    try:
        auth = check_access(headers)
    except AuthError as exc:
        log(f"登录态失效：{exc}")
        return 1
    except ApiError as exc:
        log(f"checkAccess 失败：{exc}")
        return 1

    account_label = f"{auth.get('shop') or '-'} ({auth.get('memberId') or '-'})"
    if account_filters and not any(
        keyword in f"{auth.get('shop') or ''} {auth.get('memberId') or ''}"
        for keyword in account_filters
    ):
        log(f"当前账号 {account_label} 不匹配过滤条件，跳过")
        return 0

    log(f"账号：{account_label} | cookies={len(cookies)}")
    log(
        f"日期：{', '.join(dates)} | 报表页：{', '.join(reports) or '-'}"
        f" | 端口：{port} | 输出：{output_dir}"
    )

    stats = RunStats(started_at=time.strftime("%Y-%m-%d %H:%M:%S"))
    for date_str in dates:
        collect_date(
            headers,
            auth,
            date_str,
            output_dir,
            page_size,
            reports,
            report_page_size,
            delay,
            with_hourly=not args.no_hourly,
            with_campaigns=not args.no_campaigns,
            full_day=args.full_day,
            stats=stats,
        )

    summary_path = write_summary(
        output_dir,
        stats,
        {
            "port": port,
            "shop": auth.get("shop"),
            "member_id": auth.get("memberId"),
            "dates": dates,
        },
    )
    log(f"完成：成功 {stats.success}，失败 {stats.failed}")
    log(f"数据目录：{output_dir}")
    log(f"运行汇总：{summary_path}")
    return 0 if stats.failed == 0 else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="万相台无界版关键词推广取数")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--port", type=int, default=None, help="Chrome CDP 端口，默认 9222")
    parser.add_argument("--account", default=None, help="只保留包含该字符串的账号")
    parser.add_argument("--date", default=None, help="日期 YYYY-MM-DD，逗号分隔")
    parser.add_argument("--days", type=int, default=None, help="最近 N 天（含今天）")
    parser.add_argument("--page-size", type=int, default=None, help="计划列表每页条数")
    parser.add_argument("--output", default=None, help="输出目录，覆盖 config")
    parser.add_argument("--delay", default=None, help="请求间隔，如 1-3")
    parser.add_argument(
        "--full-day",
        action="store_true",
        help="历史日期总览用全天口径（默认与页面一致：截至当前小时）",
    )
    parser.add_argument("--no-hourly", action="store_true", help="不采分时报表")
    parser.add_argument("--no-campaigns", action="store_true", help="不采计划列表")
    parser.add_argument(
        "--reports",
        default=None,
        help="报表页列表，逗号分隔：item_promotion,item_promotion_campaign,item_promotion_adgroup,campaign,adgroup,creative,crowd,bidword,area",
    )
    parser.add_argument(
        "--report-page-size",
        type=int,
        default=None,
        help="报表页每页条数，默认 100",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        raise SystemExit(asyncio.run(run(args)))
    except KeyboardInterrupt:
        raise SystemExit(130)


if __name__ == "__main__":
    main()
