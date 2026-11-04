---
name: open-shop-browser
description: Use when the user asks to 打开/启动/连接某个店铺或用户名的浏览器 (察尔汗, 察颜, 察颜专卖店, 收汁酱排骨, 淘工厂), or to open a page in that shop's real Chrome via CDP.
---

# 打开指定店铺的 Chrome 调试窗口

## 何时使用

用户说「打开察尔汗的浏览器」「用收汁酱排骨的浏览器打开百度」等。

不适用于：Playwright 自启 Chromium、无头批量采集。

## 执行

1. 从用户话里取显示名；不确定时先列出现有 profile：

   ```bash
   python "E:\VS Code\浏览器控制方案\cdp-control\open_browser.py" --list
   ```

2. 打开调试窗口并可选打开目标页面：

   ```bash
   python "E:\VS Code\浏览器控制方案\cdp-control\open_browser.py" "<显示名>" --url "https://www.baidu.com" --json
   ```

3. 汇报：显示名、profile 目录、端口、当前页面标题/URL。

## 行为

- **已有带 debug 端口的 Chrome**：用 `--new-window` handoff 打开目标 profile 的新窗口，复用现有 debug 端口，**不关闭任何 Chrome**。
- **没有 debug Chrome**：启动目标 profile（`--remote-debugging-port`），再通过 CDP `Target.createTarget` 打开 URL。
- 连接使用原始 CDP（websockets）到单个 page，不经过 Playwright。

## Profile 映射

| 显示名 | profile 目录 | 默认端口 |
|---|---|---|
| 察尔汗 | `Profile 2` | 9222 |
| 察颜专卖店 | `Profile 4` | 9222 |
| 收汁酱排骨 | `Profile 3` | 9223 |
| 察颜 | `Default` | 9223 |
| 淘工厂 | `Profile 5` | 9222 |

显示名来自 `chrome_profile_full/Local State` 的 `profile.info_cache`；脚本内置映射优先，未命中会自动查 Local State。

## 约束

- 不要用 Playwright 的 `connect_over_cdp()`：本机标签页较多时会挂起（已验证 >90s）。脚本已改用原始 CDP。
- 不要用 `contexts[0].pages[0]` 判断激活页；用 `/json` 第一个 `type:"page"`。
- 未经用户确认不要关闭 Chrome；本脚本只打开新窗口，不会 kill 进程。
- 端口属于 Chrome **进程**；同一 `--user-data-dir` 只能有一个实例，换 profile 用 handoff 新窗口。

## 常见坑

- `察颜.bat` 未传 `--profile-directory`，会沿用 `last_used`（当前 `Profile 5` 淘工厂）；不要直接用它。
- Chrome v136+ 在默认 User Data 路径下会静默忽略 debug 端口；必须用 `chrome_profile_full`。
- 如果 Chrome 已运行但 debug 端口被禁用，脚本会报错并要求先关闭；不要在未确认时 kill。

## 验证

```bash
curl http://localhost:<port>/json
```

第一个 `type:"page"` 即当前激活标签页；应与脚本输出的标题/URL 一致。
