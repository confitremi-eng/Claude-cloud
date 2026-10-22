"""NQ v3: no new trades in the hour before the US cash open (ET 08:30-09:30)? 2m and 5m, five years.

  cd indicators/backtest
  python3 -I rbs/pre_open_skip.py

v3 as now (2m: trend 0-400 minutes, 3R; 5m: 0-180 minutes, daily SMA5 side, 2R; MIX on both; events, FOMC, junk time,
ET 15:45-18:30). v3 already skips weekday 08:28-09:00 and 09:30-10:00 (event windows), so the new part is mostly
09:00-09:30. Variants: skip 08:30-09:30, 08:00-09:30, 09:00-09:30; trend only / MIX too. Each row: per year 1R and
target-R win rate / net R. The skipped trades are also scored on their own.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import setup_study as ss
import market_matrix as mm
import oos_check as oc
import daily_sma5 as ds


def main():
    one = oc.load(); M = oc.Market(one)
    yrs = list(oc.YEARS); yrs[-1] = (yrs[-1][0], yrs[-1][1], '2099-12-31')
    for tf, hi, R in ((2, 400, 3.0), (5, 180, 2.0)):
        C = M.ctx(tf); df = C.df; th = df.thr.values
        ny = pd.DatetimeIndex(df.datetime) + pd.Timedelta(minutes=tf); ny = (ny.tz_localize('UTC') if ny.tz is None else ny).tz_convert(ss.NY)
        m = np.asarray(ny.hour * 60 + ny.minute); wk = np.asarray(ny.weekday < 5)
        off = ((m >= 720) & (m <= 785)) | ((m >= 945) & (m < 1110))
        s = mm.trend_signals(df, M.H, tf, 20, 8)
        T = s[(s.side == s.h1) & (s.risk_atr >= 0.95) & ~ss.EVT(s) & (s.slow < 3) & (s.spread > th[s.i]) & (s.tm < hi)
              & ~s.date.isin(ss.FOMC) & ~off[s.i]]
        mix = [x for x in oc.mix_list(C) if C.date[x[0]] not in ss.FOMC and not off[x[0]]]
        if tf == 5 and hasattr(ds, 'filter_trend'):
            T, mix = ds.filter_trend(T, mix, C)
        print(f'\n######## NQ {tf}m（趨勢 0–{hi} 分 + MIX），每格：勝率 / 淨 R')
        print(f'   {"":<30}' + ''.join(f'{nm[:2] + " " + nm[3:8]:>15}' for nm, a, b in yrs) + f'{"合計":>15}{"少掉":>6}')
        for RR in (1.0, R):
            print(f'目標 {RR:g}R')
            base_n = None
            for lab, a, b, mixtoo in (('v3 現在', 0, 0, False), ('08:30–09:30 不進場（趨勢 + MIX）', 510, 570, True),
                                      ('08:30–09:30 不進場（只有趨勢）', 510, 570, False), ('09:00–09:30 不進場（趨勢 + MIX）', 540, 570, True),
                                      ('08:00–09:30 不進場（趨勢 + MIX）', 480, 570, True)):
                skip = wk & (m >= a) & (m < b)
                TT = T[~skip[T.i.values]]
                mx = [x for x in mix if not (mixtoo and skip[x[0]])]
                t = oc.sim(C, TT.sort_values('i'), mx, RR, RR)
                if base_n is None: base_n = len(t)
                cells = [t[(t.date >= p) & (t.date <= q)] for nm, p, q in yrs] + [t]
                print(f'   {lab:<30}' + ''.join(f'{100 * (z.R > 0).mean():5.0f}% {z.net.sum():+6.0f}R' for z in cells) + f'{base_n - len(t):6d}', flush=True)
        # the trend signals inside 08:30-09:30 on their own
        q = T[(wk & (m >= 510) & (m < 570))[T.i.values]]
        for per, z in (('v3 那年', q[q.date >= oc.YEARS[-1][1]]), ('前 4 年', q[q.date < oc.YEARS[-1][1]])):
            if len(z):
                print(f'   08:30–09:30 的趨勢訊號單獨算（{per}）：{len(z)} 個，1R 命中 {100 * (z.r1 >= 1).mean():.0f}%，{R:g}R 每筆 {(z[f"r{R:g}"] - oc.COST / z.risk).mean():+.2f}R')


if __name__ == '__main__':
    main()
