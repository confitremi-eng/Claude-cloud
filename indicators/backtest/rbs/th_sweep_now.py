"""Trend Judge threshold 6-12 points with today's v3 rules (NQ 2m / 5m, five years).

  cd indicators/backtest
  python3 -I rbs/th_sweep_now.py

The threshold sets both the trend signals (spread beyond it) and what counts as MIX (for the MIX boxes); the strong
threshold stays 35. v3 as now otherwise (2m trend 0-400, 5m 0-180 + daily SMA5 / 0.25%, stop >= 0.95 ATR, FOMC, junk
time, New York 15:45-18:30 off; one at a time; trend + MIX). Per year: win rate / R, and trades per year.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import setup_study as ss
import market_matrix as mm
import oos_check as oc
import daily_sma5 as d5


def main():
    one = oc.load(); M = oc.Market(one); D = d5.daily(one)
    for tf, R, cap in ((2, 3.0, 400), (5, 2.0, 180)):
        print(f'\nNQ {tf}m（{R:g}R）每年：勝率 / 合計 R')
        print(f'   {"門檻":<10}' + ''.join(f'{nm[:2] + " " + nm[3:8]:>15}' for nm, a, b in oc.YEARS) + '   v3 那年回撤')
        for th in (6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0):
            C = M.ctx(tf, th, 35.0); df = C.df; c = df.close.values
            dt = pd.DatetimeIndex(df.datetime); dt = dt.tz_localize('UTC') if dt.tz is None else dt
            ny = (dt + pd.Timedelta(minutes=tf)).tz_convert(ss.NY); m = np.asarray(ny.hour * 60 + ny.minute)
            skip = ((m >= 720) & (m <= 785)) | ((m >= 945) & (m < 1110))
            sma = D.sma.reindex((dt.tz_convert(ss.NY) + pd.Timedelta(hours=6)).normalize()).values
            s = mm.trend_signals(df, M.H, tf, 20, 8)
            T = s[(s.side == s.h1) & (s.risk_atr >= 0.95) & ~ss.EVT(s) & (s.slow < 3) & (s.spread > th) & (s.tm < cap) & ~s.date.isin(ss.FOMC) & ~skip[s.i]]
            if tf == 5: T = T[np.sign(c[T.i.values] - sma[T.i.values]) == T.side.values]
            mix = [x for x in oc.mix_list(C) if C.date[x[0]] not in ss.FOMC and not skip[x[0]] and (tf != 5 or ((x[2] - sma[x[0]]) * x[1] > 0 and abs(x[2] - sma[x[0]]) / x[2] * 100 >= 0.25))]
            t = oc.sim(C, T, mix, R, R)
            y = oc.year_stats(t[t.date > oc.YEARS[3][2]])
            print(f'   {th:>4.0f} 點{"（v3）" if th == 10 else "     "}' + ''.join(f'{100 * (z.R > 0).mean():5.0f}% {z.net.sum():+5.0f}R' for z in (t[(t.date >= a) & (t.date <= b)] for nm, a, b in oc.YEARS))
                  + f'   {y["dd"]:4.0f}R，{len(t) / 5:.0f} 筆 / 年', flush=True)


if __name__ == '__main__':
    main()
