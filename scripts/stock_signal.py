# -*- coding: utf-8 -*-
r"""제네시스 종목분석 v2 — 개별 종목 차트 신호 (주도섹터 '차트 신호' 트리거 규칙).

2026-10-07 개편(황원장 지시): 종목 리포트가 너무 어려워 트래픽에 불리 → 쉬운 종목 리포트 + 차트 신호 차트 제공.
규칙·계산은 market_brief.py(= 주도섹터/scripts/chart_signal.py 복사본)를 그대로 가져다 쓴다. 이 파일에 규칙을 복제하지 않는다.
  ① 준비(arm)  : 눌렸다 / 과열됐다  → 박스 시작
  ② 방아쇠(fire): 방향이 꺾였다      → 박스 끝 + ▲▼
  매도 신호는 검증상 동전 이하 → '팔아라'가 아니라 '더 사지 않는다'. 차트는 '언제'만, 단독 매매근거 아님.

데이터: 일봉 = KRX 정규장 종가(siseJson). 리포트 본문에 데이터 제공 사이트 이름은 쓰지 않는다.
산출  : public/charts/stock/YYYY-MM-DD-{코드}.json  (SignalChart 컴포넌트가 읽는 차트 데이터 — push 시 MDX와 함께 올릴 것)
        콘솔 = 리포트에 붙여 넣을 MDX 섹션(차트 + 상태 카드 + 최근 신호 + 과거 성적)

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


def section(desc, name):
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
            f"<SignalGuide />\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("code", help="6자리 종목코드")
    ap.add_argument("name", help="종목명(본문 표기용)")
    ap.add_argument("--date", default=dt.date.today().isoformat(), help="리포트 날짜 YYYY-MM-DD (차트 파일명)")
    a = ap.parse_args()
    desc, out = build(a.code, a.name, a.date)
    print(f"[차트 JSON] {out.relative_to(mb.ROOT).as_posix()}  (기준일 {desc['asof']}, 종가 {desc['close']:,.0f}원)")
    print(f"[상태] {desc['label']}")
    print("=" * 60)
    print(section(desc, a.name))


if __name__ == "__main__":
    main()
