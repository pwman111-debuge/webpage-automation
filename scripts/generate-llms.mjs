import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const BASE_URL = 'https://genesis-report.com';
const PUBLIC_DIR = path.join(__dirname, '../public');
const CONTENT_DIR = path.join(__dirname, '../content');

// 섹션당 최신 N개만 노출 (파일 비대화 방지)
const PER_SECTION = 30;

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

// llms.txt 마크다운에서 링크 텍스트를 깨뜨리는 문자 정리
function clean(str) {
    return (str || '').replace(/\r?\n/g, ' ').replace(/\[|\]/g, '').trim();
}

const contentSources = [
    { dir: 'market-analysis', route: 'market', heading: '시황 분석', desc: '코스피·코스닥 일일/주간 시황과 수급 분석' },
    { dir: 'stock-reports', route: 'analysis', heading: '종목 리포트', desc: '개별 종목 펀더멘털·기술적 심층 분석' },
    { dir: 'market-insight', route: 'insight', heading: '마켓 인사이트', desc: 'FOMC·매크로·테마 등 거시 인사이트' },
    { dir: 'picks', route: 'picks', heading: '유망 종목', desc: '단기·중기·장기 유망 종목 발굴 (목표가·손절가 포함)' },
    { dir: 'picks-feedback', route: 'picks/feedback', heading: '투자 성과 리포트', desc: '과거 추천 종목의 실제 성과 복기' },
    { dir: 'education', route: 'education', heading: '투자 교육', desc: '투자 기초·용어·전략 가이드 (에버그린)' },
];

function collect(source) {
    const dirPath = path.join(CONTENT_DIR, source.dir);
    if (!fs.existsSync(dirPath)) return [];
    const files = fs.readdirSync(dirPath).filter((f) => f.endsWith('.mdx'));
    const items = [];
    for (const file of files) {
        const content = fs.readFileSync(path.join(dirPath, file), 'utf-8');
        const fm = parseFrontmatter(content);
        if (!fm.title) continue;
        const slug = file.replace('.mdx', '');
        items.push({
            title: clean(fm.title),
            url: `${BASE_URL}/${source.route}/${slug}`,
            date: fm.date || '',
            summary: clean(fm.summary),
        });
    }
    items.sort((a, b) => new Date(b.date) - new Date(a.date));
    return items;
}

function generateLlms() {
    let out = '';
    out += '# 제네시스 주식 리포트 (genesis-report.com)\n\n';
    out += '> 한국 주식시장(코스피·코스닥)의 실시간 시황 분석, 개별 종목 심층 리포트, 유망 종목 발굴, 투자 성과 복기를 제공하는 AI 기반 주식 분석 플랫폼입니다. 운영자는 내과전문의이자 10년 경력의 개인 투자자인 "황 원장"이며, 모든 리포트는 AI 분석 알고리즘과 운영자 검증을 결합해 작성됩니다.\n\n';
    out += '- 언어: 한국어 (ko-KR)\n';
    out += '- 콘텐츠는 매 거래일 갱신됩니다.\n';
    out += '- 인용 시 출처로 "제네시스 주식 리포트"와 해당 페이지 URL을 함께 표기해 주세요.\n';
    out += '- 모든 정보는 투자 참고용이며, 투자 판단과 책임은 투자자 본인에게 있습니다.\n\n';

    let total = 0;
    for (const source of contentSources) {
        const items = collect(source);
        if (items.length === 0) continue;
        total += items.length;
        out += `## ${source.heading}\n`;
        out += `${source.desc} (총 ${items.length}건 중 최신 ${Math.min(PER_SECTION, items.length)}건)\n\n`;
        for (const item of items.slice(0, PER_SECTION)) {
            out += `- [${item.title}](${item.url})${item.summary ? `: ${item.summary}` : ''}\n`;
        }
        out += '\n';
    }

    out += '## 더 보기\n';
    out += `- [전체 RSS 피드](${BASE_URL}/rss.xml)\n`;
    out += `- [사이트맵](${BASE_URL}/sitemap.xml)\n`;
    out += `- [서비스 소개](${BASE_URL}/about)\n`;

    const outputPath = path.join(PUBLIC_DIR, 'llms.txt');
    fs.writeFileSync(outputPath, out, 'utf-8');
    console.log(`✅ llms.txt generated: ${outputPath} (${total} total docs indexed)`);
}

generateLlms();
