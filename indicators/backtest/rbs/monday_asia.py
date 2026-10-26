"""NQ v3: are the trades from the Sunday Globex open to Taipei Monday 15:00 (ET Sun 18:00 .. Mon 03:00) bad?

  cd indicators/backtest
  python3 -I rbs/monday_asia.py

v3 2m (trend 0-400 minutes, 3R) and 5m (0-180, 2R) as now, including the pre-close window from ET 15:15. Part 1: each
trend signal on its own, Taipei 06:00-15:00 on Monday vs the same hours Tuesday-Friday. Part 2: v3 traded (trend + MIX,
one at a time) with and without the Monday 06:00-15:00 entries; per year win rate / net R at 1R and the target.
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
    split = oc.YEARS[-1][1]
    for tf, hi, R in ((2, 400, 3.0), (5, 180, 2.0)):
        C = M.ctx(tf); df = C.df; th = df.thr.values
        ny = pd.DatetimeIndex(df.datetime) + pd.Timedelta(minutes=tf); ny = (ny.tz_localize('UTC') if ny.tz is None else ny).tz_convert(ss.NY)
        m = np.asarray(ny.hour * 60 + ny.minute)
        tp = ny.tz_convert('Asia/Taipei'); tm = np.asarray(tp.hour * 60 + tp.minute); tdow = np.asarray(tp.weekday)
        off = ((m >= 720) & (m <= 785)) | ((m >= 915) & (m < 1110))
        s = mm.trend_signals(df, M.H, tf, 20, 8)
        base = s[(s.side == s.h1) & (s.risk_atr >= 0.95) & ~ss.EVT(s) & (s.slow < 3) & (s.spread > th[s.i]) & (s.tm < hi)
                 & ~s.date.isin(ss.FOMC) & ~off[s.i]]
        asia = (tm >= 360) & (tm < 900)
        mon = asia & (tdow == 0); other = asia & (tdow >= 1) & (tdow <= 4)
        print(f'\n######## NQ {tf}m：台北 06:00–15:00 的趨勢訊號（每個單獨算）')
        for lab, mk in (('週一', mon), ('週二–週五', other)):
            for per, z in (('v3 那年', base[base.date >= split]), ('前 4 年', base[base.date < split])):
                q = z[mk[z.i.values]]
                if not len(q): continue
                print(f'   {lab:<8}{per:>8}{len(q):5d} 個  1R {100 * (q.r1 >= 1).mean():3.0f}%  1.5R {100 * (q["r1.5"] >= 1.5).mean():3.0f}%  '
                      f'{R:g}R {100 * (q[f"r{R:g}"] >= R).mean():3.0f}%  每筆 {(q[f"r{R:g}"] - oc.COST / q.risk).mean():+.2f}R')
        mix0 = [x for x in oc.mix_list(C) if C.date[x[0]] not in ss.FOMC and not off[x[0]]]
        print(f'   一次一筆（趨勢 + MIX），每格：勝率 / 淨 R')
        print(f'   {"":<26}' + ''.join(f'{nm[:2] + " " + nm[3:8]:>15}' for nm, a, b in yrs) + f'{"合計":>15}{"少掉":>6}')
        for RR in (1.0, R):
            n0 = None
            for lab, cut in (('v3 現在', None), ('週一台北 06–09 不做', (tm >= 360) & (tm < 540) & (tdow == 0)), ('週一台北 06–12 不做', (tm >= 360) & (tm < 720) & (tdow == 0)), ('週一台北 06–14 不做', (tm >= 360) & (tm < 840) & (tdow == 0)), ('週一台北 06–15 不做', mon)):
                T = base if cut is None else base[~cut[base.i.values]]
                mix = mix0 if cut is None else [x for x in mix0 if not cut[x[0]]]
                t = oc.sim(C, T.sort_values('i'), mix, RR, RR)
                if n0 is None: n0 = len(t)
                cells = [t[(t.date >= a) & (t.date <= b)] for nm, a, b in yrs] + [t]
                print(f'   {lab + f" {RR:g}R":<26}' + ''.join(f'{100 * (z.R > 0).mean():5.0f}% {z.net.sum():+6.0f}R' for z in cells) + f'{n0 - len(t):6d}', flush=True)


if __name__ == '__main__':
    main()
