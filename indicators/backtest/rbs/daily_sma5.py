"""Trend signals not against the daily SMA5 (NQ 2m / 5m, five years).

  cd indicators/backtest
  python3 -I rbs/daily_sma5.py

Daily bar = CME trading day (18:00 .. 17:00 New York). SMA5 = mean of the last 5 completed daily closes (no look-ahead).
Rules: 'price' = buy only when the price is above the SMA5 (sell below); 'slope' = buy only when the SMA5 is rising
(today's SMA5 > yesterday's), sell when falling; 'both'. Applied to trend signals, or to trend + MIX.
v3 as now (2m trend 0-400, 5m 0-180, stop >= 0.95 ATR, FOMC days off, junk time off, one at a time).
Win rate = share of trades with R > 0; also the 1R hit rate (each trend signal on its own).
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import setup_study as ss
import market_matrix as mm
import oos_check as oc


def daily(one):
    ny = one.index.tz_convert(ss.NY) if one.index.tz is not None else one.index.tz_localize('UTC').tz_convert(ss.NY)
    day = (ny + pd.Timedelta(hours=6)).normalize()
    d = one.close.groupby(day).last()
    sma = d.rolling(5).mean()
    return pd.DataFrame({'sma': sma.shift(1), 'sma_prev': sma.shift(2)})     # known at the start of each trading day


def main():
    one = oc.load(); M = oc.Market(one); D = daily(one)
    for tf, R, cap in ((2, 3.0, 400), (5, 2.0, 180)):
        C = M.ctx(tf); df = C.df; th = df.thr.values; c = df.close.values
        dt = pd.DatetimeIndex(df.datetime); dt = dt.tz_localize('UTC') if dt.tz is None else dt
        ny = (dt + pd.Timedelta(minutes=tf)).tz_convert(ss.NY)
        m = np.asarray(ny.hour * 60 + ny.minute); junk = (m >= 720) & (m <= 785)
        day = (dt.tz_convert(ss.NY) + pd.Timedelta(hours=6)).normalize()
        sma = D.sma.reindex(day).values; slope = np.sign(D.sma.reindex(day).values - D.sma_prev.reindex(day).values)
        side_px = np.sign(c - sma)
        s = mm.trend_signals(df, M.H, tf, 20, 8)
        T = s[(s.side == s.h1) & (s.risk_atr >= 0.95) & ~ss.EVT(s) & (s.slow < 3) & (s.spread > th[s.i]) & (s.tm < cap) & ~s.date.isin(ss.FOMC) & ~junk[s.i]]
        mix = [x for x in oc.mix_list(C) if C.date[x[0]] not in ss.FOMC and not junk[x[0]]]
        ok = {'price': lambda i, k: side_px[i] == k, 'slope': lambda i, k: slope[i] == k, 'both': lambda i, k: side_px[i] == k and slope[i] == k}
        print(f'\nNQ {tf}m（{R:g}R）每年：勝率 / 合計 R')
        print(f'   {"":<28}' + ''.join(f'{nm[:2] + " " + nm[3:8]:>16}' for nm, a, b in oc.YEARS))
        def row(lab, TT, MM):
            t = oc.sim(C, TT, MM, R, R)
            print(f'   {lab:<28}' + ''.join(f'{100 * (z.R > 0).mean():6.0f}% {z.net.sum():+6.0f}R' for z in (t[(t.date >= a) & (t.date <= b)] for nm, a, b in oc.YEARS)))
        row('v3 現在', T, mix)
        for nm, f in ok.items():
            keep = np.array([f(i, k) for i, k in zip(T.i.values, T.side.values)])
            row(f'趨勢不逆日線（{nm}）', T[keep], mix)
            row(f'趨勢 + MIX 不逆日線（{nm}）', T[keep], [x for x in mix if f(x[0], x[1])])
        # each trend signal on its own: 1R hit, with / against
        for nm in ('price', 'slope'):
            f = ok[nm]; w = np.array([f(i, k) for i, k in zip(T.i.values, T.side.values)])
            for lab, mk in (('順日線', w), ('逆日線', ~w)):
                z = T[mk]
                cells = []
                for nm2, a, b in oc.YEARS:
                    y = z[(z.date >= a) & (z.date <= b)]
                    cells.append(f'{100 * (y.r1 > 0).mean():3.0f}% ({len(y)})' if len(y) else '-')
                print(f'   趨勢訊號單獨 1R 命中（{nm}，{lab}）' + ''.join(f'{x:>16}' for x in cells))


if __name__ == '__main__':
    main()
