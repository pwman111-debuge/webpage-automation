"""쿠팡파트너스 OpenAPI로 genesis-report.com 제휴 상품 카탈로그(coupang-products.ts) 자동 생성.

카테고리별 검색어로 실제 상품을 조회하고 제휴 딥링크/이미지를 받아
src/lib/coupang-products.ts 의 COUPANG_LINKS 블록을 새 상품으로 교체한다.

실행:
  COUPANG_ACCESS_KEY=... COUPANG_SECRET_KEY=... python -X utf8 scripts/gen_coupang_products.py

필요 env:
  COUPANG_ACCESS_KEY
  COUPANG_SECRET_KEY
"""
import hashlib
import hmac
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ACCESS_KEY = os.getenv("COUPANG_ACCESS_KEY", "")
SECRET_KEY = os.getenv("COUPANG_SECRET_KEY", "")
DOMAIN = "https://api-gateway.coupang.com"

TS_PATH = Path(__file__).resolve().parent.parent / "src" / "lib" / "coupang-products.ts"

PRODUCTS_PER_CATEGORY = 3

# 카테고리: (검색어, 설명 접두 태그라인). 키워드 매칭/폴백 로직은 .ts 템플릿이 그대로 유지한다.
CATEGORIES: dict[str, tuple[str, str]] = {
    "투자서적": ("주식 투자 베스트셀러", "주식·가치투자 입문부터 실전까지, 검증된 투자 도서"),
    "차트분석서": ("주식 차트 기술적분석 책", "캔들·이평선·보조지표 — 기술적 분석 실전서"),
    "모니터": ("27인치 모니터", "HTS 듀얼 모니터로 호가창·차트 분리 배치"),
    "키보드": ("무선 키보드 마우스 세트", "장시간 트레이딩에 적합한 무선 키보드+마우스"),
    "의자": ("인체공학 사무용 의자", "장시간 트레이딩용 허리 지지·메쉬 통풍 의자"),
    "매매일지": ("주식 매매일지 노트", "진입가·손절가 기록으로 투자 복기 습관화"),
    "재테크서적": ("재테크 베스트셀러", "자본주의 본질과 부의 축적 원리를 짚는 재테크서"),
    "스마트워치": ("스마트워치 통화", "실시간 시세 알림·뉴스 푸시 수신 가능"),
    "경제신문": ("경제 경영 매거진 정기구독", "거시경제·산업 트렌드 심층 분석 매거진"),
    "코인서적": ("비트코인 투자 책", "디지털 자산·암호화폐 투자 인사이트"),
}

# 매칭/선택 로직 — 생성 대상이 아니며 그대로 보존한다.
STATIC_TAIL = '''const CATEGORY_KEYWORD_MAP: Record<string, string[]> = {
  투자서적: ['주식', '투자', '종목', '코스피', '코스닥', '장기투자', '가치투자', '버핏', '주주'],
  차트분석서: ['차트', '기술적분석', '캔들', '보조지표', 'rsi', 'macd', '이평선'],
  모니터: ['hts', '트레이딩', '데이트레이딩', '스캘핑'],
  코인서적: ['비트코인', '이더리움', '코인', '가상화폐', '암호화폐', '리플', 'btc', 'eth'],
  재테크서적: ['배당', 'etf', '펀드', '재테크', '포트폴리오', '연금', '퇴직'],
  경제신문: ['경제', '금리', '환율', '달러', 'fomc', '물가', 'cpi', 'ppi', '인플레이션', 'fed'],
  매매일지: ['매매', '복기', '투자일지'],
  스마트워치: [],
  키보드: [],
  의자: [],
};

const FALLBACK_CATEGORIES = ['투자서적', '재테크서적', '매매일지', '모니터'];

function hashSeed(s: string): number {
  let h = 0;
  for (let i = 0; i < s.length; i++) {
    h = (h * 31 + s.charCodeAt(i)) | 0;
  }
  return Math.abs(h);
}

export function pickCoupangProducts(seed: string, keywords: string[], limit = 2): CoupangProduct[] {
  const kw = keywords.join(' ').toLowerCase();
  const matched = Object.entries(CATEGORY_KEYWORD_MAP)
    .filter(([, kws]) => kws.some((k) => kw.includes(k)))
    .map(([cat]) => cat);
  const orderedCats = [...matched, ...FALLBACK_CATEGORIES.filter((c) => !matched.includes(c))];

  const candidates: CoupangProduct[] = [];
  const seenUrls = new Set<string>();
  for (const cat of orderedCats) {
    for (const p of COUPANG_LINKS[cat] ?? []) {
      if (seenUrls.has(p.url)) continue;
      candidates.push(p);
      seenUrls.add(p.url);
    }
  }
  if (candidates.length === 0) return [];

  const h = hashSeed(seed);
  const picked: CoupangProduct[] = [];
  const usedIdx = new Set<number>();
  for (let i = 0; picked.length < limit && picked.length < candidates.length; i++) {
    const idx = (h + i * 7919) % candidates.length;
    if (!usedIdx.has(idx)) {
      usedIdx.add(idx);
      picked.push(candidates[idx]);
    }
  }
  return picked;
}
'''


def _generate_authorization(method: str, path_with_query: str) -> str:
    parts = path_with_query.split("?", 1)
    path = parts[0]
    query = parts[1] if len(parts) > 1 else ""
    datetime_str = datetime.now(timezone.utc).strftime("%y%m%dT%H%M%SZ")
    message = datetime_str + method + path + query
    signature = hmac.new(
        SECRET_KEY.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return (
        f"CEA algorithm=HmacSHA256, access-key={ACCESS_KEY}, "
        f"signed-date={datetime_str}, signature={signature}"
    )


def _api_call(method: str, path_with_query: str, body: dict | None = None) -> dict:
    authorization = _generate_authorization(method, path_with_query)
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(DOMAIN + path_with_query, data=data, method=method)
    req.add_header("Authorization", authorization)
    req.add_header("Content-Type", "application/json;charset=UTF-8")
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode("utf-8"))


def search_products(keyword: str, limit: int = 5) -> list[dict]:
    encoded = urllib.parse.quote(keyword)
    path = (
        "/v2/providers/affiliate_open_api/apis/openapi/v1/products/search"
        f"?keyword={encoded}&limit={limit}"
    )
    result = _api_call("GET", path)
    if str(result.get("rCode", "")) != "0":
        print(f"  [쿠팡] API 오류({keyword}): {result.get('rMessage')}")
        return []
    products = result.get("data", {}).get("productData", []) or []
    items: list[dict] = []
    for p in products:
        url = p.get("productUrl", "")
        if not url:
            continue
        items.append({
            "name": p.get("productName", "").strip(),
            "url": url,
            "image": p.get("productImage", ""),
            "price": p.get("productPrice", 0),
        })
    return items


def ts_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace("'", "\\'").replace("\n", " ")


def html_escape(s: str) -> str:
    return (
        s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    )


def build_snippet(name: str, url: str, image: str) -> str:
    alt = html_escape(name)
    return (
        f'<a href="{url}" target="_blank" referrerpolicy="unsafe-url">'
        f'<img src="{image}" alt="{alt}" width="200" height="200" '
        f'style="border-radius:8px;object-fit:contain" loading="lazy"></a>'
    )


def render_product(name: str, tagline: str, url: str, image: str, price: int) -> str:
    price_str = f"{price:,}원" if price else "가격은 링크에서 확인"
    desc = f"{tagline} · {price_str}"
    snippet = build_snippet(name, url, image)
    return (
        "    {\n"
        f"      name: '{ts_escape(name)}',\n"
        f"      desc: '{ts_escape(desc)}',\n"
        f"      url: '{url}',\n"
        f"      htmlSnippet: `{snippet}`,\n"
        "    },"
    )


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    if not ACCESS_KEY or not SECRET_KEY:
        print("ERROR: COUPANG_ACCESS_KEY / COUPANG_SECRET_KEY 환경변수 미설정")
        return 1

    blocks: list[str] = []
    total = 0
    for cat, (query, tagline) in CATEGORIES.items():
        try:
            items = search_products(query, limit=PRODUCTS_PER_CATEGORY + 2)
        except Exception as e:
            print(f"  [{cat}] 검색 실패: {e}")
            items = []
        items = items[:PRODUCTS_PER_CATEGORY]
        if not items:
            print(f"  [{cat}] 결과 없음 — 건너뜀")
            continue
        rendered = "\n".join(render_product(it["name"], tagline, it["url"], it["image"], it["price"]) for it in items)
        blocks.append(f"  {cat}: [\n{rendered}\n  ],")
        total += len(items)
        print(f"  [{cat}] {len(items)}개 ('{query}')")

    if not blocks:
        print("ERROR: 어떤 카테고리도 상품을 받지 못함 — .ts 미수정")
        return 1

    header = (
        "export type CoupangProduct = {\n"
        "  name: string;\n"
        "  desc: string;\n"
        "  url: string;\n"
        "  htmlSnippet: string;\n"
        "};\n\n"
        "// 자동 생성: scripts/gen_coupang_products.py (쿠팡파트너스 OpenAPI)\n"
        "const COUPANG_LINKS: Record<string, CoupangProduct[]> = {\n"
    )
    content = header + "\n".join(blocks) + "\n};\n\n" + STATIC_TAIL
    TS_PATH.write_text(content, encoding="utf-8")
    print(f"\n생성 완료: {TS_PATH}  (카테고리 {len(blocks)}개 / 상품 {total}개)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
