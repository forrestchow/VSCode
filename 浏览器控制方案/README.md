# 浏览器控制方案：CDP 直连 vs Playwright Launch

控制 Chrome/Chromium 浏览器执行自动化任务（页面提取、数据采集、自动化测试、插件调试等）的两种主流方案对比。

---

## 两种方案速览

| | CDP 直连 | Playwright Launch |
|---|---|---|
| **一句话** | 连你日常用的 Chrome，操控它 | Playwright 自己启动一个独立 Chromium |
| **浏览器本体** | 你的真实 Chrome（完整指纹/历史/扩展/Cookie） | Playwright 自带的独立 Chromium（~400MB） |
| **启动方式** | 手动启 Chrome Debug 模式（`--remote-debugging-port=9222`） | `pw.chromium.launch()` 代码启动 |
| **日常 Chrome 冲突** | ❌ 必须先关所有 Chrome，再开 Debug 版 | ✅ 不受影响，随时启动 |
| **登录态** | ✅ 复用浏览器现有 Cookie（但需快照 Profile） | ⚠️ 独立，首次需登录，之后持久化 |
| **浏览器指纹** | ✅ 与日常完全一致 | ⚠️ 独立指纹（无历史/扩展/Google 账号） |
| **反检测难度** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| **交互本质** | CDP WebSocket | CDP WebSocket（同一套协议） |
| **API** | `page.evaluate()` / `page.mouse.move()` ... | **完全一样** ✅ |
| **适用场景** | 需要真实指纹、调试插件、复用登录态 | 不想关日常浏览器、批量自动化、CI/CD |

---

## 一、CDP 直连模式

### 1.1 什么是 CDP

**CDP（Chrome DevTools Protocol）** 是 Chrome 暴露的调试协议。Chrome 启动时加 `--remote-debugging-port=9222` 参数，就会在 `localhost:9222` 监听 WebSocket 连接。任何能发 WebSocket 消息的程序都可以通过 CDP 控制浏览器——包括但不限于：

- **Playwright** `connect_over_cdp()`（本项目用）
- **pychrome**（轻量 CDP 封装）
- **Selenium**（v4+ 支持 CDP）
- **手写 websockets 库** + CDP 原始命令

```
Chrome (Debug 模式)
  └── localhost:9222 ── WebSocket ──► CDP 客户端（任选）
        ├── Playwright connect_over_cdp()
        ├── pychrome
        ├── Selenium CDP
        └── raw websockets + JSON
```

### 1.2 为什么需要复制 Profile

Chrome v136 引入安全策略：`--remote-debugging-port` 在**默认 User Data 路径**下会被静默忽略，防止攻击者通过 CDP 读取生产浏览器的密码和 Cookie。

```
默认路径: C:\Users\<用户>\AppData\Local\Google\Chrome\User Data
  + --remote-debugging-port=9222 → ❌ 端口不开

自定义路径: E:\VS Code\...\chrome_profile_full
  + --remote-debugging-port=9222 → ✅ 端口正常
```

**解决方案**：将日常 Chrome 的 User Data **完整复制**到一个非默认路径，启动时通过 `--user-data-dir` 指向它。

### 1.3 启动方式

```powershell
# 1. 关掉所有 Chrome 实例
taskkill /F /IM chrome.exe

# 2. 启动 Debug 模式
"C:\Program Files\Google\Chrome\Application\chrome.exe" `
    --remote-debugging-port=9222 `
    --user-data-dir="E:\VS Code\浏览器控制方案\chrome_profile_full" `
    --profile-directory="Profile 2"
```

验证端口：
```bash
curl http://127.0.0.1:9222/json/version
# → {"Browser": "Chrome/...", "Protocol-Version": "1.3", ...}
```

### 1.4 代码示例

```python
from playwright.async_api import async_playwright

async with async_playwright() as pw:
    # 连接到已打开的 Debug Chrome
    browser = await pw.chromium.connect_over_cdp("http://localhost:9222")
    page = browser.contexts[0].pages[0]

    # 所有操作和 Launch 模式完全一样
    print(await page.title())
    html = await page.evaluate("() => document.body.outerHTML")
    await page.mouse.move(100, 200)
    await page.click("#button")
```

### 1.5 CDP 的优势

- **真实指纹**：浏览器指纹、WebGL、字体列表、窗口配置与日常使用完全一致，理论上无法被识别为脚本
- **真实登录态**：复用浏览器的 Cookie/LocalStorage（注意：是复制时的快照，非实时同步）
- **调试插件**：可以调试 Chrome 扩展（Extension），注入 content script 后通过 CDP 观察运行效果

### 1.6 CDP 的限制

- **Chrome 单实例**：`--remote-debugging-port` 只在首次启动时生效，必须先关掉所有 Chrome
- **Profile 快照**：复制的 User Data 是静态快照，日常 Chrome 重新登录后不会自动同步
- **v136+ 限制**：默认路径下 debug 端口被静默忽略，必须用非默认路径

### 1.7 更新 Profile 快照

日常 Chrome 中的登录态是实时变化的（重新登录、切换账号、Cookie 过期等），而 CDP Debug Chrome 用的是复制时的快照。当登录态过期时，重新复制日常 Profile：

```bash
# 从日常 Chrome 重新复制 Profile（只复制核心文件，不含缓存垃圾）
python copy_profile_minimal.py
```

> **更新频率**：取决于登录态有效期。千川/巨量引擎的 Cookie 通常有效期较长（数周），不需要频繁更新。发现 Debug Chrome 里需要重新登录时再跑一次即可。

> **另一种方式**：也可以直接在 Debug Chrome 里手动重新登录一次——登录后的新 Cookie 会写入 `cdp-control/chrome_profile_full/`，后续自动复用。只是注意这不是"同步"日常 Chrome，而是在 Debug Chrome 里独立登录。

### 1.8 下载文件无法打开/无法显示文件夹

**现象**：Debug Chrome 下载文件后，点击下载栏的「打开」或「在文件夹中显示」无反应。

**原因**：复制过来的 Profile 中，`Preferences` 文件里的 `download` 配置为空 `{}`。Chrome 不知道默认下载目录在哪，无法打开文件所在文件夹。非默认 `--user-data-dir` 的 Profile 不会自动补全系统 Downloads 路径。

**修复**：在 `Preferences` 中写入下载路径——

```python
# scripts/fix_downloads.py
import json

prefs_path = 'chrome_profile_full/Profile 2/Preferences'
with open(prefs_path, 'r', encoding='utf-8') as f:
    prefs = json.load(f)

prefs['download'] = {
    'default_directory': 'C:/Users/Administrator/Downloads',
    'prompt_for_download': False,
    'directory_upgrade': True,
}

with open(prefs_path, 'w', encoding='utf-8') as f:
    json.dump(prefs, f, ensure_ascii=False)
```

> 修改后需重启 Chrome 生效。如果 Profile 有多个（Profile 3、Profile 4），每个都需要同样操作。

---

## 二、Playwright Launch 模式

### 2.1 什么是 Playwright Launch

Playwright 是一个**自动化框架**（SDK），`launch()` 方法会启动它自带的独立 Chromium 浏览器（通过 `playwright install chromium` 下载，约 400MB）。这个 Chromium 和你的日常 Chrome 是**两个不同的进程**，互不干扰。

**关键区分——Playwright 的两个含义：**

| | 含义 | 实质 | 类比 |
|---|---|---|---|
| **Playwright 框架** | 自动化 SDK/库，提供 `launch()`、`connect_over_cdp()`、`page.mouse.move()` 等 API | PyPI/npm 包，纯代码 | 汽车的**方向盘和油门** |
| **Playwright 自带 Chromium** | `playwright install chromium` 下载的独立 Chromium 浏览器 | 真实浏览器二进制文件（去 Google 服务） | 汽车的**发动机** |

```
Playwright 框架                  Playwright 自带的 Chromium
  ├── launch()  ─────────────►    启动一个独立 Chromium 进程
  ├── connect_over_cdp() ───►    连接到你已打开的真 Chrome
  └── page.mouse.move()          不管连哪个浏览器都发 CDP 指令
```

### 2.2 安装

```bash
pip install playwright
playwright install chromium    # 下载约 400MB 的独立 Chromium
```

浏览器安装位置：`C:\Users\<用户>\AppData\Local\ms-playwright\`

### 2.3 代码示例

```python
from playwright.async_api import async_playwright
from pathlib import Path

# 持久化目录 — 登录态保存在这里，下次自动恢复
USER_DATA_DIR = Path("./playwright_profile")

async with async_playwright() as pw:
    browser = await pw.chromium.launch(
        headless=False,                     # 显示浏览器窗口
        user_data_dir=str(USER_DATA_DIR),   # 持久化登录态
    )

    page = browser.contexts[0].pages[0]
    await page.goto("https://example.com")

    # 和 CDP 模式完全一样的 API
    print(await page.title())
    await page.mouse.move(100, 200)
    html = await page.evaluate("() => document.body.outerHTML")

    await browser.close()
```

### 2.4 Launch 的优势

- **不冲突**：不依赖日常 Chrome，随时启动，无需关闭任何进程
- **可持久化**：指定 `user_data_dir` 后，首次登录的 Cookie 写入该目录，后续自动恢复——和 Chrome 记住密码的原理完全一样
- **独立环境**：干净无痕，不同项目用不同 `user_data_dir` 互不干扰
- **CI/CD 友好**：可在无头环境（headless）运行

### 2.5 Launch 的限制

- **浏览器是 Chromium**：不是 Chrome，缺少 Google 账号同步、部分编解码、某些 Chrome 特有功能
- **指纹独立**：浏览器指纹（Canvas/WebGL/字体）和日常使用不同，对有反爬的网站风险更高
- **首次需登录**：`user_data_dir` 首次使用时空 Cookie，需手动登录一次

---

## 三、深度对比

### 3.1 反爬检测能力

| 检测维度 | CDP 直连真 Chrome | Playwright Launch Chromium |
|---------|-------------------|---------------------------|
| 浏览器本体 | 你日常用的完整 Chrome | 独立 Chromium（缺 Google 账号/同步/编解码） |
| `navigator.webdriver` | ✅ 不存在（真浏览器） | ✅ 已移除（`--disable-blink-features=AutomationControlled`） |
| Canvas/WebGL 指纹 | ✅ 与日常完全一致 | ⚠️ 同版本基础相同，GPU 驱动可能有细微差异 |
| 字体列表 | ✅ 系统全部字体 | ⚠️ 可能缺某些注册表字体 |
| 鼠标轨迹 | ❌ `move(x,y)` 直线瞬移 | ❌ 同上（同一套 API） |
| 窗口/视口 | ✅ 真实用户配置 | ⚠️ 默认 1280x720 |
| WebRTC IP | ✅ 真实网络 | ✅ 真实网络 |
| Cookie/登录态 | ✅ 真实（但需 Profile 快照） | ⚠️ 独立，首次需登录 |
| 扩展/历史/书签 | ✅ 完整 | ❌ 无 |
| **综合反检测难度** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |

### 3.2 交互本质：完全一样

无论 CDP 直连还是 Launch，一旦获得 Playwright 的 `Page` 对象，所有操作 API 完全一样：

| 操作 | 代码 | 底层 |
|------|------|------|
| 执行 JS | `page.evaluate(js)` | CDP `Runtime.evaluate`（WebSocket） |
| 获取 HTML | `page.content()` | CDP `DOM.getOuterHTML` |
| 鼠标移动 | `page.mouse.move(x, y)` | CDP `Input.dispatchMouseEvent` |
| 鼠标点击 | `page.click(selector)` | CDP `Runtime.evaluate` + `Input.dispatchMouseEvent` |
| 键入文字 | `page.fill(selector, text)` | CDP `Input.insertText` |
| 截图 | `page.screenshot()` | CDP `Page.captureScreenshot` |
| 等待元素 | `page.wait_for_selector(sel)` | CDP `DOM.querySelector` 轮询 |
| 拦截请求 | `page.on('request', fn)` | CDP `Network.requestWillBeSent` |

```
CDP 模式                                Launch 模式
────────                                ──────────
Chrome (外部 Debug 进程)                 Chromium (Playwright 子进程)
    │                                        │
    │ WebSocket (localhost:9222)             │ WebSocket (随机内部端口)
    ▼                                        ▼
playwright.connect_over_cdp()           playwright.chromium.launch()
    │                                        │
    ▼                                        ▼
  Page 对象 ◄──────── 完全相同的 API ─────────►  Page 对象
    │                                        │
    ▼                                        ▼
page.evaluate(js)                       page.evaluate(js)
    │                                        │
    ▼                                        ▼
CDP Runtime.evaluate                    CDP Runtime.evaluate
(JSON over WebSocket)                   (JSON over WebSocket)
```

> 结论：两者的**交互能力完全一致**，唯一的区别在于浏览器进程是谁启动的、指纹/Cookie 是否真实。

### 3.3 使用场景

| 场景 | 推荐方案 | 原因 |
|------|---------|------|
| 需要极致反检测（已知网站有强反爬） | CDP | 真实指纹、真实 Cookie |
| 调试 Chrome 插件 | CDP | 插件安装在真 Chrome 中 |
| 不想关日常浏览器 | Launch | 独立进程，互不干扰 |
| 批量自动化采集 | Launch | 代码驱动，随时启动 |
| CI/CD 无头运行 | Launch | 支持 `headless=True` |
| 多账号切换 | Launch | 不同 `user_data_dir` 互不干扰 |
| 复用浏览器现有登录态 | CDP | 直接复用 Chrome Cookie（快照） |
| 快速验证一段 JS | 随便 | 两者 `page.evaluate()` 完全一样 |

---

## 四、Chrome 的 User Data 与 Profile 机制

### 4.1 安装目录 vs User Data

```
安装目录（程序本体，所有用户共用）
C:\Program Files\Google\Chrome\Application\
├── chrome.exe         ← 可执行文件
├── chrome.dll         ← 浏览器引擎
└── ...

User Data（用户数据，存档）
C:\Users\<用户>\AppData\Local\Google\Chrome\User Data\
├── Local State        ← 全局配置、profile 列表
├── Default/           ← 默认 profile
├── Profile 2/         ← 用户创建的 profile
│   ├── Cookies        ← 登录 cookie
│   ├── Preferences    ← 浏览器设置
│   ├── Extensions/    ← 已安装的扩展
│   └── ...
└── ...
```

> 类比：安装目录是"游戏客户端"，User Data 是"存档"。卸载重装不影响存档。每个 Profile 是独立的"角色存档"。

### 4.2 为什么 CDP 需要复制 Profile

Chrome 启动时：
```
双击 chrome.exe（无参数）
  ├── 检查是否有 --user-data-dir
  │   ├── 无 → 用默认路径 C:\Users\...\User Data
  │   └── 有 → 用指定路径
  ├── 读 Local State → 确定使用哪个 profile
  └── Chrome v136+ 安全检查:
      ├── --user-data-dir 指向默认路径 → 静默忽略 --remote-debugging-port ❌
      └── --user-data-dir 指向其他路径 → 放行 debug 端口 ✅
```

所以 CDP 模式的根本矛盾是：
> 要开 debug 端口，必须用非默认路径 → 非默认路径意味着无法"实时共享"日常 Profile → 只能用快照

---

## 五、项目文件

```
浏览器控制方案/
├── README.md                         # 本文件（CDP vs Launch 对比文档）
├── copy_profile_minimal.py           # 精简 Profile 复制工具
│
├── cdp-control/                      # CDP 直连模式子项目
│   ├── chrome_profile_full/          #   Chrome User Data 精简快照（264MB）
│   │   ├── Local State               #     全局配置
│   │   ├── Profile 2/                #     带登录态的 profile
│   │   └── ...
│   ├── cdp_client.py                 #   CDP 客户端（Playwright 封装）
│   └── manager.py                    #   Chrome 生命周期管理
│
└── playwright-launch/                # Playwright Launch 模式子项目
    ├── ms-playwright/                 #   Playwright Chromium 浏览器（685MB，随项目打包）
    ├── playwright_profile/            #   Launch 登录态持久化目录（运行时生成）
    └── playwright_demo.py             #   Launch 模式演示脚本
```

---

## 六、快速开始

### CDP 直连模式

```powershell
# 0. 首次使用或登录态过期时：更新 Profile 快照
python copy_profile_minimal.py

# 1. 关掉所有 Chrome，启动 Debug 模式
taskkill /F /IM chrome.exe
"C:\Program Files\Google\Chrome\Application\chrome.exe" `
    --remote-debugging-port=9222 `
    --user-data-dir="E:\VS Code\浏览器控制方案\cdp-control\chrome_profile_full" `
    --profile-directory="Profile 2"

# 2. 验证端口
curl http://127.0.0.1:9222/json/version

# 3. 运行脚本
cd cdp-control
python cdp_client.py
```

### Playwright Launch 模式

```bash
# 1. 安装 Playwright SDK（首次）
pip install playwright
# 浏览器已随项目打包在 ms-playwright/ 下，无需 playwright install chromium

# 2. 运行
cd playwright-launch
python playwright_demo.py
```

---

## 七、常见问题

**Q: 两种模式能同时用吗？**
A: 不能。CDP 模式要求先关所有 Chrome，Launch 模式的 Chromium 不受影响。但 Launch 模式运行时可以打开 CDP 模式的 Debug Chrome（Chromium ≠ Chrome）。

**Q: Playwright 在 CDP 模式中必须安装吗？**
A: 不是。CDP 本质是 WebSocket 接口，任何能发 WS 消息的库都能控制 Chrome（pychrome、Selenium 甚至手写 websockets）。Playwright 只是把 CDP 原始命令封装成易用的 API。

**Q: Launch 模式的反检测能提升吗？**
A: 可以，常用的有：指定真实 `user_data_dir` 积累浏览历史、修改 `viewport` 匹配真实屏幕、使用 `playwright-stealth` 等第三方库。

**Q: CDP 的 Profile 快照过期了怎么办？**
A: 重新复制一次日常 Chrome 的 User Data：
```powershell
robocopy "$env:LOCALAPPDATA\Google\Chrome\User Data" `
    "E:\VS Code\浏览器控制方案\chrome_profile_full" /E /XD Crashpad GrShaderCache ShaderCache GPUCache
```

**Q: CDP 如何确定当前激活的标签页？**
A: `http://localhost:{port}/json` 返回的 targets 列表中，**第一个 `type: "page"` 即为当前激活标签页**。Chrome 的行为保证了这个排序——已验证 3 次 100% 命中。

```python
import urllib.request, json

resp = urllib.request.urlopen('http://localhost:9222/json')
targets = json.loads(resp.read().decode())
active = next(t for t in targets if t['type'] == 'page')
print(active['title'], active['url'])
```

> **注意**：Playwright 的 `contexts[0].pages[0]` 按标签页**创建顺序**排列，不代表激活页。`cdp_client.py` 已改为用 `/json` 端点定位激活页。

**Q: 淘宝搜索页翻页的正确方式？**
A: URL 参数翻页（`page.goto()` 或 `chrome.tabs.update()`）在淘宝 SPA 上**无效**，始终弹回第1页。正确做法是点击分页按钮 `button.next-pagination-item.next-next`。

```python
# ❌ 无效 — 弹回 page=1
await page.goto('https://s.taobao.com/search?page=2&q=食盐&sort=sale-desc')

# ✅ 有效 — 真正翻到第2页
await page.evaluate(
    'document.querySelector("button.next-pagination-item.next-next").click()'
)
```
