"""v3 with the 30-minute EMA89 instead of (or on top of) the 1-hour EMA20 same-side filter (NQ 2m / 5m, five years).

  cd indicators/backtest
  python3 -I rbs/m30_ema.py

Same rule shape as v3's 1h filter: side of the last closed bar's close vs its EMA (no repaint). MIX unchanged.
FOMC days off, one at a time; also each trend signal on its own (flip_wait.each).
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import setup_study as ss
import market_matrix as mm
import oos_check as oc
import flip_wait as fw


def htf(one, minutes, span):
    hc = one.close.resample(f'{minutes}min').last().dropna(); he = hc.ewm(span=span, adjust=False).mean()
    return pd.DataFrame({'t': hc.index + pd.Timedelta(minutes=minutes), 'h1': np.sign(hc - he).values}).dropna()


def main():
    one = oc.load(); M = oc.Market(one); H30 = htf(one, 30, 89)
    for tf, R in ((2, 3.0), (5, 2.0)):
        C = M.ctx(tf); df = C.df; th = df.thr.values
        s = mm.trend_signals(df, M.H, tf, 20, 8)
        s30 = mm.trend_signals(df, H30, tf, 20, 8).set_index('i').h1.reindex(s.i).values
        base = (s.risk_atr >= 1.0) & ~ss.EVT(s) & (s.slow < 3.0) & (s.spread > th[s.i]) & (s.tm >= 0) & (s.tm < 180) & ~s.date.isin(ss.FOMC)
        a = s.side == s.h1; b = s.side.values == s30
        mix = [x for x in oc.mix_list(C) if C.date[x[0]] not in ss.FOMC]
        print(f'\nNQ {tf}m（FOMC 整天不做；每年 R：Y1 Y2 Y3 Y4 IS）')
        for lab, m in (('v3（1h EMA20）', base & a), ('30m EMA89', base & b), ('兩個都同向', base & a & b),
                       ('任一同向', base & (a | b)), ('30m 同向、1h 逆向', base & b & ~a), ('1h 同向、30m 逆向', base & a & ~b)):
            T = s[m.values if hasattr(m, 'values') else m]
            oc.one_line(f'{lab}（{len(T)}）', oc.sim(C, T, mix, R, R))
            n = fw.each(C, T, R); oos = (T.date <= oc.YEARS[3][2]).values
            if len(n):
                print(f'      單獨進場：樣本外 勝 {100 * (n[oos] > 0).mean():.0f}% 每筆 {n[oos].mean():+.2f}R；v3 那年 {(~oos).sum()} 筆 勝 {100 * (n[~oos] > 0).mean():.0f}% 每筆 {n[~oos].mean():+.2f}R')


if __name__ == '__main__':
    main()
