"""NQ 2m super-strong trend, sells only: grid of the Trend Judge level (45-80) x stage (5-20). Time filters and the
0-400 minute limit kept; 1h EMA20, slow line and stop size skipped (as nq2m_super55.py).

  cd indicators/backtest
  python3 -I rbs/nq2m_super_sell_grid.py

Part 1, the last year (2025-10-15 .. latest): the extra sells alone (one at a time), 1R win rate / R, 1.5R R, 3R R,
trades; and v3 2m + those sells (1R win rate / R, 3R R). Part 2: the same cells over the four years before (per year
1R win rate / R) so the pick can be checked out of sample.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import setup_study as ss
import market_matrix as mm
import oos_check as oc

LV = (45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 100)
ST = (5, 8, 10, 12, 15, 20)


def main():
    one = oc.load(); M = oc.Market(one); C = M.ctx(2); df = C.df; th = df.thr.values
    ny = pd.DatetimeIndex(df.datetime) + pd.Timedelta(minutes=2); ny = (ny.tz_localize('UTC') if ny.tz is None else ny).tz_convert(ss.NY)
    m = np.asarray(ny.hour * 60 + ny.minute); off = ((m >= 720) & (m <= 785)) | ((m >= 945) & (m < 1110))
    a, b = oc.YEARS[-1][1], str(C.date[-1])
    keep = lambda s: s[~ss.EVT(s) & ~s.date.isin(ss.FOMC) & ~off[s.i] & (s.tm < 400)]
    s = mm.trend_signals(df, M.H, 2, 20, 8)
    base = keep(s[(s.side == s.h1) & (s.risk_atr >= 0.95) & (s.slow < 3) & (s.spread > th[s.i])])
    mix = [x for x in oc.mix_list(C) if C.date[x[0]] not in ss.FOMC and not off[x[0]]]
    raw = {st: keep(mm.trend_signals(df, M.H, 2, st, 8)) for st in ST}
    runs = {}

    def sim(T, mx, R):
        key = (tuple(T.i.values), len(mx), R)
        if key not in runs: runs[key] = oc.sim(C, T.sort_values('i'), mx, R, R)
        return runs[key]

    cut = lambda t: t[(t.date >= a) & (t.date <= b)]
    b1, b3 = cut(sim(base, mix, 1.0)), cut(sim(base, mix, 3.0))
    print(f'{a} .. {b}   v3 2m + MIX: 1R {100 * (b1.R > 0).mean():.0f}% {b1.net.sum():+.0f}R，3R {b3.net.sum():+.0f}R')
    print(f'   {"TJ  階段":<10}{"只做新增賣單：1R 勝率 / R":>26}{"1.5R":>8}{"3R":>8}{"筆":>6}   {"v3 + 這些賣單：1R 勝率 / R":>26}{"3R":>8}')
    for lv in LV:
        for st in ST:
            x = raw[st]; x = x[(x.side == -1) & (x.spread > lv) & ~x.i.isin(base.i)]
            t1, t15, t3 = (cut(sim(x, [], R)) for R in (1.0, 1.5, 3.0))
            c1, c3 = (cut(sim(pd.concat([base, x]), mix, R)) for R in (1.0, 3.0))
            print(f'   {lv:>3} {st:>4}  {100 * (t1.R > 0).mean():18.0f}% {t1.net.sum():+5.0f}R{t15.net.sum():+7.0f}R{t3.net.sum():+7.0f}R{len(t1):6d}'
                  f'   {100 * (c1.R > 0).mean():20.0f}% {c1.net.sum():+5.0f}R{c3.net.sum():+7.0f}R', flush=True)
    print('\n前 4 年：只做新增賣單，1R 勝率 / R')
    print(f'   {"TJ  階段":<10}' + ''.join(f'{nm[:8]:>15}' for nm, _, _ in oc.YEARS[:4]))
    for lv in LV:
        for st in ST:
            x = raw[st]; x = x[(x.side == -1) & (x.spread > lv) & ~x.i.isin(base.i)]
            t = sim(x, [], 1.0)
            print(f'   {lv:>3} {st:>4} ' + ''.join(f'{100 * (z.R > 0).mean():8.0f}% {z.net.sum():+4.0f}R' for z in (t[(t.date >= p) & (t.date <= q)] for _, p, q in oc.YEARS[:4])), flush=True)


if __name__ == '__main__':
    main()
