"""Trend Judge parameters: EMA length and the fast / slow seconds (v3 = EMA1130 on 5 s / 15 s). NQ 2m / 5m, five years.

  cd indicators/backtest
  python3 -I rbs/tj_params.py

The per-minute EMAs are rebuilt with alpha = 1 - (1 - 2/(L+1))^(60/s). Changing them changes the size of the spread, so
the thresholds are recalibrated: the new 一般 / 強勢 thresholds are the values of |spread| at the same percentiles that
10 / 35 points have for the v3 setting (so 'trend' covers the same share of the time). v3 as now otherwise (2m trend
0-400, 5m 0-180 + daily SMA5, stop >= 0.95 ATR, slow line <= 3 ATR of the new slow line, FOMC, junk time, New York
15:45-18:30 off; one at a time; trend + MIX). Per year: win rate / R.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import rbs
import setup_study as ss
import market_matrix as mm
import oos_check as oc
import daily_sma5 as d5

SETS = [(1130, 5, 15), (1130, 3, 15), (1130, 8, 15), (1130, 5, 10), (1130, 5, 20), (1130, 5, 30), (1130, 10, 30), (800, 5, 15), (1500, 5, 15)]


def main():
    one = oc.load(); D = d5.daily(one)
    base_q = None
    for tf, R, cap in ((2, 3.0, 400), (5, 2.0, 180)):
        print(f'\nNQ {tf}m（{R:g}R）每年：勝率 / 合計 R')
        print(f'   {"EMA 長度, 快, 慢（門檻）":<30}' + ''.join(f'{nm[:2] + " " + nm[3:8]:>15}' for nm, a, b in oc.YEARS))
        for L, fs, ss_ in SETS:
            rbs.A_FAST = 1 - (1 - 2 / (L + 1)) ** (60 / fs); rbs.A_SLOW = 1 - (1 - 2 / (L + 1)) ** (60 / ss_)
            M = oc.Market(one)
            d = M.tdm['diff'].abs().dropna().values
            if (L, fs, ss_) == (1130, 5, 15):
                base_q = ((d < 10).mean(), (d < 35).mean()); th, st = 10.0, 35.0
            else:
                th, st = float(np.quantile(d, base_q[0])), float(np.quantile(d, base_q[1]))
            C = M.ctx(tf, th, st); df = C.df; c = df.close.values
            dt = pd.DatetimeIndex(df.datetime); dt = dt.tz_localize('UTC') if dt.tz is None else dt
            ny = (dt + pd.Timedelta(minutes=tf)).tz_convert(ss.NY); m = np.asarray(ny.hour * 60 + ny.minute)
            skip = ((m >= 720) & (m <= 785)) | ((m >= 945) & (m < 1110))
            sma = D.sma.reindex((dt.tz_convert(ss.NY) + pd.Timedelta(hours=6)).normalize()).values
            s = mm.trend_signals(df, M.H, tf, 20, 8)
            T = s[(s.side == s.h1) & (s.risk_atr >= 0.95) & ~ss.EVT(s) & (s.slow < 3) & (s.spread > df.thr.values[s.i]) & (s.tm < cap) & ~s.date.isin(ss.FOMC) & ~skip[s.i]]
            if tf == 5: T = T[np.sign(c[T.i.values] - sma[T.i.values]) == T.side.values]
            mix = [x for x in oc.mix_list(C) if C.date[x[0]] not in ss.FOMC and not skip[x[0]] and (tf != 5 or ((x[2] - sma[x[0]]) * x[1] > 0 and abs(x[2] - sma[x[0]]) / x[2] * 100 >= 0.25))]
            t = oc.sim(C, T, mix, R, R)
            lab = f'{L}, {fs}s, {ss_}s（{th:.1f} / {st:.0f}）' + ('  ← v3' if (L, fs, ss_) == (1130, 5, 15) else '')
            print(f'   {lab:<30}' + ''.join(f'{100 * (z.R > 0).mean():5.0f}% {z.net.sum():+5.0f}R' for z in (t[(t.date >= a) & (t.date <= b)] for nm, a, b in oc.YEARS)), flush=True)


if __name__ == '__main__':
    main()
