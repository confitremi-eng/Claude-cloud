"""How long into a trend may v3 still take trend signals? Upper limit of 趨勢時間 (NQ 2m / 5m, five years).

  cd indicators/backtest
  python3 -I rbs/trend_cap.py

v3 as now (FOMC days off, one at a time, MIX unchanged) with the trend-time cap 120 / 180 (v3) / 240 / 300 / 400 /
none. Also the extra trend signals each cap adds over 180, each on its own (flip_wait.each), and the last 3 months.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import setup_study as ss
import oos_check as oc
import flip_wait as fw

CAPS = (120, 180, 240, 300, 400, 10 ** 6)


def main():
    one = oc.load(); M = oc.Market(one)
    for tf, R in ((2, 3.0), (5, 2.0)):
        C = M.ctx(tf); df = C.df
        mix = [x for x in oc.mix_list(C) if C.date[x[0]] not in ss.FOMC]
        print(f'\nNQ {tf}m（{R:g}R，FOMC 整天不做；每年 R：Y1 Y2 Y3 Y4 IS）')
        base = None
        for cap in CAPS:
            T = oc.trend_set(df, M.H, tf, 20, df.thr.values, 3.0, 0, cap); T = T[~T.date.isin(ss.FOMC)]
            t = oc.sim(C, T, mix, R, R)
            lab = f'0–{cap} 分' if cap < 10 ** 6 else '不限'
            oc.one_line(f'{lab}{"（v3）" if cap == 180 else ""}（{len(T)}）', t)
            r3 = t[t.date >= '2026-07-19']
            line = f'      最近 3 個月 {len(r3)} 筆 {r3.net.sum():+.1f}R'
            if cap == 180: base = T
            if cap > 180 and base is not None:
                ex = T[~T.i.isin(base.i)]
                if len(ex):
                    n = fw.each(C, ex, R); oos = (ex.date <= oc.YEARS[3][2]).values
                    line += (f'；多出的 {len(ex)} 個訊號單獨進場：樣本外 每筆 {n[oos].mean():+.2f}R、v3 那年 {(~oos).sum()} 筆'
                             f' 勝 {100 * (n[~oos] > 0).mean():.0f}% 每筆 {n[~oos].mean():+.2f}R')
            print(line)


if __name__ == '__main__':
    main()
