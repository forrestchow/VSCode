/**
 * popup.js - 弹窗逻辑
 */
'use strict';

const $ = id => document.getElementById(id);
const logBox = $('logBox');

// ===== 日志系统 =====

/** 向日志框追加一行，并持久化 */
function appendLog(text) {
  const line = document.createElement('div');

  if (text.startsWith('❌') || text.startsWith('Error') || text.startsWith('出错')) {
    line.className = 'log-err';
  } else if (text.startsWith('✅') || text.startsWith('🎉')) {
    line.className = 'log-ok';
  } else if (text.startsWith('⏳') || text.startsWith('⏭️')) {
    line.className = 'log-warn';
  } else if (text.startsWith('🔍') || text.startsWith('📩') || text.startsWith('📦') || text.startsWith('🔄') || text.startsWith('🚀')) {
    line.className = 'log-info';
  } else if (text.startsWith('=')) {
    line.className = 'log-sep';
  } else {
    line.className = 'log-line';
  }

  line.textContent = text;
  logBox.appendChild(line);
  logBox.scrollTop = logBox.scrollHeight;

  // 持久化（保留最近 200 条）
  chrome.storage.local.get('pdd_logs', result => {
    const logs = result.pdd_logs || [];
    logs.push(text);
    if (logs.length > 200) logs.splice(0, logs.length - 200);
    chrome.storage.local.set({ pdd_logs: logs });
  });
}

/** 恢复或清空日志（页面刷新时清空） */
async function restoreLogs() {
  const { pdd_page_version, pdd_logs, pdd_seen_version } = await chrome.storage.local.get([
    'pdd_page_version', 'pdd_logs', 'pdd_seen_version'
  ]);

  if (pdd_page_version && pdd_page_version !== pdd_seen_version) {
    // 页面已刷新 → 清空旧日志和计数
    await chrome.storage.local.remove(['pdd_logs', 'pdd_total_replied']);
    await chrome.storage.local.set({ pdd_seen_version: pdd_page_version });
  } else if (pdd_logs && pdd_logs.length > 0) {
    // 页面未刷新 → 恢复日志
    pdd_logs.forEach(t => {
      const line = document.createElement('div');
      line.className = 'log-line';
      line.textContent = t;
      logBox.appendChild(line);
    });
    logBox.scrollTop = logBox.scrollHeight;
  }
}

// ===== 设置 =====

async function loadSettings() {
  const { replyText, replyCount, replySpeed } = await chrome.storage.sync.get(['replyText', 'replyCount', 'replySpeed']);
  $('replyText').value = replyText || '感谢老板认可～正宗天然湖盐，纯净无添加，吃得放心又健康，期待您下次回购！';
  $('replyCount').value = replyCount ?? 10;
  $('replySpeed').value = replySpeed || 2000;
}

async function saveSettings() {
  await chrome.storage.sync.set({
    replyText: $('replyText').value,
    replyCount: parseInt($('replyCount').value) || 0,
    replySpeed: parseInt($('replySpeed').value) || 2000,
  });
  appendLog('✅ 设置已保存');
}

// ===== 从存储加载累计回复数 =====
function updateCounterFromStorage() {
  chrome.storage.local.get('pdd_total_replied', r => {
    $('replyCounter').textContent = r.pdd_total_replied || 0;
  });
}

// ===== 与 content script 通信 =====

let isRunning = false;

function setRunningState(running) {
  const btn = $('runBtn');
  isRunning = running;
  if (running) {
    btn.textContent = '停止';
    btn.className = 'btn-danger';
  } else {
    btn.textContent = '立即运行';
    btn.className = 'btn-primary';
  }
}

async function sendRunCommand() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab || !tab.id) { appendLog('❌ 无法获取当前标签页'); return; }

  if (isRunning) {
    try {
      await chrome.tabs.sendMessage(tab.id, { action: 'stop' });
      setRunningState(false);
    } catch (e) { /* ignore */ }
    return;
  }

  await saveSettings();
  appendLog('📩 发送运行指令到页面...');
  try {
    await chrome.tabs.sendMessage(tab.id, { action: 'run' });
    setRunningState(true);
  } catch (e) {
    appendLog('❌ content script 未响应');
    appendLog('   可能原因: 不在评价管理页面 / 页面未刷新');
    appendLog('   请刷新评价管理页面后重试');
  }
}

// ===== 监听来自 content script 的日志 =====

chrome.runtime.onMessage.addListener((message) => {
  if (message.type === 'log') {
    appendLog(message.text);
  } else if (message.type === 'page_loaded') {
    logBox.innerHTML = '';
    $('replyCounter').textContent = '0';
    chrome.storage.local.remove('pdd_total_replied');
    chrome.storage.local.set({ pdd_logs: [], pdd_seen_version: message.version });
    setRunningState(false);
  } else if (message.type === 'reply_progress') {
    updateCounterFromStorage();
  } else if (message.type === 'run_finished') {
    setRunningState(false);
  }
});

// ===== 事件绑定 =====

document.addEventListener('DOMContentLoaded', async () => {
  await restoreLogs();
  // 无恢复日志时才显示默认提示
  if (logBox.children.length === 0) appendLog('💡 点击 "立即运行" 开始执行');
  loadSettings();
  updateCounterFromStorage();
});

$('saveBtn').addEventListener('click', saveSettings);

$('clearBtn').addEventListener('click', () => {
  logBox.innerHTML = '';
  chrome.storage.local.remove('pdd_logs');
});

$('runBtn').addEventListener('click', sendRunCommand);

$('checkStatusBtn').addEventListener('click', async () => {
  await saveSettings();
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab || !tab.id) { appendLog('❌ 无法获取当前标签页'); return; }
  appendLog('📩 发送状态检测指令...');
  try {
    await chrome.tabs.sendMessage(tab.id, { action: 'check_status' });
  } catch (e) {
    appendLog('❌ content script 未响应, 请刷新页面后重试');
  }
});

$('replyText').addEventListener('input', () => {
  chrome.storage.sync.set({ replyText: $('replyText').value });
});

$('replySpeed').addEventListener('change', () => {
  chrome.storage.sync.set({ replySpeed: parseInt($('replySpeed').value) || 2000 });
});

