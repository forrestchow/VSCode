# 05 · 分辨不同 profile 与账号

同一个 Chrome 进程里可以同时打开多个 profile 窗口。它们的页面都挂在同一个 CDP 端口下，`/json` 只返回页面列表，**不告诉你页面属于哪个 profile**。本文说明如何分辨。

## 三层身份，不要混在一起

| 层级 | 标识 | 从哪里读 | 例子 |
|---|---|---|---|
| CDP browser context | `browserContextId` | `Target.getTargets` | `D0373B94...`（UUID，会话级，不稳定） |
| Chrome profile | profile 目录 + 显示名 | `Local State` → `profile.info_cache` | `Default` / 察颜；`Profile 2` / 察尔汗 |
| 网站账号 | `loginUserId` / `tracknick` / 店铺名 | 页面 DOM / `meta[microdata]` / Cookie | `2220801699546` / 察颜旗舰店 |

关键点：

- **`browserContextId` 不是 Chrome profile ID**，它只是 CDP 用来分组页面的 UUID。
- **Chrome profile 显示名不是网站账号名**。例如 Chrome profile 叫「察颜」，网站账号叫「察颜旗舰店」。
- 稳定可复用的身份是：`profile 目录 + 显示名 + loginUserId`。

## 识别顺序（推荐）

```text
1. 页面 DOM / meta[microdata]     ← 最可靠
2. Cookie tracknick / unb         ← 辅助，部分 context 可能返回 0
3. chrome://version Profile Path  ← 确认 profile 目录
4. Local State info_cache         ← 目录 → 显示名
```

### 第 1 步：按 browserContextId 分组页面

连接浏览器级 CDP WebSocket（`/json/version` 的 `webSocketDebuggerUrl`），发送：

```json
{"id":1,"method":"Target.getTargets"}
```

返回的 `targetInfos` 里每个 `type:"page"` 都带 `browserContextId`。按它分组：

```python
groups = {}
for t in target_infos:
    if t.get("type") == "page":
        groups.setdefault(t.get("browserContextId", ""), []).append(t)
```

### 第 2 步：从页面 DOM 识别账号（优先）

对每个 context 选一个页面，`Target.attachToTarget(flatten=true)` 后执行：

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

- 生意参谋页面：`loginUserId` 直接是账号 ID；正文通常以「生意参谋 + 店铺名」开头。
- 淘工厂页面：正文里会出现公司/店铺名，例如「格尔木盐化(集团)有限责任公司」。

### 第 3 步：Cookie 读取（页面级更可靠）

`Storage.getCookies({browserContextId})` 对部分 context 会返回 **0 个 Cookie**。改用页面级 `Network.getCookies`：

```text
Target.attachToTarget({targetId, flatten:true})
  → Network.enable
  → Network.getCookies({urls:["https://sycm.taobao.com/"]})
```

提取：

```text
tracknick  → 登录账号名（URL 编码，需要解码）
lgc        → 登录账号名
unb        → 用户 ID
```

本机实测：

| context | Storage.getCookies | Network.getCookies | tracknick | unb |
|---|---:|---:|---|---|
| `CA0487...` | 0 | **32** | `scm54009219` | `2223101531825` |
| `76DF1E...` | 0 | **41** | 察尔汗壹品盐专卖店 | `2216332095488` |
| `D0373B...` | 156 | **43** | 察颜旗舰店 | `2220801699546` |

> `Network.getCookies` 是页面级命令，需要先 attach 到目标 context 的页面，再带 `sessionId` 调用。

### 第 4 步：读取 profile 目录（可选但精确）

在目标 context 后台打开 `chrome://version`：

```text
Target.createTarget({url:"about:blank", background:true, browserContextId: ctx})
  → Target.attachToTarget(flatten=true)
  → Page.enable
  → Page.navigate("chrome://version")
  → Runtime.evaluate(document.body.innerText)
  → 解析 "个人资料路径"
  → Target.closeTarget
```

取路径最后一段，例如：

```text
E:\VS Code\浏览器控制方案\chrome_profile_full\Profile 2
→ Profile 2
```

然后读 `Local State`：

```python
info_cache = json.loads(Path(user_data_dir, "Local State").read_text())["profile"]["info_cache"]
# {目录: 显示名}
```

当前映射：

| profile 目录 | 显示名 |
|---|---|
| `Default` | 察颜 |
| `Profile 2` | 察尔汗 |
| `Profile 3` | 收汁酱排骨 |
| `Profile 4` | 察颜专卖店 |
| `Profile 5` | 淘工厂 |

## 现成脚本

```bash
python list_browser_profiles.py
python list_browser_profiles.py --json
python list_browser_profiles.py --profile-path   # 额外读 Profile Path，会开临时后台页
```

默认不会创建任何 tab，只读取现有页面。

### 实测输出示例

```text
context: CA0487C2D61A750C2477F84CF093FAF3
  account: 格尔木盐化(集团)有限责任公司
  loginUserId: 2223101531825
  cookies: 32 | tracknick=scm54009219 | unb=2223101531825
  page: 淘工厂 | https://tgc.tmall.com/ds/page/supplier/product-redirect?...

context: 76DF1E3A378B166290A860D4EAEFDBBC
  account: 察尔汗壹品盐专卖店
  loginUserId: 2216332095488
  cookies: 41 | tracknick=察尔汗壹品盐专卖店 | unb=2216332095488
  page: 生意参谋 | https://sycm.taobao.com/cc/item_rank?dateRange=2026-11-02...

context: D0373B945D83386A54147C9F945ABDB2
  account: 察颜旗舰店
  loginUserId: 2220801699546
  cookies: 43 | tracknick=察颜旗舰店 | unb=2220801699546
  page: 生意参谋 | https://sycm.taobao.com/cc/item_rank?dateRange=2026-11-01...
```

推断的 Chrome profile：

| context | 页面账号 | loginUserId | tracknick | 推断 profile |
|---|---|---|---|---|
| `CA0487...` | 格尔木盐化(集团)有限责任公司 | 2223101531825 | `scm54009219` | `Profile 5` / 淘工厂 |
| `76DF1E...` | 察尔汗壹品盐专卖店 | 2216332095488 | 察尔汗壹品盐专卖店 | `Profile 2` / 察尔汗 |
| `D0373B...` | 察颜旗舰店 | 2220801699546 | 察颜旗舰店 | `Default` / 察颜 |

> `tracknick` 有时是登录 ID（如淘工厂的 `scm54009219`），页面正文才是公司/店铺名。两者都保留。 

> profile 列是「账号 + Local State」推断；要 100% 确认，用 `--profile-path` 或在对应 context 读 `chrome://version`。

## 为什么“默认 profile”不是识别依据

`Default` 只是 Chrome 的目录名。它当前对应的显示名是「察颜」，网站账号是「察颜旗舰店」，但这只是当前配置。

识别依据应该是：

```text
loginUserId / tracknick / 页面店铺名
```

而不是：

```text
Default 目录 / browserContextId / 端口号
```

## 端口与 profile 的关系

- 端口是 **Chrome 进程**属性，不是 profile 属性。
- 当前只有一个 Chrome 进程监听 `9223`，三个 context 都共用 `9223`。
- `.bat` 里的 9222/9223 只是启动约定，不是 profile 自带端口。
- 不同 profile 想用不同端口，必须用不同的 `--user-data-dir` 启动不同 Chrome 进程。

## 检查清单

- [ ] 用 `Target.getTargets` 分组，而不是只看 `/json`
- [ ] 每个 context 至少读一个页面的 `meta[microdata]`
- [ ] Cookie 返回 0 时，不要断定未登录，改用页面 DOM
- [ ] 区分 Chrome profile 显示名和网站账号名
- [ ] 需要稳定标识时，记录 `profile 目录 + 显示名 + loginUserId`
- [ ] 不要把 `browserContextId` 当作长期 profile ID
