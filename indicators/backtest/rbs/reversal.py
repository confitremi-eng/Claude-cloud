"""When v3 trend signals fail in a row against a rally, is it the start of a big reversal?

  cd indicators/backtest
  python3 -I rbs/reversal.py

Prompted by 2026-10-20: two NQ 2m trend sells in a row while price had already climbed back over both EMA1130
lines; the first was stopped, the second went nowhere. Everything below is known at the signal bar:
  慢線另一邊   close on the wrong side of the 15 s EMA1130 (sell above / buy below it)
  差值縮小     Trend Judge spread on the trade's side smaller than 20 minutes ago (the trend fading)
  前一筆停損   the previous v3 trend signal on the same side, within 60 minutes, already hit its stop
After the signal: share where Trend Judge turns the other way (UP for a sell) within 60 / 120 minutes, the move
over the next 60 minutes on the trade's side in ATR, and the signal's own 1R / 3R result.
v3 frozen trend signals on NQ 2m (rbs/oos_check.py), the v3 year and the five years.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import market_matrix as mm
import oos_check as oc

PERIODS = (('v3 那一年 25/10–26/10', '2025-10-15', '2026-10-18'), ('五年 21/10–26/10', '2021-10-15', '2026-10-18'))


def main(tf=2):
    one = oc.load(); M = oc.Market(one); C = M.ctx(tf); df = C.df
    s = oc.trend_set(df, M.H, tf, 20, df.thr.values, 3.0, 0, 180).copy()
    _, atr = mm.ss.bar_context(df, tf)
    c = df.close.values; d = df.tj_diff.values; tdir = np.sign(df.tj_dir.values); n = len(c)
    i = s.i.values; k = s.side.values
    s['slow_side'] = (c[i] - df.emaS.values[i]) * k / atr[i]
    lag = max(1, round(20 / tf))
    s['dspr'] = (d[i] - d[np.maximum(i - lag, 0)]) * k
    # previous same-side signal within 60 minutes that was already stopped (3R table: r3 == -1 and exit before i)
    prev_fail = np.zeros(len(s), bool)
    ii, kk, xx, rr = s.i.values, s.side.values, s.x3.values, s.r3.values
    for q in range(len(s)):
        for p in range(q - 1, -1, -1):
            if ii[q] - ii[p] > round(60 / tf): break
            if kk[p] == kk[q]:
                prev_fail[q] = rr[p] <= -0.99 and xx[p] <= ii[q]
                break
    s['prev_fail'] = prev_fail
    for m in (60, 120):
        w = round(m / tf)
        s[f'flip{m}'] = [bool((tdir[j + 1:min(j + 1 + w, n)] == -kk_).any()) for j, kk_ in zip(i, k)]
    w60 = round(60 / tf)
    s['fwd'] = (c[np.minimum(i + w60, n - 1)] - c[i]) * k / atr[i]
    print(f'NQ {tf} 分 K，v3 的趨勢訊號（凍結規則）。轉向 = Trend Judge 之後轉成反方向的趨勢；60 分走勢 = 60 分鐘後收盤順著交易方向幾 ATR')
    for nm, a, b in PERIODS:
        z = s[(s.date >= a) & (s.date <= b)]
        print(f'\n## {nm}')
        print(f'   {"":<30} {"筆數":>5} {"60分內轉向":>9} {"120分內轉向":>10} {"60分走勢":>8} {"1R勝率":>7} {"3R每筆":>7}')
        rows = [('全部', z.side != 0), ('慢線另一邊', z.slow_side < 0), ('差值縮小', z.dspr < 0), ('前一筆停損', z.prev_fail),
                ('慢線另一邊 + 差值縮小', (z.slow_side < 0) & (z.dspr < 0)), ('前一筆停損 + 慢線另一邊', z.prev_fail & (z.slow_side < 0)),
                ('前一筆停損 + 差值縮小', z.prev_fail & (z.dspr < 0)), ('三個都有（像 10/20）', z.prev_fail & (z.slow_side < 0) & (z.dspr < 0))]
        for lab, m in rows:
            y = z[m]
            if len(y) == 0:
                print(f'   {lab:<30} {0:5d}'); continue
            print(f'   {lab:<30} {len(y):5d} {100 * y.flip60.mean():8.1f}% {100 * y.flip120.mean():9.1f}% {y.fwd.mean():+8.2f} {100 * (y.r1 > 0).mean():6.1f}% {(y.r3 - 1.0 / y.risk).mean():+7.2f}')


if __name__ == '__main__':
    main()
