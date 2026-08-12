# -*- coding: utf-8 -*-
"""
제네시스 시장 전수 스크리너
- 시가총액 상위 종목(KOSPI+KOSDAQ)에 대해 ATR(14, Wilder), MA5/20/60, 20일선 이격도, RSI(14) 산출
- 발간 게이트 판정용 시장 평균 ATR / 발간금지 등급 비중 / 정배열 종목 수 집계

사용법:
  python -X utf8 scripts/market_screener.py [종목수]     # 기본 295
  python -X utf8 scripts/market_screener.py 295 --json out.json
"""
import sys, re, json, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'ko-KR,ko;q=0.9',
    'Referer': 'https://finance.naver.com/',
}


def fetch(url, enc='euc-kr'):
    req = urllib.request.Request(url, headers=HEADERS)
    for _ in range(3):
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                return r.read().decode(enc, errors='replace')
        except Exception:
            continue
    return ''


def market_cap_universe(limit=295, market='KOSPI'):
    """시가총액 상위 목록. market='KOSPI'|'KOSDAQ'|'ALL'

    시가총액 페이지 컬럼 순서(td.number):
      0 현재가 / 1 전일비 / 2 등락률 / 3 액면가 / 4 시가총액(억) / 5 상장주식수 ...

    ※ 게이트 지표(시장 평균 ATR·발간금지 비중·정배열)는 KOSPI 시총 상위 295종목 기준으로
      산출해온 기존 시계열과의 연속성을 위해 기본값을 KOSPI로 둔다.
    """
    targets = {'KOSPI': [(0, 'KOSPI')], 'KOSDAQ': [(1, 'KOSDAQ')],
               'ALL': [(0, 'KOSPI'), (1, 'KOSDAQ')]}[market]
    rows = []
    for sosok, mname in targets:
        for page in range(1, 8):
            html = fetch(f'https://finance.naver.com/sise/sise_market_sum.naver?sosok={sosok}&page={page}')
            for tr in re.split(r'<tr\s', html):
                m = re.search(r'code=(\d{6})"[^>]*class="tltle">([^<]+)</a>', tr)
                if not m:
                    continue
                nums = [re.sub(r'<[^>]+>', '', t).strip().replace(',', '')
                        for t in re.findall(r'<td class="number">(.*?)</td>', tr, re.S)]
                if len(nums) < 5 or not nums[4].isdigit():
                    continue
                rows.append({'code': m.group(1), 'name': m.group(2).strip(), 'market': mname,
                             'price': int(nums[0]) if nums[0].isdigit() else 0,
                             'cap': int(nums[4])})
    seen, uniq = set(), []
    for r in sorted(rows, key=lambda x: -x['cap']):
        if r['code'] in seen:
            continue
        seen.add(r['code'])
        uniq.append(r)
    return uniq[:limit]


def ohlc(code, start='20260101', end=None):
    url = (f'https://api.finance.naver.com/siseJson.naver?symbol={code}'
           f'&requestType=1&startTime={start}&endTime={end}&timeframe=day')
    txt = fetch(url, enc='utf-8')
    out = []
    for m in re.finditer(r'\["(\d{8})",\s*([\d.]+),\s*([\d.]+),\s*([\d.]+),\s*([\d.]+),\s*(\d+)', txt):
        d, o, h, l, c, v = m.groups()
        out.append({'date': d, 'open': float(o), 'high': float(h), 'low': float(l),
                    'close': float(c), 'vol': int(v)})
    return out


def atr14(bars):
    """Wilder ATR(14). bars: 시간 오름차순"""
    if len(bars) < 15:
        return None
    trs = []
    for i in range(1, len(bars)):
        h, l, pc = bars[i]['high'], bars[i]['low'], bars[i - 1]['close']
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    atr = sum(trs[:14]) / 14
    for tr in trs[14:]:
        atr = (atr * 13 + tr) / 14
    return atr


def rsi14(bars):
    if len(bars) < 15:
        return None
    gains, losses = [], []
    for i in range(1, len(bars)):
        d = bars[i]['close'] - bars[i - 1]['close']
        gains.append(max(d, 0.0))
        losses.append(max(-d, 0.0))
    ag = sum(gains[:14]) / 14
    al = sum(losses[:14]) / 14
    for i in range(14, len(gains)):
        ag = (ag * 13 + gains[i]) / 14
        al = (al * 13 + losses[i]) / 14
    if al == 0:
        return 100.0
    rs = ag / al
    return 100 - 100 / (1 + rs)


def analyze(stock, end_date):
    bars = ohlc(stock['code'], end=end_date)
    if len(bars) < 61:
        return None
    closes = [b['close'] for b in bars]
    close = closes[-1]
    prev = closes[-2]
    a = atr14(bars[-60:])
    if not a or close <= 0:
        return None
    ma5 = sum(closes[-5:]) / 5
    ma20 = sum(closes[-20:]) / 20
    ma60 = sum(closes[-60:]) / 60
    return {
        **stock,
        'close': close,
        'chg': (close / prev - 1) * 100,
        'atr': a,
        'atr_pct': a / close * 100,
        'ma5': ma5, 'ma20': ma20, 'ma60': ma60,
        'align': close > ma5 > ma20 > ma60,
        'disp20': (close / ma20 - 1) * 100,
        'rsi': rsi14(bars[-60:]),
        'hi60': max(b['high'] for b in bars[-60:]),
        'lo60': min(b['low'] for b in bars[-60:]),
        'last_date': bars[-1]['date'],
    }


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    limit = int(args[0]) if args else 295
    end_date = args[1] if len(args) > 1 else None
    if end_date is None:
        import datetime
        end_date = datetime.date.today().strftime('%Y%m%d')

    mkt = 'KOSPI'
    for flag in ('--kosdaq', '--all'):
        if flag in sys.argv:
            mkt = flag[2:].upper()
    universe = market_cap_universe(limit, mkt)
    print(f'[universe] {mkt} {len(universe)}종목 수집 (기준일 {end_date})', file=sys.stderr)

    with ThreadPoolExecutor(max_workers=12) as ex:
        res = [r for r in ex.map(lambda s: analyze(s, end_date), universe) if r]

    res.sort(key=lambda x: x['atr_pct'])
    n = len(res)
    normal = [r for r in res if r['atr_pct'] <= 3]
    caution = [r for r in res if 3 < r['atr_pct'] <= 5]
    banned = [r for r in res if r['atr_pct'] > 5]
    aligned = [r for r in res if r['align']]
    avg = sum(r['atr_pct'] for r in res) / n
    med = sorted(r['atr_pct'] for r in res)[n // 2]

    print('=' * 62)
    print(f'  시장 전수 스크리닝 — 시총 상위 {n}종목 (기준일 {end_date})')
    print('=' * 62)
    print(f'  평균 ATR/주가 : {avg:.2f}%')
    print(f'  중앙값        : {med:.2f}%')
    print(f'  정상(3%이하)  : {len(normal):3d}종목 ({len(normal)/n*100:.1f}%)')
    print(f'  주의(3~5%)    : {len(caution):3d}종목 ({len(caution)/n*100:.1f}%)')
    print(f'  발간금지(5%↑) : {len(banned):3d}종목 ({len(banned)/n*100:.1f}%)')
    print(f'  5·20·60 정배열: {len(aligned)}종목')
    print('=' * 62)

    passed = [r for r in res if r['atr_pct'] <= 5 and r['align'] and -5 <= r['disp20'] <= 15]
    print(f'\n[3중 필터 통과] ATR 5%이하 + 정배열 + 20일선 이격도 -5~+15% : {len(passed)}종목\n')
    print(f'{"종목명":<22}{"코드":>8}{"종가":>12}{"등락률":>9}{"ATR%":>8}{"이격도":>9}{"RSI":>7}  시장')
    for r in passed:
        print(f'{r["name"][:20]:<22}{r["code"]:>8}{r["close"]:>12,.0f}{r["chg"]:>8.2f}%'
              f'{r["atr_pct"]:>7.2f}%{r["disp20"]:>8.2f}%{r["rsi"]:>7.1f}  {r["market"]}')

    if '--json' in sys.argv:
        out = sys.argv[sys.argv.index('--json') + 1]
        with open(out, 'w', encoding='utf-8') as f:
            json.dump({'summary': {'n': n, 'avg_atr': avg, 'median_atr': med,
                                   'normal': len(normal), 'caution': len(caution),
                                   'banned': len(banned), 'banned_pct': len(banned) / n * 100,
                                   'aligned': len(aligned), 'passed': len(passed)},
                       'stocks': res}, f, ensure_ascii=False)
        print(f'\n[saved] {out}', file=sys.stderr)


if __name__ == '__main__':
    main()
