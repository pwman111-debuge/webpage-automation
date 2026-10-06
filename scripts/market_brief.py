# -*- coding: utf-8 -*-
r"""제네시스 시황 v4 — '쉬운 시황' 데이터 수집 + 코스피·코스닥 차트 신호 + MDX 초안 생성.

2026-10-06 개편(황원장 지시): 기존 시황이 너무 길고 전문적 → ①한눈에 보는 지수 카드·수급·업종 중심의 쉬운 시황
②주도섹터 워크스페이스 '차트 신호' 트리거(scripts/chart_signal.py) 규칙으로 코스피·코스닥 차트를 그리고 신호를 마킹·기술.

데이터 (키·로그인 불필요):
  stock.naver.com/api  integration/v1/indicators  지수·수급(개인·외국인·기관)·등락 종목수·해외지수·환율·금리·원자재
                       domestic/market/stock/default            거래대금·상승률 상위
                       domestic/market/trend/trendForeignOrg    외국인·기관 순매수 상위(확정은 20:36 이후)
  m.stock.naver.com/api stocks/industry · stocks/theme           업종 79 · 테마 264 등락률
  api.finance.naver.com siseJson                                 코스피·코스닥 일봉(KRX 정규장)
  ⚠️ 리포트 본문에는 데이터 제공 사이트 이름을 쓰지 않는다(황원장 지시). 출처 표기는 '한국거래소 시세·투자자별 매매동향'.

차트 신호 규칙 = 주도섹터/scripts/chart_signal.py 와 동일(파라미터 포함, 바꾸면 양쪽 같이 바꿀 것):
  ① 준비(arm)  : 눌렸다 / 과열됐다  → 박스 시작
  ② 방아쇠(fire): 방향이 꺾였다      → 박스 끝 + ▲▼
  매수▲ = 종가>120일선 안에서 %B<20 또는 RSI7<35로 20일선 아래 눌림 → MACD 막대 음→양 + 20일선 회복
          (단 120일선 이격 1년 백분위 ≥92면 취소)
  매도▼ = 120일선 이격 1년 백분위 ≥80 + RSI7>70 또는 %B>85 과열 → MACD 막대 양→음 + 20일선 이탈
  검증 한계: 매도 신호 적중은 동전 이하 → '판다'가 아니라 '더 사지 않는다'. 차트는 '언제'만, 단독 매매근거 아님.

산출:
  public/charts/market/YYYY-MM-DD-kospi.json · -kosdaq.json   (SignalChart 컴포넌트가 읽는 차트 데이터)
  %TEMP%/genesis_market_brief_YYYYMMDD.json                   (분석가가 읽는 원자료 — 저장소 밖)
  --write 시 content/market-analysis/YYYY-MM-DD-market-analysis-genesis.mdx 초안 (기존 파일은 --force 없으면 보존)

CLI:
  python -X utf8 scripts/market_brief.py            # 데이터 + 차트 JSON + 콘솔 요약
  python -X utf8 scripts/market_brief.py --write    # + MDX 초안
"""
import argparse
import datetime as dt
import json
import pathlib
import re
import sys
import tempfile

import numpy as np
import pandas as pd
import requests

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = pathlib.Path(__file__).resolve().parents[1]
CHART_DIR = ROOT / "public" / "charts" / "market"
MDX_DIR = ROOT / "content" / "market-analysis"

HDR = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/130 Safari/537.36",
       "Referer": "https://stock.naver.com/"}
API = "https://stock.naver.com/api"
MAPI = "https://m.stock.naver.com/api"
SISE = ("https://api.finance.naver.com/siseJson.naver?symbol={sym}"
        "&requestType=1&startTime={s}&endTime={e}&timeframe=day")
IND_URL = (f"{API}/securityService/integration/v1/indicators"
           "?domesticIndexCodes=KOSPI,KOSDAQ,KPI200"
           "&foreignIndexCodes=.INX,.IXIC,.SOX"
           "&currencyCodes=USD&bondCodes=US10YT%3DRR,KR10YT%3DRR"
           "&commodityCodes=CLcv1,GCcv1&includeBreadth=true&includeTrend=true")

INDEX_NAME = {"KOSPI": "코스피", "KOSDAQ": "코스닥", "KPI200": "코스피200"}
MACRO = [  # (그룹, 코드, 표시 이름, 단위, 금리 여부)
    ("exchangeRate", "USD", "원/달러", "원", False),
    ("governmentBond", "US10YT=RR", "미국 10년물 금리", "%", True),
    ("governmentBond", "KR10YT=RR", "한국 10년물 금리", "%", True),
    ("commodity", "CLcv1", "WTI 유가", "달러", False),
    ("commodity", "GCcv1", "금", "달러", False),
    ("foreignIndex", ".INX", "S&P500", "", False),
    ("foreignIndex", ".IXIC", "나스닥", "", False),
    ("foreignIndex", ".SOX", "필라델피아 반도체", "", False),
]
THUMBS = [
    "https://images.unsplash.com/photo-1590283603385-17ffb3a7f29f?auto=format&fit=crop&w=1200&q=80",
    "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?auto=format&fit=crop&w=1200&q=80",
    "https://images.unsplash.com/photo-1518186285589-2f7649de83e0?auto=format&fit=crop&w=1200&q=80",
    "https://images.unsplash.com/photo-1591696205602-2f950c417cb9?auto=format&fit=crop&w=1200&q=80",
]
WEEKDAY = "월화수목금토일"

# ── 차트 신호 규칙 파라미터 (chart_signal.py와 동일 — 조정 금지) ─────────────
ARM_WINDOW = 10
COOLDOWN = 10
VETO_D120 = 92
ARM_BB, ARM_RSI = 20, 35
HOT_RSI, HOT_BB, HOT_D120 = 70, 85, 80
DISPLAY_DAYS = 250


# ══════════════════════════════════════════════ 수집
def _get(url):
    r = requests.get(url, headers=HDR, timeout=15)
    r.raise_for_status()
    return r.json()


def _f(x):
    try:
        return float(str(x).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _safe(fn, *a, default=None):
    try:
        return fn(*a)
    except Exception as e:
        print(f"  (건너뜀 {fn.__name__}: {e})")
        return default


def fetch_indicators():
    d = _get(IND_URL)
    idx = []
    for code in ("KOSPI", "KOSDAQ", "KPI200"):
        x = (d.get("domesticIndex") or {}).get(code)
        if not x:
            continue
        p = x["price"]
        row = {"code": code, "name": INDEX_NAME[code], "value": _f(p.get("currentPrice")),
               "change": _f(p.get("changePrice")), "rate": _f(p.get("changeRate")),
               "open": _f(p.get("openingPrice")), "high": _f(p.get("highPrice")), "low": _f(p.get("lowPrice")),
               "high52": _f(p.get("highPriceOf52Weeks")), "low52": _f(p.get("lowPriceOf52Weeks")),
               "asof": (p.get("localTradedAt") or "")[:10], "status": p.get("marketStatus")}
        if p.get("priceMovement") == "falling" and row["change"] and row["change"] > 0:
            row["change"] = -row["change"]
        inv = {t["investorType"]: _f(t["netBuyAmount"]) for t in x.get("investorTrends") or []}
        if inv:   # 원 → 억
            row["flows"] = {"individual": round((inv.get("individual") or 0) / 1e8),
                            "foreign": round((inv.get("foreigner") or 0) / 1e8),
                            "institution": round((inv.get("organization") or 0) / 1e8)}
            row["flow_date"] = x.get("investorTrendBaseDate")
        prog = x.get("programTrend") or {}
        if prog.get("totalNetBuyAmount") is not None:
            row["program"] = round(_f(prog["totalNetBuyAmount"]) / 1e8)
        br = x.get("breadth") or {}
        if br:
            row["breadth"] = {"up": int(br.get("risingCount") or 0), "flat": int(br.get("unchangedCount") or 0),
                              "down": int(br.get("fallingCount") or 0),
                              "upper": int(br.get("upperLimitCount") or 0), "lower": int(br.get("lowerLimitCount") or 0)}
        idx.append(row)

    macro = []
    for grp, code, name, unit, is_rate in MACRO:
        x = (d.get(grp) or {}).get(code)
        if not x:
            continue
        p = x["price"]
        v = _f(p.get("currentYield") if is_rate else p.get("currentPrice"))
        ch = _f(p.get("yieldChange") if is_rate else p.get("changePrice"))
        rt = None if is_rate else _f(p.get("changeRate"))
        if not is_rate and p.get("priceMovement") == "falling" and ch and ch > 0:
            ch = -ch
        macro.append({"code": code, "name": name, "unit": unit, "value": v, "change": ch, "rate": rt,
                      "isRate": is_rate, "asof": (p.get("localTradedAt") or "")[:10]})
    return idx, macro


def fetch_groups(kind):
    groups, page = [], 1
    while page <= 5:   # 페이지당 최대 100 (업종 79 · 테마 264)
        j = _get(f"{MAPI}/stocks/{kind}?page={page}&pageSize=100")
        groups += j.get("groups") or []
        if len(groups) >= int(j.get("totalCount") or 0) or not j.get("groups"):
            break
        page += 1
    rows = [{"name": g["name"], "rate": _f(g.get("changeRate")), "count": g.get("totalCount"),
             "up": g.get("riseCount"), "down": g.get("fallCount")} for g in groups]
    # 종목 5개 미만 소형 그룹(문구류 등)은 한두 종목 움직임에 휘둘려 '업종 흐름'을 왜곡 → 제외
    return sorted([r for r in rows if r["rate"] is not None and (r["count"] or 0) >= 5], key=lambda r: -r["rate"])


def fetch_rank(order, market, n=5):
    j = _get(f"{API}/domestic/market/stock/default?tradeType=KRX&marketType={market}&orderType={order}"
             f"&startIdx=0&pageSize={n * 3}")
    out = []
    for x in j:
        if x.get("type") not in (None, "ST"):   # ETF·ETN 제외
            continue
        out.append({"name": x["itemname"], "code": x["itemcode"], "price": _f(x.get("nowPrice")),
                    "rate": _f(x.get("prevChangeRate")), "amount": _f(x.get("tradeAmount"))})
    return out[:n]


def fetch_netbuy(investor, market, n=5):
    j = _get(f"{API}/domestic/market/trend/trendForeignOrg?investorType={investor}&tradeType=KRX"
             f"&marketType={market}&startIdx=0&pageSize={n}&periodType=DAY")
    s = j.get("sections") or {}

    def rows(lst):
        return [{"name": x["itemname"], "code": x["itemcode"], "amount": round(_f(x.get("accTradeAmount")) / 1e8)
                 if _f(x.get("accTradeAmount")) else None, "rate": _f(x.get("prevChangeRate")),
                 "estimated": bool(x.get("estimated")), "date": x.get("bizdateTo")} for x in lst[:n]]
    return {"buy": rows(s.get("buyRankList") or []), "sell": rows(s.get("sellRankList") or [])}


def fetch_daily(sym, years=7):
    end = dt.date.today()
    start = end - dt.timedelta(days=365 * years)
    txt = requests.get(SISE.format(sym=sym, s=start.strftime("%Y%m%d"), e=end.strftime("%Y%m%d")),
                       headers=HDR, timeout=30).text
    rows = re.findall(r'\["(\d{8})",\s*([\d.]+),\s*([\d.]+),\s*([\d.]+),\s*([\d.]+),\s*(\d+)', txt)
    if not rows:
        raise RuntimeError(f"{sym}: 일봉 응답 비어있음")
    df = pd.DataFrame(rows, columns=["date", "open", "high", "low", "close", "vol"])
    for c in ("open", "high", "low", "close", "vol"):
        df[c] = df[c].astype(float)
    df["date"] = pd.to_datetime(df["date"], format="%Y%m%d")
    return df.set_index("date").sort_index()


# ══════════════════════════════════════════════ 차트 신호 (chart_signal.py 규칙 그대로)
def indicators(df):
    c = df["close"]
    df["ma5"] = c.rolling(5).mean()
    df["ma20"] = c.rolling(20).mean()
    df["ma120"] = c.rolling(120).mean()
    sd = c.rolling(20).std(ddof=0)
    df["bb_up"], df["bb_dn"] = df["ma20"] + 2 * sd, df["ma20"] - 2 * sd
    df["bb_pct"] = (c - df["bb_dn"]) / (df["bb_up"] - df["bb_dn"]) * 100
    e12, e26 = c.ewm(span=12, adjust=False).mean(), c.ewm(span=26, adjust=False).mean()
    df["macd"] = e12 - e26
    df["macd_sig"] = df["macd"].ewm(span=9, adjust=False).mean()
    df["macd_hist"] = df["macd"] - df["macd_sig"]
    d = c.diff()
    for n in (7, 14):
        up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
        dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
        df[f"rsi{n}"] = 100 - 100 / (1 + up / dn)
    df["dist120"] = (c / df["ma120"] - 1) * 100
    df["d120_pct"] = df["dist120"].rolling(250, min_periods=120).rank(pct=True) * 100
    return df


def arms(df):
    c, ma20, ma120 = df["close"], df["ma20"], df["ma120"]
    buy_arm = ((df["bb_pct"] < ARM_BB) | (df["rsi7"] < ARM_RSI)) & (c < ma20) & (c > ma120)
    sell_arm = ((df["rsi7"] > HOT_RSI) | (df["bb_pct"] > HOT_BB)) & (df["d120_pct"] >= HOT_D120)
    return buy_arm, sell_arm


def signals(df):
    c, ma20, ma120, hist = df["close"], df["ma20"], df["ma120"], df["macd_hist"]
    buy_arm, sell_arm = arms(df)
    not_hot = df["d120_pct"] < VETO_D120
    buy_fire = (hist > 0) & (hist.shift(1) <= 0) & (c > ma20) & (c > ma120) & not_hot
    sell_fire = (hist < 0) & (hist.shift(1) >= 0) & (c < ma20)
    out, last = [], {"B": None, "S": None}
    for i in range(len(df)):
        d, lo = df.index[i], max(0, i - ARM_WINDOW)
        for kind, fire, arm in (("B", buy_fire, buy_arm), ("S", sell_fire, sell_arm)):
            if not bool(fire.iloc[i]):
                continue
            win = arm.iloc[lo:i + 1]
            if not win.any():
                continue
            if last[kind] is not None and (d - last[kind]).days < COOLDOWN:
                continue
            last[kind] = d
            out.append({"kind": kind, "start": win[win].index[0], "fire": d,
                        "i_start": df.index.get_loc(win[win].index[0]), "i_fire": i,
                        "price": float(c.iloc[i])})
    return out


def backtest(df, sigs, h=20):
    res = {}
    for k in ("B", "S"):
        v = [(df["close"].iloc[s["i_fire"] + h] / s["price"] - 1) * 100
             for s in sigs if s["kind"] == k and s["i_fire"] + h < len(df)]
        v = np.array(v)
        res[k] = {"n": int(sum(1 for s in sigs if s["kind"] == k)), "scored": int(len(v)),
                  "win": (float(((v < 0) if k == "S" else (v > 0)).mean() * 100) if len(v) else None),
                  "avg": (float(v.mean()) if len(v) else None)}
    # 아무 날이나 샀을 때(기준선) — 매수 적중률을 이것과 비교해야 의미가 있다
    fwd = (df["close"].shift(-h) / df["close"] - 1).dropna() * 100
    res["base"] = {"win": float((fwd > 0).mean() * 100), "avg": float(fwd.mean())}
    return res


def josa(word, pair="은는"):
    """받침 있으면 pair[0], 없으면 pair[1] (은/는·이/가)."""
    ch = word[-1]
    has = "가" <= ch <= "힣" and (ord(ch) - 0xAC00) % 28 != 0
    return word + (pair[0] if has else pair[1])


def _n(x, d=2):
    return f"{x:,.{d}f}"


def describe(df, sigs, bt, name):
    """오늘의 신호 상태 → 쉬운 말 + 조건 체크리스트 + 다음 방아쇠 조건."""
    r, p = df.iloc[-1], df.iloc[-2]
    c, ma20, ma120 = r["close"], r["ma20"], r["ma120"]
    buy_arm, sell_arm = arms(df)
    buy_recent = bool(buy_arm.iloc[-ARM_WINDOW - 1:].any())
    sell_recent = bool(sell_arm.iloc[-ARM_WINDOW - 1:].any())
    hist_up = r["macd_hist"] > 0
    hist_turn = "막 플러스로 돌아섬" if hist_up and p["macd_hist"] <= 0 else (
        "막 마이너스로 돌아섬" if not hist_up and p["macd_hist"] >= 0 else ("플러스" if hist_up else "마이너스"))
    last = sigs[-1] if sigs else None
    days_since = (len(df) - 1 - last["i_fire"]) if last else None

    # 상태 판정 — 오늘 방아쇠 > 최근 5거래일 신호 > 준비 > 대기
    if last and days_since == 0:
        state = "buy_fire" if last["kind"] == "B" else "sell_fire"
    elif last and days_since <= 5:
        state = "buy_fire" if last["kind"] == "B" else "sell_fire"
    elif buy_recent and c > ma120:
        state = "buy_arm"
    elif sell_recent:
        state = "sell_arm"
    else:
        state = "none"
    label = {"buy_fire": "▲ 매수 신호", "sell_fire": "▼ 매도 신호(더 사지 않음)",
             "buy_arm": "매수 준비", "sell_arm": "과열 주의", "none": "신호 대기"}[state]

    # 쉬운 말 한 단락
    gap20, gap120 = (c / ma20 - 1) * 100, (c / ma120 - 1) * 100
    pos20 = "위" if c > ma20 else "아래"
    trend = ("120일선 위 — 큰 흐름은 아직 오르는 쪽" if c > ma120 else "120일선 아래 — 큰 흐름이 꺾인 상태라 매수 신호가 나오지 않는 구간")
    if state == "buy_fire":
        when = "오늘" if days_since == 0 else f"{days_since}거래일 전({last['fire']:%m/%d})"
        text = (f"{josa(name)} {when} 매수 신호(▲)가 켜졌습니다. 20일선 아래로 눌렸다가 다시 올라서며 "
                f"방향이 위로 꺾인 자리입니다. 신호가 나온 가격은 {_n(last['price'])}입니다.")
    elif state == "sell_fire":
        when = "오늘" if days_since == 0 else f"{days_since}거래일 전({last['fire']:%m/%d})"
        text = (f"{josa(name)} {when} 매도 신호(▼)가 켜졌습니다. 많이 오른 뒤 20일선 아래로 내려오며 방향이 아래로 꺾인 자리입니다. "
                f"이 신호는 '팔아라'가 아니라 '여기서 더 사지는 말자'로 읽습니다.")
    elif state == "buy_arm":
        text = (f"{josa(name)} 매수 준비 단계입니다. 큰 흐름(120일선) 위에서 20일선 아래로 충분히 눌렸습니다. "
                f"아직 방아쇠는 당겨지지 않았고, 방향이 위로 꺾이는 것을 확인해야 합니다.")
    elif state == "sell_arm":
        text = (f"{josa(name)} 과열 구간입니다. 1년 기준으로 120일선에서 많이 떨어진 높은 자리이고 단기 과열 지표도 켜졌습니다. "
                f"새로 사기에는 부담스러운 자리입니다.")
    else:
        text = (f"{josa(name)} 지금 특별한 신호가 없는 '대기' 상태입니다. 종가는 20일선 {pos20}, {trend}입니다.")

    checks = [
        {"label": "큰 흐름: 종가가 120일선 위", "ok": bool(c > ma120),
         "value": f"종가 {_n(c)} / 120일선 {_n(ma120)} ({gap120:+.1f}%)"},
        {"label": "단기 위치: 종가가 20일선 위", "ok": bool(c > ma20),
         "value": f"20일선 {_n(ma20)} ({gap20:+.1f}%)"},
        {"label": "눌림 확인: 볼린저 %B 20 미만 또는 RSI(7) 35 미만", "ok": bool(r["bb_pct"] < ARM_BB or r["rsi7"] < ARM_RSI),
         "value": f"%B {r['bb_pct']:.0f} · RSI(7) {r['rsi7']:.0f}"},
        {"label": "방향 전환: MACD 막대 플러스", "ok": bool(hist_up), "value": f"MACD 막대 {hist_turn}"},
        {"label": "과열 아님: 120일선 이격 1년 백분위 92 미만", "ok": bool(r["d120_pct"] < VETO_D120),
         "value": f"이격 {gap120:+.1f}% · 1년 백분위 {r['d120_pct']:.0f} (92 이상이면 과열)" if r["d120_pct"] == r["d120_pct"] else "계산 불가"},
    ]

    # 다음 방아쇠 조건 (무엇이 바뀌면 신호가 켜지나)
    if state in ("buy_arm",) or (buy_recent and c > ma120 and state not in ("buy_fire",)):
        nxt = (f"앞으로 며칠 안에 MACD 막대가 플러스로 돌아서고 종가가 20일선({_n(ma20)}) 위로 올라오면 ▲매수 신호가 켜집니다. "
               f"반대로 120일선({_n(ma120)})이 깨지면 준비가 취소됩니다.")
    elif state == "sell_arm" or (sell_recent and state != "sell_fire"):
        nxt = (f"MACD 막대가 마이너스로 바뀌고 종가가 20일선({_n(ma20)}) 아래로 내려가면 ▼매도 신호(더 사지 않음)가 켜집니다.")
    elif state == "buy_fire":
        nxt = (f"신호가 유지되려면 종가가 20일선({_n(ma20)}) 위에 머물러야 합니다. 120일선({_n(ma120)})이 마지막 방어선입니다.")
    elif state == "sell_fire":
        nxt = (f"20일선({_n(ma20)})을 다시 회복하기 전까지는 추가 매수를 쉬어 갑니다. "
               f"120일선({_n(ma120)})까지 눌린 뒤 방향이 위로 꺾이면 다음 매수 신호를 기다릴 수 있습니다.")
    elif c > ma120:
        nxt = (f"종가가 20일선({_n(ma20)}) 아래로 눌리고 RSI(7)가 35 아래로 내려가면 '매수 준비'가 시작됩니다. "
               f"지금은 기다리는 구간입니다.")
    else:
        nxt = (f"종가가 120일선({_n(ma120)}) 위로 돌아와야 매수 신호를 다시 볼 수 있습니다.")

    b, s = bt["B"], bt["S"]
    record = (f"이 규칙을 지난 {df.index[0].year}년부터 {name}에 적용하면 매수 신호 {b['n']}번, "
              + (f"20거래일 뒤 오른 비율 {b['win']:.0f}%(평균 {b['avg']:+.1f}%)" if b["win"] is not None else "채점 표본 없음")
              + f" · 아무 날이나 샀을 때 {bt['base']['win']:.0f}%(평균 {bt['base']['avg']:+.1f}%)입니다. "
              + f"매도 신호 {s['n']}번은 "
              + (f"20거래일 뒤 내린 비율 {s['win']:.0f}%였습니다. " if s["win"] is not None else "아직 채점 표본이 없습니다. ")
              + "다만 여러 종목을 20년 넘게 검증하면 매도 신호는 동전 던지기 수준이라 '팔아라'가 아니라 '더 사지 않는다'로만 씁니다.")

    return {"state": state, "label": label, "text": text, "checks": checks, "next": nxt, "record": record,
            "last": (None if not last else {"kind": "매수" if last["kind"] == "B" else "매도",
                                            "date": last["fire"].strftime("%Y-%m-%d"), "price": round(last["price"], 2),
                                            "since": round((c / last["price"] - 1) * 100, 2), "daysAgo": int(days_since)}),
            "close": round(float(c), 2), "ma20": round(float(ma20), 2), "ma120": round(float(ma120), 2)}


def chart_payload(df, sigs, desc, code, name):
    w = df.iloc[-DISPLAY_DAYS:]
    off = len(df) - len(w)

    def col(k, d=2):
        return [None if pd.isna(v) else round(float(v), d) for v in w[k]]
    vis = []
    for s in sigs:
        if s["i_fire"] < off:
            continue
        a, b = max(s["i_start"] - off, 0), s["i_fire"] - off
        vis.append({"kind": s["kind"], "start": a, "fire": b, "date": s["fire"].strftime("%Y-%m-%d"),
                    "price": round(s["price"], 2)})
    return {"code": code, "name": name, "asof": w.index[-1].strftime("%Y-%m-%d"),
            "dates": [d.strftime("%Y-%m-%d") for d in w.index],
            "open": col("open"), "high": col("high"), "low": col("low"), "close": col("close"),
            "ma5": col("ma5"), "ma20": col("ma20"), "ma120": col("ma120"),
            "bbUp": col("bb_up"), "bbDn": col("bb_dn"),
            "macdHist": col("macd_hist", 3), "rsi7": col("rsi7", 1),
            "signals": vis, "state": desc["state"], "label": desc["label"]}


def chart_for(code, name, date_str):
    df = indicators(fetch_daily(code))
    sigs = signals(df)
    bt = backtest(df, sigs)
    desc = describe(df, sigs, bt, name)
    CHART_DIR.mkdir(parents=True, exist_ok=True)
    out = CHART_DIR / f"{date_str}-{code.lower()}.json"
    out.write_text(json.dumps(chart_payload(df, sigs, desc, code, name), ensure_ascii=False,
                              separators=(",", ":")), encoding="utf-8")
    desc["src"] = f"/charts/market/{out.name}"
    desc["asof"] = df.index[-1].strftime("%Y-%m-%d")
    desc["recent"] = [{"kind": "매수" if s["kind"] == "B" else "매도", "date": s["fire"].strftime("%Y-%m-%d"),
                       "price": round(s["price"], 2)} for s in sigs[-4:]]
    return desc


# ══════════════════════════════════════════════ 수집 묶음
def collect():
    idx, macro = fetch_indicators()
    base_day = next((r["asof"] for r in idx if r["code"] == "KOSPI"), dt.date.today().isoformat())
    d = {"generated": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "base_day": base_day,
         "indices": idx, "macro": macro,
         "industry": _safe(fetch_groups, "industry", default=[]),
         "theme": _safe(fetch_groups, "theme", default=[]),
         "amount": {m: _safe(fetch_rank, "priceTop", m, default=[]) for m in ("KOSPI", "KOSDAQ")},
         "up": {m: _safe(fetch_rank, "up", m, default=[]) for m in ("KOSPI", "KOSDAQ")},
         "foreign": {m: _safe(fetch_netbuy, "FOREIGNER", m, default={"buy": [], "sell": []}) for m in ("KOSPI", "KOSDAQ")},
         "institution": {m: _safe(fetch_netbuy, "ORGANIZATION", m, default={"buy": [], "sell": []}) for m in ("KOSPI", "KOSDAQ")},
         "charts": {}}
    for code in ("KOSPI", "KOSDAQ"):
        d["charts"][code] = _safe(chart_for, code, INDEX_NAME[code], base_day, default=None)
    return d


# ══════════════════════════════════════════════ MDX 초안
def _js(x):
    return json.dumps(x, ensure_ascii=False, separators=(",", ":"))


def _eok(x):
    if x is None:
        return "—"
    return f"{x / 1e4:+.2f}조 원" if abs(x) >= 1e4 else f"{x:+,}억 원"


def _who(flows):
    """가장 많이 산 주체 / 판 주체."""
    nm = {"individual": "개인", "foreign": "외국인", "institution": "기관"}
    srt = sorted(flows.items(), key=lambda kv: kv[1])
    return nm[srt[-1][0]], srt[-1][1], nm[srt[0][0]], srt[0][1]


def _idx(d, code):
    return next((r for r in d["indices"] if r["code"] == code), None)


def won(x):
    """억 단위 절댓값 → '1조 7,575억' 같은 읽기 쉬운 금액."""
    a = abs(int(round(x)))
    jo, ok = divmod(a, 10000)
    return (f"{jo}조 {ok:,}억" if ok else f"{jo}조") if jo else f"{ok:,}억"


def build_points(d):
    k, q = _idx(d, "KOSPI"), _idx(d, "KOSDAQ")
    pts = []
    mv = lambda r: f"{abs(r['rate']):.2f}% 오른" if r["rate"] > 0 else (f"{abs(r['rate']):.2f}% 내린" if r["rate"] < 0 else "보합인")
    if k and q:
        pts.append(f"코스피는 {mv(k)} {_n(k['value'])}, 코스닥은 {mv(q)} {_n(q['value'])}로 마감했습니다.")
    if k and k.get("flows"):
        b, bv, s, sv = _who(k["flows"])
        if bv > 0 and sv < 0:
            pts.append(f"코스피에서 {josa(b, '이가')} {won(bv)} 원어치를 사들였고, {josa(s, '이가')} {won(sv)} 원어치를 팔았습니다.")
    ind = d.get("industry") or []
    if len(ind) >= 2:
        pts.append(f"가장 강한 업종은 {ind[0]['name']}({r_pct(ind[0]['rate'])}), 가장 약한 업종은 {ind[-1]['name']}({r_pct(ind[-1]['rate'])})입니다.")
    return pts


def r_pct(x):
    return "—" if x is None else f"{x:+.2f}%"


def draft_title(d):
    k, q = _idx(d, "KOSPI"), _idx(d, "KOSDAQ")
    ind = d.get("industry") or []
    hot = ind[0]["name"] if ind else ""
    return (f"코스피 {r_pct(k['rate'])}, 코스닥 {r_pct(q['rate'])}" + (f" — {hot} 강세" if hot else "")) if k and q else "오늘의 시황"


def signal_section(desc, title):
    if not desc:
        return f"## {title}\n\n차트 데이터를 불러오지 못했습니다.\n"
    last = desc["last"]
    last_txt = (f"가장 최근 신호는 **{last['date']} {last['kind']}**({_n(last['price'])})이고, 그 뒤 지금까지 **{last['since']:+.1f}%** 움직였습니다."
                if last else "표시 구간에 신호가 없습니다.")
    card = {"state": desc["state"], "label": desc["label"], "summary": desc["text"],
            "checks": desc["checks"], "next": desc["next"]}
    return (f"## {title}\n\n"
            f"<SignalChart src=\"{desc['src']}\" />\n\n"
            f"<SignalCard data={{{_js(card)}}} />\n\n"
            f"{last_txt}\n\n"
            f"> {desc['record']}\n")


def build_mdx(d, title=None):
    day = dt.date.fromisoformat(d["base_day"])
    k, q = _idx(d, "KOSPI"), _idx(d, "KOSDAQ")
    title = title or draft_title(d)
    pts = build_points(d)
    summary = " ".join(pts)
    ind, th = d.get("industry") or [], d.get("theme") or []

    board = [{kk: r.get(kk) for kk in ("name", "value", "change", "rate", "high", "low", "high52", "low52", "flows", "breadth")}
             for r in d["indices"]]
    macro = [{kk: r.get(kk) for kk in ("name", "value", "change", "rate", "unit", "isRate")} for r in d["macro"]]
    sect = {"up": [{"name": r["name"], "rate": r["rate"]} for r in ind[:5]],
            "down": [{"name": r["name"], "rate": r["rate"]} for r in ind[-5:][::-1]]}
    themes = [{"name": r["name"], "rate": r["rate"]} for r in th[:5]]

    def rank_items(rows, kind):
        out = []
        for r in rows:
            if kind == "amount":
                sub = f"{r['amount'] / 1e12:,.2f}조" if r.get("amount") and r["amount"] >= 1e12 else (
                    f"{r['amount'] / 1e8:,.0f}억" if r.get("amount") else "")
            else:
                sub = (('+' if r['amount'] >= 0 else '-') + won(r['amount'])) if r.get("amount") is not None else ""
            out.append({"name": r["name"], "sub": sub, "rate": r.get("rate")})
        return out

    lists = {
        "amount": [{"market": m, "items": rank_items(d["amount"][m], "amount")} for m in ("KOSPI", "KOSDAQ")],
        "foreign": [{"label": "외국인이 많이 산 종목", "items": rank_items(d["foreign"]["KOSPI"]["buy"], "net")},
                    {"label": "외국인이 많이 판 종목", "items": rank_items(d["foreign"]["KOSPI"]["sell"], "net")}],
        "inst": [{"label": "기관이 많이 산 종목", "items": rank_items(d["institution"]["KOSPI"]["buy"], "net")},
                 {"label": "기관이 많이 판 종목", "items": rank_items(d["institution"]["KOSPI"]["sell"], "net")}],
    }
    est = any(x.get("estimated") for g in (d["foreign"]["KOSPI"], d["institution"]["KOSPI"]) for side in g.values() for x in side)

    flow_txt = ""
    if k and k.get("flows"):
        f = k["flows"]
        flow_txt = "코스피에서 " + ", ".join(f"{nm} {won(f[kk])} {'순매수' if f[kk] >= 0 else '순매도'}" for kk, nm in (("individual", "개인"), ("foreign", "외국인"), ("institution", "기관"))) + "입니다. "
    if q and q.get("flows"):
        f = q["flows"]
        flow_txt += "코스닥에서는 " + ", ".join(f"{nm} {won(f[kk])} {'순매수' if f[kk] >= 0 else '순매도'}" for kk, nm in (("individual", "개인"), ("foreign", "외국인"), ("institution", "기관"))) + "입니다."

    breadth_txt = ""
    if k and k.get("breadth") and q and q.get("breadth"):
        kb, qb = k["breadth"], q["breadth"]
        breadth_txt = (f"코스피는 오른 종목 {kb['up']:,}개·내린 종목 {kb['down']:,}개, "
                       f"코스닥은 오른 종목 {qb['up']:,}개·내린 종목 {qb['down']:,}개입니다.")

    why_txt = (f"오늘은 {', '.join(r['name'] for r in ind[:3])} 업종이 강했고, {ind[-1]['name']} 업종이 약했습니다."
               if len(ind) >= 3 else "")

    fm = (f"---\n"
          f"title: {_js(title)}\n"
          f"date: \"{d['base_day']}\"\n"
          f"category: \"Genesis\"\n"
          f"summary: {_js(summary)}\n"
          f"tags: {_js(['코스피', '코스닥', '시황분석', '차트신호', '외국인수급'] + [r['name'] for r in ind[:2]] + ['제네시스'])}\n"
          f"thumbnail: \"{THUMBS[day.toordinal() % len(THUMBS)]}\"\n"
          f"---\n\n")

    body = (
        f"> **{day.year}년 {day.month}월 {day.day}일 ({WEEKDAY[day.weekday()]}) 장 마감 기준** · "
        f"데이터: 한국거래소 시세·투자자별 매매동향 · 차트 신호는 제네시스 자체 규칙\n\n"
        f"<KeyPoints title=\"오늘 시장 3줄 요약\" items={{{_js(pts)}}} />\n\n"
        f"## 오늘 왜 이렇게 움직였나\n\n"
        f"{{/* WRITE: 마감 시황 뉴스를 확인해 3~5문장으로 쉽게 쓴다 — 무엇이 지수를 움직였나, 어떤 업종이 왜 강했나. "
        f"전문용어 대신 일상어, 한 문장에 한 가지 사실. 다 쓰면 이 주석 줄은 지운다. */}}\n"
        f"{why_txt}\n\n"
        f"## 1. 오늘 시장 한눈에\n\n"
        f"<IndexBoard items={{{_js(board)}}} />\n\n"
        f"{breadth_txt}\n\n"
        f"## 2. 누가 사고 팔았나\n\n"
        f"{flow_txt}\n\n"
        f"<RankGroup lists={{{_js(lists['foreign'] + lists['inst'])}}} />\n\n"
        + (f"※ 종목별 순매수는 장 마감 직후 잠정치입니다.\n\n" if est else "")
        + f"## 3. 오늘 강했던 업종·테마\n\n"
        f"<SectorBoard up={{{_js(sect['up'])}}} down={{{_js(sect['down'])}}} themes={{{_js(themes)}}} />\n\n"
        f"## 4. 거래대금 상위 종목\n\n"
        f"돈이 가장 많이 몰린 종목입니다. 시장의 관심이 어디 있는지 보여 줍니다.\n\n"
        f"<RankGroup lists={{{_js([{'label': ('코스피' if x['market'] == 'KOSPI' else '코스닥') + ' 거래대금 상위', 'items': x['items']} for x in lists['amount']])}}} />\n\n"
        f"## 5. 해외 시장·환율·금리\n\n"
        f"<MacroStrip items={{{_js(macro)}}} />\n\n"
        f"{signal_section(d['charts'].get('KOSPI'), '6. 코스피 차트 신호')}\n"
        f"{signal_section(d['charts'].get('KOSDAQ'), '7. 코스닥 차트 신호')}\n"
        f"<SignalGuide />\n\n"
        f"## 8. 내일 볼 것\n\n"
    )
    for code in ("KOSPI", "KOSDAQ"):
        c = d["charts"].get(code)
        if c:
            body += f"- {INDEX_NAME[code]}: {c['next']}\n"
    body += ("- 외국인이 코스피에서 사는 쪽으로 돌아서는지\n\n"
             "---\n\n"
             "*본 리포트는 투자 참고용 정보이며, 특정 종목의 매수·매도를 권유하지 않습니다. "
             "차트 신호는 과거 가격으로 만든 규칙이라 미래를 보장하지 않습니다. 투자 판단과 책임은 투자자 본인에게 있습니다.*\n")
    return fm + body


# ══════════════════════════════════════════════ 실행
def console(d):
    L = [f"[시황 데이터 {d['base_day']}] 생성 {d['generated']}"]
    for r in d["indices"]:
        f = r.get("flows") or {}
        L.append(f"- {r['name']} {_n(r['value'])} ({r_pct(r['rate'])})"
                 + (f" · 개인 {f.get('individual'):+,} 외국인 {f.get('foreign'):+,} 기관 {f.get('institution'):+,}억" if f else ""))
    ind = d.get("industry") or []
    if ind:
        L.append("- 업종 상위: " + ", ".join(f"{r['name']}({r_pct(r['rate'])})" for r in ind[:5]))
        L.append("- 업종 하위: " + ", ".join(f"{r['name']}({r_pct(r['rate'])})" for r in ind[-5:][::-1]))
    for code, c in d["charts"].items():
        if c:
            L.append(f"- [{code} 차트 신호] {c['label']} — {c['text']}")
            L.append(f"    다음: {c['next']}")
            L.append("    최근 신호: " + ", ".join(f"{s['date']} {s['kind']}" for s in c["recent"]))
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="MDX 초안 생성")
    ap.add_argument("--force", action="store_true", help="기존 MDX 덮어쓰기")
    ap.add_argument("--title", help="MDX 제목 지정")
    ap.add_argument("--out", help="MDX 저장 경로 지정(미리보기용)")
    a = ap.parse_args()

    d = collect()
    dump = pathlib.Path(tempfile.gettempdir()) / f"genesis_market_brief_{d['base_day'].replace('-', '')}.json"
    dump.write_text(json.dumps(d, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(console(d))
    print(f"\n원자료: {dump}")
    for c in d["charts"].values():
        if c:
            print(f"차트 JSON: public{c['src']}")
    if d["base_day"] != dt.date.today().isoformat():
        print(f"⚠️ 기준 거래일 {d['base_day']} ≠ 오늘 {dt.date.today()} — 휴장일이거나 장 시작 전입니다.")

    if a.write:
        out = pathlib.Path(a.out).resolve() if a.out else MDX_DIR / f"{d['base_day']}-market-analysis-genesis.mdx"
        if out.exists() and not a.force:
            print(f"⚠️ {out.relative_to(ROOT)} 이미 있음 — 덮어쓰려면 --force")
            return
        out.write_text(build_mdx(d, a.title), encoding="utf-8", newline="\n")   # CRLF는 contentlayer YAML 파싱을 깬다
        print(f"MDX 초안: {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
