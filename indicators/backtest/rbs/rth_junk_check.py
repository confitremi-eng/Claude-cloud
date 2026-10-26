"""NQ RTH 1m (QQQ setting): are the trades in the junk time (ET 12:00-13:05) any good? Five years.

  cd indicators/backtest
  python3 -I rbs/rth_junk_check.py

Trades as oos_check.nq_rth (one at a time, 3R). By entry time: 10:15-12:00, junk 12:00-13:05, 13:05-15:45; per year
1R / 3R win rate and net R. Also the total with the junk-time trades removed (the trades they blocked are not added).
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import setup_study as ss
import oos_check as oc


def main():
    one = oc.load()
    df, t = oc.nq_rth(one, detail=True)
    ny = pd.DatetimeIndex(df.datetime.values[t.i.values]); ny = (ny.tz_localize('UTC') if ny.tz is None else ny).tz_convert(ss.NY) + pd.Timedelta(minutes=1)
    m = np.asarray(ny.hour * 60 + ny.minute)
    t = t.assign(m=m, n1=t.r1 - oc.COST / t.risk, n3=t.r3 - oc.COST / t.risk)
    yrs = list(oc.YEARS); yrs[-1] = (yrs[-1][0], yrs[-1][1], '2099-12-31')
    print('NQ RTH 1m（QQQ 做法），一次一筆。每格：1R 命中 / 3R 勝率 / 3R 淨 R / 筆數')
    print(f'   {"":<22}' + ''.join(f'{nm[:2] + " " + nm[3:8]:>22}' for nm, a, b in yrs) + f'{"合計":>22}')
    for lab, mk in (('上午 10:15–12:00', (m < 720)), ('垃圾時間 12:00–13:05', (m >= 720) & (m <= 785)), ('下午 13:05–15:45', (m > 785)),
                    ('全部', m >= 0), ('拿掉垃圾時間', ~((m >= 720) & (m <= 785)))):
        z = t[mk]
        cells = [z[(z.date >= a) & (z.date <= b)] for nm, a, b in yrs] + [z]
        print(f'   {lab:<22}' + ''.join(f'{100 * (q.r1 >= 1).mean() if len(q) else 0:5.0f}% {100 * (q.r3 > 0).mean() if len(q) else 0:4.0f}% {q.n3.sum():+5.1f}R {len(q):3d}' for q in cells))


if __name__ == '__main__':
    main()
