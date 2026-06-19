'use strict';

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'get_html') {
    sendResponse({ html: document.documentElement.outerHTML, url: location.href });
  }
  return true;
});
