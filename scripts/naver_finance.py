"""
네이버 증권 데이터 수집 스크립트 - 제네시스 워크플로우용
사용법: python naver_finance.py [명령] [인자]

명령:
  market              - 1단계: 시장 국면 (KOSPI/KOSDAQ 지수)
  sector              - 1단계: 업종별 시세 상위/하위
  theme               - 1단계: 테마별 시세
  stock [종목코드]    - 2단계: 종목 기본 정보 + 현재가
  investor [종목코드] - 3단계: 투자자별 매매동향
  short [종목코드]    - 3단계: 공매도 현황
  screen [업종번호]   - 2단계: 업종 내 종목 리스트
  all [종목코드]      - 전체: 종목 종합 분석 데이터

예시:
  python naver_finance.py market
  python naver_finance.py stock 005930
  python naver_finance.py sector
  python naver_finance.py all 005930
"""

import sys
import io
import ssl
import json
import re
from datetime import datetime

import requests
from bs4 import BeautifulSoup

# Windows 터미널 한글 출력 설정
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ── 공통 설정 ──────────────────────────────────────────────
SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://finance.naver.com/",
    "Accept-Language": "ko-KR,ko;q=0.9",
})
SESSION.verify = False

MOBILE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://m.stock.naver.com/",
    "Accept": "application/json",
}

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def fetch_json_mobile(url):
    resp = requests.get(url, headers=MOBILE_HEADERS, verify=False, timeout=10)
    resp.raise_for_status()
    return resp.json()


def fetch_html_pc(url, encoding="euc-kr"):
    resp = SESSION.get(url, timeout=10)
    resp.encoding = encoding
    return BeautifulSoup(resp.text, "html.parser")


def divider(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


# ── 1단계: 시장 국면 ───────────────────────────────────────
def cmd_market():
    divider("1단계 - 시장 국면 (KOSPI / KOSDAQ)")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"조회 시각: {now}\n")

    for index_code in ["KOSPI", "KOSDAQ"]:
        try:
            d = fetch_json_mobile(f"https://m.stock.naver.com/api/index/{index_code}/basic")
            direction = "▲" if d.get("compareToPreviousPrice", {}).get("name") == "RISING" else "▼"
            print(f"[{index_code}]")
            print(f"  현재가:  {d.get('closePrice', 'N/A')}")
            print(f"  등락:    {direction} {d.get('compareToPreviousClosePrice', 'N/A')} ({d.get('fluctuationsRatio', 'N/A')}%)")
            print(f"  상태:    {d.get('marketStatus', 'N/A')}")
            print()
        except Exception as e:
            print(f"[{index_code}] 오류: {e}")

    # 시장 국면 판단 힌트
    print("※ 시장 국면 판단은 위 수치 + 이평선 위치를 종합해 판단하세요")
    print("  (상승추세 초입 / 상승추세 지속 / 조정 중 / 하락추세)")


# ── 1단계: 업종별 시세 ─────────────────────────────────────
def cmd_sector():
    divider("1단계 - 업종별 시세 (KOSPI + KOSDAQ)")
    url = "https://finance.naver.com/sise/sise_group.naver?type=upjong"
    try:
        soup = fetch_html_pc(url)
        rows = soup.select("table.type_1 tr")
        sectors = []
        for row in rows:
            cols = row.select("td")
            if len(cols) < 4:
                continue
            name_tag = cols[0].find("a")
            if not name_tag:
                continue
            name = name_tag.get_text(strip=True)
            href = name_tag.get("href", "")
            no_match = re.search(r"no=(\d+)", href)
            sector_no = no_match.group(1) if no_match else ""
            # col[0]=업종명, col[1]=등락률, col[2]=전체, col[3]=상승, col[4]=보합, col[5]=하락
            chg_text = cols[1].get_text(strip=True) if len(cols) > 1 else ""
            total     = cols[2].get_text(strip=True) if len(cols) > 2 else ""
            rising    = cols[3].get_text(strip=True) if len(cols) > 3 else ""
            falling   = cols[5].get_text(strip=True) if len(cols) > 5 else ""
            try:
                chg = float(chg_text.replace("+", "").replace("%", "").replace(",", ""))
            except ValueError:
                chg = 0
            sectors.append({
                "no": sector_no,
                "name": name,
                "change_pct": chg,
                "change_str": chg_text,
                "total": total,
                "rising": rising,
                "falling": falling,
            })

        if not sectors:
            print("업종 데이터를 파싱하지 못했습니다.")
            return

        sectors.sort(key=lambda x: x["change_pct"], reverse=True)
        print(f"{'순위':<4} {'업종명':<24} {'등락률':>8}  {'상승/하락/전체':>14}  {'번호'}")
        print("-" * 65)
        for i, s in enumerate(sectors[:10], 1):
            print(f"{i:<4} {s['name']:<24} {s['change_str']:>8}  {s['rising']}↑/{s['falling']}↓/{s['total']}  ({s['no']})")
        print()
        print("▼ 하위 업종 (약세)")
        print("-" * 65)
        for s in sectors[-5:]:
            print(f"     {s['name']:<24} {s['change_str']:>8}  {s['rising']}↑/{s['falling']}↓/{s['total']}")

    except Exception as e:
        print(f"업종 조회 오류: {e}")


# ── 1단계: 테마별 시세 ─────────────────────────────────────
def cmd_theme():
    divider("1단계 - 테마별 시세")
    url = "https://finance.naver.com/sise/sise_group.naver?type=theme"
    try:
        soup = fetch_html_pc(url)
        rows = soup.select("table.type_1 tr")
        themes = []
        for row in rows:
            cols = row.select("td")
            if len(cols) < 2:
                continue
            name_tag = cols[0].find("a")
            if not name_tag:
                continue
            name = name_tag.get_text(strip=True)
            # 컬럼 구조: [테마명, 전일대비(등락률%), 전체종목수, 상승, 보합, 하락, 등락그래프]
            # cols[2]는 '전체 종목 수'다. 이를 등락률로 읽으면 "+148.00%" 같은 값이 나온다.
            values = [c.get_text(strip=True) for c in cols[1:3]]
            try:
                chg = float(values[0].replace(",", "").replace("%", "").replace("+", ""))
            except (ValueError, IndexError):
                chg = 0
            themes.append({"name": name, "change_pct": chg})

        themes.sort(key=lambda x: x["change_pct"], reverse=True)
        print(f"{'순위':<4} {'테마명':<30} {'등락률':>8}")
        print("-" * 50)
        for i, t in enumerate(themes[:15], 1):
            sign = "+" if t["change_pct"] >= 0 else ""
            print(f"{i:<4} {t['name']:<30} {sign}{t['change_pct']:>6.2f}%")

    except Exception as e:
        print(f"테마 조회 오류: {e}")


# ── 2단계: 업종 내 종목 스크리닝 ───────────────────────────
def cmd_screen(sector_no):
    divider(f"2단계 - 업종({sector_no}) 내 종목 리스트")
    url = f"https://finance.naver.com/sise/sise_group_detail.naver?type=upjong&no={sector_no}"
    try:
        soup = fetch_html_pc(url)
        rows = soup.select("table.type_5 tr, table.type_3 tr")
        stocks = []
        for row in rows:
            cols = row.select("td")
            if len(cols) < 5:
                continue
            name_tag = cols[0].find("a")
            if not name_tag:
                continue
            name = name_tag.get_text(strip=True)
            code_match = re.search(r"code=(\d+)", name_tag.get("href", ""))
            code = code_match.group(1) if code_match else ""
            values = [c.get_text(strip=True) for c in cols[1:6]]
            stocks.append({"name": name, "code": code, "values": values})

        if not stocks:
            print("종목 데이터를 가져오지 못했습니다. 업종 번호를 확인하세요.")
            return

        print(f"{'종목명':<20} {'코드':<8} {'현재가':>10} {'등락률':>8}")
        print("-" * 55)
        for s in stocks[:20]:
            vals = s["values"]
            price = vals[0] if vals else ""
            chg   = vals[1] if len(vals) > 1 else ""
            print(f"{s['name']:<20} {s['code']:<8} {price:>10} {chg:>8}")

    except Exception as e:
        print(f"업종 종목 조회 오류: {e}")


# ── 2단계: 종목 기본 정보 ─────────────────────────────────
def cmd_stock(code):
    divider(f"2단계 - 종목 기본 정보 [{code}]")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        d = fetch_json_mobile(f"https://m.stock.naver.com/api/stock/{code}/basic")
        direction = "▲" if d.get("compareToPreviousPrice", {}).get("name") == "RISING" else "▼"

        print(f"조회 시각:    {now}  ★ 현재가 기준 시각 확정")
        print(f"종목명:       {d.get('stockName', 'N/A')}")
        print(f"종목코드:     {d.get('itemCode', 'N/A')}")
        print(f"거래소:       {d.get('stockExchangeName', 'N/A')}")
        print(f"현재가:       {d.get('closePrice', 'N/A')} 원")
        print(f"등락:         {direction} {d.get('compareToPreviousClosePrice', 'N/A')} ({d.get('fluctuationsRatio', 'N/A')}%)")
        print(f"시장 상태:    {d.get('marketStatus', 'N/A')}")

        over = d.get("overMarketPriceInfo", {})
        if over:
            print(f"시간외 현재가: {over.get('overPrice', 'N/A')} ({over.get('fluctuationsRatio', 'N/A')}%)")

    except Exception as e:
        print(f"종목 기본 조회 오류: {e}")

    # 밸류에이션 요약 + 재무 + 컨센서스 (모바일 API)
    # PC HTML(main.naver / coinfo.naver)은 테이블 셀렉터가 바뀌어 빈 결과만 반환하므로
    # integration / finance API로 대체한다.
    print()
    print("[밸류에이션 요약 - 네이버 증권]")
    integ = None
    try:
        integ = fetch_json_mobile(f"https://m.stock.naver.com/api/stock/{code}/integration")
        for item in integ.get("totalInfos", []):
            desc = f"  ({item['valueDesc']})" if item.get("valueDesc") else ""
            print(f"  {item.get('key', ''):<12}: {item.get('value', '-')}{desc}")
    except Exception as e:
        print(f"  밸류에이션 조회 오류: {e}")

    print()
    print("[기업실적분석 - 최근 3개년(A) + 전망치(E)]")
    try:
        fin = fetch_json_mobile(
            f"https://m.stock.naver.com/api/stock/{code}/finance/annual")["financeInfo"]
        cols = [(t["key"], t["title"], t["isConsensus"]) for t in fin["trTitleList"]]
        header = "".join(f"{t + ('(E)' if c == 'Y' else '(A)'):>14}" for _, t, c in cols)
        print(f"  {'항목':<16}{header}")
        keep = ("매출액", "영업이익", "당기순이익", "영업이익률", "ROE",
                "부채비율", "EPS", "PER", "BPS", "PBR", "주당배당금")
        for row in fin["rowList"]:
            if not any(row["title"].startswith(k) for k in keep):
                continue
            line = "".join(
                f"{((row['columns'].get(k) or {}).get('value') or '-'):>14}"
                for k, _, _ in cols)
            print(f"  {row['title']:<16}{line}")
        print("  ※ 전망치(E)는 컨센서스이며 실제 결과와 다를 수 있습니다.")
    except Exception as e:
        print(f"  재무 정보 조회 오류: {e}")

    print()
    print("[증권사 컨센서스]")
    try:
        cons = (integ or {}).get("consensusInfo") or {}
        if cons:
            print(f"  목표주가 평균: {cons.get('priceTargetMean', '-')} 원")
            print(f"  투자의견(5점): {cons.get('recommMean', '-')}")
            print(f"  기준일:        {cons.get('createDate', '-')}")
        else:
            print("  컨센서스 미형성 종목 (참여 증권사 부족)")
    except Exception as e:
        print(f"  컨센서스 조회 오류: {e}")


# ── 3단계: 투자자별 매매동향 ───────────────────────────────
def cmd_investor(code):
    divider(f"3단계 - 투자자별 매매동향 [{code}]")
    try:
        soup = fetch_html_pc(f"https://finance.naver.com/item/frgn.naver?code={code}")
        rows = soup.select("table.type2 tr, table.frgn_table tr")
        # frgn.naver 컬럼 구조 (인덱스):
        #   0 날짜 | 1 종가 | 2 전일비 | 3 등락률 | 4 거래량
        #   5 기관 순매매량 | 6 외국인 순매매량 | 7 외국인 보유주수 | 8 외국인 보유율
        # 과거 구현은 texts[:5]를 출력해 수급 대신 시세(전일비·등락률·거래량)를 찍었다.
        print(f"{'날짜':<12} {'종가':>10} {'등락률':>8} {'기관':>12} {'외국인':>12} {'외인보유율':>9}")
        print("-" * 70)
        count = 0
        cum_org = cum_frgn = 0
        for row in rows:
            cols = row.select("td")
            if len(cols) < 7:
                continue
            texts = [c.get_text(strip=True) for c in cols]
            if not re.match(r"\d{4}\.\d{2}\.\d{2}", texts[0]):
                continue

            def to_int(s):
                try:
                    return int(s.replace(",", "").replace("+", ""))
                except ValueError:
                    return 0

            org, frgn = to_int(texts[5]), to_int(texts[6])
            cum_org += org
            cum_frgn += frgn
            hold = texts[8] if len(texts) > 8 else ""
            print(f"  {texts[0]:<12} {texts[1]:>10} {texts[3]:>8} "
                  f"{texts[5]:>12} {texts[6]:>12} {hold:>9}")
            count += 1
            if count in (5, 20):
                print(f"  {'':-<12} {count}일 누적: 기관 {cum_org:+,} / 외국인 {cum_frgn:+,}")
            if count >= 20:
                break

        if count == 0:
            print("  (표 파싱 실패 - 페이지 직접 확인 권장)")
            print(f"  URL: https://finance.naver.com/item/frgn.naver?code={code}")
        else:
            print()
            print("  ※ 단위: 주식수. '쌍끌이'는 기관·외국인이 동시에 (+)일 때만 사용한다.")

    except Exception as e:
        print(f"투자자 동향 조회 오류: {e}")


# ── 3단계: 공매도 현황 ─────────────────────────────────────
def cmd_short(code):
    divider(f"3단계 - 공매도 현황 [{code}]")
    try:
        soup = fetch_html_pc(
            f"https://finance.naver.com/item/short_sell.naver?code={code}",
            encoding="utf-8"
        )
        rows = soup.select("table tr")
        count = 0
        for row in rows:
            cols = row.select("td, th")
            if len(cols) >= 3:
                texts = [c.get_text(strip=True) for c in cols[:5]]
                if any(texts):
                    print("  " + " | ".join(texts))
                    count += 1
            if count >= 15:
                break
        if count == 0:
            print(f"  공매도 데이터 없음 또는 직접 확인 필요")
            print(f"  URL: https://finance.naver.com/item/short_sell.naver?code={code}")
    except Exception as e:
        print(f"공매도 조회 오류: {e}")


# ── 전체 종합 ─────────────────────────────────────────────
def cmd_all(code):
    cmd_stock(code)
    cmd_investor(code)
    cmd_short(code)
    print()
    divider("참고 링크")
    print(f"  종목분석:  https://finance.naver.com/item/main.naver?code={code}")
    print(f"  투자의견:  https://finance.naver.com/item/coinfo.naver?code={code}&target=cnc")
    print(f"  차트:      https://finance.naver.com/item/fchart.naver?code={code}")
    print(f"  공시:      https://dart.fss.or.kr/dsab007/main.do?option=S&textCrpNm={code}")
    print(f"  종목토론:  https://finance.naver.com/item/board.naver?code={code}")


# ── 메인 ──────────────────────────────────────────────────
if __name__ == "__main__":
    args = sys.argv[1:]

    if not args:
        print(__doc__)
        sys.exit(0)

    cmd = args[0].lower()

    if cmd == "market":
        cmd_market()
    elif cmd == "sector":
        cmd_sector()
    elif cmd == "theme":
        cmd_theme()
    elif cmd == "stock" and len(args) > 1:
        cmd_stock(args[1])
    elif cmd == "investor" and len(args) > 1:
        cmd_investor(args[1])
    elif cmd == "short" and len(args) > 1:
        cmd_short(args[1])
    elif cmd == "screen" and len(args) > 1:
        cmd_screen(args[1])
    elif cmd == "all" and len(args) > 1:
        cmd_all(args[1])
    else:
        print(f"알 수 없는 명령: {' '.join(args)}")
        print(__doc__)
