# -*- coding: utf-8 -*-
"""生意参谋 HTTP 层：Cookie、token、接口请求、返回码处理。

不依赖页面执行 JS；Cookie 和 User-Agent 由 collect.py 从 CDP 提供。
"""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://sycm.taobao.com"
DEFAULT_TIMEOUT = 20


class SycmError(Exception):
    """所有接口错误的基类。"""


class AuthError(SycmError):
    """Cookie / token 失效，或返回登录页。"""


class NoPermissionError(SycmError):
    """当前账号没有该商品 / 接口权限（code=1100）。"""


class MissingParamError(SycmError):
    """接口缺参数（code=1003）。"""


class ApiError(SycmError):
    """其他接口或网络错误。"""


def build_cookie_header(cookies: list[dict]) -> str:
    """从 CDP Cookie 列表拼 Cookie 头：优先 sycm 域，跳过过期。"""
    now = time.time()
    seen: dict[str, tuple[int, str]] = {}
    for cookie in cookies:
        domain = cookie.get("domain", "") or ""
        if "taobao.com" not in domain and "tmall.com" not in domain:
            continue
        expires = cookie.get("expires", -1)
        if isinstance(expires, (int, float)) and 0 < expires < now:
            continue
        name = cookie.get("name")
        if not name:
            continue
        score = 2 if "sycm.taobao.com" in domain else 1
        value = cookie.get("value") or ""
        if name not in seen or score > seen[name][0]:
            seen[name] = (score, value)
    return "; ".join(f"{name}={value}" for name, (_, value) in seen.items())


def make_headers(cookie: str, referer: str, user_agent: str) -> dict[str, str]:
    return {
        "Cookie": cookie,
        "User-Agent": user_agent,
        "Referer": referer,
        "Accept": "application/json, text/plain, */*",
        "Origin": BASE,
        "x-requested-with": "XMLHttpRequest",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Dest": "empty",
    }


def get_html(page_url: str, headers: dict[str, str], timeout: float = DEFAULT_TIMEOUT) -> str:
    """GET 页面 HTML（不开 tab、不渲染）。"""
    request_headers = dict(headers)
    request_headers["Accept"] = (
        "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    )
    request = urllib.request.Request(page_url, headers=request_headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            raise AuthError(f"页面 HTTP {exc.code}") from exc
        raise ApiError(f"页面 HTTP {exc.code}: {exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise ApiError(f"页面网络错误: {exc.reason}") from exc


_META_NAME_FIRST = re.compile(
    r'<meta[^>]*name=["\']microdata["\'][^>]*content=["\']([^"\']*)["\']',
    re.IGNORECASE,
)
_META_CONTENT_FIRST = re.compile(
    r'<meta[^>]*content=["\']([^"\']*)["\'][^>]*name=["\']microdata["\']',
    re.IGNORECASE,
)


def parse_token(html: str) -> str:
    """从 HTML 的 meta[microdata] 里取 legalityToken。"""
    match = _META_NAME_FIRST.search(html) or _META_CONTENT_FIRST.search(html)
    if not match:
        head = html[:20000].lower()
        if "login" in head or "登录" in head:
            raise AuthError("页面是登录页，Cookie 可能已失效")
        raise AuthError("找不到 meta[microdata]，Cookie 可能已失效")

    token_match = re.search(r"(?:^|;)legalityToken=([^;]*)", match.group(1))
    if not token_match:
        raise AuthError("meta[microdata] 里没有 legalityToken")
    token = token_match.group(1)
    if not token:
        raise AuthError("legalityToken 为空")
    return token


def get_token(page_url: str, headers: dict[str, str], timeout: float = DEFAULT_TIMEOUT) -> str:
    """GET 页面 HTML 并解析 token。每个账号 / 页面各自取，不能跨账号复用。"""
    return parse_token(get_html(page_url, headers, timeout=timeout))


def api_url(path: str, params: dict) -> str:
    return BASE + path + "?" + urllib.parse.urlencode(params)


def parse_endpoint_params(param_list: list[str]) -> tuple[list[str], dict[str, str]]:
    """把 endpoints.json 的 params 拆成参数名和默认值。

    "device=0" -> 参数名 device，默认值 "0"
    "itemId"   -> 参数名 itemId，无默认值
    """
    names: list[str] = []
    defaults: dict[str, str] = {}
    for item in param_list or []:
        if "=" in item:
            name, value = item.split("=", 1)
            names.append(name)
            defaults[name] = value
        else:
            names.append(item)
    return names, defaults


def build_params(
    endpoint: dict,
    item_id: str,
    date_type: str,
    date_range: str,
    token: str,
    overrides: dict | None = None,
) -> dict:
    """公共参数 + 接口默认值 + config 覆盖。"""
    names, params = parse_endpoint_params(endpoint.get("params", []))

    if "itemId" in names and item_id:
        params["itemId"] = item_id
    if "itemIds" in names and item_id:
        params["itemIds"] = item_id
    if "dateType" in names and date_type and "dateType" not in params:
        params["dateType"] = date_type
    if "dateRange" in names and date_range and "dateRange" not in params:
        params["dateRange"] = date_range

    params["token"] = token
    params["_"] = int(time.time() * 1000)

    if overrides:
        params.update({
            key: value
            for key, value in overrides.items()
            if key not in ("token", "_") and value is not None
        })
    return params


def _check_code(obj: dict) -> None:
    raw_code = obj.get("code")
    try:
        code = int(raw_code)
    except (TypeError, ValueError):
        raise ApiError(
            f"返回里没有 code：{json.dumps(obj, ensure_ascii=False)[:300]}"
        )

    if code == 0:
        return

    message = obj.get("message") or obj.get("msg") or ""
    if code == 1100:
        raise NoPermissionError(f"code=1100, {message}")
    if code == 1003:
        raise MissingParamError(f"code=1003, {message}")
    if code in (401, 403):
        raise AuthError(f"code={code}, {message}")
    raise ApiError(f"code={code}, {message}")


def request_json(url: str, headers: dict[str, str], timeout: float = DEFAULT_TIMEOUT) -> dict:
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            text = response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            raise AuthError(f"HTTP {exc.code}") from exc
        raise ApiError(f"HTTP {exc.code}: {exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise ApiError(f"网络错误: {exc.reason}") from exc

    text = text.lstrip("﻿").strip()
    if not text:
        raise ApiError("接口返回空内容")
    if text.startswith("<") or "<html" in text[:500].lower():
        raise AuthError("接口返回 HTML，登录态可能失效")

    try:
        obj = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ApiError(f"JSON 解析失败: {exc}") from exc

    if not isinstance(obj, dict):
        raise ApiError(f"返回不是 JSON 对象: {text[:200]}")
    _check_code(obj)
    return obj
