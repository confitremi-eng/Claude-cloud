"""NQ RTH 1m (v3's QQQ setting): the signal stage 15-60 and EMA 5 / 8 / 13, five years.

  cd indicators/backtest
  python3 -I rbs/rth_stage.py [nojunk]

Same as oos_check.nq_rth (Trend Judge 20 / 40, 1h EMA20 from cash-session data, slow line <= 7 ATR, NQ 2m not opposite,
3R, Friday cut-off) plus today's stop >= 0.95 ATR, FOMC days and the junk time (12:00-13:05) off. Each signal on its own
for the 1R / 3R hit rate, and one at a time for R per year.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import setup_study as ss
import market_matrix as mm
import oos_check as oc

JUNK = len(sys.argv) < 2 or sys.argv[1] != "nojunk"     # python3 -I rbs/rth_stage.py nojunk：不套垃圾時間


def main():
    one = oc.load()
    cash = mm.cash_only(one); tdq = mm.minute_trend(cash); Hq = mm.hourly(cash, True)
    df = oc.chart(cash, tdq, 1, 20.0, 40.0)
    dn = mm.chart(one, mm.minute_trend(one), 2, 10.0, 35.0)
    c2 = dn.close.values
    aF = 1 - (1 - 2 / 1131) ** 24; aS = 1 - (1 - 2 / 1131) ** 8
    d2 = pd.Series(c2).ewm(alpha=aF, adjust=False).mean().values - pd.Series(c2).ewm(alpha=aS, adjust=False).mean().values
    ndir = np.where(d2 > 10, 1, np.where(d2 < -10, -1, 0))
    nstart = pd.DatetimeIndex(dn.datetime).values.astype('datetime64[ns]').astype(np.int64)
    t_open = pd.DatetimeIndex(df.last_min.values); t_open = (t_open.tz_localize('UTC') if t_open.tz is None else t_open).values.astype('datetime64[ns]').astype(np.int64)
    ny = (pd.DatetimeIndex(df.datetime).tz_localize('UTC') if pd.DatetimeIndex(df.datetime).tz is None else pd.DatetimeIndex(df.datetime)) + pd.Timedelta(minutes=1)
    tw = ny.tz_convert('Asia/Taipei'); late = np.asarray((tw.weekday == 5) & (tw.hour * 60 + tw.minute >= 120))
    m = np.asarray(ny.tz_convert(ss.NY).hour * 60 + ny.tz_convert(ss.NY).minute); junk = (m >= 720) & (m <= 785)
    print(f'NQ RTH 1m（3R）每年：勝率 / 合計 R；每個訊號單獨：1R / 3R 命中（v3 那年）')
    print(f'   {"(階段, EMA)":<14}' + ''.join(f'{nm[:2] + " " + nm[3:8]:>15}' for nm, a, b in oc.YEARS) + '   v3 那年單獨 1R / 3R、筆 / 年')
    for stage in (15, 20, 25, 30, 35, 40, 50, 60):
        for ema in ((5, 8, 13) if stage in (30, 35, 40) else (8,)):
            s = mm.trend_signals(df, Hq, 1, stage, ema)
            k = np.searchsorted(nstart, t_open[s.i.values], 'right') - 2
            ok = (ndir[k] * s.side.values >= 0)
            s = s[(s.side == s.h1) & (s.risk_atr >= 0.95) & ~ss.EVT(s) & (s.slow < 7.0) & (s.spread > df.thr.values[s.i]) & ok
                  & ~s.date.isin(ss.FOMC) & ~(junk[s.i] & JUNK) & ~late[s.i]]
            t = ss.seq(s.sort_values('i'), 3.0)
            tt = pd.DataFrame({'date': t.date.values, 'R': t.r3.values, 'net': t.r3.values - oc.COST / t.risk.values})
            y = s[s.date > oc.YEARS[3][2]]
            lab = f'({stage}, {ema})' + (' ← v3' if (stage, ema) == (35, 8) else '')
            print(f'   {lab:<14}' + ''.join(f'{100 * (z.R > 0).mean():5.0f}% {z.net.sum():+5.0f}R' for z in (tt[(tt.date >= a) & (tt.date <= b)] for nm, a, b in oc.YEARS))
                  + f'   {100 * (y.r1 > 0).mean():3.0f}% / {100 * (y.r3 >= 3).mean():3.0f}%、{len(tt) / 5:.0f}', flush=True)


if __name__ == '__main__':
    main()
