---
description: "투자성과 리뷰 보고서 GitHub 자동 Push 워크플로우"
---

# 🚀 투자성과 리뷰 보고서 자동 Push

보고서 생성 완료 즉시 자동 실행. 사용자 승인 불필요.

## 배포 정보
- **저장 경로:** `content/picks-feedback/YYYY-MM-DD-performance-review.mdx`
- **저장소:** `https://github.com/pwman111-debuge/stockanalysis` → Cloudflare Pages 자동 배포
- **배포 URL:** `https://genesis-report.com/picks/feedback`

## 실행 절차

### Step 1. frontmatter 검증
필수 필드 누락 시 수정 후 진행:
- `title`, `date`, `summary`, `tags`, `thumbnail`
- 날짜 형식: `date: "YYYY-MM-DD"` (따옴표 필수)

### Step 2. Git Push (stockanalysis 레포로 자동 push)
```bash
python -X utf8 scripts/push_report.py content/picks-feedback/YYYY-MM-DD-performance-review.mdx "feat: YYYY-MM-DD 투자성과 리뷰 리포트"
```

### Step 3. Threads 자동 포스팅
```bash
python -X utf8 scripts/post_threads.py content/picks-feedback/YYYY-MM-DD-performance-review.mdx
```
포스팅 완료 후 Post ID 및 Threads 링크 보고

### Step 4. LinkedIn 자동 포스팅
```bash
python -X utf8 scripts/post_linkedin.py content/picks-feedback/YYYY-MM-DD-performance-review.mdx
```
포스팅 완료 후 Post URN 보고

### Step 5. 완료 보고
커밋 해시, 푸시된 파일 경로, Threads 포스팅 링크, LinkedIn Post URN 보고
