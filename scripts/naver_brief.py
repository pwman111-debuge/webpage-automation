"""네이버 블로그용 '간략 HTML' 생성기 — genesis MDX → 핵심만 추린 복붙용 HTML.

트리거: "네이버 블로그글 저장" / "네이버 블로그에 올릴 글 저장해줘"
→ 지정한 리포트(MDX)를 frontmatter summary(리드) + 본문의 '📌 논의 포인트 제목 +
   ✅ 결론'만 뽑아, 소제목 4꼭지 안팎의 짧은 HTML로 변환한다.
   naver_export.py(충실한 요약)와 달리 '핵심만' 담아 훨씬 간략하다.

설계:
  • 제목   : frontmatter title (브랜드어 '제네시스' 제거).
  • 리드   : frontmatter summary 앞 1~2문장.
  • 본문   : 각 '### 📌 …' 제목을 H2로, 바로 뒤 '**✅ 결론:** …'를 본문 한 단락으로.
             (📌/✅ 패턴이 없으면 각 H2 섹션의 첫 단락으로 폴백.)
  • 백링크 : content 폴더 → genesis-report.com 경로 매핑.
  • 태그   : frontmatter tags (브랜드 제거·중복 제거, 최대 6개).

출력:
  naver_out/<파일명>-naver.html  (브라우저로 열어 제목/본문 복사 → 네이버 글쓰기에 붙여넣기)
  추천 카테고리·제목·백링크는 터미널에 출력된다.

사용법:
  python -X utf8 scripts/naver_brief.py content/market-insight/20260621-iran-ceasefire-nps-rebalancing.mdx
"""
from __future__ import annotations

import html
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "naver_out"
SITE_URL = "https://genesis-report.com"

# content 폴더 → (사이트 URL 경로, 네이버 카테고리명)
FOLDER_MAP = [
    ("content/picks-feedback", "/picks/feedback", "투자성과 리포트"),
    ("content/market-analysis", "/market", "시황분석"),
    ("content/picks", "/picks", "유망종목"),
    ("content/stock-reports", "/analysis", "종목리포트"),
    ("content/market-insight", "/insight", "마켓인사이트"),
    ("content/education", "/education", "투자교육"),
]

MAX_POINTS = 5  # 너무 길어지지 않게 본문 꼭지 상한


def parse_frontmatter(text: str):
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    raw, body = text[3:end].strip(), text[end + 4:].lstrip("\n")
    fm = {}
    for line in raw.splitlines():
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        k, v = k.strip(), v.strip()
        if v.startswith("[") and v.endswith("]"):
            parts = [x.strip().strip('"').strip("'").strip() for x in v[1:-1].split(",")]
            fm[k] = [x for x in parts if x]
        else:
            fm[k] = v.strip().strip('"').strip("'")
    return fm, body


def scrub_brand(text: str) -> str:
    """네이버 블로그를 genesis 브랜드와 분리 — '제네시스' 용어 제거."""
    if not text:
        return ""
    text = text.replace("[제네시스 리포트]", "").replace("제네시스 리포트", "")
    text = text.replace("- 제네시스 모멘텀", "").replace("제네시스 모멘텀", "모멘텀")
    text = re.sub(r"제네시스\s*", "", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip(" -—·|\t").strip()


def md_inline(text: str) -> str:
    """간단한 인라인 마크다운(**굵게**)만 HTML로. 나머지는 escape."""
    out, last = [], 0
    for m in re.finditer(r"\*\*(.+?)\*\*", text):
        out.append(html.escape(text[last:m.start()]))
        out.append("<b>" + html.escape(m.group(1)) + "</b>")
        last = m.end()
    out.append(html.escape(text[last:]))
    return "".join(out)


def first_sentences(text: str, n: int = 2) -> str:
    """리드용: 앞 n문장만."""
    parts = re.split(r"(?<=[.!?。])\s+", text.strip())
    return " ".join(parts[:n]).strip()


def extract_points(body: str):
    """본문에서 (소제목, 결론) 꼭지 리스트 추출.

    1순위: '### 📌 …' 제목 + 바로 뒤 '**✅ 결론:** …'.
    폴백 : '## …' 섹션(시사점/리스크/뷰 등 정형 섹션 제외)의 첫 단락.
    """
    lines = body.splitlines()
    points = []

    # 1순위: 📌 + ✅ 결론
    cur_head = None
    for line in lines:
        s = line.strip()
        mh = re.match(r"^###\s+📌\s*(.*)", s)
        if mh:
            cur_head = re.sub(r"\s*[-—]\s*$", "", mh.group(1)).strip()
            continue
        mc = re.match(r"^\*\*\s*✅?\s*결론[:：]?\s*\*\*\s*(.*)", s)
        if mc and cur_head:
            concl = mc.group(1).strip()
            concl = re.sub(r"^[:：]\s*", "", concl)
            points.append((cur_head, concl))
            cur_head = None
    if points:
        return points[:MAX_POINTS]

    # 폴백: H2 섹션 첫 단락 (정형/부록 섹션은 건너뜀)
    skip = re.compile(r"(논의 배경|투자 시사점|리스크|뷰|면책|유의|Q\s*&\s*A|부록)")
    head, buf = None, []
    for line in lines + ["## __END__"]:
        m = re.match(r"^##\s+(.*)", line)
        if m:
            if head and not skip.search(head):
                para = next((b.strip() for b in buf if b.strip() and not b.startswith(("#", "|", ">", "-"))), "")
                if para:
                    points.append((head, para))
            head, buf = m.group(1).strip(), []
        else:
            buf.append(line)
    return points[:MAX_POINTS]


def backlink_for(rel_path: str):
    norm = rel_path.replace("\\", "/")
    fname = os.path.splitext(os.path.basename(norm))[0]
    for prefix, url_path, cat in FOLDER_MAP:
        if (prefix + "/") in (norm + "/"):
            return f"{SITE_URL}{url_path}/{fname}", cat
    return SITE_URL, "(수동 선택)"


def render(mdx_path: str) -> int:
    p = Path(mdx_path)
    if not p.exists():
        print(f"[오류] 파일 없음: {mdx_path}")
        return 1
    fm, body = parse_frontmatter(p.read_text(encoding="utf-8"))
    body = scrub_brand(body)

    title = scrub_brand(fm.get("title", p.stem))
    lead = first_sentences(scrub_brand(fm.get("summary", "")), 2)
    rel = str(p.relative_to(ROOT)) if p.is_absolute() else str(p)
    backlink, category = backlink_for(rel)

    raw_tags = fm.get("tags", []) if isinstance(fm.get("tags"), list) else []
    tags, seen = [], set()
    for t in raw_tags:
        s = scrub_brand(t).replace(" ", "")
        if s and s not in seen and len(s) <= 18:
            seen.add(s); tags.append(s)
    tags = tags[:6]

    points = extract_points(body)
    points_html = "\n".join(
        f'<h2>{md_inline(head)}</h2>\n<p>{md_inline(concl)}</p>'
        for head, concl in points
    )
    tags_html = " ".join("#" + t for t in tags)

    post_html = f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
body{{font-family:'맑은 고딕',sans-serif;max-width:680px;margin:24px auto;padding:0 16px;line-height:1.8;color:#222}}
h1{{font-size:22px;margin-bottom:18px}}
.lead{{font-size:16px;font-weight:700;background:#f7faf7;border-left:4px solid #1a8917;padding:10px 14px;margin:14px 0}}
h2{{font-size:17px;margin-top:24px;border-bottom:1px solid #eee;padding-bottom:4px}}
p{{margin:8px 0}}
.box{{border:1px dashed #ccc;padding:8px 12px;margin-bottom:14px;border-radius:6px;font-size:13px;color:#555}}
.tags{{color:#1a8917;font-size:14px;margin-top:8px}}
a{{color:#1a64d4}} hr{{border:0;border-top:1px solid #eee;margin:22px 0}}
.note{{color:#888;font-size:13px}}
</style></head><body>

<div class="box">📋 네이버 글쓰기 붙여넣기 — <b>카테고리: {html.escape(category)}</b> · 제목/본문 각각 복사 (이 줄은 복사 제외)</div>

<h1>{html.escape(title)}</h1>

{f'<p class="lead">{md_inline(lead)}</p>' if lead else ''}

{points_html}

<hr>
<p>📊 전체 리포트(표·리스크 포함) → <a href="{backlink}">{backlink.replace('https://', '')}</a></p>
<p class="note">※ 본 글은 정보 제공 목적이며, 투자 판단과 책임은 투자자 본인에게 있습니다.</p>
{f'<p class="tags">{tags_html}</p>' if tags_html else ''}

</body></html>
"""

    OUT_DIR.mkdir(exist_ok=True)
    out_path = OUT_DIR / (p.stem + "-naver.html")
    out_path.write_text(post_html, encoding="utf-8")

    print(f"[완료] 간략 변환: {mdx_path}")
    print(f"  추천 카테고리 : {category}")
    print(f"  제목         : {title}")
    print(f"  꼭지 수      : {len(points)}")
    print(f"  백링크       : {backlink}")
    print(f"  출력 HTML    : {out_path}")
    print(f"  → 브라우저로 열어 제목/본문 복사 후 네이버 글쓰기에 붙여넣기")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) < 2:
        print(__doc__)
        raise SystemExit(1)
    raise SystemExit(render(sys.argv[1]))
