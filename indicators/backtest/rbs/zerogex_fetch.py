"""Download ZeroGEX history for SPY / QQQ into data/zerogex/ (needs a ZeroGEX Pro API key; history starts 2026-06-29).

  cd indicators/backtest
  python3 -I rbs/zerogex_fetch.py "../../ZEROGEX API.txt" [range] [frames] [regime] [hourly] [syms=SPX,SPY,QQQ]

The key is read from the file given (keep it out of git). Writes, per symbol:
  zerogex/{SYM}_minute.csv   every minute (replay/range): ts (UTC, minute start), gamma_flip, call_wall, put_wall,
                             max_gamma_strike, and ZeroGEX's own 1-minute candle (open, high, low, close, volume)
  zerogex/{SYM}_frames.csv   every 30 minutes 09:30-15:30 ET and 15:59 (replay/frame summary): ts, spot, net_gex,
                             net_gex_at_spot, gamma_flip, call_wall, put_wall
  zerogex/{SYM}_regime.csv   per session (gex/regime-history): state, spot / gamma flip at the open and close
  zerogex/{SYM}_hourly.csv   hourly buckets incl. pre-market / after-hours (gex/historical, 1hour; rewritten each run):
                             ts (UTC, bucket start; the value is the last snapshot inside the hour, so use it from
                             ts + 1 hour), spot, gamma_flip, call_wall, put_wall, net_gex
Days already on disk are skipped, so it can be re-run to add new sessions. Stops on HTTP 429.
"""
import csv, json, os, sys, time, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

BASE = 'https://api.zerogex.io'
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, 'data', 'zerogex')
NY = ZoneInfo('America/New_York')
SYMS = ('SPY', 'QQQ')


def num(x):
    return '' if x is None else float(x)


class Api:
    def __init__(self, key_file):
        self.key = open(key_file, encoding='utf-8').read().strip()
        self.calls = 0

    def get(self, path):
        req = urllib.request.Request(BASE + path, headers={'Authorization': 'Bearer ' + self.key, 'Accept': 'application/json',
                                                           'User-Agent': 'remi-backtest'})
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=120) as r:
                    self.calls += 1
                    return json.loads(r.read().decode())
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    sys.exit(f'HTTP 429 (rate limit) after {self.calls} calls; run again later')
                if e.code == 404:
                    return None
                if attempt == 2: raise
            except (urllib.error.URLError, TimeoutError):
                if attempt == 2: raise
            time.sleep(3)


def done_dates(path, col):
    if not os.path.exists(path): return set()
    with open(path, newline='') as f:
        return {r[col][:10] for r in csv.DictReader(f)}


def append(path, header, rows):
    new = not os.path.exists(path)
    with open(path, 'a', newline='') as f:
        w = csv.writer(f)
        if new: w.writerow(header)
        w.writerows(rows)


def sessions(api, sym):
    js = api.get(f'/api/replay/sessions?symbol={sym}&limit=180')
    return sorted(s['date'] for s in js['sessions'])


def fetch_range(api, sym, days):
    path = os.path.join(OUT, f'{sym}_minute.csv'); have = done_dates(path, 'ts')
    hdr = ['ts', 'gamma_flip', 'call_wall', 'put_wall', 'max_gamma_strike', 'open', 'high', 'low', 'close', 'volume']
    for d in days:
        if d in have: continue
        js = api.get(f'/api/replay/range?symbol={sym}&date={d}&strike_band_pct=0.005')
        if not js: continue
        cd = {c['timestamp']: c for c in js.get('candles', [])}
        rows = []
        for fr in js.get('frames', []):
            c = cd.get(fr['timestamp'], {})
            rows.append([fr['timestamp'], num(fr.get('gamma_flip')), num(fr.get('call_wall')), num(fr.get('put_wall')),
                         num(fr.get('max_gamma_strike')), num(c.get('open')), num(c.get('high')), num(c.get('low')),
                         num(c.get('close')), num(c.get('volume'))])
        append(path, hdr, rows)
        print(f'  {sym} {d} 每分鐘 {len(rows)} 筆', flush=True)
        time.sleep(0.5)


def fetch_frames(api, sym, days):
    path = os.path.join(OUT, f'{sym}_frames.csv'); have = done_dates(path, 'ts')
    hdr = ['ts', 'spot', 'net_gex', 'net_gex_at_spot', 'gamma_flip', 'call_wall', 'put_wall']
    for d in days:
        if d in have: continue
        y, m, dd = map(int, d.split('-'))
        times = [datetime(y, m, dd, 9, 30, tzinfo=NY) + timedelta(minutes=30 * k) for k in range(13)]
        times.append(datetime(y, m, dd, 15, 59, tzinfo=NY))
        rows = []
        for t in times:
            ts = t.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
            js = api.get(f'/api/replay/frame?symbol={sym}&ts={ts}&strike_limit=10')
            if js and js.get('summary'):
                s = js['summary']
                rows.append([s['timestamp'], num(s.get('spot')), num(s.get('net_gex')), num(s.get('net_gex_at_spot')),
                             num(s.get('gamma_flip')), num(s.get('call_wall')), num(s.get('put_wall'))])
            time.sleep(0.3)
        append(path, hdr, rows)
        print(f'  {sym} {d} 抽樣 {len(rows)} 筆（累計呼叫 {api.calls} 次）', flush=True)


def fetch_regime(api, sym):
    js = api.get(f'/api/gex/regime-history?symbol={sym}&limit=180')
    path = os.path.join(OUT, f'{sym}_regime.csv')
    keys = ['session_date', 'state', 'adverb', 'magnitude', 'net_shift', 'spot_open', 'gamma_flip_open', 'spot_close', 'gamma_flip_close']
    with open(path, 'w', newline='') as f:
        w = csv.writer(f); w.writerow(keys)
        for s in sorted(js['sessions'], key=lambda x: x['session_date']):
            w.writerow([s.get(k) if k in ('session_date', 'state', 'adverb') else num(s.get(k)) for k in keys])
    print(f'  {sym} 每天的狀態 {len(js["sessions"])} 天')


def fetch_hourly(api, sym, start='2026-06-29'):
    path = os.path.join(OUT, f'{sym}_hourly.csv'); rows = {}; end = None
    while True:
        q = f'/api/gex/historical?symbol={sym}&timeframe=1hour&window_units=90&start_date={start}' + (f'&end_date={urllib.parse.quote(end)}' if end else '')
        js = api.get(q)
        b = js if isinstance(js, list) else (js or {}).get('data') or []
        new = [r for r in b if r.get('timestamp') and r['timestamp'] not in rows]
        if not new: break
        for r in new:
            rows[r['timestamp']] = [r['timestamp'], num(r.get('spot_price')), num(r.get('gamma_flip')), num(r.get('call_wall')),
                                    num(r.get('put_wall')), num(r.get('net_gex'))]
        end = min(r['timestamp'] for r in new)
        if end[:10] < start: break
    with open(path, 'w', newline='') as f:
        w = csv.writer(f); w.writerow(['ts', 'spot', 'gamma_flip', 'call_wall', 'put_wall', 'net_gex'])
        for k in sorted(rows): w.writerow(rows[k])
    print(f'  {sym} 每小時 {len(rows)} 筆（{min(rows)[:10] if rows else "-"} .. {max(rows)[:10] if rows else "-"}）')


def main():
    api = Api(sys.argv[1])
    args = sys.argv[2:]
    syms = [a.split('=', 1)[1].upper() for a in args if a.startswith('syms=')]
    syms = syms[0].split(',') if syms else list(SYMS)
    what = {a for a in args if not a.startswith('syms=')} or {'range', 'frames', 'regime'}
    os.makedirs(OUT, exist_ok=True)
    now = datetime.now(NY); today = now.strftime('%Y-%m-%d')
    done_today = now.hour * 60 + now.minute >= 16 * 60 + 5                     # today's session is over after 16:05 ET
    for sym in syms:
        days = [d for d in sessions(api, sym) if d < today or (d == today and done_today)]   # finished sessions only
        if 'hourly' in what: fetch_hourly(api, sym)
        if 'regime' in what: fetch_regime(api, sym)
        if 'range' in what: fetch_range(api, sym, days)
        if 'frames' in what: fetch_frames(api, sym, days)
    print(f'完成，API 呼叫 {api.calls} 次')


if __name__ == '__main__':
    main()
