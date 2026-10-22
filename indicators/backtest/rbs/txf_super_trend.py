"""TXF 2m "super-strong trend" (the NQ 2m rule added to v3 on 2026-10-22): when Trend Judge is beyond L on the signal's
side, take a short stage's signals and skip 1h EMA20, slow line and stop size; keep the event windows and a 0-400 minute
trend limit. Sells, buys and both. TXFR1 1-minute dumps (2024-01 .. 2026-09), roll windows skipped, 2 points cost.

  cd indicators/backtest
  python3 -I rbs/txf_super_trend.py ../../ohlc資料/data_TXFR1_2024.sql ../../ohlc資料/data_TXFR1_2025.sql ../../ohlc資料/data_TXFR1_2026.sql

v3 on TXF 2m: (20, 0, 8, 1), Trend Judge 30, 1h EMA20, stop >= 1 ATR, slow line <= 3 ATR, trend 60-120 minutes, 3R
(market_matrix.V3). TXF's Trend Judge is in TXF points (normal 30, strong 60), so the levels tried are 60-240.
Rows: the extra signals alone (one at a time) and v3 + extras. Per calendar year: 1R and 3R win rate / net R / trades.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import setup_study as ss
import market_matrix as mm

COST = 2.0


def main():
    paths = sys.argv[1:]
    one = mm.load_market('txf', paths); tdm = mm.minute_trend(one); H = mm.hourly(one, False)
    df = mm.chart(one, tdm, 2, 30.0, 60.0)
    raw = {st: mm.trend_signals(df, H, 2, st, 8) for st in (5, 10, 12, 20)}
    s = raw[20]
    base = s[mm.filt(s, 30.0, 3.0) & (s.tm >= 60) & (s.tm < 120)]
    yrs = sorted(s.date.str[:4].unique())
    print(f'TXF 2m，{df.datetime.iloc[0]} .. {df.datetime.iloc[-1]}，每格：勝率 / 淨 R / 筆數（成本 {COST:g} 點）')
    print(f'   {"":<34}' + ''.join(f'{y:>18}' for y in yrs) + f'{"合計":>18}{"停損中位":>8}')

    def row(lab, T, R):
        q = ss.seq(T.sort_values('i'), R).copy(); q['n'] = q[f'r{R:g}'] - COST / q.risk
        cells = [q[q.date.str[:4] == y] for y in yrs] + [q]
        print(f'   {lab + f" {R:g}R":<34}' + ''.join(f'{100 * (z[f"r{R:g}"] > 0).mean() if len(z) else 0:6.0f}% {z.n.sum():+5.1f}R {len(z):3d}' for z in cells)
              + f'{q.risk.median():6.0f}點', flush=True)

    for R in (1.0, 3.0):
        print(f'\n目標 {R:g}R')
        row('v3 TXF 2m', base, R)
        for lv in (60, 90, 120, 150, 200):
            for st in (10, 20):
                x = raw[st]; x = x[(x.spread > lv) & ~ss.EVT(x) & (x.tm < 400) & ~x.i.isin(base.i)]
                for side, nm in ((-1, '賣'), (1, '買')):
                    z = x[x.side == side]
                    row(f'只做 TJ>{lv} ({st}) {nm}', z, R)
                xs = x[x.side == -1]
                row(f'  v3 + TJ>{lv} ({st}) 只加賣', pd.concat([base, xs]), R)


if __name__ == '__main__':
    main()
