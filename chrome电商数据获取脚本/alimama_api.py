# -*- coding: utf-8 -*-
"""万相台无界版 HTTP 层：Cookie → checkAccess(csrfId) → JSON 接口。

不依赖页面执行 JS；Cookie / User-Agent 由 collect_alimama.py 从 CDP 提供。
接口来源与验证状态见 endpoints.json 的 alimama 段。
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://one.alimama.com"
REFERER = "https://one.alimama.com/index.html"
DEFAULT_TIMEOUT = 20
BIZ_CODE = "onebpSearch"

REPORT_FIELDS = [
    "charge",
    "alipayInshopAmt",
    "roi",
    "adPv",
    "click",
    "ctr",
    "ecpc",
    "cvr",
    "alipayInshopNum",
    "cartInshopNum",
    "cartRate",
    "alipayInshopCost",
]

CAMPAIGN_FIELDS = (
    "adPv,click,charge,ecpc,cvr,alipayInshopCost,roi,"
    "alipayInshopAmt,alipayInshopNum,ctr,cartInshopNum,cartCost"
)

ADGROUP_REPORT_FIELDS = [
    "charge",
    "alipayInshopAmt",
    "roi",
    "adPv",
    "click",
    "ctr",
    "ecpc",
    "cvr",
    "alipayInshopNum",
    "cartInshopNum",
    "cartRate",
    "alipayInshopCost",
]

# 报表页列表接口：同一个 POST /report/query.json，用 rptType + queryDomains 区分维度。
REPORT_LIST_FIELDS = [
    "adPv",
    "click",
    "charge",
    "ctr",
    "ecpc",
    "alipayInshopAmt",
    "alipayInshopNum",
    "cvr",
    "cartInshopNum",
    "itemColInshopNum",
    "shopColDirNum",
    "colNum",
    "itemColInshopCost",
]

# 各报表页的差异参数（抓包确认，2026-11-02）。rptType 同时是报表类型 key。
REPORT_LIST_SPECS: dict[str, dict] = {
    "item_promotion": {
        "label": "商品报表",
        "query_domains": ["promotion"],
        "extra": {"subPromotionTypes": ["ITEM"]},
        "fields": REPORT_LIST_FIELDS,
    },
    "item_promotion_campaign": {
        "label": "商品报表（商品×计划）",
        "rpt_type": "item_promotion",
        "query_domains": ["promotion", "campaign"],
        "extra": {"subPromotionTypes": ["ITEM"]},
        "fields": REPORT_LIST_FIELDS,
    },
    "item_promotion_adgroup": {
        "label": "商品报表（商品×计划×单元）",
        "rpt_type": "item_promotion",
        "query_domains": ["promotion", "campaign", "adgroup"],
        "extra": {"subPromotionTypes": ["ITEM"]},
        "fields": REPORT_LIST_FIELDS,
    },
    "campaign": {
        "label": "计划报表",
        "query_domains": ["campaign"],
        "extra": {},
        "fields": REPORT_LIST_FIELDS,
    },
    "adgroup": {
        "label": "单元报表",
        "query_domains": ["adgroup"],
        "extra": {"bizCodeIn": ["onebpSearch"]},
        "fields": REPORT_LIST_FIELDS,
    },
    "creative": {
        "label": "创意报表",
        "query_domains": ["creative", "promotion"],
        "extra": {},
        "fields": REPORT_LIST_FIELDS,
    },
    "crowd": {
        "label": "人群报表",
        "query_domains": ["crowd"],
        "extra": {
            "filterAppendSubwayChannel": True,
            "filterNullCrowdSubwayTag": True,
        },
        "fields": REPORT_LIST_FIELDS,
    },
    "bidword": {
        "label": "关键词报表",
        "query_domains": ["word"],
        "extra": {"isKeyWordNotContainChase": "true", "bizCodeIn": ["onebpSearch"]},
        "fields": [*REPORT_LIST_FIELDS, "avgRank"],
    },
    "area": {
        "label": "地域报表",
        "query_domains": ["province"],
        "extra": {},
        "fields": REPORT_LIST_FIELDS,
    },
}


class AlimamaError(Exception):
    """万相台接口错误的基类。"""


class AuthError(AlimamaError):
    """Cookie / csrfId 失效，或接口返回登录页。"""


class ApiError(AlimamaError):
    """接口业务错误或网络错误。"""


def build_cookie_header(cookies: list[dict]) -> str:
    """从 CDP Cookie 列表拼 Cookie 头：优先 alimama 域，跳过过期。"""
    now = time.time()
    seen: dict[str, tuple[int, str]] = {}
    for cookie in cookies:
        domain = cookie.get("domain", "") or ""
        if "alimama.com" not in domain and "taobao.com" not in domain:
            continue
        expires = cookie.get("expires", -1)
        if isinstance(expires, (int, float)) and 0 < expires < now:
            continue
        name = cookie.get("name")
        if not name:
            continue
        score = 2 if "alimama.com" in domain else 1
        value = cookie.get("value") or ""
        if name not in seen or score > seen[name][0]:
            seen[name] = (score, value)
    return "; ".join(f"{name}={value}" for name, (_, value) in seen.items())


def make_headers(cookie: str, user_agent: str, referer: str = REFERER) -> dict[str, str]:
    return {
        "Cookie": cookie,
        "User-Agent": user_agent,
        "Referer": referer,
        "Origin": BASE,
        "Content-Type": "application/json;charset=UTF-8",
        "Accept": "application/json, text/plain, */*",
        "x-requested-with": "XMLHttpRequest",
    }


def _post_json(
    path: str,
    payload: dict,
    headers: dict[str, str],
    query: dict | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> dict:
    url = BASE + path
    if query:
        url += "?" + urllib.parse.urlencode(query)
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        method="POST",
        headers=headers,
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            text = response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            raise AuthError(f"HTTP {exc.code}，Cookie 或 csrfId 失效") from exc
        raise ApiError(f"HTTP {exc.code}: {exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise ApiError(f"网络错误: {exc.reason}") from exc

    text = text.lstrip("﻿").strip()
    if not text:
        raise ApiError("接口返回空内容")
    if text.startswith("<"):
        raise AuthError("接口返回 HTML，登录态可能失效")
    try:
        obj = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ApiError(f"JSON 解析失败: {exc}") from exc
    if not isinstance(obj, dict):
        raise ApiError(f"返回不是 JSON 对象: {text[:200]}")

    info = obj.get("info") or {}
    if info.get("ok") is False:
        code = info.get("errorCode") or info.get("httpStatus") or "-"
        message = info.get("message") or ""
        raise ApiError(f"errorCode={code}, {message}")
    return obj


def check_access(headers: dict[str, str], timeout: float = DEFAULT_TIMEOUT) -> dict:
    """识别当前登录账号，并取得 csrfId / loginPointId。

    这个接口本身不需要 csrfId，是「不打开页面」链路的第一步。
    """
    obj = _post_json(
        "/member/checkAccess.json",
        {"bizCode": "universalBP"},
        headers,
        query={"bizCode": "universalBP"},
        timeout=timeout,
    )
    data = obj.get("data") or {}
    access = data.get("accessInfo") or {}
    meta = data.get("meta") or {}
    csrf_id = access.get("csrfId") or ""
    if not csrf_id:
        raise AuthError("checkAccess 未返回 csrfId，登录态可能失效")
    return {
        "csrfId": csrf_id,
        "loginPointId": data.get("loginPointId") or "",
        "shop": meta.get("nickName") or "",
        "memberId": meta.get("memberId"),
        "accountType": meta.get("accountType"),
    }


def build_report_body(
    start: str, end: str, split_type: str, is_today: bool, all_day: bool = False
) -> dict:
    """all_day 只影响历史日期的 sum：页面默认按「截至当前小时」统计。"""
    body = {
        "bizCode": BIZ_CODE,
        "mx_bizCode": BIZ_CODE,
        "startTime": start,
        "endTime": end,
        "sourceList": ["scene"],
        "queryFieldIn": list(REPORT_FIELDS),
    }
    if is_today:
        body.update({
            "fromRealTime": True,
            "splitType": split_type,
            "queryDomains": ["date"] if split_type == "hour" else [],
        })
    else:
        body.update({
            "fromRealTime": False,
            "fromHourTable": True,
            "needEffHour": False,
        })
        if split_type == "hour":
            body.update({"allDay": True, "splitType": "hour", "queryDomains": ["date"]})
        else:
            body.update({"allDay": bool(all_day), "splitType": "sum", "queryDomains": []})
    return body


def report_query(
    headers: dict[str, str],
    auth: dict,
    start: str,
    end: str,
    split_type: str = "sum",
    is_today: bool = True,
    all_day: bool = False,
    timeout: float = DEFAULT_TIMEOUT,
) -> list[dict]:
    """总览（sum）或分时（hour）报表；返回 data.list。"""
    body = build_report_body(start, end, split_type, is_today, all_day)
    body["csrfId"] = auth["csrfId"]
    body["loginPointId"] = auth.get("loginPointId") or ""
    obj = _post_json(
        "/report/query.json",
        body,
        headers,
        query={"csrfId": auth["csrfId"], "bizCode": BIZ_CODE},
        timeout=timeout,
    )
    return (obj.get("data") or {}).get("list") or []


def build_report_list_body(
    report_type: str,
    start: str,
    end: str,
    offset: int = 0,
    page_size: int = 20,
    is_today: bool = False,
) -> dict:
    """构造报表页列表请求体；今天用实时口径（fromRealTime=true）。"""
    spec = REPORT_LIST_SPECS.get(report_type)
    if not spec:
        choices = ", ".join(REPORT_LIST_SPECS)
        raise ValueError(f"未知报表类型: {report_type}（可选：{choices}）")
    body = {
        "bizCode": "universalBP",
        "fromRealTime": bool(is_today),
        "source": "baseReport",
        "byPage": True,
        "totalTag": True,
        "needCountAccelerate": True,
        "byPageWithoutCount": False,
        "rptType": spec.get("rpt_type", report_type),
        "pageSize": page_size,
        "offset": offset,
        "havingList": [],
        "endTime": end,
        "from": "pcBaseReport",
        "unifyType": "zhai",
        "effectEqual": 15,
        "startTime": start,
        "splitType": "day",
        "queryFieldIn": list(spec["fields"]),
        "queryDomains": list(spec["query_domains"]),
    }
    body.update(spec.get("extra") or {})
    return body


def report_list(
    headers: dict[str, str],
    auth: dict,
    report_type: str,
    start: str,
    end: str,
    offset: int = 0,
    page_size: int = 20,
    is_today: bool = False,
    timeout: float = DEFAULT_TIMEOUT,
) -> dict:
    """报表页列表（商品/计划/单元/创意/人群/关键词/地域）；返回 data。

    data 结构：count + totalData[0]（汇总行）+ list（维度行）。
    offset 分页已实测有效。
    """
    body = build_report_list_body(
        report_type, start, end, offset, page_size, is_today
    )
    body["csrfId"] = auth["csrfId"]
    body["loginPointId"] = auth.get("loginPointId") or ""
    obj = _post_json(
        "/report/query.json",
        body,
        headers,
        query={"csrfId": auth["csrfId"], "bizCode": "universalBP"},
        timeout=timeout,
    )
    return obj.get("data") or {}


def campaign_find_list(
    headers: dict[str, str],
    auth: dict,
    biz_code: str,
    status_list: tuple[str, ...] = ("start", "pause"),
    page_source: str = "simplifyQueryList",
    timeout: float = DEFAULT_TIMEOUT,
) -> list[dict]:
    """按场景列出在投/暂停计划（不依赖报表日期，可用于发现新计划）。"""
    body = {
        "statusList": list(status_list),
        "bizCode": biz_code,
        "pageSource": page_source,
        "csrfId": auth["csrfId"],
        "loginPointId": auth.get("loginPointId") or "",
    }
    obj = _post_json(
        "/campaign/findList.json",
        body,
        headers,
        query={"csrfId": auth["csrfId"], "bizCode": biz_code},
        timeout=timeout,
    )
    return (obj.get("data") or {}).get("list") or []


def adgroup_find_list(
    headers: dict[str, str],
    auth: dict,
    biz_code: str,
    campaign_id: int | str,
    status_list: tuple[str, ...] = ("start", "pause"),
    timeout: float = DEFAULT_TIMEOUT,
) -> list[dict]:
    """计划下的单元列表（不打开页面）。"""
    body = {
        "statusList": list(status_list),
        "bizCode": biz_code,
        "campaignId": str(campaign_id),
        "csrfId": auth["csrfId"],
        "loginPointId": auth.get("loginPointId") or "",
    }
    obj = _post_json(
        "/adgroup/findList.json",
        body,
        headers,
        query={"csrfId": auth["csrfId"], "bizCode": biz_code},
        timeout=timeout,
    )
    return (obj.get("data") or {}).get("list") or []


def adgroup_get(
    headers: dict[str, str],
    auth: dict,
    biz_code: str,
    campaign_id: int | str,
    adgroup_id: int | str,
    timeout: float = DEFAULT_TIMEOUT,
) -> dict:
    """单元设置/详情（adgroupName、onlineStatus、出价类型、智能创意等）。"""
    body = {
        "bizCode": biz_code,
        "campaignId": str(campaign_id),
        "adgroupId": str(adgroup_id),
        "csrfId": auth["csrfId"],
        "loginPointId": auth.get("loginPointId") or "",
    }
    obj = _post_json(
        "/adgroup/get.json",
        body,
        headers,
        query={"csrfId": auth["csrfId"], "bizCode": biz_code},
        timeout=timeout,
    )
    return (obj.get("data") or {}).get("adgroup") or {}


def adgroup_report_query(
    headers: dict[str, str],
    auth: dict,
    biz_code: str,
    campaign_id: int | str,
    adgroup_id: int | str,
    start: str,
    end: str,
    fields: list[str] | None = None,
    is_today: bool = False,
    timeout: float = DEFAULT_TIMEOUT,
) -> list[dict]:
    """单元维度报表；返回 data.list（单日或区间汇总）。

    查今天时必须 is_today=True（fromRealTime=true），否则返回空。
    """
    body = {
        "bizCode": biz_code,
        "mx_bizCode": biz_code,
        "campaignId": str(campaign_id),
        "adgroupId": str(adgroup_id),
        "startTime": start,
        "endTime": end,
        "strategyCampaignIdIn": [int(campaign_id)],
        "strategyAdgroupIdIn": [int(adgroup_id)],
        "sourceList": ["adgroup_detail"],
        "queryFieldIn": list(fields or ADGROUP_REPORT_FIELDS),
        "csrfId": auth["csrfId"],
        "loginPointId": auth.get("loginPointId") or "",
    }
    if is_today:
        body["fromRealTime"] = True
    obj = _post_json(
        "/report/query.json",
        body,
        headers,
        query={"csrfId": auth["csrfId"], "bizCode": biz_code},
        timeout=timeout,
    )
    return (obj.get("data") or {}).get("list") or []


def adgroup_time_series(
    headers: dict[str, str],
    auth: dict,
    biz_code: str,
    campaign_id: int | str,
    adgroup_id: int | str,
    start: str,
    end: str,
    split_type: str = "day",
    fields: list[str] | None = None,
    is_today: bool = False,
    timeout: float = DEFAULT_TIMEOUT,
) -> list[dict]:
    """单元时间明细（按日/小时）。

    返回的行只包含有数据的日期；页面会把缺失日期补 0。
    查今天时必须 is_today=True（fromRealTime=true），否则返回空。
    """
    body = {
        "bizCode": biz_code,
        "mx_bizCode": biz_code,
        "campaignId": str(campaign_id),
        "adgroupId": str(adgroup_id),
        "startTime": start,
        "endTime": end,
        "strategyCampaignIdIn": [int(campaign_id)],
        "strategyAdgroupIdIn": [int(adgroup_id)],
        "sourceList": ["adgroup_detail"],
        "queryDomains": ["date"],
        "splitType": split_type,
        "queryFieldIn": list(fields or ADGROUP_REPORT_FIELDS),
        "csrfId": auth["csrfId"],
        "loginPointId": auth.get("loginPointId") or "",
    }
    if is_today:
        body["fromRealTime"] = True
    obj = _post_json(
        "/report/query.json",
        body,
        headers,
        query={"csrfId": auth["csrfId"], "bizCode": biz_code},
        timeout=timeout,
    )
    return (obj.get("data") or {}).get("list") or []


def build_campaign_body(
    start: str, end: str, offset: int, page_size: int, is_today: bool
) -> dict:
    return {
        "offset": offset,
        "pageSize": page_size,
        "orderField": "",
        "orderBy": "",
        "mx_bizCode": BIZ_CODE,
        "bizCode": BIZ_CODE,
        "rptQuery": {
            "fields": CAMPAIGN_FIELDS,
            "conditionList": [{
                "sourceList": ["scene", "campaign_list"],
                "startTime": start,
                "endTime": end,
                "isRt": bool(is_today),
            }],
        },
    }


def campaign_find_page(
    headers: dict[str, str],
    auth: dict,
    start: str,
    end: str,
    offset: int = 0,
    page_size: int = 40,
    is_today: bool = False,
    timeout: float = DEFAULT_TIMEOUT,
) -> dict:
    """计划列表（含 rptQuery 指标）；返回 data，包含 count / list。"""
    body = build_campaign_body(start, end, offset, page_size, is_today)
    body["csrfId"] = auth["csrfId"]
    body["loginPointId"] = auth.get("loginPointId") or ""
    obj = _post_json(
        "/campaign/horizontal/findPage.json",
        body,
        headers,
        query={"csrfId": auth["csrfId"], "bizCode": BIZ_CODE},
        timeout=timeout,
    )
    return obj.get("data") or {}
