"""Remi Superb settings on NQ 2 minutes (the Databento year).

  cd indicators/backtest
  NQ_DATA=data/NQ_1m_databento.csv python3 rbs/superb_study.py

Prints
  1. Trend Judge thresholds 20/40 vs 15/35 x avoid the Asia session / keep it / Asia only (2R)
  2. cash session only (09:30-16:00 ET by signal bar start), 15/35 and 20/40: R, points, months
  3. cash session, long and short separately, and each side traded alone
  4. cash session with and without the stop >= 1 ATR filter

Filter = the filtered alerts with 「有趨勢（一般 + 強）」: Trend Judge UP / 強UP for a buy (DOWN / 強Down
for a sell), last complete 1-hour close on the same side of its EMA20, stop >= 1 ATR, the data / open /
close / Globex windows avoided. Signals, exits and costs come from setup_study.py (2R unless stated,
one position at a time, 1 point cost, 1 contract for the point totals).
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import rbs
import setup_study as ss
from remi_export import signals

TREND = lambda x: (x.side * x.dir >= 1) & (x.side == x.h1)
RISK = lambda x: x.risk_atr >= 1.0
BASE = lambda x: TREND(x) & ~ss.EVT(x) & RISK(x)


def build2(th):
    """2-minute signals with context for one pair of Trend Judge thresholds."""
    rbs.TH['NQ'] = th
    rbs._cache.pop(('NQ', 2), None)
    H = ss.hourly(); tf = 2
    df = rbs.prepared('NQ', tf)
    B, S = signals(df)
    h, l, c = df.high.values, df.low.values, df.close.values
    nxt, atr = ss.bar_context(df, tf)
    rows = []
    for i in np.where((B == 1) | (S == 1))[0]:
        if i < 15 or not df.tradable.values[i]: continue
        end = min(i + ss.HORIZON, nxt[i])
        if end <= i: continue
        k = 1 if B[i] else -1
        stop = min(l[i - 1], l[i]) if k == 1 else max(h[i - 1], h[i])
        risk = (c[i] - stop) * k
        if not risk > 0: continue
        rows.append([tf, i, k, risk, (h[i] - l[i]) / atr[i - 1], risk / atr[i - 1]] + ss.outcome(h, l, c, i, k, stop, end))
    cols = ['tf', 'i', 'side', 'risk', 'bar_atr', 'risk_atr']
    for R in ss.TARGETS: cols += [f'r{R:g}', f'x{R:g}']
    s = ss.add_context(pd.DataFrame(rows, columns=cols), df, tf, H).sort_values('i')
    days = (df.datetime[df.tradable].dt.tz_convert(ss.NY) + pd.Timedelta(hours=6)).dt.date.astype(str).nunique()
    return s, days


def pts_line(t, R=2.0):
    r = t[f'r{R:g}'].values; pts = r * t.risk.values - ss.COST
    eq = np.cumsum(pts); dd = float(np.max(np.maximum.accumulate(np.r_[0, eq])[1:] - eq)) if len(eq) else 0.0
    mon = pd.Series(pts, index=t.month.values).groupby(level=0).sum()
    a = t.date.values < ss.SPLIT
    return (f'{len(t):4d} 筆  勝率 {100 * (r > 0).mean():4.1f}%  停損中位數 {np.median(t.risk):4.1f} 點  合計 {pts.sum():+6.0f} 點'
            f'（前 {pts[a].sum():+5.0f} 後 {pts[~a].sum():+5.0f}）  回撤 {dd:4.0f} 點  賺錢月份 {(mon > 0).sum()}/{len(mon)}  最差月 {mon.min():+4.0f}')


def main():
    S = {th: build2(th) for th in ((20.0, 40.0), (15.0, 35.0))}

    print('\n######## 1. 門檻 × 亞洲盤（2m 2R）')
    for th, (s, days) in S.items():
        for nm, f in (('避開亞洲盤', lambda x: BASE(x) & ~x.asia), ('不避開亞洲盤', BASE), ('只做亞洲盤', lambda x: BASE(x) & x.asia)):
            print(f'  {th[0]:g}/{th[1]:g} {nm:<6} {ss.fmt(ss.stats(ss.seq(s[f(s)], 2.0), 2.0, days))}')

    print('\n######## 2. 只做現金盤（美東 09:30-16:00）')
    for th, (s, days) in S.items():
        sub = s[BASE(s) & s.rth]
        for R in (1.0, 2.0, 3.0):
            print(f'  {th[0]:g}/{th[1]:g} {R:g}R  {ss.fmt(ss.stats(ss.seq(sub, R), R, days))}')
        t = ss.seq(sub, 2.0)
        print(f'  {th[0]:g}/{th[1]:g} 2R 點數  {pts_line(t)}')
        mon = pd.Series((t.r2 * t.risk - ss.COST).values, index=t.month.values).groupby(level=0).sum()
        print('    逐月點數：' + '，'.join(f'{m} {v:+.0f}' for m, v in mon.items()))
        sub2 = s[TREND(s) & ~s.ev_data & ~s.ev_globex & RISK(s) & s.rth]
        print(f'  {th[0]:g}/{th[1]:g} 2R 不避開開收盤  {ss.fmt(ss.stats(ss.seq(sub2, 2.0), 2.0, days))}')

    print('\n######## 3. 現金盤，多空分開（2m 2R）')
    for th, (s, days) in S.items():
        sub = s[BASE(s) & s.rth]
        t = ss.seq(sub, 2.0)
        for sd, nm in ((1, '作多'), (-1, '做空')):
            print(f'  {th[0]:g}/{th[1]:g} 多空都做時的{nm}  {pts_line(t[t.side == sd])}')
        for sd, nm in ((1, '只作多'), (-1, '只做空')):
            print(f'  {th[0]:g}/{th[1]:g} {nm:<10}  {pts_line(ss.seq(sub[sub.side == sd], 2.0))}')

    print('\n######## 4. 現金盤，停損 >= 1 ATR 拿掉（2m 2R，15/35）')
    s, days = S[(15.0, 35.0)]
    core = TREND(s) & ~ss.EVT(s) & s.rth
    for nm, m in (('有 >= 1 ATR（現在）', core & RISK(s)), ('拿掉', core), ('只看 < 1 ATR', core & ~RISK(s))):
        t = ss.seq(s[m], 2.0)
        print(f'  {nm:<12} {pts_line(t)}  每筆淨 {(t.r2 - ss.COST / t.risk).mean():+.3f}R')


if __name__ == '__main__':
    main()
