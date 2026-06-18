"""Connect to Metabase page, find Save button, monitor console errors."""
import asyncio, json, websockets, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# First find the right page
import urllib.request
pages = json.loads(urllib.request.urlopen('http://127.0.0.1:9222/json').read())
target = None
for p in pages:
    if p['type'] == 'page' and 'localhost:3000/question' in p.get('url', ''):
        target = p
        print(f"Found page: {p['title']}")
        print(f"URL: {p['url'][:100]}")
        break

if not target:
    print("No Metabase question page found!")
    sys.exit(1)

WS_URL = target['webSocketDebuggerUrl']
print(f"WS: {WS_URL[:80]}...")

async def send_and_wait(ws, msg_id, payload, timeout=5):
    """Send a command and wait for its response."""
    await ws.send(json.dumps({'id': msg_id, **payload}))
    for _ in range(30):
        try:
            r = await asyncio.wait_for(ws.recv(), timeout=timeout)
            d = json.loads(r)
            # Log console messages as we see them
            if d.get('method') == 'Log.entryAdded':
                entry = d.get('params', {}).get('entry', {})
                level = entry.get('level', 'info')
                text = ''
                for line in entry.get('lines', []):
                    text += line.get('text', '')
                if level in ('error', 'warning'):
                    print(f'  [CONSOLE {level.upper()}] {text[:200]}')
            if d.get('id') == msg_id:
                return d
        except asyncio.TimeoutError:
            print(f'  [TIMEOUT waiting for id={msg_id}]')
            return None
    return None

async def main():
    async with websockets.connect(WS_URL, max_size=20*1024*1024) as ws:
        # Enable Log (for console monitoring) and Runtime
        r = await send_and_wait(ws, 1, {'method': 'Runtime.enable'})
        r = await send_and_wait(ws, 2, {'method': 'Log.enable'})

        print("\n=== Page State ===")
        r = await send_and_wait(ws, 10, {
            'method': 'Runtime.evaluate',
            'params': {'expression': 'document.title', 'returnByValue': True}
        })
        if r:
            print(f'Title: {r.get("result",{}).get("result",{}).get("value","?")}')

        # Find ALL visible buttons
        r = await send_and_wait(ws, 11, {
            'method': 'Runtime.evaluate',
            'params': {
                'expression': '''(() => {
                    return JSON.stringify(
                        Array.from(document.querySelectorAll('button'))
                            .filter(b => b.offsetParent !== null)
                            .map(b => ({
                                text: (b.textContent || '').trim().substring(0, 100),
                                disabled: b.disabled,
                                testid: b.getAttribute('data-testid') || '',
                                classes: (b.className || '').substring(0, 60)
                            }))
                    );
                })()''',
                'returnByValue': True
            }
        })
        if r:
            buttons = json.loads(r['result']['result']['value'])
            print(f'\nVisible buttons ({len(buttons)}):')
            for i, b in enumerate(buttons):
                s = '[D]' if b['disabled'] else '[ ]'
                print(f'  [{i}] {s} testid={b["testid"]:30s} "{b["text"]}"')

        # Find modal content
        r = await send_and_wait(ws, 12, {
            'method': 'Runtime.evaluate',
            'params': {
                'expression': '''(() => {
                    // Find modal - Metabase uses specific patterns
                    const selectors = [
                        '[role="dialog"]', '[role="alertdialog"]',
                        '[data-testid="save-question-modal"]',
                        '.Modal', '[aria-modal="true"]',
                        '.emotion-1v3gouc', '.emotion-1udg5zl'
                    ];
                    for (const sel of selectors) {
                        const el = document.querySelector(sel);
                        if (el && window.getComputedStyle(el).display !== 'none') {
                            // Get all buttons inside
                            const btns = el.querySelectorAll('button');
                            const btnTexts = Array.from(btns).map(b => ({
                                text: (b.textContent||'').trim(),
                                disabled: b.disabled,
                                testid: b.getAttribute('data-testid')||''
                            }));
                            return JSON.stringify({
                                selector: sel,
                                text: (el.textContent || '').trim().substring(0, 500),
                                buttons: btnTexts
                            });
                        }
                    }
                    return JSON.stringify({found: false});
                })()''',
                'returnByValue': True
            }
        })
        if r:
            modal = json.loads(r['result']['result']['value'])
            print(f'\n=== Modal ===')
            print(json.dumps(modal, indent=2, ensure_ascii=False))

        # Now try to click Save/Replace button
        print('\n=== Attempting Save ===')
        r = await send_and_wait(ws, 20, {
            'method': 'Runtime.evaluate',
            'params': {
                'expression': '''(() => {
                    const btns = document.querySelectorAll('button');
                    for (const b of btns) {
                        const t = (b.textContent||'').trim();
                        if ((t.includes('Save') || t.includes('Replace') ||
                             t.includes('保存') || t.includes('替换')) &&
                            !b.disabled && b.offsetParent !== null) {
                            b.click();
                            return JSON.stringify({clicked: true, text: t});
                        }
                    }
                    return JSON.stringify({clicked: false, reason: 'no matching button'});
                })()''',
                'returnByValue': True
            }
        })
        if r:
            result = json.loads(r['result']['result']['value'])
            print(f'Click result: {result}')

        # Wait and collect console messages
        print('\n=== Console Messages (waiting 5s) ===')
        for _ in range(30):
            try:
                r = await asyncio.wait_for(ws.recv(), timeout=5)
                d = json.loads(r)
                if d.get('method') == 'Log.entryAdded':
                    entry = d['params']['entry']
                    level = entry.get('level', 'info')
                    text = ''.join(line.get('text', '') for line in entry.get('lines', []))
                    print(f'  [{level.upper()}] {text[:300]}')
                elif d.get('method') == 'Runtime.consoleAPICalled':
                    ctype = d['params']['type']
                    text = ''.join(str(a.get('value','')) for a in d['params']['args'])
                    print(f'  [CONSOLE.{ctype}] {text[:300]}')
                # Also catch network errors
                elif d.get('method') == 'Network.responseReceived':
                    resp = d['params']['response']
                    if resp.get('status', 200) >= 400:
                        print(f'  [NETWORK {resp["status"]}] {resp["url"][:200]}')
            except asyncio.TimeoutError:
                print('  (no more messages)')
                break

        # Check if error toast appeared
        r = await send_and_wait(ws, 30, {
            'method': 'Runtime.evaluate',
            'params': {
                'expression': '''(() => {
                    const toasts = document.querySelectorAll('[role="status"], [role="alert"], .Toast, .toast, [data-testid="toast"]');
                    return JSON.stringify(
                        Array.from(toasts).map(t => ({
                            text: (t.textContent||'').trim().substring(0, 300),
                            visible: t.offsetParent !== null
                        }))
                    );
                })()''',
                'returnByValue': True
            }
        })
        if r:
            toasts = json.loads(r['result']['result']['value'])
            print(f'\n=== Toast messages ===')
            for t in toasts:
                print(f'  [{t["visible"]}] {t["text"]}')

asyncio.run(main())
