---
description: 황원장-우팀장 논의 내용을 마켓인사이트 리포트로 변환 후 GitHub Push + SNS 자동 포스팅
---

# 🧠 마켓인사이트 워크플로우

사용자가 **"제네시스 하자"** 또는 논의 내용과 함께 이 워크플로우를 실행하면,  
황원장-우팀장 간의 투자 논의를 전문 리포트로 변환하고 자동으로 배포한다.

---

## 📥 Step 1. 입력 소스 확인

### 1-1. 마켓인사이트 폴더 내 파일 탐색

```bash
ls 마켓인사이트/
```

- `.txt`, `.md` 파일이 있으면 해당 파일을 읽어 논의 내용으로 사용한다.
- 파일이 없으면 → **사용자에게 논의 내용을 직접 붙여넣기 요청**한다.

### 1-2. 입력 전처리

읽어온 논의 내용에서 다음을 파악한다:

| 항목 | 내용 |
|------|------|
| 주제 | 대화의 핵심 주제 (예: FOMC 금리 결정, 반도체 섹터 전망 등) |
| 날짜 | 논의가 이루어진 날짜 (없으면 오늘 날짜 사용) |
| 카테고리 | `fomc` / `macro` / `special` / `trend` 중 자동 판별 |
| 핵심 결론 | 황원장·우팀장이 도달한 주요 결론 및 투자 시사점 |

**카테고리 판별 기준:**
- `fomc` — 연준, 금리, FOMC 관련 논의
- `macro` — 환율, 국채, CPI, 경기침체, 글로벌 경제 등 거시경제
- `special` — 특정 이벤트·정책 발표·지정학적 이슈
- `trend` — 섹터 트렌드, 테마, 산업 전환 이슈

---

## 📝 Step 2. 리포트 MDX 생성

### 2-1. 파일명 결정

```
YYYYMMDD-{영문-slug}.mdx
```

- 날짜: 논의 날짜 또는 오늘 날짜 (YYYYMMDD 8자리)
- slug: 주제를 영문 소문자·하이픈으로 변환 (예: `fomc-rate-hold-april`, `semiconductor-supply-trend`)
- 최종 예시: `20260425-fomc-rate-hold-april.mdx`

### 2-2. Frontmatter 작성

아래 스키마를 **반드시 준수**한다 (contentlayer `MarketInsight` 타입):

```yaml
---
title: "제목 (한국어, 핵심 메시지 중심, 40자 이내)"
date: "YYYY-MM-DD"
category: "fomc | macro | special | trend"
tags: ["태그1", "태그2", "태그3"]
summary: "한 문단 요약 (SNS 포스팅 텍스트로 사용됨, 150자 이내, 핵심 인사이트 포함)"
thumbnail: "/og-image.png"
---
```

**tags 예시:**
- fomc → `["FOMC", "금리", "연준", "달러"]`
- macro → `["거시경제", "환율", "인플레이션"]`
- trend → `["반도체", "AI", "섹터분석"]`

### 2-3. 본문 구조 (아래 형식을 따른다)

```mdx
## 오늘의 논의 배경

[논의가 시작된 맥락·계기를 2~3문장으로 서술]

---

## 황원장 × 우팀장 핵심 논의

### 📌 [논의 포인트 1 제목]

> **황원장:** [황원장 발언 요약 또는 직접 인용]

> **우팀장:** [우팀장 발언 요약 또는 직접 인용]

**✅ 결론:** [이 포인트의 결론 1~2문장]

---

### 📌 [논의 포인트 2 제목]

> **황원장:** ...

> **우팀장:** ...

**✅ 결론:** ...

---

### 📌 [논의 포인트 3 제목 — 필요 시]

...

---

## 투자 시사점

| 구분 | 내용 |
|------|------|
| 단기 (1~4주) | [단기 영향 및 대응] |
| 중기 (1~3개월) | [중기 영향 및 전략] |
| 주목 섹터/종목 | [논의에서 언급된 섹터 또는 종목] |

---

## 리스크 요인

- [리스크 1]
- [리스크 2]
- [리스크 3]

---

## 제네시스 뷰

> [황원장·우팀장의 논의를 종합한 최종 시장 전망 및 포지셔닝 제언. 2~4문장. 단호하고 명확하게.]
```

### 2-4. 작성 원칙

- 논의 내용을 **충실히 반영**하되, 구조화·정제하여 읽기 쉽게 만든다.
- 발언이 모호하면 **맥락에서 추론**하되, 불확실한 경우 "논의 중"으로 표기한다.
- 투자 시사점은 **실용적이고 구체적**으로 작성한다.
- 전체 분량: **800~1500자** 목표 (너무 짧거나 길지 않게).

---

## 💾 Step 3. 파일 저장

```bash
# 저장 경로 (반드시 이 경로에 저장)
content/market-insight/YYYYMMDD-{slug}.mdx
```

저장 후 구조 검증 실행:

```bash
python -X utf8 scripts/check-structure.py
```

오류 발생 시 즉시 수정 후 재검증.

---

## 🚀 Step 4. GitHub Push

> **[대상 저장소]** `https://github.com/pwman111-debuge/stockanalysis` (remote name: `origin`)  
> **[저장 경로]** 해당 저장소의 `content/market-insight/YYYYMMDD-{slug}.mdx`

```bash
python -X utf8 scripts/push_report.py content/market-insight/YYYYMMDD-{slug}.mdx "feat: 마켓인사이트 - {제목} ({YYYY-MM-DD})"
```

- **저장소:** `https://github.com/pwman111-debuge/stockanalysis` → Cloudflare Pages 자동 배포
- Push 완료 후 커밋 해시 및 파일 경로 보고.

---

## 📣 Step 5. SNS 자동 포스팅

### 5-1. Threads 포스팅 (먼저 실행)

```bash
python -X utf8 scripts/post_threads.py content/market-insight/YYYYMMDD-{slug}.mdx
```

Post ID 및 Threads 링크 기록.

### 5-2. LinkedIn 포스팅

```bash
python -X utf8 scripts/post_linkedin.py content/market-insight/YYYYMMDD-{slug}.mdx
```

Post URN 기록.

### 5-3. 포스팅 실패 시 처리

- **토큰 만료**: `[오류] LINKEDIN_ACCESS_TOKEN` → 사용자에게 재발급 안내
- **Threads 429**: 5초 대기 후 1회 재시도, 재실패 시 사용자 보고
- **기타 오류**: 오류 메시지 전체를 사용자에게 전달

---

## ✅ 완료 보고 형식

```
✅ 마켓인사이트 리포트 완료!

📄 파일: content/market-insight/YYYYMMDD-{slug}.mdx
🔗 사이트: https://genesis-report.com/insight/YYYYMMDD-{slug}
📤 GitHub: {커밋 해시} — origin/main push 완료
🧵 Threads: https://www.threads.net/post/{post_id}
💼 LinkedIn: {post_urn}
```

---

## 🗂️ 논의 파일 정리 (선택)

보고서 생성 완료 후, 마켓인사이트 폴더의 원본 논의 파일(.txt/.md)은  
**사용자 확인 후** 삭제하거나 `마켓인사이트/archive/` 로 이동한다.  
(자동 삭제 금지 — 반드시 사용자 확인 요청)
