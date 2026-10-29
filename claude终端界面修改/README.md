# claude终端界面修改

Claude Code 终端状态栏（statusLine）定制：目录、模型、上下文余量、上一轮 token 用量、按 DeepSeek 价格换算的费用占比、权限模式，外加 Unicode 边框。

- 归属层级：**Claude Code 用户级全局配置**（`~/.claude`），不是 VS Code 配置。
  VS Code 只是终端宿主；换到 Windows Terminal / PowerShell 运行同一个 `claude`，显示一致。
- 平台：Windows 10 + Git Bash（statusLine 命令经 Git Bash 执行）
- 最后更新：2026-10-29

## 效果预览

```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ 目录: E:\淘系自动上架 | 模型: deepseek-flash[1m]                                        ┃
┃ Free space: 877.5k (87.7%) | 上一轮: 出 2.5k · 入 120.0k                                ┃
┃ 总费用: ¥0.2208（高峰价） | 输出占比: 9.1% | 输入命中占比: 0.4% | 输入未命中占比: 90.5% ┃
┃ 权限模式: bypassPermissions                                                             ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
```

## 文件清单

| 文件 | 运行位置 | 作用 |
|---|---|---|
| `statusline.py` | `C:\Users\Administrator\.claude\statusline.py` | 全部逻辑：解析 stdin JSON、读 transcript、算费用、画边框 |
| `statusline.sh` | `C:\Users\Administrator\.claude\statusline.sh` | 薄封装：用固定路径的 Python 执行 statusline.py |
| `settings.json` | `C:\Users\Administrator\.claude\settings.json` | 仅需其中的 `statusLine` 配置；**含 API token，不纳入本仓库** |

本仓库只保存前两个脚本和本文档；恢复时把它们放回 `~/.claude/` 即可。

## 工作原理

1. Claude Code 在会话事件（新消息、模型/权限模式变化等）后执行 statusLine 命令，并把 JSON 通过 stdin 传入。
2. `statusline.sh` 调用 `D:\Program Files\Python312\python.exe statusline.py`。
3. `statusline.py` 按 **UTF-8** 显式读取 stdin（Windows 默认 GBK，遇中文路径会崩溃导致状态栏空白）。
4. 读取 `transcript_path` 指向的会话 JSONL 尾部 512KB：
   - 最后一条带 `"usage"` 的消息的 `timestamp` → 判定高峰/空闲计价时段
   - 最后一条 `"permissionMode"` → 权限模式行
5. 输出多行文本；Claude Code 逐行渲染（官方支持多行，每个换行一行）。脚本按显示宽度补齐边框（CJK 字符按 2 列）。

### 用到的输入字段

| 字段 | 用途 |
|---|---|
| `workspace.current_dir`（回退 `cwd`） | 第 1 行目录；`C:\Users\Administrator` 缩写为 `~/` |
| `model.display_name` / `model.id` | 第 1 行模型；`id` 用于匹配价格表（去掉 `[1m]` 后缀） |
| `context_window.context_window_size` | 计算剩余 token 绝对值 |
| `context_window.remaining_percentage` | Free space 百分比（缺失时用 `100 - used_percentage`） |
| `context_window.current_usage.{input_tokens, cache_creation_input_tokens, cache_read_input_tokens, output_tokens}` | 上一轮（最后一次 API 调用）用量与费用 |
| `transcript_path` | 读取请求时间、权限模式 |

注：statusLine 输入**没有** cost 金额字段，费用一律本地计算。

## 显示规格

| 行 | 内容 |
|---|---|
| 1 | `目录: <cwd> | 模型: <display_name>` |
| 2 | `Free space: <剩余 token> (<xx.x>%) | 上一轮: 出 <n> · 入 <n>` |
| 3 | `总费用: ¥<金额>（高峰价/空闲价） | 输出占比: x% | 输入命中占比: x% | 输入未命中占比: x%` |
| 4 | `权限模式: <permissionMode>`（transcript 无记录时省略） |

- “入” = `input_tokens + cache_creation_input_tokens + cache_read_input_tokens`
- 第 3 行占比按**费用**加权；未命中占比取 `100 - 输出占比 - 命中占比`，保证合计 100.0%
- 无 `current_usage` 时省略第 2 行后半段、第 3 行；模型不在价格表时不显示费用

## 计价规则（DeepSeek，CNY / 百万 tokens）

| 模型 | 时段 | 缓存命中 | 缓存未命中 | 输出 |
|---|---|---:|---:|---:|
| deepseek-flash | 高峰 | 0.04 | 2.0 | 8.0 |
| deepseek-flash | 空闲 | 0.02 | 1.0 | 4.0 |
| deepseek-v4-pro | 高峰 | 0.30 | 9.0 | 27.0 |
| deepseek-v4-pro | 空闲 | 0.15 | 4.5 | 13.5 |

- 高峰：北京时间周一至周五 9:00–12:00、14:00–18:00；其余为空闲（空闲价 = 高峰价一半）
- 旧模型名 `deepseek-v4-flash`、`deepseek-v4-flash-vision-exp` 按 Flash 价计
- 费用公式：
  - 未命中费 = `(input_tokens + cache_creation_input_tokens) × 未命中单价`
  - 命中费 = `cache_read_input_tokens × 命中单价`
  - 输出费 = `output_tokens × 输出单价`
  - 总费用 = 三者之和 ÷ 1,000,000
- **法定节假日未排除**：节假日 9–12 / 14–18 点仍按高峰价计算

## 安装 / 恢复

1. 把 `statusline.py`、`statusline.sh` 放回 `C:\Users\Administrator\.claude\`。
2. 按本机 Python 路径调整 `statusline.sh` 中的可执行文件（当前为 `/d/Program Files/Python312/python.exe`，对应 `D:\Program Files\Python312\python.exe`）。
3. 在 `~/.claude/settings.json` 中加入（不要提交 token）：

```json
{
  "statusLine": {
    "type": "command",
    "command": "C:/Users/Administrator/.claude/statusline.sh"
  }
}
```

4. 重启 Claude Code。状态栏下一次刷新生效。

### 本地验证

```bash
printf '%s' '{"workspace":{"current_dir":"E:/淘系自动上架"},"model":{"id":"deepseek-flash[1m]","display_name":"deepseek-flash[1m]"},"context_window":{"context_window_size":1000000,"remaining_percentage":87.7,"current_usage":{"input_tokens":100000,"cache_creation_input_tokens":0,"cache_read_input_tokens":20000,"output_tokens":2500}},"transcript_path":"<会话 jsonl 路径>"}' \
  | bash -c 'C:/Users/Administrator/.claude/statusline.sh'
```

## 快速修改索引

| 想改什么 | 改哪里 |
|---|---|
| 单价 / 新增模型 | `statusline.py` 顶部 `PRICES`、`ALIASES` |
| 高峰时段定义 | `price_period()` |
| 某行文案或顺序 | 搜索 `lines.append` / `segments.append` |
| 边框样式 | `print_box()` 里的 `┏ ━ ┓ ┃ ┗ ┛`（可换 ASCII `+ - |`） |
| 去掉权限模式行 | 删除 `last_permission_mode()` 调用及 `lines.append(f'权限模式...')` |
| 定时刷新（时钟类需求） | settings.json 的 `statusLine` 加 `"refreshInterval": 30` |
| 目录显示完整路径 | 删除 `home` 缩写那几行 |

## 已知限制

- 法定节假日未排除（无节假日日历）。
- 终端宽度小于约 95 列时，边框会折行。
- 多行 + ANSI 颜色在 Claude Code 中较易渲染异常，本版未使用颜色。
- 会话 transcript 超过尾部 512KB 未覆盖到记录时：时间退回当前时间，权限模式行可能缺失。
- provider 不返回 cache 字段时（当前实测 `cache_read` / `cache_creation` 均为 0），命中占比显示 0%。
- 底部自带的 `⏵⏵ bypass permissions on` 属于 Claude Code footer，无法包进边框；框内第 4 行是对应信息。

## 变更记录

| 日期 | 内容 |
|---|---|
| 2026-10-29 | 初版：修复 UTF-8 读取；加入目录/模型/Free space/上一轮用量/费用占比/权限模式/边框 |

## 安全说明

- 本仓库**不包含** `settings.json`，因为其中含 `ANTHROPIC_AUTH_TOKEN`。
- 两个脚本不含任何 cookie、token 或签名。
