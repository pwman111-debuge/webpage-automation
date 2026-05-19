"""
LinkedIn OAuth 2.0 인증 스크립트 (최초 1회 실행)
사용법: python -X utf8 scripts/linkedin_auth.py

실행하면 브라우저가 열리고, 인증 후 access_token이 .env에 저장됩니다.
"""
import http.server
import urllib.request
import urllib.parse
import json
import os
import webbrowser
import threading

ENV_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
REDIRECT_URI = "http://localhost:8000/callback"
SCOPES = "openid profile w_member_social"

# OAuth 콜백에서 code를 받기 위한 전역 변수
auth_code = None


def load_credentials():
    env = {}
    with open(ENV_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                env[key.strip()] = val.strip()

    client_id = env.get("LINKEDIN_CLIENT_ID", "")
    client_secret = env.get("LINKEDIN_CLIENT_SECRET", "")

    if not client_id or client_id.startswith("여기에"):
        print("[오류] .env 파일에 LINKEDIN_CLIENT_ID를 입력하세요.")
        raise SystemExit(1)
    if not client_secret or client_secret.startswith("여기에"):
        print("[오류] .env 파일에 LINKEDIN_CLIENT_SECRET을 입력하세요.")
        raise SystemExit(1)

    return client_id, client_secret


def save_token(access_token, person_urn):
    with open(ENV_PATH, encoding="utf-8") as f:
        content = f.read()

    def upsert(text, key, value):
        import re
        pattern = rf"^{key}=.*$"
        replacement = f"{key}={value}"
        if re.search(pattern, text, re.MULTILINE):
            return re.sub(pattern, replacement, text, flags=re.MULTILINE)
        return text + f"\n{replacement}"

    content = upsert(content, "LINKEDIN_ACCESS_TOKEN", access_token)
    content = upsert(content, "LINKEDIN_PERSON_URN", person_urn)

    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.write(content)


def get_person_urn(access_token):
    """OpenID userinfo 엔드포인트로 person URN 조회"""
    url = "https://api.linkedin.com/v2/userinfo"
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {access_token}")
    with urllib.request.urlopen(req) as r:
        data = json.loads(r.read().decode("utf-8"))
    sub = data.get("sub", "")
    return f"urn:li:person:{sub}"


class CallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        global auth_code
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        if "code" in params:
            auth_code = params["code"][0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(
                "<html><body><h2>✅ 인증 완료! 이 창을 닫고 터미널로 돌아가세요.</h2></body></html>".encode("utf-8")
            )
        else:
            error = params.get("error", ["알 수 없는 오류"])[0]
            self.send_response(400)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(f"<html><body><h2>❌ 오류: {error}</h2></body></html>".encode("utf-8"))

    def log_message(self, format, *args):
        pass  # 서버 로그 숨김


def main():
    global auth_code

    client_id, client_secret = load_credentials()

    # 인증 URL 생성
    auth_params = urllib.parse.urlencode({
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPES,
        "state": "genesis_linkedin",
    })
    auth_url = f"https://www.linkedin.com/oauth/v2/authorization?{auth_params}"

    print("=" * 50)
    print("[LinkedIn] 브라우저에서 LinkedIn 로그인을 진행하세요.")
    print(f"인증 URL: {auth_url}")
    print("=" * 50)

    # 로컬 서버 백그라운드 실행
    server = http.server.HTTPServer(("localhost", 8000), CallbackHandler)
    server_thread = threading.Thread(target=server.handle_request)
    server_thread.start()

    webbrowser.open(auth_url)
    print("[LinkedIn] 브라우저에서 인증을 완료하면 자동으로 진행됩니다...")
    server_thread.join(timeout=120)

    if not auth_code:
        print("[오류] 120초 내에 인증이 완료되지 않았습니다. 다시 시도하세요.")
        raise SystemExit(1)

    print(f"[LinkedIn] 인증 코드 획득: {auth_code[:10]}...")

    # Access Token 교환
    token_url = "https://www.linkedin.com/oauth/v2/accessToken"
    token_params = {
        "grant_type": "authorization_code",
        "code": auth_code,
        "redirect_uri": REDIRECT_URI,
        "client_id": client_id,
        "client_secret": client_secret,
    }
    data = urllib.parse.urlencode(token_params).encode("utf-8")
    req = urllib.request.Request(token_url, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")

    try:
        with urllib.request.urlopen(req) as r:
            token_data = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        print(f"[오류] 토큰 교환 실패 {e.code}: {body}")
        raise SystemExit(1)

    access_token = token_data.get("access_token", "")
    expires_in = token_data.get("expires_in", 0)

    if not access_token:
        print(f"[오류] 토큰 발급 실패: {token_data}")
        raise SystemExit(1)

    print(f"[LinkedIn] 액세스 토큰 발급 완료 (유효기간: {expires_in // 86400}일)")

    # Person URN 조회
    try:
        person_urn = get_person_urn(access_token)
        print(f"[LinkedIn] Person URN: {person_urn}")
    except Exception as e:
        print(f"[주의] Person URN 조회 실패: {e}")
        person_urn = ""

    # .env 저장
    save_token(access_token, person_urn)
    print("[LinkedIn] .env 파일에 토큰 저장 완료!")
    print("이제 python -X utf8 scripts/post_linkedin.py <mdx파일경로> 로 포스팅하세요.")


if __name__ == "__main__":
    main()
