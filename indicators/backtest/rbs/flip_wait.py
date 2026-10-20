"""After the trend flips, wait before taking trend signals in the new direction (v3, NQ 2m / 5m, five years).

  cd indicators/backtest
  python3 -I rbs/flip_wait.py

Two clocks, counted in chart bars (trading time):
  run  = time since the current Trend Judge run began (resets on any MIX bar, as in the earlier trend-age study)
  flip = time since Trend Judge was last on the opposite side (MIX in between does not reset it)
Trend signals need clock >= W minutes; MIX breakouts unchanged. v3 otherwise frozen (FOMC days off), one at a time.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import setup_study as ss
import oos_check as oc


def flip_age(df, tf):
    d = np.sign(df.tj_dir.values); n = len(d)
    last = {1: np.full(n, -10 ** 9), -1: np.full(n, -10 ** 9)}
    lu = ld = -10 ** 9
    for j in range(n):
        if d[j] == 1: lu = j
        if d[j] == -1: ld = j
        last[1][j] = lu; last[-1][j] = ld
    return last


def main():
    one = oc.load(); M = oc.Market(one)
    for tf, R in ((2, 3.0), (5, 2.0)):
        C = M.ctx(tf); df = C.df
        T = oc.trend_set(df, M.H, tf, 20, df.thr.values, 3.0, 0, 180)
        T = T[~T.date.isin(ss.FOMC)]
        mix = [x for x in oc.mix_list(C) if C.date[x[0]] not in ss.FOMC]
        last = flip_age(df, tf)
        fa = np.array([(i - last[-k][i]) * tf for i, k in zip(T.i, T.side)])
        print(f'\nNQ {tf}m（v3 含 FOMC 整天不做；每年 R：Y1 Y2 Y3 Y4 IS）')
        oc.one_line('v3 現在', oc.sim(C, T, mix, R, R))
        for w in (15, 30, 45, 60):
            a = T[T.tm.values >= w]; b = T[fa >= w]
            oc.one_line(f'趨勢連續 ≥ {w} 分', oc.sim(C, a, mix, R, R))
            oc.one_line(f'翻轉後 ≥ {w} 分', oc.sim(C, b, mix, R, R))
            print(f'      趨勢訊號 {len(T)} → 連續 {len(a)}、翻轉 {len(b)}')


if __name__ == '__main__':
    main()
