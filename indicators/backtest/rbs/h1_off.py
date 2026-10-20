"""v3 without the 1-hour EMA20 same-side filter (NQ 2m / 5m, five years).

  cd indicators/backtest
  python3 -I rbs/h1_off.py

Same trend signals as v3 except the 1h EMA20 condition: on (v3), off, and only the signals it would remove. MIX
unchanged. FOMC days off, one at a time; also each trend signal on its own (flip_wait.each).
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import setup_study as ss
import market_matrix as mm
import oos_check as oc
import flip_wait as fw


def main():
    one = oc.load(); M = oc.Market(one)
    for tf, R in ((2, 3.0), (5, 2.0)):
        C = M.ctx(tf); df = C.df; th = df.thr.values
        s = mm.trend_signals(df, M.H, tf, 20, 8)
        base = (s.risk_atr >= 1.0) & ~ss.EVT(s) & (s.slow < 3.0) & (s.spread > th[s.i]) & (s.tm >= 0) & (s.tm < 180) & ~s.date.isin(ss.FOMC)
        same = s.side == s.h1
        mix = [x for x in oc.mix_list(C) if C.date[x[0]] not in ss.FOMC]
        print(f'\nNQ {tf}m（FOMC 整天不做；每年 R：Y1 Y2 Y3 Y4 IS）')
        for lab, m in (('v3（1h 同向）', base & same), ('關掉 1h 同向', base), ('只做 1h 逆向的', base & ~same)):
            T = s[m]
            oc.one_line(f'{lab}（{len(T)} 筆訊號）', oc.sim(C, T, mix, R, R))
            n = fw.each(C, T, R); oos = (T.date <= oc.YEARS[3][2]).values
            print(f'      單獨進場：樣本外 勝 {100 * (n[oos] > 0).mean():.0f}% 每筆 {n[oos].mean():+.2f}R；v3 那年 {(~oos).sum()} 筆 勝 {100 * (n[~oos] > 0).mean():.0f}% 每筆 {n[~oos].mean():+.2f}R')


if __name__ == '__main__':
    main()
