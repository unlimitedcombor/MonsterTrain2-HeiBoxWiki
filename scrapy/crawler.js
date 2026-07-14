/**
 * Monster Train 2 Wiki 浏览器爬虫
 *
 * 用法:
 *   1. 打开 https://monstertrain2.miraheze.org (确保已通过 Cloudflare 验证)
 *   2. F12 打开开发者工具 → Console
 *   3. 粘贴此脚本并运行
 *   4. 调用以下任一函数:
 *
 *   // 按分类爬取
 *   await crawlCategory('Enemies')
 *   await crawlCategory('Banner_units')
 *   await crawlCategory('Artifacts')
 *
 *   // 按列表页爬取 (从页面中提取链接)
 *   await crawlFromListPage('Enemies')
 *
 *   // 爬取后自动下载 JSON 文件
 *   await crawlAndDownload('Enemies', 'enemies.json')
 */

const API = 'https://monstertrain2.miraheze.org/w/api.php';

// ============================================================
// 1. 按分类爬取 (使用 MediaWiki categorymembers API)
// ============================================================

async function crawlCategory(categoryName, delay = 500) {
    const pages = [];
    let cmcontinue = null;

    console.log(`[crawlCategory] Fetching Category:${categoryName}...`);

    do {
        let url = `${API}?action=query&list=categorymembers&cmtitle=Category:${encodeURIComponent(categoryName)}&cmlimit=500&format=json`;
        if (cmcontinue) url += `&cmcontinue=${encodeURIComponent(cmcontinue)}`;

        const resp = await fetch(url);
        const data = await resp.json();

        if (!data.query) {
            console.error('API error:', data);
            break;
        }

        for (const m of data.query.categorymembers) {
            if (m.ns === 0) {  // ns=0 = 主命名空间 (排除 Category:, Template: 等)
                pages.push(m.title);
            }
        }

        cmcontinue = data.continue?.cmcontinue;
        console.log(`  ... got ${pages.length} pages so far`);
    } while (cmcontinue);

    console.log(`[crawlCategory] Found ${pages.length} pages in Category:${categoryName}`);
    return pages;
}

// ============================================================
// 2. 从列表页提取所有 wiki 链接
// ============================================================

async function extractLinksFromPage(pageTitle) {
    console.log(`[extractLinks] Fetching page: ${pageTitle}`);
    const htmlUrl = `${API}?action=parse&page=${encodeURIComponent(pageTitle)}&prop=text&format=json`;
    const resp = await fetch(htmlUrl);
    const data = await resp.json();

    if (!data.parse) {
        console.error('Failed to parse page:', data);
        return [];
    }

    const html = data.parse.text['*'];
    const parser = new DOMParser();
    const doc = parser.parseFromString(html, 'text/html');

    // 提取所有指向主命名空间的内部链接
    const links = new Set();
    for (const a of doc.querySelectorAll('a[href^="/wiki/"]')) {
        const href = a.getAttribute('href');
        // 排除特殊页面和文件页面
        if (href && !href.includes(':') && !href.includes('?') && !href.includes('#')) {
            const title = decodeURIComponent(href.replace('/wiki/', '')).replace(/_/g, ' ');
            links.add(title);
        }
    }

    console.log(`[extractLinks] Found ${links.size} unique wiki links on "${pageTitle}"`);
    return [...links];
}

// ============================================================
// 3. 批量获取原始 wikitext
// ============================================================

async function fetchWikitext(title) {
    const url = `${API}?action=parse&page=${encodeURIComponent(title)}&prop=wikitext&format=json`;
    const resp = await fetch(url);
    const data = await resp.json();
    return data.parse?.wikitext?.['*'] || '';
}

async function fetchAllWikitext(titles, delay = 300, onProgress = null) {
    const results = {};
    let count = 0;

    for (const title of titles) {
        try {
            results[title] = await fetchWikitext(title);
            count++;
            if (onProgress) {
                onProgress(count, titles.length, title);
            } else {
                console.log(`  [${count}/${titles.length}] ${title}`);
            }
        } catch (e) {
            console.error(`  FAILED: ${title} - ${e.message}`);
            results[title] = null;
        }
        await new Promise(r => setTimeout(r, delay));
    }

    return results;
}

// ============================================================
// 4. 一键爬取 + 下载
// ============================================================

async function crawlAndDownload(categoryOrPage, filename = null) {
    // 检测是分类名还是页面名
    let titles;

    // 先尝试作为分类
    titles = await crawlCategory(categoryOrPage);
    if (titles.length === 0) {
        // 回退：作为列表页提取链接
        console.log(` Category:${categoryOrPage} 为空, 尝试作为列表页...`);
        titles = await extractLinksFromPage(categoryOrPage);
    }

    if (titles.length === 0) {
        console.error('No pages found!');
        return;
    }

    console.log(`\n开始爬取 ${titles.length} 个页面...`);
    const data = await fetchAllWikitext(titles);

    downloadJSON(data, filename || `${categoryOrPage}_wikitext.json`);
    console.log(`\n完成! 共 ${Object.keys(data).length} 个页面`);
    return data;
}

// ============================================================
// 5. 从列表页一键爬取
// ============================================================

async function crawlFromListPage(pageTitle, filename = null) {
    const titles = await extractLinksFromPage(pageTitle);
    if (titles.length === 0) {
        console.error(`No links found on "${pageTitle}"`);
        return;
    }

    console.log(`\n开始爬取 ${titles.length} 个页面...`);
    const data = await fetchAllWikitext(titles);
    downloadJSON(data, filename || `${pageTitle}_data.json`);
    console.log(`\n完成!`);
    return data;
}

// ============================================================
// 6. 工具函数
// ============================================================

function downloadJSON(data, filename) {
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    console.log(`  [download] Saved as ${filename}`);
}

// 列出 wiki 上所有分类
async function listAllCategories(prefix = '') {
    const categories = [];
    let apcontinue = null;

    do {
        let url = `${API}?action=query&list=allcategories&aclimit=500&format=json`;
        if (prefix) url += `&acprefix=${encodeURIComponent(prefix)}`;
        if (apcontinue) url += `&apcontinue=${encodeURIComponent(apcontinue)}`;

        const resp = await fetch(url);
        const data = await resp.json();
        categories.push(...(data.query?.allcategories || []).map(c => c['*']));
        apcontinue = data.continue?.apcontinue;
    } while (apcontinue);

    console.log('All categories:');
    categories.forEach(c => console.log(`  - ${c}`));
    return categories;
}

// 列出某分类下的页面 (只看标题不下载)
async function listCategoryMembers(categoryName) {
    const pages = await crawlCategory(categoryName);
    console.log(`\nPages in Category:${categoryName}:`);
    pages.forEach(p => console.log(`  - ${p}`));
    return pages;
}

console.log('%c Monster Train 2 Wiki Crawler Ready %c v1.0',
    'background:#c8a96e;color:#000;padding:4px 8px;font-size:14px',
    'color:#888');
console.log('');
console.log('可用命令:');
console.log('  await listAllCategories()          - 列出所有分类');
console.log('  await listCategoryMembers("分类名") - 查看分类下的页面');
console.log('  await crawlAndDownload("分类名")    - 一键爬取+下载');
console.log('  await crawlFromListPage("页面名")   - 从列表页提取链接并爬取');
console.log('');
console.log('示例:');
console.log('  await listAllCategories()');
console.log('  await listCategoryMembers("Enemies")');
console.log('  await crawlAndDownload("Enemies", "mt2_enemies.json")');
