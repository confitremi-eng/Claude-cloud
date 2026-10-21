"""QQQ on the 2-minute chart with today's v3 rules? NQ cash-session bars stand in for QQQ (as in the other QQQ studies).

  cd indicators/backtest
  python3 -I rbs/qqq_2m.py

Cash-session-only NQ (09:30-16:15 New York), 2-minute chart; Trend Judge and the 1h EMA20 from the cash-only data.
  NQ 2m rules : (20, 0, 8, 1), Trend Judge 10 / 35, slow line <= 3 ATR, trend 0-400 min, 3R
  ETF rules   : (35, 0, 8, 1), Trend Judge 20 / 40, slow line <= 7 ATR, no trend window, 3R
both with stop >= 0.95 ATR, event windows, FOMC days off, junk time off; trend only, or trend + MIX breakouts; also 1R.
Baseline: NQ RTH 1m (v3's QQQ setting). One at a time. Per year: win rate / R.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import setup_study as ss
import market_matrix as mm
import oos_check as oc


def main():
    one = oc.load()
    cash = mm.cash_only(one); tdm = mm.minute_trend(cash); H = mm.hourly(cash, True)
    print(f'   {"":<34}' + ''.join(f'{nm[:2] + " " + nm[3:8]:>15}' for nm, a, b in oc.YEARS))
    def row(lab, t):
        print(f'   {lab:<34}' + ''.join(f'{100 * (z.R > 0).mean():5.0f}% {z.net.sum():+5.0f}R' if len(z) else '              -' for z in (t[(t.date >= a) & (t.date <= b)] for nm, a, b in oc.YEARS))
              + f'   {len(t) / 5:.0f} 筆 / 年')
    row('NQ RTH 1m（v3 的 QQQ 做法）', oc.nq_rth(one))
    for th, st, stage, dist, cap, lab in ((10.0, 35.0, 20, 3.0, 400, 'NQ 2m 規則'), (20.0, 40.0, 35, 7.0, 10 ** 6, 'ETF 規則')):
        df = oc.chart(cash, tdm, 2, th, st)
        C = oc.Ctx(df, 2, H)
        ny = (pd.DatetimeIndex(df.datetime).tz_localize('UTC') if pd.DatetimeIndex(df.datetime).tz is None else pd.DatetimeIndex(df.datetime)) + pd.Timedelta(minutes=2)
        ny = ny.tz_convert(ss.NY); m = np.asarray(ny.hour * 60 + ny.minute); junk = (m >= 720) & (m <= 785)
        s = mm.trend_signals(df, H, 2, stage, 8)
        T = s[(s.side == s.h1) & (s.risk_atr >= 0.95) & ~ss.EVT(s) & (s.slow < dist) & (s.spread > df.thr.values[s.i]) & (s.tm < cap) & ~s.date.isin(ss.FOMC) & ~junk[s.i]]
        mix = [x for x in oc.mix_list(C) if C.date[x[0]] not in ss.FOMC and not junk[x[0]]]
        for R in (3.0, 1.0):
            row(f'2m RTH {lab}，只趨勢，{R:g}R', oc.sim(C, T, [], R, R))
            row(f'2m RTH {lab}，趨勢 + MIX，{R:g}R', oc.sim(C, T, mix, R, R))


if __name__ == '__main__':
    main()
