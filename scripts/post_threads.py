"""
Threads 자동 포스팅 스크립트
사용법: python -X utf8 scripts/post_threads.py <mdx파일경로>
예시:   python -X utf8 scripts/post_threads.py content/picks/20260417-genesis-report.mdx
"""
import sys
import json
import re
import time
import urllib.request
import urllib.parse
import os

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "threads_config.json")
SITE_URL = "https://genesis-report.com"

# MDX 파일 경로 매핑 (frontmatter 경로 → 사이트 URL 경로)
PATH_MAP = {
    "content/picks": "/picks",
    "content/market-analysis": "/market-analysis",
    "content/stock-reports": "/stock-reports",
}


def load_config():
    if not os.path.exists(CONFIG_PATH):
        print(f"[오류] config 파일 없음: {CONFIG_PATH}")
        print("config/threads_config.json 을 생성하고 user_id, access_token을 입력하세요.")
        sys.exit(1)
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def save_config(config):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def refresh_token(config):
    """장기 액세스 토큰 자동 갱신 (60일 유효, 매 포스팅 시 갱신)"""
    url = "https://graph.threads.net/refresh_access_token"
    params = {
        "grant_type": "th_refresh_token",
        "access_token": config["access_token"],
    }
    req = urllib.request.Request(f"{url}?{urllib.parse.urlencode(params)}")
    try:
        with urllib.request.urlopen(req) as r:
            data = json.loads(r.read().decode("utf-8"))
        config["access_token"] = data["access_token"]
        save_config(config)
        print("[토큰] 액세스 토큰 자동 갱신 완료")
    except Exception as e:
        print(f"[주의] 토큰 갱신 실패 (기존 토큰으로 계속 진행): {e}")
    return config


def parse_frontmatter(mdx_path):
    """MDX 파일에서 frontmatter 파싱"""
    with open(mdx_path, encoding="utf-8") as f:
        content = f.read()

    match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not match:
        print("[오류] frontmatter를 찾을 수 없습니다.")
        sys.exit(1)

    fm = {}
    for line in match.group(1).splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            fm[key.strip()] = val.strip().strip('"').strip("'")
    return fm


def build_post_url(mdx_path):
    """MDX 파일 경로 → 사이트 URL 변환"""
    # 경로 구분자 통일
    normalized = mdx_path.replace("\\", "/")
    filename = os.path.splitext(os.path.basename(normalized))[0]

    for prefix, url_path in PATH_MAP.items():
        if prefix in normalized:
            return f"{SITE_URL}{url_path}/{filename}"

    return SITE_URL


def build_post_text(fm, post_url):
    """Threads 포스팅 텍스트 생성"""
    title = fm.get("title", "제네시스 리포트")
    summary = fm.get("summary", "")
    tags = fm.get("tags", "")

    # tags에서 해시태그 생성
    hashtags = ""
    if tags:
        tag_list = re.findall(r'"([^"]+)"', tags)
        if tag_list:
            hashtags = " ".join([f"#{t.replace(' ', '')}" for t in tag_list[:4]])

    text = f"{title}\n\n{summary}"
    if hashtags:
        text += f"\n\n{hashtags}"
    text += f"\n\n🔗 {post_url}"

    # Threads 최대 500자 제한
    if len(text) > 490:
        text = text[:487] + "..."

    return text


def post_to_threads(config, text):
    """Threads API 2단계 포스팅"""
    user_id = config["user_id"]
    token = config["access_token"]

    # 1단계: 미디어 컨테이너 생성
    url1 = f"https://graph.threads.net/v1.0/{user_id}/threads"
    params1 = {
        "media_type": "TEXT",
        "text": text,
        "access_token": token,
    }
    data1 = urllib.parse.urlencode(params1).encode("utf-8")
    req1 = urllib.request.Request(url1, data=data1, method="POST")
    req1.add_header("Content-Type", "application/x-www-form-urlencoded")

    with urllib.request.urlopen(req1) as r:
        result1 = json.loads(r.read().decode("utf-8"))

    creation_id = result1.get("id")
    if not creation_id:
        print(f"[오류] 컨테이너 생성 실패: {result1}")
        sys.exit(1)

    print(f"[Threads] 컨테이너 생성: {creation_id}")
    time.sleep(2)  # API 안정화 대기

    # 2단계: 게시
    url2 = f"https://graph.threads.net/v1.0/{user_id}/threads_publish"
    params2 = {
        "creation_id": creation_id,
        "access_token": token,
    }
    data2 = urllib.parse.urlencode(params2).encode("utf-8")
    req2 = urllib.request.Request(url2, data=data2, method="POST")
    req2.add_header("Content-Type", "application/x-www-form-urlencoded")

    with urllib.request.urlopen(req2) as r:
        result2 = json.loads(r.read().decode("utf-8"))

    post_id = result2.get("id")
    return post_id


def main():
    if len(sys.argv) < 2:
        print("사용법: python -X utf8 scripts/post_threads.py <mdx파일경로>")
        sys.exit(1)

    mdx_path = sys.argv[1]

    if not os.path.exists(mdx_path):
        print(f"[오류] 파일을 찾을 수 없습니다: {mdx_path}")
        sys.exit(1)

    print(f"[Threads] 포스팅 시작: {mdx_path}")

    # 설정 로드 및 토큰 자동 갱신
    config = load_config()
    config = refresh_token(config)

    # MDX 파싱
    fm = parse_frontmatter(mdx_path)
    post_url = build_post_url(mdx_path)
    text = build_post_text(fm, post_url)

    print(f"[Threads] 포스팅 내용 미리보기:\n{'='*40}\n{text}\n{'='*40}")

    # 포스팅
    post_id = post_to_threads(config, text)
    print(f"[Threads] 포스팅 완료! Post ID: {post_id}")
    print(f"[Threads] 확인: https://www.threads.net/post/{post_id}")


if __name__ == "__main__":
    main()
