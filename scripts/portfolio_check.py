# -*- coding: utf-8 -*-
r"""제네시스 모의 포트폴리오 일일 점검.

사용법: python -X utf8 scripts/portfolio_check.py [--days 4]

달 중간에 편출이 생기는 경우는 사건 편출뿐이므로 위성 종목의 공시 제목만 매일 점검한다.
공시가 걸려도 자동 편출하지 않는다. 원문을 확인한 뒤 public/charts/portfolio/events.json 에 기록한다.
점수·사이클 편출은 매달 마지막 거래일 점검에서 정한다. 그날이면 알림을 출력한다.
"""
import datetime
import io
import json
import pathlib
import sys
import xml.etree.ElementTree as ET
import zipfile

import requests

ROOT = pathlib.Path(__file__).resolve().parents[1]
PORTFOLIO = ROOT / "public" / "charts" / "portfolio"
ENV = pathlib.Path.home() / "OneDrive" / "바탕 화면" / "주식스크리너" / "stock-screener" / ".env.local"
DART = "https://opendart.fss.or.kr/api"
KEYWORDS = ("횡령", "배임", "의견거절", "의견 거절", "관리종목", "상장폐지", "상장적격성")


def dart_key():
    for line in ENV.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("DART_API_KEY="):
            return line.split("=", 1)[1].strip().strip("\"'")
    sys.exit("[오류] DART_API_KEY 없음")


def corp_codes(key):
    r = requests.get(f"{DART}/corpCode.xml", params={"crtfc_key": key}, timeout=60)
    r.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        root = ET.fromstring(z.read(z.namelist()[0]))
    return {e.findtext("stock_code").strip(): e.findtext("corp_code") for e in root.iter("list")
            if (e.findtext("stock_code") or "").strip()}


def filings(key, corp, days):
    end = datetime.date.today()
    params = {"crtfc_key": key, "corp_code": corp, "bgn_de": (end - datetime.timedelta(days=days)).strftime("%Y%m%d"),
              "end_de": end.strftime("%Y%m%d"), "page_count": 100}
    j = requests.get(f"{DART}/list.json", params=params, timeout=30).json()
    if j["status"] == "013":  # 조회 결과 없음
        return []
    if j["status"] != "000":
        sys.exit(f"[오류] DART 응답 {j['status']}: {j.get('message')}")
    return j["list"]


def is_month_end(day):
    """주말과 12/31(증시 휴장)만 건너뛴다. 월말 공휴일은 반영하지 않으므로 그달 휴장일은 따로 확인한다."""
    nxt = day + datetime.timedelta(days=1)
    while nxt.weekday() >= 5 or (nxt.month, nxt.day) == (12, 31):
        nxt += datetime.timedelta(days=1)
    return nxt.month != day.month


def main():
    days = int(sys.argv[sys.argv.index("--days") + 1]) if "--days" in sys.argv else 4
    path = sorted(p for p in PORTFOLIO.glob("*.json") if p.stem[:2] == "20")[-1]
    holdings = [h for h in json.loads(path.read_text(encoding="utf-8"))["holdings"] if h["role"] != "코어"]
    key = dart_key()
    codes = corp_codes(key)

    hits = []
    for h in holdings:
        rows = filings(key, codes[h["code"]], days)
        found = [r for r in rows if any(k in r["report_nm"] for k in KEYWORDS)]
        print(f"[점검] {h['name']}: 공시 {len(rows)}건, 해당 {len(found)}건")
        hits += [(h["name"], r) for r in found]

    if hits:
        print("\n[확인 필요] 사건 편출 후보. 원문을 확인할 것")
        for name, r in hits:
            print(f"- {name} {r['rcept_dt']} {r['report_nm']} https://dart.fss.or.kr/dsaf001/main.do?rcpNo={r['rcept_no']}")
    else:
        print("\n[결과] 사건 편출 대상 없음")
    if is_month_end(datetime.date.today()):
        print("[알림] 오늘은 월말 점검일입니다. 점수 계산 후 저녁에 명단을 교체합니다.")


if __name__ == "__main__":
    main()
