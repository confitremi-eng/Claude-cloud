"""NQ 5m: why does the daily-SMA5 filter look worse under today's rules? Split it into its parts. Five years.

  cd indicators/backtest
  python3 -I rbs/nq5m_sma5_split.py

v3 5m: trend 0-180 minutes + MIX, 2R, events, FOMC, junk time. Two sets of time rules: 'now' (ET 15:15-18:30, Monday
Taipei 06-15) and 'old' (ET 15:45-18:30, no Monday rule, as when the SMA5 filter was adopted on 2026-10-21).
SMA5 parts: trend side (buy above / sell below), MIX side (breakout price vs SMA5), MIX distance (>= 0.25% from SMA5).
Per year: win rate / net R; trades.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import setup_study as ss
import market_matrix as mm
import oos_check as oc
import daily_sma5 as dsm


def main():
    one = oc.load(); M = oc.Market(one); D = dsm.daily(one)
    C = M.ctx(5); df = C.df; th = df.thr.values; c = df.close.values
    dt = pd.DatetimeIndex(df.datetime); dt = dt.tz_localize('UTC') if dt.tz is None else dt
    ny = (dt + pd.Timedelta(minutes=5)).tz_convert(ss.NY); m = np.asarray(ny.hour * 60 + ny.minute)
    tp = ny.tz_convert('Asia/Taipei'); tm = np.asarray(tp.hour * 60 + tp.minute)
    day = (dt.tz_convert(ss.NY) + pd.Timedelta(hours=6)).normalize(); sma = D.sma.reindex(day).values
    s = mm.trend_signals(df, M.H, 5, 20, 8)
    mix_all = oc.mix_list(C)
    yrs = list(oc.YEARS); yrs[-1] = (yrs[-1][0], yrs[-1][1], '2099-12-31')
    for rules in ('now', 'old'):
        junk = (m >= 720) & (m <= 785)
        off = junk | (((m >= 915) & (m < 1110)) | ((np.asarray(tp.weekday) == 0) & (tm >= 360) & (tm < 900)) if rules == 'now' else (m >= 945) & (m < 1110))
        T0 = s[(s.side == s.h1) & (s.risk_atr >= 0.95) & ~ss.EVT(s) & (s.slow < 3) & (s.spread > th[s.i]) & (s.tm < 180) & ~s.date.isin(ss.FOMC) & ~off[s.i]]
        M0 = [z for z in mix_all if C.date[z[0]] not in ss.FOMC and not off[z[0]]]
        tside = np.sign(c[T0.i.values] - sma[T0.i.values]) == T0.side.values
        mside = lambda z: np.sign(z[2] - sma[z[0]]) == z[1]
        mfar = lambda z: abs(z[2] - sma[z[0]]) / z[2] * 100 >= 0.25
        print(f'\n######## NQ 5m 2R，時間規則 = {"現在（15:15、週一）" if rules == "now" else "舊（15:45、沒有週一）"}，每格：勝率 / 淨 R')
        print(f'   {"":<30}' + ''.join(f'{nm[:2] + " " + nm[3:8]:>15}' for nm, a, b in yrs) + f'{"合計":>15}{"筆/年":>7}')
        for lab, T, mx in (('不過濾', T0, M0), ('只有趨勢順 SMA5', T0[tside], M0), ('只有 MIX 順 SMA5', T0, [z for z in M0 if mside(z)]),
                           ('只有 MIX 離 SMA5 ≥ 0.25%', T0, [z for z in M0 if mfar(z)]), ('趨勢 + MIX 順 SMA5', T0[tside], [z for z in M0 if mside(z)]),
                           ('趨勢順 + MIX 離 ≥ 0.25%', T0[tside], [z for z in M0 if mfar(z)]), ('全部（現在 v3）', T0[tside], [z for z in M0 if mside(z) and mfar(z)])):
            t = oc.sim(C, T.sort_values('i'), mx, 2.0, 2.0)
            cells = [t[(t.date >= a) & (t.date <= b)] for nm, a, b in yrs] + [t]
            print(f'   {lab:<30}' + ''.join(f'{100 * (z.R > 0).mean():5.0f}% {z.net.sum():+6.1f}R' for z in cells) + f'{len(t) / 5:7.0f}', flush=True)
            if lab == '不過濾':
                for kd in ('趨勢', 'MIX'):
                    z = t[(t.kind == kd) & (t.date >= yrs[-1][1])]
                    print(f'      其中 v3 那年 {kd}：{len(z)} 筆 {100 * (z.R > 0).mean():.0f}% {z.net.sum():+.1f}R')


if __name__ == '__main__':
    main()
