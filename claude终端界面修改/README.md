# claude终端界面修改

Claude Code 终端状态栏（statusLine）定制：目录、模型、上下文余量、上一轮（一次提问 → 最终答复）token 用量、按 DeepSeek 价格换算的费用占比、权限模式，外加 Unicode 边框。

- 归属层级：**Claude Code 用户级全局配置**（`~/.claude`），不是 VS Code 配置。
  VS Code 只是终端宿主；换到 Windows Terminal / PowerShell 运行同一个 `claude`，显示一致。
- 平台：Windows 10 + Git Bash（statusLine 命令经 Git Bash 执行）
- 最后更新：2026-10-29

## 效果预览

```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ 目录: E:\淘系自动上架 | 模型: deepseek-flash[1m]                                         ┃
┃ Free space: 877.0k (87.7%) | 上一轮: 出 8.7k · 入 7.53M                                  ┃
┃ 总费用: ¥0.3861（高峰价） | 输出占比: 18.0% | 输入命中占比: 77.9% | 输入未命中占比: 4.1% ┃
┃ 权限模式: bypassPermissions                                                              ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
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
4. 读取 `transcript_path` 指向的会话 JSONL：
   - 尾部 512KB：最后一条 `"permissionMode"` → 权限模式行；最后一条带 `"usage"` 的消息的 `timestamp` 只在回退时用于计价
   - 全文倒序扫描 → 切出最后一轮并累计用量（见下节）
5. 输出多行文本；Claude Code 逐行渲染（官方支持多行，每个换行一行）。脚本按显示宽度补齐边框（CJK 字符按 2 列）。

### 「上一轮」怎么切

bypass 模式下一次提问会连续触发几十次 API 调用（每个工具步骤一次），所以「轮」不能按 API 调用算：

- **起点**：最后一条人工提问——`type:"user"`，且不是 `tool_result`、不是 `isMeta`、不是 `isSidechain`、不是压缩摘要，内容为文本（字符串，或含 `text`/`image` 块的列表）。
- **终点**：文件末尾。答复还没结束时就是「到目前为止」，数字随步骤增长。
- **合计**：起点之后所有 assistant 消息的 `message.usage` 累加。
- **去重**：同一次响应会按 content block 写多行（thinking / text / tool_use 各一行），每行都带同一份 usage，按 `message.id` 只取一次。
- **未答提问**：刚提交提问、还没有 API 调用时，回溯显示再上一轮，避免闪成 0。
- **扫描**：按 256KB 块从文件末尾倒着读，命中提问即停；只有找不到边界时才读完整个文件（28MB 实测约 90ms）。

### 用到的输入字段

| 字段 | 用途 |
|---|---|
| `workspace.current_dir`（回退 `cwd`） | 第 1 行目录；`C:\Users\Administrator` 缩写为 `~/` |
| `model.display_name` / `model.id` | 第 1 行模型；`id` 用于匹配价格表（去掉 `[1m]` 后缀） |
| `context_window.context_window_size` | 计算剩余 token 绝对值 |
| `context_window.remaining_percentage` | Free space 百分比（缺失时用 `100 - used_percentage`） |
| `context_window.current_usage.{input_tokens, cache_creation_input_tokens, cache_read_input_tokens, output_tokens}` | 回退用量：transcript 不可用或找不到轮次边界时，用最后一次 API 调用的数字 |
| `transcript_path` | 倒序扫描整轮用量；尾部 512KB 取权限模式与回退计价时间 |

注：statusLine 输入**没有** cost 金额字段，费用一律本地计算。

## 显示规格

| 行 | 内容 |
|---|---|
| 1 | `目录: <cwd> | 模型: <display_name>` |
| 2 | `Free space: <剩余 token> (<xx.x>%) | 上一轮: 出 <n> · 入 <n>` |
| 3 | `总费用: ¥<金额>（高峰价/空闲价/跨时段） | 输出占比: x% | 输入命中占比: x% | 输入未命中占比: x%` |
| 4 | `权限模式: <permissionMode>`（transcript 无记录时省略） |

- “上一轮” = 用户最后一次提问到当前答复之间的**全部 API 调用**合计；正在回答时数字随步骤增长，答完即定格
- “入” = `input_tokens + cache_creation_input_tokens + cache_read_input_tokens`
- 第 3 行占比按**费用**加权；未命中占比取 `100 - 输出占比 - 命中占比`，保证合计 100.0%
- 整轮用量和 `current_usage` 都取不到时，省略第 2 行后半段与第 3 行；模型不在价格表时不显示费用

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
- 每次 API 调用按**各自 `timestamp`** 所在时段计价；一轮跨过高峰/空闲边界时，标签显示「跨时段」
- 上一轮的费用与占比均按整轮合计计算；回退到 `current_usage` 时只算最后一次调用
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
| 轮次的起止定义 | `is_real_prompt()`（哪些消息算提问）、`round_usage()`（倒序扫描与累计） |
| 边框样式 | `print_box()` 里的 `┏ ━ ┓ ┃ ┗ ┛`（可换 ASCII `+ - |`） |
| 去掉权限模式行 | 删除 `last_permission_mode()` 调用及 `lines.append(f'权限模式...')` |
| 定时刷新（时钟类需求） | settings.json 的 `statusLine` 加 `"refreshInterval": 30` |
| 目录显示完整路径 | 删除 `home` 缩写那几行 |

## 已知限制

- 法定节假日未排除（无节假日日历）。
- 终端宽度小于约 95 列时，边框会折行。
- 多行 + ANSI 颜色在 Claude Code 中较易渲染异常，本版未使用颜色。
- 权限模式只查尾部 512KB：更早的记录取不到时该行缺失；回退用量的计价时间则会退回当前时间。
- 子代理若写入独立 transcript 文件，其用量不计入本轮；写进同一会话文件的 sidechain 调用计入。
- 提问正文里若出现字面量 `"type":"tool_result"`，该提问会被预过滤跳过（极罕见），上一轮会并到更早一轮。
- 超长轮次（几十 MB）倒序扫描约百毫秒内，状态栏刷新可能略慢。
- provider 不返回 cache 字段时（当前实测 `cache_read` / `cache_creation` 均为 0），命中占比显示 0%。
- 底部自带的 `⏵⏵ bypass permissions on` 属于 Claude Code footer，无法包进边框；框内第 4 行是对应信息。

## 变更记录

| 日期 | 内容 |
|---|---|
| 2026-10-29 | 初版：修复 UTF-8 读取；加入目录/模型/Free space/上一轮用量/费用占比/权限模式/边框 |
| 2026-10-29 | 「上一轮」改为整轮口径：从最后一条人工提问到当前答复，累计期间全部 API 调用（按 `message.id` 去重），费用按各调用时间戳分时段计价；未答提问回退到上一轮 |

## 安全说明

- 本仓库**不包含** `settings.json`，因为其中含 `ANTHROPIC_AUTH_TOKEN`。
- 两个脚本不含任何 cookie、token 或签名。
