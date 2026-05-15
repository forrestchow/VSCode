'use strict';

// ─── 诊断日志 ───
const diag = {
  logs: [],
  log(msg) { this.logs.push(`[${new Date().toLocaleTimeString()}] ${msg}`); console.log('[淘宝采集]', msg); },
  async flush() { await chrome.storage.local.set({ __tb_diag: this.logs }); },
};

// 页面刷新/重新加载时清除 popup 缓存状态
chrome.storage.local.remove('__tb_last_results');

// ─── 判断是否含销量文本（人付款 / 人收货） ───
function hasSalesText(text) {
  return text.includes('人付款') || text.includes('人收货') || text.includes('本月行业热销');
}

// ─── 等待商品渲染完成（轮询） ───
async function waitForProducts(maxWaitMs = 15000) {
  const pollInterval = 500;
  let waited = 0;
  while (waited < maxWaitMs) {
    const wrapper = document.querySelector('#content_items_wrapper');
    if (wrapper && wrapper.innerHTML.length > 1000 && hasSalesText(wrapper.innerText)) {
      diag.log(`等待 ${waited}ms 后商品已加载`);
      return true;
    }
    // 骨架屏消失 + 容器有内容 = 商品可能已加载
    const skeleton = document.querySelector('.boneClass_boneWrapper');
    if (!skeleton && wrapper && wrapper.innerHTML.length > 1000) {
      diag.log(`等待 ${waited}ms 后骨架屏消失，商品已加载`);
      return true;
    }
    await new Promise((r) => setTimeout(r, pollInterval));
    waited += pollInterval;
  }
  diag.log(`等待 ${maxWaitMs}ms 超时，商品未加载`);
  return false;
}

// ─── 自动采集（页面跳转后） ───
chrome.storage.local.get('__tb_pending_scrape').then(async (data) => {
  if (data.__tb_pending_scrape) {
    diag.log('检测到待采集标记，页面刚跳转过来');
    await chrome.storage.local.remove('__tb_pending_scrape');

    // 等 React 初始化（骨架屏可能已显示）
    await new Promise((r) => setTimeout(r, 1000));
    const ready = await waitForProducts();
    await saveSnapshot('after_sort');
    await doScrapeAndStore();
    await diag.flush();
    if (!ready) {
      diag.log('自动采集结束：超时未等到商品');
      await diag.flush();
    }
  }
});

// ─── 销量文本解析 ───
function parseSales(text) {
  if (!text) return 0;
  if (text.includes('本月行业热销')) return 99999;
  text = text.replace(/\s/g, '').replace('人付款', '').replace('人收货', '');
  let num = 0;
  let magnitude = 0;
  if (text.includes('万')) {
    const m = text.match(/([\d.]+)万/);
    if (m) num = parseFloat(m[1]) * 10000;
    magnitude = 10000;
  } else {
    const m = text.match(/(\d+)/);
    if (m) num = parseInt(m[1]);
    if (num > 0) magnitude = Math.pow(10, Math.floor(Math.log10(num)));
  }
  return text.includes('+') && magnitude > 0 ? num + magnitude / 2 : num;
}

// ─── 提取卡片数据（wrapper = doubleCard 容器） ───
function extractCardData(wrapper) {
  // 图片
  const imgs = wrapper.querySelectorAll('img');
  let imgUrl = '';
  for (const img of imgs) {
    const w = img.getAttribute('width');
    const h = img.getAttribute('height');
    if ((w && parseInt(w) >= 100) || (h && parseInt(h) >= 100)) {
      imgUrl = img.src || '';
      break;
    }
  }
  if (!imgUrl) {
    for (const img of imgs) {
      if (img.src && !img.src.includes('data:image')) {
        imgUrl = img.src;
        break;
      }
    }
  }
  if (imgUrl && !imgUrl.startsWith('http')) {
    try { imgUrl = new URL(imgUrl, location.origin).href; } catch (_) {}
  }

  // 标题
  const titleEl = wrapper.querySelector('[class*="title--"], [class*="Title--"]');
  const title = titleEl
    ? (titleEl.getAttribute('title') || titleEl.textContent || '').trim()
    : '';

  // 销量：找 realSales span 的文本（人付款 / 人收货 / 本月行业热销）
  let salesText = '';
  const walker = document.createTreeWalker(wrapper, NodeFilter.SHOW_TEXT, null, false);
  let node;
  while ((node = walker.nextNode())) {
    if (hasSalesText(node.textContent)) {
      salesText = node.textContent.trim();
      diag.log(`销量原文: "${salesText}" | 父元素: ${node.parentElement?.className?.substring(0,30) || '(none)'}`);
      break;
    }
  }

  // 店铺名：在 wrapper 内查找（可能在卡片 <a> 外部）
  const shopEl = wrapper.querySelector('[class*="shopNameText"]');
  const shopName = shopEl ? (shopEl.textContent || '').trim() : '';

  // product link from the <a> tag inside wrapper
  let productUrl = '';
  const linkEl = wrapper.querySelector('a[href]');
  if (linkEl) {
    let href = linkEl.getAttribute('href');
    if (href.startsWith('//')) href = 'https:' + href;
    else if (!href.startsWith('http')) {
      try { href = new URL(href, location.origin).href; } catch (_) { href = ''; }
    }
    productUrl = href;
  }

  return {
    imgUrl,
    title,
    salesText,
    salesNum: parseSales(salesText),
    shopName,
    productUrl,
  };
}

// ─── 扫描页面 ───
function scrapePage() {
  // 找到所有含销量文本（人付款/人收货）的节点 → 向上找 <a> 标签 → 用 <a> 的父元素作为容器
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null, false);
  const wrapperSet = new Set();
  let node;
  let textCount = 0;
  while ((node = walker.nextNode())) {
    if (hasSalesText(node.textContent)) {
      textCount++;
      let el = node.parentElement;
      let depth = 0;
      while (el && el.tagName !== 'A' && depth < 20) { el = el.parentElement; depth++; }
      if (el && el.tagName === 'A' && el.parentElement && !wrapperSet.has(el.parentElement)) {
        wrapperSet.add(el.parentElement);
      }
    }
  }

  diag.log(`找到 ${textCount} 个销量文本, ${wrapperSet.size} 个商品卡片`);

  const items = Array.from(wrapperSet).map(extractCardData);
  diag.log(`提取完成: ${items.length} 个商品`);

  if (items.length > 0) {
    diag.log(`首个: ${(items[0].title||'').substring(0,30)} | 销量:${items[0].salesNum} | ${items[0].shopName}`);
  } else {
    const aCount = document.querySelectorAll('a').length;
    const hasText = hasSalesText(document.body.innerText);
    diag.log(`诊断: <a>标签=${aCount}, 含销量文本=${hasText}`);
  }

  return items;
}

// replace 本月行业热销 (99999) with median of real sales
function normalizeHotSales(items) {
  const realSales = items.filter(i => i.salesNum > 0 && i.salesNum < 99999).map(i => i.salesNum);
  if (realSales.length === 0) return items;
  realSales.sort((a, b) => a - b);
  const mid = Math.floor(realSales.length / 2);
  const median = realSales.length % 2 === 0
    ? Math.round((realSales[mid - 1] + realSales[mid]) / 2)
    : realSales[mid];
  diag.log(`销量中位数: ${median} (来自 ${realSales.length} 个有效值)`);
  for (const item of items) {
    if (item.salesNum === 99999) {
      item.salesNum = median;
      item.salesText = `${median}+ (预估)`;
    }
  }
  return items;
}

// ─── 采集并存入 storage ───
async function doScrapeAndStore() {
  let items = scrapePage();
  items = normalizeHotSales(items);
  const filtered = items
    .filter((i) => i.salesNum >= 1000)
    .sort((a, b) => b.salesNum - a.salesNum);
  diag.log(`过滤后: ${filtered.length} 个 ≥ 1000`);
  await chrome.storage.local.set({
    __tb_scrape_done: true,
    __tb_scrape_total: items.length,
    __tb_scrape_items: filtered,
  });
  await diag.flush();
}

// ─── 保存页面快照（诊断用） ───
async function saveSnapshot(label) {
  try {
    // 找商品列表区域
    const areas = [
      document.querySelector('#content_items_wrapper'),
      document.querySelector('[class*="itemsWrapper"]'),
      document.querySelector('[class*="contentWrapper"]'),
      document.querySelector('#pageContent'),
      document.querySelector('[class*="searchContent"]'),
    ];
    let html = '';
    for (const area of areas) {
      if (area && area.innerHTML.length > 500) {
        html = area.innerHTML;
        diag.log(`快照[${label}]: 取自 ${area.className?.substring(0,40) || area.id}, ${html.length} 字符`);
        break;
      }
    }
    if (!html) {
      html = document.body.innerHTML.substring(0, 100000);
      diag.log(`快照[${label}]: 取自 body, 100000 字符`);
    }
    // 限制存储大小（200KB 够分析用）
    const MAX = 200000;
    if (html.length > MAX) html = html.substring(0, MAX);
    await chrome.storage.local.set({ [`__tb_snapshot_${label}`]: html });
  } catch (e) {
    diag.log(`快照[${label}] 失败: ${e.message}`);
  }
}

// ─── 获取销量排序按钮信息 ───
function getSortButtonInfo() {
  const active = !!document.querySelector('li[data-spm="_sale"].active');
  const tab = document.querySelector('li[data-spm="_sale"]');
  if (!tab) return { active: false, exists: false };
  // 确保按钮在视口内
  tab.scrollIntoView({ block: 'center', behavior: 'instant' });
  const r = tab.getBoundingClientRect();
  return {
    active,
    exists: true,
    rect: { x: r.x, y: r.y, width: r.width, height: r.height },
  };
}

// ─── 监听消息 ───
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'click_sort_and_scrape') {
    (async () => {
      diag.log('收到排序+采集指令');

      // click sort button if not already active
      const sortTab = document.querySelector('li[data-spm="_sale"]');
      if (!sortTab) {
        diag.log('未找到销量排序按钮');
        sendResponse({ items: [], diag: diag.logs });
        return;
      }

      if (!sortTab.classList.contains('active')) {
        diag.log('点击销量排序按钮...');
        sortTab.click();
        // wait for SPA re-render
        await new Promise(r => setTimeout(r, 1500));
        const ready = await waitForProducts(10000);
        if (!ready) diag.log('排序后商品未在预期时间内加载');
      } else {
        diag.log('销量排序已激活');
        await waitForProducts(5000);
      }

      let items = scrapePage();
      items = normalizeHotSales(items);
      const filtered = items
        .filter((i) => i.salesNum >= 1000)
        .sort((a, b) => b.salesNum - a.salesNum);
      diag.log(`完成: ${items.length} 商品, ${filtered.length} 符合条件`);
      await diag.flush();
      sendResponse({ total: items.length, items: filtered, diag: diag.logs });
    })();
    return true;
  }

  if (request.action === 'get_sort_rect') {
    const info = getSortButtonInfo();
    sendResponse(info);
    return true;
  }

  if (request.action === 'scrape') {
    (async () => {
      diag.log('收到采集指令');
      await chrome.storage.local.set({ __tb_diag: [] });
      diag.log(`URL: ${location.href}`);

      const isActive = !!document.querySelector('li[data-spm="_sale"].active');
      diag.log(`销量排序: ${isActive ? '已激活' : '未激活'}`);

      await saveSnapshot('before_sort');

      // popup 应该已通过 debugger API 点击了销量按钮
      // 如果排序尚未激活，等一会儿（点击可能需要时间处理）
      if (!isActive) {
        diag.log('排序尚未激活，等待排序生效...');
        for (let i = 0; i < 10; i++) {
          await new Promise((r) => setTimeout(r, 500));
          if (document.querySelector('li[data-spm="_sale"].active')) {
            diag.log(`排序已激活 (等待 ${(i + 1) * 500}ms)`);
            break;
          }
        }
      }

      diag.log('等待渲染完成（轮询等待商品出现）...');
      await diag.flush();

      const productsReady = await waitForProducts();

      await saveSnapshot('after_sort');

      let items = scrapePage();
      items = normalizeHotSales(items);
      const filtered = items
        .filter((i) => i.salesNum >= 1000)
        .sort((a, b) => b.salesNum - a.salesNum);

      diag.log(`完成: ${items.length} 商品, ${filtered.length} 符合条件`);

      await chrome.storage.local.set({
        __tb_scrape_done: true,
        __tb_scrape_total: items.length,
        __tb_scrape_items: filtered,
      });
      await chrome.storage.local.remove('__tb_pending_scrape');
      await diag.flush();

      sendResponse({ total: items.length, items: filtered, diag: diag.logs });
    })();
    return true;
  }

  if (request.action === 'poll_result') {
    (async () => {
      const data = await chrome.storage.local.get([
        '__tb_scrape_done', '__tb_scrape_total', '__tb_scrape_items', '__tb_diag',
      ]);
      sendResponse(data);
    })();
    return true;
  }

  if (request.action === 'get_snapshot') {
    (async () => {
      const key = request.label || 'after_sort';
      const data = await chrome.storage.local.get(`__tb_snapshot_${key}`);
      sendResponse({ html: data[`__tb_snapshot_${key}`] || '', label: key });
    })();
    return true;
  }
});
