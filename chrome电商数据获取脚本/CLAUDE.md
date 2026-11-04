# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 首要规则：文档同步

任何新增、修改、完成的需求、模块、状态（包括接口验证状态、脚本行为、配置项、目录约定），都必须在同一次改动中更新 `PLAN.md`：

- 更新「当前阶段」、对应步骤清单和平台矩阵；
- 在「进度记录」末尾追加一条带日期的说明；
- 若涉及接口，同步更新对应数据源 `endpoints.json` 的 `status` 字段；
- 若涉及文件 / 目录的新增、移动、删除、重命名，同步更新 `STRUCTURE.md`；
- 若涉及命令、目录或流程，同步更新 `README.md`、`CLAUDE.md`；若改变规范，更新 `SPEC.md`。

`PLAN.md` 是本项目进度的唯一记录，不要只在对话里说明完成情况。

## 文档同步 Hook

项目 `.claude/settings.json` 配置了两个 Hook，调用 `.claude/hooks/check_docs.py`：

- `PostToolUse`（`Edit|Write|MultiEdit`）：记录本次会话编辑过的文件。
- `Stop`：机械检查：
  - 改了 `endpoints.json` → 必须有 `PLAN.md`
  - 改了 `api.py` / `collect.py` → 必须有 `SPEC.md`
  - `platforms/` 下新增 / 删除 / 重命名文件 → 必须有 `STRUCTURE.md`
- 缺失时 Stop 会 block 一次；第二次 `stop_hook_active` 会放行并提示，避免死循环。
- Hook 只检查文件路径和 git status，不判断「底层逻辑是否真的变了」；语义判断仍靠本文件规则和模型。

## 项目定位

不开 tab、不渲染 DOM：用已登录 Chrome 的 Cookie + 鉴权 token，直接 HTTP 调用电商后台的 JSON 接口。项目分两步：

1. **Profile 与账号**：分辨 Chrome profile，识别各平台账号，确认登录态。
2. **数据采集**：按「平台 → 数据源」取数。技术核心是无页面、无 tab。

当前覆盖淘系 / 天猫的三个数据源：

- 万相台推广（`one.alimama.com`）：`checkAccess` → `csrfId` → `platforms/taobao/alimama/`
- 生意参谋（`sycm.taobao.com`）：页面 HTML → `legalityToken` → `platforms/taobao/sycm/`
- 卖家中心：待写 → `platforms/taobao/seller_center/`

拼多多、抖音、ERP 为占位平台，待写（ERP 也在 `platforms/` 下）。

页面内 `fetch` 只是备选方案；后台 tab 只用于发现接口，不用于日常取数。

## URL → 接口 → 代码 查询流程

当用户给出 URL 或问「这个页面怎么取数」时，按顺序：

1. 归一化 URL：去掉域名，保留 path / hash 路由 + 关键参数（`rptType`、`queryDomains`、`activeKey`、`bizCode`、`campaignId`、`adgroupId`）。
2. 在 `PLAN.md` 的「接口分类总表」的「页面 / 路由」列查找。
3. 命中：直接使用「代码映射」列对应的函数；参数以 `endpoints.json` 为准，不要重新抓包。
4. 未命中：按 `SPEC.md` 4.6 定位接口 → 写/改代码 → 更新 `endpoints.json`、`PLAN.md`、`STRUCTURE.md`。
5. hash 路由的 query 参数是前端状态，实际请求体以 `endpoints.json` 的记录为准。

## DOM 定位

- 需要定位/操作 DOM 时，先调用项目级 `dom-locating` skill（`chrome电商数据获取脚本:dom-locating`），不要凭猜测写选择器。
- sycm 登录表单在跨域 iframe `#alibaba-login-box`（`havanalogin.taobao.com`）内；稳定选择器：`#fm-login-id`、`#fm-login-password`、`#login-form`、`button.fm-submit`。
- Chrome 密码管理器弹窗是浏览器 UI，不在 DOM/网络里；Skill 也覆盖不了，只能人工点击、Chrome 自动登录或 OS 级 UI 自动化。
- 使用 Skill 时若规则失效，必须按 Skill 的「失败闭环」更新规则和 `references/cases.md`，并报告改动。

## 常用命令

从项目根目录执行：

```bash
pip install websockets          # 唯一第三方依赖

# 第一步：profile / 账号
python -m core.browser_profiles
python -m core.browser_profiles --json
python -m core.browser_profiles --profile-path   # 额外开临时后台页读 chrome://version

# 第二步：生意参谋（默认端口 9223）
python -m platforms.taobao.sycm.collect
python -m platforms.taobao.sycm.collect --account 察尔汗
python -m platforms.taobao.sycm.collect --item 731918476865 --date 2026-11-01
python -m platforms.taobao.sycm.collect --endpoint sale_overview,flow_top
python -m platforms.taobao.sycm.collect --output data_test --delay 2-5

# 第二步：万相台（默认端口 9222）
python -m platforms.taobao.alimama.collect
python -m platforms.taobao.alimama.collect --date 2026-11-02,2026-11-01
python -m platforms.taobao.alimama.collect --days 7
python -m platforms.taobao.alimama.collect --full-day             # 历史总览用全天口径
python -m platforms.taobao.alimama.collect --no-hourly --no-campaigns
python -m platforms.taobao.alimama.collect --reports item_promotion --date 2026-11-02
python -m platforms.taobao.alimama.collect --reports item_promotion_campaign,item_promotion_adgroup
python -m platforms.taobao.alimama.collect --reports item_promotion,campaign,adgroup,creative,crowd,bidword,area --no-hourly --no-campaigns

# 冒烟检查
python -m py_compile core/browser_profiles.py platforms/taobao/sycm/api.py platforms/taobao/sycm/collect.py platforms/taobao/alimama/api.py platforms/taobao/alimama/collect.py
python -m platforms.taobao.sycm.collect --help
python -m platforms.taobao.alimama.collect --help
```

项目没有测试套件。改动后用 `py_compile` 和 `--help` 做冒烟检查；条件允许时连接真实 Chrome 实跑一个接口。

需要启动店铺浏览器时，使用项目内的 `open-shop-browser` skill（`.claude/skills/open-shop-browser/`），不要手写 Chrome 启动命令。默认 user data dir 见 `core/browser_profiles.py` 的 `DEFAULT_USER_DATA`（`E:\VS Code\浏览器控制方案\chrome_profile_full`），profile 映射见 `SPEC.md` 第 3 节。

## 架构

```text
core/browser_profiles.py        # 共用：CDP、context 分组、账号识别、Cookie
platforms/taobao/sycm/          # 数据源：collect.py（编排）+ api.py（HTTP）+ endpoints.json + config.json
platforms/taobao/alimama/       # 数据源：同上
platforms/taobao/seller_center/ # 待写
platforms/pdd/                  # 待写
platforms/douyin/               # 待写
platforms/erp/                  # 待写
```

完整文件树、每个文件的作用和新增文件放置规则见 `STRUCTURE.md`；物理结构以该文件为准。

### 1. `core/browser_profiles.py` — 第一步 / CDP 基础层

- 连接 `http://localhost:9223/json/version` 的浏览器级 WebSocket，`Target.getTargets` 后过滤 `type=page`，按 `browserContextId` 分组
- 账号识别：优先 attach 页面执行 `JS_IDENTIFY`，读 `meta[name=microdata]` 的 `loginUserId` / `runAsShopTitle` 和正文店铺名
- Cookie：页面级 `Network.getCookies` 优先；失败才回退 `Storage.getCookies`（实测部分 context 返回 0 个 Cookie）
- 同时作为 CLI 输出账号清单；`--profile-path` 会临时开后台页读 `chrome://version`

### 2. `platforms/taobao/sycm/` — 生意参谋

- `api.py`：纯 HTTP 层。Cookie 头只保留 taobao / tmall 域，跳过已过期项，sycm 域同名 Cookie 优先；token 从页面 HTML 解析；参数合并 = 公共参数 → 接口默认值 → config 覆盖；错误映射 `code=0/1100/1003/401/403`
- `collect.py`：编排层。按 context 识别账号；账号 key = `店铺名_loginUserId`；四层串行（账号 → 商品 → 日期 → 接口）；token 缓存键为 `(account.key, page_key)`；输出 `data/taobao/sycm/{店铺}_{loginUserId}/{日期}/{商品ID}/{接口}.json`

### 3. `platforms/taobao/alimama/` — 万相台

- `api.py`：纯 HTTP 层。Cookie 头优先 alimama 域；`check_access()` 调 `POST /member/checkAccess.json` 拿 `csrfId`、`loginPointId`、`memberId`；`report_query()` 取总览/分时；`campaign_find_page()` 取计划列表；`report_list()` 取报表页列表（`REPORT_LIST_SPECS` 覆盖 item_promotion / item_promotion_campaign / item_promotion_adgroup / campaign / adgroup / creative / crowd / bidword / area）；`campaign_find_list()` / `adgroup_find_list()` / `adgroup_get()` / `adgroup_report_query()` / `adgroup_time_series()` 取计划 / 单元链路
- `collect.py`：编排层。浏览器级 `Storage.getCookies`（不开 tab）→ `check_access` → 按日期串行取 overview / hourly / campaigns / reports → 保存 `data/taobao/alimama/{店铺}_{memberId}/{日期}/`
- `csrfId` 过期（HTTP 403）时自动重新 `checkAccess` 并重试一次
- 历史日期总览默认 `allDay=false`（与页面一致：截至当前小时）；`--full-day` 改为全天口径。分时与计划始终全天

## 配置与接口模板

**每个数据源一个 `endpoints.json`，与自己的代码同目录；它是该数据源接口的唯一事实来源。**

- 生意参谋：`pages[页面URL].endpoints[接口名] = {url, params, status}`
- 万相台：`pages[#!/manage/search]` / `pages[#!/report/item_promotion]` / `pages[#!/manage/search-detail]`；`report_pages` 记录报表页的 `route` + `rptType` + `queryDomains` + `extra`；`common` 记录 checkAccess 鉴权链路
- 万相台 `config.json` 的 `reports` 选择报表页，`reportPageSize` 控制分页
- `params` 是字符串数组：`"itemId"` 表示参数名；`"device=0"` 表示参数带默认值
- `status` 取值：`已验证` / `代码确认` / `部分验证` / `未验证`；接口状态变化时同步更新 `PLAN.md`
- `config.json` 的 `endpoints` 可写接口名，或 `{page, name, params}`；只写名字时由 `collect.py` 的 `PAGE_HINTS` 决定用哪个页面取 token
- 参数合并顺序：公共参数 → `endpoints.json` 默认值 → `config.json` 覆盖
- 配置里的相对路径以项目根为基准

## 关键约定

- 账号身份用 `店铺名 + loginUserId`；`browserContextId` 是会话级 UUID，重启会变，不能当稳定 ID
- Cookie、token、权限按账号隔离：不能拿 A 账号的 token 配 B 账号的 Cookie；同一商品在不同账号下可能返回 `1100`
- `_` 是防缓存毫秒时间戳，不是数据时间；`dateRange=start|end`（URL 编码为 `%7C`）；`dateType=today` 使用 realtime 版接口
- 正常取数不创建 tab；只有 `--profile-path` 和接口探测兜底会开后台页
- 万相台 `csrfId` 不在 Cookie / localStorage / HTML 里，必须从 `checkAccess` 拿；该接口不需要 csrf，所以不需要先打开页面
- 万相台历史总览默认是页面口径（截至当前小时），`--full-day` 才是全天；报数时先确认用哪个口径
- 找新接口的顺序：已开页面 `performance` 资源列表 → 下载 `op-cc/app.js`、`65.js` → grep `.json` → 从代码上下文确认参数。不要猜 `index.js`，不要扫 Chrome 缓存（详见 `SPEC.md` 4.6）
- Windows 下入口脚本统一 `reconfigure(encoding="utf-8", errors="replace")`，新增入口脚本沿用
- 目录名用英文：`platforms/<platform>/<source>/`；每个已实现的数据源必须有自己的 `collect.py`、`api.py`、`endpoints.json`、`config.json`，待写数据源先用 `README.md` 占位

## 文档地图

| 文件 | 作用 |
|---|---|
| `README.md` | 项目入口、目录、常用命令、适用边界 |
| `SPEC.md` | 项目规范：两步流程、关键技术、接口获取方法、目录约定 |
| `PLAN.md` | 计划与进度（每次改动必须更新） |
| `STRUCTURE.md` | 文件目录：物理树、每个文件的作用、新增文件放置规则 |
| `CLAUDE.md` | 本文件：给 Claude 的项目约定 |
| `platforms/taobao/sycm/endpoints.json` | 生意参谋接口模板与验证状态 |
| `platforms/taobao/alimama/endpoints.json` | 万相台接口模板与验证状态 |
| `.claude/skills/dom-locating/` | DOM 定位 skill |
