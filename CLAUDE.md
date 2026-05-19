# 웹페이지자동화 워크스페이스 가이드

## 워크스페이스 구조
이 프로젝트는 genesis-report.com (한국 주식 AI 분석 웹사이트)의 콘텐츠 자동 생성 및 게시 시스템입니다.

---

## 명령어 가이드

### "제네시스 하자" (메인 명령어)

오늘 한국 날짜/요일을 확인하고, 아래 순서대로 각 워크플로우를 실행하여 보고서를 생성한다.
생성된 보고서는 **`https://github.com/pwman111-debuge/stockanalysis`** 의 해당 경로로 push한다.

```
월~목:            시황분석 → 단기유망종목(3개) → 종목분석(단기1순위) → 투자성과리뷰
금요일:           시황분석 → 단기유망종목(3개) → 중기유망종목(3개) → 종목분석(중기1순위) → 투자성과리뷰
매달 1일(금):     시황분석 → 단기유망종목(3개) → 중기유망종목(3개) → 장기유망종목(3개) → 종목분석(장기1순위) → 투자성과리뷰
매달 1일(금 제외): 시황분석 → 단기유망종목(3개) → 장기유망종목(3개) → 종목분석(장기1순위) → 투자성과리뷰
```

> 투자성과리뷰 실행 기준:
> - **매일(월~금)**: 단기 T-7 복기 (지난주 같은 요일 단기 picks ~7일 경과)
> - **매달 1일**: 추가로 중기 T-30 + 장기 T-90 복기 (해당 기간 리포트 없으면 자동 생략)

**종목분석(단기1순위) 규칙:**
- 단기유망종목 보고서의 **섹션 2 첫 번째 종목**(R:R 기준 1순위)을 자동으로 심층 분석
- 해당 종목코드를 `종목분석/.agents/workflows/analyze-stock.md` 에 전달하여 즉시 실행
- 결과물: `content/stock-reports/YYYY-MM-DD-[english-slug].mdx` 저장 후 push + SNS 포스팅

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
| "단기유망종목 제네시스하자" | 단기유망종목/.agents/workflows/제네시스-단기유망종목.md |
| "중기유망종목 제네시스하자" | 중기유망종목/.agents/workflows/제네시스-중기유망.md |
| "장기유망종목 제네시스하자" | 장기유망종목/.agents/workflows/genesis-long-term.md |
| "종목분석 제네시스하자" | 종목분석/.agents/workflows/analyze-stock.md |
| "마켓인사이트 제네시스하자" | 마켓인사이트/.agents/workflows/market-insight.md |
| "투자성과리뷰 제네시스하자" | 투자성과리뷰/agents/workflows/제네시스.md |

---

## 폴더 구조

```
웹페이지자동화/
├── 시황분석/          → 일일 시황 리포트 생성 (매일)
├── 단기유망종목/       → 단기 유망종목 3개 발굴 (매일)
├── 중기유망종목/       → 중기 유망종목 3개 발굴 (매주 금요일)
├── 장기유망종목/       → 장기 유망종목 3개 발굴 (매달 1일)
├── 종목분석/          → 개별 종목 심층 분석 (필요 시)
├── 마켓인사이트/       → 황원장-우팀장 논의 → 인사이트 리포트 (수시)
└── 투자성과리뷰/       → 과거 투자 결과 복기 및 피드백 리포트 생성 (필요 시)
```

**GitHub 저장소 (보고서):** `https://github.com/pwman111-debuge/stockanalysis`  
**GitHub 저장소 (코드):** `https://github.com/pwman111-debuge/webpage-automation`

---

## 코드·워크플로우 수정 시 Push 규칙

워크플로우(.md), 스킬(SKILL.md), 스크립트(.py, .js) 등 코드 파일을 수정·보완한 경우,
**`https://github.com/pwman111-debuge/webpage-automation`** 의 해당 경로로 push한다.

- 보고서 파일(MDX)과 코드 파일은 저장소를 분리하여 관리한다.
  - 보고서 → `pwman111-debuge/stockanalysis`
  - 코드/워크플로우 → `pwman111-debuge/webpage-automation`
- Push 완료 후 커밋 해시 및 경로 보고

---

## ⚠️ 폴더 구조 엄격 규칙 (반드시 준수)

### 각 워크플로우 폴더에 허용되는 파일/폴더

| 폴더 | 허용 항목 | 절대 금지 |
|------|----------|----------|
| `시황분석/` | `workflows/`, `.claude/` | content/, src/, public/, scripts/, skills/, package.json 등 Next.js 파일 |
| `단기유망종목/` | `.agents/workflows/`, `.agents/skills/`, `.claude/` | .agent/, scratch/, *.md 보고서, *.bat |
| `중기유망종목/` | `.agents/workflows/`, `.agents/skills/`, `.agents/rules/`, `.claude/` | content/, src/, public/, package.json 등 Next.js 파일 |
| `장기유망종목/` | `.agents/workflows/`, `.agents/rules/`, `.claude/`, `skills/` | genesis_output/, reports/ |
| `종목분석/` | `.agents/workflows/`, `.agents/rules/`, `.claude/`, `skills/` | *.mdx 보고서, *.html 테스트 파일 |
| `마켓인사이트/` | `.agents/workflows/`, `.claude/`, `archive/` | *.mdx 보고서, content/, src/, public/ |
| `투자성과리뷰/` | `agents/workflows/`, `agents/skills/` | content/, src/, public/, package.json 등 Next.js 파일 |

### 보고서 파일 저장 위치 (루트의 content/ 하위에만 저장)

| 종류 | 경로 |
|------|------|
| 시황분석 | `content/market-analysis/YYYYMMDD-*.mdx` |
| 단기유망종목 | `content/picks/YYYYMMDD-genesis-report.mdx` |
| 중기유망종목 | `content/picks/YYYYMMDD-genesis-mid-report.mdx` |
| 장기유망종목 | `content/picks/YYYYMMDD-genesis-long-report.mdx` |
| 종목분석 | `content/stock-reports/YYYY-MM-DD-[english-slug].mdx` (영문 소문자·하이픈, 예: `2026-04-25-sejin-heavy.mdx`) |
| 마켓인사이트 | `content/market-insight/YYYYMMDD-[english-slug].mdx` (영문 소문자·하이픈, 예: `20260425-fomc-rate-hold.mdx`) |

### 워크플로우 파일 보호 규칙

각 폴더의 `workflows/`, `.agents/workflows/`, `agents/workflows/`, `agents/skills/` 파일을 **다른 폴더의 것으로 절대 덮어쓰지 않는다.**
과거 폴더 간 워크플로우 혼선으로 시스템이 유실된 사고가 있었다. 항상 해당 폴더 내의 파일만 참조하고 수정한다.

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

