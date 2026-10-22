"""NQ v3: start the pre-close no-trade window earlier? Now ET 15:45-18:30 (Taipei 03:45-06:30); try 15:30, 15:15, 15:00.
2m and 5m, five years; trend + MIX as v3 now (5m without the daily SMA5 filter here).

  cd indicators/backtest
  python3 -I rbs/pm_start.py

Each row: per year win rate / net R at 1R and at the target (2m 3R, 5m 2R). Also the trend signals inside
15:30-15:45 scored on their own.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import setup_study as ss
import market_matrix as mm
import oos_check as oc


def main():
    one = oc.load(); M = oc.Market(one)
    yrs = list(oc.YEARS); yrs[-1] = (yrs[-1][0], yrs[-1][1], '2099-12-31')
    for tf, hi, R in ((2, 400, 3.0), (5, 180, 2.0)):
        C = M.ctx(tf); df = C.df; th = df.thr.values
        ny = pd.DatetimeIndex(df.datetime) + pd.Timedelta(minutes=tf); ny = (ny.tz_localize('UTC') if ny.tz is None else ny).tz_convert(ss.NY)
        m = np.asarray(ny.hour * 60 + ny.minute)
        s = mm.trend_signals(df, M.H, tf, 20, 8)
        base = s[(s.side == s.h1) & (s.risk_atr >= 0.95) & ~ss.EVT(s) & (s.slow < 3) & (s.spread > th[s.i]) & (s.tm < hi) & ~s.date.isin(ss.FOMC)]
        mix0 = [x for x in oc.mix_list(C) if C.date[x[0]] not in ss.FOMC]
        print(f'\n######## NQ {tf}m，每格：勝率 / 淨 R')
        print(f'   {"不做的開始時間（美東 / 台北）":<28}' + ''.join(f'{nm[:2] + " " + nm[3:8]:>15}' for nm, a, b in yrs) + f'{"合計":>15}')
        for RR in (1.0, R):
            print(f'目標 {RR:g}R')
            for st, lab in ((945, '15:45 / 03:45（現在）'), (930, '15:30 / 03:30'), (915, '15:15 / 03:15'), (900, '15:00 / 03:00')):
                off = ((m >= 720) & (m <= 785)) | ((m >= st) & (m < 1110))
                T = base[~off[base.i.values]]; mix = [x for x in mix0 if not off[x[0]]]
                t = oc.sim(C, T.sort_values('i'), mix, RR, RR)
                cells = [t[(t.date >= a) & (t.date <= b)] for nm, a, b in yrs] + [t]
                print(f'   {lab:<28}' + ''.join(f'{100 * (z.R > 0).mean():5.0f}% {z.net.sum():+6.0f}R' for z in cells), flush=True)
        q = base[((m >= 930) & (m < 945))[base.i.values]]
        for per, z in (('v3 那年', q[q.date >= oc.YEARS[-1][1]]), ('前 4 年', q[q.date < oc.YEARS[-1][1]])):
            if len(z):
                print(f'   15:30–15:45 的趨勢訊號單獨算（{per}）：{len(z)} 個，1R 命中 {100 * (z.r1 >= 1).mean():.0f}%，{R:g}R 每筆 {(z[f"r{R:g}"] - oc.COST / z.risk).mean():+.2f}R')


if __name__ == '__main__':
    main()
