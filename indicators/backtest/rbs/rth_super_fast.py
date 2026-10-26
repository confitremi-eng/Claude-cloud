"""QQQ 1m (NQ RTH 1m): should the super-trend buys (Trend Judge above 120, stage 10) also stay within X ATR of the 5s
fast line, like the normal trend buys (now 1.0 ATR)? Five years.

  cd indicators/backtest
  python3 -I rbs/rth_super_fast.py

Base = QQQ 1m as now (35, 0, 8, 1 with the ETF filters, buys within 1.0 ATR of the fast line). Super buys added with no
limit or a fast-line limit of 1.0 / 1.5 / 2 / 3 ATR. One at a time; per year win rate / net R at 1R and 3R. Also the super
buys on their own by fast-line distance band.
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
    df = oc.chart(cash, tdq, 1, 20.0, 40.0)
    dn = mm.chart(one, mm.minute_trend(one), 2, 10.0, 35.0); c2 = dn.close.values
    aF = 1 - (1 - 2 / 1131) ** 24; aS = 1 - (1 - 2 / 1131) ** 8
    d2 = pd.Series(c2).ewm(alpha=aF, adjust=False).mean().values - pd.Series(c2).ewm(alpha=aS, adjust=False).mean().values
    ndir = np.where(d2 > 10, 1, np.where(d2 < -10, -1, 0)); nstart = pd.DatetimeIndex(dn.datetime).values.astype('datetime64[ns]').astype(np.int64)
    t_open = pd.DatetimeIndex(df.last_min.values); t_open = (t_open.tz_localize('UTC') if t_open.tz is None else t_open).values.astype('datetime64[ns]').astype(np.int64)
    tw = pd.DatetimeIndex(df.datetime + pd.Timedelta(minutes=1)); tw = (tw.tz_localize('UTC') if tw.tz is None else tw).tz_convert('Asia/Taipei')
    late = np.asarray((tw.weekday == 5) & (tw.hour * 60 + tw.minute >= 120))
    h, l, c = df.high.values, df.low.values, df.close.values
    tr = np.maximum(h - l, np.maximum(abs(h - np.r_[c[0], c[:-1]]), abs(l - np.r_[c[0], c[:-1]])))
    atr = pd.Series(tr).ewm(alpha=1 / 14, adjust=False).mean().values
    fast = df.emaS.values + df.tj_diff.values
    s = mm.trend_signals(df, Hq, 1, 35, 8)
    k = np.searchsorted(nstart, t_open[s.i.values], 'right') - 2
    s['fast'] = (c[s.i] - fast[s.i]) * s.side / atr[s.i]
    base = s[(s.side == s.h1) & (s.risk_atr >= 1.0) & ~ss.EVT(s) & (s.slow < 7.0) & (s.spread > df.thr.values[s.i]) & (ndir[k] * s.side.values >= 0) & ~late[s.i]
             & ~((s.side == 1) & (s.fast > 1.0))]
    x = mm.trend_signals(df, Hq, 1, 10, 8)
    x['fast'] = (c[x.i] - fast[x.i]) * x.side / atr[x.i]
    x = x[(x.side == 1) & (x.spread > 120) & ~ss.EVT(x) & ~x.date.isin(ss.FOMC) & ~late[x.i] & ~x.i.isin(base.i)]
    split = oc.YEARS[-1][1]
    print('######## 超強趨勢買單單獨算：離快線（ATR）')
    for a, b in ((-9, 1.0), (1.0, 1.5), (1.5, 2.0), (2.0, 3.0), (3.0, 99)):
        out = []
        for per, z in (('v3 那年', x[x.date >= split]), ('前 4 年', x[x.date < split])):
            q = z[(z.fast > a) & (z.fast <= b)]
            out.append(f'{per} {len(q):4d} 個 1R {100 * (q.r1 >= 1).mean() if len(q) else 0:3.0f}% 3R 每筆 {(q.r3 - oc.COST / q.risk).mean() if len(q) else 0:+.2f}R')
        print(f'   {(f"≤ {b:g}" if a < -8 else f"{a:g}–{b:g}"):<8}' + '   '.join(out))
    yrs = list(oc.YEARS); yrs[-1] = (yrs[-1][0], yrs[-1][1], '2099-12-31')
    print('\n######## 一次一筆，每格：勝率 / 淨 R')
    print(f'   {"":<26}' + ''.join(f'{nm[:2] + " " + nm[3:8]:>15}' for nm, a, b in yrs) + f'{"合計":>15}{"筆/年":>7}')
    for R in (1.0, 3.0):
        rows = [('只有一般訊號（快線 1.0）', base), ('+ 超強買，不限快線（現在）', pd.concat([base, x]))] + \
               [(f'+ 超強買，快線 ≤ {v:g}', pd.concat([base, x[x.fast <= v]])) for v in (1.0, 1.5, 2.0, 3.0)]
        for lab, T in rows:
            q = ss.seq(T.sort_values('i'), R).copy(); q['n'] = q[f'r{R:g}'] - oc.COST / q.risk
            cells = [q[(q.date >= a) & (q.date <= b)] for nm, a, b in yrs] + [q]
            print(f'   {lab + f" {R:g}R":<26}' + ''.join(f'{100 * (z[f"r{R:g}"] > 0).mean():5.0f}% {z.n.sum():+6.1f}R' for z in cells) + f'{len(q) / 5:7.0f}', flush=True)


if __name__ == '__main__':
    main()
