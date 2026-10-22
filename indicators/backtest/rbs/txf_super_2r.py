"""Remi TXF with per-kind targets: trend signals 3R, super-trend sells 1R / 2R / 3R, traded together as the indicator
(5m EMA20 filter on super sells, 5-bar cooldown after a stop, one at a time, 2 points cost).

  cd indicators/backtest
  python3 -I rbs/txf_super_2r.py <TXFR1 .sql dumps ...> --tv "TAIFEX_TXF1!, 1_xxxxx.csv"

Per year: win rate / net R / trades; max losing streak; max drawdown (R); net points per contract; the 10/22 trades.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import setup_study as ss
import market_matrix as mm
import txf_streaks as ts
import txf_tf_super as tt


def main():
    one = ts.load(sys.argv[1:]); tdm = mm.minute_trend(one); H = mm.hourly(one, False)
    d2 = mm.chart(one, tdm, 2, 30.0, 60.0); d5 = mm.chart(one, tdm, 5, 30.0, 60.0)
    s = mm.trend_signals(d2, H, 2, 20, 8); base = s[mm.filt(s, 30.0, 3.0) & (s.tm >= 60) & (s.tm < 120)].assign(kind='趨勢')
    x = mm.trend_signals(d2, H, 2, 3, 8); x = x[(x.side == -1) & ~ss.EVT(x) & (x.tm < 400) & (x.spread > 90) & ~x.i.isin(base.i)].assign(kind='超強')
    c5 = d5.close.values; e20 = pd.Series(c5).ewm(span=20, adjust=False).mean().values
    end5 = (pd.DatetimeIndex(d5.datetime) + pd.Timedelta(minutes=5)).values.astype('datetime64[ns]').astype(np.int64)
    end2 = (pd.DatetimeIndex(d2.datetime) + pd.Timedelta(minutes=2)).values.astype('datetime64[ns]').astype(np.int64)
    k = np.searchsorted(end5, end2[x.i.values], 'right') - 1
    x = x[c5[k] < e20[k]]
    sess, tw = tt.sessions(d2, 2)
    yrs = sorted(set(pd.Series(tw.strftime('%Y'))))
    print(f'Remi TXF（趨勢 3R + 超強賣 xR，EMA20、冷卻 5 根），到 {tw[-1]:%Y-%m-%d}。每格：勝率 / 淨 R / 筆數')
    print(f'   {"":<22}' + ''.join(f'{y:>18}' for y in yrs) + f'{"合計":>18}{"最長連停":>8}{"最大回撤":>8}{"淨點數":>9}   10/22')
    for R in (3.0, 2.0, 1.0):
        xs = x.copy(); xs['x3'] = xs[f'x{R:g}']; xs['r3'] = xs[f'r{R:g}']        # run() reads x3 / r3
        T = pd.concat([base, xs]).sort_values('i'); T['tj_off'] = 0.0
        t = ts.run(T, d2, sess, 'cool', 5); best, dd, _ = ts.summary(t)
        pts = (t.r3 * t.risk - 2.0).sum()
        today = ' '.join(f'{tw[r.i]:%H:%M}{r.r3:+.0f}R' for r in t.itertuples() if f'{tw[r.i]:%Y-%m-%d}' == '2026-10-22')
        cells = [t[t.date.str[:4] == y] for y in yrs] + [t]
        print(f'   {f"超強賣 {R:g}R":<22}' + ''.join(f'{100 * (z.r3 > 0).mean():6.0f}% {z.n.sum():+5.1f}R {len(z):3d}' for z in cells)
              + f'{best:7d}{dd:9.1f}R{pts:+9.0f}   {today}', flush=True)


if __name__ == '__main__':
    main()
