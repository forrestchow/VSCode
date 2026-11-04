# Chrome 电商数据采集

**不开 tab、不渲染 DOM**，用已登录 Chrome 的 Cookie + 平台鉴权 token，直接 HTTP 调用电商后台的 JSON 接口。

项目核心是两步：

1. **Profile 与账号**：分辨不同用户名称的 Chrome profile，并让不同平台对应的账号处于登录态。
2. **数据采集**：按「平台 → 数据源」采集数据。第二步的技术核心是无页面、无 tab 直接取数。

规范见 [SPEC.md](SPEC.md)，当前进度见 [PLAN.md](PLAN.md)。想知道某个页面 URL 对应哪个接口，查 `PLAN.md` 的「接口分类总表」的「页面 / 路由」列。

## 平台与数据源

| 平台 | 数据源 | 状态 |
|---|---|---|
| 淘系 / 天猫 | 万相台推广（`one.alimama.com`） | ✅ 已实跑 |
| 淘系 / 天猫 | 生意参谋（`sycm.taobao.com`） | 🟡 代码完成待实跑 |
| 淘系 / 天猫 | 卖家中心后台 | ⬜ 待写 |
| 拼多多 | 待定 | ⬜ 待写 |
| 抖音 | 待定 | ⬜ 待写 |
| ERP | 待定（具体 ERP 系统） | ⬜ 待写 |

## 目录

```text
chrome电商数据获取脚本/
├─ SPEC.md                       # 项目规范：两步流程、关键技术、接口获取
├─ PLAN.md                       # 进度：两步 × 平台 × 数据源
├─ core/
│   └─ browser_profiles.py       # CDP / profile / 账号 / Cookie
├─ platforms/
│   ├─ taobao/
│   │   ├─ sycm/                 # 生意参谋：collect.py / api.py / endpoints.json / config.json
│   │   ├─ alimama/              # 万相台：同上
│   │   └─ seller_center/        # 待写
│   ├─ pdd/                      # 待写
│   ├─ douyin/                   # 待写
│   └─ erp/                      # 待写
└─ data/                         # 运行后生成（gitignore）
```

完整文件树和每个文件夹 / 文件的作用见 [STRUCTURE.md](STRUCTURE.md)。

## 环境

```bash
pip install websockets
```

前提：对应店铺的 Chrome 以 debug 端口启动，并已登录目标平台。需要启动店铺浏览器时，使用项目内的 `open-shop-browser` skill（`.claude/skills/open-shop-browser/`），不要手写 Chrome 启动命令。

## 常用命令

从项目根目录执行：

```bash
# 第一步：列出当前 profile / context / 账号
python -m core.browser_profiles
python -m core.browser_profiles --json
python -m core.browser_profiles --profile-path   # 额外读 chrome://version，会开临时后台页

# 第二步：生意参谋（默认端口 9223）
python -m platforms.taobao.sycm.collect
python -m platforms.taobao.sycm.collect --account 察尔汗
python -m platforms.taobao.sycm.collect --item 731918476865 --date 2026-11-01
python -m platforms.taobao.sycm.collect --endpoint sale_overview,flow_top

# 第二步：万相台（默认端口 9222）
python -m platforms.taobao.alimama.collect
python -m platforms.taobao.alimama.collect --date 2026-11-02,2026-11-01
python -m platforms.taobao.alimama.collect --days 7
python -m platforms.taobao.alimama.collect --account 察尔汗 --full-day
python -m platforms.taobao.alimama.collect --no-hourly --no-campaigns
python -m platforms.taobao.alimama.collect --reports item_promotion --date 2026-11-02
python -m platforms.taobao.alimama.collect --reports item_promotion_campaign,item_promotion_adgroup
python -m platforms.taobao.alimama.collect --reports item_promotion,campaign,adgroup,creative,crowd,bidword,area --no-hourly --no-campaigns
```

也支持直接跑文件，例如 `python platforms/taobao/sycm/collect.py`。

## 输出

| 数据源 | 路径 |
|---|---|
| 生意参谋 | `data/taobao/sycm/{店铺}_{loginUserId}/{日期}/{商品ID}/{接口}.json` |
| 万相台 | `data/taobao/alimama/{店铺}_{memberId}/{日期}/{overview,hourly,campaigns}.json` |
| 万相台报表页 | `data/taobao/alimama/{店铺}_{memberId}/{日期}/{报表类型}.json`（如 `item_promotion.json`、`item_promotion_campaign.json`） |
| 运行汇总 | 各数据源输出目录下的 `_run_*.json` |

## 配置与接口模板

- 每个数据源自带 `config.json`（商品 / 日期 / 账号 / 接口开关）和 `endpoints.json`（接口模板与验证状态）。
- `endpoints.json` 是该数据源接口的唯一事实来源；`PLAN.md` 的「接口分类总表」按「平台 → 数据源 → 页面 / 路由 → 接口」做人读索引。
- 万相台 `config.json` 的 `reports` 选择报表页，`reportPageSize` 控制每页条数；报表页的 `route` / `rptType` / `queryDomains` 记录在 `endpoints.json` 的 `report_pages`。
- 配置里的相对路径以项目根为基准。

## 适用 / 不适用

**适用：**

- 已有登录态的同一 Chrome profile。
- 接口只依赖 Cookie + 页面 token / 接口换取的 token + 普通参数。
- 已知接口模板，或能从静态 JS 中找到接口。

**不适用 / 需回退：**

- 接口有逐请求动态签名、加密参数。
- 需要验证码、滑块、登录挑战。
- 一次性 token、强时间戳校验。
- WebSocket 推送数据。
- 页面改版导致接口变化。

## 风险与边界

- 只操作自己账号有权查看的数据。
- 串行、随机间隔，不要并发几十个请求。
- 遇到 401 / 403 / 429 / 验证码立即降速或停止。
- Cookie 会过期；失败时重新读 Cookie、重新取 token。
- 前端发版可能改变接口路径或参数，需要重新定位。
