"""Big gap-down days: after 09:45, buy the close of the first 5-minute bar that closes green; stop at the day's low.
NQ cash-session 1m bars stand in for QQQ. Five years.

  cd indicators/backtest
  python3 -I rbs/gapdown_5m_green.py [data/NQ_1m_5y.csv] [bar minutes, default 5]

5-minute bars from the 1m bars (09:45-09:50, 09:50-09:55, ...). The first one with close > open is the entry (at its
close), up to 12:00. Stop = the day's low so far, 1 tick below. Targets 1R / 1.5R / 2R, flat at 16:00, 1 point cost, one
per day. Gap = 09:30 open vs the previous 15:59 close. Rows: gap <= -0.75% (Remi's rule), -0.5%, -1%, and the control
(gap > -0.3%). Years as in oos_check. Each cell: win rate / net R / trades.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import oos_check as oc
import gapdown_long as gl

HERE = os.path.dirname(os.path.abspath(__file__))
RS = (1.0, 1.5, 2.0)


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, '..', 'data', 'NQ_1m_5y.csv')
    B = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    one = gl.load(path); rows = []; prev = None
    for d, g in one.groupby('day', sort=True):
        o, h, l, c, m = g.open.values, g.high.values, g.low.values, g.close.values, g['min'].values
        if prev is not None:
            for s0 in range(585, 720, B):
                w = np.flatnonzero((m >= s0) & (m < s0 + B))
                if len(w) < B: continue
                k = w[-1]
                if c[k] > o[w[0]]:
                    stop = l[:k + 1].min() - 0.25; e = c[k]
                    risk, rs = gl.trade(h, l, c, k, stop, len(c), [e + R * (e - stop) for R in RS])
                    rows.append(dict(date=d, gap=100 * (o[0] / prev - 1), risk=risk, entry=s0 + B, below_open=e < o[0],
                                     **{f'r{R:g}': r for R, r in zip(RS, rs)}, **{f'n{R:g}': r - oc.COST / risk for R, r in zip(RS, rs)}))
                    break
        prev = c[-1]
    t = pd.DataFrame(rows)
    yrs = list(oc.YEARS); yrs[-1] = (yrs[-1][0], yrs[-1][1], '2099-12-31')
    print(f'{os.path.basename(path)}：09:45 後第一根 {B} 分 K 收紅，收盤買，停損當天低點。每格：勝率 / 淨 R / 筆數')
    print(f'   {"":<30}' + ''.join(f'{nm[:2] + " " + nm[3:8]:>19}' for nm, a, b in yrs) + f'{"合計":>19}{"停損中位":>9}')
    groups = (('缺口 ≤ −0.75%', t.gap <= -0.75), ('缺口 ≤ −0.5%', t.gap <= -0.5), ('缺口 ≤ −1%', t.gap <= -1.0),
              ('≤ −0.75%、進場還在開盤價下', (t.gap <= -0.75) & t.below_open), ('≤ −0.75%、進場已在開盤價上', (t.gap <= -0.75) & ~t.below_open),
              ('對照：缺口 > −0.3%', t.gap > -0.3))
    for lab, mk in groups:
        z = t[mk]
        for R in RS:
            cells = [z[(z.date >= a) & (z.date <= b)] for nm, a, b in yrs] + [z]
            print(f'   {lab + f" {R:g}R":<30}' + ''.join(f'{100 * (q[f"r{R:g}"] > 0).mean() if len(q) else 0:6.0f}% {q[f"n{R:g}"].sum():+5.1f}R {len(q):3d}' for q in cells)
                  + f'{z.risk.median():7.0f}點')
        print()
    z = t[t.gap <= -0.75]
    print('缺口 ≤ −0.75% 的進場時間分布：', z.entry.map(lambda x: f'{x // 60}:{x % 60:02d}').value_counts().sort_index().head(8).to_dict())
    print(f'10/20 那天：', t[t.date == '2026-10-20'][['gap', 'entry', 'risk', 'r1', 'r2']].to_dict('records'))


if __name__ == '__main__':
    main()
