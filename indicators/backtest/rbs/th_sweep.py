"""Trend Judge threshold sweep for the filtered alerts on NQ 2 minutes (the Databento year).

  cd indicators/backtest
  NQ_DATA=data/NQ_1m_databento.csv python3 rbs/th_sweep.py

The signals are built once with the raw Trend Judge spread (5s - 15s EMA1130, locked per 2-minute bar),
so any threshold is just a cut on that number:
  有趨勢 mode   buy when spread > 一般, sell when spread < -一般   (強勢 does not matter in this mode)
  有強趨勢 mode  the same with 強勢
Other filters as the filtered alerts: last complete 1-hour close on the same side of its EMA20, stop >= 1 ATR.
Hours: all, or avoiding the data / open / close / Globex windows. Exits and costs from setup_study.py,
one position at a time, 1 point cost. 前 = 2025-10 .. 2026-05 (pick here), 後 = 2026-06 .. 10 (check here).
Prints
  1. one threshold for both sides, 0 .. 60 points, 1R / 2R / 3R
  2. separate thresholds for buys and sells
  3. an upper cap (skip spreads that are already very stretched)
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import pandas as pd
import rbs
import setup_study as ss
from remi_export import signals

TF = 2
CACHE = os.path.join(ss.DATA_DIR, 'th_sweep_2m.pkl')


def build():
    if os.path.exists(CACHE):
        return pd.read_pickle(CACHE)
    H = ss.hourly()
    df = rbs.prepared('NQ', TF)
    B, S = signals(df)
    h, l, c = df.high.values, df.low.values, df.close.values
    nxt, atr = ss.bar_context(df, TF)
    rows = []
    for i in np.where((B == 1) | (S == 1))[0]:
        if i < 15 or not df.tradable.values[i]: continue
        end = min(i + ss.HORIZON, nxt[i])
        if end <= i: continue
        k = 1 if B[i] else -1
        stop = min(l[i - 1], l[i]) if k == 1 else max(h[i - 1], h[i])
        risk = (c[i] - stop) * k
        if not risk > 0: continue
        rows.append([TF, i, k, risk, (h[i] - l[i]) / atr[i - 1], risk / atr[i - 1]] + ss.outcome(h, l, c, i, k, stop, end))
    cols = ['tf', 'i', 'side', 'risk', 'bar_atr', 'risk_atr']
    for R in ss.TARGETS: cols += [f'r{R:g}', f'x{R:g}']
    s = ss.add_context(pd.DataFrame(rows, columns=cols), df, TF, H)
    s['spread'] = df.tj_diff.values[s.i] * s.side          # Trend Judge spread in the trade's direction
    s = s.sort_values('i').reset_index(drop=True)
    s.attrs['days'] = (df.datetime[df.tradable].dt.tz_convert(ss.NY) + pd.Timedelta(hours=6)).dt.date.astype(str).nunique()
    s.to_pickle(CACHE)
    return s


def run(sub, R):
    t = ss.seq(sub, R)
    r = t[f'r{R:g}'].values; net = r - ss.COST / t.risk.values; a = t.date.values < ss.SPLIT
    m = lambda v: v.mean() if len(v) else np.nan
    return dict(n=len(t), win=m(r > 0), net=m(net), A=m(net[a]), B=m(net[~a]), tot=net.sum(),
                nb=(t.side == 1).sum(), ns=(t.side == -1).sum(),
                wb=m(r[t.side.values == 1] > 0), ws=m(r[t.side.values == -1] > 0),
                eb=m(net[t.side.values == 1]), es=m(net[t.side.values == -1]))


def row(name, m):
    return (f'{name:<14} {m["n"]:5d} 筆  勝率 {100 * m["win"]:4.1f}%  每筆 {m["net"]:+.3f}R（前 {m["A"]:+.3f} 後 {m["B"]:+.3f}）'
            f'  合計 {m["tot"]:+6.1f}R | 多 {m["nb"]:4d} {100 * m["wb"]:4.1f}% {m["eb"]:+.3f}  空 {m["ns"]:4d} {100 * m["ws"]:4.1f}% {m["es"]:+.3f}')


def main():
    s = build()
    base = (s.side == s.h1) & (s.risk_atr >= 1.0)
    hours = {'全時段': s.side != 0, '避開事件時段': ~ss.EVT(s)}
    print(f'資料：{s.date.min()} .. {s.date.max()}，2 分 K，{s.attrs["days"]} 個交易日')
    print('spread 分布（訊號方向，點）：', ' '.join(f'{q:.0%}={v:.1f}' for q, v in s.spread.quantile([.1, .25, .5, .75, .9]).items()))

    print('\n######## 1. 同一個門檻（有趨勢：spread > 門檻），買賣共用')
    for hn, hm in hours.items():
        for R in (1.0, 2.0, 3.0):
            print(f'\n  {hn}，{R:g}R')
            for th in (0, 5, 10, 12.5, 15, 17.5, 20, 22.5, 25, 30, 35, 40, 50, 60):
                print('   ' + row(f'門檻 {th:g}', run(s[base & hm & (s.spread > th)], R)))
            print('   ' + row('不看 TJ', run(s[base & hm], R)))

    print('\n######## 2. 買、賣各自的門檻（避開事件時段，2R）：每筆淨 R，前 / 後')
    grid = (5, 10, 15, 20, 25, 30, 40)
    hm = hours['避開事件時段']
    print('    買\\賣 ' + ''.join(f'{g:>16g}' for g in grid))
    for tb in grid:
        cells = []
        for ts in grid:
            keep = ((s.side == 1) & (s.spread > tb)) | ((s.side == -1) & (s.spread > ts))
            m = run(s[base & hm & keep], 2.0)
            cells.append(f'{m["net"]:+.3f}({m["A"]:+.2f}/{m["B"]:+.2f})')
        print(f'    {tb:>4g} ' + ''.join(f'{c:>16}' for c in cells))

    print('\n######## 3. 上限：spread 太大就不做（避開事件時段，2R）')
    for th in (10, 15, 20):
        for cap in (40, 60, 80, 100, 150, np.inf):
            print('   ' + row(f'{th:g} < s < {cap:g}', run(s[base & hm & (s.spread > th) & (s.spread < cap)], 2.0)))


if __name__ == '__main__':
    main()
