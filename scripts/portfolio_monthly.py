# -*- coding: utf-8 -*-
r"""제네시스 모의 포트폴리오 월말 교체.

사용법 (매달 마지막 거래일, 20:40 이후 확정 종가):
  python -X utf8 scripts/portfolio_monthly.py                # 다음 달 명단 계산, 출력만
  python -X utf8 scripts/portfolio_monthly.py --apply --start 2026-12-01   # 명단 저장 + 변경 내역 기록
  python -X utf8 scripts/portfolio_monthly.py --fresh        # 보유 종목 없이 점수 순서만 확인

규칙은 content/portfolio-log/ 시작 명단과 /portfolio 운용 기준이 원본이다.
백테스트(2017-05~2026-10)와 같게 업종 상한은 주도섹터 모델 업종, 재무는 네이버 지배주주 값을 쓴다.
주도섹터의 leading_score(주도점수)와 최신 주간 모니터(리비전)가 먼저 갱신돼 있어야 한다.
"""
import argparse
import datetime as dt
import json
import pathlib
import re
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import market_brief as mb  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = mb.ROOT
JUDO = pathlib.Path.home() / "OneDrive" / "바탕 화면" / "주도섹터"
PORTFOLIO = ROOT / "public" / "charts" / "portfolio"
API = "https://m.stock.naver.com/api"
UNIVERSE = {"KOSPI": 200, "KOSDAQ": 50}
POOL = {"KOSPI": 230, "KOSDAQ": 70}  # 거래·이력 조건으로 빠지는 종목을 감안해 넉넉히 받는다.
BUFFER = 15
MAX_SECTOR = MAX_KOSDAQ = 2
EXCLUDED_SECTORS = {"기타", "연구개발"}
HEADERS = {"User-Agent": "Mozilla/5.0"}


def get(url, tries=3):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=20) as r:
                return json.loads(r.read())
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(1 + i)


def num(v):
    try:
        return float(str(v).replace(",", ""))
    except ValueError:
        return None


def universe_pool():
    pool = []
    for market, size in POOL.items():
        got = []
        for page in range(1, 10):
            for s in get(f"{API}/stocks/marketValue/{market}?page={page}&pageSize=100")["stocks"]:
                code, name = s["itemCode"], s["stockName"]
                if s.get("stockEndType") != "stock" or not re.fullmatch(r"\d{5}0", code):
                    continue  # 우선주·ETF 제외
                if re.search(r"리츠|스팩|SPAC|인프라|맥쿼리", name):
                    continue
                got.append({"code": code, "name": name, "market": market, "cap": num(s["marketValue"])})
            if len(got) >= size:
                break
        pool += got[:size]
    return pool


def load_one(s):
    code = s["code"]
    s["px"] = mb.fetch_daily(code, years=2)["close"]
    rows = get(f"{API}/stock/{code}/finance/annual")["financeInfo"]["rowList"]
    s["fin"] = {r["title"]: {k: num(v.get("value")) for k, v in r["columns"].items()} for r in rows}
    return s


def fin(s, key, year):
    return (s["fin"].get(key) or {}).get(f"{year}12")


def features(pool, day):
    fy = day.year - 1 if day.month >= 4 else day.year - 2
    rows = {}
    for s in pool:
        c = s["px"].loc[:day]
        if len(c) < 253 or c.index[-1] != day:
            continue  # 1년 이력 또는 당일 거래 없음
        last = c.iloc[-1]
        eps = [fin(s, "EPS", y) for y in (fy, fy - 1)]
        roe = [fin(s, "ROE", y) for y in (fy, fy - 1)]
        rows[s["code"]] = {
            "name": s["name"], "market": s["market"], "cap": s["cap"], "close": last,
            "mom": c.iloc[-22] / c.iloc[-253] - 1, "vol": c.pct_change().iloc[-60:].std(), "r21": last / c.iloc[-22] - 1,
            "ep2": np.nanmean([e for e in eps if e is not None] or [np.nan]) / last,
            "bp": (fin(s, "BPS", fy) or np.nan) / last,
            "roe2": np.nanmean([r for r in roe if r is not None] or [np.nan]),
            "dp": (fin(s, "주당배당금", fy) or 0) / last,
        }
    f = pd.DataFrame(rows).T
    for col in ("cap", "close", "mom", "vol", "r21", "ep2", "bp", "roe2", "dp"):
        f[col] = pd.to_numeric(f[col])
    return pd.concat([f[f.market == m].nlargest(n, "cap") for m, n in UNIVERSE.items()])


def score(u):
    def rank(x):
        return x.rank(pct=True)

    def in_sector(x):
        g = u.sector.fillna("NA")
        n = g.map(g.value_counts())
        return x.groupby(g).rank(pct=True).where((n >= 5) & (g != "NA"), rank(x))

    per = (in_sector(u.ep2) + rank(u.ep2)) / 2
    pbr = (in_sector(u.bp) + rank(u.bp)) / 2
    s = pd.concat([per, pbr, rank(u.roe2), rank(u.dp), rank(u.mom), rank(-u.vol)], axis=1).mean(axis=1, skipna=False)
    s[u.r21 >= u.r21.quantile(0.9)] = np.nan
    return s.dropna().sort_values(ascending=False)


def pick(s, u, n, prev):
    order = list(s.index)
    keep = [c for c in prev if c in s.index and order.index(c) < BUFFER]
    out, kosdaq, sectors = [], 0, {}
    for c in keep + [c for c in order if c not in keep]:
        if len(out) >= n:
            break
        is_kq = u.market[c] == "KOSDAQ"
        sec = u.sector[c] if pd.notna(u.sector[c]) else c
        if (is_kq and kosdaq >= MAX_KOSDAQ) or sectors.get(sec, 0) >= MAX_SECTOR:
            continue
        out.append(c)
        kosdaq += is_kq
        sectors[sec] = sectors.get(sec, 0) + 1
    return out


def live_sectors(day):
    """온라인 사이클: 점수 1 이상 10일 시작, 0 미만 15일 종료. 점수 높은 순으로 돌려준다."""
    ls = pd.read_parquet(JUDO / "data" / "processed" / "leading_score.parquet")
    ls.columns = [c.split(":")[1] for c in ls.columns]
    if ls.index[-1] < day:
        sys.exit(f"[오류] 주도점수가 {ls.index[-1].date()}까지입니다. 주도섹터 점수 갱신 후 다시 실행하세요.")
    ls = ls.loc[:day].drop(columns=list(EXCLUDED_SECTORS), errors="ignore")
    live = {}
    for sec in ls.columns:
        on, up, down = False, 0, 0
        for x in ls[sec].values:
            if not np.isnan(x):
                up = up + 1 if x >= 1 else 0
                down = down + 1 if x < 0 else 0
                if not on and up >= 10:
                    on = True
                elif on and down >= 15:
                    on = False
        if on:
            live[sec] = ls[sec].iloc[-1]
    return sorted(live, key=lambda k: -live[k]), live


def revision_down(day):
    path = max((JUDO / "monitor").glob("모니터_*.md"))
    stamp = dt.datetime.strptime(path.stem.split("_")[1], "%Y%m%d")
    if (day - stamp).days > 3:
        sys.exit(f"[오류] 주간 모니터가 {path.name}입니다. 주도섹터 점검 후 다시 실행하세요.")
    return {m for m in re.findall(r"^\| ([^|]+?) \|.*⬇️ 하향\(확정\)", path.read_text(encoding="utf-8"), re.M)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=dt.date.today().isoformat())
    ap.add_argument("--fresh", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--start", help="다음 달 첫 거래일 YYYY-MM-DD (--apply 때 필수)")
    a = ap.parse_args()
    if a.apply and not a.start:
        sys.exit("[오류] --apply 에는 --start 가 필요합니다.")
    day = pd.Timestamp(a.date)

    path = sorted(p for p in PORTFOLIO.glob("*.json") if p.stem[:2] == "20")[-1]
    old = json.loads(path.read_text(encoding="utf-8"))
    prev_m = [] if a.fresh else [h["code"] for h in old["holdings"] if h["role"] == "멀티팩터"]
    prev_l = [] if a.fresh else [h["code"] for h in old["holdings"] if h["role"] == "주도산업"]
    prev_c = [] if a.fresh else [h["code"] for h in old["compare"]]

    with ThreadPoolExecutor(10) as ex:
        pool = list(ex.map(load_one, universe_pool()))
    u = features(pool, day)
    smap = pd.read_parquet(JUDO / "data" / "raw" / "sector_map" / "ticker_sector_map.parquet").sector
    u["sector"] = smap.reindex(u.index)
    s = score(u)
    print(f"[후보] {len(u)}종목, 점수 산출 {len(s)}종목 (기준일 {a.date})")

    ordered, scores = live_sectors(day)
    down = revision_down(day)
    live = [c for c in ordered if c not in down]
    print("[사이클] " + ", ".join(f"{c} {scores[c]:+.2f}{'(하향 확정 제외)' if c in down else ''}" for c in ordered))

    slot = [c for c in prev_l if c in s.index and u.sector.get(c) in live][:1]
    for sec in live:
        if slot:
            break
        slot = [c for c in s.index if u.sector.get(c) == sec][:1]
    rest = s.drop(slot, errors="ignore")
    multi = pick(rest, u.drop(slot), 5 - len(slot), [c for c in prev_m if c not in slot])
    compare = pick(s, u, 5, prev_c)
    rank = {c: i + 1 for i, c in enumerate(s.index)}

    print("\n[점수 상위 10]")
    for c in s.index[:10]:
        print(f"  {rank[c]:>2}. {u.name[c]} ({c}, {u.sector[c]}) {s[c]:.3f}")
    print("\n[다음 달 명단]")
    for c in multi:
        print(f"  멀티팩터 {u.name[c]} ({c}) {rank[c]}위 {'유지' if c in prev_m else '편입'}")
    for c in slot:
        print(f"  주도산업 {u.name[c]} ({c}, {u.sector[c]}) 전체 {rank[c]}위 {'유지' if c in prev_l else '편입'}")
    print("  비교 기준: " + ", ".join(u.name[c] for c in compare))

    def why(c):
        if c not in u.index:
            return "후보 조건 이탈"
        if c not in s.index:
            return "1달 수익률 상위 10%"
        return "사이클 종료 또는 이익 전망 하향" if c in prev_l else "점수 15위 밖"

    new = [c for c in multi + slot if c not in prev_m + prev_l]
    names = {h["code"]: h["name"] for h in old["holdings"]}
    gone = [c for c in prev_m + prev_l if c not in multi + slot]
    for c in gone:
        print(f"  편출 {names[c]}: {why(c)}")

    if not a.apply:
        return
    core = next(h for h in old["holdings"] if h["role"] == "코어")
    start = pd.Timestamp(a.start)
    holdings = [{**core, "close": mb.fetch_daily(core["code"], years=1)["close"].loc[day].item(), "open": None, "reportUrl": None}]
    for role, codes in (("멀티팩터", multi), ("주도산업", slot)):
        for c in codes:
            reason = f"혼합 점수 {rank[c]}위" if role == "멀티팩터" else f"주도 사이클이 진행 중인 {u.sector[c]} 산업의 혼합 점수 1위"
            prior = next((h["reportUrl"] for h in old["holdings"] if h["code"] == c), None)
            holdings.append({"role": role, "name": u.name[c], "code": c, "weight": 10, "close": float(u.close[c]),
                             "open": None, "reason": reason, "reportUrl": prior})
    data = {"month": start.strftime("%Y-%m"), "scoreDate": a.date, "startDate": a.start, "holdings": holdings,
            "compare": [{"name": u.name[c], "code": c, "open": None} for c in compare]}
    out = PORTFOLIO / f"{data['month']}.json"
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    events_path = PORTFOLIO / "events.json"
    events = json.loads(events_path.read_text(encoding="utf-8"))
    detail = "변경 없음" if not new and not gone else ", ".join(
        [f"편입 {u.name[c]}" for c in new] + [f"편출 {names[c]}({why(c)})" for c in gone])
    events.append({"date": a.date, "type": "월말 교체", "detail": detail})
    events_path.write_text(json.dumps(events, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"\n[완료] public/charts/portfolio/{out.name}, 변경 내역 기록")
    if new:
        print("[종목분석 대상] " + ", ".join(f"{c}:{u.name[c]}" for c in new))


if __name__ == "__main__":
    main()
