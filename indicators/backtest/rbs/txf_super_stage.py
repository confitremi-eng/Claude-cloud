"""Remi TXF: super-sell stage vs number of trades and profit, everything else as the indicator now (TJ below -100,
5m EMA30, trend under 600 minutes, 2R, 5-bar cooldown; trend signals 60-120 minutes, 3R; one at a time; 2 points cost).

  cd indicators/backtest
  python3 -I rbs/txf_super_stage.py <TXFR1 .sql dumps ...> --tv "TAIFEX_TXF1!, 1_xxxxx.csv"

Per stage: super sells per year (trades actually taken), their win rate and R per trade, R per year by calendar year,
and the whole indicator's total, max losing streak and drawdown.
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
    c5 = d5.close.values; e30 = pd.Series(c5).ewm(span=30, adjust=False).mean().values
    end5 = (pd.DatetimeIndex(d5.datetime) + pd.Timedelta(minutes=5)).values.astype('datetime64[ns]').astype(np.int64)
    end2 = (pd.DatetimeIndex(d2.datetime) + pd.Timedelta(minutes=2)).values.astype('datetime64[ns]').astype(np.int64)
    sess, tw = tt.sessions(d2, 2)
    yrs = sorted(set(pd.Series(tw.strftime('%Y'))))
    span = (tw[-1] - tw[0]).days / 365.25
    print(f'Remi TXF，{tw[0]:%Y-%m-%d} .. {tw[-1]:%Y-%m-%d}（{span:.1f} 年）')
    print(f'   {"階段":<6}{"超強賣 筆/年":>12}{"勝率":>6}{"每筆":>8}' + ''.join(f'{y + " R":>10}' for y in yrs) + f'{"整個指標合計":>14}{"筆/年":>6}{"連停":>5}{"回撤":>7}')
    for st in (4, 5, 6, 8, 10, 12, 15, 20):
        x = mm.trend_signals(d2, H, 2, st, 8)
        x = x[(x.side == -1) & ~ss.EVT(x) & (x.tm < 600) & (x.spread > 100) & ~x.i.isin(base.i)].assign(kind='超強')
        k = np.searchsorted(end5, end2[x.i.values], 'right') - 1
        x = x[c5[k] < e30[k]].copy(); x['x3'] = x['x2']; x['r3'] = x['r2']
        T = pd.concat([base, x]).sort_values('i'); T['tj_off'] = 0.0
        t = ts.run(T, d2, sess, 'cool', 5); best, dd, _ = ts.summary(t)
        u = t[t.kind == '超強']
        print(f'   {st:<6}{len(u) / span:12.0f}{100 * (u.r3 > 0).mean():5.0f}%{u.n.mean():+7.2f}R' + ''.join(f'{u[u.date.str[:4] == y].n.sum():+9.1f}R' for y in yrs)
              + f'{t.n.sum():+13.1f}R{len(t) / span:6.0f}{best:5d}{dd:6.1f}R', flush=True)


if __name__ == '__main__':
    main()
