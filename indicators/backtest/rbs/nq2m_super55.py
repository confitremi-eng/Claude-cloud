"""NQ 2m super-strong trend, Remi's version: Trend Judge beyond 55 on the signal's side -> take a short stage (5 / 10 / 20)
and skip 1h EMA20, slow line and stop size, but keep the time filters (events, FOMC, junk time, ET 15:45-18:30) and the
0-400 minute trend limit. The last year only (v3's year to the latest data).

  cd indicators/backtest
  python3 -I rbs/nq2m_super55.py

Rows: the extra signals alone (one at a time) and added to v3 2m (base + MIX, shared position). Win rate / net R / trades
at 1R, 1.5R and 3R, all and by side (buy / sell).
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
    a, b = oc.YEARS[-1][1], str(C.date[-1])
    keep = lambda s: s[~ss.EVT(s) & ~s.date.isin(ss.FOMC) & ~off[s.i] & (s.tm < 400)]
    s = mm.trend_signals(df, M.H, 2, 20, 8)
    base = keep(s[(s.side == s.h1) & (s.risk_atr >= 0.95) & (s.slow < 3) & (s.spread > th[s.i])])
    mix = [x for x in oc.mix_list(C) if C.date[x[0]] not in ss.FOMC and not off[x[0]]]
    print(f'{a} .. {b}')
    print(f'   {"":<28}' + ''.join(f'{f"{R:g}R":>20}' for R in (1.0, 1.5, 3.0)))

    def row(lab, T, mx):
        ts = [oc.sim(C, T.sort_values('i'), mx, R, R) for R in (1.0, 1.5, 3.0)]
        ts = [t[(t.date >= a) & (t.date <= b)] for t in ts]
        for side, nm_ in ((None, ''), (1, ' 買'), (-1, ' 賣')):
            out = [f'{100 * (z.R > 0).mean():6.0f}% {z.net.sum():+5.0f}R {len(z):4d}筆' for z in (t if side is None else t[t.side == side] for t in ts)]
            print(f'   {lab + nm_:<28}' + ''.join(out), flush=True)

    row('v3 2m + MIX', base, mix)
    for st in (5, 10, 20):
        x = mm.trend_signals(df, M.H, 2, st, 8); x = keep(x[x.spread > 55])
        row(f'只做 TJ>55 ({st})', x, [])
        row(f'  v3 + TJ>55 ({st})', pd.concat([base, x[~x.i.isin(base.i)]]), mix)
        xs = x[(x.side == -1) & ~x.i.isin(base.i)]
        row(f'  v3 + TJ>55 ({st}) 只加賣', pd.concat([base, xs]), mix)


if __name__ == '__main__':
    main()
