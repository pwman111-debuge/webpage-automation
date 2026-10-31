# -*- coding: utf-8 -*-
r"""제네시스 모의 포트폴리오 일일 성과 리포트.

사용법:
  python -X utf8 scripts/portfolio_review.py --set-open          # 시작일 장 시작 후, 시가를 기록
  python -X utf8 scripts/portfolio_review.py --write             # 장 마감 후, 리포트 + 차트 JSON 생성
  python -X utf8 scripts/portfolio_review.py --date 2026-10-30 --dry   # 시험 출력 (파일 저장 없음)

산출: content/picks-feedback/YYYY-MM-DD-performance-review.mdx, public/charts/stock/YYYY-MM-DD-{코드}.json

성과는 시작 시가 대비 종가, 시작 비중 그대로 계산한다(거래비용 미반영).
여러 달을 잇는 누적 계산은 월말 교체 스크립트가 맡는다.
차트 신호는 주도섹터 규칙을 쓰는 stock_signal.py를 그대로 불러 쓴다. 규칙 복제 금지.
"""
import argparse
import datetime as dt
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import stock_signal as ss  # noqa: E402

mb = ss.mb
ROOT = mb.ROOT
PORTFOLIO = ROOT / "public" / "charts" / "portfolio"
START_LOG = ROOT / "content" / "portfolio-log"
THUMBNAIL = "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?auto=format&fit=crop&w=1200&q=80"


def latest_path():
    return sorted(p for p in PORTFOLIO.glob("*.json") if p.stem[:2] == "20")[-1]


def set_open():
    path = latest_path()
    data = json.loads(path.read_text(encoding="utf-8"))
    day = pd_day(data["startDate"])
    log = next(START_LOG.glob(f"{data['month']}-*.mdx"))
    text = log.read_text(encoding="utf-8")
    for h in data["holdings"] + data["compare"]:
        df = mb.fetch_daily(h["code"], years=1)
        if day not in df.index:
            sys.exit(f"[오류] {h['name']} {data['startDate']} 시세 없음")
        h["open"] = int(df.loc[day, "open"])
        text = re.sub(rf"(\| {h['code']} \|.*\| )기록 예정( \|)", rf"\g<1>{h['open']:,}\g<2>", text)
        print(f"{h['name']} 시가 {h['open']:,}")
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    log.write_text(text, encoding="utf-8", newline="\n")


def pd_day(text):
    import pandas as pd
    return pd.Timestamp(text)


def closes(code, day, start):
    """(시작 시가 없을 때 쓰는 당일 시가, 어제까지의 비교 종가, 오늘 종가)."""
    df = mb.fetch_daily(code, years=1)
    if day not in df.index:
        sys.exit(f"[오류] {code} {day.date()} 시세 없음. 휴장일이거나 장 마감 전입니다.")
    held = df.loc[start:day]
    return float(held["open"].iloc[0]), float(held["close"].iloc[-2]) if len(held) > 1 else None, float(held["close"].iloc[-1])


def value(rows):
    """오늘 등락과 시작 후 수익률(비중 가중, %)."""
    now = sum(r["weight"] * r["close"] / r["open"] for r in rows) / 100
    prev = sum(r["weight"] * (r["prev"] or r["open"]) / r["open"] for r in rows) / 100
    return (now / prev - 1) * 100, (now - 1) * 100


def pct(v):
    return f"{v:+.2f}%"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=dt.date.today().isoformat())
    ap.add_argument("--set-open", action="store_true")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    if a.set_open:
        return set_open()

    data = json.loads(latest_path().read_text(encoding="utf-8"))
    day = pd_day(a.date)
    start = day if a.dry else pd_day(data["startDate"])
    rows = []
    for h in data["holdings"]:
        first, prev, close = closes(h["code"], day, start)
        opened = h["open"] or (first if a.dry else None)
        if not opened:
            sys.exit("[오류] 시작 시가가 없습니다. --set-open 을 먼저 실행하세요.")
        rows.append({**h, "open": opened, "prev": prev, "close": close})

    alt = data["compare"][0]
    first, prev, close = closes(alt["code"], day, start)
    swap = {**alt, "weight": 10, "open": alt["open"] or first, "prev": prev, "close": close}
    c5 = [r for r in rows if r["role"] != "주도산업"] + [swap]
    core = [r for r in rows if r["role"] == "코어"]
    kospi = mb.fetch_daily("KOSPI", years=1)
    k_prev, k_now = kospi["close"].loc[:day].iloc[-2:]
    k_open = float(kospi.loc[start:, "open"].iloc[0])
    if day == start:  # 시작일의 오늘 등락은 모두 시가 기준으로 맞춘다.
        k_prev = k_open
    day_ret, total = value(rows)
    core_day, core_total = value([{**core[0], "weight": 100}])
    c5_day, c5_total = value(c5)
    gap = total - core_total

    table, charts, files = [], [], []
    for r in rows:
        desc, out = ss.build(r["code"], r["name"], a.date)
        files.append(out)
        r_day = (r["close"] / (r["prev"] or r["open"]) - 1) * 100
        r_total = (r["close"] / r["open"] - 1) * 100
        table.append(f"| {r['name']} | {r['weight']}% | {r['close']:,.0f}원 | {pct(r_day)} | **{pct(r_total)}** | {desc['label']} |")
        charts.append(f"### {r['name']}: {desc['label']}\n\n<SignalChart src=\"{desc['src']}\" />\n\n{desc['text']}\n")

    events = json.loads((PORTFOLIO / "events.json").read_text(encoding="utf-8"))
    today = [f"- {e['type']}: {e['detail']}" for e in events if e["date"] == a.date]
    m, d = day.month, day.day
    best = max(rows, key=lambda r: r["close"] / r["open"])
    worst = min(rows, key=lambda r: r["close"] / r["open"])
    summary = (f"오늘 모의 포트폴리오는 {pct(day_ret)}, 시작 후 {pct(total)}입니다. "
               f"같은 기간 KIWOOM 200TR 100%는 {pct(core_total)}로 {abs(gap):.2f}%p {'앞섰' if gap >= 0 else '뒤졌'}습니다.")
    first_day = chr(10) + "시작일의 오늘 등락은 시가 기준입니다." + chr(10) if day == start else ""
    doc = f'''---
title: "제네시스 모의 포트폴리오 {m}월 {d}일 성적표 · 오늘 {pct(day_ret)}, 시작 후 {pct(total)}"
date: "{a.date}"
summary: "{summary}"
tags: ["제네시스성적표", "모의포트폴리오", "포트폴리오수익률", "차트신호"]
thumbnail: "{THUMBNAIL}"
---

# {m}월 {d}일 모의 포트폴리오 성적표

> **한 줄 요약:** {summary}

## 오늘 변경 사항

{chr(10).join(today) if today else "변경 없음. 달 중간에는 사건 편출 외에는 종목을 바꾸지 않습니다."}

## 종목별 등락
{first_day}
| 종목 | 비중 | 오늘 종가 | 오늘 등락 | 시작 후 | 차트 신호 |
| :--- | ---: | ---: | ---: | ---: | :--- |
{chr(10).join(table)}

가장 좋은 종목은 {best['name']}, 가장 약한 종목은 {worst['name']}입니다.

## 지금까지의 성과

{data["startDate"]} 시가 기준입니다. 거래비용은 반영하지 않았습니다.

| 구분 | 오늘 | 시작 후 |
| :--- | ---: | ---: |
| **제네시스 모의 포트폴리오** | **{pct(day_ret)}** | **{pct(total)}** |
| KIWOOM 200TR 100% | {pct(core_day)} | {pct(core_total)} |
| 비교 기준(주도산업 슬롯 없음) | {pct(c5_day)} | {pct(c5_total)} |
| 코스피 지수 | {pct((k_now / k_prev - 1) * 100)} | {pct((k_now / k_open - 1) * 100)} |

## 종목별 차트 신호

차트 신호는 참고 표시입니다. 이 신호로 달 중간에 종목을 바꾸지 않습니다.

{chr(10).join(charts)}
<SignalGuide />

모의 운용 기록이며 투자 권유가 아닙니다. 구성과 운용 기준은 [제네시스 모의 포트폴리오](/portfolio)에서 볼 수 있습니다.
'''
    rel = [f.relative_to(ROOT).as_posix() for f in files]
    if a.dry:
        print(doc)
        for f in files:
            f.unlink()
        return
    if a.write:
        path = ROOT / "content" / "picks-feedback" / f"{a.date}-performance-review.mdx"
        path.write_text(doc, encoding="utf-8", newline="\n")
        print(f"[완료] {path.relative_to(ROOT).as_posix()}")
        print("[차트 JSON] " + " ".join(rel))


if __name__ == "__main__":
    main()
