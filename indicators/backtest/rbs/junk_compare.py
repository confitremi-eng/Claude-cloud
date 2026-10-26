"""Junk time (ET 12:00-13:05): trade it or not, on NQ 2m (24-hour, v3 as now) and QQQ 1m (NQ RTH 1m). Five years.

  cd indicators/backtest
  python3 -I rbs/junk_compare.py

NQ 2m: trend + MIX, one at a time, with today's other time filters (ET 15:15-18:30, Monday Taipei 06-15, events, FOMC),
1R and 3R. QQQ 1m: oos_check.nq_rth signals (no super-trend buys), 1R and 3R; the junk-time version drops signals
entered in 12:00-13:05 before trading them one at a time. Per year: win rate / net R; trades.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import setup_study as ss
import market_matrix as mm
import oos_check as oc


def main():
    one = oc.load(); M = oc.Market(one)
    yrs = list(oc.YEARS); yrs[-1] = (yrs[-1][0], yrs[-1][1], '2099-12-31')
    hdr = f'   {"":<22}' + ''.join(f'{nm[:2] + " " + nm[3:8]:>15}' for nm, a, b in yrs) + f'{"合計":>15}{"筆/年":>7}'

    def line(lab, t, rcol='R', ncol='net'):
        cells = [t[(t.date >= a) & (t.date <= b)] for nm, a, b in yrs] + [t]
        print(f'   {lab:<22}' + ''.join(f'{100 * (z[rcol] > 0).mean():5.0f}% {z[ncol].sum():+6.0f}R' for z in cells) + f'{len(t) / 5:7.0f}', flush=True)

    # NQ 2m
    C = M.ctx(2); df = C.df; th = df.thr.values
    ny = pd.DatetimeIndex(df.datetime) + pd.Timedelta(minutes=2); ny = (ny.tz_localize('UTC') if ny.tz is None else ny).tz_convert(ss.NY)
    m = np.asarray(ny.hour * 60 + ny.minute); tp = ny.tz_convert('Asia/Taipei'); tm = np.asarray(tp.hour * 60 + tp.minute)
    junk = (m >= 720) & (m <= 785)
    other = ((m >= 915) & (m < 1110)) | ((np.asarray(tp.weekday) == 0) & (tm >= 360) & (tm < 900))
    s = mm.trend_signals(df, M.H, 2, 20, 8)
    T0 = s[(s.side == s.h1) & (s.risk_atr >= 0.95) & ~ss.EVT(s) & (s.slow < 3) & (s.spread > th[s.i]) & (s.tm < 400) & ~s.date.isin(ss.FOMC) & ~other[s.i]]
    mix0 = [x for x in oc.mix_list(C) if C.date[x[0]] not in ss.FOMC and not other[x[0]]]
    print('######## NQ 2m（趨勢 + MIX）\n' + hdr)
    for R in (1.0, 3.0):
        for lab, skip in ((f'垃圾時間不做（現在） {R:g}R', True), (f'垃圾時間照做 {R:g}R', False)):
            T = T0[~junk[T0.i.values]] if skip else T0
            mix = [x for x in mix0 if not (skip and junk[x[0]])]
            line(lab, oc.sim(C, T.sort_values('i'), mix, R, R))
    # QQQ 1m
    cash = mm.cash_only(one); tdq = mm.minute_trend(cash); Hq = mm.hourly(cash, True)
    df1, _ = oc.nq_rth(one, detail=True)
    s1 = mm.trend_signals(df1, Hq, 1, 35, 8)
    dn = mm.chart(one, mm.minute_trend(one), 2, 10.0, 35.0); c2 = dn.close.values
    aF = 1 - (1 - 2 / 1131) ** 24; aS = 1 - (1 - 2 / 1131) ** 8
    d2 = pd.Series(c2).ewm(alpha=aF, adjust=False).mean().values - pd.Series(c2).ewm(alpha=aS, adjust=False).mean().values
    ndir = np.where(d2 > 10, 1, np.where(d2 < -10, -1, 0)); nstart = pd.DatetimeIndex(dn.datetime).values.astype('datetime64[ns]').astype(np.int64)
    t_open = pd.DatetimeIndex(df1.last_min.values); t_open = (t_open.tz_localize('UTC') if t_open.tz is None else t_open).values.astype('datetime64[ns]').astype(np.int64)
    k = np.searchsorted(nstart, t_open[s1.i.values], 'right') - 2
    ny1 = pd.DatetimeIndex(df1.datetime) + pd.Timedelta(minutes=1); ny1 = (ny1.tz_localize('UTC') if ny1.tz is None else ny1).tz_convert(ss.NY)
    m1 = np.asarray(ny1.hour * 60 + ny1.minute); tw1 = ny1.tz_convert('Asia/Taipei')
    late = np.asarray((tw1.weekday == 5) & (tw1.hour * 60 + tw1.minute >= 120))
    B = s1[(s1.side == s1.h1) & (s1.risk_atr >= 1.0) & ~ss.EVT(s1) & (s1.slow < 7.0) & (s1.spread > df1.thr.values[s1.i]) & (ndir[k] * s1.side.values >= 0) & ~late[s1.i]]
    j1 = (m1 >= 720) & (m1 <= 785)
    print('\n######## QQQ 1m（NQ RTH 1m）\n' + hdr)
    for R in (1.0, 3.0):
        for lab, skip in ((f'垃圾時間照做（現在） {R:g}R', False), (f'垃圾時間不做 {R:g}R', True)):
            T = B[~j1[B.i.values]] if skip else B
            q = ss.seq(T.sort_values('i'), R).copy(); q['n'] = q[f'r{R:g}'] - oc.COST / q.risk
            line(lab, q, f'r{R:g}', 'n')


if __name__ == '__main__':
    main()
