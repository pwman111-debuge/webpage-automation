"""네이버 로그인 OAuth 토큰 발급/갱신 헬퍼 (제네시스 리포트 블로그용).

사용법:
  python -X utf8 scripts/naver_oauth.py exchange <code> [state]   # 인가코드 → 토큰 발급 후 .env 저장
  python -X utf8 scripts/naver_oauth.py refresh                   # refresh_token으로 access_token 갱신

인가코드 얻는 법:
  브라우저로 아래 URL 접속 → 동의 → localhost 리다이렉트 URL의 code= 값 사용
  https://nid.naver.com/oauth2.0/authorize?response_type=code&client_id=<ID>&redirect_uri=<REDIRECT>&state=genesis2026

필요 env (.env):
  NAVER_CLIENT_ID, NAVER_CLIENT_SECRET, NAVER_REDIRECT_URI
저장 env:
  NAVER_ACCESS_TOKEN, NAVER_REFRESH_TOKEN
"""
import os
import sys
import json
import urllib.parse
import urllib.request
from pathlib import Path

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
TOKEN_URL = "https://nid.naver.com/oauth2.0/token"


def load_env() -> dict:
    env = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip()
    return env


def save_env(updates: dict) -> None:
    lines = ENV_PATH.read_text(encoding="utf-8").splitlines() if ENV_PATH.exists() else []
    keys_done = set()
    for i, line in enumerate(lines):
        s = line.strip()
        if s and not s.startswith("#") and "=" in s:
            k = s.split("=", 1)[0].strip()
            if k in updates:
                lines[i] = f"{k}={updates[k]}"
                keys_done.add(k)
    for k, v in updates.items():
        if k not in keys_done:
            lines.append(f"{k}={v}")
    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _call(params: dict) -> dict:
    url = TOKEN_URL + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode("utf-8"))


def exchange(code: str, state: str = "genesis2026") -> int:
    env = load_env()
    result = _call({
        "grant_type": "authorization_code",
        "client_id": env["NAVER_CLIENT_ID"],
        "client_secret": env["NAVER_CLIENT_SECRET"],
        "code": code,
        "state": state,
    })
    if "access_token" not in result:
        print(f"[오류] 토큰 발급 실패: {result}")
        return 1
    save_env({
        "NAVER_ACCESS_TOKEN": result["access_token"],
        "NAVER_REFRESH_TOKEN": result.get("refresh_token", env.get("NAVER_REFRESH_TOKEN", "")),
    })
    print(f"[성공] access_token 저장 완료 (만료 {result.get('expires_in')}초)")
    print(f"  access_token: {result['access_token'][:20]}...")
    return 0


def refresh() -> int:
    env = load_env()
    rt = env.get("NAVER_REFRESH_TOKEN", "")
    if not rt:
        print("[오류] NAVER_REFRESH_TOKEN 없음 — exchange 먼저 실행")
        return 1
    result = _call({
        "grant_type": "refresh_token",
        "client_id": env["NAVER_CLIENT_ID"],
        "client_secret": env["NAVER_CLIENT_SECRET"],
        "refresh_token": rt,
    })
    if "access_token" not in result:
        print(f"[오류] 갱신 실패: {result}")
        return 1
    save_env({"NAVER_ACCESS_TOKEN": result["access_token"]})
    print(f"[성공] access_token 갱신 완료 (만료 {result.get('expires_in')}초)")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) < 2:
        print(__doc__)
        raise SystemExit(1)
    cmd = sys.argv[1]
    if cmd == "exchange":
        if len(sys.argv) < 3:
            print("사용법: python naver_oauth.py exchange <code> [state]")
            raise SystemExit(1)
        st = sys.argv[3] if len(sys.argv) > 3 else "genesis2026"
        raise SystemExit(exchange(sys.argv[2], st))
    elif cmd == "refresh":
        raise SystemExit(refresh())
    else:
        print(f"알 수 없는 명령: {cmd}")
        raise SystemExit(1)
