# DOM 定位失败案例库

> 每次按 Skill 失败并解决后追加一条。通用规则晋升到 `SKILL.md`；项目特有规则写进项目文档，不在此处堆砌选择器。

## 模板

### YYYY-MM-DD · 场景

- 症状：
- 根因分类：
- 证据：
- 临时修复：
- 新规则：
- 是否晋升到 SKILL.md：是/否（原因）

## 案例

### 2026-11-02 · 跨域登录 iframe

- 症状：顶层 `document.querySelector('input')` 返回 0，登录表单找不到。
- 根因分类：document 作用域。
- 证据：`Page.getFrameTree` 显示 `havanalogin.taobao.com` iframe；`Page.createIsolatedWorld` 内能查到 `#fm-login-id`。
- 临时修复：在 iframe 的 execution context 内查询/填值。
- 新规则：先确定 document/root；跨域 iframe 用 frameId + isolated world；OOPIF 用 target attach。
- 是否晋升到 SKILL.md：是（通用规则）。

### 2026-11-02 · Chrome 密码管理器弹窗

- 症状：登录页点击账号名后弹出保存的账号，但 CDP 无法选中；`Runtime.evaluate` / `Input` 都无效。
- 根因分类：浏览器 UI，不在 DOM/网络。
- 证据：弹窗不出现在 `document.querySelectorAll('*')` 或 `/json` 页面列表中。
- 临时修复：人工点击一次；或 OS 级 UI 自动化。
- 新规则：Chrome 密码管理器/下载气泡/权限提示不是 DOM；不要尝试用 querySelector/CDP Input 操作。
- 是否晋升到 SKILL.md：是（通用规则）。

### 2026-11-02 · 属性名与显示相反

- 症状：`data-sku-col-key="skuRetailPrice"` 的列显示「结算价（元）」，而 `skuPrice` 列显示「建议零售价（元）」。
- 根因分类：key 映射。
- 证据：可见表头与 `data-*` key 不一致。
- 临时修复：按可见表头文字映射列；不按 `data-*` key 或 index。
- 新规则：属性名和值都不可信；至少用两行/两列验证；冲突时以显示为准并 fail loudly。
- 是否晋升到 SKILL.md：是（通用规则）。

### 2026-11-02 · 纯前端计算值

- 症状：页面显示的「建议零售价」是结算价 × 1.5，但网络响应里没有这个值。
- 根因分类：网络边界。
- 证据：响应里只有结算价；页面值随结算价输入实时变化。
- 临时修复：读取输入/显示值前后对比，按公式验证。
- 新规则：纯前端计算抓不到 XHR；用 DOM/页面状态，并对比前后值。
- 是否晋升到 SKILL.md：是（通用规则）。
