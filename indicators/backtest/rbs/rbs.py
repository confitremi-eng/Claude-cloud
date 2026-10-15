"""Remi's Buy/Sell research: Trend Judge (5s/15s EMA1130 spread) + BO signal rule on NQ / ES."""
import os
import sys
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(HERE), 'data')
# clean files from build_data.py (2026-02-02 .. 2026-09-01, synthetic days removed)
DATA = {'NQ': os.environ.get('NQ_DATA', os.path.join(DATA_DIR, 'NQ_1m_clean.csv')),
        'ES': os.environ.get('ES_DATA', os.path.join(DATA_DIR, 'ES_1m_clean.csv'))}
TICK = {'NQ': 0.25, 'ES': 0.25}
COST = {'NQ': 1.0, 'ES': 0.5}            # round-trip points: ~2 ticks slippage + commission
TH = {'NQ': (20.0, 40.0), 'ES': (4.0, 8.0)}
SPLIT = pd.Timestamp('2026-07-01', tz='UTC')
SEG_GAP = pd.Timedelta(days=4)          # longer holes than a long weekend restart the trend EMAs
WARM_DAYS = 2                           # New York dates at the start of each stretch used only to warm up

# EMA 1130 on 5-second / 15-second bars expressed as a per-minute smoothing factor
A_FAST = 1 - (1 - 2 / 1131) ** 12
A_SLOW = 1 - (1 - 2 / 1131) ** 4


def load1(sym):
    df = pd.read_csv(DATA[sym], parse_dates=['datetime']).set_index('datetime').sort_index()
    return df


def trading_minutes(start, end):
    idx = pd.date_range(start, end, freq='1min')
    et = idx.tz_convert('America/New_York')
    wd = et.weekday
    m = et.hour * 60 + et.minute
    closed = (wd == 5) | ((wd == 4) & (m >= 17 * 60)) | ((wd == 6) & (m < 18 * 60)) | ((m >= 17 * 60) & (m < 18 * 60))
    return idx[~closed]


def segments(idx):
    """Id of each stretch of data without a hole longer than SEG_GAP."""
    return (pd.Series(idx).diff() > SEG_GAP).cumsum().values


def trend_diff_minutes(df1):
    """5s-EMA1130 minus 15s-EMA1130, per minute. Missing CME trading minutes (overnight on the
    session-only days) are filled by a straight line from the previous close to the next open.
    The EMAs restart after a hole longer than SEG_GAP."""
    seg = segments(df1.index)
    parts = []
    for s in np.unique(seg):
        g = df1[seg == s]
        grid = trading_minutes(g.index[0], g.index[-1]).union(g.index)
        c = g.close.reindex(grid).interpolate(method='linear', limit_area='inside')
        ef = c.ewm(alpha=A_FAST, adjust=False).mean()
        es = c.ewm(alpha=A_SLOW, adjust=False).mean()
        parts.append(pd.DataFrame({'diff': ef - es, 'emaF': ef, 'emaS': es}))
    return pd.concat(parts)


def bars(df1, tf):
    """Chart bars of `tf` minutes inside contiguous blocks of real data; keeps the time of the last
    1-minute bar so the trend value can be sampled at the bar's close."""
    df1 = df1.copy()
    df1['last_min'] = df1.index
    block = (df1.index.to_series().diff() != pd.Timedelta('1min')).cumsum()
    parts = []
    for _, g in df1.groupby(block):
        if tf == 1:
            r = g.copy()
        else:
            r = g.resample(f'{tf}min', origin=g.index[0]).agg(
                {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum', 'last_min': 'last'}).dropna()
        parts.append(r)
    df = pd.concat(parts)
    df.index.name = 'datetime'
    df = df.reset_index()
    gap = df.datetime.diff() > pd.Timedelta(minutes=tf)
    df['block'] = gap.cumsum()
    df['bar_in_block'] = df.groupby('block').cumcount()
    return df


def trend_judge(df, tdm, tf, sym):
    """dirCode per chart bar exactly like Trend Judge: diff locked at each new 2-minute window
    (every bar on >= 2-minute charts, every even-minute bar on 1-minute charts)."""
    d = tdm['diff'].reindex(pd.DatetimeIndex(df.last_min)).values
    if tf == 1:
        newwin = (df.datetime.dt.minute % 2 == 0).values
        locked = np.full(len(d), np.nan)
        cur = np.nan
        for i in range(len(d)):
            if newwin[i]:
                cur = d[i]
            locked[i] = cur
    else:
        locked = d
    th, st = TH[sym]
    code = np.where(locked > st, 2, np.where(locked > th, 1, np.where(locked < -st, -2, np.where(locked < -th, -1, 0))))
    code = np.where(np.isnan(locked), 0, code)
    df = df.copy()
    df['tj_diff'] = locked
    df['tj_dir'] = code
    df['emaF'] = tdm['emaF'].reindex(pd.DatetimeIndex(df.last_min)).values
    df['emaS'] = tdm['emaS'].reindex(pd.DatetimeIndex(df.last_min)).values
    return df


def ema(x, n):
    return pd.Series(x).ewm(span=n, adjust=False).mean().values


def atr(h, l, c, n=14):
    pc = np.r_[c[0], c[:-1]]
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    return pd.Series(tr).ewm(alpha=1 / n, adjust=False).mean().values


def bo_signals(df, N=20, E=8, src='hl2', ema_on=True):
    """BO Signals rule: strict new N-bar low arms a buy; first close above that bar's high triggers;
    EMA filter on the trigger bar; one shot. Returns (i, dir, swing_extreme)."""
    h, l, c = df.high.values, df.low.values, df.close.values
    s = (h + l) / 2 if src == 'hl2' else c
    e = ema(s, E)
    lp = pd.Series(l).rolling(N).min().shift().values
    hp = pd.Series(h).rolling(N).max().shift().values
    out = []
    armB = armS = False
    refB = refS = swB = swS = np.nan
    for i in range(len(c)):
        nl = (not np.isnan(lp[i])) and l[i] < lp[i]
        nh = (not np.isnan(hp[i])) and h[i] > hp[i]
        tB = (not nl) and armB and c[i] > refB
        tS = (not nh) and armS and c[i] < refS
        if tB and ((not ema_on) or c[i] > e[i]):
            out.append((i, 1, swB))
        if tS and ((not ema_on) or c[i] < e[i]):
            out.append((i, -1, swS))
        if nl:
            armB, refB, swB = True, h[i], l[i]
        elif tB:
            armB = False
        if nh:
            armS, refS, swS = True, l[i], h[i]
        elif tS:
            armS = False
    return out


def simulate(df, sigs, sym, R=1.5, hold=60, warm=30, exit_mode='R', trend_exit=False):
    """Independent trades. Entry = signal close; stop = swing extreme -/+ 1 tick; target = R x risk.
    exit_mode 'R': stop/target/time. trend_exit: also exit at close when Trend Judge leaves the trade's
    direction (dir code becomes 0 or opposite). Trades end at the end of their session block."""
    h, l, c = df.high.values, df.low.values, df.close.values
    td = df.tj_dir.values
    n = len(df)
    tradable = df.tradable.values if 'tradable' in df else np.ones(n, bool)
    blk = df.block.values
    bib = df.bar_in_block.values
    blk_end = pd.Series(np.arange(n)).groupby(blk).transform('max').values
    tick, cost = TICK[sym], COST[sym]
    rows = []
    for i, d, sw in sigs:
        if bib[i] < warm or not tradable[i]:
            continue
        entry = c[i]
        stop = sw - d * tick
        risk = (entry - stop) * d
        if not risk > 0:
            continue
        tgt = entry + d * R * risk
        end = min(blk_end[i], i + hold)
        out = None
        for k in range(i + 1, end + 1):
            if (l[k] <= stop) if d == 1 else (h[k] >= stop):
                out = stop
                break
            if exit_mode == 'R' and ((h[k] >= tgt) if d == 1 else (l[k] <= tgt)):
                out = tgt
                break
            if trend_exit and td[k] * d <= 0:
                out = c[k]
                break
        if out is None:
            out = c[end]
        pts = (out - entry) * d - cost
        rows.append((i, d, pts / risk, pts, risk, df.datetime.iloc[i]))
    return pd.DataFrame(rows, columns=['i', 'dir', 'R', 'pts', 'risk', 'time'])


def stats(t):
    if len(t) == 0:
        return dict(n=0, win=np.nan, expR=np.nan, pf=np.nan, pts=np.nan)
    w = t.R[t.R > 0].sum()
    L = -t.R[t.R < 0].sum()
    return dict(n=len(t), win=100 * (t.R > 0).mean(), expR=t.R.mean(), pf=(w / L) if L > 0 else np.inf,
                pts=t.pts.mean())


_cache = {}


def prepared(sym, tf):
    key = (sym, tf)
    if key not in _cache:
        df1 = load1(sym)
        if ('tdm', sym) not in _cache:
            _cache[('tdm', sym)] = trend_diff_minutes(df1)
        df = trend_judge(bars(df1, tf), _cache[('tdm', sym)], tf, sym)
        df['seg'] = segments(pd.DatetimeIndex(df.datetime))
        day = df.datetime.dt.tz_convert('America/New_York').dt.date
        warm = {d for _, g in day.groupby(df.seg) for d in sorted(g.unique())[:WARM_DAYS]}
        df['tradable'] = ~day.isin(warm).values
        _cache[key] = df
    return _cache[key]
