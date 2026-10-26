"""QQQ 1m (NQ RTH 1m) "super-strong trend": while Trend Judge is beyond L on the signal's side, also take a short stage's
signals (close past EMA8), skipping 1h EMA20, slow line and stop size; keep event windows, FOMC days, Friday cut-off.
Buys and sells separately. Five years.

  cd indicators/backtest
  python3 -I rbs/rth_super.py

Base = v3's QQQ setting (oos_check.nq_rth signals: (35, 0, 8, 1), Trend Judge 20 / 40, slow line <= 7 ATR, NQ 2m not
opposite). One at a time, flat at 16:00 / 60 bars, 1 point cost. Per year: win rate / net R at 1R, 2R and 3R (same R for
every trade), and the extra trades alone.
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

    def nqok(s):
        k = np.searchsorted(nstart, t_open[s.i.values], 'right') - 2
        return ndir[k] * s.side.values >= 0
    s = mm.trend_signals(df, Hq, 1, 35, 8)
    base = s[(s.side == s.h1) & (s.risk_atr >= 1.0) & ~ss.EVT(s) & (s.slow < 7.0) & (s.spread > df.thr.values[s.i]) & nqok(s) & ~late[s.i]]
    raw = {st: mm.trend_signals(df, Hq, 1, st, 8) for st in (5, 10, 15, 20)}
    yrs = list(oc.YEARS); yrs[-1] = (yrs[-1][0], yrs[-1][1], '2099-12-31')
    print(f'   {"":<30}' + ''.join(f'{nm[:2] + " " + nm[3:8]:>15}' for nm, a, b in yrs) + f'{"合計":>15}{"筆/年":>7}')

    def row(lab, T, R):
        q = ss.seq(T.sort_values('i'), R).copy(); q['n'] = q[f'r{R:g}'] - oc.COST / q.risk
        cells = [q[(q.date >= a) & (q.date <= b)] for nm, a, b in yrs] + [q]
        print(f'   {lab:<30}' + ''.join(f'{100 * (z[f"r{R:g}"] > 0).mean() if len(z) else 0:5.0f}% {z.n.sum():+6.1f}R' for z in cells) + f'{len(q) / 5:7.0f}', flush=True)

    for R in (1.0, 2.0, 3.0):
        print(f'\n目標 {R:g}R')
        row('QQQ 1m 現在 (35)', base, R)
        for lv in (60, 80, 120):
            for st in (5, 10, 20):
                x = raw[st]; x = x[(x.spread > lv) & ~ss.EVT(x) & ~x.date.isin(ss.FOMC) & ~late[x.i] & ~x.i.isin(base.i)]
                for side, nm in ((1, '買'), (-1, '賣')):
                    xs = x[x.side == side]
                    row(f'+ TJ>{lv} ({st}) 只加{nm}', pd.concat([base, xs]), R)
                row(f'+ TJ>{lv} ({st}) 買賣都加', pd.concat([base, x]), R)
    tp = pd.DatetimeIndex(df.datetime + pd.Timedelta(minutes=1)); tp = (tp.tz_localize('UTC') if tp.tz is None else tp).tz_convert(ss.NY)
    for lv, st in ((120, 10), (120, 5)):
        x = raw[st]; x = x[(x.spread > lv) & ~ss.EVT(x) & ~x.date.isin(ss.FOMC) & ~late[x.i] & ~x.i.isin(base.i) & (x.side == 1)]
        q = ss.seq(pd.concat([base, x]).sort_values('i'), 3.0)
        print(f'\nTJ>{lv} ({st}) 只加買，3R，單邊日的單（美東時間，r3）：')
        for d in ('2026-09-21', '2026-09-22', '2026-10-05', '2026-10-15', '2026-08-13', '2026-09-03'):
            z = q[[f'{tp[i]:%Y-%m-%d}' == d for i in q.i]]
            print(f'   {d}：' + ('、'.join(f'{tp[i]:%H:%M}{"買" if sd > 0 else "賣"}{r:+.1f}' for i, sd, r in zip(z.i, z.side, z.r3)) or '沒有'))


if __name__ == '__main__':
    main()
