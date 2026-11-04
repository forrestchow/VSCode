# 电商数据采集 · Spec

> 本文件是项目规范：两步流程、关键技术、接口获取方法、目录与代码约定。
> 当前进度、平台展开和接口 → 代码映射见 [PLAN.md](PLAN.md)。
> 本文合并自原 `01-无tab获取框架.md`、`02-URL与接口映射.md`、`03-快速定位接口.md`、`04-代码模板.md`、`05-分辨不同profile与账号.md`。

## 1. 项目定位

目标：**不开 tab、不渲染 DOM**，用已登录 Chrome 的 Cookie + 平台鉴权 token，直接 HTTP 调用电商后台的 JSON 接口。

项目核心只有两步：

1. **Profile 与账号**：分辨不同用户名称的 Chrome profile，并让不同平台对应的账号处于登录态。
2. **数据采集**：登录账号后，按「平台 → 数据源」采集数据。

### 1.1 平台与数据源分类

| 平台 | 数据源 | 说明 | 状态 |
|---|---|---|---|
| 淘系 / 天猫 | 万相台推广数据 | `one.alimama.com` 关键词推广 | ✅ 已实跑 |
| 淘系 / 天猫 | 生意参谋平台数据 | `sycm.taobao.com` 商品 / 销售 / 流量 | 🟡 代码完成待实跑 |
| 淘系 / 天猫 | 卖家中心后台数据 | 千牛 / 卖家中心后台 | ⬜ 待写 |
| 拼多多 | 平台自有分类，待定 | 暂不讨论 | ⬜ 待写 |
| 抖音 | 平台自有分类，待定 | 暂不讨论 | ⬜ 待写 |
| ERP | ERP 数据 | 独立平台；具体 ERP 系统作为该平台下的数据源 | ⬜ 待写 |

第二步的技术核心是**无页面、无 tab**：不依赖页面渲染，只读 Cookie、页面 HTML 中的鉴权字段和 JSON 接口。

### 1.2 第一版非目标

- 不做数据库、Excel、定时任务、可视化前端。
- 不以 DOM 提取作为主线；DOM 只用于账号识别和接口定位。
- 不追求全量历史 / 全部分页；先跑通已验证接口的第一页。
- 不处理验证码、滑块、登录挑战；遇到时降速或停止。

## 2. 总体模型

```text
一个 Chrome 进程（一个 CDP 端口）
  ├─ context A → Chrome profile A → 平台账号 A → Cookie / 鉴权 A → 数据源接口 → data/...
  ├─ context B → Chrome profile B → 平台账号 B → Cookie / 鉴权 B → 数据源接口 → data/...
  └─ context C → Chrome profile C → 平台账号 C → Cookie / 鉴权 C → 数据源接口 → data/...
```

哪些共享、哪些按账号隔离：

| 内容 | 是否跨账号共享 | 说明 |
|---|---|---|
| 页面结构 / 路由 | ✅ 共享 | 同一套平台后台 |
| 接口路径 / 参数模板 | ✅ 共享 | 找到一次，写入该数据源的 `endpoints.json` |
| 解析逻辑 | ✅ 共享 | 同一套 JSON 字段 |
| Cookie | ❌ 按账号 | 每个 profile 独立登录态 |
| 鉴权 token | ❌ 按账号 / 页面 | 生意参谋 `legalityToken`、万相台 `csrfId` 都不能跨账号复用 |
| 页面上下文 | ❌ 按账号 | 每个 context 有自己的页面 |
| 权限 | ❌ 按账号 | 同一商品 ID 可能只有部分账号有权限 |
| 结果数据 | ❌ 按账号 | 必须带 `account` 标签并分仓保存 |

## 3. 第一步：Profile 与账号

### 3.1 三层身份，不要混在一起

| 层级 | 标识 | 从哪里读 | 例子 |
|---|---|---|---|
| CDP browser context | `browserContextId` | `Target.getTargets` | `D0373B94...`（UUID，会话级，不稳定） |
| Chrome profile | profile 目录 + 显示名 | `Local State` → `profile.info_cache` | `Default` / 察颜；`Profile 2` / 察尔汗 |
| 网站账号 | `loginUserId` / `tracknick` / 店铺名 | 页面 DOM / `meta[microdata]` / Cookie | `2220801699546` / 察颜旗舰店 |

关键点：

- `browserContextId` 不是 Chrome profile ID，只是 CDP 用来分组页面的 UUID。
- Chrome profile 显示名不是网站账号名。例如 profile 叫「察颜」，网站账号叫「察颜旗舰店」。
- 稳定可复用的身份是：`profile 目录 + 显示名 + loginUserId`。
- 落盘目录用 `店铺名_loginUserId`，不用 `browserContextId`。

当前本机实测映射（2026-11-02，环境变化后用 `python -m core.browser_profiles --profile-path` 重新确认）：

| profile 目录 | 显示名 | 已知网站账号 |
|---|---|---|
| `Default` | 察颜 | 察颜旗舰店 |
| `Profile 2` | 察尔汗 | 察尔汗壹品盐专卖店 |
| `Profile 3` | 收汁酱排骨 | — |
| `Profile 4` | 察颜专卖店 | — |
| `Profile 5` | 淘工厂 | 格尔木盐化(集团)有限责任公司 |

### 3.2 识别流程

```text
连接浏览器级 CDP WebSocket（/json/version 的 webSocketDebuggerUrl）
  → Target.getTargets
  → 过滤 type="page"
  → 按 browserContextId 分组
  → 每个 context 选一个页面，Runtime.evaluate 读取 meta[microdata] / 正文
  → 页面级 Network.getCookies（Storage.getCookies 作兜底）
  → 可选：chrome://version → Profile Path → Local State → 显示名
```

账号识别依据，按可靠性排序：

1. 页面 DOM / `meta[name=microdata]` 的 `loginUserId` / `runAsUserId` / `runAsShopTitle`。
2. 页面正文的店铺名 / 公司名。
3. 页面级 `Network.getCookies` 的 `tracknick` / `unb`。

用于识别账号的最小 JS：

```js
(() => {
  const metaEl = document.querySelector('meta[name=microdata]');
  const meta = metaEl ? metaEl.content : '';
  const get = (name) => {
    const m = meta.match(new RegExp('(?:^|;)' + name + '=([^;]*)'));
    return m ? m[1] : '';
  };
  return JSON.stringify({
    title: document.title,
    url: location.href,
    loginUserId: get('loginUserId'),
    mainUserId: get('mainUserId'),
    runAsUserId: get('runAsUserId'),
    runAsShopTitle: get('runAsShopTitle'),
    runAsShopId: get('runAsShopId'),
    body: (document.body && document.body.innerText || '').slice(0, 1200)
  });
})()
```

### 3.3 Cookie 读取

`Storage.getCookies({browserContextId})` 对部分 context 会返回 0 个 Cookie。多账号场景优先用页面级 `Network.getCookies`：

```text
Target.attachToTarget({targetId, flatten:true})
  → Network.enable
  → Network.getCookies({urls:["https://sycm.taobao.com/"]})
```

| 方式 | 特点 | 适用 |
|---|---|---|
| 页面级 `Network.getCookies` | 需要先 attach 页面；结果可靠 | 多 context / 多账号（生意参谋） |
| 浏览器级 `Storage.getCookies` | 不 attach 页面；部分 context 可能返回 0 | 单 profile（万相台） |

Cookie 头规则：

- 只保留目标平台相关域（如 `taobao.com` / `tmall.com` / `alimama.com`）。
- 跳过已过期 Cookie。
- 同名 Cookie 优先目标子域（如 `sycm.taobao.com` 优先于 `.taobao.com`）。
- `tracknick` 可能是 URL 编码或 `\uXXXX` 形式，需要解码。

### 3.4 多平台登录态

当前实现只**读取**已登录状态，不保存密码：

- 淘系：对应的店铺 Chrome 保持登录；需要启动浏览器时使用项目内的 `open-shop-browser` skill（`.claude/skills/open-shop-browser/`），不手写 Chrome 启动命令。
- 淘系登录页：在跨域 iframe `#alibaba-login-box`（`havanalogin.taobao.com`）内；稳定选择器 `#fm-login-id`、`#fm-login-password`、`#login-form`、`button.fm-submit`，详见项目级 `dom-locating` skill。
- Chrome 密码管理器弹窗是浏览器 UI，不在 DOM / 网络里；只能人工点击、Chrome 自动登录或 OS 级 UI 自动化。
- 拼多多 / 抖音 / ERP：账号识别与登录方式待写。

登录态是否有效的判断：

| 现象 | 含义 | 处理 |
|---|---|---|
| HTTP 401 / 403 | 登录态失效，或万相台 csrfId 过期 | 重新读 Cookie / 重新 `checkAccess` |
| 接口返回 HTML 登录页 | Cookie 过期 | 在对应 Chrome profile 重新登录 |
| `checkAccess` 无 `csrfId` | 未登录万相台 | 重新登录万相台 |
| 生意参谋 `code=1100` | 当前账号无该商品 / 接口权限 | 按跳过处理，不是登录失效 |

### 3.5 账号隔离规则

- 不能用账号 A 的 Cookie / token 取账号 B 的数据。
- 不能假设同一商品 ID 在所有账号下都有数据。
- 每个账号的返回结果单独校验 `code`。
- 每个账号串行取数，账号之间加随机间隔。

真实例子：同一商品 `731918476865`，察尔汗账号调用 `/cc/item/sale/overview.json` 返回 `code:0`；察颜账号调用同一接口返回 `code:1100, message:"用户无权限"`。所以不能拿 A 账号的 Cookie 取 B 账号的数据，也不能把 `1100` 的数据混进成功数据。

### 3.6 代码入口

```bash
python -m core.browser_profiles
python -m core.browser_profiles --json
python -m core.browser_profiles --profile-path   # 额外开临时后台页读 chrome://version
```

默认不创建任何 tab，只读取现有页面。默认端口 `9223`，默认 user data dir 见 `core/browser_profiles.py` 的 `DEFAULT_USER_DATA`。

## 4. 第二步：数据采集

### 4.1 无 tab 取数模型

```text
已登录的 Chrome（该账号的 context）
  │
  ├─ 读 Cookie（CDP，不开 tab、不导航、不渲染）
  │
  ├─ 获取鉴权 token
  │     ├─ 生意参谋：HTTP GET 页面 HTML → meta[microdata] → legalityToken
  │     └─ 万相台：POST /member/checkAccess.json → csrfId / loginPointId
  │
  └─ 直接 HTTP 调用 JSON 接口
        Cookie + User-Agent + Referer + token + 业务参数
              │
              └─ 解析 JSON → data/{平台}/{数据源}/{账号}/{日期}/...
```

整个过程不需要页面 JS 执行，也不需要 DOM 渲染。

### 4.2 三种取数路线

| 路线 | 开 tab | 执行页面 JS | 多账号支持 | 适用 |
|---|---|---|---|---|
| Python HTTP + CDP Cookie | ❌ | ❌ | ✅ 推荐 | 批量、离线、需要自己控制请求 |
| 页面上下文 `fetch` | ❌ | ✅（仅 fetch） | ✅ 最稳 | 已有该账号页面，跨域 / 签名复杂时 |
| 后台 tab 抓包 | ✅ 后台 | ✅ | ✅ 但重 | 首次发现接口、动态签名 |

主路线是 Python HTTP；页面内 `fetch` 是备选；后台 tab 只用于**发现接口**，不用于日常取数。

页面上下文 `fetch` 示例：

```js
(async () => {
  const meta = document.querySelector('meta[name=microdata]')?.content || '';
  const token = (meta.match(/(?:^|;)legalityToken=([^;]*)/) || [])[1] || '';
  const params = new URLSearchParams({
    itemId: '731918476865',
    dateType: 'day',
    dateRange: '2026-11-01|2026-11-01',
    device: '0',
    _: String(Date.now()),
    token,
  });
  const r = await fetch('/cc/item/sale/overview.json?' + params.toString(), {
    credentials: 'include',
  });
  return await r.text();
})()
```

优点：自动带该账号 Cookie、同源无 CORS、token 从当前页面解析不会串账号。

### 4.3 鉴权类型

| 类型 | 平台 | 获取方式 | 失效处理 |
|---|---|---|---|
| 页面 token | 生意参谋 | HTTP GET 页面 HTML，解析 `meta[microdata]` 的 `legalityToken` | 401/403 或返回 HTML → 重新 GET HTML |
| 接口换 token | 万相台 | `POST /member/checkAccess.json` → `data.accessInfo.csrfId` + `data.loginPointId` | HTTP 403 → 重新 `checkAccess` 重试一次 |
| Cookie-only | 待写 | 平台只校验 Cookie | 重新读 Cookie / 重新登录 |

规则：

- `token` / `csrfId` 按账号 / 页面缓存，不能跨账号复用。
- 生意参谋 token 过期后，重新 GET 该账号的页面 HTML。
- 万相台 `csrfId` 不在 Cookie、localStorage 或页面 HTML 里，只能由 `checkAccess` 获取；该接口本身不校验 csrf，所以整条链路不需要打开页面。

### 4.4 请求头与参数

通用请求头：

```http
Cookie: <该账号的 Cookie>
User-Agent: <Chrome UA>
Referer: <该数据源页面 URL>
Accept: application/json, text/plain, */*
Origin: <平台 origin>
x-requested-with: XMLHttpRequest
```

生意参谋参数：

```text
itemId / dateType / dateRange / device / belong / order / orderBy / page / pageSize / indexCode
token / _
```

万相台参数：

```text
query: csrfId / bizCode
body: bizCode / startTime / endTime / sourceList / queryFieldIn / splitType / allDay / ...
```

### 4.5 接口分类与模板

**每个数据源一个 `endpoints.json`，与自己的代码同目录。** 不设全局接口大文件：

```text
platforms/taobao/sycm/endpoints.json       # 生意参谋
platforms/taobao/alimama/endpoints.json    # 万相台
```

分类层级：

```text
平台 → 数据源 → 页面 / 路由 → 接口名 → {url, method, params/body, status, note}
```

规则：

- `endpoints.json` 是接口模板的唯一事实来源；Markdown 只做分类和映射摘要，不重复抄全部参数。
- `status` 取值：`已验证` / `代码确认` / `部分验证` / `未验证`。
- 接口状态变化时，同一次改动里更新 `endpoints.json` 和 `PLAN.md`。
- 接口路径和参数模板跨账号共享；Cookie、token、权限按账号隔离。

接口 → 代码的两种映射方式：

- **数据驱动（生意参谋）**：接口名是 `endpoints.json` 的 key；`collect.py` 的 `resolve_endpoint()` 按 key 找到页面和参数模板，`api.py` 提供通用 `request_json()`。新增接口通常只改 `endpoints.json` 和 `config.json`。
- **函数驱动（万相台）**：每个接口在 `api.py` 里有一个函数（`check_access` / `report_query` / `campaign_find_page`），因为请求体结构复杂；`endpoints.json` 记录契约和状态。
- **报表页映射（万相台）**：`endpoints.json` 的 `report_pages` key → `api.report_list(<key>)`；`rptType` / `queryDomains` / `extra` 由 `REPORT_LIST_SPECS` 定义。

### 4.5.1 URL → 接口 → 代码 查询流程

拿到一个页面 URL 时，不要先抓包，先查索引：

1. 归一化：去掉域名，保留 path / hash 路由 + 关键参数（`rptType`、`queryDomains`、`activeKey`、`bizCode`、`campaignId`、`adgroupId`）。
2. 在 `PLAN.md` 的「接口分类总表」的「页面 / 路由」列匹配。
3. 命中：按「代码映射」调用；参数以该数据源 `endpoints.json` 为准。
4. 未命中：按 4.6 定位接口 → 写代码 → 更新 `endpoints.json`、`PLAN.md`、`STRUCTURE.md`。

注意：万相台报表页共用 `POST /report/query.json`，仅靠路由无法区分，必须把 `rptType` + `queryDomains` 作为路由键的一部分；同一个接口可以服务多个路由。

### 4.6 如何获取接口

优先级：**静态分析 → 抓包兜底**。

#### 首选：performance + bundle grep

1. 在**已打开的同域页面**读已加载的 JS 资源（不新开 tab）：

```js
performance.getEntriesByType('resource')
  .map(e => e.name)
  .filter(n => /\.js(\?|$)/.test(n))
```

2. 从 HTML 的 `meta[microdata]` 确认 bundle 版本：

| 路由前缀 | app bundle | 版本字段 |
|---|---|---|
| `/cc/*` | `op-cc` | `ctxCcVersion` |
| `/flow/*` | `ops-flow` | `ctxSFlowVersion` |
| `/portal/*` | `op-eportal` | `ctxCustomVersion` |
| `/mc/*` | `op-mc` | `ctxMcVersion` |
| `/qos/*` | `op-service` | `ctxServiceVersion` |

3. 下载并 grep：

```bash
curl -s https://g.alicdn.com/dt/op-cc/2.4.238/65.js -o 65.js
grep -oE '"/[^"]+\.json[^"]*"' 65.js | sort -u
```

Python 版本：

```python
import re, urllib.request

url = "https://g.alicdn.com/dt/op-cc/2.4.238/65.js"
text = urllib.request.urlopen(url, timeout=60).read().decode("utf-8", "replace")
paths = sorted(set(re.findall(r'["\'](/[^"\']+?\.json[^"\']*)["\']', text)))
for p in paths:
    print(p)
```

4. 从代码上下文提取参数（打印接口字符串前后约 900 字符）：

```python
idx = text.find("/cc/item/flow/top/v4.json")
print(text[max(0, idx-900):idx+900])
```

通常能看到固定参数、页面状态参数、行数据参数和枚举值。

5. 把接口和参数模板写入对应数据源的 `endpoints.json`。

#### 备选：后台 tab 抓包

静态分析找不到，或接口有动态签名 / 加密参数时：

```text
Target.createTarget({url:"about:blank", background:true})
  → Target.attachToTarget(flatten=true)
  → Network.enable
  → Page.navigate(目标 URL)
  → 收集 XHR / Fetch
  → 等待页面数据加载完
  → Target.closeTarget
```

注意：

- `background:true` 不抢焦点，但仍是真实页面加载。
- 后台 tab 可能被 Chrome 节流；必要时加启动参数：
  `--disable-background-timer-throttling`
  `--disable-backgrounding-occluded-windows`
  `--disable-renderer-backgrounding`
- 抓包的目的不是取数，而是获得接口契约；拿到后写入 `endpoints.json`，后续不再抓。

#### 判断接口属于哪个页面 / tab

看代码里的「更多」链接：

| 接口 | 「更多」链接 | 归属 |
|---|---|---|
| `/cc/item/flow/top/v4.json` | `activeKey=flow` | 流量 |
| `/cc/item/searchword/top/v3.json` | `activeKey=flow` | 流量 |
| `/cc/item/sku/top.json` | `activeKey=sale` | 销售 |

规律：

- 「更多」链接指向哪个 `activeKey`，这张卡就属于哪个 tab 的数据范围。
- Top10 / Top5 通常是摘要卡；tab 内的完整表格用另一个接口。
- 不要因为接口在同一个 JS bundle 里，就认为它属于同一个 tab。

### 4.7 参数与时间

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
| `token` | HTML `meta[microdata]` 的 `legalityToken` |
| `_` | 毫秒时间戳，防缓存，**不是数据时间** |

时间规则：

- 单日：`dateRange=2026-11-01|2026-11-01`。
- 区间：`start|end` 不同；接口可能返回聚合值，也可能返回逐日序列。
- 趋势接口：`dateRange` 通常只决定「结束日」，响应返回往前 30 天。
- 实时接口：`dateType=today`，并使用 `realtime` 版本的 URL。
- 非时间接口：`getItemCrowds.json`、`skuAttr.json`、`stock/isOff.json`、`supersku/verify.json` 不需要 `dateRange`。
- 页面 URL 里的 `dateType` / `dateRange` 是前端路由状态；调接口时要把它传给 API。

### 4.8 返回码与异常

生意参谋：

| code / 现象 | 含义 | 处理 |
|---:|---|---|
| `0` | 成功 | 保存数据 |
| `1003` | 缺少参数 | 按 `message` 补参数（`device` / `belong` / `order` / `pageId`） |
| `1000` | 未知异常 | 接口路径 / 参数不对 |
| `1100` | 用户无权限 | 当前账号无权限，按跳过处理 |
| HTTP 401 / 403 | 登录态失效 | 重新读 Cookie / token |
| 返回 HTML 登录页 | Cookie 过期 | 重新登录 |

万相台：

| 现象 | 含义 | 处理 |
|---|---|---|
| HTTP 403 | csrfId 缺失或过期 | 重新 `checkAccess` 拿新 csrfId；脚本自动重试一次 |
| `checkAccess` 无 `csrfId` | Cookie 过期 / 未登录万相台 | 在对应 Chrome profile 重新登录 |
| 返回 HTML | 登录态失效 | 同上 |
| `info.ok === false` | 业务错误 | 按 `errorCode` / `message` 处理 |

### 4.9 保存与合并

目录约定：

```text
data/
  taobao/
    sycm/{店铺}_{loginUserId}/{日期}/{商品ID}/{接口}.json
    alimama/{店铺}_{memberId}/{日期}/{overview,hourly,campaigns}.json
  pdd/        # 待写
  douyin/     # 待写
  erp/<system>/  # 待写；每个 ERP 系统一个子目录
```

每条数据带账号信息：

```json
{
  "account": {
    "shop": "察尔汗壹品盐专卖店",
    "login_user_id": "2216332095488",
    "tracknick": "察尔汗壹品盐专卖店"
  },
  "date": "2026-11-01",
  "endpoint": "sale_overview",
  "request": {},
  "response": {}
}
```

合并规则：

- 每个账号保留原始 JSON。
- 合并时增加 `account` / `shop` / `loginUserId` 列。
- 不要按商品 ID 去重：同一商品 ID 在不同账号下权限和数据可能不同。
- 先按账号校验 `code`，再合并；`1100` 的数据不要混进成功数据。
- 每次运行的汇总写入该数据源输出目录下的 `_run_*.json`（例如 `data/taobao/sycm/_run_*.json`）。

### 4.10 限速与边界

- 串行请求，每个请求之间随机 `sleep(1~3)` 秒。
- 不要并发几十个请求。
- 遇到 401 / 403 / 429 / 验证码立即降速或停止。
- 只操作自己账号有权查看的数据。
- 前端发版后接口可能变化，用 `performance` + bundle grep 重新定位。

## 5. 代码组织约定

完整目录树、每个文件夹 / 文件的作用、新增文件放置规则见 [STRUCTURE.md](STRUCTURE.md)。本节只写命名与运行约定。

命名与运行规则：

- 目录名用英文：`platforms/<platform>/<source>/`；平台内的数据源名尽量与后台名一致（`sycm`、`alimama`、`seller_center`）。
- 每个已实现的数据源必须有自己的 `collect.py`、`api.py`、`endpoints.json`、`config.json`；待写数据源先用 `README.md` 占位。
- 入口命令统一从项目根目录执行：

```bash
python -m platforms.taobao.sycm.collect
python -m platforms.taobao.alimama.collect
```

也支持直接运行文件；入口脚本内部会把项目根加入 `sys.path`。

- 共用能力放 `core/`，不要复制到各数据源。
- 配置文件里的相对路径以项目根为基准。
- Windows 下入口脚本统一 `reconfigure(encoding="utf-8", errors="replace")`。

### 5.1 新增一个平台 / 数据源的落地清单

1. 建目录 `platforms/<platform>/<source>/`，加 `__init__.py`。
2. 确认该平台的 profile / 账号识别方式，必要时扩展 `core/browser_profiles.py`。
3. 确认鉴权类型：页面 token / 接口换 token / Cookie-only。
4. 按 4.6 定位接口，写入本数据源的 `endpoints.json`。
5. 写 `api.py`（HTTP 层）和 `collect.py`（编排层），复用 `core/`。
6. 写 `config.json`，输出目录设为 `data/<platform>/<source>`。
7. 更新 `PLAN.md` 的平台矩阵、接口分类和代码映射。
8. 更新 `STRUCTURE.md` 的项目树和角色表。
9. 更新 `README.md`、`CLAUDE.md` 里的命令和目录说明。

### 5.2 文档同步的机械检查

`.claude/hooks/check_docs.py` 由项目的 `.claude/settings.json` 调用：

- `PostToolUse`（`Edit|Write|MultiEdit`）：记录本次会话编辑过的文件。
- `Stop`：
  - 改了 `endpoints.json` → 必须有 `PLAN.md`
  - 改了 `api.py` / `collect.py` → 必须有 `SPEC.md`
  - `platforms/` 下新增 / 删除 / 重命名文件 → 必须有 `STRUCTURE.md`
- 缺失时 Stop 会 block 一次；第二次 `stop_hook_active` 放行并提示，避免死循环。

Hook 只检查文件路径和 git status，不判断「底层逻辑是否真的变了」；语义判断仍由模型完成。

## 6. 平台规范

### 6.1 淘系 / 天猫

| 数据源 | 取数方式 | 鉴权 | 代码目录 | 状态 |
|---|---|---|---|---|
| 万相台推广 | `POST` JSON 接口 | `checkAccess` → `csrfId` | `platforms/taobao/alimama/` | ✅ 已实跑（含报表页） |
| 生意参谋 | `GET` JSON 接口 | 页面 HTML → `legalityToken` | `platforms/taobao/sycm/` | 🟡 代码完成待实跑 |
| 卖家中心 | 待定 | 待定 | `platforms/taobao/seller_center/` | ⬜ 待写 |

具体接口分类、验证状态和代码映射见 `PLAN.md`。

### 6.2 拼多多（待写）

- 数据源分类待定。
- 账号识别、登录态、鉴权方式、接口发现方法均待补。
- 目录占位：`platforms/pdd/`。

### 6.3 抖音（待写）

- 数据源分类待定。
- 账号识别、登录态、鉴权方式、接口发现方法均待补。
- 目录占位：`platforms/douyin/`。

### 6.4 ERP（待写）

- ERP 按平台管理，具体 ERP 系统作为该平台下的数据源。
- 目录占位：`platforms/erp/`；每个 ERP 系统使用 `platforms/erp/<system>/`。
- 待确认：具体 ERP 系统、账号 / 鉴权、数据分类（订单 / 库存 / 采购 / 财务等）、接口或导出方式。

## 附录 A：最小代码模板

```python
# -*- coding: utf-8 -*-
"""无 tab 获取生意参谋数据的最小模板。"""
import asyncio
import json
import re
import time
import urllib.parse
import urllib.request

import websockets

PORT = 9223
BASE = "https://sycm.taobao.com"
ITEM_ID = "731918476865"
DATE_RANGE = "2026-11-01|2026-11-01"


def get_browser_info() -> dict:
    with urllib.request.urlopen(f"http://localhost:{PORT}/json/version", timeout=10) as r:
        return json.loads(r.read().decode())


async def read_cookies() -> list[dict]:
    info = get_browser_info()
    async with websockets.connect(info["webSocketDebuggerUrl"], open_timeout=10) as ws:
        await ws.send(json.dumps({"id": 1, "method": "Storage.getCookies"}))
        while True:
            msg = json.loads(await asyncio.wait_for(ws.recv(), 10))
            if msg.get("id") == 1:
                return msg["result"]["cookies"]


def build_cookie_header(cookies: list[dict]) -> str:
    now = time.time()
    seen = {}
    for c in cookies:
        domain = c.get("domain", "")
        if "taobao.com" not in domain and "tmall.com" not in domain:
            continue
        expires = c.get("expires", -1)
        if isinstance(expires, (int, float)) and 0 < expires < now:
            continue
        name, value = c.get("name"), c.get("value")
        if not name:
            continue
        score = 2 if domain == "sycm.taobao.com" else 1
        if name not in seen or score > seen[name][0]:
            seen[name] = (score, value)
    return "; ".join(f"{k}={v}" for k, (_, v) in seen.items())


def parse_token(html: str) -> str:
    m = re.search(r'<meta name="microdata" content="([^"]*)"', html)
    if not m:
        raise RuntimeError("找不到 meta[microdata]，可能被重定向到登录页")
    mm = re.search(r"(?:^|;)legalityToken=([^;]*)", m.group(1))
    if not mm:
        raise RuntimeError("microdata 里没有 legalityToken")
    return mm.group(1)


def get_html(url: str, headers: dict) -> str:
    req = urllib.request.Request(url, headers={**headers, "Accept": "text/html"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", "replace")


def get_json(url: str, headers: dict) -> dict:
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as r:
        obj = json.loads(r.read().decode("utf-8", "replace"))
    if obj.get("code") != 0:
        raise RuntimeError(f"接口返回 code={obj.get('code')}, message={obj.get('message')}")
    return obj


async def demo_flow():
    cookies = await read_cookies()
    cookie = build_cookie_header(cookies)
    info = get_browser_info()
    headers = {
        "Cookie": cookie,
        "User-Agent": info.get("User-Agent", "Mozilla/5.0"),
        "Referer": f"{BASE}/cc/item_archives?activeKey=flow&itemId={ITEM_ID}",
        "Accept": "application/json, text/plain, */*",
        "Origin": BASE,
        "x-requested-with": "XMLHttpRequest",
    }

    page_url = (
        f"{BASE}/cc/item_archives?activeKey=flow&itemId={ITEM_ID}"
        f"&dateType=day&dateRange={urllib.parse.quote(DATE_RANGE)}"
    )
    token = parse_token(get_html(page_url, headers))
    params = {
        "itemId": ITEM_ID,
        "page": 1,
        "pageSize": 10,
        "dateType": "day",
        "dateRange": DATE_RANGE,
        "_": int(time.time() * 1000),
        "token": token,
    }
    url = f"{BASE}/cc/item/flow/top/v4.json?" + urllib.parse.urlencode(params)
    data = get_json(url, headers)
    print("rows:", len(data.get("data", [])))


if __name__ == "__main__":
    asyncio.run(demo_flow())
```

注意事项：

1. 不要硬编码 token；每次从 HTML 的 `meta[microdata]` 解析，失效时重新 GET。
2. Cookie 从浏览器读；`Storage.getCookies` 是浏览器级命令，不创建 tab。
3. 串行请求，每个请求之间 `sleep(1~3)` 秒。
4. `code=1003` 按 `message` 补参数。
5. 返回 HTML 登录页或 401/403：重新登录、重新读 Cookie、重新取 token。
6. 验证过的接口写进对应数据源的 `endpoints.json`。

## 附录 B：接口定位踩坑

| 错误做法 | 结果 |
|---|---|
| 只搜 `sycm-micro-v2` | 那里只有壳和路由，没有业务接口 |
| 猜 `sycm-cc/2.4.238/index.js` | 404；实际是 `op-cc/2.4.238/app.js` |
| 猜 `op-cc/2.4.238/index.js` | 404；实际文件是 `app.js` / `vendors.js` / `65.js` |
| 扫 280MB Chrome 缓存找 URL | 缓存索引不是明文，基本找不到 |
| 枚举 151 个 micro-v2 chunk | 只有 11 个存在，且没有业务接口 |
| 先开后台 tab | 多一次真实页面加载；应该先读 `performance` |

正确顺序：

```text
1. 已有同域页面？
   ├─ 是 → performance 资源列表 → 下载 app.js / 65.js → grep 接口
   └─ 否 → 先读 HTML + meta token，再决定是否需要后台 tab

2. 接口字符串找到了？
   ├─ 是 → 读上下文确定参数 → 直接 GET
   └─ 否 → 后台 tab 抓一次 → 保存模板

3. 参数报 1003？
   → 按 message 补 device / belong / order / pageId 等
```

检查清单：

- [ ] 是否先读了 `performance` 资源列表？
- [ ] 是否确认了 `ctxCcVersion` / `ctxSFlowVersion`？
- [ ] 是否下载的是 `app.js` / `65.js`，而不是猜 `index.js`？
- [ ] 是否从代码上下文确认了参数，而不是靠猜？
- [ ] 是否从 HTML meta 解析了 `legalityToken`？
- [ ] 是否把接口模板保存到了对应数据源的 `endpoints.json`？
- [ ] 是否避免了不必要的后台 tab / 缓存扫描 / chunk 枚举？

## 附录 C：术语

| 术语 | 含义 |
|---|---|
| profile / Chrome profile | Chrome 的用户资料目录，一个 profile 一套登录态 |
| browser context | CDP 的页面分组，`browserContextId` 是会话级 UUID |
| 数据源 | 平台内的一个后台，例如万相台、生意参谋、卖家中心 |
| 无 tab | 不创建新标签页、不导航、不渲染页面 |
| `legalityToken` | 生意参谋页面 `meta[microdata]` 里的接口鉴权字段 |
| `csrfId` | 万相台 `checkAccess` 返回的会话级鉴权字段 |
