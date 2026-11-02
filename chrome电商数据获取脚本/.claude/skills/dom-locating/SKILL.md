---
name: dom-locating
description: >-
  Use when locating, querying, clicking, hovering, or typing into DOM elements,
  especially inside iframes, shadow roots, virtualized lists, hidden duplicates,
  or when querySelector returns null / a click has no effect. 触发词：定位 DOM、
  查找元素、querySelector 为空、元素点不到、iframe、Shadow DOM、虚拟列表、
  填表、悬停、点击。
metadata:
  version: 1.0.0
---

# DOM Locating

## Overview

定位 DOM 不是猜 selector，而是一条决策链：

```text
数据已在网络响应里？
  ├─ 是 → 直接用数据，不定位 DOM
  └─ 否 → 确定 document/root → 选稳定锚点 → 验证可点击 → 真实输入事件 → 具体成功信号
```

核心原则：**用最稳定的信号定位，动作前验证，动作后用具体信号确认；规则失效时更新规则，而不是只绕过这一次。**

## When to Use

- 查找、定位、点击、悬停、填写 DOM 元素
- `querySelector` 返回 `null`、匹配多个、匹配到隐藏元素
- 元素在 iframe、Shadow DOM、虚拟列表/懒加载里
- 点击/输入无效，需要判断是选择器、可点击性还是事件问题
- 需要从网络响应反查 DOM

**不适用：**

- 数据已在 XHR/fetch 响应里 → 直接用数据
- Chrome 密码管理器、下载气泡、权限提示等浏览器 UI → 不在 DOM/网络里
- 纯静态 HTML 文本 → 解析 HTML，不要开页面

## 决策流程

1. **先判断数据来源**：在响应里 → 直接用；不在 → 继续。
2. **确定 document/root**：顶层 / iframe / Shadow Root / OOPIF。顶层查询看不到跨域 iframe 和 shadow root。
3. **判断元素类型**：数据行用业务 key + 可见文本；UI 控件用 `id/name/placeholder/aria-label/role/文本`。
4. **处理列表**：虚拟列表/懒加载先滚动或翻页到目标；用数据索引，不用行索引。
5. **收集候选**：`querySelectorAll` + 容器作用域；检查数量；排除隐藏模板/响应式副本。
6. **验证可点击**：rect、`checkVisibility`、`elementFromPoint`、`disabled/inert`、overflow/z-index。
7. **执行动作**：真实 `Input` 事件；hover 用 `mouseMoved`；输入用 `Input.insertText` 或 native setter + `input/change`。
8. **验证成功**：关联具体请求（URL/方法/参数/code）或 DOM/URL/toast/值变化；加超时和负信号。
9. **失败 → 走失败闭环**。

## Quick Reference

| 场景 | 首选定位 | 关键点 |
|---|---|---|
| 跨域 iframe | `Page.getFrameTree` → `Page.createIsolatedWorld` → `Runtime.evaluate(contextId)` | 顶层 `querySelector` 无效；OOPIF 用 `Target.setAutoAttach` |
| Shadow DOM | 从 host 进 `shadowRoot` BFS；closed root 用 `DOM.getDocument({pierce:true})` | id 在每个 root 内独立 |
| 虚拟列表 | 滚动容器 + 数据索引 `scrollTop = index * rowHeight` | 节点会回收；找到后同一 evaluate 内取坐标并点击 |
| 数据行 | 响应 key + 可见文本双重校验 | 属性名/值可能被转换或与显示相反 |
| 按钮/输入框 | `id/name/placeholder/aria-label/role/文本` | 不要用哈希 class |
| 隐藏副本 | `querySelectorAll` + 可见性过滤 + `elementFromPoint` | 第一个匹配不一定可点 |
| 悬停菜单 | `Input.dispatchMouseEvent` `mouseMoved` | JS `mouseover` 不一定触发 CSS `:hover` |
| 框架输入框 | focus + `Input.insertText`；或 native setter + `input/change` | 只改 `.value` 可能不更新 React/Vue |

## Core Rules

1. **网络优先是条件策略。** 数据在响应里就直接用；静态/UI 控件直接语义定位。抓包用于发现接口或确认数据来源。
2. **先确定 document 作用域。** 顶层、iframe、shadow root、OOPIF 查询方式不同；跨域 iframe 用 frameId + isolated world，OOPIF 用 target attach。
3. **锚点优先级不是固定的 `id > url > name`。** 标准：跨刷新稳定 > 作用域内唯一 > 可见文本/语义二次校验。key 也可能来自请求参数。
4. **响应有 key ≠ DOM 有元素。** 虚拟列表/懒加载要滚动或翻页；用数据索引；节点回收后重新查询。
5. **`querySelector` 只返回第一个。** 用 `querySelectorAll` + 作用域 + 可见性过滤；检查匹配数。
6. **rect + style 不等于可点击。** 加 `elementFromPoint`、`scrollIntoView`、`checkVisibility`、`disabled/inert`、overflow/z-index 遮挡检查。
7. **动作要用真实输入事件。** `element.click()` 只初试；hover 用 `mouseMoved`；输入用 `insertText`/native setter + `input/change`。密码管理器弹窗是浏览器 UI，DOM/CDP 点不到。
8. **成功信号要具体。** “下一个请求”可能是无关请求；按 URL/参数/code 关联。无网络动作用 DOM/URL/toast/值变化；加超时和负信号。
9. **网络不是万能的。** SSR/初始 HTML、`__INITIAL_STATE__`、localStorage、WebSocket、纯前端计算抓不到 XHR；走页面状态/DOM/存储，并对比前后值。
10. **属性名和值都不可信。** 至少用两行/两列验证映射；列按可见表头映射，不按 index；冲突时以显示为准并 fail loudly。
11. **选择器要能退化。** 记录 key/selector/rect/匹配数；miss 时重新发现；映射绑定页面版本；元素句柄 re-render 后失效，动作前重新 query。
12. **浏览器 UI 不是 DOM。** Chrome 密码管理器/下载气泡/权限提示只能人工、Chrome 自动登录或 OS 级 UI 自动化。

## 失败闭环（强制）

**本 Skill 是活文档：规则失效时，修规则，不要只修这一次的 workaround。**

当定位失败、找不到元素、点击无效、值不对、成功信号不符合预期：

1. **停止盲目重试**，记录证据：目标 key、document/root、selector、匹配数、rect、visibility/pointer-events、`elementFromPoint`、网络请求/响应、页面版本。
2. **归类失败**：document 作用域 / key 映射 / 虚拟列表 / 多匹配 / 可点击性 / 事件 / 成功信号 / 网络边界 / 选择器过期。
3. **先用降级路径完成当前任务**。
4. **任务完成前**，把失败追加到 `references/cases.md`（症状、根因、新规则、证据）。
5. **规则晋升**：通用规则 → 更新本 `SKILL.md`；项目特有规则 → 写进项目文档，不污染通用 Skill。
6. 在 `references/changelog.md` 追加日期 + 变更摘要。
7. **向用户报告**：改了哪条规则、为什么、有什么证据。
8. **结束前自检**：本次是否遇到规则未覆盖的情况？是否已记录并更新？未更新要说明原因。

**禁止：** 静默绕过、不记录；无证据删除旧规则；把项目特有选择器写进通用 Skill；只改代码不更新规则。

## Common Mistakes

| 错误 | 修正 |
|---|---|
| 顶层 `querySelector` 找 iframe 元素 | `Page.getFrameTree` + `Page.createIsolatedWorld` |
| 第一个匹配就点击 | `querySelectorAll` + 可见性 + 命中测试 |
| 用行索引定位虚拟列表 | 业务 key/数据索引；滚动到目标 |
| 只改 `.value` | native setter + `input/change` 或 `Input.insertText` |
| `element.click()` 无效就反复点 | 真实鼠标事件；检查 overlay/disabled |
| 用 `data-*` key 直接映射列 | 可见表头二次校验；冲突以显示为准 |
| 固定 sleep | 等具体请求/DOM 状态/URL |
| 把密码管理器弹窗当 DOM | 浏览器 UI；人工/OS 自动化/Chrome 自动登录 |

## References

- `references/cdp-patterns.md`：CDP 代码模式（iframe、shadow DOM、虚拟列表、点击、输入、成功信号）
- `references/cases.md`：失败案例库（每次失败后追加）
- `references/changelog.md`：规则变更记录
