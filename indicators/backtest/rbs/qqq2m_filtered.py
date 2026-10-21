"""QQQ 2m (NQ cash-session 2m bars) with v3's ETF filters and stage 35 / 40 / 50, EMA 8, targets 1R / 2R / 3R.

  cd indicators/backtest
  python3 -I rbs/qqq2m_filtered.py

Filters as v3's QQQ setting: Trend Judge 20 / 40 (cash data) on the signal's side (or only strong, > 40), 1h EMA20,
stop >= 0.95 ATR, slow line <= 7 ATR, NQ 2m not opposite, event windows, FOMC days, Friday cut-off. One at a time.
Per year: win rate / R. Reference: NQ RTH 1m (35, 0, 8, 1).
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
    dn = mm.chart(one, mm.minute_trend(one), 2, 10.0, 35.0); c2 = dn.close.values
    aF = 1 - (1 - 2 / 1131) ** 24; aS = 1 - (1 - 2 / 1131) ** 8
    d2 = pd.Series(c2).ewm(alpha=aF, adjust=False).mean().values - pd.Series(c2).ewm(alpha=aS, adjust=False).mean().values
    ndir = np.where(d2 > 10, 1, np.where(d2 < -10, -1, 0)); nstart = pd.DatetimeIndex(dn.datetime).values.astype('datetime64[ns]').astype(np.int64)
    print(f'   {"":<34}' + ''.join(f'{nm[:2] + " " + nm[3:8]:>15}' for nm, a, b in oc.YEARS) + '   筆 / 年')
    for tf in (1, 2):
        df = oc.chart(cash, tdq, tf, 20.0, 40.0)
        t_open = pd.DatetimeIndex(df.last_min.values); t_open = (t_open.tz_localize('UTC') if t_open.tz is None else t_open).values.astype('datetime64[ns]').astype(np.int64)
        ny = (pd.DatetimeIndex(df.datetime).tz_localize('UTC') if pd.DatetimeIndex(df.datetime).tz is None else pd.DatetimeIndex(df.datetime)) + pd.Timedelta(minutes=tf)
        tw = ny.tz_convert('Asia/Taipei'); late = np.asarray((tw.weekday == 5) & (tw.hour * 60 + tw.minute >= 120))
        for stage in ((35,) if tf == 1 else (35, 40, 50)):
            s = mm.trend_signals(df, Hq, tf, stage, 8)
            k = np.searchsorted(nstart, t_open[s.i.values], 'right') - 2
            s = s[(s.side == s.h1) & (s.risk_atr >= 0.95) & ~ss.EVT(s) & (s.slow < 7.0) & (s.spread > df.thr.values[s.i]) & (ndir[k] * s.side.values >= 0) & ~s.date.isin(ss.FOMC) & ~late[s.i]]
            for strong in ((False,) if tf == 1 else (False, True)):
                z0 = s[s.spread > 40] if strong else s
                for R in (1.0, 2.0, 3.0):
                    t = ss.seq(z0.sort_values('i'), R); col = f'r{R:g}'
                    tt = pd.DataFrame({'date': t.date.values, 'R': t[col].values, 'net': t[col].values - oc.COST / t.risk.values})
                    lab = f'{tf}m ({stage},0,8,1){" 只強勢" if strong else ""} {R:g}R'
                    print(f'   {lab:<34}' + ''.join(f'{100 * (z.R > 0).mean():5.0f}% {z.net.sum():+5.0f}R' for z in (tt[(tt.date >= a) & (tt.date <= b)] for nm, a, b in oc.YEARS)) + f'   {len(tt) / 5:.0f}', flush=True)


if __name__ == '__main__':
    main()
