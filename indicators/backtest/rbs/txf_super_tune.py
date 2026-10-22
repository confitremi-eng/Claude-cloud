"""Remi TXF fine-tuning of the super-trend sells' periods, everything else as the indicator now (trend signals 3R,
super sells 2R, 5-bar cooldown, one at a time, 2 points cost):
  stage (2-6), the signal EMA (5 / 8 / 13), the 5m filter EMA (10 / 20 / 30 / off), and the TJ level (80 / 90 / 100).

  cd indicators/backtest
  python3 -I rbs/txf_super_tune.py <TXFR1 .sql dumps ...> --tv "TAIFEX_TXF1!, 1_xxxxx.csv"

Per year: win rate / net R; then total, max losing streak, max drawdown, and the 10/22 trades.
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
    c5 = d5.close.values
    end5 = (pd.DatetimeIndex(d5.datetime) + pd.Timedelta(minutes=5)).values.astype('datetime64[ns]').astype(np.int64)
    end2 = (pd.DatetimeIndex(d2.datetime) + pd.Timedelta(minutes=2)).values.astype('datetime64[ns]').astype(np.int64)
    sess, tw = tt.sessions(d2, 2)
    yrs = sorted(set(pd.Series(tw.strftime('%Y'))))
    cache = {}
    print(f'Remi TXF（趨勢 3R + 超強賣 2R、冷卻 5 根），到 {tw[-1]:%Y-%m-%d}。每格：勝率 / 淨 R')
    print(f'   {"階段 EMA 5mEMA TJ":<20}' + ''.join(f'{y:>14}' for y in yrs) + f'{"合計":>18}{"連停":>5}{"回撤":>7}   10/22')

    def row(st, em, f5, lv):
        if (st, em) not in cache: cache[(st, em)] = mm.trend_signals(d2, H, 2, st, em)
        x = cache[(st, em)]; x = x[(x.side == -1) & ~ss.EVT(x) & (x.tm < 400) & (x.spread > lv) & ~x.i.isin(base.i)].assign(kind='超強')
        if f5:
            e = pd.Series(c5).ewm(span=f5, adjust=False).mean().values
            k = np.searchsorted(end5, end2[x.i.values], 'right') - 1
            x = x[c5[k] < e[k]]
        x = x.copy(); x['x3'] = x['x2']; x['r3'] = x['r2']
        T = pd.concat([base, x]).sort_values('i'); T['tj_off'] = 0.0
        t = ts.run(T, d2, sess, 'cool', 5); best, dd, _ = ts.summary(t)
        today = ' '.join(f'{tw[r.i]:%H:%M}{r.r3:+.0f}' for r in t.itertuples() if f'{tw[r.i]:%Y-%m-%d}' == '2026-10-22' and r.kind == '超強')
        cells = [t[t.date.str[:4] == y] for y in yrs]
        lab = f'{st:>3} {em:>3} {f5 if f5 else "關":>4} {lv:>4}'
        print(f'   {lab:<20}' + ''.join(f'{100 * (z.r3 > 0).mean():5.0f}% {z.n.sum():+6.1f}R' for z in cells)
              + f'{100 * (t.r3 > 0).mean():6.0f}% {t.n.sum():+6.1f}R {len(t):3d}{best:5d}{dd:6.1f}R   {today}', flush=True)

    print('-- 階段'); [row(st, 8, 20, 90) for st in (2, 3, 4, 5, 6)]
    print('-- 訊號 EMA'); [row(3, em, 20, 90) for em in (5, 13)]
    print('-- 5 分 K 過濾 EMA'); [row(3, 8, f5, 90) for f5 in (10, 30, 0)]
    print('-- TJ 門檻'); [row(3, 8, 20, lv) for lv in (80, 100)]
    print('-- 組合'); [row(st, 8, f5, lv) for lv in (100, 110) for f5 in (20, 30, 0) for st in (3, 4)]


if __name__ == '__main__':
    main()
