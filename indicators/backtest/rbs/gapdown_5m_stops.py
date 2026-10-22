"""Big gap-down days, first up 5-minute bar after 09:45 (close > open, entry at its close, up to 12:00): where to put
the stop so it is smaller than the day's low? NQ cash-session 1m bars stand in for QQQ. Five years.

  cd indicators/backtest
  python3 -I rbs/gapdown_5m_stops.py [data/NQ_1m_5y.csv]

Stops (1 tick beyond):
  當天低點       the day's low so far (the rule as tested in gapdown_5m_green.py)
  訊號 5m 低點    the entry 5m bar's low
  兩根 5m 低點    the lower low of the entry 5m bar and the one before
  固定 0.15–0.3% fixed % below entry
  當天低點，最多 X%  the day's low, but at most X% below entry
Targets 1R / 2R, flat at 16:00, 1 point cost. Each cell: 1R (or 2R) win rate / net R; then stop median in points and
points per trade (per contract, after cost) so stops of different sizes can be compared.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import oos_check as oc
import gapdown_long as gl

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, '..', 'data', 'NQ_1m_5y.csv')
    one = gl.load(path); rows = []; prev = None
    for d, g in one.groupby('day', sort=True):
        o, h, l, c, m = g.open.values, g.high.values, g.low.values, g.close.values, g['min'].values
        if prev is not None:
            gap = 100 * (o[0] / prev - 1)
            if gap <= -0.5:
                k = None; pw = None
                for s0 in range(585, 720, 5):
                    w = np.flatnonzero((m >= s0) & (m < s0 + 5))
                    if len(w) < 5: pw = None; continue
                    if c[w[-1]] > o[w[0]]: k = w[-1]; break
                    pw = w
                if k is not None:
                    e = c[k]; w5 = np.arange(k - 4, k + 1); dl = l[:k + 1].min()
                    stops = {'當天低點': dl, '訊號 5m 低點': l[w5].min(),
                             '兩根 5m 低點': min(l[w5].min(), l[pw].min()) if pw is not None else l[w5].min()}
                    for p in (0.15, 0.2, 0.3): stops[f'固定 {p:g}%'] = e * (1 - p / 100)
                    for p in (0.2, 0.3): stops[f'當天低點，最多 {p:g}%'] = max(dl, e * (1 - p / 100))
                    for sk, st in stops.items():
                        st -= 0.25
                        if e - st <= 0: continue
                        risk, (r1, r2) = gl.trade(h, l, c, k, st, len(c), (e + (e - st), e + 2 * (e - st)))
                        rows.append(dict(date=d, gap=gap, stop=sk, risk=risk, r1=r1, r2=r2))
        prev = c[-1]
    t = pd.DataFrame(rows)
    for R in (1, 2): t[f'n{R}'] = t[f'r{R}'] - oc.COST / t.risk; t[f'p{R}'] = t[f'r{R}'] * t.risk - oc.COST
    yrs = list(oc.YEARS); yrs[-1] = (yrs[-1][0], yrs[-1][1], '2099-12-31')
    for gm in (-0.75, -1.0):
        print(f'\n缺口 ≤ {gm:g}%：09:45 後第一根 5 分 K 收漲，收盤買。每格：勝率 / 淨 R')
        print(f'   {"":<24}' + ''.join(f'{nm[:2] + " " + nm[3:8]:>15}' for nm, a, b in yrs) + f'{"合計":>15}{"筆":>5}{"停損中位":>8}{"每筆點數":>8}')
        for R in (1, 2):
            for sk in t.stop.unique():
                z = t[(t.stop == sk) & (t.gap <= gm)]
                cells = [z[(z.date >= a) & (z.date <= b)] for nm, a, b in yrs] + [z]
                print(f'   {sk + f" {R}R":<24}' + ''.join(f'{100 * (q[f"r{R}"] > 0).mean() if len(q) else 0:6.0f}% {q[f"n{R}"].sum():+5.1f}R' for q in cells)
                      + f'{len(z):5d}{z.risk.median():7.0f}點{z[f"p{R}"].mean():+7.1f}點', flush=True)
            print()


if __name__ == '__main__':
    main()
