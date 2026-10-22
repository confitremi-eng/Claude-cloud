"""NQ 2m: are v3's trend SELLS with a small Trend Judge spread better skipped, while small-spread BUYS are kept?
Five years.

  cd indicators/backtest
  python3 -I rbs/nq2m_tj_side.py

v3 2m trend signals as now ((20, 0, 8, 1), Trend Judge 10 / 35, 1h EMA20, stop >= 0.95 ATR, slow line <= 3 ATR,
trend 0-400 minutes, events, FOMC, junk time, ET 15:45-18:30).
Part 1, each signal on its own (no position overlap, so buckets do not affect each other): side x spread band
(10-20, 20-35, 35-55, 55-80, 80+); the v3 year and the four years before; 1R / 1.5R / 3R hit rate and 3R net R.
Part 2, policies traded one at a time with MIX (as v3): skip sells below X, skip buys below X (the mirror, as a
control), skip both. Per year: 1R and 3R win rate / net R.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import setup_study as ss
import market_matrix as mm
import oos_check as oc

BANDS = ((10, 20), (20, 35), (35, 55), (55, 80), (80, 1e9))


def main():
    one = oc.load(); M = oc.Market(one); C = M.ctx(2); df = C.df; th = df.thr.values
    ny = pd.DatetimeIndex(df.datetime) + pd.Timedelta(minutes=2); ny = (ny.tz_localize('UTC') if ny.tz is None else ny).tz_convert(ss.NY)
    m = np.asarray(ny.hour * 60 + ny.minute); off = ((m >= 720) & (m <= 785)) | ((m >= 945) & (m < 1110))
    s = mm.trend_signals(df, M.H, 2, 20, 8)
    base = s[(s.side == s.h1) & (s.risk_atr >= 0.95) & ~ss.EVT(s) & (s.slow < 3) & (s.spread > th[s.i]) & (s.tm < 400)
             & ~s.date.isin(ss.FOMC) & ~off[s.i]].copy()
    split = oc.YEARS[-1][1]
    print('######## 1. 每個訊號單獨算（不管持倉），方向 × 趨勢值')
    print(f'   {"":<16}{"":>10}{"筆":>6}{"1R":>6}{"1.5R":>6}{"3R":>6}{"3R 每筆":>9}')
    for side, nm in ((1, '買'), (-1, '賣')):
        for lo, hi in BANDS:
            for per, z in (('v3 那年', base[base.date >= split]), ('前 4 年', base[base.date < split])):
                q = z[(z.side == side) & (z.spread >= lo) & (z.spread < hi)]
                if not len(q): continue
                n3 = q.r3 - oc.COST / q.risk
                lab = f'{nm} {lo:g}–{hi:g}' if hi < 1e9 else f'{nm} {lo:g}+'
                print(f'   {lab:<16}{per:>10}{len(q):6d}' + ''.join(f'{100 * (q[f"r{R:g}"] >= R - 1e-9).mean():5.0f}%' for R in (1.0, 1.5, 3.0)) + f'{n3.mean():+8.2f}R')
        print()

    mix = [x for x in oc.mix_list(C) if C.date[x[0]] not in ss.FOMC and not off[x[0]]]
    yrs = list(oc.YEARS); yrs[-1] = (yrs[-1][0], yrs[-1][1], '2099-12-31')
    print('######## 2. 一次一筆（加 MIX，同 v3），每格：勝率 / 淨 R')
    print(f'   {"":<26}' + ''.join(f'{nm[:2] + " " + nm[3:8]:>15}' for nm, a, b in yrs) + f'{"合計":>15}{"筆 / 年":>8}')
    for R in (1.0, 3.0):
        print(f'\n目標 {R:g}R')
        rows = [('v3 現在', base)]
        for X in (20, 35, 55):
            rows += [(f'賣單 TJ < {X} 不做', base[~((base.side == -1) & (base.spread < X))]),
                     (f'買單 TJ < {X} 不做（對照）', base[~((base.side == 1) & (base.spread < X))]),
                     (f'買賣 TJ < {X} 都不做', base[base.spread >= X])]
        for lab, T in rows:
            t = oc.sim(C, T.sort_values('i'), mix, R, R)
            cells = [t[(t.date >= a) & (t.date <= b)] for nm, a, b in yrs] + [t]
            print(f'   {lab:<26}' + ''.join(f'{100 * (z.R > 0).mean():5.0f}% {z.net.sum():+6.0f}R' for z in cells) + f'{len(t) / 5:8.0f}', flush=True)


if __name__ == '__main__':
    main()
