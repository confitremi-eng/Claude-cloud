"""Where the signal bar sits against moving averages, NQ 2 minutes (the Databento year).

  cd indicators/backtest
  NQ_DATA=data/NQ_1m_databento.csv python3 rbs/ma_position.py [門檻]

Base: the filtered alerts (有趨勢 with the given Trend Judge threshold, default 10; 1-hour trend; stop >= 1 ATR;
data / open / close / Globex windows avoided), 2R, 1 point cost.
Features, all in the trade's direction (positive = price on the trade's side of the average), in ATR(14):
  ema8      close - EMA8 (the signal's own EMA)
  ema20     close - EMA20 on the 2-minute chart
  ema50     close - EMA50 on the 2-minute chart
  tjFast    close - EMA1130 on 5-second bars (Trend Judge fast line, estimated from 1-minute closes)
  tjSlow    close - EMA1130 on 15-second bars (Trend Judge slow line)
  d5        close - SMA5 of the last 5 completed daily (18:00 ET session) closes, in ATR
  d5pct     the same in percent of price
Prints
  1. every feature in quintiles (signals taken independently): count, win rate, net R, both halves
  2. simple filters picked from section 1, one position at a time, both halves
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import rbs
import setup_study as ss
import th_sweep as tw


def features(s, df):
    c = df.close.values; i = s.i.values; k = s.side.values
    tr = np.maximum(df.high - df.low, np.maximum((df.high - df.close.shift()).abs(), (df.low - df.close.shift()).abs()))
    atr = tr.ewm(alpha=1 / 14, adjust=False).mean().values
    f = pd.DataFrame(index=s.index)
    for n in (8, 20, 50):
        e = df.close.ewm(span=n, adjust=False).mean().values
        f[f'ema{n}'] = (c[i] - e[i]) * k / atr[i]
    f['tjFast'] = (c[i] - df.emaF.values[i]) * k / atr[i]
    f['tjSlow'] = (c[i] - df.emaS.values[i]) * k / atr[i]
    one = rbs.load1('NQ')
    sess = (one.index.tz_convert(ss.NY) + pd.Timedelta(hours=6)).date
    dclose = one.close.groupby(sess).last()
    sma5 = dclose.rolling(5).mean().shift(1)                     # last 5 completed sessions
    bar_sess = (df.datetime.dt.tz_convert(ss.NY) + pd.Timedelta(hours=6)).dt.date.values[i]
    d5 = pd.Series(bar_sess).map(sma5).values
    f['d5'] = (c[i] - d5) * k / atr[i]
    f['d5pct'] = (c[i] - d5) * k / d5 * 100
    return f


def stat(t, R=2.0):
    r = t[f'r{R:g}'].values; net = r - ss.COST / t.risk.values; a = t.date.values < ss.SPLIT
    m = lambda v: v.mean() if len(v) else np.nan
    return len(t), m(r > 0), m(net), m(net[a]), m(net[~a]), net.sum()


def main():
    th = float(sys.argv[1]) if len(sys.argv) > 1 else 10.0
    s = tw.build()
    df = rbs.prepared('NQ', tw.TF)
    s = pd.concat([s, features(s, df)], axis=1)
    b = s[(s.side == s.h1) & (s.risk_atr >= 1.0) & ~ss.EVT(s) & (s.spread > th)].sort_values('i')
    n, w, net, A, B, tot = stat(ss.seq(b, 2.0))
    print(f'基準（門檻 {th:g}，一次一筆，2R）：{n} 筆  勝率 {100 * w:.1f}%  每筆 {net:+.3f}R（前 {A:+.3f} 後 {B:+.3f}）  一年 {tot:+.1f}R')

    print('\n######## 1. 五等分（訊號各自獨立，2R）')
    feats = ['ema8', 'ema20', 'ema50', 'tjFast', 'tjSlow', 'd5', 'd5pct']
    for f in feats:
        x = b.dropna(subset=[f])
        q = pd.qcut(x[f], 5)
        print(f'  {f}')
        for iv, g in x.groupby(q, observed=True):
            n, w, net, A, B, tot = stat(g)
            print(f'    {str(iv):<22} {n:4d} 筆  勝率 {100 * w:4.1f}%  每筆 {net:+.3f}R（前 {A:+.3f} 後 {B:+.3f}）')
        for sgn, nm in ((x[f] > 0, '均線同側（順勢方）'), (x[f] <= 0, '均線另一側')):
            n, w, net, A, B, tot = stat(x[sgn])
            print(f'    {nm:<20} {n:4d} 筆  勝率 {100 * w:4.1f}%  每筆 {net:+.3f}R（前 {A:+.3f} 後 {B:+.3f}）')

    print('\n######## 2. 加一個條件（一次一筆，2R）')
    tests = {
        '基準': b.side != 0,
        'ema8 < 1.5 ATR（離 EMA8 不太遠）': b.ema8 < 1.5,
        'ema8 < 1 ATR': b.ema8 < 1.0,
        'ema20 > 0': b.ema20 > 0,
        'ema20 < 2 ATR': b.ema20 < 2,
        'ema50 > 0': b.ema50 > 0,
        'ema50 < 3 ATR': b.ema50 < 3,
        'tjSlow > 0（在 15 秒 EMA1130 順勢方）': b.tjSlow > 0,
        'tjSlow < 3 ATR': b.tjSlow < 3,
        'tjSlow < 5 ATR': b.tjSlow < 5,
        'd5 > 0（在日線 SMA5 順勢方）': b.d5 > 0,
        'd5 <= 0（日線 SMA5 另一側）': b.d5 <= 0,
    }
    for nm, m in tests.items():
        n, w, net, A, B, tot = stat(ss.seq(b[m], 2.0))
        print(f'  {nm:<34} {n:5d} 筆  勝率 {100 * w:4.1f}%  每筆 {net:+.3f}R（前 {A:+.3f} 後 {B:+.3f}）  一年 {tot:+6.1f}R')


if __name__ == '__main__':
    main()
