// background service worker — runs collection even when popup is closed
let isRunning = false;
let stopRequested = false;

function log(msg, type) {
  console.log(`[BG:${type||'info'}] ${msg}`);
  chrome.storage.local.get('__tb_logs').then(d => {
    const logs = (d.__tb_logs || []).slice(-199);
    logs.push({ msg, type: type || 'info', time: Date.now() });
    chrome.storage.local.set({ __tb_logs: logs });
  });
}

// JSON block extractor (same as popup.js)
function extractJsonBlock(text, key) {
  const idx = text.indexOf('"' + key + '"');
  if (idx === -1) return null;
  let start = text.indexOf(':', idx) + 1;
  while (start < text.length && /\s/.test(text[start])) start++;
  if (start >= text.length || (text[start] !== '{' && text[start] !== '[')) return null;
  const stack = [text[start]];
  let end = start + 1;
  while (end < text.length && stack.length > 0) {
    const c = text[end];
    if (c === '{' || c === '[') stack.push(c);
    else if (c === '}' || c === ']') {
      const last = stack.pop();
      if ((last === '{' && c !== '}') || (last === '[' && c !== ']')) return null;
    }
    end++;
  }
  try { return JSON.parse(text.substring(start, end)); } catch (_) { return null; }
}

function parseQuantity(name) {
  if (!name) return null;
  const combo = name.match(/(\d+)\s*袋\s*\+\s*[^\d]*(\d+)\s*袋/);
  if (combo) return parseInt(combo[1]) + parseInt(combo[2]);
  const direct = name.match(/(\d+)\s*(?:袋装|袋|包|件装|包装|瓶装|瓶)/);
  if (direct) return parseInt(direct[1]);
  const star = name.match(/\*\s*(\d+)\s*(?:袋|包|瓶)?/);
  if (star) return parseInt(star[1]);
  const wq = name.match(/g\s*(\d+)\s*(?:袋|包|瓶)/);
  if (wq) return parseInt(wq[1]);
  return null;
}

const SALES_DECAY = 0.65;
function estimateSalesPercentages(n) {
  if (n <= 1) return [100];
  const w = Array.from({length: n}, (_, i) => Math.pow(SALES_DECAY, i));
  const sum = w.reduce((a, b) => a + b, 0);
  return w.map(v => +((v / sum) * 100).toFixed(1));
}

function calcEstimatedAvgPrice(items) {
  if (!items || items.length === 0) return null;
  if (items.length === 1) return items[0].price;
  const sorted = [...items].sort((a, b) => (a.price || 0) - (b.price || 0));
  const pcts = estimateSalesPercentages(sorted.length);
  let ws = 0;
  for (let i = 0; i < sorted.length; i++) ws += (sorted[i].price || 0) * (pcts[i] / 100);
  return +ws.toFixed(2);
}

// fetch detail page data (same as popup.js fetchDetailData)
async function fetchDetailData(productUrl) {
  let html, resp;
  try {
    resp = await fetch(productUrl);
    html = await resp.text();
  } catch (e) {
    log(`fetch fail: ${e.message}`, 'error');
    return null;
  }
  const sizeKB = html.length / 1024;
  const isVerify = sizeKB < 20 || html.includes('login') || html.includes('captcha')
    || html.includes('verify') || !html.includes('sku2info');
  if (isVerify) {
    log(`verify block (${sizeKB.toFixed(1)}KB)`, 'warn');
    return { _verify: true, url: productUrl };
  }
  const skuBase = extractJsonBlock(html, 'skuBase');
  const skuCore = extractJsonBlock(html, 'skuCore');
  const indVO = extractJsonBlock(html, 'industryParamVO');
  if (!skuCore || !skuCore.sku2info) {
    log('no sku2info', 'error');
    return null;
  }
  const sku2info = skuCore.sku2info;
  const hasVariants = (skuBase && skuBase.skus && skuBase.skus.length > 0);
  const titleMatch = html.match(/<title[^>]*>([^<]*)<\/title>/i);
  const htmlTitle = titleMatch ? titleMatch[1].replace(/-tmall\.com天猫.*$/, '').replace(/-淘宝.*$/, '').trim() : '';
  const bodyMatch = html.match(/(\d+)\s*(?:袋装|袋|包|件装)/);
  const bodyQty = bodyMatch ? parseInt(bodyMatch[1]) : null;
  let items = [];

  if (hasVariants) {
    const vidToName = {};
    for (const prop of (skuBase.props || []))
      for (const val of (prop.values || [])) vidToName[val.vid] = val.name;
    const vidToSkuId = {};
    for (const sku of skuBase.skus) {
      const parts = sku.propPath.split(':');
      if (parts.length >= 2) vidToSkuId[parts[1]] = sku.skuId;
    }
    for (const [vid, name] of Object.entries(vidToName)) {
      const skuId = vidToSkuId[vid];
      if (!skuId) continue;
      const info = sku2info[skuId];
      if (!info) continue;
      const subPrice = info.subPrice ? parseFloat(info.subPrice.priceText) : null;
      const origPrice = info.price ? parseFloat(info.price.priceText) : null;
      if (subPrice == null && origPrice == null) continue;
      const price = subPrice != null ? subPrice : origPrice;
      const qty = parseQuantity(name) || parseQuantity(htmlTitle) || bodyQty || 1;
      items.push({ name, price, priceOriginal: origPrice || price, quantity: qty, unitPrice: (qty && price) ? +(price / qty).toFixed(2) : null });
    }
  } else if (sku2info['0']) {
    const info = sku2info['0'];
    const price = info.subPrice ? parseFloat(info.subPrice.priceText) : (info.price ? parseFloat(info.price.priceText) : null);
    const priceOriginal = info.price ? parseFloat(info.price.priceText) : null;
    const label = info.subPrice ? info.subPrice.priceTitle : '价格';
    const qty = parseQuantity(label) || parseQuantity(htmlTitle) || bodyQty || 1;
    items.push({ name: label || '当前价格', price, priceOriginal, quantity: qty, unitPrice: (qty && price) ? +(price / qty).toFixed(2) : null });
  }
  if (items.length === 0) return null;

  const estimatedAvgPrice = calcEstimatedAvgPrice(items);
  const productAttrs = {};
  if (indVO) {
    for (const list of [...(indVO.enhanceParamList || []), ...(indVO.basicParamList || [])])
      if (list.propertyName && list.valueName) productAttrs[list.propertyName] = list.valueName;
  }
  const priceResult = sku2info['0']
    ? { price: parseFloat(sku2info['0'].subPrice ? sku2info['0'].subPrice.priceText : sku2info['0'].price.priceText) }
    : null;
  return { price: priceResult, skuPrices: [{ groupLabel: '规格', items, estimatedAvgPrice, productAttrs }] };
}

// search via background tab
async function fetchSearchAPI(keyword, page) {
  const url = `https://s.taobao.com/search?page=${page}&q=${encodeURIComponent(keyword)}&sort=sale-desc`;
  log(`search page ${page}: ${keyword}`, 'info');
  let tab;
  try { tab = await chrome.tabs.create({ url, active: false }); } catch (e) {
    log(`tab error: ${e.message}`, 'error'); return [];
  }
  await new Promise((resolve) => {
    const listener = (id, info) => {
      if (id === tab.id && info.status === 'complete') {
        chrome.tabs.onUpdated.removeListener(listener);
        setTimeout(resolve, 2000);
      }
    };
    setTimeout(() => { chrome.tabs.onUpdated.removeListener(listener); resolve(); }, 25000);
    chrome.tabs.onUpdated.addListener(listener);
  });
  log('tab loaded, scraping...', 'info');
  let items = [];
  for (let retry = 0; retry < 3; retry++) {
    try {
      const resp = await chrome.tabs.sendMessage(tab.id, { action: 'click_sort_and_scrape' });
      if (resp && resp.items && resp.items.length > 0) { items = resp.items; break; }
    } catch (e) { log(`retry ${retry + 1}: ${e.message}`, 'warn'); }
    await new Promise(r => setTimeout(r, 1500));
  }
  try { await chrome.tabs.remove(tab.id); } catch (_) {}
  log(`got ${items.length} items`, items.length > 0 ? 'success' : 'error');
  return items;
}

// main collection loop
async function runCollection(keywords, autoPage, minSales, delay, maxCount) {
  if (isRunning) { log('already running', 'warn'); return; }
  isRunning = true;
  stopRequested = false;

  let items = [];
  const saved = await chrome.storage.local.get('__tb_last_results');
  if (saved.__tb_last_results && saved.__tb_last_results.items) items = saved.__tb_last_results.items;

  for (let ki = 0; ki < keywords.length && !stopRequested; ki++) {
    const kw = keywords[ki];
    log(`--- keyword ${ki+1}/${keywords.length}: ${kw} ---`, 'info');
    let page = 1;
    while (!stopRequested) {
      const pageItems = await fetchSearchAPI(kw, page);
      if (pageItems.length === 0) break;
      const minOnPage = Math.min(...pageItems.map(i => i.salesNum));
      // dedup
      const existingIds = new Set(items.map(i => i.productUrl));
      for (const item of pageItems) {
        if (existingIds.has(item.productUrl)) continue;
        existingIds.add(item.productUrl);
        items.push(item);
      }
      items.sort((a, b) => b.salesNum - a.salesNum);
      await chrome.storage.local.set({ __tb_last_results: { items, total: items.length } });

      // detail extraction
      const pending = items.filter(i => i.productUrl && !i._detailDone);
      const count = maxCount > 0 ? Math.min(pending.length, maxCount) : pending.length;
      for (let i = 0; i < count && !stopRequested; i++) {
        const item = pending[i];
        const idx = items.indexOf(item);
        log(`[${i+1}/${count}] ${item.title?.substring(0,20)}`, 'info');
        chrome.storage.local.set({ __tb_progress: { current: i + 1, total: count } });

        const result = await fetchDetailData(item.productUrl);
        if (result && result._verify) {
          log(`verify needed: ${item.title}`, 'warn');
          chrome.storage.local.set({ __tb_verify: { url: item.productUrl, index: idx } });
          isRunning = false;
          return;
        }
        if (result && result.price) {
          items[idx].detailPrice = result.price.price;
          if (result.skuPrices && result.skuPrices.length > 0) {
            items[idx].skuPrices = result.skuPrices;
            const g = result.skuPrices[0];
            if (g.estimatedAvgPrice != null) items[idx].detailPrice = g.estimatedAvgPrice;
            if (g.productAttrs) log(`brand: ${g.productAttrs['品牌']||'-'} salt: ${g.productAttrs['食盐种类']||'-'}`, 'info');
          }
          items[idx]._detailDone = true;
        }
        await chrome.storage.local.set({ __tb_last_results: { items, total: items.length } });
        if (i < count - 1) await new Promise(r => setTimeout(r, delay + (Math.random() - 0.5) * 1000));
      }
      if (!autoPage) break;
      if (minSales > 0 && minOnPage < minSales) break;
      if (page >= 100) break;
      page++;
    }
  }
  isRunning = false;
  chrome.storage.local.set({ __tb_progress: null });
  log('collection done', 'success');
}

// resume detail extraction from saved items (after verification fix)
async function continueFromSaved(delay, maxCount) {
  if (isRunning) { log('already running', 'warn'); return; }
  isRunning = true;
  stopRequested = false;
  const saved = await chrome.storage.local.get('__tb_last_results');
  const items = (saved.__tb_last_results && saved.__tb_last_results.items) ? saved.__tb_last_results.items : [];
  const pending = items.filter(i => i.productUrl && !i._detailDone);
  const count = maxCount > 0 ? Math.min(pending.length, maxCount) : pending.length;
  log(`resume: ${count} pending details`, 'info');

  for (let i = 0; i < count && !stopRequested; i++) {
    const item = pending[i];
    const idx = items.indexOf(item);
    log(`[${i+1}/${count}] ${item.title?.substring(0,20)}`, 'info');
    chrome.storage.local.set({ __tb_progress: { current: i + 1, total: count } });

    const result = await fetchDetailData(item.productUrl);
    if (result && result._verify) {
      log(`verify needed: ${item.title}`, 'warn');
      chrome.storage.local.set({ __tb_verify: { url: item.productUrl, index: idx } });
      isRunning = false;
      return;
    }
    if (result && result.price) {
      items[idx].detailPrice = result.price.price;
      if (result.skuPrices && result.skuPrices.length > 0) {
        items[idx].skuPrices = result.skuPrices;
        const g = result.skuPrices[0];
        if (g.estimatedAvgPrice != null) items[idx].detailPrice = g.estimatedAvgPrice;
        if (g.productAttrs) log(`brand: ${g.productAttrs['品牌']||'-'} salt: ${g.productAttrs['食盐种类']||'-'}`, 'info');
      }
      items[idx]._detailDone = true;
    }
    await chrome.storage.local.set({ __tb_last_results: { items, total: items.length } });
    if (i < count - 1) await new Promise(r => setTimeout(r, delay + (Math.random() - 0.5) * 1000));
  }
  isRunning = false;
  chrome.storage.local.set({ __tb_progress: null });
  log('resume done', 'success');
}

// listen for popup messages
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'start') {
    runCollection(request.keywords, request.autoPage, request.minSales, request.delay, request.maxCount);
    sendResponse({ ok: true });
  }
  if (request.action === 'stop') {
    stopRequested = true;
    isRunning = false;
    sendResponse({ ok: true });
  }
  if (request.action === 'status') {
    sendResponse({ isRunning, stopRequested });
  }
  if (request.action === 'resume') {
    chrome.storage.local.remove('__tb_verify');
    // continue from current items without re-searching
    continueFromSaved(request.delay, request.maxCount);
    sendResponse({ ok: true });
  }
});
