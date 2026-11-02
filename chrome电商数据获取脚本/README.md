# Chrome 电商数据获取脚本

目标：**不打开 tab、不渲染 DOM**，用已登录 Chrome 的 Cookie + 页面 HTML 里的 token（或接口返回的 csrfId），直接调用电商后台的 JSON 接口取数。

当前覆盖两套后台：

- 生意参谋（sycm.taobao.com）→ `collect.py`
- 万相台无界版（one.alimama.com）关键词推广 → `collect_alimama.py`

## 核心结论

1. 页面 HTML 只是 SPA 壳（约 3.6KB），商品数据全部来自 XHR/GET JSON。
2. `token` 不在 Cookie/localStorage，而在 HTML 的 `<meta name="microdata">` 里：
   ```html
   <meta name="microdata" content="...;legalityToken=xxxxxxxx;ctxCcVersion=2.4.238;...">
   ```
3. 不同页面/不同 tab 用**不同的接口集**；`itemId`、`dateRange` 只是参数。
4. 最快定位接口的方式：在**已打开的同域页面**读 `performance` 资源列表 → 找到对应 app bundle → 下载并 grep 接口。
5. 不需要后台 tab；后台 tab 只作为静态分析失败时的兜底。
6. 同一个 bundle 里可能有多个 tab 的卡片；判断归属看代码里的“更多”链接指向哪个 `activeKey`。
7. 页面 URL 里的 `dateType` / `dateRange` 要传给接口；`_` 只是防缓存时间戳，不是数据时间。
8. 万相台的 `csrfId` 不在 Cookie / localStorage / HTML 里，而是由 `POST /member/checkAccess.json` 返回；该接口本身不需要 csrf，所以整条链路同样不需要打开页面。

## 目录

| 文件 | 内容 |
|---|---|
| [01-无tab获取框架.md](01-无tab获取框架.md) | 多账号整体流程：context/账号 → Cookie → token → 接口 → 按账号分仓 |
| [02-URL与接口映射.md](02-URL与接口映射.md) | 页面 URL / tab 对应的接口和参数 |
| [03-快速定位接口.md](03-快速定位接口.md) | 如何从已加载 JS 中快速找到接口 |
| [04-代码模板.md](04-代码模板.md) | Python 最小实现模板 |
| [05-分辨不同profile与账号.md](05-分辨不同profile与账号.md) | 多 profile / 多账号的当前页与账号识别 |
| [endpoints.json](endpoints.json) | 接口清单（占位符版本，可直接改造成配置） |
| [list_browser_profiles.py](list_browser_profiles.py) | 列出当前 browser context、页面、账号 |
| [sycm_api.py](sycm_api.py) | HTTP 层：Cookie、token、接口请求、返回码处理 |
| [collect.py](collect.py) | 生意参谋主入口：多账号批量取数并保存 JSON |
| [config.json](config.json) | 生意参谋采集配置：商品、日期、账号、接口开关 |
| [alimama_api.py](alimama_api.py) | 万相台 HTTP 层：Cookie、checkAccess(csrfId)、报表、计划列表 |
| [collect_alimama.py](collect_alimama.py) | 万相台主入口：总览 / 分时 / 计划列表 |
| [alimama_config.json](alimama_config.json) | 万相台采集配置：端口、账号、日期、输出目录 |
| [PLAN.md](PLAN.md) | 开发计划与当前进度 |

## 快速开始（3 步）

```text
1. 读 Cookie
   CDP 页面级 Network.getCookies（不创建 tab；Storage.getCookies 作兜底）
   或从本地 cookie jar 读取

2. GET 目标页面 HTML
   解析 <meta name="microdata"> → legalityToken

3. 直接 GET JSON 接口
   Cookie + User-Agent + Referer + token + 业务参数
```

## 运行采集脚本

1. Chrome 以 `9223` 端口启动，并已登录店铺账号。
2. 改 `config.json`：`items`（商品 ID）、`dates`（日期）、`accounts`（为空 = 全部账号）。
3. 运行：

```bash
python collect.py
```

常用参数：

```bash
python collect.py --account 察尔汗
python collect.py --item 731918476865 --date 2026-11-01
python collect.py --endpoint sale_overview,flow_top
```

输出在 `data/{店铺}_{loginUserId}/{日期}/{商品ID}/{接口}.json`，每次运行的汇总在 `data/_run_*.json`。

## 运行万相台采集

1. 对应店铺的 Chrome 以 debug 端口启动并已登录万相台（端口见 `alimama_config.json`，默认 9222）。
2. 运行：

```bash
python collect_alimama.py                                  # 今天，当前 profile 账号
python collect_alimama.py --date 2026-11-02,2026-11-01
python collect_alimama.py --days 7                         # 最近 7 天（含今天）
python collect_alimama.py --account 察尔汗 --full-day
python collect_alimama.py --no-hourly --no-campaigns
python collect_alimama.py --reports item_promotion --date 2026-11-02
python collect_alimama.py --reports item_promotion,campaign,adgroup,creative,crowd,bidword,area --date 2026-11-01 --no-hourly --no-campaigns
python collect_alimama.py --reports item_promotion_campaign --date 2026-11-01 --no-hourly --no-campaigns
python collect_alimama.py --reports item_promotion_adgroup --date 2026-11-01 --no-hourly --no-campaigns
```

报表页列表由 `alimama_config.json` 的 `reports` 控制（默认 `["item_promotion"]`），`--reports` 可覆盖；`reportPageSize` 默认 100，自动按 `offset` 翻页。

商品报表支持维度变体：`item_promotion`（商品）、`item_promotion_campaign`（商品×计划）、`item_promotion_adgroup`（商品×计划×单元）。

单元数据（无 tab）：`adgroup_find_list()` / `adgroup_get()` / `adgroup_report_query()` / `adgroup_time_series()`，链路见 `02-URL与接口映射.md` 9.7。时间明细接口只返回有数据的日期，页面表格会把缺失日期补 0；查今天时汇总/分时必须 `fromRealTime=true`。

输出在 `data/alimama/{店铺}_{memberId}/{日期}/`：

| 文件 | 内容 |
|---|---|
| `overview.json` | 总览指标（消耗、点击、成交、ROI 等） |
| `hourly.json` | 分时报表 |
| `campaigns.json` | 计划列表 + 每个计划的 `reportInfoList` |
| `item_promotion.json` | 商品报表：`totalData` 汇总 + `list` 商品行 |
| `item_promotion_campaign.json` | 商品×计划：每行带 `campaignId` / `campaignName` / `promotions` |
| `item_promotion_adgroup.json` | 商品×计划×单元：再带 `adgroupId` / `adgroupName` |
| `campaign/adgroup/creative/crowd/bidword/area.json` | 计划/单元/创意/人群/关键词/地域报表（`--reports` 选择） |

说明：历史日期的 `overview.json` 默认与页面一致，是「截至当前小时」口径；需要全天合计加 `--full-day`。`hourly.json` 和 `campaigns.json` 始终是全天数据。

## 多账号 / 多 profile

如果同时打开了多个 Chrome profile：

```bash
python list_browser_profiles.py
```

它会列出：

- `browserContextId`（CDP 分组用）
- 页面账号（优先从 `meta[name=microdata]` / 页面正文识别）
- `loginUserId` / `tracknick` / `unb`
- Cookie 是否可读
- 当前页标题 / URL
- 可选的 profile 目录 / 显示名（`--profile-path`）

详细原理见 [05-分辨不同profile与账号.md](05-分辨不同profile与账号.md)。

## 适用 / 不适用

**适用：**

- 已有登录态的同一 Chrome profile
- 接口只依赖 Cookie + 页面 token + 普通 query 参数
- 已知页面/接口模板，或能从静态 JS 中找到接口

**不适用 / 需回退：**

- 接口有逐请求动态签名、加密参数
- 需要验证码、滑块、登录挑战
- 一次性 token、强时间戳校验
- WebSocket 推送数据
- 页面改版导致接口变化

## 风险与边界

- 只操作自己账号有权查看的数据。
- 控制频率：串行、随机间隔、不要并发几十个请求。
- 遇到 401/403/429/验证码立即降速或停止。
- Cookie 会过期，`_m_h5_tk` 会轮换；失败时重新读 Cookie、重新取 token。
- 前端发版可能改变接口路径或参数，需要重新定位。

## 一句话流程

```text
生意参谋：
Chrome Cookie（CDP 读，不开 tab）
        +
HTML 里的 legalityToken（HTTP GET，不开 tab）
        +
静态 JS 里找到的接口模板（performance → bundle → grep）
        ↓
直接 HTTP GET JSON

万相台：
Chrome Cookie（CDP 读，不开 tab）
        +
POST /member/checkAccess.json 返回的 csrfId / loginPointId
        ↓
直接 HTTP POST JSON（report/query、campaign/horizontal/findPage）
```
