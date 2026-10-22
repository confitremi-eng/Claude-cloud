"""NQ 2m (v3 rules): while Trend Judge is strong (beyond 35 on the signal's side), also take signals of a shorter stage
(10 / 12 / 15), so a one-way trend without a 20-bar bounce can still be caught. Five years.

  cd indicators/backtest
  python3 -I rbs/nq2m_strong_stage.py

v3 2m as now: (20, 0, 8, 1), Trend Judge 10 / 35, 1h EMA20, stop >= 0.95 ATR, slow line <= 3 ATR, trend 0-400 minutes,
events, FOMC, junk time ET 12:00-13:05, ET 15:45-18:30, Friday cut-off; MIX shares the position. Extra signals pass the
same filters (and, in the "no 400 cap" rows, may come after 400 minutes). One at a time. Per year: win rate / net R at
3R (v3's target) and at 1R (= 1R hit rate). "Alone" rows: the extra signals traded by themselves (no base, no MIX).
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import setup_study as ss
import market_matrix as mm
import oos_check as oc


def main():
    one = oc.load(); M = oc.Market(one); C = M.ctx(2); df = C.df; th = df.thr.values
    ny = pd.DatetimeIndex(df.datetime) + pd.Timedelta(minutes=2); ny = (ny.tz_localize('UTC') if ny.tz is None else ny).tz_convert(ss.NY)
    m = np.asarray(ny.hour * 60 + ny.minute); off = ((m >= 720) & (m <= 785)) | ((m >= 945) & (m < 1110))

    def sigs(stage, cap=400):
        s = mm.trend_signals(df, M.H, 2, stage, 8)
        return s[(s.side == s.h1) & (s.risk_atr >= 0.95) & ~ss.EVT(s) & (s.slow < 3) & (s.spread > th[s.i]) & (s.tm < cap)
                 & ~s.date.isin(ss.FOMC) & ~off[s.i]]

    mix = [x for x in oc.mix_list(C) if C.date[x[0]] not in ss.FOMC and not off[x[0]]]
    base = sigs(20)
    print(f'   {"":<34}' + ''.join(f'{nm[:2] + " " + nm[3:8]:>15}' for nm, a, b in oc.YEARS) + '   筆 / 年')

    def row(lab, T, mx, R):
        t = oc.sim(C, T.sort_values('i'), mx, R, R)
        print(f'   {lab:<34}' + ''.join(f'{100 * (z.R > 0).mean():5.0f}% {z.net.sum():+5.0f}R' for z in (t[(t.date >= a) & (t.date <= b)] for nm, a, b in oc.YEARS))
              + f'   {len(t) / 5:.0f}', flush=True)

    for R in (3.0, 1.0):
        print(f'\n目標 {R:g}R')
        row(f'v3 2m（20）+ MIX', base, mix, R)
        for st in (10, 12, 15):
            for cap, tag in ((400, ''), (10 ** 6, '，不限 400 分')):
                x = sigs(st, cap); x = x[(x.spread > 35) & ~x.i.isin(base.i)]
                row(f'+ 強勢時 ({st}, 8){tag}', pd.concat([base, x]), mix, R)
                row(f'   只做新增的 ({st}){tag}', x, [], R)


if __name__ == '__main__':
    main()
