"""Remi's 垃圾時間: no signals New York 12:00-13:05 (Taipei 00:00-01:05). What it does to v3 (NQ 2m / 5m, five years).

  cd indicators/backtest
  python3 -I rbs/junk_time.py

v3 as now (2m trend time 0-400, 5m 0-180, stop >= 0.95 ATR, FOMC days off, one at a time). Signals whose bar closes
inside the window (inclusive) are dropped: trend signals and MIX breakouts (a MIX touch there is skipped; the box is
not carried on, so this slightly differs from the indicator, which voids the box).
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import setup_study as ss
import market_matrix as mm
import oos_check as oc


def main():
    one = oc.load(); M = oc.Market(one)
    for tf, R, cap in ((2, 3.0, 400), (5, 2.0, 180)):
        C = M.ctx(tf); df = C.df; th = df.thr.values
        s = mm.trend_signals(df, M.H, tf, 20, 8)
        T = s[(s.side == s.h1) & (s.risk_atr >= 0.95) & ~ss.EVT(s) & (s.slow < 3.0) & (s.spread > th[s.i]) & (s.tm < cap) & ~s.date.isin(ss.FOMC)]
        mix = [x for x in oc.mix_list(C) if C.date[x[0]] not in ss.FOMC]
        ny = (pd.DatetimeIndex(df.datetime) + pd.Timedelta(minutes=tf)); ny = (ny.tz_localize('UTC') if ny.tz is None else ny).tz_convert(ss.NY)
        m = np.asarray(ny.hour * 60 + ny.minute); junk = (m >= 720) & (m <= 785)
        print(f'\nNQ {tf}m（{R:g}R；每年 R：Y1 Y2 Y3 Y4 IS）')
        a = oc.sim(C, T, mix, R, R)
        b = oc.sim(C, T[~junk[T.i.values]], [x for x in mix if not junk[x[0]]], R, R)
        for lab, t in (('v3 現在', a), ('垃圾時間不做', b)):
            oc.one_line(lab, t)
            y = oc.year_stats(t[t.date > oc.YEARS[3][2]]); r = t[t.date >= '2026-07-19']
            print(f'      v3 那年 {y["n"]} 筆 勝 {y["win"]:.0f}% 每筆 {y["per"]:+.3f} 合計 {y["tot"]:+.0f} 回撤 {y["dd"]:.0f} 月 {y["months"]}；最近 3 個月 {r.net.sum():+.1f}R')
        print(f'      垃圾時間裡的訊號：趨勢 {int(junk[T.i.values].sum())} 個、MIX {sum(1 for x in mix if junk[x[0]])} 個（五年）')


if __name__ == '__main__':
    main()
