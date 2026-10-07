# -*- coding: utf-8 -*-
r"""제네시스 종목분석 v2 — 개별 종목 차트 신호 (주도섹터 '차트 신호' 트리거 규칙).

2026-10-07 개편(황원장 지시): 종목 리포트가 너무 어려워 트래픽에 불리 → 쉬운 종목 리포트 + 차트 신호 차트 제공.
규칙·계산은 market_brief.py(= 주도섹터/scripts/chart_signal.py 복사본)를 그대로 가져다 쓴다. 이 파일에 규칙을 복제하지 않는다.
  ① 준비(arm)  : 눌렸다 / 과열됐다  → 박스 시작
  ② 방아쇠(fire): 방향이 꺾였다      → 박스 끝 + ▲▼
  매도 신호는 검증상 동전 이하 → '팔아라'가 아니라 '더 사지 않는다'. 차트는 '언제'만, 단독 매매근거 아님.

PER 함수(참고·신호 미반영) = 주도섹터/scripts/per_forecast.py 를 그대로 불러 쓴다(복사 금지 — 가중치는 주도섹터에서만 갱신).
  ln(PER_1y/PER_now) = b0 + b_g·ln(EPS_1y/EPS_now) + b_mr·ln(median36(PER)/PER_now) → 1년 후 주가 = PER_1y × EPS_1y
  주도섹터 폴더가 없거나 적자·EPS 결측이면 그 섹션만 생략한다.

데이터: 일봉 = KRX 정규장 종가(siseJson). 리포트 본문에 데이터 제공 사이트 이름은 쓰지 않는다.
산출  : public/charts/stock/YYYY-MM-DD-{코드}.json  (SignalChart 컴포넌트가 읽는 차트 데이터 — push 시 MDX와 함께 올릴 것)
        콘솔 = 리포트에 붙여 넣을 MDX 섹션(차트 + 상태 카드 + 최근 신호 + 과거 성적 + PER 함수)

CLI:
  python -X utf8 scripts/stock_signal.py 011200 HMM
  python -X utf8 scripts/stock_signal.py 011200 HMM --date 2026-10-07
"""
import argparse
import datetime as dt
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import market_brief as mb  # noqa: E402

CHART_DIR = mb.ROOT / "public" / "charts" / "stock"
JUDO_SCRIPTS = pathlib.Path.home() / "OneDrive" / "바탕 화면" / "주도섹터" / "scripts"

# 지수는 소수 둘째 자리, 주가는 원 단위 — describe()의 가격 표기만 원 단위로 바꾼다.
mb._n = lambda x, d=0: f"{x:,.0f}"

# 영문·숫자로 끝나는 종목명(HMM·SK·LG)은 읽는 소리로 받침을 판단한다 (HMM은 · SK는 · LG는).
_EN_BATCHIM = set("LMNR") | set("013678")
_hangul_josa = mb.josa


def _josa(word, pair="은는"):
    ch = word[-1].upper()
    if "A" <= ch <= "Z" or ch.isdigit():
        return word + (pair[0] if ch in _EN_BATCHIM else pair[1])
    return _hangul_josa(word, pair)


mb.josa = _josa


def build(code, name, date_str):
    df = mb.indicators(mb.fetch_daily(code))
    sigs = mb.signals(df)
    bt = mb.backtest(df, sigs)
    desc = mb.describe(df, sigs, bt, name)
    CHART_DIR.mkdir(parents=True, exist_ok=True)
    out = CHART_DIR / f"{date_str}-{code}.json"
    out.write_text(json.dumps(mb.chart_payload(df, sigs, desc, code, name), ensure_ascii=False,
                              separators=(",", ":")), encoding="utf-8")
    desc["src"] = f"/charts/stock/{out.name}"
    desc["asof"] = df.index[-1].strftime("%Y-%m-%d")
    return desc, out


def per_forecast(code):
    """주도섹터 PER 함수 → 1년 후 시장이 받아들일 PER·주가. 쓸 수 없으면 None."""
    if not JUDO_SCRIPTS.exists():
        print(f"[PER 함수] 주도섹터 폴더 없음 — 생략 ({JUDO_SCRIPTS})", file=sys.stderr)
        return None
    sys.path.insert(0, str(JUDO_SCRIPTS))
    try:
        import per_forecast as pf
        a = pf.forecast(code)
        a["hit"] = pf.OOS.get("hit")
        return a
    except Exception as e:
        print(f"[PER 함수] 적용 불가 — 생략 ({e})", file=sys.stderr)
        return None


def per_section(a, name):
    rel = ("과거보다 비싼 편" if a["per_now"] > a["med36"] * 1.1 else
           "과거보다 싼 편" if a["per_now"] < a["med36"] * 0.9 else "과거와 비슷")
    eps_chg = (a["eps_1y"] / a["eps_now"] - 1) * 100
    chg = a["chg"] * 100
    r = a["range"]
    rows = [
        "| 항목 | 값 |",
        "| :--- | :--- |",
        f"| 지금 PER | **{a['per_now']:.1f}배** (과거 3년 중앙값 {a['med36']:.1f}배 → {rel}) |",
        f"| 1년 뒤 예상 주당이익(EPS) | {a['eps_now']:,.0f}원 → **{a['eps_1y']:,.0f}원** ({eps_chg:+.0f}%) |",
        f"| 1년 뒤 시장이 받아들일 PER | **{a['per_1y']:.1f}배** |",
        f"| **1년 뒤 계산 주가** | **{a['price_1y']:,.0f}원** (지금보다 {chg:+.0f}%) |",
        f"| 보통 범위 | {r['q25']:,.0f}원 ~ {r['q75']:,.0f}원 |",
    ]
    t = a.get("target")
    if t:
        rows.append(f"| 증권가 목표주가 평균 | {t['target']:,.0f}원 = 1년 뒤 PER {t['per']:.1f}배를 가정 → "
                    + ("**계산값보다 낙관적**" if t["per"] > a["per_1y"] else "**계산값보다 보수적**") + " |")
    if chg <= -10:
        easy = "이익이 줄어들 것으로 예상되는 데다 지금 PER이 과거보다 높아, 계산상으로는 지금보다 낮은 가격이 나옵니다."
        if eps_chg > 0:
            easy = "지금 PER이 과거보다 높아, 이익이 늘어나도 계산상으로는 지금보다 낮은 가격이 나옵니다."
    elif chg >= 10:
        easy = "예상 이익과 과거 PER을 함께 보면, 계산상으로는 지금보다 높은 가격이 나옵니다."
    else:
        easy = "예상 이익과 과거 PER을 함께 보면, 계산상으로는 지금 가격과 큰 차이가 없습니다."
    hit = f"방향 적중 약 {a['hit'] * 100:.0f}%" if a.get("hit") else "검증 진행 중"
    return (f"### 🧮 이익으로 본 1년 뒤 주가 (PER 함수 · 참고)\n\n"
            f"주가는 결국 **이익 × 시장이 쳐주는 배수(PER)**입니다. 증권가가 예상하는 1년 뒤 이익과 "
            f"{name}의 과거 3년 PER을 함께 넣어, 1년 뒤 시장이 받아들일 가격을 계산했습니다.\n\n"
            + "\n".join(rows) + "\n\n"
            f"{easy}\n\n"
            f"> ⚠️ 참고용 계산입니다. 차트 신호에는 반영하지 않습니다. 36개 종목 2012~2024년 검증에서 {hit}였고, "
            f"보통 범위를 벗어나는 경우도 흔합니다.\n")


def section(desc, name, per=None):
    last = desc["last"]
    last_txt = (f"가장 최근 신호는 **{last['date']} {last['kind']}**({last['price']:,.0f}원)이고, "
                f"그 뒤 지금까지 **{last['since']:+.1f}%** 움직였습니다."
                if last else "최근 1년 차트에는 신호가 없습니다.")
    card = {"state": desc["state"], "label": desc["label"], "summary": desc["text"],
            "checks": desc["checks"], "next": desc["next"]}
    return (f"## 📈 {name} 차트 신호: {desc['label']}\n\n"
            f"<SignalChart src=\"{desc['src']}\" />\n\n"
            f"<SignalCard data={{{mb._js(card)}}} />\n\n"
            f"{last_txt}\n\n"
            f"> {desc['record']}\n\n"
            + (per_section(per, name) + "\n" if per else "")
            + "<SignalGuide />\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("code", help="6자리 종목코드")
    ap.add_argument("name", help="종목명(본문 표기용)")
    ap.add_argument("--date", default=dt.date.today().isoformat(), help="리포트 날짜 YYYY-MM-DD (차트 파일명)")
    a = ap.parse_args()
    desc, out = build(a.code, a.name, a.date)
    per = per_forecast(a.code)
    print(f"[차트 JSON] {out.relative_to(mb.ROOT).as_posix()}  (기준일 {desc['asof']}, 종가 {desc['close']:,.0f}원)")
    print(f"[상태] {desc['label']}")
    print("=" * 60)
    print(section(desc, a.name, per))


if __name__ == "__main__":
    main()
