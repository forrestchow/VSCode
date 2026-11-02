# 01 · 无 tab 获取框架（多账号版）

这个框架默认就是**多账号**的：一个 Chrome 进程里可以有多个 browser context，每个 context 对应一个店铺账号；接口模板共享，Cookie、token、页面上下文和权限按账号隔离，结果按账号分仓。

## 核心模型

```text
一个 Chrome 进程（一个 CDP 端口）
  ├─ context A → 账号 A → Cookie A / token A / 权限 A → data/账号A/
  ├─ context B → 账号 B → Cookie B / token B / 权限 B → data/账号B/
  └─ context C → 账号 C → Cookie C / token C / 权限 C → data/账号C/

共享：页面结构、接口路径、参数模板、解析逻辑
按账号独立：Cookie、token、页面上下文、权限、数据
```

哪些东西共享，哪些按账号独立：

| 内容 | 是否跨账号共享 | 说明 |
|---|---|---|
| 页面 URL / tab 结构 | ✅ 共享 | 同一套生意参谋页面 |
| 接口路径 / 参数模板 | ✅ 共享 | 找到一次即可，存进 `endpoints.json` |
| 解析逻辑 | ✅ 共享 | 同一套 JSON 字段 |
| Cookie | ❌ 按账号 | 每个 profile 独立登录态 |
| `legalityToken` | ❌ 按账号/页面 | 从各自页面的 `meta[microdata]` 解析 |
| 页面上下文 | ❌ 按账号 | 每个 context 有自己的页面 |
| 权限 | ❌ 按账号 | 同一商品 ID 可能只有部分账号有权限 |
| 结果数据 | ❌ 按账号 | 必须打 `account` 标签 |

## 整体架构

### 1. 先识别不同 profile / 账号

```text
一个 Chrome 进程（一个 CDP 端口）
  │
  ├─ Target.getTargets
  │     └─ 按 browserContextId 分组页面
  │           ├─ context A → 页面 meta[microdata] / 正文 → 账号 A
  │           ├─ context B → 页面 meta[microdata] / 正文 → 账号 B
  │           └─ context C → 页面 meta[microdata] / 正文 → 账号 C
  │
  └─ account key = profile_dir + loginUserId
```

账号识别依据：

- `meta[name=microdata]` 的 `loginUserId` / `runAsUserId`
- 页面正文的店铺名 / 公司名
- 页面级 `Network.getCookies` 的 `tracknick` / `unb`

### 2. 每个账号的取数流程

```text
已登录的 Chrome（该账号的 context）
  │
  ├─ 页面级 Network.getCookies
  │     └─ 只读 Cookie，不创建 tab、不导航、不渲染
  │
  ├─ HTTP GET 目标页面 HTML
  │     └─ <meta name="microdata"> → legalityToken / ctxCcVersion / ...
  │
  └─ HTTP GET JSON 接口
        Cookie + User-Agent + Referer + token + 业务参数
              │
              └─ 解析 JSON → data/{账号}_{loginUserId}/{日期}/{接口}.json
```

整个过程不需要页面 JS 执行，也不需要 DOM 渲染。

> 多账号时，第 1 步对每个 context 执行一次；第 2 步对每个账号分别执行。
> 如果走“页面上下文 fetch”，第 2 步中的 Cookie/HTML 可以省略，直接在该账号页面里 fetch。

## 第 1 步：确定账号和页面上下文

多账号的第一步不是拿 Cookie，而是**先知道当前有哪些账号、每个账号的页面在哪个 context**。

```text
连接浏览器级 WebSocket（/json/version 的 webSocketDebuggerUrl）
  → Target.getTargets
  → 过滤 type="page"
  → 按 browserContextId 分组
```

对每个 context 选一个页面，读取：

```js
const meta = document.querySelector('meta[name=microdata]')?.content || '';
// loginUserId / runAsUserId / runAsShopTitle
document.body.innerText.slice(0, 500);  // 店铺名 / 公司名
```

账号 key 用：

```text
profile_dir + loginUserId
```

不要用：

```text
browserContextId   ← 会话级 UUID，重启会变
```

单账号时这一步仍然只执行一次；多账号时循环执行。

> 详细的 context ↔ profile 映射见 [05-分辨不同profile与账号.md](05-分辨不同profile与账号.md)。

## 第 2 步：按账号拿 Cookie

多账号场景下，**不要用 `Storage.getCookies({browserContextId})` 作为主方案**。本机实测它对部分 context 返回 0 个 Cookie。

推荐用页面级命令：

```text
Target.attachToTarget({targetId, flatten:true})
  → Network.enable
  → Network.getCookies({urls:["https://sycm.taobao.com/"]})
```

实测：

| context | Storage.getCookies | Network.getCookies | tracknick | unb |
|---|---:|---:|---|---|
| `CA0487...` | 0 | **32** | `scm54009219` | `2223101531825` |
| `76DF1E...` | 0 | **41** | 察尔汗壹品盐专卖店 | `2216332095488` |
| `D0373B...` | 156 | **43** | 察颜旗舰店 | `2220801699546` |

如果走“页面上下文 fetch”路线，其实**不需要手动提取 Cookie**：

```js
fetch(url, { credentials: 'include' })
```

浏览器会自动带当前账号的 Cookie。多账号最稳的路径就是这条。

## 第 3 步：按账号拿 Token

`token` 在页面 HTML 的 `meta[microdata]` 里，**每个账号/页面各自解析，不能跨账号复用**。

```http
GET https://sycm.taobao.com/cc/item_archives?activeKey=flow&itemId=...&dateType=day&dateRange=...
Cookie: <该账号的 Cookie>
User-Agent: ...
```

```python
import re

m = re.search(r'<meta name="microdata" content="([^"]*)"', html)
token = re.search(r'(?:^|;)legalityToken=([^;]*)', m.group(1)).group(1)
```

如果走页面上下文 fetch，则直接在页面里解析：

```js
const meta = document.querySelector('meta[name=microdata]')?.content || '';
const token = (meta.match(/(?:^|;)legalityToken=([^;]*)/) || [])[1] || '';
```

规则：

- 每个账号的 token 可能不同。
- token 过期后，重新 GET 该账号的页面 HTML。
- 不要把账号 A 的 token 用到账号 B 的 cookie 上。

## 第 4 步：找接口（跨账号共享）

接口路径和参数模板是**跨账号共享**的，只需要找一次，不要每个账号都重新逆向。

最快路径：在任意一个已打开的生意参谋页面读 `performance`：

```js
performance.getEntriesByType('resource')
  .map(e => e.name)
  .filter(n => /\.js(\?|$)/.test(n))
```

会看到：

```text
https://g.alicdn.com/dt/op-cc/2.4.238/app.js
https://g.alicdn.com/dt/op-cc/2.4.238/65.js
https://g.alicdn.com/dt/ops-flow/2.0.185/app.js
```

下载并 grep：

```bash
grep -oE '"/[^"]+\.json[^"]*"' 65.js | sort -u
```

把接口和参数写进共享的 `endpoints.json`，后续所有账号复用同一份模板。

### 抓包是备选方案

获得接口的优先级：

1. **首选：静态分析**——读 `performance` → 下载 bundle → grep `.json`；
2. **备选：抓包**——静态分析找不到，或接口有动态签名/加密参数时，才开后台 tab 用 CDP `Network` 捕获真实请求。

抓包的目的不是取数，而是**获得接口契约**：URL、方法、参数、请求头、返回结构，以及触发它的是哪个 tab / 操作。拿到后写进 `endpoints.json`，后续所有账号直接重放，不再抓包。

> 详细定位方法见 [03-快速定位接口.md](03-快速定位接口.md)；抓包的具体步骤见其中的「兜底路径：后台 tab 抓包」。

## 第 5 步：按账号调接口

### 路线 A：页面上下文 fetch（多账号最推荐）

在目标账号的生意参谋页面里执行：

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

优点：

- 自动带该账号 Cookie。
- 不需要手动拼 Cookie 头。
- token 从该页面解析，不会串账号。
- 同源，无 CORS 问题。

### 路线 B：Python HTTP（适合批量/离线）

用该账号的 Cookie + token 直接 GET：

```http
Cookie: <账号 A 的 Cookie>
User-Agent: <Chrome UA>
Referer: https://sycm.taobao.com/cc/item_archives?...
Accept: application/json, text/plain, */*
Origin: https://sycm.taobao.com
x-requested-with: XMLHttpRequest
```

必要参数：

```text
itemId / dateType / dateRange / device / belong / order / orderBy / page / pageSize
token / _
```

返回码：

| code | 含义 | 处理 |
|---:|---|---|
| `0` | 成功 | 保存数据 |
| `1003` | 缺少参数 | 按 `message` 补参数 |
| `1000` | 未知异常 | 接口路径/参数不对 |
| `1100` | 用户无权限 | 当前账号无权限，不是接口坏了 |
| HTTP 401/403 | 登录态失效 | 重新读该账号 Cookie / token |

### 账号隔离的真实例子

同一商品 `731918476865`：

- 察尔汗账号：`/cc/item/sale/overview.json` → `code:0`，有数据
- 察颜账号：同一接口 → `code:1100, message:"用户无权限"`

所以：

- 不能用账号 A 的 Cookie 取账号 B 的数据。
- 不能假设同一个商品 ID 在所有账号下都有数据。
- 每个账号的返回结果要单独校验 `code`。

## 第 6 步：按账号保存与合并

建议目录：

```text
data/
  察尔汗_2216332095488/
    2026-11-01/
      sale_overview.json
      flow_top.json
  察颜_2220801699546/
    2026-11-01/
      ...
```

每条数据带账号信息：

```json
{
  "account": {
    "profile_dir": "Profile 2",
    "profile_name": "察尔汗",
    "login_user_id": "2216332095488",
    "shop": "察尔汗壹品盐专卖店"
  },
  "date": "2026-11-01",
  "tab": "flow",
  "endpoint": "/cc/item/flow/top/v4.json",
  "data": []
}
```

合并规则：

- 每个账号保留原始 JSON。
- 合并时增加 `account` / `shop` / `loginUserId` 列。
- 不要按商品 ID 去重：同一商品 ID 在不同账号下权限和数据可能不同。
- 先按账号校验 `code`，再合并；`1100` 的数据不要混进成功数据。

## 异常与兜底

### 某个账号没有 sycm 页面

如果该 profile 当前没有 `sycm.taobao.com` 页面：

1. 在该 context 后台开一个 `sycm.taobao.com` 页面（一次性初始化）；
2. 之后在该页面里 fetch；
3. 不要从 `tgc.tmall.com` 等其他域页面跨域 fetch sycm 接口。

> 这是账号初始化的一次性成本；后续取数不再需要新页面。

### 备选方案：抓包（静态分析找不到接口时）

回退到后台 tab + Network 捕获：

```text
Target.createTarget({url:"about:blank", background:true})
  → Target.attachToTarget(flatten=true)
  → Network.enable
  → Page.navigate(目标 URL)
  → 收集 XHR/Fetch
  → Target.closeTarget
```

抓到后把接口模板写进 `endpoints.json`，所有账号共享。

### 接口改版

- 重新读 `performance` 资源列表。
- 下载新的 `op-cc/<version>/app.js` / `65.js`。
- grep 接口，更新 `endpoints.json`。

## 三种取数方式对比

| 方式 | 开 tab | 执行页面 JS | 多账号支持 | 适用 |
|---|---|---|---|---|
| 页面上下文 fetch | ❌ | ✅（仅 fetch） | ✅ 最稳 | 已有该账号页面，推荐 |
| Python HTTP + 页面 Cookie | ❌ | ❌ | ✅ 可用 | 批量、离线、需要自己控制请求 |
| 后台 tab 抓包 | ✅ 后台 | ✅ | ✅ 但重 | 首次发现接口、动态签名 |
| Playwright connect_over_cdp | ❌ | ✅ | ⚠️ 标签多时可能挂起 | 需要页面交互 |

## 关键约束

- 同一个 `--user-data-dir` 只能有一个 Chrome 实例；所有 profile 共用一个端口。
- 端口是进程属性，不是 profile 属性。
- 每个账号的 Cookie / token / 权限独立。
- 账号 key 用 `profile_dir + loginUserId`，不要用 `browserContextId`。
- 每个账号串行取数，账号之间加随机间隔。
- 只操作自己账号有权查看的数据。
- 前端发版后接口可能变化，用 `performance` + bundle grep 重新定位。
