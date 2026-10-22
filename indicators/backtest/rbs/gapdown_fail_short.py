"""Remi 大低開買 failed -> short the break of the day's low? NQ cash-session 1m bars stand in for QQQ. Five years.

  cd indicators/backtest
  python3 -I rbs/gapdown_fail_short.py [data/NQ_1m_5y.csv]

Days with a gap down (<= -1.1% as the indicator, also -0.75%) where the 大低開買 long fired (first up 5m bar after
09:45, stop at the day's low). If the price later breaks that low (the long is stopped) before the cutoff, short:
  觸價空   a sell stop at the day's low - 1 tick (filled when touched)
  收破空   the first 1m close below the low, entry at that close
Stops: the long's entry price (risk = the long's risk), or the midpoint between the low and that entry.
Targets 1R / 2R / 3R, flat at 16:00, 1 point cost. Each cell: win rate / net R / trades.
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
            k = None
            if gap <= -0.75:
                for s0 in range(585, 720, 5):
                    w = np.flatnonzero((m >= s0) & (m < s0 + 5))
                    if len(w) < 5: continue
                    if c[w[-1]] > o[w[0]]: k = w[-1]; break
            if k is not None:
                low = l[:k + 1].min(); le = c[k]
                for cut in (720, 900):
                    for mode in ('觸價空', '收破空'):
                        q = None
                        for j in range(k + 1, len(c)):
                            if m[j] >= cut: break
                            if mode == '觸價空' and l[j] <= low - 0.25: q = j; e = low - 0.25; break
                            if mode == '收破空' and c[j] < low: q = j; e = c[j]; break
                        if q is None: continue
                        for sk, st in (('多單進場價', le), ('一半', (le + low) / 2)):
                            risk = st - e
                            if risk <= 0: continue
                            res = {}
                            for R in (1, 2, 3):
                                tp = e - R * risk; r = None
                                start = q if mode == '收破空' else q            # touch: the entry bar may also hit the stop
                                for j in range(q + (1 if mode == '收破空' else 0), len(c)):
                                    if h[j] >= st and not (mode == '觸價空' and j == q and o[j] < st): r = -1.0; break
                                    if l[j] <= tp and j > q: r = float(R); break
                                res[R] = r if r is not None else (e - c[-1]) / risk
                            rows.append(dict(date=d, gap=gap, cut=cut, mode=mode, stop=sk, risk=risk, entry=m[q],
                                             **{f'r{R}': res[R] for R in (1, 2, 3)}, **{f'n{R}': res[R] - oc.COST / risk for R in (1, 2, 3)}))
        prev = c[-1]
    t = pd.DataFrame(rows)
    yrs = list(oc.YEARS); yrs[-1] = (yrs[-1][0], yrs[-1][1], '2099-12-31')
    print(f'{os.path.basename(path)}：大低開買之後跌破當天低點就空。每格：勝率 / 淨 R / 筆數')
    print(f'   {"":<36}' + ''.join(f'{nm[:2] + " " + nm[3:8]:>17}' for nm, a, b in yrs) + f'{"合計":>17}{"停損中位":>8}')
    for gm in (-1.1, -0.75):
        for cut in (720, 900):
            for mode in ('觸價空', '收破空'):
                for sk in ('多單進場價', '一半'):
                    z = t[(t.gap <= gm) & (t.cut == cut) & (t['mode'] == mode) & (t.stop == sk)]
                    for R in (1, 2, 3):
                        cells = [z[(z.date >= a) & (z.date <= b)] for nm, a, b in yrs] + [z]
                        lab = f'≤{gm:g}% {cut // 60}點前 {mode} 停{sk} {R}R'
                        print(f'   {lab:<36}' + ''.join(f'{100 * (q[f"r{R}"] > 0).mean() if len(q) else 0:5.0f}% {q[f"n{R}"].sum():+5.1f}R {len(q):2d}' for q in cells)
                              + f'{z.risk.median():7.0f}點')
            print()


if __name__ == '__main__':
    main()
