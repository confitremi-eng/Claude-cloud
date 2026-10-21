"""Exception to 'too far from the slow line': take a signal that is too far if another raw signal on the same side came
within the previous N bars (a second push). NQ RTH 1m (QQQ setting, limit 7 ATR), five years.

  cd indicators/backtest
  python3 -I rbs/far_confirm.py

Candidates = (35, 0, 8, 1) signals that pass every v3 filter except the slow-line distance. A far one (beyond 7 ATR) is
taken only if an earlier raw signal on the same side ((35, 0, 8, 1), or the shorter (20, 0, 8, 1)) fired within N bars
before it. One at a time, 3R. Also the far signals on their own, with / without the earlier signal.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import setup_study as ss
import market_matrix as mm
import oos_check as oc


def prev_within(sig_bars, sides, j, k, N):
    a = np.searchsorted(sig_bars, j - N); b = np.searchsorted(sig_bars, j)
    return bool((sides[a:b] == k).any())


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
    s = mm.trend_signals(df, Hq, 1, 35, 8)
    k = np.searchsorted(nstart, t_open[s.i.values], 'right') - 2
    base = (s.side == s.h1) & (s.risk_atr >= 0.95) & ~ss.EVT(s) & (s.spread > df.thr.values[s.i]) & (ndir[k] * s.side.values >= 0) & ~s.date.isin(ss.FOMC) & ~late[s.i]
    raws = {'35': mm.trend_signals(df, Hq, 1, 35, 8)[['i', 'side']].sort_values('i'), '20': mm.trend_signals(df, Hq, 1, 20, 8)[['i', 'side']].sort_values('i')}

    def run(S):
        t = ss.seq(S.sort_values('i'), 3.0)
        return pd.DataFrame({'date': t.date.values, 'R': t.r3.values, 'net': t.r3.values - oc.COST / t.risk.values})

    def report(lab, t):
        print(f'   {lab:<34}' + ''.join(f'{100 * (z.R > 0).mean():5.0f}% {z.net.sum():+5.0f}R' for z in (t[(t.date >= a) & (t.date <= b)] for nm, a, b in oc.YEARS)) + f'   {len(t) / 5:.0f} 筆 / 年', flush=True)

    print('NQ RTH 1m（QQQ 做法，3R）每年：勝率 / 合計 R')
    print(f'   {"":<34}' + ''.join(f'{nm[:2] + " " + nm[3:8]:>15}' for nm, a, b in oc.YEARS))
    near = s[base & (s.slow < 7.0)]; far = s[base & (s.slow >= 7.0)]
    report('v3（離慢線 ≤ 7 ATR）', run(near))
    report('不限距離', run(s[base]))
    for src, rw in raws.items():
        bars, sides = rw.i.values, rw.side.values
        for N in (5, 10, 20):
            keep = np.array([prev_within(bars, sides, j, kk, N) for j, kk in zip(far.i.values, far.side.values)], dtype=bool)
            report(f'+ 太遠但前 {N} 根內有 ({src},0,8,1)', run(pd.concat([near, far[keep]])))
    print('\n   太遠的訊號單獨算（每筆 3R、1R 勝率；v3 那年 / 前 4 年）：')
    bars, sides = raws['20'].i.values, raws['20'].side.values
    for N in (5, 10, 20):
        w = np.array([prev_within(bars, sides, j, kk, N) for j, kk in zip(far.i.values, far.side.values)], dtype=bool)
        for lab, z in (('前面有 (20) 同向', far[w]), ('前面沒有', far[~w])):
            y = z[z.date > oc.YEARS[3][2]]; o = z[z.date <= oc.YEARS[3][2]]
            print(f'      N={N:<3} {lab}：v3 那年 {len(y)} 筆 {(y.r3 - 1 / y.risk).mean():+.2f}R、1R 勝 {100 * (y.r1 > 0).mean():.0f}%；前 4 年 {len(o)} 筆 {(o.r3 - 1 / o.risk).mean():+.2f}R、1R 勝 {100 * (o.r1 > 0).mean():.0f}%')


if __name__ == '__main__':
    main()
