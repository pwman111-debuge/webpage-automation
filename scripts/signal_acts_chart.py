# -*- coding: utf-8 -*-
r"""/signal 4막 기간 차트용 데이터 — 코스피 종가 + 막별 구간.

사용법 (pandas 필요 → 주도섹터 venv):
  ../주도섹터/.venv/Scripts/python.exe -X utf8 scripts/signal_acts_chart.py

입력: 주도섹터/data/four_act_daily.parquet (일별 막 판정)
산출: public/charts/signal/acts.json  (파일명이 날짜가 아니라 /signal 기록 목록에는 섞이지 않는다)

일별 판정은 3막·경보·구분없음이 하루씩 깜빡이므로 보기 좋게 정리한다.
  1) 3!는 3으로 합친다.  2) 10거래일 미만 조각은 앞 구간에 흡수한다(첫 구간이면 뒤 구간).
  3) 4막(4-1~4-4)은 한 번 시작되면 하위 단계 순서대로 이어진다 → 짧은 4-1 깜빡임도 위 규칙으로 흡수된다.
"""
import json
import pathlib
import sys

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
JUDO = pathlib.Path.home() / "OneDrive" / "바탕 화면" / "주도섹터"
OUT = ROOT / "public" / "charts" / "signal" / "acts.json"
START = "2025-07-04"   # 이번 사이클 1막 매집 시작일부터
MIN_RUN = 10


def segments(codes):
    runs = []   # [code, start_i, end_i]
    for i, c in enumerate(codes):
        if runs and runs[-1][0] == c:
            runs[-1][2] = i
        else:
            runs.append([c, i, i])
    # 짧은 조각 흡수 (가장 짧은 것부터 반복)
    while len(runs) > 1:
        short = [k for k, r in enumerate(runs) if r[2] - r[1] + 1 < MIN_RUN]
        if not short:
            break
        k = min(short, key=lambda j: runs[j][2] - runs[j][1])
        if k > 0:
            runs[k - 1][2] = runs[k][2]
        else:
            runs[1][1] = runs[0][1]
        del runs[k]
        merged = [runs[0]]
        for r in runs[1:]:
            if r[0] == merged[-1][0]:
                merged[-1][2] = r[2]
            else:
                merged.append(r)
        runs = merged
    return runs


def main():
    d = pd.read_parquet(JUDO / "data" / "four_act_daily.parquet").loc[START:]
    codes = ["3" if a == "3!" else a for a in d["act"]]
    runs = segments(codes)
    dates = [t.strftime("%Y-%m-%d") for t in d.index]
    # 1차 저점(4-2 투매에서 만들어진 저점)·2차 저점(4-4 바닥 다지기 안의 최저 종가)
    study = json.loads((JUDO / "data" / "four_act_study.json").read_text(encoding="utf-8"))["current"]
    lows = {}
    fl = study.get("일차저점일")
    if fl and fl in dates:
        lows["first"] = {"date": fl, "value": round(float(d["px"].loc[fl]), 1)}
        s44 = [r for r in runs if r[0] == "4-4" and dates[r[1]] > fl]
        if s44:
            seg = d["px"].iloc[s44[-1][1]:]
            lows["second"] = {"date": seg.idxmin().strftime("%Y-%m-%d"), "value": round(float(seg.min()), 1),
                              "confirmed": runs[-1][0] != "4-4"}
    out = {
        "asof": dates[-1],
        "lows": lows,
        "dates": dates,
        "close": [round(float(v), 1) for v in d["px"]],
        "segments": [
            {"code": c, "start": dates[a], "end": dates[b], "days": b - a + 1,
             "calDays": (pd.Timestamp(dates[b]) - pd.Timestamp(dates[a])).days + 1}
            for c, a, b in runs
        ],
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8", newline="\n")
    print(f"[완료] {OUT.relative_to(ROOT).as_posix()} · 구간 {len(runs)}개")
    for s in out["segments"]:
        print(f"  {s['code']:>3} {s['start']} ~ {s['end']} ({s['days']}거래일)")


if __name__ == "__main__":
    sys.exit(main())
