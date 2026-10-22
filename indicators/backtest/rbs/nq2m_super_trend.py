"""NQ 2m "super-strong trend": when Trend Judge is beyond 50 / 60 / 70 on the signal's side, take every signal of a short
stage (5 / 10 / 20) and skip v3's other filters (1h EMA20, slow line, 0-400 minutes, stop size). Five years.

  cd indicators/backtest
  python3 -I rbs/nq2m_super_trend.py

Two variants of the extra signals: "全不管" ignores everything else; "留時段" still skips events, FOMC days, junk time
and ET 15:45-18:30. Rows: the extra signals alone (one at a time), and added to v3 2m (base + MIX, shared position).
Per year: win rate / net R at 1R and at 3R.
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
    raw = {st: mm.trend_signals(df, M.H, 2, st, 8) for st in (5, 10, 20)}
    s = raw[20]
    base = s[(s.side == s.h1) & (s.risk_atr >= 0.95) & ~ss.EVT(s) & (s.slow < 3) & (s.spread > th[s.i]) & (s.tm < 400)
             & ~s.date.isin(ss.FOMC) & ~off[s.i]]
    mix = [x for x in oc.mix_list(C) if C.date[x[0]] not in ss.FOMC and not off[x[0]]]
    print(f'   {"":<30}' + ''.join(f'{nm[:2] + " " + nm[3:8]:>15}' for nm, a, b in oc.YEARS) + '   筆 / 年')

    def row(lab, T, mx, R):
        t = oc.sim(C, T.sort_values('i'), mx, R, R)
        print(f'   {lab:<30}' + ''.join(f'{100 * (z.R > 0).mean():5.0f}% {z.net.sum():+5.0f}R' for z in (t[(t.date >= a) & (t.date <= b)] for nm, a, b in oc.YEARS))
              + f'   {len(t) / 5:.0f}', flush=True)

    for R in (1.0, 3.0):
        print(f'\n目標 {R:g}R')
        row('v3 2m + MIX', base, mix, R)
        for keep in (False, True):
            for lv in (50, 60, 70):
                for st in (5, 10, 20):
                    x = raw[st]; x = x[x.spread > lv]
                    if keep: x = x[~ss.EVT(x) & ~x.date.isin(ss.FOMC) & ~off[x.i]]
                    tag = f'{"留時段" if keep else "全不管"} TJ>{lv} ({st})'
                    row(f'只做 {tag}', x, [], R)
                    row(f'  v3 + {tag}', pd.concat([base, x[~x.i.isin(base.i)]]), mix, R)


if __name__ == '__main__':
    main()
