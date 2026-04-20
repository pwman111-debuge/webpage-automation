---
description: "장기 유망종목 보고서 GitHub 자동 Push 워크플로우"
---

# 🚀 장기 유망종목 보고서 자동 Push

보고서 생성 완료 즉시 자동 실행. 사용자 승인 불필요.

## 배포 정보
- **저장 경로:** `content/picks/YYYYMMDD-genesis-long-report.mdx`
- **저장소:** `https://github.com/pwman111-debuge/stockanalysis` → Cloudflare Pages 자동 배포

## 실행 절차

### Step 1. frontmatter 검증
필수 필드 누락 시 수정 후 진행:
- `title`, `date`, `term`(`"long"`), `summary`, `tags`, `status`(`"active"`)
- `ticker`, `market`, `currentPrice`, `targetPrice`, `stopLoss` (숫자, 없으면 0)

### Step 2. Git Push
```bash
git add content/picks/YYYYMMDD-genesis-long-report.mdx
git commit -m "feat: [YYYY-MM-DD] 장기 유망종목 보고서 업데이트"
git push origin main
```

### Step 3. Threads 자동 포스팅
```bash
python -X utf8 scripts/post_threads.py content/picks/YYYYMMDD-genesis-long-report.mdx
```
포스팅 완료 후 Post ID 및 Threads 링크 보고

### Step 4. 완료 보고
커밋 해시, 푸시된 파일 경로, Threads 포스팅 링크 보고
