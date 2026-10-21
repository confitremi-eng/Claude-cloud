"""NQ RTH 1m (QQQ setting) in a strong trend: allow signals that are far from the slow line when they are close to the fast
line, and optionally also shorter-stage signals there. Five years.

  cd indicators/backtest
  python3 -I rbs/rth_fastline.py

Base = v3's NQ RTH rules (35, 0, 8, 1), slow line <= 7 ATR (junk time not applied). Strong = Trend Judge beyond 40 on the
signal's side. 'Near fast' = close within X ATR of the 5 s EMA1130 on the trade's side (0 <= distance <= X).
  A : + strong & near fast & beyond 7 ATR from the slow line, stage 35
  B : A plus stage S (20 / 25) signals when strong & near fast (any slow-line distance)
One at a time, 3R and 1R. Per year: win rate / R.
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
    df = oc.chart(cash, tdq, 1, 20.0, 40.0); c = df.close.values
    dn = mm.chart(one, mm.minute_trend(one), 2, 10.0, 35.0); c2 = dn.close.values
    aF = 1 - (1 - 2 / 1131) ** 24; aS = 1 - (1 - 2 / 1131) ** 8
    d2 = pd.Series(c2).ewm(alpha=aF, adjust=False).mean().values - pd.Series(c2).ewm(alpha=aS, adjust=False).mean().values
    ndir = np.where(d2 > 10, 1, np.where(d2 < -10, -1, 0)); nstart = pd.DatetimeIndex(dn.datetime).values.astype('datetime64[ns]').astype(np.int64)
    t_open = pd.DatetimeIndex(df.last_min.values); t_open = (t_open.tz_localize('UTC') if t_open.tz is None else t_open).values.astype('datetime64[ns]').astype(np.int64)
    ny = (pd.DatetimeIndex(df.datetime).tz_localize('UTC') if pd.DatetimeIndex(df.datetime).tz is None else pd.DatetimeIndex(df.datetime)) + pd.Timedelta(minutes=1)
    tw = ny.tz_convert('Asia/Taipei'); late = np.asarray((tw.weekday == 5) & (tw.hour * 60 + tw.minute >= 120))
    F = tdq['emaF'].reindex(pd.DatetimeIndex(df.last_min)).values
    _, atr = ss.bar_context(df, 1)

    def sigs(stage):
        s = mm.trend_signals(df, Hq, 1, stage, 8)
        k = np.searchsorted(nstart, t_open[s.i.values], 'right') - 2
        s = s[(s.side == s.h1) & (s.risk_atr >= 0.95) & ~ss.EVT(s) & (s.spread > df.thr.values[s.i]) & (ndir[k] * s.side.values >= 0) & ~s.date.isin(ss.FOMC) & ~late[s.i]].copy()
        s['fast'] = (c[s.i.values] - F[s.i.values]) * s.side.values / atr[s.i.values]
        return s

    s35 = sigs(35); base = s35[s35.slow < 7.0]
    def row(lab, S, R):
        t = ss.seq(S.sort_values('i'), R); col = f'r{R:g}'
        tt = pd.DataFrame({'date': t.date.values, 'R': t[col].values, 'net': t[col].values - oc.COST / t.risk.values})
        print(f'   {lab:<38}' + ''.join(f'{100 * (z.R > 0).mean():5.0f}% {z.net.sum():+5.0f}R' for z in (tt[(tt.date >= a) & (tt.date <= b)] for nm, a, b in oc.YEARS)) + f'   {len(tt) / 5:.0f} 筆 / 年', flush=True)
    for R in (3.0, 1.0):
        print(f'\nNQ RTH 1m（{R:g}R）每年：勝率 / 合計 R')
        print(f'   {"":<38}' + ''.join(f'{nm[:2] + " " + nm[3:8]:>15}' for nm, a, b in oc.YEARS))
        row('v3（離慢線 ≤ 7 ATR）', base, R)
        for X in (2.0, 3.5, 5.0):
            far = s35[(s35.slow >= 7.0) & (s35.spread > 40) & (s35.fast >= 0) & (s35.fast <= X)]
            row(f'A：強勢 + 離快線 ≤ {X:g} ATR 就不看慢線', pd.concat([base, far]), R)
        for st in (20, 25):
            x = sigs(st); x = x[(x.spread > 40) & (x.fast >= 0) & (x.fast <= 3.5)]
            far = s35[(s35.slow >= 7.0) & (s35.spread > 40) & (s35.fast >= 0) & (s35.fast <= 3.5)]
            add = pd.concat([far, x[~x.i.isin(s35.i)]])
            row(f'B：A（3.5）+ 強勢靠快線時階段 {st}', pd.concat([base, add[~add.i.isin(base.i)]]), R)


if __name__ == '__main__':
    main()
