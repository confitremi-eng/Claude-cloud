"""Skip new entries in a clock window (NQ 2m / 5m, five years). Default: Taipei 03:00-07:00 (= New York 15:00-19:00),
and the same hours on the New York clock for comparison.

  cd indicators/backtest
  python3 -I rbs/avoid_window.py

v3 as now (2m trend 0-400, 5m 0-180 + daily SMA5, stop >= 0.95 ATR, FOMC days off, junk time off, one at a time; no
re-entry / 15s rule). Window by the entry bar's close time, start inclusive, end exclusive. Per year: win rate / R.
Also the trades inside the window on their own.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import setup_study as ss
import market_matrix as mm
import oos_check as oc
import daily_sma5 as d5

WINDOWS = (('台北 03:00–07:00（美東 15:00–19:00）', 'Asia/Taipei', 180, 420), ('美東 03:00–07:00（台北 15:00–19:00）', 'America/New_York', 180, 420))


def main():
    one = oc.load(); M = oc.Market(one); D = d5.daily(one)
    for tf, R, cap in ((2, 3.0, 400), (5, 2.0, 180)):
        C = M.ctx(tf); df = C.df; th = df.thr.values; c = df.close.values
        dt = pd.DatetimeIndex(df.datetime); dt = dt.tz_localize('UTC') if dt.tz is None else dt
        ct = dt + pd.Timedelta(minutes=tf)
        ny = ct.tz_convert(ss.NY); m = np.asarray(ny.hour * 60 + ny.minute); junk = (m >= 720) & (m <= 785)
        sma = D.sma.reindex((dt.tz_convert(ss.NY) + pd.Timedelta(hours=6)).normalize()).values
        s = mm.trend_signals(df, M.H, tf, 20, 8)
        T = s[(s.side == s.h1) & (s.risk_atr >= 0.95) & ~ss.EVT(s) & (s.slow < 3) & (s.spread > th[s.i]) & (s.tm < cap) & ~s.date.isin(ss.FOMC) & ~junk[s.i]]
        if tf == 5: T = T[np.sign(c[T.i.values] - sma[T.i.values]) == T.side.values]
        mix = [x for x in oc.mix_list(C) if C.date[x[0]] not in ss.FOMC and not junk[x[0]] and (tf != 5 or (x[2] - sma[x[0]]) * x[1] > 0)]
        print(f'\nNQ {tf}m（{R:g}R）每年：勝率 / 合計 R')
        print(f'   {"":<36}' + ''.join(f'{nm[:2] + " " + nm[3:8]:>15}' for nm, a, b in oc.YEARS))
        def row(lab, t):
            print(f'   {lab:<36}' + ''.join(f'{100 * (z.R > 0).mean():5.0f}% {z.net.sum():+5.0f}R' if len(z) else '              -' for z in (t[(t.date >= a) & (t.date <= b)] for nm, a, b in oc.YEARS)))
        row('v3 現在', oc.sim(C, T, mix, R, R))
        for lab, tz, a, b in WINDOWS:
            lt = ct.tz_convert(tz); mm_ = np.asarray(lt.hour * 60 + lt.minute); win = (mm_ >= a) & (mm_ < b)
            row(f'避開 {lab}', oc.sim(C, T[~win[T.i.values]], [x for x in mix if not win[x[0]]], R, R))
            row(f'   只做這段（{len(T[win[T.i.values]]) + sum(1 for x in mix if win[x[0]])} 個訊號）', oc.sim(C, T[win[T.i.values]], [x for x in mix if win[x[0]]], R, R))


if __name__ == '__main__':
    main()
