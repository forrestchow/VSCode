# Changelog

## 2026-11-02 · 作用域下调

- 从用户级（`~/.claude/skills/dom-locating`）迁移到目录级（`E:\VS Code\chrome电商数据获取脚本\.claude\skills\dom-locating`）。
- Skill 名变为 `chrome电商数据获取脚本:dom-locating`，内容不变。

## 2026-11-02 · v1.0.0

- 初始版本。
- 决策流程：网络优先是条件策略；先判断数据来源和 document 作用域。
- 覆盖 iframe/OOPIF、Shadow DOM、虚拟列表、隐藏副本、可点击性、真实输入事件、成功信号。
- 加入失败闭环：失败 → 证据 → 归因 → 降级修复 → 写 `cases.md` → 晋升 `SKILL.md` → 更新 changelog → 报告用户。
- 加入浏览器 UI 例外（Chrome 密码管理器）。
