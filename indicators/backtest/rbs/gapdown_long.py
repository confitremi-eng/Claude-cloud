"""QQQ 低開高走 (gap down, then up): which confirmation after a gap-down open is worth a long? NQ cash-session bars
stand in for QQQ, as in the other QQQ studies.

  cd indicators/backtest
  python3 -I rbs/gapdown_long.py [data.csv]        # default: $NQ_DATA or data/NQ_1m_databento.csv; works on NQ_1m_5y.csv

Day = weekday 09:30-16:00 ET bars (days with fewer than 300 bars skipped: holidays, half days). Gap = 09:30 open vs the
previous day's 15:59 close, % of price. The narrow version (first candle closes green, entry at its close) is in
rth_open_gap.py and has no edge; here the entry waits for a confirmation, longs only, entry from 09:45 to 12:00:
  ORB 5 / 15 / 30   first 1m close above the high of the first 5 / 15 / 30 minutes
  收復開盤價        first 1m close above the day's open after trading below it
  收復 VWAP         first 1m close above the session VWAP after at least 15 minutes below it
Stop = the day's low so far (1 tick below), targets 1R / 2R and the gap fill (previous close), flat at 16:00, 1 point
cost. The same rules on days without a gap down are the control: a setup is only a gap-down setup if it is better there.
Prints
  1. gap-down days: how often the gap fills, and when the low of the day comes
  2. each setup x gap size, against the control
  3. per half (1-year file) or per year (5-year file) for gap <= -0.5%
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import setup_study as ss

HERE = os.path.dirname(os.path.abspath(__file__))
COST = 1.0
GAPS = (0.0, -0.3, -0.5, -0.75, -1.0)          # gap <= these % (0.0 = any gap down)
SETUPS = ('ORB 5', 'ORB 15', 'ORB 30', '收復開盤價', '收復 VWAP')


def load(path):
    one = pd.read_csv(path, parse_dates=['datetime']).set_index('datetime').sort_index()
    ny = one.index.tz_convert(ss.NY)
    m = ny.hour * 60 + ny.minute
    one = one[(ny.weekday < 5) & (m >= 570) & (m < 960)].copy()
    ny = one.index.tz_convert(ss.NY)
    one['day'] = ny.strftime('%Y-%m-%d'); one['min'] = ny.hour * 60 + ny.minute
    n = one.groupby('day').size()
    return one[one.day.isin(n[n >= 300].index)]


def trade(h, l, c, k, stop, end, targets):
    """R for each target from entry at close k, stop first when both are in one bar, flat at bar end."""
    e = c[k]; risk = e - stop; out = []
    for tgt in targets:
        r = None
        for q in range(k + 1, end):
            if l[q] <= stop: r = -1.0; break
            if h[q] >= tgt: r = (tgt - e) / risk; break
        out.append(r if r is not None else (c[end - 1] - e) / risk)
    return risk, out


def day_rows(g, prev_close):
    o, h, l, c, v, mins = (g[x].values for x in ('open', 'high', 'low', 'close', 'volume', 'min'))
    n = len(c); op = o[0]; gap = 100 * (op - prev_close) / prev_close
    tp = (h + l + c) / 3; vw = np.cumsum(tp * v) / np.maximum(np.cumsum(v), 1)
    lod = np.minimum.accumulate(l)
    rows = []
    for name in SETUPS:
        k = None
        if name.startswith('ORB'):
            w = int(name.split()[1]); orh = h[:w].max()
            for q in range(w, n):
                if mins[q] >= 720: break
                if mins[q] >= 584 and c[q] > orh: k = q; break
        elif name == '收復開盤價':
            below = False
            for q in range(n):
                if mins[q] >= 720: break
                if c[q] < op: below = True
                elif below and mins[q] >= 584 and c[q] > op: k = q; break
        else:
            run = 0
            for q in range(n):
                if mins[q] >= 720: break
                if c[q] < vw[q]: run += 1
                elif run >= 15 and mins[q] >= 584 and c[q] > vw[q]: k = q; break
                else: run = 0
        if k is None: continue
        stop = lod[k] - 0.25
        if c[k] - stop <= 0: continue
        risk, (r1, r2, rf) = trade(h, l, c, k, stop, n, (c[k] + (c[k] - stop), c[k] + 2 * (c[k] - stop), max(prev_close, c[k] + 0.25)))
        rows.append(dict(setup=name, gap=gap, risk=risk, entry=mins[k], r1=r1, r2=r2, rf=rf, fill_tgt=prev_close > c[k]))
    return rows, dict(gap=gap, fill=h.max() >= prev_close, low_min=mins[int(np.argmin(l))])


def build(one):
    rows, days = [], []
    prev = None
    for d, g in one.groupby('day', sort=True):
        if prev is not None:
            rs, info = day_rows(g, prev)
            for r in rs: r['date'] = d
            rows += rs; info['date'] = d; days.append(info)
        prev = g.close.values[-1]
    t = pd.DataFrame(rows)
    for col, R in (('r1', 'n1'), ('r2', 'n2'), ('rf', 'nf')): t[R] = t[col] - COST / t.risk
    return t, pd.DataFrame(days)


def stats(z):
    if len(z) < 5: return f'{len(z):4d} 筆'
    return (f'{len(z):4d} 筆  1R 勝 {100 * (z.r1 > 0).mean():3.0f}% 每筆 {z.n1.mean():+.2f}R  2R 勝 {100 * (z.r2 > 0).mean():3.0f}% 每筆 {z.n2.mean():+.2f}R'
            f'  補缺口目標 每筆 {z.nf[z.fill_tgt].mean() if z.fill_tgt.any() else np.nan:+.2f}R  停損中位 {z.risk.median():.0f} 點')


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else os.environ.get('NQ_DATA', os.path.join(HERE, '..', 'data', 'NQ_1m_databento.csv'))
    one = load(path)
    t, D = build(one)
    yrs = sorted({d[:4] for d in D.date})
    print(f'{os.path.basename(path)}：{len(D)} 個交易日（{D.date.min()} .. {D.date.max()}），一次只看每天每個 setup 的第一個訊號，扣 {COST:g} 點')

    print('\n######## 1. 低開的日子')
    for gmax in GAPS[1:]:
        x = D[D.gap <= gmax]
        if not len(x): continue
        print(f'  缺口 ≤ {gmax:g}%：{len(x):3d} 天，當天回補昨收 {100 * x.fill.mean():3.0f}%，'
              f'當天最低點在 10:00 前 {100 * (x.low_min < 600).mean():3.0f}%、11:00 前 {100 * (x.low_min < 660).mean():3.0f}%')
    x = D[D.gap > -0.3]
    print(f'  對照：缺口 > −0.3% 的 {len(x)} 天，最低點在 10:00 前 {100 * (x.low_min < 600).mean():3.0f}%')

    print('\n######## 2. 各 setup × 缺口大小（09:45–12:00 進場，停損當天低點，16:00 平倉）')
    for s in SETUPS:
        z = t[t.setup == s]
        print(f'\n  {s}')
        print(f'    對照：沒有低開（缺口 > −0.3%）  {stats(z[z.gap > -0.3])}')
        for gmax in GAPS:
            print(f'    缺口 ≤ {gmax:5g}%              {stats(z[z.gap <= gmax])}')

    split = len(yrs) <= 2
    print('\n######## 3. 缺口 ≤ −0.5%，' + ('前後半年' if split else '各年'))
    mid = D.date.iloc[len(D) // 2]
    for s in SETUPS:
        z = t[(t.setup == s) & (t.gap <= -0.5)]
        parts = [('前半', z[z.date < mid]), ('後半', z[z.date >= mid])] if split else [(y, z[z.date.str[:4] == y]) for y in yrs]
        print(f'  {s:<10}' + '  '.join(f'{nm} {len(p)} 筆 1R {100 * (p.r1 > 0).mean() if len(p) else 0:3.0f}% {p.n1.sum():+5.1f}R' for nm, p in parts))


if __name__ == '__main__':
    main()
