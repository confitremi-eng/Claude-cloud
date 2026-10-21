"""Trend signals without the Trend Judge threshold: only the 5 s or the 15 s EMA1130 (NQ 2m / 5m, five years).

  cd indicators/backtest
  python3 -I rbs/line_only.py

v3 as now except the Trend Judge condition (fast - slow beyond 10 points on the trade's side) and the trend-time window,
which depends on it. Replacement rules for a buy (sell mirrored), at the signal bar:
  above 5s / above 15s : close above the 5 s / 15 s EMA1130
  5s up / 15s up       : that line higher than one bar before
  5s > 15s             : fast above slow, any size (Trend Judge without the threshold)
Other v3 filters stay (1h EMA20, stop >= 0.95 ATR, slow line <= 3 ATR, events, FOMC, junk time; 5m daily SMA5).
MIX breakouts unchanged. One at a time. Per year: win rate / R.
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
        C = M.ctx(tf); df = C.df; th = df.thr.values; c = df.close.values
        dt = pd.DatetimeIndex(df.datetime); dt = dt.tz_localize('UTC') if dt.tz is None else dt
        ny = (dt + pd.Timedelta(minutes=tf)).tz_convert(ss.NY)
        m = np.asarray(ny.hour * 60 + ny.minute); junk = (m >= 720) & (m <= 785)
        lm = pd.DatetimeIndex(df.last_min); F = M.tdm['emaF'].reindex(lm).values; S = M.tdm['emaS'].reindex(lm).values
        dayk = (dt.tz_convert(ss.NY) + pd.Timedelta(hours=6)).normalize(); sma = D.sma.reindex(dayk).values
        s = mm.trend_signals(df, M.H, tf, 20, 8)
        i, k = s.i.values, s.side.values
        base = (s.side == s.h1) & (s.risk_atr >= 0.95) & ~ss.EVT(s) & (s.slow < 3) & ~s.date.isin(ss.FOMC) & ~junk[i]
        if tf == 5:
            base &= np.sign(c[i] - sma[i]) == k
        rules = {
            'v3（Trend Judge 門檻 + 趨勢時間）': (s.spread > th[i]) & (s.tm < cap),
            '收在 5s 線同側': np.sign(c[i] - F[i]) == k,
            '收在 15s 線同側': np.sign(c[i] - S[i]) == k,
            '5s 線往同方向': np.sign(F[i] - F[i - 1]) == k,
            '15s 線往同方向': np.sign(S[i] - S[i - 1]) == k,
            '5s 在 15s 同側（不要門檻）': np.sign(F[i] - S[i]) == k,
            '收在 5s 同側 + 5s 同方向': (np.sign(c[i] - F[i]) == k) & (np.sign(F[i] - F[i - 1]) == k),
        }
        mix = [x for x in oc.mix_list(C) if C.date[x[0]] not in ss.FOMC and not junk[x[0]] and (tf != 5 or (x[2] - sma[x[0]]) * x[1] > 0)]
        print(f'\nNQ {tf}m（{R:g}R）每年：勝率 / 合計 R（趨勢訊號筆數 / 年）')
        print(f'   {"":<30}' + ''.join(f'{nm[:2] + " " + nm[3:8]:>15}' for nm, a, b in oc.YEARS))
        for lab, cond in rules.items():
            T = s[base & cond]
            t = oc.sim(C, T, mix, R, R)
            tt = t[t.kind == '趨勢']
            print(f'   {lab:<30}' + ''.join(f'{100 * (z.R > 0).mean():5.0f}% {z.net.sum():+5.0f}R' for z in (t[(t.date >= a) & (t.date <= b)] for nm, a, b in oc.YEARS))
                  + f'   趨勢單 {len(tt) / 5:.0f} / 年、勝率 {100 * (tt.R > 0).mean():.0f}%')


if __name__ == '__main__':
    main()
