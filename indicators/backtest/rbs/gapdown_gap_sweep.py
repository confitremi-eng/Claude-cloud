"""Remi 大低開買 (first up 5m bar after 09:45, stop at the day's low): which gap threshold gives the steadiest win rate?
NQ cash-session 1m bars stand in for QQQ. Five years.

  cd indicators/backtest
  python3 -I rbs/gapdown_gap_sweep.py [data/NQ_1m_5y.csv]

Per threshold (gap <= -X%) and per year: 1R win rate / net R / trades; then the spread of the yearly win rates (min-max)
and 2R. Also gap bands (e.g. -1% .. -0.75%) to see where the edge sits.
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
        if prev is not None and o[0] < prev:
            for s0 in range(585, 720, 5):
                w = np.flatnonzero((m >= s0) & (m < s0 + 5))
                if len(w) < 5: continue
                if c[w[-1]] > o[w[0]]:
                    k = w[-1]; e = c[k]; st = l[:k + 1].min() - 0.25
                    risk, (r1, r2) = gl.trade(h, l, c, k, st, len(c), (e + (e - st), e + 2 * (e - st)))
                    rows.append(dict(date=d, gap=100 * (o[0] / prev - 1), risk=risk, r1=r1, r2=r2, n1=r1 - oc.COST / risk, n2=r2 - oc.COST / risk))
                    break
        prev = c[-1]
    t = pd.DataFrame(rows)
    yrs = list(oc.YEARS); yrs[-1] = (yrs[-1][0], yrs[-1][1], '2099-12-31')
    print(f'{os.path.basename(path)}：09:45 後第一根 5 分 K 收漲，停損當天低點。每格：1R 勝率 / 淨 R / 筆數')
    print(f'   {"":<16}' + ''.join(f'{nm[:2] + " " + nm[3:8]:>17}' for nm, a, b in yrs) + f'{"合計":>17}{"各年勝率範圍":>12}{"2R 合計":>14}')

    def row(lab, z):
        ys = [z[(z.date >= a) & (z.date <= b)] for nm, a, b in yrs]
        wr = [100 * (q.r1 > 0).mean() for q in ys if len(q)]
        print(f'   {lab:<16}' + ''.join(f'{100 * (q.r1 > 0).mean() if len(q) else 0:5.0f}% {q.n1.sum():+5.1f}R {len(q):2d}' for q in ys + [z])
              + f'{min(wr):7.0f}–{max(wr):.0f}%{100 * (z.r2 > 0).mean():8.0f}% {z.n2.sum():+5.1f}R', flush=True)

    for x in (0.3, 0.5, 0.6, 0.75, 0.9, 1.0, 1.1, 1.25, 1.5, 2.0):
        row(f'低開 ≥ {x:g}%', t[t.gap <= -x])
    print()
    for a, b in ((0.3, 0.5), (0.5, 0.75), (0.75, 1.0), (1.0, 1.5), (1.5, 9)):
        row(f'{a:g}–{b:g}%' if b < 9 else f'≥ {a:g}%', t[(t.gap <= -a) & (t.gap > -b)])


if __name__ == '__main__':
    main()
