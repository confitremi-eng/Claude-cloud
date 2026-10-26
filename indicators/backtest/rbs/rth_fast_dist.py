"""QQQ 1m (NQ RTH 1m): are trend buys far from the 5-second fast line bad? Five years.

  cd indicators/backtest
  python3 -I rbs/rth_fast_dist.py

v3's QQQ setting (oos_check.nq_rth signals; no super-trend buys). Fast-line distance = (close - 5s EMA1130) on the
trade's side / ATR14. Part 1: each signal on its own by distance band, buys and sells, the v3 year and the four years
before (1R hit, 3R net R per trade). Part 2: one at a time with an extra "fast line <= X ATR" rule (buys only, or both).
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import setup_study as ss
import market_matrix as mm
import oos_check as oc


def main():
    one = oc.load()
    cash = mm.cash_only(one); tdq = mm.minute_trend(cash); Hq = mm.hourly(cash, True)
    df, _ = oc.nq_rth(one, detail=True)
    s = mm.trend_signals(df, Hq, 1, 35, 8)
    dn = mm.chart(one, mm.minute_trend(one), 2, 10.0, 35.0); c2 = dn.close.values
    aF = 1 - (1 - 2 / 1131) ** 24; aS = 1 - (1 - 2 / 1131) ** 8
    d2 = pd.Series(c2).ewm(alpha=aF, adjust=False).mean().values - pd.Series(c2).ewm(alpha=aS, adjust=False).mean().values
    ndir = np.where(d2 > 10, 1, np.where(d2 < -10, -1, 0)); nstart = pd.DatetimeIndex(dn.datetime).values.astype('datetime64[ns]').astype(np.int64)
    t_open = pd.DatetimeIndex(df.last_min.values); t_open = (t_open.tz_localize('UTC') if t_open.tz is None else t_open).values.astype('datetime64[ns]').astype(np.int64)
    k = np.searchsorted(nstart, t_open[s.i.values], 'right') - 2
    tw = pd.DatetimeIndex(df.datetime + pd.Timedelta(minutes=1)); tw = (tw.tz_localize('UTC') if tw.tz is None else tw).tz_convert('Asia/Taipei')
    late = np.asarray((tw.weekday == 5) & (tw.hour * 60 + tw.minute >= 120))
    B = s[(s.side == s.h1) & (s.risk_atr >= 1.0) & ~ss.EVT(s) & (s.slow < 7.0) & (s.spread > df.thr.values[s.i]) & (ndir[k] * s.side.values >= 0) & ~late[s.i]].copy()
    h, l, c = df.high.values, df.low.values, df.close.values
    tr = np.maximum(h - l, np.maximum(abs(h - np.r_[c[0], c[:-1]]), abs(l - np.r_[c[0], c[:-1]])))
    atr = pd.Series(tr).ewm(alpha=1 / 14, adjust=False).mean().values
    B['fast'] = (c[B.i] - (df.emaS.values[B.i] + df.tj_diff.values[B.i])) * B.side / atr[B.i]
    split = oc.YEARS[-1][1]
    print('######## 1. 每個訊號單獨算：離 5 秒快線（ATR）')
    for side, nm in ((1, '買'), (-1, '賣')):
        for a, b in ((-9, 0.5), (0.5, 1.0), (1.0, 1.5), (1.5, 2.0), (2.0, 3.0), (3.0, 99)):
            out = []
            for per, z in (('v3 那年', B[B.date >= split]), ('前 4 年', B[B.date < split])):
                q = z[(z.side == side) & (z.fast > a) & (z.fast <= b)]
                out.append(f'{per} {len(q):4d} 個 1R {100 * (q.r1 >= 1).mean() if len(q) else 0:3.0f}% 3R 每筆 {(q.r3 - oc.COST / q.risk).mean() if len(q) else 0:+.2f}R')
            lab = f'{nm} {a:g}–{b:g}' if a > -9 else f'{nm} ≤ {b:g}'
            print(f'   {lab:<10}' + '   '.join(out))
    yrs = list(oc.YEARS); yrs[-1] = (yrs[-1][0], yrs[-1][1], '2099-12-31')
    print('\n######## 2. 一次一筆，每格：勝率 / 淨 R')
    print(f'   {"":<26}' + ''.join(f'{nm[:2] + " " + nm[3:8]:>15}' for nm, a, b in yrs) + f'{"合計":>15}{"筆/年":>7}')
    for R in (1.0, 3.0):
        rows = [('現在', B)] + [(f'買單離快線 ≤ {x:g} ATR', B[~((B.side == 1) & (B.fast > x))]) for x in (0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0)] + \
               [(f'買賣都離快線 ≤ {x:g} ATR', B[B.fast <= x]) for x in (2.0, 3.0)]
        for lab, T in rows:
            q = ss.seq(T.sort_values('i'), R).copy(); q['n'] = q[f'r{R:g}'] - oc.COST / q.risk
            cells = [q[(q.date >= a) & (q.date <= b)] for nm, a, b in yrs] + [q]
            print(f'   {lab + f" {R:g}R":<26}' + ''.join(f'{100 * (z[f"r{R:g}"] > 0).mean():5.0f}% {z.n.sum():+6.1f}R' for z in cells) + f'{len(q) / 5:7.0f}', flush=True)


if __name__ == '__main__':
    main()
