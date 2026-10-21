"""Win-rate log for a bought TradingView indicator (no source code), from chart-data exports.

  cd indicators/backtest
  python3 -I rbs/bought_signal_log.py "TAIFEX_TXF1!, 2_xxxxx.csv" [更多匯出檔 ...] [--cols Chars=🍦,Chars.1=🦀] [--cost 2]
  python3 -I rbs/bought_signal_log.py --mkt nq "CME_MINI_NQ1!, 2_xxxxx.csv" ...      # NQ: cost 1, 美股盤 / 夜盤

Each export is a TradingView "匯出圖表數據" CSV (UNIX time) with only the bought indicator on the chart; its
plotchar columns are 0/1 per bar. Exports are merged by bar time (a later file wins), so new exports just extend
the log. A signal seen in an earlier export but missing from a later export that covers its bar is marked
消失 (the indicator repainted it).

Every signal is a long (搶反彈) entered at the signal bar's close. Stops: 30 points, 50 points, 1 ATR(14), and the
user's rule (low of the signal bar and the bar before, at least 1 ATR). Price must reach 1 / 1.5 / 2 / 3R before
the stop; when one bar touches both, the stop counts first. Exits after 60 bars or at the session end (a gap
longer than 30 minutes). Cost is TXF points per round trip.

Writes signal_log/txf_bought.csv (or nq_bought.csv) (one row per signal, Excel-readable) and prints the summary.
"""
import sys, os, argparse
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, 'signal_log', '{}_bought.csv')
RS = (1, 1.5, 2, 3)
MAX_BARS = 60


def load(path, cols):
    d = pd.read_csv(path)
    d['t'] = pd.to_datetime(d.time, unit='s') + pd.Timedelta(hours=8)   # Taipei, bar open as on the chart
    keep = ['t', 'open', 'high', 'low', 'close'] + [c for c in cols if c in d.columns]
    missing = [c for c in cols if c not in d.columns]
    if missing:
        sys.exit(f'{os.path.basename(path)} 沒有欄位 {missing}，欄位有：{list(d.columns)}')
    return d[keep]


def part(t, mkt):
    """Session of a Taipei bar time: NQ 美股盤 = 09:30-16:00 New York, TXF 日盤 = 08:45-13:45."""
    if mkt == 'nq':
        ny = t.tz_localize('Asia/Taipei').tz_convert('America/New_York')
        return '美股盤' if 570 <= ny.hour * 60 + ny.minute < 960 else '夜盤'
    return '日盤' if 8 <= t.hour < 14 else '夜盤'


def stops(bars, i, atr):
    two_low = min(bars.low.iat[i], bars.low.iat[i - 1]) if i else bars.low.iat[i]
    e = bars.close.iat[i]
    return {'30點': 30.0, '50點': 50.0, '1ATR': atr[i], '兩根K': max(e - two_low, atr[i])}


def walk(bars, sess, i, dist, cost):
    """Highest R level reached before the stop, and fixed-target results in R after cost."""
    e = bars.close.iat[i]
    stop = e - dist
    best, hit_stop, end = 0.0, False, i
    res = {}
    open_k = set(RS)
    for j in range(i + 1, min(i + 1 + MAX_BARS, len(bars))):
        if sess[j] != sess[i]:
            break
        end = j
        if bars.low.iat[j] <= stop:
            hit_stop = True
            for k in open_k:
                res[k] = -1.0
            break
        up = (bars.high.iat[j] - e) / dist
        for k in sorted(open_k):
            if up >= k:
                res[k] = float(k)
                open_k.discard(k)
        best = max(best, up)
        if not open_k:
            break
    # the data running out is not an exit: the trade is still open
    done = hit_stop or not open_k or end - i >= MAX_BARS or (end + 1 < len(bars) and sess[end + 1] != sess[i])
    for k in open_k:
        res[k] = (bars.close.iat[end] - e) / dist   # time / session exit
    c = cost / dist
    return best, hit_stop, done, {k: v - c for k, v in res.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('files', nargs='+')
    ap.add_argument('--cols', default='Chars=🍦,Chars.1=🦀')
    ap.add_argument('--mkt', choices=('txf', 'nq'), default='txf')
    ap.add_argument('--cost', type=float)
    a = ap.parse_args()
    cols = dict(x.split('=') for x in a.cols.split(','))
    if a.cost is None:
        a.cost = 1.0 if a.mkt == 'nq' else 2.0
    out = OUT.format(a.mkt)
    parts = ('美股盤', '夜盤') if a.mkt == 'nq' else ('日盤', '夜盤')

    frames, seen = [], []
    for n, f in enumerate(a.files):
        d = load(f, cols)
        d['src'] = n
        frames.append(d)
        for c, sym in cols.items():
            for t in d.t[d[c] == 1]:
                seen.append((t, sym, n))
    bars = (pd.concat(frames).sort_values(['t', 'src']).drop_duplicates('t', keep='last')
            .reset_index(drop=True))
    gap = bars.t.diff().dt.total_seconds().fillna(1e9) > 30 * 60
    sess = gap.cumsum().values
    pc = bars.close.shift()
    tr = np.maximum(bars.high - bars.low, np.maximum((bars.high - pc).abs(), (bars.low - pc).abs()))
    atr = tr.ewm(alpha=1 / 14, adjust=False).mean().values
    idx = {t: i for i, t in enumerate(bars.t)}

    sig = pd.DataFrame(seen, columns=['t', 'sym', 'src']).groupby(['t', 'sym']).src.agg(list).reset_index()
    rows = []
    for _, s in sig.iterrows():
        first = s.src[0]
        later = [n for n, d in enumerate(frames) if n > first and d.t.iat[0] <= s.t <= d.t.iat[-1]]
        gone = [n for n in later if n not in s.src]
        i = idx[s.t]
        o, c = bars.open.iat[i], bars.close.iat[i]
        r = {'訊號K(台北)': s.t.strftime('%Y-%m-%d %H:%M'), '符號': s.sym,
             'K棒': '陽' if c > o else '陰' if c < o else '平',
             '盤別': part(s.t, a.mkt), '進場(收盤)': c,
             'ATR': round(atr[i], 1), '狀態': '消失' if gone else '有效',
             '首次出現': os.path.basename(a.files[first])}
        f = bars.iloc[i + 1:i + 31]
        r['30根內最多賺'] = f.high.max() - bars.close.iat[i] if len(f) else np.nan
        r['30根內最多虧'] = bars.close.iat[i] - f.low.min() if len(f) else np.nan
        for name, dist in stops(bars, i, atr).items():
            best, hit, done, res = walk(bars, sess, i, dist, a.cost)
            r[f'{name}停損點數'] = round(dist, 1)
            r[f'{name}最多到幾R'] = round(best, 2)
            r[f'{name}結果'] = ('未完成' if not done else '停損' if hit else '時間出場') if best < 1 else \
                f'先到{max(k for k in RS if best >= k)}R'
            for k in RS:
                r[f'{name}_{k}R'] = round(res[k], 3) if done or best >= k else np.nan   # a reached target is final
        rows.append(r)
    log = pd.DataFrame(rows).sort_values('訊號K(台北)')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    log.to_csv(out, index=False, encoding='utf-8-sig')

    ok = log[log.狀態 == '有效']
    print(f'K 線 {bars.t.iat[0]:%Y-%m-%d %H:%M} .. {bars.t.iat[-1]:%Y-%m-%d %H:%M}（台北），'
          f'訊號 {len(log)} 個，消失 {(log.狀態 == "消失").sum()} 個；全部當作做多，成本 {a.cost:g} 點')
    groups = [('全部', ok)]
    for s in cols.values():
        groups.append((s, ok[ok.符號 == s]))
        for k in ('陽', '陰'):
            g = ok[(ok.符號 == s) & (ok.K棒 == k)]
            if 0 < len(g) < (ok.符號 == s).sum():         # only when the symbol comes in both colours
                groups.append((f'{s} {k}線', g))
    groups += [(p, ok[ok.盤別 == p]) for p in parts]
    for grp, g in groups:
        print(f'\n== {grp}（{len(g)} 筆）')
        print(f'{"停損":<6}{"平均點數":>8}  {"1R 命中":>8}{"1.5R 命中":>10}{"2R 命中":>8}{"3R 命中":>8}   '
              f'{"每筆R: 1R":>9}{"1.5R":>7}{"2R":>7}{"3R":>7}')
        for name in ('30點', '50點', '1ATR', '兩根K'):
            h = g[g[f'{name}結果'] != '未完成']
            if not len(h):
                continue
            hit = [(h[f'{name}最多到幾R'] >= k).mean() for k in RS]
            ev = [h[f'{name}_{k}R'].mean() for k in RS]
            print(f'{name:<6}{h[f"{name}停損點數"].mean():>8.0f}  ' + ''.join(f'{x:>9.0%}' for x in hit) +
                  '   ' + ''.join(f'{x:>+8.2f}' for x in ev))
    print(f'\n紀錄：{out}')


if __name__ == '__main__':
    main()
