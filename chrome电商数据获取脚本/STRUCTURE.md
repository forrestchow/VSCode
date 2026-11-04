# 文件目录（项目结构）

> 本文件是项目**物理结构**的唯一事实来源：新增、移动、删除、重命名任何文件或目录，必须在同一次改动中更新本文件。
> 项目规范见 [SPEC.md](SPEC.md)，进度见 [PLAN.md](PLAN.md)，快速开始见 [README.md](README.md)。
> 如果本文件与 README / SPEC / CLAUDE 中的目录描述冲突，以本文件为准。

## 1. 维护规则

1. **任何文件 / 目录变化**（新增、移动、删除、重命名）都要更新本文件的「项目树」和对应角色表。
2. **新增平台 / 数据源**时，同时更新：项目树、角色表、「新增文件放哪里」。
3. 本文件只回答「有什么、在哪、干什么」；接口参数放 `endpoints.json`，进度放 `PLAN.md`，流程规范放 `SPEC.md`。
4. 运行产物（`data/`、`__pycache__/`）只描述结构和路径模式，不逐条列出实际数据文件。
5. 改变目录约定时，同一次改动更新 `SPEC.md` 第 5 节、`README.md`、`CLAUDE.md` 和本文件。

刷新目录树可参考（排除 `.git`、`data/`、`__pycache__`）：

```bash
find . -path ./.git -prune -o -path ./data -prune -o -name __pycache__ -prune -o -print | sort
```

## 2. 项目树

```text
chrome电商数据获取脚本/
├─ .claude/
│  ├─ hooks/
│  │  └─ check_docs.py
│  ├─ settings.json
│  └─ skills/
│     ├─ dom-locating/
│     │  ├─ SKILL.md
│     │  └─ references/
│     │     ├─ cases.md
│     │     ├─ cdp-patterns.md
│     │     └─ changelog.md
│     └─ open-shop-browser/
│        └─ SKILL.md
├─ .gitignore
├─ README.md
├─ SPEC.md
├─ PLAN.md
├─ CLAUDE.md
├─ STRUCTURE.md
├─ core/
│  ├─ __init__.py
│  └─ browser_profiles.py
├─ platforms/
│  ├─ __init__.py
│  ├─ taobao/
│  │  ├─ __init__.py
│  │  ├─ sycm/
│  │  │  ├─ __init__.py
│  │  │  ├─ collect.py
│  │  │  ├─ api.py
│  │  │  ├─ endpoints.json
│  │  │  └─ config.json
│  │  ├─ alimama/
│  │  │  ├─ __init__.py
│  │  │  ├─ collect.py
│  │  │  ├─ api.py
│  │  │  ├─ endpoints.json
│  │  │  └─ config.json
│  │  └─ seller_center/
│  │     └─ README.md
│  ├─ pdd/
│  │  └─ README.md
│  ├─ douyin/
│  │  └─ README.md
│  └─ erp/
│     └─ README.md
└─ data/                         # 运行时生成，gitignore
   ├─ taobao/
   │  ├─ sycm/
   │  │  └─ {店铺}_{loginUserId}/{日期}/{商品ID}/{接口}.json
   │  └─ alimama/
   │     └─ {店铺}_{memberId}/{日期}/{overview,hourly,campaigns}.json
   ├─ pdd/                        # 计划中
   ├─ douyin/                     # 计划中
   └─ erp/<system>/               # 计划中；每个 ERP 系统一个子目录
```

## 3. 根目录文件

| 文件 | 作用 | 主要内容 / 谁使用 |
|---|---|---|
| `README.md` | 项目入口 | 项目定位、平台状态、快速命令、适用边界；给人看 |
| `SPEC.md` | 项目规范 | 两步流程、关键技术、接口获取方法、代码约定；给人 / AI 看 |
| `PLAN.md` | 计划与进度 | 第一步清单、第二步平台矩阵、接口分类与代码映射、进度记录；每次改动必须更新 |
| `CLAUDE.md` | 给 Claude Code 的项目约定 | 文档同步规则、常用命令、架构摘要、DOM 定位规则、关键约定 |
| `STRUCTURE.md` | 本文件 | 物理目录树、每个文件夹 / 文件的作用、新增文件放置规则 |
| `.gitignore` | Git 忽略规则 | 忽略 `__pycache__/`、`*.pyc`、`data/`、本地 Claude 设置 |

## 4. `core/`：跨数据源共用能力

| 文件 | 作用 | 关键内容 |
|---|---|---|
| `__init__.py` | 包标记 | 空文件，使 `core` 可被 `python -m` / `import` |
| `browser_profiles.py` | CDP 基础层（第一步） | `CDP` 类、`Target.getTargets`、`JS_IDENTIFY`、页面级 `Network.getCookies`、`Storage.getCookies` 兜底、profile 路径 / 显示名、账号 CLI |

使用方：

- `platforms/taobao/sycm/collect.py`：`CDP`、`JS_IDENTIFY`、`attach_page`、`evaluate`、`read_page_cookies`、`pick_page`、`shop_hint`、`decode_cookie`、`http_json`
- `platforms/taobao/alimama/collect.py`：`CDP`、`http_json`

## 5. `platforms/`：平台与数据源

### 5.1 层级约定

```text
platforms/<平台>/<数据源>/
```

- `<平台>`：`taobao`、`pdd`、`douyin`、`erp` 等。
- `<数据源>`：平台内的一个后台，如 `sycm`（生意参谋）、`alimama`（万相台）、`seller_center`（卖家中心）。
- 每个已实现的数据源固定四件套：`collect.py`、`api.py`、`endpoints.json`、`config.json`。
- 待写数据源先用 `README.md` 占位。

### 5.2 `platforms/__init__.py`、`platforms/taobao/__init__.py`

空文件，包标记，使 `platforms.taobao.sycm` / `platforms.taobao.alimama` 可被 `python -m` 识别。

### 5.3 `platforms/taobao/sycm/`：生意参谋

| 文件 | 作用 | 关键内容 |
|---|---|---|
| `__init__.py` | 包标记 | 空文件 |
| `collect.py` | 编排层 / 主入口 | CLI、读 `config.json` + `endpoints.json`、CDP 连接、账号识别、账号 → 商品 → 日期 → 接口四层循环、token 缓存、错误处理、保存、运行汇总 |
| `api.py` | HTTP 层 | Cookie 头、请求头、GET 页面 HTML、解析 `legalityToken`、参数合并、`request_json`、返回码映射 |
| `endpoints.json` | 接口模板（代码会读） | `pages[页面路由].endpoints[接口名] = {url, params, status, note}`；完整接口清单 |
| `config.json` | 运行配置 | 端口 9223、账号、商品、日期、`dateType`、接口开关、请求间隔、输出目录 |

入口：

```bash
python -m platforms.taobao.sycm.collect
```

输出：

```text
data/taobao/sycm/{店铺}_{loginUserId}/{日期}/{商品ID}/{接口}.json
data/taobao/sycm/_run_*.json
```

### 5.4 `platforms/taobao/alimama/`：万相台

| 文件 | 作用 | 关键内容 |
|---|---|---|
| `__init__.py` | 包标记 | 空文件 |
| `collect.py` | 编排层 / 主入口 | CLI、读 `config.json`、浏览器级 Cookie、`check_access`、按日期取 overview / hourly / campaigns / reports、报表页分页、csrfId 失效重试、保存、运行汇总 |
| `api.py` | HTTP 层 | Cookie 头、POST JSON、`check_access`、`report_query`、`campaign_find_page`、`report_list`（报表页列表）、`campaign_find_list` / `adgroup_find_list` / `adgroup_get` / `adgroup_report_query` / `adgroup_time_series`、请求体构造、指标字段 |
| `endpoints.json` | 接口契约（代码不读） | 鉴权链路、接口 URL / method / query / body / 返回结构 / 状态；`report_pages` 记录报表页的 `route` / `rptType` / `queryDomains` / `extra`；给人看 |
| `config.json` | 运行配置 | 端口 9222、账号、日期、计划分页大小、报表页选择（`reports`）、报表分页大小（`reportPageSize`）、请求间隔、输出目录 |

入口：

```bash
python -m platforms.taobao.alimama.collect
```

输出：

```text
data/taobao/alimama/{店铺}_{memberId}/{日期}/overview.json
data/taobao/alimama/{店铺}_{memberId}/{日期}/hourly.json
data/taobao/alimama/{店铺}_{memberId}/{日期}/campaigns.json
data/taobao/alimama/{店铺}_{memberId}/{日期}/{报表类型}.json
data/taobao/alimama/_run_*.json
```

> 注意：生意参谋的 `endpoints.json` 会被代码读取（数据驱动）；万相台的 `endpoints.json` 只作契约和状态记录（函数驱动）。

### 5.5 `platforms/taobao/seller_center/`：卖家中心（待写）

| 文件 | 作用 |
|---|---|
| `README.md` | 占位说明：状态、目标、落地步骤、输出目录 |

尚无 `collect.py` / `api.py` / `endpoints.json` / `config.json`，也没有 `__init__.py`。

### 5.6 `platforms/pdd/`：拼多多（待写）

| 文件 | 作用 |
|---|---|
| `README.md` | 占位说明：数据源分类待定、账号 / 登录 / 鉴权 / 接口发现待确认 |

### 5.7 `platforms/douyin/`：抖音（待写）

| 文件 | 作用 |
|---|---|
| `README.md` | 占位说明：数据源分类待定、账号 / 登录 / 鉴权 / 接口发现待确认 |

### 5.8 `platforms/erp/`：ERP（待写）

| 文件 | 作用 |
|---|---|
| `README.md` | 占位说明：ERP 按平台管理，具体 ERP 系统作为其下的数据源（`platforms/erp/<system>/`） |

## 6. `.claude/`：项目级 Claude 配置

| 文件 | 作用 |
|---|---|
| `settings.json` | Hook 配置：`PostToolUse` 调用 `check_docs.py --event post-tool-use`；`Stop` 调用 `check_docs.py --event stop` |
| `hooks/check_docs.py` | 文档同步 Hook：PostToolUse 记录编辑过的文件；Stop 检查 PLAN / SPEC / STRUCTURE 是否同步 |
| `skills/dom-locating/SKILL.md` | DOM 定位 skill 入口：选择器、iframe / Shadow DOM / 虚拟列表规则、失败闭环 |
| `skills/dom-locating/references/cases.md` | DOM 定位案例库 |
| `skills/dom-locating/references/cdp-patterns.md` | CDP 定位 / 操作模式 |
| `skills/dom-locating/references/changelog.md` | Skill 规则变更记录 |
| `skills/open-shop-browser/SKILL.md` | 打开指定店铺的 Chrome 调试窗口（open-shop-browser） |

> Hook 命令使用相对路径 `.claude/hooks/check_docs.py`，因此工作时区应为项目根目录 `chrome电商数据获取脚本`。

## 7. `data/`：运行产物（gitignore）

`data/` 不入库，运行时按需创建。当前已实现的数据源：

| 路径 | 内容 |
|---|---|
| `data/taobao/sycm/{店铺}_{loginUserId}/{日期}/{商品ID}/{接口}.json` | 生意参谋接口原始响应 + 请求参数 + 账号信息 |
| `data/taobao/sycm/_run_*.json` | 生意参谋每次运行的汇总 |
| `data/taobao/alimama/{店铺}_{memberId}/{日期}/overview.json` | 万相台总览 |
| `data/taobao/alimama/{店铺}_{memberId}/{日期}/hourly.json` | 万相台分时 |
| `data/taobao/alimama/{店铺}_{memberId}/{日期}/campaigns.json` | 万相台计划列表 |
| `data/taobao/alimama/{店铺}_{memberId}/{日期}/{报表类型}.json` | 万相台报表页列表（如 `item_promotion.json`、`item_promotion_campaign.json`） |
| `data/taobao/alimama/_run_*.json` | 万相台每次运行的汇总 |

计划中的输出目录：`data/pdd/`、`data/douyin/`、`data/erp/<system>/`。

其他生成物：`__pycache__/`、`*.pyc`，已由 `.gitignore` 忽略。

## 8. 新增文件放哪里

| 要新增的东西 | 放置位置 |
|---|---|
| 共用 CDP / profile / 账号 / Cookie 能力 | `core/` |
| 新平台 | `platforms/<platform>/` |
| 新数据源 | `platforms/<platform>/<source>/` |
| 数据源的接口模板 | `platforms/<platform>/<source>/endpoints.json` |
| 数据源的运行配置 | `platforms/<platform>/<source>/config.json` |
| 数据源的 HTTP 层 | `platforms/<platform>/<source>/api.py` |
| 数据源的编排 / 入口 | `platforms/<platform>/<source>/collect.py` |
| 待写数据源占位 | `platforms/<platform>/<source>/README.md` |
| ERP 平台 | `platforms/erp/`；具体 ERP 系统作为其数据源放在 `platforms/erp/<system>/` |
| 项目规范 / 计划 / 目录 | 根目录 `SPEC.md` / `PLAN.md` / `STRUCTURE.md` |
| 项目级 skill | `.claude/skills/<skill-name>/`（如 `dom-locating/`、`open-shop-browser/`） |
| 项目级 Hook 脚本 / 配置 | `.claude/hooks/` + `.claude/settings.json` |
| 临时输出 / 采集结果 | `data/`（gitignore，不提交） |

## 9. 目录变更检查清单

- [ ] 项目树是否更新？
- [ ] 对应文件 / 目录的角色表是否更新？
- [ ] `README.md` 的目录入口是否仍然正确？
- [ ] `SPEC.md` 第 5 节的目录约定是否仍然正确？
- [ ] `CLAUDE.md` 的架构 / 文档地图是否仍然正确？
- [ ] `PLAN.md` 的「进度记录」是否追加了结构变更说明？
- [ ] 是否有旧的路径 / 命令引用没有清理？
