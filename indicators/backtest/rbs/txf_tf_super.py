"""Remi TXF on longer bars: does a 3m / 5m chart (or a 5m filter on the 2m signals) avoid the losing streaks?

  cd indicators/backtest
  python3 -I rbs/txf_tf_super.py <TXFR1 .sql dumps ...> --tv "TAIFEX_TXF1!, 1_xxxxx.csv"

Part 1: the same rules on 2m / 3m / 5m charts: super-trend sells (Trend Judge below -90, stage S, event windows,
trend under 400 minutes) + v3 TXF trend signals (60-120 minutes); 3R, 60 bars, one at a time, 2 points cost.
Part 2: 2m signals (stage 3) kept only when the last completed 5-minute bar agrees: 5m close below its EMA8 / EMA20
(sells; buys above), or the 5m EMA8 falling (rising); and the EMA20 filter together with a cooldown after a stop.
Per year: 3R win rate / net R / trades; max losing streak; max drawdown.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import setup_study as ss
import market_matrix as mm
import txf_streaks as ts


def sessions(df, tf):
    tw = pd.DatetimeIndex(df.datetime); tw = (tw.tz_localize('UTC') if tw.tz is None else tw).tz_convert('Asia/Taipei') + pd.Timedelta(minutes=tf)
    mins = tw.hour * 60 + tw.minute; d = tw.floor('D')
    return np.asarray(np.where((mins > 525) & (mins <= 825), d.strftime('%Y-%m-%d') + ' 日', np.where(mins > 900, d.strftime('%Y-%m-%d') + ' 夜',
                      (d - pd.Timedelta(days=1)).strftime('%Y-%m-%d') + ' 夜'))), tw


def main():
    one = ts.load(sys.argv[1:])
    tdm = mm.minute_trend(one); H = mm.hourly(one, False)
    D = {tf: mm.chart(one, tdm, tf, 30.0, 60.0) for tf in (2, 3, 5)}
    yrs = None

    def line(lab, t):
        best, dd, _ = ts.summary(t)
        cells = [t[t.date.str[:4] == y] for y in yrs] + [t]
        print(f'   {lab:<30}' + ''.join(f'{100 * (z.r3 > 0).mean() if len(z) else 0:6.0f}% {z.n.sum():+5.1f}R {len(z):3d}' for z in cells) + f'{best:7d}{dd:9.1f}R', flush=True)

    def signals(tf, st, trend=True, sup=True):
        df = D[tf]
        s = mm.trend_signals(df, H, tf, 20, 8); base = s[mm.filt(s, 30.0, 3.0) & (s.tm >= 60) & (s.tm < 120)].assign(kind='趨勢')
        x = mm.trend_signals(df, H, tf, st, 8); x = x[(x.side == -1) & ~ss.EVT(x) & (x.tm < 400) & (x.spread > 90) & ~x.i.isin(base.i)].assign(kind='超強')
        T = pd.concat(([base] if trend else []) + ([x] if sup else [])).sort_values('i'); T['tj_off'] = 0.0
        return T

    for tf in (2, 3, 5):
        sess, tw = sessions(D[tf], tf)
        if yrs is None:
            yrs = sorted(D[2].date.unique().astype(str)) if False else sorted(set(pd.Series(tw.strftime('%Y'))))
            print(f'每格：3R 勝率 / 淨 R / 筆數；到 {tw[-1]:%Y-%m-%d}')
            print(f'   {"":<30}' + ''.join(f'{y:>18}' for y in yrs) + f'{"合計":>18}{"最長連停":>8}{"最大回撤":>8}')
        print(f'\n######## {tf} 分 K')
        line('只做趨勢訊號', ts.run(signals(tf, 3, sup=False), D[tf], sess))
        for st in (3, 5, 10):
            line(f'只做超強賣（階段 {st}）', ts.run(signals(tf, st, trend=False), D[tf], sess))
            line(f'趨勢 + 超強賣（階段 {st}）', ts.run(signals(tf, st), D[tf], sess))

    # Part 2: 2m signals with a 5m filter
    print('\n######## 2 分 K 訊號（階段 3）＋ 5 分 K 過濾')
    d5 = D[5]; c5 = d5.close.values
    end5 = (pd.DatetimeIndex(d5.datetime) + pd.Timedelta(minutes=5)).values.astype('datetime64[ns]').astype(np.int64)
    e8 = pd.Series(c5).ewm(span=8, adjust=False).mean().values; e20 = pd.Series(c5).ewm(span=20, adjust=False).mean().values
    df2 = D[2]; sess, tw = sessions(df2, 2)
    end2 = (pd.DatetimeIndex(df2.datetime) + pd.Timedelta(minutes=2)).values.astype('datetime64[ns]').astype(np.int64)
    T = signals(2, 3)
    k = np.searchsorted(end5, end2[T.i.values], 'right') - 1              # last 5m bar finished by the 2m signal's close
    side = T.side.values
    f = {'5m 收盤在 EMA8 同側': (c5[k] - e8[k]) * side > 0, '5m 收盤在 EMA20 同側': (c5[k] - e20[k]) * side > 0,
         '5m EMA8 同方向': (e8[k] - e8[np.maximum(k - 1, 0)]) * side > 0}
    line('不過濾（現在）', ts.run(T, df2, sess))
    for nm, m in f.items():
        line(nm, ts.run(T[m], df2, sess))
        line(nm + '（只過濾超強賣）', ts.run(T[m | (T.kind.values == '趨勢')], df2, sess))
    m = f['5m 收盤在 EMA20 同側'] | (T.kind.values == '趨勢')
    for k in (3, 5, 8):
        line(f'EMA20（只過濾超強賣）+ 冷卻 {k} 根', ts.run(T[m], df2, sess, 'cool', k))


if __name__ == '__main__':
    main()
