"""Remi's Buy/Sell split by Trend Judge state at the signal bar, with 1R / 1.5R / 2R / 3R targets.

  python3 trend_quadrants_tv.py NQ_1M.csv NQ_2M.csv
      TradingView "Export chart data" of Remi's Buy/Sell on NQ1! 1-minute and 2-minute charts (uses the
      exported BUY 訊號 / SELL 訊號 columns). Trend Judge is estimated from the export's own closes like
      rbs.py; on the 2m chart the 1m export's value is used where it covers the same time.
  python3 trend_quadrants_tv.py clean
      The same table on the NQ clean data (rbs.py).

Exits as trend_quadrants.py (stop = extreme of the signal bar and the one before, entry at the signal close,
stop first if both hit, 60-bar time exit). The first 2 New York dates of each file only warm up the EMAs.
"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODE = 'clean' if sys.argv[1] == 'clean' else 'tv'
import numpy as np, pandas as pd
from rbs import trend_diff_minutes, trend_judge, prepared, COST
from remi_export import signals

TARGETS = (1.0, 1.5, 2.0, 3.0)


def trades(df, B, S, horizon=60):
    h, l, c = df.high.values, df.low.values, df.close.values; out = []
    for i in np.where((B == 1) | (S == 1))[0]:
        if i < 1 or i + 10 > len(c) - 1: continue
        k = 1 if B[i] else -1
        stop = min(l[i - 1], l[i]) if k == 1 else max(h[i - 1], h[i])
        risk = (c[i] - stop) * k
        if not risk > 0: continue
        end = min(len(c) - 1, i + horizon); res = []
        for R in TARGETS:
            tgt = c[i] + k * R * risk; r = None
            for j in range(i + 1, end + 1):
                if (l[j] <= stop) if k == 1 else (h[j] >= stop): r = -1.0; break
                if (h[j] >= tgt) if k == 1 else (l[j] <= tgt): r = R; break
            res.append((c[end] - c[i]) * k / risk if r is None else r)
        out.append((i, k, risk, *res))
    return pd.DataFrame(out, columns=['i', 'side', 'risk'] + [f'r{R:g}' for R in TARGETS])


GROUPS = [('全部訊號', lambda t: t.side != 0),
          ('強UP + Buy', lambda t: (t.side == 1) & (t.dir == 2)), ('UP + Buy', lambda t: (t.side == 1) & (t.dir == 1)),
          ('強Down + Sell', lambda t: (t.side == -1) & (t.dir == -2)), ('DOWN + Sell', lambda t: (t.side == -1) & (t.dir == -1)),
          ('四象限 (順勢)', lambda t: t.side * t.dir > 0), ('一般兩象限', lambda t: t.side * t.dir == 1),
          ('強勢兩象限', lambda t: t.side * t.dir == 2), ('MIX', lambda t: t.dir == 0), ('逆勢', lambda t: t.side * t.dir < 0)]


def report(title, t, cost):
    print(f'\n=== {title}  停損中位數 {t.risk.median():.2f} 點, 成本 {cost} 點 ≈ {cost / t.risk.median():.2f}R')
    print(f'{"":<14} {"筆數":>4}  ' + '  '.join(f'{f"{R:g}R 勝率 平均":>15}' for R in TARGETS) + f'  {"2R扣成本":>8}')
    for name, f in GROUPS:
        g = t[f(t)]
        if len(g) == 0: print(f'{name:<14} {0:4d}'); continue
        cells = '  '.join(f'{100 * (g[f"r{R:g}"] > 0).mean():5.1f}% {g[f"r{R:g}"].mean():+.3f}' for R in TARGETS)
        print(f'{name:<14} {len(g):4d}  {cells}  {(g.r2 - cost / g.risk).mean():+8.3f}')


def load_tv(path):
    d = pd.read_csv(path)
    d['datetime'] = pd.to_datetime(d.time, unit='s', utc=True)
    return d


def warm_mask(dt, days=2):
    day = dt.dt.tz_convert('America/New_York').dt.date
    return ~day.isin(sorted(day.unique())[:days]).values


if MODE == 'tv':
    d1 = load_tv(sys.argv[1]); d2 = load_tv(sys.argv[2])
    # Trend Judge for the 1m chart from its own 1-minute closes
    one = d1.set_index('datetime')[['open', 'high', 'low', 'close']]
    tdm1 = trend_diff_minutes(one)
    b1 = d1[['datetime', 'open', 'high', 'low', 'close']].copy(); b1['last_min'] = b1.datetime
    b1 = trend_judge(b1, tdm1, 1, 'NQ')
    # Trend Judge for the 2m chart: 2m closes placed at the bar's last minute, minutes in between interpolated
    two = d2.set_index(d2.datetime + pd.Timedelta(minutes=1))[['open', 'high', 'low', 'close']]
    tdm2 = trend_diff_minutes(two)
    b2 = d2[['datetime', 'open', 'high', 'low', 'close']].copy(); b2['last_min'] = b2.datetime + pd.Timedelta(minutes=1)
    b2 = trend_judge(b2, tdm2, 2, 'NQ')
    # where the 1m file covers the 2m chart, the 1m-based value is closer to the real one: compare, then use it
    m = b2.last_min.isin(tdm1.index) & warm_mask(b2.datetime, 4)
    b2x = trend_judge(b2[['datetime', 'open', 'high', 'low', 'close', 'last_min']], tdm1.reindex(tdm1.index.union(b2.last_min)), 2, 'NQ')
    agree = (b2x.tj_dir[m] == b2.tj_dir[m]).mean()
    print(f'2m 圖趨勢：用 2 分收盤推算 vs 用 1 分收盤推算，重疊期間一致 {100 * agree:.1f}% ({m.sum()} 根)')
    b2.loc[m, 'tj_dir'] = b2x.tj_dir[m]
    for name, d, b in (('NQ 1m TradingView 匯出', d1, b1), ('NQ 2m TradingView 匯出', d2, b2)):
        B, S = d['BUY 訊號'].values, d['SELL 訊號'].values
        oB, oS = signals(d)
        print(f'{name}: 匯出訊號 {B.sum() + S.sum()}，用規則重算 {oB.sum() + oS.sum()}，同一根 {((B == 1) & (oB == 1)).sum() + ((S == 1) & (oS == 1)).sum()}')
        t = trades(d, B, S)
        t = t[warm_mask(d.datetime)[t.i]].reset_index(drop=True)
        t['dir'] = b.tj_dir.values[t.i]
        dd = d.datetime.dt.tz_convert('America/New_York')
        report(f'{name}  {dd[warm_mask(d.datetime)].iloc[0]:%m/%d}..{dd.iloc[-1]:%m/%d}', t, COST['NQ'])
else:
    for tf in (1, 2):
        df = prepared('NQ', tf); B, S = signals(df); t = trades(df, B, S)
        t = t[df.tradable.values[t.i]].reset_index(drop=True); t['dir'] = df.tj_dir.values[t.i]
        report(f'NQ {tf}m 乾淨資料 2/4..9/2', t, COST['NQ'])
