"""
워크스페이스 구조 검증 스크립트
실행: python scripts/check-structure.py
"""
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 각 워크플로우 폴더에 절대 있으면 안 되는 패턴
FORBIDDEN = {
    "시황분석": ["content", "src", "public", "scripts", "skills",
                 "package.json", "next.config.ts", "tsconfig.json"],
    "단기유망종목": [".agent", "scratch", "push_report.bat"],
    "중기유망종목": ["content", "src", "public", "package.json",
                    "next.config.ts", "tsconfig.json", "gold.html"],
    "장기유망종목": ["genesis_output", "reports"],
    "종목분석": ["tv_test.html"],
    "마켓인사이트": ["content", "src", "public", "package.json",
                    "next.config.ts", "tsconfig.json"],
}

# 루트에 있으면 안 되는 파일 패턴
ROOT_FORBIDDEN_SUFFIXES = [
    "_report.md", "_report.mdx", "test-", ".html"
]
ROOT_FORBIDDEN_NAMES = [
    "gold.html", "genesis_report_20260313.md"
]

# 보고서가 저장되어야 하는 올바른 위치
CORRECT_REPORT_PATHS = {
    "단기": "content/picks/YYYYMMDD-genesis-report.mdx",
    "중기": "content/picks/YYYYMMDD-genesis-mid-report.mdx",
    "장기": "content/picks/YYYYMMDD-genesis-long-report.mdx",
    "종목분석": "content/stock-reports/YYYY-MM-DD-[종목명].mdx",
    "마켓인사이트": "content/market-insight/YYYYMMDD-[slug].mdx",
}

errors = []
warnings = []

# 1. 워크플로우 폴더 내 금지 항목 검사
for folder, forbidden_list in FORBIDDEN.items():
    folder_path = os.path.join(BASE, folder)
    if not os.path.exists(folder_path):
        warnings.append(f"[없음] {folder}/ 폴더가 존재하지 않습니다.")
        continue
    for item in os.listdir(folder_path):
        if item in forbidden_list:
            errors.append(f"[오류] {folder}/{item}  - 이 폴더에 있으면 안 되는 항목입니다.")

# 2. 루트 레벨 잡파일 검사
root_items = os.listdir(BASE)
for item in root_items:
    if item in ROOT_FORBIDDEN_NAMES:
        errors.append(f"[오류] 루트/{item}  - 루트에 있으면 안 되는 파일입니다.")
    for suffix in ROOT_FORBIDDEN_SUFFIXES:
        if item.startswith("test-") or (item.endswith(".html") and item != "gold.html"):
            if item not in ["check-headers.mjs"]:
                warnings.append(f"[주의] 루트/{item}  - 테스트/임시 파일로 의심됩니다.")
            break

# 3. 워크플로우 폴더 루트에 .mdx/.md 보고서 파일 검사
for folder in FORBIDDEN.keys():
    folder_path = os.path.join(BASE, folder)
    if not os.path.exists(folder_path):
        continue
    for item in os.listdir(folder_path):
        if item.endswith(".mdx") or (item.endswith(".md") and item not in ["README.md"]):
            errors.append(f"[오류] {folder}/{item}  - 보고서는 content/ 하위에만 저장해야 합니다.")

# 결과 출력
print("=" * 50)
print("웹페이지자동화 구조 검증 결과")
print("=" * 50)

if not errors and not warnings:
    print("[OK] 이상 없음. 구조가 올바릅니다.")
else:
    if errors:
        print(f"\n[오류] {len(errors)}건:")
        for e in errors:
            print(f"  {e}")
    if warnings:
        print(f"\n[주의] {len(warnings)}건:")
        for w in warnings:
            print(f"  {w}")
    print(f"\n총 {len(errors)}개 오류, {len(warnings)}개 주의사항")

print("=" * 50)
