"""네이버 블로그 자동 발행기 (Playwright)

naver_export.py가 만든 naver_out/*.html (요약본)을 네이버 블로그에 자동 발행한다.

설계 원칙
─────────
1. 비밀번호 하드코딩 금지 → scripts/.env.naver (gitignore됨)에서 로드.
2. 세션 영속화 → scripts/.naver_profile/ 에 로그인 쿠키 보존. 최초 1회만 로그인,
   이후 실행은 로그인 단계를 건너뛴다(네이버 봇 탐지·캡차 노출 최소화).
3. 로그인은 '클립보드 붙여넣기' 방식 → 키 입력 탐지(키로깅 방지) 우회.
4. 캡차/기기등록 등 예외는 headed 모드에서 사람이 개입할 수 있게 일시정지.

모드
─────
  (기본) assist   : 자동 로그인 + 글쓰기 페이지 오픈 + 제목/본문을 클립보드에 적재.
                    → 에디터에 직접 붙여넣고(Ctrl+V) 발행은 사람이 클릭. (가장 안전·확실)
  --publish       : 제목/본문/카테고리/발행까지 전 과정 자동 시도(베스트에포트).
  --draft         : 발행 대신 임시저장까지만.

사용법
──────
  # 의존성(최초 1회): pip install playwright python-dotenv && playwright install chromium
  python -X utf8 scripts/naver_blog_publisher.py                      # 오늘자 4건, assist 모드
  python -X utf8 scripts/naver_blog_publisher.py --publish            # 전자동 발행 시도
  python -X utf8 scripts/naver_blog_publisher.py naver_out/2026-06-18-samsung-electronics.html
  python -X utf8 scripts/naver_blog_publisher.py --date 20260618 --publish

주의: 네이버 SmartEditor ONE은 iframe·버전 변동이 잦다. --publish 첫 실행 시
      naver_out/_shots/ 의 단계별 스크린샷으로 셀렉터를 점검하라. 실패해도 브라우저는
      열린 채로 두어 수동 보정이 가능하다.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys
import time
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("[오류] beautifulsoup4 필요: pip install beautifulsoup4")
    raise SystemExit(1)

try:
    from playwright.sync_api import TimeoutError as PWTimeout
    from playwright.sync_api import sync_playwright
except ImportError:
    print("[오류] playwright 필요: pip install playwright && playwright install chromium")
    raise SystemExit(1)

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
OUT_DIR = ROOT / "naver_out"
SHOT_DIR = OUT_DIR / "_shots"
PROFILE_DIR = SCRIPTS / ".naver_profile"
ENV_FILE = SCRIPTS / ".env.naver"
MOD = "Meta" if sys.platform == "darwin" else "Control"


# ── 자격증명 로드 ──────────────────────────────────────────
def load_creds() -> tuple[str, str]:
    nid = os.environ.get("NAVER_ID")
    npw = os.environ.get("NAVER_PW")
    if (not nid or not npw) and ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k, v = k.strip(), v.strip()
            if k == "NAVER_ID" and not nid:
                nid = v
            elif k == "NAVER_PW" and not npw:
                npw = v
    if not nid or not npw:
        print(f"[오류] 자격증명 없음. {ENV_FILE} 에 NAVER_ID / NAVER_PW 를 넣거나 환경변수로 설정하라.")
        raise SystemExit(1)
    return nid, npw


# ── 발행할 HTML 파일 선택 ──────────────────────────────────
def pick_files(args) -> list[Path]:
    if args.files:
        return [Path(f) if Path(f).is_absolute() else (ROOT / f) for f in args.files]
    date_str = args.date or _dt.date.today().strftime("%Y%m%d")
    # naver_out 파일명에는 2026-06-18 또는 20260618 형태가 섞여 있음 → 둘 다 매칭
    dashed = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
    hits = [
        p for p in sorted(OUT_DIR.glob("*.html"))
        if date_str in p.name or dashed in p.name
    ]
    if not hits:
        print(f"[경고] {OUT_DIR} 에서 날짜({date_str}/{dashed}) 매칭 HTML 없음.")
    return hits


# ── 내보낸 HTML에서 제목·카테고리·본문 추출 ────────────────
def parse_export(html_path: Path) -> dict:
    soup = BeautifulSoup(html_path.read_text(encoding="utf-8"), "html.parser")
    # 제목: <div ...><b>제목:</b> TITLE</div>
    title = ""
    for div in soup.find_all("div"):
        b = div.find("b")
        if b and b.get_text(strip=True).startswith("제목"):
            title = div.get_text(" ", strip=True).split(":", 1)[-1].strip()
            break
    if not title:
        title = (soup.title.get_text(strip=True) if soup.title else html_path.stem)
    # 카테고리: <div class="guide"> ... 추천 카테고리: CATEGORY</div>
    category = ""
    guide = soup.find("div", class_="guide")
    if guide:
        gt = guide.get_text(" ", strip=True)
        if "추천 카테고리:" in gt:
            category = gt.split("추천 카테고리:", 1)[1].strip().split("·")[0].strip()
    # 본문: #naver-body (안내·제목 박스는 그 바깥이라 자동 제외됨)
    body_el = soup.find(id="naver-body")
    body_html = body_el.decode_contents() if body_el else ""
    body_text = body_el.get_text("\n", strip=True) if body_el else ""
    return {"title": title, "category": category, "body_html": body_html, "body_text": body_text}


# ── 클립보드 헬퍼 ──────────────────────────────────────────
def clip_write_text(page, text: str):
    page.evaluate("(t) => navigator.clipboard.writeText(t)", text)


def clip_write_html(page, html: str, text: str):
    page.evaluate(
        """async ([html, text]) => {
            const item = new ClipboardItem({
                'text/html': new Blob([html], {type: 'text/html'}),
                'text/plain': new Blob([text], {type: 'text/plain'}),
            });
            await navigator.clipboard.write([item]);
        }""",
        [html, text],
    )


def paste_text(page, selector, text, frame=None):
    target = frame or page
    target.click(selector)
    clip_write_text(page, text)
    page.keyboard.press(f"{MOD}+V")


# ── 로그인 ─────────────────────────────────────────────────
def already_logged_in(page) -> bool:
    try:
        page.goto("https://www.naver.com", wait_until="domcontentloaded", timeout=20000)
        # 로그인 상태면 '로그아웃' 또는 내 정보 영역이 존재
        return page.locator("a[href*='nid.naver.com/nidlogin.logout'], .MyView-module__btn_logout___").count() > 0
    except PWTimeout:
        return False


def do_login(page, nid: str, npw: str):
    print("[로그인] 네이버 로그인 시도...")
    page.goto("https://nid.naver.com/nidlogin.login?mode=form", wait_until="domcontentloaded")
    page.wait_for_selector("#id", timeout=15000)
    # 클립보드 붙여넣기 방식 (키로깅 탐지 우회)
    paste_text(page, "#id", nid)
    time.sleep(0.4)
    paste_text(page, "#pw", npw)
    time.sleep(0.4)
    page.click("#log\\.login, button[type='submit']")
    time.sleep(2.5)

    # 캡차/추가인증 감지 → 사람이 개입
    url = page.url
    if "nidlogin" in url or page.locator("#captcha, .captcha").count() > 0:
        if page.locator("#captcha, .captcha, #frmNIDLogin").count() > 0 and "blog" not in url:
            print("\n[개입필요] 캡차/추가 인증으로 보입니다. 열린 브라우저에서 직접 해결한 뒤 Enter를 누르세요.")
            try:
                input("  → 로그인 완료 후 Enter: ")
            except EOFError:
                time.sleep(20)

    # 기기 등록 페이지 → '등록안함'
    for sel in ["#new\\.dontsave", "a:has-text('등록안함')", "button:has-text('등록안함')"]:
        try:
            if page.locator(sel).count() > 0:
                page.click(sel, timeout=3000)
                break
        except Exception:
            pass
    time.sleep(1.5)
    print("[로그인] 단계 완료(세션 저장됨).")


# ── 글쓰기 에디터 진입 + 팝업 정리 ─────────────────────────
def open_writer(page, nid: str):
    page.goto(f"https://blog.naver.com/{nid}?Redirect=Write&", wait_until="domcontentloaded")
    time.sleep(3)
    frame = None
    for _ in range(20):
        frame = page.frame(name="mainFrame")
        if frame:
            break
        time.sleep(0.5)
    if not frame:
        print("[경고] mainFrame(에디터 iframe)을 찾지 못함. 페이지 구조 변경 가능성.")
        return None
    # '작성 중인 글 불러오기' 팝업 → 취소
    for sel in ["button:has-text('취소')", ".se-popup-button-cancel", "button.se-popup-button-cancel"]:
        try:
            if frame.locator(sel).count() > 0:
                frame.click(sel, timeout=2500)
                break
        except Exception:
            pass
    # 도움말 패널 닫기
    for sel in [".se-help-panel-close-button", "button.se-help-panel-close-button", ".se_help_close"]:
        try:
            if frame.locator(sel).count() > 0:
                frame.click(sel, timeout=2000)
        except Exception:
            pass
    return frame


# ── 전자동 발행(베스트에포트) ──────────────────────────────
def autofill_and_publish(page, frame, data: dict, do_publish: bool, shot_prefix: str):
    def shot(tag):
        try:
            SHOT_DIR.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(SHOT_DIR / f"{shot_prefix}_{tag}.png"))
        except Exception:
            pass

    # 제목 입력
    title_selectors = [
        ".se-section-documentTitle .se-text-paragraph",
        ".se-documentTitle .se-text-paragraph",
        ".se-placeholder.__se_placeholder",
    ]
    for sel in title_selectors:
        try:
            if frame.locator(sel).count() > 0:
                frame.click(sel, timeout=3000)
                clip_write_text(page, data["title"])
                page.keyboard.press(f"{MOD}+V")
                break
        except Exception:
            continue
    shot("title")

    # 본문 입력 (HTML 클립보드 붙여넣기 → 실패 시 평문)
    body_selectors = [
        ".se-section-text .se-text-paragraph",
        ".se-component.se-text .se-text-paragraph",
        ".se-content .se-text-paragraph",
    ]
    pasted = False
    for sel in body_selectors:
        try:
            if frame.locator(sel).count() > 0:
                frame.click(sel, timeout=3000)
                try:
                    clip_write_html(page, data["body_html"], data["body_text"])
                except Exception:
                    clip_write_text(page, data["body_text"])
                page.keyboard.press(f"{MOD}+V")
                pasted = True
                break
        except Exception:
            continue
    if not pasted:
        print("  [경고] 본문 입력 영역을 찾지 못함 — 수동 붙여넣기 필요(클립보드에 본문 적재됨).")
        clip_write_html(page, data["body_html"], data["body_text"])
    time.sleep(1.5)
    shot("body")

    if not do_publish:
        # 임시저장 (Ctrl+S 또는 저장 버튼)
        try:
            frame.click("button:has-text('저장')", timeout=3000)
        except Exception:
            page.keyboard.press(f"{MOD}+s")
        print("  [완료] 임시저장 시도. 에디터에서 확인하세요.")
        shot("draft")
        return

    # 발행 패널 열기
    for sel in ["button:has-text('발행')", ".publish_btn__m9KHH", "button.publish_btn__m9KHH"]:
        try:
            if frame.locator(sel).count() > 0:
                frame.click(sel, timeout=4000)
                break
        except Exception:
            continue
    time.sleep(1.5)
    shot("publish_panel")

    # 카테고리 선택 (가능하면)
    if data.get("category"):
        try:
            frame.click("button:has-text('카테고리')", timeout=2500)
            time.sleep(0.5)
            frame.click(f"label:has-text('{data['category']}'), span:has-text('{data['category']}')", timeout=2500)
        except Exception:
            print(f"  [참고] 카테고리 '{data['category']}' 자동 선택 실패 — 기본 카테고리로 진행.")

    # 최종 발행 확정
    confirmed = False
    for sel in [".confirm_btn__WEaBq", "button.confirm_btn__WEaBq",
                ".layer_btn_area button:has-text('발행')", "button:has-text('발행')"]:
        try:
            if frame.locator(sel).count() > 0:
                frame.click(sel, timeout=4000)
                confirmed = True
                break
        except Exception:
            continue
    time.sleep(3)
    shot("done")
    print(f"  [{'완료' if confirmed else '미확인'}] 발행 {'성공 추정' if confirmed else '버튼 확인 실패 — 스크린샷 점검'}.")


# ── 메인 ───────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description="네이버 블로그 자동 발행기")
    ap.add_argument("files", nargs="*", help="발행할 naver_out/*.html (생략 시 오늘자 전체)")
    ap.add_argument("--date", help="YYYYMMDD (해당 날짜 파일만)")
    ap.add_argument("--publish", action="store_true", help="제목/본문/카테고리/발행 전자동")
    ap.add_argument("--draft", action="store_true", help="발행 대신 임시저장까지만")
    ap.add_argument("--headless", action="store_true", help="헤드리스(권장X — 캡차 대응 불가)")
    args = ap.parse_args()

    nid, npw = load_creds()
    files = pick_files(args)
    if not files:
        print("[종료] 발행할 파일이 없습니다.")
        return 1

    reports = []
    for f in files:
        if not f.exists():
            print(f"[건너뜀] 파일 없음: {f}")
            continue
        d = parse_export(f)
        d["src"] = f
        reports.append(d)
        print(f"[대상] {f.name}  | 카테고리: {d['category'] or '(미상)'} | 제목: {d['title'][:40]}...")

    if not reports:
        return 1

    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    mode = "publish" if args.publish else ("draft" if args.draft else "assist")
    print(f"\n[모드] {mode}\n")

    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=args.headless,
            args=["--disable-blink-features=AutomationControlled", "--start-maximized"],
            viewport=None,
        )
        for origin in ("https://nid.naver.com", "https://blog.naver.com", "https://www.naver.com"):
            try:
                ctx.grant_permissions(["clipboard-read", "clipboard-write"], origin=origin)
            except Exception:
                pass
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        if not already_logged_in(page):
            do_login(page, nid, npw)
            if not already_logged_in(page):
                print("[오류] 로그인 확인 실패. 브라우저에서 수동 로그인 후 다시 실행하세요(세션 저장됨).")
                input("  → 수동 로그인 완료 후 Enter(세션 저장): ")
        else:
            print("[로그인] 기존 세션 재사용.")

        for i, d in enumerate(reports, 1):
            print(f"\n=== [{i}/{len(reports)}] {d['src'].name} ===")
            frame = open_writer(page, nid)
            if not frame:
                print("  [건너뜀] 에디터 진입 실패.")
                continue

            if mode == "assist":
                clip_write_html(page, d["body_html"], d["body_text"])
                print("  [assist] 글쓰기 페이지가 열렸습니다.")
                print(f"    • 제목(클립보드 대체용): {d['title']}")
                print(f"    • 추천 카테고리: {d['category'] or '(수동 선택)'}")
                print("    • 본문 HTML이 클립보드에 적재됨 → 본문 영역 클릭 후 Ctrl+V, 발행은 직접 클릭.")
                input("    → 이 글 처리 완료 후 Enter(다음 글로): ")
            else:
                autofill_and_publish(page, frame, d, do_publish=(mode == "publish"),
                                     shot_prefix=d["src"].stem)
                time.sleep(1)

        print("\n[종료] 모든 대상 처리. 브라우저는 점검을 위해 열어둡니다.")
        try:
            input("→ 종료하려면 Enter: ")
        except EOFError:
            time.sleep(5)
        ctx.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
