# 02 · URL 与接口映射

> 标记说明：
> - ✅ **已验证**：实际调用过，返回 `code:0` 和预期数据。
> - ⚠️ **代码确认**：从 op-cc 的 JS 中确认了调用方式和参数，但没有逐个实测。
> - ❌ **未验证**：只知道页面路由，接口需要重新定位。

## 1. 接口总表（分类 / URL / 接口 / 关键词参数）

> 分类未确定的先留空，后续补充。
> 基址：生意参谋 `https://sycm.taobao.com`；万相台 `https://one.alimama.com/index.html`。
> 生意参谋接口统一追加 `token`（HTML `meta[name=microdata]` 的 `legalityToken`）和 `_`（毫秒时间戳）。
> 万相台报表页公共参数：`bizCode=universalBP`、`source=baseReport`、`from=pcBaseReport`、`unifyType=zhai`、`effectEqual=15`、`byPage=true`、`totalTag=true`、`needCountAccelerate=true`、`byPageWithoutCount=false`、`splitType=day`、`offset`、`pageSize`、`fromRealTime`（今天 true / 历史 false）；query 参数 `bizCode=universalBP`。下表只列差异参数。

| 分类 | URL | 接口 | 关键词参数 |
|---|---|---|---|
| 万相台-推广-关键词推广 | https://one.alimama.com/index.html#!/manage/search | POST /member/checkAccess.json | query/body：`bizCode=universalBP` |
| 万相台-推广-关键词推广 | https://one.alimama.com/index.html#!/manage/search | POST /report/query.json | `bizCode=onebpSearch`、`startTime`、`endTime`、`sourceList=["scene"]`、`queryFieldIn`、`splitType=sum/hour`、`queryDomains`、`fromRealTime`、`allDay` |
| 万相台-推广-关键词推广 | https://one.alimama.com/index.html#!/manage/search | POST /campaign/horizontal/findPage.json | `offset`、`pageSize`、`rptQuery.fields`、`rptQuery.conditionList[]` |
| 万相台-推广-关键词推广 | https://one.alimama.com/index.html#!/manage/search | POST /adgroup/horizontal/findPage.json | `offset`、`pageSize`、`statusList` |
| 万相台-推广-全站推广 | （待补） | POST /campaign/search/totalConvCampaignPage.json | 抓包确认，参数待补 |
| 万相台-报表 | https://one.alimama.com/index.html#!/report/item_promotion?rptType=item_promotion | POST /report/query.json | `rptType=item_promotion`、`queryDomains=["promotion"]`、`subPromotionTypes=["ITEM"]` |
| 万相台-报表 | https://one.alimama.com/index.html#!/report/item_promotion?rptType=item_promotion&queryDomains=%5B%22promotion%22%2C%22campaign%22%5D | POST /report/query.json | 商品×计划：`rptType=item_promotion`、`queryDomains=["promotion","campaign"]`、`subPromotionTypes=["ITEM"]`；返回带 `campaignId`、`campaignName`、`promotions` |
| 万相台-报表 | https://one.alimama.com/index.html#!/report/item_promotion?rptType=item_promotion&queryDomains=%5B%22promotion%22%2C%22campaign%22%2C%22adgroup%22%5D | POST /report/query.json | 商品×计划×单元：`rptType=item_promotion`、`queryDomains=["promotion","campaign","adgroup"]`、`subPromotionTypes=["ITEM"]`；再带 `adgroupId`、`adgroupName` |
| 万相台-报表 | https://one.alimama.com/index.html#!/report/campaign?rptType=campaign | POST /report/query.json | `rptType=campaign`、`queryDomains=["campaign"]` |
| 万相台-报表 | https://one.alimama.com/index.html#!/report/adgroup?rptType=adgroup | POST /report/query.json | `rptType=adgroup`、`queryDomains=["adgroup"]`、`bizCodeIn=["onebpSearch"]` |
| 万相台-报表 | https://one.alimama.com/index.html#!/report/creative?rptType=creative | POST /report/query.json | `rptType=creative`、`queryDomains=["creative","promotion"]` |
| 万相台-报表 | https://one.alimama.com/index.html#!/report/crowd?rptType=crowd | POST /report/query.json | `rptType=crowd`、`queryDomains=["crowd"]`、`filterAppendSubwayChannel=true`、`filterNullCrowdSubwayTag=true` |
| 万相台-报表 | https://one.alimama.com/index.html#!/report/bidword?rptType=bidword | POST /report/query.json | `rptType=bidword`、`queryDomains=["word"]`、`isKeyWordNotContainChase="true"`、`bizCodeIn=["onebpSearch"]`、`queryFieldIn` 加 `avgRank` |
| 万相台-报表 | https://one.alimama.com/index.html#!/report/area?rptType=area | POST /report/query.json | `rptType=area`、`queryDomains=["province"]` |
| 万相台-推广-关键词推广 | https://one.alimama.com/index.html#!/manage/search-detail?bizCode=onebpSearch&campaignId={campaignId} | POST /adgroup/findList.json | `bizCode=onebpSearch`、`campaignId`、`statusList=["start","pause"]` |
| 万相台-推广-关键词推广 | https://one.alimama.com/index.html#!/manage/search-detail?bizCode=onebpSearch&campaignId={campaignId}&adgroupId={adgroupId} | POST /adgroup/get.json | `bizCode=onebpSearch`、`campaignId`、`adgroupId` |
| 万相台-推广-关键词推广 | https://one.alimama.com/index.html#!/manage/search-detail?bizCode=onebpSearch&campaignId={campaignId}&adgroupId={adgroupId} | POST /report/query.json（单元报表） | `sourceList=["adgroup_detail"]`、`campaignId`、`adgroupId`、`strategyAdgroupIdIn`、`startTime`、`endTime`、`queryFieldIn` |
|  | https://sycm.taobao.com/cc/item_rank | GET /cc/item/view/top.json | `itemId`、`dateType`、`dateRange`、`page`、`pageSize`、`order`、`orderBy` |
|  | https://sycm.taobao.com/cc/item_rank | GET /cc/item/live/view/top.json | `dateType=today`、`page`、`pageSize`、`order`、`orderBy` |
|  | https://sycm.taobao.com/cc/item_rank | GET /cc/item/view/foucs.json | `itemId`、`dateType`、`dateRange`、`page`、`pageSize` |
|  | https://sycm.taobao.com/cc/item_rank | GET /cc/item/view/foucs/live.json | `dateType=today`、`page`、`pageSize` |
|  | https://sycm.taobao.com/cc/item_rank | GET /cc/item/view/angle/select.json | `token`、`_` |
|  | https://sycm.taobao.com/cc/item_rank | GET /cc/item/view/excel/top.json | 同 `view/top.json` + 导出参数 |
|  | https://sycm.taobao.com/cc/item_rank | GET /cc/item/sku/top.json | `itemId`、`pageSize`、`dateType`、`dateRange`（商品排行/销售共用） |
|  | https://sycm.taobao.com/cc/item_rank | GET /cc/item/searchword/top/v3.json | `itemId`、`page`、`pageSize`、`dateType`、`dateRange`（商品排行/流量共用） |
|  | https://sycm.taobao.com/cc/item_rank | GET /cc/item/price/hasPriceAct.json | `itemId` |
|  | https://sycm.taobao.com/cc/item_rank | GET /cc/item/price/analysis/trend/live.json | `itemId` |
|  | https://sycm.taobao.com/cc/item_archives?activeKey=sale | GET /cc/item/sale/overview.json | `itemId`、`dateType`、`dateRange`、`device=0` |
|  | https://sycm.taobao.com/cc/item_archives?activeKey=sale | GET /cc/item/sale/sku/list.json | `itemId`、`dateType`、`dateRange`、`device=0`、`page`、`pageSize`、`order`、`orderBy`、`indexCode` |
|  | https://sycm.taobao.com/cc/item_archives?activeKey=sale | GET /cc/item/sale/trend.json | `itemId`、`dateType`、`dateRange`、`device=0`、`indexCode=itmUv` |
|  | https://sycm.taobao.com/cc/item_archives?activeKey=sale | GET /cc/item/crowd/info.json | `itemId`、`dateType`、`dateRange` |
|  | https://sycm.taobao.com/cc/item_archives?activeKey=sale | GET /cc/item/getItemCrowds.json | `itemId` |
|  | https://sycm.taobao.com/cc/item_archives?activeKey=sale | GET /cc/item/activity/trend.json | `itemId`、`dateType`、`dateRange`、`actionType=basic_op,ct_op` |
|  | https://sycm.taobao.com/cc/item_archives?activeKey=sale | GET /cc/item/new/product/check.json | `itemId` |
|  | https://sycm.taobao.com/cc/item_archives?activeKey=sale | GET /cc/item/property/suggestions.json | `itemId` |
|  | https://sycm.taobao.com/cc/item_archives?activeKey=sale | GET /cc/item/skuAttr.json | `itemId` |
|  | https://sycm.taobao.com/cc/item_archives?activeKey=sale | GET /cc/item/stock/isOff.json | 无业务参数 |
|  | https://sycm.taobao.com/cc/item_archives?activeKey=sale | GET /cc/supersku/verify.json | `itemIdList` |
|  | https://sycm.taobao.com/cc/item_archives?activeKey=sale | GET /ai/one/mama/item/diagnosis.json | `type=shop`、`recordList`、`channelKeys=sycm_item_360_zbzdcl` |
|  | https://sycm.taobao.com/cc/item_archives?activeKey=sale | GET /portal/risk/priceUpControl/queryItemWarnInfo.json | `itemIds` |
|  | https://sycm.taobao.com/cc/item_archives?activeKey=sale | GET /cc/common/batch/commDate.json | `tab=service,flow,sale,customer,content` |
|  | https://sycm.taobao.com/cc/item_archives?activeKey=sale | GET /cc/category/compete/checkWhiteList.json | 无业务参数 |
|  | https://sycm.taobao.com/cc/item_archives?activeKey=flow | GET /cc/item/flow/top/v4.json | `itemId`、`page=1`、`pageSize=10`、`dateType`、`dateRange` |
|  | https://sycm.taobao.com/cc/item_archives?activeKey=flow | GET /cc/item/flow/realtime/top/v4.json | `itemId`、`page=1`、`pageSize=10`、`dateType=today` |
|  | https://sycm.taobao.com/cc/item_archives?activeKey=flow | GET /flow/qzt/item/crowdtype/source/trend.json | `itemId`、`dateType`、`dateRange`、`device=2`、`flowBizType=classic`、`belong=all`、`pageId`、`pPageId`、`pageName`、`pageLevel`、`childPageType` |
|  | https://sycm.taobao.com/cc/item_archives?activeKey=flow | GET /flow/new/events/list.json | `itemId`、`dateType`、`dateRange` |
|  | https://sycm.taobao.com/cc/item_archives?activeKey=flow | GET /flow/v4/item/source/cc/security.json | `itemId`、`dateType`、`dateRange`、`device=2`、`belong=all`、`order`、`orderBy`、`pageId`、`pPageId` |
|  | https://sycm.taobao.com/cc/item_archives?activeKey=flow | GET /flow/v6/item/crowdtype/source.json | 同 `security.json` + `crowdType` |
|  | https://sycm.taobao.com/cc/item_archives?activeKey=flow | GET /flow/v4/live/item/source/cc.json | `itemId`、`dateType=today`、`device=2`、`belong=all` |
|  | https://sycm.taobao.com/cc/item_archives?activeKey=flow | GET /flow/v3/new/item/source/competitor/v3/security.json | `itemId`、`dateType`、`dateRange`、`device=2`、`belong=all`、`pageId`、`pPageId`、`pageName` |
|  | https://sycm.taobao.com/cc/item_archives?activeKey=service | （待定位） | — |
|  | https://sycm.taobao.com/cc/item_archives?activeKey=customer | （待定位） | — |
|  | https://sycm.taobao.com/cc/item_archives?activeKey=content | （待定位） | — |

> 分类为空表示待确认。`activeKey` 是前端路由参数，**不会**作为 API 参数传给后端；换 tab = 前端调用另一组接口。
> 万相台页面路由中的 `isRequestedQztDefaultSet=1` 是页面状态参数，不影响接口请求。

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
  → POST /report/query.json?csrfId=...&bizCode=universalBP            报表页列表
       rptType + queryDomains 区分商品/计划/单元/创意/人群/关键词/地域
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
| `POST /report/query.json`（报表列表） | 商品/计划/单元/创意/人群/关键词/地域报表 | `rptType`, `queryDomains`, `byPage`, `offset`, `pageSize`, `queryFieldIn`, `fromRealTime` | ✅ 已验证 |
| `POST /campaign/horizontal/findPage.json` | 计划列表 + 指标 | `offset`, `pageSize`, `rptQuery.fields`, `rptQuery.conditionList[]` | ✅ 已验证 |
| `POST /adgroup/horizontal/findPage.json` | 单元列表 | `offset`, `pageSize`, `statusList` | ⚠️ 抓包确认，未直接调用 |
| `POST /campaign/search/totalConvCampaignPage.json` | 全站推广计划 | 抓包确认 | ⚠️ 抓包确认，未直接调用 |

### 9.3 报表页列表（商品/计划/单元/创意/人群/关键词/地域）

万相台「报表」下各页共用 `POST /report/query.json`，差异只在 `rptType` + `queryDomains`（query 参数 `bizCode=universalBP`）：

| 页面 | rptType | queryDomains | 额外参数 |
|---|---|---|---|
| 商品报表 | `item_promotion` | `["promotion"]` | `subPromotionTypes=["ITEM"]` |
| 商品报表（商品×计划） | `item_promotion` | `["promotion","campaign"]` | `subPromotionTypes=["ITEM"]`；返回带 `campaignId`、`campaignName`、`promotions` |
| 商品报表（商品×计划×单元） | `item_promotion` | `["promotion","campaign","adgroup"]` | `subPromotionTypes=["ITEM"]`；再带 `adgroupId`、`adgroupName` |
| 计划报表 | `campaign` | `["campaign"]` | |
| 单元报表 | `adgroup` | `["adgroup"]` | `bizCodeIn=["onebpSearch"]` |
| 创意报表 | `creative` | `["creative","promotion"]` | |
| 人群报表 | `crowd` | `["crowd"]` | `filterAppendSubwayChannel=true`、`filterNullCrowdSubwayTag=true` |
| 关键词报表 | `bidword` | `["word"]` | `isKeyWordNotContainChase="true"`、`bizCodeIn=["onebpSearch"]`；字段加 `avgRank` |
| 地域报表 | `area` | `["province"]` | |

公共 body：`bizCode=universalBP`、`source=baseReport`、`from=pcBaseReport`、`unifyType=zhai`、`effectEqual=15`、`byPage=true`、`totalTag=true`、`needCountAccelerate=true`、`byPageWithoutCount=false`、`splitType=day`；`fromRealTime` 今天 `true` / 历史 `false`。

返回：`data.totalData[0]`（汇总行）+ `data.list`（维度行）+ `data.count`；`offset` 分页已实测。

页面上的「维度」选择器本质上是在 `queryDomains` 后追加维度：商品 `["promotion"]` → 商品×计划 `["promotion","campaign"]` → 商品×计划×单元 `["promotion","campaign","adgroup"]`。

```bash
python collect_alimama.py --reports item_promotion --date 2026-11-02
python collect_alimama.py --reports item_promotion,campaign,adgroup,creative,crowd,bidword,area --date 2026-11-01 --no-hourly --no-campaigns
python collect_alimama.py --reports item_promotion_campaign --date 2026-11-01 --no-hourly --no-campaigns
python collect_alimama.py --reports item_promotion_adgroup --date 2026-11-01 --no-hourly --no-campaigns
```

输出：`data/alimama/{店铺}_{memberId}/{日期}/{报表类型}.json`

### 9.4 历史日期的统计口径

历史日期的总览默认 `fromHourTable=true, allDay=false`，与页面卡片一致，是**截至当前小时**的口径：

| 日期 | 页面总览（截至当前小时） | 全天合计（分时求和 / 计划求和） |
|---|---:|---:|
| 2026-11-01 | 77.06 | 122.33 |

分时报表和计划列表返回的是**全天**数据。需要全天总览时使用：

```bash
python collect_alimama.py --date 2026-11-01 --full-day
```

### 9.5 错误处理

| 现象 | 含义 | 处理 |
|---|---|---|
| HTTP 403 | csrfId 缺失或过期 | 重新 `checkAccess` 拿新 csrfId；`collect_alimama.py` 会自动重试一次 |
| `checkAccess` 无 `csrfId` | Cookie 过期 / 未登录万相台 | 在对应 Chrome profile 重新登录 |
| 返回 HTML | 登录态失效 | 同上 |

### 9.6 计划报表 → 管理推广计划

计划报表行的 `operationList` 中 `code=gotoCampaignDetail`，前端跳转规则：

```text
#!/{managePath}-detail?bizCode={bizCode}&campaignId={campaignId}
```

| 营销场景 | bizCode | managePath | 详情页 |
|---|---|---|---|
| 关键词推广 | `onebpSearch` | `/manage/search` | `#!/manage/search-detail?bizCode=onebpSearch&campaignId=...` |
| 货品全站推广 | `onebpSite` | `/manage/onesite` | `#!/manage/onesite-detail?bizCode=onebpSite&campaignId=...` |
| 人群推广 | `onebpDisplay` | `/manage/display` | `#!/manage/display-detail?bizCode=onebpDisplay&campaignId=...` |
| 店铺直达 | `onebpStarShop` | `/manage/shop` | `#!/manage/shop-detail?bizCode=onebpStarShop&campaignId=...` |
| 线索推广 | `onebpAdStrategyLiuZi` | `/manage/hky` | `#!/manage/hky-detail?bizCode=onebpAdStrategyLiuZi&campaignId=...` |
| 超级短视频 | `onebpShortVideo` | `/manage/content` | `#!/manage/content-detail?bizCode=onebpShortVideo&campaignId=...` |
| 超级直播 | `onebpLive` | `/manage/content` | `#!/manage/content-detail?bizCode=onebpLive&campaignId=...` |
| 短直联动 | `onebpUnion` | `/manage/content` | `#!/manage/content-detail?bizCode=onebpUnion&campaignId=...` |

`gotoAdgroupDetail` 规则相同，额外带 `adgroupId`。

点击计划详情页「单元」表格中的标题（`adgroupName`）也会进入同一路由并带 `adgroupId`，页面切换为单元概览（单元 ID、状态、类目、数据汇总）。

已验证示例（关键词推广计划 `84609956458`）：

```text
计划详情页：
https://one.alimama.com/index.html#!/manage/search-detail?bizCode=onebpSearch&campaignId=84609956458

单元详情页（adgroupId=84445547910）：
https://one.alimama.com/index.html#!/manage/search-detail?bizCode=onebpSearch&campaignId=84609956458&adgroupId=84445547910
```

### 9.7 计划 → 单元（无 tab）

计划报表行已经提供 `bizCode` + `campaignId`，不需要打开计划/单元页面：

| 步骤 | 接口 | 关键参数 | 状态 |
|---|---|---|---|
| 0. 计划清单（可选） | `POST /campaign/findList.json` | `statusList=["start","pause"]`、`pageSource="simplifyQueryList"`、`bizCode` | ✅ 已验证 |
| 1. 单元列表 | `POST /adgroup/findList.json` | `bizCode`、`campaignId`、`statusList=["start","pause"]` | ✅ 已验证 |
| 2. 单元设置 | `POST /adgroup/get.json` | `bizCode`、`campaignId`、`adgroupId` | ✅ 已验证 |
| 3. 单元指标 | `POST /report/query.json` | `sourceList=["adgroup_detail"]`、`campaignId`、`adgroupId`、`strategyAdgroupIdIn=[adgroupId]`、`startTime`、`endTime`、`fromRealTime`（今天 true）、`queryFieldIn` | ✅ 已验证 |
| 4. 时间明细 | `POST /report/query.json` | `sourceList=["adgroup_detail"]`、`queryDomains=["date"]`、`splitType=day/hour`、`campaignId`、`adgroupId`、`strategyAdgroupIdIn`、`startTime`、`endTime`、`fromRealTime`（今天 true）、`queryFieldIn` | ✅ 已验证 |

query 参数：`?csrfId=...&bizCode=onebpSearch`。

动态发现已验证：计划报表 15 个计划全部成功调用 `/adgroup/findList.json`（15/15）；`/campaign/findList.json` 在 `onebpSearch` / `onebpSite` / `onebpShortVideo` 分别返回 6 / 7 / 4 个在投或暂停计划，可用于发现尚未产生报表数据的新计划。`statusList` 只覆盖 `start` / `pause`，已结束或删除的计划需调整状态列表。

时间明细说明：接口只返回**有数据的日期**；页面表格会把缺失日期补 0。实测 `2026-10-26 ~ 2026-11-01` 接口返回 5 天，页面表格为 7 天（10-26 / 10-27 为 0）。`alimama_api.adgroup_time_series()` 已封装。

今天查询必须 `fromRealTime=true`，否则汇总/分时返回空；小时粒度用 `hourId`（0-23）标识，接口只返回有数据的小时（页面会补 0）。

`alimama_api.py` 已封装：

```python
ags  = adgroup_find_list(headers, auth, "onebpSearch", 84609956458)
ag   = adgroup_get(headers, auth, "onebpSearch", 84609956458, 84445547910)
rows = adgroup_report_query(headers, auth, "onebpSearch", 84609956458, 84445547910,
                            "2026-10-03", "2026-11-01")
daily = adgroup_time_series(headers, auth, "onebpSearch", 84609956458, 84445547910,
                            "2026-10-26", "2026-11-01", split_type="day")
```

实测（2026-10-03 ~ 2026-11-01，单元 84445547910）：消耗 186.00、点击 72、成交 171.00、ROI 0.91935。

单元页还会加载 `/campaign/get.json`、`/bidword/findList.json`、`/creative/horizontal/findPage.json`、`/material/item/shieldConfig.json`；核心三项已封装，其余标记为抓包确认。

其他场景把 `onebpSearch` 换成对应 `bizCode`（见 9.6），接口路径不变。

### 9.8 推广解读（趋势主题对比 / Top 关键词）

单元页点击「推广解读」，弹层数据来自两次 `POST /report/query.json`（`bizCode=onebpSearch`）：

| 区块 | sourceList | queryDomains | 关键参数 | 状态 |
|---|---|---|---|---|
| 趋势主题对比 | `["theme_campare"]` | `["account","campaign","theme"]` | `strategyCampaignIdIn`、`strategyAdgroupIdIn`、`strategyBidwordIdIn`、`isAutoMatchedIn`、`fromRealTime`、`startTime`、`endTime`、`queryFieldIn` | ✅ 已验证 |
| Top 关键词 | `["theme_top_keyword"]` | `["account","campaign","word"]` | 同上 + `disPlaySystemWord=true`、`orderField`、`orderBy`、`pageSize` | ✅ 已验证 |

query 参数：`?csrfId=...&bizCode=onebpSearch`。

注意：`strategyBidwordIdIn` / `isAutoMatchedIn` 是词包 / 自动匹配标识。当前单元为 `[6]` / `[24]`；不同单元取值可能不同，需从单元关键词包数据获取（待补）。

日期口径：「汇总周期」选项为 今日 / 昨日 / 过去 7 天 / 过去 15 天；**过去 7 天 = 最近 7 个完整日（不含今天）**，例如 2026-11-02 时对应 `2026-10-26 ~ 2026-11-01`。

分页：**Top 关键词接口每页最多返回 20 条**（即使 `pageSize` 传 30/100 也只返回 20）；区间 `count` 可能大于 20，必须用 `offset=20` 取第二页，否则消耗/点击会偏小。

实测（单元 `84445547910`）：

- 单日 2026-11-02：趋势主题 5 条、Top 关键词 20 条。
- 区间 2026-10-26 ~ 2026-11-01：趋势主题 5 条、Top 关键词 22 条（分 2 页）。

一致性对比（逐日 7 次求和 vs 区间一次查询）：

| 数据块 | 逐日求和 | 区间 | 逐 key 差异 |
|---|---:|---:|---:|
| 趋势主题（5 个）adPv/click/charge/成交/订单/购物车 | 983 / 72 / 186 / 171 / 7 / 4 | 983 / 72 / 186 / 171 / 7 / 4 | 0 |
| Top 关键词（22 个）adPv/click/charge/成交/订单/购物车 | 983 / 72 / 186 / 171 / 7 / 4 | 983 / 72 / 186 / 171 / 7 / 4 | 0 |

比率（CTR / CVR / ROI）应按汇总值复算，不能对逐日比率直接求和；复算结果与区间一致。
