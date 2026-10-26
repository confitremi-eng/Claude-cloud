"""NQ v3 2m / 5m: stop trading for the day after N stops? (the 2026-10-26 Monday: five stops in a row in a range day)

  cd indicators/backtest
  python3 -I rbs/daily_stop_rule.py

v3 as now (pre-close window from ET 15:15). Trades from oc.sim (trend + MIX, one at a time); the rule is applied to
that list in order (trades after the N-th stop of the same trading date are dropped; signals that the dropped trades
blocked are not added back, so the count is slightly low). Rules: N stops in a row, N stops in the day.
Per year: win rate / net R at 1R and the target; trades dropped.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import setup_study as ss
import market_matrix as mm
import oos_check as oc


def apply(t, n, kind):
    keep = []; cur = None; cnt = 0
    for d, r in zip(t.date.values, t.R.values):
        if d != cur: cur, cnt = d, 0
        if cnt >= n: keep.append(False); continue
        keep.append(True)
        if r < 0: cnt += 1
        elif kind == '連續': cnt = 0
    return t[np.array(keep)]


def main():
    one = oc.load(); M = oc.Market(one)
    yrs = list(oc.YEARS); yrs[-1] = (yrs[-1][0], yrs[-1][1], '2099-12-31')
    for tf, hi, R in ((2, 400, 3.0), (5, 180, 2.0)):
        C = M.ctx(tf); df = C.df; th = df.thr.values
        ny = pd.DatetimeIndex(df.datetime) + pd.Timedelta(minutes=tf); ny = (ny.tz_localize('UTC') if ny.tz is None else ny).tz_convert(ss.NY)
        m = np.asarray(ny.hour * 60 + ny.minute); off = ((m >= 720) & (m <= 785)) | ((m >= 915) & (m < 1110))
        s = mm.trend_signals(df, M.H, tf, 20, 8)
        T = s[(s.side == s.h1) & (s.risk_atr >= 0.95) & ~ss.EVT(s) & (s.slow < 3) & (s.spread > th[s.i]) & (s.tm < hi) & ~s.date.isin(ss.FOMC) & ~off[s.i]]
        mix = [x for x in oc.mix_list(C) if C.date[x[0]] not in ss.FOMC and not off[x[0]]]
        print(f'\n######## NQ {tf}m，每格：勝率 / 淨 R')
        print(f'   {"":<22}' + ''.join(f'{nm[:2] + " " + nm[3:8]:>15}' for nm, a, b in yrs) + f'{"合計":>15}{"少掉":>6}')
        for RR in (1.0, R):
            t0 = oc.sim(C, T.sort_values('i'), mix, RR, RR)
            print(f'目標 {RR:g}R')
            for lab, n, kind in (('v3 現在', 99, '累計'), ('連停 2 次當天不做', 2, '連續'), ('連停 3 次當天不做', 3, '連續'),
                                 ('當天停 2 次不做', 2, '累計'), ('當天停 3 次不做', 3, '累計'), ('當天停 4 次不做', 4, '累計')):
                t = apply(t0, n, kind)
                cells = [t[(t.date >= a) & (t.date <= b)] for nm, a, b in yrs] + [t]
                print(f'   {lab:<22}' + ''.join(f'{100 * (z.R > 0).mean():5.0f}% {z.net.sum():+6.0f}R' for z in cells) + f'{len(t0) - len(t):6d}', flush=True)


if __name__ == '__main__':
    main()
