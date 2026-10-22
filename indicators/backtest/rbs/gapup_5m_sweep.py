"""Mirror of Remi 大低開買 on gap-up days: gap up >= X%, after 09:45 the first 5-minute bar that closes down
(close < open) -> short at its close, stop at the day's high so far (1 tick above), 1R / 2R, flat at 16:00.
NQ cash-session 1m bars stand in for QQQ. Five years.

  cd indicators/backtest
  python3 -I rbs/gapup_5m_sweep.py [data/NQ_1m_5y.csv]

Per threshold and per year: 1R win rate / net R / trades, yearly win-rate range, 2R; gap bands; split by whether the
entry is still above the open; and the control (no gap up).
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import oos_check as oc
import gapdown_long as gl

HERE = os.path.dirname(os.path.abspath(__file__))


def short_trade(h, l, c, k, stop, end, targets):
    e = c[k]; risk = stop - e; out = []
    for tgt in targets:
        r = None
        for q in range(k + 1, end):
            if h[q] >= stop: r = -1.0; break
            if l[q] <= tgt: r = (e - tgt) / risk; break
        out.append(r if r is not None else (e - c[end - 1]) / risk)
    return risk, out


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, '..', 'data', 'NQ_1m_5y.csv')
    one = gl.load(path); rows = []; prev = None
    for d, g in one.groupby('day', sort=True):
        o, h, l, c, m = g.open.values, g.high.values, g.low.values, g.close.values, g['min'].values
        if prev is not None:
            for s0 in range(585, 720, 5):
                w = np.flatnonzero((m >= s0) & (m < s0 + 5))
                if len(w) < 5: continue
                if c[w[-1]] < o[w[0]]:
                    k = w[-1]; e = c[k]; st = h[:k + 1].max() + 0.25
                    risk, (r1, r2) = short_trade(h, l, c, k, st, len(c), (e - (st - e), e - 2 * (st - e)))
                    rows.append(dict(date=d, gap=100 * (o[0] / prev - 1), risk=risk, above=e > o[0], r1=r1, r2=r2,
                                     n1=r1 - oc.COST / risk, n2=r2 - oc.COST / risk))
                    break
        prev = c[-1]
    t = pd.DataFrame(rows)
    yrs = list(oc.YEARS); yrs[-1] = (yrs[-1][0], yrs[-1][1], '2099-12-31')
    print(f'{os.path.basename(path)}：大高開，09:45 後第一根 5 分 K 收跌，收盤做空，停損當天高點。每格：1R 勝率 / 淨 R / 筆數')
    print(f'   {"":<22}' + ''.join(f'{nm[:2] + " " + nm[3:8]:>17}' for nm, a, b in yrs) + f'{"合計":>17}{"各年勝率":>10}{"2R 合計":>14}{"停損中位":>8}')

    def row(lab, z):
        ys = [z[(z.date >= a) & (z.date <= b)] for nm, a, b in yrs]
        wr = [100 * (q.r1 > 0).mean() for q in ys if len(q)]
        print(f'   {lab:<22}' + ''.join(f'{100 * (q.r1 > 0).mean() if len(q) else 0:5.0f}% {q.n1.sum():+5.1f}R {len(q):2d}' for q in ys + [z])
              + f'{min(wr):6.0f}–{max(wr):.0f}%{100 * (z.r2 > 0).mean():8.0f}% {z.n2.sum():+5.1f}R{z.risk.median():6.0f}點', flush=True)

    for x in (0.3, 0.5, 0.75, 0.9, 1.0, 1.1, 1.25, 1.5):
        row(f'高開 ≥ {x:g}%', t[t.gap >= x])
    print()
    for a, b in ((0.3, 0.5), (0.5, 0.75), (0.75, 1.0), (1.0, 1.5), (1.5, 9)):
        row(f'{a:g}–{b:g}%' if b < 9 else f'≥ {a:g}%', t[(t.gap >= a) & (t.gap < b)])
    print()
    for x in (0.75, 1.0):
        row(f'≥ {x:g}%、還在開盤價上', t[(t.gap >= x) & t.above]); row(f'≥ {x:g}%、已跌破開盤價', t[(t.gap >= x) & ~t.above])
    row('對照：高開 < 0.3%', t[t.gap < 0.3])


if __name__ == '__main__':
    main()
