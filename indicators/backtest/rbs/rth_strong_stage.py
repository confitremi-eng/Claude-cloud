"""NQ RTH 1m (QQQ setting): while Trend Judge is strong (beyond 40), also take signals of a shorter stage (shallower
pullbacks); otherwise the usual (35, 0, 8, 1). Five years.

  cd indicators/backtest
  python3 -I rbs/rth_strong_stage.py

Same filters as rth_stage.py (Trend Judge 20 / 40, 1h EMA20, stop >= 0.95 ATR, slow line <= 7 ATR, NQ 2m not opposite,
events, FOMC, Friday cut-off; junk time not applied, as v3 now does on NQ RTH). Extra signals from stage S (S = 15 / 20 /
25 / 30) are added only when the spread is beyond 40 on the signal's side. One at a time, 3R (and 1R). Per year: win rate / R.
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
    ny = (pd.DatetimeIndex(df.datetime).tz_localize('UTC') if pd.DatetimeIndex(df.datetime).tz is None else pd.DatetimeIndex(df.datetime)) + pd.Timedelta(minutes=1)
    tw = ny.tz_convert('Asia/Taipei'); late = np.asarray((tw.weekday == 5) & (tw.hour * 60 + tw.minute >= 120))

    def sigs(stage):
        s = mm.trend_signals(df, Hq, 1, stage, 8)
        k = np.searchsorted(nstart, t_open[s.i.values], 'right') - 2
        return s[(s.side == s.h1) & (s.risk_atr >= 0.95) & ~ss.EVT(s) & (s.slow < 7.0) & (s.spread > df.thr.values[s.i]) & (ndir[k] * s.side.values >= 0)
                 & ~s.date.isin(ss.FOMC) & ~late[s.i]]

    base = sigs(35)
    print(f'   {"":<30}' + ''.join(f'{nm[:2] + " " + nm[3:8]:>15}' for nm, a, b in oc.YEARS) + '   筆 / 年')
    for R in (3.0, 1.0):
        def row(lab, s):
            t = ss.seq(s.sort_values('i'), R); col = f'r{R:g}'
            tt = pd.DataFrame({'date': t.date.values, 'R': t[col].values, 'net': t[col].values - oc.COST / t.risk.values})
            print(f'   {lab:<30}' + ''.join(f'{100 * (z.R > 0).mean():5.0f}% {z.net.sum():+5.0f}R' for z in (tt[(tt.date >= a) & (tt.date <= b)] for nm, a, b in oc.YEARS)) + f'   {len(tt) / 5:.0f}', flush=True)
        row(f'(35, 8)（v3），{R:g}R', base)
        for st in (15, 20, 25, 30):
            x = sigs(st); x = x[x.spread > 40]
            row(f'+ 強勢時 ({st}, 8)，{R:g}R', pd.concat([base, x[~x.i.isin(base.i)]]))


if __name__ == '__main__':
    main()
