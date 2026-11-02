# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 首要规则：文档同步

任何新增、修改、完成的需求、模块、状态（包括接口验证状态、脚本行为、配置项、目录约定），都必须在同一次改动中更新 `PLAN.md`：

- 更新「当前阶段」和计划表中的进度 / 状态
- 在「进度记录」末尾追加一条带日期的说明
- 若涉及接口，同步更新 `endpoints.json` 的 `status` 字段和 `02-URL与接口映射.md` 的状态标记

`PLAN.md` 是本项目进度的唯一记录，不要只在对话里说明完成情况。

## 项目定位

不开 tab、不渲染 DOM：用已登录 Chrome 的 Cookie + 页面 HTML 里的 `legalityToken`，直接 HTTP 调用生意参谋（sycm.taobao.com）的 JSON 接口。主力路线是 Python HTTP（`collect.py`），页面内 `fetch` 只是备选方案。

## DOM 定位

- 需要定位/操作 DOM 时，先调用项目级 `dom-locating` skill（`chrome电商数据获取脚本:dom-locating`），不要凭猜测写选择器。
- sycm 登录表单在跨域 iframe `#alibaba-login-box`（`havanalogin.taobao.com`）内；稳定选择器：`#fm-login-id`、`#fm-login-password`、`#login-form`、`button.fm-submit`。
- Chrome 密码管理器弹窗是浏览器 UI，不在 DOM/网络里；Skill 也覆盖不了，只能人工点击、Chrome 自动登录或 OS 级 UI 自动化。
- 使用 Skill 时若规则失效，必须按 Skill 的「失败闭环」更新规则和 `references/cases.md`，并报告改动。

## 常用命令

```bash
pip install websockets          # 唯一第三方依赖

# 前提：Chrome 以 --remote-debugging-port=9223 启动并已登录店铺
python list_browser_profiles.py                  # 列出 context / 账号 / Cookie
python list_browser_profiles.py --json
python list_browser_profiles.py --profile-path   # 额外开临时后台页读 chrome://version

python collect.py                                # 按 config.json 采集
python collect.py --account 察尔汗
python collect.py --item 731918476865 --date 2026-11-01
python collect.py --endpoint sale_overview,flow_top
python collect.py --output data_test --delay 2-5

python -m py_compile collect.py sycm_api.py list_browser_profiles.py   # 语法检查
```

项目没有测试套件。改动后用 `python -m py_compile ...` 和 `python collect.py --help` 做冒烟检查；条件允许时连接真实 Chrome 实跑一个接口。

需要启动店铺浏览器时，按工作区规则使用 `open-shop-browser` skill，不要手写 Chrome 启动命令。默认 user data dir 见 `list_browser_profiles.py` 的 `DEFAULT_USER_DATA`（`E:\VS Code\浏览器控制方案\chrome_profile_full`），profile 映射见 `05-分辨不同profile与账号.md`。

## 架构

三层，自下而上：

### 1. `list_browser_profiles.py` — CDP 基础层

- 连接 `http://localhost:9223/json/version` 的浏览器级 WebSocket，`Target.getTargets` 后过滤 `type=page`，按 `browserContextId` 分组
- 账号识别：优先 attach 页面执行 `JS_IDENTIFY`，读 `meta[name=microdata]` 的 `loginUserId` / `runAsShopTitle` 和正文店铺名
- Cookie：固定按 `https://sycm.taobao.com/` 用页面级 `Network.getCookies`；失败才回退 `Storage.getCookies`（实测部分 context 返回 0 个 Cookie）
- 同时作为 CLI 输出账号清单；`--profile-path` 会临时开后台页读 `chrome://version`

### 2. `sycm_api.py` — 纯 HTTP 层（不依赖浏览器）

- Cookie 头：只保留 taobao / tmall 域，跳过已过期项，sycm 域同名 Cookie 优先
- token：HTTP GET 页面 HTML（不开 tab），从 `<meta name="microdata">` 解析 `legalityToken`
- 参数：`parse_endpoint_params` 读取 `endpoints.json` 的 params（支持 `device=0` 形式的内联默认值）；`build_params` 依次合并公共参数（itemId / dateType / dateRange）→ 接口默认值 → config 覆盖，最后补 `token` 和 `_` 时间戳
- 错误映射：`code=0` 成功；`1100` → `NoPermissionError`（按跳过处理）；`1003` → `MissingParamError`；HTTP 401/403 或返回 HTML → `AuthError`；其余 → `ApiError`

### 3. `collect.py` — 编排层

- 启动时读 `config.json` + `endpoints.json`，连接一次 CDP
- `identify_account` 按 context 识别账号；`--account` 按 shop / tracknick / loginUserId 子串过滤；账号 key = `店铺名_loginUserId`（不是 browserContextId）
- 四层串行循环：账号 → 商品 → 日期 → 接口，每次请求后随机 `sleep(1~3s)`
- token 缓存键为 `(account.key, page_key)`，账号间绝不共享；遇到 `AuthError` 清缓存重取 token 并重试一次
- 保存 `data/{店铺}_{loginUserId}/{日期}/{商品ID}/{接口}.json`，每次运行的汇总写入 `data/_run_*.json`

## 配置与接口模板

**`endpoints.json` 是接口模板的唯一事实来源**，结构为 `pages[页面URL].endpoints[接口名] = {url, params, status}`。

- `params` 是字符串数组：`"itemId"` 表示参数名；`"device=0"` 表示参数带默认值
- `status` 取值：`已验证` / `代码确认` / `部分验证` / `未验证`；接口状态变化时同步更新 `02-URL与接口映射.md`
- `config.json` 的 `endpoints` 可写接口名，或 `{page, name, params}`；只写名字时由 `collect.py` 的 `PAGE_HINTS` 决定用哪个页面取 token
- 参数合并顺序：公共参数 → `endpoints.json` 默认值 → `config.json` 覆盖

## 关键约定

- 账号身份用 `店铺名 + loginUserId`；`browserContextId` 是会话级 UUID，重启会变，不能当稳定 ID
- Cookie、token、权限按账号隔离：不能拿 A 账号的 token 配 B 账号的 Cookie；同一商品在不同账号下可能返回 `1100`
- `_` 是防缓存毫秒时间戳，不是数据时间；`dateRange=start|end`（URL 编码为 `%7C`）；`dateType=today` 使用 realtime 版接口
- 正常取数不创建 tab；只有 `--profile-path` 和接口探测兜底会开后台页
- 找新接口的顺序：已开页面 `performance` 资源列表 → 下载 `op-cc/app.js`、`65.js` → grep `.json` → 从代码上下文确认参数。不要猜 `index.js`，不要扫 Chrome 缓存（详见 `03-快速定位接口.md`）
- Windows 下入口脚本统一 `reconfigure(encoding="utf-8", errors="replace")`，新增入口脚本沿用

## 文档地图

| 文件 | 作用 |
|---|---|
| `README.md` | 总览、核心结论、快速开始 |
| `01-无tab获取框架.md` | 多账号整体流程与账号隔离 |
| `02-URL与接口映射.md` | 页面 / 接口 / 参数 / 验证状态 |
| `03-快速定位接口.md` | bundle 定位方法与踩坑记录 |
| `04-代码模板.md` | 最小可运行模板 |
| `05-分辨不同profile与账号.md` | context / profile / 账号三层身份 |
| `PLAN.md` | 计划与进度（每次改动必须更新） |
