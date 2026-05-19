import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const BASE_URL = 'https://genesis-report.com';
const PUBLIC_DIR = path.join(__dirname, '../public');
const CONTENT_DIR = path.join(__dirname, '../content');

function parseFrontmatter(content) {
    const match = content.match(/^---\r?\n([\s\S]*?)\r?\n---/);
    if (!match) return {};
    const result = {};
    for (const line of match[1].split('\n')) {
        const colonIdx = line.indexOf(':');
        if (colonIdx === -1) continue;
        const key = line.slice(0, colonIdx).trim();
        const val = line.slice(colonIdx + 1).trim().replace(/^['"]|['"]$/g, '');
        if (key) result[key] = val;
    }
    return result;
}

function escapeXml(str) {
    return (str || '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&apos;');
}

const contentSources = [
    { dir: 'market-analysis',  route: 'market',   category: '시황분석' },
    { dir: 'stock-reports',    route: 'analysis',  category: '종목분석' },
    { dir: 'market-insight',   route: 'insight',   category: '마켓인사이트' },
    { dir: 'picks',            route: 'picks',     category: '유망종목' },
];

function generateRss() {
    const items = [];

    for (const source of contentSources) {
        const dirPath = path.join(CONTENT_DIR, source.dir);
        if (!fs.existsSync(dirPath)) continue;

        const files = fs.readdirSync(dirPath).filter(f => f.endsWith('.mdx'));
        for (const file of files) {
            const content = fs.readFileSync(path.join(dirPath, file), 'utf-8');
            const fm = parseFrontmatter(content);
            if (!fm.title || !fm.date) continue;
            const slug = file.replace('.mdx', '');
            items.push({
                title: fm.title,
                url: `${BASE_URL}/${source.route}/${slug}`,
                date: fm.date,
                summary: fm.summary || '',
                category: source.category,
            });
        }
    }

    items.sort((a, b) => new Date(b.date) - new Date(a.date));
    const top50 = items.slice(0, 50);

    const itemsXml = top50.map(item => `
    <item>
      <title>${escapeXml(item.title)}</title>
      <link>${escapeXml(item.url)}</link>
      <guid isPermaLink="true">${escapeXml(item.url)}</guid>
      <pubDate>${new Date(item.date).toUTCString()}</pubDate>
      <description>${escapeXml(item.summary)}</description>
      <category>${escapeXml(item.category)}</category>
    </item>`).join('');

    const rss = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>제네시스 주식 리포트</title>
    <link>${BASE_URL}</link>
    <description>한국 주식시장 실시간 시황 분석, 유망 종목 리포트, 투자 전략 정보 플랫폼</description>
    <language>ko</language>
    <managingEditor>pwman111@gmail.com (제네시스 주식 리포트)</managingEditor>
    <webMaster>pwman111@gmail.com (제네시스 주식 리포트)</webMaster>
    <lastBuildDate>${new Date().toUTCString()}</lastBuildDate>
    <atom:link href="${BASE_URL}/rss.xml" rel="self" type="application/rss+xml"/>
    <image>
      <url>${BASE_URL}/og-image.png</url>
      <title>제네시스 주식 리포트</title>
      <link>${BASE_URL}</link>
    </image>${itemsXml}
  </channel>
</rss>`;

    const outputPath = path.join(PUBLIC_DIR, 'rss.xml');
    fs.writeFileSync(outputPath, rss, 'utf-8');
    console.log(`✅ RSS feed generated: ${outputPath} (${top50.length} items)`);
}

generateRss();
