# -*- coding: utf-8 -*-
r"""제네시스 중기·장기 v3 — 관심 종목 3개 차트 신호 + PER 함수(1년 뒤 주가)를 한 번에.

2026-10-08 개편(황원장 지시): 단기 신호등·종목분석 v2처럼 중기·장기 리포트도 쉬운 공개 페이지로.
계산은 stock_signal.py(= market_brief 차트 신호 규칙 + 주도섹터 per_forecast)를 그대로 불러 쓴다. 규칙 복제 금지.

산출  : public/charts/stock/YYYY-MM-DD-{코드}.json  (종목마다 1개 — push 시 MDX와 함께 올릴 것)
        콘솔 = ① '한눈에 보기' 표 행  ② 종목별 차트 신호 블록  ③ 끝에 붙일 <SignalGuide />

CLI:
  python -X utf8 scripts/picks_signal.py 010120:LS ELECTRIC 005930:삼성전자 036570:NC --date 2026-10-09
  python -X utf8 scripts/picks_signal.py 071050:한국금융지주 402340:SK스퀘어 015760:한국전력 --date 2026-11-02 --full
    --full : 종목마다 상태 카드(체크리스트)와 PER 함수 표 전체를 넣는다 (장기 권장 — 1~3년은 이익이 핵심)
"""
import argparse
import datetime as dt
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import stock_signal as ss  # noqa: E402
mb = ss.mb


def per_line(a):
    if not a:
        return "적자이거나 이익 예상치가 없어 계산하지 않음"
    return f"약 {round(a['price_1y'], -2):,.0f}원 (지금보다 {a['chg'] * 100:+.0f}%)"


def per_short(a, name):
    if not a:
        return ""
    rel = ("과거보다 비싼 편" if a["per_now"] > a["med36"] * 1.1 else
           "과거보다 싼 편" if a["per_now"] < a["med36"] * 0.9 else "과거와 비슷")
    return (f"**🧮 이익으로 본 1년 뒤 주가 (참고):** {per_line(a)} — 지금 PER {a['per_now']:.1f}배, "
            f"과거 3년 중앙값 {a['med36']:.1f}배({rel}). 차트 신호에는 반영하지 않는 참고 계산입니다.\n\n")


def block(rank, name, desc, per, full):
    last = desc["last"]
    last_txt = (f"가장 최근 신호는 **{last['date']} {last['kind']}**({last['price']:,.0f}원), "
                f"그 뒤 **{last['since']:+.1f}%**."
                if last else "최근 1년 차트에는 신호가 없습니다.")
    head = f"#### 📈 {name} 차트 신호: {desc['label']}\n\n<SignalChart src=\"{desc['src']}\" />\n\n"
    if full:
        card = {"state": desc["state"], "label": desc["label"], "summary": desc["text"],
                "checks": desc["checks"], "next": desc["next"]}
        return (head + f"<SignalCard data={{{mb._js(card)}}} />\n\n{last_txt}\n\n"
                + (ss.per_section(per, name).replace("### 🧮", "#### 🧮") + "\n" if per else ""))
    return head + f"{desc['text']} {last_txt}\n\n" + per_short(per, name)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stocks", nargs="+", help="코드:종목명 (관심 순위 순서대로)")
    ap.add_argument("--date", default=dt.date.today().isoformat(), help="리포트 날짜 YYYY-MM-DD (차트 파일명)")
    ap.add_argument("--full", action="store_true", help="상태 카드 + PER 함수 표 전체 (장기 권장)")
    a = ap.parse_args()

    rows, blocks, files = [], [], []
    for i, s in enumerate(a.stocks, 1):
        code, _, name = s.partition(":")
        if not (code.isdigit() and len(code) == 6 and name):
            sys.exit(f"[오류] '{s}' — 코드:종목명 형식이어야 합니다 (예: 005930:삼성전자)")
        try:
            desc, out = ss.build(code, name, a.date)
        except Exception as e:
            print(f"[{name}] 차트 신호 실패 — 이 종목은 차트 블록 생략 ({e})", file=sys.stderr)
            rows.append(f"| {name} | — | 데이터 없음 | — |")
            continue
        per = ss.per_forecast(code)
        files.append(out.relative_to(mb.ROOT).as_posix())
        rows.append(f"| {name} | {desc['close']:,.0f}원 | {desc['label']} | {per_line(per)} |")
        blocks.append(block(i, name, desc, per, a.full))
        print(f"[{name}] 기준일 {desc['asof']} · 종가 {desc['close']:,.0f}원 · {desc['label']}", file=sys.stderr)

    print("[차트 JSON] " + " ".join(files))
    print("=" * 60)
    print("① 한눈에 보기 표 (그대로 붙여 넣기)\n")
    print("| 종목 | 오늘 종가 | 차트 신호 | 이익으로 본 1년 뒤 주가 (참고) |")
    print("| :--- | ---: | :--- | :--- |")
    print("\n".join(rows))
    print("\n" + "=" * 60)
    print("② 종목별 차트 신호 블록 (각 종목 섹션 끝에 붙여 넣기)\n")
    print(("\n" + "-" * 40 + "\n").join(blocks))
    print("=" * 60)
    print("③ 페이지 끝(FAQ 앞)에 한 번만\n\n<SignalGuide />")


if __name__ == "__main__":
    main()
