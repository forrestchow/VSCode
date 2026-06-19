'use strict';

async function getCurrentTab() {
  const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
  return tabs[0];
}

async function downloadHTML() {
  const btn = document.getElementById('downloadBtn');
  const status = document.getElementById('status');
  btn.disabled = true;
  status.textContent = '⏳ 获取页面源码...';

  try {
    const tab = await getCurrentTab();
    if (!tab || !tab.id) {
      status.textContent = '❌ 无法获取当前标签页';
      return;
    }

    // 通过 content script 获取页面完整 DOM
    const response = await chrome.tabs.sendMessage(tab.id, { action: 'get_html' });
    if (!response || !response.html) {
      status.textContent = '❌ 获取源码为空';
      return;
    }

    const sourceUrl = response.url || tab.url || '';
    const titleMatch = response.html.match(/<title[^>]*>([^<]*)<\/title>/i);
    const pageTitle = titleMatch ? titleMatch[1].trim() : '页面';

    // 构建完整 HTML 文档
    const fullDoc = `<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="generator" content="HTML下载器">
  ${sourceUrl ? `<meta name="source-url" content="${esc(sourceUrl)}">` : ''}
  <title>${esc(pageTitle)}</title>
</head>
<body>
${response.html}
</body>
</html>`;

    const blob = new Blob([fullDoc], { type: 'text/html;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const filename = `${sanitizeFilename(pageTitle)}_${new Date().toISOString().slice(0, 10)}.html`;

    await chrome.downloads.download({ url, filename, saveAs: true });
    status.textContent = '✅ 下载成功';
  } catch (err) {
    status.textContent = '❌ 下载失败';
    console.error('[HTML下载器]', err);
  } finally {
    btn.disabled = false;
  }
}

function esc(s) {
  if (!s) return '';
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

function sanitizeFilename(name) {
  return name.replace(/[\\/:*?"<>|]/g, '_').substring(0, 60);
}

document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('downloadBtn').addEventListener('click', downloadHTML);
});
