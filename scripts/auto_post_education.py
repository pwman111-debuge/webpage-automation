"""
투자 교육 콘텐츠 자동 SNS 포스팅 (Threads + LinkedIn)

content/education/ 의 글 중 '아직 올리지 않은 글'만 골라 Threads·LinkedIn에 포스팅한다.
이미 올린 글은 상태파일(scripts/.posted_education.json)에 플랫폼별로 기록되어 재게시되지 않는다.
(예: LinkedIn만 실패하면 다음 실행 때 LinkedIn만 재시도)

사용법:
  python -X utf8 scripts/auto_post_education.py              # 새 글을 양쪽에 게시
  python -X utf8 scripts/auto_post_education.py --platform threads   # Threads만
  python -X utf8 scripts/auto_post_education.py --platform linkedin  # LinkedIn만
  python -X utf8 scripts/auto_post_education.py --seed       # 게시하지 않고 현재 글 전부 '완료'로 표시(초기화)
  python -X utf8 scripts/auto_post_education.py --dry-run    # 대상만 출력, 실제 게시 X

교육글 작성 직후 이 스크립트를 실행하면 신규 글이 자동으로 SNS에 배포된다.
"""
import os
import sys
import json
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EDU_DIR = os.path.join(ROOT, "content", "education")
STATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".posted_education.json")
POST_THREADS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "post_threads.py")
POST_LINKEDIN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "post_linkedin.py")

PLATFORMS = ("threads", "linkedin")
SCRIPT_OF = {"threads": POST_THREADS, "linkedin": POST_LINKEDIN}
LABEL_OF = {"threads": "Threads", "linkedin": "LinkedIn"}


def load_state():
    if not os.path.exists(STATE_PATH):
        return {}
    try:
        with open(STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        print("[주의] 상태파일을 읽지 못해 빈 상태로 시작합니다.")
        return {}


def save_state(state):
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2, sort_keys=True)


def list_education_slugs():
    if not os.path.isdir(EDU_DIR):
        return []
    return sorted(
        os.path.splitext(f)[0]
        for f in os.listdir(EDU_DIR)
        if f.endswith(".mdx")
    )


def entry_for(state, slug):
    """slug 상태 항목 보장 (없으면 생성)"""
    e = state.setdefault(slug, {})
    for p in PLATFORMS:
        e.setdefault(p, False)
    return e


def post_one(platform, slug):
    """해당 플랫폼 포스팅 스크립트를 서브프로세스로 실행. 성공 시 True."""
    mdx_path = os.path.join("content", "education", slug + ".mdx")
    cmd = [sys.executable, "-X", "utf8", SCRIPT_OF[platform], mdx_path]
    print(f"  → {LABEL_OF[platform]} 게시: {mdx_path}")
    result = subprocess.run(cmd, cwd=ROOT)
    return result.returncode == 0


def main():
    args = sys.argv[1:]
    platform_arg = "both"
    seed = "--seed" in args
    dry_run = "--dry-run" in args
    if "--platform" in args:
        idx = args.index("--platform")
        if idx + 1 < len(args):
            platform_arg = args[idx + 1]

    targets = (PLATFORMS if platform_arg == "both" else (platform_arg,))
    for p in targets:
        if p not in PLATFORMS:
            print(f"[오류] 알 수 없는 플랫폼: {p} (threads | linkedin | both)")
            sys.exit(1)

    state = load_state()
    slugs = list_education_slugs()
    if not slugs:
        print("[정보] content/education 에 글이 없습니다.")
        return

    # --seed: 게시 없이 현재 글을 전부 완료 표시 (최초 초기화용)
    if seed:
        for slug in slugs:
            e = entry_for(state, slug)
            for p in PLATFORMS:
                e[p] = True
        save_state(state)
        print(f"[완료] 현재 교육글 {len(slugs)}편을 '게시 완료'로 초기화했습니다. 이후 신규 글만 자동 게시됩니다.")
        return

    # 게시 대상 산출: 타깃 플랫폼 중 아직 안 올린 (slug, platform)
    pending = []
    for slug in slugs:
        e = entry_for(state, slug)
        for p in targets:
            if not e[p]:
                pending.append((slug, p))

    if not pending:
        print("[정보] 새로 게시할 교육글이 없습니다. (모두 게시 완료)")
        save_state(state)  # 새로 발견된 slug 항목 저장
        return

    print(f"[대상] {len(pending)}건 게시 예정:")
    for slug, p in pending:
        print(f"  - {slug} → {LABEL_OF[p]}")

    if dry_run:
        print("[dry-run] 실제 게시는 하지 않았습니다.")
        save_state(state)
        return

    ok, fail = 0, 0
    for slug, p in pending:
        try:
            if post_one(p, slug):
                entry_for(state, slug)[p] = True
                save_state(state)  # 매 건 즉시 저장 (중간 실패해도 진행분 보존)
                ok += 1
            else:
                print(f"  [실패] {slug} → {LABEL_OF[p]} (다음 실행 때 재시도)")
                fail += 1
        except Exception as ex:
            print(f"  [오류] {slug} → {LABEL_OF[p]}: {ex}")
            fail += 1

    print(f"\n[요약] 성공 {ok}건, 실패 {fail}건. 상태 저장: {STATE_PATH}")
    if fail:
        sys.exit(1)


if __name__ == "__main__":
    main()
