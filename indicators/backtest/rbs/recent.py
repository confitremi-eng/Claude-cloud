"""v3 over the last few months of data (default from 2026-07-19), month by month.

  cd indicators/backtest
  python3 -I rbs/recent.py [start yyyy-mm-dd]

NQ 2m (3R) and NQ 5m (2R): v3 as now (FOMC days off), split cash session (09:30-16:00 New York entries) / night.
NQ RTH 1m (QQQ setting). One at a time, 1 point cost.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import setup_study as ss
import oos_check as oc
import night_stop as ns


def show(lab, t):
    if not len(t): print(f'   {lab}: 沒有交易'); return
    eq = np.cumsum(t.net.values); dd = np.max(np.maximum.accumulate(np.r_[0, eq])[1:] - eq)
    mo = t.groupby(t.date.str[:7]).net.agg(['sum', 'count'])
    print(f'   {lab:<14} {len(t):4d} 筆 勝 {100 * (t.R > 0).mean():3.0f}% 合計 {t.net.sum():+6.1f}R 每筆 {t.net.mean():+.2f}R 回撤 {dd:4.1f}R   每月 '
          + '  '.join(f'{m[5:]}月 {r["sum"]:+.0f}R（{int(r["count"])}）' for m, r in mo.iterrows()))


def main():
    start = sys.argv[1] if len(sys.argv) > 1 else '2026-07-19'
    one = oc.load(); M = oc.Market(one)
    print(f'v3 從 {start} 到資料最後一天')
    for tf, R in ((2, 3.0), (5, 2.0)):
        C = M.ctx(tf); df = C.df
        T = oc.trend_set(df, M.H, tf, 20, df.thr.values, 3.0, 0, 180); T = T[~T.date.isin(ss.FOMC)]
        mix = [x for x in oc.mix_list(C) if C.date[x[0]] not in ss.FOMC]
        t, _ = ns.sim(C, T, mix, R, 0); t = t[t.date >= start]
        print(f'\nNQ {tf}m（{R:g}R）')
        show('全部', t); show('現金盤', t[~t.night]); show('夜盤', t[t.night])
    t = oc.nq_rth(one); t = t[t.date >= start]
    print('\nNQ RTH 1m（QQQ 做法）'); show('全部', t)


if __name__ == '__main__':
    main()
