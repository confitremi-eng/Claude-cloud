"""Remi Superb V4 candidate: v3 as it is now, with the original signal at Remi's chart setting (8, 0, 9, 1).

  cd indicators/backtest
  python3 -I rbs/v4_check.py          # NQ 2m and 5m, per year, v3 (20, 0, 8, 1) next to (8, 0, 9, 1)

Rules as reentry.py ("v3 as now"): 2m trend 0-400 minutes, 5m 0-180, Trend Judge > 10, 1-hour EMA20 side,
stop >= 0.95 ATR, <= 3 ATR from the 15 s EMA1130, event / junk windows and FOMC days off, MIX breakouts, one position
at a time, Friday cut-off, 60-bar exit, 17:00 halt, 1 point cost; NQ 2m also re-enters once after a stop-out (5 bars,
two-bar stop). Only the signal's stage and EMA change. Each target is shown with the win rate (share of trades that
made money), Remi's main yardstick.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import setup_study as ss
import market_matrix as mm
import oos_check as oc
import reentry as rb

SIGNALS = (('v3 (20,0,8,1)', 20, 8), ('V4 (8,0,9,1)', 8, 9))


def setup(M, tf):
    C = M.ctx(tf); df = C.df
    ny = pd.DatetimeIndex(df.datetime) + pd.Timedelta(minutes=tf)
    ny = (ny.tz_localize('UTC') if ny.tz is None else ny).tz_convert(ss.NY)
    m = np.asarray(ny.hour * 60 + ny.minute); wk = np.asarray(ny.weekday < 5)
    junk = (m >= 720) & (m <= 785)
    isf = np.isin(np.asarray(C.date), list(ss.FOMC))
    evt = (wk & (((m >= 508) & (m < 540)) | ((m >= 598) & (m < 615)))) | (isf & (m >= 838) & (m < 900)) | \
          ((m >= 570) & (m < 600)) | ((m >= 945) & (m < 975)) | ((m >= 1005) & (m < 1020)) | ((m >= 1080) & (m < 1110)) | junk
    tjs = np.sign(df.tj_dir.values).astype(int)
    _, atr = ss.bar_context(df, tf)
    mix = [x for x in oc.mix_list(C) if C.date[x[0]] not in ss.FOMC and not junk[x[0]]]
    return C, junk, evt, tjs, atr, mix


def trend(M, C, tf, stage, ema, junk, cap):
    th = C.df.thr.values
    s = mm.trend_signals(C.df, M.H, tf, stage, ema)
    return s[(s.side == s.h1) & (s.risk_atr >= 0.95) & ~ss.EVT(s) & (s.slow < 3) & (s.spread > th[s.i]) & (s.tm < cap)
             & ~s.date.isin(ss.FOMC) & ~junk[s.i]]


def line(name, t):
    cells = []
    for nm, a, b in oc.YEARS:
        y = t[(t.date >= a) & (t.date <= b)]
        cells.append(f'{y.net.sum():+5.0f} {(y.R > 0).mean() * 100:3.0f}%' if len(y) else '    -     ')
    r = oc.year_stats(t)
    rec = t[t.date >= '2026-04-15']
    print(f'   {name:<20} ' + '  '.join(cells) + f'   合計 {r["tot"]:+5.0f}R 每筆 {r["per"]:+.3f}；'
          f'最近半年 {rec.net.sum():+4.0f}R 勝率 {(rec.R > 0).mean() * 100:3.0f}%；每天 {len(t) / max(t.date.nunique(), 1):.1f} 筆')


def main():
    one = oc.load(); M = oc.Market(one)
    print(f'NQ {one.index[0]:%Y-%m-%d} .. {one.index[-1]:%Y-%m-%d}，v3 現行規則，每筆扣 {oc.COST:g} 點')
    print('每格 = 全年 R、勝率（賺錢的筆數比例）；年度 10 月到 10 月，IS = 2025-10 .. 2026-10')
    print('   ' + ' ' * 20 + '  '.join(f'{nm[:2]:^10}' for nm, a, b in oc.YEARS))
    for tf, Rs, cap, N in ((2, (1.0, 1.5, 2.0, 3.0), 400, 5), (5, (1.0, 1.5, 2.0), 180, 0)):
        C, junk, evt, tjs, atr, mix = setup(M, tf)
        print(f'\n## NQ {tf}m（趨勢 0–{cap} 分 + MIX{"，停損後再進場一次" if N else ""}）')
        for R in Rs:
            for name, stage, ema in SIGNALS:
                T = trend(M, C, tf, stage, ema, junk, cap)
                line(f'{name} {R:g}R', rb.sim(C, T, mix, R, N, 'two-bar', evt, tjs, atr))


if __name__ == '__main__':
    main()
