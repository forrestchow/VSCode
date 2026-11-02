# CDP Patterns

Assume a page-level WebSocket or a `CDP` helper with `send(method, params, session_id)`.

## 1. Cross-origin iframe

```python
tree = await cdp.send("Page.getFrameTree")
frame = find_frame(tree, "havanalogin.taobao.com")  # walk childFrames, match URL
world = await cdp.send("Page.createIsolatedWorld", {
    "frameId": frame["id"],
    "worldName": "dom-probe",
})
ctx = world["executionContextId"]

res = await cdp.send("Runtime.evaluate", {
    "expression": """
      JSON.stringify({
        inputs: [...document.querySelectorAll('input')].map(el => ({
          id: el.id, name: el.name, type: el.type,
          placeholder: el.placeholder, visible: el.checkVisibility()
        })),
        buttons: [...document.querySelectorAll('button, [role=button]')]
          .map(el => ({text: el.innerText.trim(), id: el.id, cls: el.className})),
      })
    """,
    "contextId": ctx,
    "returnByValue": True,
})
```

- If the iframe is an OOPIF, use `Target.setAutoAttach` with `autoAttach=True, waitForDebuggerOnStart=True, flatten=True`; attach to the iframe target's session and evaluate there.
- Re-acquire the execution context after any navigation.
- `Page.createIsolatedWorld` is enough for same-process cross-origin frames; OOPIF needs target attach.

## 2. Shadow DOM

Walk hosts breadth-first:

```js
function collectRoots(root, out = []) {
  out.push(root);
  for (const el of root.querySelectorAll('*')) {
    if (el.shadowRoot) collectRoots(el.shadowRoot, out);
  }
  return out;
}
```

- Closed shadow roots are not reachable via `el.shadowRoot`. Use CDP `DOM.getDocument({depth: -1, pierce: true})`, walk `shadowRoots`, then `DOM.resolveNode` to get an objectId.
- IDs are scoped per root: `document.querySelector('#save')` will not find a button inside a shadow root.
- For composed hit-testing, prefer `elementsFromPoint` and check the composed ancestry, not just `elementFromPoint`.

## 3. Actionability

```js
const rect = el.getBoundingClientRect();
const style = getComputedStyle(el);
const visible = el.checkVisibility({checkOpacity: true, checkVisibilityCSS: true});
const inViewport = rect.width > 0 && rect.height > 0;
const enabled = !el.disabled && !el.closest('[inert]') &&
  el.getAttribute('aria-disabled') !== 'true';
const hit = document.elementFromPoint(rect.left + rect.width / 2, rect.top + rect.height / 2);
const clickable = visible && inViewport && enabled &&
  style.pointerEvents !== 'none' &&
  (hit === el || el.contains(hit));
```

- Also check `getClientRects().length > 0`, ancestor `overflow` clipping, and overlay elements via `elementsFromPoint`.
- `scrollIntoView({block: 'center'})`, await a frame, then re-read the rect.
- For iframe elements, coordinates from `getBoundingClientRect()` are relative to the iframe viewport; add the iframe's offset in the parent page, or use `DOM.getContentQuads` on the iframe target.

## 4. Click

```python
await cdp.send("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y})
await cdp.send("Input.dispatchMouseEvent", {
    "type": "mousePressed", "x": x, "y": y, "button": "left", "clickCount": 1,
})
await cdp.send("Input.dispatchMouseEvent", {
    "type": "mouseReleased", "x": x, "y": y, "button": "left", "clickCount": 1,
})
```

- Prefer real mouse events over `el.click()` when the UI checks `event.isTrusted`, hover state, or pointer events.
- For hover menus: `mouseMoved` to the trigger, wait for the submenu's network/DOM signal, then click.
- Re-check `isConnected` and visibility immediately before dispatch; re-render can invalidate the element.

## 5. Typing

```python
await cdp.send("Runtime.evaluate", {
    "expression": "document.querySelector('#fm-login-id').focus()",
    "contextId": ctx,
})
await cdp.send("Input.insertText", {"text": value})
```

For React/Vue controlled inputs, the native setter is more reliable:

```js
const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
setter.call(el, value);
el.dispatchEvent(new Event('input', {bubbles: true}));
el.dispatchEvent(new Event('change', {bubbles: true}));
```

- Verify by reading back `el.value` and checking the framework's state.
- For IME composition, use `Input.imeSetComposition`; for search boxes with debounce, wait for the specific search request.

## 6. Virtual list

- Find the scroll container: walk ancestors for `overflow: auto|scroll` and `scrollHeight > clientHeight`.
- Get the target's data index from the network response; set `scrollTop = index * rowHeight` (or call the virtualizer's `scrollToIndex` if exposed).
- For variable row heights, use the virtualizer API or binary-search the scroll position.
- After each scroll, await two `requestAnimationFrame`s.
- In the same `Runtime.evaluate`, re-query the row by key, verify its text, `scrollIntoView`, get the rect/center, and return coordinates. Click immediately; virtual lists recycle nodes.

## 7. Success signals

- Enable `Network` before the action. Filter `Network.requestWillBeSent` / `Network.responseReceived` by URL, method, and params (e.g., `skuId`).
- After `Network.loadingFinished`, call `Network.getResponseBody({requestId})`; handle `base64Encoded`.
- Non-network actions: `Page.frameNavigated`, URL change, attribute/class/text change, toast, row count, value change.
- Always add a timeout and negative signals (error toast, `code != 0`, failed request).

## 8. Chrome password manager

The password manager bubble is browser UI. CDP `Input` events go to the renderer; they cannot select a saved credential. Options:

- manual click once;
- Chrome auto sign-in setting;
- OS-level UI automation (pyautogui / Windows UIAutomation / SendKeys).

Do not treat it as DOM, and do not attempt to read or export saved passwords.
