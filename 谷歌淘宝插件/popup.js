'use strict';

let collectedItems = [];

// ─── JSON 解析工具 (从 HTML 文本提取内嵌数据) ───
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

// ─── Fetch 方式获取详情页数据（不打开浏览器标签页）───
async function fetchDetailData(productUrl) {
  let html, resp;
  try {
    resp = await fetch(productUrl);
    html = await resp.text();
  } catch (e) {
    appendLog(`  fetch 失败: ${e.message}`, 'error');
    return null;
  }

  // verification detection
  const sizeKB = html.length / 1024;
  const isVerify = sizeKB < 20 || html.includes('login') || html.includes('captcha')
    || html.includes('verify') || html.includes('punish') || !html.includes('sku2info');
  if (isVerify) {
    appendLog(`  ⚠ 验证拦截 (${sizeKB.toFixed(1)}KB)`, 'warn');
    return { _verify: true, url: productUrl };
  }

  const skuBase = extractJsonBlock(html, 'skuBase');
  const skuCore = extractJsonBlock(html, 'skuCore');
  const indVO = extractJsonBlock(html, 'industryParamVO');

  if (!skuCore || !skuCore.sku2info) {
    appendLog('  未找到 sku2info 数据', 'error');
    return null;
  }

  const sku2info = skuCore.sku2info;
  const hasVariants = (skuBase && skuBase.skus && skuBase.skus.length > 0);
  let items = [];

  // extract title once for quantity fallback
  const titleMatch = html.match(/<title[^>]*>([^<]*)<\/title>/i);
  const htmlTitle = titleMatch ? titleMatch[1].replace(/-tmall\.com天猫.*$/, '').replace(/-淘宝.*$/, '').trim() : '';
  const bodyMatch = html.match(/(\d+)\s*(?:袋装|袋|包|件装)/);
  const bodyQty = bodyMatch ? parseInt(bodyMatch[1]) : null;

  if (hasVariants) {
    const vidToName = {};
    for (const prop of (skuBase.props || [])) {
      for (const val of (prop.values || [])) vidToName[val.vid] = val.name;
    }
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
      if (subPrice == null && origPrice == null) { appendLog(`  skip sold-out: ${name}`, 'warn'); continue; }
      const price = subPrice != null ? subPrice : origPrice;
      let qty = parseQuantity(name) || parseQuantity(htmlTitle) || bodyQty || 1;
      items.push({ name, price, priceOriginal: origPrice || price, quantity: qty, unitPrice: (qty && price) ? +(price / qty).toFixed(2) : null });
    }
  } else if (sku2info['0']) {
    const info = sku2info['0'];
    const price = info.subPrice ? parseFloat(info.subPrice.priceText) : (info.price ? parseFloat(info.price.priceText) : null);
    const priceOriginal = info.price ? parseFloat(info.price.priceText) : null;
    const label = info.subPrice ? info.subPrice.priceTitle : '价格';

    let qty = parseQuantity(label) || parseQuantity(htmlTitle) || bodyQty;
    if (!qty) {
      const specMatch = html.match(/(?:净含量|规格|总净含量)[^<]*?(\d+)\s*(?:g|克|袋|包)/);
      if (specMatch) qty = parseInt(specMatch[1]);
    }
    appendLog(`  数量解析: label="${label}" title="${htmlTitle?.substring(0,40)}" → ${qty || '未识别'}`, 'info');
    items.push({ name: label || '当前价格', price, priceOriginal, quantity: qty, unitPrice: (qty && price) ? +(price / qty).toFixed(2) : null });
  } else {
    appendLog('  未找到任何价格数据', 'error');
    return null;
  }

  if (items.length === 0) return null;

  const estimatedAvgPrice = calcEstimatedAvgPrice(items);
  const productAttrs = {};
  if (indVO) {
    for (const list of [...(indVO.enhanceParamList || []), ...(indVO.basicParamList || [])]) {
      if (list.propertyName && list.valueName) productAttrs[list.propertyName] = list.valueName;
    }
  }
  // also get price from block2 (DOM not available, use sku2info[0])
  const priceResult = sku2info['0']
    ? { price: parseFloat(sku2info['0'].subPrice ? sku2info['0'].subPrice.priceText : sku2info['0'].price.priceText) }
    : null;

  return {
    price: priceResult,
    skuPrices: [{ groupLabel: '规格', items, estimatedAvgPrice, productAttrs }],
  };
}

const logCache = [];
function appendLog(msg, type) {
  type = type || 'info';
  console.log(`[${type}] ${msg}`);
  logCache.push({ msg, type, time: Date.now() });
  // persist last 200 entries
  chrome.storage.local.set({ __tb_logs: logCache.slice(-200) }).catch(() => {});
  const logBody = document.getElementById('logBody');
  if (logBody) {
    const entry = document.createElement('div');
    entry.className = `log-entry ${type}`;
    entry.textContent = `[${new Date().toLocaleTimeString()}] ${msg}`;
    logBody.appendChild(entry);
    logBody.scrollTop = logBody.scrollHeight;
  }
}

function isDetailPage(url) {
  return /^(https?:\/\/)?item\.taobao\.com\/item/.test(url || '')
    || /^(https?:\/\/)?detail\.tmall\.com\/item/.test(url || '');
}

async function getCurrentTab() {
  const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
  return tabs[0];
}

function esc(s) {
  if (!s) return '';
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

function downloadCSV(items) {
  const BOM = '﻿';
  const hasPrice = items.some(i => i.detailPrice != null);

  // flatten SKUs and find max count
  const productSkus = items.map(i => {
    const flat = [];
    if (i.skuPrices) {
      for (const g of i.skuPrices) {
        for (const s of g.items) flat.push(s);
      }
    }
    return flat;
  });
  const maxSku = Math.max(1, ...productSkus.map(a => a.length));

  // build headers matching table layout
  const headers = ['图片链接', '产品名称', '销量', '店铺名称', '商品ID', '商品链接'];
  if (hasPrice) headers.push('客单价');
  headers.push('品牌', '食盐种类');
  for (let i = 0; i < maxSku; i++) {
    headers.push(`SKU${i + 1}-规格`, `SKU${i + 1}-价格`);
  }

  const rows = items.map((i, idx) => {
    const field = (s) => {
      s = String(s || '');
      if (s.includes(',') || s.includes('"') || s.includes('\n')) {
        return '"' + s.replace(/"/g, '""') + '"';
      }
      return s;
    };
    const attrs = (i.skuPrices && i.skuPrices[0] && i.skuPrices[0].productAttrs) || {};

    const pidMatch = (i.productUrl || '').match(/[?&]id=(\d+)/);
    const row = [field(i.imgUrl), field(i.title), i.salesNum, field(i.shopName), pidMatch ? pidMatch[1] : '', field(i.productUrl || '')];
    if (hasPrice) {
      const ap = (i.skuPrices && i.skuPrices[0] && i.skuPrices[0].estimatedAvgPrice != null)
        ? i.skuPrices[0].estimatedAvgPrice
        : i.detailPrice;
      row.push(ap != null ? ap : '');
    }
    row.push(field(attrs['品牌'] || ''), field(attrs['食盐种类'] || ''));

    const skus = productSkus[idx];
    for (let j = 0; j < maxSku; j++) {
      if (j < skus.length) {
        row.push(skus[j].quantity != null ? skus[j].quantity : '');
        row.push(skus[j].price != null ? skus[j].price : '');
      } else {
        row.push('', '');
      }
    }
    return row.join(',');
  });
  const csv = BOM + headers.join(',') + '\n' + rows.join('\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  chrome.downloads.download({ url, filename: `淘宝销量数据_${new Date().toISOString().slice(0, 10)}.csv`, saveAs: true });
}

// ─── 解析价格包裹格式 ───
function unwrapPriceResult(wrapper) {
  const isWrapped = wrapper.price && typeof wrapper.price === 'object';
  return {
    priceResult: isWrapped ? wrapper.price : wrapper,
    skuPrices: isWrapped ? wrapper.skuPrices : (wrapper.skuPrices || null),
  };
}

// ─── 将价格数据应用到商品列表 ───
async function applyPriceResult(wrapper, pending) {
  const { priceResult, skuPrices } = unwrapPriceResult(wrapper);

  if (priceResult && priceResult.price != null) {
    appendLog(`价格提取成功: ￥${priceResult.price}`, 'success');
  }
  if (skuPrices && skuPrices.length > 0) {
    appendLog(`SKU 价格采集完成: ${skuPrices.reduce((s, g) => s + g.items.length, 0)} 个 SKU`, 'success');
  }

  if (pending && collectedItems.length > 0) {
    if (priceResult) {
      collectedItems[pending.itemIndex || 0].detailPrice = priceResult.price;
      collectedItems[pending.itemIndex || 0].detailPriceText = priceResult.priceText;
    }
    if (skuPrices) collectedItems[pending.itemIndex || 0].skuPrices = skuPrices;
  }

  const saved = await chrome.storage.local.get('__tb_last_results');
  if (saved.__tb_last_results && saved.__tb_last_results.items) {
    const items = saved.__tb_last_results.items;
    if (pending && items[pending.itemIndex || 0]) {
      if (priceResult) {
        items[pending.itemIndex || 0].detailPrice = priceResult.price;
        items[pending.itemIndex || 0].detailPriceText = priceResult.priceText;
      }
      if (skuPrices) items[pending.itemIndex || 0].skuPrices = skuPrices;
    }
    await chrome.storage.local.set({ __tb_last_results: { items, total: saved.__tb_last_results.total } });
  }

  if (collectedItems.length > 0) {
    renderResults(collectedItems, collectedItems.length);
  }

  const statusPrice = priceResult ? `￥${priceResult.price}` : '';
  const statusSku = skuPrices ? `, ${skuPrices.reduce((s, g) => s + g.items.length, 0)} 个SKU` : '';
  document.getElementById('statusText').textContent = `✅ 价格采集完成: ${statusPrice}${statusSku}`;
  await chrome.storage.local.remove('__tb_price_pending');
}

// ─── 自动循环提取所有商品详情 ───
async function runDetailExtractionLoop(items, searchTabId) {
  // filter to items with URL and without _detailDone
  const itemsWithUrl = items.filter(i => i.productUrl && !i._detailDone);
  const maxInput = document.getElementById('maxCountInput');
  const maxCount = parseInt(maxInput?.value) || 0;
  const count = maxCount > 0 ? Math.min(itemsWithUrl.length, maxCount) : itemsWithUrl.length;

  if (count === 0) {
    appendLog('没有可提取详情的商品', 'warn');
    return;
  }

  // read delay from input (seconds), default 2, clamp 1-3
  const delayInput = document.getElementById('delayInput');
  const baseDelay = Math.min(3, Math.max(1, parseFloat(delayInput?.value) || 2)) * 1000;

  appendLog(`开始 fetch 提取 ${count} 个商品 (间隔约${(baseDelay/1000).toFixed(1)}秒)...`, 'info');

  for (let i = 0; i < count; i++) {
    if (stopRequested) {
      appendLog('用户停止采集', 'warn');
      document.getElementById('statusText').textContent = '⏹ 已停止';
      break;
    }
    const item = itemsWithUrl[i];
    const idx = items.indexOf(item);
    appendLog(`[${i + 1}/${count}] ${item.title}`, 'info');
    document.getElementById('statusText').textContent = `⏳ 详情 ${i + 1}/${count}`;

    // only show spinner on the current row
    for (const it of itemsWithUrl) {
      const ix = items.indexOf(it);
      items[ix]._loading = false;
    }
    items[idx]._loading = true;
    renderResults(items, items.length);

    const result = await fetchDetailData(item.productUrl);

    items[idx]._loading = false;

    if (result && result._verify) {
      appendLog(`  ⚠ 触发验证，暂停采集`, 'warn');
      document.getElementById('statusText').textContent = '⚠ 需要验证 — 点击修复';
      document.getElementById('fixBtn').style.display = '';
      document.getElementById('resumeBtn').style.display = '';
      document.getElementById('startBtn').style.display = 'none';

      document.getElementById('fixBtn').onclick = () => chrome.tabs.create({ url: item.productUrl, active: true });
      document.getElementById('resumeBtn').onclick = () => {
        document.getElementById('fixBtn').style.display = 'none';
        document.getElementById('resumeBtn').style.display = 'none';
        document.getElementById('startBtn').style.display = '';
        resumeDetailLoop(items, itemsWithUrl, i, count, baseDelay);
      };
      return;
    }

    if (result && result.price) {
      items[idx].detailPrice = result.price.price;
      if (result.skuPrices && result.skuPrices.length > 0) {
        items[idx].skuPrices = result.skuPrices;
        const g = result.skuPrices[0];
        if (g.estimatedAvgPrice != null) {
          items[idx].detailPrice = g.estimatedAvgPrice;
        }
        const totalSkus = result.skuPrices.reduce((s, g) => s + g.items.length, 0);
        appendLog(`  ✅ ￥${result.price.price} | ${totalSkus}个SKU | 客单价: ￥${g.estimatedAvgPrice || '?'}`, 'success');
        if (g.productAttrs) {
          appendLog(`  品牌: ${g.productAttrs['品牌'] || '-'} | 食盐种类: ${g.productAttrs['食盐种类'] || '-'}`, 'info');
        }
      } else {
        appendLog(`  ✅ ￥${result.price.price}`, 'success');
      }
      items[idx]._detailDone = true;
    } else {
      appendLog(`  ❌ 提取失败`, 'error');
    }

    collectedItems = items;
    renderResults(collectedItems, collectedItems.length);
    await chrome.storage.local.set({
      __tb_last_results: { items: collectedItems, total: collectedItems.length },
    });

    // delay with random jitter
    if (i < count - 1) {
      const jitter = (Math.random() - 0.5) * 1000; // ±500ms
      const delay = baseDelay + jitter;
      await new Promise(r => setTimeout(r, delay));
    }
  }

  document.getElementById('statusText').textContent = `✅ 全部完成: ${collectedItems.length} 个商品`;
  appendLog(`全部 ${count} 个商品详情提取完成`, 'success');
}

// resume detail extraction from a specific index (after verification fix)
async function resumeDetailLoop(items, itemsWithUrl, startIdx, count, baseDelay) {
  appendLog(`从第 ${startIdx + 1}/${count} 个恢复...`, 'info');
  document.getElementById('statusText').textContent = '⏳ 恢复采集...';

  for (let i = startIdx; i < count; i++) {
    if (stopRequested) break;
    const item = itemsWithUrl[i];
    const idx = items.indexOf(item);
    appendLog(`[${i + 1}/${count}] ${item.title}`, 'info');
    document.getElementById('statusText').textContent = `⏳ 详情 ${i + 1}/${count}`;

    for (const it of itemsWithUrl) { const ix = items.indexOf(it); items[ix]._loading = false; }
    items[idx]._loading = true;
    renderResults(items, items.length);

    const result = await fetchDetailData(item.productUrl);
    items[idx]._loading = false;

    if (result && result._verify) {
      appendLog(`  ⚠ 再次触发验证，暂停`, 'warn');
      document.getElementById('statusText').textContent = '⚠ 需要验证 — 点击修复';
      document.getElementById('fixBtn').style.display = '';
      document.getElementById('resumeBtn').style.display = '';
      document.getElementById('startBtn').style.display = 'none';
      document.getElementById('fixBtn').onclick = () => chrome.tabs.create({ url: item.productUrl, active: true });
      document.getElementById('resumeBtn').onclick = () => {
        document.getElementById('fixBtn').style.display = 'none';
        document.getElementById('resumeBtn').style.display = 'none';
        document.getElementById('startBtn').style.display = '';
        resumeDetailLoop(items, itemsWithUrl, i, count, baseDelay);
      };
      return;
    }

    if (result && result.price) {
      items[idx].detailPrice = result.price.price;
      if (result.skuPrices && result.skuPrices.length > 0) {
        items[idx].skuPrices = result.skuPrices;
        const g = result.skuPrices[0];
        if (g.estimatedAvgPrice != null) items[idx].detailPrice = g.estimatedAvgPrice;
        const totalSkus = result.skuPrices.reduce((s, g) => s + g.items.length, 0);
        appendLog(`  ✅ ￥${result.price.price} | ${totalSkus}个SKU | 客单价: ￥${g.estimatedAvgPrice || '?'}`, 'success');
        if (g.productAttrs) {
          appendLog(`  品牌: ${g.productAttrs['品牌'] || '-'} | 食盐种类: ${g.productAttrs['食盐种类'] || '-'}`, 'info');
        }
      } else {
        appendLog(`  ✅ ￥${result.price.price}`, 'success');
      }
      items[idx]._detailDone = true;
    } else {
      appendLog(`  ❌ 提取失败`, 'error');
    }

    collectedItems = items;
    renderResults(collectedItems, collectedItems.length);
    await chrome.storage.local.set({ __tb_last_results: { items: collectedItems, total: collectedItems.length } });

    if (i < count - 1) {
      const jitter = (Math.random() - 0.5) * 1000;
      await new Promise(r => setTimeout(r, baseDelay + jitter));
    }
  }

  document.getElementById('statusText').textContent = `✅ 全部完成: ${collectedItems.length} 个商品`;
  appendLog(`全部完成`, 'success');
}

// ─── 从详情页读取价格结果 ───
async function checkPriceResult() {
  appendLog('检查价格采集结果...', 'info');

  const data = await chrome.storage.local.get([
    '__tb_price_result', '__tb_price_diag', '__tb_price_pending',
  ]);

  // show detail page diag logs
  if (data.__tb_price_diag && data.__tb_price_diag.length > 0) {
    for (const log of data.__tb_price_diag) {
      appendLog(`[详情页] ${log}`, 'info');
    }
  }

  if (data.__tb_price_result) {
    await applyPriceResult(data.__tb_price_result, data.__tb_price_pending);
    return;
  }

  // result not ready yet — poll briefly (extraction may be in progress)
  appendLog('正在等待价格提取完成...', 'warn');
  document.getElementById('statusText').textContent = '⏳ 正在提取价格...';
  for (let i = 0; i < 8; i++) {
    await new Promise(r => setTimeout(r, 500));
    const updated = await chrome.storage.local.get(['__tb_price_result', '__tb_price_diag']);
    if (updated.__tb_price_result) {
      // show any new diag logs since last read
      const prevLen = data.__tb_price_diag ? data.__tb_price_diag.length : 0;
      if (updated.__tb_price_diag && updated.__tb_price_diag.length > prevLen) {
        for (const log of updated.__tb_price_diag.slice(prevLen)) {
          appendLog(`[详情页] ${log}`, 'info');
        }
      }
      await applyPriceResult(updated.__tb_price_result, data.__tb_price_pending);
      return;
    }
  }
  appendLog('价格提取超时', 'error');
  document.getElementById('statusText').textContent = '❌ 价格提取超时';
}

function renderResults(items, totalCount) {
  const area = document.getElementById('resultArea');
  if (items.length === 0) {
    area.innerHTML = `<div class="hint">共抓取 ${totalCount} 个商品，但没有销量 ≥ 1000 的商品。</div>`;
    document.getElementById('statusText').textContent = `已采集 ${totalCount} 个商品，符合条件 0 个`;
    return;
  }

  // collect all SKU items across products, find max count
  const hasDetail = items.some(i => i._loading || i.detailPrice != null || (i.skuPrices && i.skuPrices.length > 0));
  const showAttrs = items.some(i => {
    if (i._loading) return true;
    const a = (i.skuPrices && i.skuPrices[0] && i.skuPrices[0].productAttrs);
    return a && (a['品牌'] || a['食盐种类']);
  });
  let maxSkuCount = 0;
  const productSkus = items.map(i => {
    const flat = [];
    if (i.skuPrices) {
      for (const g of i.skuPrices) {
        for (const s of g.items) {
          flat.push(s);
        }
      }
    }
    if (flat.length > maxSkuCount) maxSkuCount = flat.length;
    return flat;
  });

  // build header: 产品名称 | 销量 | 店铺名称 | 客单价 | 品牌 | 食盐种类
  const basicCols = ['产品名称', '销量', '店铺名称', '商品ID', '商品链接'];
  if (hasDetail) basicCols.push('客单价');
  if (showAttrs) basicCols.push('品牌', '食盐种类');

  let html = `<div class="table-wrap"><table><thead>`;
  html += `<tr>`;
  for (const h of basicCols) {
    html += `<th rowspan="2">${h}</th>`;
  }
  if (maxSkuCount > 0) {
    html += `<th colspan="${maxSkuCount * 2}" style="text-align:center;">SKU 明细 (上:规格数量 下:价格)</th>`;
  }
  html += `</tr>`;
  // header row 2: SKU sub-headers (规格 / 价格 pairs)
  if (maxSkuCount > 0) {
    html += `<tr>`;
    for (let i = 0; i < maxSkuCount; i++) {
      html += `<th style="text-align:center;font-size:10px;">规格</th><th style="text-align:center;font-size:10px;">价格</th>`;
    }
    html += `</tr>`;
  }
  html += `</thead><tbody>`;

  // product rows — 2 rows per product
  for (let pi = 0; pi < items.length; pi++) {
    const item = items[pi];
    const skus = productSkus[pi];

    const salesDisplay = item.salesText && item.salesText.includes('预估')
      ? `<span class="sales-cell" title="本月行业热销，取中位数预估">~${item.salesNum}</span>`
      : `<span class="sales-cell">${item.salesNum}</span>`;

    const isLoading = item._loading === true;
    const spinner = '<span class="loading" style="width:12px;height:12px;"></span>';

    const avgPrice = isLoading ? spinner
      : (item.skuPrices && item.skuPrices[0] && item.skuPrices[0].estimatedAvgPrice != null)
        ? '￥' + item.skuPrices[0].estimatedAvgPrice
        : (item.detailPrice != null ? '￥' + item.detailPrice : '-');
    const attrs = isLoading ? {} : ((item.skuPrices && item.skuPrices[0] && item.skuPrices[0].productAttrs) || {});

    // Row 1: basic cols (产品|销量|店铺|客单价|品牌|种类) + SKU quantities
    html += `<tr style="border-bottom:1px dashed #ddd;">`;
    html += `<td rowspan="2"><div class="prod-title" title="${esc(item.title)}">${esc(item.title)}</div></td>`;
    html += `<td rowspan="2">${salesDisplay}</td>`;
    html += `<td rowspan="2">${esc(item.shopName)}</td>`;
    // product ID from URL
    const pidMatch = (item.productUrl || '').match(/[?&]id=(\d+)/);
    const pid = pidMatch ? pidMatch[1] : '-';
    html += `<td rowspan="2">${pid}</td>`;
    // product link (shortened)
    html += `<td rowspan="2"><a href="${esc(item.productUrl || '#')}" target="_blank" style="color:#ff5000;font-size:11px;" title="${esc(item.productUrl || '')}">🔗</a></td>`;
    if (hasDetail) html += `<td rowspan="2" class="sales-cell">${avgPrice}</td>`;
    if (showAttrs) {
      html += `<td rowspan="2">${isLoading ? spinner : esc(attrs['品牌'] || '-')}</td>`;
      html += `<td rowspan="2">${isLoading ? spinner : esc(attrs['食盐种类'] || '-')}</td>`;
    }

    if (isLoading && maxSkuCount === 0) {
      // no SKU data yet, show a single spinner cell for detail placeholder
      html += `<td rowspan="2" style="text-align:center;">${spinner}</td>`;
    }

    for (let si = 0; si < maxSkuCount; si++) {
      if (si < skus.length) {
        const qty = isLoading ? spinner : (skus[si].quantity || '-');
        html += `<td style="text-align:center;color:#ff5000;font-weight:700;font-size:13px;">${qty}</td>`;
        html += `<td></td>`;
      } else {
        html += `<td></td><td></td>`;
      }
    }
    html += `</tr>`;

    // Row 2: SKU prices
    html += `<tr>`;
    for (let si = 0; si < maxSkuCount; si++) {
      if (si < skus.length) {
        html += `<td></td>`;
        const price = isLoading ? spinner : (skus[si].price != null ? '￥' + skus[si].price : '-');
        html += `<td class="sales-cell" style="font-size:12px;">${price}</td>`;
      } else {
        html += `<td></td><td></td>`;
      }
    }
    html += `</tr>`;
  }

  html += `</tbody></table></div>
    <div class="bottom-bar">
      <span style="font-size:12px;color:#999;line-height:32px;">共 ${totalCount} 个商品，符合条件 ${items.length} 个</span>
      <button class="btn btn-success" id="downloadBtn">⬇ 下载 CSV</button>
    </div>`;
  area.innerHTML = html;
  document.getElementById('statusText').textContent = `✅ 采集完成 — 共 ${totalCount} 个商品，销量 ≥ 1000 的有 ${items.length} 个`;
  document.getElementById('downloadBtn').addEventListener('click', () => downloadCSV(items));
  chrome.storage.local.set({ __tb_last_results: { items, total: totalCount } });
}

// ─── search via existing or new tab ───
async function fetchSearchAPI(keyword, page = 1) {
  const url = `https://s.taobao.com/search?page=${page}&q=${encodeURIComponent(keyword)}&sort=sale-desc`;
  appendLog(`search: ${url.substring(0, 80)}...`, 'info');

  let tab, needClose = false;
  try {
    // try to find an existing taobao search tab
    const tabs = await chrome.tabs.query({});
    tab = tabs.find(t => /taobao\.com\/search/.test(t.url || ''));
    if (tab) {
      appendLog(`reuse existing tab #${tab.id}`, 'info');
      await chrome.tabs.update(tab.id, { url, active: false });
    } else {
      tab = await chrome.tabs.create({ url, active: false });
      needClose = true;
      appendLog(`new background tab #${tab.id}`, 'info');
    }
  } catch (e) {
    appendLog(`tab error: ${e.message}`, 'error'); return [];
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

  appendLog('tab loaded, click sort + scrape...', 'info');

  let items = [];
  for (let retry = 0; retry < 3; retry++) {
    try {
      const resp = await chrome.tabs.sendMessage(tab.id, { action: 'click_sort_and_scrape' });
      if (resp && resp.items && resp.items.length > 0) {
        items = resp.items;
        break;
      }
    } catch (e) {
      appendLog(`retry ${retry + 1}: ${e.message}`, 'warn');
    }
    await new Promise(r => setTimeout(r, 1500));
  }

  if (needClose) { try { await chrome.tabs.remove(tab.id); } catch (_) {} }

  if (items.length === 0) {
    appendLog('no products extracted', 'error');
    return [];
  }

  appendLog(`extracted ${items.length} products (sorted by sales)`, 'success');
  const sample = items.slice(0, 3).map(i => `"${(i.title||'').substring(0,15)}" ${i.salesText}`).join(' | ');
  appendLog(`top 3: ${sample}`, 'info');
  return items;
}

async function startScrape() {
  const rawKw = document.getElementById('searchKeyword')?.value?.trim();
  if (!rawKw) {
    document.getElementById('statusText').textContent = '❌ 请输入搜索关键词';
    return;
  }
  const keywords = rawKw.split(/[\n\r]+/).map(k => k.trim()).filter(Boolean);
  const autoPage = document.getElementById('autoPageChk')?.checked || false;
  const minSales = parseInt(document.getElementById('minSalesInput')?.value) || 0;
  const delay = (parseFloat(document.getElementById('delayInput')?.value) || 2) * 1000;
  const maxCount = parseInt(document.getElementById('maxCountInput')?.value) || 0;

  const btn = document.getElementById('startBtn');
  btn.textContent = '⏹ 停止采集';
  btn.style.background = '#e64500';
  document.getElementById('statusText').textContent = '⏳ 后台采集中...';
  document.getElementById('emptyHint').style.display = 'none';

  chrome.runtime.sendMessage({ action: 'start', keywords, autoPage, minSales, delay, maxCount });
  startPolling();
}

function startPolling() {
  if (window._pollTimer) clearInterval(window._pollTimer);
  window._pollTimer = setInterval(async () => {
    const data = await chrome.storage.local.get(['__tb_last_results', '__tb_logs', '__tb_progress', '__tb_verify']);
    // update table
    if (data.__tb_last_results && data.__tb_last_results.items) {
      collectedItems = data.__tb_last_results.items;
      renderResults(collectedItems, data.__tb_last_results.total || collectedItems.length);
    }
    // update logs
    if (data.__tb_logs && data.__tb_logs.length > 0) {
      const logBody = document.getElementById('logBody');
      if (logBody && logBody.children.length < data.__tb_logs.length) {
        for (let i = logBody.children.length; i < data.__tb_logs.length; i++) {
          const e = data.__tb_logs[i];
          const div = document.createElement('div');
          div.className = `log-entry ${e.type || 'info'}`;
          div.textContent = `[${new Date(e.time).toLocaleTimeString()}] ${e.msg}`;
          logBody.appendChild(div);
        }
        logBody.scrollTop = logBody.scrollHeight;
      }
    }
    // progress
    if (data.__tb_progress) {
      document.getElementById('statusText').textContent = `⏳ 详情 ${data.__tb_progress.current}/${data.__tb_progress.total}`;
    }
    // verify
    if (data.__tb_verify) {
      document.getElementById('statusText').textContent = '⚠ 需要验证 — 点击修复';
      document.getElementById('fixBtn').style.display = '';
      document.getElementById('resumeBtn').style.display = '';
      document.getElementById('startBtn').style.display = 'none';
      document.getElementById('fixBtn').onclick = () => chrome.tabs.create({ url: data.__tb_verify.url, active: true });
      document.getElementById('resumeBtn').onclick = () => {
        document.getElementById('fixBtn').style.display = 'none';
        document.getElementById('resumeBtn').style.display = 'none';
        document.getElementById('startBtn').style.display = '';
        chrome.runtime.sendMessage({
          action: 'resume', keywords: [], autoPage: false, minSales: 0, delay: 2000, maxCount: 0
        });
        startPolling();
      };
      clearInterval(window._pollTimer);
    }
    // check if done
    chrome.runtime.sendMessage({ action: 'status' }, (resp) => {
      if (resp && !resp.isRunning && !data.__tb_verify) {
        clearInterval(window._pollTimer);
        const btn = document.getElementById('startBtn');
        btn.textContent = '▶ 重新采集';
        btn.style.background = '#ff5000';
        document.getElementById('statusText').textContent = `✅ 采集完成 (${collectedItems.length} 个商品)`;
      }
    });
  }, 500);
}

async function init() {
  let tab;
  try { tab = await getCurrentTab(); } catch (_) {}
  const statusText = document.getElementById('statusText');
  const startBtn = document.getElementById('startBtn');

  // ─── 日志面板折叠/展开 ───
  document.getElementById('logHeader').addEventListener('click', () => {
    const body = document.getElementById('logBody');
    const toggle = document.getElementById('logToggle');
    const isOpen = body.classList.toggle('open');
    toggle.textContent = isOpen ? '收起' : '展开';
  });

  // ─── 恢复上次数据 ───
  const saved = await chrome.storage.local.get(['__tb_last_results', '__tb_logs']);
  if (saved.__tb_last_results && saved.__tb_last_results.items && saved.__tb_last_results.items.length > 0) {
    const r = saved.__tb_last_results;
    collectedItems = r.items;
    renderResults(r.items, r.total);
  }
  // restore logs
  if (saved.__tb_logs && saved.__tb_logs.length > 0) {
    for (const entry of saved.__tb_logs) {
      appendLog(entry.msg, entry.type);
    }
  }

  // auto-poll if collection is running
  const status = await chrome.runtime.sendMessage({ action: 'status' });
  if (status && status.isRunning) {
    document.getElementById('startBtn').textContent = '⏹ 停止采集';
    document.getElementById('startBtn').style.background = '#e64500';
    startPolling();
  }

  // ─── 清空按钮 ───
  document.getElementById('clearBtn').addEventListener('click', async () => {
    collectedItems = [];
    await chrome.storage.local.remove(['__tb_last_results', '__tb_logs', '__tb_price_result', '__tb_price_pending']);
    document.getElementById('resultArea').innerHTML = `<div class="hint">已清空</div>`;
    document.getElementById('logBody').innerHTML = '';
    document.getElementById('statusText').textContent = '等待启动...';
  });

  // ─── 当前页面类型判断 ───
  const onDetail = tab && isDetailPage(tab.url);

  if (onDetail) {
    statusText.textContent = '📋 当前是商品详情页';
    startBtn.style.display = 'none';
    document.getElementById('skuPriceBtn').click();
  } else {
    startBtn.addEventListener('click', async () => {
      const status = await chrome.runtime.sendMessage({ action: 'status' });
      if (status && status.isRunning) {
        chrome.runtime.sendMessage({ action: 'stop' });
        startBtn.textContent = '▶ 开始采集';
        startBtn.style.background = '#ff5000';
      } else {
        startScrape();
      }
    });
    // pre-fill keyword from URL if on search page
    if (tab && /taobao\.com\/search/.test(tab.url || '')) {
      const m = (tab.url.match(/[?&]q=([^&]*)/) || [])[1];
      if (m) {
        document.getElementById('searchKeyword').value = decodeURIComponent(m);
        statusText.textContent = `🔍 ${decodeURIComponent(m)}`;
        return;
      }
    }
    statusText.textContent = '✅ 输入关键词，点击开始采集';
  }

  // SKU 价格按钮 — 任何页面都可以尝试触发
  document.getElementById('skuPriceBtn').addEventListener('click', async () => {
    const btn = document.getElementById('skuPriceBtn');
    btn.disabled = true;
    btn.textContent = '⏳ 提取中...';
    appendLog('正在提取 SKU 价格...', 'info');

    try {
      const resp = await chrome.tabs.sendMessage(tab.id, { action: 'extract_sku_prices' });
      if (resp && resp.success && resp.skuPrices) {
        appendLog(`✅ 提取到 ${resp.skuPrices.reduce((s, g) => s + g.items.length, 0)} 个 SKU 价格`, 'success');
        for (const g of resp.skuPrices) {
          appendLog(`--- ${g.groupLabel} ---`, 'info');
          for (const item of g.items) {
            const qtyStr = item.quantity ? ` | ${item.quantity}袋/包` : '';
            const unitStr = item.unitPrice ? ` | 单价 ￥${item.unitPrice}` : '';
            appendLog(`  ${item.name}: ￥${item.price} (原价 ￥${item.priceOriginal || '?'})${qtyStr}${unitStr}`, 'info');
          }
          if (g.estimatedAvgPrice != null) {
            appendLog(`📊 预估客单价: ￥${g.estimatedAvgPrice}`, 'success');
          }
          if (g.productAttrs) {
            const brand = g.productAttrs['品牌'] || '';
            const saltType = g.productAttrs['食盐种类'] || '';
            if (brand || saltType) {
              appendLog(`📋 品牌: ${brand || '-'} | 食盐种类: ${saltType || '-'}`, 'info');
            }
          }
        }
        const wrapper = { price: null, skuPrices: resp.skuPrices };
        await chrome.storage.local.set({ __tb_price_result: wrapper });
        const pending = await chrome.storage.local.get('__tb_price_pending');
        await applyPriceResult(wrapper, pending.__tb_price_pending);
        document.getElementById('statusText').textContent = '✅ SKU 价格已更新';
      } else if (resp && resp.diag) {
        for (const log of resp.diag) {
          appendLog(`[详情页] ${log}`, 'info');
        }
        appendLog('SKU 价格提取失败，查看上方诊断日志', 'error');
      } else {
        appendLog('SKU 价格提取失败', 'error');
      }
    } catch (err) {
      appendLog(`通信失败: ${err.message} (可能当前页面不支持)`, 'error');
    }

    btn.disabled = false;
    btn.textContent = '📊 查看SKU价格';
  });
}

document.addEventListener('DOMContentLoaded', init);
