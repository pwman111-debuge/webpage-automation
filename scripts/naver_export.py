"""네이버 블로그 붙여넣기용 변환기 — genesis MDX → "충실한 요약 + 백링크" HTML.

genesis 원문(MDX)은 JSX·차트·쿠팡배너가 페이지 템플릿에서 주입되는 구조라 본문은
대체로 깨끗한 마크다운이다. 이 스크립트는 frontmatter `summary`를 리드로 쓰고,
본문을 리스크/면책 섹션 직전까지 충실히 담아 HTML로 변환한 뒤, 하단에 원문 백링크를 붙인다.
중복 콘텐츠로 인한 저품질을 피하려 "전문"이 아닌 "충실한 요약"만 내보낸다.

사용법:
  python -X utf8 scripts/naver_export.py content/picks/20260529-genesis-report.mdx

출력:
  naver_out/<파일명>.html  (브라우저로 열어 본문 영역 전체선택→복사 후 네이버 글쓰기에 붙여넣기)
  추천 카테고리와 제목은 터미널에 출력된다.
"""
import html
import os
import re
import sys
from pathlib import Path

try:
    from markdown_it import MarkdownIt
except ImportError:
    print("[오류] markdown-it-py 필요: pip install markdown-it-py")
    raise SystemExit(1)

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "naver_out"
SITE_URL = "https://genesis-report.com"

# genesis 폴더 → (사이트 URL 경로, 네이버 카테고리명)
FOLDER_MAP = {
    "content/picks-feedback": ("/picks/feedback", "투자성과 리포트"),
    "content/picks": ("/picks", "유망종목"),
    "content/market-analysis": ("/market", "시황분석"),
    "content/stock-reports": ("/analysis", "종목리포트"),
    "content/market-insight": ("/insight", "마켓인사이트"),
    "content/education": ("/education", "투자교육"),
}

# 요약에서 제외할 (리스크/면책/부록) 섹션 헤딩 키워드
STOP_HEADING_RE = re.compile(
    r"(리스크\s*가이드|투자\s*유의|유의\s*사항|면책|책임|disclaimer|고지|자주\s*묻|Q\s*&\s*A|부록|용어)",
    re.IGNORECASE,
)
SUMMARY_CHAR_BUDGET = 1500  # 본문 누적 길이(이 이상이면 다음 섹션부터 중단)


def parse_frontmatter(text: str):
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    raw = text[3:end].strip()
    body = text[end + 4:].lstrip("\n")
    fm = {}
    for line in raw.splitlines():
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        k, v = k.strip(), v.strip()
        if v.startswith("[") and v.endswith("]"):
            items = re.findall(r'"([^"]*)"|\'([^\']*)\'|([^,\[\]]+)', v[1:-1])
            fm[k] = [a or b or c.strip() for a, b, c in items if (a or b or c.strip())]
        else:
            fm[k] = v.strip().strip('"').strip("'")
    return fm, body


def build_backlink(mdx_path: str):
    norm = mdx_path.replace("\\", "/")
    fname = os.path.splitext(os.path.basename(norm))[0]
    for prefix, (url_path, cat) in FOLDER_MAP.items():
        if prefix in norm:
            return f"{SITE_URL}{url_path}/{fname}", cat
    return SITE_URL, None


def strip_noise(body: str) -> str:
    """import/export/JSX 컴포넌트 줄 제거 (본문에 거의 없지만 안전장치)."""
    out = []
    for line in body.splitlines():
        s = line.strip()
        if s.startswith(("import ", "export ")):
            continue
        if re.match(r"^<[A-Z][A-Za-z0-9]*[\s/>]", s):  # <CoupangBanner .../> 류
            continue
        out.append(line)
    return "\n".join(out)


def summarize_body(body: str) -> str:
    """본문을 H2(## ) 단위로 끊어, 리스크/면책 섹션 전까지 예산 내에서 충실히 담는다."""
    lines = body.splitlines()
    # 섹션 분할: 각 섹션은 (heading_text, [lines])
    sections, cur_head, cur = [], None, []
    for line in lines:
        m = re.match(r"^##\s+(.*)", line)
        if m:
            if cur_head is not None or cur:
                sections.append((cur_head, cur))
            cur_head, cur = m.group(1).strip(), [line]
        else:
            cur.append(line)
    if cur_head is not None or cur:
        sections.append((cur_head, cur))

    kept, total, truncated = [], 0, False
    for i, (head, sec_lines) in enumerate(sections):
        if head and STOP_HEADING_RE.search(head):
            truncated = True
            break
        if total >= SUMMARY_CHAR_BUDGET and i > 0:
            truncated = True
            break
        kept.append("\n".join(sec_lines))
        total += len("\n".join(sec_lines))
    if len(kept) < len(sections):
        truncated = True
    return "\n".join(kept).strip(), truncated


def render(mdx_path: str) -> int:
    p = Path(mdx_path)
    if not p.exists():
        print(f"[오류] 파일 없음: {mdx_path}")
        return 1
    text = p.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(text)
    title = fm.get("title", p.stem)
    summary = fm.get("summary", "")
    backlink, category = build_backlink(mdx_path)
    if category is None:
        print(f"[경고] 매핑되는 카테고리 없음: {mdx_path}")
        category = "(수동 선택)"

    body = strip_noise(body)
    summary_md, truncated = summarize_body(body)

    md = MarkdownIt("commonmark")
    for rule in ("table", "strikethrough"):
        try:
            md.enable(rule)
        except Exception:
            pass

    body_html = md.render(summary_md)
    lead_html = f'<p style="font-size:17px;font-weight:700;line-height:1.7">{html.escape(summary)}</p>' if summary else ""
    more_note = '<p style="color:#888">··· 이하 전문(차트·리스크 가이드·목표가 근거 포함)은 원문에서 확인하세요.</p>' if truncated else ""

    backlink_box = f"""
<hr>
<p style="font-size:16px"><b>📊 전체 리포트 보기</b></p>
<p>👉 <a href="{backlink}">{backlink}</a></p>
<p style="color:#888;font-size:13px">본 글은 정보 제공 목적이며, 투자 판단과 책임은 투자자 본인에게 있습니다.</p>
"""

    post_html = f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>body{{font-family:'맑은 고딕',sans-serif;max-width:720px;margin:24px auto;padding:0 16px;line-height:1.75;color:#222}}
table{{border-collapse:collapse;width:100%;margin:12px 0}} th,td{{border:1px solid #ddd;padding:6px 10px;font-size:14px}}
th{{background:#f6f8fa}} blockquote{{border-left:4px solid #1a8917;margin:12px 0;padding:4px 14px;color:#444;background:#f7faf7}}
h2{{font-size:19px;margin-top:28px}} h3{{font-size:16px}} hr{{border:0;border-top:1px solid #eee;margin:24px 0}}
.guide{{background:#fff7e6;border:1px solid #ffe0a3;padding:10px 14px;border-radius:8px;font-size:13px;color:#7a5b00;margin-bottom:18px}}</style>
</head><body>
<div class="guide">📋 네이버 글쓰기에 붙여넣기 — <b>추천 카테고리: {category}</b> · 제목/본문을 각각 복사하세요. (이 안내줄은 복사 제외)</div>
<div style="border:1px dashed #ccc;padding:8px 12px;margin-bottom:14px;border-radius:6px"><b>제목:</b> {html.escape(title)}</div>
<div id="naver-body">
{lead_html}
{body_html}
{more_note}
{backlink_box}
</div>
</body></html>"""

    OUT_DIR.mkdir(exist_ok=True)
    out_path = OUT_DIR / (p.stem + ".html")
    out_path.write_text(post_html, encoding="utf-8")

    print(f"[완료] 변환: {mdx_path}")
    print(f"  추천 카테고리 : {category}")
    print(f"  제목         : {title}")
    print(f"  백링크       : {backlink}")
    print(f"  요약 잘림     : {'예 (전문 일부만)' if truncated else '아니오 (본문 전체)'}")
    print(f"  출력 HTML    : {out_path}")
    print(f"  → 브라우저로 열어 '본문' 영역 복사 후 네이버 글쓰기에 붙여넣기")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) < 2:
        print(__doc__)
        raise SystemExit(1)
    raise SystemExit(render(sys.argv[1]))
