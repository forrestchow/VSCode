# 02 · URL 与接口映射

> 标记说明：
> - ✅ **已验证**：实际调用过，返回 `code:0` 和预期数据。
> - ⚠️ **代码确认**：从 op-cc 的 JS 中确认了调用方式和参数，但没有逐个实测。
> - ❌ **未验证**：只知道页面路由，接口需要重新定位。

## 1. 页面 → 接口总览

| 页面 URL | 页面名称 | 主要接口 |
|---|---|---|
| `/cc/item_rank` | 商品排行 | `/cc/item/view/top.json`、`/cc/item/live/view/top.json`、`/cc/item/view/foucs.json`、`/cc/item/sku/top.json`、`/cc/item/searchword/top/v3.json` |
| `/cc/item_archives?activeKey=sale` | 商品360 · 销售 | `/cc/item/sale/overview.json`、`sale/sku/list.json`、`sale/trend.json`、`crowd/info.json`、`getItemCrowds.json` 等 |
| `/cc/item_archives?activeKey=flow` | 商品360 · 流量 | `/cc/item/flow/top/v4.json`、`searchword/top/v3.json`、`/flow/qzt/item/crowdtype/source/trend.json`、`/flow/v4/item/source/cc/security.json` 等 |
| `/cc/item_archives?activeKey=service` | 商品360 · 服务 | ❌ 未验证 |
| `/cc/item_archives?activeKey=customer` | 商品360 · 客户 | ❌ 未验证 |
| `/cc/item_archives?activeKey=content` | 商品360 · 内容 | ❌ 未验证 |

> `activeKey` 是前端路由参数，**不会**作为 API 参数传给后端。
> 换 tab = 前端调用另一组接口，不是同一个接口换参数。

## 2. 商品排行 `/cc/item_rank`

| 接口 | 用途 | 关键参数 | 状态 |
|---|---|---|---|
| `/cc/item/view/top.json` | 商品排行（日/周/月） | `itemId`, `dateType`, `dateRange`, `page`, `pageSize`, `order`, `orderBy` | ⚠️ 代码确认 |
| `/cc/item/live/view/top.json` | 实时商品排行 | `dateType=today`, `page`, `pageSize`, `order`, `orderBy` | ⚠️ 代码确认 |
| `/cc/item/view/foucs.json` | 我关注的商品 | `itemId`, `dateType`, `dateRange`, `page`, `pageSize` | ⚠️ 代码确认 |
| `/cc/item/view/foucs/live.json` | 实时关注商品 | `dateType=today`, `page`, `pageSize` | ⚠️ 代码确认 |
| `/cc/item/view/angle/select.json` | 视角选择 | `token`, `_` | ⚠️ 代码确认 |
| `/cc/item/view/excel/top.json` | 排行榜导出 | 同上 + 导出参数 | ⚠️ 代码确认 |
| `/cc/item/sku/top.json` | Top5 SKU 销售摘要卡（“更多”指向 `activeKey=sale`） | `itemId`, `pageSize`, `dateType`, `dateRange` | ✅ 已验证 |
| `/cc/item/searchword/top/v3.json` | 搜索词 Top | `itemId`, `page`, `pageSize`, `dateType`, `dateRange` | ✅ 已验证 |
| `/cc/item/price/hasPriceAct.json` | 是否有价格活动 | `itemId` | ⚠️ 代码确认 |
| `/cc/item/price/analysis/trend/live.json` | 实时价格趋势 | `itemId` | ⚠️ 代码确认 |

> `sku/top.json` 是“Top5 SKU销售”摘要卡，代码里的“更多”链接指向 `activeKey=sale`，属于销售语境；`searchword/top/v3.json` 的“更多”链接指向 `activeKey=flow`，属于流量语境。

示例：

```http
GET /cc/item/view/top.json?dateType=day&dateRange=2026-11-01%7C2026-11-01&page=1&pageSize=10&order=desc&orderBy=payAmt&_={ts}&token={token}
```

## 3. 商品360 · 销售 `/cc/item_archives?activeKey=sale`

| 接口 | 用途 | 关键参数 | 状态 |
|---|---|---|---|
| `/cc/item/sale/overview.json` | 销售总览 | `itemId`, `dateType`, `dateRange`, `device=0` | ✅ 已验证 |
| `/cc/item/sale/sku/list.json` | SKU 销售明细 | `itemId`, `dateType`, `dateRange`, `device=0`, `page`, `pageSize`, `order`, `orderBy`, `indexCode` | ✅ 已验证 |
| `/cc/item/sale/trend.json` | 30 天趋势 | `itemId`, `dateType`, `dateRange`, `device=0`, `indexCode=itmUv` | ✅ 已验证 |
| `/cc/item/sku/top.json` | Top5 SKU 销售摘要卡（“更多”指向 `activeKey=sale`） | `itemId`, `pageSize=10`, `dateType`, `dateRange` | ✅ 已验证 |
| `/cc/item/crowd/info.json` | 商品信息/人群可用性 | `itemId`, `dateType`, `dateRange` | ✅ 已验证 |
| `/cc/item/getItemCrowds.json` | 可触达人群规模 | `itemId` | ✅ 已验证 |
| `/cc/item/activity/trend.json` | 活动趋势 | `itemId`, `dateType`, `dateRange`, `actionType=basic_op,ct_op` | ✅ 已验证（当前为空） |
| `/cc/item/new/product/check.json` | 是否新品 | `itemId` | ✅ 已验证 |
| `/cc/item/property/suggestions.json` | 属性建议 | `itemId` | ✅ 已验证（当前为空） |
| `/cc/item/skuAttr.json` | SKU 属性 | `itemId` | ✅ 已验证 |
| `/cc/item/stock/isOff.json` | 是否下架 | 无业务参数 | ✅ 已验证 |
| `/cc/supersku/verify.json` | 超级 SKU 校验 | `itemIdList` | ✅ 已验证 |
| `/ai/one/mama/item/diagnosis.json` | AI 诊断 | `type=shop`, `recordList`, `channelKeys=sycm_item_360_zbzdcl` | ✅ 已验证（当前为空） |
| `/portal/risk/priceUpControl/queryItemWarnInfo.json` | 价格预警 | `itemIds` | ✅ 已验证（当前为空） |
| `/cc/common/batch/commDate.json` | 数据更新时间 | `tab=service,flow,sale,customer,content` | ✅ 已验证 |
| `/cc/category/compete/checkWhiteList.json` | 竞争白名单 | 无业务参数 | ✅ 已验证 |

示例：

```http
GET /cc/item/sale/overview.json?dateType=day&dateRange=2026-11-01%7C2026-11-01&device=0&itemId=731918476865&_={ts}&token={token}
GET /cc/item/sale/sku/list.json?dateRange=2026-11-01%7C2026-11-01&dateType=day&pageSize=10&page=1&order=desc&orderBy=cartCnt&device=0&itemId=731918476865&indexCode=cartCnt%2CpayAmt%2CpayByrCnt&_={ts}&token={token}
GET /cc/item/sale/trend.json?dateType=day&dateRange=2026-11-01%7C2026-11-01&indexCode=itmUv&device=0&itemId=731918476865&_={ts}&token={token}
```

## 4. 商品360 · 流量 `/cc/item_archives?activeKey=flow`

| 接口 | 用途 | 关键参数 | 状态 |
|---|---|---|---|
| `/cc/item/flow/top/v4.json` | Top10 流量来源 | `itemId`, `page=1`, `pageSize=10`, `dateType`, `dateRange` | ✅ 已验证 |
| `/cc/item/flow/realtime/top/v4.json` | 实时 Top 流量来源 | `itemId`, `page=1`, `pageSize=10`, `dateType=today` | ⚠️ 代码确认 |
| `/cc/item/searchword/top/v3.json` | Top10 搜索词 | `itemId`, `page=1`, `pageSize=10`, `dateType`, `dateRange` | ✅ 已验证 |
| `/flow/qzt/item/crowdtype/source/trend.json` | 单个来源 30 天趋势 | `itemId`, `dateType`, `dateRange`, `device=2`, `flowBizType=classic`, `belong=all`, `pageId`, `pPageId`, `pageName`, `pageLevel`, `childPageType` | ✅ 已验证 |
| `/flow/new/events/list.json` | 流量事件 | `itemId`, `dateType`, `dateRange` | ✅ 已验证（当前为空） |
| `/flow/v4/item/source/cc/security.json` | 流量来源明细（day） | `itemId`, `dateType`, `dateRange`, `device=2`, `belong=all`, `order`, `orderBy`，可能还需 `pageId`/`pPageId` | ⚠️ 部分验证 |
| `/flow/v6/item/crowdtype/source.json` | 人群来源明细 | 同上 + `crowdType` | ⚠️ 部分验证 |
| `/flow/v4/live/item/source/cc.json` | 实时来源明细 | `itemId`, `dateType=today`, `device=2`, `belong=all` | ⚠️ 代码确认 |
| `/flow/v3/new/item/source/competitor/v3/security.json` | 竞品来源明细 | `itemId`, `dateType`, `dateRange`, `device=2`, `belong=all`, `pageId`, `pPageId`, `pageName` | ⚠️ 代码确认 |

> 说明：`flow/top/v4.json` 和 `searchword/top/v3.json` 的代码里，“更多”链接都指向 `activeKey=flow`，归为 flow 相关；`sku/top.json` 的“更多”链接指向 `activeKey=sale`，属于销售，不属于 flow。  
> 另外，`flow/top` / `searchword/top` 是摘要卡（Top10），flow tab 的完整来源表用 `/flow/v4/item/source/cc/security.json`（需要更多参数）。

示例：

```http
GET /cc/item/flow/top/v4.json?itemId=731918476865&page=1&pageSize=10&dateType=day&dateRange=2026-11-01%7C2026-11-01&_={ts}&token={token}
GET /cc/item/searchword/top/v3.json?itemId=731918476865&page=1&pageSize=10&dateType=day&dateRange=2026-11-01%7C2026-11-01&_={ts}&token={token}
GET /flow/qzt/item/crowdtype/source/trend.json?itemId=731918476865&dateType=day&dateRange=2026-11-01%7C2026-11-01&device=2&flowBizType=classic&belong=all&pageId=reward.5081&pPageId=reward&pageName=%E6%8E%A8%E8%8D%90&pageLevel=2&childPageType=&_={ts}&token={token}
```

## 5. 参数说明

| 参数 | 说明 |
|---|---|
| `itemId` | 商品 ID |
| `dateType` | `day` / `today` / `week` / `month` 等 |
| `dateRange` | `YYYY-MM-DD\|YYYY-MM-DD`，URL 编码后为 `%7C` |
| `device` | `0`=全部；部分接口只接受 `1` 或 `2` |
| `belong` | 来源归属，流量来源通常为 `all` |
| `order` | `desc` / `asc` |
| `orderBy` | 排序字段，如 `uv`、`pv`、`payAmt` |
| `indexCode` | 指标列表，逗号分隔，如 `cartCnt,payAmt,payByrCnt` |
| `page` / `pageSize` | 分页 |
| `token` | HTML `<meta name="microdata">` 的 `legalityToken` |
| `_` | 毫秒时间戳，防缓存 |

## 6. 时间范围怎么处理

页面 URL 里的 `dateType` / `dateRange` 是前端路由状态；调接口时要把它传给 API。

| 参数 | 示例 | 说明 |
|---|---|---|
| `dateType` | `day` / `today` / `week` / `month` | 时间粒度 |
| `dateRange` | `2026-11-01%7C2026-11-01` | 开始\|结束，URL 编码 |
| `_` | `1793598912670` | 毫秒时间戳，防缓存，**不是数据时间** |

规则：

- **单日**：`dateRange=2026-11-01|2026-11-01`。
- **区间**：`start|end` 不同；接口可能返回聚合值，也可能返回逐日序列。
- **趋势接口**：`dateRange` 通常只决定“结束日”，响应返回往前 30 天（如 `sale/trend.json`）。
- **实时接口**：`dateType=today`，并使用 `realtime` 版本的 URL（如 `/cc/item/flow/realtime/top/v4.json`）。
- **非时间接口**：`getItemCrowds.json`、`skuAttr.json`、`stock/isOff.json`、`supersku/verify.json` 不需要 `dateRange`。
- **7 天 / 30 天**：以页面实际请求为准；通常是 `dateType=day` + 对应的 7/30 天 `dateRange`，或专门的 `dateType`（未逐个验证）。

### 接口 → 数据形态 → 时间维度

| 接口 | 数据形态 | 时间参数 |
|---|---|---|
| `/cc/item/sale/overview.json` | 总览指标 | `dateType` + `dateRange` |
| `/cc/item/sale/sku/list.json` | 明细列表 | `dateType` + `dateRange` |
| `/cc/item/sale/trend.json` | 30 天趋势 | `dateRange` 决定结束日 |
| `/cc/item/flow/top/v4.json` | Top10 列表 | `dateType` + `dateRange` |
| `/cc/item/searchword/top/v3.json` | Top10 列表 | `dateType` + `dateRange` |
| `/flow/qzt/item/crowdtype/source/trend.json` | 来源趋势 | `dateType` + `dateRange` |
| `/cc/item/getItemCrowds.json` | 人群摘要 | 无 |
| `/cc/item/skuAttr.json` | SKU 元数据 | 无 |
| `/cc/item/stock/isOff.json` | 状态 | 无 |
| `/cc/supersku/verify.json` | 状态/校验 | 无 |
| `/cc/common/batch/commDate.json` | 数据更新时间 | 无 |

示例：把页面 URL 的时间参数传给接口：

```text
页面 URL:
/cc/item_archives?activeKey=flow&itemId=731918476865&dateType=day&dateRange=2026-11-01%7C2026-11-01

接口:
/cc/item/flow/top/v4.json
  ?itemId=731918476865
  &dateType=day
  &dateRange=2026-11-01%7C2026-11-01
  &page=1&pageSize=10
  &_={ts}&token={token}
```

## 7. 返回码

| code | 含义 | 处理 |
|---:|---|---|
| `0` | 成功 | 解析 `data` |
| `1003` | 缺少参数 | 按 `message` 补参数，例如 `device not exist`、`belong not exist`、`order not exist` |
| `1000` | 未知异常 | 接口路径或参数不对 |
| HTTP 401/403 | 登录态失效 | 重新读 Cookie、重新取 token |
| 返回 HTML 登录页 | Cookie 过期 | 重新登录后再读取 |

## 8. 未验证的 tab

`activeKey=service` / `customer` / `content` 的接口尚未验证。定位方法见
[03-快速定位接口.md](03-快速定位接口.md)，按同样的流程即可补全。

## 9. 万相台无界版（one.alimama.com）关键词推广

> 第 1–8 节是生意参谋；本节是万相台。两套脚本独立：`collect.py` / `collect_alimama.py`。

### 9.1 无 tab 取数链路

```text
CDP Storage.getCookies（浏览器级，不开 tab、不导航）
  → POST /member/checkAccess.json（此接口不需要 csrfId）
       返回 data.meta.nickName / memberId
            data.accessInfo.csrfId
            data.loginPointId
  → POST /report/query.json?csrfId=...&bizCode=onebpSearch            总览 / 分时
  → POST /campaign/horizontal/findPage.json?csrfId=...&bizCode=onebpSearch
       计划列表 + reportInfoList 指标
```

关键点：`csrfId` **不在** Cookie、localStorage 或页面 HTML 里，只能由 `checkAccess` 获取；
该接口本身不校验 csrf，所以整条链路不需要打开页面。

### 9.2 接口表

| 接口 | 用途 | 关键参数 | 状态 |
|---|---|---|---|
| `POST /member/checkAccess.json` | 账号识别 + 获取 csrfId / loginPointId | query `bizCode=universalBP`；body `{"bizCode":"universalBP"}` | ✅ 已验证 |
| `POST /report/query.json` | 总览 / 分时报表 | `startTime`, `endTime`, `sourceList=["scene"]`, `queryFieldIn`, `splitType=sum/hour`, `fromRealTime`, `allDay`, `queryDomains` | ✅ 已验证 |
| `POST /campaign/horizontal/findPage.json` | 计划列表 + 指标 | `offset`, `pageSize`, `rptQuery.fields`, `rptQuery.conditionList[]` | ✅ 已验证 |
| `POST /adgroup/horizontal/findPage.json` | 单元列表 | `offset`, `pageSize`, `statusList` | ⚠️ 抓包确认，未直接调用 |
| `POST /campaign/search/totalConvCampaignPage.json` | 全站推广计划 | 抓包确认 | ⚠️ 抓包确认，未直接调用 |

### 9.3 历史日期的统计口径

历史日期的总览默认 `fromHourTable=true, allDay=false`，与页面卡片一致，是**截至当前小时**的口径：

| 日期 | 页面总览（截至当前小时） | 全天合计（分时求和 / 计划求和） |
|---|---:|---:|
| 2026-11-01 | 77.06 | 122.33 |

分时报表和计划列表返回的是**全天**数据。需要全天总览时使用：

```bash
python collect_alimama.py --date 2026-11-01 --full-day
```

### 9.4 错误处理

| 现象 | 含义 | 处理 |
|---|---|---|
| HTTP 403 | csrfId 缺失或过期 | 重新 `checkAccess` 拿新 csrfId；`collect_alimama.py` 会自动重试一次 |
| `checkAccess` 无 `csrfId` | Cookie 过期 / 未登录万相台 | 在对应 Chrome profile 重新登录 |
| 返回 HTML | 登录态失效 | 同上 |
