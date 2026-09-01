---
name: naver-data-fetcher
description: 네이버 증권에서 시장 데이터를 Python Bash로 직접 수집하는 스킬 (로컬 PC 한국 IP 활용)
---

# 📡 Naver Data Fetcher 스킬

네이버 증권은 Claude의 WebFetch로 접근 불가(미국 IP 차단)하므로,
**Python Bash를 사용자 로컬 PC에서 실행**하여 데이터를 수집한다.

---

## 🔧 공통 헤더 (모든 함수에 적용)

```python
import urllib.request, re

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'ko-KR,ko;q=0.9',
    'Referer': 'https://finance.naver.com/'
}

def fetch(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req) as r:
        return r.read().decode('euc-kr', errors='replace')
```

---

## [Function 1] KOSPI / KOSDAQ 지수 조회

```python
import urllib.request, re

HEADERS = {'User-Agent': 'Mozilla/5.0','Accept-Language': 'ko-KR,ko;q=0.9','Referer': 'https://finance.naver.com/'}

for code in ['KOSPI', 'KOSDAQ']:
    url = f'https://finance.naver.com/sise/sise_index_day.naver?code={code}'
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req) as r:
        html = r.read().decode('euc-kr', errors='replace')
    rows = re.findall(r'(\d{4}\.\d{2}\.\d{2}).*?([\d,]+\.\d+)', html, re.DOTALL)
    if rows:
        print(f'{code} | {rows[0][0]} | {rows[0][1]}')
```

**출력 예시:**
```
KOSPI | 2026.04.14 | 5,967.75
KOSDAQ | 2026.04.14 | 1,093.63
```

---

## ⚠️ "쌍끌이" 판정 규칙 — 반드시 두 리스트 교차 확인

**"외국인+기관 쌍끌이"는 두 조건이 동시에 충족될 때만 사용 가능하다:**
1. Function 2 (외국인 순매수 상위) 목록에 해당 종목이 있다
2. Function 3 (기관 순매수 상위) 목록에 해당 종목이 있다

**두 리스트 중 하나에만 있으면:**
- 기관 리스트에만 있음 → **"기관 독주"** (외국인은 매도 중일 수 있음)
- 외국인 리스트에만 있음 → **"외국인 주도"**

**개별 종목 외국인·기관 수치 직접 확인 (쌍끌이 의심 시 필수):**
```python
python scripts/naver_finance.py investor [종목코드]
# 출력의 최상단 행(오늘 날짜) 기관 순매수·외국인 순매수 수치 확인
```

> ❌ 잘못된 예: "기관 1위 HD현대중공업 → 조선 쌍끌이"
> ✅ 올바른 예: "Function 2·3 교차 결과, 두 리스트에 동시 등장한 종목만 쌍끌이로 표기"

---

## ⚠️ 핵심 주의사항: 당일 vs 전날 데이터 구분

**네이버 증권 투자자별 순매매 상위 페이지는 항상 두 날짜를 나란히 표시한다:**
- 좌측 컬럼 = **전날** 데이터 (절대 사용 금지)
- 우측 컬럼 = **당일(오늘)** 데이터 (반드시 이것만 사용)

`re.findall` 결과는 `[전날1위, 전날2위, ..., 전날20위, 당일1위, 당일2위, ..., 당일20위]` 순서로 반환된다.
**오늘 데이터만 추출하려면 `all_items[len(all_items)//2:]` (후반부)를 반드시 사용할 것.**

---

## [Function 2] 외국인 순매수 상위 종목

```python
import urllib.request, re, datetime

HEADERS = {'User-Agent': 'Mozilla/5.0','Accept-Language': 'ko-KR,ko;q=0.9','Referer': 'https://finance.naver.com/sise/sise_deal_rank.naver'}

today_str = datetime.date.today().strftime('%y.%m.%d')  # 표시용: 26.04.22

for market, sosok in [('KOSPI', '01'), ('KOSDAQ', '02')]:
    url = f'https://finance.naver.com/sise/sise_deal_rank_iframe.naver?sosok={sosok}&investor_gubun=9000&type=buy'
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req) as r:
        html = r.read().decode('euc-kr', errors='replace')
    all_items = re.findall(
        r'code=(\d{6})[^>]*>(.*?)</a>.*?class="number">([\d,\-]+)</td>.*?class="number">([\d,\-]+)</td>',
        html, re.DOTALL
    )
    # 당일(우측) 데이터만 사용: 전체 결과의 후반부 = 당일, 전반부 = 전날
    # 구조: [전날1위, 전날2위, ..., 전날20위, 당일1위, 당일2위, ..., 당일20위]
    items = all_items[len(all_items)//2:]
    print(f'\n=== 외국인 순매수 상위 ({market}) [{today_str} 당일 기준] ===')
    for code, name, price, amount in items[:10]:
        print(f'  {name.strip()} ({code}) | 현재가: {price} | 순매수: {amount}백만원')
```

**출력 예시:**
```
=== 외국인 순매수 상위 (KOSPI) [26.04.22 당일 기준] ===
  TIGER MSCI Korea TR (310970) | 현재가: 10,200 | 순매수: 433,701백만원
  이수페타시스 (007660) | 현재가: 1,024 | 순매수: 151,845백만원
```

---

## [Function 3] 기관 순매수 상위 종목

```python
import urllib.request, re, datetime

HEADERS = {'User-Agent': 'Mozilla/5.0','Accept-Language': 'ko-KR,ko;q=0.9','Referer': 'https://finance.naver.com/sise/sise_deal_rank.naver'}

today_str = datetime.date.today().strftime('%y.%m.%d')  # 표시용: 26.04.22

url = 'https://finance.naver.com/sise/sise_deal_rank_iframe.naver?sosok=01&investor_gubun=1000&type=buy'
req = urllib.request.Request(url, headers=HEADERS)
with urllib.request.urlopen(req) as r:
    html = r.read().decode('euc-kr', errors='replace')

all_items = re.findall(
    r'code=(\d{6})[^>]*>(.*?)</a>.*?class="number">([\d,\-]+)</td>.*?class="number">([\d,\-]+)</td>',
    html, re.DOTALL
)
# 당일(우측) 데이터만 사용: 전체 결과의 후반부 = 당일, 전반부 = 전날
# 구조: [전날1위, 전날2위, ..., 전날20위, 당일1위, 당일2위, ..., 당일20위]
items = all_items[len(all_items)//2:]
print(f'=== 기관 순매수 상위 (KOSPI) [{today_str} 당일 기준] ===')
for code, name, price, amount in items[:10]:
    print(f'  {name.strip()} ({code}) | 현재가: {price} | 순매수: {amount}백만원')
```

---

## [Function 4] 거래량 급증 종목

```python
import urllib.request, re

HEADERS = {'User-Agent': 'Mozilla/5.0','Accept-Language': 'ko-KR,ko;q=0.9','Referer': 'https://finance.naver.com/'}

url = 'https://finance.naver.com/sise/sise_quant.naver?sosok=0'
req = urllib.request.Request(url, headers=HEADERS)
with urllib.request.urlopen(req) as r:
    html = r.read().decode('euc-kr', errors='replace')

items = re.findall(
    r'code=(\d{6})[^>]*class="tltle">(.*?)</a>.*?class="number">([\d,]+)</td>.*?class="number">([\d,]+)</td>',
    html, re.DOTALL
)
print('=== 거래량 급증 종목 (KOSPI) ===')
for code, name, price, volume in items[:10]:
    print(f'  {name.strip()} ({code}) | 현재가: {price} | 거래량: {volume}')
```

---

## [Function 5] 종목 일별시세 (현재가·등락률 확인)

```python
import urllib.request, re

HEADERS = {'User-Agent': 'Mozilla/5.0','Accept-Language': 'ko-KR,ko;q=0.9','Referer': 'https://finance.naver.com/'}

def get_stock_price(code):
    url = f'https://finance.naver.com/item/sise_day.naver?code={code}'
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req) as r:
        html = r.read().decode('euc-kr', errors='replace')
    rows = re.findall(
        r'(\d{4}\.\d{2}\.\d{2}).*?<span class="tah p11">([\d,]+)</span>.*?<span class="tah p11">([\d,]+)</span>.*?<span class="tah p11">([\d,]+)</span>',
        html[:5000], re.DOTALL
    )
    if rows:
        date, close, open_, volume = rows[0]
        print(f'종목: {code} | 날짜: {date} | 종가: {close} | 시가: {open_} | 거래량: {volume}')

# 사용 예시
get_stock_price('012450')  # 한화에어로스페이스
get_stock_price('000660')  # SK하이닉스
```

**출력 예시:**
```
종목: 012450 | 날짜: 2026.04.14 | 종가: 1,523,000 | 시가: 1,515,000 | 거래량: 1,531,000
```

---

## [Function 6] 종목 뉴스·공시 확인

```python
import urllib.request, re

HEADERS = {'User-Agent': 'Mozilla/5.0','Accept-Language': 'ko-KR,ko;q=0.9','Referer': 'https://finance.naver.com/'}

def get_stock_news(code, name):
    url = f'https://finance.naver.com/item/news_news.naver?code={code}&sm=title_entity_id.basic&clusterId='
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req) as r:
        html = r.read().decode('euc-kr', errors='replace')
    headlines = re.findall(r'class="tit"[^>]*>(.*?)</a>', html, re.DOTALL)
    cleaned = [re.sub(r'<[^>]+>', '', h).strip() for h in headlines]
    print(f'=== {name} ({code}) 최근 뉴스 ===')
    for h in cleaned[:5]:
        if h:
            print(f'  - {h}')

# 사용 예시
get_stock_news('012450', '한화에어로스페이스')
```

---

## ⚠️ Failover (Python 실행 불가 시)

Python Bash 실행이 불가한 경우 아래 대체 소스를 사용한다:

| 용도 | 대체 URL |
| :--- | :--- |
| 외국인+기관 동반 순매수 | `https://comp.fnguide.com/SVO2/json/data/NH/SUPPLY_TREND_WITH_BUY.json` (WebFetch) |
| 종목 상세 | `https://comp.fnguide.com/SVO2/ASP/SVD_Main.asp?gicode=AXXXXXX` (WebFetch) |
| 시황 요약 | WebSearch: `코스피 코스닥 {날짜} 마감 시황` |

> **⚠️ Failover 시 날짜 확인 필수:** WebSearch나 WebFetch로 수급 데이터를 수집할 때도
> 반드시 **당일(오늘) 날짜 기준** 데이터인지 확인한다. 네이버 증권 페이지는 항상 좌측=전날, 우측=당일
> 두 컬럼이 표시되므로, 오늘 날짜(우측)의 데이터만 사용해야 한다.
