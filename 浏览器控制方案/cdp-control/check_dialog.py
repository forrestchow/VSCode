"""Handle browser native dialog and check page state."""
import asyncio, json, websockets, sys, io, urllib.request
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

pages = json.loads(urllib.request.urlopen('http://127.0.0.1:9222/json').read())
target = None
for p in pages:
    if p['type'] == 'page' and 'localhost:3000/question' in p.get('url',''):
        target = p
        break

WS = target['webSocketDebuggerUrl']
print('Connecting to: ' + target['url'][:120])

async def main():
    async with websockets.connect(WS, max_size=20*1024*1024) as ws:
        # Enable Page first to catch dialog events
        await ws.send(json.dumps({'id': 1, 'method': 'Page.enable'}))

        msgs = []
        for _ in range(5):
            try:
                r = await asyncio.wait_for(ws.recv(), timeout=2)
                msgs.append(json.loads(r))
            except asyncio.TimeoutError:
                break

        # Check if there's a dialog already open
        has_dialog = False
        for d in msgs:
            if d.get('method') == 'Page.javascriptDialogOpening':
                has_dialog = True
                dialog_type = d['params']['type']
                dialog_msg = d['params']['message']
                print('DIALOG FOUND: type=' + dialog_type + ' msg=' + str(dialog_msg)[:200])

        if not has_dialog:
            print('No active dialog detected. Checking page state...')
        else:
            # Dismiss the dialog
            print('Dismissing dialog...')
            await ws.send(json.dumps({
                'id': 2,
                'method': 'Page.handleJavaScriptDialog',
                'params': {'accept': False}
            }))
            for _ in range(5):
                try:
                    r = await asyncio.wait_for(ws.recv(), timeout=2)
                    d = json.loads(r)
                    if d.get('id') == 2:
                        print('Dialog dismissed: ' + str(d))
                        break
                except asyncio.TimeoutError:
                    break

        # Now enable Runtime and check state
        await ws.send(json.dumps({'id': 5, 'method': 'Runtime.enable'}))
        for _ in range(5):
            try:
                r = await asyncio.wait_for(ws.recv(), timeout=1)
                if json.loads(r).get('id') == 5:
                    break
            except asyncio.TimeoutError:
                break

        # Remove beforeunload handler
        await ws.send(json.dumps({
            'id': 10, 'method': 'Runtime.evaluate',
            'params': {
                'expression': 'window.onbeforeunload = null; "cleared"',
                'returnByValue': True
            }
        }))
        for _ in range(5):
            try:
                r = await asyncio.wait_for(ws.recv(), timeout=2)
                d = json.loads(r)
                if d.get('id') == 10:
                    print('beforeunload cleared: ' + str(d.get('result',{}).get('result',{}).get('value','?')))
                    break
            except asyncio.TimeoutError:
                break

        # Check page state
        checks = [
            ('Title', 'document.title'),
            ('URL', 'location.href'),
            ('Body class', 'document.body.className'),
            ('Has dark overlay', '''(() => {
                // Check for Metabase modal overlay
                const el = document.querySelector('[data-testid="save-question-modal"], [role="dialog"], .Modal');
                if (el && window.getComputedStyle(el).display !== "none") {
                    return "YES - " + (el.getAttribute("data-testid") || el.getAttribute("role") || el.className.substring(0,60));
                }
                // Check for mantine overlay
                const o = document.querySelector('.mantine-Modal-root, .mantine-Overlay-root');
                if (o) return "YES - mantine overlay";
                return "NO overlay";
            })()'''),
            ('beforeunload', 'window.onbeforeunload ? "ACTIVE" : "none"'),
            ('Visible buttons', '''JSON.stringify(
                Array.from(document.querySelectorAll("button"))
                    .filter(b => b.offsetParent !== null)
                    .map(b => ({
                        t: (b.textContent||"").trim().substring(0,60),
                        d: b.disabled,
                        m: !!b.closest('[role="dialog"]')
                    }))
            )'''),
        ]

        for i, (label, expr) in enumerate(checks):
            await ws.send(json.dumps({
                'id': 20+i, 'method': 'Runtime.evaluate',
                'params': {'expression': expr, 'returnByValue': True}
            }))
            for _ in range(5):
                try:
                    r = await asyncio.wait_for(ws.recv(), timeout=2)
                    d = json.loads(r)
                    if d.get('id') == 20+i:
                        val = d.get('result',{}).get('result',{}).get('value','?')
                        print(label + ': ' + str(val)[:500])
                        break
                except asyncio.TimeoutError:
                    break

asyncio.run(main())
