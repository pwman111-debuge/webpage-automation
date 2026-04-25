"""
LinkedIn 자동 포스팅 스크립트
사용법: python -X utf8 scripts/post_linkedin.py <mdx파일경로>
예시:   python -X utf8 scripts/post_linkedin.py content/picks/20260425-genesis-report.mdx
"""
import sys
import json
import re
import os
import urllib.request
import urllib.parse

ENV_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
SITE_URL = "https://genesis-report.com"
OG_IMAGE_URL = "https://genesis-report.com/og-image.png"

PATH_MAP = {
    "content/picks": "/picks",
    "content/market-analysis": "/market",
    "content/stock-reports": "/analysis",
}


def load_env():
    if not os.path.exists(ENV_PATH):
        print(f"[오류] .env 파일 없음: {ENV_PATH}")
        sys.exit(1)

    env = {}
    with open(ENV_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                env[key.strip()] = val.strip()

    token = env.get("LINKEDIN_ACCESS_TOKEN", "")
    person_urn = env.get("LINKEDIN_PERSON_URN", "")

    if not token or token.startswith("여기에"):
        print("[오류] LINKEDIN_ACCESS_TOKEN이 없습니다. 먼저 linkedin_auth.py를 실행하세요.")
        sys.exit(1)
    if not person_urn or person_urn.startswith("여기에"):
        print("[오류] LINKEDIN_PERSON_URN이 없습니다. 먼저 linkedin_auth.py를 실행하세요.")
        sys.exit(1)

    return token, person_urn


def parse_frontmatter(mdx_path):
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
    normalized = mdx_path.replace("\\", "/")
    filename = os.path.splitext(os.path.basename(normalized))[0]

    for prefix, url_path in PATH_MAP.items():
        if prefix in normalized:
            return f"{SITE_URL}{url_path}/{filename}"

    return SITE_URL


def build_post_text(fm, post_url):
    """LinkedIn 포스팅 텍스트 생성 (최대 3000자)"""
    title = fm.get("title", "제네시스 리포트")
    summary = fm.get("summary", "")
    tags = fm.get("tags", "")

    hashtags = ""
    if tags:
        tag_list = re.findall(r'"([^"]+)"', tags)
        if tag_list:
            hashtags = " ".join([f"#{t.replace(' ', '')}" for t in tag_list[:5]])

    text = f"📊 {title}\n\n{summary}"
    if hashtags:
        text += f"\n\n{hashtags}"
    text += f"\n\n🔗 전체 분석 보기: {post_url}"
    text += "\n\n#한국주식 #주식분석 #투자 #GenesisReport"

    if len(text) > 3000:
        text = text[:2997] + "..."

    return text


def post_to_linkedin(token, person_urn, text, post_url, title="제네시스 주식 리포트", fm_summary=""):
    """LinkedIn UGC Posts API로 포스팅 (이미지 썸네일 포함)"""
    url = "https://api.linkedin.com/v2/ugcPosts"

    payload = {
        "author": person_urn,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": text},
                "shareMediaCategory": "ARTICLE",
                "media": [
                    {
                        "status": "READY",
                        "originalUrl": post_url,
                        "title": {"text": title},
                        "description": {"text": fm_summary},
                    }
                ],
            }
        },
        "visibility": {
            "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
        },
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")
    req.add_header("X-Restli-Protocol-Version", "2.0.0")

    try:
        with urllib.request.urlopen(req) as r:
            result = json.loads(r.read().decode("utf-8"))
            return result.get("id", "")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        print(f"[오류] LinkedIn API 응답 {e.code}: {body}")
        sys.exit(1)


def main():
    if len(sys.argv) < 2:
        print("사용법: python -X utf8 scripts/post_linkedin.py <mdx파일경로>")
        sys.exit(1)

    mdx_path = sys.argv[1]

    if not os.path.exists(mdx_path):
        print(f"[오류] 파일을 찾을 수 없습니다: {mdx_path}")
        sys.exit(1)

    print(f"[LinkedIn] 포스팅 시작: {mdx_path}")

    token, person_urn = load_env()
    fm = parse_frontmatter(mdx_path)
    post_url = build_post_url(mdx_path)
    text = build_post_text(fm, post_url)

    print(f"[LinkedIn] 포스팅 내용 미리보기:\n{'='*40}\n{text}\n{'='*40}")

    post_urn = post_to_linkedin(token, person_urn, text, post_url, title=fm.get("title", "제네시스 주식 리포트"), fm_summary=fm.get("summary", ""))
    print(f"[LinkedIn] 포스팅 완료! URN: {post_urn}")


if __name__ == "__main__":
    main()
