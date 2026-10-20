"""GEX setup on big gap days: are the toward-the-flip signals better after a big gap up / down? (NQ RTH 1m)

  cd indicators/backtest
  python3 -I rbs/gex_gap.py

Setup = v3's GEX setup (35, 0, 8, 1), as in gex_params.setup_rows (ZeroGEX minute flip, 2026-06-29 .. 10-14).
Gap = NQ 09:30 open vs the previous cash-session close (16:00), in %. Groups by |gap|; within gap days also whether the
signal fills the gap (trades against the gap direction) and whether it comes in the first hour. Each signal on its own
(3R and 1R win %, 1 point cost) and one at a time (3R).
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import setup_study as ss
import market_matrix as mm
import gex_params as gp


def line(lab, y, cost=1.0):
    if not len(y): print(f'   {lab:<30}    0 筆'); return
    n = y.r3 - cost / y.risk; k, tot, dd = gp.seq_stats(y, 3.0, cost)
    print(f'   {lab:<30} {len(y):4d} 筆（{y.date.nunique():2d} 天） 1R 勝 {100 * (y.r1 > 0).mean():3.0f}%  3R 每筆 {n.mean():+.2f}R   一次一筆 {k} 筆 {tot:+.1f}R')


def main():
    one = mm.load_market('qqq', []); tdm = mm.minute_trend(one); H = mm.hourly(one, True)
    df = mm.chart(one, tdm, 1, 20.0, 40.0)
    y = gp.setup_rows(df, H, 35, 8, '2026-06-29', '2026-10-14').copy()
    d = df.assign(date=df.datetime.dt.tz_convert(ss.NY).dt.date.astype(str))
    o = d.groupby('date').open.first(); c = d.groupby('date').close.last()
    gap = (o / c.shift(1) - 1) * 100
    y['gap'] = gap.reindex(y.date).values
    et = (df.datetime.values[y.i.values]); et = pd.DatetimeIndex(et).tz_convert(ss.NY) if pd.DatetimeIndex(et).tz else pd.DatetimeIndex(et).tz_localize('UTC').tz_convert(ss.NY)
    y['first_hr'] = (et.hour * 60 + et.minute) < 630
    y['fill'] = np.sign(y.gap) == -y.side
    print('NQ RTH 1m GEX setup (35, 0, 8, 1)，2026-06-29 .. 10-14')
    gap = gap[(gap.index >= '2026-06-29') & (gap.index <= '2026-10-14')]
    print(f'   跳空天數：|gap| < 0.3% {(gap.abs() < 0.3).sum()} 天、0.3–0.75% {((gap.abs() >= 0.3) & (gap.abs() < 0.75)).sum()} 天、≥ 0.75% {(gap.abs() >= 0.75).sum()} 天')
    line('全部', y)
    for lo, hi, lab in ((0, 0.3, '小跳空 < 0.3%'), (0.3, 0.75, '中跳空 0.3–0.75%'), (0.75, 99, '大跳空 ≥ 0.75%'), (0.5, 99, '跳空 ≥ 0.5%')):
        z = y[(y.gap.abs() >= lo) & (y.gap.abs() < hi)]
        line(lab, z)
        if lo >= 0.3:
            line('   ┣ 回補方向（逆跳空）', z[z.fill]); line('   ┣ 順跳空方向', z[~z.fill])
            line('   ┣ 開盤第一小時', z[z.first_hr]); line('   ┗ 第一小時以後', z[~z.first_hr])
    for lab, m in (('大高開 ≥ +0.5%', y.gap >= 0.5), ('大低開 ≤ −0.5%', y.gap <= -0.5)):
        line(lab, y[m])


if __name__ == '__main__':
    main()
