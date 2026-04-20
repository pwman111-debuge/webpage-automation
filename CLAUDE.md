# 웹페이지자동화 워크스페이스 가이드

## 워크스페이스 구조
이 프로젝트는 genesis-report.com (한국 주식 AI 분석 웹사이트)의 콘텐츠 자동 생성 및 게시 시스템입니다.

---

## 명령어 가이드

### "제네시스 하자" (메인 명령어)

오늘 한국 날짜/요일을 확인하고, 아래 순서대로 각 워크플로우를 실행하여 보고서를 생성한다.
생성된 보고서는 **`https://github.com/pwman111-debuge/stockanalysis`** 의 해당 경로로 push한다.

```
월~목:            시황분석 → 단기유망종목(3개)
금요일:           시황분석 → 단기유망종목(3개) → 중기유망종목(3개)
매달 1일(금):     시황분석 → 단기유망종목(3개) → 중기유망종목(3개) → 장기유망종목(3개)
매달 1일(금 제외): 시황분석 → 단기유망종목(3개) → 장기유망종목(3개)
```

**Push 규칙:**
- 각 워크플로우 보고서 생성 완료 즉시 자동으로 GitHub push 실행
- Push 완료 후 커밋 해시 및 경로 보고

> 전체 실행 시 각 워크플로우는 위 순서대로 자동 호출된다.
> 개별 실행이 필요할 때는 아래 개별 명령어를 사용한다.

---

### 개별 워크플로우 직접 실행 (필요 시)

| 명령어 | 실행 워크플로우 |
|--------|--------------|
| "시황분석 제네시스하자" | 시황분석/workflows/제네시스.md |
| "단기유망종목 제네시스하자" | 단기유망종목/.agent/workflows/제네시스-단기유망종목.md |
| "중기유망종목 제네시스하자" | 중기유망종목/.agents/workflows/제네시스-중기유망.md |
| "장기유망종목 제네시스하자" | 장기유망종목/.agents/workflows/genesis-long-term.md |
| "종목분석 제네시스하자" | 종목분석/.agents/workflows/analyze-stock.md |

---

## 폴더 구조

```
웹페이지자동화/
├── 시황분석/          → 일일 시황 리포트 생성 (매일)
├── 단기유망종목/       → 단기 유망종목 3개 발굴 (매일)
├── 중기유망종목/       → 중기 유망종목 3개 발굴 (매주 금요일)
├── 장기유망종목/       → 장기 유망종목 3개 발굴 (매달 1일)
└── 종목분석/          → 개별 종목 심층 분석 (필요 시)
```

**GitHub 저장소:** `https://github.com/pwman111-debuge/stockanalysis`

---

## ⚠️ 폴더 구조 엄격 규칙 (반드시 준수)

### 각 워크플로우 폴더에 허용되는 파일/폴더

| 폴더 | 허용 항목 | 절대 금지 |
|------|----------|----------|
| `시황분석/` | `workflows/`, `.claude/` | content/, src/, public/, scripts/, skills/, package.json 등 Next.js 파일 |
| `단기유망종목/` | `.agent/workflows/`, `.agent/skills/`, `.claude/` | .agents/, scratch/, *.md 보고서, *.bat |
| `중기유망종목/` | `.agents/workflows/`, `.agents/skills/`, `.agents/rules/`, `.claude/` | content/, src/, public/, package.json 등 Next.js 파일 |
| `장기유망종목/` | `.agents/workflows/`, `.agents/rules/`, `.claude/`, `skills/` | genesis_output/, reports/ |
| `종목분석/` | `.agents/workflows/`, `.agents/rules/`, `.claude/`, `skills/` | *.mdx 보고서, *.html 테스트 파일 |

### 보고서 파일 저장 위치 (루트의 content/ 하위에만 저장)

| 종류 | 경로 |
|------|------|
| 시황분석 | `content/market-analysis/YYYYMMDD-*.mdx` |
| 단기유망종목 | `content/picks/YYYYMMDD-genesis-report.mdx` |
| 중기유망종목 | `content/picks/YYYYMMDD-genesis-mid-report.mdx` |
| 장기유망종목 | `content/picks/YYYYMMDD-genesis-long-report.mdx` |
| 종목분석 | `content/stock-reports/YYYY-MM-DD-[종목명].mdx` |

### 절대 하지 말 것

- 워크플로우 폴더(시황분석/, 단기유망종목/ 등) 안에 보고서 파일 저장 금지
- 루트 레벨에 임시 보고서(.md, .mdx), 테스트 파일(.html, test-*.js) 생성 금지
- 워크플로우 폴더 안에 Next.js 관련 파일(package.json, src/, content/ 등) 생성 금지
- 작업 완료 후 scratch/, genesis_output/ 등 임시 산출물 폴더 정리 필수

### 구조 자동 검증 규칙

**다음 상황에서 반드시 `python -X utf8 scripts/check-structure.py` 를 자동 실행한다:**
- 파일/폴더를 새로 생성했을 때
- 보고서를 저장했을 때
- 워크플로우 실행이 완료됐을 때
- 세션 시작 시 첫 작업 전

검증 결과 오류가 있으면 즉시 사용자에게 보고하고 수정한다.

---

