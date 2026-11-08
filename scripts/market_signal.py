# -*- coding: utf-8 -*-
r"""제네시스 시장 신호등 — 주도섹터 산출물을 공개용 JSON으로 변환.

사용법:
  python -X utf8 scripts/market_signal.py --refresh   # 주도섹터 데이터를 갱신한 뒤 변환
  python -X utf8 scripts/market_signal.py             # 기존 데이터로 변환만

산출: public/charts/signal/YYYY-MM-DD.json (/signal 페이지가 빌드 때 읽음)

공개 원칙: 시장의 위치와 상태만 표시한다. 주도섹터의 조언 문구(action·verdict 문장)는 가져오지 않고,
값을 이 파일의 중립 문구로 다시 쓴다. 코스피 천장 수치는 지수 전망이 아니라는 안내와 함께 공개한다.
"""
import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
JUDO = pathlib.Path.home() / "OneDrive" / "바탕 화면" / "주도섹터"
OUT = ROOT / "public" / "charts" / "signal"

# 주도섹터 jonghap_prep 순서를 따른다: 뒤 단계가 앞 단계 JSON을 읽는다.
# kospi_earnings.py는 넣지 않는다. 지수 PER과 순이익의 기준이 섞이는 문제를 종합점검에서 손으로
# 보정(manual_fix)하므로, 다시 실행하면 보정이 지워져 밸류천장이 크게 부풀려진다.
REFRESH = [
    ["scripts/macro_tracker.py"],
    ["scripts/market_flow_tracker.py"],
    ["scripts/ai_capex_tracker.py"],
    ["scripts/credit_stress.py", "--no-report"],
    ["scripts/credit_gauge.py"],
    ["scripts/m2_tracker.py"],
    ["scripts/kospi_ceiling.py"],
    ["scripts/four_act_study.py"],
    ["scripts/cycle_gauge.py"],
]

ACTS = {
    "1": ("1막 매집", "외국인이 사고 개인이 파는 구간입니다."),
    "2": ("2막 손바뀜", "외국인이 팔기 시작했지만 지수는 고점 근처입니다."),
    "3": ("3막 과열", "외국인 물량을 개인이 받고 있는 구간입니다."),
    "3!": ("3막 과열 경보", "고점 근처에서 외국인 매도와 개인 매수가 함께 평소보다 크게 나온 구간입니다."),
    "4-1": ("4-1 버티기", "지수는 빠졌지만 빚을 낸 개인의 투매는 아직 나오지 않은 구간입니다."),
    "4-2": ("4-2 투매", "신용잔고가 빠르게 줄며 1차 저점이 만들어지는 구간입니다."),
    "4-3": ("4-3 안도 반등", "1차 저점에서 6% 넘게 반등한 구간입니다."),
    "4-4": ("4-4 바닥 다지기", "1차 저점 부근으로 다시 내려와 2차 저점을 시험하는 구간입니다."),
    "4-E": ("4막 끝", "바닥 다지기의 최저점에서 10% 오른 구간입니다."),
    "R": ("회복", "4막이 끝나고 지수가 회복 중인 구간입니다."),
    "—": ("구분 없음", "뚜렷한 막으로 분류되지 않는 구간입니다."),
}
ACT_LIGHT = {"3!": "r", "4-1": "r", "3": "y", "4-2": "y", "4-3": "y", "4-4": "y", "4-E": "y"}
CLS_LIGHT = {"up": "g", "flat": "y", "down": "r"}
MAX_CEILING_MOVE = 0.10  # 하루 천장 변화가 이보다 크면 입력 오류로 보고 게시하지 않는다.
BANNED = ("분할", "매수존", "매도존", "신규", "회피", "권고", "자제", "사세요", "파세요")


def load(name):
    return json.loads((JUDO / "data" / name).read_text(encoding="utf-8"))


def clean(text):
    """이모지를 뗀 라벨. 괄호 뒤 해설은 조언이 섞이기 쉬워 버린다."""
    text = re.sub(r"[^\w\s·,./%+\-()가-힣]", "", text or "").strip()
    return re.sub(r"\s*\(.*$", "", text).strip()


def signed(v, unit):
    return f"{v:+.1f}{unit}"


def build():
    fa = load("four_act_study.json")
    now = fa["current"]
    ceil, gauge = load("kospi_ceiling.json"), load("cycle_gauge.json")
    macro, flow = load("macro_tracker.json"), load("market_flow.json")
    credit, capex = load("credit_stress.json"), load("ai_capex_tracker.json")
    regimes = {r["name"]: r for r in macro["regimes"]}
    snap = macro["snapshot"]

    code = now["막"]
    name, desc = ACTS.get(code, ACTS["—"])
    stat = next((t for t in fa["tab"] if t["code"] == code), None)
    act = {
        "code": code, "name": name, "desc": desc, "light": ACT_LIGHT.get(code, "g"),
        "fromPeak": now["고점대비"], "firstLow": now.get("일차저점"), "firstLowDate": now.get("일차저점일"),
        "fromFirstLow": now.get("일차대비"), "foreign5d": now["외국인5일"],
        "history": {"up250": stat["up250"], "episodes": stat["에피소드"]} if stat else None,
    }

    pct = ceil["blended_pct"]
    near = ceil["zone_pct"] >= 95
    k = flow["markets"]["코스피"]
    f5, f20 = (k["cum"]["외국인"][n] / 10000 for n in ("5", "20"))
    top = gauge["top"]
    gate = macro["macro_gate"]["sox"]
    hy, ig = credit["axes"]["hy"], credit["axes"]["ig"]
    wti = snap["wti"]
    items = [
        {"key": "ceiling", "title": "코스피 천장",
         "light": "r" if near else "y" if pct >= 80 else "g",
         "state": f"통합천장의 {pct:.0f}%",
         "detail": "수급천장은 지금 돈의 흐름, 밸류천장은 기업 이익, 통합천장은 둘을 합친 선입니다. 지수 전망이 아닙니다.",
         "levels": [
             {"label": "수급천장", "value": round(ceil["eff_ceiling"])},
             {"label": "통합천장", "value": round(ceil["ceiling_blended"])},
             {"label": "밸류천장", "value": round(ceil["ceiling_base"])},
         ],
         "asof": ceil["as_of"]},
        {"key": "flow", "title": "외국인 수급",
         "light": CLS_LIGHT.get(k["phase_cls"], "y"), "state": clean(k["phase"]),
         "detail": f"외국인 순매수 5일 {signed(f5, '조')}, 20일 {signed(f20, '조')}입니다.",
         "asof": flow["as_of"]},
        {"key": "handover", "title": "고점 손바뀜",
         "light": ("r" if top["handover_on"] else "g") if top["near"] else None,
         "state": ("경보 켜짐" if top["handover_on"] else "경보 없음") if top["near"] else "고점권 아님",
         "detail": ("고점 근처에서 외국인 물량이 개인에게 넘어가는지 봅니다."
                    if top["near"] else "코스피가 1년 최고가의 5% 안에 있을 때만 판단하는 항목입니다.")
                   + f" 마지막 경보는 {top['last_alarm']}입니다.",
         "asof": gauge["as_of"]},
        {"key": "chips", "title": "미국 반도체",
         "light": "g" if gate["on"] else "r",
         "state": f"100일선 {'위' if gate['on'] else '아래'} {gate['margin_pct']:+.1f}%",
         "detail": f"SOX 지수 {gate['last']:,.0f}, 최근 5일 {snap['sox']['trend_5d_pct']:+.1f}%입니다.",
         "asof": snap["sox"]["asof"]},
        {"key": "ai", "title": "AI 투자",
         "light": {0: "g", 1: "y"}.get(capex["verdict"]["bears"], "r"),
         "state": clean(capex["verdict"]["level"]),
         "detail": f"빅테크 설비투자, SOX, 반도체 외국인 수급 3축 중 {capex['verdict']['bears']}축이 둔화했습니다.",
         "asof": capex["generated"]},
        {"key": "rate", "title": "미국 금리",
         "light": CLS_LIGHT.get(regimes["금리"]["cls"], "y"),
         "state": f"10년물 {snap['us10y']['value']:.2f}%",
         "detail": f"최근 5일 {snap['us10y']['trend_5d_pct']:+.1f}% 움직였습니다.",
         "asof": macro["as_of"]},
        {"key": "fx", "title": "원달러 환율",
         "light": CLS_LIGHT.get(regimes["달러·환율"]["cls"], "y"),
         "state": f"{snap['usdkrw']['value']:,.0f}원",
         "detail": f"최근 5일 {snap['usdkrw']['trend_5d_pct']:+.1f}% 움직였습니다.",
         "asof": snap["usdkrw"]["asof"]},
        {"key": "credit", "title": "신용시장",
         "light": CLS_LIGHT.get(credit["verdict"]["cls"], "y"),
         "state": clean(credit["verdict"]["level"]),
         "detail": f"미국 회사채 스프레드는 하이일드 {hy['value']:.2f}%p, 투자등급 {ig['value']:.2f}%p입니다.",
         "asof": hy["as_of"]},
        {"key": "oil", "title": "국제 유가", "light": None,
         "state": f"WTI ${wti['value']:.1f}",
         "detail": f"최근 5일 {wti['trend_5d_pct']:+.1f}% 움직였습니다. 기준선이 없어 색을 표시하지 않습니다.",
         "asof": wti.get("asof", macro["as_of"])},
    ]
    lights = [i["light"] for i in items if i["light"]] + [act["light"]]
    return {
        "date": now["as_of"], "kospi": now["코스피"], "act": act, "items": items,
        "count": {c: lights.count(c) for c in "gyr"},
    }


def check_ceiling(data):
    days = sorted(p for p in OUT.glob("*.json") if p.stem < data["date"]) or sorted(OUT.glob("*.json"))
    if not days:
        return
    prev = json.loads(days[-1].read_text(encoding="utf-8"))
    old = {x["label"]: x["value"] for i in prev["items"] if i["key"] == "ceiling" for x in i.get("levels", [])}
    new = {x["label"]: x["value"] for i in data["items"] if i["key"] == "ceiling" for x in i["levels"]}
    jumps = [f"{k} {old[k]:,}→{v:,}" for k, v in new.items() if k in old and abs(v / old[k] - 1) > MAX_CEILING_MOVE]
    if jumps:
        sys.exit(f"[오류] 코스피 천장 급변, 게시 중단: {', '.join(jumps)}. kospi_earnings 보정 여부를 확인할 것")


def main():
    if "--refresh" in sys.argv:
        python = JUDO / ".venv" / "Scripts" / "python.exe"
        for step in REFRESH:
            print(f"[갱신] {step[0]}", flush=True)
            r = subprocess.run([str(python), "-X", "utf8", *step], cwd=JUDO, capture_output=True,
                               text=True, encoding="utf-8", errors="replace")
            if r.returncode:
                sys.exit(f"[오류] {step[0]} 실패\n{r.stderr[-800:]}")

    data = build()
    # 주말에 실행하면 일부 산출물의 as_of가 실행일이 되므로 거래 기준일로 맞춘다.
    for item in data["items"]:
        item["asof"] = min(str(item["asof"])[:10], data["date"])
    text = json.dumps(data, ensure_ascii=False, indent=1)
    found = [w for w in BANNED if w in text]
    if found:
        sys.exit(f"[오류] 공개 금지 표현 발견: {found}")
    check_ceiling(data)
    stale = [f"{i['title']} {i['asof']}" for i in data["items"] if str(i["asof"])[:10] < data["date"]]
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{data['date']}.json"
    path.write_text(text + "\n", encoding="utf-8", newline="\n")
    print(f"[완료] {path.relative_to(ROOT).as_posix()} · {data['act']['name']} · {data['count']}")
    # 4막 기간 차트 데이터(acts.json) — pandas가 필요해 주도섹터 venv로 실행
    r = subprocess.run([str(JUDO / ".venv" / "Scripts" / "python.exe"), "-X", "utf8", str(ROOT / "scripts" / "signal_acts_chart.py")],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    print(r.stdout.splitlines()[0] if r.returncode == 0 and r.stdout else f"[경고] acts.json 갱신 실패: {r.stderr[-300:]}")
    if stale:
        print("[참고] 기준일이 이전인 항목(해외 시장·발표 시차):", ", ".join(stale))


if __name__ == "__main__":
    main()
