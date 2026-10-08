# -*- coding: utf-8 -*-
r"""제네시스 투자성과리뷰 v3 — 지난 추천·관심 종목 '성적표' 자동 계산.

2026-10-08 개편(황원장 지시): 성과리뷰 공개 페이지를 쉬운 '성적표'로. 수익률·목표가 도달·위험 기준선 이탈을
손으로 세지 않고 일봉 종가로 계산해, 공개 페이지와 상세 기록이 같은 숫자를 쓰게 한다.
일봉은 KRX+NXT 통합 시세라 기준일이 오늘이면 20시까지 종가가 움직인다 → 20시 전 실행은 '잠정' 표시가 붙는다.
같은 회차 안에서는 한 번 돌린 출력(--json)을 끝까지 쓰고, 다시 돌려 숫자를 바꾸지 않는다.

판정 (모두 종가 기준, 리포트 날짜 다음 거래일부터 기준일까지)
  🎯 목표가 도달  : 종가가 목표가 이상인 첫 날
  🛑 기준선 이탈  : 종가가 위험 기준선(손절가) 이하인 첫 날
  둘 다 있으면 먼저 온 것. 없으면 '진행 중'(📈 플러스 / 📉 마이너스).
  목표가가 리포트 가격보다 2% 미만 위면 '도달'이 의미 없으므로 목표가 판정을 하지 않는다(결과에 표시).
  목표가·기준선이 없는 종목(옛 섀도 후보 등)은 '-'로 넣는다 — 그 판정만 건너뛴다. 값을 지어내지 말 것.
  수익률 = 기준일 종가 ÷ 리포트 가격 − 1.  같은 기간 코스피 수익률을 나란히 둔다.

입력
  --log  content/picks-log/YYYYMMDD-genesis-*-log.mdx   (프론트매터 picks: 목록을 읽는다 — v3 상세 기록부터)
  --pick 코드:종목명:리포트일:가격:목표가:기준선[:구분]   (picks: 가 없는 옛 리포트용, 여러 번 가능)
         종목명에 공백이 있으면 통째로 따옴표: --pick "010120:LS ELECTRIC:2026-10-02:209000:296400:186000"
         목표가·기준선이 없으면 '-':          --pick 006280:녹십자:2026-10-01:128600:-:-:섀도
  --public : 공개 페이지용 — 구분(kind)이 '섀도'인 행(조건 미달로 담지 않은 후보)을 뺀다

CLI:
  python -X utf8 scripts/review_scoreboard.py --log content/picks-log/20261001-genesis-log.mdx
  python -X utf8 scripts/review_scoreboard.py --pick 011200:HMM:2026-10-01:21250:22850:20369:관심 --asof 2026-10-08
  python -X utf8 scripts/review_scoreboard.py --log ... --json scratch.json   (상세 기록용 원자료)
"""
import argparse
import datetime as dt
import json
import pathlib
import re
import sys

import pandas as pd
import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import market_brief as mb  # noqa: E402

TERM_NAME = {"short": "단기", "mid": "중기", "long": "장기"}


def read_log(path):
    txt = pathlib.Path(path).read_text(encoding="utf-8")
    m = re.match(r"---\n(.*?)\n---", txt, re.S)
    if not m:
        sys.exit(f"[오류] 프론트매터 없음: {path}")
    fm = yaml.safe_load(m.group(1))
    picks = fm.get("picks") or []
    if not picks:
        print(f"[경고] {path} — picks: 목록 없음. --pick 으로 직접 넣어 주세요.", file=sys.stderr)
    date = str(fm["date"])
    return [{"code": str(p["code"]).zfill(6), "name": p["name"], "date": date, "price": float(p["price"]),
             "target": p.get("target"), "stop": p.get("stop"), "kind": p.get("kind", "추천"),
             "term": fm.get("term", "short")} for p in picks]


def parse_pick(s, term):
    f = s.split(":")
    if len(f) < 6:
        sys.exit(f"[오류] '{s}' — 코드:종목명:리포트일:가격:목표가:기준선[:구분]")
    num = lambda x: float(x.replace(",", "")) if x not in ("", "-") else None  # noqa: E731
    return {"code": f[0].zfill(6), "name": f[1], "date": f[2], "price": num(f[3]), "target": num(f[4]),
            "stop": num(f[5]), "kind": f[6] if len(f) > 6 else "추천", "term": term}


_cache = {}


def closes(sym):
    if sym not in _cache:
        _cache[sym] = mb.fetch_daily(sym, years=2)["close"]
    return _cache[sym]


def judge(p, asof):
    c = closes(p["code"])
    d0, d1 = pd.Timestamp(p["date"]), pd.Timestamp(asof)
    win = c[(c.index > d0) & (c.index <= d1)]
    if win.empty:
        return {**p, "days": 0, "now": None, "ret": None, "result": "⏳ 아직 거래일 없음"}
    now = float(win.iloc[-1])
    k = closes("KOSPI")
    k0 = k[k.index <= d0]
    k1 = k[k.index <= d1]
    kret = (float(k1.iloc[-1]) / float(k0.iloc[-1]) - 1) * 100 if len(k0) and len(k1) else None
    ev = []
    # 목표가가 리포트 가격과 2% 이내면 '도달'이 의미 없다 (예: 목표가 = 종가인 섀도 후보)
    weak_target = bool(p["target"]) and p["target"] < p["price"] * 1.02
    if p["target"] and not weak_target:
        hit = win[win >= p["target"]]
        if len(hit):
            ev.append((hit.index[0], "🎯 목표가 도달", float(hit.iloc[0])))
    if p["stop"]:
        hit = win[win <= p["stop"]]
        if len(hit):
            ev.append((hit.index[0], "🛑 기준선 이탈", float(hit.iloc[0])))
    ret = (now / p["price"] - 1) * 100
    if ev:
        d, label, px = min(ev)
        result = f"{label} ({d.month}/{d.day}, {(px / p['price'] - 1) * 100:+.1f}%)"
        event = {"date": d.strftime("%Y-%m-%d"), "label": label, "price": px}
    else:
        result = ("📈" if ret > 0 else "📉" if ret < 0 else "➖") + " 진행 중"
        event = None
    if weak_target:
        result += " (목표가가 가격과 2% 이내라 도달 판정 제외)"
    return {**p, "days": len(win), "asof": win.index[-1].strftime("%Y-%m-%d"), "now": now, "ret": ret,
            "kospi": kret, "best": (float(win.max()) / p["price"] - 1) * 100,
            "worst": (float(win.min()) / p["price"] - 1) * 100, "event": event, "result": result}


def won(x):
    return "—" if x is None else f"{x:,.0f}원"


def pct(x):
    return "—" if x is None else f"{x:+.1f}%"


def table(rows):
    out = ["| 종목 | 구분 | 그때 가격 | 지금 가격 | 수익률 | 같은 기간 코스피 | 결과 |",
           "| :--- | :---: | ---: | ---: | ---: | ---: | :--- |"]
    for r in rows:
        d = pd.Timestamp(r["date"])
        out.append(f"| {r['name']} | {r['kind']} | {won(r['price'])} ({d.month}/{d.day}) | {won(r['now'])} | "
                   f"**{pct(r['ret'])}** | {pct(r.get('kospi'))} | {r['result']} |")
    return "\n".join(out)


def stats(rows):
    v = [r for r in rows if r["ret"] is not None]
    if not v:
        return "평가할 거래일이 아직 없습니다."
    avg = sum(r["ret"] for r in v) / len(v)
    ks = [r["kospi"] for r in v if r.get("kospi") is not None]
    kavg = sum(ks) / len(ks) if ks else None
    up = sum(r["ret"] > 0 for r in v)
    tgt = sum(1 for r in v if r["event"] and r["event"]["label"].startswith("🎯"))
    stp = sum(1 for r in v if r["event"] and r["event"]["label"].startswith("🛑"))
    line = f"**평균 {avg:+.1f}%**"
    if kavg is not None:
        diff = avg - kavg
        line += f" · 같은 기간 코스피 {kavg:+.1f}% → **코스피보다 {abs(diff):.1f}%p {'앞섬' if diff >= 0 else '뒤짐'}**"
    line += f" · 오른 종목 {up}/{len(v)} · 목표가 도달 {tgt} · 기준선 이탈 {stp}"
    return line


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", action="append", default=[], help="v3 상세 기록 파일 (picks: 프론트매터)")
    ap.add_argument("--pick", action="append", default=[], help="코드:종목명:리포트일:가격:목표가:기준선[:구분]")
    ap.add_argument("--term", default="short", choices=list(TERM_NAME), help="--pick 종목의 기간 구분")
    ap.add_argument("--asof", default=dt.date.today().isoformat(), help="기준일 YYYY-MM-DD")
    ap.add_argument("--public", action="store_true", help="공개 페이지용 — kind '섀도' 행 제외")
    ap.add_argument("--json", help="계산 원자료 저장 경로 (상세 기록 작성용, scratchpad에 둘 것)")
    a = ap.parse_args()

    picks = [p for f in a.log for p in read_log(f)] + [parse_pick(s, a.term) for s in a.pick]
    if a.public:
        picks = [p for p in picks if p["kind"] != "섀도"]
    if not picks:
        sys.exit("[오류] --log 또는 --pick 이 필요합니다.")
    rows = []
    for p in picks:
        try:
            rows.append(judge(p, a.asof))
        except Exception as e:
            print(f"[{p['name']}] 시세 수집 실패 — 제외 ({e})", file=sys.stderr)

    now = dt.datetime.now()
    provisional = a.asof == now.date().isoformat() and now.hour < 20
    if provisional:
        print(f"[주의] {now:%H:%M} 실행 — 오늘 종가는 20시까지 움직이는 잠정치입니다. 상세 기록에 '잠정'을 표시하고, "
              "이 출력(--json)을 이 회차 끝까지 그대로 쓰세요.", file=sys.stderr)
    tag = f", {now:%H:%M} 잠정" if provisional else ""
    for term in TERM_NAME:
        g = [r for r in rows if r["term"] == term]
        if not g:
            continue
        print(f"=== {TERM_NAME[term]} (기준일 {a.asof}{tag}) ===\n")
        print(table(g) + "\n")
        print(stats(g) + "\n")
    if a.json:
        pathlib.Path(a.json).write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"[원자료] {a.json}", file=sys.stderr)


if __name__ == "__main__":
    main()
