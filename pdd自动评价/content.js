/**
 * 拼多多评价自动回复 - Content Script
 * 基于实际DOM结构: beast-core Table
 */
'use strict';

// ===== 停止标志 =====
let shouldStop = false;

// ===== 日志 =====
function log(msg, data) {
  const text = msg + (data ? ' ' + JSON.stringify(data) : '');
  console.log('[PDD-AutoReply]', text);
  chrome.runtime.sendMessage({ type: 'log', text }).catch(() => {});
}
function logError(msg, err) {
  const text = msg + (err ? ' ' + (err.message || err) : '');
  console.error('[PDD-AutoReply]', text);
  chrome.runtime.sendMessage({ type: 'log', text: '❌ ' + text }).catch(() => {});
}

// ===== 获取配置 =====
function getReplyText() {
  return new Promise(resolve => {
    chrome.storage.sync.get({ replyText: '感谢老板认可～正宗天然湖盐，纯净无添加，吃得放心又健康，期待您下次回购！' }, result => {
      resolve(result.replyText || '111');
    });
  });
}

/** 获取回复速度 (毫秒), 用于操作间等待 */
async function getReplySpeed() {
  const { replySpeed } = await chrome.storage.sync.get('replySpeed');
  return parseInt(replySpeed) || 2000;
}

// ===== 等待评价组加载 =====
async function waitForReviewGroups() {
  const startTime = Date.now();
  const TIMEOUT = 60000;

  while (Date.now() - startTime < TIMEOUT) {
    // 策略1: 按 data-testid 查找 (最可靠)
    const groups = document.querySelectorAll('[data-testid="beast-core-table-middle-body"]');
    if (groups.length > 0) {
      // found groups
      return groups;
    }

    // 策略2: 按 class 前缀查找
    const tableGroups = document.querySelectorAll('[class*="TB_bodyGroup"]');
    if (tableGroups.length > 0) {
      log(`✅ 找到 ${tableGroups.length} 个评价组 (TB_bodyGroup)`);
      return tableGroups;
    }

    // 策略3: 查找 evaluation-item-header (评价头)
    const headers = document.querySelectorAll('.evaluation-item-header, [class*="evaluation-item-header"]');
    if (headers.length > 0) {
      log(`✅ 找到 ${headers.length} 个评价头部`);
      return headers;
    }

    await new Promise(r => setTimeout(r, 1000));
  }

  logError('评价列表加载超时', '');
  throw new Error('评价列表加载超时');
}

// ===== 检测评分 =====
function getStarCount(reviewGroup) {
  const stars = reviewGroup.querySelectorAll('[data-testid="beast-core-icon-star_filled"]');
  if (stars.length > 0) return stars.length;
  const icons = reviewGroup.querySelectorAll('[class*="icon-star"], [class*="star_filled"], [class*="star-filled"]');
  if (icons.length > 0) return icons.length;
  return 0;
}

// ===== 查找并点击"回复/互动" =====
function clickReplyButton(reviewGroup) {
  const candidates = reviewGroup.querySelectorAll('a, button');
  const btn = Array.from(candidates).find(el => el.textContent.trim() === '回复/互动');
  if (!btn) {
    logError('未找到"回复/互动"按钮');
    return false;
  }

  // 多种方式触发点击 (兼容React/Vue合成事件)
  btn.click();
  btn.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }));
  btn.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true, view: window }));
  btn.dispatchEvent(new MouseEvent('mouseup', { bubbles: true, cancelable: true, view: window }));

  // 父元素事件代理
  let parent = btn.parentElement;
  let depth = 0;
  while (parent && depth < 5) {
    parent.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }));
    parent = parent.parentElement;
    depth++;
  }

  return true;
}

// ===== 填写弹窗 =====
async function fillReplyDialog() {
  const replyText = await getReplyText();

  // 轮询等待弹窗出现 (最长10秒)
  for (let i = 0; i < 10; i++) {
    await new Promise(r => setTimeout(r, 1000));

    const modal = document.querySelector('[data-testid="beast-core-modal-innerWrapper"]');
    if (!modal || getComputedStyle(modal).display === 'none') continue;

    const isReviewInteraction = modal.querySelector(
      '[data-tracking-impr-viewid="review_details_reply_interactions"]'
    );
    const headerEl = modal.querySelector('.MDL_header_5-188-0');
    const headerText = headerEl ? headerEl.textContent.trim() : '';

    if (isReviewInteraction) {
      log('   已回复过, 关闭弹窗');
      await new Promise(r => setTimeout(r, 800));
      const closeBtn = modal.querySelector(
        '[data-testid="beast-core-modal-icon-close"], .MDL_iconWrapper_5-188-0'
      );
      if (closeBtn) {
        closeBtn.click();
        closeBtn.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }));
      } else {
        logError('未找到关闭按钮');
      }
      await new Promise(r => setTimeout(r, 500));
      return 'already_replied';
    }

    if (headerText === '快捷回复' || modal.querySelector('[data-tracking-impr-viewid="quick_reply_popup"]')) {
      const textarea = modal.querySelector('[data-testid="beast-core-textArea-htmlInput"]');
      if (!textarea) {
        logError('弹窗内未找到 textarea');
        return 'error';
      }

      textarea.focus();
      textarea.click();
      const nativeSetter = Object.getOwnPropertyDescriptor(
        HTMLTextAreaElement.prototype, 'value'
      ).set;
      nativeSetter.call(textarea, replyText);
      textarea.dispatchEvent(new Event('input', { bubbles: true }));
      textarea.dispatchEvent(new Event('change', { bubbles: true }));

      await new Promise(r => setTimeout(r, 500));
      const replyBtn = Array.from(modal.querySelectorAll('button')).find(
        el => el.textContent.trim() === '回复' && el.offsetParent !== null
      );
      if (!replyBtn) {
        logError('未找到"回复"按钮');
        return 'error';
      }
      replyBtn.click();
      replyBtn.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }));
      return 'replied';
    }

    logError('未知弹窗类型');
    return 'error';
  }

  logError('弹窗未出现(超时10秒)');
  return 'error';
}

// ===== 列出所有评价信息 =====
function listAllReviews(groups) {
  log('='.repeat(40));
  log(`📋 评价列表 (共 ${groups.length} 条)`);
  log('='.repeat(40));

  groups.forEach((group, index) => {
    // 获取星星数
    const starCount = group.querySelectorAll('[data-testid="beast-core-icon-star_filled"]').length;

    // 获取订单编号
    let orderNo = '';
    const orderEl = group.querySelector('[class*="orderInfo"], [class*="order-info"], [class*="order_info"]');
    if (orderEl) {
      orderNo = orderEl.textContent.replace('订单编号：', '').trim();
    }

    // 获取评价内容概要
    let reviewText = '';
    const reviewEl = group.querySelector('[class*="reviewWrapper"], [class*="review-wrapper"], [class*="review_wrapper"]');
    if (reviewEl) {
      reviewText = reviewEl.textContent.trim().substring(0, 40);
    }

    log(`  #${index + 1} | ⭐${starCount}星 | 订单: ${orderNo || 'N/A'} | ${reviewText || ''}`);
  });
}

// ===== 查找筛选按钮 =====
function findFilterButtons() {
  const allContents = document.querySelectorAll('[class*="evaluation_search_content"]');
  let star4Btn = null, star5Btn = null, unrepliedBtn = null;

  allContents.forEach(content => {
    const title = content.querySelector('[class*="evaluation_search_firstTitle"]');
    if (!title) return;
    const txt = title.textContent.trim();

    if (txt === '用户评价得分') {
      content.querySelectorAll('[class*="evaluation_search_btn"]').forEach(btn => {
        const t = btn.textContent.trim();
        if (t === '4星') star4Btn = btn;
        if (t === '5星') star5Btn = btn;
      });
    }

    if (txt === '商家回复') {
      content.querySelectorAll('[class*="evaluation_search_btn"]').forEach(btn => {
        if (btn.textContent.trim() === '未回复') unrepliedBtn = btn;
      });
    }
  });

  return { star4Btn, star5Btn, unrepliedBtn };
}

/** 从评价组中提取订单编号 */
function getOrderNo(group) {
  const el = group.querySelector('[class*="orderInfo"], [class*="order-info"], [class*="order_info"]');
  return el ? el.textContent.replace('订单编号：', '').trim() : 'N/A';
}

/** 从评价组中提取互动数 */
function getInteractionCount(group) {
  const span = Array.from(group.querySelectorAll('span')).find(
    s => s.textContent.trim().startsWith('互动数：')
  );
  return span ? parseInt(span.textContent.replace('互动数：', '')) : 0;
}

// ===== 激活筛选条件 =====
async function activateFilters() {
  const filters = findFilterButtons();
  if (!filters.star4Btn || !filters.star5Btn || !filters.unrepliedBtn) {
    logError('未找到筛选按钮(4星/5星/未回复)');
    return false;
  }

  const speed = await getReplySpeed();
  const needClick = [
    { btn: filters.star4Btn, name: '4星' },
    { btn: filters.star5Btn, name: '5星' },
    { btn: filters.unrepliedBtn, name: '未回复' },
  ];

  for (const { btn, name } of needClick) {
    if (!btn.className.includes('checked')) {
      btn.click();
      btn.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }));
      await new Promise(r => setTimeout(r, speed));
    }
  }

  log('✅ 筛选条件已激活 (4星+5星+未回复)');
  return true;
}

// ===== 主流程 =====
async function processFirstReview() {
  log('='.repeat(40));
  log('🚀 开始执行');
  log('='.repeat(40));

  const { replyCount = 0 } = await chrome.storage.sync.get('replyCount');
  const limit = parseInt(replyCount) || 0;
  const speed = await getReplySpeed();
  log(`📋 回复条数: ${limit > 0 ? limit + ' 条' : '不限制'} | 速度: ${speed / 1000}s`);

  // 第一步: 等待页面加载
  log('⏳ 等待评价列表...');
  try {
    await waitForReviewGroups();
  } catch (e) {
    logError('等待超时', e);
    return;
  }

  // 第二步: 激活筛选 (4星 + 5星 + 未回复)
  const filtersOk = await activateFilters();
  if (!filtersOk) return;

  // 第三步: 给筛选结果一点加载时间
  await new Promise(r => setTimeout(r, speed));

  let repliedCount = 0;

  // 动态循环: 每次回复后重新获取 DOM (回复过的评价消失, 新评价补入)
  while (!shouldStop && (limit === 0 || repliedCount < limit)) {
    let groups;
    try {
      groups = await waitForReviewGroups();
    } catch (e) {
      logError('等待评价列表超时', e);
      break;
    }

    // 筛选4星及以上 且 互动数为0 的评价, 取第一条
    const candidates = Array.from(groups).filter(g =>
      g.querySelectorAll('[data-testid="beast-core-icon-star_filled"]').length >= 4 &&
      getInteractionCount(g) === 0
    );

    if (candidates.length === 0) {
      log('⏭️ 没有找到符合条件的评价 (4星及以上且互动数为0)');
      break;
    }

    const review = candidates[0];
    const orderNo = getOrderNo(review);

    if (!clickReplyButton(review)) {
      log('⏹️ 未找到"回复/互动"按钮, 停止');
      break;
    }

    if (shouldStop) break;
    const result = await fillReplyDialog();

    if (result === 'replied') {
      repliedCount++;
      chrome.runtime.sendMessage({ type: 'reply_progress', count: repliedCount }).catch(() => {});
      chrome.storage.local.get('pdd_total_replied', r => {
        const total = (r.pdd_total_replied || 0) + 1;
        chrome.storage.local.set({ pdd_total_replied: total });
      });
    } else if (result === 'already_replied') {
      // 已回复过, 下一轮重新获取 DOM
    } else {
      logError(`订单 ${orderNo}: 回复处理失败`);
    }

    await new Promise(r => setTimeout(r, speed));
  }

  log('='.repeat(40));
  log(`🏁 执行完毕, 共回复 ${repliedCount} 条`);
  log('='.repeat(40));
  sendFinished();
}

function sendFinished() {
  shouldStop = false;
  chrome.runtime.sendMessage({ type: 'run_finished' }).catch(() => {});
}

// ===== 检测回复状态 (测试用) =====
async function checkReplyStatus() {
  log('='.repeat(40));
  log('🔬 检测筛选状态');
  log('='.repeat(40));

  const filters = findFilterButtons();
  if (!filters.unrepliedBtn) {
    log('❌ 未找到"未回复"筛选按钮, 请确认在评价管理页面');
    return;
  }

  const isUnrepliedActive = filters.unrepliedBtn.className.includes('checked');
  const is4StarActive = filters.star4Btn ? filters.star4Btn.className.includes('checked') : false;
  const is5StarActive = filters.star5Btn ? filters.star5Btn.className.includes('checked') : false;

  log(`📋 商家回复筛选:`);
  log(`   "未回复" 按钮: ✅ class="${filters.unrepliedBtn.className}"`);
  log(`      激活状态: ${isUnrepliedActive ? '✅ 已激活' : '⭕ 未激活'}`);

  log(`\n📋 评价得分筛选:`);
  log(`   "4星" 按钮: ${filters.star4Btn ? '✅ 已找到' : '❌ 未找到'}`);
  if (filters.star4Btn) log(`      激活状态: ${is4StarActive ? '✅ 已激活' : '⭕ 未激活'}`);
  log(`   "5星" 按钮: ${filters.star5Btn ? '✅ 已找到' : '❌ 未找到'}`);
  if (filters.star5Btn) log(`      激活状态: ${is5StarActive ? '✅ 已激活' : '⭕ 未激活'}`);

  log(`\n📋 三个筛选是否全部激活: ${isUnrepliedActive && is4StarActive && is5StarActive ? '✅ 是' : '❌ 否'}`);

  // 顺便列出所有评价的回复按钮情况
  const groups = document.querySelectorAll('[data-testid="beast-core-table-middle-body"]');
  if (groups.length > 0) {
    log(`\n📋 共 ${groups.length} 条评价, 回复按钮状态:`);
    Array.from(groups).forEach((group, idx) => {
      const starCount = group.querySelectorAll('[data-testid="beast-core-icon-star_filled"]').length;
      const btn = Array.from(group.querySelectorAll('a, button')).find(el => el.textContent.trim() === '回复/互动');
      log(`   #${idx + 1} ⭐${starCount}星 | 回复按钮: ${btn ? '✅' : '❌'}`);
    });
  }

  log('='.repeat(40));
  log('🔬 检测完毕');
  log('='.repeat(40));
}

// ===== 消息监听 =====
chrome.runtime.onMessage.addListener((message) => {
  if (message.action === 'run') {
    shouldStop = false;
    log('📩 收到运行指令');
    processFirstReview();
  } else if (message.action === 'stop') {
    shouldStop = true;
    log('⏹️ 正在停止...');
  } else if (message.action === 'check_status') {
    log('📩 收到检测指令');
    checkReplyStatus();
  }
});

log('📦 已加载，等待指令...');

// 页面刷新 = 全新会话, 清空日志和累计计数
const pageVer = Date.now();
chrome.storage.local.set({ pdd_page_version: pageVer, pdd_logs: [], pdd_total_replied: 0 });
chrome.runtime.sendMessage({ type: 'page_loaded', version: pageVer }).catch(() => {});
