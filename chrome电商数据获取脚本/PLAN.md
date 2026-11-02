# Chrome 电商数据获取脚本 · 开发计划

> 每完成一个阶段，更新本文件的「进度」。第一版只做「取数 + 存 JSON」，不做数据库、Excel、定时任务。

## 文档维护规则

任何新增、修改、完成的需求、模块、状态（含接口验证状态、脚本行为、配置项、目录约定），都必须在同一次改动中更新本文件：

1. 更新「当前阶段」和计划表中的进度 / 状态；
2. 在「进度记录」末尾追加一条带日期的说明；
3. 涉及接口时，同步更新 `endpoints.json` 的 `status` 和 `02-URL与接口映射.md` 的状态标记。

本文件是项目进度的唯一记录，不要只在对话里说明完成情况。

## 当前阶段

**生意参谋 `collect.py` 待实跑；万相台 `collect_alimama.py` 已实跑验证（2026-11-02）**

## 计划

| 当前阶段 | 进度 | 关键点 | 映射的代码文件 |
|---|---|---|---|
| 阶段 0 · 资料与接口确认 | ✅ 100% | 文档、接口清单、账号识别已完成；sale / flow 主要接口已验证 | `01~05-*.md`、`endpoints.json`、`list_browser_profiles.py` |
| 阶段 1 · CDP 底座 | ✅ 100%（已复用） | websockets 直连 `9223`；按 `browserContextId` 分组；账号用「店铺名 + loginUserId」；Cookie 固定按 `sycm.taobao.com` 用页面级 `Network.getCookies` 取 | `list_browser_profiles.py` |
| **阶段 2 · Token + 接口调用** | 🟡 代码完成，待实跑 | 每个账号 GET 自己页面 HTML → 解析 `meta[microdata]` 的 `legalityToken`；token 按「账号 + 页面」缓存，不跨账号；`code=0` 成功，`1100` 跳过，`1003` 记日志，401/403 判登录失效 | `sycm_api.py`（新建） |
| 阶段 3 · 批量采集主流程 | 🟡 代码完成，待实跑 | 账号 → 商品 → 日期 → 接口，四层串行；请求间隔 1~3 秒；单账号失败不影响其他；第一版只跑 5 个已验证接口 | `collect.py`（新建） |
| 阶段 4 · 配置与保存 | 🟡 代码完成，待实跑 | `config.json` 配商品 / 日期 / 账号 / 接口开关；参数合并 = 公共参数 + 接口默认值 + config 覆盖；保存到 `data/{店铺}_{loginUserId}/{日期}/{商品ID}/{接口}.json`；结束打印成功/失败汇总 | `config.json`（新建）、`collect.py` |
| 阶段 5 · 万相台无界版 | ✅ 100% | `Storage.getCookies` → `checkAccess` 取 csrfId → 总览 / 分时 / 计划列表；`--full-day` 切换历史总览全天口径；察尔汗 2026-11-01、11-02 实跑通过 | `alimama_api.py`、`collect_alimama.py`、`alimama_config.json`、`endpoints.json` |
| 阶段 6 · 报表页列表 | ✅ 100% | 通用 `POST /report/query.json`：`rptType` + `queryDomains` 区分商品/计划/单元/创意/人群/关键词/地域；商品报表支持维度变体（商品×计划、商品×计划×单元）；`offset` 分页；`--reports` 选择；察尔汗 2026-11-01 七类报表、11-02 商品报表实跑通过 | `alimama_api.py`、`collect_alimama.py`、`alimama_config.json`、`endpoints.json` |

## 第一版范围

- 主路线：Python HTTP 直连（README 的「不开 tab」方案）；页面内 `fetch` 留作后续兜底。
- 只跑 5 个已验证接口：`sale_overview`、`sale_sku_list`、`sale_trend`、`flow_top`、`searchword_top`。
- 每个接口只取第一页（`page=1`，`pageSize=10`）；完整分页后续再加。
- 不做：数据库、Excel、定时任务、后台 tab 抓包、未验证的 service / customer / content tab。

## 文件结构

```text
chrome电商数据获取脚本/
├─ collect.py               # 生意参谋主入口 + 批量采集 + 保存
├─ sycm_api.py              # 生意参谋 token、请求头、GET JSON、返回码处理
├─ config.json              # 生意参谋：商品 / 日期 / 账号 / 接口配置
├─ collect_alimama.py       # 万相台主入口：总览 / 分时 / 计划列表
├─ alimama_api.py           # 万相台 checkAccess(csrfId)、报表、计划列表
├─ alimama_config.json      # 万相台：端口 / 账号 / 日期 / 输出目录
├─ endpoints.json           # 接口模板（含 alimama 段）
├─ list_browser_profiles.py # CDP / 账号 / Cookie（已有，直接复用）
├─ PLAN.md                  # 本文件
└─ data/                    # 运行后生成（data/alimama 为万相台）
```

## 进度记录

- 2026-11-02：计划确认，开始写 `sycm_api.py`、`collect.py`、`config.json`。
- 2026-11-02：三个文件已写完，`py_compile` 和 `--help` 通过；尚未连接真实 Chrome 实跑。
- 2026-11-02：新增 `CLAUDE.md`（项目架构、常用命令、文档同步规则）；本文件自此作为进度唯一记录。
- 2026-11-02：在 `01-无tab获取框架.md` 明确「抓包是获得接口的备选方案」：首选 performance + bundle grep，静态分析失败才后台 tab 抓 Network；抓到后写入 `endpoints.json`，日常采集不再抓包。
- 2026-11-02：新增用户级 `dom-locating` Skill（含失败闭环、案例库、changelog）；在 `CLAUDE.md` 加入 DOM 定位指针和 sycm 登录页选择器。
- 2026-11-02：新增万相台无界版采集：`alimama_api.py`、`collect_alimama.py`、`alimama_config.json`；接口模板写入 `endpoints.json` 的 `alimama` 段；`02-URL与接口映射.md` 新增第 9 节；`README.md` / `CLAUDE.md` 同步。
- 2026-11-02：万相台实跑察尔汗 2026-11-02 / 2026-11-01，6 次调用全部成功；历史总览默认页面口径（11-01 为 77.06，截至当前小时），`--full-day` 返回全天 122.33。
- 2026-11-02：`dom-locating` Skill 由用户级迁移为项目级 `.claude/skills/dom-locating`，CLAUDE.md 指针同步；原用户级目录已送回收站。
- 2026-11-02：补充 `dom-locating` 案例：Playwright 只能点击账号框触发 Chrome 密码管理器弹层，弹层需用 Windows UIA 的 `InvokePattern` 选择；实测「察尔汗壹品盐专卖店:绍飞」自动填表并登录万相台成功。
- 2026-11-02：新增万相台报表页列表采集：`report_list()` + `REPORT_LIST_SPECS` 覆盖 item_promotion/campaign/adgroup/creative/crowd/bidword/area；`collect_alimama.py` 新增 `--reports` / `--report-page-size`，输出 `{报表类型}.json`；察尔汗 2026-11-01 七类报表、2026-11-02 商品报表实跑通过。
- 2026-11-02：`CLAUDE.md` 首要规则新增「接口优先登记」：新接口/接口变更必须第一时间写入 `02-URL与接口映射.md` 第 1 节「接口总表」（分类 / URL / 接口 / 关键词参数），分类未定先留空；同步 `endpoints.json`。
- 2026-11-02：破解并验证商品报表维度变体：`queryDomains` 加 `campaign` 得到商品×计划（`campaignId` / `campaignName` / `promotions`），再加 `adgroup` 得到商品×计划×单元；新增 `item_promotion_campaign` / `item_promotion_adgroup` specs；2026-11-01 实跑分别 15 / 6 条，7 天区间商品×计划 20 条。
- 2026-11-02：定位计划报表「管理推广计划」跳转规则 `#!/{managePath}-detail?bizCode={bizCode}&campaignId={campaignId}`，验证关键词推广 `/manage/search-detail?...&campaignId=84609956458` 可正常打开；`02-URL与接口映射.md` 新增 9.6 节记录各场景 managePath。
- 2026-11-02：验证计划详情页「单元」标题跳转：同一 `/manage/search-detail` 路由追加 `adgroupId` 即进入单元概览；实测 `campaignId=84609956458&adgroupId=84445547910` 正常打开，文档 9.6 同步。
- 2026-11-02：验证并封装计划→单元无 tab 链路：`/adgroup/findList.json`、`/adgroup/get.json`、`/report/query.json`（`sourceList=["adgroup_detail"]`）；实测 2026-10-03~11-01 单元 84445547910 消耗 186.00 / 点击 72 / 成交 171.00 / ROI 0.92；文档 9.7 与 `endpoints.json` 同步。
- 2026-11-02：验证动态发现：计划报表 15 个计划全部成功调用 `/adgroup/findList.json`（15/15）；`/campaign/findList.json` 在 onebpSearch/onebpSite/onebpShortVideo 返回 6/7/4 个在投或暂停计划，可用于发现新计划；新增 `campaign_find_list()`，文档与 `endpoints.json` 同步。
- 2026-11-02：定位并验证单元页「推广解读」弹层数据：`/report/query.json` 的 `theme_campare`（趋势主题 5 条）与 `theme_top_keyword`（Top 关键词 20 条）；无 tab 复现并保存到 `adgroup_84445547910_promotion_insight.json`；文档 9.8 与 `endpoints.json` 同步。
- 2026-11-02：验证推广解读日期粒度一致性：过去 7 天 = 2026-10-26~2026-11-01（不含今天）；逐日 7 次求和与区间一次查询在趋势主题（5 个）和 Top 关键词（22 个）上 adPv/click/charge/成交/订单/购物车逐 key 完全一致；发现 Top 关键词接口每页最多 20 条，区间查询必须用 `offset=20` 取第二页，否则会误判为不一致。
- 2026-11-02：验证单元时间明细无 tab 采集：`/report/query.json` 加 `sourceList=["adgroup_detail"]`、`queryDomains=["date"]`、`splitType="day"`；2026-10-26~11-01 接口返回 5 天有数据行，页面补齐 7 天（10-26/10-27 为 0）；新增 `adgroup_time_series()`，数据保存到 `adgroup_84445547910_daily.json`。
- 2026-11-02：验证今天（实时）口径：单元汇总/分时必须 `fromRealTime=true`，否则返回空；`adgroup_report_query()` / `adgroup_time_series()` 增加 `is_today` 参数；今日数据已采集到 `adgroup_84445547910_today.json`（汇总消耗 7.43、点击 3、adPv 121；分时 15 个有数据小时，用 `hourId` 标识）。
