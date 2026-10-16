"""Remi's Buy/Sell vs the original 買賣訊號, using TradingView "Export chart data" CSVs.

  python3 remi_export.py match ORIGINAL.csv [LONG_1M.csv]
      Compare the original's Buy / Sell columns with this rule bar by bar. With LONG_1M.csv
      (a longer 1-minute export) the rule runs on it, resampled to the original's timeframe,
      so the swing state is fully warmed up.
  python3 remi_export.py bt DATA.csv
      Old vs current rule, 1 / 2 / 3 / 5 minute, user's stop (extreme of the signal candle and the
      one before it), entry at the signal close, fixed 1R / 2R target, stop first if both hit on the
      same bar, 60-bar time exit, no costs. DATA.csv: a TradingView export (time column) or a
      datetime,open,high,low,close file.
"""
import sys
import numpy as np, pandas as pd


def signals(df, stage=20, ema_len=8, src='close', old=False):
    """Port of remis_buy_sell.pine. old=True is the previous rule (no trigger on a new-low bar, EMA on hl2)."""
    h, l, c = df.high.values, df.low.values, df.close.values
    s = (h + l) / 2 if src == 'hl2' else c
    ema = pd.Series(s).ewm(span=ema_len, adjust=False).mean().values
    lo = pd.Series(l).rolling(stage).min().shift().values
    hi = pd.Series(h).rolling(stage).max().shift().values
    n = len(c); B = np.zeros(n, int); S = np.zeros(n, int)
    armB = armS = False; refH = refL = np.nan
    for i in range(stage, n):
        newLow, newHigh = l[i] < lo[i], h[i] > hi[i]
        trigB = armB and c[i] > refH and not (old and newLow)
        trigS = armS and c[i] < refL and not (old and newHigh)
        B[i] = trigB and c[i] > ema[i]
        S[i] = trigS and c[i] < ema[i]
        if old:
            if newLow: armB, refH = True, h[i]
            elif trigB: armB = False
            if newHigh: armS, refL = True, l[i]
            elif trigS: armS = False
        else:
            if trigB: armB = False
            elif newLow: armB, refH = True, h[i]
            if trigS: armS = False
            elif newHigh: armS, refL = True, l[i]
    return B, S


def load(path):
    df = pd.read_csv(path)
    if 'time' not in df.columns:
        t = pd.to_datetime(df.datetime, utc=True).dt.tz_localize(None)
        df['time'] = ((t - pd.Timestamp(0)) // pd.Timedelta('1s')).astype(int)
    return df.rename(columns={'BUY 訊號': 'Buy', 'SELL 訊號': 'Sell'})


def resample(df1, minutes):
    if minutes == 1:
        return df1[['time', 'open', 'high', 'low', 'close']].reset_index(drop=True)
    g = df1.groupby(pd.to_datetime(df1.time, unit='s').dt.floor(f'{minutes}min'))
    r = pd.DataFrame({'open': g.open.first(), 'high': g.high.max(), 'low': g.low.min(), 'close': g.close.last()})
    r['time'] = ((r.index - pd.Timestamp(0)) // pd.Timedelta('1s')).astype(int)
    return r.reset_index(drop=True)


def match(orig_path, long_path=None):
    o = load(orig_path)
    if long_path:
        minutes = int(np.median(np.diff(o.time)) // 60)
        d = resample(load(long_path), minutes)
        B, S = signals(d)
        x = o.merge(pd.DataFrame({'time': d.time, 'B': B, 'S': S}), on='time').iloc[:-1]   # last bar may be live
    else:
        B, S = signals(o)
        x = o.assign(B=B, S=S).iloc[20:]
    ob, ub = np.r_[x.Buy, x.Sell], np.r_[x.B, x.S]
    print(f'{orig_path}: bars {len(x)}  original {ob.sum()}  ours {ub.sum()}  same bar {((ob == 1) & (ub == 1)).sum()}'
          f'  every bar equal {(ob == ub).mean() * 100:.2f}%')


def trades(df, B, S, horizon=60):
    h, l, c = df.high.values, df.low.values, df.close.values; out = []
    for i in np.where((B == 1) | (S == 1))[0]:
        if i < 1 or i + 10 > len(c) - 1: continue
        k = 1 if B[i] else -1
        stop = min(l[i - 1], l[i]) if k == 1 else max(h[i - 1], h[i])
        risk = (c[i] - stop) * k
        if not risk > 0: continue
        end = min(len(c) - 1, i + horizon); res = []
        for R in (1.0, 2.0):
            tgt = c[i] + k * R * risk; r = None
            for j in range(i + 1, end + 1):
                if (l[j] <= stop) if k == 1 else (h[j] >= stop): r = -1.0; break
                if (h[j] >= tgt) if k == 1 else (l[j] <= tgt): r = R; break
            res.append((c[end] - c[i]) * k / risk if r is None else r)
        out.append((risk, *res))
    return pd.DataFrame(out, columns=['risk', 'r1', 'r2'])


def backtest(path):
    d1 = load(path)
    for m in (1, 2, 3, 5):
        d = resample(d1, m)
        for name, kw in (('old', dict(src='hl2', old=True)), ('new', dict())):
            t = trades(d, *signals(d, **kw))
            print(f'{m}m {name}: n {len(t):5d}  1R win {(t.r1 > 0).mean() * 100:4.1f}% avg {t.r1.mean():+.3f}R  '
                  f'2R win {(t.r2 > 0).mean() * 100:4.1f}% avg {t.r2.mean():+.3f}R  median stop {t.risk.median():.2f}')


if __name__ == '__main__':
    if sys.argv[1] == 'match':
        match(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
    else:
        backtest(sys.argv[2])
