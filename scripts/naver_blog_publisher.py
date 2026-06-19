"""네이버 블로그 자동 발행기 (Playwright) — 당일 발행 리포트 요약본 일괄 게시.

트리거: "네이버 블로그 포스팅하자"
→ 오늘(또는 --date) content/ 하위에 생성된 모든 리포트를 찾아, 각각 '요약본 + 원문
   백링크' 형태로 blog.naver.com/pwman11 에 카테고리·태그까지 자동 발행한다.

2026-06-18 라이브 실증으로 확정된 방법을 그대로 코드화했다:
  • 로그인  : #id/#pw에 네이티브 setter로 value 주입 후 #log.login 클릭 (캡차 없이 통과,
              세션은 .naver_profile/에 영속 → 이후 실행은 로그인 생략).
  • 본문입력: SmartEditor ONE은 execCommand·합성 paste를 무시한다. 시스템 클립보드
              (PowerShell Set-Clipboard) + 실제 Ctrl+V(page.keyboard) 만 반영됨.
  • 취소선  : 진입 시 취소선 토글이 켜져 있으면 붙여넣기 텍스트가 <strike>로 감싸진다.
              붙여넣기 전 반드시 토글 OFF 확인/해제.
  • 카테고리: 발행패널 '카테고리 목록 버튼' → 라벨 라디오 JS click (공백 정규화 매칭).
  • 발행확정: data-testid="seOnePublishBtn".

의존성(최초 1회): pip install playwright beautifulsoup4 && playwright install chromium

사용법:
  python -X utf8 scripts/naver_blog_publisher.py                 # 오늘자 전체 발행
  python -X utf8 scripts/naver_blog_publisher.py --date 20260618 # 특정일
  python -X utf8 scripts/naver_blog_publisher.py --draft         # 임시저장만(테스트)
  python -X utf8 scripts/naver_blog_publisher.py content/picks/20260618-genesis-report.mdx
"""
from __future__ import annotations

import argparse
import datetime as _dt
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

try:
    from playwright.sync_api import TimeoutError as PWTimeout
    from playwright.sync_api import sync_playwright
except ImportError:
    print("[오류] playwright 필요: pip install playwright && playwright install chromium")
    raise SystemExit(1)

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
PROFILE_DIR = SCRIPTS / ".naver_profile"
ENV_FILE = SCRIPTS / ".env.naver"
SITE_URL = "https://genesis-report.com"
BLOG_ID = "pwman11"

# content 폴더 → (사이트 URL 경로, 네이버 카테고리명).  발행 순서이기도 하다.
FOLDER_MAP = [
    ("content/market-analysis", "/market", "시황분석"),
    ("content/picks", "/picks", "유망종목"),
    ("content/stock-reports", "/analysis", "종목리포트"),
    ("content/market-insight", "/insight", "마켓인사이트"),
    ("content/education", "/education", "투자교육"),
    ("content/picks-feedback", "/picks/feedback", "투자성과 리포트"),
]


# ── 자격증명 ───────────────────────────────────────────────
def load_creds() -> tuple[str, str]:
    nid, npw = os.environ.get("NAVER_ID"), os.environ.get("NAVER_PW")
    if (not nid or not npw) and ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            if k.strip() == "NAVER_ID" and not nid:
                nid = v.strip()
            elif k.strip() == "NAVER_PW" and not npw:
                npw = v.strip()
    if not nid or not npw:
        print(f"[오류] 자격증명 없음 → {ENV_FILE} 에 NAVER_ID / NAVER_PW 설정")
        raise SystemExit(1)
    return nid, npw


# ── 시스템 클립보드 (PowerShell, 한글 안전) ────────────────
def set_clipboard(text: str):
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".txt", encoding="utf-8") as f:
        f.write(text)
        path = f.name
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             f"Set-Clipboard -Value (Get-Content -LiteralPath '{path}' -Raw -Encoding UTF8).TrimEnd()"],
            check=True, capture_output=True,
        )
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


# ── frontmatter & 콘텐츠 ───────────────────────────────────
def parse_frontmatter(text: str):
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    raw, body = text[3:end].strip(), text[end + 4:].lstrip("\n")
    fm = {}
    for line in raw.splitlines():
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        k, v = k.strip(), v.strip()
        if v.startswith("[") and v.endswith("]"):
            parts = [x.strip().strip('"').strip("'").strip() for x in v[1:-1].split(",")]
            fm[k] = [x for x in parts if x]
        else:
            fm[k] = v.strip().strip('"').strip("'")
    return fm, body


def scrub_brand(text: str) -> str:
    if not text:
        return ""
    text = text.replace("[제네시스 리포트]", "").replace("제네시스 리포트", "")
    text = text.replace("- 제네시스 모멘텀", "").replace("제네시스 모멘텀", "모멘텀")
    text = re.sub(r"제네시스\s*", "", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip(" -—·|\t").strip()


def make_title(raw: str) -> str:
    t = scrub_brand(raw)
    if ":" in t:                       # 핵심 헤드라인만 (콜론 이후 상세 절단)
        t = t.split(":", 1)[0].strip()
    if len(t) > 60:
        cut = t[:60]
        for sep in ["—", "·", ", ", " "]:
            i = cut.rfind(sep)
            if i > 30:
                cut = cut[:i]
                break
        t = cut.strip(" -—·,")
    return t


def backlink_for(rel_path: str) -> tuple[str, str]:
    norm = rel_path.replace("\\", "/")
    fname = os.path.splitext(os.path.basename(norm))[0]
    for prefix, url_path, cat in FOLDER_MAP:
        if (prefix + "/") in (norm + "/"):     # 정확한 디렉토리 매칭 (picks vs picks-feedback)
            return f"{SITE_URL}{url_path}/{fname}", cat
    return SITE_URL, "(수동 선택)"


def build_post(mdx_path: Path) -> dict:
    fm, _ = parse_frontmatter(mdx_path.read_text(encoding="utf-8"))
    rel = str(mdx_path.relative_to(ROOT)) if mdx_path.is_absolute() else str(mdx_path)
    backlink, category = backlink_for(rel)
    title = make_title(fm.get("title", mdx_path.stem))
    summary = scrub_brand(fm.get("summary", ""))
    body = (
        f"{summary}\n\n"
        f"📊 전체 리포트 보기 → {backlink}\n\n"
        f"본 글은 정보 제공 목적이며, 투자 판단과 책임은 투자자 본인에게 있습니다."
    )
    raw_tags = fm.get("tags", []) if isinstance(fm.get("tags"), list) else []
    tags = []
    for t in raw_tags:
        s = scrub_brand(t)
        if s and len(s) <= 18 and s not in tags:
            tags.append(s)
    tags = tags[:5] or [category.replace(" ", "")]
    return {"title": title, "body": body, "category": category, "tags": tags,
            "backlink": backlink, "src": mdx_path}


# ── 발행 대상 수집 ─────────────────────────────────────────
def collect_today(date_str: str) -> list[Path]:
    dashed = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
    found = []
    for prefix, _u, _c in FOLDER_MAP:
        d = ROOT / prefix
        if not d.exists():
            continue
        for p in sorted(d.glob("*.mdx")):
            if date_str in p.name or dashed in p.name:
                found.append(p)
    return found


# ── 네이버 로그인 ──────────────────────────────────────────
def logged_in(page) -> bool:
    try:
        page.goto("https://www.naver.com", wait_until="domcontentloaded", timeout=20000)
        return page.locator("a[href*='nidlogin.logout']").count() > 0 or "로그아웃" in page.content()
    except PWTimeout:
        return False


def login(page, nid: str, npw: str):
    print("[로그인] 시도...")
    page.goto("https://nid.naver.com/nidlogin.login?mode=form", wait_until="domcontentloaded")
    page.wait_for_selector("#id", timeout=15000)
    page.evaluate(
        """([id, pw]) => {
            const set=(el,v)=>{const s=Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;
              s.call(el,v); el.dispatchEvent(new Event('input',{bubbles:true}));
              el.dispatchEvent(new Event('change',{bubbles:true})); el.dispatchEvent(new KeyboardEvent('keyup',{bubbles:true}));};
            set(document.querySelector('#id'), id); set(document.querySelector('#pw'), pw);
        }""", [nid, npw])
    time.sleep(0.5)
    page.click("#log\\.login")
    time.sleep(3)
    if "nidlogin" in page.url:   # 캡차/추가인증
        print("\n[개입필요] 캡차/추가 인증으로 보입니다. 브라우저에서 직접 해결 후 Enter.")
        try:
            input("  → 완료 후 Enter: ")
        except EOFError:
            time.sleep(25)
    for sel in ["#new\\.dontsave", "a:has-text('등록안함')", "button:has-text('등록안함')"]:
        try:
            if page.locator(sel).count():
                page.click(sel, timeout=2500)
                break
        except Exception:
            pass
    print("[로그인] 완료(세션 저장).")


# ── 에디터 헬퍼 ────────────────────────────────────────────
# SmartEditor ONE 루트를 식별하는 셀렉터(제목칸 or 본문 캔버스)
_EDITOR_PROBE = ".se-section-documentTitle, .se-content, .se-canvas"


def get_editor(ctx, page):
    """모든 탭·모든 프레임을 훑어 SmartEditor가 들어있는 (owner_page, frame)을 반환.

    글쓰기 페이지가 새 탭으로 열리거나(target=_blank) mainFrame 이름이 바뀌어도
    에디터 DOM(_EDITOR_PROBE) 존재 여부로 직접 찾는다.
    """
    deadline = time.time() + 18
    while time.time() < deadline:
        for pg in list(reversed(ctx.pages)):   # 최근 열린 탭 우선
            try:
                cands = []
                fr = pg.frame(name="mainFrame")
                if fr:
                    cands.append(fr)
                cands.extend(f for f in pg.frames if f not in cands)
                for f in cands:
                    try:
                        if f.locator(_EDITOR_PROBE).count() > 0:
                            return pg, f
                    except Exception:
                        continue
            except Exception:
                continue
        time.sleep(0.5)
    return None, None


def dismiss_popups(page, frame):
    """임시저장 글 복구 팝업·도움말 패널을 닫아 새 에디터 상태로 만든다."""
    for _ in range(3):
        try:
            frame.evaluate(
                """() => {
                    // 도움말 패널
                    const h=document.querySelector('.se-help-panel-close-button'); if(h)h.click();
                    // 작성 중이던 글 복구 팝업 → '취소'(새 글로 시작)
                    const btns=[...document.querySelectorAll('button')];
                    const cancel=btns.find(b=>/^\\s*(취소|닫기)\\s*$/.test(b.textContent||'')
                        && (b.closest('[class*=popup]')||b.closest('[class*=layer]')||b.closest('[class*=dialog]')));
                    if(cancel){cancel.click(); return;}
                    // data-testid 기반 취소 버튼
                    const t=document.querySelector('[data-testid*="cancel"],[data-testid*="Cancel"]');
                    if(t)t.click();
                }""")
        except Exception:
            pass
        time.sleep(0.5)


def paste_into(page, frame, paragraph_selector: str, text: str):
    set_clipboard(text)
    time.sleep(0.3)
    frame.locator(paragraph_selector).first.click()
    time.sleep(0.3)
    page.keyboard.press("Control+V")
    time.sleep(0.7)


def ensure_strike_off(frame):
    on = frame.evaluate(
        """() => { const b=[...document.querySelectorAll('button')]
            .find(x=>x.className.includes('se-strikethrough-toolbar-button'));
            return b ? b.className.includes('se-is-selected') : false; }""")
    if on:
        try:
            frame.locator(".se-strikethrough-toolbar-button").first.click()
            time.sleep(0.3)
        except Exception:
            pass


def select_category(frame, category: str) -> bool:
    try:
        frame.get_by_role("button", name="카테고리 목록 버튼").click()
        time.sleep(0.6)
    except Exception:
        pass
    return bool(frame.evaluate(
        """(cat) => {
            const key = cat.replace(/\\s+/g,'');
            const labels=[...document.querySelectorAll('[class*=category] label')];
            let t=labels.find(l=>l.textContent.replace(/\\s+/g,'').includes(key));
            if(t){const inp=t.querySelector('input')||(t.htmlFor?document.getElementById(t.htmlFor):null);(inp||t).click();return true;}
            const sp=[...document.querySelectorAll('[class*=category] span,[class*=category] li')]
                .find(e=>e.textContent.replace(/\\s+/g,'').includes(key));
            if(sp){sp.click();return true;}
            return false;
        }""", category))


# ── 단일 글 발행 ───────────────────────────────────────────
def publish_one(ctx, page, post: dict, do_publish: bool) -> str:
    page.goto(f"https://blog.naver.com/{BLOG_ID}?Redirect=Write&", wait_until="domcontentloaded")
    time.sleep(3)
    owner, frame = get_editor(ctx, page)
    if not frame:
        diag = f"pages={len(ctx.pages)} url={page.url[:60]}"
        print(f"    [진단] 에디터 프레임 미발견 — {diag}")
        return "FAIL(no-frame)"
    # 도움말/작성중 복구 팝업 정리 (새 글 상태로)
    dismiss_popups(owner, frame)
    try:
        frame.wait_for_selector(".se-section-documentTitle .se-text-paragraph", timeout=15000)
    except PWTimeout:
        return "FAIL(no-title)"

    paste_into(owner, frame, ".se-section-documentTitle .se-text-paragraph", post["title"])
    ensure_strike_off(frame)
    paste_into(owner, frame, ".se-section-text .se-text-paragraph", post["body"])

    strike = frame.evaluate("() => document.querySelector('.se-section-text').querySelectorAll('strike,s').length")
    if strike:
        print(f"    [경고] 취소선 {strike}개 감지 → 재처리")
        frame.locator(".se-section-text .se-text-paragraph").first.click()
        owner.keyboard.press("Control+A")
        owner.keyboard.press("Delete")
        ensure_strike_off(frame)
        paste_into(owner, frame, ".se-section-text .se-text-paragraph", post["body"])

    if not do_publish:
        try:
            frame.get_by_role("button", name="저장").first.click()
        except Exception:
            owner.keyboard.press("Control+S")
        time.sleep(1.5)
        return "DRAFT"

    frame.get_by_role("button", name="발행").first.click()      # 패널 열기
    time.sleep(1.5)
    ok = select_category(frame, post["category"])
    if not ok:
        print(f"    [참고] 카테고리 '{post['category']}' 자동선택 실패 → 기본값 유지")
    # 태그
    try:
        tagbox = frame.get_by_role("combobox", name=re.compile("태그 입력"))
        for tg in post["tags"]:
            tagbox.fill(tg)
            tagbox.press("Enter")
            time.sleep(0.3)
    except Exception:
        pass
    # 발행 확정
    frame.get_by_test_id("seOnePublishBtn").click()
    time.sleep(4)
    return page.url


# ── 메인 ───────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description="네이버 블로그 당일 리포트 일괄 발행")
    ap.add_argument("files", nargs="*", help="특정 .mdx (생략 시 오늘자 전체)")
    ap.add_argument("--date", help="YYYYMMDD")
    ap.add_argument("--draft", action="store_true", help="발행 대신 임시저장")
    ap.add_argument("--headless", action="store_true")
    args = ap.parse_args()

    nid, npw = load_creds()
    if args.files:
        paths = [Path(f) if Path(f).is_absolute() else ROOT / f for f in args.files]
    else:
        date_str = args.date or _dt.date.today().strftime("%Y%m%d")
        paths = collect_today(date_str)
    paths = [p for p in paths if p.exists()]
    if not paths:
        print("[종료] 발행할 당일 리포트가 없습니다.")
        return 1

    posts = [build_post(p) for p in paths]
    print(f"[대상] {len(posts)}건")
    for p in posts:
        print(f"  - [{p['category']}] {p['title'][:42]}  ({p['src'].name})")

    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    results = []
    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR), headless=args.headless,
            args=["--disable-blink-features=AutomationControlled", "--start-maximized"],
            viewport=None,
        )
        for origin in ("https://nid.naver.com", "https://blog.naver.com", "https://www.naver.com"):
            try:
                ctx.grant_permissions(["clipboard-read", "clipboard-write"], origin=origin)
            except Exception:
                pass
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        if not logged_in(page):
            login(page, nid, npw)
        else:
            print("[로그인] 기존 세션 재사용.")

        for i, post in enumerate(posts, 1):
            print(f"\n=== [{i}/{len(posts)}] {post['src'].name} ===")
            try:
                res = publish_one(ctx, page, post, do_publish=not args.draft)
            except Exception as e:
                res = f"FAIL({type(e).__name__}: {str(e)[:80]})"
            print(f"    → {res}")
            results.append((post["title"], post["category"], res))
            time.sleep(1)

        print("\n===== 발행 요약 =====")
        for t, c, r in results:
            print(f"  [{c}] {r}  | {t[:40]}")
        ctx.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
