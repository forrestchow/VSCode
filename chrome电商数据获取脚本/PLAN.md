# 电商数据采集 · 计划

> 本文件是项目进度的唯一记录。规范见 [SPEC.md](SPEC.md)。
> 每完成一个阶段，更新「当前阶段」、平台矩阵和「进度记录」。

## 文档维护规则

任何新增、修改、完成的需求 / 模块 / 状态（含接口验证状态、脚本行为、配置项、目录约定），都必须在同一次改动中更新本文件：

1. 更新「当前阶段」和对应步骤的清单 / 状态；
2. 在「进度记录」末尾追加一条带日期的说明；
3. 涉及接口时，同步更新该数据源 `endpoints.json` 的 `status`；
4. 涉及文件 / 目录的新增、移动、删除、重命名时，同步更新 `STRUCTURE.md`；
5. 涉及命令 / 目录时，同步更新 `README.md` 和 `CLAUDE.md`。

本文件是项目进度的唯一记录，不要只在对话里说明完成情况。

## 当前阶段

**第一步（淘系）基本完成；第二步淘系：万相台已实跑，生意参谋待实跑，卖家中心待写；拼多多 / 抖音 / ERP 待写。**

## 总览

| 步骤 | 状态 | 说明 |
|---|---|---|
| 第一步 · Profile 与账号 | ✅ 淘系基本完成 | context 分组、账号识别、Cookie 读取、登录态判断；其他平台待扩展 |
| 第二步 · 数据采集 | 🟡 淘系进行中 | 万相台 ✅ / 生意参谋 🟡 / 卖家中心 ⬜；拼多多、抖音、ERP 待写 |

## 第一步 · Profile 与账号

| 能力 | 状态 | 说明 | 代码 / 文档 |
|---|---|---|---|
| 按 `browserContextId` 分组页面 | ✅ | `Target.getTargets` 过滤 `type=page` | `core/browser_profiles.py` |
| 账号识别 | ✅ | 优先 `meta[microdata]` / 页面正文；Cookie 辅助 | `core/browser_profiles.py` |
| profile 目录 / 显示名 | ✅ | `chrome://version` → Profile Path；`Local State` → `info_cache` | `core/browser_profiles.py --profile-path` |
| 页面级 Cookie | ✅ | `Network.getCookies` 优先；`Storage.getCookies` 兜底 | `core/browser_profiles.py` |
| 登录态判断 | ✅ | 401/403、返回 HTML 登录页、`checkAccess` 无 csrfId | 各数据源 `api.py` |
| 店铺浏览器启动 | ✅ | 项目内 `open-shop-browser` skill | `.claude/skills/open-shop-browser/SKILL.md` |
| 淘系登录页选择器 | ✅ | `#fm-login-id` / `#fm-login-password` / `button.fm-submit` | `.claude/skills/dom-locating/` |
| 拼多多账号识别 | ⬜ 待写 | 页面结构 / 登录态待确认 | — |
| 抖音账号识别 | ⬜ 待写 | 页面结构 / 登录态待确认 | — |
| ERP 账号 | ⬜ 待写 | 具体 ERP 待确认 | — |

说明：当前登录由人工在对应 Chrome profile 完成，脚本只读取登录态；自动填表不是主流程。

## 第二步 · 数据采集

### 平台矩阵

| 平台 | 数据源 | 状态 | 代码目录 | 接口模板 | 输出目录 |
|---|---|---|---|---|---|
| 淘系 / 天猫 | 万相台推广 | ✅ 已实跑（含报表页） | `platforms/taobao/alimama/` | `endpoints.json` | `data/taobao/alimama/` |
| 淘系 / 天猫 | 生意参谋 | 🟡 代码完成待实跑 | `platforms/taobao/sycm/` | `endpoints.json` | `data/taobao/sycm/` |
| 淘系 / 天猫 | 卖家中心 | ⬜ 待写 | `platforms/taobao/seller_center/` | — | — |
| 拼多多 | 待定 | ⬜ 待写 | `platforms/pdd/` | — | — |
| 抖音 | 待定 | ⬜ 待写 | `platforms/douyin/` | — | — |
| ERP | 待定（具体 ERP 系统） | ⬜ 待写 | `platforms/erp/` | — | — |

### 代码映射总表

| 数据源 | 入口命令 | 编排层 | HTTP 层 | 接口模板 | 配置 | 输出 |
|---|---|---|---|---|---|---|
| 生意参谋 | `python -m platforms.taobao.sycm.collect` | `platforms/taobao/sycm/collect.py` | `platforms/taobao/sycm/api.py` | `platforms/taobao/sycm/endpoints.json` | `platforms/taobao/sycm/config.json` | `data/taobao/sycm/` |
| 万相台 | `python -m platforms.taobao.alimama.collect` | `platforms/taobao/alimama/collect.py` | `platforms/taobao/alimama/api.py` | `platforms/taobao/alimama/endpoints.json` | `platforms/taobao/alimama/config.json` | `data/taobao/alimama/` |
| 卖家中心 | — | — | — | — | — | — |

### 接口分类总表

> 本表是人工索引；`endpoints.json` 是机器可读的唯一事实来源。接口新增 / 修改时，两处同一次更新。
> 生意参谋是**数据驱动**：表中的接口 key 对应 `platforms/taobao/sycm/endpoints.json`，运行时由 `collect.py` 的 `resolve_endpoint()` 查找，`api.py` 的 `request_json()` 发送。
> 万相台是**函数驱动**：每个接口在 `platforms/taobao/alimama/api.py` 里有对应函数。
> 「采集」列：`默认` = 默认配置会跑；`可选` = 已写入模板但未默认启用；`未接入` = 只有契约或抓包记录；`鉴权` = 只用于取 token；`未验证` = 还没定位到接口。

**URL 查询规则**

1. 去掉域名，保留 path / hash 路由 + 关键参数（`rptType`、`queryDomains`、`activeKey`、`bizCode`、`campaignId`、`adgroupId`）。
2. 在「页面 / 路由」列匹配；同一个接口可以服务多个路由，一个路由也可能有多个接口。
3. 命中后按「代码映射」调用；万相台报表页统一走 `api.report_list(<spec key>)`，参数以 `endpoints.json` 的 `report_pages` 为准。
4. 未命中 → 按 `SPEC.md` 4.6 定位接口 → 写代码 → 更新本表、`endpoints.json`、`STRUCTURE.md`。

基址：生意参谋 `https://sycm.taobao.com`；万相台 `https://one.alimama.com/index.html`。

| 平台 | 数据源 | 页面 / 路由 | 分类 | 接口 | 用途 | 状态 | 采集 | 代码映射 | 备注 |
|---|---|---|---|---|---|---|---|---|---|
| 淘系 / 天猫 | 万相台推广 | #!/manage/search | 鉴权 / 账号 | `POST /member/checkAccess.json` | 识别账号，获取 `csrfId` / `loginPointId` / `memberId` | ✅ 已验证 | 鉴权 | `api.check_access` | 不需要 csrfId，是免开页取数的入口 |
| 淘系 / 天猫 | 万相台推广 | #!/manage/search | 报表 | `POST /report/query.json` | 总览 / 分时 | ✅ 已验证 | 默认 | `api.report_query` | 历史总览默认截至当前小时；`--full-day` 为全天 |
| 淘系 / 天猫 | 万相台推广 | #!/manage/search | 计划 | `POST /campaign/horizontal/findPage.json` | 计划列表 + 每个计划的指标 | ✅ 已验证 | 默认 | `api.campaign_find_page` | 分页取全 |
| 淘系 / 天猫 | 万相台推广 | #!/manage/search | 单元 | `POST /adgroup/horizontal/findPage.json` | 单元列表 | ⚠️ 抓包确认，未直接调用 | 未接入 | — | — |
| 淘系 / 天猫 | 万相台推广 | —（全站推广页待补） | 全站推广 | `POST /campaign/search/totalConvCampaignPage.json` | 全站推广计划 | ⚠️ 抓包确认，未直接调用 | 未接入 | — | — |
| 淘系 / 天猫 | 生意参谋 | /cc/item_rank | 商品排行 | `GET /cc/item/view/top.json` | 商品排行（日 / 周 / 月） | ⚠️ 代码确认 | 可选 | `endpoints.json: item_rank` | 需 order / orderBy / page / pageSize |
| 淘系 / 天猫 | 生意参谋 | /cc/item_rank | 商品排行 | `GET /cc/item/live/view/top.json` | 实时商品排行 | ⚠️ 代码确认 | 可选 | `endpoints.json: item_rank_realtime` | `dateType=today` |
| 淘系 / 天猫 | 生意参谋 | /cc/item_rank | 商品排行 | `GET /cc/item/view/foucs.json` | 我关注的商品 | ⚠️ 代码确认 | 可选 | `endpoints.json: item_focus` | — |
| 淘系 / 天猫 | 生意参谋 | /cc/item_rank | 商品排行 | `GET /cc/item/view/foucs/live.json` | 实时关注商品 | ⚠️ 代码确认 | 可选 | `endpoints.json: item_focus_realtime` | `dateType=today` |
| 淘系 / 天猫 | 生意参谋 | /cc/item_rank | 商品排行 | `GET /cc/item/view/angle/select.json` | 视角选择 | ⚠️ 代码确认 | 可选 | `endpoints.json: view_angle` | — |
| 淘系 / 天猫 | 生意参谋 | /cc/item_rank | 商品排行 | `GET /cc/item/price/hasPriceAct.json` | 是否有价格活动 | ⚠️ 代码确认 | 可选 | `endpoints.json: price_activity` | — |
| 淘系 / 天猫 | 生意参谋 | /cc/item_rank | 商品排行 | `GET /cc/item/price/analysis/trend/live.json` | 实时价格趋势 | ⚠️ 代码确认 | 可选 | `endpoints.json: price_trend_live` | — |
| 淘系 / 天猫 | 生意参谋 | /cc/item_rank | 商品排行 | `GET /cc/item/sku/top.json` | Top5 SKU 销售摘要卡 | ✅ 已验证 | 可选 | `endpoints.json: sku_top` | “更多”链接指向 `activeKey=sale` |
| 淘系 / 天猫 | 生意参谋 | /cc/item_archives?activeKey=sale | 商品360 · 销售 | `GET /cc/item/sale/overview.json` | 销售总览 | ✅ 已验证 | 默认 | `endpoints.json: sale_overview` | `device=0` |
| 淘系 / 天猫 | 生意参谋 | /cc/item_archives?activeKey=sale | 商品360 · 销售 | `GET /cc/item/sale/sku/list.json` | SKU 销售明细 | ✅ 已验证 | 默认 | `endpoints.json: sale_sku_list` | 完整 SKU 明细；Top5 摘要卡是 `sku/top` |
| 淘系 / 天猫 | 生意参谋 | /cc/item_archives?activeKey=sale | 商品360 · 销售 | `GET /cc/item/sale/trend.json` | 30 天趋势 | ✅ 已验证 | 默认 | `endpoints.json: sale_trend` | `dateRange` 决定结束日，返回往前 30 天 |
| 淘系 / 天猫 | 生意参谋 | /cc/item_archives?activeKey=sale | 商品360 · 销售 | `GET /cc/item/crowd/info.json` | 商品信息 / 人群可用性 | ✅ 已验证 | 可选 | `endpoints.json: crowd_info` | — |
| 淘系 / 天猫 | 生意参谋 | /cc/item_archives?activeKey=sale | 商品360 · 销售 | `GET /cc/item/getItemCrowds.json` | 可触达人群规模 | ✅ 已验证 | 可选 | `endpoints.json: get_item_crowds` | 无时间参数 |
| 淘系 / 天猫 | 生意参谋 | /cc/item_archives?activeKey=sale | 商品360 · 销售 | `GET /cc/item/activity/trend.json` | 活动趋势 | ✅ 已验证（当前为空） | 可选 | `endpoints.json: activity_trend` | `actionType=basic_op,ct_op` |
| 淘系 / 天猫 | 生意参谋 | /cc/item_archives?activeKey=sale | 商品360 · 销售 | `GET /cc/item/new/product/check.json` | 是否新品 | ✅ 已验证 | 可选 | `endpoints.json: new_product_check` | 无时间参数 |
| 淘系 / 天猫 | 生意参谋 | /cc/item_archives?activeKey=sale | 商品360 · 销售 | `GET /cc/item/property/suggestions.json` | 属性建议 | ✅ 已验证（当前为空） | 可选 | `endpoints.json: property_suggestions` | 当前为空 |
| 淘系 / 天猫 | 生意参谋 | /cc/item_archives?activeKey=sale | 商品360 · 销售 | `GET /cc/item/skuAttr.json` | SKU 属性 | ✅ 已验证 | 可选 | `endpoints.json: sku_attr` | 无时间参数 |
| 淘系 / 天猫 | 生意参谋 | /cc/item_archives?activeKey=sale | 商品360 · 销售 | `GET /cc/item/stock/isOff.json` | 是否下架 | ✅ 已验证 | 可选 | `endpoints.json: stock_is_off` | 无业务参数 |
| 淘系 / 天猫 | 生意参谋 | /cc/item_archives?activeKey=sale | 商品360 · 销售 | `GET /cc/supersku/verify.json` | 超级 SKU 校验 | ✅ 已验证 | 可选 | `endpoints.json: supersku_verify` | `itemIdList` |
| 淘系 / 天猫 | 生意参谋 | /cc/item_archives?activeKey=sale | 商品360 · 销售 | `GET /ai/one/mama/item/diagnosis.json` | AI 诊断 | ✅ 已验证（当前为空） | 可选 | `endpoints.json: item_diagnosis` | `type=shop`；当前为空 |
| 淘系 / 天猫 | 生意参谋 | /cc/item_archives?activeKey=sale | 商品360 · 销售 | `GET /portal/risk/priceUpControl/queryItemWarnInfo.json` | 价格预警 | ✅ 已验证（当前为空） | 可选 | `endpoints.json: price_warn` | `itemIds`；当前为空 |
| 淘系 / 天猫 | 生意参谋 | /cc/item_archives?activeKey=sale | 商品360 · 销售 | `GET /cc/common/batch/commDate.json` | 数据更新时间 | ✅ 已验证 | 可选 | `endpoints.json: comm_date` | `tab=service,flow,sale,customer,content` |
| 淘系 / 天猫 | 生意参谋 | /cc/item_archives?activeKey=sale | 商品360 · 销售 | `GET /cc/category/compete/checkWhiteList.json` | 竞争白名单 | ✅ 已验证 | 可选 | `endpoints.json: compete_whitelist` | 无业务参数 |
| 淘系 / 天猫 | 生意参谋 | /cc/item_archives?activeKey=flow | 商品360 · 流量 | `GET /cc/item/flow/top/v4.json` | Top10 流量来源 | ✅ 已验证 | 默认 | `endpoints.json: flow_top` | Top10 摘要卡；“更多”指向 `activeKey=flow` |
| 淘系 / 天猫 | 生意参谋 | /cc/item_archives?activeKey=flow | 商品360 · 流量 | `GET /cc/item/flow/realtime/top/v4.json` | 实时 Top 流量来源 | ⚠️ 代码确认 | 可选 | `endpoints.json: flow_top_realtime` | `dateType=today` |
| 淘系 / 天猫 | 生意参谋 | /cc/item_rank / /cc/item_archives?activeKey=flow | 商品排行 / 商品360 · 流量 | `GET /cc/item/searchword/top/v3.json` | Top10 搜索词 | ✅ 已验证 | 默认 | `endpoints.json: searchword_top` | 同名接口也出现在商品排行；`PAGE_HINTS` 默认选 `activeKey=flow` |
| 淘系 / 天猫 | 生意参谋 | /cc/item_archives?activeKey=flow | 商品360 · 流量 | `GET /flow/qzt/item/crowdtype/source/trend.json` | 单个来源 30 天趋势 | ✅ 已验证 | 可选 | `endpoints.json: source_trend` | `device=2`、`belong=all`、`pageId` 等 |
| 淘系 / 天猫 | 生意参谋 | /cc/item_archives?activeKey=flow | 商品360 · 流量 | `GET /flow/new/events/list.json` | 流量事件 | ✅ 已验证（当前为空） | 可选 | `endpoints.json: events_list` | 当前为空 |
| 淘系 / 天猫 | 生意参谋 | /cc/item_archives?activeKey=flow | 商品360 · 流量 | `GET /flow/v4/item/source/cc/security.json` | 流量来源明细（day） | ⚠️ 部分验证 | 可选 | `endpoints.json: source_detail_security` | 还需 `pageId` / `pPageId` 等参数 |
| 淘系 / 天猫 | 生意参谋 | /cc/item_archives?activeKey=flow | 商品360 · 流量 | `GET /flow/v6/item/crowdtype/source.json` | 人群来源明细 | ⚠️ 部分验证 | 可选 | `endpoints.json: source_detail_crowdtype` | 还需 `crowdType` 等参数 |
| 淘系 / 天猫 | 生意参谋 | /cc/item_archives?activeKey=flow | 商品360 · 流量 | `GET /flow/v4/live/item/source/cc.json` | 实时来源明细 | ⚠️ 代码确认 | 可选 | `endpoints.json: source_detail_live` | `dateType=today` |
| 淘系 / 天猫 | 生意参谋 | /cc/item_archives?activeKey=flow | 商品360 · 流量 | `GET /flow/v3/new/item/source/competitor/v3/security.json` | 竞品来源明细 | ⚠️ 代码确认 | 可选 | `endpoints.json: competitor_detail` | — |
| 淘系 / 天猫 | 生意参谋 | /cc/item_archives?activeKey=service/customer/content | 商品360 · 服务 / 客户 / 内容 | 未定位 | 对应页面数据 | ❌ 未验证 | 未接入 | — | 待定位接口 |
| 淘系 / 天猫 | 万相台推广 | #!/report/item_promotion?rptType=item_promotion | 商品报表 | `POST /report/query.json` | 商品维度报表 | ✅ 已验证 | 默认 | `api.report_list("item_promotion")` | `queryDomains=["promotion"]`；`subPromotionTypes=["ITEM"]` |
| 淘系 / 天猫 | 万相台推广 | #!/report/item_promotion?rptType=item_promotion&queryDomains=["promotion","campaign"] | 商品报表（商品×计划） | `POST /report/query.json` | 商品×计划报表 | ✅ 已验证 | 可选 | `api.report_list("item_promotion_campaign")` | 返回 `campaignId`、`campaignName`、`promotions` |
| 淘系 / 天猫 | 万相台推广 | #!/report/item_promotion?rptType=item_promotion&queryDomains=["promotion","campaign","adgroup"] | 商品报表（商品×计划×单元） | `POST /report/query.json` | 商品×计划×单元报表 | ✅ 已验证 | 可选 | `api.report_list("item_promotion_adgroup")` | 再带 `adgroupId`、`adgroupName` |
| 淘系 / 天猫 | 万相台推广 | #!/report/campaign?rptType=campaign | 计划报表 | `POST /report/query.json` | 计划维度报表 | ✅ 已验证 | 可选 | `api.report_list("campaign")` | `queryDomains=["campaign"]` |
| 淘系 / 天猫 | 万相台推广 | #!/report/adgroup?rptType=adgroup | 单元报表 | `POST /report/query.json` | 单元维度报表 | ✅ 已验证 | 可选 | `api.report_list("adgroup")` | `queryDomains=["adgroup"]`；`bizCodeIn=["onebpSearch"]` |
| 淘系 / 天猫 | 万相台推广 | #!/report/creative?rptType=creative | 创意报表 | `POST /report/query.json` | 创意维度报表 | ✅ 已验证 | 可选 | `api.report_list("creative")` | `queryDomains=["creative","promotion"]` |
| 淘系 / 天猫 | 万相台推广 | #!/report/crowd?rptType=crowd | 人群报表 | `POST /report/query.json` | 人群维度报表 | ✅ 已验证 | 可选 | `api.report_list("crowd")` | `queryDomains=["crowd"]`；带人群筛选参数 |
| 淘系 / 天猫 | 万相台推广 | #!/report/bidword?rptType=bidword | 关键词报表 | `POST /report/query.json` | 关键词维度报表 | ✅ 已验证 | 可选 | `api.report_list("bidword")` | `queryDomains=["word"]`；字段加 `avgRank` |
| 淘系 / 天猫 | 万相台推广 | #!/report/area?rptType=area | 地域报表 | `POST /report/query.json` | 地域维度报表 | ✅ 已验证 | 可选 | `api.report_list("area")` | `queryDomains=["province"]` |
| 淘系 / 天猫 | 万相台推广 | #!/manage/search-detail?bizCode=onebpSearch | 计划 / 单元详情 | `POST /campaign/findList.json` | 场景下计划列表 | ✅ 已验证 | 可选 | `api.campaign_find_list` | 不依赖报表日期，可用于发现新计划 |
| 淘系 / 天猫 | 万相台推广 | #!/manage/search-detail?bizCode=onebpSearch&campaignId={campaignId} | 计划 / 单元详情 | `POST /adgroup/findList.json` | 计划下单元列表 | ✅ 已验证 | 可选 | `api.adgroup_find_list` | 返回 `adgroupId`、`adgroupName`、`onlineStatus` |
| 淘系 / 天猫 | 万相台推广 | #!/manage/search-detail?bizCode=onebpSearch&campaignId={campaignId}&adgroupId={adgroupId} | 计划 / 单元详情 | `POST /adgroup/get.json` | 单元设置 / 详情 | ✅ 已验证 | 可选 | `api.adgroup_get` | 返回 `adgroupName`、`onlineStatus`、出价类型等 |
| 淘系 / 天猫 | 万相台推广 | #!/manage/search-detail?bizCode=onebpSearch&campaignId={campaignId}&adgroupId={adgroupId} | 计划 / 单元详情 | `POST /report/query.json`（单元报表） | 单元维度指标 | ✅ 已验证 | 可选 | `api.adgroup_report_query` | `sourceList=["adgroup_detail"]`；查今天需 `fromRealTime=true` |
| 淘系 / 天猫 | 万相台推广 | #!/manage/search-detail?bizCode=onebpSearch&campaignId={campaignId}&adgroupId={adgroupId} | 计划 / 单元详情 | `POST /report/query.json`（单元时间明细） | 单元按日 / 小时明细 | ✅ 已验证 | 可选 | `api.adgroup_time_series` | `queryDomains=["date"]`、`splitType=day/hour` |
| 淘系 / 天猫 | 万相台推广 | #!/manage/search-detail?bizCode=onebpSearch&campaignId={campaignId}&adgroupId={adgroupId} | 计划 / 单元详情 | `POST /report/query.json`（推广解读：趋势主题） | 趋势主题对比 | ✅ 已验证 | 可选 | —（待封装） | `sourceList=["theme_campare"]`、`queryDomains=["account","campaign","theme"]` |
| 淘系 / 天猫 | 万相台推广 | #!/manage/search-detail?bizCode=onebpSearch&campaignId={campaignId}&adgroupId={adgroupId} | 计划 / 单元详情 | `POST /report/query.json`（推广解读：Top 关键词） | Top 关键词 | ✅ 已验证 | 可选 | —（待封装） | `sourceList=["theme_top_keyword"]`；每页最多 20 条，第二页 `offset=20` |
| 淘系 / 天猫 | 万相台推广 | #!/manage/search-detail?bizCode=onebpSearch&campaignId={campaignId} | 计划 / 单元详情 | `POST /campaign/get.json` | 计划详情 | ⚠️ 抓包确认，未直接调用 | 未接入 | — | — |
| 淘系 / 天猫 | 万相台推广 | #!/manage/search-detail?bizCode=onebpSearch&campaignId={campaignId}&adgroupId={adgroupId} | 计划 / 单元详情 | `POST /bidword/findList.json` | 关键词列表 | ⚠️ 抓包确认，未直接调用 | 未接入 | — | — |
| 淘系 / 天猫 | 万相台推广 | #!/manage/search-detail?bizCode=onebpSearch&campaignId={campaignId}&adgroupId={adgroupId} | 计划 / 单元详情 | `POST /creative/horizontal/findPage.json` | 创意列表 | ⚠️ 抓包确认，未直接调用 | 未接入 | — | — |

拼多多、抖音、卖家中心、ERP 暂无已定位接口，暂按数据源保留在下面的待写章节。

---

### 淘系 · 万相台推广数据

**取数链路**

```text
CDP Storage.getCookies（浏览器级，不开 tab）
  → POST /member/checkAccess.json（不需要 csrfId）
       返回 data.meta.nickName / memberId
            data.accessInfo.csrfId
            data.loginPointId
  → POST /report/query.json?csrfId=...&bizCode=onebpSearch        总览 / 分时
  → POST /report/query.json?csrfId=...&bizCode=universalBP        报表页列表
       rptType + queryDomains 区分商品/计划/单元/创意/人群/关键词/地域
  → POST /campaign/horizontal/findPage.json?csrfId=...&bizCode=onebpSearch
       计划列表 + reportInfoList 指标
```

关键点：`csrfId` 不在 Cookie、localStorage 或页面 HTML 里，只能由 `checkAccess` 获取；该接口本身不校验 csrf，所以整条链路不需要打开页面。

接口分类、验证状态和代码映射见上方「接口分类总表」的万相台推广行。

接口 → 代码：**函数驱动**。每个接口对应 `api.py` 的一个函数；`endpoints.json` 记录契约与状态。

示例：`overview` / `hourly` → `collect.py` 的 `collect_date()` → `api.report_query()`；`campaigns` → `api.campaign_find_page()`；`item_promotion` / `item_promotion_campaign` / `item_promotion_adgroup` 等 → `api.report_list(<spec key>)`。

**当前能力**

- 总览、分时、计划列表三个文件写入 `data/taobao/alimama/{店铺}_{memberId}/{日期}/`。
- 历史日期总览默认与页面一致：`allDay=false`，截至当前小时；`--full-day` 改为全天口径。
- 分时和计划列表始终是全天数据。
- 报表页列表：默认 `item_promotion`（商品维度）；`--reports` 可选 `item_promotion_campaign`、`item_promotion_adgroup`、`campaign`、`adgroup`、`creative`、`crowd`、`bidword`、`area`。
- 报表页支持 `offset` 分页，`--report-page-size` 控制每页条数；输出到 `{报表类型}.json`。
- 实跑记录：2026-11-01 七类报表、2026-11-02 商品报表；`item_promotion_campaign` 15 条、`item_promotion_adgroup` 6 条、7 天区间商品×计划 20 条。

**待办**

- [ ] 接入单元列表（`adgroup_list`）。
- [ ] 接入全站推广计划（`total_conv_campaign`）。
- [ ] 把推广解读（`theme_campare` / `theme_top_keyword`）封装成函数。
- [ ] 接入 `campaign_get` / `bidword_find_list` / `creative_find_page`。
- [ ] 多账号 / 多 profile 批量采集。

---

### 淘系 · 生意参谋平台数据

**取数链路**

```text
已登录的 Chrome（该账号的 context）
  → 页面级 Network.getCookies（只读 Cookie，不开 tab）
  → HTTP GET 目标页面 HTML（不开 tab）
        <meta name="microdata"> → legalityToken
  → HTTP GET JSON 接口
        Cookie + User-Agent + Referer + token + 业务参数
```

关键点：`legalityToken` 在页面 HTML 的 `meta[microdata]` 里，每个账号 / 页面各自解析，不能跨账号复用。

接口分类、验证状态和代码映射见上方「接口分类总表」的生意参谋行。

完整接口清单、参数和状态见 [`platforms/taobao/sycm/endpoints.json`](platforms/taobao/sycm/endpoints.json)。总表是人的索引，`endpoints.json` 是机器可读的唯一事实来源。

接口 → 代码：**数据驱动**。`endpoints.json` 的接口 key 由 `collect.py` 的 `resolve_endpoint()` 解析；`api.py` 提供通用 HTTP 请求。新增已验证接口通常只需在 `endpoints.json` 增加模板，并在 `config.json` 的 `endpoints` 里启用。

示例：`config.json` 的 `sale_overview` → `collect.py` 的 `resolve_endpoint()` → `endpoints.json` 中页面 `/cc/item_archives?activeKey=sale` 下的接口 `sale_overview` → `api.request_json()`。

**当前采集范围（第一版）**

默认采集 5 个接口：`sale_overview`、`sale_sku_list`、`sale_trend`、`flow_top`、`searchword_top`（见总表「采集」列）。

- 每个接口只取第一页（`page=1`，`pageSize=10`）。
- 四层串行：账号 → 商品 → 日期 → 接口；请求间隔 1~3 秒。
- `code=1100` 按跳过处理；`1003` 记失败；401/403 判登录失效。
- 输出：`data/taobao/sycm/{店铺}_{loginUserId}/{日期}/{商品ID}/{接口}.json`。

**待办**

- [ ] 连接真实 Chrome 实跑 `collect.py`，确认 5 个接口全部成功。
- [ ] 补全 `activeKey=service` / `customer` / `content` 的接口。
- [ ] 完整分页 / 全量历史。
- [ ] 把更多已验证接口加入 `config.json` 默认范围。

---

### 淘系 · 卖家中心后台数据

**状态：⬜ 待写。**

- 目标：订单、商品、店铺后台数据。
- 现状：本目录暂无代码、无接口模板。
- 下一步：
  1. 确认卖家中心 / 千牛后台的入口页面和登录态；
  2. 按 `SPEC.md` 4.6 的流程定位接口；
  3. 若接口依赖动态签名或只能 DOM 提取，先记录限制，不强行纳入主线；
  4. 建立 `platforms/taobao/seller_center/` 下的 `collect.py`、`api.py`、`endpoints.json`、`config.json`。
- 代码目录：`platforms/taobao/seller_center/`。

---

### 拼多多（待写）

- 数据源分类待定，暂不展开。
- 目录占位：`platforms/pdd/`。
- 待确认：账号识别、登录态、鉴权方式、接口发现方法。

### 抖音（待写）

- 数据源分类待定，暂不展开。
- 目录占位：`platforms/douyin/`。
- 待确认：账号识别、登录态、鉴权方式、接口发现方法。

### ERP（待写）

- ERP 按平台管理，具体 ERP 系统作为该平台下的数据源。
- 目录占位：`platforms/erp/`；每个 ERP 系统使用 `platforms/erp/<system>/`。
- 待确认：具体 ERP 系统、账号 / 鉴权、数据分类、接口或导出方式。

## 第一版范围

- 主路线：Python HTTP 直连（`SPEC.md` 4.1）；页面内 `fetch` 留作兜底。
- 生意参谋只跑 5 个已验证接口；万相台跑总览 / 分时 / 计划列表。
- 不做：数据库、Excel、定时任务、后台 tab 日常取数、未验证的 service / customer / content 页面。
- 不做：拼多多、抖音、卖家中心、ERP（先占位）。

## 进度记录

> 2026-11-04 之前的记录使用旧文件名；从该日起，代码位于 `core/` 和 `platforms/<平台>/<数据源>/`。

- 2026-11-02：计划确认，开始写 `sycm_api.py`、`collect.py`、`config.json`。
- 2026-11-02：三个文件已写完，`py_compile` 和 `--help` 通过；尚未连接真实 Chrome 实跑。
- 2026-11-02：新增 `CLAUDE.md`（项目架构、常用命令、文档同步规则）；本文件自此作为进度唯一记录。
- 2026-11-02：明确「抓包是获得接口的备选方案」：首选 performance + bundle grep，静态分析失败才后台 tab 抓 Network；抓到后写入 `endpoints.json`，日常采集不再抓包。
- 2026-11-02：新增用户级 `dom-locating` Skill（含失败闭环、案例库、changelog）；在 `CLAUDE.md` 加入 DOM 定位指针和 sycm 登录页选择器。
- 2026-11-02：新增万相台无界版采集：`alimama_api.py`、`collect_alimama.py`、`alimama_config.json`；接口模板写入 `endpoints.json` 的 `alimama` 段；在当时的 `02-URL与接口映射.md` 新增第 9 节接口映射。
- 2026-11-02：万相台实跑察尔汗 2026-11-02 / 2026-11-01，6 次调用全部成功；历史总览默认页面口径（11-01 为 77.06，截至当前小时），`--full-day` 返回全天 122.33。
- 2026-11-02：`dom-locating` Skill 由用户级迁移为项目级 `.claude/skills/dom-locating`，CLAUDE.md 指针同步；原用户级目录已送回收站。
- 2026-11-02：补充 `dom-locating` 案例：Playwright 只能点击账号框触发 Chrome 密码管理器弹层，弹层需用 Windows UIA 的 `InvokePattern` 选择；实测「察尔汗壹品盐专卖店:绍飞」自动填表并登录万相台成功。
- 2026-11-02：新增万相台报表页列表采集：`report_list()` + `REPORT_LIST_SPECS` 覆盖 item_promotion / campaign / adgroup / creative / crowd / bidword / area；`collect_alimama.py` 新增 `--reports` / `--report-page-size`，输出 `{报表类型}.json`；察尔汗 2026-11-01 七类报表、2026-11-02 商品报表实跑通过。
- 2026-11-02：`CLAUDE.md` 首要规则新增「接口优先登记」：新接口 / 接口变更第一时间登记到接口总表，并同步 `endpoints.json`；分类未定先留空。
- 2026-11-02：破解并验证商品报表维度变体：`queryDomains` 加 `campaign` 得到商品×计划（`campaignId` / `campaignName` / `promotions`），再加 `adgroup` 得到商品×计划×单元；新增 `item_promotion_campaign` / `item_promotion_adgroup` specs；2026-11-01 实跑分别 15 / 6 条，7 天区间商品×计划 20 条。
- 2026-11-02：定位计划报表「管理推广计划」跳转规则 `#!/{managePath}-detail?bizCode={bizCode}&campaignId={campaignId}`，验证关键词推广 `/manage/search-detail?...&campaignId=84609956458` 可正常打开。
- 2026-11-02：验证计划详情页「单元」标题跳转：同一 `/manage/search-detail` 路由追加 `adgroupId` 即进入单元概览；实测 `campaignId=84609956458&adgroupId=84445547910` 正常打开。
- 2026-11-02：验证并封装计划→单元无 tab 链路：`/adgroup/findList.json`、`/adgroup/get.json`、`/report/query.json`（`sourceList=["adgroup_detail"]`）；实测 2026-10-03~11-01 单元 84445547910 消耗 186.00 / 点击 72 / 成交 171.00 / ROI 0.92。
- 2026-11-02：验证动态发现：计划报表 15 个计划全部成功调用 `/adgroup/findList.json`（15/15）；`/campaign/findList.json` 在 onebpSearch / onebpSite / onebpShortVideo 返回 6 / 7 / 4 个在投或暂停计划，可用于发现新计划；新增 `campaign_find_list()`。
- 2026-11-02：定位并验证单元页「推广解读」弹层数据：`/report/query.json` 的 `theme_campare`（趋势主题 5 条）与 `theme_top_keyword`（Top 关键词 20 条）；无 tab 复现并保存到 `adgroup_84445547910_promotion_insight.json`。
- 2026-11-02：验证推广解读日期粒度一致性：过去 7 天 = 2026-10-26~2026-11-01（不含今天）；逐日 7 次求和与区间一次查询在趋势主题（5 个）和 Top 关键词（22 个）上 adPv / click / charge / 成交 / 订单 / 购物车逐 key 完全一致；发现 Top 关键词接口每页最多 20 条，区间查询必须用 `offset=20` 取第二页。
- 2026-11-02：验证单元时间明细无 tab 采集：`/report/query.json` 加 `sourceList=["adgroup_detail"]`、`queryDomains=["date"]`、`splitType="day"`；2026-10-26~11-01 接口返回 5 天有数据行，页面补齐 7 天（10-26 / 10-27 为 0）；新增 `adgroup_time_series()`。
- 2026-11-02：验证今天（实时）口径：单元汇总 / 分时必须 `fromRealTime=true`，否则返回空；`adgroup_report_query()` / `adgroup_time_series()` 增加 `is_today` 参数；今日数据汇总消耗 7.43、点击 3、adPv 121；分时 15 个有数据小时，用 `hourId` 标识。
- 2026-11-04：文档与代码重构。`01-05-*.md` 合并为 `SPEC.md`；`PLAN.md` 改为「两步 × 平台 / 数据源」结构；代码按 `core/` + `platforms/<平台>/<数据源>/` 重组；接口模板从根目录 `endpoints.json` 拆分到各数据源 `endpoints.json`；数据目录迁移到 `data/taobao/`。
- 2026-11-04：新增 `STRUCTURE.md`，作为项目物理结构的唯一事实来源；补充每个文件夹 / 文件的作用和新增文件放置规则；在 `PLAN.md`、`CLAUDE.md`、`SPEC.md`、`README.md` 中加入同步规则和指针。
- 2026-11-04：ERP 从根目录 `erp/` 移到 `platforms/erp/`，按平台管理；具体 ERP 系统作为该平台下的数据源（`platforms/erp/<system>/`），输出到 `data/erp/<system>/`。
- 2026-11-04：`PLAN.md` 新增「接口分类总表」，按「平台 → 数据源 → 分类 → 接口」统一列出万相台和生意参谋的全部接口、用途、状态、采集开关和代码映射；移除各数据源下重复的接口分类表，数据源级概览和待写章节保留。
- 2026-11-04：从提交 `eb04ba0` 恢复万相台报表页列表与计划/单元链路：`report_list()` + `REPORT_LIST_SPECS`（item_promotion / item_promotion_campaign / item_promotion_adgroup / campaign / adgroup / creative / crowd / bidword / area）、`campaign_find_list()` / `adgroup_find_list()` / `adgroup_get()` / `adgroup_report_query()` / `adgroup_time_series()`；`collect.py` 新增 `--reports` / `--report-page-size`，`config.json` 默认采集 `item_promotion`；`endpoints.json` 补 `report_pages` 和 `#!/manage/search-detail`。
- 2026-11-04：`PLAN.md` 接口总表新增「页面 / 路由」列，并补回 `#!/report/item_promotion` 等报表页路由；新增「URL 查询规则」：先按路由 + `rptType` / `queryDomains` / `activeKey` 匹配，命中直接调代码，未命中再按 `SPEC.md` 4.6 定位。
- 2026-11-04：新增文档同步 Hook：`.claude/hooks/check_docs.py` + 项目 `.claude/settings.json`。PostToolUse 记录编辑文件；Stop 检查 `endpoints.json` → `PLAN.md`、`api.py` / `collect.py` → `SPEC.md`、`platforms/` 结构变化 → `STRUCTURE.md`，缺失则 block 一次。
- 2026-11-04：Hook 配置从 workspace 根目录迁移到项目 `.claude/settings.json`，命令改为相对路径 `.claude/hooks/check_docs.py`；后续以 `chrome电商数据获取脚本` 作为工作区。
- 2026-11-04：将 `open-shop-browser` skill 复制到项目 `.claude/skills/open-shop-browser/`，随项目工作区加载；原 workspace 版本保留。
