(() => {
    // 基本信息
    console.log('TITLE:', document.title);
    console.log('URL:', location.href);
    console.log('');

    // DOM 结构（前3层）
    console.log('=== DOM STRUCTURE ===');
    function walk(el, depth) {
        if (depth > 3) return;
        const tag = el.tagName ? el.tagName.toLowerCase() : '#text';
        const id = el.id ? '#' + el.id : '';
        const cls = el.className && typeof el.className === 'string'
            ? '.' + el.className.trim().split(/\s+/).slice(0, 2).join('.') : '';
        const kids = el.children.length;
        console.log('  '.repeat(depth) + '<' + tag + id + cls + '>'
            + (kids ? ' [' + kids + ' children]' : ''));
        for (let i = 0; i < Math.min(el.children.length, 5); i++) {
            walk(el.children[i], depth + 1);
        }
    }
    walk(document.body, 0);

    // 统计
    console.log('');
    console.log('=== STATS ===');
    console.log('forms:', document.querySelectorAll('form').length);
    console.log('inputs:', document.querySelectorAll('input').length);
    console.log('buttons:', document.querySelectorAll('button').length);
    console.log('links:', document.querySelectorAll('a').length);
    console.log('scripts:', document.querySelectorAll('script').length);
    console.log('images:', document.querySelectorAll('img').length);
    console.log('iframes:', document.querySelectorAll('iframe').length);

    // 登录相关
    console.log('');
    console.log('=== LOGIN ELEMENTS ===');
    document.querySelectorAll('input[type="text"], input[type="password"], input:not([type]), button[type="submit"], .login-btn, [class*="login"]').forEach(function(el) {
        console.log('<' + el.tagName + '> type=' + (el.type || '') + ' id=' + (el.id || '')
            + ' class=' + (el.className || '').slice(0, 40)
            + ' placeholder=' + (el.placeholder || '').slice(0, 30));
    });

    return 'done';
})()
