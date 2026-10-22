"""TXF 2m super-strong-trend sells: grid of Trend Judge level x stage on all the data there is, and whether each cell
catches a given day.

  cd indicators/backtest
  python3 -I rbs/txf_super_grid.py <TXFR1 .sql dumps ...> [--tv "TAIFEX_TXF1!, 1_xxxxx.csv"] [--day 2026-10-22]

Data: the TXFR1 1-minute .sql dumps (2024-01 .. 2026-09) plus, with --tv, a TradingView TXF1! 1-minute export appended
after them (its first 5 days are only warm-up: the price level jumps between the two sources). Roll windows skipped in the
.sql part only (TXF1! is back-adjusted, no jump at the roll).
Rule as in txf_super_trend.py: stage S sells (close < EMA8) while Trend Judge is below -L, event windows avoided,
trend under 400 minutes, two-bar stop, 2 points cost, one at a time. Per year: 3R win rate / net R / trades, 1R total,
v3 TXF 2m + these sells at 3R, and the sells on --day (Taipei time of the signal bar's close).
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import setup_study as ss
import market_matrix as mm
import txf_check as tx

COST = 2.0


def main():
    args = sys.argv[1:]; tv = None; day = '2026-10-22'
    if '--tv' in args: k = args.index('--tv'); tv = args[k + 1]; del args[k:k + 2]
    if '--day' in args: k = args.index('--day'); day = args[k + 1]; del args[k:k + 2]
    one = tx.read_sql_1m(args)[['open', 'high', 'low', 'close']]
    one['bad'] = tx.roll_mask(one.index)
    if tv:
        r = pd.read_csv(tv, usecols=[0, 1, 2, 3, 4]); r.index = pd.DatetimeIndex(pd.to_datetime(r.time, unit='s', utc=True))
        r = r[r.index > one.index[-1]][['open', 'high', 'low', 'close']]
        r['bad'] = r.index < r.index[0] + pd.Timedelta(days=5)          # TXF1! is back-adjusted: no roll jump, only warm-up
        one = pd.concat([one, r])
    tdm = mm.minute_trend(one); H = mm.hourly(one, False)
    df = mm.chart(one, tdm, 2, 30.0, 60.0)
    s = mm.trend_signals(df, H, 2, 20, 8); base = s[mm.filt(s, 30.0, 3.0) & (s.tm >= 60) & (s.tm < 120)]
    tw = pd.DatetimeIndex(df.datetime); tw = (tw.tz_localize('UTC') if tw.tz is None else tw).tz_convert('Asia/Taipei') + pd.Timedelta(minutes=2)
    yrs = sorted(s.date.str[:4].unique())
    print(f'TXF 2m 到 {tw[-1]:%Y-%m-%d %H:%M} 台北，成本 {COST:g} 點；只做超強趨勢賣單（一次一筆）。每格：3R 勝率 / 淨 R / 筆數')
    print(f'   {"TJ  階段":<10}' + ''.join(f'{y:>18}' for y in yrs) + f'{"3R 合計":>18}{"1R 合計":>14}{"v3+賣 3R":>10}   {day} 的賣單')

    def run(T, R):
        q = ss.seq(T.sort_values('i'), R).copy(); q['n'] = q[f'r{R:g}'] - COST / q.risk
        return q

    b3 = run(base, 3.0)
    print(f'   {"v3 趨勢":<10}' + ''.join(f'{100 * (z.r3 > 0).mean() if len(z) else 0:6.0f}% {z.n.sum():+5.1f}R {len(z):3d}' for z in [b3[b3.date.str[:4] == y] for y in yrs] + [b3]))
    for st in (3, 4, 5, 6, 8, 10):
        x0 = mm.trend_signals(df, H, 2, st, 8)
        x0 = x0[(x0.side == -1) & ~ss.EVT(x0) & (x0.tm < 400)]
        for lv in (60, 90, 120, 150, 200):
            x = x0[x0.spread > lv]
            q3, q1 = run(x, 3.0), run(x, 1.0)
            c3 = run(pd.concat([base, x[~x.i.isin(base.i)]]), 3.0)
            today = [f'{tw[i]:%H:%M}({r:+.0f}R)' for i, r in zip(q3.i, q3.r3) if f'{tw[i]:%Y-%m-%d}' == day]
            print(f'   {lv:>3} {st:>4}  ' + ''.join(f'{100 * (z.r3 > 0).mean() if len(z) else 0:6.0f}% {z.n.sum():+5.1f}R {len(z):3d}' for z in [q3[q3.date.str[:4] == y] for y in yrs] + [q3])
                  + f'{100 * (q1.r1 > 0).mean():6.0f}% {q1.n.sum():+5.1f}R{c3.n.sum():+9.1f}R   {" ".join(today) if today else "—"}', flush=True)


if __name__ == '__main__':
    main()
