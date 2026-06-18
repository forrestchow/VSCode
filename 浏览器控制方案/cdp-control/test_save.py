"""Toggle show_values, save, and capture errors."""
import asyncio, json, websockets, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

WS = 'ws://127.0.0.1:9222/devtools/page/857A49194A5A937E76C1D4FD5948078D'

async def main():
    async with websockets.connect(WS, max_size=10*1024*1024) as ws:
        await ws.send(json.dumps({'id':1,'method':'Runtime.enable'}))
        await ws.send(json.dumps({'id':2,'method':'Log.enable'}))
        await ws.send(json.dumps({'id':3,'method':'Network.enable'}))
        for _ in range(8):
            try:
                r = await asyncio.wait_for(ws.recv(), timeout=1)
                d = json.loads(r)
                if d.get('id') == 3: break
            except: break

        # Toggle show_values
        await ws.send(json.dumps({
            'id': 20, 'method': 'Runtime.evaluate',
            'params': {
                'expression': """
(() => {
    const all = document.querySelectorAll('*');
    for (const el of all) {
        if (el.textContent === 'Show values on data points' && el.offsetParent !== null) {
            const toggle = el.closest('label')?.querySelector('input[type="checkbox"]');
            if (toggle) { toggle.click(); return 'toggled'; }
            el.click(); return 'clicked text';
        }
    }
    return 'not found';
})()
""",
                'returnByValue': True
            }
        }))
        for _ in range(5):
            try:
                r = await asyncio.wait_for(ws.recv(), timeout=1)
                d = json.loads(r)
                if d.get('id') == 20:
                    print('Toggle:', d['result']['result']['value'])
                    break
            except: break

        await asyncio.sleep(1)

        # Click Save button in header
        await ws.send(json.dumps({
            'id': 30, 'method': 'Runtime.evaluate',
            'params': {
                'expression': """
(() => {
    const btns = Array.from(document.querySelectorAll('button'));
    for (const b of btns) {
        if (b.textContent.trim() === 'Save' && !b.disabled && b.offsetParent !== null) {
            b.click(); return 'clicked Save';
        }
    }
    const all = Array.from(document.querySelectorAll('button'))
        .filter(b => b.offsetParent !== null)
        .map(b => b.textContent.trim());
    return 'no Save. Buttons: ' + all.join(', ');
})()
""",
                'returnByValue': True
            }
        }))
        for _ in range(5):
            try:
                r = await asyncio.wait_for(ws.recv(), timeout=1)
                d = json.loads(r)
                if d.get('id') == 30:
                    print('Save click:', d['result']['result']['value'])
                    break
            except: break

        await asyncio.sleep(1)

        # Check dialog state
        await ws.send(json.dumps({
            'id': 40, 'method': 'Runtime.evaluate',
            'params': {
                'expression': """
JSON.stringify({
    hasDialog: !!document.querySelector('[role="dialog"]'),
    saveDisabled: (() => {
        const d = document.querySelector('[role="dialog"]');
        if (!d) return 'no dlg';
        const b = Array.from(d.querySelectorAll('button'))
            .find(b => b.textContent.trim() === 'Save');
        return b ? b.disabled : 'no btn';
    })(),
    dialogText: (document.querySelector('[role="dialog"]')?.textContent || '').substring(0, 200)
})
""",
                'returnByValue': True
            }
        }))
        for _ in range(5):
            try:
                r = await asyncio.wait_for(ws.recv(), timeout=1)
                d = json.loads(r)
                if d.get('id') == 40:
                    print('Dialog:', d['result']['result']['value'])
                    break
            except: break

        # Click Save in dialog (if present and enabled)
        await ws.send(json.dumps({
            'id': 50, 'method': 'Runtime.evaluate',
            'params': {
                'expression': """
(() => {
    const d = document.querySelector('[role="dialog"]');
    if (!d) return 'no dlg';
    const b = Array.from(d.querySelectorAll('button'))
        .find(b => b.textContent.trim() === 'Save');
    if (!b) return 'no btn';
    if (b.disabled) return 'disabled';
    b.click();
    return 'clicked';
})()
""",
                'returnByValue': True
            }
        }))
        for _ in range(5):
            try:
                r = await asyncio.wait_for(ws.recv(), timeout=1)
                d = json.loads(r)
                if d.get('id') == 50:
                    print('Dialog Save:', d['result']['result']['value'])
                    break
            except: break

        # Monitor console + network for 5s
        await asyncio.sleep(3)
        print('\n=== Monitoring ===')
        for _ in range(20):
            try:
                r = await asyncio.wait_for(ws.recv(), timeout=3)
                d = json.loads(r)
                m = d.get('method', '')
                if m == 'Network.responseReceived':
                    resp = d['params']['response']
                    if '/api/card' in resp.get('url', ''):
                        print('NET %s: %s' % (resp['status'], resp['url'][:200]))
                elif m == 'Log.entryAdded':
                    lvl = d['params']['entry'].get('level', '')
                    txt = ''.join(l.get('text', '') for l in d['params']['entry'].get('lines', []))
                    if txt.strip() and lvl in ('error',):
                        print('ERR: ' + txt[:300])
                elif m == 'Runtime.consoleAPICalled':
                    txt = ' '.join(str(a.get('value', '')) for a in d['params']['args'])
                    if any(w in txt.lower() for w in ('error', 'fail', 'invalid', 'param')):
                        print('LOG: ' + txt[:300])
            except asyncio.TimeoutError:
                break

        # Final URL
        await ws.send(json.dumps({
            'id': 60, 'method': 'Runtime.evaluate',
            'params': {
                'expression': 'location.href.substring(0, 200)',
                'returnByValue': True
            }
        }))
        for _ in range(5):
            try:
                r = await asyncio.wait_for(ws.recv(), timeout=1)
                d = json.loads(r)
                if d.get('id') == 60:
                    print('\nFinal URL:', d['result']['result']['value'])
                    break
            except: break

asyncio.run(main())
