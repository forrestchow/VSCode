import sys, json, os, re, unicodedata
from datetime import datetime, timezone, timedelta

# Status line input arrives as UTF-8; read the raw buffer so the Windows
# default code page cannot fail on non-ASCII paths (e.g. E:\淘系自动上架).
sys.stdout.reconfigure(encoding='utf-8')

CST = timezone(timedelta(hours=8))

# DeepSeek list prices, CNY per 1M tokens: (cache hit, cache miss, output).
# Peak: Mon-Fri 09:00-12:00 and 14:00-18:00 Beijing time; idle = half of peak.
# Statutory holidays are not excluded here.
PRICES = {
    'deepseek-flash': {
        'peak': (0.04, 2.0, 8.0),
        'idle': (0.02, 1.0, 4.0),
    },
    'deepseek-v4-pro': {
        'peak': (0.30, 9.0, 27.0),
        'idle': (0.15, 4.5, 13.5),
    },
}
# Old names still served by DeepSeek-V4.1-Flash and billed at Flash rates.
ALIASES = {
    'deepseek-v4-flash': 'deepseek-flash',
    'deepseek-v4-flash-vision-exp': 'deepseek-flash',
}

# Cheap prefilters for the backwards transcript scan. Transcript lines can be
# megabytes long (tool output), so every line is tested with these before it
# is handed to json.loads.
RE_ASSISTANT = re.compile(rb'"type"\s*:\s*"assistant"')
RE_USER = re.compile(rb'"type"\s*:\s*"user"')
RE_TOOL_RESULT = re.compile(rb'"type"\s*:\s*"tool_result"')

try:
    data = json.loads(sys.stdin.buffer.read().decode('utf-8', 'replace'))
except Exception:
    sys.exit(0)


def fmt_tokens(n):
    n = int(n)
    if n >= 1_000_000:
        return f'{n / 1_000_000:.2f}M'
    if n >= 1000:
        return f'{n / 1000:.1f}k'
    return str(n)


def fmt_cost(c):
    return '<¥0.0001' if 0 < c < 0.0001 else f'¥{c:.4f}'


def read_tail(path, n=512_000):
    """Last n bytes of the session transcript (JSONL, UTF-8)."""
    if not path:
        return ''
    try:
        with open(path, 'rb') as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - n))
            return f.read().decode('utf-8', 'replace')
    except Exception:
        return ''


def parse_time(s):
    """ISO timestamp -> aware datetime, or None when unparseable."""
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s).replace('Z', '+00:00'))
    except (TypeError, ValueError):
        return None


def last_request_time(tail):
    """Timestamp of the latest API call recorded in the transcript tail."""
    for line in reversed(tail.splitlines()):
        if re.search(r'"usage"\s*:\s*\{\s*"input_tokens"', line):
            m = re.search(r'"timestamp"\s*:\s*"([^"]+)"', line)
            if m:
                try:
                    return datetime.fromisoformat(m.group(1).replace('Z', '+00:00'))
                except ValueError:
                    break
    return datetime.now(timezone.utc)


def last_permission_mode(tail):
    """Latest permission mode recorded in the transcript tail (None if absent)."""
    mode = None
    for m in re.finditer(r'"permissionMode"\s*:\s*"([^"]+)"', tail):
        mode = m.group(1)
    return mode


def price_period(dt):
    t = dt.astimezone(CST)
    if t.weekday() < 5 and (9 <= t.hour < 12 or 14 <= t.hour < 18):
        return 'peak'
    return 'idle'


def iter_lines_reverse(path, chunk=256 * 1024):
    """Yield a file's lines from the last one backwards.

    Runs of lines are read in fixed-size blocks; the head of each block is
    kept as `pending` and glued to the block before it, so no line is cut.
    """
    with open(path, 'rb') as f:
        f.seek(0, 2)
        pos = f.tell()
        pending = b''
        while pos > 0:
            step = min(chunk, pos)
            pos -= step
            f.seek(pos)
            parts = (f.read(step) + pending).split(b'\n')
            pending = parts[0]
            for line in reversed(parts[1:]):
                yield line
        if pending:
            yield pending


def is_real_prompt(entry):
    """True for a prompt the human typed.

    Skips tool results, meta notes, compaction summaries and subagent
    sidechains, so only top-level prompts start a round.
    """
    if entry.get('isMeta') or entry.get('isSidechain') or entry.get('isCompactSummary'):
        return False
    content = (entry.get('message') or {}).get('content')
    if isinstance(content, str):
        return bool(content.strip())
    if isinstance(content, list):
        return any(isinstance(b, dict) and b.get('type') in ('text', 'image')
                   for b in content)
    return False


def round_usage(path):
    """Usage of the latest round: one human prompt through the final answer.

    In bypass mode a single round makes many API calls (one per tool-use
    step), and the transcript repeats each call once per content block, so
    calls are de-duplicated by message.id. The scan runs backwards from the
    newest line and stops at the prompt that opened the round; a prompt sent
    but not answered yet (no calls after it) falls through to the round
    before it. Returns [(time, input, cache_write, cache_read, output), ...]
    or None when no round boundary is found.
    """
    if not path:
        return None
    calls = []
    seen = set()
    found_prompt = False
    try:
        for raw in iter_lines_reverse(path):
            if RE_ASSISTANT.search(raw):
                try:
                    entry = json.loads(raw)
                except ValueError:
                    continue
                if entry.get('type') != 'assistant':
                    continue
                message = entry.get('message') or {}
                usage = message.get('usage') or {}
                mid = message.get('id')
                if not usage or (mid and mid in seen):
                    continue
                if mid:
                    seen.add(mid)
                calls.append((
                    parse_time(entry.get('timestamp')),
                    int(usage.get('input_tokens') or 0),
                    int(usage.get('cache_creation_input_tokens') or 0),
                    int(usage.get('cache_read_input_tokens') or 0),
                    int(usage.get('output_tokens') or 0),
                ))
            elif RE_USER.search(raw):
                if RE_TOOL_RESULT.search(raw):
                    continue
                try:
                    entry = json.loads(raw)
                except ValueError:
                    continue
                if entry.get('type') != 'user' or not is_real_prompt(entry):
                    continue
                if calls:
                    found_prompt = True
                    break
                # Prompt sent, no API call yet: fall back to the round before it.
                calls = []
                seen = set()
    except OSError:
        return None
    return calls if found_prompt and calls else None


def disp_width(s):
    """Terminal columns; CJK wide chars count 2."""
    w = 0
    for ch in s:
        if unicodedata.combining(ch):
            continue
        w += 2 if unicodedata.east_asian_width(ch) in ('W', 'F') else 1
    return w


def print_box(lines):
    inner = max(disp_width(x) for x in lines)
    print('┏' + '━' * (inner + 2) + '┓')
    for x in lines:
        print('┃ ' + x + ' ' * (inner - disp_width(x)) + ' ┃')
    print('┗' + '━' * (inner + 2) + '┛')


transcript = data.get('transcript_path')
tail = read_tail(transcript)
calls = round_usage(transcript)

# Line 1: working directory + model
ws = data.get('workspace') or {}
cwd = ws.get('current_dir') or data.get('cwd') or '?'
home = os.path.expanduser('~')
if home and cwd.lower().startswith(home.lower()):
    cwd = '~' + cwd[len(home):].replace('\\', '/')

m = data.get('model') or {}
model = m.get('display_name') or m.get('id') or 'unknown'
lines = [f'目录: {cwd} | 模型: {model}']

# Line 2: free space | round tokens (fallback: last API call when the
# transcript is unreadable or has no round boundary yet)
segments = []
cw = data.get('context_window') or {}

free_pct = cw.get('remaining_percentage')
if free_pct is None and cw.get('used_percentage') is not None:
    try:
        free_pct = 100 - float(cw['used_percentage'])
    except (TypeError, ValueError):
        free_pct = None
if free_pct is not None:
    try:
        free_pct = float(free_pct)
        size = float(cw.get('context_window_size') or 0)
        free_tokens = round(size * free_pct / 100)
        segments.append(f'Free space: {fmt_tokens(free_tokens)} ({free_pct:.1f}%)' if size
                        else f'Free space: {free_pct:.1f}%')
    except (TypeError, ValueError):
        free_pct = None

usage = cw.get('current_usage') or {}
if calls:
    u_in = sum(c[1] for c in calls)
    u_cw = sum(c[2] for c in calls)
    u_cr = sum(c[3] for c in calls)
    u_out = sum(c[4] for c in calls)
else:
    u_in = int(usage.get('input_tokens') or 0)
    u_cw = int(usage.get('cache_creation_input_tokens') or 0)
    u_cr = int(usage.get('cache_read_input_tokens') or 0)
    u_out = int(usage.get('output_tokens') or 0)
usage_ok = bool(u_in or u_cw or u_cr or u_out)

rates = None
label = ''
hit_cost = miss_cost = out_cost = 0.0

if usage_ok:
    segments.append(f'上一轮: 出 {fmt_tokens(u_out)} · 入 {fmt_tokens(u_in + u_cw + u_cr)}')

    base = re.sub(r'\[[^\]]*\]$', '', (m.get('id') or model or '')).strip()
    rates = PRICES.get(ALIASES.get(base, base))
    if rates:
        if calls:
            # Price every call at the period it was made in; a round that
            # straddles the peak boundary cannot carry a single label.
            periods = set()
            for ts, c_in, c_cw, c_cr, c_out in calls:
                period = price_period(ts or datetime.now(timezone.utc))
                periods.add(period)
                hit_p, miss_p, out_p = rates[period]
                hit_cost += c_cr * hit_p / 1_000_000.0
                miss_cost += (c_in + c_cw) * miss_p / 1_000_000.0
                out_cost += c_out * out_p / 1_000_000.0
            if len(periods) == 1:
                label = '高峰价' if 'peak' in periods else '空闲价'
            else:
                label = '跨时段'
        else:
            period = price_period(last_request_time(tail))
            hit_p, miss_p, out_p = rates[period]
            hit_cost = u_cr * hit_p / 1_000_000.0
            miss_cost = (u_in + u_cw) * miss_p / 1_000_000.0
            out_cost = u_out * out_p / 1_000_000.0
            label = '高峰价' if period == 'peak' else '空闲价'

if segments:
    lines.append(' | '.join(segments))

# Line 3: total cost and its split by output / cache hit / cache miss
if usage_ok and rates:
    total = hit_cost + miss_cost + out_cost
    if total > 0:
        p_out = round(out_cost / total * 100, 1)
        p_hit = round(hit_cost / total * 100, 1)
        p_miss = round(100 - p_out - p_hit, 1)
    else:
        p_out = p_hit = p_miss = 0.0
    lines.append(f'总费用: {fmt_cost(total)}（{label}） | '
                 f'输出占比: {p_out:.1f}% | 输入命中占比: {p_hit:.1f}% | 输入未命中占比: {p_miss:.1f}%')

# Line 4: permission mode (the built-in bypass footer cannot be moved inside)
mode = last_permission_mode(tail)
if mode:
    lines.append(f'权限模式: {mode}')

print_box(lines)
