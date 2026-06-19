'use strict';

// detail page price extraction for taobao/tmall product pages

const diag = {
  logs: [],
  log(msg) { this.logs.push(`[${new Date().toLocaleTimeString()}] ${msg}`); console.log('[详情采集]', msg); },
};

// extract price from block2--MLcO9YdF, pick the lower price
function extractPrice() {
  const block = document.querySelector('.block2--MLcO9YdF');
  if (!block) {
    diag.log('未找到 block2--MLcO9YdF 容器');
    return null;
  }

  // find price containers (highlightPrice and subPrice) within block2
  // the ￥ and number are in separate spans, so we query the parent containers
  const priceContainers = [
    ...block.querySelectorAll('[class*="highlightPrice"]'),
    ...block.querySelectorAll('[class*="subPrice"]'),
  ];

  diag.log(`在 block2 内找到 ${priceContainers.length} 个价格容器`);

  if (priceContainers.length === 0) {
    diag.log('未找到价格容器');
    return null;
  }

  // extract price from each container, pick the lower price
  let best = null;
  let bestPrice = Infinity;

  for (const container of priceContainers) {
    const fullText = container.textContent.trim();
    const match = fullText.match(/￥\s*(\d+\.?\d*)/);
    if (!match) {
      diag.log(`  跳过: 未找到价格数字, text="${fullText.substring(0, 30)}", class="${container.className?.substring(0, 40)}"`);
      continue;
    }

    const num = parseFloat(match[1]);
    const style = getComputedStyle(container);
    const fontSize = parseFloat(style.fontSize) || 0;

    diag.log(`  候选: ￥${num}, fontSize=${fontSize}px, class="${container.className?.substring(0, 40)}"`);

    if (!isNaN(num) && num < bestPrice) {
      bestPrice = num;
      best = { price: num, priceText: fullText, fontSize };
    }
  }

  if (best) {
    diag.log(`选中最低价格: ￥${best.price}`);
  } else {
    diag.log('未能确定价格');
  }

  return best;
}

// wait for an element matching selector to appear in DOM (handles React lazy-load on scroll)
function waitForElement(selector, timeoutMs = 15000) {
  // fast path: already present
  const existing = document.querySelector(selector);
  if (existing && existing.innerText.length > 10) {
    return Promise.resolve(existing);
  }

  return new Promise((resolve) => {
    let resolved = false;
    const observer = new MutationObserver(() => {
      const el = document.querySelector(selector);
      if (el && el.innerText.length > 10) {
        resolved = true;
        observer.disconnect();
        resolve(el);
      }
    });

    observer.observe(document.body, { childList: true, subtree: true });

    setTimeout(() => {
      if (!resolved) {
        observer.disconnect();
        resolve(document.querySelector(selector));
      }
    }, timeoutMs);
  });
}

// wait for price block to appear (page may lazy-load)
async function waitForPriceBlock() {
  const block = await waitForElement('.block2--MLcO9YdF', 15000);
  if (block && block.innerText.includes('￥')) {
    diag.log('价格块已就绪');
    return true;
  }
  diag.log('等待超时，价格块未出现');
  return false;
}

// ─── SKU 价格提取（从页面内嵌 JSON 数据直接读取，无需点击）───

// extract a JSON block from a string by finding matching braces
function extractJsonBlock(text, key) {
  const idx = text.indexOf('"' + key + '"');
  if (idx === -1) return null;
  // find the start of the value after the key
  let start = text.indexOf(':', idx) + 1;
  while (start < text.length && text[start] !== '{' && text[start] !== '[') start++;
  if (start >= text.length) return null;

  // track braces/brackets to find matching close
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
  try {
    return JSON.parse(text.substring(start, end));
  } catch (_) {
    return null;
  }
}

// read SKU names + prices from page's embedded SSR data
// handles: 天猫店铺详情页, 天猫超市详情页, 淘宝店铺详情页
function extractSkuPricesFromData() {
  // find the script tag containing sku2info
  const scripts = document.querySelectorAll('script');
  let scriptText = '';
  for (const s of scripts) {
    if (s.textContent.includes('"sku2info"') && s.textContent.includes('"skuBase"')) {
      scriptText = s.textContent;
      break;
    }
  }
  if (!scriptText) {
    diag.log('未找到包含 sku2info 的 script 标签');
    return null;
  }

  const skuBase = extractJsonBlock(scriptText, 'skuBase');
  const skuCore = extractJsonBlock(scriptText, 'skuCore');

  if (!skuBase || !skuCore || !skuCore.sku2info) {
    diag.log('未能解析 skuBase 或 skuCore 数据');
    return null;
  }

  const sku2info = skuCore.sku2info;
  const hasVariants = (skuBase.skus && skuBase.skus.length > 0);

  // ─── 有 SKU 变体（多规格可选）───
  if (hasVariants) {
    diag.log(`检测到 ${skuBase.skus.length} 个 SKU 变体`);

    const title = getProductTitle();

    const vidToName = {};
    const props = skuBase.props || [];
    for (const prop of props) {
      for (const val of (prop.values || [])) {
        vidToName[val.vid] = val.name;
      }
    }

    const vidToSkuId = {};
    for (const sku of skuBase.skus) {
      const parts = sku.propPath.split(':');
      if (parts.length >= 2) {
        vidToSkuId[parts[1]] = sku.skuId;
      }
    }

    const results = [];
    for (const [vid, name] of Object.entries(vidToName)) {
      const skuId = vidToSkuId[vid];
      if (!skuId) { diag.log(`  跳过: vid=${vid} 无对应 skuId`); continue; }

      const info = sku2info[skuId];
      if (!info) { diag.log(`  跳过: skuId=${skuId} 无价格数据`); continue; }

      const subPrice = info.subPrice ? parseFloat(info.subPrice.priceText) : null;
      const origPrice = info.price ? parseFloat(info.price.priceText) : null;
      if (subPrice == null && origPrice == null) { diag.log(`  跳过售空/无价格: ${name}`); continue; }
      const price = subPrice != null ? subPrice : origPrice;

      let qty = parseQuantity(name) || parseQuantity(title) || 1;
      const unitPrice = (qty && price) ? +(price / qty).toFixed(2) : null;
      results.push({ name, price, priceOriginal: origPrice || price, quantity: qty, unitPrice });
      diag.log(`  SKU: ${name} → ￥${lowerPrice} (原价 ￥${higherPrice})${qty ? ' | ' + qty + '袋 | 单价￥' + unitPrice : ''}`);
    }

    if (results.length > 0) {
      diag.log(`从页面数据中提取到 ${results.length} 个 SKU 价格`);
      return results;
    }
    diag.log('未能解析出任何 SKU 价格，回退到单价');
  }

  // ─── 无 SKU 变体 — 取单一价格 ───
  if (sku2info['0']) {
    diag.log('无SKU变体, 读取单一价格');

    const info = sku2info['0'];
    const lowerPrice = info.subPrice ? parseFloat(info.subPrice.priceText) : null;
    const higherPrice = info.price ? parseFloat(info.price.priceText) : null;
    const label = info.subPrice ? info.subPrice.priceTitle : (info.price ? info.price.priceTitle : '价格');

    if (lowerPrice || higherPrice) {
      const price = lowerPrice || higherPrice;
      const title = getProductTitle();
      const qty = parseQuantity(title);
      const unitPrice = (qty && price) ? +(price / qty).toFixed(2) : null;
      diag.log(`  单一价格: ￥${price} (${label})${qty ? ' | 标题数量: ' + qty + ' | 单价￥' + unitPrice : ''}`);
      return [{ name: label || '当前价格', price, priceOriginal: higherPrice, quantity: qty, unitPrice }];
    }
  }

  diag.log('未能解析出任何价格数据');
  return null;
}

// parse quantity from SKU name or product title
// e.g. "3袋装"→3, "400g*12袋"→12, "加碘4袋+未加碘5袋"→9, "300g*6"→6
function parseQuantity(name) {
  if (!name) return null;

  // pattern: "X袋+Y袋" → sum them (mixed combos)
  const comboMatch = name.match(/(\d+)\s*袋\s*\+\s*[^\d]*(\d+)\s*袋/);
  if (comboMatch) {
    return parseInt(comboMatch[1]) + parseInt(comboMatch[2]);
  }

  // pattern: "X袋装" or "X袋" or "X包" or "X件装"
  const directMatch = name.match(/(\d+)\s*(?:袋装|袋|包|件装|包装|瓶装|瓶)/);
  if (directMatch) {
    return parseInt(directMatch[1]);
  }

  // pattern: "*X袋" or "*X包" or "g*X" or "g*X袋" (quantity after asterisk)
  const starMatch = name.match(/\*\s*(\d+)\s*(?:袋|包|瓶)?/);
  if (starMatch) {
    return parseInt(starMatch[1]);
  }

  // pattern: "g X袋" or "g X包" (quantity after weight)
  const weightQtyMatch = name.match(/g\s*(\d+)\s*(?:袋|包|瓶)/);
  if (weightQtyMatch) {
    return parseInt(weightQtyMatch[1]);
  }

  return null;
}

// extract product attributes (品牌, 食盐种类, etc.) from page SSR data
function extractProductAttrs() {
  const scripts = document.querySelectorAll('script');
  let scriptText = '';
  for (const s of scripts) {
    if (s.textContent.includes('"industryParamVO"')) {
      scriptText = s.textContent;
      break;
    }
  }
  if (!scriptText) {
    diag.log('未找到 industryParamVO 数据');
    return null;
  }

  const vo = extractJsonBlock(scriptText, 'industryParamVO');
  if (!vo) {
    diag.log('未能解析 industryParamVO');
    return null;
  }

  const attrs = {};

  // extract from enhanceParamList + basicParamList
  const lists = [...(vo.enhanceParamList || []), ...(vo.basicParamList || [])];
  for (const item of lists) {
    if (item.propertyName && item.valueName) {
      attrs[item.propertyName] = item.valueName;
    }
  }

  const keys = Object.keys(attrs);
  diag.log(`提取到 ${keys.length} 个产品属性: ${keys.join(', ')}`);
  return attrs;
}

// get product title from DOM (fallback to JSON data if DOM not ready)
function getProductTitle() {
  // try DOM first
  const titleEl = document.querySelector('[class*="MainTitle"] [class*="mainTitle"]');
  if (titleEl) {
    const t = (titleEl.getAttribute('title') || titleEl.textContent || '').trim();
    if (t) return t;
  }
  // fallback: try document.title (browser tab title)
  const docTitle = document.title;
  if (docTitle) {
    // strip site suffix like "-tmall.com天猫"
    const cleaned = docTitle.replace(/-tmall\.com天猫.*$/, '').replace(/-淘宝.*$/, '').trim();
    if (cleaned) return cleaned;
  }
  return '';
}

// estimate sales percentage for each SKU by index position (0=cheapest)
// uses exponential decay: weight[i] = decay^i, normalized to 100%
const SALES_DECAY = 0.65;
function estimateSalesPercentages(n) {
  if (n <= 1) return [100];
  const weights = [];
  for (let i = 0; i < n; i++) {
    weights.push(Math.pow(SALES_DECAY, i));
  }
  const sum = weights.reduce((a, b) => a + b, 0);
  return weights.map(w => +((w / sum) * 100).toFixed(1));
}

// calculate weighted average price from SKU items (sorted by price ascending)
function calcEstimatedAvgPrice(items) {
  if (!items || items.length === 0) return null;
  if (items.length === 1) return items[0].price;

  // sort by price ascending (cheapest first = highest sales)
  const sorted = [...items].sort((a, b) => (a.price || 0) - (b.price || 0));
  const pcts = estimateSalesPercentages(sorted.length);

  let weightedSum = 0;
  for (let i = 0; i < sorted.length; i++) {
    weightedSum += (sorted[i].price || 0) * (pcts[i] / 100);
  }
  return +weightedSum.toFixed(2);
}

// get SKU group label from DOM (e.g. "口味"), with lazy-load wait
async function getSkuGroupLabel() {
  // try DOM first
  let body = document.querySelector('.body--FO6TDxA0');
  if (!body) {
    body = await waitForElement('.body--FO6TDxA0', 8000);
  }
  if (body) {
    const labelEl = body.querySelector('[class*="ItemLabel"]');
    if (labelEl) return (labelEl.textContent || '').trim();
  }
  return '规格';
}

// extract all SKU prices (data-driven, no clicking)
async function extractAllSkuPrices() {
  const skuPrices = extractSkuPricesFromData();
  if (!skuPrices || skuPrices.length === 0) return null;

  const estimatedAvgPrice = calcEstimatedAvgPrice(skuPrices);
  diag.log(`预估客单价: ￥${estimatedAvgPrice} (${skuPrices.length}个SKU加权)`);

  const productAttrs = extractProductAttrs();
  const groupLabel = await getSkuGroupLabel();
  return [{ groupLabel: groupLabel || '规格', items: skuPrices, estimatedAvgPrice, productAttrs }];
}

// listen for messages from popup
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'extract_price') {
    (async () => {
      diag.log(`收到价格提取指令, URL: ${location.href}`);
      const ready = await waitForPriceBlock();
      const priceResult = extractPrice();
      let skuPrices = await extractAllSkuPrices();

      if (!skuPrices || skuPrices.length === 0) {
        diag.log('SKU 数据为空，回退到 DOM 价格');
        if (priceResult) {
          skuPrices = [{ groupLabel: '价格', items: [{ name: '当前价格', price: priceResult.price, priceOriginal: null }] }];
        }
      }

      const result = { price: priceResult, skuPrices };
      await chrome.storage.local.set({ __tb_price_result: result });
      await chrome.storage.local.set({ __tb_price_diag: diag.logs });

      sendResponse({ success: !!priceResult, price: result, diag: diag.logs, ready });
    })();
    return true;
  }

  if (request.action === 'extract_sku_prices') {
    (async () => {
      diag.log('收到 SKU 价格提取指令');
      const ready = await waitForPriceBlock();
      let skuPrices = await extractAllSkuPrices();

      // fallback: if no SKU data, use DOM price as single result
      if (!skuPrices || skuPrices.length === 0) {
        diag.log('SKU 数据为空，回退到 DOM 价格');
        const price = extractPrice();
        if (price) {
          skuPrices = [{ groupLabel: '价格', items: [{ name: '当前价格', price: price.price, priceOriginal: null }] }];
        }
      }

      await chrome.storage.local.set({ __tb_price_diag: diag.logs });

      sendResponse({ success: !!skuPrices, skuPrices, diag: diag.logs });
    })();
    return true;
  }

  if (request.action === 'poll_price') {
    (async () => {
      const data = await chrome.storage.local.get(['__tb_price_result', '__tb_price_diag']);
      sendResponse({
        done: !!data.__tb_price_result,
        price: data.__tb_price_result || null,
        diag: data.__tb_price_diag || [],
      });
    })();
    return true;
  }
});

// auto-extract if there's a pending price collection
(async () => {
  const data = await chrome.storage.local.get('__tb_price_pending');
  if (data.__tb_price_pending) {
    diag.log(`检测到待采集标记: ${data.__tb_price_pending.itemTitle}`);
    await new Promise(r => setTimeout(r, 500));
    const ready = await waitForPriceBlock();
    if (ready) {
      const priceResult = extractPrice();
      diag.log(`价格提取: ${priceResult ? '￥' + priceResult.price : '失败'}`);

      const skuPrices = await extractAllSkuPrices();

      const result = { price: priceResult, skuPrices };
      await chrome.storage.local.set({ __tb_price_result: result });
      diag.log(`自动提取完成, SKU 分组数: ${skuPrices ? skuPrices.length : 0}`);
    } else {
      diag.log('自动提取超时');
    }
    await chrome.storage.local.set({ __tb_price_diag: diag.logs });
  }
})();
