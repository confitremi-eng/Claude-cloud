"""Remi TXF: which trend-time limits work best, with everything else as the indicator now (trend signals 3R; super
sells TJ below -100, stage 4, 5m EMA30, 2R; 5-bar cooldown; one at a time; 2 points cost)?
  1. trend signals: the 60-120 minute window -> other lower / upper limits
  2. super sells: the 400-minute cap -> 150 .. no cap

  cd indicators/backtest
  python3 -I rbs/txf_trend_cap.py <TXFR1 .sql dumps ...> --tv "TAIFEX_TXF1!, 1_xxxxx.csv"

Per year: win rate / net R; then total, max losing streak, max drawdown.
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
    s = mm.trend_signals(d2, H, 2, 20, 8); s = s[mm.filt(s, 30.0, 3.0)].assign(kind='趨勢')
    x = mm.trend_signals(d2, H, 2, 4, 8); x = x[(x.side == -1) & ~ss.EVT(x) & (x.spread > 100)].assign(kind='超強')
    c5 = d5.close.values; e30 = pd.Series(c5).ewm(span=30, adjust=False).mean().values
    end5 = (pd.DatetimeIndex(d5.datetime) + pd.Timedelta(minutes=5)).values.astype('datetime64[ns]').astype(np.int64)
    end2 = (pd.DatetimeIndex(d2.datetime) + pd.Timedelta(minutes=2)).values.astype('datetime64[ns]').astype(np.int64)
    k = np.searchsorted(end5, end2[x.i.values], 'right') - 1
    x = x[c5[k] < e30[k]].copy(); x['x3'] = x['x2']; x['r3'] = x['r2']
    sess, tw = tt.sessions(d2, 2)
    yrs = sorted(set(pd.Series(tw.strftime('%Y'))))
    print(f'Remi TXF，到 {tw[-1]:%Y-%m-%d}。每格：勝率 / 淨 R')
    print(f'   {"":<26}' + ''.join(f'{y:>14}' for y in yrs) + f'{"合計":>18}{"連停":>5}{"回撤":>7}')

    def row(lab, lo, hi, cap, trend=True, sup=True):
        b = s[(s.tm >= lo) & (s.tm < hi)]; xs = x[(x.tm < cap) & ~x.i.isin(b.i)]
        T = pd.concat(([b] if trend else []) + ([xs] if sup else [])).sort_values('i'); T['tj_off'] = 0.0
        t = ts.run(T, d2, sess, 'cool', 5); best, dd, _ = ts.summary(t)
        cells = [t[t.date.str[:4] == y] for y in yrs]
        print(f'   {lab:<26}' + ''.join(f'{100 * (z.r3 > 0).mean():5.0f}% {z.n.sum():+6.1f}R' for z in cells)
              + f'{100 * (t.r3 > 0).mean():6.0f}% {t.n.sum():+6.1f}R {len(t):3d}{best:5d}{dd:6.1f}R', flush=True)

    INF = 10 ** 6
    print('-- 只做趨勢訊號：趨勢時間範圍（分鐘）')
    for lo, hi in ((60, 120), (60, 150), (60, 180), (60, 240), (60, 300), (60, 400), (60, INF), (30, 120), (0, 120), (0, 180), (90, 180), (120, 240)):
        row(f'{lo}–{hi if hi < INF else "∞"}', lo, hi, 400, sup=False)
    print('-- 只做超強賣：趨勢時間上限')
    for cap in (150, 200, 300, 400, 500, 600, INF):
        row(f'< {cap if cap < INF else "∞"}', 60, 120, cap, trend=False)
    print('-- 兩種一起')
    for lo, hi, cap in ((60, 120, 400), (60, 180, 400), (60, 240, 400), (60, 120, 600), (60, 180, 600), (60, 120, INF)):
        row(f'趨勢 {lo}–{hi}，超強 < {cap if cap < INF else "∞"}', lo, hi, cap)


if __name__ == '__main__':
    main()
