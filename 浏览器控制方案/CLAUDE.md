# 浏览器控制方案 — 项目规则

## CDP 激活标签页

`http://localhost:{port}/json` 返回的 targets 中，**第一个 `type: "page"` 即为当前激活标签页**。

- `cdp_client.py` 的 `connect()` 已实现此逻辑：默认连激活页，传 `url_pattern` 可指定匹配 URL 的页面
- 不要用 Playwright 的 `contexts[0].pages[0]`（按创建顺序，不是激活页）

## 淘宝搜索翻页

URL 参数翻页在淘宝 SPA 上无效，始终弹回第一页。正确方式：

- 第一页：`location.href = url` 跳转
- 后续页：点击分页按钮 `button.next-pagination-item.next-next`

## 当前页 vs 翻页

- **当前页** = 用户 Chrome 中激活的标签页（CDP 测试用 `/json` 端点获取）
- **翻页** = 淘宝搜索页内页码切换（插件功能，用点击分页按钮实现）
- 两者完全不同，不可混用
