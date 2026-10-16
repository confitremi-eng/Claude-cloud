"""Build a back-adjusted continuous NQ 1-minute file from a Databento GLBX.MDP3 OHLCV-1m download.

The download holds every NQ outright and calendar spread (product NQ, CSV, decimal prices, ISO 8601
timestamps, symbol field). The continuous series follows TradingView's NQ1! with back-adjustment, checked
bar for bar against TradingView exports (2026-09-06 .. 10-14): each session (18:00-17:00 New York) uses the
outright with the most volume in the previous session, so the roll happens at a session open; at a roll
every earlier price moves by (new contract close - old contract close) at the last minute of the old
session where both traded. Spreads are dropped.

usage: python3 build_databento.py DATABENTO.csv OUT.csv
  OUT.csv: datetime,open,high,low,close,volume,symbol (rbs.py reads it with NQ_DATA=OUT.csv)
"""
import sys
import numpy as np
import pandas as pd

PX = ['open', 'high', 'low', 'close']


def session(ts):
    """New York trading session date: 18:00 ET opens the next day's session."""
    return (ts.dt.tz_convert('America/New_York') + pd.Timedelta(hours=6)).dt.date


def build(path):
    d = pd.read_csv(path)
    d = d[~d.symbol.str.contains('-')].copy()
    d['datetime'] = pd.to_datetime(d.ts_event, utc=True)
    d['sess'] = session(d.datetime)
    vol = d.groupby(['sess', 'symbol']).volume.sum().unstack(fill_value=0)
    lead = vol.idxmax(axis=1)
    use = lead.shift().fillna(lead.iloc[0])            # previous session's leader: no look-ahead
    d = d[d.symbol.values == d.sess.map(use).values].sort_values('datetime').reset_index(drop=True)
    # back-adjust: walk the rolls from the newest to the oldest
    rolls = use[use != use.shift()].iloc[1:]
    raw = pd.read_csv(path, usecols=['ts_event', 'close', 'symbol'])
    raw = raw[~raw.symbol.str.contains('-')]
    raw['datetime'] = pd.to_datetime(raw.ts_event, utc=True)
    raw['sess'] = session(raw.datetime)
    adj = np.zeros(len(d))
    for s, new in rolls.items():
        old = use[use.index < s].iloc[-1]
        prev = use.index[use.index < s][-1]
        r = raw[raw.sess == prev].pivot_table(index='datetime', columns='symbol', values='close')[[old, new]].dropna()
        off = r[new].iloc[-1] - r[old].iloc[-1]
        adj[(d.sess < s).values] += off
        print(f'roll {old} -> {new} at session {s}: offset {off:+.2f} (last common minute {r.index[-1]})')
    for c in PX:
        d[c] = d[c] + adj
    return d[['datetime'] + PX + ['volume', 'symbol']]


if __name__ == '__main__':
    out = build(sys.argv[1])
    out.to_csv(sys.argv[2], index=False)
    print(f'{len(out)} rows, {out.datetime.iloc[0]} .. {out.datetime.iloc[-1]}')
