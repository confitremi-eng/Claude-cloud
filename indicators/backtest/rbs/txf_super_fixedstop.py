"""Remi TXF super-trend sells: two-bar stop (now) vs a fixed stop in points (e.g. 150), compared in TXF points.

  cd indicators/backtest
  python3 -I rbs/txf_super_fixedstop.py <TXFR1 .sql dumps ...> --tv "TAIFEX_TXF1!, 1_xxxxx.csv"

Super sells as the indicator now: Trend Judge below -90, stage 3, event windows, trend under 400 minutes, the last
finished 5m close below its EMA20. Each run trades the super sells alone, one at a time, 5-bar cooldown after a stop,
60-bar limit, flat before a break of more than 30 minutes, 2 points cost. Stops: two-bar high (as now) or entry + P
points; targets 1R / 2R / 3R of that stop, or fixed points. Per year: win rate / net points (1 contract); then max
drawdown in points and median stop.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import setup_study as ss
import market_matrix as mm
import txf_streaks as ts

COST = 2.0


def main():
    one = ts.load(sys.argv[1:]); tdm = mm.minute_trend(one); H = mm.hourly(one, False)
    d2 = mm.chart(one, tdm, 2, 30.0, 60.0); d5 = mm.chart(one, tdm, 5, 30.0, 60.0)
    x = mm.trend_signals(d2, H, 2, 3, 8); x = x[(x.side == -1) & ~ss.EVT(x) & (x.tm < 400) & (x.spread > 90)]
    c5 = d5.close.values; e20 = pd.Series(c5).ewm(span=20, adjust=False).mean().values
    end5 = (pd.DatetimeIndex(d5.datetime) + pd.Timedelta(minutes=5)).values.astype('datetime64[ns]').astype(np.int64)
    end2 = (pd.DatetimeIndex(d2.datetime) + pd.Timedelta(minutes=2)).values.astype('datetime64[ns]').astype(np.int64)
    k = np.searchsorted(end5, end2[x.i.values], 'right') - 1
    x = x[c5[k] < e20[k]].sort_values('i')
    h, l, c = d2.high.values, d2.low.values, d2.close.values
    dt = pd.DatetimeIndex(d2.datetime); hole = np.r_[(dt[1:] - dt[:-1]) > pd.Timedelta(minutes=30), True]
    yrs = sorted(x.date.str[:4].unique())

    def sim(stop_kind, P, tgt):
        out = []; busy = -1; cool = -10 ** 9
        for i, d in zip(x.i.values, x.date.values):
            if i < busy or i - cool < 5: continue
            e = c[i]; st = max(h[i - 1], h[i]) if stop_kind == 'bar' else e + P
            risk = st - e
            if risk <= 0: continue
            tp = e - (tgt * risk if isinstance(tgt, float) else tgt)
            j = i; res = None
            while True:
                j += 1
                if j >= len(c): res = e - c[-1]; break
                if h[j] >= st: res = -risk; break
                if l[j] <= tp: res = e - tp; break
                if j - i >= 60 or hole[j]: res = e - c[j]; break
            busy = j
            if res <= -risk + 1e-9: cool = j
            out.append((d, res - COST, risk))
        return pd.DataFrame(out, columns=['date', 'pts', 'risk'])

    print(f'超強趨勢賣單（TJ 90 / 階段 3 / 5m EMA20 / 冷卻 5 根），單獨做。每格：勝率 / 淨點數（1 口） / 筆數')
    print(f'   {"":<26}' + ''.join(f'{y:>20}' for y in yrs) + f'{"合計":>20}{"最大回撤":>9}{"停損中位":>8}')
    rows = [('兩根高點停損', 'bar', None, R) for R in (1.0, 2.0, 3.0)]
    rows += [(f'固定 {P} 點停損', 'fix', P, R) for P in (100, 150, 200) for R in (1.0, 2.0, 3.0)]
    rows += [('固定 150 停損、目標 150 點', 'fix', 150, 150), ('固定 150 停損、目標 300 點', 'fix', 150, 300)]
    for lab, sk, P, R in rows:
        t = sim(sk, P, R)
        eq = np.cumsum(t.pts.values); dd = float(np.max(np.maximum.accumulate(np.r_[0, eq])[1:] - eq))
        cells = [t[t.date.str[:4] == y] for y in yrs] + [t]
        tag = f'{R:g}R' if isinstance(R, float) else ''
        print(f'   {lab + " " + tag:<26}' + ''.join(f'{100 * (z.pts > 0).mean():6.0f}% {z.pts.sum():+7.0f}點 {len(z):3d}' for z in cells)
              + f'{dd:8.0f}點{t.risk.median():7.0f}點', flush=True)


if __name__ == '__main__':
    main()
