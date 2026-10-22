"""Big gap-down days: just buy at 09:45? NQ cash-session 1m bars stand in for QQQ. Five years.

  cd indicators/backtest
  python3 -I rbs/gapdown_945.py [data/NQ_1m_5y.csv]

Entry at the close of the 09:44 bar (09:45). Stops: the day's low so far (1 tick below) or a fixed 0.4% (about QQQ's
usual 09:45 range). Targets 1R / 2R, flat at 16:00, 1 point cost. Gap = 09:30 open vs the previous 15:59 close. Extra
rows: only when 09:45 is still below the open (still falling) / already above it. Control: days without a gap down.
Years as in oos_check. Each cell: win rate / net R / trades.
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
        h, l, c, m = g.high.values, g.low.values, g.close.values, g['min'].values
        if prev is not None and (m == 584).any():
            k = int(np.argmax(m == 584)); op = g.open.values[0]; e = c[k]
            for sk, stop in (('當天低點', l[:k + 1].min() - 0.25), ('固定 0.4%', e * 0.996)):
                risk, (r1, r2) = gl.trade(h, l, c, k, stop, len(c), (e + (e - stop), e + 2 * (e - stop)))
                rows.append(dict(date=d, gap=100 * (op / prev - 1), stop=sk, risk=risk, below=e < op, r1=r1, r2=r2,
                                 n1=r1 - oc.COST / risk, n2=r2 - oc.COST / risk))
        prev = g.close.values[-1]
    t = pd.DataFrame(rows)
    yrs = list(oc.YEARS); yrs[-1] = (yrs[-1][0], yrs[-1][1], '2099-12-31')
    print(f'{os.path.basename(path)}：09:45 收盤買，16:00 平倉。每格：勝率 / 淨 R / 筆數')
    print(f'   {"":<36}' + ''.join(f'{nm[:2] + " " + nm[3:8]:>19}' for nm, a, b in yrs) + f'{"合計":>19}{"停損中位":>8}')
    for sk in ('當天低點', '固定 0.4%'):
        print(f'\n停損：{sk}')
        z0 = t[t.stop == sk]
        for lab, z in (('缺口 ≤ −0.3%', z0[z0.gap <= -0.3]), ('缺口 ≤ −0.5%', z0[z0.gap <= -0.5]), ('缺口 ≤ −0.75%', z0[z0.gap <= -0.75]),
                       ('缺口 ≤ −0.5%，09:45 還在開盤價下', z0[(z0.gap <= -0.5) & z0.below]), ('缺口 ≤ −0.5%，09:45 已在開盤價上', z0[(z0.gap <= -0.5) & ~z0.below]),
                       ('對照：缺口 > −0.3%', z0[z0.gap > -0.3])):
            for R in (1, 2):
                cells = [z[(z.date >= a) & (z.date <= b)] for nm, a, b in yrs] + [z]
                print(f'   {lab + f" {R}R":<36}' + ''.join(f'{100 * (q[f"r{R}"] > 0).mean() if len(q) else 0:6.0f}% {q[f"n{R}"].sum():+5.1f}R {len(q):3d}' for q in cells)
                      + f'{z.risk.median():7.0f}點')


if __name__ == '__main__':
    main()
